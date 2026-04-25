"""Info command implementation."""

from __future__ import annotations

import platform
import sys
from typing import Any

from python_template.core.base import BaseCommand, CommandResult
from python_template.version import __version__


class InfoCommand(BaseCommand):
    """Display runtime and version information.

    Example::

        mise run run info
    """

    name = "info"
    help = "Show version and runtime information"

    def execute(self, **_kwargs: Any) -> CommandResult:
        """Execute the info command.

        Returns:
            CommandResult with version and platform data.
        """
        data = {
            "version": __version__,
            "python": sys.version,
            "platform": platform.platform(),
            "arch": platform.machine(),
        }

        lines = [
            f"python-template {__version__}",
            f"  Python  : {sys.version.split()[0]}",
            f"  Platform: {platform.system()} {platform.machine()}",
        ]
        return CommandResult(message="\n".join(lines), data=data)

    def __call__(self, **kwargs: Any) -> CommandResult:
        """Allow the command to be called directly."""
        return self.execute(**kwargs)
