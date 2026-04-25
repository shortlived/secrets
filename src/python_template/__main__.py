"""Entry point for the python-template CLI."""

from __future__ import annotations

import argparse
import sys

from python_template.commands.greet import GreetCommand
from python_template.commands.info import InfoCommand
from python_template.version import __version__


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser.

    Returns:
        Configured ArgumentParser with all sub-commands registered.
    """
    parser = argparse.ArgumentParser(
        prog="python-template",
        description="Python 3 template CLI — replace this with your application",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    sub = parser.add_subparsers(dest="command", metavar="<command>")

    # greet
    greet_parser = sub.add_parser("greet", help=GreetCommand.help)
    greet_parser.add_argument("--name", default="world", help="Name to greet")
    greet_parser.add_argument("--loud", action="store_true", help="Shout the greeting (uppercase)")

    # info
    sub.add_parser("info", help=InfoCommand.help)

    return parser


def main() -> None:
    """Run the CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "greet":
        result = GreetCommand().execute(name=args.name, loud=args.loud)
    elif args.command == "info":
        result = InfoCommand().execute()
    else:
        print(f"Unknown command: {args.command}", file=sys.stderr)
        sys.exit(2)

    result.exit()


if __name__ == "__main__":
    main()
