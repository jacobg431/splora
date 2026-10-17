"""Fixtures shared by the integration tests."""

from __future__ import annotations

import argparse
import json
import signal
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path

import pytest

from src.command import Command
from src.escalation import Response, escalating
from src.outcome import EXIT_KILLED
from src.record import Record
from test.integration.contracts import AssertInterruptResponse, NameArgs


@pytest.fixture(scope="session")
def name_args() -> NameArgs:
    """Return a helper that builds the arguments for a command whose only option is --name."""

    def build(name: str | None = None) -> argparse.Namespace:
        return argparse.Namespace(name=name)

    return build


@pytest.fixture(scope="session")
def load_json() -> Callable[[Path], Record]:
    """Return a helper that parses a JSON file a command wrote."""

    def load(path: Path) -> Record:
        data: Record = json.loads(path.read_text(encoding="utf-8"))
        return data

    return load


@pytest.fixture
def escalating_run() -> Callable[[Command], AbstractContextManager[None]]:
    """Return a helper that wraps a command in escalating(), exactly as frame.run() does."""

    def wrap(command: Command) -> AbstractContextManager[None]:
        return escalating(
            cancel=command.cancel,
            abandon=command.abandon,
            kill_code=EXIT_KILLED,
            exit_now=lambda _code: None,
        )

    return wrap


@pytest.fixture
def press() -> Callable[[int], None]:
    """Return a helper that fires the currently installed SIGINT handler N times."""

    def fire(times: int = 1) -> None:
        handler = signal.getsignal(signal.SIGINT)
        assert callable(handler)
        for _ in range(times):
            handler(signal.SIGINT, None)

    return fire


@pytest.fixture
def assert_interrupt_response(
    capsys: pytest.CaptureFixture[str],
) -> AssertInterruptResponse:
    """Return a helper that calls a command's cancel()/abandon() and checks the response."""

    def assert_response(
        command: Command, action: str, expected: Response, notice: str | None
    ) -> None:
        response = getattr(command, action)()
        assert response is expected
        if notice is not None:
            assert notice in capsys.readouterr().out

    return assert_response
