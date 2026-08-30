from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

import pytest

_TEST_ROOT = "test"
_DEFERRED_TIER = "test/end2end"
_MINIMUM_VERSION = re.compile(r">=\s*(\d+)\.(\d+)")


def _tiers(repo_root: Path) -> set[str]:
    """Return the test tier directories that exist in the repository."""
    return {
        f"{_TEST_ROOT}/{entry.name}"
        for entry in (repo_root / _TEST_ROOT).iterdir()
        if entry.is_dir() and not entry.name.startswith((".", "__"))
    }


@pytest.fixture(scope="session")
def pyproject(repo_root: Path) -> dict[str, Any]:
    """Return the parsed contents of the project's configuration file."""
    return tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def testpaths(pyproject: dict[str, Any]) -> list[str]:
    """Return the test directories the default suite runs."""
    return pyproject["tool"]["pytest"]["ini_options"]["testpaths"]


def test_the_project_declares_no_runtime_dependencies(pyproject: dict[str, Any]) -> None:
    declared = pyproject["project"]["dependencies"]
    assert declared == [], f"runtime dependencies declared: {', '.join(declared)}"


def test_runtime_dependencies_are_not_declared_dynamically(pyproject: dict[str, Any]) -> None:
    dynamic = pyproject["project"].get("dynamic", [])
    assert "dependencies" not in dynamic, "dependencies are dynamic, so their absence is unchecked"


def test_every_test_tier_runs_by_default_except_the_deferred_one(
    repo_root: Path, testpaths: list[str]
) -> None:
    absent = sorted(_tiers(repo_root) - set(testpaths) - {_DEFERRED_TIER})
    assert not absent, f"test tiers that never run in the default suite: {', '.join(absent)}"


def test_the_deferred_test_tier_is_invoked_explicitly(testpaths: list[str]) -> None:
    assert _DEFERRED_TIER not in testpaths, f"{_DEFERRED_TIER} runs in the default suite"


def test_the_python_version_is_declared_consistently(pyproject: dict[str, Any]) -> None:
    requires = pyproject["project"]["requires-python"]
    minimum = _MINIMUM_VERSION.search(requires)
    assert minimum, f"requires-python names no minimum version: {requires}"
    major, minor = minimum.groups()

    ruff = pyproject["tool"]["ruff"]["target-version"]
    assert ruff == f"py{major}{minor}", f"ruff targets {ruff}, but the project requires {requires}"

    mypy = pyproject["tool"]["mypy"]["python_version"]
    assert mypy == f"{major}.{minor}", f"mypy targets {mypy}, but the project requires {requires}"
