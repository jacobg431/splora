from __future__ import annotations

import argparse
import functools
import http.server
import re
import socket
import sys
import webbrowser
from pathlib import Path

_REPO_ROOT  = Path(__file__).parent.parent
_REPORT_DIR = _REPO_ROOT / "data" / "report"

_UNSAFE        = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')
_DEFAULT_PORT  = 5050
_PORT_ATTEMPTS = 20


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler with per-request logging suppressed."""
    def log_message(self, *_) -> None:
        pass


def _sanitize(s: str) -> str:
    return _UNSAFE.sub("_", s).strip(". ") or "unnamed"


def _latest_report(report_dir: Path) -> Path | None:
    """Return the most recently modified subdirectory of report_dir, or None."""
    if not report_dir.exists():
        return None
    dirs = [d for d in report_dir.iterdir() if d.is_dir()]
    if not dirs:
        return None
    return max(dirs, key=lambda d: d.stat().st_mtime)


def _resolve_report_dir(name: str | None, report_dir: Path) -> Path:
    """Return the report directory to serve. Exits with code 1 on failure."""
    if name:
        path = report_dir / _sanitize(name)
        if not path.is_dir():
            print(f"Error: no report found for '{name}' ({path})", file=sys.stderr)
            sys.exit(1)
        return path
    latest = _latest_report(report_dir)
    if latest is None:
        print("Error: no reports found. Run 'splora report' first.", file=sys.stderr)
        sys.exit(1)
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
    raise OSError(f"No free port available in range {start}–{start + attempts - 1}.")


def _serve(report_dir: Path, port: int, *, open_browser: bool = True) -> None:
    """Serve report_dir over HTTP on port and block until Ctrl+C."""
    handler = functools.partial(_QuietHandler, directory=str(report_dir))
    url = f"http://localhost:{port}/"
    with http.server.HTTPServer(("127.0.0.1", port), handler) as httpd:
        print(f"Serving    : {url}")
        print(f"Report     : {report_dir.name}")
        print("Press Ctrl+C to stop.")
        if open_browser:
            webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


def boot(args: argparse.Namespace) -> None:
    report_dir = _resolve_report_dir(args.name, _REPORT_DIR)
    port = _find_free_port()
    _serve(report_dir, port)
