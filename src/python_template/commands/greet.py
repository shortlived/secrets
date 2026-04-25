"""Greet command implementation."""

from __future__ import annotations

from typing import Any

from python_template.core.base import BaseCommand, CommandResult


class GreetCommand(BaseCommand):
    """Say hello to a user or the world.

    Example::

        mise run run greet --name Alice
    """

    name = "greet"
    help = "Print a personalised greeting"

    def execute(self, *, name: str = "world", loud: bool = False) -> CommandResult:
        """Execute the greet command.

        Args:
            name: Name to greet.
            loud: Whether to shout (uppercase).

        Returns:
            CommandResult with the greeting message.
        """
        message = f"Hello, {name}!"
        if loud:
            message = message.upper()
        return CommandResult(message=message)

    def __call__(self, **kwargs: Any) -> CommandResult:
        """Allow the command to be called directly."""
        return self.execute(**kwargs)
