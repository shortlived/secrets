"""Version-spec resolver — determines which repo/channel/version to sync."""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# New-format .githooks-version has exactly 4 slash-separated parts: org/repo/channel/version
_NEW_FORMAT_PARTS = 4

# ── Data classes ──────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class VersionSpec:
    """Resolved version specification for a hooks channel.

    Attributes:
        repo:        GitHub ``org/repo`` slug, e.g. ``"orchestras/dev-patterns"``.
        channel:     Sub-directory / profile name inside ``lib/``, e.g. ``"python3a"``.
        version:     Git ref, tag, or commit SHA to pull.
        use_release: True when ``version`` refers to a release tag that should be
                     downloaded as a tarball from GitHub Releases.
        source:      Human-readable label describing where this spec came from.
    """

    repo: str
    channel: str
    version: str
    use_release: bool = False
    source: str = "default"

    @property
    def short_version(self) -> str:
        """Return a short display version (first 8 chars for SHAs, full for tags)."""
        if re.match(r"^[0-9a-f]{40}$", self.version):
            return self.version[:8]
        return self.version

    def __str__(self) -> str:
        """Return a human-readable summary."""
        release_flag = " [release]" if self.use_release else ""
        return f"{self.repo} / {self.channel} @ {self.short_version}{release_flag}"


@dataclass
class VersionSpecResolver:
    """Resolve a :class:`VersionSpec` from a project directory.

    Resolution order (first match wins):

    1. ``PATTERNS_REPO`` + ``PATTERNS_CHANNEL`` + ``PATTERNS_HASH`` env vars
       (set by ``patterns:sync`` task, always authoritative when present).
    2. ``mise.toml`` ``[env]`` section — ``GITHOOKS_REPO``, ``GITHOOKS_VERSION``,
       ``GITHOOKS_PROFILE``.
    3. ``.githooks-version`` file in new ``repo/channel/version`` format.
    4. ``.githooks-version`` file in old bare-version format (``v0.1.12``).
    5. Hard-coded defaults (``orchestras/dev-patterns``, ``python3a``, ``main``).

    Attributes:
        project_root: Path to the project being synced.
        env:          Mapping of environment variables (defaults to ``os.environ``).
        defaults:     Fallback values for repo, channel, and version.
    """

    project_root: Path
    env: dict[str, str] = field(default_factory=lambda: dict(os.environ))
    defaults: dict[str, str] = field(
        default_factory=lambda: {
            "repo": "orchestras/dev-patterns",
            "channel": "python3a",
            "version": "main",
        }
    )

    def resolve(self) -> VersionSpec:
        """Resolve and return the best :class:`VersionSpec` for this project.

        Returns:
            VersionSpec with repo, channel, version and source populated.
        """
        return (
            self._from_patterns_env()
            or self._from_mise_toml()
            or self._from_githooks_version_file()
            or self._default_spec()
        )

    # ── Private resolution methods ────────────────────────────────────────────

    def _from_patterns_env(self) -> VersionSpec | None:
        """Read PATTERNS_* env vars (highest priority — set by patterns:sync)."""
        repo = self.env.get("PATTERNS_REPO", "").strip()
        channel = self.env.get("PATTERNS_CHANNEL", "").strip()
        version = self.env.get("PATTERNS_HASH", "").strip()
        if not (repo and channel):
            return None
        if not version:
            version = self.defaults["version"]
        return VersionSpec(
            repo=repo,
            channel=channel,
            version=version,
            use_release=False,
            source="PATTERNS_* env vars",
        )

    def _from_mise_toml(self) -> VersionSpec | None:
        """Read GITHOOKS_* keys from the project's mise.toml [env] section."""
        mise_toml = self.project_root / "mise.toml"
        if not mise_toml.exists():
            return None
        try:
            data: dict[str, Any] = tomllib.loads(mise_toml.read_text())
        except Exception:
            return None

        env_section: dict[str, str] = data.get("env", {})
        repo = str(env_section.get("GITHOOKS_REPO", "")).strip()
        version = str(env_section.get("GITHOOKS_VERSION", "")).strip()
        channel = str(env_section.get("GITHOOKS_PROFILE", "")).strip()

        if not (repo or version or channel):
            return None

        repo = repo or self.defaults["repo"]
        channel = channel or self.defaults["channel"]
        version = version or self.defaults["version"]
        use_release = self._looks_like_release_tag(version)
        return VersionSpec(
            repo=repo,
            channel=channel,
            version=version,
            use_release=use_release,
            source="mise.toml [env]",
        )

    def _from_githooks_version_file(self) -> VersionSpec | None:
        """Parse a ``.githooks-version`` file in new or old format."""
        version_file = self.project_root / ".githooks-version"
        if not version_file.exists():
            return None
        raw = version_file.read_text().strip()
        return self._parse_githooks_version(raw)

    def _parse_githooks_version(self, raw: str) -> VersionSpec | None:
        """Parse the contents of a .githooks-version file.

        Supported formats:
            - ``repo/channel/version`` — new: ``orchestras/dev-patterns/python3a/v0.1.2``
            - ``version``              — old: ``v0.1.12``

        Args:
            raw: Raw file contents (already stripped).

        Returns:
            VersionSpec if parseable, else None.
        """
        if not raw:
            return None

        parts = raw.split("/")

        if len(parts) == _NEW_FORMAT_PARTS:
            # New format: org/repo/channel/version
            repo = f"{parts[0]}/{parts[1]}"
            channel = parts[2]
            version = parts[3]
            use_release = self._looks_like_release_tag(version)
            return VersionSpec(
                repo=repo,
                channel=channel,
                version=version,
                use_release=use_release,
                source=".githooks-version (new format)",
            )

        if len(parts) == 1:
            # Old format: bare version tag (v0.1.12)
            version = parts[0]
            use_release = self._looks_like_release_tag(version)
            return VersionSpec(
                repo=self.defaults["repo"],
                channel=self.defaults["channel"],
                version=version,
                use_release=use_release,
                source=".githooks-version (legacy version-only format)",
            )

        # Unrecognised format — ignore and fall through
        return None

    def _default_spec(self) -> VersionSpec:
        """Return the hard-coded default VersionSpec."""
        return VersionSpec(
            repo=self.defaults["repo"],
            channel=self.defaults["channel"],
            version=self.defaults["version"],
            use_release=False,
            source="built-in defaults",
        )

    @staticmethod
    def _looks_like_release_tag(version: str) -> bool:
        """Return True if *version* looks like a semver release tag (vX.Y.Z).

        Args:
            version: Version string to check.

        Returns:
            True for tags like ``v0.1.12``, False for ``main``, ``develop``, SHAs, etc.
        """
        return bool(re.match(r"^v\d+\.\d+\.\d+", version))
