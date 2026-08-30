from __future__ import annotations

import io
import re
import tokenize
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

# Matched against comment tokens only, never against raw source text, so that the patterns
# written here as string literals are not read back as violations of the rule they describe.
_DIRECTIVE = re.compile(r"#\s*(noqa|type:\s*ignore|ruff:|mypy:|pylint:)", re.IGNORECASE)


@dataclass(frozen=True)
class _Suppression:
    """A comment that switches a checker off instead of addressing what it reported."""

    path: Path
    lineno: int
    name: str


def _comments(text: str) -> Iterator[tokenize.TokenInfo]:
    """Yield every comment token in a Python source file."""
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.COMMENT:
            yield token


def test_no_comment_switches_off_a_checker(source_files, failure_message) -> None:
    offenders = [
        _Suppression(path=path, lineno=token.start[0], name=token.string)
        for path, text in source_files
        for token in _comments(text)
        if _DIRECTIVE.search(token.string)
    ]
    assert not offenders, failure_message("a comment suppresses a checker", offenders)
