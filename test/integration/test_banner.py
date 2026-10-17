"""Integration tests for src/banner.py."""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

import src.banner as banner_mod
from src.banner import installed_version

_REPO_ROOT = Path(__file__).parent.parent.parent


@pytest.fixture(scope="module")
def declared_version() -> str:
    """Return the version the project declares in its configuration file."""
    config = tomllib.loads((_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    version: str = config["project"]["version"]
    return version


class TestInstalledVersion:
    """The version the banner reports, read from the installed package metadata."""

    def test_reports_the_version_the_project_declares(self, declared_version: str) -> None:
        assert installed_version() == declared_version

    def test_the_fallback_matches_the_declared_version(self, declared_version: str) -> None:
        assert banner_mod._VERSION_WHEN_NOT_INSTALLED == declared_version

    def test_the_reported_version_is_ascii(self) -> None:
        assert installed_version().isascii()
