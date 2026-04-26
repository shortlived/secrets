"""Pytest fixtures and configuration for the sls test suite."""

from __future__ import annotations

import tempfile
from collections.abc import Generator

import pytest

TEST_COMPILETIMEHASH = "a" * 64  # 32 bytes in hex


@pytest.fixture(autouse=True)
def set_test_compiletimehash(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject a fake compiletimehash via environment variable for all tests."""
    monkeypatch.setenv("SLS_COMPILETIMEHASH", TEST_COMPILETIMEHASH)


@pytest.fixture
def tmp_cache_dir() -> Generator[str, None, None]:
    """Provide a temporary directory to use as the cache base dir."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_secrets() -> dict[str, str]:
    """Return a small set of fake secrets for testing."""
    return {
        "API_TOKEN": "test-token-abc123",
        "DB_PASSWORD": "hunter2",
        "ANOTHER_SECRET": "s3cr3t-v4lu3",
    }


@pytest.fixture
def app_version() -> str:
    """Return the current application version."""
    from sls.version import __version__

    return __version__
