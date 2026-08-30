"""Integration tests for src/report.py."""

from __future__ import annotations

import argparse
import json
import shutil
import time
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

import pytest

import src.report as report_mod
from src.command import Command
from src.escalation import Cancel, Response
from src.outcome import EXIT_OK, Outcome
from src.report import (
    Report,
    _build_report,
    _latest_json,
    _missing_assets,
    _read_json,
    _resolve_json_path,
    _staging_dir,
)
from src.terminal import OutputConfig

_TRIMMED = OutputConfig(trim=True, use_color=False)
_DECORATED = OutputConfig(trim=False, use_color=False)
_TEMPLATE_FILES = ("index.html", "style.css", "main.js")


_REAL_COPYTREE = shutil.copytree
_REAL_RMTREE = shutil.rmtree


def _cancelling(press: Callable[[int], None]) -> Callable[..., None]:
    """Return a copytree stand-in that stages the tree in full and then presses once."""

    def stage(src: str | Path, dst: str | Path, *_args: Any, **_kwargs: Any) -> None:
        _REAL_COPYTREE(src, dst)
        press(1)

    return stage


def _cancelling_removal_of(target: Path, command: Report) -> Callable[..., None]:
    """Return an rmtree stand-in that cancels the command as the target is being removed."""

    def remove(path: str | Path, *args: Any, **kwargs: Any) -> None:
        if Path(path) == target:
            command.cancel()
        return _REAL_RMTREE(path, *args, **kwargs)

    return remove


def _raising(error: BaseException) -> Callable[..., None]:
    """Return a copytree stand-in that fails before anything is staged."""

    def fail(*_args: Any, **_kwargs: Any) -> None:
        raise error

    return fail


def _staged_then_raising(error: BaseException) -> Callable[..., None]:
    """Return a copytree stand-in that stages the tree in full and then fails."""

    def fail(src: str | Path, dst: str | Path, *_args: Any, **_kwargs: Any) -> None:
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


