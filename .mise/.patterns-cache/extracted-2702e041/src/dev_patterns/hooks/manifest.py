"""Declarative TOML hook manifest parser."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HookEntry:
    """A single hook declaration from ``githooks.toml``.

    Attributes:
        name:        Git hook name (e.g. ``"pre-commit"``).
        script:      Relative path to the script within the channel's hooks dir.
        description: Human-readable purpose shown during install.
        enabled:     Whether this hook should be installed (default ``True``).
        fail_fast:   Whether the hook aborts on first failure (default ``True``).
    """

    name: str
    script: str
    description: str = ""
    enabled: bool = True
    fail_fast: bool = True

    def __str__(self) -> str:
        """Return a human-readable one-liner."""
        status = "enabled" if self.enabled else "disabled"
        return f"{self.name} [{status}] → {self.script}"


@dataclass
class ChannelMeta:
    """Channel-level metadata from ``githooks.toml`` ``[channel]`` table.

    Attributes:
        name:        Channel identifier (e.g. ``"python3a"``).
        version:     Channel version string.
        description: Human-readable description.
        author:      Author or organisation.
        repo:        Source GitHub ``org/repo`` slug.
    """

    name: str = ""
    version: str = ""
    description: str = ""
    author: str = ""
    repo: str = ""


@dataclass
class HookManifest:
    """Parsed ``githooks.toml`` manifest.

    Attributes:
        channel: Channel metadata from the ``[channel]`` table.
        hooks:   Ordered list of hook entries from ``[[hooks]]`` tables.
        path:    Absolute path to the manifest file (if loaded from disk).
    """

    channel: ChannelMeta = field(default_factory=ChannelMeta)
    hooks: list[HookEntry] = field(default_factory=list)
    path: Path | None = None

    @classmethod
    def from_toml(cls, toml_path: Path) -> HookManifest:
        """Load and parse a ``githooks.toml`` file.

        Args:
            toml_path: Absolute or relative path to the manifest file.

        Returns:
            Populated HookManifest instance.

        Raises:
            FileNotFoundError: If ``toml_path`` does not exist.
            ValueError: If the TOML is malformed or has an unexpected structure.
        """
        if not toml_path.exists():
            raise FileNotFoundError(f"githooks.toml not found: {toml_path}")
        try:
            data: dict[str, Any] = tomllib.loads(toml_path.read_text())
        except Exception as exc:
            raise ValueError(f"Failed to parse {toml_path}: {exc}") from exc

        channel = cls._parse_channel(data.get("channel", {}))
        hooks = [cls._parse_hook(h) for h in data.get("hooks", [])]
        return cls(channel=channel, hooks=hooks, path=toml_path.resolve())

    @classmethod
    def from_string(cls, toml_str: str) -> HookManifest:
        """Parse a ``githooks.toml`` from a string (useful for testing).

        Args:
            toml_str: Raw TOML content.

        Returns:
            Populated HookManifest instance.

        Raises:
            ValueError: If the TOML is malformed.
        """
        try:
            data: dict[str, Any] = tomllib.loads(toml_str)
        except Exception as exc:
            raise ValueError(f"Failed to parse TOML string: {exc}") from exc

        channel = cls._parse_channel(data.get("channel", {}))
        hooks = [cls._parse_hook(h) for h in data.get("hooks", [])]
        return cls(channel=channel, hooks=hooks)

    @property
    def enabled_hooks(self) -> list[HookEntry]:
        """Return only hooks with ``enabled = true``."""
        return [h for h in self.hooks if h.enabled]

    # ── Private helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _parse_channel(raw: dict[str, Any]) -> ChannelMeta:
        return ChannelMeta(
            name=str(raw.get("name", "")),
            version=str(raw.get("version", "")),
            description=str(raw.get("description", "")),
            author=str(raw.get("author", "")),
            repo=str(raw.get("repo", "")),
        )

    @staticmethod
    def _parse_hook(raw: dict[str, Any]) -> HookEntry:
        return HookEntry(
            name=str(raw.get("name", "")),
            script=str(raw.get("script", "")),
            description=str(raw.get("description", "")),
            enabled=bool(raw.get("enabled", True)),
            fail_fast=bool(raw.get("fail_fast", True)),
        )
