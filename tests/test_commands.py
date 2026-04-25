"""Tests for built-in CLI commands."""

from __future__ import annotations

import pytest

from python_template.commands.greet import GreetCommand
from python_template.commands.info import InfoCommand
from python_template.core.base import CommandResult, ExitCode


class TestGreetCommand:
    """Tests for GreetCommand."""

    def test_greet_default(self) -> None:
        """Default greeting says hello to world."""
        result = GreetCommand().execute()
        assert result.ok
        assert result.message == "Hello, world!"

    def test_greet_named(self) -> None:
        """Named greeting addresses the given name."""
        result = GreetCommand().execute(name="Alice")
        assert result.ok
        assert "Alice" in result.message

    def test_greet_loud(self) -> None:
        """Loud flag uppercases the message."""
        result = GreetCommand().execute(loud=True)
        assert result.message == result.message.upper()

    def test_greet_named_loud(self) -> None:
        """Named + loud produces correct output."""
        result = GreetCommand().execute(name="Bob", loud=True)
        assert "BOB" in result.message

    def test_greet_repr(self) -> None:
        """Repr contains class name and command name."""
        cmd = GreetCommand()
        assert "GreetCommand" in repr(cmd)
        assert "greet" in repr(cmd)

    def test_greet_callable(self) -> None:
        """Command can be called directly."""
        result = GreetCommand()(name="Carol")
        assert "Carol" in result.message


class TestInfoCommand:
    """Tests for InfoCommand."""

    def test_info_returns_result(self) -> None:
        """Info command returns a successful result."""
        result = InfoCommand().execute()
        assert result.ok

    def test_info_contains_version(self) -> None:
        """Info message contains the version string."""
        from python_template.version import __version__

        result = InfoCommand().execute()
        assert __version__ in result.message

    def test_info_data_keys(self) -> None:
        """Info result data has expected keys."""
        result = InfoCommand().execute()
        assert "version" in result.data
        assert "python" in result.data
        assert "platform" in result.data
        assert "arch" in result.data

    def test_info_callable(self) -> None:
        """InfoCommand can be called directly."""
        result = InfoCommand()()
        assert result.ok


class TestCommandResult:
    """Tests for CommandResult."""

    def test_ok_when_exit_ok(self) -> None:
        """Result is ok when code is OK."""
        result = CommandResult(code=ExitCode.OK)
        assert result.ok

    def test_not_ok_when_error(self) -> None:
        """Result is not ok when code is ERROR."""
        result = CommandResult(code=ExitCode.ERROR)
        assert not result.ok

    def test_default_empty_data(self) -> None:
        """Data defaults to empty dict."""
        result = CommandResult()
        assert result.data == {}

    def test_frozen(self) -> None:
        """CommandResult is immutable (frozen dataclass)."""
        result = CommandResult(message="test")
        with pytest.raises((AttributeError, TypeError)):
            result.message = "modified"  # type: ignore[misc]
