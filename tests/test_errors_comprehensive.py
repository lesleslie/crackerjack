from pathlib import Path

import pytest

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
)


class TestErrorCode:
    def test_error_code_values(self) -> None:
        assert ErrorCode.CONFIG_FILE_NOT_FOUND.value == 1001
        assert ErrorCode.COMMAND_EXECUTION_ERROR.value == 2001
        assert ErrorCode.TEST_EXECUTION_ERROR.value == 3001
        assert ErrorCode.PUBLISH_ERROR.value == 4002
        assert ErrorCode.GIT_COMMAND_ERROR.value == 5001
        assert ErrorCode.FILE_NOT_FOUND.value == 6001
        assert ErrorCode.CODE_CLEANING_ERROR.value == 7001

    def test_error_code_enum_membership(self) -> None:
        all_codes = list(ErrorCode)
        assert len(all_codes) >= 20

        assert ErrorCode.CONFIG_FILE_NOT_FOUND in all_codes
        assert ErrorCode.COMMAND_EXECUTION_ERROR in all_codes
        assert ErrorCode.TEST_EXECUTION_ERROR in all_codes

    def test_error_code_string_representation(self) -> None:
        assert str(ErrorCode.CONFIG_FILE_NOT_FOUND) == "ErrorCode.CONFIG_FILE_NOT_FOUND"
        assert (
            str(ErrorCode.COMMAND_EXECUTION_ERROR)
            == "ErrorCode.COMMAND_EXECUTION_ERROR"
        )


class TestCrackerjackError:
    def test_basic_error_creation(self) -> None:
        error = CrackerjackError("Test error message", ErrorCode.UNKNOWN_ERROR)

        assert str(error) == "Test error message"
        assert error.message == "Test error message"
        assert error.error_code == ErrorCode.UNKNOWN_ERROR
        assert error.details is None

    def test_error_with_all_parameters(self) -> None:
        details = "file: test.py, line: 42"
        recovery = "Try fixing the configuration"

        error = CrackerjackError(
            message="Configuration error",
            error_code=ErrorCode.CONFIG_FILE_NOT_FOUND,
            details=details,
            recovery=recovery,
            exit_code=2,
        )

        assert error.message == "Configuration error"
        assert error.error_code == ErrorCode.CONFIG_FILE_NOT_FOUND
        assert error.details == details
        assert error.recovery == recovery
        assert error.exit_code == 2

    def test_error_inheritance(self) -> None:
        error = CrackerjackError("Test error", ErrorCode.UNKNOWN_ERROR)

        assert isinstance(error, Exception)
        assert isinstance(error, CrackerjackError)

    def test_error_string_representation(self) -> None:
        error = CrackerjackError("Test message", ErrorCode.UNKNOWN_ERROR)
        assert str(error) == "Test message"

    def test_error_repr(self) -> None:
        error = CrackerjackError("Test message", ErrorCode.CONFIG_FILE_NOT_FOUND)
        repr_str = repr(error)

        assert "CrackerjackError" in repr_str
        assert "Test message" in repr_str

    def test_error_with_none_details(self) -> None:
        error = CrackerjackError("Test", ErrorCode.UNKNOWN_ERROR, details=None)
        assert error.details is None

    def test_error_with_string_details(self) -> None:
        error = CrackerjackError(
            "Test", ErrorCode.UNKNOWN_ERROR, details="Some details"
        )
        assert error.details == "Some details"


class TestConfigError:
    def test_config_error_creation(self) -> None:
        error = ConfigError(
            "Configuration file not found", ErrorCode.CONFIG_FILE_NOT_FOUND
        )

        assert isinstance(error, CrackerjackError)
        assert error.message == "Configuration file not found"
        assert error.error_code == ErrorCode.CONFIG_FILE_NOT_FOUND

    def test_config_error_with_details(self) -> None:
        error = ConfigError(
            "Invalid configuration", ErrorCode.INVALID_CONFIG, details="config details"
        )

        assert error.details == "config details"
        assert error.error_code == ErrorCode.INVALID_CONFIG

    def test_config_error_inheritance(self) -> None:
        error = ConfigError("Test config error", ErrorCode.CONFIG_PARSE_ERROR)

        assert isinstance(error, CrackerjackError)
        assert isinstance(error, Exception)


