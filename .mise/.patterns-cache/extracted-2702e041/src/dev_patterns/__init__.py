"""dev-patterns — central patterns library for orchestras repositories.

Provides:
    - Git hook management via declarative TOML manifests
    - Patterns channel subscription and sync (mise tasks + git hooks)
    - Version-spec resolution supporting both old .githooks-version format
      and new PATTERNS_* env var / mise.toml approach
"""

from dev_patterns.version import __version__

__all__ = ["__version__"]
