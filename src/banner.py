from __future__ import annotations

from dataclasses import dataclass
from importlib import metadata
from itertools import groupby

from src.terminal import ACCENT, ACCENT_DEEP, ACCENT_DIM, ACCENT_LIGHT, MUTED, paint

TAGLINE = "see where your disk went"

_PACKAGE = "splora"
_VERSION_WHEN_NOT_INSTALLED = "0.1.0"

_INDENT = "  "
_GUTTER = "  "

# The logo's four treemap tiles, drawn at descending densities so the depth survives without
# colour. Each density character is painted in the matching step of the accent ramp.
_EMBLEM = (
    "##### %%%%%",
    "##### %%%%%",
    "##### +++++",
    "..........",
    "..........",
)

_DENSITY_COLORS = {
    "#": ACCENT_LIGHT,
    "%": ACCENT,
    "+": ACCENT_DEEP,
    ".": ACCENT_DIM,
}

_WORDMARK = (
    "  ____   ____   _      ___   ____      _",
    " / ___| |  _ \\ | |    / _ \\ |  _ \\    / \\",
    " \\___ \\ | |_) || |    | | | || |_) |  / _ \\",
    "  ___) ||  __/ | |___ | |_| ||  _ <  / ___ \\",
    " |____/ |_|    |_____| \\___/ |_| \\_\\/_/   \\_\\",
)

_EMBLEM_WIDTH = max(len(row) for row in _EMBLEM)


def installed_version() -> str:
    """Return the version recorded for the installed package, or the fallback when absent."""
    try:
        return metadata.version(_PACKAGE)
    except metadata.PackageNotFoundError:
        return _VERSION_WHEN_NOT_INSTALLED


def _paint_by_density(row: str, *, use_color: bool) -> str:
    painted = []
    for character, run in groupby(row):
        block = "".join(run)
        color = _DENSITY_COLORS.get(character)
        painted.append(block if color is None else paint(block, color, use_color=use_color))
    return "".join(painted)


@dataclass(frozen=True)
class Banner:
    """The emblem, wordmark, tagline and version printed once at the top of a run."""

    version: str

    def render(self, *, use_color: bool) -> str:
        """Return the whole banner as the lines to print."""
        rows = [
            _INDENT
            + _paint_by_density(emblem.ljust(_EMBLEM_WIDTH), use_color=use_color)
            + _GUTTER
            + paint(wordmark, ACCENT, use_color=use_color)
            for emblem, wordmark in zip(_EMBLEM, _WORDMARK, strict=True)
        ]
        footer = f"{TAGLINE}  -  v{self.version}"
        rows.append("")
        rows.append(_INDENT + paint(footer, MUTED, use_color=use_color))
        return "\n".join(rows)
