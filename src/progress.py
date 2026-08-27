from __future__ import annotations

import time
from collections.abc import Callable
from typing import TextIO

from src.terminal import MUTED, format_bytes, format_throughput, paint

_REDRAW_INTERVAL = 0.1


def _should_redraw(last_redraw: float | None, now: float) -> bool:
    if last_redraw is None:
        return True
    return now - last_redraw >= _REDRAW_INTERVAL


class Progress:
    """A running count of a scan, redrawn in place on a single line while it proceeds."""

    def __init__(
        self,
        stream: TextIO,
        *,
        use_color: bool,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._stream = stream
        self._use_color = use_color
        self._clock = clock
        self._renders = stream.isatty()
        self._files = 0
        self._bytes = 0
        self._started = clock()
        self._last_redraw: float | None = None
        self._widest = 0

    def record(self, size: int) -> None:
        """Count one more scanned file, redrawing the line when the interval has elapsed."""
        self._files += 1
        self._bytes += size
        if not self._renders:
            return
        now = self._clock()
        if _should_redraw(self._last_redraw, now):
            self._last_redraw = now
            self._redraw(now)

    def finish(self) -> None:
        """Erase the line so whatever prints next starts on a clean row."""
        if not self._renders:
            return
        self._stream.write("\r" + " " * self._widest + "\r")
        self._stream.flush()

    def line(self, now: float) -> str:
        """Return the counts as they read at a given moment."""
        elapsed = now - self._started
        throughput = self._bytes / elapsed if elapsed > 0 else 0.0
        return (
            f"  Scanning: {self._files:,} files  {elapsed:.1f}s  "
            f"{format_bytes(self._bytes)}  {format_throughput(throughput)}"
        )

    def _redraw(self, now: float) -> None:
        text = self.line(now)
        self._widest = max(self._widest, len(text))
        self._stream.write("\r" + paint(text.ljust(self._widest), MUTED, use_color=self._use_color))
        self._stream.flush()
