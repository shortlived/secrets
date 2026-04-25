"""Tests for dev_patterns.core.ui — Console styled output."""

from __future__ import annotations

import io

import pytest

from dev_patterns.core.ui import Color, Console


class TestConsole:
    """Tests for the Console class."""

    @pytest.fixture
    def streams(self) -> tuple[io.StringIO, io.StringIO]:
        """Return fresh stdout/stderr StringIO streams."""
        return io.StringIO(), io.StringIO()

    def _make(self, color: bool = True) -> tuple[Console, io.StringIO, io.StringIO]:
        out, err = io.StringIO(), io.StringIO()
        return Console(out=out, err=err, color=color), out, err

    def test_header_writes_to_stdout(self) -> None:
        """header() writes to stdout."""
        console, out, err = self._make()
        console.header("Patterns Sync")
        assert "Patterns Sync" in out.getvalue()
        assert err.getvalue() == ""

    def test_header_contains_cyan_when_color(self) -> None:
        """header() includes CYAN escape when color=True."""
        console, out, _ = self._make(color=True)
        console.header("Test")
        assert Color.CYAN.value in out.getvalue()

    def test_header_no_escape_when_no_color(self) -> None:
        """header() has no escape sequences when color=False."""
        console, out, _ = self._make(color=False)
        console.header("Test")
        assert "\033[" not in out.getvalue()

    def test_step_writes_arrow(self) -> None:
        """step() writes an arrow symbol."""
        console, out, _ = self._make(color=False)
        console.step("Downloading…")
        assert Console.SYM_ARROW in out.getvalue()
        assert "Downloading…" in out.getvalue()

    def test_ok_writes_check(self) -> None:
        """ok() writes a check symbol."""
        console, out, _ = self._make(color=False)
        console.ok("Done")
        assert Console.SYM_CHECK in out.getvalue()

    def test_warn_writes_to_stderr(self) -> None:
        """warn() writes to stderr."""
        console, _out, err = self._make(color=False)
        console.warn("Something wrong")
        assert "Something wrong" in err.getvalue()
        assert Console.SYM_WARN in err.getvalue()

    def test_error_writes_to_stderr(self) -> None:
        """error() writes to stderr."""
        console, _out, err = self._make(color=False)
        console.error("Fatal error")
        assert "Fatal error" in err.getvalue()
        assert Console.SYM_CROSS in err.getvalue()

    def test_info_writes_label_and_value(self) -> None:
        """info() writes both label and value."""
        console, out, _ = self._make(color=False)
        console.info("Repo", "orchestras/dev-patterns")
        output = out.getvalue()
        assert "Repo" in output
        assert "orchestras/dev-patterns" in output

    def test_blank_writes_empty_line(self) -> None:
        """blank() writes an empty line."""
        console, out, _ = self._make(color=False)
        console.blank()
        assert out.getvalue() == "\n"

    def test_done_writes_check_and_message(self) -> None:
        """done() writes check symbol and message."""
        console, out, _ = self._make(color=False)
        console.done("Sync complete")
        assert Console.SYM_CHECK in out.getvalue()
        assert "Sync complete" in out.getvalue()

    def test_working_writes_spin(self) -> None:
        """working() writes a spin symbol."""
        console, out, _ = self._make(color=False)
        console.working("Fetching…")
        assert Console.SYM_SPIN in out.getvalue()
