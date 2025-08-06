import pytest

from crackerjack.errors import (
    CleaningError,
    ConfigError,
    CrackerjackError,
    ErrorCode,
    ExecutionError,
    FileError,
    GitError,
    PublishError,
    TestExecutionError,
    ValidationError,
)


class TestErrorCode:
    def test_error_code_values(self) -> None:
        assert ErrorCode.CONFIG_FILE_NOT_FOUND.value == 1001
        assert ErrorCode.COMMAND_EXECUTION_ERROR.value == 2001
        assert ErrorCode.TEST_EXECUTION_ERROR.value == 3001
        assert ErrorCode.PUBLISH_ERROR.value == 4002

    def test_error_code_membership(self) -> None:
        all_codes = list(ErrorCode)
        assert len(all_codes) >= 20
        assert ErrorCode.UNKNOWN_ERROR in all_codes


class TestCrackerjackError:
    def test_basic_error_creation(self) -> None:
        error = CrackerjackError("Test error", ErrorCode.UNKNOWN_ERROR)

        assert str(error) == "Test error"
        assert error.message == "Test error"
        assert error.error_code == ErrorCode.UNKNOWN_ERROR
        assert error.exit_code == 1

    def test_error_with_all_params(self) -> None:
        error = CrackerjackError(
            message="Configuration error",
            error_code=ErrorCode.CONFIG_FILE_NOT_FOUND,
            details="file not found details",
            recovery="check the file path",
            exit_code=2,
        )

        assert error.message == "Configuration error"
        assert error.error_code == ErrorCode.CONFIG_FILE_NOT_FOUND
        assert error.details == "file not found details"
        assert error.recovery == "check the file path"
        assert error.exit_code == 2

    def test_error_inheritance(self) -> None:
        error = CrackerjackError("Test", ErrorCode.UNKNOWN_ERROR)
        assert isinstance(error, Exception)


class TestErrorSubclasses:
    def test_config_error(self) -> None:
        error = ConfigError("Config issue", ErrorCode.CONFIG_FILE_NOT_FOUND)
        assert isinstance(error, CrackerjackError)
        assert error.message == "Config issue"

    def test_execution_error(self) -> None:
        error = ExecutionError("Execution issue", ErrorCode.COMMAND_EXECUTION_ERROR)
        assert isinstance(error, CrackerjackError)
        assert error.message == "Execution issue"

    def test_test_execution_error(self) -> None:
        error = TestExecutionError("Test issue", ErrorCode.TEST_EXECUTION_ERROR)
        assert isinstance(error, CrackerjackError)
        assert error.message == "Test issue"

    def test_publish_error(self) -> None:
        error = PublishError("Publish issue", ErrorCode.PUBLISH_ERROR)
        assert isinstance(error, CrackerjackError)
        assert error.message == "Publish issue"

    def test_git_error(self) -> None:
        error = GitError("Git issue", ErrorCode.GIT_COMMAND_ERROR)
        assert isinstance(error, CrackerjackError)
        assert error.message == "Git issue"

    def test_file_error(self) -> None:
        error = FileError("File issue", ErrorCode.FILE_NOT_FOUND)
        assert isinstance(error, CrackerjackError)
        assert error.message == "File issue"

    def test_cleaning_error(self) -> None:
        error = CleaningError("Cleaning issue", ErrorCode.CODE_CLEANING_ERROR)
        assert isinstance(error, CrackerjackError)
        assert error.message == "Cleaning issue"

    def test_validation_error(self) -> None:
        error = ValidationError("Validation issue", ErrorCode.INVALID_CONFIG)
        assert isinstance(error, CrackerjackError)
        assert error.message == "Validation issue"


class TestErrorWithContext:
    def test_error_in_exception_context(self):
        with pytest.raises(ConfigError) as exc_info:
            raise ConfigError("Test config error", ErrorCode.CONFIG_PARSE_ERROR)

        assert exc_info.value.error_code == ErrorCode.CONFIG_PARSE_ERROR
        assert "Test config error" in str(exc_info.value)

    def test_multiple_error_types(self) -> None:
        errors = [
            ConfigError("Config", ErrorCode.CONFIG_FILE_NOT_FOUND),
            ExecutionError("Execution", ErrorCode.COMMAND_EXECUTION_ERROR),
            TestExecutionError("Test", ErrorCode.TEST_EXECUTION_ERROR),
        ]

        for error in errors:
            assert isinstance(error, CrackerjackError)
            assert isinstance(error, Exception)
            assert error.error_code is not None

    def test_error_with_complex_details(self) -> None:
        error = ExecutionError(
            message="Complex operation failed",
            error_code=ErrorCode.COMMAND_EXECUTION_ERROR,
            details="Detailed failure information",
            recovery="Check logs and retry",
            exit_code=5,
        )

        assert error.details == "Detailed failure information"
        assert error.recovery == "Check logs and retry"
        assert error.exit_code == 5