def _patch(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path, Path]:
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

    def test_generates_complete_report_folder(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        name_args: Callable[..., argparse.Namespace],
    ) -> None:
        fs_dir, report_dir, *_ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "my-run")

        Report(name_args("my-run"), _TRIMMED).run()

        out = report_dir / "my-run"
        assert (out / "index.html").exists()
        assert (out / "style.css").exists()
        assert (out / "main.js").exists()
        assert (out / "data.json").exists()

    def test_data_json_content_matches_source(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        name_args: Callable[..., argparse.Namespace],
    ) -> None:
        fs_dir, report_dir, *_ = _patch(monkeypatch, tmp_path)
        src_path = _make_fs_json(fs_dir, "my-run")

        Report(name_args("my-run"), _TRIMMED).run()

        written = (report_dir / "my-run" / "data.json").read_text(encoding="utf-8")
        assert written == src_path.read_text(encoding="utf-8")

    def test_falls_back_to_latest_json_when_no_name_given(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        name_args: Callable[..., argparse.Namespace],
    ) -> None:
        fs_dir, report_dir, *_ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "first")
        time.sleep(0.02)
        _make_fs_json(fs_dir, "second")

        Report(name_args(), _TRIMMED).run()  # no explicit name

        assert (report_dir / "second").exists()
        assert not (report_dir / "first").exists()

    def test_unknown_name_exits_with_code_1(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        name_args: Callable[..., argparse.Namespace],
    ) -> None:
        _patch(monkeypatch, tmp_path)

        with pytest.raises(SystemExit) as exc:
            Report(name_args("does-not-exist"), _TRIMMED).run()
        assert exc.value.code == 1

    def test_empty_filesystem_dir_exits_with_code_1(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        name_args: Callable[..., argparse.Namespace],
    ) -> None:
        _patch(monkeypatch, tmp_path)

        with pytest.raises(SystemExit) as exc:
            Report(name_args(), _TRIMMED).run()
        assert exc.value.code == 1

    def test_missing_template_file_exits_with_code_1(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        name_args: Callable[..., argparse.Namespace],
    ) -> None:
        fs_dir, _, template_dir = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "my-run")
        (template_dir / "style.css").unlink()

        with pytest.raises(SystemExit) as exc:
            Report(name_args("my-run"), _TRIMMED).run()
        assert exc.value.code == 1

    def test_re_running_updates_existing_report(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        name_args: Callable[..., argparse.Namespace],
        load_json: Callable[[Path], dict[str, Any]],
    ) -> None:
        fs_dir, report_dir, *_ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "my-run")

        Report(name_args("my-run"), _TRIMMED).run()

        updated_payload = {
            "meta": {"name": "my-run", "partial": False, "total_files": 99, "root": "/new"},
            "tree": {},
        }
        (fs_dir / "my-run.json").write_text(json.dumps(updated_payload), encoding="utf-8")

        Report(name_args("my-run"), _TRIMMED).run()

        data = load_json(report_dir / "my-run" / "data.json")
        assert data["meta"]["total_files"] == 99

    def test_partial_scan_does_not_prevent_report_generation(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        name_args: Callable[..., argparse.Namespace],
    ) -> None:
        fs_dir, report_dir, *_ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "partial-run", partial=True)

        Report(name_args("partial-run"), _TRIMMED).run()

        assert (report_dir / "partial-run" / "data.json").exists()

    def test_name_sanitization_finds_correct_file(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        name_args: Callable[..., argparse.Namespace],
    ) -> None:
        fs_dir, report_dir, *_ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "C_drive")  # stored with sanitized name

        Report(name_args("C:drive"), _TRIMMED).run()  # user passes unsanitized version

        assert (report_dir / "C_drive").exists()

    def test_report_output_contains_no_extra_files(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        name_args: Callable[..., argparse.Namespace],
    ) -> None:
        fs_dir, report_dir, *_ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "clean-run")

        Report(name_args("clean-run"), _TRIMMED).run()

        top = {p.name for p in (report_dir / "clean-run").iterdir()}
        assert top == {"index.html", "style.css", "main.js", "data.json"}

    def test_stale_asset_removed_after_template_change(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        name_args: Callable[..., argparse.Namespace],
    ) -> None:
        fs_dir, report_dir, template_dir = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "my-run")
        (template_dir / "legacy").mkdir()
        (template_dir / "legacy" / "old-widget.js").write_text("// old", encoding="utf-8")

        Report(name_args("my-run"), _TRIMMED).run()
        assert (report_dir / "my-run" / "legacy" / "old-widget.js").exists()

        shutil.rmtree(template_dir / "legacy")
        (template_dir / "core").mkdir()
        (template_dir / "core" / "widget.js").write_text("// widget", encoding="utf-8")

        Report(name_args("my-run"), _TRIMMED).run()

        top = {p.name for p in (report_dir / "my-run").iterdir()}
        assert top == {"index.html", "style.css", "main.js", "core", "data.json"}


class TestLatestJson:
    """Selection of the most recently modified filesystem JSON."""

    def test_empty_directory_returns_none(self, tmp_path: Path) -> None:
        assert _latest_json(tmp_path) is None

    def test_single_json_is_returned(self, tmp_path: Path) -> None:
        f = tmp_path / "only.json"
        f.write_text("{}", encoding="utf-8")
        assert _latest_json(tmp_path) == f

    def test_non_json_files_are_ignored(self, tmp_path: Path) -> None:
        (tmp_path / "note.txt").write_text("x", encoding="utf-8")
        assert _latest_json(tmp_path) is None

    def test_returns_most_recently_modified(self, tmp_path: Path) -> None:
        old = tmp_path / "old.json"
        new = tmp_path / "new.json"
        old.write_text("{}", encoding="utf-8")
        time.sleep(0.02)  # ensure distinct mtime on any filesystem
        new.write_text("{}", encoding="utf-8")
        assert _latest_json(tmp_path) == new

    def test_ignores_json_in_subdirectories(self, tmp_path: Path) -> None:
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "nested.json").write_text("{}", encoding="utf-8")
        assert _latest_json(tmp_path) is None


