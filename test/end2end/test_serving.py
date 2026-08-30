"""End-to-end tests for the HTTP server that boot starts."""

from __future__ import annotations

import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest


class TestHttpServing:
    """Responses served over HTTP from a report directory."""

    def test_serve_returns_http_200_for_index(
        self, tmp_path: Path, serve_dir: Callable[..., Any]
    ) -> None:
        (tmp_path / "index.html").write_text("<h1>Splora</h1>", encoding="utf-8")

        server = serve_dir(tmp_path, 19200)

        resp = urllib.request.urlopen(server.url, timeout=3)
        assert resp.status == 200

    def test_serve_returns_correct_file_content(
        self, tmp_path: Path, serve_dir: Callable[..., Any]
    ) -> None:
        content = "<h1>hello splora</h1>"
        (tmp_path / "index.html").write_text(content, encoding="utf-8")

        server = serve_dir(tmp_path, 19220)

        body = urllib.request.urlopen(server.url, timeout=3).read()
        assert content.encode() in body

    def test_serve_returns_404_for_missing_file(
        self, tmp_path: Path, serve_dir: Callable[..., Any]
    ) -> None:
        server = serve_dir(tmp_path, 19240)

        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(server.url + "missing.html", timeout=3)
        assert exc.value.code == 404

    def test_serve_only_serves_from_report_dir(
        self, tmp_path: Path, serve_dir: Callable[..., Any]
    ) -> None:
        report_dir = tmp_path / "report"
        report_dir.mkdir()
        (report_dir / "page.html").write_text("inside", encoding="utf-8")
        (tmp_path / "secret.html").write_text("outside", encoding="utf-8")

        server = serve_dir(report_dir, 19260)

        resp = urllib.request.urlopen(server.url + "page.html", timeout=3)
        assert resp.status == 200

        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(server.url + "secret.html", timeout=3)
        assert exc.value.code == 404
