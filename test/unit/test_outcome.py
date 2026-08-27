"""Unit tests for src/outcome.py."""

from __future__ import annotations

import dataclasses

import pytest

from src.outcome import (
    EXIT_ERROR,
    EXIT_INTERRUPTED,
    EXIT_OK,
    EXIT_PARTIAL,
    NextStep,
    Outcome,
)


class TestExitCodes:
    """The exit codes the tool issues for each documented scenario."""

    def test_success_is_zero(self):
        assert EXIT_OK == 0

    def test_user_error_is_one(self):
        assert EXIT_ERROR == 1

    def test_partial_is_three(self):
        assert EXIT_PARTIAL == 3

    def test_interrupted_follows_the_posix_signal_convention(self):
        assert EXIT_INTERRUPTED == 128 + 2

    def test_no_code_collides_with_the_argparse_usage_code(self):
        codes = (EXIT_OK, EXIT_ERROR, EXIT_PARTIAL, EXIT_INTERRUPTED)
        assert 2 not in codes

    def test_every_code_is_distinct(self):
        codes = (EXIT_OK, EXIT_ERROR, EXIT_PARTIAL, EXIT_INTERRUPTED)
        assert len(set(codes)) == len(codes)


class TestNextStep:
    """The descriptor a command returns to name the step that follows it."""

    def test_carries_the_command_and_the_run_name(self):
        step = NextStep(command="report", name="my-run")
        assert (step.command, step.name) == ("report", "my-run")

    def test_is_immutable(self):
        step = NextStep(command="report", name="my-run")
        with pytest.raises(dataclasses.FrozenInstanceError):
            step.command = "boot"


class TestOutcome:
    """The result a command body reports back to the frame."""

    def test_carries_the_exit_code(self):
        assert Outcome(code=EXIT_PARTIAL).code == EXIT_PARTIAL

    def test_has_no_next_step_by_default(self):
        assert Outcome(code=EXIT_OK).next_step is None

    def test_carries_a_next_step_when_given_one(self):
        step = NextStep(command="boot", name="my-run")
        assert Outcome(code=EXIT_OK, next_step=step).next_step is step

    def test_is_immutable(self):
        outcome = Outcome(code=EXIT_OK)
        with pytest.raises(dataclasses.FrozenInstanceError):
            outcome.code = EXIT_ERROR