class TestExecutionErrorClass:
    def test_execution_error_creation(self) -> None:
        error = ExecutionError(
            "Command execution failed", ErrorCode.COMMAND_EXECUTION_ERROR
        )

        assert isinstance(error, CrackerjackError)
        assert error.message == "Command execution failed"
        assert error.error_code == ErrorCode.COMMAND_EXECUTION_ERROR

    def test_execution_error_with_command(self) -> None:
        error = ExecutionError(
            "Ruff check failed",
            ErrorCode.EXTERNAL_TOOL_ERROR,
            details="ruff command details",
        )

        assert error.details == "ruff command details"
        assert error.error_code == ErrorCode.EXTERNAL_TOOL_ERROR


class TestTestExecutionError:
    def test_test_execution_error_creation(self) -> None:
        error = TestExecutionError("Test suite failed")

        assert isinstance(error, CrackerjackError)
        assert error.message == "Test suite failed"
        assert error.error_code == ErrorCode.TEST_EXECUTION_ERROR

    def test_test_execution_error_with_details(self) -> None:
        details = {
            "failed_tests": ["test_feature", "test_integration"],
            "coverage": 45.2,
            "duration": 120.5,
        }
        error = TestExecutionError("Test failures detected", details=details)

        assert error.details == details
        assert error.error_code == ErrorCode.TEST_EXECUTION_ERROR


class TestPublishError:
    def test_publish_error_creation(self) -> None:
        error = PublishError("Failed to publish to PyPI")

        assert isinstance(error, CrackerjackError)
        assert error.message == "Failed to publish to PyPI"
        assert error.error_code == ErrorCode.PUBLISH_ERROR

    def test_publish_error_with_version(self) -> None:
        details = {"version": "1.2.3", "repository": "pypi"}
        suggestion = "Check your PyPI credentials"

        error = PublishError(
            "Version already exists",
            details=details,
            recovery=suggestion,
        )

        assert error.details == details
        assert error.recovery == suggestion


class TestGitError:
    def test_git_error_creation(self) -> None:
        error = GitError("Git commit failed")

        assert isinstance(error, CrackerjackError)
        assert error.message == "Git commit failed"
        assert error.error_code == ErrorCode.GIT_COMMAND_ERROR

    def test_git_error_with_command(self) -> None:
        details = {"command": "git commit - m 'test'", "status": "dirty"}
        error = GitError("Repository has uncommitted changes", details=details)

        assert error.details == details
        assert error.error_code == ErrorCode.GIT_COMMAND_ERROR


class TestFileError:
    def test_file_error_creation(self) -> None:
        error = FileError("File not found")

        assert isinstance(error, CrackerjackError)
        assert error.message == "File not found"
        assert error.error_code == ErrorCode.FILE_NOT_FOUND

    def test_file_error_with_path(self) -> None:
        file_path = Path("src / missing_file.py")
        details = {"file_path": str(file_path), "operation": "read"}

        error = FileError("Cannot read file", details=details)

        assert error.details == details
        assert error.error_code == ErrorCode.FILE_NOT_FOUND


class TestCleaningError:
    def test_cleaning_error_creation(self) -> None:
        error = CleaningError("Code cleaning failed")

        assert isinstance(error, CrackerjackError)
        assert error.message == "Code cleaning failed"
        assert error.error_code == ErrorCode.EXTERNAL_TOOL_ERROR

    def test_cleaning_error_with_files(self) -> None:
        details = {
            "failed_files": ["src / file1.py", "src / file2.py"],
            "cleaned_files": 5,
            "total_files": 7,
        }

        error = CleaningError("Some files failed to clean", details=details)

        assert error.details == details
        assert error.error_code == ErrorCode.EXTERNAL_TOOL_ERROR


class TestNetworkError:
    def test_network_error_creation(self) -> None:
        error = NetworkError("Connection timeout")

        assert isinstance(error, CrackerjackError)
        assert error.message == "Connection timeout"
        assert error.error_code == ErrorCode.NETWORK_ERROR

    def test_network_error_with_url(self) -> None:
        details = {"url": "https: // pypi.org", "timeout": 30, "status_code": 408}
        suggestion = "Check your internet connection"

        error = NetworkError(
            "Request timeout",
            details=details,
            recovery=suggestion,
        )

        assert error.details == details
        assert error.recovery == suggestion


class TestDependencyError:
    def test_dependency_error_creation(self) -> None:
        error = DependencyError("Missing dependency")

        assert isinstance(error, CrackerjackError)
        assert error.message == "Missing dependency"
        assert error.error_code == ErrorCode.DEPENDENCY_ERROR

    def test_dependency_error_with_package(self) -> None:
        details = {
            "package": "missing - package",
            "version": " >= 1.0.0",
            "available_version": None,
        }
        recovery = "Install the required package with: pip install missing - package"

        error = DependencyError(
            "Package not found",
            details=details,
            recovery=recovery,
        )

        assert error.details == details
        assert error.recovery == recovery


