import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

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
    check_command_result,
    check_file_exists,
    handle_error,
)


class TestErrorCode:
    def test_error_code_values(self) -> None:
        assert ErrorCode.CONFIG_FILE_NOT_FOUND.value == 1001
        assert ErrorCode.CONFIG_PARSE_ERROR.value == 1002
        assert ErrorCode.COMMAND_EXECUTION_ERROR.value == 2001
        assert ErrorCode.TEST_EXECUTION_ERROR.value == 3001
        assert ErrorCode.BUILD_ERROR.value == 4001
        assert ErrorCode.GIT_COMMAND_ERROR.value == 5001
        assert ErrorCode.FILE_NOT_FOUND.value == 6001
        assert ErrorCode.CODE_CLEANING_ERROR.value == 7001
        assert ErrorCode.UNKNOWN_ERROR.value == 9001
        assert ErrorCode.UNEXPECTED_ERROR.value == 9999

    def test_error_code_names(self) -> None:
        assert ErrorCode.CONFIG_FILE_NOT_FOUND.name == "CONFIG_FILE_NOT_FOUND"
        assert ErrorCode.COMMAND_EXECUTION_ERROR.name == "COMMAND_EXECUTION_ERROR"
        assert ErrorCode.FILE_NOT_FOUND.name == "FILE_NOT_FOUND"


class TestCrackerjackError:
    def test_crackerjack_error_creation_minimal(self) -> None:
        error = CrackerjackError("Test message", ErrorCode.UNKNOWN_ERROR)

        assert error.message == "Test message"
        assert error.error_code == ErrorCode.UNKNOWN_ERROR
        assert error.details is None
        assert error.recovery is None
        assert error.exit_code == 1
        assert str(error) == "Test message"

    def test_crackerjack_error_creation_full(self) -> None:
        error = CrackerjackError(
            message="Full test message",
            error_code=ErrorCode.CONFIG_PARSE_ERROR,
            details="Detailed error information",
            recovery="Recovery steps",
            exit_code=2,
        )

        assert error.message == "Full test message"
        assert error.error_code == ErrorCode.CONFIG_PARSE_ERROR
        assert error.details == "Detailed error information"
        assert error.recovery == "Recovery steps"
        assert error.exit_code == 2

    def test_crackerjack_error_inheritance(self) -> None:
        error = CrackerjackError("Test", ErrorCode.UNKNOWN_ERROR)
        assert isinstance(error, Exception)
        assert isinstance(error, CrackerjackError)


class TestSpecificErrorClasses:
    def test_config_error(self) -> None:
        error = ConfigError("Config failed", ErrorCode.CONFIG_PARSE_ERROR)
        assert isinstance(error, CrackerjackError)
        assert isinstance(error, ConfigError)

    def test_execution_error(self) -> None:
        error = ExecutionError("Execution failed", ErrorCode.COMMAND_EXECUTION_ERROR)
        assert isinstance(error, CrackerjackError)
        assert isinstance(error, ExecutionError)

    def test_test_execution_error(self) -> None:
        error = TestExecutionError("Test failed", ErrorCode.TEST_EXECUTION_ERROR)
        assert isinstance(error, CrackerjackError)
        assert isinstance(error, TestExecutionError)

    def test_publish_error(self) -> None:
        error = PublishError("Publish failed", ErrorCode.PUBLISH_ERROR)
        assert isinstance(error, CrackerjackError)
        assert isinstance(error, PublishError)

    def test_git_error(self) -> None:
        error = GitError("Git failed", ErrorCode.GIT_COMMAND_ERROR)
        assert isinstance(error, CrackerjackError)
        assert isinstance(error, GitError)

    def test_file_error(self) -> None:
        error = FileError("File failed", ErrorCode.FILE_NOT_FOUND)
        assert isinstance(error, CrackerjackError)
        assert isinstance(error, FileError)

    def test_cleaning_error(self) -> None:
        error = CleaningError("Cleaning failed", ErrorCode.CODE_CLEANING_ERROR)
        assert isinstance(error, CrackerjackError)
        assert isinstance(error, CleaningError)

    def test_network_error(self) -> None:
        error = NetworkError("Network failed", ErrorCode.UNKNOWN_ERROR)
        assert isinstance(error, CrackerjackError)
        assert isinstance(error, NetworkError)

    def test_dependency_error(self) -> None:
        error = DependencyError("Dependency failed", ErrorCode.UNKNOWN_ERROR)
        assert isinstance(error, CrackerjackError)
        assert isinstance(error, DependencyError)

    def test_resource_error(self) -> None:
        error = ResourceError("Resource failed", ErrorCode.UNKNOWN_ERROR)
        assert isinstance(error, CrackerjackError)
        assert isinstance(error, ResourceError)

    def test_validation_error(self) -> None:
        error = ValidationError("Validation failed", ErrorCode.UNKNOWN_ERROR)
        assert isinstance(error, CrackerjackError)
        assert isinstance(error, ValidationError)

    def test_timeout_error(self) -> None:
        error = TimeoutError("Timeout occurred", ErrorCode.COMMAND_TIMEOUT)
        assert isinstance(error, CrackerjackError)
        assert isinstance(error, TimeoutError)

    def test_security_error(self) -> None:
        error = SecurityError("Security issue", ErrorCode.UNKNOWN_ERROR)
        assert isinstance(error, CrackerjackError)
        assert isinstance(error, SecurityError)


