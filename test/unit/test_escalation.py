"""Unit tests for src/escalation.py."""

from __future__ import annotations

import signal

import pytest

from src.escalation import escalating

_KILL_CODE = 137


class _Responses:
    """A recording stand-in for the three things a Ctrl+C can trigger."""

    def __init__(self) -> None:
        self.cancels = 0
        self.abandons = 0
        self.exits: list[int] = []

    def cancel(self) -> None:
        """Record a request to stop when safe."""
        self.cancels += 1

    def abandon(self) -> None:
        """Record a request to discard the work in flight."""
        self.abandons += 1

    def exit_now(self, code: int) -> None:
        """Record a hard kill and the code it would have exited with."""
        self.exits.append(code)


def _press(times: int) -> None:
    handler = signal.getsignal(signal.SIGINT)
    for _ in range(times):
        handler(signal.SIGINT, None)


def _pressed(times: int) -> _Responses:
    responses = _Responses()
    with escalating(
        cancel=responses.cancel,
        abandon=responses.abandon,
        kill_code=_KILL_CODE,
        exit_now=responses.exit_now,
    ):
        _press(times)
    return responses


class TestDispatch:
    """Which response each successive Ctrl+C triggers."""

    def test_the_first_press_cancels(self):
        assert _pressed(1).cancels == 1

    def test_the_first_press_does_not_abandon(self):
        assert _pressed(1).abandons == 0

    def test_the_first_press_does_not_kill(self):
        assert _pressed(1).exits == []

    def test_the_second_press_abandons(self):
        assert _pressed(2).abandons == 1

    def test_the_second_press_does_not_cancel_again(self):
        assert _pressed(2).cancels == 1

    def test_the_second_press_does_not_kill(self):
        assert _pressed(2).exits == []

    def test_the_third_press_kills(self):
        assert _pressed(3).exits == [_KILL_CODE]

    def test_the_third_press_does_not_abandon_again(self):
        assert _pressed(3).abandons == 1

    def test_a_fourth_press_kills_again(self):
        assert _pressed(4).exits == [_KILL_CODE, _KILL_CODE]

    def test_no_press_triggers_no_response(self):
        responses = _pressed(0)
        assert (responses.cancels, responses.abandons, responses.exits) == (0, 0, [])


class TestKillNotice:
    """What a hard kill writes out before it exits."""

    def test_the_kill_says_so_on_standard_error(self, capfd):
        _pressed(3)
        assert "Killed." in capfd.readouterr().err

    def test_the_kill_notice_is_ascii(self, capfd):
        _pressed(3)
        assert capfd.readouterr().err.isascii()

    def test_the_earlier_presses_write_nothing(self, capfd):
        _pressed(2)
        assert capfd.readouterr().err == ""


class TestHandlerRestoration:
    """The SIGINT handler in place before, during, and after the block."""

    def test_a_handler_is_installed_for_the_block(self):
        before = signal.getsignal(signal.SIGINT)
        responses = _Responses()
        with escalating(
            cancel=responses.cancel,
            abandon=responses.abandon,
            kill_code=_KILL_CODE,
            exit_now=responses.exit_now,
        ):
            assert signal.getsignal(signal.SIGINT) is not before

    def test_the_previous_handler_is_restored(self):
        before = signal.getsignal(signal.SIGINT)
        _pressed(1)
        assert signal.getsignal(signal.SIGINT) is before

    def test_the_previous_handler_is_restored_after_a_failure(self):
        before = signal.getsignal(signal.SIGINT)
        responses = _Responses()
        with pytest.raises(RuntimeError):
            with escalating(
                cancel=responses.cancel,
                abandon=responses.abandon,
                kill_code=_KILL_CODE,
                exit_now=responses.exit_now,
            ):
                raise RuntimeError("the body failed")
        assert signal.getsignal(signal.SIGINT) is before


class TestRaisingResponse:
    """A response that unwinds the run rather than returning to it."""

    def test_a_raising_cancel_reaches_the_caller(self):
        def cancel() -> None:
            raise KeyboardInterrupt

        with pytest.raises(KeyboardInterrupt):
            with escalating(
                cancel=cancel, abandon=lambda: None, kill_code=_KILL_CODE, exit_now=lambda _: None
            ):
                _press(1)

    def test_a_raising_cancel_still_counts_its_press(self):
        abandons = []

        def cancel() -> None:
            raise KeyboardInterrupt

        with escalating(
            cancel=cancel,
            abandon=lambda: abandons.append(1),
            kill_code=_KILL_CODE,
            exit_now=lambda _: None,
        ):
            with pytest.raises(KeyboardInterrupt):
                _press(1)
            _press(1)
        assert abandons == [1]
