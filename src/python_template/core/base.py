"""Base command abstractions for the CLI framework."""

from __future__ import annotations

import abc
import enum
import sys
from dataclasses import dataclass, field
from typing import Any


class ExitCode(enum.IntEnum):
    """Standard exit codes."""

    OK = 0
    ERROR = 1
    USAGE = 2
    NOT_FOUND = 127


@dataclass(frozen=True)
class CommandResult:
    """Result returned from a command execution.

    Attributes:
        code: Exit code for the process.
        message: Human-readable result message.
        data: Optional structured output data.
    """

    code: ExitCode = ExitCode.OK
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        """Return True if the command succeeded."""
        return self.code == ExitCode.OK

    def emit(self) -> None:
        """Print message to stdout (OK) or stderr (error) and exit."""
        if self.message:
            target = sys.stdout if self.ok else sys.stderr
            print(self.message, file=target)

    def exit(self) -> None:
        """Emit and exit with the result code."""
        self.emit()
        if not self.ok:
            sys.exit(int(self.code))


class BaseCommand(abc.ABC):
    """Abstract base class for all CLI commands.

    Subclass this to implement a command. The :meth:`execute` method
    must be implemented and should return a :class:`CommandResult`.

    Example::

        class GreetCommand(BaseCommand):
            name = "greet"
            help = "Print a greeting"

            def execute(self, name: str = "world") -> CommandResult:
                return CommandResult(message=f"Hello, {name}!")
    """

    #: Short name used to invoke the command from the CLI.
    name: str = ""

    #: One-line description shown in `--help`.
    help: str = ""

    @abc.abstractmethod
    def execute(self, **kwargs: Any) -> CommandResult:
        """Execute the command with the given arguments.

        Args:
            **kwargs: Parsed CLI arguments specific to this command.

        Returns:
            CommandResult describing the outcome.
        """

    def __repr__(self) -> str:
        """Return developer-friendly representation."""
        return f"{self.__class__.__name__}(name={self.name!r})"
