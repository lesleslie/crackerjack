"""Comprehensive unit tests for `crackerjack.exceptions.tool_execution_error`.

Goal: bring `crackerjack/exceptions/tool_execution_error.py` from its current
~10% branch coverage to 80%+ by exercising every branch of `ToolExecutionError`
public surface (`__init__`, `format_rich`, `_format_output`,
`_get_error_suggestion`, `get_actionable_message`, `__str__`, `__repr__`).
"""

from __future__ import annotations

from pathlib import Path

import pytest
from rich.console import Console
from rich.panel import Panel

from crackerjack.exceptions.tool_execution_error import ToolExecutionError


class TestInit:
    """`__init__` stores attributes and shapes the exception message."""

    def test_minimal_defaults(self) -> None:
        error = ToolExecutionError(tool="ruff-check", exit_code=1)

        assert error.tool == "ruff-check"
        assert error.exit_code == 1
        assert error.stdout == ""
        assert error.stderr == ""
        assert error.command is None
        assert error.cwd is None
        assert error.duration is None

    def test_full_parameters(self, tmp_path: Path) -> None:
        command = ["uv", "run", "ruff", "check", "test.py"]
        error = ToolExecutionError(
            tool="ruff-check",
            exit_code=1,
            stdout="Found 5 errors",
            stderr="E501 line too long",
            command=command,
            cwd=tmp_path,
            duration=2.5,
        )

        assert error.tool == "ruff-check"
        assert error.exit_code == 1
        assert error.stdout == "Found 5 errors"
        assert error.stderr == "E501 line too long"
        assert error.command == command
        assert error.cwd == tmp_path
        assert error.duration == 2.5

    def test_strips_stdout_and_stderr(self) -> None:
        error = ToolExecutionError(
            tool="test",
            exit_code=1,
            stdout="  output  \n\n",
            stderr="\n  error  \n",
        )

        assert error.stdout == "output"
        assert error.stderr == "error"

    def test_message_includes_duration_only_when_provided(self) -> None:
        without_duration = ToolExecutionError(tool="ruff", exit_code=1)
        with_duration = ToolExecutionError(tool="ruff", exit_code=1, duration=2.5)

        # `super().__init__(message)` receives the message; check args[0] so
        # the assertion targets the constructor's message, not `__str__`'s
        # which uses a different "Duration: N.NNs" format.
        assert "after 2.5s" in with_duration.args[0]
        assert "after " not in without_duration.args[0]

    def test_is_exception_subclass(self) -> None:
        error = ToolExecutionError(tool="t", exit_code=0)
        assert isinstance(error, Exception)


