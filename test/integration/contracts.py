from __future__ import annotations

import argparse
from collections.abc import Callable
from typing import Protocol

from src.command import Command
from src.escalation import Response


class NameArgs(Protocol):
    """Builds the argument namespace for a command whose only option is --name."""

    def __call__(self, name: str | None = None) -> argparse.Namespace: ...


AssertInterruptResponse = Callable[[Command, str, Response, str | None], None]
