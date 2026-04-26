"""sls acquiesce command — pull secrets from stdin and write encrypted cache."""

from __future__ import annotations

import sys
from typing import Any

from sls.core.base import BaseCommand, CommandResult, ExitCode
from sls.core.cache import CacheWriter
from sls.core.session import Session
from sls.github.compiletimehash import CompileTimeHashError, fetch_compiletimehash
from sls.keychain.store import KeychainError, KeychainStore


def parse_secrets_payload(payload: str) -> dict[str, str]:
    r"""Parse a ``KEY=VALUE\\n...`` payload into a dictionary.

    Lines that are blank or start with ``#`` are ignored.  Lines without an
    ``=`` separator are also ignored with a warning to stderr.

    Args:
        payload: Multi-line string of KEY=VALUE pairs.

    Returns:
        Dictionary mapping variable names to their values.
    """
    secrets: dict[str, str] = {}
    for raw_line in payload.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            print(
                f"[sls] WARNING: skipping malformed line (no '='): {stripped!r}",
                file=sys.stderr,
            )
            continue
        key, _, value = stripped.partition("=")
        secrets[key.strip()] = value
    return secrets


class AcquiesceCommand(BaseCommand):
    r"""Read secrets from stdin and write them to the encrypted cache.

    This is the **core** operation.  Secrets are piped in as ``KEY=VALUE``
    lines (never as CLI arguments), the session key material is rotated, and
    two encrypted files are written to ``/tmp``.

    Example::

        echo "API_TOKEN=secret123\\nDB_PASS=hunter2" | sls acquiesce
    """

    name = "acquiesce"
    help = "Read secrets from stdin and write the encrypted cache"

    def execute(self, **kwargs: Any) -> CommandResult:
        """Execute the acquiesce command.

        Reads ``KEY=VALUE`` lines from stdin, fetches the compiletimehash,
        rotates the Keychain session entries, derives all cache keys, and
        writes the encrypted cache files to ``/tmp``.

        Args:
            **kwargs: Unused; payload is always read from stdin.

        Returns:
            CommandResult indicating success or failure.
        """
        keychain = kwargs.get("keychain") or KeychainStore()
        base_dir = kwargs.get("base_dir")

        payload = sys.stdin.read()
        secrets = parse_secrets_payload(payload)

        if not secrets:
            return CommandResult(
                code=ExitCode.ERROR,
                message="No secrets received on stdin. Nothing cached.",
            )

        try:
            compiletimehash = fetch_compiletimehash()
        except CompileTimeHashError as exc:
            return CommandResult(code=ExitCode.ERROR, message=f"[sls] ERROR: {exc}")

        session = Session(keychain=keychain)
        try:
            session.new_session()
        except KeychainError as exc:
            return CommandResult(code=ExitCode.ERROR, message=f"[sls] Keychain error: {exc}")

        try:
            derived = session.derive_keys(
                gh_auth_token="",
                compiletimehash=compiletimehash,
            )
        except Exception as exc:
            return CommandResult(code=ExitCode.ERROR, message=f"[sls] Key derivation failed: {exc}")

        writer_kwargs: dict[str, Any] = {
            "dayhash_b64": derived.dayhash_b64,
            "dayhash_cbc": derived.dayhash_cbc,
            "decr_key": derived.decr_key,
        }
        if base_dir is not None:
            writer_kwargs["base_dir"] = base_dir

        writer = CacheWriter(**writer_kwargs)
        try:
            writer.write(secrets)
        except Exception as exc:
            return CommandResult(code=ExitCode.ERROR, message=f"[sls] Cache write failed: {exc}")

        count = len(secrets)
        return CommandResult(
            message=f"Secrets cached ({count} entries). TTL: {session._ttl}s",
            data={"count": count},
        )
