from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from test.lint.contracts import FailureMessage

# Raise or lower this one number to retune how much annotation nesting the tier allows.
_MAX_SHAPE_SCORE = 3


@dataclass(frozen=True)
class _Violation:
    """A source location a rule rejected, described in the terms of that rule."""

    path: Path
    lineno: int
    name: str


def _slice_elements(node: ast.Subscript) -> list[ast.expr]:
    """Return the expressions inside a subscript's brackets, one per comma-separated slot."""
    inner = node.slice
    return list(inner.elts) if isinstance(inner, ast.Tuple) else [inner]


def _union_arms(node: ast.BinOp) -> list[ast.expr]:
    """Return every arm of a union expression, flattening nested bitwise-or operands."""
    arms: list[ast.expr] = []
    for side in (node.left, node.right):
        if isinstance(side, ast.BinOp) and isinstance(side.op, ast.BitOr):
            arms.extend(_union_arms(side))
        else:
            arms.append(side)
    return arms


def _subscript_score(node: ast.Subscript) -> int:
    """Return one level above the deepest argument inside a generic's brackets."""
    return 1 + max((_score(element) for element in _slice_elements(node)), default=0)


def _union_score(node: ast.BinOp) -> int:
    """Return one level per extra arm above the deepest arm of a `|` union."""
    arms = _union_arms(node)
    return (len(arms) - 1) + max(_score(arm) for arm in arms)


def _parameter_list_score(node: ast.List) -> int:
    """Return the deepest argument score of a `Callable` parameter list, adding no level itself."""
    return max((_score(element) for element in node.elts), default=0)


def _score(node: ast.expr) -> int:
    """Return how deeply an annotation expression nests generics and unions."""
    if isinstance(node, ast.Subscript):
        return _subscript_score(node)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _union_score(node)
    if isinstance(node, ast.List):
        return _parameter_list_score(node)
    return 0


def _is_any(node: ast.AST | None) -> bool:
    """Report whether an expression is the bare name Any."""
    return isinstance(node, ast.Name) and node.id == "Any"


def _is_callable(node: ast.expr) -> bool:
    """Report whether an expression names the Callable type constructor."""
    if isinstance(node, ast.Name):
        return node.id == "Callable"
    return isinstance(node, ast.Attribute) and node.attr == "Callable"


def _annotation_exprs(tree: ast.Module) -> Iterator[ast.expr]:
    """Yield every annotation expression in a module: parameters, returns, and AnnAssign."""
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            args = node.args
            for arg in (*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg):
                if arg is not None and arg.annotation is not None:
                    yield arg.annotation
            if node.returns is not None:
                yield node.returns
        elif isinstance(node, ast.AnnAssign):
            yield node.annotation


def _callable_subscripts(tree: ast.Module) -> Iterator[ast.Subscript]:
    """Yield every Callable subscript expression anywhere in a module."""
    for node in ast.walk(tree):
        if isinstance(node, ast.Subscript) and _is_callable(node.value):
            yield node


def _elides_parameters(node: ast.Subscript) -> bool:
    """Report whether a Callable subscript leaves its parameter list as a literal ellipsis."""
    elements = _slice_elements(node)
    return (
        bool(elements) and isinstance(elements[0], ast.Constant) and elements[0].value is Ellipsis
    )


def _callable_return(node: ast.Subscript) -> ast.expr | None:
    """Return the return-type expression of a Callable subscript, when it has one."""
    elements = _slice_elements(node)
    return elements[1] if len(elements) > 1 else None


def _score_of(annotation: str) -> int:
    """Return the shape score of an annotation written as source text."""
    return _score(ast.parse(annotation, mode="eval").body)


def test_the_shape_score_stays_calibrated_against_annotations_that_must_pass() -> None:
    assert _score_of("tuple[tuple[Path, ast.Module], ...]") == 2
    assert _score_of("Callable[[Command], AbstractContextManager[None]]") == 2
    assert _score_of("Callable[[str, Sequence[Offender]], str]") == 2
    assert _MAX_SHAPE_SCORE == 3


def test_the_shape_score_flags_a_union_buried_in_a_container() -> None:
    assert _score_of("Iterator[dict[str, str | Path | int]]") == 4
    assert _score_of("list[dict[str, list[tuple[int, str]]]]") == 4


def test_annotations_do_not_nest_generics_deeply(
    parsed_files: tuple[tuple[Path, ast.Module], ...], failure_message: FailureMessage
) -> None:
    offenders: list[_Violation] = []
    for path, tree in parsed_files:
        for annotation in _annotation_exprs(tree):
            score = _score(annotation)
            if score <= _MAX_SHAPE_SCORE:
                continue
            offenders.append(
                _Violation(
                    path=path,
                    lineno=annotation.lineno,
                    name=f"{ast.unparse(annotation)} scores {score}",
                )
            )
    assert not offenders, failure_message(
        "an annotation nests generics and unions past the shape-score limit", offenders
    )


def test_callables_are_not_typed_as_any(
    parsed_files: tuple[tuple[Path, ast.Module], ...], failure_message: FailureMessage
) -> None:
    offenders = [
        _Violation(path=path, lineno=node.lineno, name=ast.unparse(node))
        for path, tree in parsed_files
        for node in _callable_subscripts(tree)
        if _elides_parameters(node) and _is_any(_callable_return(node))
    ]
    assert not offenders, failure_message(
        "a Callable states neither its parameters nor its return type", offenders
    )


def test_callables_declare_their_parameters(
    parsed_files: tuple[tuple[Path, ast.Module], ...], failure_message: FailureMessage
) -> None:
    offenders = [
        _Violation(path=path, lineno=node.lineno, name=ast.unparse(node))
        for path, tree in parsed_files
        for node in _callable_subscripts(tree)
        if _elides_parameters(node) and not _is_any(_callable_return(node))
    ]
    assert not offenders, failure_message(
        "a Callable elides its parameter list with ...; spell the parameters or write a Protocol",
        offenders,
    )


def test_production_code_does_not_bury_any(
    parsed_files: tuple[tuple[Path, ast.Module], ...], failure_message: FailureMessage
) -> None:
    offenders: list[_Violation] = []
    for path, tree in parsed_files:
        if path.parts[0] != "src":
            continue
        for annotation in _annotation_exprs(tree):
            if _is_any(annotation):
                continue
            if any(_is_any(node) for node in ast.walk(annotation)):
                offenders.append(
                    _Violation(path=path, lineno=annotation.lineno, name=ast.unparse(annotation))
                )
    assert not offenders, failure_message(
        "src/ hides Any inside a larger annotation instead of stating it outright", offenders
    )
