from __future__ import annotations

import argparse
import functools
import http.server
import re
import socket
import sys
import webbrowser
from collections.abc import Callable
from pathlib import Path

from src.command import Command
from src.escalation import Response
from src.outcome import EXIT_ERROR, EXIT_OK, Outcome
from src.terminal import OutputConfig, notice_line

_REPO_ROOT = Path(__file__).parent.parent
_REPORT_DIR = _REPO_ROOT / "data" / "report"

_UNSAFE = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_DEFAULT_PORT = 5050
_PORT_ATTEMPTS = 20
_STAGING_PREFIX = "."
_POLL_INTERVAL = 0.5


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler with per-request logging suppressed."""

    def log_message(self, *_) -> None:
        """Discard the per-request log line the base handler would emit."""


def _sanitize(s: str) -> str:
    return _UNSAFE.sub("_", s).strip(". ") or "unnamed"


def _finished_reports(report_dir: Path) -> list[Path]:
    """Return the report directories that are complete, excluding any still being staged."""
    return [
        entry
        for entry in report_dir.iterdir()
        if entry.is_dir() and not entry.name.startswith(_STAGING_PREFIX)
    ]


def _latest_report(report_dir: Path) -> Path | None:
    """Return the most recently modified subdirectory of report_dir, or None."""
    if not report_dir.exists():
        return None
    reports = _finished_reports(report_dir)
    if not reports:
        return None
    return max(reports, key=lambda d: d.stat().st_mtime)


def _resolve_report_dir(name: str | None, report_dir: Path) -> Path:
    """Return the report directory to serve, exiting with code 1 on failure."""
    if name:
        path = report_dir / _sanitize(name)
        if not path.is_dir():
            print(f"Error: no report found for '{name}' ({path})", file=sys.stderr)
            sys.exit(EXIT_ERROR)
        return path
    latest = _latest_report(report_dir)
    if latest is None:
        print("Error: no reports found. Run 'splora report' first.", file=sys.stderr)
        sys.exit(EXIT_ERROR)
    return latest


def _find_free_port(start: int = _DEFAULT_PORT, attempts: int = _PORT_ATTEMPTS) -> int:
    """Return the first available TCP port in [start, start + attempts)."""
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise OSError(f"No free port available in range {start}--{start + attempts - 1}.")


def _serve(
    report_dir: Path, port: int, *, should_stop: Callable[[], bool], open_browser: bool = True
) -> None:
    """Serve report_dir over HTTP on port until should_stop reports True."""
    handler = functools.partial(_QuietHandler, directory=str(report_dir))
    url = f"http://localhost:{port}/"
    with http.server.HTTPServer(("127.0.0.1", port), handler) as httpd:
        httpd.timeout = _POLL_INTERVAL
        print(f"Serving    : {url}")
        print(f"Report     : {report_dir.name}")
        print("Press Ctrl+C to stop.")
        if open_browser:
            webbrowser.open(url)
        while not should_stop():
            httpd.handle_request()


class Boot(Command):
    """The command that serves a generated report over HTTP."""

    def __init__(self, args: argparse.Namespace, config: OutputConfig) -> None:
        self._args = args
        self._config = config
        self._stop_requested = False

    def run(self) -> Outcome:
        """Serve a generated report over HTTP and open it in the browser."""
        report_dir = _resolve_report_dir(self._args.name, _REPORT_DIR)
        port = _find_free_port()
        _serve(report_dir, port, should_stop=lambda: self._stop_requested)
        return Outcome(code=EXIT_OK)

    def cancel(self) -> Response:
        """Stop serving, which is how this command is meant to end."""
        return self._stop()

    def abandon(self) -> Response:
        """Stop serving; there is nothing in flight to discard."""
        return self._stop()

    def _stop(self) -> Response:
        self._stop_requested = True
        print()
        print(notice_line("Stopped.", config=self._config))
        return Response.HANDLED
