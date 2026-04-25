"""sls rotate command — force immediate cache invalidation."""

from __future__ import annotations

from typing import Any

from sls.core.base import BaseCommand, CommandResult, ExitCode
from sls.core.session import Session
from sls.keychain.store import KeychainError, KeychainStore


class RotateCommand(BaseCommand):
    """Force immediate cache invalidation by rotating all session key material.

    Old ``/tmp`` cache directories become permanently unreadable because the
    Keychain entries used to derive their directory names and decryption keys
    are overwritten with new random values.  The old files are left in place
    but are cryptographically dead — they will be cleared by normal OS /tmp
    cleanup.

    Example::

        sls rotate
    """

    name = "rotate"
    help = "Rotate session key material — old cache becomes permanently unreadable"

    def execute(self, **kwargs: Any) -> CommandResult:
        """Execute the rotate command.

        Generates new systemhash, session_nonce, and session_start values
        and writes them to the Keychain.

        Args:
            **kwargs:
                keychain: Optional :class:`~sls.keychain.store.KeychainStore`.

        Returns:
            CommandResult confirming the rotation.
        """
        keychain = kwargs.get("keychain") or KeychainStore()
        session = Session(keychain=keychain)

        try:
            session.new_session()
        except KeychainError as exc:
            return CommandResult(code=ExitCode.ERROR, message=f"[sls] Keychain error: {exc}")

        return CommandResult(
            message=(
                "Cache rotated. Old /tmp entries are permanently unreadable.\n"
                "Run 'sls acquiesce' to create a new cache."
            )
        )
