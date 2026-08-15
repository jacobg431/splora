"""Integration tests for src/report.py.

All tests call report() end-to-end. Module-level path constants (_FS_DIR,
_TEMPLATE_DIR, _REPORT_DIR) are redirected via monkeypatch so no real project
directories are touched.
"""

from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

import pytest

import src.report as report_mod
from src.report import report


# ── Shared helpers ─────────────────────────────────────────────────────────


def _args(name: str | None = None) -> argparse.Namespace:
    return argparse.Namespace(name=name)


def _make_fs_json(fs_dir: Path, run_name: str, *, partial: bool = False) -> Path:
    """Write a minimal but structurally valid filesystem JSON into fs_dir."""
    payload = {
        "meta": {
            "name": run_name,
            "root": "/fake/root",
            "generated_at": "2026-06-28T00:00:00+00:00",
            "partial": partial,
            "total_size": 1024,
            "total_files": 7,
            "elapsed_seconds": 0.01,
        },
        "tree": {
            "name": run_name,
            "path": "/fake/root",
            "size": 1024,
            "file_count": 7,
            "extensions": {".py": 5, ".txt": 2},
            "categories": {"Source Code": 5, "Other": 2},
            "children": [],
        },
    }
    path = fs_dir / f"{run_name}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _patch(monkeypatch, tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create the directories and monkeypatch the module constants."""
    fs_dir = tmp_path / "filesystem"
    report_dir = tmp_path / "report"
    template_dir = tmp_path / "template"

    fs_dir.mkdir()
    template_dir.mkdir()

    for fname in ("index.html", "style.css", "main.js"):
        (template_dir / fname).write_text(f"<!-- {fname} -->", encoding="utf-8")

    monkeypatch.setattr(report_mod, "_FS_DIR", fs_dir)
    monkeypatch.setattr(report_mod, "_REPORT_DIR", report_dir)
    monkeypatch.setattr(report_mod, "_TEMPLATE_DIR", template_dir)

    return fs_dir, report_dir, template_dir


# ── Tests ──────────────────────────────────────────────────────────────────


class TestReportCommand:
    def test_generates_complete_report_folder(self, tmp_path: Path, monkeypatch):
        fs_dir, report_dir, *_ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "my-run")

        report(_args("my-run"))

        out = report_dir / "my-run"
        assert (out / "index.html").exists()
        assert (out / "style.css").exists()
        assert (out / "main.js").exists()
        assert (out / "data.json").exists()

    def test_data_json_content_matches_source(self, tmp_path: Path, monkeypatch):
        fs_dir, report_dir, *_ = _patch(monkeypatch, tmp_path)
        src_path = _make_fs_json(fs_dir, "my-run")

        report(_args("my-run"))

        written = (report_dir / "my-run" / "data.json").read_text(encoding="utf-8")
        assert written == src_path.read_text(encoding="utf-8")

    def test_falls_back_to_latest_json_when_no_name_given(self, tmp_path: Path, monkeypatch):
        fs_dir, report_dir, *_ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "first")
        time.sleep(0.02)
        _make_fs_json(fs_dir, "second")

        report(_args())  # no explicit name

        assert (report_dir / "second").exists()
        assert not (report_dir / "first").exists()

    def test_unknown_name_exits_with_code_1(self, tmp_path: Path, monkeypatch):
        _patch(monkeypatch, tmp_path)

        with pytest.raises(SystemExit) as exc:
            report(_args("does-not-exist"))
        assert exc.value.code == 1

    def test_empty_filesystem_dir_exits_with_code_1(self, tmp_path: Path, monkeypatch):
        _patch(monkeypatch, tmp_path)

        with pytest.raises(SystemExit) as exc:
            report(_args())
        assert exc.value.code == 1

    def test_missing_template_file_exits_with_code_1(self, tmp_path: Path, monkeypatch):
        fs_dir, _, template_dir = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "my-run")
        (template_dir / "style.css").unlink()

        with pytest.raises(SystemExit) as exc:
            report(_args("my-run"))
        assert exc.value.code == 1

    def test_re_running_updates_existing_report(self, tmp_path: Path, monkeypatch):
        fs_dir, report_dir, *_ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "my-run")

        report(_args("my-run"))

        updated_payload = {
            "meta": {"name": "my-run", "partial": False, "total_files": 99, "root": "/new"},
            "tree": {},
        }
        (fs_dir / "my-run.json").write_text(json.dumps(updated_payload), encoding="utf-8")

        report(_args("my-run"))

        data = json.loads((report_dir / "my-run" / "data.json").read_text(encoding="utf-8"))
        assert data["meta"]["total_files"] == 99

    def test_partial_scan_does_not_prevent_report_generation(self, tmp_path: Path, monkeypatch):
        fs_dir, report_dir, *_ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "partial-run", partial=True)

        report(_args("partial-run"))

        assert (report_dir / "partial-run" / "data.json").exists()

    def test_name_sanitization_finds_correct_file(self, tmp_path: Path, monkeypatch):
        fs_dir, report_dir, *_ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "C_drive")  # stored with sanitized name

        report(_args("C:drive"))  # user passes unsanitized version

        assert (report_dir / "C_drive").exists()

    def test_report_output_contains_no_extra_files(self, tmp_path: Path, monkeypatch):
        fs_dir, report_dir, *_ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "clean-run")

        report(_args("clean-run"))

        top = {p.name for p in (report_dir / "clean-run").iterdir()}
        assert top == {"index.html", "style.css", "main.js", "data.json"}

    def test_stale_asset_removed_after_template_change(self, tmp_path: Path, monkeypatch):
        fs_dir, report_dir, template_dir = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "my-run")
        (template_dir / "legacy").mkdir()
        (template_dir / "legacy" / "old-widget.js").write_text("// old", encoding="utf-8")

        report(_args("my-run"))
        assert (report_dir / "my-run" / "legacy" / "old-widget.js").exists()

        shutil.rmtree(template_dir / "legacy")
        (template_dir / "core").mkdir()
        (template_dir / "core" / "widget.js").write_text("// widget", encoding="utf-8")

        report(_args("my-run"))

        top = {p.name for p in (report_dir / "my-run").iterdir()}
        assert top == {"index.html", "style.css", "main.js", "core", "data.json"}
