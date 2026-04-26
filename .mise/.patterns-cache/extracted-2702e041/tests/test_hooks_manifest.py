"""Tests for dev_patterns.hooks.manifest — HookManifest and HookEntry."""

from __future__ import annotations

from pathlib import Path

import pytest

from dev_patterns.hooks.manifest import HookEntry, HookManifest

MINIMAL_TOML = """
[channel]
name    = "python3a"
version = "0.1.0"

[[hooks]]
name   = "pre-commit"
script = "pre-commit"
"""

FULL_TOML = """
[channel]
name        = "python3a"
version     = "0.1.0"
description = "Python 3 hooks"
author      = "orchestras"
repo        = "orchestras/dev-patterns"

[[hooks]]
name        = "pre-commit"
script      = "pre-commit"
description = "Lint and format checks"
enabled     = true
fail_fast   = true

[[hooks]]
name        = "commit-msg"
script      = "commit-msg"
description = "Conventional commits validation"
enabled     = true
fail_fast   = true

[[hooks]]
name        = "pre-push"
script      = "pre-push"
description = "Full test run"
enabled     = false
fail_fast   = true
"""


class TestHookEntry:
    """Tests for HookEntry dataclass."""

    def test_defaults(self) -> None:
        """Default values are applied when optional fields are omitted."""
        entry = HookEntry(name="pre-commit", script="pre-commit")
        assert entry.enabled is True
        assert entry.fail_fast is True
        assert entry.description == ""

    def test_str_enabled(self) -> None:
        """__str__ shows 'enabled' for enabled hooks."""
        entry = HookEntry(name="pre-commit", script="pre-commit", enabled=True)
        assert "enabled" in str(entry)

    def test_str_disabled(self) -> None:
        """__str__ shows 'disabled' for disabled hooks."""
        entry = HookEntry(name="pre-push", script="pre-push", enabled=False)
        assert "disabled" in str(entry)


class TestHookManifest:
    """Tests for HookManifest."""

    def test_from_string_minimal(self) -> None:
        """Parses a minimal TOML manifest."""
        manifest = HookManifest.from_string(MINIMAL_TOML)
        assert manifest.channel.name == "python3a"
        assert len(manifest.hooks) == 1
        assert manifest.hooks[0].name == "pre-commit"

    def test_from_string_full(self) -> None:
        """Parses a full manifest with all fields."""
        manifest = HookManifest.from_string(FULL_TOML)
        assert manifest.channel.version == "0.1.0"
        assert manifest.channel.author == "orchestras"
        assert len(manifest.hooks) == 3

    def test_enabled_hooks_filters_disabled(self) -> None:
        """enabled_hooks excludes entries with enabled=false."""
        manifest = HookManifest.from_string(FULL_TOML)
        enabled = manifest.enabled_hooks
        assert len(enabled) == 2
        assert all(h.enabled for h in enabled)
        names = [h.name for h in enabled]
        assert "pre-push" not in names

    def test_from_toml_file(self, tmp_path: Path) -> None:
        """Loads a manifest from a real file."""
        toml_file = tmp_path / "githooks.toml"
        toml_file.write_text(MINIMAL_TOML)
        manifest = HookManifest.from_toml(toml_file)
        assert manifest.path == toml_file.resolve()
        assert manifest.channel.name == "python3a"

    def test_from_toml_file_not_found(self, tmp_path: Path) -> None:
        """Raises FileNotFoundError for missing files."""
        with pytest.raises(FileNotFoundError):
            HookManifest.from_toml(tmp_path / "nonexistent.toml")

    def test_from_string_invalid_toml(self) -> None:
        """Raises ValueError for malformed TOML."""
        with pytest.raises(ValueError, match="Failed to parse"):
            HookManifest.from_string("{{{{ not valid toml")

    def test_empty_hooks_list(self) -> None:
        """Manifest with no [[hooks]] entries has empty lists."""
        manifest = HookManifest.from_string("[channel]\nname = 'test'\n")
        assert manifest.hooks == []
        assert manifest.enabled_hooks == []

    def test_real_githooks_toml(self) -> None:
        """Parses the actual githooks.toml from lib/python3a/hooks/."""
        real_path = Path(__file__).parent.parent / "lib" / "python3a" / "hooks" / "githooks.toml"
        if not real_path.exists():
            pytest.skip("lib/python3a/hooks/githooks.toml not present")
        manifest = HookManifest.from_toml(real_path)
        assert manifest.channel.name != ""
        assert len(manifest.hooks) > 0
