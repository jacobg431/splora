"""Session-scoped fixture that drives the full Splora pipeline once per E2E run.

explore and report are invoked as real subprocesses (testing CLI arg parsing).
boot's HTTP server is started in a daemon thread with open_browser=False.
All artifacts written to data/filesystem/ and data/report/ are deleted on teardown.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from src.boot import _find_free_port, _serve
from src.explore import _FS_DIR
from src.report import _REPORT_DIR

PROJECT_ROOT = Path(__file__).parent.parent.parent
RUN_NAME = "splora-e2e"
_PORT_START = 15000


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
def e2e_pipeline(tmp_path_factory, run_cli):
    """Run the full pipeline once and yield the artifacts it produced."""
    scan_root = tmp_path_factory.mktemp("e2e_scan")
    _build_scan_tree(scan_root)

    run_cli("explore", str(scan_root), "--name", RUN_NAME, "--no-default-excludes")
    run_cli("report", "--name", RUN_NAME)

    report_dir = _REPORT_DIR / RUN_NAME
    port = _find_free_port(start=_PORT_START)
    threading.Thread(
        target=_serve,
        kwargs={"report_dir": report_dir, "port": port, "open_browser": False},
        daemon=True,
    ).start()
    time.sleep(0.3)  # give the server time to bind

    json_path = _FS_DIR / f"{RUN_NAME}.json"

    yield {
        "scan_root": scan_root,
        "run_name": RUN_NAME,
        "json_path": json_path,
        "report_dir": report_dir,
        "port": port,
        "url": f"http://127.0.0.1:{port}/",
        "localhost_url": f"http://localhost:{port}/",
    }

    if json_path.exists():
        json_path.unlink()
    if report_dir.exists():
        shutil.rmtree(report_dir)
