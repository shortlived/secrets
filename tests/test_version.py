"""Tests for the sls version module."""

from __future__ import annotations


def test_version_is_string(app_version: str) -> None:
    """Version is a non-empty string."""
    assert isinstance(app_version, str)
    assert len(app_version) > 0


def test_version_semver_format(app_version: str) -> None:
    """Version follows MAJOR.MINOR.PATCH format."""
    parts = app_version.split(".")
    assert len(parts) >= 3
    for part in parts[:3]:
        assert part.split("-")[0].isdigit()
