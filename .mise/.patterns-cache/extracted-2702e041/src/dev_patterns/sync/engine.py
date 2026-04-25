"""Sync engine — orchestrates download, extraction, and file placement."""

from __future__ import annotations

import shutil
import stat
import tarfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO

from dev_patterns.core.ui import Console
from dev_patterns.sync.client import GitHubClient
from dev_patterns.version_spec.resolver import VersionSpec


@dataclass(frozen=True)
class SyncResult:
    """Outcome of a sync operation.

    Attributes:
        skipped:        True when the hash is already current (no-op).
        synced_files:   Relative paths of files that were written.
        commit_hash:    Commit hash that was synced.
        spec:           The resolved VersionSpec that drove the sync.
        error:          Non-empty when the sync failed.
    """

    skipped: bool = False
    synced_files: list[str] = field(default_factory=list)
    commit_hash: str = ""
    spec: VersionSpec | None = None
    error: str = ""

    @property
    def ok(self) -> bool:
        """Return True when the sync completed without error."""
        return not self.error

    @property
    def changed(self) -> bool:
        """Return True when files were actually written."""
        return bool(self.synced_files)


@dataclass
class SyncEngine:
    """Download and apply a patterns channel to a project directory.

    The engine:

    1. Reads the cached hash from ``.patterns-hash`` (if present).
    2. Fetches the latest commit SHA from the patterns repo.
    3. Skips if the hash matches (idempotent).
    4. Downloads the tarball (or release tarball for release specs).
    5. Extracts ``lib/$channel/**`` into the target tree:
       - ``hooks/`` → ``config/githooks/hooks/``
       - ``mise/tasks/`` → ``.mise/tasks/``
       - All other items copied to the project root, preserving structure.
    6. Updates ``.patterns-hash`` with the new SHA.

    For release-tagged specs (old ``.githooks-version`` style) the tarball
    is pulled from GitHub Releases.  The full archive is extracted to the
    project root so any ``config/hooks``, ``bin/`` etc. land correctly.

    Attributes:
        project_root: Absolute path to the project being synced.
        spec:         Resolved :class:`VersionSpec`.
        cache_dir:    Where to store downloaded tarballs.
        console:      UI console for output.
        client:       GitHub client (created automatically if not supplied).
    """

    project_root: Path
    spec: VersionSpec
    cache_dir: Path | None = field(default=None)
    console: Console | None = field(default=None)
    client: GitHubClient | None = field(default=None)

    # Resolved (non-None) references set in __post_init__
    _console: Console = field(init=False, repr=False)
    _client: GitHubClient = field(init=False, repr=False)
    _cache_dir: Path = field(init=False, repr=False)

    def __post_init__(self) -> None:
        """Set up defaults for console, client, and cache_dir."""
        self._console = self.console if self.console is not None else Console()
        self._client = self.client if self.client is not None else GitHubClient(self.spec.repo)
        self._cache_dir = (
            self.cache_dir
            if self.cache_dir is not None
            else self.project_root / ".mise" / ".patterns-cache"
        )

    # ── Public API ────────────────────────────────────────────────────────────

    def run(self) -> SyncResult:
        """Execute the sync.

        Returns:
            SyncResult describing what happened.
        """
        self._console.header("Patterns Sync")
        self._console.info("Repo", self.spec.repo)
        self._console.info("Channel", self.spec.channel)
        self._console.info("Source", self.spec.source)
        self._console.blank()

        if self.spec.use_release:
            return self._sync_release()
        return self._sync_ref()

    # ── Internal sync paths ───────────────────────────────────────────────────

    def _sync_ref(self) -> SyncResult:
        """Sync from a branch/SHA ref (no release required)."""
        self._console.working("Fetching latest commit hash…")
        latest_hash = self._client.head_sha(self.spec.version)
        if not latest_hash:
            msg = f"Could not resolve ref '{self.spec.version}' on {self.spec.repo}"
            self._console.warn(msg)
            return SyncResult(error=msg, spec=self.spec)

        if self._is_current(latest_hash):
            self._console.ok(f"Already current ({latest_hash[:8]})")
            return SyncResult(skipped=True, commit_hash=latest_hash, spec=self.spec)

        tarball = self._download_ref_tarball(latest_hash)
        if tarball is None:
            msg = "Tarball download failed"
            self._console.error(msg)
            return SyncResult(error=msg, spec=self.spec)

        extract_dir = self._extract(tarball)
        synced = self._apply_channel(extract_dir, latest_hash)
        self._write_hash(latest_hash)
        self._console.blank()
        self._console.done(f"Patterns synced ({self.spec.channel} @ {latest_hash[:8]})")
        return SyncResult(synced_files=synced, commit_hash=latest_hash, spec=self.spec)

    def _sync_release(self) -> SyncResult:
        """Sync from a GitHub Release tarball.

        For release-tagged specs the entire tarball is extracted to the
        project root.  This mirrors how existing scripts work.

        # NOTE: To adjust which paths are extracted from a release tarball,
        # modify the _apply_release() method.  Currently it extracts
        # everything from the tarball root into the project root.
        """
        tag = self.spec.version
        self._console.working(f"Downloading release tarball {tag}…")
        tarball_path = self._cache_dir / f"release-{tag}.tar.gz"
        try:
            self._client.download_release_tarball(tag, tarball_path)
        except RuntimeError as exc:
            msg = str(exc)
            self._console.error(msg)
            return SyncResult(error=msg, spec=self.spec)

        extract_dir = self._extract(tarball_path)
        synced = self._apply_release(extract_dir)
        self._console.blank()
        self._console.done(f"Release {tag} applied from {self.spec.repo}")
        return SyncResult(synced_files=synced, commit_hash=tag, spec=self.spec)

    # ── Download helpers ──────────────────────────────────────────────────────

    def _download_ref_tarball(self, sha: str) -> Path | None:
        """Download a ref tarball; returns path or None on failure."""
        self._console.working(f"Downloading tarball ({sha[:8]})…")
        tarball_path = self._cache_dir / f"patterns-{sha[:8]}.tar.gz"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._client.download_tarball(sha, tarball_path)
        except Exception:
            return None
        else:
            if tarball_path.stat().st_size == 0:
                return None
            return tarball_path

    def _extract(self, tarball: Path) -> Path:
        """Extract *tarball* to a sibling directory and return it."""
        extract_dir = tarball.parent / tarball.stem.replace(".tar", "")
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
        extract_dir.mkdir(parents=True)
        with tarfile.open(tarball, "r:gz") as tf:
            members = tf.getmembers()
            # Strip the GitHub-generated top-level directory (org-repo-sha/)
            prefix = members[0].name.split("/")[0] if members else ""
            pfx = prefix + "/"
            for member in members:
                rel = member.name[len(pfx) :] if member.name.startswith(pfx) else member.name
                if not rel:
                    continue
                dest = extract_dir / rel
                if member.isdir():
                    dest.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    fh: IO[bytes] | None = tf.extractfile(member)
                    if fh is not None:
                        with fh, dest.open("wb") as out:
                            shutil.copyfileobj(fh, out)
                    # Preserve executable bit
                    if member.mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
                        dest.chmod(dest.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        return extract_dir

    # ── Apply helpers ─────────────────────────────────────────────────────────

    def _apply_channel(self, extract_dir: Path, sha: str) -> list[str]:
        """Copy channel contents from the extracted tree into the project.

        Args:
            extract_dir: Root of the extracted tarball.
            sha:         Commit SHA being applied (for logging).

        Returns:
            List of relative file paths that were written.
        """
        channel_dir = extract_dir / "lib" / self.spec.channel
        if not channel_dir.exists():
            self._console.warn(f"Channel directory not found: lib/{self.spec.channel}")
            return []

        written: list[str] = []

        # Sync mise tasks
        tasks_src = channel_dir / "mise" / "tasks"
        if tasks_src.exists():
            self._console.working("Syncing mise tasks…")
            tasks_dst = self.project_root / ".mise" / "tasks"
            written += self._copy_tree(tasks_src, tasks_dst, make_executable=True)
            self._console.ok(f"Tasks synced → .mise/tasks/ ({len(written)} files)")

        # Sync hooks
        hooks_src = channel_dir / "hooks"
        hooks_count_before = len(written)
        if hooks_src.exists():
            self._console.working("Syncing git hooks…")
            hooks_dst = self.project_root / "config" / "githooks" / "hooks"
            hook_files = self._copy_tree(
                hooks_src,
                hooks_dst,
                make_executable=True,
                skip_extensions={".toml"},
            )
            manifest_files = self._copy_tree(
                hooks_src,
                hooks_dst,
                make_executable=False,
                only_extensions={".toml"},
            )
            written += hook_files + manifest_files
            n = len(written) - hooks_count_before
            self._console.ok(f"Hooks synced → config/githooks/hooks/ ({n} files)")

        # Sync any other top-level items in the channel directory
        for item in channel_dir.iterdir():
            if item.name in ("mise", "hooks"):
                continue
            dest = self.project_root / item.name
            if item.is_dir():
                extra = self._copy_tree(item, dest)
                written += extra
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest)
                written.append(item.name)
            self._console.ok(f"Synced {item.name}")

        return written

    def _apply_release(self, extract_dir: Path) -> list[str]:
        """Extract a release tarball into the project root.

        Everything from the tarball is mirrored under the project root.
        The ``config/hooks`` and ``bin/`` directories are highlighted in
        logs because those are the typical release payload.

        # NOTE: Adjust the path list below to restrict which directories
        # are extracted from a release tarball, e.g.:
        #   RELEASE_EXTRACT_PATHS = ["config/hooks", "bin"]
        # Currently we extract everything (safest for unknown layouts).

        Args:
            extract_dir: Root of the extracted tarball.

        Returns:
            List of relative paths that were written.
        """
        written: list[str] = []
        for src_path in extract_dir.rglob("*"):
            if src_path.is_dir():
                continue
            rel = src_path.relative_to(extract_dir)
            dest = self.project_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_path, dest)
            written.append(str(rel))
        if written:
            self._console.ok(f"Extracted {len(written)} files from release tarball")
        return written

    # ── Utility helpers ───────────────────────────────────────────────────────

    def _copy_tree(
        self,
        src: Path,
        dst: Path,
        make_executable: bool = False,
        skip_extensions: set[str] | None = None,
        only_extensions: set[str] | None = None,
    ) -> list[str]:
        """Recursively copy *src* into *dst*.

        Args:
            src:              Source directory.
            dst:              Destination directory (created if absent).
            make_executable:  If True, add executable bits to every copied file.
            skip_extensions:  Skip files with these extensions.
            only_extensions:  If set, only copy files with these extensions.

        Returns:
            List of relative destination paths written.
        """
        dst.mkdir(parents=True, exist_ok=True)
        written: list[str] = []
        for item in src.rglob("*"):
            if item.is_dir():
                continue
            ext = item.suffix.lower()
            if skip_extensions and ext in skip_extensions:
                continue
            if only_extensions and ext not in only_extensions:
                continue
            rel = item.relative_to(src)
            dest_file = dst / rel
            dest_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest_file)
            if make_executable:
                current = dest_file.stat().st_mode
                dest_file.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            written.append(str(dest_file.relative_to(self.project_root)))
        return written

    def _is_current(self, sha: str) -> bool:
        """Return True if *.patterns-hash* already records *sha*."""
        hash_file = self.project_root / ".patterns-hash"
        if not hash_file.exists():
            return False
        return hash_file.read_text().strip() == sha

    def _write_hash(self, sha: str) -> None:
        """Write *sha* to ``.patterns-hash``."""
        (self.project_root / ".patterns-hash").write_text(sha + "\n")
