"""Tests for the version module."""

from __future__ import annotations

import re

import pytest

from python_template.version import __version__


@pytest.mark.unit
def test_version_is_string() -> None:
    """Version should be a string."""
    assert isinstance(__version__, str)


@pytest.mark.unit
def test_version_matches_semver() -> None:
    """Version should be a valid semver string."""
    semver_pattern = r"^v?\d+\.\d+\.\d+(-[\w.]+)?(\+[\w.]+)?$"
    assert re.match(semver_pattern, __version__), f"Invalid semver: {__version__!r}"


@pytest.mark.unit
def test_version_not_empty() -> None:
    """Version should not be empty."""
    assert __version__.strip()
