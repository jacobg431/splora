"""Fixtures shared by the integration tests."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def name_args() -> Callable[..., argparse.Namespace]:
    """Return a helper that builds the arguments for a command whose only option is --name."""

    def build(name: str | None = None) -> argparse.Namespace:
        return argparse.Namespace(name=name)

    return build


@pytest.fixture(scope="session")
def load_json() -> Callable[[Path], dict]:
    """Return a helper that parses a JSON file a command wrote."""

    def load(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    return load
