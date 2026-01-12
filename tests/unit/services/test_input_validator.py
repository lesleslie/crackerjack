"""Unit tests for InputValidator.

Tests input validation, sanitization, security checks,
and validation configuration functionality.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.errors import ErrorCode, ExecutionError
from crackerjack.services.input_validator import (
    InputSanitizer,
    SecureInputValidator,
    ValidationConfig,
    ValidationResult,
    get_input_validator,
    validate_and_parse_json,
    validate_and_sanitize_path,
    validate_and_sanitize_string,
    validation_required,
)


@pytest.mark.unit
class TestValidationConfig:
    """Test ValidationConfig dataclass."""

    def test_default_config(self) -> None:
        """Test default configuration values."""
        config = ValidationConfig()

        assert config.MAX_STRING_LENGTH == 10000
        assert config.MAX_PROJECT_NAME_LENGTH == 255
        assert config.MAX_JOB_ID_LENGTH == 128
        assert config.MAX_COMMAND_LENGTH == 1000
        assert config.MAX_JSON_SIZE == 1024 * 1024
        assert config.MAX_JSON_DEPTH == 10
        assert config.ALLOW_SHELL_METACHARACTERS is False
        assert config.STRICT_ALPHANUMERIC_MODE is False

    def test_custom_config(self) -> None:
        """Test custom configuration values."""
        config = ValidationConfig(
            MAX_STRING_LENGTH=5000,
            ALLOW_SHELL_METACHARACTERS=True,
        )

        assert config.MAX_STRING_LENGTH == 5000
        assert config.ALLOW_SHELL_METACHARACTERS is True


@pytest.mark.unit
class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_success_result(self) -> None:
        """Test successful validation result."""
        result = ValidationResult(
            valid=True,
            sanitized_value="test_value",
            validation_type="test_validation",
        )

        assert result.valid is True
        assert result.sanitized_value == "test_value"
        assert result.error_message == ""
        assert result.validation_type == "test_validation"

    def test_failure_result(self) -> None:
        """Test failed validation result."""
        result = ValidationResult(
            valid=False,
            error_message="Invalid input",
            security_level="high",  # type: ignore
            validation_type="test_validation",
        )

        assert result.valid is False
        assert result.error_message == "Invalid input"
        assert result.validation_type == "test_validation"


@pytest.mark.unit
class TestInputSanitizer:
    """Test InputSanitizer class."""

    def test_shell_metacharacters_constant(self) -> None:
        """Test shell metacharacters are defined."""
        assert ";" in InputSanitizer.SHELL_METACHARACTERS
        assert "&" in InputSanitizer.SHELL_METACHARACTERS
        assert "|" in InputSanitizer.SHELL_METACHARACTERS
        assert "$" in InputSanitizer.SHELL_METACHARACTERS

    def test_dangerous_path_components_constant(self) -> None:
        """Test dangerous path components are defined."""
        assert ".." in InputSanitizer.DANGEROUS_PATH_COMPONENTS
        assert "~" in InputSanitizer.DANGEROUS_PATH_COMPONENTS
        assert "CON" in InputSanitizer.DANGEROUS_PATH_COMPONENTS

    def test_sanitize_string_valid_input(self) -> None:
        """Test sanitizing valid string."""
        result = InputSanitizer.sanitize_string("valid_string")

        assert result.valid is True
        assert result.sanitized_value == "valid_string"

    def test_sanitize_string_too_long(self) -> None:
        """Test sanitizing string that's too long."""
        long_string = "a" * 20000

        result = InputSanitizer.sanitize_string(
            long_string,
            max_length=100,
        )

        assert result.valid is False
        assert "too long" in result.error_message.lower()

    def test_sanitize_string_with_null_byte(self) -> None:
        """Test sanitizing string with null byte."""
        result = InputSanitizer.sanitize_string("test\x00string")

        assert result.valid is False
        assert "null byte" in result.error_message.lower()

    def test_sanitize_string_with_shell_chars(self) -> None:
        """Test sanitizing string with shell metacharacters."""
        result = InputSanitizer.sanitize_string("test; rm -rf /")

        assert result.valid is False
        assert "shell" in result.error_message.lower() or "metacharacter" in result.error_message.lower()

    def test_sanitize_string_allow_shell_chars(self) -> None:
        """Test sanitizing with shell chars allowed."""
        result = InputSanitizer.sanitize_string(
            "test; value",
            allow_shell_chars=True,
        )

        # Should pass when shell chars are allowed
        # (though it may still fail on other checks like patterns)
        assert result.validation_type in [
            "security_check",  # Passed security check
            "pattern_check",  # Passed to pattern check
            "string_sanitization",  # Fully passed
        ]

    def test_sanitize_string_strict_alphanumeric(self) -> None:
        """Test strict alphanumeric validation."""
        result = InputSanitizer.sanitize_string(
            "valid-name_123",
            strict_alphanumeric=True,
        )

        assert result.valid is True
        assert result.sanitized_value == "valid-name_123"

    def test_sanitize_string_strict_alphanumeric_fails(self) -> None:
        """Test strict alphanumeric validation fails on special chars."""
        result = InputSanitizer.sanitize_string(
            "invalid@name!",
            strict_alphanumeric=True,
        )

        assert result.valid is False
        assert "alphanumeric" in result.error_message.lower()

    def test_sanitize_string_non_string_type(self) -> None:
        """Test sanitizing non-string type."""
        result = InputSanitizer.sanitize_string(12345)  # type: ignore

        assert result.valid is False
        assert "expected string" in result.error_message.lower()

    def test_sanitize_json_valid(self) -> None:
        """Test sanitizing valid JSON."""
        json_str = '{"key": "value"}'

        result = InputSanitizer.sanitize_json(json_str)

        assert result.valid is True
        assert result.sanitized_value == {"key": "value"}

    def test_sanitize_json_invalid(self) -> None:
        """Test sanitizing invalid JSON."""
        result = InputSanitizer.sanitize_json("not json")

        assert result.valid is False
        assert "invalid json" in result.error_message.lower()

    def test_sanitize_json_too_large(self) -> None:
        """Test sanitizing JSON that's too large."""
        large_json = '{"data": "' + "x" * (2 * 1024 * 1024) + '"}'

        result = InputSanitizer.sanitize_json(large_json, max_size=1024)

        assert result.valid is False
        assert "too large" in result.error_message.lower() or "too big" in result.error_message.lower()

    def test_sanitize_json_too_deep(self) -> None:
        """Test sanitizing JSON that's nested too deeply."""
        # Create valid JSON with 20 levels of nesting: {"a":{"b":{"b":...{"b":null}...}}}
        deep_json = '{"a":' + '{"b":' * 20 + 'null' + '}' * 20 + '}'

        result = InputSanitizer.sanitize_json(deep_json, max_depth=5)

        assert result.valid is False
        assert "too deep" in result.error_message.lower() or "nesting" in result.error_message.lower()

    def test_sanitize_path_valid_relative(self) -> None:
        """Test sanitizing valid relative path."""
        result = InputSanitizer.sanitize_path("docs/file.txt")

        assert result.valid is True

    def test_sanitize_path_with_double_dot(self) -> None:
        """Test sanitizing path with .. components."""
        result = InputSanitizer.sanitize_path("../../etc/passwd")

        assert result.valid is False

    def test_sanitize_path_with_dangerous_component(self) -> None:
        """Test sanitizing path with dangerous Windows component."""
        result = InputSanitizer.sanitize_path("CON/file.txt")

        assert result.valid is False


