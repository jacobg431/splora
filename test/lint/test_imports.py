from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest


@dataclass(frozen=True)
class _Layer:
    """A named tier of modules that may import only from the tiers below it."""

    name: str
    modules: tuple[str, ...]


# Ordered from the lowest tier upwards: a module may import only from a layer listed before its
# own. Add a module by naming it in its tier; add a tier by inserting a row at the right height.
_LAYERS: tuple[_Layer, ...] = (
    _Layer("primitives", ("src", "src.outcome", "src.terminal")),
    _Layer("components", ("src.banner", "src.progress")),
    _Layer("commands", ("src.boot", "src.explore", "src.frame", "src.report")),
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


def test_imports_are_declared_at_module_level(imports, failure_message):
    offenders = [record for record in imports if record.is_nested]
    assert not offenders, failure_message("an import is declared inside a function", offenders)


def test_every_module_declares_a_layer(production_modules):
    undeclared = sorted(production_modules - set(_declared()))
    assert not undeclared, f"modules absent from the layer map: {', '.join(undeclared)}"


def test_the_layer_map_names_only_existing_modules(production_modules):
    stale = sorted(set(_declared()) - production_modules)
    assert not stale, f"layer map names modules that do not exist: {', '.join(stale)}"


def test_no_module_is_declared_in_two_layers(production_modules):
    declared = _declared()
    repeated = sorted({module for module in declared if declared.count(module) > 1})
    assert not repeated, f"modules declared in more than one layer: {', '.join(repeated)}"


def test_modules_import_only_from_lower_layers(imports, failure_message):
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
