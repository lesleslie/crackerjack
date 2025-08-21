"""Consolidated error testing module."""

import typing as t
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from crackerjack.errors import (
    CleaningError,
    ConfigError,
    CrackerjackError,
    DependencyError,
    ErrorCode,
    ExecutionError,
    FileError,
    GitError,
    NetworkError,
    PublishError,
    ResourceError,
    SecurityError,
    TestExecutionError,
    TimeoutError,
    ValidationError,
    format_error_report,
    handle_error,
)


class TestErrorCode:
    """Test error code enumeration."""

    def test_error_code_values(self) -> None:
        """Test that error codes have correct values."""
        assert ErrorCode.CONFIG_FILE_NOT_FOUND.value == 1001
        assert ErrorCode.COMMAND_EXECUTION_ERROR.value == 2001
        assert ErrorCode.TEST_EXECUTION_ERROR.value == 3001
        assert ErrorCode.PUBLISH_ERROR.value == 4002
        assert ErrorCode.GIT_COMMAND_ERROR.value == 5001

    def test_error_code_uniqueness(self) -> None:
        """Test that all error codes are unique."""
        values = [code.value for code in ErrorCode]
        assert len(values) == len(set(values))


class TestCrackerjackError:
    """Test base CrackerjackError class."""

    def test_base_error_class(self) -> None:
        """Test base error class functionality."""
        error = CrackerjackError(
            message="Test error",
            error_code=ErrorCode.UNKNOWN_ERROR,
            details="Test details",
            recovery="Test recovery",
            exit_code=2,
        )
        assert error.message == "Test error"
        assert error.error_code == ErrorCode.UNKNOWN_ERROR
        assert error.details == "Test details"
        assert error.recovery == "Test recovery"
        assert error.exit_code == 2
        assert str(error) == "Test error"

    def test_error_defaults(self) -> None:
        """Test error class defaults."""
        error = CrackerjackError(message="Test error")
        assert error.message == "Test error"
        assert error.error_code == ErrorCode.UNKNOWN_ERROR
        assert error.details is None
        assert error.recovery is None
        assert error.exit_code == 1

    def test_error_repr(self) -> None:
        """Test error representation."""
        error = CrackerjackError(message="Test error", error_code=ErrorCode.CONFIG_ERROR)
        repr_str = repr(error)
        assert "CrackerjackError" in repr_str
        assert "Test error" in repr_str


class TestSpecializedErrors:
    """Test specialized error classes."""

    def test_specialized_error_classes(self) -> None:
        """Test that specialized error classes inherit properly."""
        error_classes = [
            ConfigError,
            ExecutionError,
            TestExecutionError,
            PublishError,
            GitError,
            FileError,
            CleaningError,
            DependencyError,
            NetworkError,
            ResourceError,
            SecurityError,
            TimeoutError,
            ValidationError,
        ]
        for error_class in error_classes:
            error = error_class(message="Test error")
            assert isinstance(error, CrackerjackError)
            assert error.message == "Test error"

    def test_config_error_specifics(self) -> None:
        """Test ConfigError specific behavior."""
        error = ConfigError(
            message="Config file not found",
            error_code=ErrorCode.CONFIG_FILE_NOT_FOUND,
            file_path="/path/to/config",
        )
        assert error.file_path == "/path/to/config"
        assert error.error_code == ErrorCode.CONFIG_FILE_NOT_FOUND

    def test_file_error_specifics(self) -> None:
        """Test FileError specific behavior."""
        error = FileError(
            message="File not found",
            error_code=ErrorCode.FILE_NOT_FOUND,
            file_path="/path/to/file",
        )
        assert error.file_path == "/path/to/file"
        assert error.error_code == ErrorCode.FILE_NOT_FOUND

    def test_execution_error_with_command(self) -> None:
        """Test ExecutionError with command information."""
        error = ExecutionError(
            message="Command failed",
            error_code=ErrorCode.COMMAND_EXECUTION_ERROR,
            command=["pytest", "--fail"],
            exit_code=1,
        )
        assert error.command == ["pytest", "--fail"]
        assert error.exit_code == 1

    def test_git_error_with_repository(self) -> None:
        """Test GitError with repository information."""
        error = GitError(
            message="Git command failed",
            error_code=ErrorCode.GIT_COMMAND_ERROR,
            repository_path="/path/to/repo",
        )
        assert error.repository_path == "/path/to/repo"


