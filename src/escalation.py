from __future__ import annotations

import contextlib
import enum
import os
import signal
from collections.abc import Callable, Iterator
from types import FrameType

_STDERR_FD = 2
_KILL_NOTICE = b"\nKilled.\n"


class Response(enum.Enum):
    """What a command's answer to a press means for the run."""

    HANDLED = enum.auto()
    UNWIND = enum.auto()


class Interrupt(KeyboardInterrupt):
    """A Ctrl+C that the run frame is expected to catch."""


class Cancel(Interrupt):
    """Raised by escalation when a first Ctrl+C's cancel() answers UNWIND."""


class Abandon(Interrupt):
    """Raised by escalation when a second Ctrl+C's abandon() answers UNWIND."""


@contextlib.contextmanager
def escalating(
    *,
    cancel: Callable[[], Response],
    abandon: Callable[[], Response],
    kill_code: int,
    exit_now: Callable[[int], None],
) -> Iterator[None]:
    """Route the first Ctrl+C to cancel, the second to abandon, and the third to a hard kill."""
    presses = 0

    def press(_signum: int, _frame: FrameType | None) -> None:
        nonlocal presses
        presses += 1
        if presses == 1:
            if cancel() is Response.UNWIND:
                raise Cancel
        elif presses == 2:
            if abandon() is Response.UNWIND:
                raise Abandon
        else:
            os.write(_STDERR_FD, _KILL_NOTICE)
            exit_now(kill_code)

    previous = signal.signal(signal.SIGINT, press)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous)
