"""Tests for the __main__ CLI entry point."""

from __future__ import annotations

import subprocess
import sys

import pytest


def test_main_no_args(capsys: pytest.CaptureFixture[str]) -> None:
    """Running with no args prints help and exits 0."""
    from python_template.__main__ import main

    original = sys.argv
    sys.argv = ["python-template"]
    try:
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 0
    finally:
        sys.argv = original


def test_main_greet_default(capsys: pytest.CaptureFixture[str]) -> None:
    """greet with no --name prints 'Hello, world!'."""
    from python_template.__main__ import main

    original = sys.argv
    sys.argv = ["python-template", "greet"]
    try:
        main()
    finally:
        sys.argv = original

    captured = capsys.readouterr()
    assert "Hello, world!" in captured.out


def test_main_greet_named(capsys: pytest.CaptureFixture[str]) -> None:
    """greet --name Alice prints 'Hello, Alice!'."""
    from python_template.__main__ import main

    original = sys.argv
    sys.argv = ["python-template", "greet", "--name", "Alice"]
    try:
        main()
    finally:
        sys.argv = original

    captured = capsys.readouterr()
    assert "Hello, Alice!" in captured.out


def test_main_greet_loud(capsys: pytest.CaptureFixture[str]) -> None:
    """greet --loud prints uppercase greeting."""
    from python_template.__main__ import main

    original = sys.argv
    sys.argv = ["python-template", "greet", "--loud"]
    try:
        main()
    finally:
        sys.argv = original

    captured = capsys.readouterr()
    assert "HELLO, WORLD!" in captured.out


def test_main_info(capsys: pytest.CaptureFixture[str]) -> None:
    """info command prints version string."""
    from python_template.__main__ import main
    from python_template.version import __version__

    original = sys.argv
    sys.argv = ["python-template", "info"]
    try:
        main()
    finally:
        sys.argv = original

    captured = capsys.readouterr()
    assert __version__ in captured.out


def test_main_version_flag() -> None:
    """--version flag exits 0 with version string."""
    result = subprocess.run(
        [sys.executable, "-m", "python_template", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "python-template" in result.stdout or "python-template" in result.stderr
