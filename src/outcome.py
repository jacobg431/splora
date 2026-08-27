from __future__ import annotations

from dataclasses import dataclass

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_PARTIAL = 3
EXIT_INTERRUPTED = 130
EXIT_KILLED = 137


@dataclass(frozen=True)
class NextStep:
    """The command to run next, and the run name it applies to."""

    command: str
    name: str


@dataclass(frozen=True)
class Outcome:
    """The exit code a command reports, with the step it invites next."""

    code: int
    next_step: NextStep | None = None
