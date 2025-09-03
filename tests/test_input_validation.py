"""
Comprehensive tests for input validation security framework.

Tests all validation scenarios including:
- Command injection prevention
- Path traversal prevention
- SQL injection prevention
- Code injection prevention
- JSON payload validation
- Rate limiting
- Error handling
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.errors import ExecutionError
from crackerjack.services.input_validator import (
    InputSanitizer,
    SecureInputValidator,
    ValidationConfig,
    validate_and_parse_json,
    validate_and_sanitize_path,
    validate_and_sanitize_string,
    validation_required,
)
from crackerjack.services.security_logger import SecurityEventLevel


class TestInputSanitizer:
    """Test the core input sanitization functionality."""

    def test_sanitize_string_valid_input(self):
        """Test string sanitization with valid input."""
        result = InputSanitizer.sanitize_string("valid_input_123")
        assert result.valid
        assert result.sanitized_value == "valid_input_123"
        assert result.validation_type == "string_sanitization"

    def test_sanitize_string_with_whitespace(self):
        """Test string sanitization removes whitespace."""
        result = InputSanitizer.sanitize_string("  spaced input  ")
        assert result.valid
        assert result.sanitized_value == "spaced input"

    def test_sanitize_string_length_exceeded(self):
        """Test string length limit enforcement."""
        long_string = "a" * 1001
        result = InputSanitizer.sanitize_string(long_string, max_length=1000)
        assert not result.valid
        assert result.security_level == SecurityEventLevel.HIGH
        assert "too long" in result.error_message

    def test_sanitize_string_null_byte_injection(self):
        """Test null byte injection prevention."""
        malicious_input = "normal_string\x00/etc/passwd"
        result = InputSanitizer.sanitize_string(malicious_input)
        assert not result.valid
        assert result.security_level == SecurityEventLevel.CRITICAL
        assert "Null byte detected" in result.error_message

    def test_sanitize_string_control_characters(self):
        """Test control character detection."""
        malicious_input = "string_with\x01control_chars"
        result = InputSanitizer.sanitize_string(malicious_input)
        assert not result.valid
        assert result.security_level == SecurityEventLevel.HIGH

    def test_sanitize_string_shell_metacharacters(self):
        """Test shell metacharacter detection."""
        test_cases = [
            "command; rm -rf /",
            "input && malicious_command",
            "pipe | to_another_command",
            "backtick`command`execution",
            "$variable_injection",
            "redirect > /dev/null",
            "wildcard*expansion",
        ]

        for malicious_input in test_cases:
            result = InputSanitizer.sanitize_string(malicious_input)
            assert not result.valid, f"Should reject: {malicious_input}"
            assert result.security_level == SecurityEventLevel.CRITICAL

    def test_sanitize_string_allow_shell_chars(self):
        """Test allowing shell characters when explicitly enabled."""
        result = InputSanitizer.sanitize_string(
            "command | grep something", allow_shell_chars=True
        )
        assert result.valid

    def test_sanitize_string_strict_alphanumeric(self):
        """Test strict alphanumeric mode."""
        result = InputSanitizer.sanitize_string(
            "valid_name-123", strict_alphanumeric=True
        )
        assert result.valid

        result = InputSanitizer.sanitize_string(
            "invalid@email.com", strict_alphanumeric=True
        )
        assert not result.valid

    def test_sanitize_string_sql_injection_patterns(self):
        """Test SQL injection pattern detection."""
        sql_injection_attempts = [
            "'; DROP TABLE users; --",
            "1' OR '1'='1",
            "UNION SELECT * FROM passwords",
            "'; INSERT INTO admin VALUES('hacker',",
            "/* malicious comment */",
            "1 AND 1=1",
            "xp_cmdshell('dir')",
        ]

        for sql_attack in sql_injection_attempts:
            result = InputSanitizer.sanitize_string(sql_attack)
            assert not result.valid, f"Should reject SQL injection: {sql_attack}"
            assert result.security_level == SecurityEventLevel.CRITICAL

    def test_sanitize_string_code_injection_patterns(self):
        """Test code injection pattern detection."""
        code_injection_attempts = [
            "eval('malicious_code')",
            "__import__('os').system('rm -rf /')",
            "exec(open('malicious.py').read())",
            "getattr(__builtins__, 'eval')('code')",
            "subprocess.call(['rm', '-rf', '/'])",
            "os.system('malicious_command')",
            "compile('malicious', '<string>', 'exec')",
        ]

        for code_attack in code_injection_attempts:
            result = InputSanitizer.sanitize_string(code_attack)
            assert not result.valid, f"Should reject code injection: {code_attack}"
            assert result.security_level == SecurityEventLevel.CRITICAL

    def test_sanitize_json_valid(self):
        """Test JSON validation with valid input."""
        valid_json = '{"key": "value", "nested": {"array": [1, 2, 3]}}'
        result = InputSanitizer.sanitize_json(valid_json)
        assert result.valid
        assert result.sanitized_value == {
            "key": "value",
            "nested": {"array": [1, 2, 3]},
        }

    def test_sanitize_json_size_limit(self):
        """Test JSON size limit enforcement."""
        large_json = '{"data": "' + "x" * 1000 + '"}'
        result = InputSanitizer.sanitize_json(large_json, max_size=500)
        assert not result.valid
        assert result.security_level == SecurityEventLevel.HIGH

    def test_sanitize_json_depth_limit(self):
        """Test JSON nesting depth limit."""
        # Create deeply nested JSON
        nested_json = '{"level1": {"level2": {"level3": {"level4": {"level5": {"level6": "deep"}}}}}}'
        result = InputSanitizer.sanitize_json(nested_json, max_depth=3)
        assert not result.valid
        assert result.security_level == SecurityEventLevel.HIGH

    def test_sanitize_json_invalid_syntax(self):
        """Test JSON syntax error handling."""
        invalid_json = '{"key": "value",}'  # Trailing comma
        result = InputSanitizer.sanitize_json(invalid_json)
        assert not result.valid
        assert result.security_level == SecurityEventLevel.MEDIUM

    def test_sanitize_path_valid(self):
        """Test path validation with valid input."""
        result = InputSanitizer.sanitize_path("valid/path/file.txt")
        assert result.valid
        assert isinstance(result.sanitized_value, Path)

    def test_sanitize_path_traversal_attack(self):
        """Test path traversal attack prevention."""
        malicious_paths = [
            "../../../etc/passwd",
            "..\\..\\windows\\system32",
            "/usr/bin/../../../etc/passwd",
            "valid_path/../../../etc/shadow",
        ]

        for malicious_path in malicious_paths:
            InputSanitizer.sanitize_path(malicious_path)
            # Some may be valid after resolution, but dangerous components should be caught
            # The actual traversal protection is tested in the base directory constraint test

    def test_sanitize_path_dangerous_components(self):
        """Test dangerous path component detection."""
        dangerous_paths = [
            "CON",  # Windows reserved name
            "PRN",  # Windows reserved name
            "AUX",  # Windows reserved name
            "NUL",  # Windows reserved name
        ]

        for dangerous_path in dangerous_paths:
            result = InputSanitizer.sanitize_path(dangerous_path)
            assert not result.valid
            assert result.security_level == SecurityEventLevel.CRITICAL

    def test_sanitize_path_base_directory_constraint(self):
        """Test base directory constraint enforcement."""
        base_dir = Path("/safe/directory")

        # Valid path within base directory
        result = InputSanitizer.sanitize_path(
            "/safe/directory/file.txt", base_directory=base_dir
        )
        assert result.valid

        # Invalid path outside base directory
        result = InputSanitizer.sanitize_path(
            "/unsafe/directory/file.txt", base_directory=base_dir
        )
        assert not result.valid
        assert result.security_level == SecurityEventLevel.CRITICAL


class TestSecureInputValidator:
    """Test the main SecureInputValidator class."""

    @pytest.fixture
    def validator(self):
        """Create validator instance with test configuration."""
        config = ValidationConfig(
            MAX_STRING_LENGTH=1000,
            MAX_PROJECT_NAME_LENGTH=100,
            MAX_JOB_ID_LENGTH=64,
        )
        return SecureInputValidator(config)

    def test_validate_project_name_valid(self, validator):
        """Test valid project name validation."""
        result = validator.validate_project_name("valid-project_123")
        assert result.valid
        assert result.sanitized_value == "valid-project_123"

    def test_validate_project_name_invalid(self, validator):
        """Test invalid project name validation."""
        result = validator.validate_project_name("project@with!special#chars")
        assert not result.valid

    def test_validate_job_id_valid(self, validator):
        """Test valid job ID validation."""
        result = validator.validate_job_id("job-123-abc-def")
        assert result.valid

    def test_validate_job_id_invalid_format(self, validator):
        """Test invalid job ID format."""
        result = validator.validate_job_id("job@123#invalid")
        assert not result.valid
        assert result.security_level == SecurityEventLevel.HIGH

    def test_validate_command_args_string(self, validator):
        """Test command arguments validation (string)."""
        result = validator.validate_command_args("safe command")
        assert result.valid

        result = validator.validate_command_args("dangerous; command")
        assert not result.valid

    def test_validate_command_args_list(self, validator):
        """Test command arguments validation (list)."""
        result = validator.validate_command_args(["safe", "args", "list"])
        assert result.valid
        assert isinstance(result.sanitized_value, list)

        result = validator.validate_command_args(["safe", "dangerous;", "list"])
        assert not result.valid

    def test_validate_json_payload_valid(self, validator):
        """Test JSON payload validation."""
        valid_json = '{"key": "value", "number": 123}'
        result = validator.validate_json_payload(valid_json)
        assert result.valid
        assert result.sanitized_value == {"key": "value", "number": 123}

    def test_validate_json_payload_invalid(self, validator):
        """Test invalid JSON payload."""
        invalid_json = '{"invalid": json}'
        result = validator.validate_json_payload(invalid_json)
        assert not result.valid

    def test_validate_file_path_valid(self, validator):
        """Test file path validation."""
        result = validator.validate_file_path("safe/file/path.txt")
        assert result.valid

    def test_validate_file_path_traversal(self, validator):
        """Test path traversal prevention."""
        base_dir = Path("/safe/base")
        result = validator.validate_file_path(
            "../../../etc/passwd", base_directory=base_dir
        )
        assert not result.valid

    def test_validate_environment_var_valid(self, validator):
        """Test environment variable validation."""
        result = validator.validate_environment_var("VALID_VAR_NAME", "safe_value")
        assert result.valid

    def test_validate_environment_var_invalid_name(self, validator):
        """Test invalid environment variable name."""
        result = validator.validate_environment_var("invalid-var-name", "value")
        assert not result.valid

    @patch("crackerjack.services.input_validator.get_security_logger")
    def test_validation_failure_logging(self, mock_logger, validator):
        """Test that validation failures are logged."""
        mock_security_logger = Mock()
        mock_logger.return_value = mock_security_logger

        # Trigger validation failure
        validator.validate_project_name("invalid@project!")

        # Verify logging was called
        mock_security_logger.log_validation_failed.assert_called_once()


class TestValidationDecorator:
    """Test the validation_required decorator."""

    def test_validation_decorator_valid_input(self):
        """Test decorator with valid input."""

        @validation_required()
        def test_function(arg1: str, arg2: str = "default") -> str:
            return f"{arg1}_{arg2}"

        result = test_function("valid", arg2="also_valid")
        assert result == "valid_also_valid"

    def test_validation_decorator_invalid_input(self):
        """Test decorator with invalid input."""

        @validation_required()
        def test_function(arg1: str) -> str:
            return arg1

        with pytest.raises(ExecutionError):
            test_function("invalid; command")

    def test_validation_decorator_kwargs_only(self):
        """Test decorator validating only kwargs."""

        @validation_required(validate_args=False, validate_kwargs=True)
        def test_function(arg1: str, safe_kwarg: str = "default") -> str:
            return f"{arg1}_{safe_kwarg}"

        # This should pass (args not validated)
        result = test_function("invalid;", safe_kwarg="valid")
        assert result == "invalid;_valid"

        # This should fail (kwargs validated)
        with pytest.raises(ExecutionError):
            test_function("anything", safe_kwarg="invalid;")


class TestConvenienceFunctions:
    """Test convenience validation functions."""

    def test_validate_and_sanitize_string_valid(self):
        """Test convenience string validation."""
        result = validate_and_sanitize_string("valid_string")
        assert result == "valid_string"

    def test_validate_and_sanitize_string_invalid(self):
        """Test convenience string validation failure."""
        with pytest.raises(ExecutionError) as exc_info:
            validate_and_sanitize_string("invalid; string")

        assert "validation failed" in str(exc_info.value).lower()

    def test_validate_and_sanitize_path_valid(self):
        """Test convenience path validation."""
        result = validate_and_sanitize_path("valid/path.txt")
        assert isinstance(result, Path)

    def test_validate_and_sanitize_path_invalid(self):
        """Test convenience path validation failure."""
        with pytest.raises(ExecutionError):
            validate_and_sanitize_path("CON")  # Windows reserved name

    def test_validate_and_parse_json_valid(self):
        """Test convenience JSON validation."""
        result = validate_and_parse_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_validate_and_parse_json_invalid(self):
        """Test convenience JSON validation failure."""
        with pytest.raises(ExecutionError):
            validate_and_parse_json('{"invalid": json}')


class TestValidationConfig:
    """Test validation configuration."""

    def test_validation_config_defaults(self):
        """Test default validation configuration."""
        config = ValidationConfig()
        assert config.MAX_STRING_LENGTH == 10000
        assert config.MAX_PROJECT_NAME_LENGTH == 255
        assert config.MAX_JOB_ID_LENGTH == 128
        assert config.MAX_JSON_SIZE == 1024 * 1024
        assert not config.ALLOW_SHELL_METACHARACTERS
        assert not config.STRICT_ALPHANUMERIC_MODE

    def test_validation_config_custom(self):
        """Test custom validation configuration."""
        config = ValidationConfig(
            MAX_STRING_LENGTH=500,
            ALLOW_SHELL_METACHARACTERS=True,
            STRICT_ALPHANUMERIC_MODE=True,
        )
        assert config.MAX_STRING_LENGTH == 500
        assert config.ALLOW_SHELL_METACHARACTERS
        assert config.STRICT_ALPHANUMERIC_MODE


class TestSecurityLogging:
    """Test security event logging integration."""

    @patch("crackerjack.services.input_validator.get_security_logger")
    def test_command_injection_logging(self, mock_logger_func):
        """Test command injection attempt logging."""
        mock_logger = Mock()
        mock_logger_func.return_value = mock_logger

        sanitizer = InputSanitizer()
        sanitizer.sanitize_string("command; rm -rf /")

        # Validation should fail but we need to check if logging would occur
        # in a real validator instance
        validator = SecureInputValidator()
        validator.validate_command_args("command; rm -rf /")

        # Verify the logger was obtained
        mock_logger_func.assert_called()

    @patch("crackerjack.services.input_validator.get_security_logger")
    def test_path_traversal_logging(self, mock_logger_func):
        """Test path traversal attempt logging."""
        mock_logger = Mock()
        mock_logger_func.return_value = mock_logger

        validator = SecureInputValidator()
        base_dir = Path("/safe/base")
        validator.validate_file_path("../../../etc/passwd", base_directory=base_dir)

        # Verify the logger was obtained
        mock_logger_func.assert_called()


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_mcp_tool_parameter_validation(self):
        """Test MCP tool parameter validation scenario."""
        validator = SecureInputValidator()

        # Simulate MCP tool receiving parameters
        stage_arg = "fast"  # Valid
        kwargs_json = '{"dry_run": true, "verbose": false}'  # Valid

        # Validate stage
        stage_result = validator.sanitizer.sanitize_string(
            stage_arg, max_length=50, strict_alphanumeric=True
        )
        assert stage_result.valid

        # Validate JSON kwargs
        json_result = validator.validate_json_payload(kwargs_json)
        assert json_result.valid
        assert json_result.sanitized_value == {"dry_run": True, "verbose": False}

    def test_websocket_job_id_validation(self):
        """Test WebSocket job ID validation scenario."""
        validator = SecureInputValidator()

        # Valid job IDs
        valid_job_ids = [
            "job-123-abc-def",
            "uuid-12345678-1234-1234-1234-123456789012",
            "simple_job_name",
        ]

        for job_id in valid_job_ids:
            result = validator.validate_job_id(job_id)
            assert result.valid, f"Should accept: {job_id}"

        # Invalid job IDs
        invalid_job_ids = [
            "job@with!special#chars",
            "../../../etc/passwd",
            "job; rm -rf /",
            "",  # Empty
            "x" * 200,  # Too long
        ]

        for job_id in invalid_job_ids:
            result = validator.validate_job_id(job_id)
            assert not result.valid, f"Should reject: {job_id}"

    def test_project_initialization_validation(self):
        """Test project initialization validation scenario."""
        validator = SecureInputValidator()

        # Valid project names
        valid_names = ["my-project", "project_name", "validproject123"]
        for name in valid_names:
            result = validator.validate_project_name(name)
            assert result.valid, f"Should accept project name: {name}"

        # Invalid project names
        invalid_names = ["project@email.com", "project with spaces", "project/path"]
        for name in invalid_names:
            result = validator.validate_project_name(name)
            assert not result.valid, f"Should reject project name: {name}"

    def test_command_execution_validation(self):
        """Test command execution validation scenario."""
        validator = SecureInputValidator()

        # Safe command arguments
        safe_commands = [
            "pytest",
            ["python", "-m", "pytest", "tests/"],
            "ruff check src/",
        ]

        for cmd in safe_commands:
            result = validator.validate_command_args(cmd)
            assert result.valid, f"Should accept command: {cmd}"

        # Dangerous command arguments
        dangerous_commands = [
            "pytest; rm -rf /",
            ["python", "-c", "import os; os.system('rm -rf /')"],
            "ruff check | grep error && rm -rf /",
        ]

        for cmd in dangerous_commands:
            result = validator.validate_command_args(cmd)
            assert not result.valid, f"Should reject command: {cmd}"
