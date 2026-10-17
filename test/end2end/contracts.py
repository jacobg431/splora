from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class Server:
    """A report server listening in a background thread."""

    port: int
    url: str


@dataclass(frozen=True)
class Pipeline:
    """The artifacts one full explore -> report -> boot run produced."""

    scan_root: Path
    run_name: str
    json_path: Path
    report_dir: Path
    port: int
    url: str
    localhost_url: str


class ServeDir(Protocol):
    """Serves a directory in the background, returning once it accepts connections."""

    def __call__(self, report_dir: Path, start_port: int = ...) -> Server: ...


class RunCli(Protocol):
    """Runs the splora CLI as a real subprocess and requires it to exit zero."""

    def __call__(self, *args: str) -> None: ...


class AttemptCli(Protocol):
    """Runs the CLI as a real subprocess and returns its result whatever the exit code."""

    def __call__(self, *args: str) -> subprocess.CompletedProcess[bytes]: ...


class LaunchMock(Protocol):
    """Launches the mock command subprocess and waits for it to report ready."""

    def __call__(self, *, cancel: str = ..., abandon: str = ...) -> subprocess.Popen[str]: ...
