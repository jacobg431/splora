"""End-to-end tests: a real SIGINT, sent to a real subprocess, driving the real escalation stack."""

from __future__ import annotations

import subprocess
import sys
import time
from collections.abc import Callable

import pytest

_PRESS_GAP = 0.1
_EXIT_TIMEOUT = 3.0

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX signal delivery only; see SPLORA_PLAN.md's Deferred Features",
)

_CASES = [
    pytest.param("unwind", "unwind", 1, 130, id="unwind-first-press-exits-130"),
    pytest.param("handled", "unwind", 2, 130, id="handled-then-unwind-exits-130-on-second"),
    pytest.param("handled", "handled", 2, None, id="handled-twice-still-alive"),
    pytest.param("handled", "handled", 3, 137, id="third-press-hard-kills"),
]


class TestInterruptEscalation:
    """What a genuine, OS-delivered SIGINT does to a process running the real escalation stack."""

    @pytest.mark.parametrize("cancel, abandon, presses, expected_code", _CASES)
    def test_escalation(
        self,
        mock_command_process: Callable[..., subprocess.Popen[str]],
        press: Callable[[subprocess.Popen[str]], None],
        cancel: str,
        abandon: str,
        presses: int,
        expected_code: int | None,
    ) -> None:
        proc = mock_command_process(cancel=cancel, abandon=abandon)

        for _ in range(presses):
            press(proc)
            time.sleep(_PRESS_GAP)

        if expected_code is None:
            assert proc.poll() is None
        else:
            assert proc.wait(timeout=_EXIT_TIMEOUT) == expected_code
