"""Unit tests for src/explore.py.

Each test targets a single function in isolation. Tests that touch the
filesystem use pytest's built-in tmp_path fixture, which creates a
real but ephemeral directory that is cleaned up after each test.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path
from unittest.mock import patch

import pytest

import src.explore as explore_mod
from src.explore import (
    CATEGORIES,
    _build_excludes,
    _build_state,
    _fmt_bytes,
    _resolve_name,
    _sanitize,
    _scan_dir,
    _State,
)

# ── _sanitize ──────────────────────────────────────────────────────────────


class TestSanitize:
    def test_valid_name_is_unchanged(self):
        assert _sanitize("my-project_v2") == "my-project_v2"

    def test_replaces_colon(self):
        assert _sanitize("C:drive") == "C_drive"

    def test_replaces_backslash(self):
        assert _sanitize("a\\b") == "a_b"

    def test_replaces_forward_slash(self):
        assert _sanitize("a/b") == "a_b"

    def test_replaces_consecutive_unsafe_chars_with_single_underscore(self):
        assert _sanitize("a<>b") == "a_b"

    def test_strips_leading_dot(self):
        assert _sanitize(".hidden") == "hidden"

    def test_strips_trailing_space(self):
        assert _sanitize("name ") == "name"

    def test_empty_string_returns_unnamed(self):
        assert _sanitize("") == "unnamed"

    def test_only_unsafe_chars_collapses_to_single_underscore(self):
        # Consecutive unsafe chars become one "_"; "_" is a valid filename, not "unnamed"
        assert _sanitize(":::") == "_"

    def test_preserves_unicode(self):
        assert _sanitize("données") == "données"


# ── _fmt_bytes ─────────────────────────────────────────────────────────────


class TestFmtBytes:
    def test_zero(self):
        assert _fmt_bytes(0) == "0 B"

    def test_bytes(self):
        assert _fmt_bytes(512) == "512 B"

    def test_exactly_one_kb(self):
        assert _fmt_bytes(1024) == "1.0 KB"

    def test_fractional_kb(self):
        assert _fmt_bytes(1536) == "1.5 KB"

    def test_exactly_one_mb(self):
        assert _fmt_bytes(1024**2) == "1.0 MB"

    def test_exactly_one_gb(self):
        assert _fmt_bytes(1024**3) == "1.0 GB"

    def test_exactly_one_tb(self):
        assert _fmt_bytes(1024**4) == "1.0 TB"

    def test_exactly_one_pb(self):
        assert _fmt_bytes(1024**5) == "1.0 PB"

    def test_large_byte_value(self):
        result = _fmt_bytes(1024**3 * 2.5)
        assert result == "2.5 GB"


# ── CATEGORIES ─────────────────────────────────────────────────────────────


class TestCategories:
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
    def test_known_extension_maps_to_correct_category(self, ext: str, expected: str):
        assert CATEGORIES[ext] == expected

    def test_unknown_extension_is_absent_from_map(self):
        assert ".splora" not in CATEGORIES

    def test_all_values_are_valid_categories(self):
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

    def test_all_keys_are_lowercase(self):
        for key in CATEGORIES:
            assert key == key.lower(), f"Key {key!r} is not lowercase"

    def test_all_keys_start_with_dot(self):
        for key in CATEGORIES:
            assert key.startswith("."), f"Key {key!r} does not start with '.'"


# ── _State ─────────────────────────────────────────────────────────────────


class TestState:
    def test_initial_state_is_not_stopped(self):
        assert not _State().stopped
        assert not _State().check()

    def test_files_visited_increments_on_count_file(self):
        state = _State()
        state.count_file()
        state.count_file()
        assert state.files_visited == 2

    def test_stops_when_max_files_reached(self):
        state = _State(max_files=3)
        state.count_file()
        state.count_file()
        assert not state.stopped
        state.count_file()
        assert state.stopped

    def test_check_returns_true_after_stopped(self):
        state = _State(max_files=1)
        state.count_file()
        assert state.check() is True

    def test_stops_on_expired_deadline(self):
        state = _State(deadline=time.monotonic() - 1.0)  # already in the past
        assert state.check() is True
        assert state.stopped

    def test_does_not_stop_on_future_deadline(self):
        state = _State(deadline=time.monotonic() + 9999.0)
        assert state.check() is False

    def test_no_limit_never_stops_from_counting(self):
        state = _State()
        for _ in range(10_000):
            state.count_file()
        assert not state.stopped

    def test_check_is_idempotent_after_stop(self):
        state = _State(max_files=1)
        state.count_file()
        assert state.check()
        assert state.check()  # second call still returns True


# ── _resolve_name ──────────────────────────────────────────────────────────


class TestResolveName:
    def _args(self, name: str | None = None) -> argparse.Namespace:
        return argparse.Namespace(name=name)

    def test_explicit_name_takes_precedence(self, tmp_path: Path):
        assert _resolve_name(self._args("my-run"), tmp_path) == "my-run"

    def test_falls_back_to_root_directory_name(self, tmp_path: Path):
        subdir = tmp_path / "my-folder"
        subdir.mkdir()
        assert _resolve_name(self._args(), subdir) == "my-folder"

    def test_explicit_name_wins_even_when_root_has_a_name(self, tmp_path: Path):
        subdir = tmp_path / "some-dir"
        subdir.mkdir()
        assert _resolve_name(self._args("override"), subdir) == "override"


# ── _build_excludes ────────────────────────────────────────────────────────


class TestBuildExcludes:
    def _args(
        self, exclude: list[str] | None = None, no_default_excludes: bool = False
    ) -> argparse.Namespace:
        return argparse.Namespace(exclude=exclude or [], no_default_excludes=no_default_excludes)

    def test_user_excludes_are_included(self):
        args = self._args(exclude=["node_modules"], no_default_excludes=True)
        assert "node_modules" in _build_excludes(args)

    def test_default_excludes_are_merged(self):
        args = self._args(no_default_excludes=False)
        with patch.object(explore_mod, "_load_default_excludes", return_value={"venv", ".git"}):
            result = _build_excludes(args)
        assert "venv" in result
        assert ".git" in result

    def test_no_default_excludes_skips_config_file(self):
        args = self._args(no_default_excludes=True)
        with patch.object(explore_mod, "_load_default_excludes") as mock_load:
            _build_excludes(args)
        mock_load.assert_not_called()

    def test_user_and_default_excludes_are_combined(self):
        args = self._args(exclude=["custom"], no_default_excludes=False)
        with patch.object(explore_mod, "_load_default_excludes", return_value={"venv"}):
            result = _build_excludes(args)
        assert "custom" in result
        assert "venv" in result

    def test_empty_exclude_list_returns_only_defaults(self):
        args = self._args(no_default_excludes=False)
        with patch.object(explore_mod, "_load_default_excludes", return_value={"default"}):
            result = _build_excludes(args)
        assert result == {"default"}


# ── _build_state ───────────────────────────────────────────────────────────


class TestBuildState:
    def _args(
        self, max_files: int | None = None, timeout: float | None = None
    ) -> argparse.Namespace:
        return argparse.Namespace(max_files=max_files, timeout=timeout)

    def test_no_limits_produces_unlimited_state(self):
        state = _build_state(self._args())
        assert state.max_files is None
        assert state.deadline is None

    def test_max_files_is_passed_through(self):
        state = _build_state(self._args(max_files=500))
        assert state.max_files == 500

    def test_timeout_produces_a_future_deadline(self):
        before = time.monotonic()
        state = _build_state(self._args(timeout=60.0))
        assert state.deadline is not None
        assert state.deadline > before
        assert state.deadline <= before + 61.0  # generous upper bound

    def test_zero_timeout_is_treated_as_no_timeout(self):
        # timeout=0 is falsy, so no deadline should be set
        state = _build_state(self._args(timeout=0))
        assert state.deadline is None


# ── _scan_dir ──────────────────────────────────────────────────────────────


class TestScanDir:
    def test_empty_directory_returns_zero_counts(self, tmp_path: Path):
        node = _scan_dir(tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State())
        assert node["file_count"] == 0
        assert node["size"] == 0
        assert node["children"] == []
        assert node["extensions"] == {}
        assert node["categories"] == {}

    def test_node_carries_correct_name_and_path(self, tmp_path: Path):
        node = _scan_dir(tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State())
        assert node["name"] == tmp_path.name
        assert node["path"] == str(tmp_path)

    def test_counts_files_and_accumulates_size(self, tmp_path: Path):
        (tmp_path / "a.txt").write_bytes(b"hello")  # 5 bytes
        (tmp_path / "b.txt").write_bytes(b"world!")  # 6 bytes
        node = _scan_dir(tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State())
        assert node["file_count"] == 2
        assert node["size"] == 11

    def test_recurses_and_aggregates_child_stats(self, tmp_path: Path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "code.py").write_bytes(b"x" * 100)
        (tmp_path / "readme.txt").write_bytes(b"y" * 200)
        node = _scan_dir(tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State())
        assert node["file_count"] == 2
        assert node["size"] == 300
        assert len(node["children"]) == 1
        assert node["children"][0]["name"] == "sub"

    def test_assigns_correct_extension_keys(self, tmp_path: Path):
        (tmp_path / "image.jpg").write_bytes(b"img")
        (tmp_path / "script.py").write_bytes(b"code")
        node = _scan_dir(tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State())
        assert node["extensions"][".jpg"] == 1
        assert node["extensions"][".py"] == 1

    def test_assigns_correct_categories(self, tmp_path: Path):
        (tmp_path / "image.jpg").write_bytes(b"img")
        (tmp_path / "script.py").write_bytes(b"code")
        node = _scan_dir(tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State())
        assert node["categories"]["Image"] == 1
        assert node["categories"]["Source Code"] == 1

    def test_no_extension_uses_none_key(self, tmp_path: Path):
        (tmp_path / "Makefile").write_bytes(b"make")
        node = _scan_dir(tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State())
        assert node["extensions"]["(none)"] == 1
        assert node["categories"]["Other"] == 1

    def test_unknown_extension_maps_to_other(self, tmp_path: Path):
        (tmp_path / "file.splora").write_bytes(b"x")
        node = _scan_dir(tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State())
        assert node["categories"]["Other"] == 1

    def test_respects_exclude_list(self, tmp_path: Path):
        ignored = tmp_path / "node_modules"
        ignored.mkdir()
        (ignored / "big.js").write_bytes(b"x" * 1000)
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes={"node_modules"}, state=_State()
        )
        assert node["file_count"] == 0
        assert node["children"] == []

    def test_respects_depth_limit(self, tmp_path: Path):
        # Structure: root/a/b/deep.txt — depth_limit=1 means we enter 'a' but not 'b'
        deep = tmp_path / "a" / "b"
        deep.mkdir(parents=True)
        (deep / "deep.txt").write_bytes(b"too deep")
        (tmp_path / "a" / "shallow.txt").write_bytes(b"ok")
        node = _scan_dir(tmp_path, depth=0, depth_limit=1, excludes=set(), state=_State())
        assert node["file_count"] == 1  # only shallow.txt

    def test_unlimited_depth_traverses_all_levels(self, tmp_path: Path):
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        (deep / "file.txt").write_bytes(b"deep")
        node = _scan_dir(tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State())
        assert node["file_count"] == 1

    def test_stops_early_on_max_files(self, tmp_path: Path):
        for i in range(10):
            (tmp_path / f"file{i}.txt").write_bytes(b"x")
        state = _State(max_files=4)
        node = _scan_dir(tmp_path, depth=0, depth_limit=0, excludes=set(), state=state)
        assert node["file_count"] <= 4
        assert state.stopped

    def test_children_are_sorted_alphabetically(self, tmp_path: Path):
        for name in ("zebra", "alpha", "middle"):
            (tmp_path / name).mkdir()
        node = _scan_dir(tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State())
        names = [c["name"] for c in node["children"]]
        assert names == sorted(names)

    def test_skips_symlinks_to_files(self, tmp_path: Path):
        real = tmp_path / "real.txt"
        real.write_bytes(b"content")
        try:
            link = tmp_path / "link.txt"
            link.symlink_to(real)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported on this platform")
        node = _scan_dir(tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State())
        assert node["file_count"] == 1  # only the real file

    def test_skips_symlinks_to_directories(self, tmp_path: Path):
        real_dir = tmp_path / "real_dir"
        real_dir.mkdir()
        (real_dir / "file.txt").write_bytes(b"content")
        try:
            link_dir = tmp_path / "link_dir"
            link_dir.symlink_to(real_dir)
        except (OSError, NotImplementedError):
            pytest.skip("Symlinks not supported on this platform")
        node = _scan_dir(tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State())
        # file.txt inside real_dir is counted; link_dir is skipped entirely
        assert node["file_count"] == 1

    def test_permission_error_returns_empty_node(self, tmp_path: Path):
        # Simulate a directory that cannot be listed
        with patch("os.scandir", side_effect=PermissionError("denied")):
            node = _scan_dir(tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State())
        assert node["file_count"] == 0
        assert node["children"] == []
