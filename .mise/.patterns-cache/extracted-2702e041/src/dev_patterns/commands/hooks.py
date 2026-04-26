"""``hooks`` CLI command — install git hooks from a githooks.toml manifest."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dev_patterns.core.base import BaseCommand, CommandResult, ExitCode
from dev_patterns.core.ui import Console
from dev_patterns.hooks.installer import HookInstaller
from dev_patterns.hooks.manifest import HookManifest


class HooksCommand(BaseCommand):
    """Install git hooks declared in a ``githooks.toml`` manifest.

    Reads the manifest from the channel's hooks directory and installs
    all enabled hooks into the project's ``config/githooks/hooks/`` dir.
    """

    name = "hooks"
    help = "Install git hooks from a githooks.toml manifest"

    def execute(self, **kwargs: Any) -> CommandResult:
        """Run the hooks install.

        Args:
            **kwargs: Accepted keyword args:
                - ``project_root`` (Path | str): Project directory.
                  Defaults to the current working directory.
                - ``manifest`` (Path | str): Path to ``githooks.toml``.
                  Defaults to ``config/githooks/hooks/githooks.toml``.
                - ``source_dir`` (Path | str): Directory containing hook scripts.
                  Defaults to the manifest's parent directory.
                - ``dest_dir`` (Path | str): Destination hooks directory.
                  Defaults to ``config/githooks/hooks/``.

        Returns:
            CommandResult with exit code OK on success, ERROR on failure.
        """
        root = Path(kwargs.get("project_root", Path.cwd()))
        console = Console()

        default_manifest = root / "config" / "githooks" / "hooks" / "githooks.toml"
        manifest_path = Path(kwargs.get("manifest", default_manifest))
        source_dir = Path(kwargs.get("source_dir", manifest_path.parent))
        dest_dir = Path(kwargs.get("dest_dir", root / "config" / "githooks" / "hooks"))

        if not manifest_path.exists():
            msg = f"githooks.toml not found: {manifest_path}"
            console.error(msg)
            return CommandResult(code=ExitCode.NOT_FOUND, message=msg)

        try:
            manifest = HookManifest.from_toml(manifest_path)
        except (FileNotFoundError, ValueError) as exc:
            msg = str(exc)
            console.error(msg)
            return CommandResult(code=ExitCode.ERROR, message=msg)

        console.header("Installing Git Hooks")
        console.info("Channel", manifest.channel.name or "unknown")
        console.info("Version", manifest.channel.version or "—")
        console.blank()

        installer = HookInstaller(
            source_dir=source_dir,
            dest_dir=dest_dir,
            console=console,
        )
        installed = installer.install(manifest)

        console.blank()
        console.done(f"Installed {len(installed)} hooks → {dest_dir}")

        return CommandResult(
            message=f"Installed {len(installed)} hooks",
            data={"hooks": installed},
        )
