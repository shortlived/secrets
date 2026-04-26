"""Patterns sync engine — downloads and applies channel files from dev-patterns.

Supports:
    - Syncing by commit hash (preferred, no releases required)
    - Syncing from a GitHub Release tarball (supports old-style .githooks-version)
    - Skip-if-current check via .patterns-hash file
"""

from dev_patterns.sync.client import GitHubClient
from dev_patterns.sync.engine import SyncEngine, SyncResult

__all__ = ["GitHubClient", "SyncEngine", "SyncResult"]
