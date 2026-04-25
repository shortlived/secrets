"""Tests for sls keychain store abstraction."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from sls.keychain.store import KeychainError, KeychainStore


class TestKeychainStore:
    """Tests for KeychainStore using a mock keyring backend."""

    def _make_store(self) -> tuple[KeychainStore, dict[str, str]]:
        """Return a KeychainStore backed by an in-memory dict."""
        db: dict[str, str] = {}

        def mock_get(service: str, username: str) -> str | None:
            return db.get(f"{service}:{username}")

        def mock_set(service: str, username: str, password: str) -> None:
            db[f"{service}:{username}"] = password

        store = KeychainStore()
        with (
            patch("keyring.get_password", side_effect=mock_get),
            patch("keyring.set_password", side_effect=mock_set),
        ):
            return store, db

    def test_systemhash_roundtrip(self) -> None:
        """set_systemhash / get_systemhash roundtrip."""
        db: dict[str, str] = {}

        def mock_get(service: str, username: str) -> str | None:
            return db.get(f"{service}:{username}")

        def mock_set(service: str, username: str, password: str) -> None:
            db[f"{service}:{username}"] = password

        store = KeychainStore()
        data = b"\xaa" * 32
        with (
            patch("keyring.set_password", side_effect=mock_set),
            patch("keyring.get_password", side_effect=mock_get),
        ):
            store.set_systemhash(data)
            result = store.get_systemhash()
        assert result == data

    def test_session_nonce_roundtrip(self) -> None:
        """set_session_nonce / get_session_nonce roundtrip."""
        db: dict[str, str] = {}

        def mock_get(service: str, username: str) -> str | None:
            return db.get(f"{service}:{username}")

        def mock_set(service: str, username: str, password: str) -> None:
            db[f"{service}:{username}"] = password

        store = KeychainStore()
        data = b"\xbb" * 32
        with (
            patch("keyring.set_password", side_effect=mock_set),
            patch("keyring.get_password", side_effect=mock_get),
        ):
            store.set_session_nonce(data)
            result = store.get_session_nonce()
        assert result == data

    def test_session_start_roundtrip(self) -> None:
        """set_session_start / get_session_start roundtrip."""
        db: dict[str, str] = {}

        def mock_get(service: str, username: str) -> str | None:
            return db.get(f"{service}:{username}")

        def mock_set(service: str, username: str, password: str) -> None:
            db[f"{service}:{username}"] = password

        store = KeychainStore()
        ts = 1_700_000_000.5
        with (
            patch("keyring.set_password", side_effect=mock_set),
            patch("keyring.get_password", side_effect=mock_get),
        ):
            store.set_session_start(ts)
            result = store.get_session_start()
        assert result == pytest.approx(ts)

    def test_missing_entry_returns_none(self) -> None:
        """Getting a missing entry returns None."""
        store = KeychainStore()
        with patch("keyring.get_password", return_value=None):
            assert store.get_systemhash() is None
            assert store.get_session_nonce() is None
            assert store.get_session_start() is None

    def test_set_raises_keychain_error_on_failure(self) -> None:
        """set_systemhash raises KeychainError when keyring raises."""
        store = KeychainStore()
        with (
            patch("keyring.set_password", side_effect=RuntimeError("keychain locked")),
            pytest.raises(KeychainError, match="Failed to write Keychain entry"),
        ):
            store.set_systemhash(b"\x00" * 32)
