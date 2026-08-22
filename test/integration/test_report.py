"""Integration tests for src/report.py."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import pytest

import src.report as report_mod
from src.outcome import EXIT_INTERRUPTED, EXIT_OK
from src.report import (
    _build_report,
    _latest_json,
    _missing_assets,
    _read_json,
    _resolve_json_path,
    _staging_dir,
    report,
)
from src.terminal import OutputConfig

_TRIMMED = OutputConfig(trim=True, use_color=False)
_DECORATED = OutputConfig(trim=False, use_color=False)
_TEMPLATE_FILES = ("index.html", "style.css", "main.js")


_REAL_COPYTREE = shutil.copytree


def _raising(error: BaseException):
    """Return a copytree stand-in that fails before anything is staged."""

    def fail(*_args, **_kwargs):
        raise error

    return fail


def _staged_then_raising(error: BaseException):
    """Return a copytree stand-in that stages the tree in full and then fails."""

    def fail(src, dst, *_args, **_kwargs):
        _REAL_COPYTREE(src, dst)
        raise error

    return fail


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


def _make_template_dir(parent: Path) -> Path:
    """Create a template directory holding every asset a report requires."""
    template_dir = parent / "template"
    template_dir.mkdir()
    for name in _TEMPLATE_FILES:
        (template_dir / name).write_text(f"content-{name}", encoding="utf-8")
    return template_dir


def _make_nested_template_dir(parent: Path) -> Path:
    """Create a template directory that also holds a nested asset folder."""
    template_dir = _make_template_dir(parent)
    (template_dir / "core").mkdir()
    (template_dir / "core" / "widget.js").write_text("content-widget.js", encoding="utf-8")
    return template_dir


def _patch(monkeypatch, tmp_path: Path) -> tuple[Path, Path, Path]:
    """Create the directories and monkeypatch the module constants."""
    fs_dir = tmp_path / "filesystem"
    report_dir = tmp_path / "report"
    template_dir = _make_template_dir(tmp_path)

    fs_dir.mkdir()

    monkeypatch.setattr(report_mod, "_FS_DIR", fs_dir)
    monkeypatch.setattr(report_mod, "_REPORT_DIR", report_dir)
    monkeypatch.setattr(report_mod, "_TEMPLATE_DIR", template_dir)

    return fs_dir, report_dir, template_dir


class TestReportCommand:
    """The report command turning a recorded run into a report folder."""

    def test_generates_complete_report_folder(self, tmp_path: Path, monkeypatch, name_args):
        fs_dir, report_dir, *_ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "my-run")

        report(name_args("my-run"), _TRIMMED)

        out = report_dir / "my-run"
        assert (out / "index.html").exists()
        assert (out / "style.css").exists()
        assert (out / "main.js").exists()
        assert (out / "data.json").exists()

    def test_data_json_content_matches_source(self, tmp_path: Path, monkeypatch, name_args):
        fs_dir, report_dir, *_ = _patch(monkeypatch, tmp_path)
        src_path = _make_fs_json(fs_dir, "my-run")

        report(name_args("my-run"), _TRIMMED)

        written = (report_dir / "my-run" / "data.json").read_text(encoding="utf-8")
        assert written == src_path.read_text(encoding="utf-8")

    def test_falls_back_to_latest_json_when_no_name_given(
        self, tmp_path: Path, monkeypatch, name_args
    ):
        fs_dir, report_dir, *_ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "first")
        time.sleep(0.02)
        _make_fs_json(fs_dir, "second")

        report(name_args(), _TRIMMED)  # no explicit name

        assert (report_dir / "second").exists()
        assert not (report_dir / "first").exists()

    def test_unknown_name_exits_with_code_1(self, tmp_path: Path, monkeypatch, name_args):
        _patch(monkeypatch, tmp_path)

        with pytest.raises(SystemExit) as exc:
            report(name_args("does-not-exist"), _TRIMMED)
        assert exc.value.code == 1

    def test_empty_filesystem_dir_exits_with_code_1(self, tmp_path: Path, monkeypatch, name_args):
        _patch(monkeypatch, tmp_path)

        with pytest.raises(SystemExit) as exc:
            report(name_args(), _TRIMMED)
        assert exc.value.code == 1

    def test_missing_template_file_exits_with_code_1(self, tmp_path: Path, monkeypatch, name_args):
        fs_dir, _, template_dir = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "my-run")
        (template_dir / "style.css").unlink()

        with pytest.raises(SystemExit) as exc:
            report(name_args("my-run"), _TRIMMED)
        assert exc.value.code == 1

    def test_re_running_updates_existing_report(
        self, tmp_path: Path, monkeypatch, name_args, load_json
    ):
        fs_dir, report_dir, *_ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "my-run")

        report(name_args("my-run"), _TRIMMED)

        updated_payload = {
            "meta": {"name": "my-run", "partial": False, "total_files": 99, "root": "/new"},
            "tree": {},
        }
        (fs_dir / "my-run.json").write_text(json.dumps(updated_payload), encoding="utf-8")

        report(name_args("my-run"), _TRIMMED)

        data = load_json(report_dir / "my-run" / "data.json")
        assert data["meta"]["total_files"] == 99

    def test_partial_scan_does_not_prevent_report_generation(
        self, tmp_path: Path, monkeypatch, name_args
    ):
        fs_dir, report_dir, *_ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "partial-run", partial=True)

        report(name_args("partial-run"), _TRIMMED)

        assert (report_dir / "partial-run" / "data.json").exists()

    def test_name_sanitization_finds_correct_file(self, tmp_path: Path, monkeypatch, name_args):
        fs_dir, report_dir, *_ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "C_drive")  # stored with sanitized name

        report(name_args("C:drive"), _TRIMMED)  # user passes unsanitized version

        assert (report_dir / "C_drive").exists()

    def test_report_output_contains_no_extra_files(self, tmp_path: Path, monkeypatch, name_args):
        fs_dir, report_dir, *_ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "clean-run")

        report(name_args("clean-run"), _TRIMMED)

        top = {p.name for p in (report_dir / "clean-run").iterdir()}
        assert top == {"index.html", "style.css", "main.js", "data.json"}

    def test_stale_asset_removed_after_template_change(
        self, tmp_path: Path, monkeypatch, name_args
    ):
        fs_dir, report_dir, template_dir = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "my-run")
        (template_dir / "legacy").mkdir()
        (template_dir / "legacy" / "old-widget.js").write_text("// old", encoding="utf-8")

        report(name_args("my-run"), _TRIMMED)
        assert (report_dir / "my-run" / "legacy" / "old-widget.js").exists()

        shutil.rmtree(template_dir / "legacy")
        (template_dir / "core").mkdir()
        (template_dir / "core" / "widget.js").write_text("// widget", encoding="utf-8")

        report(name_args("my-run"), _TRIMMED)

        top = {p.name for p in (report_dir / "my-run").iterdir()}
        assert top == {"index.html", "style.css", "main.js", "core", "data.json"}


class TestLatestJson:
    """Selection of the most recently modified filesystem JSON."""

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


class TestResolveJsonPath:
    """Resolution of a source JSON file by name or by recency."""

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


class TestReadJson:
    """Reading and parsing of a recorded run's JSON file."""

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


