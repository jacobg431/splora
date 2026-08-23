"""Unit tests for src/frame.py."""

from __future__ import annotations

import signal

import pytest

import src.frame as frame_mod
from src.banner import TAGLINE
from src.command import Abandon, Cancel, Command
from src.frame import advice_line, run
from src.outcome import EXIT_INTERRUPTED, EXIT_OK, EXIT_PARTIAL, NextStep, Outcome
from src.terminal import OutputConfig

_ESCAPE = "\x1b["
_COMMAND_OUTPUT = "the command said this"
_STEP = NextStep(command="report", name="my-run")


@pytest.fixture(autouse=True)
def fixed_version(monkeypatch):
    """Pin the version so the frame's output never depends on how the package was installed."""
    monkeypatch.setattr(frame_mod, "installed_version", lambda: "1.2.3")


@pytest.fixture(autouse=True)
def untouched_console(monkeypatch):
    """Keep the frame from reconfiguring the console the test run is using."""
    monkeypatch.setattr(frame_mod, "enable_virtual_terminal", lambda: None)


class _Stub(Command):
    """A command that reports a prepared outcome and counts how often it was run."""

    def __init__(self, outcome: Outcome, output: str = "") -> None:
        self._outcome = outcome
        self._output = output
        self.runs = 0

    def run(self) -> Outcome:
        """Print the prepared output, if any, and report the prepared outcome."""
        self.runs += 1
        if self._output:
            print(self._output)
        return self._outcome

    def cancel(self) -> None:
        """Do nothing; this command is never cancelled."""

    def abandon(self) -> None:
        """Do nothing; this command is never abandoned."""


class _Raising(Command):
    """A command whose run raises whatever it was built with."""

    def __init__(self, error: BaseException) -> None:
        self._error = error

    def run(self) -> Outcome:
        """Raise the prepared error instead of reporting an outcome."""
        raise self._error

    def cancel(self) -> None:
        """Do nothing; the error is raised by run instead."""

    def abandon(self) -> None:
        """Do nothing; the error is raised by run instead."""


class _Watching(Command):
    """A command that records the SIGINT handler in place while it runs."""

    def __init__(self) -> None:
        self.handler_while_running = None

    def run(self) -> Outcome:
        """Record the installed handler, then report a successful run."""
        self.handler_while_running = signal.getsignal(signal.SIGINT)
        return Outcome(code=EXIT_OK)

    def cancel(self) -> None:
        """Do nothing; this command is never cancelled."""

    def abandon(self) -> None:
        """Do nothing; this command is never abandoned."""


def _decorated() -> OutputConfig:
    return OutputConfig(trim=False, use_color=False)


def _trimmed() -> OutputConfig:
    return OutputConfig(trim=True, use_color=False)


class TestAdviceLine:
    """The copy-paste command offered after a command completes."""

    def test_carries_a_label(self):
        assert advice_line(_STEP, use_color=False).startswith("Next:")

    def test_carries_the_whole_command(self):
        assert "splora report --name my-run" in advice_line(_STEP, use_color=False)

    def test_names_the_command_from_the_descriptor(self):
        step = NextStep(command="boot", name="my-run")
        assert "splora boot" in advice_line(step, use_color=False)

    def test_leaves_a_plain_name_unquoted(self):
        assert '"' not in advice_line(_STEP, use_color=False)

    def test_quotes_a_name_holding_a_space(self):
        step = NextStep(command="report", name="my run")
        assert '--name "my run"' in advice_line(step, use_color=False)

    def test_quotes_a_name_holding_a_tab(self):
        step = NextStep(command="report", name="my\trun")
        assert advice_line(step, use_color=False).endswith('"my\trun"')

    def test_carries_no_escape_when_color_is_off(self):
        assert _ESCAPE not in advice_line(_STEP, use_color=False)

    def test_carries_an_escape_when_color_is_on(self):
        assert _ESCAPE in advice_line(_STEP, use_color=True)

    def test_is_ascii(self):
        assert advice_line(_STEP, use_color=True).isascii()


class TestExitCode:
    """The code the frame hands back from the command it ran."""

    def test_returns_the_commands_code(self):
        assert run(_Stub(Outcome(code=EXIT_OK)), _decorated()) == EXIT_OK

    def test_returns_a_partial_code(self):
        assert run(_Stub(Outcome(code=EXIT_PARTIAL)), _decorated()) == EXIT_PARTIAL

    def test_returns_an_interrupted_code(self):
        assert run(_Stub(Outcome(code=EXIT_INTERRUPTED)), _decorated()) == EXIT_INTERRUPTED

    def test_trimming_does_not_change_the_code(self):
        assert run(_Stub(Outcome(code=EXIT_PARTIAL)), _trimmed()) == EXIT_PARTIAL


