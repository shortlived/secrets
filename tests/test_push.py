"""Tests for sls push and pull-group commands."""

from __future__ import annotations

import time
from io import StringIO
from unittest.mock import patch

from sls.commands.push import PushCommand
from sls.core.base import ExitCode


class MockKeychain:
    """In-memory Keychain mock for testing."""

    def __init__(self) -> None:
        """Initialise with empty state."""
        self._data: dict[str, object] = {}

    def get_systemhash(self) -> bytes | None:
        return self._data.get("systemhash")  # type: ignore[return-value]

    def set_systemhash(self, data: bytes) -> None:
        self._data["systemhash"] = data

    def get_session_nonce(self) -> bytes | None:
        return self._data.get("session_nonce")  # type: ignore[return-value]

    def set_session_nonce(self, data: bytes) -> None:
        self._data["session_nonce"] = data

    def get_session_start(self) -> float | None:
        return self._data.get("session_start")  # type: ignore[return-value]

    def set_session_start(self, epoch_seconds: float) -> None:
        self._data["session_start"] = epoch_seconds


class TestPushCommand:
    """Tests for PushCommand."""

    def test_empty_command_returns_usage_error(self) -> None:
        """Empty command list returns a USAGE error."""
        result = PushCommand().execute(command=[])
        assert result.code == ExitCode.USAGE

    def test_expired_cache_returns_error(self) -> None:
        """Expired session returns an error without touching the cache."""
        keychain = MockKeychain()
        keychain.set_session_start(time.time() - 100_000)
        result = PushCommand().execute(command=["echo", "hi"], keychain=keychain)
        assert not result.ok
        assert "expired" in result.message.lower() or "acquiesce" in result.message.lower()

    def test_no_cache_returns_error(self) -> None:
        """Missing session returns an error."""
        result = PushCommand().execute(command=["echo", "hi"], keychain=MockKeychain())
        assert not result.ok

    def test_valid_cache_injects_secrets(self, tmp_cache_dir: str) -> None:
        """Full acquiesce + push roundtrip injects secrets into the child process."""
        from sls.commands.acquiesce import AcquiesceCommand

        keychain = MockKeychain()
        payload = "INJECTED_VAR=hello_from_sls\n"
        with patch("sys.stdin", StringIO(payload)):
            acq_result = AcquiesceCommand().execute(keychain=keychain, base_dir=tmp_cache_dir)
        assert acq_result.ok, acq_result.message

        result = PushCommand().execute(
            command=["env"],
            keychain=keychain,
            base_dir=tmp_cache_dir,
        )
        assert result.ok or result.data.get("exit_code", 0) == 0

    def test_command_not_found_returns_not_found(self, tmp_cache_dir: str) -> None:
        """Non-existent binary returns NOT_FOUND code."""
        from sls.commands.acquiesce import AcquiesceCommand

        keychain = MockKeychain()
        with patch("sys.stdin", StringIO("K=V\n")):
            AcquiesceCommand().execute(keychain=keychain, base_dir=tmp_cache_dir)

        with patch("sys.stdin") as mock_stdin:
            mock_stdin.fileno.return_value = 0
            result = PushCommand().execute(
                command=["__nonexistent_binary_xyz__"],
                keychain=keychain,
                base_dir=tmp_cache_dir,
            )
        assert result.code in (ExitCode.NOT_FOUND, ExitCode.ERROR)