class TestMissingAssets:
    """Detection of template files absent from the asset directory."""

    def test_all_assets_present_returns_empty_list(self, tmp_path: Path):
        t = _make_template_dir(tmp_path)
        assert _missing_assets(t) == []

    def test_missing_template_file_is_reported(self, tmp_path: Path):
        t = _make_template_dir(tmp_path)
        (t / "style.css").unlink()
        missing = _missing_assets(t)
        assert "style.css" in missing

    def test_all_template_files_missing_are_reported(self, tmp_path: Path):
        t = tmp_path / "empty_template"
        t.mkdir()
        missing = _missing_assets(t)
        assert set(missing) == {"index.html", "style.css", "main.js"}


class TestBuildReport:
    """Construction of a report directory from the template tree."""

    def test_creates_expected_files(self, tmp_path: Path):
        template_dir = _make_nested_template_dir(tmp_path)
        out_dir = tmp_path / "report" / "my-run"

        _build_report(out_dir, template_dir, '{"meta":{}}')

        assert (out_dir / "index.html").exists()
        assert (out_dir / "style.css").exists()
        assert (out_dir / "main.js").exists()
        assert (out_dir / "core" / "widget.js").exists()
        assert (out_dir / "data.json").exists()

    def test_data_json_content_matches_raw_input(self, tmp_path: Path):
        template_dir = _make_nested_template_dir(tmp_path)
        out_dir = tmp_path / "report" / "my-run"
        raw = '{"meta": {"name": "test-run"}}'

        _build_report(out_dir, template_dir, raw)

        assert (out_dir / "data.json").read_text(encoding="utf-8") == raw

    def test_template_content_is_copied_correctly(self, tmp_path: Path):
        template_dir = _make_nested_template_dir(tmp_path)
        out_dir = tmp_path / "report" / "my-run"

        _build_report(out_dir, template_dir, "{}")

        assert (out_dir / "index.html").read_text() == "content-index.html"
        assert (out_dir / "style.css").read_text() == "content-style.css"
        assert (out_dir / "main.js").read_text() == "content-main.js"
        assert (out_dir / "core" / "widget.js").read_text() == "content-widget.js"

    def test_creates_output_dir_if_missing(self, tmp_path: Path):
        template_dir = _make_nested_template_dir(tmp_path)
        out_dir = tmp_path / "deeply" / "nested" / "report"

        _build_report(out_dir, template_dir, "{}")

        assert out_dir.is_dir()

    def test_idempotent_on_second_call(self, tmp_path: Path, load_json):
        template_dir = _make_nested_template_dir(tmp_path)
        out_dir = tmp_path / "report"

        _build_report(out_dir, template_dir, '{"v":1}')
        _build_report(out_dir, template_dir, '{"v":2}')

        assert load_json(out_dir / "data.json")["v"] == 2

    def test_no_extra_files_in_output(self, tmp_path: Path):
        template_dir = _make_nested_template_dir(tmp_path)
        out_dir = tmp_path / "report"

        _build_report(out_dir, template_dir, "{}")

        top_level = {p.name for p in out_dir.iterdir()}
        assert top_level == {"index.html", "style.css", "main.js", "core", "data.json"}

    def test_removes_preexisting_top_level_file_not_in_template(self, tmp_path: Path):
        template_dir = _make_nested_template_dir(tmp_path)
        out_dir = tmp_path / "report"
        out_dir.mkdir()
        (out_dir / "stale.js").write_text("leftover", encoding="utf-8")

        _build_report(out_dir, template_dir, "{}")

        assert not (out_dir / "stale.js").exists()

    def test_removes_preexisting_nested_directory_not_in_template(self, tmp_path: Path):
        template_dir = _make_nested_template_dir(tmp_path)
        out_dir = tmp_path / "report"
        (out_dir / "legacy").mkdir(parents=True)
        (out_dir / "legacy" / "old-widget.js").write_text("leftover", encoding="utf-8")

        _build_report(out_dir, template_dir, "{}")

        assert not (out_dir / "legacy").exists()