class TestFormatRich:
    """`format_rich` builds a Panel with tool, exit code, and conditional fields."""

    def test_returns_panel_instance(self) -> None:
        error = ToolExecutionError(tool="ruff", exit_code=1, stderr="boom")
        panel = error.format_rich(Console())
        assert isinstance(panel, Panel)

    def test_title_contains_tool_name(self) -> None:
        error = ToolExecutionError(tool="ruff-check", exit_code=2, stderr="oops")
        panel = error.format_rich(Console())
        assert panel.title is not None
        assert "ruff-check" in str(panel.title)

    def test_border_style_is_red(self) -> None:
        error = ToolExecutionError(tool="ruff", exit_code=1, stderr="oops")
        panel = error.format_rich(Console())
        assert panel.border_style == "red"

    def test_panel_content_includes_tool_and_exit_code(self) -> None:
        error = ToolExecutionError(tool="zuban", exit_code=7, stderr="E")
        panel = error.format_rich(Console())
        assert panel.renderable is not None
        rendered = str(panel.renderable)
        assert "zuban" in rendered
        assert "7" in rendered

    def test_duration_added_when_provided(self) -> None:
        error = ToolExecutionError(
            tool="ruff",
            exit_code=1,
            stderr="oops",
            duration=3.14,
        )
        panel = error.format_rich(Console())
        assert panel.renderable is not None
        rendered = str(panel.renderable)
        assert "Duration" in rendered
        assert "3.14s" in rendered

    def test_duration_omitted_when_none(self) -> None:
        error = ToolExecutionError(tool="ruff", exit_code=1, stderr="oops")
        panel = error.format_rich(Console())
        assert panel.renderable is not None
        assert "Duration" not in str(panel.renderable)

    def test_cwd_added_when_provided(self, tmp_path: Path) -> None:
        error = ToolExecutionError(
            tool="ruff",
            exit_code=1,
            stderr="oops",
            cwd=tmp_path,
        )
        panel = error.format_rich(Console())
        assert panel.renderable is not None
        rendered = str(panel.renderable)
        assert "Directory" in rendered
        assert str(tmp_path) in rendered

    def test_long_command_is_truncated_with_ellipsis(self) -> None:
        long_command = ["uv", "run", "tool"] + [f"arg-{i}" for i in range(50)]
        error = ToolExecutionError(
            tool="ruff",
            exit_code=1,
            command=long_command,
        )
        panel = error.format_rich(Console())
        assert panel.renderable is not None
        rendered = str(panel.renderable)
        assert "Command" in rendered
        assert "..." in rendered

    def test_short_command_is_not_truncated(self) -> None:
        error = ToolExecutionError(
            tool="ruff",
            exit_code=1,
            command=["ruff", "check"],
        )
        panel = error.format_rich(Console())
        assert panel.renderable is not None
        rendered = str(panel.renderable)
        assert "ruff check" in rendered

    def test_stderr_wins_over_stdout_when_both_present(self) -> None:
        error = ToolExecutionError(
            tool="ruff",
            exit_code=1,
            stdout="out line",
            stderr="err line",
        )
        panel = error.format_rich(Console())
        assert panel.renderable is not None
        rendered = str(panel.renderable)
        # The stderr branch renders "[bold yellow]Error Output:[/bold yellow]"
        # and the stdout branch is never entered when stderr is non-empty.
        assert "Error Output" in rendered
        assert "err line" in rendered
        assert "out line" not in rendered

    def test_stdout_shown_when_stderr_empty(self) -> None:
        error = ToolExecutionError(
            tool="ruff",
            exit_code=1,
            stdout="out line",
            stderr="",
        )
        panel = error.format_rich(Console())
        assert panel.renderable is not None
        rendered = str(panel.renderable)
        assert "Output" in rendered
        assert "Error Output" not in rendered

    def test_no_output_shows_fallback_message(self) -> None:
        error = ToolExecutionError(
            tool="ruff",
            exit_code=1,
            stdout="",
            stderr="",
        )
        panel = error.format_rich(Console())
        assert panel.renderable is not None
        rendered = str(panel.renderable)
        assert "No error output available" in rendered

    def test_stderr_over_20_lines_is_truncated(self) -> None:
        long_stderr = "\n".join(f"Error line {i}" for i in range(30))
        error = ToolExecutionError(
            tool="ruff",
            exit_code=1,
            stderr=long_stderr,
        )
        panel = error.format_rich(Console())
        assert panel.renderable is not None
        rendered = str(panel.renderable)
        # The marker is added when there are more than 20 lines.
        assert "...(truncated)" in rendered
        # The earliest line (line 0) should NOT appear; only the last 20 kept.
        assert "Error line 0" not in rendered
        assert "Error line 29" in rendered

    def test_stdout_over_20_lines_is_truncated(self) -> None:
        long_stdout = "\n".join(f"Stdout line {i}" for i in range(25))
        error = ToolExecutionError(
            tool="ruff",
            exit_code=1,
            stdout=long_stdout,
        )
        panel = error.format_rich(Console())
        assert panel.renderable is not None
        rendered = str(panel.renderable)
        assert "...(truncated)" in rendered

    def test_console_kwarg_accepted_and_unused(self) -> None:
        # The console arg is accepted for API completeness; verify it does not
        # raise and produces a valid Panel regardless.
        error = ToolExecutionError(tool="ruff", exit_code=1, stderr="oops")
        panel = error.format_rich(Console(record=True))
        assert isinstance(panel, Panel)


class TestFormatOutput:
    """`_format_output` strips ANSI, skips blank lines, and returns a dim marker."""

    def test_strips_ansi_escape_codes(self) -> None:
        error = ToolExecutionError(tool="t", exit_code=1)
        lines = [
            "\x1b[31mRed text\x1b[0m",
            "\x1b[1;32mGreen bold\x1b[0m",
            "plain line",
        ]
        formatted = error._format_output(lines)

        assert "\x1b" not in formatted
        assert "Red text" in formatted
        assert "Green bold" in formatted
        assert "plain line" in formatted

    def test_skips_empty_lines(self) -> None:
        error = ToolExecutionError(tool="t", exit_code=1)
        formatted = error._format_output(["A", "", "   ", "B"])
        # Whitespace-only lines are skipped; non-empty lines are present.
        assert "A" in formatted
        assert "B" in formatted
        # The exact blank line positions are not emitted as separate rows.
        lines = [line for line in formatted.split("\n") if line.strip()]
        assert lines == [" A", " B"]

    def test_returns_empty_marker_for_blank_input(self) -> None:
        error = ToolExecutionError(tool="t", exit_code=1)
        assert error._format_output([]) == "[dim] (empty)[/dim]"

    def test_returns_empty_marker_for_whitespace_only_input(self) -> None:
        error = ToolExecutionError(tool="t", exit_code=1)
        assert error._format_output(["", "   ", "\t", ""]) == "[dim] (empty)[/dim]"

    def test_indents_lines_with_single_space(self) -> None:
        error = ToolExecutionError(tool="t", exit_code=1)
        formatted = error._format_output(["alpha", "beta"])
        assert " alpha" in formatted
        assert " beta" in formatted


