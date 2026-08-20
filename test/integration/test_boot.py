"""Integration tests for src/boot.py."""

from __future__ import annotations

import threading
import time
import urllib.request
from pathlib import Path
from unittest.mock import patch

import pytest

import src.boot as boot_mod
from src.boot import _find_free_port, _latest_report, _resolve_report_dir, _serve, boot


def _patch(monkeypatch, tmp_path: Path) -> Path:
    """Create a reports root directory and redirect _REPORT_DIR to it."""
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    monkeypatch.setattr(boot_mod, "_REPORT_DIR", report_dir)
    return report_dir


def _start_server(report_dir: Path, start_port: int) -> int:
    """Serve report_dir from a daemon thread and return the port it listens on."""
    port = _find_free_port(start=start_port)
    threading.Thread(
        target=_serve,
        kwargs={"report_dir": report_dir, "port": port, "open_browser": False},
        daemon=True,
    ).start()
    time.sleep(0.2)
    return port


class TestBootCommand:
    """The boot command resolving a report and starting the server."""

    def test_calls_serve_with_correct_directory_and_port(
        self, tmp_path: Path, monkeypatch, name_args
    ):
        report_dir = _patch(monkeypatch, tmp_path)
        (report_dir / "my-run").mkdir()

        with patch.object(boot_mod, "_serve") as mock_serve:
            with patch.object(boot_mod, "_find_free_port", return_value=9001):
                boot(name_args("my-run"))

        mock_serve.assert_called_once_with(report_dir / "my-run", 9001)

    def test_resolves_latest_report_when_no_name_given(
        self, tmp_path: Path, monkeypatch, name_args
    ):
        report_dir = _patch(monkeypatch, tmp_path)
        (report_dir / "first").mkdir()
        time.sleep(0.02)
        (report_dir / "second").mkdir()

        with patch.object(boot_mod, "_serve") as mock_serve:
            with patch.object(boot_mod, "_find_free_port", return_value=9001):
                boot(name_args())

        mock_serve.assert_called_once_with(report_dir / "second", 9001)

    def test_name_sanitization_resolves_correct_directory(
        self, tmp_path: Path, monkeypatch, name_args
    ):
        report_dir = _patch(monkeypatch, tmp_path)
        (report_dir / "C_drive").mkdir()

        with patch.object(boot_mod, "_serve") as mock_serve:
            with patch.object(boot_mod, "_find_free_port", return_value=9001):
                boot(name_args("C:drive"))

        mock_serve.assert_called_once_with(report_dir / "C_drive", 9001)

    def test_unknown_name_exits_with_code_1(self, tmp_path: Path, monkeypatch, name_args):
        _patch(monkeypatch, tmp_path)

        with pytest.raises(SystemExit) as exc:
            boot(name_args("nonexistent"))
        assert exc.value.code == 1

    def test_empty_report_dir_exits_with_code_1(self, tmp_path: Path, monkeypatch, name_args):
        _patch(monkeypatch, tmp_path)

        with pytest.raises(SystemExit) as exc:
            boot(name_args())
        assert exc.value.code == 1

    def test_port_is_found_before_serve_is_called(self, tmp_path: Path, monkeypatch, name_args):
        report_dir = _patch(monkeypatch, tmp_path)
        (report_dir / "my-run").mkdir()

        call_order = []

        def fake_find_port():
            call_order.append("find_port")
            return 9001

        def fake_serve(d, p):
            call_order.append("serve")

        with patch.object(boot_mod, "_find_free_port", side_effect=fake_find_port):
            with patch.object(boot_mod, "_serve", side_effect=fake_serve):
                boot(name_args("my-run"))

        assert call_order == ["find_port", "serve"]


class TestHttpServing:
    """Responses served over HTTP from a report directory."""

    def test_serve_returns_http_200_for_index(self, tmp_path: Path):
        (tmp_path / "index.html").write_text("<h1>Splora</h1>", encoding="utf-8")

        port = _start_server(tmp_path, 19200)

        resp = urllib.request.urlopen(f"http://localhost:{port}/", timeout=3)
        assert resp.status == 200

    def test_serve_returns_correct_file_content(self, tmp_path: Path):
        content = "<h1>hello splora</h1>"
        (tmp_path / "index.html").write_text(content, encoding="utf-8")

        port = _start_server(tmp_path, 19220)

        body = urllib.request.urlopen(f"http://localhost:{port}/", timeout=3).read()
        assert content.encode() in body

    def test_serve_returns_404_for_missing_file(self, tmp_path: Path):
        port = _start_server(tmp_path, 19240)

        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(f"http://localhost:{port}/missing.html", timeout=3)
        assert exc.value.code == 404

    def test_serve_only_serves_from_report_dir(self, tmp_path: Path):
        report_dir = tmp_path / "report"
        report_dir.mkdir()
        (report_dir / "page.html").write_text("inside", encoding="utf-8")
        (tmp_path / "secret.html").write_text("outside", encoding="utf-8")

        port = _start_server(report_dir, 19260)

        # File inside report dir is accessible
        resp = urllib.request.urlopen(f"http://localhost:{port}/page.html", timeout=3)
        assert resp.status == 200

        # File outside report dir is not accessible
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(f"http://localhost:{port}/secret.html", timeout=3)
        assert exc.value.code == 404


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