class TestResolveJsonPath:
    """Resolution of a source JSON file by name or by recency."""

    def test_named_file_that_exists_is_returned(self, tmp_path: Path) -> None:
        f = tmp_path / "my-run.json"
        f.write_text("{}", encoding="utf-8")
        assert _resolve_json_path("my-run", tmp_path) == f

    def test_name_is_sanitized_before_lookup(self, tmp_path: Path) -> None:
        f = tmp_path / "C_drive.json"
        f.write_text("{}", encoding="utf-8")
        assert _resolve_json_path("C:drive", tmp_path) == f

    def test_named_file_missing_exits_with_code_1(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit) as exc:
            _resolve_json_path("nonexistent", tmp_path)
        assert exc.value.code == 1

    def test_no_name_returns_latest(self, tmp_path: Path) -> None:
        a = tmp_path / "a.json"
        b = tmp_path / "b.json"
        a.write_text("{}", encoding="utf-8")
        time.sleep(0.02)
        b.write_text("{}", encoding="utf-8")
        assert _resolve_json_path(None, tmp_path) == b

    def test_no_name_and_empty_dir_exits_with_code_1(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit) as exc:
            _resolve_json_path(None, tmp_path)
        assert exc.value.code == 1


class TestReadJson:
    """Reading and parsing of a recorded run's JSON file."""

    def test_valid_json_returns_raw_and_dict(self, tmp_path: Path) -> None:
        payload = {"meta": {"name": "test"}, "tree": {}}
        f = tmp_path / "data.json"
        f.write_text(json.dumps(payload), encoding="utf-8")

        raw, data = _read_json(f)

        assert isinstance(raw, str)
        assert data["meta"]["name"] == "test"

    def test_raw_text_matches_file_content(self, tmp_path: Path) -> None:
        content = '{"key": "value"}'
        f = tmp_path / "data.json"
        f.write_text(content, encoding="utf-8")

        raw, _ = _read_json(f)

        assert raw == content

    def test_missing_file_exits_with_code_1(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit) as exc:
            _read_json(tmp_path / "nonexistent.json")
        assert exc.value.code == 1

    def test_malformed_json_exits_with_code_1(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.json"
        f.write_text("{ not valid json", encoding="utf-8")
        with pytest.raises(SystemExit) as exc:
            _read_json(f)
        assert exc.value.code == 1


class TestMissingAssets:
    """Detection of template files absent from the asset directory."""

    def test_all_assets_present_returns_empty_list(self, tmp_path: Path) -> None:
        t = _make_template_dir(tmp_path)
        assert _missing_assets(t) == []

    def test_missing_template_file_is_reported(self, tmp_path: Path) -> None:
        t = _make_template_dir(tmp_path)
        (t / "style.css").unlink()
        missing = _missing_assets(t)
        assert "style.css" in missing

    def test_all_template_files_missing_are_reported(self, tmp_path: Path) -> None:
        t = tmp_path / "empty_template"
        t.mkdir()
        missing = _missing_assets(t)
        assert set(missing) == {"index.html", "style.css", "main.js"}


class TestBuildReport:
    """Construction of a report directory from the template tree."""

    def test_creates_expected_files(self, tmp_path: Path) -> None:
        template_dir = _make_nested_template_dir(tmp_path)
        out_dir = tmp_path / "report" / "my-run"

        _build_report(out_dir, template_dir, '{"meta":{}}')

        assert (out_dir / "index.html").exists()
        assert (out_dir / "style.css").exists()
        assert (out_dir / "main.js").exists()
        assert (out_dir / "core" / "widget.js").exists()
        assert (out_dir / "data.json").exists()

    def test_data_json_content_matches_raw_input(self, tmp_path: Path) -> None:
        template_dir = _make_nested_template_dir(tmp_path)
        out_dir = tmp_path / "report" / "my-run"
        raw = '{"meta": {"name": "test-run"}}'

        _build_report(out_dir, template_dir, raw)

        assert (out_dir / "data.json").read_text(encoding="utf-8") == raw

    def test_template_content_is_copied_correctly(self, tmp_path: Path) -> None:
        template_dir = _make_nested_template_dir(tmp_path)
        out_dir = tmp_path / "report" / "my-run"

        _build_report(out_dir, template_dir, "{}")

        assert (out_dir / "index.html").read_text() == "content-index.html"
        assert (out_dir / "style.css").read_text() == "content-style.css"
        assert (out_dir / "main.js").read_text() == "content-main.js"
        assert (out_dir / "core" / "widget.js").read_text() == "content-widget.js"

    def test_creates_output_dir_if_missing(self, tmp_path: Path) -> None:
        template_dir = _make_nested_template_dir(tmp_path)
        out_dir = tmp_path / "deeply" / "nested" / "report"

        _build_report(out_dir, template_dir, "{}")

        assert out_dir.is_dir()

    def test_idempotent_on_second_call(
        self, tmp_path: Path, load_json: Callable[[Path], dict[str, Any]]
    ) -> None:
        template_dir = _make_nested_template_dir(tmp_path)
        out_dir = tmp_path / "report"

        _build_report(out_dir, template_dir, '{"v":1}')
        _build_report(out_dir, template_dir, '{"v":2}')

        assert load_json(out_dir / "data.json")["v"] == 2

    def test_no_extra_files_in_output(self, tmp_path: Path) -> None:
        template_dir = _make_nested_template_dir(tmp_path)
        out_dir = tmp_path / "report"

        _build_report(out_dir, template_dir, "{}")

        top_level = {p.name for p in out_dir.iterdir()}
        assert top_level == {"index.html", "style.css", "main.js", "core", "data.json"}

    def test_removes_preexisting_top_level_file_not_in_template(self, tmp_path: Path) -> None:
        template_dir = _make_nested_template_dir(tmp_path)
        out_dir = tmp_path / "report"
        out_dir.mkdir()
        (out_dir / "stale.js").write_text("leftover", encoding="utf-8")

        _build_report(out_dir, template_dir, "{}")

        assert not (out_dir / "stale.js").exists()

    def test_removes_preexisting_nested_directory_not_in_template(self, tmp_path: Path) -> None:
        template_dir = _make_nested_template_dir(tmp_path)
        out_dir = tmp_path / "report"
        (out_dir / "legacy").mkdir(parents=True)
        (out_dir / "legacy" / "old-widget.js").write_text("leftover", encoding="utf-8")

        _build_report(out_dir, template_dir, "{}")

        assert not (out_dir / "legacy").exists()


class TestStaging:
    """Assembly of a report beside its destination, and the cleanup that always follows."""

    def test_the_staging_directory_is_a_sibling_of_the_destination(self, tmp_path: Path) -> None:
        out_dir = tmp_path / "report" / "my-run"
        assert _staging_dir(out_dir).parent == out_dir.parent

    def test_the_staging_directory_is_dot_prefixed(self, tmp_path: Path) -> None:
        assert _staging_dir(tmp_path / "report" / "my-run").name.startswith(".")

    def test_no_staging_directory_survives_a_successful_build(self, tmp_path: Path) -> None:
        template_dir = _make_nested_template_dir(tmp_path)
        out_dir = tmp_path / "report" / "my-run"

        _build_report(out_dir, template_dir, "{}")

        assert not _staging_dir(out_dir).exists()

    def test_nothing_is_staged_when_the_build_fails_before_copying(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        template_dir = _make_nested_template_dir(tmp_path)
        out_dir = tmp_path / "report" / "my-run"
        out_dir.parent.mkdir()
        monkeypatch.setattr(report_mod.shutil, "copytree", _raising(OSError("disk full")))

        with pytest.raises(OSError):
            _build_report(out_dir, template_dir, "{}")

        assert not _staging_dir(out_dir).exists()

    def test_a_staged_tree_is_removed_when_the_build_fails_after_copying(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        template_dir = _make_nested_template_dir(tmp_path)
        out_dir = tmp_path / "report" / "my-run"
        out_dir.parent.mkdir()
        monkeypatch.setattr(
            report_mod.shutil, "copytree", _staged_then_raising(OSError("disk full"))
        )

        with pytest.raises(OSError):
            _build_report(out_dir, template_dir, "{}")

        assert list(out_dir.parent.iterdir()) == []

    def test_the_previous_report_survives_a_failed_rebuild(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        template_dir = _make_nested_template_dir(tmp_path)
        out_dir = tmp_path / "report" / "my-run"
        _build_report(out_dir, template_dir, '{"v":1}')
        monkeypatch.setattr(report_mod.shutil, "copytree", _raising(OSError("disk full")))

        with pytest.raises(OSError):
            _build_report(out_dir, template_dir, '{"v":2}')

        assert (out_dir / "data.json").read_text(encoding="utf-8") == '{"v":1}'

    def test_a_stale_staging_directory_does_not_leak_into_the_build(self, tmp_path: Path) -> None:
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

    def _cancelled(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        name_args: Callable[..., argparse.Namespace],
        escalating_run: Callable[[Command], AbstractContextManager[None]],
        press: Callable[[int], None],
        config: OutputConfig = _TRIMMED,
    ) -> Path:
        fs_dir, report_dir, _ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "my-run")
        command = Report(name_args("my-run"), config)
        monkeypatch.setattr(report_mod.shutil, "copytree", _cancelling(press))
        with escalating_run(command):
            with pytest.raises(Cancel):
                command.run()
        return report_dir

    def test_leaves_no_staging_directory(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        name_args: Callable[..., argparse.Namespace],
        escalating_run: Callable[[Command], AbstractContextManager[None]],
        press: Callable[[int], None],
    ) -> None:
        report_dir = self._cancelled(tmp_path, monkeypatch, name_args, escalating_run, press)
        assert not _staging_dir(report_dir / "my-run").exists()

    def test_writes_no_report(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        name_args: Callable[..., argparse.Namespace],
        escalating_run: Callable[[Command], AbstractContextManager[None]],
        press: Callable[[int], None],
    ) -> None:
        report_dir = self._cancelled(tmp_path, monkeypatch, name_args, escalating_run, press)
        assert not (report_dir / "my-run").exists()

    def test_says_it_was_canceled(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        name_args: Callable[..., argparse.Namespace],
        escalating_run: Callable[[Command], AbstractContextManager[None]],
        press: Callable[[int], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._cancelled(tmp_path, monkeypatch, name_args, escalating_run, press)
        assert "Canceled." in capsys.readouterr().out

    def test_the_trimmed_notice_is_the_bare_message(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        name_args: Callable[..., argparse.Namespace],
        escalating_run: Callable[[Command], AbstractContextManager[None]],
        press: Callable[[int], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._cancelled(tmp_path, monkeypatch, name_args, escalating_run, press)
        assert capsys.readouterr().out.splitlines()[-1] == "Canceled."

    def test_the_decorated_notice_carries_a_glyph(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        name_args: Callable[..., argparse.Namespace],
        escalating_run: Callable[[Command], AbstractContextManager[None]],
        press: Callable[[int], None],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._cancelled(tmp_path, monkeypatch, name_args, escalating_run, press, config=_DECORATED)
        assert capsys.readouterr().out.splitlines()[-1] == "! Canceled."


class TestInterruptedSwap:
    """An interrupt arriving in the moment a finished report replaces its predecessor."""

    def _rebuilt(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        name_args: Callable[..., argparse.Namespace],
    ) -> tuple[Outcome, Path]:
        fs_dir, report_dir, _ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "my-run")
        Report(name_args("my-run"), _TRIMMED).run()

        out_dir = report_dir / "my-run"
        command = Report(name_args("my-run"), _TRIMMED)
        monkeypatch.setattr(report_mod.shutil, "rmtree", _cancelling_removal_of(out_dir, command))
        return command.run(), out_dir

    def test_the_report_is_completed(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        name_args: Callable[..., argparse.Namespace],
    ) -> None:
        _, out_dir = self._rebuilt(tmp_path, monkeypatch, name_args)
        assert (out_dir / "data.json").exists()

    def test_the_run_still_succeeds(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        name_args: Callable[..., argparse.Namespace],
    ) -> None:
        outcome, _ = self._rebuilt(tmp_path, monkeypatch, name_args)
        assert outcome.code == EXIT_OK

    def test_the_run_still_points_at_boot(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        name_args: Callable[..., argparse.Namespace],
    ) -> None:
        outcome, _ = self._rebuilt(tmp_path, monkeypatch, name_args)
        assert outcome.next_step is not None
        assert outcome.next_step.command == "boot"

    def test_it_says_the_interrupt_came_too_late(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        name_args: Callable[..., argparse.Namespace],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        self._rebuilt(tmp_path, monkeypatch, name_args)
        assert "The report was already complete; it was kept." in capsys.readouterr().out


class TestOutcome:
    """The result a completed report reports back to the frame."""

    def test_a_successful_report_succeeds(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        name_args: Callable[..., argparse.Namespace],
    ) -> None:
        fs_dir, *_ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "my-run")
        assert Report(name_args("my-run"), _TRIMMED).run().code == EXIT_OK

    def test_a_successful_report_points_at_boot(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        name_args: Callable[..., argparse.Namespace],
    ) -> None:
        fs_dir, *_ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "my-run")
        outcome = Report(name_args("my-run"), _TRIMMED).run()
        assert outcome.next_step is not None
        assert outcome.next_step.command == "boot"

    def test_the_next_step_names_the_run(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        name_args: Callable[..., argparse.Namespace],
    ) -> None:
        fs_dir, *_ = _patch(monkeypatch, tmp_path)
        _make_fs_json(fs_dir, "my-run")
        outcome = Report(name_args("my-run"), _TRIMMED).run()
        assert outcome.next_step is not None
        assert outcome.next_step.name == "my-run"


def _report_building(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name_args: Callable[..., argparse.Namespace]
) -> Report:
    fs_dir, *_ = _patch(monkeypatch, tmp_path)
    _make_fs_json(fs_dir, "my-run")
    return Report(name_args("my-run"), _TRIMMED)


def _report_swapping(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name_args: Callable[..., argparse.Namespace]
) -> Report:
    command = _report_building(tmp_path, monkeypatch, name_args)
    command._entering_swap()
    return command


_CASES = [
    pytest.param(_report_building, "cancel", Response.UNWIND, "Canceled.", id="building/cancel"),
    pytest.param(_report_building, "abandon", Response.UNWIND, "Canceled.", id="building/abandon"),
    pytest.param(_report_swapping, "cancel", Response.HANDLED, None, id="swapping/cancel"),
    pytest.param(_report_swapping, "abandon", Response.HANDLED, None, id="swapping/abandon"),
]


class TestInterruptResponse:
    """What cancel() and abandon() answer and print, in each phase."""

    @pytest.mark.parametrize("make_command, action, expected, notice", _CASES)
    def test_interrupt_response(
        self,
        make_command: Callable[..., Report],
        action: str,
        expected: Response,
        notice: str | None,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        name_args: Callable[..., argparse.Namespace],
        assert_interrupt_response: Callable[..., None],
    ) -> None:
        command = make_command(tmp_path, monkeypatch, name_args)
        assert_interrupt_response(command, action, expected, notice)
