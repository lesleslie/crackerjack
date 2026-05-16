from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from crackerjack.errors import (
    CrackerjackError,
    ErrorCode,
    ExecutionError,
    FileError,
    check_command_result,
    check_file_exists,
    format_error_report,
    handle_error,
)


def test_handle_error_no_exit() -> None:
    console = MagicMock()
    error = CrackerjackError(message="boom", error_code=ErrorCode.UNKNOWN_ERROR)
    handle_error(error, console=console, exit_on_error=False)
    console.print.assert_called()


def test_check_file_exists_raises(tmp_path) -> None:
    missing = tmp_path / "missing.txt"
    with pytest.raises(FileError):
        check_file_exists(missing, "missing file")


def test_check_command_result_raises() -> None:
    result = SimpleNamespace(returncode=1, stderr="nope")
    with pytest.raises(ExecutionError):
        check_command_result(result, "cmd", "failed")


def test_format_error_report() -> None:
    error = CrackerjackError(message="oops", error_code=ErrorCode.UNKNOWN_ERROR)
    assert format_error_report(error) == "Error 9001: oops"


class TestErrorCodeEnumValues:
    """Tests for ErrorCode enum values."""

    def test_error_code_config_file_not_found(self):
        """Verify ErrorCode.CONFIG_FILE_NOT_FOUND has correct value."""
        assert ErrorCode.CONFIG_FILE_NOT_FOUND.value == 1001

    def test_error_code_config_parse_error(self):
        """Verify ErrorCode.CONFIG_PARSE_ERROR has correct value."""
        assert ErrorCode.CONFIG_PARSE_ERROR.value == 1002

    def test_error_code_invalid_config(self):
        """Verify ErrorCode.INVALID_CONFIG has correct value."""
        assert ErrorCode.INVALID_CONFIG.value == 1003

    def test_error_code_command_execution_error(self):
        """Verify ErrorCode.COMMAND_EXECUTION_ERROR has correct value."""
        assert ErrorCode.COMMAND_EXECUTION_ERROR.value == 2001

    def test_error_code_command_timeout(self):
        """Verify ErrorCode.COMMAND_TIMEOUT has correct value."""
        assert ErrorCode.COMMAND_TIMEOUT.value == 2002

    def test_error_code_test_execution_error(self):
        """Verify ErrorCode.TEST_EXECUTION_ERROR has correct value."""
        assert ErrorCode.TEST_EXECUTION_ERROR.value == 3001

    def test_error_code_test_failure(self):
        """Verify ErrorCode.TEST_FAILURE has correct value."""
        assert ErrorCode.TEST_FAILURE.value == 3002

    def test_error_code_publish_error(self):
        """Verify ErrorCode.PUBLISH_ERROR has correct value."""
        assert ErrorCode.PUBLISH_ERROR.value == 4002

    def test_error_code_git_command_error(self):
        """Verify ErrorCode.GIT_COMMAND_ERROR has correct value."""
        assert ErrorCode.GIT_COMMAND_ERROR.value == 5001

    def test_error_code_file_not_found(self):
        """Verify ErrorCode.FILE_NOT_FOUND has correct value."""
        assert ErrorCode.FILE_NOT_FOUND.value == 6001

    def test_error_code_permission_error(self):
        """Verify ErrorCode.PERMISSION_ERROR has correct value."""
        assert ErrorCode.PERMISSION_ERROR.value == 6002

    def test_error_code_file_read_error(self):
        """Verify ErrorCode.FILE_READ_ERROR has correct value."""
        assert ErrorCode.FILE_READ_ERROR.value == 6003

    def test_error_code_file_write_error(self):
        """Verify ErrorCode.FILE_WRITE_ERROR has correct value."""
        assert ErrorCode.FILE_WRITE_ERROR.value == 6004

    def test_error_code_network_error(self):
        """Verify ErrorCode.NETWORK_ERROR has correct value."""
        assert ErrorCode.NETWORK_ERROR.value == 8003

    def test_error_code_dependency_error(self):
        """Verify ErrorCode.DEPENDENCY_ERROR has correct value."""
        assert ErrorCode.DEPENDENCY_ERROR.value == 8004

    def test_error_code_resource_error(self):
        """Verify ErrorCode.RESOURCE_ERROR has correct value."""
        assert ErrorCode.RESOURCE_ERROR.value == 8001

    def test_error_code_timeout_error(self):
        """Verify ErrorCode.TIMEOUT_ERROR has correct value."""
        assert ErrorCode.TIMEOUT_ERROR.value == 8002

    def test_error_code_general_error(self):
        """Verify ErrorCode.GENERAL_ERROR has correct value."""
        assert ErrorCode.GENERAL_ERROR.value == 9000

    def test_error_code_unknown_error(self):
        """Verify ErrorCode.UNKNOWN_ERROR has correct value."""
        assert ErrorCode.UNKNOWN_ERROR.value == 9001

    def test_error_code_unexpected_error(self):
        """Verify ErrorCode.UNEXPECTED_ERROR has correct value."""
        assert ErrorCode.UNEXPECTED_ERROR.value == 9999


class TestCrackerjackErrorExtended:
    """Additional tests for CrackerjackError."""

    def test_crackerjack_error_with_all_fields(self):
        """Test CrackerjackError with all fields populated."""
        error = CrackerjackError(
            message="Complete error",
            error_code=ErrorCode.GENERAL_ERROR,
            details={"key": "value"},
            recovery="Do this to fix",
            exit_code=2,
        )
        assert error.message == "Complete error"
        assert error.error_code == ErrorCode.GENERAL_ERROR
        assert error.details == {"key": "value"}
        assert error.recovery == "Do this to fix"
        assert error.exit_code == 2

    def test_crackerjack_error_inheritance(self):
        """Test CrackerjackError is subclass of Exception."""
        assert issubclass(CrackerjackError, Exception)
