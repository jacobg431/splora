from __future__ import annotations

from collections.abc import Callable

from src.banner import Banner, installed_version
from src.outcome import NextStep, Outcome
from src.terminal import ACCENT, MUTED, OutputConfig, enable_virtual_terminal, paint

_ADVICE_LABEL = "Next:"


def _as_argument(name: str) -> str:
    if any(character.isspace() for character in name):
        return f'"{name}"'
    return name


def advice_line(next_step: NextStep, *, use_color: bool) -> str:
    """Return the command to copy and paste to carry the pipeline to its next step."""
    command = f"splora {next_step.command} --name {_as_argument(next_step.name)}"
    return (
        f"{paint(_ADVICE_LABEL, MUTED, use_color=use_color)} "
        f"{paint(command, ACCENT, use_color=use_color)}"
    )


def run(body: Callable[[], Outcome], config: OutputConfig) -> int:
    """Print the banner, run the command body, print its next-step advice, return its exit code."""
    if config.use_color:
        enable_virtual_terminal()
    if not config.trim:
        print(Banner(version=installed_version()).render(use_color=config.use_color))
        print()
    outcome = body()
    if not config.trim and outcome.next_step is not None:
        print()
        print(advice_line(outcome.next_step, use_color=config.use_color))
    return outcome.code
