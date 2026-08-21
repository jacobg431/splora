from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

_UNIT_TIER = ("test", "unit")
_DISALLOWED_FIXTURES = ("tmp_path", "tmp_path_factory")


@dataclass(frozen=True)
class _Restriction:
    """A standard-library module confined to the one test tier that drives it for real."""

    module: str
    tier: str


# These modules drive real processes, threads, or sockets, so only end2end may import them.
# Add a module by naming its owning tier here.
_RESTRICTED: tuple[_Restriction, ...] = (
    _Restriction("subprocess", "end2end"),
    _Restriction("threading", "end2end"),
    _Restriction("socket", "end2end"),
    _Restriction("urllib", "end2end"),
)


@dataclass(frozen=True)
class _Violation:
    """A source location a rule rejected, described in the terms of that rule."""

    path: Path
    lineno: int
    name: str


def _function_defs(tree: ast.Module) -> Iterator[ast.FunctionDef | ast.AsyncFunctionDef]:
    """Yield every function or method definition anywhere in a module."""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            yield node


def _parameter_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
    """Return every parameter name a function or method declares."""
    args = node.args
    return [a.arg for a in (*args.posonlyargs, *args.args, *args.kwonlyargs)]


def _import_nodes(tree: ast.Module) -> Iterator[ast.Import | ast.ImportFrom]:
    """Yield every import statement anywhere in a module."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Import | ast.ImportFrom):
            yield node


def _imported_modules(node: ast.Import | ast.ImportFrom) -> list[str]:
    """Return the dotted module names a single import statement names."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names]
    if node.level or not node.module:
        return []
    return [node.module]


def _module_matches(imported: str, restricted: str) -> bool:
    """Report whether an imported dotted name is the restricted module or one of its submodules."""
    return imported == restricted or imported.startswith(f"{restricted}.")


def _tier(path: Path) -> str | None:
    """Return the test tier a repository-relative path belongs to, or None outside test/."""
    parts = path.parts
    if len(parts) < 2 or parts[0] != "test":
        return None
    return parts[1]


def test_unit_tests_do_not_request_filesystem_fixtures(parsed_files, failure_message):
    offenders: list[_Violation] = []
    for path, tree in parsed_files:
        if path.parts[:2] != _UNIT_TIER:
            continue
        for node in _function_defs(tree):
            hit = [n for n in _parameter_names(node) if n in _DISALLOWED_FIXTURES]
            if hit:
                offenders.append(
                    _Violation(path=path, lineno=node.lineno, name=f"{node.name}({', '.join(hit)})")
                )
    assert not offenders, failure_message(
        "a test/unit function requests a filesystem-touching fixture", offenders
    )


def test_restricted_modules_are_imported_only_by_their_tier(parsed_files, failure_message):
    offenders: list[_Violation] = []
    for path, tree in parsed_files:
        tier = _tier(path)
        if tier is None:
            continue
        for node in _import_nodes(tree):
            for imported in _imported_modules(node):
                for restriction in _RESTRICTED:
                    if _module_matches(imported, restriction.module) and tier != restriction.tier:
                        offenders.append(
                            _Violation(
                                path=path,
                                lineno=node.lineno,
                                name=(
                                    f"test/{tier} imports {imported}, restricted to "
                                    f"test/{restriction.tier}"
                                ),
                            )
                        )
    assert not offenders, failure_message(
        "a restricted module is imported outside its owning tier", offenders
    )