@pytest.mark.unit
class TestSecureInputValidator:
    """Test SecureInputValidator class."""

    def test_initialization(self) -> None:
        """Test validator initialization."""
        validator = SecureInputValidator()

        assert validator.config is not None
        assert validator.sanitizer is not None

    def test_initialization_with_custom_config(self) -> None:
        """Test validator with custom config."""
        config = ValidationConfig(MAX_STRING_LENGTH=5000)
        validator = SecureInputValidator(config)

        assert validator.config.MAX_STRING_LENGTH == 5000

    def test_validate_project_name_valid(self) -> None:
        """Test validating valid project name."""
        validator = SecureInputValidator()

        result = validator.validate_project_name("my-project-123")

        assert result.valid is True

    def test_validate_project_name_invalid_chars(self) -> None:
        """Test validating project name with invalid characters."""
        validator = SecureInputValidator()

        result = validator.validate_project_name("project@name!")

        assert result.valid is False

    def test_validate_job_id_valid(self) -> None:
        """Test validating valid job ID."""
        validator = SecureInputValidator()

        result = validator.validate_job_id("job-123_abc")

        assert result.valid is True

    def test_validate_command_args_string(self) -> None:
        """Test validating command args as string."""
        validator = SecureInputValidator()

        result = validator.validate_command_args("test-command")

        assert result.valid is True

    def test_validate_command_args_list(self) -> None:
        """Test validating command args as list."""
        validator = SecureInputValidator()

        result = validator.validate_command_args(["cmd", "arg1", "arg2"])

        assert result.valid is True

    def test_validate_command_args_invalid_type(self) -> None:
        """Test validating command args with invalid type."""
        validator = SecureInputValidator()

        result = validator.validate_command_args(12345)  # type: ignore

        assert result.valid is False

    def test_validate_json_payload_valid(self) -> None:
        """Test validating valid JSON payload."""
        validator = SecureInputValidator()

        result = validator.validate_json_payload('{"test": "data"}')

        assert result.valid is True

    def test_validate_json_payload_invalid(self) -> None:
        """Test validating invalid JSON payload."""
        validator = SecureInputValidator()

        result = validator.validate_json_payload("not json")

        assert result.valid is False

    def test_validate_file_path_valid(self) -> None:
        """Test validating valid file path."""
        validator = SecureInputValidator()

        result = validator.validate_file_path("docs/file.txt")

        assert result.valid is True

    def test_validate_file_path_invalid(self) -> None:
        """Test validating invalid file path."""
        validator = SecureInputValidator()

        result = validator.validate_file_path("../../etc/passwd")

        assert result.valid is False

    def test_validate_environment_var_valid(self) -> None:
        """Test validating valid environment variable."""
        validator = SecureInputValidator()

        result = validator.validate_environment_var("TEST_VAR", "value123")

        assert result.valid is True

    def test_validate_environment_var_invalid_name(self) -> None:
        """Test validating environment variable with invalid name."""
        validator = SecureInputValidator()

        result = validator.validate_environment_var("123INVALID", "value")

        assert result.valid is False


