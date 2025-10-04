"""Unit tests for command validation in CLI facade.

Tests the validate_command function to ensure:
1. Valid commands are accepted
2. Invalid commands (flags, unknown) are rejected
3. --ai-fix flag misuse is caught
4. Proper error messages are returned
"""

import pytest

from crackerjack.cli.facade import validate_command


class TestCommandValidation:
    """Test suite for validate_command function."""

    def test_valid_command_no_args(self) -> None:
        """Test valid command with no additional arguments."""
        command, args = validate_command("test", "")
        assert command == "test"
        assert args == []

    def test_valid_command_with_args(self) -> None:
        """Test valid command with additional arguments."""
        command, args = validate_command("check", "--verbose")
        assert command == "check"
        assert args == ["--verbose"]

    def test_valid_command_multiple_args(self) -> None:
        """Test valid command with multiple arguments."""
        command, args = validate_command("lint", "--verbose --fix")
        assert command == "lint"
        assert args == ["--verbose", "--fix"]

    @pytest.mark.parametrize(
        "valid_command",
        ["test", "lint", "check", "format", "security", "complexity", "all"],
    )
    def test_all_valid_commands(self, valid_command: str) -> None:
        """Test all valid semantic commands are accepted."""
        command, args = validate_command(valid_command, "")
        assert command == valid_command
        assert args == []

    def test_invalid_command_double_dash(self) -> None:
        """Test that commands starting with -- are rejected."""
        with pytest.raises(ValueError) as exc_info:
            validate_command("--ai-fix", "-t")

        error_msg = str(exc_info.value)
        assert "Invalid command: '--ai-fix'" in error_msg
        assert "Commands should be semantic" in error_msg
        assert "ai_agent_mode=True" in error_msg

    def test_invalid_command_single_dash(self) -> None:
        """Test that commands starting with - are rejected."""
        with pytest.raises(ValueError) as exc_info:
            validate_command("-t", "")

        error_msg = str(exc_info.value)
        assert "Invalid command: '-t'" in error_msg
        assert "Commands should be semantic" in error_msg

    def test_unknown_command(self) -> None:
        """Test that unknown semantic commands are rejected."""
        with pytest.raises(ValueError) as exc_info:
            validate_command("unknown", "")

        error_msg = str(exc_info.value)
        assert "Unknown command: 'unknown'" in error_msg
        assert "Valid commands:" in error_msg
        assert "test" in error_msg  # Should list valid commands

    def test_ai_fix_in_args_rejected(self) -> None:
        """Test that --ai-fix in args parameter is rejected."""
        with pytest.raises(ValueError) as exc_info:
            validate_command("test", "--ai-fix")

        error_msg = str(exc_info.value)
        assert "Do not pass --ai-fix in args parameter" in error_msg
        assert "ai_agent_mode=True" in error_msg

    def test_ai_fix_in_args_with_other_args(self) -> None:
        """Test --ai-fix rejection even when mixed with other args."""
        with pytest.raises(ValueError) as exc_info:
            validate_command("test", "--verbose --ai-fix --debug")

        error_msg = str(exc_info.value)
        assert "Do not pass --ai-fix in args parameter" in error_msg

    def test_empty_command_rejected(self) -> None:
        """Test that empty command is rejected."""
        with pytest.raises(ValueError) as exc_info:
            validate_command("", "")

        error_msg = str(exc_info.value)
        assert "Unknown command: ''" in error_msg

    def test_case_sensitive_commands(self) -> None:
        """Test that commands are case-sensitive."""
        with pytest.raises(ValueError) as exc_info:
            validate_command("TEST", "")  # Should be "test"

        error_msg = str(exc_info.value)
        assert "Unknown command: 'TEST'" in error_msg

    def test_whitespace_handling(self) -> None:
        """Test proper whitespace handling in args."""
        command, args = validate_command("test", "  --verbose   --debug  ")
        assert command == "test"
        assert args == ["--verbose", "--debug"]

    def test_args_none_handled(self) -> None:
        """Test that None args are handled safely (converted to empty list)."""
        # None should be gracefully converted to empty string -> empty list
        command, args = validate_command("test", None)
        assert command == "test"
        assert args == []

    def test_command_none_rejected(self) -> None:
        """Test that None command is rejected with clear error."""
        with pytest.raises(ValueError) as exc_info:
            validate_command(None, "")  # type: ignore[arg-type]

        error_msg = str(exc_info.value)
        assert "Command cannot be None" in error_msg

    def test_shell_quoted_arguments(self) -> None:
        """Test that shell-style quoted arguments are parsed correctly."""
        command, args = validate_command("test", '--msg "hello world"')
        assert command == "test"
        assert args == ["--msg", "hello world"]  # Should be single arg, not split


class TestValidationEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_numeric_command(self) -> None:
        """Test that numeric 'commands' are rejected."""
        with pytest.raises(ValueError):
            validate_command("123", "")

    def test_special_chars_in_command(self) -> None:
        """Test commands with special characters are rejected."""
        with pytest.raises(ValueError):
            validate_command("test!", "")

    def test_very_long_args(self) -> None:
        """Test handling of very long argument strings."""
        long_args = " ".join([f"--arg{i}" for i in range(100)])
        command, args = validate_command("test", long_args)
        assert command == "test"
        assert len(args) == 100

    def test_ai_fix_case_sensitivity(self) -> None:
        """Test that --ai-fix detection is case-sensitive."""
        # --AI-FIX should NOT trigger the error (case-sensitive check)
        command, args = validate_command("test", "--AI-FIX")
        assert command == "test"
        assert args == ["--AI-FIX"]

        # But --ai-fix should trigger the error
        with pytest.raises(ValueError):
            validate_command("test", "--ai-fix")


class TestValidationReturnTypes:
    """Test return type consistency."""

    def test_return_type_is_tuple(self) -> None:
        """Test that return type is always a tuple."""
        result = validate_command("test", "")
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_command_is_string(self) -> None:
        """Test that returned command is always a string."""
        command, _ = validate_command("test", "--verbose")
        assert isinstance(command, str)
        assert command == "test"

    def test_args_is_list(self) -> None:
        """Test that returned args is always a list."""
        _, args = validate_command("test", "--verbose")
        assert isinstance(args, list)
        assert all(isinstance(arg, str) for arg in args)


class TestValidationDocstring:
    """Test that docstring examples work correctly."""

    def test_docstring_example_1(self) -> None:
        """Test first docstring example."""
        result = validate_command("test", "")
        assert result == ("test", [])

    def test_docstring_example_2(self) -> None:
        """Test second docstring example."""
        result = validate_command("check", "--verbose")
        assert result == ("check", ["--verbose"])

    def test_docstring_example_3_raises(self) -> None:
        """Test third docstring example raises ValueError."""
        with pytest.raises(ValueError):
            validate_command("--ai-fix", "-t")
