"""Tests for dev_patterns.sync.engine — SyncEngine and SyncResult."""

from __future__ import annotations

import io
import shutil
import tarfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from dev_patterns.core.ui import Console
from dev_patterns.sync.engine import SyncEngine, SyncResult
from dev_patterns.version_spec.resolver import VersionSpec


def make_console() -> Console:
    """Return a silent Console for tests."""
    return Console(out=io.StringIO(), err=io.StringIO())


def make_spec(
    repo: str = "orchestras/dev-patterns",
    channel: str = "python3a",
    version: str = "main",
    use_release: bool = False,
) -> VersionSpec:
    """Return a VersionSpec with sensible defaults."""
    return VersionSpec(
        repo=repo,
        channel=channel,
        version=version,
        use_release=use_release,
        source="test",
    )


def make_fake_tarball(
    tmp_path: Path,
    channel: str = "python3a",
    include_tasks: bool = True,
    include_hooks: bool = True,
) -> Path:
    """Create a fake patterns tarball under tmp_path and return its path.

    The tarball mirrors the GitHub archive format with a top-level directory
    ``orchestras-dev-patterns-abc1234/`` that is stripped during extraction.
    """
    tarball = tmp_path / "fake.tar.gz"
    staging = tmp_path / "staging"

    top_dir = "orchestras-dev-patterns-abc1234"
    channel_dir = staging / top_dir / "lib" / channel

    if include_tasks:
        tasks_dir = channel_dir / "mise" / "tasks" / "patterns"
        tasks_dir.mkdir(parents=True)
        (tasks_dir / "sync").write_text("#!/usr/bin/env bash\necho sync\n")

    if include_hooks:
        hooks_dir = channel_dir / "hooks"
        hooks_dir.mkdir(parents=True)
        (hooks_dir / "pre-commit").write_text("#!/usr/bin/env bash\necho pre-commit\n")
        (hooks_dir / "githooks.toml").write_text("[channel]\nname='test'\n")

    with tarfile.open(tarball, "w:gz") as tf:
        for p in staging.rglob("*"):
            arcname = str(p.relative_to(staging))
            tf.add(p, arcname=arcname)

    shutil.rmtree(staging)
    return tarball


class TestSyncResult:
    """Tests for SyncResult dataclass."""

    def test_ok_when_no_error(self) -> None:
        """ok is True when error is empty."""
        result = SyncResult()
        assert result.ok is True

    def test_not_ok_when_error(self) -> None:
        """ok is False when error is non-empty."""
        result = SyncResult(error="something went wrong")
        assert result.ok is False

    def test_changed_when_files_written(self) -> None:
        """changed is True when synced_files is non-empty."""
        result = SyncResult(synced_files=["a", "b"])
        assert result.changed is True

    def test_not_changed_when_skipped(self) -> None:
        """changed is False when skipped."""
        result = SyncResult(skipped=True)
        assert result.changed is False


