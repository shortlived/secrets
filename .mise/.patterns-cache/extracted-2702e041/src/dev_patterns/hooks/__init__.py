"""Git hook management via declarative ``githooks.toml`` manifests.

Provides:
    :class:`HookManifest`  — parsed representation of a ``githooks.toml`` file.
    :class:`HookEntry`     — individual hook declaration from the manifest.
    :class:`HookInstaller` — installs / uninstalls hooks into a project.
"""

from dev_patterns.hooks.installer import HookInstaller
from dev_patterns.hooks.manifest import HookEntry, HookManifest

__all__ = ["HookEntry", "HookInstaller", "HookManifest"]
