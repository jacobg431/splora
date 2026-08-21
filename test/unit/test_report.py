"""Unit tests for src/report.py."""

from __future__ import annotations

from src.report import _sanitize


class TestSanitize:
    """Name sanitization applied before locating a recorded run."""

    def test_valid_name_unchanged(self):
        assert _sanitize("my-run_v2") == "my-run_v2"

    def test_replaces_colon(self):
        assert _sanitize("C:drive") == "C_drive"

    def test_replaces_backslash(self):
        assert _sanitize("a\\b") == "a_b"

    def test_strips_leading_dot(self):
        assert _sanitize(".hidden") == "hidden"

    def test_empty_string_returns_unnamed(self):
        assert _sanitize("") == "unnamed"

    def test_only_unsafe_chars_collapse_to_underscore(self):
        assert _sanitize(":::") == "_"
