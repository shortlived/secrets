"""Tests for scripts/sync_patterns.py — standalone bootstrap sync script.

These tests import the module directly to test its logic without network calls.
"""

from __future__ import annotations

# Import functions from the standalone script (not a package, so use importlib)
import importlib.util
import stat
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def sync_module():
    """Import sync_patterns.py as a module for testing."""
    script_path = Path(__file__).parent.parent / "scripts" / "sync_patterns.py"
    spec = importlib.util.spec_from_file_location("sync_patterns", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


class TestResolveSpec:
    """Tests for resolve_spec() in sync_patterns.py."""

    def test_defaults(self, sync_module: object, tmp_path: Path) -> None:
        """Falls back to defaults when nothing configured."""
        repo, channel, version, use_release = sync_module.resolve_spec(tmp_path)  # type: ignore[attr-defined]
        assert repo == "orchestras/dev-patterns"
        assert channel == "python3a"
        assert version == "main"
        assert use_release is False

    def test_mise_toml_githooks(
        self, sync_module: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Reads GITHOOKS_* from mise.toml."""
        monkeypatch.delenv("PATTERNS_REPO", raising=False)
        monkeypatch.delenv("PATTERNS_CHANNEL", raising=False)
        (tmp_path / "mise.toml").write_text(
            '[env]\nGITHOOKS_REPO = "my/repo"\n'
            'GITHOOKS_VERSION = "develop"\n'
            'GITHOOKS_PROFILE = "python3a"\n'
        )
        repo, channel, version, use_release = sync_module.resolve_spec(tmp_path)  # type: ignore[attr-defined]
        assert repo == "my/repo"
        assert channel == "python3a"
        assert version == "develop"
        assert use_release is False

    def test_githooks_version_new_format(
        self, sync_module: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Parses new-format .githooks-version."""
        monkeypatch.delenv("PATTERNS_REPO", raising=False)
        monkeypatch.delenv("PATTERNS_CHANNEL", raising=False)
        (tmp_path / ".githooks-version").write_text("myorg/myrepo/python3a/v0.2.0\n")
        repo, channel, version, use_release = sync_module.resolve_spec(tmp_path)  # type: ignore[attr-defined]
        assert repo == "myorg/myrepo"
        assert channel == "python3a"
        assert version == "v0.2.0"
        assert use_release is True

    def test_githooks_version_old_format(
        self, sync_module: object, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Parses legacy version-only .githooks-version."""
        monkeypatch.delenv("PATTERNS_REPO", raising=False)
        monkeypatch.delenv("PATTERNS_CHANNEL", raising=False)
        (tmp_path / ".githooks-version").write_text("v0.1.12\n")
        _, _, version, use_release = sync_module.resolve_spec(tmp_path)  # type: ignore[attr-defined]
        assert version == "v0.1.12"
        assert use_release is True

    def test_is_release_tag(self, sync_module: object) -> None:
        """_is_release_tag correctly identifies release tags."""
        assert sync_module._is_release_tag("v1.2.3") is True  # type: ignore[attr-defined]
        assert sync_module._is_release_tag("main") is False  # type: ignore[attr-defined]
        assert sync_module._is_release_tag("") is False  # type: ignore[attr-defined]


class TestCopyTree:
    """Tests for copy_tree() in sync_patterns.py."""

    def test_copies_files(self, sync_module: object, tmp_path: Path) -> None:
        """copy_tree copies all files to destination."""
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        (src / "a.sh").write_text("#!/bin/bash")
        (src / "sub").mkdir()
        (src / "sub" / "b.sh").write_text("#!/bin/bash")

        written = sync_module.copy_tree(src, dst)  # type: ignore[attr-defined]
        assert dst.exists()
        assert len(written) == 2

    def test_skip_extensions(self, sync_module: object, tmp_path: Path) -> None:
        """copy_tree respects skip_ext parameter."""
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        (src / "hook").write_text("#!/bin/bash")
        (src / "manifest.toml").write_text("[channel]")

        written = sync_module.copy_tree(src, dst, skip_ext={".toml"})  # type: ignore[attr-defined]
        assert len(written) == 1
        assert not (dst / "manifest.toml").exists()

    def test_only_extensions(self, sync_module: object, tmp_path: Path) -> None:
        """copy_tree respects only_ext parameter."""
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        (src / "hook").write_text("#!/bin/bash")
        (src / "manifest.toml").write_text("[channel]")

        written = sync_module.copy_tree(src, dst, only_ext={".toml"})  # type: ignore[attr-defined]
        assert len(written) == 1
        assert (dst / "manifest.toml").exists()

    def test_make_executable(self, sync_module: object, tmp_path: Path) -> None:
        """copy_tree sets executable bits when make_executable=True."""
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        hook = src / "pre-commit"
        hook.write_text("#!/bin/bash")
        hook.chmod(0o644)

        sync_module.copy_tree(src, dst, make_executable=True)  # type: ignore[attr-defined]
        copied = dst / "pre-commit"
        assert copied.stat().st_mode & stat.S_IXUSR


class TestApplyChannel:
    """Tests for apply_channel() in sync_patterns.py."""

    def _make_channel_tree(self, base: Path, channel: str = "python3a") -> Path:
        """Create a fake extracted channel tree."""
        channel_dir = base / "lib" / channel
        tasks = channel_dir / "mise" / "tasks" / "patterns"
        tasks.mkdir(parents=True)
        (tasks / "sync").write_text("#!/bin/bash\necho sync")
        hooks = channel_dir / "hooks"
        hooks.mkdir()
        (hooks / "pre-commit").write_text("#!/bin/bash\necho hook")
        (hooks / "githooks.toml").write_text("[channel]\nname='test'")
        return base

    def test_syncs_tasks_and_hooks(self, sync_module: object, tmp_path: Path) -> None:
        """apply_channel syncs both tasks and hooks."""
        extract_dir = tmp_path / "extracted"
        self._make_channel_tree(extract_dir)
        root = tmp_path / "project"
        root.mkdir()

        written = sync_module.apply_channel(extract_dir, "python3a", root)  # type: ignore[attr-defined]
        assert len(written) > 0
        assert (root / ".mise" / "tasks" / "patterns" / "sync").exists()
        assert (root / "config" / "githooks" / "hooks" / "pre-commit").exists()

    def test_missing_channel_returns_empty(self, sync_module: object, tmp_path: Path) -> None:
        """apply_channel returns [] when channel dir doesn't exist."""
        extract_dir = tmp_path / "empty"
        extract_dir.mkdir()
        root = tmp_path / "project"
        root.mkdir()

        written = sync_module.apply_channel(extract_dir, "python3a", root)  # type: ignore[attr-defined]
        assert written == []
