"""sls status command — report cache health without decrypting anything."""

from __future__ import annotations

from typing import Any

from sls.core.base import BaseCommand, CommandResult, ExitCode
from sls.core.session import Session
from sls.keychain.store import KeychainStore


def _format_hms(seconds: float) -> str:
    """Format *seconds* as HH:MM:SS.

    Args:
        seconds: Non-negative number of seconds.

    Returns:
        Zero-padded HH:MM:SS string.
    """
    total = int(seconds)
    h = total // 3600
    m = (total % 3600) // 60
    s = total % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


class StatusCommand(BaseCommand):
    """Report the cache TTL without decrypting anything.

    Reads only the ``kpsc.session_start`` Keychain entry and computes the
    remaining TTL.  No decryption keys are derived or used.

    Example::

        sls status
    """

    name = "status"
    help = "Show cache TTL remaining without decrypting anything"

    def execute(self, **kwargs: Any) -> CommandResult:
        """Execute the status command.

        Args:
            **kwargs:
                keychain: Optional :class:`~sls.keychain.store.KeychainStore`.

        Returns:
            CommandResult with TTL information.
        """
        keychain = kwargs.get("keychain") or KeychainStore()
        session = Session(keychain=keychain)

        valid, remaining = session.check_valid()

        if not valid and remaining == 0.0:
            session_start = keychain.get_session_start()
            if session_start is None:
                return CommandResult(
                    code=ExitCode.ERROR,
                    message="No active cache. Run 'sls acquiesce'.",
                )
            return CommandResult(
                code=ExitCode.ERROR,
                message="Cache expired. Run 'sls acquiesce'.",
                data={"ttl_remaining": 0},
            )

        hms = _format_hms(remaining)
        return CommandResult(
            message=f"Cache active. TTL remaining: {remaining:.0f}s ({hms})",
            data={"ttl_remaining": remaining},
        )
