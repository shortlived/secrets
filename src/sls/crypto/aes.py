"""AES-256-GCM authenticated encryption/decryption wrappers.

All operations prepend the 12-byte random nonce to the ciphertext so that
callers never need to manage nonce storage separately. On decryption the
first 12 bytes are extracted as the nonce automatically.

The GCM authentication tag (16 bytes) is appended by the cryptography
library and verified on decryption, preventing bit-flipping attacks.
"""

from __future__ import annotations

import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class DecryptionError(Exception):
    """Raised when AES-GCM decryption fails (bad key, tampered ciphertext)."""


_NONCE_LENGTH = 12
_KEY_LENGTH = 32  # AES-256


def _validate_key(key: bytes) -> None:
    if len(key) != _KEY_LENGTH:
        raise ValueError(f"AES-256 key must be exactly {_KEY_LENGTH} bytes, got {len(key)}")


def encrypt(plaintext: bytes, key: bytes) -> bytes:
    """Encrypt *plaintext* with AES-256-GCM using *key*.

    A fresh 12-byte nonce is generated for every call and prepended to the
    returned blob.  The 16-byte GCM authentication tag is appended by the
    underlying library.

    Layout of returned bytes::

        [12-byte nonce][ciphertext][16-byte GCM tag]

    Args:
        plaintext: Data to encrypt.
        key: 32-byte AES-256 key.

    Returns:
        Bytes containing nonce + ciphertext + tag.

    Raises:
        ValueError: If *key* is not 32 bytes.
    """
    _validate_key(key)
    nonce = os.urandom(_NONCE_LENGTH)
    aesgcm = AESGCM(key)
    ciphertext_and_tag = aesgcm.encrypt(nonce, plaintext, None)
    return nonce + ciphertext_and_tag


def decrypt(blob: bytes, key: bytes) -> bytes:
    """Decrypt an AES-256-GCM blob produced by :func:`encrypt`.

    Extracts the nonce from the first 12 bytes, decrypts and authenticates
    the remaining payload.

    Args:
        blob: Bytes in the format ``[nonce][ciphertext][tag]``.
        key: 32-byte AES-256 key.

    Returns:
        Decrypted plaintext bytes.

    Raises:
        ValueError: If *key* is not 32 bytes or the blob is too short.
        DecryptionError: If authentication fails (wrong key or tampered data).
    """
    _validate_key(key)
    if len(blob) < _NONCE_LENGTH + 16:
        raise ValueError("Ciphertext blob is too short to contain a nonce and GCM tag")
    nonce = blob[:_NONCE_LENGTH]
    payload = blob[_NONCE_LENGTH:]
    aesgcm = AESGCM(key)
    try:
        return aesgcm.decrypt(nonce, payload, None)
    except InvalidTag as exc:
        raise DecryptionError("AES-GCM authentication failed — wrong key or tampered data") from exc