class TestStaging:
    """Assembly of a report beside its destination, and the cleanup that always follows."""

    def test_the_staging_directory_is_a_sibling_of_the_destination(self, tmp_path: Path):
        out_dir = tmp_path / "report" / "my-run"
        assert _staging_dir(out_dir).parent == out_dir.parent

    def test_the_staging_directory_is_dot_prefixed(self, tmp_path: Path):
        assert _staging_dir(tmp_path / "report" / "my-run").name.startswith(".")

    def test_no_staging_directory_survives_a_successful_build(self, tmp_path: Path):
        template_dir = _make_nested_template_dir(tmp_path)
        out_dir = tmp_path / "report" / "my-run"

        _build_report(out_dir, template_dir, "{}")

        assert not _staging_dir(out_dir).exists()

    def test_nothing_is_staged_when_the_build_fails_before_copying(
        self, tmp_path: Path, monkeypatch
    ):
        template_dir = _make_nested_template_dir(tmp_path)
        out_dir = tmp_path / "report" / "my-run"
        out_dir.parent.mkdir()
        monkeypatch.setattr(report_mod.shutil, "copytree", _raising(OSError("disk full")))

        with pytest.raises(OSError):
            _build_report(out_dir, template_dir, "{}")

        assert not _staging_dir(out_dir).exists()

    def test_a_staged_tree_is_removed_when_the_build_fails_after_copying(
        self, tmp_path: Path, monkeypatch
    ):
        template_dir = _make_nested_template_dir(tmp_path)
        out_dir = tmp_path / "report" / "my-run"
        out_dir.parent.mkdir()
        monkeypatch.setattr(
            report_mod.shutil, "copytree", _staged_then_raising(OSError("disk full"))
        )

        with pytest.raises(OSError):
            _build_report(out_dir, template_dir, "{}")

        assert not _staging_dir(out_dir).exists()

    def test_a_failure_after_copying_leaves_the_report_root_clean(
        self, tmp_path: Path, monkeypatch
    ):
        template_dir = _make_nested_template_dir(tmp_path)
        out_dir = tmp_path / "report" / "my-run"
        out_dir.parent.mkdir()
        monkeypatch.setattr(
            report_mod.shutil, "copytree", _staged_then_raising(OSError("disk full"))
        )

        with pytest.raises(OSError):
            _build_report(out_dir, template_dir, "{}")

        assert list(out_dir.parent.iterdir()) == []

    def test_the_previous_report_survives_a_failed_rebuild(self, tmp_path: Path, monkeypatch):
        template_dir = _make_nested_template_dir(tmp_path)
        out_dir = tmp_path / "report" / "my-run"
        _build_report(out_dir, template_dir, '{"v":1}')
        monkeypatch.setattr(report_mod.shutil, "copytree", _raising(OSError("disk full")))

        with pytest.raises(OSError):
            _build_report(out_dir, template_dir, '{"v":2}')

        assert (out_dir / "data.json").read_text(encoding="utf-8") == '{"v":1}'

    def test_a_stale_staging_directory_does_not_leak_into_the_build(self, tmp_path: Path):
        template_dir = _make_nested_template_dir(tmp_path)
        out_dir = tmp_path / "report" / "my-run"
        stale = _staging_dir(out_dir)
        stale.mkdir(parents=True)
        (stale / "junk.txt").write_text("leftover", encoding="utf-8")

        _build_report(out_dir, template_dir, "{}")

        assert not (out_dir / "junk.txt").exists()
        assert not stale.exists()


