"""Unit tests for src/terminal.py."""

from __future__ import annotations

import argparse
import dataclasses
import sys

import pytest

from src.terminal import (
    _ENABLE_VIRTUAL_TERMINAL_PROCESSING,
    ACCENT,
    WARNING,
    OutputConfig,
    _with_virtual_terminal,
    enable_virtual_terminal,
    format_bytes,
    format_throughput,
    notice_line,
    output_config,
    paint,
)

_ESCAPE = "\x1b["


class _Stream:
    """A stand-in for an output stream that reports whether it is a terminal."""

    def __init__(self, *, tty: bool):
        self.tty = tty

    def isatty(self) -> bool:
        """Report whether the stream is attached to a terminal."""
        return self.tty


def _args(*, trim_output: bool = False, no_color: bool = False) -> argparse.Namespace:
    return argparse.Namespace(trim_output=trim_output, no_color=no_color)


class TestOutputConfig:
    """The record carrying whether a run decorates its output and colours it."""

    def test_carries_both_fields(self):
        config = OutputConfig(trim=True, use_color=False)
        assert (config.trim, config.use_color) == (True, False)

    def test_is_immutable(self):
        config = OutputConfig(trim=False, use_color=True)
        with pytest.raises(dataclasses.FrozenInstanceError):
            config.trim = True

    def test_declares_no_separate_no_color_field(self):
        fields = {f.name for f in dataclasses.fields(OutputConfig)}
        assert fields == {"trim", "use_color"}


class TestOutputConfigFactory:
    """Derivation of the output configuration from parsed arguments and the stream."""

    def test_trim_follows_the_flag(self, monkeypatch):
        monkeypatch.setattr(sys, "stdout", _Stream(tty=True))
        assert output_config(_args(trim_output=True)).trim is True

    def test_trim_is_off_without_the_flag(self, monkeypatch):
        monkeypatch.setattr(sys, "stdout", _Stream(tty=True))
        assert output_config(_args(trim_output=False)).trim is False

    def test_color_is_on_for_a_terminal_without_the_flag(self, monkeypatch):
        monkeypatch.setattr(sys, "stdout", _Stream(tty=True))
        assert output_config(_args()).use_color is True

    def test_the_flag_turns_color_off_on_a_terminal(self, monkeypatch):
        monkeypatch.setattr(sys, "stdout", _Stream(tty=True))
        assert output_config(_args(no_color=True)).use_color is False

    def test_color_is_off_when_stdout_is_not_a_terminal(self, monkeypatch):
        monkeypatch.setattr(sys, "stdout", _Stream(tty=False))
        assert output_config(_args()).use_color is False

    def test_color_is_off_when_redirected_and_the_flag_is_given(self, monkeypatch):
        monkeypatch.setattr(sys, "stdout", _Stream(tty=False))
        assert output_config(_args(no_color=True)).use_color is False

    def test_trim_is_independent_of_color(self, monkeypatch):
        monkeypatch.setattr(sys, "stdout", _Stream(tty=False))
        assert output_config(_args(trim_output=True)).trim is True


class TestPaint:
    """Wrapping text in a colour sequence, gated on whether colour is in use."""

    def test_returns_the_text_unchanged_when_color_is_off(self):
        assert paint("hello", ACCENT, use_color=False) == "hello"

    def test_writes_no_escape_when_color_is_off(self):
        assert _ESCAPE not in paint("hello", ACCENT, use_color=False)

    def test_wraps_the_text_when_color_is_on(self):
        assert paint("hello", ACCENT, use_color=True) == f"\x1b[{ACCENT}mhello\x1b[0m"

    def test_resets_the_color_after_the_text(self):
        assert paint("hello", ACCENT, use_color=True).endswith("\x1b[0m")

    def test_keeps_the_text_intact(self):
        assert "hello" in paint("hello", WARNING, use_color=True)

    def test_uses_the_color_it_is_given(self):
        assert paint("hello", WARNING, use_color=True).startswith(f"\x1b[{WARNING}m")


class TestFormatBytes:
    """Human-readable byte formatting across every unit boundary."""

    def test_zero(self):
        assert format_bytes(0) == "0 B"

    def test_bytes(self):
        assert format_bytes(512) == "512 B"

    def test_exactly_one_kb(self):
        assert format_bytes(1024) == "1.0 KB"

    def test_fractional_kb(self):
        assert format_bytes(1536) == "1.5 KB"

    def test_exactly_one_mb(self):
        assert format_bytes(1024**2) == "1.0 MB"

    def test_exactly_one_gb(self):
        assert format_bytes(1024**3) == "1.0 GB"

    def test_exactly_one_tb(self):
        assert format_bytes(1024**4) == "1.0 TB"

    def test_exactly_one_pb(self):
        assert format_bytes(1024**5) == "1.0 PB"

    def test_large_byte_value(self):
        result = format_bytes(1024**3 * 2.5)
        assert result == "2.5 GB"

    def test_output_is_ascii(self):
        assert format_bytes(1536).isascii()


class TestFormatThroughput:
    """Transfer rates rendered as a size per second."""

    def test_zero(self):
        assert format_throughput(0) == "0 B/s"

    def test_bytes_per_second(self):
        assert format_throughput(512) == "512 B/s"

    def test_kilobytes_per_second(self):
        assert format_throughput(1536) == "1.5 KB/s"

    def test_megabytes_per_second(self):
        assert format_throughput(1024**2) == "1.0 MB/s"

    def test_output_is_ascii(self):
        assert format_throughput(1024**3).isascii()


class TestNoticeLine:
    """The shared rendering every command's notice passes through."""

    def test_trimmed_output_is_the_bare_message(self):
        config = OutputConfig(trim=True, use_color=False)
        assert notice_line("Stopped.", config=config) == "Stopped."

    def test_trimmed_output_carries_no_glyph(self):
        config = OutputConfig(trim=True, use_color=True)
        assert notice_line("Stopped.", config=config) == "Stopped."

    def test_trimmed_output_carries_no_escape(self):
        config = OutputConfig(trim=True, use_color=True)
        assert _ESCAPE not in notice_line("Stopped.", config=config)

    def test_styled_output_carries_a_glyph(self):
        config = OutputConfig(trim=False, use_color=False)
        assert notice_line("Stopped.", config=config) == "! Stopped."

    def test_styled_output_without_color_carries_no_escape(self):
        config = OutputConfig(trim=False, use_color=False)
        assert _ESCAPE not in notice_line("Stopped.", config=config)

    def test_styled_output_with_color_carries_an_escape(self):
        config = OutputConfig(trim=False, use_color=True)
        assert _ESCAPE in notice_line("Stopped.", config=config)

    def test_styled_output_keeps_the_message(self):
        config = OutputConfig(trim=False, use_color=True)
        assert "Stopped." in notice_line("Stopped.", config=config)

    def test_the_message_is_never_dropped(self):
        for config in (
            OutputConfig(trim=True, use_color=True),
            OutputConfig(trim=False, use_color=False),
        ):
            assert "Canceled." in notice_line("Canceled.", config=config)


class TestVirtualTerminal:
    """Enabling escape-sequence interpretation on a Windows console."""

    def test_adds_the_virtual_terminal_flag(self):
        assert _with_virtual_terminal(0) == _ENABLE_VIRTUAL_TERMINAL_PROCESSING

    def test_preserves_the_flags_already_in_force(self):
        assert _with_virtual_terminal(0x0001 | 0x0002) & 0x0003 == 0x0003

    def test_is_idempotent(self):
        once = _with_virtual_terminal(0x0001)
        assert _with_virtual_terminal(once) == once

    def test_does_nothing_when_the_windows_api_is_absent(self, monkeypatch):
        monkeypatch.delattr("ctypes.windll", raising=False)
        assert enable_virtual_terminal() is None
