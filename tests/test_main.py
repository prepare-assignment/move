import json
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
