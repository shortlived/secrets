"""Tests for the dev-patterns __main__ CLI entry point."""

from __future__ import annotations

import subprocess
import sys

import pytest


def test_main_no_args(capsys: pytest.CaptureFixture[str]) -> None:
    """Running with no args prints help and exits 0."""
    from dev_patterns.__main__ import main

    original = sys.argv
    sys.argv = ["dev-patterns"]
    try:
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
    finally:
        sys.argv = original


def test_main_version_flag() -> None:
    """--version flag exits 0 and includes version in output."""
    result = subprocess.run(
        [sys.executable, "-m", "dev_patterns", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    output = result.stdout + result.stderr
    assert "dev-patterns" in output or "0.1.0" in output


def test_main_help_flag() -> None:
    """--help exits 0 and shows usage."""
    result = subprocess.run(
        [sys.executable, "-m", "dev_patterns", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "dev-patterns" in result.stdout or "sync" in result.stdout


def test_main_sync_subcommand_help() -> None:
    """sync --help shows sync usage."""
    result = subprocess.run(
        [sys.executable, "-m", "dev_patterns", "sync", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "sync" in result.stdout.lower() or "dir" in result.stdout.lower()


def test_main_hooks_subcommand_help() -> None:
    """hooks --help shows hooks usage."""
    result = subprocess.run(
        [sys.executable, "-m", "dev_patterns", "hooks", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "hook" in result.stdout.lower() or "manifest" in result.stdout.lower()
