from __future__ import annotations

from dataclasses import dataclass

# The exit codes the tool issues. 2 is absent because argparse claims it for usage errors, and
# 130 is the POSIX convention of 128 plus the signal number for SIGINT.
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_PARTIAL = 3
EXIT_INTERRUPTED = 130


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
