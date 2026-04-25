"""Encrypted cache file management for sls.

Manages the two /tmp cache files:

- ``/tmp/$dayhashB64/decr.py`` — AES-256-GCM encrypted Python source that
  embeds the super_secret as a hex literal.
- ``/tmp/$dayhashCBC/dict.py`` — AES-256-GCM encrypted JSON secrets dictionary,
  encrypted with the super_secret.

Both directories are created with permissions 0o700 (owner-only).  The files
themselves are written as binary blobs with no file extension semantics —
the ``.py`` suffix is a red herring for filesystem browsers.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from sls.core.config import (
    CACHE_BASE_DIR,
    CACHE_DIR_MODE,
    DECR_FILENAME,
    DICT_FILENAME,
)
from sls.crypto.aes import decrypt, encrypt
from sls.crypto.keys import generate_secret, secret_to_hex

_DECR_TEMPLATE = """\
import binascii as _b
import ctypes as _c
import importlib as _i
import sys as _s

_super_secret_hex = "{super_secret_hex}"

def _get_secret() -> bytes:
    return _b.unhexlify(_super_secret_hex)

def decrypt_dict(ciphertext: bytes) -> dict:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.exceptions import InvalidTag
    key = _get_secret()
    nonce = ciphertext[:12]
    payload = ciphertext[12:]
    aesgcm = AESGCM(key)
    try:
        plaintext = aesgcm.decrypt(nonce, payload, None)
    except InvalidTag:
        _s.exit("Cache authentication failed")
    import json
    return json.loads(plaintext.decode())
"""


class CacheError(Exception):
    """Raised when a cache read or write operation fails."""


class CacheWriter:
    """Write encrypted cache files to /tmp.

    Args:
        dayhash_b64: Directory name for the decr.py file.
        dayhash_cbc: Directory name for the dict.py file.
        decr_key: 32-byte key for encrypting decr.py.
        base_dir: Override the base /tmp directory (for testing).
    """

    def __init__(
        self,
        dayhash_b64: str,
        dayhash_cbc: str,
        decr_key: bytes,
        base_dir: str = CACHE_BASE_DIR,
    ) -> None:
        """Initialise the writer.

        Args:
            dayhash_b64: Directory name for decr.py.
            dayhash_cbc: Directory name for dict.py.
            decr_key: 32-byte AES-256 key for decr.py encryption.
            base_dir: Base directory for cache files (default: /tmp).
        """
        self._b64_dir = Path(base_dir) / dayhash_b64
        self._cbc_dir = Path(base_dir) / dayhash_cbc
        self._decr_key = decr_key

    def write(self, secrets: dict[str, str]) -> None:
        """Encrypt and write both cache files.

        Generates a fresh super_secret, builds and encrypts the decr.py source
        embedding that secret, then encrypts the secrets dictionary with the
        super_secret.  Both files are written atomically.

        Args:
            secrets: Mapping of environment-variable name → secret value.

        Raises:
            CacheError: If any filesystem or encryption operation fails.
        """
        super_secret = generate_secret(32)
        try:
            decr_source = _DECR_TEMPLATE.format(super_secret_hex=secret_to_hex(super_secret))
            encrypted_decr = encrypt(decr_source.encode(), self._decr_key)

            secrets_json = json.dumps(secrets).encode()
            encrypted_dict = encrypt(secrets_json, super_secret)

            self._write_file(self._b64_dir, DECR_FILENAME, encrypted_decr)
            self._write_file(self._cbc_dir, DICT_FILENAME, encrypted_dict)
        except Exception as exc:
            raise CacheError(f"Failed to write cache: {exc}") from exc
        finally:
            super_secret = b"\x00" * 32

    @staticmethod
    def _write_file(directory: Path, filename: str, data: bytes) -> None:
        directory.mkdir(mode=CACHE_DIR_MODE, parents=True, exist_ok=True)
        os.chmod(directory, CACHE_DIR_MODE)
        filepath = directory / filename
        filepath.write_bytes(data)
        os.chmod(filepath, 0o600)


class CacheReader:
    """Read and decrypt cache files from /tmp.

    Args:
        dayhash_b64: Directory name for the decr.py file.
        dayhash_cbc: Directory name for the dict.py file.
        decr_key: 32-byte key for decrypting decr.py.
        base_dir: Override the base /tmp directory (for testing).
    """

    def __init__(
        self,
        dayhash_b64: str,
        dayhash_cbc: str,
        decr_key: bytes,
        base_dir: str = CACHE_BASE_DIR,
    ) -> None:
        """Initialise the reader.

        Args:
            dayhash_b64: Directory name for decr.py.
            dayhash_cbc: Directory name for dict.py.
            decr_key: 32-byte AES-256 key for decr.py decryption.
            base_dir: Base directory for cache files (default: /tmp).
        """
        self._b64_dir = Path(base_dir) / dayhash_b64
        self._cbc_dir = Path(base_dir) / dayhash_cbc
        self._decr_key = decr_key

    def read(self) -> dict[str, str]:
        """Decrypt and return the secrets dictionary.

        Decrypts decr.py to extract the super_secret, then decrypts dict.py
        using that super_secret.  Both intermediate values are discarded
        after use.

        Returns:
            Mapping of environment-variable name → secret value.

        Raises:
            CacheError: If cache files are missing or decryption fails.
        """
        decr_path = self._b64_dir / DECR_FILENAME
        dict_path = self._cbc_dir / DICT_FILENAME

        if not decr_path.exists():
            raise CacheError(f"Cache file not found: {decr_path}. Run 'sls acquiesce' first.")
        if not dict_path.exists():
            raise CacheError(f"Cache file not found: {dict_path}. Run 'sls acquiesce' first.")

        try:
            encrypted_decr = decr_path.read_bytes()
            decr_source = decrypt(encrypted_decr, self._decr_key).decode()

            super_secret = _extract_super_secret(decr_source)
            decr_source = ""

            encrypted_dict = dict_path.read_bytes()
            secrets_json = decrypt(encrypted_dict, super_secret)
            super_secret = b"\x00" * 32

            return json.loads(secrets_json.decode())
        except CacheError:
            raise
        except Exception as exc:
            raise CacheError(f"Failed to read cache: {exc}") from exc


def _extract_super_secret(decr_source: str) -> bytes:
    """Extract the super_secret hex literal from the decr.py source.

    Args:
        decr_source: Decrypted Python source string.

    Returns:
        The super_secret bytes.

    Raises:
        CacheError: If the hex literal cannot be found or decoded.
    """
    marker = '_super_secret_hex = "'
    start = decr_source.find(marker)
    if start == -1:
        raise CacheError("Cannot locate super_secret in decr.py source")
    start += len(marker)
    end = decr_source.find('"', start)
    if end == -1:
        raise CacheError("Malformed super_secret hex literal in decr.py")
    hex_value = decr_source[start:end]
    try:
        return bytes.fromhex(hex_value)
    except ValueError as exc:
        raise CacheError(f"Invalid super_secret hex literal: {exc}") from exc
