"""Unit tests for src/frame.py."""

from __future__ import annotations

from collections.abc import Callable

import pytest

import src.frame as frame_mod
from src.banner import TAGLINE
from src.frame import advice_line, run
from src.outcome import EXIT_INTERRUPTED, EXIT_OK, EXIT_PARTIAL, NextStep, Outcome
from src.terminal import OutputConfig

_ESCAPE = "\x1b["
_BODY_OUTPUT = "the command said this"
_STEP = NextStep(command="report", name="my-run")


@pytest.fixture(autouse=True)
def fixed_version(monkeypatch):
    """Pin the version so the frame's output never depends on how the package was installed."""
    monkeypatch.setattr(frame_mod, "installed_version", lambda: "1.2.3")


@pytest.fixture(autouse=True)
def untouched_console(monkeypatch):
    """Keep the frame from reconfiguring the console the test run is using."""
    monkeypatch.setattr(frame_mod, "enable_virtual_terminal", lambda: None)


def _body(outcome: Outcome, output: str = "") -> Callable[[], Outcome]:
    def command() -> Outcome:
        if output:
            print(output)
        return outcome

    return command


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
    """The code the frame hands back from the body it ran."""

    def test_returns_the_bodys_code(self):
        assert run(_body(Outcome(code=EXIT_OK)), _decorated()) == EXIT_OK

    def test_returns_a_partial_code(self):
        assert run(_body(Outcome(code=EXIT_PARTIAL)), _decorated()) == EXIT_PARTIAL

    def test_returns_an_interrupted_code(self):
        assert run(_body(Outcome(code=EXIT_INTERRUPTED)), _decorated()) == EXIT_INTERRUPTED

    def test_trimming_does_not_change_the_code(self):
        assert run(_body(Outcome(code=EXIT_PARTIAL)), _trimmed()) == EXIT_PARTIAL


class TestBannerGating:
    """Whether the banner is printed, decided solely by the frame."""

    def test_prints_the_banner_by_default(self, capsys):
        run(_body(Outcome(code=EXIT_OK)), _decorated())
        assert TAGLINE in capsys.readouterr().out

    def test_trimming_suppresses_the_banner(self, capsys):
        run(_body(Outcome(code=EXIT_OK)), _trimmed())
        assert TAGLINE not in capsys.readouterr().out

    def test_the_banner_precedes_the_body(self, capsys):
        run(_body(Outcome(code=EXIT_OK), _BODY_OUTPUT), _decorated())
        out = capsys.readouterr().out
        assert out.index(TAGLINE) < out.index(_BODY_OUTPUT)


class TestAdviceGating:
    """Whether the next-step advice is printed."""

    def test_prints_the_advice_for_a_next_step(self, capsys):
        run(_body(Outcome(code=EXIT_OK, next_step=_STEP)), _decorated())
        assert "splora report --name my-run" in capsys.readouterr().out

    def test_trimming_suppresses_the_advice(self, capsys):
        run(_body(Outcome(code=EXIT_OK, next_step=_STEP)), _trimmed())
        assert "splora report" not in capsys.readouterr().out

    def test_no_advice_without_a_next_step(self, capsys):
        run(_body(Outcome(code=EXIT_INTERRUPTED)), _decorated())
        assert "Next:" not in capsys.readouterr().out

    def test_the_advice_follows_the_body(self, capsys):
        run(_body(Outcome(code=EXIT_OK, next_step=_STEP), _BODY_OUTPUT), _decorated())
        out = capsys.readouterr().out
        assert out.index(_BODY_OUTPUT) < out.index("Next:")

    def test_a_partial_run_still_advises(self, capsys):
        run(_body(Outcome(code=EXIT_PARTIAL, next_step=_STEP)), _decorated())
        assert "Next:" in capsys.readouterr().out


class TestBody:
    """How the frame treats the body it was handed."""

    def test_runs_the_body_exactly_once(self):
        calls = []

        def counted() -> Outcome:
            calls.append(1)
            return Outcome(code=EXIT_OK)

        run(counted, _decorated())
        assert len(calls) == 1

    def test_lets_the_bodys_output_through(self, capsys):
        run(_body(Outcome(code=EXIT_OK), _BODY_OUTPUT), _decorated())
        assert _BODY_OUTPUT in capsys.readouterr().out

    def test_trimming_keeps_the_bodys_output(self, capsys):
        run(_body(Outcome(code=EXIT_OK), _BODY_OUTPUT), _trimmed())
        assert _BODY_OUTPUT in capsys.readouterr().out

    def test_trimmed_output_is_the_body_alone(self, capsys):
        run(_body(Outcome(code=EXIT_OK, next_step=_STEP), _BODY_OUTPUT), _trimmed())
        assert capsys.readouterr().out == f"{_BODY_OUTPUT}\n"

    def test_a_body_that_exits_hard_passes_through(self):
        def exiting() -> Outcome:
            raise SystemExit(1)

        with pytest.raises(SystemExit):
            run(exiting, _decorated())

    def test_a_body_that_exits_hard_gets_no_advice(self, capsys):
        def exiting() -> Outcome:
            raise SystemExit(1)

        with pytest.raises(SystemExit):
            run(exiting, _decorated())
        assert "Next:" not in capsys.readouterr().out


class TestColor:
    """Colouring of what the frame itself prints."""

    def test_carries_no_escape_when_color_is_off(self, capsys):
        run(
            _body(Outcome(code=EXIT_OK, next_step=_STEP)), OutputConfig(trim=False, use_color=False)
        )
        assert _ESCAPE not in capsys.readouterr().out

    def test_carries_escapes_when_color_is_on(self, capsys):
        run(_body(Outcome(code=EXIT_OK, next_step=_STEP)), OutputConfig(trim=False, use_color=True))
        assert _ESCAPE in capsys.readouterr().out

    def test_everything_printed_is_ascii(self, capsys):
        run(_body(Outcome(code=EXIT_OK, next_step=_STEP)), OutputConfig(trim=False, use_color=True))
        assert capsys.readouterr().out.isascii()
