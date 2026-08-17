from __future__ import annotations

import ast
import functools
import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent.parent
_SCANNED_DIRS = ("src", "test")
_SCANNED_MODULES = ("splora.py",)
_SENTENCE_END = re.compile(r"[.!?][\"')\]]*(?:\s|$)")


@dataclass(frozen=True)
class _Definition:
    """A class, function, or method declared in a scanned Python file."""

    path: Path
    lineno: int
    name: str
    is_class: bool
    is_nested: bool
    is_test_function: bool
    docstring: str | None


def _python_files() -> list[Path]:
    """Return every Python file the docstring rules apply to."""
    files = [_REPO_ROOT / name for name in _SCANNED_MODULES]
    for directory in _SCANNED_DIRS:
        files.extend(sorted((_REPO_ROOT / directory).rglob("*.py")))
    return files


def _visit(
    node: ast.AST, path: Path, in_test_file: bool, inside_function: bool
) -> Iterator[_Definition]:
    """Yield the definitions declared directly or indirectly under a node."""
    for child in ast.iter_child_nodes(node):
        is_function = isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
        if is_function or isinstance(child, ast.ClassDef):
            yield _Definition(
                path=path,
                lineno=child.lineno,
                name=child.name,
                is_class=not is_function,
                is_nested=inside_function,
                is_test_function=is_function and in_test_file and child.name.startswith("test_"),
                docstring=ast.get_docstring(child),
            )
            yield from _visit(child, path, in_test_file, inside_function or is_function)
        else:
            yield from _visit(child, path, in_test_file, inside_function)


@functools.cache
def _definitions() -> tuple[_Definition, ...]:
    """Return every class, function, and method across the scanned files."""
    found: list[_Definition] = []
    for file in _python_files():
        relative = file.relative_to(_REPO_ROOT)
        tree = ast.parse(file.read_text(encoding="utf-8"))
        in_test_file = relative.parts[0] == "test"
        found.extend(_visit(tree, relative, in_test_file, inside_function=False))
    return tuple(found)


def _sentences(docstring: str) -> int:
    """Return how many sentences a docstring contains."""
    return len(_SENTENCE_END.findall(docstring.strip()))


def _report(offenders: list[_Definition], problem: str) -> str:
    """Render a failure message listing every offending definition."""
    lines = [f"{len(offenders)} definition(s) where {problem}:"]
    lines += [f"  {d.path}:{d.lineno} {d.name}" for d in offenders]
    return "\n".join(lines)


def test_test_functions_have_no_docstring():
    offenders = [d for d in _definitions() if d.is_test_function and d.docstring]
    assert not offenders, _report(offenders, "a test function has a docstring")


def test_classes_have_a_docstring():
    offenders = [d for d in _definitions() if d.is_class and not d.docstring]
    assert not offenders, _report(offenders, "a class is missing a docstring")


def test_public_functions_and_methods_have_a_docstring():
    offenders = [
        d
        for d in _definitions()
        if not d.is_class
        and not d.is_nested
        and not d.is_test_function
        and not d.name.startswith("_")
        and not d.docstring
    ]
    assert not offenders, _report(offenders, "a public function or method is missing a docstring")


def test_docstrings_contain_exactly_one_sentence():
    offenders = [d for d in _definitions() if d.docstring and _sentences(d.docstring) != 1]
    assert not offenders, _report(offenders, "a docstring does not contain exactly one sentence")


def test_docstrings_are_a_single_line():
    offenders = [d for d in _definitions() if d.docstring and "\n" in d.docstring.strip()]
    assert not offenders, _report(offenders, "a docstring spans more than one line")
