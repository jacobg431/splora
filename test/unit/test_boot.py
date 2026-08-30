"""Unit tests for src/boot.py."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.boot import _POLL_INTERVAL, _find_free_port, _sanitize, _serve

_SERVED_DIR = Path("/reports/my-run")


def _stop_after(n: int) -> Callable[[], bool]:
    """Return a should_stop callable that answers False n times, then True forever."""
    calls = 0

    def should_stop() -> bool:
        nonlocal calls
        calls += 1
        return calls > n

    return should_stop


class TestSanitize:
    """Name sanitization applied before a report directory lookup."""

    def test_valid_name_unchanged(self) -> None:
        assert _sanitize("my-run_v2") == "my-run_v2"

    def test_replaces_colon(self) -> None:
        assert _sanitize("C:drive") == "C_drive"

    def test_replaces_backslash(self) -> None:
        assert _sanitize("a\\b") == "a_b"

    def test_strips_leading_dot(self) -> None:
        assert _sanitize(".hidden") == "hidden"

    def test_empty_string_returns_unnamed(self) -> None:
        assert _sanitize("") == "unnamed"

    def test_only_unsafe_chars_collapse_to_underscore(self) -> None:
        assert _sanitize(":::") == "_"


class TestFindFreePort:
    """Selection of the first available port within the scan range."""

    def _mock_socket(self, bind_side_effect: object = None) -> MagicMock:
        """Return a mock socket context manager."""
        s = MagicMock()
        s.__enter__.return_value = s
        s.__exit__.return_value = False
        if bind_side_effect is not None:
            s.bind.side_effect = bind_side_effect
        return s

    def test_returns_start_port_when_it_is_free(self) -> None:
        mock_s = self._mock_socket()
        with patch("src.boot.socket.socket", return_value=mock_s):
            port = _find_free_port(start=7000, attempts=5)
        assert port == 7000
        mock_s.bind.assert_called_once_with(("127.0.0.1", 7000))

    def test_skips_occupied_ports_and_returns_next_free(self) -> None:
        mock_s = self._mock_socket(bind_side_effect=[OSError, OSError, None])
        with patch("src.boot.socket.socket", return_value=mock_s):
            port = _find_free_port(start=7000, attempts=5)
        assert port == 7002

    def test_raises_os_error_when_all_ports_occupied(self) -> None:
        mock_s = self._mock_socket(bind_side_effect=OSError)
        with patch("src.boot.socket.socket", return_value=mock_s):
            with pytest.raises(OSError):
                _find_free_port(start=7000, attempts=3)
        assert mock_s.bind.call_count == 3

    def test_returns_port_within_the_specified_range(self) -> None:
        mock_s = self._mock_socket(bind_side_effect=[OSError, OSError, None])
        with patch("src.boot.socket.socket", return_value=mock_s):
            port = _find_free_port(start=8000, attempts=10)
        assert 8000 <= port < 8010


class TestServe:
    """Server startup, polling, and browser launch."""

    def _make_httpd_mock(self) -> MagicMock:
        """Build a mock HTTPServer whose handle_request returns instead of blocking."""
        httpd = MagicMock()
        httpd.__enter__ = MagicMock(return_value=httpd)
        httpd.__exit__ = MagicMock(return_value=False)
        return httpd

    def test_opens_browser_when_open_browser_is_true(self) -> None:
        httpd = self._make_httpd_mock()
        with patch("src.boot.http.server.HTTPServer", return_value=httpd):
            with patch("src.boot.webbrowser.open") as mock_open:
                _serve(_SERVED_DIR, 5050, should_stop=lambda: True, open_browser=True)
        mock_open.assert_called_once_with("http://localhost:5050/")

    def test_does_not_open_browser_when_open_browser_is_false(self) -> None:
        httpd = self._make_httpd_mock()
        with patch("src.boot.http.server.HTTPServer", return_value=httpd):
            with patch("src.boot.webbrowser.open") as mock_open:
                _serve(_SERVED_DIR, 5050, should_stop=lambda: True, open_browser=False)
        mock_open.assert_not_called()

    def test_binds_to_localhost_on_given_port(self) -> None:
        httpd = self._make_httpd_mock()
        with patch("src.boot.http.server.HTTPServer", return_value=httpd) as MockServer:
            with patch("src.boot.webbrowser.open"):
                _serve(_SERVED_DIR, 8080, should_stop=lambda: True, open_browser=False)
        MockServer.assert_called_once_with(("127.0.0.1", 8080), MockServer.call_args[0][1])

    def test_sets_a_timeout_so_polling_never_blocks_forever(self) -> None:
        httpd = self._make_httpd_mock()
        with patch("src.boot.http.server.HTTPServer", return_value=httpd):
            with patch("src.boot.webbrowser.open"):
                _serve(_SERVED_DIR, 5050, should_stop=lambda: True, open_browser=False)
        assert httpd.timeout == _POLL_INTERVAL

    def test_handles_requests_until_told_to_stop(self) -> None:
        httpd = self._make_httpd_mock()
        with patch("src.boot.http.server.HTTPServer", return_value=httpd):
            with patch("src.boot.webbrowser.open"):
                _serve(_SERVED_DIR, 5050, should_stop=_stop_after(3), open_browser=False)
        assert httpd.handle_request.call_count == 3

    def test_url_is_constructed_from_port(self) -> None:
        httpd = self._make_httpd_mock()
        with patch("src.boot.http.server.HTTPServer", return_value=httpd):
            with patch("src.boot.webbrowser.open") as mock_open:
                _serve(_SERVED_DIR, 9999, should_stop=lambda: True, open_browser=True)
        mock_open.assert_called_once_with("http://localhost:9999/")
