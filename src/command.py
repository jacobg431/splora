from __future__ import annotations

from abc import ABC, abstractmethod

from src.outcome import Outcome


class Interrupt(KeyboardInterrupt):
    """A Ctrl+C that the run frame is expected to catch."""


class Cancel(Interrupt):
    """A first Ctrl+C, raised by a command with no cooperative stopping point of its own."""


class Abandon(Interrupt):
    """A second Ctrl+C, discarding whatever work was in flight."""


class Command(ABC):
    """A command that can be run, cancelled when safe, and abandoned outright."""

    @abstractmethod
    def run(self) -> Outcome:
        """Carry out the command and report its result."""

    @abstractmethod
    def cancel(self) -> None:
        """Stop as soon as it is safe to do so, keeping whatever is already valid."""

    @abstractmethod
    def abandon(self) -> None:
        """Give up in-flight work now, leaving nothing half-written behind."""
