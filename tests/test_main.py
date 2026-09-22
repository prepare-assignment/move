import json
import os
from pathlib import Path
from typing import Any, Dict, List

import pytest
import yaml
from pytest_mock import MockerFixture

import prepare_move.main as move_main
from prepare_move.main import move

TASK = Path(__file__).parent.parent / "task.yml"


def set_inputs(monkeypatch: pytest.MonkeyPatch, **inputs: Any) -> None:
    """
    Pass the inputs like prepare-assignment core does: as JSON in PREPARE_<NAME> environment variables,
    including the defaults from task.yml. Use the names from task.yml, with '_' for '-'.
    """
    definition: Dict[str, Any] = yaml.safe_load(TASK.read_text(encoding="utf-8"))["inputs"]
    values = {name: spec["default"] for name, spec in definition.items() if "default" in spec}
    values.update({key.replace("_", "-"): value for key, value in inputs.items()})
    for key, value in values.items():
        if value is not None:
            monkeypatch.setenv(f"PREPARE_{key.upper()}", json.dumps(value))


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    project
    |- test.txt
    |- out
    |- in
    |  |- a.txt
    |  |- b.txt
    |  |- nested
    |     |- c.txt
    """
    (tmp_path / "out").mkdir()
    (tmp_path / "in" / "nested").mkdir(parents=True)
    for file in ["test.txt", "in/a.txt", "in/b.txt", "in/nested/c.txt"]:
        (tmp_path / file).write_text(file)
    monkeypatch.chdir(tmp_path)
    return tmp_path


def moved(set_output: Any) -> List[str]:
    """The paths output, as is: paths use '/' on every platform (they are used in other steps)"""
    set_output.assert_called_once()
    return list(set_output.call_args.args[1])


def test_rename_file(project: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    set_inputs(monkeypatch, source="test.txt", destination="new.txt")
    set_output = mocker.patch("prepare_move.main.set_output")
    move()
    assert moved(set_output) == ["new.txt"]
    assert (project / "new.txt").read_text() == "test.txt"
    assert not (project / "test.txt").exists()


def test_move_into_directory(project: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    set_inputs(monkeypatch, source="in/nested/c.txt", destination="out")
    set_output = mocker.patch("prepare_move.main.set_output")
    move()
    assert moved(set_output) == ["out/c.txt"]
    assert (project / "out" / "c.txt").read_text() == "in/nested/c.txt"
    assert not (project / "in" / "nested" / "c.txt").exists()


def test_move_several_files_into_directory(project: Path, monkeypatch: pytest.MonkeyPatch,
                                           mocker: MockerFixture) -> None:
    set_inputs(monkeypatch, source="in/*.txt", destination="out")
    set_output = mocker.patch("prepare_move.main.set_output")
    move()
    assert moved(set_output) == ["out/a.txt", "out/b.txt"]
    assert (project / "out" / "a.txt").read_text() == "in/a.txt"
    assert not (project / "in" / "a.txt").exists()


def test_move_directory(project: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    set_inputs(monkeypatch, source="in", destination="out")
    set_output = mocker.patch("prepare_move.main.set_output")
    move()
    assert moved(set_output) == ["out/in"]
    assert (project / "out" / "in" / "nested" / "c.txt").read_text() == "in/nested/c.txt"
    assert not (project / "in").exists()


def test_rename_directory(project: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    set_inputs(monkeypatch, source="in", destination="renamed")
    set_output = mocker.patch("prepare_move.main.set_output")
    move()
    assert moved(set_output) == ["renamed"]
    assert (project / "renamed" / "a.txt").read_text() == "in/a.txt"


def test_overwrite_file_with_force(project: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    set_inputs(monkeypatch, source="test.txt", destination="in/a.txt", force=True)
    set_output = mocker.patch("prepare_move.main.set_output")
    move()
    assert moved(set_output) == ["in/a.txt"]
    assert (project / "in" / "a.txt").read_text() == "test.txt"


def test_existing_file_without_force_fails(project: Path, monkeypatch: pytest.MonkeyPatch,
                                           mocker: MockerFixture) -> None:
    set_inputs(monkeypatch, source="test.txt", destination="in/a.txt", force=False)
    failed = mocker.spy(move_main, "set_failed")
    with pytest.raises(SystemExit):
        move()
    assert "already exists, use 'force' to overwrite" in failed.call_args.args[0]
    assert (project / "in" / "a.txt").read_text() == "in/a.txt"
    assert (project / "test.txt").exists()


def test_no_match_fails(project: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    set_inputs(monkeypatch, source="missing.txt", destination="out")
    failed = mocker.spy(move_main, "set_failed")
    with pytest.raises(SystemExit):
        move()
    assert "doesn't match any files" in failed.call_args.args[0]


def test_destination_outside_working_directory_fails(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    set_inputs(monkeypatch, source="test.txt", destination="..")
    with pytest.raises(SystemExit):
        move()
    assert (project / "test.txt").exists()


@pytest.mark.parametrize("destination", ["new.txt", "test.txt", "missing/dir"])
def test_several_files_to_non_directory_fails(destination: str, project: Path, monkeypatch: pytest.MonkeyPatch,
                                              mocker: MockerFixture) -> None:
    """Every file was moved onto the same path: all but the last one were lost"""
    set_inputs(monkeypatch, source="in/*.txt", destination=destination)
    failed = mocker.spy(move_main, "set_failed")
    with pytest.raises(SystemExit):
        move()
    assert (f"'in/*.txt' matches 2 files, the destination '{destination}' must be an existing directory"
            in failed.call_args.args[0])
    # Nothing is moved: the source files are still there
    assert (project / "in" / "a.txt").read_text() == "in/a.txt"
    assert (project / "in" / "b.txt").read_text() == "in/b.txt"
    assert (project / "test.txt").read_text() == "test.txt"
    assert not (project / "new.txt").exists()


def symlink(link: Path, target: str, directory: bool = False) -> None:
    try:
        # On Windows a link to a directory is only a directory link with target_is_directory, and the
        # target has to use the platform separator to be resolved
        link.symlink_to(target.replace("/", os.sep), target_is_directory=directory)
    except OSError:  # pragma: no cover
        pytest.skip("Creating symbolic links is not allowed (Windows without developer mode)")


@pytest.fixture
def linked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """
    tmp_path
    |- outside
    |  |- secret.txt
    |- project
       |- dest
       |- in
          |- a.txt
          |- dir-link -> ../../outside
    """
    (tmp_path / "outside").mkdir()
    (tmp_path / "outside" / "secret.txt").write_text("secret")
    (tmp_path / "project" / "dest").mkdir(parents=True)
    (tmp_path / "project" / "in").mkdir()
    (tmp_path / "project" / "in" / "a.txt").write_text("a")
    symlink(tmp_path / "project" / "in" / "dir-link", "../../outside", directory=True)
    monkeypatch.chdir(tmp_path / "project")
    return tmp_path


@pytest.mark.parametrize("source", ["in/**/*.txt", "in/dir-link/*"])
def test_files_behind_symlink_are_not_moved(source: str, linked: Path, monkeypatch: pytest.MonkeyPatch,
                                            mocker: MockerFixture) -> None:
    """Globs followed symbolic links and moved files out of a directory outside the working directory"""
    set_inputs(monkeypatch, source=source, destination="dest")
    set_output = mocker.patch("prepare_move.main.set_output")
    mocker.spy(move_main, "set_failed")
    move()
    assert (linked / "outside" / "secret.txt").read_text() == "secret"
    assert not any("secret" in path for path in moved(set_output))


def test_symlink_itself_is_moved(linked: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    set_inputs(monkeypatch, source="in/dir-link", destination="dest")
    set_output = mocker.patch("prepare_move.main.set_output")
    move()
    assert moved(set_output) == ["dest/dir-link"]
    assert (linked / "project" / "dest" / "dir-link").is_symlink()
    assert not (linked / "project" / "in" / "dir-link").exists()
    assert (linked / "outside" / "secret.txt").read_text() == "secret"


def test_files_behind_symlink_do_not_count_as_several_files(linked: Path, monkeypatch: pytest.MonkeyPatch,
                                                            mocker: MockerFixture) -> None:
    """'in/**/*.txt' matches a.txt and the secret.txt behind the link: only a.txt is really moved"""
    set_inputs(monkeypatch, source="in/**/*.txt", destination="renamed.txt")
    set_output = mocker.patch("prepare_move.main.set_output")
    failed = mocker.spy(move_main, "set_failed")
    move()
    failed.assert_not_called()
    assert moved(set_output) == ["renamed.txt"]
    assert (linked / "project" / "renamed.txt").read_text() == "a"
    assert (linked / "outside" / "secret.txt").read_text() == "secret"


def test_nothing_moved_when_a_file_exists_without_force(project: Path, monkeypatch: pytest.MonkeyPatch,
                                                        mocker: MockerFixture) -> None:
    """The existing file was only noticed after the files before it were moved"""
    (project / "out" / "b.txt").write_text("old")
    set_inputs(monkeypatch, source="in/*.txt", destination="out", force=False)
    with pytest.raises(SystemExit):
        move()
    assert (project / "in" / "a.txt").read_text() == "in/a.txt"
    assert (project / "out" / "b.txt").read_text() == "old"
    assert not (project / "out" / "a.txt").exists()


def test_directory_and_its_contents(project: Path, monkeypatch: pytest.MonkeyPatch,
                                    mocker: MockerFixture) -> None:
    """'in/**' matches the directory and its contents: after moving the directory the rest is gone"""
    set_inputs(monkeypatch, source="in/**", destination="out")
    set_output = mocker.patch("prepare_move.main.set_output")
    failed = mocker.spy(move_main, "set_failed")
    move()
    failed.assert_not_called()
    # 'in' is moved first (sorted), the paths in it are skipped: they moved along with the directory
    assert moved(set_output) == ["out/in"]
    assert (project / "out" / "in" / "nested" / "c.txt").read_text() == "in/nested/c.txt"
    assert (project / "out" / "in" / "a.txt").read_text() == "in/a.txt"
    assert not (project / "in").exists()


    assert not (project / "out" / "in" / "old.txt").exists()


def test_existing_directory_without_force_fails(project: Path, monkeypatch: pytest.MonkeyPatch,
                                                mocker: MockerFixture) -> None:
    (project / "out" / "in").mkdir()
    (project / "out" / "in" / "old.txt").write_text("old")
    set_inputs(monkeypatch, source="in", destination="out", force=False)
    failed = mocker.spy(move_main, "set_failed")
    with pytest.raises(SystemExit):
        move()
    assert "'out/in' already exists, use 'force' to overwrite" in failed.call_args.args[0]
    assert (project / "out" / "in" / "old.txt").read_text() == "old"
    assert (project / "in" / "a.txt").exists()


def test_file_does_not_overwrite_a_directory(project: Path, monkeypatch: pytest.MonkeyPatch,
                                             mocker: MockerFixture) -> None:
    """With force, a directory at the destination would be removed entirely; mv refuses this"""
    (project / "out" / "test.txt").mkdir()
    (project / "out" / "test.txt" / "keep.txt").write_text("keep")
    set_inputs(monkeypatch, source="test.txt", destination="out", force=True)
    failed = mocker.spy(move_main, "set_failed")
    with pytest.raises(SystemExit):
        move()
    assert "Cannot overwrite 'out/test.txt', it is a directory" in failed.call_args.args[0]
    assert (project / "out" / "test.txt" / "keep.txt").read_text() == "keep"
    assert (project / "test.txt").exists()


def test_directory_does_not_overwrite_a_file(project: Path, monkeypatch: pytest.MonkeyPatch,
                                             mocker: MockerFixture) -> None:
    (project / "out" / "in").write_text("a file")
    set_inputs(monkeypatch, source="in", destination="out", force=True)
    failed = mocker.spy(move_main, "set_failed")
    with pytest.raises(SystemExit):
        move()
    assert "Cannot overwrite 'out/in', it is a file" in failed.call_args.args[0]
    assert (project / "out" / "in").read_text() == "a file"
    assert (project / "in" / "a.txt").exists()


@pytest.fixture
def hidden(project: Path) -> Path:
    (project / "in" / ".gitignore").write_text("in/.gitignore")
    return project


def test_hidden_files_not_moved_by_default(hidden: Path, monkeypatch: pytest.MonkeyPatch,
                                           mocker: MockerFixture) -> None:
    set_inputs(monkeypatch, source="in/*", destination="out")
    set_output = mocker.patch("prepare_move.main.set_output")
    move()
    assert moved(set_output) == ["out/a.txt", "out/b.txt", "out/nested"]
    assert (hidden / "in" / ".gitignore").read_text() == "in/.gitignore"


def test_include_hidden(hidden: Path, monkeypatch: pytest.MonkeyPatch, mocker: MockerFixture) -> None:
    set_inputs(monkeypatch, source="in/*", destination="out", include_hidden=True)
    set_output = mocker.patch("prepare_move.main.set_output")
    move()
    assert moved(set_output) == ["out/.gitignore", "out/a.txt", "out/b.txt", "out/nested"]
    assert (hidden / "out" / ".gitignore").read_text() == "in/.gitignore"
    assert not (hidden / "in" / ".gitignore").exists()


def test_overwrite_file_in_directory_with_force(project: Path, monkeypatch: pytest.MonkeyPatch,
                                                mocker: MockerFixture) -> None:
    """Failed with 'Destination path out/a.txt already exists', because shutil.move got the directory"""
    (project / "out" / "a.txt").write_text("old")
    set_inputs(monkeypatch, source="in/a.txt", destination="out", force=True)
    set_output = mocker.patch("prepare_move.main.set_output")
    failed = mocker.spy(move_main, "set_failed")
    move()
    failed.assert_not_called()
    assert moved(set_output) == ["out/a.txt"]
    assert (project / "out" / "a.txt").read_text() == "in/a.txt"
    assert not (project / "in" / "a.txt").exists()


def test_existing_file_in_directory_without_force_fails(project: Path, monkeypatch: pytest.MonkeyPatch,
                                                        mocker: MockerFixture) -> None:
    (project / "out" / "a.txt").write_text("old")
    set_inputs(monkeypatch, source="in/a.txt", destination="out", force=False)
    failed = mocker.spy(move_main, "set_failed")
    with pytest.raises(SystemExit):
        move()
    assert "'out/a.txt' already exists, use 'force' to overwrite" in failed.call_args.args[0]
    assert (project / "out" / "a.txt").read_text() == "old"
    assert (project / "in" / "a.txt").exists()


def test_overwrite_directory_with_force(project: Path, monkeypatch: pytest.MonkeyPatch,
                                        mocker: MockerFixture) -> None:
    """force was never applied to directories: it failed with 'Destination path out/in already exists'"""
    (project / "out" / "in").mkdir()
    (project / "out" / "in" / "old.txt").write_text("old")
    set_inputs(monkeypatch, source="in", destination="out", force=True)
    set_output = mocker.patch("prepare_move.main.set_output")
    failed = mocker.spy(move_main, "set_failed")
    move()
    failed.assert_not_called()
    assert moved(set_output) == ["out/in"]
    assert (project / "out" / "in" / "a.txt").read_text() == "in/a.txt"
    assert not (project / "out" / "in" / "old.txt").exists()
