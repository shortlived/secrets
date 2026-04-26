"""Tests for dev_patterns.version_spec — VersionSpec and VersionSpecResolver."""

from __future__ import annotations

from pathlib import Path

import pytest

from dev_patterns.version_spec.resolver import VersionSpec, VersionSpecResolver

# ── VersionSpec unit tests ────────────────────────────────────────────────────


class TestVersionSpec:
    """Tests for VersionSpec dataclass."""

    def test_short_version_sha(self) -> None:
        """SHA versions are truncated to 8 characters."""
        spec = VersionSpec(
            repo="orchestras/dev-patterns",
            channel="python3a",
            version="a" * 40,
        )
        assert spec.short_version == "a" * 8

    def test_short_version_tag(self) -> None:
        """Tag versions are returned as-is."""
        spec = VersionSpec(
            repo="orchestras/dev-patterns",
            channel="python3a",
            version="v0.1.12",
        )
        assert spec.short_version == "v0.1.12"

    def test_str_without_release(self) -> None:
        """__str__ shows repo / channel @ version without [release] suffix."""
        spec = VersionSpec(
            repo="orchestras/dev-patterns",
            channel="python3a",
            version="main",
        )
        assert "[release]" not in str(spec)
        assert "orchestras/dev-patterns" in str(spec)

    def test_str_with_release(self) -> None:
        """__str__ appends [release] when use_release is True."""
        spec = VersionSpec(
            repo="orchestras/dev-patterns",
            channel="python3a",
            version="v0.1.0",
            use_release=True,
        )
        assert "[release]" in str(spec)


# ── VersionSpecResolver unit tests ───────────────────────────────────────────


