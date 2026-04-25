"""Tests for the GitHub compiletimehash fetcher."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from sls.github.compiletimehash import CompileTimeHashError, fetch_compiletimehash


class TestFetchCompileTimeHash:
    """Tests for fetch_compiletimehash."""

    def test_env_variable_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """SLS_COMPILETIMEHASH env var returns its hex value without network call."""
        fake_hash = "ab" * 32
        monkeypatch.setenv("SLS_COMPILETIMEHASH", fake_hash)
        result = fetch_compiletimehash()
        assert result == bytes.fromhex(fake_hash)

    def test_env_variable_invalid_hex_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Invalid hex in SLS_COMPILETIMEHASH raises CompileTimeHashError."""
        monkeypatch.setenv("SLS_COMPILETIMEHASH", "not-hex!")
        with pytest.raises(CompileTimeHashError, match="not valid hex"):
            fetch_compiletimehash()

    def test_env_variable_takes_priority(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Env variable is used even if gh CLI is not available."""
        fake_hash = "cc" * 32
        monkeypatch.setenv("SLS_COMPILETIMEHASH", fake_hash)
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = fetch_compiletimehash()
        assert result == bytes.fromhex(fake_hash)

    def test_returns_bytes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Result is always bytes."""
        monkeypatch.setenv("SLS_COMPILETIMEHASH", "ff" * 32)
        result = fetch_compiletimehash()
        assert isinstance(result, bytes)
        assert len(result) == 32
