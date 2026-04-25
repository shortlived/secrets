"""``sync`` CLI command — sync patterns from the configured channel."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dev_patterns.core.base import BaseCommand, CommandResult, ExitCode
from dev_patterns.core.ui import Console
from dev_patterns.sync.engine import SyncEngine
from dev_patterns.version_spec.resolver import VersionSpecResolver


class SyncCommand(BaseCommand):
    """Sync patterns (hooks + mise tasks) from the configured channel.

    Reads configuration from environment variables and/or ``mise.toml``,
    then downloads and applies the latest patterns.
    """

    name = "sync"
    help = "Sync patterns (git hooks + mise tasks) from the channel"

    def execute(self, **kwargs: Any) -> CommandResult:
        """Run the sync.

        Args:
            **kwargs: Accepted keyword args:
                - ``project_root`` (Path | str): Project directory to sync into.
                  Defaults to the current working directory.
                - ``force`` (bool): Skip the hash-current check and always sync.

        Returns:
            CommandResult with exit code OK on success, ERROR on failure.
        """
        root = Path(kwargs.get("project_root", Path.cwd()))
        console = Console()

        resolver = VersionSpecResolver(project_root=root)
        spec = resolver.resolve()

        engine = SyncEngine(project_root=root, spec=spec, console=console)
        result = engine.run()

        if not result.ok:
            return CommandResult(
                code=ExitCode.ERROR,
                message=f"Sync failed: {result.error}",
            )

        if result.skipped:
            return CommandResult(message=f"Already current ({result.commit_hash[:8]})")

        return CommandResult(
            message=f"Synced {len(result.synced_files)} files from {spec.channel}",
            data={"hash": result.commit_hash, "files": result.synced_files},
        )
