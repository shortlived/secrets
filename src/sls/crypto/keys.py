"""Key material assembly helpers — generating and zeroing secret bytes."""

from __future__ import annotations

import ctypes
import os


def generate_secret(length: int = 32) -> bytes:
    """Generate *length* cryptographically-secure random bytes.

    Args:
        length: Number of random bytes to generate.  Defaults to 32.

    Returns:
        Random bytes of the requested length.
    """
    return os.urandom(length)


def zero_bytes(data: bytearray) -> None:
    """Overwrite *data* in place with zeros.

    Works on :class:`bytearray` objects.  For ``bytes`` objects (which are
    immutable) callers must first copy to a ``bytearray``, zero that, then
    discard the original reference.

    Args:
        data: Mutable byte buffer to zero out.
    """
    ctypes.memset(ctypes.addressof((ctypes.c_char * len(data)).from_buffer(data)), 0, len(data))


def secret_to_hex(data: bytes) -> str:
    """Encode *data* as a lowercase hex string.

    Args:
        data: Raw bytes to encode.

    Returns:
        Lowercase hex string representation.
    """
    return data.hex()


def hex_to_secret(hex_str: str) -> bytes:
    """Decode a hex string produced by :func:`secret_to_hex`.

    Args:
        hex_str: Lowercase hex string.

    Returns:
        Raw bytes.
    """
    return bytes.fromhex(hex_str)
