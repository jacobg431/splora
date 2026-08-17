"""Unit tests for src/report.py."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from src.report import (
    _build_report,
    _latest_json,
    _missing_assets,
    _read_json,
    _resolve_json_path,
    _sanitize,
)

# ── _sanitize ──────────────────────────────────────────────────────────────


class TestSanitize:
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


# ── _latest_json ───────────────────────────────────────────────────────────


class TestLatestJson:
    def test_empty_directory_returns_none(self, tmp_path: Path):
        assert _latest_json(tmp_path) is None

    def test_single_json_is_returned(self, tmp_path: Path):
        f = tmp_path / "only.json"
        f.write_text("{}", encoding="utf-8")
        assert _latest_json(tmp_path) == f

    def test_non_json_files_are_ignored(self, tmp_path: Path):
        (tmp_path / "note.txt").write_text("x", encoding="utf-8")
        assert _latest_json(tmp_path) is None

    def test_returns_most_recently_modified(self, tmp_path: Path):
        old = tmp_path / "old.json"
        new = tmp_path / "new.json"
        old.write_text("{}", encoding="utf-8")
        time.sleep(0.02)  # ensure distinct mtime on any filesystem
        new.write_text("{}", encoding="utf-8")
        assert _latest_json(tmp_path) == new

    def test_ignores_json_in_subdirectories(self, tmp_path: Path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.json").write_text("{}", encoding="utf-8")
        assert _latest_json(tmp_path) is None


# ── _resolve_json_path ─────────────────────────────────────────────────────


class TestResolveJsonPath:
    def test_named_file_that_exists_is_returned(self, tmp_path: Path):
        f = tmp_path / "my-run.json"
        f.write_text("{}", encoding="utf-8")
        assert _resolve_json_path("my-run", tmp_path) == f

    def test_name_is_sanitized_before_lookup(self, tmp_path: Path):
        f = tmp_path / "C_drive.json"
        f.write_text("{}", encoding="utf-8")
        assert _resolve_json_path("C:drive", tmp_path) == f

    def test_named_file_missing_exits_with_code_1(self, tmp_path: Path):
        with pytest.raises(SystemExit) as exc:
            _resolve_json_path("nonexistent", tmp_path)
        assert exc.value.code == 1

    def test_no_name_returns_latest(self, tmp_path: Path):
        a = tmp_path / "a.json"
        b = tmp_path / "b.json"
        a.write_text("{}", encoding="utf-8")
        time.sleep(0.02)
        b.write_text("{}", encoding="utf-8")
        assert _resolve_json_path(None, tmp_path) == b

    def test_no_name_and_empty_dir_exits_with_code_1(self, tmp_path: Path):
        with pytest.raises(SystemExit) as exc:
            _resolve_json_path(None, tmp_path)
        assert exc.value.code == 1


# ── _read_json ─────────────────────────────────────────────────────────────


class TestReadJson:
    def test_valid_json_returns_raw_and_dict(self, tmp_path: Path):
        payload = {"meta": {"name": "test"}, "tree": {}}
        f = tmp_path / "data.json"
        f.write_text(json.dumps(payload), encoding="utf-8")

        raw, data = _read_json(f)

        assert isinstance(raw, str)
        assert data["meta"]["name"] == "test"

    def test_raw_text_matches_file_content(self, tmp_path: Path):
        content = '{"key": "value"}'
        f = tmp_path / "data.json"
        f.write_text(content, encoding="utf-8")

        raw, _ = _read_json(f)

        assert raw == content

    def test_missing_file_exits_with_code_1(self, tmp_path: Path):
        with pytest.raises(SystemExit) as exc:
            _read_json(tmp_path / "nonexistent.json")
        assert exc.value.code == 1

    def test_malformed_json_exits_with_code_1(self, tmp_path: Path):
        f = tmp_path / "bad.json"
        f.write_text("{ not valid json", encoding="utf-8")
        with pytest.raises(SystemExit) as exc:
            _read_json(f)
        assert exc.value.code == 1


# ── _missing_assets ────────────────────────────────────────────────────────


class TestMissingAssets:
    def _make_template_dir(self, base: Path) -> Path:
        d = base / "template"
        d.mkdir()
        for f in ("index.html", "style.css", "main.js"):
            (d / f).write_text(f"<!-- {f} -->", encoding="utf-8")
        return d

    def test_all_assets_present_returns_empty_list(self, tmp_path: Path):
        t = self._make_template_dir(tmp_path)
        assert _missing_assets(t) == []

    def test_missing_template_file_is_reported(self, tmp_path: Path):
        t = self._make_template_dir(tmp_path)
        (t / "style.css").unlink()
        missing = _missing_assets(t)
        assert "style.css" in missing

    def test_all_template_files_missing_are_reported(self, tmp_path: Path):
        t = tmp_path / "empty_template"
        t.mkdir()
        missing = _missing_assets(t)
        assert set(missing) == {"index.html", "style.css", "main.js"}


# ── _build_report ──────────────────────────────────────────────────────────


class TestBuildReport:
    def _setup_template(self, base: Path) -> Path:
        template_dir = base / "template"
        template_dir.mkdir()
        for f in ("index.html", "style.css", "main.js"):
            (template_dir / f).write_text(f"content-{f}", encoding="utf-8")
        # A nested module directory to exercise the recursive template copy.
        (template_dir / "core").mkdir()
        (template_dir / "core" / "widget.js").write_text("content-widget.js", encoding="utf-8")
        return template_dir

    def test_creates_expected_files(self, tmp_path: Path):
        template_dir = self._setup_template(tmp_path)
        out_dir = tmp_path / "report" / "my-run"

        _build_report(out_dir, template_dir, '{"meta":{}}')

        assert (out_dir / "index.html").exists()
        assert (out_dir / "style.css").exists()
        assert (out_dir / "main.js").exists()
        assert (out_dir / "core" / "widget.js").exists()
        assert (out_dir / "data.json").exists()

    def test_data_json_content_matches_raw_input(self, tmp_path: Path):
        template_dir = self._setup_template(tmp_path)
        out_dir = tmp_path / "report" / "my-run"
        raw = '{"meta": {"name": "test-run"}}'

        _build_report(out_dir, template_dir, raw)

        assert (out_dir / "data.json").read_text(encoding="utf-8") == raw

    def test_template_content_is_copied_correctly(self, tmp_path: Path):
        template_dir = self._setup_template(tmp_path)
        out_dir = tmp_path / "report" / "my-run"

        _build_report(out_dir, template_dir, "{}")

        assert (out_dir / "index.html").read_text() == "content-index.html"
        assert (out_dir / "style.css").read_text() == "content-style.css"
        assert (out_dir / "main.js").read_text() == "content-main.js"
        assert (out_dir / "core" / "widget.js").read_text() == "content-widget.js"

    def test_creates_output_dir_if_missing(self, tmp_path: Path):
        template_dir = self._setup_template(tmp_path)
        out_dir = tmp_path / "deeply" / "nested" / "report"

        _build_report(out_dir, template_dir, "{}")

        assert out_dir.is_dir()

    def test_idempotent_on_second_call(self, tmp_path: Path):
        template_dir = self._setup_template(tmp_path)
        out_dir = tmp_path / "report"

        _build_report(out_dir, template_dir, '{"v":1}')
        _build_report(out_dir, template_dir, '{"v":2}')

        assert json.loads((out_dir / "data.json").read_text())["v"] == 2

    def test_no_extra_files_in_output(self, tmp_path: Path):
        template_dir = self._setup_template(tmp_path)
        out_dir = tmp_path / "report"

        _build_report(out_dir, template_dir, "{}")

        top_level = {p.name for p in out_dir.iterdir()}
        assert top_level == {"index.html", "style.css", "main.js", "core", "data.json"}

    def test_removes_preexisting_top_level_file_not_in_template(self, tmp_path: Path):
        template_dir = self._setup_template(tmp_path)
        out_dir = tmp_path / "report"
        out_dir.mkdir()
        (out_dir / "stale.js").write_text("leftover", encoding="utf-8")

        _build_report(out_dir, template_dir, "{}")

        assert not (out_dir / "stale.js").exists()

    def test_removes_preexisting_nested_directory_not_in_template(self, tmp_path: Path):
        template_dir = self._setup_template(tmp_path)
        out_dir = tmp_path / "report"
        (out_dir / "legacy").mkdir(parents=True)
        (out_dir / "legacy" / "old-widget.js").write_text("leftover", encoding="utf-8")

        _build_report(out_dir, template_dir, "{}")

        assert not (out_dir / "legacy").exists()
