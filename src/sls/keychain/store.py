"""Keychain storage backend for sls session state.

On macOS the ``keyring`` library delegates to the system Keychain via the
``SecretService`` or ``macOS Keychain`` backend automatically.  On Linux
(e.g., CI) it falls back to the ``SecretService`` (libsecret / GNOME Keyring)
or an encrypted file backend.

All three session entries live under the service name ``kpsc``:

- ``kpsc.systemhash``    — 32 random bytes (hex-encoded)
- ``kpsc.session_nonce`` — 32 random bytes (hex-encoded)
- ``kpsc.session_start`` — epoch seconds (decimal string)
"""

from __future__ import annotations

from sls.core.config import (
    KEYCHAIN_SERVICE,
    KEYCHAIN_SESSION_NONCE,
    KEYCHAIN_SESSION_START,
    KEYCHAIN_SYSTEMHASH,
)


class KeychainError(Exception):
    """Raised when a Keychain read or write operation fails."""


class KeychainStore:
    """Read/write session key material from/to the system Keychain.

    Uses the ``keyring`` library which maps to the OS-native credential store
    (macOS Keychain, Windows Credential Manager, Linux SecretService).
    """

    def __init__(self, service: str = KEYCHAIN_SERVICE) -> None:
        """Initialise the store with the given service name.

        Args:
            service: Service name used for all Keychain entries.
        """
        self._service = service

    def _get(self, key: str) -> str | None:
        """Retrieve a raw string value from the Keychain.

        Args:
            key: Keychain entry name.

        Returns:
            The stored string, or None if the entry does not exist.
        """
        import keyring

        return keyring.get_password(self._service, key)

    def _set(self, key: str, value: str) -> None:
        """Write a string value to the Keychain.

        Args:
            key: Keychain entry name.
            value: Value to store.

        Raises:
            KeychainError: If the write operation fails.
        """
        import keyring

        try:
            keyring.set_password(self._service, key, value)
        except Exception as exc:
            raise KeychainError(f"Failed to write Keychain entry '{key}': {exc}") from exc

    def get_systemhash(self) -> bytes | None:
        """Read the stored systemhash.

        Returns:
            32 bytes, or None if not present.
        """
        value = self._get(KEYCHAIN_SYSTEMHASH)
        if value is None:
            return None
        return bytes.fromhex(value)

    def set_systemhash(self, data: bytes) -> None:
        """Write the systemhash.

        Args:
            data: 32 random bytes.
        """
        self._set(KEYCHAIN_SYSTEMHASH, data.hex())

    def get_session_nonce(self) -> bytes | None:
        """Read the stored session_nonce.

        Returns:
            32 bytes, or None if not present.
        """
        value = self._get(KEYCHAIN_SESSION_NONCE)
        if value is None:
            return None
        return bytes.fromhex(value)

    def set_session_nonce(self, data: bytes) -> None:
        """Write the session_nonce.

        Args:
            data: 32 random bytes.
        """
        self._set(KEYCHAIN_SESSION_NONCE, data.hex())

    def get_session_start(self) -> float | None:
        """Read the stored session_start epoch timestamp.

        Returns:
            Float epoch seconds, or None if not present.
        """
        value = self._get(KEYCHAIN_SESSION_START)
        if value is None:
            return None
        return float(value)

    def set_session_start(self, epoch_seconds: float) -> None:
        """Write the session_start timestamp.

        Args:
            epoch_seconds: Epoch timestamp as a float.
        """
        self._set(KEYCHAIN_SESSION_START, str(epoch_seconds))
