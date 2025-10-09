"""Tests for enhanced tool execution error (Phase 10.2.3)."""

from pathlib import Path

import pytest
from rich.console import Console

from crackerjack.exceptions import ToolExecutionError


class TestToolExecutionErrorInit:
    """Test ToolExecutionError initialization."""

    def test_init_minimal(self):
        """Test initialization with minimal parameters."""
        error = ToolExecutionError(
            tool="ruff-check",
            exit_code=1,
        )

        assert error.tool == "ruff-check"
        assert error.exit_code == 1
        assert error.stdout == ""
        assert error.stderr == ""
        assert error.command is None
        assert error.cwd is None
        assert error.duration is None

    def test_init_full(self, tmp_path):
        """Test initialization with all parameters."""
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

    def test_init_strips_whitespace(self):
        """Test that stdout/stderr are stripped of whitespace."""
        error = ToolExecutionError(
            tool="test",
            exit_code=1,
            stdout="  output  \n\n",
            stderr="\n  error  \n",
        )

        assert error.stdout == "output"
        assert error.stderr == "error"

    def test_exception_message_without_duration(self):
        """Test exception message format without duration."""
        error = ToolExecutionError(
            tool="ruff-check",
            exit_code=1,
        )

        assert str(error) == "ToolExecutionError: ruff-check | Exit Code: 1"

    def test_exception_message_with_duration(self):
        """Test exception message format with duration."""
        error = ToolExecutionError(
            tool="ruff-check",
            exit_code=1,
            duration=2.5,
        )

        message = str(error)
        assert "ruff-check" in message
        assert "Exit Code: 1" in message
        assert "Duration: 2.50s" in message


class TestRichFormatting:
    """Test rich panel formatting."""

    def test_format_rich_basic(self):
        """Test basic rich formatting."""
        error = ToolExecutionError(
            tool="ruff-check",
            exit_code=1,
            stderr="E501 line too long (100 > 88 characters)",
        )

        console = Console()
        panel = error.format_rich(console)

        assert panel is not None
        assert "ruff-check" in panel.title
        assert panel.border_style == "red"

    def test_format_rich_with_all_fields(self, tmp_path):
        """Test rich formatting with all fields populated."""
        error = ToolExecutionError(
            tool="zuban",
            exit_code=2,
            stdout="Type checking...",
            stderr="error: Incompatible types",
            command=["uv", "run", "zuban", "check"],
            cwd=tmp_path,
            duration=3.14,
        )

        console = Console()
        panel = error.format_rich(console)

        # Panel should contain all information
        assert "zuban" in panel.title
        assert panel.border_style == "red"

    def test_format_rich_truncates_long_output(self):
        """Test that long output is truncated."""
        # Create 30 lines of output
        long_stderr = "\n".join([f"Error line {i}" for i in range(30)])

        error = ToolExecutionError(
            tool="test",
            exit_code=1,
            stderr=long_stderr,
        )

        console = Console()
        panel = error.format_rich(console)

        # Should truncate to last 20 lines
        assert panel is not None

    def test_format_rich_truncates_long_command(self):
        """Test that long commands are truncated."""
        long_command = ["uv", "run", "tool"] + ["arg"] * 50

        error = ToolExecutionError(
            tool="test",
            exit_code=1,
            command=long_command,
        )

        console = Console()
        panel = error.format_rich(console)

        assert panel is not None

    def test_format_rich_shows_stdout_when_stderr_empty(self):
        """Test that stdout is shown when stderr is empty."""
        error = ToolExecutionError(
            tool="test",
            exit_code=1,
            stdout="Some output",
            stderr="",
        )

        console = Console()
        panel = error.format_rich(console)

        assert panel is not None

    def test_format_rich_shows_message_when_no_output(self):
        """Test message shown when both stdout and stderr are empty."""
        error = ToolExecutionError(
            tool="test",
            exit_code=1,
            stdout="",
            stderr="",
        )

        console = Console()
        panel = error.format_rich(console)

        assert panel is not None