class TestBannerGating:
    """Whether the banner is printed, decided solely by the frame."""

    def test_prints_the_banner_by_default(self, capsys):
        run(_Stub(Outcome(code=EXIT_OK)), _decorated())
        assert TAGLINE in capsys.readouterr().out

    def test_trimming_suppresses_the_banner(self, capsys):
        run(_Stub(Outcome(code=EXIT_OK)), _trimmed())
        assert TAGLINE not in capsys.readouterr().out

    def test_the_banner_precedes_the_command(self, capsys):
        run(_Stub(Outcome(code=EXIT_OK), _COMMAND_OUTPUT), _decorated())
        out = capsys.readouterr().out
        assert out.index(TAGLINE) < out.index(_COMMAND_OUTPUT)


class TestAdviceGating:
    """Whether the next-step advice is printed."""

    def test_prints_the_advice_for_a_next_step(self, capsys):
        run(_Stub(Outcome(code=EXIT_OK, next_step=_STEP)), _decorated())
        assert "splora report --name my-run" in capsys.readouterr().out

    def test_trimming_suppresses_the_advice(self, capsys):
        run(_Stub(Outcome(code=EXIT_OK, next_step=_STEP)), _trimmed())
        assert "splora report" not in capsys.readouterr().out

    def test_no_advice_without_a_next_step(self, capsys):
        run(_Stub(Outcome(code=EXIT_INTERRUPTED)), _decorated())
        assert "Next:" not in capsys.readouterr().out

    def test_the_advice_follows_the_command(self, capsys):
        run(_Stub(Outcome(code=EXIT_OK, next_step=_STEP), _COMMAND_OUTPUT), _decorated())
        out = capsys.readouterr().out
        assert out.index(_COMMAND_OUTPUT) < out.index("Next:")

    def test_a_partial_run_still_advises(self, capsys):
        run(_Stub(Outcome(code=EXIT_PARTIAL, next_step=_STEP)), _decorated())
        assert "Next:" in capsys.readouterr().out


class TestRunningTheCommand:
    """How the frame treats the command it was handed."""

    def test_runs_the_command_exactly_once(self):
        command = _Stub(Outcome(code=EXIT_OK))
        run(command, _decorated())
        assert command.runs == 1

    def test_lets_the_commands_output_through(self, capsys):
        run(_Stub(Outcome(code=EXIT_OK), _COMMAND_OUTPUT), _decorated())
        assert _COMMAND_OUTPUT in capsys.readouterr().out

    def test_trimming_keeps_the_commands_output(self, capsys):
        run(_Stub(Outcome(code=EXIT_OK), _COMMAND_OUTPUT), _trimmed())
        assert _COMMAND_OUTPUT in capsys.readouterr().out

    def test_trimmed_output_is_the_command_alone(self, capsys):
        run(_Stub(Outcome(code=EXIT_OK, next_step=_STEP), _COMMAND_OUTPUT), _trimmed())
        assert capsys.readouterr().out == f"{_COMMAND_OUTPUT}\n"

    def test_a_command_that_exits_hard_passes_through(self):
        with pytest.raises(SystemExit):
            run(_Raising(SystemExit(1)), _decorated())

    def test_a_command_that_exits_hard_gets_no_advice(self, capsys):
        with pytest.raises(SystemExit):
            run(_Raising(SystemExit(1)), _decorated())
        assert "Next:" not in capsys.readouterr().out


class TestInterrupt:
    """What the frame does with a command that reports being interrupted."""

    def test_a_cancel_becomes_the_interrupted_code(self):
        assert run(_Raising(Cancel()), _decorated()) == EXIT_INTERRUPTED

    def test_an_abandon_becomes_the_interrupted_code(self):
        assert run(_Raising(Abandon()), _decorated()) == EXIT_INTERRUPTED

    def test_the_frame_adds_no_notice_of_its_own(self, capsys):
        run(_Raising(Abandon()), _trimmed())
        assert capsys.readouterr().out == ""

    def test_an_interrupted_command_gets_no_advice(self, capsys):
        run(_Raising(Cancel()), _decorated())
        assert "Next:" not in capsys.readouterr().out

    def test_the_command_runs_under_a_handler_of_its_own(self):
        command = _Watching()
        before = signal.getsignal(signal.SIGINT)
        run(command, _trimmed())
        assert command.handler_while_running is not before

    def test_the_previous_handler_is_restored_afterwards(self):
        before = signal.getsignal(signal.SIGINT)
        run(_Watching(), _trimmed())
        assert signal.getsignal(signal.SIGINT) is before
