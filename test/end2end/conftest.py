"""Session-scoped fixture that drives the full Splora pipeline once per E2E run.

explore and report are invoked as real subprocesses (testing CLI arg parsing).
boot's HTTP server is started in a daemon thread with open_browser=False.
All artifacts written to data/filesystem/ and data/report/ are deleted on teardown.
"""

from __future__ import annotations

import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytest

from src.boot import _find_free_port, _serve
from src.explore import _FS_DIR
from src.report import _REPORT_DIR

PROJECT_ROOT = Path(__file__).parent.parent.parent
RUN_NAME = "splora-e2e"
_PORT_START = 15000
_READY_LINE = "Ready.\n"


@dataclass(frozen=True)
class _Server:
    """A report server listening in a background thread."""

    port: int
    url: str


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


@pytest.fixture(scope="session")
def serve_dir() -> Callable[..., _Server]:
    """Return a helper that serves a directory in the background once it accepts connections."""

    def serve(report_dir: Path, start_port: int = _PORT_START) -> _Server:
        port = _find_free_port(start=start_port)
        threading.Thread(
            target=_serve,
            kwargs={
                "report_dir": report_dir,
                "port": port,
                "should_stop": lambda: False,
                "open_browser": False,
            },
            daemon=True,
        ).start()
        _wait_until_listening(port)
        return _Server(port=port, url=f"http://127.0.0.1:{port}/")

    return serve


def _build_scan_tree(root: Path) -> None:
    """Create a small, predictable directory tree to explore."""
    (root / "main.py").write_bytes(b"print('hello')")
    (root / "readme.txt").write_bytes(b"Splora end-to-end test")
    (root / "image.png").write_bytes(b"\x89PNG" + b"\x00" * 96)
    sub = root / "subdir"
    sub.mkdir()
    (sub / "data.json").write_bytes(b'{"key": "value"}')
    (sub / "video.mp4").write_bytes(b"\x00" * 200)


@pytest.fixture(scope="session")
def run_cli() -> Callable[..., None]:
    """Return a helper that runs the splora CLI as a real subprocess."""

    def run(*args: str) -> None:
        subprocess.run(
            [sys.executable, "splora.py", *args],
            cwd=PROJECT_ROOT,
            check=True,
            capture_output=True,
        )

    return run


@pytest.fixture(scope="session")
def attempt_cli() -> Callable[..., subprocess.CompletedProcess]:
    """Return a helper that runs the CLI and hands back its result whatever the exit code."""

    def attempt(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "splora.py", *args],
            cwd=PROJECT_ROOT,
            capture_output=True,
        )

    return attempt


def _wait_until_ready(proc: subprocess.Popen[str]) -> None:
    """Block until the mock command process prints its readiness line."""
    line = proc.stdout.readline()
    if line != _READY_LINE:
        raise AssertionError(f"mock command process did not print {_READY_LINE!r}; got {line!r}")


@pytest.fixture
def mock_command_process() -> Callable[..., subprocess.Popen[str]]:
    """Return a helper that launches the mock command and waits for it to report ready."""
    procs: list[subprocess.Popen[str]] = []

    def launch(*, cancel: str = "handled", abandon: str = "unwind") -> subprocess.Popen[str]:
        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "test.end2end.mock_command",
                "--cancel",
                cancel,
                "--abandon",
                abandon,
            ],
            cwd=PROJECT_ROOT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
            stdout=subprocess.PIPE,
            text=True,
        )
        procs.append(proc)
        _wait_until_ready(proc)
        return proc

    yield launch

    for proc in procs:
        if proc.poll() is None:
            proc.kill()
            proc.wait()


@pytest.fixture
def press() -> Callable[[subprocess.Popen[str]], None]:
    """Return a helper that sends a real SIGINT to a live process."""

    def send(proc: subprocess.Popen[str]) -> None:
        os.kill(proc.pid, signal.SIGINT)

    return send


@pytest.fixture
def scratch_run() -> Callable[[str], str]:
    """Return a helper naming a run whose artifacts are deleted when the test ends."""
    names: list[str] = []

    def name(label: str) -> str:
        run = f"e2e-{label}"
        names.append(run)
        return run

    yield name

    for run in names:
        (_FS_DIR / f"{run}.json").unlink(missing_ok=True)
        (_FS_DIR / f"{run}.tmp").unlink(missing_ok=True)
        shutil.rmtree(_REPORT_DIR / run, ignore_errors=True)
        shutil.rmtree(_REPORT_DIR / f".{run}.tmp", ignore_errors=True)


@pytest.fixture(scope="session")
def e2e_pipeline(tmp_path_factory, run_cli, serve_dir) -> dict[str, str | Path | int]:
    """Run the full pipeline once and yield the artifacts it produced."""
    scan_root = tmp_path_factory.mktemp("e2e_scan")
    _build_scan_tree(scan_root)

    run_cli("explore", str(scan_root), "--name", RUN_NAME, "--no-default-excludes")
    run_cli("report", "--name", RUN_NAME)

    report_dir = _REPORT_DIR / RUN_NAME
    server = serve_dir(report_dir)

    json_path = _FS_DIR / f"{RUN_NAME}.json"

    yield {
        "scan_root": scan_root,
        "run_name": RUN_NAME,
        "json_path": json_path,
        "report_dir": report_dir,
        "port": server.port,
        "url": server.url,
        "localhost_url": f"http://localhost:{server.port}/",
    }

    if json_path.exists():
        json_path.unlink()
    if report_dir.exists():
        shutil.rmtree(report_dir)
