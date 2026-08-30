"""Unit tests for src/banner.py."""

from __future__ import annotations

import re
from importlib import metadata

import src.banner as banner_mod
from src.banner import TAGLINE, Banner
from src.terminal import ACCENT, ACCENT_DEEP, ACCENT_DIM, ACCENT_LIGHT

_ESCAPE = "\x1b["
_ANY_ESCAPE = re.compile(r"\x1b\[[0-9;]*m")
_ART_ROWS = 5
_EMBLEM_COLUMNS = 13
_GUTTER_COLUMNS = slice(13, 15)


def _rendered(*, use_color: bool = False, version: str = "1.2.3") -> str:
    return Banner(version=version).render(use_color=use_color)


class TestBannerContent:
    """What the banner states, independent of how it is coloured."""

    def test_spells_the_wordmark(self) -> None:
        assert "|____/ |_|    |_____|" in _rendered()

    def test_draws_every_density_step(self) -> None:
        assert all(step in _rendered() for step in "#%+.")

    def test_carries_the_tagline(self) -> None:
        assert TAGLINE in _rendered()

    def test_carries_the_version(self) -> None:
        assert "v1.2.3" in _rendered(version="1.2.3")

    def test_separates_the_tagline_from_the_version(self) -> None:
        assert f"{TAGLINE}  -  v9.9.9" in _rendered(version="9.9.9")

    def test_the_footer_is_the_last_row(self) -> None:
        assert TAGLINE in _rendered().splitlines()[-1]

    def test_leaves_a_blank_row_above_the_footer(self) -> None:
        assert _rendered().splitlines()[-2] == ""


class TestBannerShape:
    """The geometry that keeps the emblem beside the wordmark."""

    def test_renders_the_art_and_the_footer(self) -> None:
        assert len(_rendered().splitlines()) == _ART_ROWS + 2

    def test_the_emblem_never_reaches_into_the_wordmark(self) -> None:
        for row in _rendered().splitlines()[:_ART_ROWS]:
            assert set(row[:_EMBLEM_COLUMNS]) <= set(" #%+.")

    def test_a_gutter_separates_the_two(self) -> None:
        for row in _rendered().splitlines()[:_ART_ROWS]:
            assert row[_GUTTER_COLUMNS] == "  "

    def test_every_art_row_carries_a_wordmark_stroke(self) -> None:
        for row in _rendered().splitlines()[:_ART_ROWS]:
            assert any(stroke in row for stroke in "_|/\\")

    def test_output_is_entirely_ascii(self) -> None:
        assert _rendered().isascii()

    def test_colored_output_is_entirely_ascii(self) -> None:
        assert _rendered(use_color=True).isascii()


class TestBannerColor:
    """The monochrome fallback and the coloured rendering."""

    def test_monochrome_carries_no_escape(self) -> None:
        assert _ESCAPE not in _rendered(use_color=False)

    def test_color_carries_escapes(self) -> None:
        assert _ESCAPE in _rendered(use_color=True)

    def test_stripping_the_color_yields_the_monochrome_banner(self) -> None:
        assert _ANY_ESCAPE.sub("", _rendered(use_color=True)) == _rendered(use_color=False)

    def test_each_density_step_uses_its_own_color(self) -> None:
        colored = _rendered(use_color=True)
        ramp = (ACCENT_LIGHT, ACCENT, ACCENT_DEEP, ACCENT_DIM)
        assert all(f"\x1b[{color}m" in colored for color in ramp)

    def test_the_ramp_is_four_distinct_colors(self) -> None:
        assert len({ACCENT_LIGHT, ACCENT, ACCENT_DEEP, ACCENT_DIM}) == 4

    def test_monochrome_keeps_every_density_step(self) -> None:
        assert all(step in _rendered(use_color=False) for step in "#%+.")


class TestVersionFallback:
    """The version reported when the package is not installed."""

    def test_falls_back_when_the_package_is_absent(self, monkeypatch) -> None:
        def absent(_name: str) -> str:
            raise metadata.PackageNotFoundError

        monkeypatch.setattr(banner_mod.metadata, "version", absent)
        assert banner_mod.installed_version() == "0.1.0"

    def test_the_fallback_is_ascii(self, monkeypatch) -> None:
        def absent(_name: str) -> str:
            raise metadata.PackageNotFoundError

        monkeypatch.setattr(banner_mod.metadata, "version", absent)
        assert banner_mod.installed_version().isascii()

    def test_reports_what_the_metadata_says_when_present(self, monkeypatch) -> None:
        monkeypatch.setattr(banner_mod.metadata, "version", lambda _name: "4.5.6")
        assert banner_mod.installed_version() == "4.5.6"
