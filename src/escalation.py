from __future__ import annotations

import contextlib
import os
import signal
from collections.abc import Callable, Iterator
from types import FrameType

_STDERR_FD = 2
_KILL_NOTICE = b"\nKilled.\n"


@contextlib.contextmanager
def escalating(
    *,
    cancel: Callable[[], None],
    abandon: Callable[[], None],
    kill_code: int,
    exit_now: Callable[[int], None],
) -> Iterator[None]:
    """Route the first Ctrl+C to cancel, the second to abandon, and the third to a hard kill."""
    presses = 0

    def press(_signum: int, _frame: FrameType | None) -> None:
        nonlocal presses
        presses += 1
        if presses == 1:
            cancel()
        elif presses == 2:
            abandon()
        else:
            os.write(_STDERR_FD, _KILL_NOTICE)
            exit_now(kill_code)

    previous = signal.signal(signal.SIGINT, press)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, previous)