class TestHandleError:
    @pytest.fixture
    def console(self):
        return Mock(spec=Console)

    @pytest.fixture
    def error(self):
        return CrackerjackError(
            message="Test error message",
            error_code=ErrorCode.CONFIG_PARSE_ERROR,
            details="Detailed error information",
            recovery="Try fixing the configuration",
            exit_code=2,
        )

    def test_handle_error_ai_agent_mode_basic(self, console, error) -> None:
        with patch("sys.exit") as mock_exit:
            handle_error(error, console, ai_agent=True)

            console.print.assert_called_once()
            printed_content = console.print.call_args[0][0]

            assert printed_content.startswith("[json]")
            assert printed_content.endswith("[ / json]")

            json_str = printed_content[6:-7]
            error_data = json.loads(json_str)

            assert error_data["status"] == "error"
            assert error_data["error_code"] == "CONFIG_PARSE_ERROR"
            assert error_data["code"] == 1002
            assert error_data["message"] == "Test error message"
            assert error_data["recovery"] == "Try fixing the configuration"

            mock_exit.assert_called_once_with(2)

    def test_handle_error_ai_agent_mode_verbose(self, console, error) -> None:
        with patch("sys.exit"):
            handle_error(error, console, verbose=True, ai_agent=True)

            console.print.assert_called_once()
            printed_content = console.print.call_args[0][0]

            json_str = printed_content[6:-7]
            error_data = json.loads(json_str)

            assert "details" in error_data
            assert error_data["details"] == "Detailed error information"

    def test_handle_error_ai_agent_mode_no_details(self, console) -> None:
        error_no_details = CrackerjackError(
            message="Simple error",
            error_code=ErrorCode.UNKNOWN_ERROR,
        )

        with patch("sys.exit"):
            handle_error(error_no_details, console, verbose=True, ai_agent=True)

            printed_content = console.print.call_args[0][0]
            json_str = printed_content[6:-7]
            error_data = json.loads(json_str)

            assert "details" not in error_data
            assert "recovery" not in error_data

    def test_handle_error_normal_mode_basic(self, console, error) -> None:
        with patch("sys.exit") as mock_exit:
            handle_error(error, console, verbose=False)

            console.print.assert_called_once()

            call_args = console.print.call_args[0][0]

            from rich.panel import Panel

            assert isinstance(call_args, Panel)

            mock_exit.assert_called_once_with(2)

    def test_handle_error_normal_mode_verbose(self, console, error) -> None:
        with patch("sys.exit"):
            handle_error(error, console, verbose=True)

            console.print.assert_called_once()

            call_args = console.print.call_args[0][0]

            from rich.panel import Panel

            assert isinstance(call_args, Panel)

    def test_handle_error_no_exit(self, console, error) -> None:
        with patch("sys.exit") as mock_exit:
            handle_error(error, console, exit_on_error=False)

            console.print.assert_called_once()
            mock_exit.assert_not_called()

    def test_handle_error_no_recovery(self, console) -> None:
        error_no_recovery = CrackerjackError(
            message="Error without recovery",
            error_code=ErrorCode.UNKNOWN_ERROR,
        )

        with patch("sys.exit"):
            handle_error(error_no_recovery, console)

            console.print.assert_called_once()

    def test_handle_error_no_details_verbose(self, console) -> None:
        error_no_details = CrackerjackError(
            message="Error without details",
            error_code=ErrorCode.UNKNOWN_ERROR,
        )

        with patch("sys.exit"):
            handle_error(error_no_details, console, verbose=True)

            console.print.assert_called_once()


