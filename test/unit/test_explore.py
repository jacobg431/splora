"""Unit tests for src/explore.py."""

from __future__ import annotations

import argparse
import io
import time
from pathlib import Path
from unittest.mock import patch

import pytest

import src.explore as explore_mod
from src.explore import (
    CATEGORIES,
    _build_excludes,
    _build_state,
    _resolve_name,
    _sanitize,
    _scan_dir,
    _State,
)
from src.progress import Progress


def _quiet() -> Progress:
    return Progress(io.StringIO(), use_color=False)


class TestSanitize:
    """Name sanitization applied to run names and output filenames."""

    def test_valid_name_is_unchanged(self) -> None:
        assert _sanitize("my-project_v2") == "my-project_v2"

    def test_replaces_colon(self) -> None:
        assert _sanitize("C:drive") == "C_drive"

    def test_replaces_backslash(self) -> None:
        assert _sanitize("a\\b") == "a_b"

    def test_replaces_forward_slash(self) -> None:
        assert _sanitize("a/b") == "a_b"

    def test_replaces_consecutive_unsafe_chars_with_single_underscore(self) -> None:
        assert _sanitize("a<>b") == "a_b"

    def test_strips_leading_dot(self) -> None:
        assert _sanitize(".hidden") == "hidden"

    def test_strips_trailing_space(self) -> None:
        assert _sanitize("name ") == "name"

    def test_empty_string_returns_unnamed(self) -> None:
        assert _sanitize("") == "unnamed"

    def test_only_unsafe_chars_collapses_to_single_underscore(self) -> None:
        # Consecutive unsafe chars become one "_"; "_" is a valid filename, not "unnamed"
        assert _sanitize(":::") == "_"

    def test_preserves_unicode(self) -> None:
        assert _sanitize("données") == "données"


class TestCategories:
    """Integrity of the extension-to-category mapping."""

    @pytest.mark.parametrize(
        "ext,expected",
        [
            (".jpg", "Image"),
            (".jpeg", "Image"),
            (".png", "Image"),
            (".mp4", "Video"),
            (".avi", "Video"),
            (".mp3", "Audio"),
            (".flac", "Audio"),
            (".pdf", "Document"),
            (".docx", "Document"),
            (".py", "Source Code"),
            (".js", "Source Code"),
            (".ts", "Source Code"),
            (".go", "Source Code"),
            (".json", "Data"),
            (".csv", "Data"),
            (".yaml", "Data"),
            (".zip", "Archive"),
            (".tar", "Archive"),
            (".7z", "Archive"),
            (".exe", "Executable"),
            (".dll", "Executable"),
            (".so", "Executable"),
            (".ttf", "Font"),
            (".woff", "Font"),
            (".ini", "Config"),
            (".env", "Config"),
        ],
    )
    def test_known_extension_maps_to_correct_category(self, ext: str, expected: str) -> None:
        assert CATEGORIES[ext] == expected

    def test_unknown_extension_is_absent_from_map(self) -> None:
        assert ".splora" not in CATEGORIES

    def test_all_values_are_valid_categories(self) -> None:
        valid = {
            "Image",
            "Video",
            "Audio",
            "Document",
            "Source Code",
            "Data",
            "Archive",
            "Executable",
            "Font",
            "Config",
        }
        assert set(CATEGORIES.values()) == valid

    def test_all_keys_are_lowercase(self) -> None:
        for key in CATEGORIES:
            assert key == key.lower(), f"Key {key!r} is not lowercase"

    def test_all_keys_start_with_dot(self) -> None:
        for key in CATEGORIES:
            assert key.startswith("."), f"Key {key!r} does not start with '.'"


class TestState:
    """Limit tracking that decides when a traversal stops."""

    def test_initial_state_is_not_stopped(self) -> None:
        assert not _State().stopped
        assert not _State().check()

    def test_files_visited_increments_on_count_file(self) -> None:
        state = _State()
        state.count_file()
        state.count_file()
        assert state.files_visited == 2

    def test_stops_when_max_files_reached(self) -> None:
        state = _State(max_files=3)
        state.count_file()
        state.count_file()
        assert not state.stopped
        state.count_file()
        assert state.stopped

    def test_check_returns_true_after_stopped(self) -> None:
        state = _State(max_files=1)
        state.count_file()
        assert state.check() is True

    def test_stops_on_expired_deadline(self) -> None:
        state = _State(deadline=time.monotonic() - 1.0)  # already in the past
        assert state.check() is True
        assert state.stopped

    def test_does_not_stop_on_future_deadline(self) -> None:
        state = _State(deadline=time.monotonic() + 9999.0)
        assert state.check() is False

    def test_no_limit_never_stops_from_counting(self) -> None:
        state = _State()
        for _ in range(10_000):
            state.count_file()
        assert not state.stopped

    def test_check_is_idempotent_after_stop(self) -> None:
        state = _State(max_files=1)
        state.count_file()
        assert state.check()
        assert state.check()  # second call still returns True


