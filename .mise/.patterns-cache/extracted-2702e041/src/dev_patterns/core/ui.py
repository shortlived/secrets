"""Terminal UI helpers — styled output inspired by mise and lefthook."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TextIO


class Color(StrEnum):
    """ANSI color escape codes."""

    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    MAGENTA = "\033[0;35m"
    CYAN = "\033[0;36m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RESET = "\033[0m"


@dataclass
class Console:
    """Styled console output for dev-patterns CLI commands.

    Provides mise/lefthook-style formatted output with:
    - Section headers  (cyan bold)
    - Steps            (blue arrow)
    - Success lines    (green check)
    - Warnings         (yellow warning)
    - Errors           (red cross)
    - Dim metadata     (dim/grey)

    Attributes:
        out:   Stream for normal output (default: stdout).
        err:   Stream for error output  (default: stderr).
        color: Whether to emit ANSI color sequences.
    """

    out: TextIO = field(default_factory=lambda: sys.stdout)
    err: TextIO = field(default_factory=lambda: sys.stderr)
    color: bool = True

    # ── Symbols ───────────────────────────────────────────────────────────────
    SYM_CHECK = "✓"
    SYM_CROSS = "✗"
    SYM_ARROW = "→"
    SYM_SPIN = "⟳"
    SYM_WARN = "⚠"
    SYM_DOT = "·"

    def _c(self, *codes: Color) -> str:
        """Return the escape sequence for one or more color codes, or empty string."""
        if not self.color:
            return ""
        return "".join(c.value for c in codes)

    def _reset(self) -> str:
        return self._c(Color.RESET) if self.color else ""

    def _write(self, text: str, stream: TextIO | None = None) -> None:
        target = stream or self.out
        print(text, file=target)

    # ── Public helpers ────────────────────────────────────────────────────────

    def header(self, title: str) -> None:
        """Print a section header (cyan bold).

        Example output::

            Patterns Sync
        """
        self._write(f"{self._c(Color.CYAN, Color.BOLD)}{title}{self._reset()}")

    def step(self, msg: str) -> None:
        """Print a processing step (blue arrow, indented).

        Example output::

              → Downloading tarball…
        """
        self._write(f"  {self._c(Color.BLUE)}{self.SYM_ARROW}{self._reset()} {msg}")

    def working(self, msg: str) -> None:
        """Print a working/spinner line (dim spin symbol, indented).

        Example output::

              ⟳ Resolving commit hash…
        """
        self._write(f"  {self._c(Color.DIM)}{self.SYM_SPIN}{self._reset()} {msg}")

    def ok(self, msg: str) -> None:
        """Print a success line (green check, indented).

        Example output::

              ✓ Tasks synced → .mise/tasks/
        """
        self._write(f"  {self._c(Color.GREEN)}{self.SYM_CHECK}{self._reset()} {msg}")

    def warn(self, msg: str) -> None:
        """Print a warning (yellow warning symbol, indented).

        Example output::

              ⚠ Channel directory not found
        """
        self._write(
            f"  {self._c(Color.YELLOW)}{self.SYM_WARN}{self._reset()} {msg}",
            stream=self.err,
        )

    def error(self, msg: str) -> None:
        """Print an error (red cross, indented).

        Example output::

              ✗ Sync failed: connection refused
        """
        self._write(
            f"  {self._c(Color.RED)}{self.SYM_CROSS}{self._reset()} {msg}",
            stream=self.err,
        )

    def info(self, label: str, value: str) -> None:
        """Print a key/value info line (dim label, normal value).

        Example output::

              Repo    orchestras/dev-patterns
        """
        self._write(f"  {self._c(Color.DIM)}{label:<12}{self._reset()} {value}")

    def blank(self) -> None:
        """Print a blank line."""
        self._write("")

    def done(self, msg: str) -> None:
        """Print a bold success summary line (green bold check).

        Example output::

            ✓ Patterns synced (python3a @ a1b2c3d4)
        """
        self._write(f"{self._c(Color.GREEN, Color.BOLD)}{self.SYM_CHECK} {msg}{self._reset()}")