class TestCheckFileExists:
    @pytest.fixture
    def temp_dir(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            yield Path(temp_dir)

    def test_check_file_exists_success(self, temp_dir) -> None:
        test_file = temp_dir / "test_file.txt"
        test_file.write_text("test content")

        check_file_exists(test_file, "File should exist")

    def test_check_file_exists_failure(self, temp_dir) -> None:
        non_existent_file = temp_dir / "non_existent.txt"

        with pytest.raises(FileError) as exc_info:
            check_file_exists(non_existent_file, "Custom error message")

        assert exc_info.value.message == "Custom error message"
        assert exc_info.value.error_code == ErrorCode.FILE_NOT_FOUND
        assert str(non_existent_file) in exc_info.value.details
        assert "Check the file path" in exc_info.value.recovery

    def test_check_file_exists_directory(self, temp_dir) -> None:
        test_dir = temp_dir / "test_directory"
        test_dir.mkdir()

        check_file_exists(test_dir, "Directory should exist")


class TestCheckCommandResult:
    def test_check_command_result_success(self) -> None:
        result = Mock()
        result.returncode = 0

        check_command_result(result, "test - command", "Command should succeed")

    def test_check_command_result_failure_basic(self) -> None:
        result = Mock()
        result.returncode = 1
        result.stderr = ""

        with pytest.raises(ExecutionError) as exc_info:
            check_command_result(result, "test - command", "Command failed")

        assert exc_info.value.message == "Command failed"
        assert exc_info.value.error_code == ErrorCode.COMMAND_EXECUTION_ERROR
        assert "test - command" in exc_info.value.details
        assert "return code 1" in exc_info.value.details
        assert exc_info.value.recovery is None

    def test_check_command_result_failure_with_stderr(self) -> None:
        result = Mock()
        result.returncode = 2
        result.stderr = "Error: command not found"

        with pytest.raises(ExecutionError) as exc_info:
            check_command_result(result, "missing - command", "Command not found")

        assert "return code 2" in exc_info.value.details
        assert "Error: command not found" in exc_info.value.details

    def test_check_command_result_custom_error_code(self) -> None:
        result = Mock()
        result.returncode = 1
        result.stderr = ""

        with pytest.raises(ExecutionError) as exc_info:
            check_command_result(
                result,
                "git - command",
                "Git failed",
                error_code=ErrorCode.GIT_COMMAND_ERROR,
            )

        assert exc_info.value.error_code == ErrorCode.GIT_COMMAND_ERROR

    def test_check_command_result_with_recovery(self) -> None:
        result = Mock()
        result.returncode = 1
        result.stderr = ""

        with pytest.raises(ExecutionError) as exc_info:
            check_command_result(
                result,
                "test - command",
                "Command failed",
                recovery="Try running with sudo",
            )

        assert exc_info.value.recovery == "Try running with sudo"

    def test_check_command_result_none_returncode(self) -> None:
        class SimpleResult:
            pass

        result = SimpleResult()

        check_command_result(result, "test - command", "Command succeeded")

    def test_check_command_result_no_stderr(self) -> None:
        result = Mock()
        result.returncode = 1

        with pytest.raises(ExecutionError) as exc_info:
            check_command_result(result, "test - command", "Command failed")

        assert "test - command" in exc_info.value.details
        assert "return code 1" in exc_info.value.details


class TestErrorCodeCoverage:
    def test_all_config_error_codes(self) -> None:
        assert ErrorCode.INVALID_CONFIG.value == 1003
        assert ErrorCode.MISSING_CONFIG_FIELD.value == 1004

    def test_all_execution_error_codes(self) -> None:
        assert ErrorCode.COMMAND_TIMEOUT.value == 2002
        assert ErrorCode.EXTERNAL_TOOL_ERROR.value == 2003
        assert ErrorCode.PDM_INSTALL_ERROR.value == 2004
        assert ErrorCode.PRE_COMMIT_ERROR.value == 2005

    def test_all_test_error_codes(self) -> None:
        assert ErrorCode.TEST_FAILURE.value == 3002
        assert ErrorCode.BENCHMARK_REGRESSION.value == 3003

    def test_all_build_error_codes(self) -> None:
        assert ErrorCode.VERSION_BUMP_ERROR.value == 4003
        assert ErrorCode.AUTHENTICATION_ERROR.value == 4004

    def test_all_git_error_codes(self) -> None:
        assert ErrorCode.PULL_REQUEST_ERROR.value == 5002
        assert ErrorCode.COMMIT_ERROR.value == 5003

    def test_all_file_error_codes(self) -> None:
        assert ErrorCode.PERMISSION_ERROR.value == 6002
        assert ErrorCode.FILE_READ_ERROR.value == 6003
        assert ErrorCode.FILE_WRITE_ERROR.value == 6004
        assert ErrorCode.FILE_TOO_LARGE.value == 6005

    def test_all_formatting_error_codes(self) -> None:
        assert ErrorCode.FORMATTING_ERROR.value == 7002

    def test_all_general_error_codes(self) -> None:
        assert ErrorCode.NOT_IMPLEMENTED.value == 9002
