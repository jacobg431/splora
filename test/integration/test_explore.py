"""Integration tests for src/explore.py."""

from __future__ import annotations

import argparse
import io
from pathlib import Path

import pytest

import src.explore as explore_mod
from src.explore import _scan_dir, _State, explore
from src.progress import Progress
from src.terminal import OutputConfig

_TRIMMED = OutputConfig(trim=True, use_color=False)


def _quiet() -> Progress:
    return Progress(io.StringIO(), use_color=False)


def _args(**kwargs) -> argparse.Namespace:
    """Build an argparse.Namespace with sensible test defaults."""
    defaults: dict = {
        "path": None,
        "name": None,
        "depth": 0,
        "max_files": None,
        "timeout": None,
        "exclude": [],
        "no_default_excludes": True,  # isolate from real config file
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


def _patch(monkeypatch, tmp_path: Path) -> Path:
    """Redirect _FS_DIR to an output directory and return it."""
    out_dir = tmp_path / "output"
    monkeypatch.setattr(explore_mod, "_FS_DIR", out_dir)
    return out_dir


class TestExploreCommand:
    """The explore command traversing a tree and writing its JSON."""

    def test_generates_valid_json_with_correct_structure(
        self, tmp_path: Path, monkeypatch, load_json
    ):
        # Keep scan_dir and out_dir as siblings so out_dir is never included in the scan.
        scan_dir = tmp_path / "scan"
        scan_dir.mkdir()
        (scan_dir / "file.txt").write_bytes(b"hello")
        (scan_dir / "script.py").write_bytes(b"code")
        sub = scan_dir / "subdir"
        sub.mkdir()
        (sub / "data.json").write_bytes(b"{}")

        out_dir = _patch(monkeypatch, tmp_path)

        explore(_args(path=str(scan_dir), name="test-run"), _TRIMMED)

        data = load_json(out_dir / "test-run.json")

        assert data["meta"]["name"] == "test-run"
        assert data["meta"]["root"] == str(scan_dir)
        assert data["meta"]["partial"] is False
        assert data["meta"]["total_files"] == 3
        assert data["tree"]["file_count"] == 3
        assert len(data["tree"]["children"]) == 1
        assert data["tree"]["children"][0]["name"] == "subdir"

    def test_name_defaults_to_root_folder_name(self, tmp_path: Path, monkeypatch, load_json):
        (tmp_path / "file.txt").write_bytes(b"x")

        out_dir = _patch(monkeypatch, tmp_path)

        explore(_args(path=str(tmp_path)), _TRIMMED)  # no explicit name

        data = load_json(out_dir / f"{tmp_path.name}.json")
        assert data["meta"]["name"] == tmp_path.name

    def test_total_size_is_accurate(self, tmp_path: Path, monkeypatch, load_json):
        (tmp_path / "small.bin").write_bytes(b"x" * 100)
        (tmp_path / "large.bin").write_bytes(b"y" * 900)

        out_dir = _patch(monkeypatch, tmp_path)

        explore(_args(path=str(tmp_path), name="size-run"), _TRIMMED)

        data = load_json(out_dir / "size-run.json")
        assert data["meta"]["total_size"] == 1000

    def test_marks_partial_when_max_files_reached(self, tmp_path: Path, monkeypatch, load_json):
        for i in range(10):
            (tmp_path / f"file{i}.txt").write_bytes(b"x")

        out_dir = _patch(monkeypatch, tmp_path)

        explore(_args(path=str(tmp_path), name="partial-run", max_files=5), _TRIMMED)

        data = load_json(out_dir / "partial-run.json")
        assert data["meta"]["partial"] is True
        assert data["meta"]["total_files"] <= 5

    def test_marks_partial_when_timeout_expires(self, tmp_path: Path, monkeypatch, load_json):
        for i in range(200):
            (tmp_path / f"file{i}.py").write_bytes(b"x" * 1000)

        out_dir = _patch(monkeypatch, tmp_path)

        explore(_args(path=str(tmp_path), name="timeout-run", timeout=0.0001), _TRIMMED)

        data = load_json(out_dir / "timeout-run.json")
        assert data["meta"]["partial"] is True

    def test_respects_exclude_list(self, tmp_path: Path, monkeypatch, load_json):
        keep = tmp_path / "keep"
        keep.mkdir()
        (keep / "file.txt").write_bytes(b"x")

        skip = tmp_path / "node_modules"
        skip.mkdir()
        (skip / "big.js").write_bytes(b"y" * 1000)

        out_dir = _patch(monkeypatch, tmp_path)

        explore(_args(path=str(tmp_path), name="exc-run", exclude=["node_modules"]), _TRIMMED)

        data = load_json(out_dir / "exc-run.json")
        assert data["meta"]["total_files"] == 1
        child_names = [c["name"] for c in data["tree"]["children"]]
        assert "node_modules" not in child_names
        assert "keep" in child_names

    def test_depth_limit_prevents_deep_traversal(self, tmp_path: Path, monkeypatch, load_json):
        # root/a/b/c/deep.txt is 3 levels deep; root/a/shallow.txt is 1 level deep
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        (deep / "deep.txt").write_bytes(b"deep")
        (tmp_path / "a" / "shallow.txt").write_bytes(b"shallow")

        out_dir = _patch(monkeypatch, tmp_path)

        # depth=2: root(0) → a(1) → b(2) → c is at depth 2 so NOT entered
        explore(_args(path=str(tmp_path), name="depth-run", depth=2), _TRIMMED)

        data = load_json(out_dir / "depth-run.json")
        assert data["meta"]["total_files"] == 1  # only shallow.txt

    def test_extension_and_category_distribution_in_output(
        self, tmp_path: Path, monkeypatch, load_json
    ):
        (tmp_path / "photo.jpg").write_bytes(b"img")
        (tmp_path / "code.py").write_bytes(b"src")
        (tmp_path / "archive.zip").write_bytes(b"zip")

        out_dir = _patch(monkeypatch, tmp_path)

        explore(_args(path=str(tmp_path), name="cat-run"), _TRIMMED)

        data = load_json(out_dir / "cat-run.json")
        tree = data["tree"]
        assert tree["extensions"][".jpg"] == 1
        assert tree["extensions"][".py"] == 1
        assert tree["extensions"][".zip"] == 1
        assert tree["categories"]["Image"] == 1
        assert tree["categories"]["Source Code"] == 1
        assert tree["categories"]["Archive"] == 1

    def test_output_file_is_not_written_as_partial_tmp(self, tmp_path: Path, monkeypatch):
        (tmp_path / "file.txt").write_bytes(b"x")

        out_dir = _patch(monkeypatch, tmp_path)

        explore(_args(path=str(tmp_path), name="atomic-run"), _TRIMMED)

        # The .tmp file should have been renamed away; only the final .json remains
        assert (out_dir / "atomic-run.json").exists()
        assert not (out_dir / "atomic-run.tmp").exists()

    def test_child_stats_are_aggregated_to_root(self, tmp_path: Path, monkeypatch, load_json):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "a.py").write_bytes(b"x" * 50)
        (tmp_path / "b.txt").write_bytes(b"y" * 50)

        out_dir = _patch(monkeypatch, tmp_path)

        explore(_args(path=str(tmp_path), name="agg-run"), _TRIMMED)

        data = load_json(out_dir / "agg-run.json")
        assert data["tree"]["size"] == 100
        assert data["tree"]["file_count"] == 2
        # .py is Source Code; .txt is Other — both should appear at root level
        assert "Source Code" in data["tree"]["categories"]
        assert "Other" in data["tree"]["categories"]


class TestScanDir:
    """Recursive directory scanning and aggregation of child statistics."""

    def test_empty_directory_returns_zero_counts(self, tmp_path: Path):
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State(), progress=_quiet()
        )
        assert node["file_count"] == 0
        assert node["size"] == 0
        assert node["children"] == []
        assert node["extensions"] == {}
        assert node["categories"] == {}

    def test_node_carries_correct_name_and_path(self, tmp_path: Path):
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State(), progress=_quiet()
        )
        assert node["name"] == tmp_path.name
        assert node["path"] == str(tmp_path)

    def test_counts_files_and_accumulates_size(self, tmp_path: Path):
        (tmp_path / "a.txt").write_bytes(b"hello")  # 5 bytes
        (tmp_path / "b.txt").write_bytes(b"world!")  # 6 bytes
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State(), progress=_quiet()
        )
        assert node["file_count"] == 2
        assert node["size"] == 11

    def test_recurses_and_aggregates_child_stats(self, tmp_path: Path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "code.py").write_bytes(b"x" * 100)
        (tmp_path / "readme.txt").write_bytes(b"y" * 200)
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State(), progress=_quiet()
        )
        assert node["file_count"] == 2
        assert node["size"] == 300
        assert len(node["children"]) == 1
        assert node["children"][0]["name"] == "sub"

    def test_assigns_correct_extension_keys(self, tmp_path: Path):
        (tmp_path / "image.jpg").write_bytes(b"img")
        (tmp_path / "script.py").write_bytes(b"code")
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State(), progress=_quiet()
        )
        assert node["extensions"][".jpg"] == 1
        assert node["extensions"][".py"] == 1

    def test_assigns_correct_categories(self, tmp_path: Path):
        (tmp_path / "image.jpg").write_bytes(b"img")
        (tmp_path / "script.py").write_bytes(b"code")
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State(), progress=_quiet()
        )
        assert node["categories"]["Image"] == 1
        assert node["categories"]["Source Code"] == 1

    def test_no_extension_uses_none_key(self, tmp_path: Path):
        (tmp_path / "Makefile").write_bytes(b"make")
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State(), progress=_quiet()
        )
        assert node["extensions"]["(none)"] == 1
        assert node["categories"]["Other"] == 1

    def test_unknown_extension_maps_to_other(self, tmp_path: Path):
        (tmp_path / "file.splora").write_bytes(b"x")
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State(), progress=_quiet()
        )
        assert node["categories"]["Other"] == 1

    def test_respects_exclude_list(self, tmp_path: Path):
        ignored = tmp_path / "node_modules"
        ignored.mkdir()
        (ignored / "big.js").write_bytes(b"x" * 1000)
        node = _scan_dir(
            tmp_path,
            depth=0,
            depth_limit=0,
            excludes={"node_modules"},
            state=_State(),
            progress=_quiet(),
        )
        assert node["file_count"] == 0
        assert node["children"] == []

    def test_respects_depth_limit(self, tmp_path: Path):
        # Structure: root/a/b/deep.txt — depth_limit=1 means we enter 'a' but not 'b'
        deep = tmp_path / "a" / "b"
        deep.mkdir(parents=True)
        (deep / "deep.txt").write_bytes(b"too deep")
        (tmp_path / "a" / "shallow.txt").write_bytes(b"ok")
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=1, excludes=set(), state=_State(), progress=_quiet()
        )
        assert node["file_count"] == 1  # only shallow.txt

    def test_unlimited_depth_traverses_all_levels(self, tmp_path: Path):
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        (deep / "file.txt").write_bytes(b"deep")
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State(), progress=_quiet()
        )
        assert node["file_count"] == 1

    def test_stops_early_on_max_files(self, tmp_path: Path):
        for i in range(10):
            (tmp_path / f"file{i}.txt").write_bytes(b"x")
        state = _State(max_files=4)
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes=set(), state=state, progress=_quiet()
        )
        assert node["file_count"] <= 4
        assert state.stopped

    def test_children_are_sorted_alphabetically(self, tmp_path: Path):
        for name in ("zebra", "alpha", "middle"):
            (tmp_path / name).mkdir()
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State(), progress=_quiet()
        )
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
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State(), progress=_quiet()
        )
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
        node = _scan_dir(
            tmp_path, depth=0, depth_limit=0, excludes=set(), state=_State(), progress=_quiet()
        )
        # file.txt inside real_dir is counted; link_dir is skipped entirely
        assert node["file_count"] == 1
