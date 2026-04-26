"""sls pull commands — pull secrets directly from a KeePass database.

Two sub-operations are provided:

- ``sls pull group <db> <group>``  — pull all entries in a KeePass folder and
  write them to the encrypted cache.
- ``sls pull entry <db> <path>``   — pull a single entry by path and print it
  to stdout (for piping, not for storing).

These commands prompt for the KeePass master password interactively so the
password is never supplied on the command line (invisible to ``ps aux``).
"""

from __future__ import annotations

import getpass
import sys
from typing import Any

from sls.core.base import BaseCommand, CommandResult, ExitCode
from sls.core.cache import CacheWriter
from sls.core.session import Session
from sls.github.compiletimehash import CompileTimeHashError, fetch_compiletimehash
from sls.keepass.reader import KeePassError, KeePassReader
from sls.keychain.store import KeychainError, KeychainStore


class PullGroupCommand(BaseCommand):
    """Pull all entries in a KeePass group and write them to the encrypted cache.

    Opens the KeePass database once, extracts all entries from the named
    group, closes the database, then calls the acquiesce pipeline to write
    the encrypted cache.

    Example::

        sls pull group /path/to/safe.kdbx generic
    """

    name = "pull-group"
    help = "Pull all secrets in a KeePass group and write the encrypted cache"

    def execute(self, **kwargs: Any) -> CommandResult:  # noqa: PLR0911
        """Execute the pull-group command.

        Args:
            **kwargs:
                db_path (str): Path to the .kdbx file.
                group_name (str): Name of the group to pull.
                keyfile (str | None): Optional path to a key file.
                keychain: Optional :class:`~sls.keychain.store.KeychainStore`.
                base_dir (str): Override /tmp base directory (for testing).
                password (str): Master password (for testing — omit to prompt).

        Returns:
            CommandResult indicating success or failure.
        """
        db_path: str = kwargs.get("db_path", "")
        group_name: str = kwargs.get("group_name", "")
        keyfile: str | None = kwargs.get("keyfile")
        keychain = kwargs.get("keychain") or KeychainStore()
        base_dir: str | None = kwargs.get("base_dir")
        password: str | None = kwargs.get("password")

        if not db_path or not group_name:
            return CommandResult(
                code=ExitCode.USAGE,
                message="Usage: sls pull group <db_path> <group_name> [--keyfile <path>]",
            )

        if password is None:
            try:
                password = getpass.getpass(f"KeePass password for {db_path}: ")
            except (KeyboardInterrupt, EOFError):
                print("", file=sys.stderr)
                return CommandResult(code=ExitCode.ERROR, message="Aborted.")

        reader = KeePassReader(db_path, password, keyfile=keyfile)
        try:
            secrets = reader.pull_group(group_name)
        except KeePassError as exc:
            return CommandResult(code=ExitCode.ERROR, message=f"[sls] KeePass error: {exc}")
        finally:
            password = ""

        if not secrets:
            return CommandResult(
                code=ExitCode.ERROR,
                message=f"Group '{group_name}' is empty — nothing to cache.",
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
            message=f"Secrets cached ({count} entries from '{group_name}'). TTL: {session._ttl}s",
            data={"count": count, "group": group_name},
        )


class PullEntryCommand(BaseCommand):
    """Pull a single KeePass entry by path and print its value to stdout.

    The value is written to stdout only — it is never stored in a variable by
    this command.  Use shell process-substitution or a pipe if you need to
    pass it to another program.

    Example::

        sls pull entry /path/to/safe.kdbx "DevSecrets/API_TOKEN"
    """

    name = "pull-entry"
    help = "Pull a single KeePass entry and print its value to stdout"

    def execute(self, **kwargs: Any) -> CommandResult:
        """Execute the pull-entry command.

        Args:
            **kwargs:
                db_path (str): Path to the .kdbx file.
                entry_path (str): Slash-separated path to the entry.
                keyfile (str | None): Optional path to a key file.
                password (str): Master password (for testing — omit to prompt).

        Returns:
            CommandResult with the secret value in ``data['value']``.
        """
        db_path: str = kwargs.get("db_path", "")
        entry_path: str = kwargs.get("entry_path", "")
        keyfile: str | None = kwargs.get("keyfile")
        password: str | None = kwargs.get("password")

        if not db_path or not entry_path:
            return CommandResult(
                code=ExitCode.USAGE,
                message="Usage: sls pull entry <db_path> <entry_path> [--keyfile <path>]",
            )

        if password is None:
            try:
                password = getpass.getpass(f"KeePass password for {db_path}: ")
            except (KeyboardInterrupt, EOFError):
                print("", file=sys.stderr)
                return CommandResult(code=ExitCode.ERROR, message="Aborted.")

        reader = KeePassReader(db_path, password, keyfile=keyfile)
        try:
            value = reader.pull_entry(entry_path)
        except KeePassError as exc:
            return CommandResult(code=ExitCode.ERROR, message=f"[sls] KeePass error: {exc}")
        finally:
            password = ""

        return CommandResult(
            message=value,
            data={"value": value},
        )
