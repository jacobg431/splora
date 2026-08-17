"""Integration tests for src/boot.py.

Most tests call boot() end-to-end with _REPORT_DIR monkeypatched and _serve
mocked to avoid blocking. One test starts a real HTTP server in a daemon thread
to verify that files are actually served over the network.
"""

from __future__ import annotations

import argparse
import threading
import time
import urllib.request
from pathlib import Path
from unittest.mock import patch

import pytest

import src.boot as boot_mod
from src.boot import _find_free_port, _serve, boot

# ── Shared helpers ─────────────────────────────────────────────────────────


def _args(name: str | None = None) -> argparse.Namespace:
    return argparse.Namespace(name=name)


def _patch(monkeypatch, tmp_path: Path) -> Path:
    """Create a reports root directory and redirect _REPORT_DIR to it."""
    report_dir = tmp_path / "reports"
    report_dir.mkdir()
    monkeypatch.setattr(boot_mod, "_REPORT_DIR", report_dir)
    return report_dir


# ── Tests ──────────────────────────────────────────────────────────────────


class TestBootCommand:
    def test_calls_serve_with_correct_directory_and_port(self, tmp_path: Path, monkeypatch):
        report_dir = _patch(monkeypatch, tmp_path)
        (report_dir / "my-run").mkdir()

        with patch.object(boot_mod, "_serve") as mock_serve:
            with patch.object(boot_mod, "_find_free_port", return_value=9001):
                boot(_args("my-run"))

        mock_serve.assert_called_once_with(report_dir / "my-run", 9001)

    def test_resolves_latest_report_when_no_name_given(self, tmp_path: Path, monkeypatch):
        report_dir = _patch(monkeypatch, tmp_path)
        (report_dir / "first").mkdir()
        time.sleep(0.02)
        (report_dir / "second").mkdir()

        with patch.object(boot_mod, "_serve") as mock_serve:
            with patch.object(boot_mod, "_find_free_port", return_value=9001):
                boot(_args())

        mock_serve.assert_called_once_with(report_dir / "second", 9001)

    def test_name_sanitization_resolves_correct_directory(self, tmp_path: Path, monkeypatch):
        report_dir = _patch(monkeypatch, tmp_path)
        (report_dir / "C_drive").mkdir()

        with patch.object(boot_mod, "_serve") as mock_serve:
            with patch.object(boot_mod, "_find_free_port", return_value=9001):
                boot(_args("C:drive"))

        mock_serve.assert_called_once_with(report_dir / "C_drive", 9001)

    def test_unknown_name_exits_with_code_1(self, tmp_path: Path, monkeypatch):
        _patch(monkeypatch, tmp_path)

        with pytest.raises(SystemExit) as exc:
            boot(_args("nonexistent"))
        assert exc.value.code == 1

    def test_empty_report_dir_exits_with_code_1(self, tmp_path: Path, monkeypatch):
        _patch(monkeypatch, tmp_path)

        with pytest.raises(SystemExit) as exc:
            boot(_args())
        assert exc.value.code == 1

    def test_port_is_found_before_serve_is_called(self, tmp_path: Path, monkeypatch):
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
                boot(_args("my-run"))

        assert call_order == ["find_port", "serve"]


class TestHttpServing:
    def test_serve_returns_http_200_for_index(self, tmp_path: Path):
        (tmp_path / "index.html").write_text("<h1>Splora</h1>", encoding="utf-8")

        port = _find_free_port(start=19200)
        thread = threading.Thread(
            target=_serve,
            kwargs={"report_dir": tmp_path, "port": port, "open_browser": False},
            daemon=True,
        )
        thread.start()
        time.sleep(0.2)

        resp = urllib.request.urlopen(f"http://localhost:{port}/", timeout=3)
        assert resp.status == 200

    def test_serve_returns_correct_file_content(self, tmp_path: Path):
        content = "<h1>hello splora</h1>"
        (tmp_path / "index.html").write_text(content, encoding="utf-8")

        port = _find_free_port(start=19220)
        thread = threading.Thread(
            target=_serve,
            kwargs={"report_dir": tmp_path, "port": port, "open_browser": False},
            daemon=True,
        )
        thread.start()
        time.sleep(0.2)

        body = urllib.request.urlopen(f"http://localhost:{port}/", timeout=3).read()
        assert content.encode() in body

    def test_serve_returns_404_for_missing_file(self, tmp_path: Path):
        port = _find_free_port(start=19240)
        thread = threading.Thread(
            target=_serve,
            kwargs={"report_dir": tmp_path, "port": port, "open_browser": False},
            daemon=True,
        )
        thread.start()
        time.sleep(0.2)

        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(f"http://localhost:{port}/missing.html", timeout=3)
        assert exc.value.code == 404

    def test_serve_only_serves_from_report_dir(self, tmp_path: Path):
        report_dir = tmp_path / "report"
        report_dir.mkdir()
        (report_dir / "page.html").write_text("inside", encoding="utf-8")
        (tmp_path / "secret.html").write_text("outside", encoding="utf-8")

        port = _find_free_port(start=19260)
        thread = threading.Thread(
            target=_serve,
            kwargs={"report_dir": report_dir, "port": port, "open_browser": False},
            daemon=True,
        )
        thread.start()
        time.sleep(0.2)

        # File inside report dir is accessible
        resp = urllib.request.urlopen(f"http://localhost:{port}/page.html", timeout=3)
        assert resp.status == 200

        # File outside report dir is not accessible
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(f"http://localhost:{port}/secret.html", timeout=3)
        assert exc.value.code == 404