class TestSyncEngine:
    """Tests for SyncEngine."""

    @pytest.fixture
    def project(self, tmp_path: Path) -> Path:
        """Return a temporary project root with a mock mise.toml."""
        (tmp_path / "mise.toml").write_text('[env]\nPATTERNS_CHANNEL = "python3a"\n')
        return tmp_path

    def test_skip_when_hash_current(self, project: Path) -> None:
        """run() skips when .patterns-hash already matches latest SHA."""
        sha = "a" * 40
        (project / ".patterns-hash").write_text(sha + "\n")

        mock_client = MagicMock()
        mock_client.head_sha.return_value = sha

        spec = make_spec()
        engine = SyncEngine(
            project_root=project,
            spec=spec,
            console=make_console(),
            client=mock_client,
        )
        result = engine.run()
        assert result.skipped is True
        assert result.commit_hash == sha
        mock_client.download_tarball.assert_not_called()

    def test_error_when_sha_unreachable(self, project: Path) -> None:
        """run() returns error when HEAD SHA cannot be fetched."""
        mock_client = MagicMock()
        mock_client.head_sha.return_value = None

        spec = make_spec()
        engine = SyncEngine(
            project_root=project,
            spec=spec,
            console=make_console(),
            client=mock_client,
        )
        result = engine.run()
        assert not result.ok
        assert "resolve ref" in result.error.lower() or result.error != ""

    def test_sync_applies_channel_files(self, project: Path, tmp_path: Path) -> None:
        """run() downloads and applies channel files from the tarball."""
        sha = "b" * 40
        tarball_path = make_fake_tarball(tmp_path)

        mock_client = MagicMock()
        mock_client.head_sha.return_value = sha
        mock_client.download_tarball.side_effect = lambda ref, dest: (
            shutil.copy2(tarball_path, dest) or dest
        )

        spec = make_spec()
        cache_dir = project / ".mise" / ".patterns-cache"
        engine = SyncEngine(
            project_root=project,
            spec=spec,
            cache_dir=cache_dir,
            console=make_console(),
            client=mock_client,
        )
        result = engine.run()

        assert result.ok
        assert result.commit_hash == sha
        assert (project / ".patterns-hash").read_text().strip() == sha
        assert len(result.synced_files) > 0

        # Hooks should be installed
        hooks_dir = project / "config" / "githooks" / "hooks"
        assert (hooks_dir / "pre-commit").exists()

        # Tasks should be installed
        tasks_dir = project / ".mise" / "tasks" / "patterns"
        assert (tasks_dir / "sync").exists()

    def test_hash_file_written_after_sync(self, project: Path, tmp_path: Path) -> None:
        """run() writes .patterns-hash after a successful sync."""
        sha = "c" * 40
        tarball_path = make_fake_tarball(tmp_path)

        mock_client = MagicMock()
        mock_client.head_sha.return_value = sha
        mock_client.download_tarball.side_effect = lambda ref, dest: (
            shutil.copy2(tarball_path, dest) or dest
        )

        spec = make_spec()
        engine = SyncEngine(
            project_root=project,
            spec=spec,
            console=make_console(),
            client=mock_client,
        )
        engine.run()

        hash_file = project / ".patterns-hash"
        assert hash_file.exists()
        assert hash_file.read_text().strip() == sha

    def test_release_sync_calls_release_download(self, project: Path, tmp_path: Path) -> None:
        """run() calls download_release_tarball for use_release specs."""
        tarball_path = make_fake_tarball(tmp_path)

        mock_client = MagicMock()
        mock_client.download_release_tarball.side_effect = lambda tag, dest: (
            shutil.copy2(tarball_path, dest) or dest
        )

        spec = make_spec(version="v0.1.0", use_release=True)
        cache_dir = project / ".mise" / ".patterns-cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        engine = SyncEngine(
            project_root=project,
            spec=spec,
            cache_dir=cache_dir,
            console=make_console(),
            client=mock_client,
        )
        result = engine.run()

        mock_client.download_release_tarball.assert_called_once_with(
            "v0.1.0", cache_dir / "release-v0.1.0.tar.gz"
        )
        assert result.ok

    def test_release_sync_error_on_download_failure(self, project: Path) -> None:
        """run() returns error when release download fails."""
        mock_client = MagicMock()
        mock_client.download_release_tarball.side_effect = RuntimeError("404 Not Found")

        spec = make_spec(version="v9.9.9", use_release=True)
        cache_dir = project / ".mise" / ".patterns-cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        engine = SyncEngine(
            project_root=project,
            spec=spec,
            cache_dir=cache_dir,
            console=make_console(),
            client=mock_client,
        )
        result = engine.run()
        assert not result.ok
        assert "404" in result.error or result.error != ""

    def test_missing_channel_in_tarball(self, project: Path, tmp_path: Path) -> None:
        """run() handles missing channel dir in tarball gracefully."""
        sha = "d" * 40
        # Create a tarball WITHOUT the expected channel directory
        tarball_path = make_fake_tarball(tmp_path, channel="OTHER_CHANNEL")

        mock_client = MagicMock()
        mock_client.head_sha.return_value = sha
        mock_client.download_tarball.side_effect = lambda ref, dest: (
            shutil.copy2(tarball_path, dest) or dest
        )

        spec = make_spec(channel="python3a")
        engine = SyncEngine(
            project_root=project,
            spec=spec,
            console=make_console(),
            client=mock_client,
        )
        result = engine.run()
        assert result.ok
        assert result.synced_files == []
