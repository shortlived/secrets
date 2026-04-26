"""Entry point for the dev-patterns CLI.

Usage::

    dev-patterns sync
    dev-patterns hooks
    dev-patterns --version
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from dev_patterns.commands.hooks import HooksCommand
from dev_patterns.commands.sync import SyncCommand
from dev_patterns.version import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser.

    Returns:
        Configured ArgumentParser with all sub-commands registered.
    """
    parser = argparse.ArgumentParser(
        prog="dev-patterns",
        description=(
            "dev-patterns — central patterns library for orchestras repositories.\n"
            "Manages git hooks and mise tasks via declarative TOML subscriptions."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # ── sync ──────────────────────────────────────────────────────────────────
    sync_parser = sub.add_parser("sync", help=SyncCommand.help)
    sync_parser.add_argument(
        "--root",
        type=Path,
        default=None,
        metavar="DIR",
        help="Project root directory (default: current directory)",
    )
    sync_parser.add_argument(
        "--force",
        action="store_true",
        help="Force sync even when hash is current",
    )

    # ── hooks ─────────────────────────────────────────────────────────────────
    hooks_parser = sub.add_parser("hooks", help=HooksCommand.help)
    hooks_parser.add_argument(
        "--root",
        type=Path,
        default=None,
        metavar="DIR",
        help="Project root directory (default: current directory)",
    )
    hooks_parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        metavar="FILE",
        help="Path to githooks.toml (default: config/githooks/hooks/githooks.toml)",
    )

    return parser


def main() -> None:
    """Run the CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    root = args.root or Path.cwd()

    if args.command == "sync":
        result = SyncCommand().execute(project_root=root, force=getattr(args, "force", False))
    elif args.command == "hooks":
        kwargs: dict = {"project_root": root}
        if getattr(args, "manifest", None):
            kwargs["manifest"] = args.manifest
        result = HooksCommand().execute(**kwargs)
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        sys.exit(2)

    result.exit()


if __name__ == "__main__":
    main()