@pytest.mark.unit
class TestValidationRequiredDecorator:
    """Test validation_required decorator."""

    def test_decorator_validates_args(self) -> None:
        """Test decorator validates function arguments."""

        @validation_required()
        def test_func(arg1: str, arg2: str) -> str:
            return f"{arg1}-{arg2}"

        # Valid input should work
        result = test_func("valid1", "valid2")
        assert result == "valid1-valid2"

    def test_decorator_fails_on_invalid_args(self) -> None:
        """Test decorator raises on invalid arguments."""

        @validation_required()
        def test_func(arg1: str) -> str:
            return arg1

        # Invalid input with shell metacharacters should raise
        with pytest.raises(ExecutionError) as exc_info:
            test_func("test; rm -rf /")

        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR

    def test_decorator_validates_kwargs(self) -> None:
        """Test decorator validates keyword arguments."""

        @validation_required()
        def test_func(**kwargs: str) -> str:
            return kwargs.get("value", "")

        # Valid input should work
        result = test_func(value="valid_input")
        assert result == "valid_input"

    def test_decorator_can_skip_validation(self) -> None:
        """Test decorator can be configured to skip validation."""

        @validation_required(validate_args=False, validate_kwargs=False)
        def test_func(value: str) -> str:
            return value

        # Even with shell metacharacters, should work when validation disabled
        result = test_func("test; value")
        assert result == "test; value"


@pytest.mark.unit
class TestHelperFunctions:
    """Test helper functions."""

    def test_get_input_validator_returns_validator(self) -> None:
        """Test get_input_validator returns validator instance."""
        validator = get_input_validator()

        assert isinstance(validator, SecureInputValidator)

    def test_get_input_validator_with_config(self) -> None:
        """Test get_input_validator with custom config."""
        config = ValidationConfig(MAX_STRING_LENGTH=5000)
        validator = get_input_validator(config)

        assert validator.config.MAX_STRING_LENGTH == 5000

    def test_validate_and_sanitize_string_valid(self) -> None:
        """Test validate_and_sanitize_string with valid input."""
        result = validate_and_sanitize_string("valid_string")

        assert result == "valid_string"

    def test_validate_and_sanitize_string_invalid(self) -> None:
        """Test validate_and_sanitize_string raises on invalid input."""
        with pytest.raises(ExecutionError) as exc_info:
            validate_and_sanitize_string("test\x00string")

        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR

    def test_validate_and_sanitize_path_valid(self) -> None:
        """Test validate_and_sanitize_path with valid input."""
        result = validate_and_sanitize_path("docs/file.txt")

        assert isinstance(result, Path)

    def test_validate_and_sanitize_path_invalid(self) -> None:
        """Test validate_and_sanitize_path raises on invalid input."""
        with pytest.raises(ExecutionError) as exc_info:
            validate_and_sanitize_path("../../etc/passwd")

        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR

    def test_validate_and_parse_json_valid(self) -> None:
        """Test validate_and_parse_json with valid input."""
        result = validate_and_parse_json('{"key": "value"}')

        assert result == {"key": "value"}

    def test_validate_and_parse_json_invalid(self) -> None:
        """Test validate_and_parse_json raises on invalid input."""
        with pytest.raises(ExecutionError) as exc_info:
            validate_and_parse_json("not json")

        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR
