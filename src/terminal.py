from __future__ import annotations

import argparse
import ctypes
import sys
from dataclasses import dataclass

# 256-colour SGR parameters, approximating the blues the report UI already uses.
ACCENT_LIGHT = "38;5;153"
ACCENT = "38;5;75"
ACCENT_DEEP = "38;5;68"
ACCENT_DIM = "38;5;60"
MUTED = "38;5;245"
WARNING = "38;5;179"

_RESET = "\x1b[0m"
_NOTICE_GLYPH = "!"

_STD_OUTPUT_HANDLE = -11
_ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004

_UNITS = ("B", "KB", "MB", "GB", "TB")


@dataclass(frozen=True)
class OutputConfig:
    """Whether a run prints its decorations, and whether it colours what it prints."""

    trim: bool
    use_color: bool


def output_config(args: argparse.Namespace) -> OutputConfig:
    """Build the output configuration from the parsed command-line arguments."""
    return OutputConfig(
        trim=args.trim_output,
        use_color=not args.no_color and sys.stdout.isatty(),
    )


def _with_virtual_terminal(mode: int) -> int:
    return mode | _ENABLE_VIRTUAL_TERMINAL_PROCESSING


def enable_virtual_terminal() -> None:
    """Ask Windows to interpret escape sequences, and do nothing on platforms that already do."""
    windll = getattr(ctypes, "windll", None)
    if windll is None:
        return
    kernel32 = windll.kernel32
    handle = kernel32.GetStdHandle(_STD_OUTPUT_HANDLE)
    mode = ctypes.c_uint32()
    if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
        return
    kernel32.SetConsoleMode(handle, _with_virtual_terminal(mode.value))


def paint(text: str, color: str, *, use_color: bool) -> str:
    """Return the text wrapped in a colour sequence, or unchanged when colour is off."""
    if not use_color:
        return text
    return f"\x1b[{color}m{text}{_RESET}"


def format_bytes(n: float) -> str:
    """Return a byte count as a human-readable size."""
    for unit in _UNITS:
        if n < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def format_throughput(bytes_per_second: float) -> str:
    """Return a rate of transfer as a human-readable size per second."""
    return f"{format_bytes(bytes_per_second)}/s"


def notice_line(message: str, *, config: OutputConfig) -> str:
    """Return a notice as the bare message when trimmed, and as a styled line otherwise."""
    if config.trim:
        return message
    return paint(f"{_NOTICE_GLYPH} {message}", WARNING, use_color=config.use_color)