class TestCancel:
    """A Ctrl+C arriving while the report is being assembled."""

    def _cancelled(self, tmp_path: Path, monkeypatch, name_args, config=_TRIMMED):
        fs_dir, report_dir, _ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "my-run")
        monkeypatch.setattr(
            report_mod.shutil, "copytree", _staged_then_raising(KeyboardInterrupt())
        )
        return report(name_args("my-run"), config), report_dir

    def test_returns_the_interrupted_code(self, tmp_path: Path, monkeypatch, name_args):
        outcome, _ = self._cancelled(tmp_path, monkeypatch, name_args)
        assert outcome.code == EXIT_INTERRUPTED

    def test_offers_no_next_step(self, tmp_path: Path, monkeypatch, name_args):
        outcome, _ = self._cancelled(tmp_path, monkeypatch, name_args)
        assert outcome.next_step is None

    def test_leaves_no_staging_directory(self, tmp_path: Path, monkeypatch, name_args):
        _, report_dir = self._cancelled(tmp_path, monkeypatch, name_args)
        assert not _staging_dir(report_dir / "my-run").exists()

    def test_writes_no_report(self, tmp_path: Path, monkeypatch, name_args):
        _, report_dir = self._cancelled(tmp_path, monkeypatch, name_args)
        assert not (report_dir / "my-run").exists()

    def test_says_it_was_canceled(self, tmp_path: Path, monkeypatch, name_args, capsys):
        self._cancelled(tmp_path, monkeypatch, name_args)
        assert "Canceled." in capsys.readouterr().out

    def test_the_trimmed_notice_is_the_bare_message(
        self, tmp_path: Path, monkeypatch, name_args, capsys
    ):
        self._cancelled(tmp_path, monkeypatch, name_args)
        assert capsys.readouterr().out.splitlines()[-1] == "Canceled."

    def test_the_decorated_notice_carries_a_glyph(
        self, tmp_path: Path, monkeypatch, name_args, capsys
    ):
        self._cancelled(tmp_path, monkeypatch, name_args, config=_DECORATED)
        assert capsys.readouterr().out.splitlines()[-1] == "! Canceled."


class TestOutcome:
    """The result a completed report reports back to the frame."""

    def test_a_successful_report_succeeds(self, tmp_path: Path, monkeypatch, name_args):
        fs_dir, *_ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "my-run")
        assert report(name_args("my-run"), _TRIMMED).code == EXIT_OK

    def test_a_successful_report_points_at_boot(self, tmp_path: Path, monkeypatch, name_args):
        fs_dir, *_ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "my-run")
        assert report(name_args("my-run"), _TRIMMED).next_step.command == "boot"

    def test_the_next_step_names_the_run(self, tmp_path: Path, monkeypatch, name_args):
        fs_dir, *_ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "my-run")
        assert report(name_args("my-run"), _TRIMMED).next_step.name == "my-run"
