"""Tests for dev_patterns.hooks.installer — HookInstaller."""

from __future__ import annotations

import io
import stat
from pathlib import Path

import pytest

from dev_patterns.core.ui import Console
from dev_patterns.hooks.installer import HookInstaller
from dev_patterns.hooks.manifest import HookManifest


def make_console() -> Console:
    """Return a Console that writes to StringIO (silent during tests)."""
    return Console(out=io.StringIO(), err=io.StringIO())


class TestHookInstaller:
    """Tests for HookInstaller."""

    @pytest.fixture
    def source_dir(self, tmp_path: Path) -> Path:
        """Create a source directory with fake hook scripts."""
        src = tmp_path / "hooks_src"
        src.mkdir()
        for name in ("pre-commit", "commit-msg", "pre-push"):
            script = src / name
            script.write_text(f"#!/usr/bin/env bash\necho '{name}'\n")
            script.chmod(0o644)
        return src

    @pytest.fixture
    def dest_dir(self, tmp_path: Path) -> Path:
        """Return a (non-existent) destination directory."""
        return tmp_path / "hooks_dest"

    @pytest.fixture
    def manifest(self) -> HookManifest:
        """Return a manifest with three hooks."""
        return HookManifest.from_string("""
[channel]
name = "test"

[[hooks]]
name   = "pre-commit"
script = "pre-commit"

[[hooks]]
name   = "commit-msg"
script = "commit-msg"

[[hooks]]
name    = "pre-push"
script  = "pre-push"
enabled = false
""")

    def test_install_creates_dest_dir(
        self, source_dir: Path, dest_dir: Path, manifest: HookManifest
    ) -> None:
        """Install creates the destination directory."""
        installer = HookInstaller(source_dir=source_dir, dest_dir=dest_dir, console=make_console())
        installer.install(manifest)
        assert dest_dir.exists()

    def test_install_only_enabled_hooks(
        self, source_dir: Path, dest_dir: Path, manifest: HookManifest
    ) -> None:
        """Only enabled hooks are installed."""
        installer = HookInstaller(source_dir=source_dir, dest_dir=dest_dir, console=make_console())
        installed = installer.install(manifest)
        assert "pre-commit" in installed
        assert "commit-msg" in installed
        assert "pre-push" not in installed

    def test_installed_files_are_executable(
        self, source_dir: Path, dest_dir: Path, manifest: HookManifest
    ) -> None:
        """Installed hooks have executable bits set."""
        installer = HookInstaller(source_dir=source_dir, dest_dir=dest_dir, console=make_console())
        installer.install(manifest)
        for name in ("pre-commit", "commit-msg"):
            hook = dest_dir / name
            assert hook.exists()
            mode = hook.stat().st_mode
            assert mode & stat.S_IXUSR, f"{name} should be user-executable"

    def test_install_missing_script_skipped(self, tmp_path: Path, dest_dir: Path) -> None:
        """Hooks whose script file is missing are skipped gracefully."""
        src = tmp_path / "empty_src"
        src.mkdir()
        manifest = HookManifest.from_string("""
[channel]
name = "test"
[[hooks]]
name   = "pre-commit"
script = "pre-commit"
""")
        console = make_console()
        installer = HookInstaller(source_dir=src, dest_dir=dest_dir, console=console)
        installed = installer.install(manifest)
        assert installed == []

    def test_list_installed_empty(self, tmp_path: Path) -> None:
        """list_installed returns [] when dest_dir does not exist."""
        installer = HookInstaller(
            source_dir=tmp_path,
            dest_dir=tmp_path / "nonexistent",
            console=make_console(),
        )
        assert installer.list_installed() == []

    def test_list_installed_after_install(
        self, source_dir: Path, dest_dir: Path, manifest: HookManifest
    ) -> None:
        """list_installed returns installed hook names."""
        installer = HookInstaller(source_dir=source_dir, dest_dir=dest_dir, console=make_console())
        installer.install(manifest)
        listed = installer.list_installed()
        assert "pre-commit" in listed
        assert "commit-msg" in listed

    def test_uninstall_removes_hook(
        self, source_dir: Path, dest_dir: Path, manifest: HookManifest
    ) -> None:
        """uninstall removes specified hooks."""
        installer = HookInstaller(source_dir=source_dir, dest_dir=dest_dir, console=make_console())
        installer.install(manifest)
        removed = installer.uninstall(["pre-commit"])
        assert "pre-commit" in removed
        assert not (dest_dir / "pre-commit").exists()
        assert (dest_dir / "commit-msg").exists()

    def test_uninstall_nonexistent_ignored(self, tmp_path: Path) -> None:
        """uninstall does not raise when a hook file is missing."""
        dest = tmp_path / "hooks"
        dest.mkdir()
        installer = HookInstaller(source_dir=tmp_path, dest_dir=dest, console=make_console())
        removed = installer.uninstall(["pre-commit"])
        assert removed == []
