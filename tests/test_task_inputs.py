import ast
from pathlib import Path
from typing import Set

import yaml

ROOT = Path(__file__).parent.parent


def _declared_inputs() -> Set[str]:
    task = yaml.safe_load((ROOT / "task.yml").read_text(encoding="utf-8"))
    return set((task.get("inputs") or {}).keys())


def _read_inputs() -> Set[str]:
    """All literal keys passed to get_input(...) in the task's code"""
    task = yaml.safe_load((ROOT / "task.yml").read_text(encoding="utf-8"))
    package = (ROOT / task["runs"]["main"]).parent
    keys: Set[str] = set()
    for file in package.rglob("*.py"):
        for node in ast.walk(ast.parse(file.read_text(encoding="utf-8"))):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "get_input"
                    and node.args and isinstance(node.args[0], ast.Constant)):
                keys.add(node.args[0].value)
    return keys


def test_read_inputs_are_declared() -> None:
    """
    An input that is read under a different name than in task.yml is silently ignored, e.g.
    'allow_outside_working_directory' instead of 'allow-outside-working-directory'.
    """
    read = _read_inputs()
    assert read, "No get_input calls found"
    assert read - _declared_inputs() == set()


def test_declared_inputs_are_read() -> None:
    """An input in task.yml that the code never reads doesn't do anything"""
    assert _declared_inputs() - _read_inputs() == set()
