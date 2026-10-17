from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from test.lint.contracts import FailureMessage


@dataclass(frozen=True)
class _Layer:
    """A named tier of modules that may import only from the tiers below it."""

    name: str
    modules: tuple[str, ...]


# Ordered from the lowest tier upwards: a module may import only from a layer listed before its
# own. Add a module by naming it in its tier; add a tier by inserting a row at the right height.
_LAYERS: tuple[_Layer, ...] = (
    _Layer("primitives", ("src", "src.escalation", "src.outcome", "src.record", "src.terminal")),
    _Layer("components", ("src.banner", "src.command", "src.progress")),
    _Layer("runtime", ("src.frame",)),
    _Layer("commands", ("src.boot", "src.explore", "src.report")),
    _Layer("entry point", ("splora",)),
)


@dataclass(frozen=True)
class _Import:
    """An import statement and the first-party modules it depends on."""

    path: Path
    lineno: int
    name: str
    module: str
    targets: tuple[str, ...]
    is_nested: bool


@dataclass(frozen=True)
class _Violation:
    """A source location a rule rejected, described in the terms of that rule."""

    path: Path
    lineno: int
    name: str


def _module_name(path: Path) -> str:
    """Return the dotted module name that a repository-relative path defines."""
    parts = path.with_suffix("").parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _is_production(path: Path) -> bool:
    """Report whether a scanned file is shipped code rather than a test."""
    return path.parts[0] != "test"


def _statement_name(node: ast.Import | ast.ImportFrom) -> str:
    """Return the imported name to quote back when a rule rejects an import statement."""
    if isinstance(node, ast.Import):
        return ", ".join(alias.name for alias in node.names)
    return "." * node.level + (node.module or "")


def _base_module(node: ast.ImportFrom, module: str) -> str:
    """Return the absolute module an import statement reads from, resolving relative ones."""
    if not node.level:
        return node.module or ""
    package = module.split(".")[: -node.level]
    return ".".join([*package, node.module] if node.module else package)


def _targets(node: ast.Import | ast.ImportFrom, module: str, known: frozenset[str]) -> list[str]:
    """Return the first-party modules a single import statement depends on."""
    if isinstance(node, ast.Import):
        return [alias.name for alias in node.names if alias.name in known]
    base = _base_module(node, module)
    found = [f"{base}.{alias.name}" for alias in node.names if f"{base}.{alias.name}" in known]
    if not found and base in known:
        found = [base]
    return found


def _walk_imports(node: ast.AST, inside_function: bool) -> Iterator[tuple[ast.stmt, bool]]:
    """Yield every import statement under a node, flagged when it sits inside a function body."""
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.Import | ast.ImportFrom):
            yield child, inside_function
        is_function = isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
        yield from _walk_imports(child, inside_function or is_function)


def _names_conftest(node: ast.Import | ast.ImportFrom) -> bool:
    """Report whether an import statement reads from a conftest module, which only pytest loads."""
    if isinstance(node, ast.Import):
        return any(alias.name.split(".")[-1] == "conftest" for alias in node.names)
    if node.module and node.module.split(".")[-1] == "conftest":
        return True
    return any(alias.name == "conftest" for alias in node.names)


def _statement_names_conftest(statement: str) -> bool:
    """Report whether an import statement written as source text reads from a conftest module."""
    node = ast.parse(statement).body[0]
    assert isinstance(node, ast.Import | ast.ImportFrom)
    return _names_conftest(node)


def _layer_index(module: str) -> int | None:
    """Return the position of the layer a module is declared in, or None when it has none."""
    for index, layer in enumerate(_LAYERS):
        if module in layer.modules:
            return index
    return None


def _declared() -> list[str]:
    """Return every module named by the layer map, including any named more than once."""
    return [module for layer in _LAYERS for module in layer.modules]


@pytest.fixture(scope="session")
def production_modules(parsed_files: tuple[tuple[Path, ast.Module], ...]) -> frozenset[str]:
    """Return the dotted names of every module that ships as part of the tool."""
    return frozenset(_module_name(path) for path, _ in parsed_files if _is_production(path))


@pytest.fixture(scope="session")
def imports(
    parsed_files: tuple[tuple[Path, ast.Module], ...], production_modules: frozenset[str]
) -> tuple[_Import, ...]:
    """Return every import statement in the scanned files with its first-party targets."""
    found: list[_Import] = []
    for path, tree in parsed_files:
        module = _module_name(path)
        for node, is_nested in _walk_imports(tree, inside_function=False):
            assert isinstance(node, ast.Import | ast.ImportFrom)
            found.append(
                _Import(
                    path=path,
                    lineno=node.lineno,
                    name=_statement_name(node),
                    module=module,
                    targets=tuple(_targets(node, module, production_modules)),
                    is_nested=is_nested,
                )
            )
    return tuple(found)


def test_imports_are_declared_at_module_level(
    imports: tuple[_Import, ...], failure_message: FailureMessage
) -> None:
    offenders = [record for record in imports if record.is_nested]
    assert not offenders, failure_message("an import is declared inside a function", offenders)


@pytest.mark.parametrize(
    ("statement", "expected"),
    [
        ("from test.lint.conftest import FailureMessage", True),
        ("from .conftest import FailureMessage", True),
        ("from test.lint import conftest", True),
        ("from . import conftest", True),
        ("import test.lint.conftest", True),
        ("from test.lint.contracts import FailureMessage", False),
        ("import conftest_helpers", False),
    ],
)
def test_the_conftest_check_recognises_every_import_form(statement: str, expected: bool) -> None:
    assert _statement_names_conftest(statement) is expected


def test_no_module_imports_a_conftest(
    parsed_files: tuple[tuple[Path, ast.Module], ...], failure_message: FailureMessage
) -> None:
    offenders = [
        _Violation(path=path, lineno=node.lineno, name=ast.unparse(node))
        for path, tree in parsed_files
        for node, _ in _walk_imports(tree, inside_function=False)
        if isinstance(node, ast.Import | ast.ImportFrom) and _names_conftest(node)
    ]
    assert not offenders, failure_message(
        "a module imports a conftest; move the shared types into the tier's contracts.py",
        offenders,
    )


def test_every_module_declares_a_layer(production_modules: frozenset[str]) -> None:
    undeclared = sorted(production_modules - set(_declared()))
    assert not undeclared, f"modules absent from the layer map: {', '.join(undeclared)}"


def test_the_layer_map_names_only_existing_modules(production_modules: frozenset[str]) -> None:
    stale = sorted(set(_declared()) - production_modules)
    assert not stale, f"layer map names modules that do not exist: {', '.join(stale)}"


def test_no_module_is_declared_in_two_layers(production_modules: frozenset[str]) -> None:
    declared = _declared()
    repeated = sorted({module for module in declared if declared.count(module) > 1})
    assert not repeated, f"modules declared in more than one layer: {', '.join(repeated)}"


def test_modules_import_only_from_lower_layers(
    imports: tuple[_Import, ...], failure_message: FailureMessage
) -> None:
    offenders: list[_Violation] = []
    for record in imports:
        source = _layer_index(record.module)
        if not _is_production(record.path) or source is None:
            continue
        for target in record.targets:
            destination = _layer_index(target)
            if destination is None or destination < source:
                continue
            offenders.append(
                _Violation(
                    path=record.path,
                    lineno=record.lineno,
                    name=(
                        f"{record.module} ({_LAYERS[source].name}) imports "
                        f"{target} ({_LAYERS[destination].name})"
                    ),
                )
            )
    assert not offenders, failure_message("an import does not point to a lower layer", offenders)
