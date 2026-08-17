"""Unit tests for src/boot.py."""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.boot import (
    _find_free_port,
    _latest_report,
    _resolve_report_dir,
    _sanitize,
    _serve,
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


# ── _latest_report ─────────────────────────────────────────────────────────


class TestLatestReport:
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


# ── _resolve_report_dir ────────────────────────────────────────────────────


class TestResolveReportDir:
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


# ── _find_free_port ────────────────────────────────────────────────────────


class TestFindFreePort:
    def _mock_socket(self, bind_side_effect=None):
        """Return a mock socket context manager."""
        s = MagicMock()
        s.__enter__.return_value = s
        s.__exit__.return_value = False
        if bind_side_effect is not None:
            s.bind.side_effect = bind_side_effect
        return s

    def test_returns_start_port_when_it_is_free(self):
        mock_s = self._mock_socket()
        with patch("src.boot.socket.socket", return_value=mock_s):
            port = _find_free_port(start=7000, attempts=5)
        assert port == 7000
        mock_s.bind.assert_called_once_with(("127.0.0.1", 7000))

    def test_skips_occupied_ports_and_returns_next_free(self):
        mock_s = self._mock_socket(bind_side_effect=[OSError, OSError, None])
        with patch("src.boot.socket.socket", return_value=mock_s):
            port = _find_free_port(start=7000, attempts=5)
        assert port == 7002

    def test_raises_os_error_when_all_ports_occupied(self):
        mock_s = self._mock_socket(bind_side_effect=OSError)
        with patch("src.boot.socket.socket", return_value=mock_s):
            with pytest.raises(OSError):
                _find_free_port(start=7000, attempts=3)
        assert mock_s.bind.call_count == 3

    def test_returns_port_within_the_specified_range(self):
        mock_s = self._mock_socket(bind_side_effect=[OSError, OSError, None])
        with patch("src.boot.socket.socket", return_value=mock_s):
            port = _find_free_port(start=8000, attempts=10)
        assert 8000 <= port < 8010


# ── _serve ─────────────────────────────────────────────────────────────────


class TestServe:
    def _make_httpd_mock(self):
        """Build a mock HTTPServer that raises KeyboardInterrupt on serve_forever."""
        httpd = MagicMock()
        httpd.__enter__ = MagicMock(return_value=httpd)
        httpd.__exit__ = MagicMock(return_value=False)
        httpd.serve_forever.side_effect = KeyboardInterrupt
        return httpd

    def test_opens_browser_when_open_browser_is_true(self, tmp_path: Path):
        httpd = self._make_httpd_mock()
        with patch("src.boot.http.server.HTTPServer", return_value=httpd):
            with patch("src.boot.webbrowser.open") as mock_open:
                _serve(tmp_path, 5050, open_browser=True)
        mock_open.assert_called_once_with("http://localhost:5050/")

    def test_does_not_open_browser_when_open_browser_is_false(self, tmp_path: Path):
        httpd = self._make_httpd_mock()
        with patch("src.boot.http.server.HTTPServer", return_value=httpd):
            with patch("src.boot.webbrowser.open") as mock_open:
                _serve(tmp_path, 5050, open_browser=False)
        mock_open.assert_not_called()

    def test_binds_to_localhost_on_given_port(self, tmp_path: Path):
        httpd = self._make_httpd_mock()
        with patch("src.boot.http.server.HTTPServer", return_value=httpd) as MockServer:
            with patch("src.boot.webbrowser.open"):
                _serve(tmp_path, 8080, open_browser=False)
        MockServer.assert_called_once_with(("127.0.0.1", 8080), MockServer.call_args[0][1])

    def test_serve_forever_is_called(self, tmp_path: Path):
        httpd = self._make_httpd_mock()
        with patch("src.boot.http.server.HTTPServer", return_value=httpd):
            with patch("src.boot.webbrowser.open"):
                _serve(tmp_path, 5050, open_browser=False)
        httpd.serve_forever.assert_called_once()

    def test_keyboard_interrupt_is_handled_gracefully(self, tmp_path: Path):
        httpd = self._make_httpd_mock()
        with patch("src.boot.http.server.HTTPServer", return_value=httpd):
            with patch("src.boot.webbrowser.open"):
                # Should NOT propagate KeyboardInterrupt to the caller
                _serve(tmp_path, 5050, open_browser=False)

    def test_url_is_constructed_from_port(self, tmp_path: Path):
        httpd = self._make_httpd_mock()
        with patch("src.boot.http.server.HTTPServer", return_value=httpd):
            with patch("src.boot.webbrowser.open") as mock_open:
                _serve(tmp_path, 9999, open_browser=True)
        mock_open.assert_called_once_with("http://localhost:9999/")
