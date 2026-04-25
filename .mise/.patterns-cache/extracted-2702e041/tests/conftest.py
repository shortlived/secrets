"""Pytest fixtures and configuration for the test suite."""

from __future__ import annotations

import pytest


@pytest.fixture(scope="session")
def app_version() -> str:
    """Return the current application version."""
    from dev_patterns.version import __version__

    return __version__