class TestResolveName:
    """Run-name resolution from arguments or the root directory."""

    def _args(self, name: str | None = None) -> argparse.Namespace:
        return argparse.Namespace(name=name)

    def test_explicit_name_takes_precedence(self) -> None:
        assert _resolve_name(self._args("my-run"), Path("/data/projects")) == "my-run"

    def test_falls_back_to_root_directory_name(self) -> None:
        assert _resolve_name(self._args(), Path("/data/my-folder")) == "my-folder"

    def test_explicit_name_wins_even_when_root_has_a_name(self) -> None:
        assert _resolve_name(self._args("override"), Path("/data/some-dir")) == "override"


class TestBuildExcludes:
    """Merging of user-supplied excludes with the built-in defaults."""

    def _args(
        self, exclude: list[str] | None = None, no_default_excludes: bool = False
    ) -> argparse.Namespace:
        return argparse.Namespace(exclude=exclude or [], no_default_excludes=no_default_excludes)

    def test_user_excludes_are_included(self) -> None:
        args = self._args(exclude=["node_modules"], no_default_excludes=True)
        assert "node_modules" in _build_excludes(args)

    def test_default_excludes_are_merged(self) -> None:
        args = self._args(no_default_excludes=False)
        with patch.object(explore_mod, "_load_default_excludes", return_value={"venv", ".git"}):
            result = _build_excludes(args)
        assert "venv" in result
        assert ".git" in result

    def test_no_default_excludes_skips_config_file(self) -> None:
        args = self._args(no_default_excludes=True)
        with patch.object(explore_mod, "_load_default_excludes") as mock_load:
            _build_excludes(args)
        mock_load.assert_not_called()

    def test_user_and_default_excludes_are_combined(self) -> None:
        args = self._args(exclude=["custom"], no_default_excludes=False)
        with patch.object(explore_mod, "_load_default_excludes", return_value={"venv"}):
            result = _build_excludes(args)
        assert "custom" in result
        assert "venv" in result

    def test_empty_exclude_list_returns_only_defaults(self) -> None:
        args = self._args(no_default_excludes=False)
        with patch.object(explore_mod, "_load_default_excludes", return_value={"default"}):
            result = _build_excludes(args)
        assert result == {"default"}


class TestBuildState:
    """Construction of traversal state from the command-line limits."""

    def _args(
        self, max_files: int | None = None, timeout: float | None = None
    ) -> argparse.Namespace:
        return argparse.Namespace(max_files=max_files, timeout=timeout)

    def test_no_limits_produces_unlimited_state(self) -> None:
        state = _build_state(self._args())
        assert state.max_files is None
        assert state.deadline is None

    def test_max_files_is_passed_through(self) -> None:
        state = _build_state(self._args(max_files=500))
        assert state.max_files == 500

    def test_timeout_produces_a_future_deadline(self) -> None:
        before = time.monotonic()
        state = _build_state(self._args(timeout=60.0))
        assert state.deadline is not None
        assert state.deadline > before
        assert state.deadline <= before + 61.0  # generous upper bound

    def test_zero_timeout_is_treated_as_no_timeout(self) -> None:
        # timeout=0 is falsy, so no deadline should be set
        state = _build_state(self._args(timeout=0))
        assert state.deadline is None


class TestScanDir:
    """Recursive directory scanning when the directory cannot be listed."""

    def test_permission_error_returns_empty_node(self) -> None:
        # Simulate a directory that cannot be listed
        with patch("os.scandir", side_effect=PermissionError("denied")):
            node = _scan_dir(
                Path("/unreadable"),
                depth=0,
                depth_limit=0,
                excludes=set(),
                state=_State(),
                progress=_quiet(),
            )
        assert node["file_count"] == 0
        assert node["children"] == []