class TestVersionSpecResolver:
    """Tests for VersionSpecResolver."""

    @pytest.fixture
    def tmp_project(self, tmp_path: Path) -> Path:
        """Return a temporary project directory."""
        return tmp_path

    def test_defaults_when_nothing_configured(self, tmp_project: Path) -> None:
        """Falls back to hard-coded defaults when nothing is configured."""
        resolver = VersionSpecResolver(project_root=tmp_project, env={})
        spec = resolver.resolve()
        assert spec.repo == "orchestras/dev-patterns"
        assert spec.channel == "python3a"
        assert spec.version == "main"
        assert spec.use_release is False
        assert "default" in spec.source

    def test_patterns_env_vars(self, tmp_project: Path) -> None:
        """PATTERNS_* env vars take highest priority."""
        env = {
            "PATTERNS_REPO": "myorg/my-patterns",
            "PATTERNS_CHANNEL": "deno1a",
            "PATTERNS_HASH": "abc123def456" + "0" * 28,
        }
        resolver = VersionSpecResolver(project_root=tmp_project, env=env)
        spec = resolver.resolve()
        assert spec.repo == "myorg/my-patterns"
        assert spec.channel == "deno1a"
        assert spec.version == env["PATTERNS_HASH"]
        assert "PATTERNS_*" in spec.source

    def test_patterns_env_without_hash(self, tmp_project: Path) -> None:
        """PATTERNS_REPO + PATTERNS_CHANNEL without hash uses default version."""
        env = {"PATTERNS_REPO": "myorg/my-patterns", "PATTERNS_CHANNEL": "deno1a"}
        resolver = VersionSpecResolver(project_root=tmp_project, env=env)
        spec = resolver.resolve()
        assert spec.version == "main"

    def test_mise_toml_githooks_vars(self, tmp_project: Path) -> None:
        """Reads GITHOOKS_* from mise.toml [env] section."""
        (tmp_project / "mise.toml").write_text(
            '[env]\nGITHOOKS_REPO = "myorg/hooks"\n'
            'GITHOOKS_VERSION = "v0.2.0"\n'
            'GITHOOKS_PROFILE = "node18"\n'
        )
        resolver = VersionSpecResolver(project_root=tmp_project, env={})
        spec = resolver.resolve()
        assert spec.repo == "myorg/hooks"
        assert spec.version == "v0.2.0"
        assert spec.channel == "node18"
        assert spec.use_release is True
        assert "mise.toml" in spec.source

    def test_mise_toml_non_release_version(self, tmp_project: Path) -> None:
        """GITHOOKS_VERSION = 'main' is not a release tag."""
        (tmp_project / "mise.toml").write_text(
            '[env]\nGITHOOKS_REPO = "myorg/hooks"\n'
            'GITHOOKS_VERSION = "main"\n'
            'GITHOOKS_PROFILE = "python3a"\n'
        )
        resolver = VersionSpecResolver(project_root=tmp_project, env={})
        spec = resolver.resolve()
        assert spec.use_release is False

    def test_githooks_version_new_format(self, tmp_project: Path) -> None:
        """Parses new-format .githooks-version: org/repo/channel/version."""
        (tmp_project / ".githooks-version").write_text("orchestras/dev-patterns/python3a/v0.3.1\n")
        resolver = VersionSpecResolver(project_root=tmp_project, env={})
        spec = resolver.resolve()
        assert spec.repo == "orchestras/dev-patterns"
        assert spec.channel == "python3a"
        assert spec.version == "v0.3.1"
        assert spec.use_release is True
        assert "new format" in spec.source

    def test_githooks_version_old_format(self, tmp_project: Path) -> None:
        """Parses old-format .githooks-version: bare version tag."""
        (tmp_project / ".githooks-version").write_text("v0.1.12\n")
        resolver = VersionSpecResolver(project_root=tmp_project, env={})
        spec = resolver.resolve()
        assert spec.version == "v0.1.12"
        assert spec.use_release is True
        assert "legacy" in spec.source

    def test_env_overrides_mise_toml(self, tmp_project: Path) -> None:
        """PATTERNS_* env vars override mise.toml settings."""
        (tmp_project / "mise.toml").write_text(
            '[env]\nGITHOOKS_REPO = "other/repo"\nGITHOOKS_VERSION = "v1.0.0"\n'
        )
        env = {"PATTERNS_REPO": "preferred/repo", "PATTERNS_CHANNEL": "channel1"}
        resolver = VersionSpecResolver(project_root=tmp_project, env=env)
        spec = resolver.resolve()
        assert spec.repo == "preferred/repo"
        assert "PATTERNS_*" in spec.source

    def test_env_overrides_githooks_version_file(self, tmp_project: Path) -> None:
        """PATTERNS_* env vars override .githooks-version file."""
        (tmp_project / ".githooks-version").write_text("v0.1.12\n")
        env = {"PATTERNS_REPO": "preferred/repo", "PATTERNS_CHANNEL": "channel1"}
        resolver = VersionSpecResolver(project_root=tmp_project, env=env)
        spec = resolver.resolve()
        assert spec.repo == "preferred/repo"

    def test_looks_like_release_tag(self) -> None:
        """_looks_like_release_tag correctly classifies versions."""
        assert VersionSpecResolver._looks_like_release_tag("v0.1.0") is True
        assert VersionSpecResolver._looks_like_release_tag("v1.2.3-alpha.1") is True
        assert VersionSpecResolver._looks_like_release_tag("main") is False
        assert VersionSpecResolver._looks_like_release_tag("develop") is False
        assert VersionSpecResolver._looks_like_release_tag("abc1234") is False
        assert VersionSpecResolver._looks_like_release_tag("") is False

    def test_invalid_githooks_version_ignored(self, tmp_project: Path) -> None:
        """Unrecognised .githooks-version format falls through to defaults."""
        (tmp_project / ".githooks-version").write_text("not/valid\n")
        resolver = VersionSpecResolver(project_root=tmp_project, env={})
        spec = resolver.resolve()
        assert spec.source == "built-in defaults"

    def test_malformed_mise_toml_ignored(self, tmp_project: Path) -> None:
        """Malformed mise.toml falls through to lower-priority sources."""
        (tmp_project / "mise.toml").write_text("this is not valid toml {{{{")
        resolver = VersionSpecResolver(project_root=tmp_project, env={})
        spec = resolver.resolve()
        assert spec.source == "built-in defaults"
