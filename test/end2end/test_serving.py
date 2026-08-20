"""End-to-end tests for the HTTP server that boot starts."""

from __future__ import annotations

import socket
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from src.boot import _find_free_port, _serve


def _wait_until_listening(port: int, timeout: float = 5.0) -> None:
    """Block until the server accepts a connection on port."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.01)
    raise AssertionError(f"no server listening on port {port} after {timeout}s")


def _start_server(report_dir: Path, start_port: int) -> str:
    """Serve report_dir from a daemon thread and return the URL it answers on."""
    port = _find_free_port(start=start_port)
    threading.Thread(
        target=_serve,
        kwargs={"report_dir": report_dir, "port": port, "open_browser": False},
        daemon=True,
    ).start()
    _wait_until_listening(port)
    return f"http://127.0.0.1:{port}/"


class TestHttpServing:
    """Responses served over HTTP from a report directory."""

    def test_serve_returns_http_200_for_index(self, tmp_path: Path):
        (tmp_path / "index.html").write_text("<h1>Splora</h1>", encoding="utf-8")

        url = _start_server(tmp_path, 19200)

        resp = urllib.request.urlopen(url, timeout=3)
        assert resp.status == 200

    def test_serve_returns_correct_file_content(self, tmp_path: Path):
        content = "<h1>hello splora</h1>"
        (tmp_path / "index.html").write_text(content, encoding="utf-8")

        url = _start_server(tmp_path, 19220)

        body = urllib.request.urlopen(url, timeout=3).read()
        assert content.encode() in body

    def test_serve_returns_404_for_missing_file(self, tmp_path: Path):
        url = _start_server(tmp_path, 19240)

        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(url + "missing.html", timeout=3)
        assert exc.value.code == 404

    def test_serve_only_serves_from_report_dir(self, tmp_path: Path):
        report_dir = tmp_path / "report"
        report_dir.mkdir()
        (report_dir / "page.html").write_text("inside", encoding="utf-8")
        (tmp_path / "secret.html").write_text("outside", encoding="utf-8")

        url = _start_server(report_dir, 19260)

        resp = urllib.request.urlopen(url + "page.html", timeout=3)
        assert resp.status == 200

        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(url + "secret.html", timeout=3)
        assert exc.value.code == 404
