"""Integration tests for src/boot.py."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import patch

import pytest

import src.boot as boot_mod
from src.boot import _latest_report, _resolve_report_dir, boot
from src.terminal import OutputConfig

_TRIMMED = OutputConfig(trim=True, use_color=False)


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
    ):
        report_dir = _patch(monkeypatch, tmp_path)
        (report_dir / "my-run").mkdir()

        with patch.object(boot_mod, "_serve") as mock_serve:
            with patch.object(boot_mod, "_find_free_port", return_value=9001):
                boot(name_args("my-run"), _TRIMMED)

        mock_serve.assert_called_once_with(report_dir / "my-run", 9001, config=_TRIMMED)

    def test_resolves_latest_report_when_no_name_given(
        self, tmp_path: Path, monkeypatch, name_args
    ):
        report_dir = _patch(monkeypatch, tmp_path)
        (report_dir / "first").mkdir()
        time.sleep(0.02)
        (report_dir / "second").mkdir()

        with patch.object(boot_mod, "_serve") as mock_serve:
            with patch.object(boot_mod, "_find_free_port", return_value=9001):
                boot(name_args(), _TRIMMED)

        mock_serve.assert_called_once_with(report_dir / "second", 9001, config=_TRIMMED)

    def test_name_sanitization_resolves_correct_directory(
        self, tmp_path: Path, monkeypatch, name_args
    ):
        report_dir = _patch(monkeypatch, tmp_path)
        (report_dir / "C_drive").mkdir()

        with patch.object(boot_mod, "_serve") as mock_serve:
            with patch.object(boot_mod, "_find_free_port", return_value=9001):
                boot(name_args("C:drive"), _TRIMMED)

        mock_serve.assert_called_once_with(report_dir / "C_drive", 9001, config=_TRIMMED)

    def test_unknown_name_exits_with_code_1(self, tmp_path: Path, monkeypatch, name_args):
        _patch(monkeypatch, tmp_path)

        with pytest.raises(SystemExit) as exc:
            boot(name_args("nonexistent"), _TRIMMED)
        assert exc.value.code == 1

    def test_empty_report_dir_exits_with_code_1(self, tmp_path: Path, monkeypatch, name_args):
        _patch(monkeypatch, tmp_path)

        with pytest.raises(SystemExit) as exc:
            boot(name_args(), _TRIMMED)
        assert exc.value.code == 1

    def test_port_is_found_before_serve_is_called(self, tmp_path: Path, monkeypatch, name_args):
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
                boot(name_args("my-run"), _TRIMMED)

        assert call_order == ["find_port", "serve"]


class TestLatestReport:
    """Selection of the most recently modified report directory."""

    def test_nonexistent_report_dir_returns_none(self, tmp_path: Path):
        assert _latest_report(tmp_path / "does-not-exist") is None

    def test_empty_report_dir_returns_none(self, tmp_path: Path):
        assert _latest_report(tmp_path) is None

    def test_single_subdirectory_is_returned(self, tmp_path: Path):
        (tmp_path / "run-a").mkdir()
        assert _latest_report(tmp_path) == tmp_path / "run-a"

    def test_files_in_report_dir_are_ignored(self, tmp_path: Path):
        (tmp_path / "stray.json").write_text("{}", encoding="utf-8")
        assert _latest_report(tmp_path) is None

    def test_returns_most_recently_modified_dir(self, tmp_path: Path):
        old = tmp_path / "old-run"
        old.mkdir()
        time.sleep(0.02)
        new = tmp_path / "new-run"
        new.mkdir()
        assert _latest_report(tmp_path) == new

    def test_ignores_nested_subdirectories(self, tmp_path: Path):
        parent = tmp_path / "run-a"
        parent.mkdir()
        (parent / "nested").mkdir()
        # Only direct children count; nested should not influence the result
        assert _latest_report(tmp_path) == parent


class TestResolveReportDir:
    """Resolution of a report directory by name or by recency."""

    def test_named_dir_that_exists_is_returned(self, tmp_path: Path):
        (tmp_path / "my-run").mkdir()
        assert _resolve_report_dir("my-run", tmp_path) == tmp_path / "my-run"

    def test_name_is_sanitized_before_lookup(self, tmp_path: Path):
        (tmp_path / "C_drive").mkdir()
        assert _resolve_report_dir("C:drive", tmp_path) == tmp_path / "C_drive"

    def test_named_dir_missing_exits_with_code_1(self, tmp_path: Path):
        with pytest.raises(SystemExit) as exc:
            _resolve_report_dir("nonexistent", tmp_path)
        assert exc.value.code == 1

    def test_named_path_that_is_a_file_exits_with_code_1(self, tmp_path: Path):
        (tmp_path / "not-a-dir").write_text("x", encoding="utf-8")
        with pytest.raises(SystemExit) as exc:
            _resolve_report_dir("not-a-dir", tmp_path)
        assert exc.value.code == 1

    def test_no_name_returns_latest_dir(self, tmp_path: Path):
        (tmp_path / "first").mkdir()
        time.sleep(0.02)
        (tmp_path / "second").mkdir()
        assert _resolve_report_dir(None, tmp_path) == tmp_path / "second"

    def test_no_name_empty_dir_exits_with_code_1(self, tmp_path: Path):
        with pytest.raises(SystemExit) as exc:
            _resolve_report_dir(None, tmp_path)
        assert exc.value.code == 1

    def test_no_name_nonexistent_report_dir_exits_with_code_1(self, tmp_path: Path):
        with pytest.raises(SystemExit) as exc:
            _resolve_report_dir(None, tmp_path / "missing")
        assert exc.value.code == 1
