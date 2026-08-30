from __future__ import annotations

import ast
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

_EXEMPT = Path("src") / "escalation.py"


@dataclass(frozen=True)
class _Violation:
    """A source location a rule rejected, described in the terms of that rule."""

    path: Path
    lineno: int
    name: str


def _is_scanned(path: Path) -> bool:
    """Report whether a file is production code under src/, other than the exempt module."""
    return path.parts[0] == "src" and path != _EXEMPT


def _names_keyboard_interrupt(node: ast.expr) -> bool:
    """Report whether an except clause's type expression names KeyboardInterrupt."""
    if isinstance(node, ast.Name):
        return node.id == "KeyboardInterrupt"
    if isinstance(node, ast.Tuple):
        return any(_names_keyboard_interrupt(element) for element in node.elts)
    return False


def _except_handlers(tree: ast.Module) -> list[ast.ExceptHandler]:
    """Return every except handler anywhere in a module."""
    return [node for node in ast.walk(tree) if isinstance(node, ast.ExceptHandler)]


def test_no_broad_interrupt_catch_outside_escalation(
    parsed_files: tuple[tuple[Path, ast.Module], ...], failure_message: Callable[..., str]
) -> None:
    offenders = [
        _Violation(path=path, lineno=handler.lineno, name=f"except {ast.unparse(handler.type)}")
        for path, tree in parsed_files
        if _is_scanned(path)
        for handler in _except_handlers(tree)
        if handler.type is not None and _names_keyboard_interrupt(handler.type)
    ]
    assert not offenders, failure_message(
        "a broad except KeyboardInterrupt could silently downgrade an Abandon into a Cancel",
        offenders,
    )
