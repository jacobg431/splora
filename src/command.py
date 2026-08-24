from __future__ import annotations

from abc import ABC, abstractmethod

from src.escalation import Response
from src.outcome import Outcome


class Command(ABC):
    """A command that can be run, cancelled when safe, and abandoned outright."""

    @abstractmethod
    def run(self) -> Outcome:
        """Carry out the command and report its result."""

    @abstractmethod
    def cancel(self) -> Response:
        """Stop as soon as it is safe to do so, keeping whatever is already valid."""

    @abstractmethod
    def abandon(self) -> Response:
        """Give up in-flight work now, leaving nothing half-written behind."""
