"""Dayhash key-derivation logic for the sls cache system.

The dayhash_input is the root of all key material:

    dayhash_input = CONCAT(
        UTF8(day), UTF8(month), UTF8(year),
        systemhash,      # 32 random bytes from Keychain
        session_nonce,   # 32 random bytes from Keychain
        gh_auth_token,   # bytes of the GitHub OAuth token string
        compiletimehash  # 32 bytes from the private runtime-fetch repo
    )

From dayhash_input we derive:

    dayhashB64  = Base64(dayhash_input)        → /tmp directory name for decr.py
    dayhashCBC  = AES-256-GCM(dayhash_input, key=compiletimehash)
                                               → /tmp directory name for dict.py
    decr_key    = AES-256-GCM(
                    data = dayhashCBC || dayhashB64 || compiletimehash,
                    key  = compiletimehash
                  )                            → key for encrypting decr.py
"""

from __future__ import annotations

import base64
import datetime


def _today_parts() -> tuple[str, str, str]:
    """Return (day, month, year) strings for today (UTC)."""
    today = datetime.datetime.now(tz=datetime.UTC)
    return str(today.day), str(today.month), str(today.year)


def build_dayhash_input(  # noqa: PLR0913
    systemhash: bytes,
    session_nonce: bytes,
    gh_auth_token: str,
    compiletimehash: bytes,
    *,
    day: str | None = None,
    month: str | None = None,
    year: str | None = None,
) -> bytes:
    """Assemble the raw dayhash_input bytes.

    Args:
        systemhash: 32 random bytes stored in Keychain.
        session_nonce: 32 random bytes stored in Keychain.
        gh_auth_token: GitHub OAuth token string.
        compiletimehash: 32-byte value fetched from the private secrets repo.
        day: Override day string (for testing).
        month: Override month string (for testing).
        year: Override year string (for testing).

    Returns:
        Concatenated raw bytes used as the derivation root.
    """
    d, m, y = _today_parts()
    if day is not None:
        d = day
    if month is not None:
        m = month
    if year is not None:
        y = year

    return (
        d.encode()
        + m.encode()
        + y.encode()
        + systemhash
        + session_nonce
        + gh_auth_token.encode()
        + compiletimehash
    )


def derive_dayhash_b64(dayhash_input: bytes) -> str:
    """Derive the Base64-encoded directory name for decr.py.

    Args:
        dayhash_input: Raw bytes from :func:`build_dayhash_input`.

    Returns:
        URL-safe base64 string (no padding) used as the directory name.
    """
    return base64.urlsafe_b64encode(dayhash_input).rstrip(b"=").decode()


def derive_dayhash_cbc(dayhash_input: bytes, compiletimehash: bytes) -> str:
    """Derive the AES-GCM encrypted directory name for dict.py.

    This uses compiletimehash as the encryption key.  A deterministic nonce is
    derived from the inputs (first 12 bytes of SHA-256 of the input) so that
    the same inputs always produce the same directory name — required so that
    ``push`` can locate the directory created by ``acquiesce``.

    Args:
        dayhash_input: Raw bytes from :func:`build_dayhash_input`.
        compiletimehash: 32-byte key.

    Returns:
        URL-safe base64 string used as the /tmp sub-directory name for dict.py.
    """
    import hashlib

    deterministic_nonce = hashlib.sha256(dayhash_input + compiletimehash + b"cbc").digest()[:12]
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    aesgcm = AESGCM(compiletimehash)
    ciphertext = aesgcm.encrypt(deterministic_nonce, dayhash_input, None)
    blob = deterministic_nonce + ciphertext
    return base64.urlsafe_b64encode(blob).rstrip(b"=").decode()


def derive_decr_key(
    dayhash_b64: str,
    dayhash_cbc: str,
    compiletimehash: bytes,
) -> bytes:
    """Derive the key used to encrypt/decrypt decr.py.

    Uses HKDF-SHA-256 to deterministically derive a 32-byte key from the
    combination of dayhashCBC, dayhashB64, and compiletimehash.  This is
    deterministic so that ``push`` can derive the same key as ``acquiesce``
    without storing anything extra.

    Args:
        dayhash_b64: String from :func:`derive_dayhash_b64`.
        dayhash_cbc: String from :func:`derive_dayhash_cbc`.
        compiletimehash: 32-byte key material.

    Returns:
        32-byte key for AES-256-GCM encryption of decr.py.
    """
    import hashlib
    import hmac

    ikm = dayhash_cbc.encode() + dayhash_b64.encode() + compiletimehash
    return hmac.new(compiletimehash, ikm + b"decr_key", hashlib.sha256).digest()


class DerivedKeys:
    """Container for all derived key-material values for one session.

    Attributes:
        dayhash_input: Raw concatenated input bytes.
        dayhash_b64: Base64 directory name for decr.py.
        dayhash_cbc: AES-GCM encrypted directory name for dict.py.
        decr_key: 32-byte key to encrypt/decrypt decr.py.
    """

    def __init__(  # noqa: PLR0913
        self,
        systemhash: bytes,
        session_nonce: bytes,
        gh_auth_token: str,
        compiletimehash: bytes,
        *,
        day: str | None = None,
        month: str | None = None,
        year: str | None = None,
    ) -> None:
        """Derive all session keys from the provided key material.

        Args:
            systemhash: 32 random bytes stored in Keychain.
            session_nonce: 32 random bytes stored in Keychain.
            gh_auth_token: GitHub OAuth token string.
            compiletimehash: 32-byte value fetched from the private secrets repo.
            day: Override day string (for testing).
            month: Override month string (for testing).
            year: Override year string (for testing).
        """
        self.dayhash_input = build_dayhash_input(
            systemhash,
            session_nonce,
            gh_auth_token,
            compiletimehash,
            day=day,
            month=month,
            year=year,
        )
        self.dayhash_b64 = derive_dayhash_b64(self.dayhash_input)
        self.dayhash_cbc = derive_dayhash_cbc(self.dayhash_input, compiletimehash)
        self.decr_key = derive_decr_key(self.dayhash_b64, self.dayhash_cbc, compiletimehash)
