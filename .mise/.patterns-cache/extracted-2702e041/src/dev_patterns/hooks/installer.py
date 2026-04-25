"""Hook installer — copies hook scripts into a project's hooks destination directory."""

from __future__ import annotations

import shutil
import stat
from dataclasses import dataclass, field
from pathlib import Path

from dev_patterns.core.ui import Console
from dev_patterns.hooks.manifest import HookEntry, HookManifest


@dataclass
class HookInstaller:
    """Install git hooks from a channel's hooks directory into a project.

    Reads hook entries from a :class:`HookManifest` and copies the
    corresponding scripts from the channel source into the project's
    hooks destination, making them executable.

    Attributes:
        source_dir: Directory containing the channel's hook scripts.
        dest_dir:   Destination directory where git expects hooks to live.
        console:    UI console for styled output.
    """

    source_dir: Path
    dest_dir: Path
    console: Console | None = field(default=None)

    _console: Console = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Initialise the resolved console."""
        self._console = self.console if self.console is not None else Console()

    # ── Public API ────────────────────────────────────────────────────────────

    def install(self, manifest: HookManifest) -> list[str]:
        """Install all enabled hooks declared in *manifest*.

        Args:
            manifest: Parsed TOML manifest.

        Returns:
            List of installed hook names.
        """
        self.dest_dir.mkdir(parents=True, exist_ok=True)
        return [entry.name for entry in manifest.enabled_hooks if self._install_hook(entry)]

    def uninstall(self, hook_names: list[str]) -> list[str]:
        """Remove named hooks from the destination directory.

        Args:
            hook_names: List of hook names to remove (e.g. ``["pre-commit"]``).

        Returns:
            List of hook names that were removed.
        """
        removed: list[str] = []
        for name in hook_names:
            hook_path = self.dest_dir / name
            if hook_path.exists():
                hook_path.unlink()
                self._console.ok(f"Removed {name}")
                removed.append(name)
        return removed

    def list_installed(self) -> list[str]:
        """Return names of all currently installed hook scripts.

        Returns:
            Sorted list of file names in the destination directory.
        """
        if not self.dest_dir.exists():
            return []
        return sorted(
            f.name for f in self.dest_dir.iterdir() if f.is_file() and not f.name.endswith(".toml")
        )

    # ── Private helpers ───────────────────────────────────────────────────────

    def _install_hook(self, entry: HookEntry) -> bool:
        """Copy one hook script to the destination and make it executable.

        Args:
            entry: The hook entry from the manifest.

        Returns:
            True if the hook was installed successfully.
        """
        src = self.source_dir / entry.script
        if not src.exists():
            self._console.warn(f"Hook script not found, skipping: {entry.script}")
            return False

        dest = self.dest_dir / entry.name
        shutil.copy2(src, dest)
        self._make_executable(dest)
        self._console.ok(f"Installed {entry.name}  {self._dim(entry.description)}")
        return True

    @staticmethod
    def _make_executable(path: Path) -> None:
        """Add executable bits to *path* (equivalent to ``chmod +x``).

        Args:
            path: Path to the file to make executable.
        """
        current = path.stat().st_mode
        path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    @staticmethod
    def _dim(text: str) -> str:
        """Wrap text in dim ANSI escape for descriptions."""
        if not text:
            return ""
        return f"\033[2m— {text}\033[0m"
