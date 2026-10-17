from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Protocol


class Offender(Protocol):
    """A source location that a lint rule rejected."""

    @property
    def path(self) -> Path:
        """The repository-relative file the violation is in."""

    @property
    def lineno(self) -> int:
        """The 1-indexed line the violation sits on."""

    @property
    def name(self) -> str:
        """The offending construct, phrased in the rule's own terms."""


FailureMessage = Callable[[str, Sequence[Offender]], str]