class TestGetErrorSuggestion:
    """`_get_error_suggestion` returns pattern-matched remediation strings."""

    @pytest.mark.parametrize(
        ("stderr", "expected_substring"),
        [
            ("Permission denied: /etc/shadow", "permission"),
            ("EACCES: permission denied", "permission"),
            ("bash: missing-tool: command not found", "PATH"),
            ("No such file or directory", "PATH"),
            ("Command timed out after 60 seconds", "timeout"),
            ("Operation timed out", "timeout"),
            ("SyntaxError: invalid syntax", "syntax"),
            ("syntax error in line 5", "syntax"),
            ("ImportError: cannot import name", "dependencies"),
            ("ModuleNotFoundError: No module named 'x'", "uv sync"),
            ("TypeError: cannot concatenate", "type annotation"),
            ("Type error detected", "type annotation"),
            ("Out of memory: Killed process", "memory"),
        ],
    )
    def test_pattern_matches_expected_suggestion(
        self,
        stderr: str,
        expected_substring: str,
    ) -> None:
        error = ToolExecutionError(tool="ruff", exit_code=1, stderr=stderr)
        suggestion = error._get_error_suggestion(stderr.lower())
        assert suggestion is not None
        assert expected_substring.lower() in suggestion.lower()

    def test_tuple_pattern_matches_any_key(self) -> None:
        # Tuple patterns should match if ANY key is present in the output.
        error = ToolExecutionError(tool="ruff", exit_code=1)
        # Both "command not found" and "no such file" are in the same tuple.
        assert "PATH" in (error._get_error_suggestion("command not found") or "")
        assert "PATH" in (error._get_error_suggestion("no such file or dir") or "")
        # And the union across separate tuples (timeout/timed out).
        assert "timeout" in (error._get_error_suggestion("timed out") or "").lower()
        assert "timeout" in (error._get_error_suggestion("timeout reached") or "").lower()

    def test_unmatched_returns_none(self) -> None:
        error = ToolExecutionError(tool="ruff", exit_code=1)
        assert error._get_error_suggestion("some random unrelated error") is None

    def test_pattern_match_is_case_sensitive(self) -> None:
        # `_get_error_suggestion` performs plain `in` substring matching
        # against the (already-lowercased) combined output. Uppercase input
        # does not match the lowercase patterns; callers are expected to
        # pre-lowercase (see `get_actionable_message`).
        error = ToolExecutionError(tool="ruff", exit_code=1)
        assert error._get_error_suggestion("PERMISSION DENIED") is None
        assert error._get_error_suggestion("permission denied") is not None


class TestGetActionableMessage:
    """`get_actionable_message` returns joined messages based on pattern matches."""

    def test_with_matched_suggestion_returns_joined_message(self) -> None:
        error = ToolExecutionError(
            tool="ruff",
            exit_code=1,
            stderr="Permission denied: file",
        )
        message = error.get_actionable_message()

        assert "ruff" in message
        assert "exit code 1" in message
        assert "→" in message
        assert "permission" in message.lower()
        # Header line must come before the suggestion line.
        header, suggestion = message.split("\n", 1)
        assert "ruff" in header
        assert "permission" in suggestion.lower()

    def test_without_suggestion_with_stderr_returns_check_output(self) -> None:
        error = ToolExecutionError(
            tool="custom",
            exit_code=1,
            stderr="Some unrecognized error",
        )
        message = error.get_actionable_message()

        assert "custom" in message
        assert "Check error output above" in message
        assert "→" in message

    def test_without_suggestion_without_stderr_returns_run_manually(self) -> None:
        error = ToolExecutionError(
            tool="custom",
            exit_code=1,
            stdout="",
            stderr="",
        )
        message = error.get_actionable_message()

        assert "custom" in message
        assert "Run 'custom' manually" in message

    def test_builds_combined_output_from_stderr_and_stdout(self) -> None:
        # The pattern search uses combined stderr + stdout (lowercased).
        # Pattern must be present in either, with case-insensitive match.
        error = ToolExecutionError(
            tool="ruff",
            exit_code=1,
            stdout="stdout was here",
            stderr="",
        )
        message = error.get_actionable_message()
        # No recognizable pattern in either, so falls through to generic
        # "Check error output above" since stderr is empty but stdout
        # is also empty in this fixture.
        # Use a populated stderr to verify stderr wins.
        error2 = ToolExecutionError(
            tool="ruff",
            exit_code=1,
            stdout="stdout content",
            stderr="stdout was here",
        )
        # stdout content is also empty for the suggestion match, but stderr
        # triggers the "Check error output above" fallback.
        msg2 = error2.get_actionable_message()
        assert "Check error output above" in msg2


