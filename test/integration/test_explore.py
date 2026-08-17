"""Integration tests for src/explore.py.

These tests call explore() end-to-end with real (temporary) directory trees
built by pytest's tmp_path fixture. The module-level _FS_DIR is redirected
via monkeypatch so no files are written to the real data/filesystem/ folder.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import src.explore as explore_mod
from src.explore import explore

# ── Shared helpers ─────────────────────────────────────────────────────────


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


def _load(out_dir: Path, name: str) -> dict:
    return json.loads((out_dir / f"{name}.json").read_text(encoding="utf-8"))


# ── Tests ──────────────────────────────────────────────────────────────────


class TestExploreCommand:
    def test_generates_valid_json_with_correct_structure(self, tmp_path: Path, monkeypatch):
        # Keep scan_dir and out_dir as siblings so out_dir is never included in the scan.
        scan_dir = tmp_path / "scan"
        scan_dir.mkdir()
        (scan_dir / "file.txt").write_bytes(b"hello")
        (scan_dir / "script.py").write_bytes(b"code")
        sub = scan_dir / "subdir"
        sub.mkdir()
        (sub / "data.json").write_bytes(b"{}")

        out_dir = tmp_path / "output"
        monkeypatch.setattr(explore_mod, "_FS_DIR", out_dir)

        explore(_args(path=str(scan_dir), name="test-run"))

        data = _load(out_dir, "test-run")

        assert data["meta"]["name"] == "test-run"
        assert data["meta"]["root"] == str(scan_dir)
        assert data["meta"]["partial"] is False
        assert data["meta"]["total_files"] == 3
        assert data["tree"]["file_count"] == 3
        assert len(data["tree"]["children"]) == 1
        assert data["tree"]["children"][0]["name"] == "subdir"

    def test_name_defaults_to_root_folder_name(self, tmp_path: Path, monkeypatch):
        (tmp_path / "file.txt").write_bytes(b"x")

        out_dir = tmp_path / "output"
        monkeypatch.setattr(explore_mod, "_FS_DIR", out_dir)

        explore(_args(path=str(tmp_path)))  # no explicit name

        data = _load(out_dir, tmp_path.name)
        assert data["meta"]["name"] == tmp_path.name

    def test_total_size_is_accurate(self, tmp_path: Path, monkeypatch):
        (tmp_path / "small.bin").write_bytes(b"x" * 100)
        (tmp_path / "large.bin").write_bytes(b"y" * 900)

        out_dir = tmp_path / "output"
        monkeypatch.setattr(explore_mod, "_FS_DIR", out_dir)

        explore(_args(path=str(tmp_path), name="size-run"))

        data = _load(out_dir, "size-run")
        assert data["meta"]["total_size"] == 1000

    def test_marks_partial_when_max_files_reached(self, tmp_path: Path, monkeypatch):
        for i in range(10):
            (tmp_path / f"file{i}.txt").write_bytes(b"x")

        out_dir = tmp_path / "output"
        monkeypatch.setattr(explore_mod, "_FS_DIR", out_dir)

        explore(_args(path=str(tmp_path), name="partial-run", max_files=5))

        data = _load(out_dir, "partial-run")
        assert data["meta"]["partial"] is True
        assert data["meta"]["total_files"] <= 5

    def test_marks_partial_when_timeout_expires(self, tmp_path: Path, monkeypatch):
        for i in range(200):
            (tmp_path / f"file{i}.py").write_bytes(b"x" * 1000)

        out_dir = tmp_path / "output"
        monkeypatch.setattr(explore_mod, "_FS_DIR", out_dir)

        explore(_args(path=str(tmp_path), name="timeout-run", timeout=0.0001))

        data = _load(out_dir, "timeout-run")
        assert data["meta"]["partial"] is True

    def test_respects_exclude_list(self, tmp_path: Path, monkeypatch):
        keep = tmp_path / "keep"
        keep.mkdir()
        (keep / "file.txt").write_bytes(b"x")

        skip = tmp_path / "node_modules"
        skip.mkdir()
        (skip / "big.js").write_bytes(b"y" * 1000)

        out_dir = tmp_path / "output"
        monkeypatch.setattr(explore_mod, "_FS_DIR", out_dir)

        explore(_args(path=str(tmp_path), name="exc-run", exclude=["node_modules"]))

        data = _load(out_dir, "exc-run")
        assert data["meta"]["total_files"] == 1
        child_names = [c["name"] for c in data["tree"]["children"]]
        assert "node_modules" not in child_names
        assert "keep" in child_names

    def test_depth_limit_prevents_deep_traversal(self, tmp_path: Path, monkeypatch):
        # root/a/b/c/deep.txt is 3 levels deep; root/a/shallow.txt is 1 level deep
        deep = tmp_path / "a" / "b" / "c"
        deep.mkdir(parents=True)
        (deep / "deep.txt").write_bytes(b"deep")
        (tmp_path / "a" / "shallow.txt").write_bytes(b"shallow")

        out_dir = tmp_path / "output"
        monkeypatch.setattr(explore_mod, "_FS_DIR", out_dir)

        # depth=2: root(0) → a(1) → b(2) → c is at depth 2 so NOT entered
        explore(_args(path=str(tmp_path), name="depth-run", depth=2))

        data = _load(out_dir, "depth-run")
        assert data["meta"]["total_files"] == 1  # only shallow.txt

    def test_extension_and_category_distribution_in_output(self, tmp_path: Path, monkeypatch):
        (tmp_path / "photo.jpg").write_bytes(b"img")
        (tmp_path / "code.py").write_bytes(b"src")
        (tmp_path / "archive.zip").write_bytes(b"zip")

        out_dir = tmp_path / "output"
        monkeypatch.setattr(explore_mod, "_FS_DIR", out_dir)

        explore(_args(path=str(tmp_path), name="cat-run"))

        data = _load(out_dir, "cat-run")
        tree = data["tree"]
        assert tree["extensions"][".jpg"] == 1
        assert tree["extensions"][".py"] == 1
        assert tree["extensions"][".zip"] == 1
        assert tree["categories"]["Image"] == 1
        assert tree["categories"]["Source Code"] == 1
        assert tree["categories"]["Archive"] == 1

    def test_output_file_is_not_written_as_partial_tmp(self, tmp_path: Path, monkeypatch):
        (tmp_path / "file.txt").write_bytes(b"x")

        out_dir = tmp_path / "output"
        monkeypatch.setattr(explore_mod, "_FS_DIR", out_dir)

        explore(_args(path=str(tmp_path), name="atomic-run"))

        # The .tmp file should have been renamed away; only the final .json remains
        assert (out_dir / "atomic-run.json").exists()
        assert not (out_dir / "atomic-run.tmp").exists()

    def test_child_stats_are_aggregated_to_root(self, tmp_path: Path, monkeypatch):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "a.py").write_bytes(b"x" * 50)
        (tmp_path / "b.txt").write_bytes(b"y" * 50)

        out_dir = tmp_path / "output"
        monkeypatch.setattr(explore_mod, "_FS_DIR", out_dir)

        explore(_args(path=str(tmp_path), name="agg-run"))

        data = _load(out_dir, "agg-run")
        assert data["tree"]["size"] == 100
        assert data["tree"]["file_count"] == 2
        # .py is Source Code; .txt is Other — both should appear at root level
        assert "Source Code" in data["tree"]["categories"]
        assert "Other" in data["tree"]["categories"]
