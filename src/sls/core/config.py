"""Non-secret runtime constants for the sls cache system."""

from __future__ import annotations

# Cache TTL in seconds (8 hours)
CACHE_TTL_SECONDS: int = 28_800

# Keychain service name for all kpsc entries
KEYCHAIN_SERVICE: str = "kpsc"

# Keychain entry names
KEYCHAIN_SYSTEMHASH: str = "kpsc.systemhash"
KEYCHAIN_SESSION_NONCE: str = "kpsc.session_nonce"
KEYCHAIN_SESSION_START: str = "kpsc.session_start"

# GitHub repository containing the compiletimehash at runtime
COMPILETIMEHASH_REPO: str = "softdist/kpsc-secrets"
COMPILETIMEHASH_FILE: str = "compiletimehash.txt"

# Base /tmp directory for cache files
CACHE_BASE_DIR: str = "/tmp"  # noqa: S108

# Cache file names within their respective /tmp subdirectories
DECR_FILENAME: str = "decr.py"
DICT_FILENAME: str = "dict.py"

# Permissions for cache directories (owner read/write/execute only)
CACHE_DIR_MODE: int = 0o700