class TestResourceError:
    def test_resource_error_creation(self) -> None:
        error = ResourceError("Insufficient memory")

        assert isinstance(error, CrackerjackError)
        assert error.message == "Insufficient memory"
        assert error.error_code == ErrorCode.RESOURCE_ERROR

    def test_resource_error_with_metrics(self) -> None:
        details = {
            "memory_used": "8GB",
            "memory_available": "2GB",
            "cpu_usage": "95 % ",
        }

        error = ResourceError("System overload", details=details)

        assert error.details == details
        assert error.error_code == ErrorCode.RESOURCE_ERROR


class TestValidationError:
    def test_validation_error_creation(self) -> None:
        error = ValidationError("Invalid input")

        assert isinstance(error, CrackerjackError)
        assert error.message == "Invalid input"
        assert error.error_code == ErrorCode.VALIDATION_ERROR

    def test_validation_error_with_field(self) -> None:
        details = {
            "field": "version",
            "value": "invalid.version",
            "expected_format": "semantic version (x.y.z)",
        }

        error = ValidationError("Invalid version format", details=details)

        assert error.details == details
        assert error.error_code == ErrorCode.VALIDATION_ERROR


class TestTimeoutError:
    def test_timeout_error_creation(self) -> None:
        error = TimeoutError("Operation timed out")

        assert isinstance(error, CrackerjackError)
        assert error.message == "Operation timed out"
        assert error.error_code == ErrorCode.TIMEOUT_ERROR

    def test_timeout_error_with_duration(self) -> None:
        details = {
            "operation": "test execution",
            "timeout_limit": 300,
            "actual_duration": 450,
        }
        suggestion = "Increase timeout limit or optimize the operation"

        error = TimeoutError(
            "Test execution exceeded time limit",
            details=details,
            recovery=suggestion,
        )

        assert error.details == details
        assert error.recovery == suggestion


class TestSecurityError:
    def test_security_error_creation(self) -> None:
        error = SecurityError("Security violation detected")

        assert isinstance(error, CrackerjackError)
        assert error.message == "Security violation detected"
        assert error.error_code == ErrorCode.SECURITY_ERROR

    def test_security_error_with_threat(self) -> None:
        details = {
            "threat_type": "hardcoded_secret",
            "file": "config.py",
            "line": 42,
            "pattern": "api_key = '...'",
        }
        suggestion = "Remove hardcoded secrets and use environment variables"

        error = SecurityError(
            "Hardcoded secret detected",
            details=str(details),
            recovery=suggestion,
        )

        assert str(error.details) == str(details)
        assert error.recovery == suggestion


class TestErrorIntegration:
    def test_error_chain(self) -> None:
        original_error = FileError("File not found")
        chained_error = ExecutionError(
            "Cannot process file",
            details={"original_error": str(original_error)},
        )

        assert isinstance(original_error, CrackerjackError)
        assert isinstance(chained_error, CrackerjackError)
        assert str(original_error) in str(chained_error.details["original_error"])

    def test_error_context_manager(self):
        with pytest.raises(ValidationError) as exc_info:
            raise ValidationError("Test validation error")

        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
        assert "Test validation error" in str(exc_info.value)

    def test_multiple_error_types(self) -> None:
        errors = [
            ConfigError("Config issue"),
            ExecutionError("Execution issue"),
            TestExecutionError("Test issue"),
            PublishError("Publish issue"),
            GitError("Git issue"),
        ]

        for error in errors:
            assert isinstance(error, CrackerjackError)
            assert isinstance(error, Exception)
            assert error.error_code is not None

    def test_error_with_complex_details(self) -> None:
        complex_details = {
            "timestamp": "2024 - 01 - 01T12: 00: 00Z",
            "environment": {
                "python_version": "3.13",
                "platform": "linux",
                "working_directory": " / project",
            },
            "context": {
                "operation": "test_execution",
                "phase": "setup",
                "step": 3,
            },
            "metrics": {
                "memory_usage": "256MB",
                "duration": 15.5,
                "cpu_time": 12.3,
            },
        }

        error = ExecutionError(
            "Complex operation failed",
            details=complex_details,
            recovery="Check the environment setup and resource availability",
        )

        assert error.details == complex_details
        assert error.recovery is not None
        assert error.error_code == ErrorCode.COMMAND_EXECUTION_ERROR
