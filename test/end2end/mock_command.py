"""Runs a mock Command through the real frame, for a real subprocess to be signalled."""

from __future__ import annotations

import argparse
import time

from src.command import Command
from src.escalation import Response
from src.frame import run
from src.outcome import Outcome
from src.terminal import OutputConfig

_POLL_INTERVAL = 0.05


class MockCommand(Command):
    """A command that waits until interrupted, answering however it was configured to."""

    def __init__(self, cancel_response: Response, abandon_response: Response) -> None:
        self._cancel_response = cancel_response
        self._abandon_response = abandon_response

    def run(self) -> Outcome:
        """Print a readiness line, then wait indefinitely for an UNWIND or a hard kill."""
        print("Ready.", flush=True)
        while True:
            time.sleep(_POLL_INTERVAL)

    def cancel(self) -> Response:
        """Answer however configured; a HANDLED answer is a no-op."""
        return self._cancel_response

    def abandon(self) -> Response:
        """Answer however configured; a HANDLED answer is a no-op."""
        return self._abandon_response


def _response(name: str) -> Response:
    return Response.HANDLED if name == "handled" else Response.UNWIND


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cancel", choices=("handled", "unwind"), default="handled")
    parser.add_argument("--abandon", choices=("handled", "unwind"), default="unwind")
    args = parser.parse_args()
    command = MockCommand(_response(args.cancel), _response(args.abandon))
    raise SystemExit(run(command, OutputConfig(trim=True, use_color=False)))
