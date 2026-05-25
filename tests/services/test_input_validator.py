"""Comprehensive tests for input_validator module.

Tests all public methods and edge cases including:
- String sanitization
- Path sanitization
- JSON validation
- Command argument validation
- Environment variable validation
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

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
from crackerjack.services.security_logger import SecurityEventLevel


class TestValidationConfig:
    """Test ValidationConfig."""

    def test_default_config(self) -> None:
        """Test default validation config."""
        config = ValidationConfig()
        assert config.MAX_STRING_LENGTH == 10000
        assert config.MAX_PROJECT_NAME_LENGTH == 255
        assert config.MAX_JOB_ID_LENGTH == 128
        assert config.MAX_COMMAND_LENGTH == 1000

    def test_custom_config(self) -> None:
        """Test custom validation config."""
        config = ValidationConfig(
            MAX_STRING_LENGTH=5000,
            ALLOW_SHELL_METACHARACTERS=True,
        )
        assert config.MAX_STRING_LENGTH == 5000
        assert config.ALLOW_SHELL_METACHARACTERS is True


class TestValidationResult:
    """Test ValidationResult."""

    def test_valid_result(self) -> None:
        """Test valid validation result."""
        result = ValidationResult(
            valid=True,
            sanitized_value="test_value",
            validation_type="string_sanitization",
        )
        assert result.valid is True
        assert result.sanitized_value == "test_value"

    def test_invalid_result(self) -> None:
        """Test invalid validation result."""
        result = ValidationResult(
            valid=False,
            error_message="Invalid input",
            security_level=SecurityEventLevel.HIGH,
            validation_type="security_check",
        )
        assert result.valid is False
        assert result.error_message == "Invalid input"


class TestInputSanitizerString:
    """Test InputSanitizer string sanitization."""

    def test_sanitize_string_valid(self) -> None:
        """Test sanitizing valid string."""
        result = InputSanitizer.sanitize_string("valid_input_123")
        assert result.valid
        assert result.sanitized_value == "valid_input_123"

    def test_sanitize_string_whitespace_trimmed(self) -> None:
        """Test whitespace is trimmed."""
        result = InputSanitizer.sanitize_string("  spaced input  ")
        assert result.valid
        assert result.sanitized_value == "spaced input"

    def test_sanitize_string_null_byte_rejected(self) -> None:
        """Test null bytes are rejected."""
        result = InputSanitizer.sanitize_string("input\x00null")
        assert result.valid is False
        assert result.security_level == SecurityEventLevel.CRITICAL

    def test_sanitize_string_control_chars_rejected(self) -> None:
        """Test control characters are rejected."""
        result = InputSanitizer.sanitize_string("input\x01control")
        assert result.valid is False
        assert result.security_level == SecurityEventLevel.HIGH

    def test_sanitize_string_too_long(self) -> None:
        """Test string length limit."""
        long_string = "a" * 1001
        result = InputSanitizer.sanitize_string(long_string, max_length=1000)
        assert result.valid is False
        assert "too long" in result.error_message

    def test_sanitize_string_shell_chars_blocked(self) -> None:
        """Test shell metacharacters are blocked."""
        result = InputSanitizer.sanitize_string("echo; rm -rf /")
        assert result.valid is False
        assert result.security_level == SecurityEventLevel.CRITICAL

    def test_sanitize_string_shell_chars_allowed(self) -> None:
        """Test shell characters allowed when configured."""
        result = InputSanitizer.sanitize_string(
            "echo | grep",
            allow_shell_chars=True,
        )
        assert result.valid

    def test_sanitize_string_strict_alphanumeric(self) -> None:
        """Test strict alphanumeric mode."""
        result = InputSanitizer.sanitize_string(
            "valid-name_123",
            strict_alphanumeric=True,
        )
        assert result.valid

    def test_sanitize_string_non_alphanumeric_rejected(self) -> None:
        """Test non-alphanumeric rejected in strict mode."""
        result = InputSanitizer.sanitize_string(
            "invalid name!",
            strict_alphanumeric=True,
        )
        assert result.valid is False

    def test_sanitize_string_non_string_rejected(self) -> None:
        """Test non-string types are rejected."""
        result = InputSanitizer.sanitize_string(123)
        assert result.valid is False
        assert "Expected string" in result.error_message


class TestInputSanitizerJson:
    """Test InputSanitizer JSON sanitization."""

    def test_sanitize_json_valid(self) -> None:
        """Test sanitizing valid JSON."""
        result = InputSanitizer.sanitize_json('{"key": "value"}')
        assert result.valid
        assert result.sanitized_value == {"key": "value"}

    def test_sanitize_json_too_large(self) -> None:
        """Test oversized JSON is rejected."""
        large_json = '{"key": "' + "x" * 1000000 + '"}'
        result = InputSanitizer.sanitize_json(large_json, max_size=1000)
        assert result.valid is False
        assert "too large" in result.error_message

    def test_sanitize_json_too_nested(self) -> None:
        """Test deeply nested JSON is rejected."""
        nested = '{"a": {"b": {"c": {"d": "value"}}}}'
        result = InputSanitizer.sanitize_json(nested, max_depth=2)
        assert result.valid is False
        assert "nesting too deep" in result.error_message

    def test_sanitize_json_invalid(self) -> None:
        """Test invalid JSON is rejected."""
        result = InputSanitizer.sanitize_json("not valid json")
        assert result.valid is False
        assert "Invalid JSON" in result.error_message


class TestInputSanitizerPath:
    """Test InputSanitizer path sanitization."""

    def test_sanitize_path_valid(self) -> None:
        """Test sanitizing valid path."""
        result = InputSanitizer.sanitize_path("home/user/project", allow_absolute=True)
        assert result.valid

    def test_sanitize_path_dangerous_component(self) -> None:
        """Test dangerous path components are rejected."""
        result = InputSanitizer.sanitize_path("../etc/passwd", allow_absolute=True)
        assert result.valid is False
        assert "Dangerous path component" in result.error_message

    def test_sanitize_path_dangerous_windows_names(self) -> None:
        """Test dangerous Windows device names are rejected."""
        result = InputSanitizer.sanitize_path("C:/CON/prn")
        assert result.valid is False

    def test_sanitize_path_with_base_directory(self, tmp_path: Path) -> None:
        """Test path with base directory validation."""
        subdir = tmp_path / "project"
        subdir.mkdir()

        result = InputSanitizer.sanitize_path(subdir / "file.txt", base_directory=tmp_path)
        assert result.valid

    def test_sanitize_path_outside_base_directory(self, tmp_path: Path) -> None:
        """Test path outside base directory is rejected."""
        result = InputSanitizer.sanitize_path(
            "/etc/passwd",
            base_directory=tmp_path,
        )
        assert result.valid is False
        assert "outside base directory" in result.error_message

    def test_sanitize_path_absolute_not_allowed(self) -> None:
        """Test absolute paths not allowed when configured."""
        result = InputSanitizer.sanitize_path(
            "/absolute/path",
            allow_absolute=False,
        )
        assert result.valid is False
        assert "Absolute paths not allowed" in result.error_message

    def test_sanitize_path_absolute_allowed(self) -> None:
        """Test absolute paths allowed when configured."""
        result = InputSanitizer.sanitize_path(
            "/absolute/path",
            allow_absolute=True,
        )
        assert result.valid

    def test_sanitize_path_resolves_symlinks(self, tmp_path: Path) -> None:
        """Test path sanitization resolves symlinks."""
        real_dir = tmp_path / "real"
        real_dir.mkdir()
        link_dir = tmp_path / "link"
        link_dir.symlink_to(real_dir)

        # Use allow_absolute since tmp_path is absolute
        result = InputSanitizer.sanitize_path(link_dir / "file.txt", allow_absolute=True)
        assert result.valid


class TestSecureInputValidator:
    """Test SecureInputValidator."""

    def test_validate_project_name_valid(self) -> None:
        """Test validating valid project name."""
        validator = SecureInputValidator()
        result = validator.validate_project_name("my-project_123")

        assert result.valid
        assert result.validation_type == "string_sanitization"

    def test_validate_project_name_invalid_chars(self) -> None:
        """Test validating project name with invalid characters."""
        validator = SecureInputValidator()
        result = validator.validate_project_name("invalid name!")

        assert result.valid is False

    def test_validate_job_id_valid(self) -> None:
        """Test validating valid job ID."""
        validator = SecureInputValidator()
        result = validator.validate_job_id("job-123_abc")

        assert result.valid

    def test_validate_job_id_invalid_format(self) -> None:
        """Test validating job ID with invalid format."""
        validator = SecureInputValidator()
        result = validator.validate_job_id("invalid job id!")

        assert result.valid is False
        assert result.validation_type == "job_id_format"

    def test_validate_command_args_string(self) -> None:
        """Test validating command args as string."""
        validator = SecureInputValidator()
        result = validator.validate_command_args("safe command")

        assert result.valid

    def test_validate_command_args_list(self) -> None:
        """Test validating command args as list."""
        validator = SecureInputValidator()
        result = validator.validate_command_args(["arg1", "arg2"])

        assert result.valid
        assert result.sanitized_value == ["arg1", "arg2"]

    def test_validate_command_args_mixed_types(self) -> None:
        """Test validating mixed type args fails."""
        validator = SecureInputValidator()
        result = validator.validate_command_args(["string", 123])

        assert result.valid is False
        assert "must be string" in result.error_message

    def test_validate_json_payload_valid(self) -> None:
        """Test validating valid JSON payload."""
        validator = SecureInputValidator()
        result = validator.validate_json_payload('{"key": "value"}')

        assert result.valid
        assert result.validation_type == "json_parsing"

    def test_validate_json_payload_invalid(self) -> None:
        """Test validating invalid JSON payload."""
        validator = SecureInputValidator()
        result = validator.validate_json_payload("not json")

        assert result.valid is False

    def test_validate_file_path_valid(self) -> None:
        """Test validating valid file path."""
        validator = SecureInputValidator()
        result = validator.validate_file_path("path/to/file.txt")

        assert result.valid

    def test_validate_environment_var_valid(self) -> None:
        """Test validating valid environment variable."""
        validator = SecureInputValidator()
        result = validator.validate_environment_var("MY_VAR", "value123")

        assert result.valid

    def test_validate_environment_var_invalid_name(self) -> None:
        """Test validating invalid environment variable name."""
        validator = SecureInputValidator()
        result = validator.validate_environment_var("INVALID!", "value")

        assert result.valid is False
        assert "Invalid environment variable name" in result.error_message


class TestValidationFailureLogging:
    """Test validation failure logging."""

    def test_failure_count_tracked(self) -> None:
        """Test failure counts are tracked."""
        validator = SecureInputValidator()

        validator.validate_project_name("invalid name!")
        validator.validate_project_name("also invalid!")

        assert validator._failure_counts.get("project_name", 0) == 2

    def test_log_validation_failure_called(self) -> None:
        """Test _log_validation_failure is called on invalid input."""
        validator = SecureInputValidator()
        validator.logger = MagicMock()

        validator.validate_project_name("invalid!")

        validator.logger.log_validation_failed.assert_called()


class TestValidateAndSanitizeFunctions:
    """Test standalone validation functions."""

    def test_validate_and_sanitize_string_success(self) -> None:
        """Test validate_and_sanitize_string returns sanitized value."""
        result = validate_and_sanitize_string("  valid input  ")
        assert result == "valid input"

    def test_validate_and_sanitize_string_raises_on_invalid(self) -> None:
        """Test validate_and_sanitize_string raises on invalid input."""
        with pytest.raises(ExecutionError) as exc_info:
            validate_and_sanitize_string("echo; rm")

        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR

    def test_validate_and_sanitize_path_success(self) -> None:
        """Test validate_and_sanitize_path returns sanitized path."""
        # Use a path that won't trigger absolute path rejection
        result = validate_and_sanitize_path("home/user/project", allow_absolute=True)
        assert isinstance(result, Path)

    def test_validate_and_sanitize_path_raises_on_invalid(self) -> None:
        """Test validate_and_sanitize_path raises on invalid path."""
        with pytest.raises(ExecutionError) as exc_info:
            validate_and_sanitize_path("../etc/passwd", allow_absolute=True)

        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR

    def test_validate_and_parse_json_success(self) -> None:
        """Test validate_and_parse_json returns parsed JSON."""
        result = validate_and_parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_validate_and_parse_json_raises_on_invalid(self) -> None:
        """Test validate_and_parse_json raises on invalid JSON."""
        with pytest.raises(ExecutionError) as exc_info:
            validate_and_parse_json("not json")

        assert exc_info.value.error_code == ErrorCode.VALIDATION_ERROR


class TestValidationRequiredDecorator:
    """Test validation_required decorator."""

    def test_decorator_validates_args(self) -> None:
        """Test decorator validates function arguments."""
        @validation_required()
        def test_func(arg: str) -> str:
            return arg

        # Should pass with valid input
        result = test_func("valid_input")
        assert result == "valid_input"

    def test_decorator_rejects_invalid_arg(self) -> None:
        """Test decorator rejects invalid argument."""
        @validation_required()
        def test_func(arg: str) -> str:
            return arg

        with pytest.raises(ExecutionError):
            test_func("echo; rm")

    def test_decorator_validates_kwargs(self) -> None:
        """Test decorator validates keyword arguments."""
        @validation_required()
        def test_func(value: str = "default") -> str:
            return value

        # Should pass with valid input
        result = test_func(value="valid")
        assert result == "valid"

    def test_decorator_disabled_validation(self) -> None:
        """Test decorator can disable validation."""
        @validation_required(validate_args=False, validate_kwargs=False)
        def test_func(arg: str) -> str:
            return arg

        # Should pass even with potentially dangerous input
        result = test_func("echo; rm")
        assert result == "echo; rm"


class TestGetInputValidator:
    """Test get_input_validator function."""

    def test_get_input_validator_default(self) -> None:
        """Test get_input_validator returns new instance."""
        validator = get_input_validator()
        assert validator is not None
        assert isinstance(validator, SecureInputValidator)

    def test_get_input_validator_custom_config(self) -> None:
        """Test get_input_validator with custom config."""
        config = ValidationConfig(MAX_STRING_LENGTH=5000)
        validator = get_input_validator(config)

        assert validator.config.MAX_STRING_LENGTH == 5000


class TestInputSanitizerCheckJsonDepth:
    """Test JSON depth checking."""

    def test_check_json_depth_nested_dict(self) -> None:
        """Test depth checking for nested dictionaries."""
        depth = InputSanitizer._check_json_depth(
            {"a": {"b": {"c": "value"}}},
            max_depth=10,
        )
        assert depth == 3

    def test_check_json_depth_nested_list(self) -> None:
        """Test depth checking for nested lists."""
        depth = InputSanitizer._check_json_depth(
            [[1, 2], [3, [4, 5]]],
            max_depth=10,
        )
        assert depth == 3

    def test_check_json_depth_exceeds_max(self) -> None:
        """Test depth exceeding max is detected."""
        depth = InputSanitizer._check_json_depth(
            {"a": {"b": {"c": "value"}}},
            max_depth=2,
        )
        assert depth > 2


class TestPathComponents:
    """Test dangerous path component detection."""

    def test_dangerous_path_components_set(self) -> None:
        """Test dangerous components are defined."""
        assert ".." in InputSanitizer.DANGEROUS_PATH_COMPONENTS
        assert "CON" in InputSanitizer.DANGEROUS_PATH_COMPONENTS
        assert "PRN" in InputSanitizer.DANGEROUS_PATH_COMPONENTS

    def test_dangerous_path_case_insensitive(self) -> None:
        """Test dangerous detection is case insensitive."""
        result = InputSanitizer.sanitize_path("C:/CON/prn")
        assert result.valid is False


class TestShellMetacharacters:
    """Test shell metacharacter detection."""

    def test_shell_metacharacters_set_complete(self) -> None:
        """Test all dangerous metacharacters are defined."""
        dangerous_chars = {";", "&", "|", "`", "$", "(", ")", "<", ">", "\n"}
        for char in dangerous_chars:
            assert char in InputSanitizer.SHELL_METACHARACTERS

    def test_newline_in_input_rejected(self) -> None:
        """Test newline in input is rejected."""
        result = InputSanitizer.sanitize_string("line1\nline2")
        assert result.valid is False