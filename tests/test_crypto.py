"""Tests for sls cryptographic primitives."""

from __future__ import annotations

import pytest

from sls.crypto.aes import DecryptionError, decrypt, encrypt
from sls.crypto.dayhash import (
    DerivedKeys,
    build_dayhash_input,
    derive_dayhash_b64,
    derive_dayhash_cbc,
    derive_decr_key,
)
from sls.crypto.keys import generate_secret, hex_to_secret, secret_to_hex, zero_bytes


class TestAesGcm:
    """Tests for AES-256-GCM encrypt/decrypt."""

    def test_roundtrip(self) -> None:
        """Encrypt then decrypt returns original plaintext."""
        key = generate_secret(32)
        plaintext = b"hello, world!"
        ciphertext = encrypt(plaintext, key)
        assert decrypt(ciphertext, key) == plaintext

    def test_different_ciphertexts_same_plaintext(self) -> None:
        """Two encryptions of the same plaintext produce different ciphertext (nonce)."""
        key = generate_secret(32)
        plaintext = b"same content"
        c1 = encrypt(plaintext, key)
        c2 = encrypt(plaintext, key)
        assert c1 != c2

    def test_wrong_key_raises_decryption_error(self) -> None:
        """Decrypting with a wrong key raises DecryptionError."""
        key = generate_secret(32)
        wrong_key = generate_secret(32)
        ciphertext = encrypt(b"secret", key)
        with pytest.raises(DecryptionError):
            decrypt(ciphertext, wrong_key)

    def test_tampered_ciphertext_raises(self) -> None:
        """Tampered ciphertext raises DecryptionError."""
        key = generate_secret(32)
        ciphertext = bytearray(encrypt(b"secret", key))
        ciphertext[-1] ^= 0xFF
        with pytest.raises(DecryptionError):
            decrypt(bytes(ciphertext), key)

    def test_wrong_key_length_raises_value_error(self) -> None:
        """Key that is not 32 bytes raises ValueError."""
        with pytest.raises(ValueError, match="32 bytes"):
            encrypt(b"data", b"short-key")

    def test_too_short_blob_raises_value_error(self) -> None:
        """Blob shorter than nonce+tag raises ValueError."""
        key = generate_secret(32)
        with pytest.raises(ValueError, match="too short"):
            decrypt(b"tooshort", key)

    def test_empty_plaintext(self) -> None:
        """Encrypting empty bytes works."""
        key = generate_secret(32)
        ciphertext = encrypt(b"", key)
        assert decrypt(ciphertext, key) == b""

    def test_large_payload(self) -> None:
        """Encryption works on a large payload."""
        key = generate_secret(32)
        plaintext = b"X" * 100_000
        assert decrypt(encrypt(plaintext, key), key) == plaintext


class TestDayhash:
    """Tests for dayhash key derivation."""

    _compiletimehash = bytes.fromhex("a" * 64)
    _systemhash = generate_secret(32)
    _session_nonce = generate_secret(32)

    def _make_input(self) -> bytes:
        return build_dayhash_input(
            self._systemhash,
            self._session_nonce,
            "gh-token",
            self._compiletimehash,
            day="15",
            month="4",
            year="2026",
        )

    def test_dayhash_input_is_bytes(self) -> None:
        """build_dayhash_input returns bytes."""
        result = self._make_input()
        assert isinstance(result, bytes)

    def test_dayhash_input_contains_date(self) -> None:
        """dayhash_input contains the date strings."""
        result = self._make_input()
        assert b"15" in result
        assert b"4" in result
        assert b"2026" in result

    def test_dayhash_b64_is_string(self) -> None:
        """derive_dayhash_b64 returns a non-empty string."""
        h = derive_dayhash_b64(self._make_input())
        assert isinstance(h, str)
        assert len(h) > 0

    def test_dayhash_cbc_is_string(self) -> None:
        """derive_dayhash_cbc returns a non-empty string."""
        h = derive_dayhash_cbc(self._make_input(), self._compiletimehash)
        assert isinstance(h, str)
        assert len(h) > 0

    def test_different_nonces_produce_different_b64(self) -> None:
        """Different session nonces produce different dayhashB64 values."""
        inp1 = build_dayhash_input(
            self._systemhash,
            b"\x01" * 32,
            "token",
            self._compiletimehash,
            day="1",
            month="1",
            year="2026",
        )
        inp2 = build_dayhash_input(
            self._systemhash,
            b"\x02" * 32,
            "token",
            self._compiletimehash,
            day="1",
            month="1",
            year="2026",
        )
        assert derive_dayhash_b64(inp1) != derive_dayhash_b64(inp2)

    def test_decr_key_is_32_bytes(self) -> None:
        """derive_decr_key returns exactly 32 bytes."""
        inp = self._make_input()
        b64 = derive_dayhash_b64(inp)
        cbc = derive_dayhash_cbc(inp, self._compiletimehash)
        key = derive_decr_key(b64, cbc, self._compiletimehash)
        assert isinstance(key, bytes)
        assert len(key) == 32

    def test_derived_keys_container(self) -> None:
        """DerivedKeys produces consistent values."""
        dk = DerivedKeys(
            systemhash=self._systemhash,
            session_nonce=self._session_nonce,
            gh_auth_token="token",  # noqa: S106
            compiletimehash=self._compiletimehash,
            day="1",
            month="1",
            year="2026",
        )
        assert dk.dayhash_b64
        assert dk.dayhash_cbc
        assert len(dk.decr_key) == 32

    def test_deterministic_for_same_inputs(self) -> None:
        """Same inputs produce same derived keys."""
        kwargs = {
            "systemhash": b"\xaa" * 32,
            "session_nonce": b"\xbb" * 32,
            "gh_auth_token": "same-token",
            "compiletimehash": b"\xcc" * 32,
            "day": "1",
            "month": "1",
            "year": "2026",
        }
        dk1 = DerivedKeys(**kwargs)
        dk2 = DerivedKeys(**kwargs)
        assert dk1.dayhash_b64 == dk2.dayhash_b64
        assert dk1.dayhash_cbc == dk2.dayhash_cbc


class TestKeyHelpers:
    """Tests for key generation and hex encoding helpers."""

    def test_generate_secret_default_length(self) -> None:
        """generate_secret produces 32 bytes by default."""
        secret = generate_secret()
        assert len(secret) == 32

    def test_generate_secret_custom_length(self) -> None:
        """generate_secret produces the requested length."""
        secret = generate_secret(16)
        assert len(secret) == 16

    def test_generate_secret_is_random(self) -> None:
        """Two calls produce different values."""
        assert generate_secret() != generate_secret()

    def test_hex_roundtrip(self) -> None:
        """secret_to_hex / hex_to_secret roundtrip."""
        original = generate_secret(32)
        assert hex_to_secret(secret_to_hex(original)) == original

    def test_zero_bytes(self) -> None:
        """zero_bytes overwrites buffer with zeros."""
        buf = bytearray(b"\xff" * 16)
        zero_bytes(buf)
        assert buf == bytearray(16)
