"""Unit tests for src/progress.py."""

from __future__ import annotations

import io

from src.progress import _REDRAW_INTERVAL, Progress, _should_redraw

_ESCAPE = "\x1b["


class _Terminal(io.StringIO):
    """A text buffer that presents itself as a terminal."""

    def isatty(self) -> bool:
        """Report the stream as a terminal."""
        return True


class _Clock:
    """A hand-wound clock standing in for the monotonic one."""

    def __init__(self, start: float = 0.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        """Move the clock forward."""
        self.now += seconds


def _on_terminal(clock: _Clock | None = None) -> tuple[Progress, _Terminal]:
    stream = _Terminal()
    return Progress(stream, use_color=False, clock=clock or _Clock()), stream


class TestShouldRedraw:
    """The throttle deciding whether the line is redrawn yet."""

    def test_redraws_when_it_has_never_been_drawn(self) -> None:
        assert _should_redraw(None, 0.0) is True

    def test_holds_back_before_the_interval_elapses(self) -> None:
        assert _should_redraw(0.0, _REDRAW_INTERVAL / 2) is False

    def test_redraws_once_the_interval_elapses(self) -> None:
        assert _should_redraw(0.0, _REDRAW_INTERVAL) is True

    def test_redraws_well_after_the_interval(self) -> None:
        assert _should_redraw(0.0, _REDRAW_INTERVAL * 10) is True

    def test_holds_back_when_no_time_has_passed(self) -> None:
        assert _should_redraw(5.0, 5.0) is False


class TestRenderingGate:
    """Whether anything is drawn at all, decided by the stream."""

    def test_writes_nothing_when_the_stream_is_not_a_terminal(self) -> None:
        stream = io.StringIO()
        progress = Progress(stream, use_color=False, clock=_Clock())
        for _ in range(100):
            progress.record(1024)
        assert stream.getvalue() == ""

    def test_finishing_writes_nothing_when_the_stream_is_not_a_terminal(self) -> None:
        stream = io.StringIO()
        progress = Progress(stream, use_color=False, clock=_Clock())
        progress.record(1024)
        progress.finish()
        assert stream.getvalue() == ""

    def test_writes_to_a_terminal(self) -> None:
        progress, stream = _on_terminal()
        progress.record(1024)
        assert stream.getvalue() != ""


class TestThrottling:
    """How often a terminal is redrawn as files are recorded."""

    def test_draws_on_the_first_file(self) -> None:
        progress, stream = _on_terminal()
        progress.record(1)
        assert stream.getvalue().count("\r") == 1

    def test_holds_back_within_the_interval(self) -> None:
        clock = _Clock()
        progress, stream = _on_terminal(clock)
        progress.record(1)
        for _ in range(50):
            progress.record(1)
        assert stream.getvalue().count("\r") == 1

    def test_draws_again_once_the_interval_elapses(self) -> None:
        clock = _Clock()
        progress, stream = _on_terminal(clock)
        progress.record(1)
        clock.advance(_REDRAW_INTERVAL)
        progress.record(1)
        assert stream.getvalue().count("\r") == 2

    def test_counts_every_file_regardless_of_drawing(self) -> None:
        clock = _Clock()
        progress, _ = _on_terminal(clock)
        for _ in range(10):
            progress.record(100)
        clock.advance(1.0)
        assert "10 files" in progress.line(clock.now)


class TestLine:
    """The counts the line reports."""

    def test_reports_the_file_count(self) -> None:
        progress, _ = _on_terminal()
        progress.record(1)
        assert "1 files" in progress.line(0.0)

    def test_groups_large_file_counts(self) -> None:
        progress, _ = _on_terminal()
        for _ in range(1000):
            progress.record(1)
        assert "1,000 files" in progress.line(0.0)

    def test_reports_the_cumulative_size(self) -> None:
        progress, _ = _on_terminal()
        progress.record(1024)
        progress.record(1024)
        assert "2.0 KB" in progress.line(0.0)

    def test_reports_the_elapsed_time(self) -> None:
        clock = _Clock()
        progress, _ = _on_terminal(clock)
        progress.record(1)
        assert "1.5s" in progress.line(1.5)

    def test_reports_the_throughput(self) -> None:
        clock = _Clock()
        progress, _ = _on_terminal(clock)
        progress.record(1024)
        assert "1.0 KB/s" in progress.line(1.0)

    def test_reports_no_throughput_before_any_time_passes(self) -> None:
        progress, _ = _on_terminal()
        progress.record(1024)
        assert "0 B/s" in progress.line(0.0)

    def test_the_line_is_ascii(self) -> None:
        progress, _ = _on_terminal()
        progress.record(1024)
        assert progress.line(1.0).isascii()


class TestFinish:
    """Erasing the line once the scan is over."""

    def test_erases_what_was_drawn(self) -> None:
        clock = _Clock()
        progress, stream = _on_terminal(clock)
        progress.record(1024)
        drawn = len(stream.getvalue()) - 1
        stream.truncate(0)
        stream.seek(0)
        progress.finish()
        assert stream.getvalue() == "\r" + " " * drawn + "\r"

    def test_returns_to_the_row_start_when_nothing_was_drawn(self) -> None:
        progress, stream = _on_terminal()
        progress.finish()
        assert stream.getvalue() == "\r\r"

    def test_leaves_the_cursor_at_the_start_of_the_row(self) -> None:
        progress, stream = _on_terminal()
        progress.record(1024)
        progress.finish()
        assert stream.getvalue().endswith("\r")


class TestColor:
    """Colouring of the progress line."""

    def test_carries_no_escape_when_color_is_off(self) -> None:
        progress, stream = _on_terminal()
        progress.record(1024)
        assert _ESCAPE not in stream.getvalue()

    def test_carries_an_escape_when_color_is_on(self) -> None:
        stream = _Terminal()
        progress = Progress(stream, use_color=True, clock=_Clock())
        progress.record(1024)
        assert _ESCAPE in stream.getvalue()

    def test_color_leaves_the_counts_readable(self) -> None:
        stream = _Terminal()
        progress = Progress(stream, use_color=True, clock=_Clock())
        progress.record(1024)
        assert "1 files" in stream.getvalue()
