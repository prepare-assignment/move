import os
import sys
import tempfile
from pathlib import Path
import time
from typing import List

import pytest
from _pytest.monkeypatch import MonkeyPatch
from pytest_mock import MockerFixture

from move import main
from move.main import move


def setup_temp(path: str) -> None:
    """
    Set up a temporary directory structure for testing
    path
    |- test.txt
    |- a.txt
    |- out
    |   |-
    |- in
    |  |- a.txt
    |  |- b.txt
    |  | nested
    |  |  | - c.txt
    :param path: path to the temporary root dir
    :return: None
    """
    out_dir = os.path.join(path, "out")
    os.mkdir(out_dir)
    Path(os.path.join(path, "test.txt")).touch()
    Path(os.path.join(path, "a.txt")).touch()
    in_dir = os.path.join(path, "in")
    os.mkdir(in_dir)
    Path(os.path.join(in_dir, "a.txt")).touch()
    Path(os.path.join(in_dir, "b.txt")).touch()
    nested_dir = os.path.join(in_dir, "nested")
    os.mkdir(nested_dir)
    Path(os.path.join(nested_dir, "c.txt")).touch()


@pytest.mark.parametrize(
    "source, destination, force, expected",
    [
        ("test.txt", "new.txt", True, ["new.txt"]),  # rename
        ("test.txt", "in/a.txt", True, [os.path.join("in", "a.txt")]),  # overwrite
        ("test.txt", "out", True, [os.path.join("out", "test.txt")]),  # move one file
        ("in/nested/c.txt", "out", True, [os.path.join("out", "c.txt")]),  # move deeper nested file
        ("in/*", "out", True, [
            os.path.join("out", "a.txt"),
            os.path.join("out", "b.txt"),
            os.path.join("out", "nested")
        ]),  # move multiple files
        ("in", "out", True, [os.path.join("out", "in")]),  # move directory
    ]
)
def test_move_success(source: str,
                      destination: str,
                      force: bool,
                      expected: List[str],
                      monkeypatch: MonkeyPatch,
                      mocker: MockerFixture) -> None:
    def __get_input(key: str):
        if key == "source":
            return source
        elif key == "destination":
            return destination
        else:
            return force

    mocker.patch('move.main.get_input', side_effect=__get_input)
    spy = mocker.patch("move.main.set_output")
    old_cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tempdir:
        monkeypatch.chdir(tempdir)
        setup_temp(tempdir)
        move()
        # We need to do this otherwise it won't work on Windows......
        monkeypatch.chdir(old_cwd)
    spy.assert_called_once_with("paths", expected)


@pytest.mark.parametrize(
    "source, destination, force",
    [
        ("test.txt", "in/a.txt", False),  # destination already exists
        ("a.txt", "in", False),  # file already exists in destination directory
        ("d.txt", "in", False),  # file doesn't exist
    ]
)
def test_move_fail(source: str,
                   destination: str,
                   force: bool,
                   monkeypatch: MonkeyPatch,
                   mocker: MockerFixture,
                   capsys: pytest.CaptureFixture) -> None:
    def __get_input(key: str):
        if key == "source":
            return source
        elif key == "destination":
            return destination
        else:
            return force

    mocker.patch('move.main.get_input', side_effect=__get_input)
    #spy = mocker.patch("move.main.set_failed", side_effect=SystemExit())
    spy = mocker.spy(main, "set_failed")
    old_cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tempdir:
        monkeypatch.chdir(tempdir)
        setup_temp(tempdir)
        with pytest.raises(SystemExit):
            move()
        monkeypatch.chdir(old_cwd)
    spy.assert_called_once()


def test_other_exception(mocker: MockerFixture) -> None:
    def __get_input():
        raise Exception("test")

    mocker.patch('move.main.get_input', side_effect=__get_input)
    spy = mocker.spy(main, "set_failed")
    with pytest.raises(SystemExit):
        move()
    spy.assert_called_once()
