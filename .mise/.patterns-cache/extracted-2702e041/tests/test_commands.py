"""Tests for dev-patterns CLI commands."""

from __future__ import annotations

from pathlib import Path

import pytest

from dev_patterns.commands.hooks import HooksCommand
from dev_patterns.commands.sync import SyncCommand
from dev_patterns.core.base import CommandResult, ExitCode


class TestCommandResult:
    """Tests for CommandResult base class."""

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


class TestHooksCommand:
    """Tests for HooksCommand."""

    def test_hooks_command_name(self) -> None:
        """Command has the right name and help text."""
        cmd = HooksCommand()
        assert cmd.name == "hooks"
        assert "hook" in cmd.help.lower()

    def test_hooks_command_missing_manifest(self, tmp_path: Path) -> None:
        """Returns NOT_FOUND when githooks.toml is absent."""
        result = HooksCommand().execute(
            project_root=tmp_path,
            manifest=tmp_path / "does_not_exist.toml",
        )
        assert result.code == ExitCode.NOT_FOUND

    def test_hooks_command_with_manifest(self, tmp_path: Path) -> None:
        """Installs hooks when manifest and scripts are present."""
        hooks_dir = tmp_path / "config" / "githooks" / "hooks"
        hooks_dir.mkdir(parents=True)
        # Create a fake hook script
        (hooks_dir / "pre-commit").write_text("#!/bin/bash\necho ok")
        # Create the manifest
        manifest_path = hooks_dir / "githooks.toml"
        manifest_path.write_text(
            '[channel]\nname="test"\n[[hooks]]\nname="pre-commit"\nscript="pre-commit"\n'
        )
        result = HooksCommand().execute(
            project_root=tmp_path,
            manifest=manifest_path,
            source_dir=hooks_dir,
            dest_dir=tmp_path / "installed",
        )
        assert result.ok
        assert (tmp_path / "installed" / "pre-commit").exists()


class TestSyncCommand:
    """Tests for SyncCommand (offline)."""

    def test_sync_command_name(self) -> None:
        """SyncCommand has correct name and help."""
        cmd = SyncCommand()
        assert cmd.name == "sync"
        assert "sync" in cmd.help.lower()

    def test_sync_command_repr(self) -> None:
        """SyncCommand repr contains class name."""
        assert "SyncCommand" in repr(SyncCommand())
