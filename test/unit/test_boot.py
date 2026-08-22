"""Unit tests for src/boot.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.boot import _find_free_port, _sanitize, _serve
from src.terminal import OutputConfig

_SERVED_DIR = Path("/reports/my-run")


_TRIMMED = OutputConfig(trim=True, use_color=False)
_DECORATED = OutputConfig(trim=False, use_color=False)


class TestSanitize:
    """Name sanitization applied before a report directory lookup."""

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


class TestFindFreePort:
    """Selection of the first available port within the scan range."""

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


class TestServe:
    """Server startup, browser launch, and interrupt handling."""

    def _make_httpd_mock(self):
        """Build a mock HTTPServer that raises KeyboardInterrupt on serve_forever."""
        httpd = MagicMock()
        httpd.__enter__ = MagicMock(return_value=httpd)
        httpd.__exit__ = MagicMock(return_value=False)
        httpd.serve_forever.side_effect = KeyboardInterrupt
        return httpd

    def test_opens_browser_when_open_browser_is_true(self):
        httpd = self._make_httpd_mock()
        with patch("src.boot.http.server.HTTPServer", return_value=httpd):
            with patch("src.boot.webbrowser.open") as mock_open:
                _serve(_SERVED_DIR, 5050, config=_TRIMMED, open_browser=True)
        mock_open.assert_called_once_with("http://localhost:5050/")

    def test_does_not_open_browser_when_open_browser_is_false(self):
        httpd = self._make_httpd_mock()
        with patch("src.boot.http.server.HTTPServer", return_value=httpd):
            with patch("src.boot.webbrowser.open") as mock_open:
                _serve(_SERVED_DIR, 5050, config=_TRIMMED, open_browser=False)
        mock_open.assert_not_called()

    def test_binds_to_localhost_on_given_port(self):
        httpd = self._make_httpd_mock()
        with patch("src.boot.http.server.HTTPServer", return_value=httpd) as MockServer:
            with patch("src.boot.webbrowser.open"):
                _serve(_SERVED_DIR, 8080, config=_TRIMMED, open_browser=False)
        MockServer.assert_called_once_with(("127.0.0.1", 8080), MockServer.call_args[0][1])

    def test_serve_forever_is_called(self):
        httpd = self._make_httpd_mock()
        with patch("src.boot.http.server.HTTPServer", return_value=httpd):
            with patch("src.boot.webbrowser.open"):
                _serve(_SERVED_DIR, 5050, config=_TRIMMED, open_browser=False)
        httpd.serve_forever.assert_called_once()

    def test_keyboard_interrupt_is_handled_gracefully(self):
        httpd = self._make_httpd_mock()
        with patch("src.boot.http.server.HTTPServer", return_value=httpd):
            with patch("src.boot.webbrowser.open"):
                # Should NOT propagate KeyboardInterrupt to the caller
                _serve(_SERVED_DIR, 5050, config=_TRIMMED, open_browser=False)

    def test_stopping_says_so(self, capsys):
        httpd = self._make_httpd_mock()
        with patch("src.boot.http.server.HTTPServer", return_value=httpd):
            with patch("src.boot.webbrowser.open"):
                _serve(_SERVED_DIR, 5050, config=_TRIMMED, open_browser=False)
        assert capsys.readouterr().out.splitlines()[-1] == "Stopped."

    def test_the_decorated_stop_notice_carries_a_glyph(self, capsys):
        httpd = self._make_httpd_mock()
        with patch("src.boot.http.server.HTTPServer", return_value=httpd):
            with patch("src.boot.webbrowser.open"):
                _serve(_SERVED_DIR, 5050, config=_DECORATED, open_browser=False)
        assert capsys.readouterr().out.splitlines()[-1] == "! Stopped."

    def test_url_is_constructed_from_port(self):
        httpd = self._make_httpd_mock()
        with patch("src.boot.http.server.HTTPServer", return_value=httpd):
            with patch("src.boot.webbrowser.open") as mock_open:
                _serve(_SERVED_DIR, 9999, config=_TRIMMED, open_browser=True)
        mock_open.assert_called_once_with("http://localhost:9999/")
