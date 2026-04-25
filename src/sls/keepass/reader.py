"""KeePass database reader for sls.

Opens a KeePass (.kdbx) database with a master password, reads secrets from a
named group (folder), and returns them as a plain ``dict[str, str]``.

The database is opened once, the required secrets are extracted into memory,
and the database handle is closed immediately — the safe is never held open
longer than the single batch read.

Secrets are keyed by the KeePass entry *title*, which becomes the environment
variable name in the cache.  The value is the entry's *password* field.

For single-path lookup (``pull_entry``), the entry path is specified as a
slash-separated string relative to the database root, e.g.
``"DevSecrets/API_TOKEN"``.
"""

from __future__ import annotations

import contextlib
from pathlib import Path


class KeePassError(Exception):
    """Raised when a KeePass operation fails."""


class KeePassReader:
    """Read secrets from a KeePass .kdbx file.

    Args:
        db_path: Path to the .kdbx database file.
        password: Master password string.
        keyfile: Optional path to a key file (second factor).
    """

    def __init__(
        self,
        db_path: str | Path,
        password: str,
        keyfile: str | Path | None = None,
    ) -> None:
        """Initialise the reader.

        Args:
            db_path: Filesystem path to the .kdbx file.
            password: Master password.
            keyfile: Optional path to a key file used as a second factor.
        """
        self._db_path = Path(db_path)
        self._password = password
        self._keyfile = Path(keyfile) if keyfile else None

    def _open(self) -> pykeepass.PyKeePass:  # type: ignore[name-defined]  # noqa: F821
        """Open and return the database handle.

        Returns:
            An open PyKeePass instance.

        Raises:
            KeePassError: If the database cannot be opened.
        """
        try:
            from pykeepass import PyKeePass  # type: ignore[import-untyped]
        except ImportError as exc:
            raise KeePassError("pykeepass is not installed") from exc

        try:
            return PyKeePass(
                str(self._db_path),
                password=self._password,
                keyfile=str(self._keyfile) if self._keyfile else None,
            )
        except Exception as exc:
            raise KeePassError(f"Failed to open KeePass database: {exc}") from exc

    def pull_group(self, group_name: str) -> dict[str, str]:
        """Pull all entries from a named top-level group.

        The KeePass entry *title* becomes the key; the entry *password*
        becomes the value.  Only entries in the immediate group are returned
        (sub-groups are not traversed).

        Args:
            group_name: Name of the group (folder) within the database.

        Returns:
            Mapping of entry title → password string.

        Raises:
            KeePassError: If the group is not found or the database cannot
                be opened.
        """
        kp = self._open()
        try:
            groups = kp.find_groups(name=group_name, first=False)
            if not groups:
                raise KeePassError(f"Group '{group_name}' not found in database")
            group = groups[0]
            secrets: dict[str, str] = {}
            for entry in group.entries:
                title = entry.title or ""
                password = entry.password or ""
                if title:
                    secrets[title] = password
            return secrets
        finally:
            with contextlib.suppress(Exception):
                kp.close()  # type: ignore[attr-defined]

    def pull_entry(self, entry_path: str) -> str:
        """Pull a single entry by its slash-separated path.

        The path is specified relative to the database root, e.g.
        ``"DevSecrets/API_TOKEN"`` or just ``"API_TOKEN"`` for a root entry.

        Args:
            entry_path: Slash-separated path to the entry.

        Returns:
            The entry's password string.

        Raises:
            KeePassError: If the entry is not found.
        """
        kp = self._open()
        try:
            parts = entry_path.strip("/").split("/")
            title = parts[-1]
            group_path = parts[:-1]

            entries = kp.find_entries(title=title, first=False)
            if not entries:
                raise KeePassError(f"Entry '{title}' not found in database")

            if group_path:
                group_name = group_path[-1]
                matching = [e for e in entries if e.group and e.group.name == group_name]
                if not matching:
                    raise KeePassError(
                        f"Entry '{title}' not found under group path '{'/'.join(group_path)}'"
                    )
                return matching[0].password or ""

            return entries[0].password or ""
        finally:
            with contextlib.suppress(Exception):
                kp.close()  # type: ignore[attr-defined]
