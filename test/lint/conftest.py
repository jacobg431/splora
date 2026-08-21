from __future__ import annotations

import ast
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol

import pytest

_REPO_ROOT = Path(__file__).parent.parent.parent
_SCANNED_DIRS = ("src", "test")
_SCANNED_MODULES = ("splora.py",)


class _Offender(Protocol):
    """A source location that a lint rule rejected."""

    path: Path
    lineno: int
    name: str


def _python_files() -> list[Path]:
    """Return every Python file the lint rules apply to."""
    files = [_REPO_ROOT / name for name in _SCANNED_MODULES]
    for directory in _SCANNED_DIRS:
        files.extend(sorted((_REPO_ROOT / directory).rglob("*.py")))
    return files


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Return the repository root that every scanned path is relative to."""
    return _REPO_ROOT


@pytest.fixture(scope="session")
def source_files() -> tuple[tuple[Path, str], ...]:
    """Return each scanned file as its repository-relative path paired with its text."""
    return tuple(
        (file.relative_to(_REPO_ROOT), file.read_text(encoding="utf-8")) for file in _python_files()
    )


@pytest.fixture(scope="session")
def parsed_files(source_files: tuple[tuple[Path, str], ...]) -> tuple[tuple[Path, ast.Module], ...]:
    """Return each scanned file as its repository-relative path paired with its syntax tree."""
    return tuple((path, ast.parse(text)) for path, text in source_files)


@pytest.fixture(scope="session")
def failure_message() -> Callable[[str, Sequence[_Offender]], str]:
    """Return a helper that renders a lint failure as a problem and the locations breaking it."""

    def render(problem: str, offenders: Sequence[_Offender]) -> str:
        lines = [f"{len(offenders)} violation(s) where {problem}:"]
        lines += [f"  {o.path}:{o.lineno} {o.name}" for o in offenders]
        return "\n".join(lines)

    return render
