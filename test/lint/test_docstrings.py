from __future__ import annotations

import ast
import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

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


def _sentences(docstring: str) -> int:
    """Return how many sentences a docstring contains."""
    return len(_SENTENCE_END.findall(docstring.strip()))


@pytest.fixture(scope="session")
def definitions(parsed_files: tuple[tuple[Path, ast.Module], ...]) -> tuple[_Definition, ...]:
    """Return every class, function, and method across the scanned files."""
    found: list[_Definition] = []
    for path, tree in parsed_files:
        found.extend(_visit(tree, path, path.parts[0] == "test", inside_function=False))
    return tuple(found)


def test_test_functions_have_no_docstring(
    definitions: tuple[_Definition, ...], failure_message: Callable[..., str]
) -> None:
    offenders = [d for d in definitions if d.is_test_function and d.docstring]
    assert not offenders, failure_message("a test function has a docstring", offenders)


def test_classes_have_a_docstring(
    definitions: tuple[_Definition, ...], failure_message: Callable[..., str]
) -> None:
    offenders = [d for d in definitions if d.is_class and not d.docstring]
    assert not offenders, failure_message("a class is missing a docstring", offenders)


def test_public_functions_and_methods_have_a_docstring(
    definitions: tuple[_Definition, ...], failure_message: Callable[..., str]
) -> None:
    offenders = [
        d
        for d in definitions
        if not d.is_class
        and not d.is_nested
        and not d.is_test_function
        and not d.name.startswith("_")
        and not d.docstring
    ]
    assert not offenders, failure_message(
        "a public function or method is missing a docstring", offenders
    )


def test_docstrings_contain_exactly_one_sentence(
    definitions: tuple[_Definition, ...], failure_message: Callable[..., str]
) -> None:
    offenders = [d for d in definitions if d.docstring and _sentences(d.docstring) != 1]
    assert not offenders, failure_message(
        "a docstring does not contain exactly one sentence", offenders
    )


def test_docstrings_are_a_single_line(
    definitions: tuple[_Definition, ...], failure_message: Callable[..., str]
) -> None:
    offenders = [d for d in definitions if d.docstring and "\n" in d.docstring.strip()]
    assert not offenders, failure_message("a docstring spans more than one line", offenders)