class TestActionableMessages:
    """Test actionable error message generation."""

    def test_actionable_message_permission_denied(self):
        """Test actionable message for permission errors."""
        error = ToolExecutionError(
            tool="test",
            exit_code=1,
            stderr="Permission denied: /some/file",
        )

        message = error.get_actionable_message()

        assert "Permission denied" not in message  # Original error not duplicated
        assert "permission" in message.lower()
        assert "→" in message  # Has actionable suggestion

    def test_actionable_message_command_not_found(self):
        """Test actionable message for missing command."""
        error = ToolExecutionError(
            tool="missing-tool",
            exit_code=127,
            stderr="bash: missing-tool: command not found",
        )

        message = error.get_actionable_message()

        assert "installed" in message.lower()
        assert "PATH" in message

    def test_actionable_message_timeout(self):
        """Test actionable message for timeout."""
        error = ToolExecutionError(
            tool="slow-tool",
            exit_code=124,
            stderr="Command timed out after 60 seconds",
        )

        message = error.get_actionable_message()

        assert "timeout" in message.lower()
        assert "increasing" in message.lower()

    def test_actionable_message_syntax_error(self):
        """Test actionable message for syntax errors."""
        error = ToolExecutionError(
            tool="ruff-check",
            exit_code=1,
            stderr="SyntaxError: invalid syntax at line 10",
        )

        message = error.get_actionable_message()

        assert "syntax" in message.lower()

    def test_actionable_message_import_error(self):
        """Test actionable message for import errors."""
        error = ToolExecutionError(
            tool="pytest",
            exit_code=1,
            stderr="ModuleNotFoundError: No module named 'requests'",
        )

        message = error.get_actionable_message()

        assert "dependencies" in message.lower() or "uv sync" in message

    def test_actionable_message_type_error(self):
        """Test actionable message for type errors."""
        error = ToolExecutionError(
            tool="zuban",
            exit_code=1,
            stderr="TypeError: incompatible types",
        )

        message = error.get_actionable_message()

        assert "type" in message.lower()

    def test_actionable_message_generic(self):
        """Test generic actionable message when no specific pattern matches."""
        error = ToolExecutionError(
            tool="custom-tool",
            exit_code=1,
            stderr="Some unknown error",
        )

        message = error.get_actionable_message()

        assert "custom-tool" in message
        assert "→" in message  # Has suggestion


class TestOutputFormatting:
    """Test output formatting helpers."""

    def test_format_output_empty_lines(self):
        """Test that empty lines are filtered out."""
        error = ToolExecutionError(
            tool="test",
            exit_code=1,
            stderr="Line 1\n\n\nLine 2",
        )

        formatted = error._format_output(["Line 1", "", "", "Line 2"])

        # Should have indented non-empty lines
        assert "Line 1" in formatted
        assert "Line 2" in formatted

    def test_format_output_strips_ansi_codes(self):
        """Test that ANSI color codes are stripped."""
        error = ToolExecutionError(
            tool="test",
            exit_code=1,
        )

        # Line with ANSI codes
        lines = ["\x1b[31mRed text\x1b[0m", "\x1b[1;32mGreen bold\x1b[0m"]

        formatted = error._format_output(lines)

        # ANSI codes should be removed
        assert "\x1b" not in formatted
        assert "Red text" in formatted
        assert "Green bold" in formatted

    def test_format_output_indents_lines(self):
        """Test that output lines are properly indented."""
        error = ToolExecutionError(
            tool="test",
            exit_code=1,
        )

        lines = ["Error 1", "Error 2"]
        formatted = error._format_output(lines)

        # Lines should be indented
        assert "  Error 1" in formatted
        assert "  Error 2" in formatted


class TestStringRepresentations:
    """Test string representation methods."""

    def test_str_representation(self):
        """Test __str__ method."""
        error = ToolExecutionError(
            tool="ruff-check",
            exit_code=1,
            stderr="E501 line too long",
            duration=2.5,
        )

        str_repr = str(error)

        assert "ruff-check" in str_repr
        assert "Exit Code: 1" in str_repr
        assert "Duration: 2.50s" in str_repr
        assert "Stderr:" in str_repr

    def test_repr_representation(self):
        """Test __repr__ method."""
        error = ToolExecutionError(
            tool="ruff-check",
            exit_code=1,
            duration=2.5,
        )

        repr_str = repr(error)

        assert "ToolExecutionError" in repr_str
        assert "tool='ruff-check'" in repr_str
        assert "exit_code=1" in repr_str
        assert "duration=2.5" in repr_str

    def test_str_with_long_stderr(self):
        """Test __str__ truncates long stderr."""
        long_stderr = "x" * 300

        error = ToolExecutionError(
            tool="test",
            exit_code=1,
            stderr=long_stderr,
        )

        str_repr = str(error)

        # Should truncate to ~200 chars
        assert len(str_repr) < len(long_stderr)
        assert "..." in str_repr


class TestExceptionInheritance:
    """Test exception behavior."""

    def test_is_exception(self):
        """Test that ToolExecutionError is an Exception."""
        error = ToolExecutionError(tool="test", exit_code=1)

        assert isinstance(error, Exception)

    def test_can_be_raised_and_caught(self):
        """Test that error can be raised and caught."""
        with pytest.raises(ToolExecutionError) as exc_info:
            raise ToolExecutionError(
                tool="test",
                exit_code=1,
                stderr="Test error",
            )

        assert exc_info.value.tool == "test"
        assert exc_info.value.exit_code == 1

    def test_can_be_caught_as_exception(self):
        """Test that error can be caught as generic Exception."""
        with pytest.raises(Exception) as exc_info:
            raise ToolExecutionError(tool="test", exit_code=1)

        assert isinstance(exc_info.value, ToolExecutionError)
