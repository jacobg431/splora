"""Integration tests for src/boot.py."""

from __future__ import annotations

import os
import time
from pathlib import Path
from unittest.mock import ANY, patch

import pytest

import src.boot as boot_mod
from src.boot import Boot, _finished_reports, _latest_report, _resolve_report_dir
from src.escalation import Response
from src.outcome import EXIT_OK, Outcome
from src.terminal import OutputConfig

_TRIMMED = OutputConfig(trim=True, use_color=False)


def _set_mtime(path: Path, when: float) -> None:
    os.utime(path, (when, when))


def _patch(monkeypatch, tmp_path: Path) -> Path:
    """Create a reports root directory and redirect _REPORT_DIR to it."""
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    monkeypatch.setattr(boot_mod, "_REPORT_DIR", report_dir)
    return report_dir


class TestBootCommand:
    """The boot command resolving a report and starting the server."""

    def test_calls_serve_with_correct_directory_and_port(
        self, tmp_path: Path, monkeypatch, name_args
    ) -> None:
        report_dir = _patch(monkeypatch, tmp_path)
        (report_dir / "my-run").mkdir()

        with patch.object(boot_mod, "_serve") as mock_serve:
            with patch.object(boot_mod, "_find_free_port", return_value=9001):
                Boot(name_args("my-run"), _TRIMMED).run()

        mock_serve.assert_called_once_with(report_dir / "my-run", 9001, should_stop=ANY)

    def test_resolves_latest_report_when_no_name_given(
        self, tmp_path: Path, monkeypatch, name_args
    ) -> None:
        report_dir = _patch(monkeypatch, tmp_path)
        (report_dir / "first").mkdir()
        time.sleep(0.02)
        (report_dir / "second").mkdir()

        with patch.object(boot_mod, "_serve") as mock_serve:
            with patch.object(boot_mod, "_find_free_port", return_value=9001):
                Boot(name_args(), _TRIMMED).run()

        mock_serve.assert_called_once_with(report_dir / "second", 9001, should_stop=ANY)

    def test_name_sanitization_resolves_correct_directory(
        self, tmp_path: Path, monkeypatch, name_args
    ) -> None:
        report_dir = _patch(monkeypatch, tmp_path)
        (report_dir / "C_drive").mkdir()

        with patch.object(boot_mod, "_serve") as mock_serve:
            with patch.object(boot_mod, "_find_free_port", return_value=9001):
                Boot(name_args("C:drive"), _TRIMMED).run()

        mock_serve.assert_called_once_with(report_dir / "C_drive", 9001, should_stop=ANY)

    def test_unknown_name_exits_with_code_1(self, tmp_path: Path, monkeypatch, name_args) -> None:
        _patch(monkeypatch, tmp_path)

        with pytest.raises(SystemExit) as exc:
            Boot(name_args("nonexistent"), _TRIMMED).run()
        assert exc.value.code == 1

    def test_empty_report_dir_exits_with_code_1(
        self, tmp_path: Path, monkeypatch, name_args
    ) -> None:
        _patch(monkeypatch, tmp_path)

        with pytest.raises(SystemExit) as exc:
            Boot(name_args(), _TRIMMED).run()
        assert exc.value.code == 1

    def test_port_is_found_before_serve_is_called(
        self, tmp_path: Path, monkeypatch, name_args
    ) -> None:
        report_dir = _patch(monkeypatch, tmp_path)
        (report_dir / "my-run").mkdir()

        call_order = []

        def fake_find_port():
            call_order.append("find_port")
            return 9001

        def fake_serve(d, p, **_):
            call_order.append("serve")

        with patch.object(boot_mod, "_find_free_port", side_effect=fake_find_port):
            with patch.object(boot_mod, "_serve", side_effect=fake_serve):
                Boot(name_args("my-run"), _TRIMMED).run()

        assert call_order == ["find_port", "serve"]


class TestStopping:
    """How the command ends once the user interrupts the server it started."""

    def _served(self, tmp_path: Path, monkeypatch, name_args, action: str) -> Outcome:
        report_dir = _patch(monkeypatch, tmp_path)
        (report_dir / "my-run").mkdir()
        command = Boot(name_args("my-run"), _TRIMMED)

        def fake_serve(_report_dir, _port, *, should_stop, **_kwargs) -> None:
            getattr(command, action)()
            assert should_stop()

        with patch.object(boot_mod, "_find_free_port", return_value=9001):
            with patch.object(boot_mod, "_serve", side_effect=fake_serve):
                return command.run()

    def test_a_cancel_ends_the_run_cleanly(self, tmp_path: Path, monkeypatch, name_args) -> None:
        assert self._served(tmp_path, monkeypatch, name_args, "cancel").code == EXIT_OK

    def test_a_cancel_offers_no_next_step(self, tmp_path: Path, monkeypatch, name_args) -> None:
        assert self._served(tmp_path, monkeypatch, name_args, "cancel").next_step is None

    def test_an_abandon_also_ends_the_run_cleanly(
        self, tmp_path: Path, monkeypatch, name_args
    ) -> None:
        assert self._served(tmp_path, monkeypatch, name_args, "abandon").code == EXIT_OK


def _boot_serving(name_args) -> Boot:
    return Boot(name_args("my-run"), _TRIMMED)


_CASES = [
    pytest.param(_boot_serving, "cancel", Response.HANDLED, "Stopped.", id="serving/cancel"),
    pytest.param(_boot_serving, "abandon", Response.HANDLED, "Stopped.", id="serving/abandon"),
]


