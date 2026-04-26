"""Tests for the sls encrypted cache read/write pipeline."""

from __future__ import annotations

import pytest

from sls.core.cache import CacheReader, CacheWriter, _extract_super_secret
from sls.crypto.dayhash import DerivedKeys
from sls.crypto.keys import generate_secret


def _make_keys(suffix: str = "") -> DerivedKeys:
    """Create a deterministic DerivedKeys for testing."""
    return DerivedKeys(
        systemhash=b"\xaa" * 32,
        session_nonce=b"\xbb" * 32,
        gh_auth_token=f"token{suffix}",
        compiletimehash=b"\xcc" * 32,
        day="1",
        month="1",
        year="2026",
    )


class TestCacheWriterReader:
    """Integration tests for CacheWriter + CacheReader."""

    def test_roundtrip(self, tmp_cache_dir: str, sample_secrets: dict[str, str]) -> None:
        """Write then read returns the original secrets."""
        dk = _make_keys()
        writer = CacheWriter(dk.dayhash_b64, dk.dayhash_cbc, dk.decr_key, base_dir=tmp_cache_dir)
        writer.write(sample_secrets)

        reader = CacheReader(dk.dayhash_b64, dk.dayhash_cbc, dk.decr_key, base_dir=tmp_cache_dir)
        result = reader.read()
        assert result == sample_secrets

    def test_wrong_decr_key_raises(self, tmp_cache_dir: str) -> None:
        """Reading with wrong decr_key raises CacheError."""
        from sls.core.cache import CacheError

        dk = _make_keys()
        writer = CacheWriter(dk.dayhash_b64, dk.dayhash_cbc, dk.decr_key, base_dir=tmp_cache_dir)
        writer.write({"KEY": "value"})

        wrong_key = generate_secret(32)
        reader = CacheReader(dk.dayhash_b64, dk.dayhash_cbc, wrong_key, base_dir=tmp_cache_dir)
        with pytest.raises(CacheError):
            reader.read()

    def test_missing_cache_raises(self, tmp_cache_dir: str) -> None:
        """Reading from an empty directory raises CacheError."""
        from sls.core.cache import CacheError

        dk = _make_keys()
        reader = CacheReader(dk.dayhash_b64, dk.dayhash_cbc, dk.decr_key, base_dir=tmp_cache_dir)
        with pytest.raises(CacheError, match="not found"):
            reader.read()

    def test_cache_files_are_not_plaintext(
        self, tmp_cache_dir: str, sample_secrets: dict[str, str]
    ) -> None:
        """Cache files do not contain the secret values in plaintext."""
        import os

        dk = _make_keys()
        writer = CacheWriter(dk.dayhash_b64, dk.dayhash_cbc, dk.decr_key, base_dir=tmp_cache_dir)
        writer.write(sample_secrets)

        for root, _, files in os.walk(tmp_cache_dir):
            for fname in files:
                filepath = os.path.join(root, fname)
                with open(filepath, "rb") as f:
                    raw = f.read()
                for val in sample_secrets.values():
                    assert val.encode() not in raw, f"Secret found in plaintext in {fname}"

    def test_empty_secrets(self, tmp_cache_dir: str) -> None:
        """Writing and reading an empty secrets dict works."""
        dk = _make_keys()
        writer = CacheWriter(dk.dayhash_b64, dk.dayhash_cbc, dk.decr_key, base_dir=tmp_cache_dir)
        writer.write({})
        reader = CacheReader(dk.dayhash_b64, dk.dayhash_cbc, dk.decr_key, base_dir=tmp_cache_dir)
        assert reader.read() == {}

    def test_unicode_secret_values(self, tmp_cache_dir: str) -> None:
        """Unicode values are preserved through the cache roundtrip."""
        dk = _make_keys()
        secrets = {"UNICODE_KEY": "café ☕ 日本語"}
        writer = CacheWriter(dk.dayhash_b64, dk.dayhash_cbc, dk.decr_key, base_dir=tmp_cache_dir)
        writer.write(secrets)
        reader = CacheReader(dk.dayhash_b64, dk.dayhash_cbc, dk.decr_key, base_dir=tmp_cache_dir)
        assert reader.read() == secrets

    def test_multiple_writes_with_different_keys(self, tmp_cache_dir: str) -> None:
        """Multiple writes with different keys produce independently readable caches."""
        dk1 = _make_keys("1")
        dk2 = DerivedKeys(
            systemhash=b"\xdd" * 32,
            session_nonce=b"\xee" * 32,
            gh_auth_token="token2",  # noqa: S106
            compiletimehash=b"\xff" * 32,
            day="2",
            month="2",
            year="2026",
        )

        CacheWriter(dk1.dayhash_b64, dk1.dayhash_cbc, dk1.decr_key, base_dir=tmp_cache_dir).write(
            {"K1": "V1"}
        )
        CacheWriter(dk2.dayhash_b64, dk2.dayhash_cbc, dk2.decr_key, base_dir=tmp_cache_dir).write(
            {"K2": "V2"}
        )

        r1 = CacheReader(dk1.dayhash_b64, dk1.dayhash_cbc, dk1.decr_key, base_dir=tmp_cache_dir)
        r2 = CacheReader(dk2.dayhash_b64, dk2.dayhash_cbc, dk2.decr_key, base_dir=tmp_cache_dir)
        assert r1.read() == {"K1": "V1"}
        assert r2.read() == {"K2": "V2"}


class TestExtractSuperSecret:
    """Tests for the _extract_super_secret helper."""

    def test_extracts_correctly(self) -> None:
        """Correctly extracts the hex secret from the template."""
        source = '_super_secret_hex = "aabbccdd"\n'
        secret = _extract_super_secret(source)
        assert secret == bytes.fromhex("aabbccdd")

    def test_missing_marker_raises(self) -> None:
        """Missing marker raises CacheError."""
        from sls.core.cache import CacheError

        with pytest.raises(CacheError, match="Cannot locate super_secret"):
            _extract_super_secret("no marker here")

    def test_invalid_hex_raises(self) -> None:
        """Non-hex content raises CacheError."""
        from sls.core.cache import CacheError

        source = '_super_secret_hex = "not-hex!"\n'
        with pytest.raises(CacheError, match="Invalid super_secret hex literal"):
            _extract_super_secret(source)