class TestErrorHandling:
    """Test error handling utilities."""

    def test_handle_error_function(self) -> None:
        """Test handle_error function."""
        console = Console()
        error = CrackerjackError(message="Test error")
        
        with patch.object(console, "print") as mock_print:
            handle_error(error, console)
            mock_print.assert_called()

    def test_handle_error_with_details(self) -> None:
        """Test handle_error with error details."""
        console = Console()
        error = CrackerjackError(
            message="Test error",
            details="Additional details",
            recovery="Try this fix",
        )
        
        with patch.object(console, "print") as mock_print:
            handle_error(error, console)
            mock_print.assert_called()
            # Verify details and recovery are included
            call_args = [str(call) for call in mock_print.call_args_list]
            assert any("Additional details" in arg for arg in call_args)

    def test_format_error_report(self) -> None:
        """Test format_error_report function."""
        error = CrackerjackError(
            message="Test error",
            error_code=ErrorCode.CONFIG_ERROR,
            details="Error details",
        )
        
        report = format_error_report(error)
        assert isinstance(report, str)
        assert "Test error" in report
        assert "CONFIG_ERROR" in report


class TestErrorIntegration:
    """Test error integration with other components."""

    def test_error_with_pathlib(self) -> None:
        """Test error classes work with pathlib."""
        file_path = Path("/test/path/file.txt")
        error = FileError(
            message="File not found",
            error_code=ErrorCode.FILE_NOT_FOUND,
            file_path=str(file_path),
        )
        assert error.file_path == str(file_path)

    def test_error_chaining(self) -> None:
        """Test error chaining functionality."""
        original_error = ValueError("Original error")
        
        try:
            raise ConfigError(
                message="Config error",
                error_code=ErrorCode.CONFIG_ERROR,
            ) from original_error
        except ConfigError as e:
            assert e.__cause__ is original_error
            assert str(e.__cause__) == "Original error"

    def test_error_context_management(self) -> None:
        """Test error handling in context managers."""
        with pytest.raises(CrackerjackError) as exc_info:
            raise CrackerjackError(message="Context error")
        
        assert exc_info.value.message == "Context error"


class TestErrorRecovery:
    """Test error recovery mechanisms."""

    def test_error_recovery_suggestions(self) -> None:
        """Test that errors provide recovery suggestions."""
        error = ConfigError(
            message="Configuration file is invalid",
            error_code=ErrorCode.CONFIG_VALIDATION_ERROR,
            recovery="Check your pyproject.toml syntax",
        )
        assert error.recovery == "Check your pyproject.toml syntax"

    def test_error_severity_levels(self) -> None:
        """Test different error severity handling."""
        # Test that different error types have appropriate exit codes
        config_error = ConfigError(message="Config error")
        execution_error = ExecutionError(message="Execution error") 
        test_error = TestExecutionError(message="Test error")
        
        # All should inherit the base exit code of 1
        assert config_error.exit_code == 1
        assert execution_error.exit_code == 1
        assert test_error.exit_code == 1


class TestErrorValidation:
    """Test error validation and constraints."""

    def test_error_message_required(self) -> None:
        """Test that error message is required."""
        with pytest.raises(TypeError):
            CrackerjackError()  # Missing required message parameter

    def test_error_code_validation(self) -> None:
        """Test error code validation."""
        error = CrackerjackError(
            message="Test error",
            error_code=ErrorCode.CONFIG_FILE_NOT_FOUND,
        )
        assert isinstance(error.error_code, ErrorCode)

    def test_error_details_optional(self) -> None:
        """Test that error details are optional."""
        error = CrackerjackError(message="Test error")
        assert error.details is None
        
        error_with_details = CrackerjackError(
            message="Test error",
            details="Additional information",
        )
        assert error_with_details.details == "Additional information"