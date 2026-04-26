"""Tests for sls CLI commands."""

from __future__ import annotations

import time
from io import StringIO
from unittest.mock import patch

import pytest

from sls.commands.acquiesce import AcquiesceCommand, parse_secrets_payload
from sls.commands.rotate import RotateCommand
from sls.commands.status import StatusCommand, _format_hms
from sls.core.base import CommandResult, ExitCode


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


class TestParseSecretsPayload:
    """Tests for the parse_secrets_payload helper."""

    def test_basic_parsing(self) -> None:
        """Simple KEY=VALUE lines are parsed correctly."""
        payload = "FOO=bar\nBAZ=qux\n"
        result = parse_secrets_payload(payload)
        assert result == {"FOO": "bar", "BAZ": "qux"}

    def test_blank_lines_ignored(self) -> None:
        """Blank lines are silently ignored."""
        payload = "\nFOO=bar\n\n"
        assert parse_secrets_payload(payload) == {"FOO": "bar"}

    def test_comment_lines_ignored(self) -> None:
        """Lines starting with # are ignored."""
        payload = "# comment\nFOO=bar\n"
        assert parse_secrets_payload(payload) == {"FOO": "bar"}

    def test_value_with_equals(self) -> None:
        """Values that contain '=' are preserved correctly."""
        payload = "URL=https://example.com?a=1&b=2\n"
        result = parse_secrets_payload(payload)
        assert result["URL"] == "https://example.com?a=1&b=2"

    def test_empty_payload(self) -> None:
        """Empty payload returns empty dict."""
        assert parse_secrets_payload("") == {}

    def test_malformed_line_skipped(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Lines without '=' are skipped with a warning."""
        payload = "NOTAKVPAIR\nFOO=bar\n"
        result = parse_secrets_payload(payload)
        assert result == {"FOO": "bar"}
        captured = capsys.readouterr()
        assert "WARNING" in captured.err


class TestAcquiesceCommand:
    """Tests for AcquiesceCommand."""

    def test_empty_stdin_returns_error(self) -> None:
        """Empty stdin produces an error result."""
        with patch("sys.stdin", StringIO("")):
            result = AcquiesceCommand().execute(keychain=MockKeychain())
        assert not result.ok

    def test_valid_secrets_writes_cache(self, tmp_cache_dir: str) -> None:
        """Valid secrets payload writes cache and returns success."""
        payload = "API_TOKEN=secret123\nDB_PASS=hunter2\n"
        keychain = MockKeychain()
        with patch("sys.stdin", StringIO(payload)):
            result = AcquiesceCommand().execute(keychain=keychain, base_dir=tmp_cache_dir)
        assert result.ok, result.message
        assert result.data["count"] == 2

    def test_result_contains_count(self, tmp_cache_dir: str) -> None:
        """Result data contains the number of cached entries."""
        payload = "A=1\nB=2\nC=3\n"
        keychain = MockKeychain()
        with patch("sys.stdin", StringIO(payload)):
            result = AcquiesceCommand().execute(keychain=keychain, base_dir=tmp_cache_dir)
        assert result.data.get("count") == 3

    def test_ttl_in_message(self, tmp_cache_dir: str) -> None:
        """Success message contains TTL information."""
        payload = "K=V\n"
        keychain = MockKeychain()
        with patch("sys.stdin", StringIO(payload)):
            result = AcquiesceCommand().execute(keychain=keychain, base_dir=tmp_cache_dir)
        assert "TTL" in result.message


class TestRotateCommand:
    """Tests for RotateCommand."""

    def test_rotate_updates_keychain(self) -> None:
        """Rotate writes new values to all Keychain entries."""
        keychain = MockKeychain()
        keychain.set_systemhash(b"\xaa" * 32)
        keychain.set_session_nonce(b"\xbb" * 32)
        keychain.set_session_start(0.0)

        old_hash = keychain.get_systemhash()
        result = RotateCommand().execute(keychain=keychain)

        assert result.ok
        assert keychain.get_systemhash() != old_hash

    def test_rotate_message(self) -> None:
        """Rotate returns a confirmation message."""
        result = RotateCommand().execute(keychain=MockKeychain())
        assert result.ok
        assert "rotated" in result.message.lower()


class TestStatusCommand:
    """Tests for StatusCommand."""

    def test_no_session_returns_error(self) -> None:
        """Status with no active session returns error."""
        result = StatusCommand().execute(keychain=MockKeychain())
        assert not result.ok

    def test_active_session_returns_ok(self) -> None:
        """Status with active session returns ok with TTL."""
        keychain = MockKeychain()
        keychain.set_session_start(time.time())
        result = StatusCommand().execute(keychain=keychain)
        assert result.ok
        assert result.data["ttl_remaining"] > 0

    def test_expired_session_returns_error(self) -> None:
        """Status with expired session returns error."""
        keychain = MockKeychain()
        keychain.set_session_start(time.time() - 100_000)
        result = StatusCommand().execute(keychain=keychain)
        assert not result.ok

    def test_ttl_in_hms_format(self) -> None:
        """Active status message contains HH:MM:SS format."""
        keychain = MockKeychain()
        keychain.set_session_start(time.time())
        result = StatusCommand().execute(keychain=keychain)
        assert result.ok
        import re

        assert re.search(r"\d{2}:\d{2}:\d{2}", result.message)


class TestFormatHms:
    """Tests for the _format_hms helper."""

    def test_zero(self) -> None:
        """Zero seconds formats as 00:00:00."""
        assert _format_hms(0) == "00:00:00"

    def test_one_hour(self) -> None:
        """3600 seconds formats as 01:00:00."""
        assert _format_hms(3600) == "01:00:00"

    def test_mixed(self) -> None:
        """3661 seconds formats as 01:01:01."""
        assert _format_hms(3661) == "01:01:01"

    def test_28800(self) -> None:
        """28800 seconds (8 hours) formats as 08:00:00."""
        assert _format_hms(28800) == "08:00:00"


class TestCommandResult:
    """Tests for CommandResult base class."""

    def test_ok_when_exit_ok(self) -> None:
        """Result is ok when code is OK."""
        result = CommandResult(code=ExitCode.OK)
        assert result.ok

    def test_not_ok_when_error(self) -> None:
        """Result is not ok when code is ERROR."""
        result = CommandResult(code=ExitCode.ERROR)
        assert not result.ok

    def test_default_empty_data(self) -> None:
        """Data defaults to empty dict."""
        result = CommandResult()
        assert result.data == {}

    def test_frozen(self) -> None:
        """CommandResult is immutable (frozen dataclass)."""
        result = CommandResult(message="test")
        with pytest.raises((AttributeError, TypeError)):
            result.message = "modified"  # type: ignore[misc]
