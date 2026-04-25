"""Session management — orchestrates key derivation, keychain I/O, and cache I/O."""

from __future__ import annotations

import time

from sls.core.config import CACHE_TTL_SECONDS
from sls.crypto.dayhash import DerivedKeys
from sls.crypto.keys import generate_secret
from sls.keychain.store import KeychainStore


class SessionError(Exception):
    """Raised when the session state is invalid or expired."""


class Session:
    """Manage sls session state and derive key material for cache operations.

    A session is created fresh on every ``acquiesce`` or ``rotate`` call and
    validated on every ``push`` call.

    Args:
        keychain: Keychain store to read/write session entries.
        ttl: Cache time-to-live in seconds (default: 28 800).
    """

    def __init__(
        self,
        keychain: KeychainStore | None = None,
        ttl: int = CACHE_TTL_SECONDS,
    ) -> None:
        """Initialise the session manager.

        Args:
            keychain: Keychain store instance (creates a default one if None).
            ttl: TTL in seconds.
        """
        self._keychain = keychain or KeychainStore()
        self._ttl = ttl

    def new_session(self) -> float:
        """Generate fresh key material and record a new session start.

        Writes three new entries to the Keychain:
        - ``kpsc.systemhash`` — 32 random bytes
        - ``kpsc.session_nonce`` — 32 random bytes
        - ``kpsc.session_start`` — current epoch seconds

        Returns:
            The session start epoch timestamp.
        """
        systemhash = generate_secret(32)
        session_nonce = generate_secret(32)
        session_start = time.time()

        self._keychain.set_systemhash(systemhash)
        self._keychain.set_session_nonce(session_nonce)
        self._keychain.set_session_start(session_start)

        return session_start

    def check_valid(self) -> tuple[bool, float]:
        """Check whether the current session is still valid.

        Returns:
            Tuple of ``(is_valid, ttl_remaining_seconds)``.
            If no session exists ``is_valid`` is False and remaining is 0.
        """
        session_start = self._keychain.get_session_start()
        if session_start is None:
            return False, 0.0
        elapsed = time.time() - session_start
        remaining = self._ttl - elapsed
        return remaining > 0, max(0.0, remaining)

    def derive_keys(
        self,
        gh_auth_token: str,
        compiletimehash: bytes,
    ) -> DerivedKeys:
        """Read session key material from Keychain and derive all cache keys.

        Args:
            gh_auth_token: GitHub OAuth token string.
            compiletimehash: 32-byte value fetched from the private repo.

        Returns:
            :class:`~sls.crypto.dayhash.DerivedKeys` containing all derived values.

        Raises:
            SessionError: If Keychain entries are missing.
        """
        systemhash = self._keychain.get_systemhash()
        session_nonce = self._keychain.get_session_nonce()

        if systemhash is None:
            raise SessionError("Keychain entry 'kpsc.systemhash' is missing. Run 'sls acquiesce'.")
        if session_nonce is None:
            raise SessionError(
                "Keychain entry 'kpsc.session_nonce' is missing. Run 'sls acquiesce'."
            )

        return DerivedKeys(
            systemhash=systemhash,
            session_nonce=session_nonce,
            gh_auth_token=gh_auth_token,
            compiletimehash=compiletimehash,
        )
