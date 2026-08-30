"""Unit tests for src/command.py."""

from __future__ import annotations

import pytest

from src.command import Command
from src.escalation import Response
from src.outcome import EXIT_OK, Outcome


class _Complete(Command):
    """A command implementing every member of the contract."""

    def run(self) -> Outcome:
        """Report a run that succeeded."""
        return Outcome(code=EXIT_OK)

    def cancel(self) -> Response:
        """Stop, having nothing to wind down."""
        return Response.HANDLED

    def abandon(self) -> Response:
        """Give up, having nothing to discard."""
        return Response.UNWIND


class _WithoutAbandon(Command):
    """A command that leaves one member of the contract unimplemented."""

    def run(self) -> Outcome:
        """Report a run that succeeded."""
        return Outcome(code=EXIT_OK)

    def cancel(self) -> Response:
        """Stop, having nothing to wind down."""
        return Response.HANDLED


class TestContract:
    """What the base class requires of a command before one can exist."""

    def test_the_contract_itself_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            Command()

    def test_a_complete_command_can_be_instantiated(self) -> None:
        assert isinstance(_Complete(), Command)

    def test_a_command_missing_a_member_cannot_be_instantiated(self) -> None:
        with pytest.raises(TypeError):
            _WithoutAbandon()

    def test_the_refusal_names_the_missing_member(self) -> None:
        with pytest.raises(TypeError) as exc:
            _WithoutAbandon()
        assert "abandon" in str(exc.value)

    def test_a_complete_command_reports_its_outcome(self) -> None:
        assert _Complete().run().code == EXIT_OK
