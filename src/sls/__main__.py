"""Entry point for the sls (Short-Lived Secrets) CLI."""

from __future__ import annotations

import argparse
import sys

from sls.version import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser.

    Returns:
        Configured ArgumentParser with all sub-commands registered.
    """
    parser = argparse.ArgumentParser(
        prog="sls",
        description=(
            "Short-Lived Secrets — time-boxed encrypted secret injection from KeePass.\n\n"
            "Secrets are pulled from KeePass in a single brief batch operation, immediately\n"
            "encrypted into /tmp, and injected as environment variables scoped exclusively\n"
            "to the target child process. The safe closes immediately after acquiesce."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # ── acquiesce ──────────────────────────────────────────────────────────────
    sub.add_parser(
        "acquiesce",
        help="Read KEY=VALUE secrets from stdin and write the encrypted cache",
        description=(
            "Read KEY=VALUE pairs from stdin and write them to an AES-256-GCM encrypted\n"
            "cache in /tmp. Rotates session key material (systemhash + session_nonce)\n"
            "on every invocation. The cache expires after 28 800 seconds (8 hours)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # ── push ───────────────────────────────────────────────────────────────────
    push_parser = sub.add_parser(
        "push",
        help="Decrypt the cache and execute a command with secrets in its environment",
        description=(
            "Decrypt the secret cache and execute <command> with the cached secrets\n"
            "injected as environment variables. Secrets exist only for the duration\n"
            "of the child process — when it exits, the secrets are gone."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    push_parser.add_argument(
        "cmd_args",
        nargs=argparse.REMAINDER,
        metavar="<command> [args...]",
        help="Command and arguments to run with secrets injected",
    )

    # ── rotate ─────────────────────────────────────────────────────────────────
    sub.add_parser(
        "rotate",
        help="Rotate session key material — old cache becomes permanently unreadable",
        description=(
            "Generate new systemhash and session_nonce and write them to the Keychain.\n"
            "Old /tmp cache files become permanently unreadable (keys are gone).\n"
            "Run 'sls acquiesce' after rotating to create a fresh cache."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # ── status ─────────────────────────────────────────────────────────────────
    sub.add_parser(
        "status",
        help="Show cache TTL remaining without decrypting anything",
        description=(
            "Read the session_start Keychain entry and compute the remaining TTL.\n"
            "No decryption is performed."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # ── pull ───────────────────────────────────────────────────────────────────
    pull_parser = sub.add_parser(
        "pull",
        help="Pull secrets directly from a KeePass database",
        description="Pull one or many secrets from a KeePass .kdbx file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    pull_sub = pull_parser.add_subparsers(dest="pull_subcommand", metavar="<subcommand>")

    pull_group = pull_sub.add_parser(
        "group",
        help="Pull all entries in a KeePass group and write the encrypted cache",
        description=(
            "Open a KeePass .kdbx file, pull all entries from the named group, close\n"
            "the database, then write the encrypted cache. Prompts for the master\n"
            "password interactively."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    pull_group.add_argument("db_path", metavar="<db_path>", help="Path to the .kdbx file")
    pull_group.add_argument("group_name", metavar="<group>", help="KeePass group (folder) name")
    pull_group.add_argument("--keyfile", metavar="<path>", help="Optional key file path")

    pull_entry = pull_sub.add_parser(
        "entry",
        help="Pull a single KeePass entry and print its value to stdout",
        description=(
            "Open a KeePass .kdbx file, read the entry at <path>, close the database,\n"
            "and print the entry's password to stdout. Prompts for the master password\n"
            "interactively."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    pull_entry.add_argument("db_path", metavar="<db_path>", help="Path to the .kdbx file")
    pull_entry.add_argument(
        "entry_path",
        metavar="<entry_path>",
        help="Slash-separated path to the entry, e.g. 'GroupName/ENTRY_TITLE'",
    )
    pull_entry.add_argument("--keyfile", metavar="<path>", help="Optional key file path")

    return parser


def main() -> None:
    """Run the sls CLI entry point."""
    from sls.commands.acquiesce import AcquiesceCommand
    from sls.commands.pull import PullEntryCommand, PullGroupCommand
    from sls.commands.push import PushCommand
    from sls.commands.rotate import RotateCommand
    from sls.commands.status import StatusCommand

    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "acquiesce":
        result = AcquiesceCommand().execute()

    elif args.command == "push":
        cmd_args = args.cmd_args
        if cmd_args and cmd_args[0] == "--":
            cmd_args = cmd_args[1:]
        result = PushCommand().execute(command=cmd_args)

    elif args.command == "rotate":
        result = RotateCommand().execute()

    elif args.command == "status":
        result = StatusCommand().execute()

    elif args.command == "pull":
        if args.pull_subcommand == "group":
            result = PullGroupCommand().execute(
                db_path=args.db_path,
                group_name=args.group_name,
                keyfile=getattr(args, "keyfile", None),
            )
        elif args.pull_subcommand == "entry":
            result = PullEntryCommand().execute(
                db_path=args.db_path,
                entry_path=args.entry_path,
                keyfile=getattr(args, "keyfile", None),
            )
        else:
            pull_actions = [
                action
                for action in parser._subparsers._group_actions  # type: ignore[attr-defined]
                if hasattr(action, "choices") and "pull" in (action.choices or {})
            ]
            if pull_actions:
                pull_actions[0].choices["pull"].print_help()
            sys.exit(0)

    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        sys.exit(2)

    result.exit()


if __name__ == "__main__":
    main()