class TestInterruptResponse:
    """What cancel() and abandon() answer and print."""

    @pytest.mark.parametrize("make_command, action, expected, notice", _CASES)
    def test_interrupt_response(
        self, make_command, action, expected, notice, name_args, assert_interrupt_response
    ) -> None:
        command = make_command(name_args)
        assert_interrupt_response(command, action, expected, notice)


class TestLatestReport:
    """Selection of the most recently modified report directory."""

    def test_nonexistent_report_dir_returns_none(self, tmp_path: Path) -> None:
        assert _latest_report(tmp_path / "does-not-exist") is None

    def test_empty_report_dir_returns_none(self, tmp_path: Path) -> None:
        assert _latest_report(tmp_path) is None

    def test_single_subdirectory_is_returned(self, tmp_path: Path) -> None:
        (tmp_path / "run-a").mkdir()
        assert _latest_report(tmp_path) == tmp_path / "run-a"

    def test_files_in_report_dir_are_ignored(self, tmp_path: Path) -> None:
        (tmp_path / "stray.json").write_text("{}", encoding="utf-8")
        assert _latest_report(tmp_path) is None

    def test_returns_most_recently_modified_dir(self, tmp_path: Path) -> None:
        old = tmp_path / "old-run"
        old.mkdir()
        time.sleep(0.02)
        new = tmp_path / "new-run"
        new.mkdir()
        assert _latest_report(tmp_path) == new

    def test_ignores_nested_subdirectories(self, tmp_path: Path) -> None:
        parent = tmp_path / "run-a"
        parent.mkdir()
        (parent / "nested").mkdir()
        # Only direct children count; nested should not influence the result
        assert _latest_report(tmp_path) == parent


class TestResolveReportDir:
    """Resolution of a report directory by name or by recency."""

    def test_named_dir_that_exists_is_returned(self, tmp_path: Path) -> None:
        (tmp_path / "my-run").mkdir()
        assert _resolve_report_dir("my-run", tmp_path) == tmp_path / "my-run"

    def test_name_is_sanitized_before_lookup(self, tmp_path: Path) -> None:
        (tmp_path / "C_drive").mkdir()
        assert _resolve_report_dir("C:drive", tmp_path) == tmp_path / "C_drive"

    def test_named_dir_missing_exits_with_code_1(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit) as exc:
            _resolve_report_dir("nonexistent", tmp_path)
        assert exc.value.code == 1

    def test_named_path_that_is_a_file_exits_with_code_1(self, tmp_path: Path) -> None:
        (tmp_path / "not-a-dir").write_text("x", encoding="utf-8")
        with pytest.raises(SystemExit) as exc:
            _resolve_report_dir("not-a-dir", tmp_path)
        assert exc.value.code == 1

    def test_no_name_returns_latest_dir(self, tmp_path: Path) -> None:
        (tmp_path / "first").mkdir()
        time.sleep(0.02)
        (tmp_path / "second").mkdir()
        assert _resolve_report_dir(None, tmp_path) == tmp_path / "second"

    def test_no_name_empty_dir_exits_with_code_1(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit) as exc:
            _resolve_report_dir(None, tmp_path)
        assert exc.value.code == 1

    def test_no_name_nonexistent_report_dir_exits_with_code_1(self, tmp_path: Path) -> None:
        with pytest.raises(SystemExit) as exc:
            _resolve_report_dir(None, tmp_path / "missing")
        assert exc.value.code == 1


class TestStagingDirectoriesAreIgnored:
    """A report still being staged must never be mistaken for one ready to serve."""

    def test_finished_reports_excludes_a_staging_directory(self, tmp_path: Path) -> None:
        (tmp_path / "run-a").mkdir()
        (tmp_path / ".run-a.tmp").mkdir()
        assert _finished_reports(tmp_path) == [tmp_path / "run-a"]

    def test_finished_reports_excludes_files(self, tmp_path: Path) -> None:
        (tmp_path / "run-a").mkdir()
        (tmp_path / "stray.json").write_text("{}", encoding="utf-8")
        assert _finished_reports(tmp_path) == [tmp_path / "run-a"]

    def test_finished_reports_is_empty_when_only_staging_remains(self, tmp_path: Path) -> None:
        (tmp_path / ".run-a.tmp").mkdir()
        assert _finished_reports(tmp_path) == []

    def test_a_newer_staging_directory_is_not_chosen_as_the_latest(self, tmp_path: Path) -> None:
        finished = tmp_path / "run-a"
        finished.mkdir()
        staging = tmp_path / ".run-a.tmp"
        staging.mkdir()
        _set_mtime(finished, 1_000_000)
        _set_mtime(staging, 2_000_000)
        assert _latest_report(tmp_path) == finished

    def test_only_staging_directories_resolve_to_nothing(self, tmp_path: Path) -> None:
        (tmp_path / ".run-a.tmp").mkdir()
        assert _latest_report(tmp_path) is None

    def test_resolving_without_a_name_skips_a_newer_staging_directory(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        report_dir = _patch(monkeypatch, tmp_path)
        finished = report_dir / "run-a"
        finished.mkdir()
        staging = report_dir / ".run-a.tmp"
        staging.mkdir()
        _set_mtime(finished, 1_000_000)
        _set_mtime(staging, 2_000_000)
        assert _resolve_report_dir(None, report_dir) == finished

    def test_a_staging_directory_alone_leaves_nothing_to_serve(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        report_dir = _patch(monkeypatch, tmp_path)
        (report_dir / ".run-a.tmp").mkdir()
        with pytest.raises(SystemExit) as exc:
            _resolve_report_dir(None, report_dir)
        assert exc.value.code == 1
