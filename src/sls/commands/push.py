"""sls push command — decrypt the cache and inject secrets into a child process."""

from __future__ import annotations

import os
import subprocess
import sys
from typing import Any

from sls.core.base import BaseCommand, CommandResult, ExitCode
from sls.core.cache import CacheError, CacheReader
from sls.core.session import Session, SessionError
from sls.github.compiletimehash import CompileTimeHashError, fetch_compiletimehash
from sls.keychain.store import KeychainStore


class PushCommand(BaseCommand):
    """Decrypt the secret cache and inject secrets into a child process environment.

    The child process receives all cached secrets as environment variables.
    The secrets exist only for the duration of the child process — when it
    exits, the secrets are gone.

    Example::

        sls push terraform plan
        sls push docker build --secret env=MY_TOKEN .
    """

    name = "push"
    help = "Decrypt the cache and execute a command with secrets injected as env vars"

    def execute(self, **kwargs: Any) -> CommandResult:  # noqa: PLR0911
        """Execute the push command.

        Validates session TTL, decrypts the cache, and executes the target
        command with secrets injected into its environment.

        Args:
            **kwargs:
                command (list[str]): Program and arguments to run.
                keychain: Optional :class:`~sls.keychain.store.KeychainStore`.
                base_dir (str): Override /tmp base directory (for testing).

        Returns:
            CommandResult with the child process exit code.  Does not return
            normally if ``sys.exit`` is called by the child.
        """
        command: list[str] = kwargs.get("command", [])
        keychain = kwargs.get("keychain") or KeychainStore()
        base_dir = kwargs.get("base_dir")

        if not command:
            return CommandResult(
                code=ExitCode.USAGE,
                message="Usage: sls push <command> [args...]",
            )

        session = Session(keychain=keychain)
        valid, _remaining = session.check_valid()
        if not valid:
            return CommandResult(
                code=ExitCode.ERROR,
                message="Cache expired or missing. Run 'sls acquiesce' to refresh.",
            )

        try:
            compiletimehash = fetch_compiletimehash()
        except CompileTimeHashError as exc:
            return CommandResult(code=ExitCode.ERROR, message=f"[sls] ERROR: {exc}")

        try:
            derived = session.derive_keys(
                gh_auth_token="",
                compiletimehash=compiletimehash,
            )
        except SessionError as exc:
            return CommandResult(code=ExitCode.ERROR, message=f"[sls] Session error: {exc}")
        except Exception as exc:
            return CommandResult(code=ExitCode.ERROR, message=f"[sls] Key derivation failed: {exc}")

        reader_kwargs: dict[str, Any] = {
            "dayhash_b64": derived.dayhash_b64,
            "dayhash_cbc": derived.dayhash_cbc,
            "decr_key": derived.decr_key,
        }
        if base_dir is not None:
            reader_kwargs["base_dir"] = base_dir

        reader = CacheReader(**reader_kwargs)
        try:
            secrets = reader.read()
        except CacheError as exc:
            return CommandResult(code=ExitCode.ERROR, message=f"[sls] Cache error: {exc}")

        env = {**os.environ, **secrets}
        secrets.clear()

        program = command[0]
        args = command[1:]

        try:
            proc = subprocess.run(  # noqa: S603
                [program, *args],
                env=env,
                stdin=sys.stdin,
                stdout=sys.stdout,
                stderr=sys.stderr,
                check=False,
            )
            exit_code = proc.returncode
        except FileNotFoundError:
            return CommandResult(
                code=ExitCode.NOT_FOUND,
                message=f"[sls] Command not found: {program}",
            )
        except Exception as exc:
            return CommandResult(code=ExitCode.ERROR, message=f"[sls] Failed to run command: {exc}")
        finally:
            env.clear()

        if exit_code != 0:
            return CommandResult(
                code=ExitCode.ERROR,
                message="",
                data={"exit_code": exit_code},
            )
        return CommandResult(data={"exit_code": exit_code})
