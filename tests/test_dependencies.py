import ast
import sys
from importlib.metadata import packages_distributions, requires
from pathlib import Path
from typing import Set

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

PACKAGE = Path(__file__).parent.parent / "move"


def _imported_modules() -> Set[str]:
    modules: Set[str] = set()
    for file in PACKAGE.rglob("*.py"):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module is not None:
                modules.add(node.module.split(".")[0])
    return {module for module in modules
            if module not in sys.stdlib_module_names and module != "move"}


def _declared_dependencies() -> Set[str]:
    declared: Set[str] = set()
    for line in requires("move") or []:
        requirement = Requirement(line)
        # Skip optional dependencies (extras)
        if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
            declared.add(canonicalize_name(requirement.name))
    return declared


def test_all_imports_are_declared_dependencies() -> None:
    """
    A module that is only installed as a dependency of a (test) dependency works in development, but not for users.
    """
    distributions = packages_distributions()
    declared = _declared_dependencies()
    undeclared = {}
    for module in sorted(_imported_modules()):
        names = {canonicalize_name(name) for name in distributions.get(module, [])}
        if not names & declared:
            undeclared[module] = sorted(names) or ["not installed"]
    assert undeclared == {}, f"Imported, but not declared in pyproject.toml dependencies: {undeclared}"