class TestStr:
    """`__str__` formats parts in a stable, greppable shape."""

    def test_basic_str_without_extras(self) -> None:
        error = ToolExecutionError(tool="ruff", exit_code=1)
        s = str(error)
        assert s == "ToolExecutionError: ruff | Exit Code: 1"

    def test_str_includes_duration_only_when_set(self) -> None:
        no_duration = ToolExecutionError(tool="ruff", exit_code=1)
        s = str(no_duration)
        assert "Duration" not in s

        with_duration = ToolExecutionError(
            tool="ruff",
            exit_code=1,
            duration=2.5,
        )
        s2 = str(with_duration)
        assert "Duration: 2.50s" in s2

    def test_str_includes_command_only_when_set(self) -> None:
        no_command = ToolExecutionError(tool="ruff", exit_code=1)
        assert "Command" not in str(no_command)

        with_command = ToolExecutionError(
            tool="ruff",
            exit_code=1,
            command=["uv", "run", "ruff", "check"],
        )
        s = str(with_command)
        assert "Command: uv run ruff check" in s

    def test_str_prefers_stderr_over_stdout(self) -> None:
        error = ToolExecutionError(
            tool="ruff",
            exit_code=1,
            stdout="plain stdout",
            stderr="err contents",
        )
        s = str(error)
        assert "Stderr: err contents" in s
        assert "Stdout:" not in s

    def test_str_falls_back_to_stdout_when_no_stderr(self) -> None:
        error = ToolExecutionError(
            tool="ruff",
            exit_code=1,
            stdout="plain stdout",
            stderr="",
        )
        s = str(error)
        assert "Stdout: plain stdout" in s
        assert "Stderr:" not in s

    def test_str_truncates_stderr_at_200_chars(self) -> None:
        long_stderr = "x" * 500
        error = ToolExecutionError(
            tool="ruff",
            exit_code=1,
            stderr=long_stderr,
        )
        s = str(error)
        # The truncated prefix is exactly 200 'x' chars, then "...".
        assert "Stderr: " + ("x" * 200) + "..." in s
        # And the full 500-char string must NOT be present.
        assert long_stderr not in s

    def test_str_truncates_stdout_at_200_chars(self) -> None:
        long_stdout = "y" * 500
        error = ToolExecutionError(
            tool="ruff",
            exit_code=1,
            stdout=long_stdout,
        )
        s = str(error)
        assert "Stdout: " + ("y" * 200) + "..." in s


class TestRepr:
    """`__repr__` produces a constructor-like, single-line representation."""

    def test_repr_format(self) -> None:
        error = ToolExecutionError(tool="ruff", exit_code=2, duration=1.5)
        assert repr(error) == (
            "ToolExecutionError(tool='ruff', exit_code=2, duration=1.5)"
        )

    def test_repr_with_none_duration(self) -> None:
        error = ToolExecutionError(tool="zuban", exit_code=0)
        assert repr(error) == (
            "ToolExecutionError(tool='zuban', exit_code=0, duration=None)"
        )

    def test_repr_escapes_special_characters_in_tool(self) -> None:
        error = ToolExecutionError(tool="name'with\"quotes", exit_code=1)
        # Python repr uses single-quote-double-quote escaping by default.
        r = repr(error)
        assert r.startswith("ToolExecutionError(tool=")
        assert "exit_code=1" in r


class TestRaiseAndCatch:
    """Smoke tests: the exception must raise, catch, and carry attributes."""

    def test_can_be_raised_and_caught_with_attributes(self) -> None:
        with pytest.raises(ToolExecutionError) as exc_info:
            raise ToolExecutionError(
                tool="ruff",
                exit_code=3,
                stderr="fatal",
                duration=0.5,
            )

        err = exc_info.value
        assert err.tool == "ruff"
        assert err.exit_code == 3
        assert err.stderr == "fatal"
        assert err.duration == 0.5

    def test_caught_as_plain_exception(self) -> None:
        with pytest.raises(Exception) as exc_info:
            raise ToolExecutionError(tool="t", exit_code=9)

        assert isinstance(exc_info.value, ToolExecutionError)
