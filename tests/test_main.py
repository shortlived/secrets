"""Tests for the sls __main__ CLI entry point."""

from __future__ import annotations

import subprocess
import sys

import pytest


def test_main_no_args(capsys: pytest.CaptureFixture[str]) -> None:
    """Running with no args prints help and exits 0."""
    from sls.__main__ import main

    original = sys.argv
    sys.argv = ["sls"]
    try:
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
    finally:
        sys.argv = original


def test_main_version_flag() -> None:
    """--version flag exits 0 with version string."""
    result = subprocess.run(
        [sys.executable, "-m", "sls", "--version"],
        capture_output=True,
        text=True,
        check=False,
        env={**__import__("os").environ, "SLS_COMPILETIMEHASH": "a" * 64},
    )
    assert result.returncode == 0
    assert "sls" in result.stdout or "sls" in result.stderr


def test_main_status_no_cache() -> None:
    """sls status exits non-zero when no cache exists."""
    result = subprocess.run(
        [sys.executable, "-m", "sls", "status"],
        capture_output=True,
        text=True,
        check=False,
        env={
            **__import__("os").environ,
            "SLS_COMPILETIMEHASH": "a" * 64,
            "PYTHON_KEYRING_BACKEND": "keyring.backends.null.Keyring",
        },
    )
    assert result.returncode != 0
    assert "acquiesce" in result.stderr.lower() or "acquiesce" in result.stdout.lower()


def test_main_help_contains_commands() -> None:
    """Top-level --help lists all expected sub-commands."""
    result = subprocess.run(
        [sys.executable, "-m", "sls", "--help"],
        capture_output=True,
        text=True,
        check=False,
        env={**__import__("os").environ, "SLS_COMPILETIMEHASH": "a" * 64},
    )
    assert result.returncode == 0
    output = result.stdout + result.stderr
    for cmd in ("acquiesce", "push", "rotate", "status", "pull"):
        assert cmd in output, f"'{cmd}' not found in --help output"
