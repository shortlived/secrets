"""Core abstractions shared across dev-patterns sub-packages."""

from dev_patterns.core.base import BaseCommand, CommandResult, ExitCode
from dev_patterns.core.ui import Console

__all__ = ["BaseCommand", "CommandResult", "Console", "ExitCode"]
