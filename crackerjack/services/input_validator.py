import json
import typing as t
from functools import wraps
from pathlib import Path

from pydantic import BaseModel, Field

from ..errors import ErrorCode, ExecutionError
from .regex_patterns import SAFE_PATTERNS
from .security_logger import (
    SecurityEventLevel,
    get_security_logger,
)


class ValidationConfig(BaseModel):
    MAX_STRING_LENGTH: int = Field(default=10000, ge=1)
    MAX_PROJECT_NAME_LENGTH: int = Field(default=255, ge=1)
    MAX_JOB_ID_LENGTH: int = Field(default=128, ge=1)
    MAX_COMMAND_LENGTH: int = Field(default=1000, ge=1)

    MAX_JSON_SIZE: int = Field(default=1024 * 1024, ge=1)
    MAX_JSON_DEPTH: int = Field(default=10, ge=1)

    MAX_VALIDATION_FAILURES_PER_MINUTE: int = Field(default=10, ge=1)

    ALLOW_SHELL_METACHARACTERS: bool = Field(default=False)
    STRICT_ALPHANUMERIC_MODE: bool = Field(default=False)


class ValidationResult(BaseModel):
    valid: bool
    sanitized_value: t.Any = None
    error_message: str = ""
    security_level: SecurityEventLevel = SecurityEventLevel.LOW
    validation_type: str = ""


class InputSanitizer:
    SHELL_METACHARACTERS = {
        ";",
        "&",
        "|",
        "`",
        "$",
        "(",
        ")",
        "<",
        ">",
        "\n",
        "\r",
        "\\",
        '"',
        "'",
        "*",
        "?",
        "[",
        "]",
        "{",
        "}",
        "~",
        "^",
    }

    DANGEROUS_PATH_COMPONENTS = {
        "..",
        ".",
        "~",
        "$",
        "`",
        ";",
        "&",
        "|",
        "<",
        ">",
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    }

    @classmethod
    def sanitize_string(
        cls,
        value: t.Any,
        max_length: int = 10000,
        allow_shell_chars: bool = False,
        strict_alphanumeric: bool = False,
    ) -> ValidationResult:
        type_result = cls._validate_string_type(value)
        if not type_result.valid:
            return type_result

        length_result = cls._validate_string_length(value, max_length)
        if not length_result.valid:
            return length_result

        security_result = cls._validate_string_security(value, allow_shell_chars)
        if not security_result.valid:
            return security_result

        pattern_result = cls._validate_string_patterns(value)
        if not pattern_result.valid:
            return pattern_result

        if strict_alphanumeric and not cls._is_strictly_alphanumeric(value):
            return ValidationResult(
                valid=False,
                error_message="Only alphanumeric characters, hyphens, and underscores allowed",
                security_level=SecurityEventLevel.MEDIUM,
                validation_type="alphanumeric_only",
            )

        sanitized = value.strip()

        return ValidationResult(
            valid=True, sanitized_value=sanitized, validation_type="string_sanitization"
        )

    @classmethod
    def _validate_string_type(cls, value: t.Any) -> ValidationResult:
        if not isinstance(value, str):
            return ValidationResult(
                valid=False,
                error_message=f"Expected string, got {type(value).__name__}",
                security_level=SecurityEventLevel.MEDIUM,
                validation_type="type_check",
            )
        return ValidationResult(valid=True, validation_type="type_check")

    @classmethod
    def _validate_string_length(cls, value: str, max_length: int) -> ValidationResult:
        if len(value) > max_length:
            return ValidationResult(
                valid=False,
                error_message=f"String too long: {len(value)} > {max_length}",
                security_level=SecurityEventLevel.HIGH,
                validation_type="length_check",
            )
        return ValidationResult(valid=True, validation_type="length_check")

    @classmethod
    def _validate_string_security(
        cls, value: str, allow_shell_chars: bool
    ) -> ValidationResult:
        if "\x00" in value:
            return ValidationResult(
                valid=False,
                error_message="Null byte detected in input",
                security_level=SecurityEventLevel.CRITICAL,
                validation_type="null_byte_injection",
            )

        if any(ord(c) < 32 and c not in "\t\n\r" for c in value):
            return ValidationResult(
                valid=False,
                error_message="Control characters detected in input",
                security_level=SecurityEventLevel.HIGH,
                validation_type="control_chars",
            )

        if not allow_shell_chars:
            found_chars = [c for c in value if c in cls.SHELL_METACHARACTERS]
            if found_chars:
                return ValidationResult(
                    valid=False,
                    error_message=f"Shell metacharacters detected: {found_chars}",
                    security_level=SecurityEventLevel.CRITICAL,
                    validation_type="shell_injection",
                )

        return ValidationResult(valid=True, validation_type="security_check")

    @classmethod
    def _validate_string_patterns(cls, value: str) -> ValidationResult:
        sql_patterns = [
            "validate_sql_injection_patterns",
            "validate_sql_comment_patterns",
            "validate_sql_boolean_injection",
            "validate_sql_server_specific",
        ]
        for pattern_name in sql_patterns:
            pattern = SAFE_PATTERNS[pattern_name]
            if pattern.test(value):
                return ValidationResult(
                    valid=False,
                    error_message="SQL injection pattern detected",
                    security_level=SecurityEventLevel.CRITICAL,
                    validation_type="sql_injection",
                )

        code_patterns = [
            "validate_code_eval_injection",
            "validate_code_dynamic_access",
            "validate_code_system_commands",
            "validate_code_compilation",
        ]
        for pattern_name in code_patterns:
            pattern = SAFE_PATTERNS[pattern_name]
            if pattern.test(value):
                return ValidationResult(
                    valid=False,
                    error_message="Code injection pattern detected",
                    security_level=SecurityEventLevel.CRITICAL,
                    validation_type="code_injection",
                )

        return ValidationResult(valid=True, validation_type="pattern_check")

    @classmethod
    def _is_strictly_alphanumeric(cls, value: str) -> bool:
        return value.replace("-", "").replace("_", "").isalnum()

    @classmethod
    def sanitize_json(
        cls, value: str, max_size: int = 1024 * 1024, max_depth: int = 10
    ) -> ValidationResult:
        if len(value) > max_size:
            return ValidationResult(
                valid=False,
                error_message=f"JSON too large: {len(value)} > {max_size} bytes",
                security_level=SecurityEventLevel.HIGH,
                validation_type="json_size",
            )

        try:
            parsed = json.loads(value)

            def check_depth(obj: t.Any, current_depth: int = 0) -> int:
                if current_depth > max_depth:
                    return current_depth

                if isinstance(obj, dict):
                    return (
                        max(check_depth(v, current_depth + 1) for v in obj.values())
                        if obj
                        else current_depth
                    )
                elif isinstance(obj, list):
                    return (
                        max(check_depth(item, current_depth + 1) for item in obj)
                        if obj
                        else current_depth
                    )
                return current_depth

            actual_depth = check_depth(parsed)
            if actual_depth > max_depth:
                return ValidationResult(
                    valid=False,
                    error_message=f"JSON nesting too deep: {actual_depth} > {max_depth}",
                    security_level=SecurityEventLevel.HIGH,
                    validation_type="json_depth",
                )

            return ValidationResult(
                valid=True, sanitized_value=parsed, validation_type="json_parsing"
            )

        except json.JSONDecodeError as e:
            return ValidationResult(
                valid=False,
                error_message=f"Invalid JSON: {e}",
                security_level=SecurityEventLevel.MEDIUM,
                validation_type="json_syntax",
            )

    @classmethod
    def sanitize_path(
        cls,
        value: str | Path,
        base_directory: Path | None = None,
        allow_absolute: bool = False,
    ) -> ValidationResult:
        try:
            path = Path(value)

            danger_result = cls._check_dangerous_components(path)
            if not danger_result.valid:
                return danger_result

            if base_directory:
                base_result = cls._validate_base_directory(
                    path, base_directory, allow_absolute
                )
                if not base_result.valid:
                    return base_result
                resolved = base_result.sanitized_value
            else:
                resolved = path.resolve()

            absolute_result = cls._validate_absolute_path(
                resolved, allow_absolute, base_directory
            )
            if not absolute_result.valid:
                return absolute_result

            return ValidationResult(
                valid=True,
                sanitized_value=resolved,
                validation_type="path_sanitization",
            )

        except (OSError, ValueError) as e:
            return ValidationResult(
                valid=False,
                error_message=f"Invalid path: {e}",
                security_level=SecurityEventLevel.HIGH,
                validation_type="path_syntax",
            )

    @classmethod
    def _check_dangerous_components(cls, path: Path) -> ValidationResult:
        for part in path.parts:
            if part.upper() in cls.DANGEROUS_PATH_COMPONENTS:
                return ValidationResult(
                    valid=False,
                    error_message=f"Dangerous path component: {part}",
                    security_level=SecurityEventLevel.CRITICAL,
                    validation_type="path_traversal",
                )
        return ValidationResult(valid=True, validation_type="path_components")

    @classmethod
    def _validate_base_directory(
        cls, path: Path, base_directory: Path, allow_absolute: bool
    ) -> ValidationResult:
        base_resolved = base_directory.resolve()

        if path.is_absolute() and not str(path).startswith(str(base_resolved)):
            return ValidationResult(
                valid=False,
                error_message=f"Path outside base directory: {path}",
                security_level=SecurityEventLevel.CRITICAL,
                validation_type="directory_escape",
            )

        if not path.is_absolute():
            resolved = (base_resolved / path).resolve()
            try:
                resolved.relative_to(base_resolved)
            except ValueError:
                return ValidationResult(
                    valid=False,
                    error_message=f"Path outside base directory: {path}",
                    security_level=SecurityEventLevel.CRITICAL,
                    validation_type="directory_escape",
                )
        else:
            resolved = path.resolve()
            try:
                resolved.relative_to(base_resolved)
            except ValueError:
                return ValidationResult(
                    valid=False,
                    error_message=f"Path outside base directory: {path}",
                    security_level=SecurityEventLevel.CRITICAL,
                    validation_type="directory_escape",
                )

        return ValidationResult(
            valid=True, sanitized_value=resolved, validation_type="base_directory"
        )

    @classmethod
    def _validate_absolute_path(
        cls, resolved: Path, allow_absolute: bool, base_directory: Path | None
    ) -> ValidationResult:
        if not allow_absolute and resolved.is_absolute() and base_directory:
            return ValidationResult(
                valid=False,
                error_message="Absolute paths not allowed",
                security_level=SecurityEventLevel.HIGH,
                validation_type="absolute_path",
            )
        return ValidationResult(valid=True, validation_type="absolute_path")


class SecureInputValidator:
    def __init__(self, config: ValidationConfig | None = None):
        self.config = config or ValidationConfig()
        self.logger = get_security_logger()
        self.sanitizer = InputSanitizer()
        self._failure_counts: dict[str, int] = {}

    def validate_project_name(self, name: str) -> ValidationResult:
        result = self.sanitizer.sanitize_string(
            name,
            max_length=self.config.MAX_PROJECT_NAME_LENGTH,
            allow_shell_chars=False,
            strict_alphanumeric=True,
        )

        if not result.valid:
            self._log_validation_failure(
                "project_name", name, result.error_message, result.security_level
            )

        return result

    def validate_job_id(self, job_id: str) -> ValidationResult:
        job_id_pattern = SAFE_PATTERNS["validate_job_id_format"]
        if not job_id_pattern.test(job_id):
            result = ValidationResult(
                valid=False,
                error_message="Job ID must be alphanumeric with hyphens/underscores only",
                security_level=SecurityEventLevel.HIGH,
                validation_type="job_id_format",
            )
            self._log_validation_failure(
                "job_id", job_id, result.error_message, result.security_level
            )
            return result

        result = self.sanitizer.sanitize_string(
            job_id,
            max_length=self.config.MAX_JOB_ID_LENGTH,
            allow_shell_chars=False,
            strict_alphanumeric=True,
        )

        if not result.valid:
            self._log_validation_failure(
                "job_id", job_id, result.error_message, result.security_level
            )

        return result

    def validate_command_args(self, args: t.Any) -> ValidationResult:
        if isinstance(args, str):
            result = self.sanitizer.sanitize_string(
                args,
                max_length=self.config.MAX_COMMAND_LENGTH,
                allow_shell_chars=self.config.ALLOW_SHELL_METACHARACTERS,
            )
        elif isinstance(args, list):
            sanitized_args = []
            for arg in args:
                if not isinstance(arg, str):
                    result = ValidationResult(
                        valid=False,
                        error_message=f"Command argument must be string, got {type(arg).__name__}",
                        security_level=SecurityEventLevel.HIGH,
                        validation_type="command_arg_type",
                    )
                    break

                arg_result = self.sanitizer.sanitize_string(
                    arg,
                    max_length=self.config.MAX_COMMAND_LENGTH,
                    allow_shell_chars=self.config.ALLOW_SHELL_METACHARACTERS,
                )

                if not arg_result.valid:
                    result = arg_result
                    break

                sanitized_args.append(arg_result.sanitized_value)
            else:
                result = ValidationResult(
                    valid=True,
                    sanitized_value=sanitized_args,
                    validation_type="command_args_list",
                )
        else:
            result = ValidationResult(
                valid=False,
                error_message=f"Command args must be string or list[t.Any], got {type(args).__name__}",
                security_level=SecurityEventLevel.HIGH,
                validation_type="command_args_type",
            )

        if not result.valid:
            self._log_validation_failure(
                "command_args", str(args), result.error_message, result.security_level
            )

        return result

    def validate_json_payload(self, payload: str) -> ValidationResult:
        result = self.sanitizer.sanitize_json(
            payload,
            max_size=self.config.MAX_JSON_SIZE,
            max_depth=self.config.MAX_JSON_DEPTH,
        )

        if not result.valid:
            self._log_validation_failure(
                "json_payload",
                payload[:100] + "...",
                result.error_message,
                result.security_level,
            )

        return result

    def validate_file_path(
        self,
        path: str | Path,
        base_directory: Path | None = None,
        allow_absolute: bool = False,
    ) -> ValidationResult:
        result = self.sanitizer.sanitize_path(path, base_directory, allow_absolute)

        if not result.valid:
            self._log_validation_failure(
                "file_path", str(path), result.error_message, result.security_level
            )

        return result

    def validate_environment_var(self, name: str, value: str) -> ValidationResult:
        env_var_pattern = SAFE_PATTERNS["validate_env_var_name_format"]
        if not env_var_pattern.test(name):
            result = ValidationResult(
                valid=False,
                error_message="Invalid environment variable name format",
                security_level=SecurityEventLevel.MEDIUM,
                validation_type="env_var_name",
            )
            self._log_validation_failure(
                "env_var_name", name, result.error_message, result.security_level
            )
            return result

        result = self.sanitizer.sanitize_string(
            value, max_length=self.config.MAX_STRING_LENGTH, allow_shell_chars=False
        )

        if not result.valid:
            self._log_validation_failure(
                "env_var_value",
                f"{name}={value}",
                result.error_message,
                result.security_level,
            )

        return result

    def _log_validation_failure(
        self,
        validation_type: str,
        input_value: str,
        reason: str,
        level: SecurityEventLevel,
    ) -> None:
        self.logger.log_validation_failed(
            validation_type=validation_type,
            file_path=input_value,
            reason=reason,
        )

        self._failure_counts[validation_type] = (
            self._failure_counts.get(validation_type, 0) + 1
        )


def validation_required(
    *,
    validate_args: bool = True,
    validate_kwargs: bool = True,
    config: ValidationConfig | None = None,
) -> t.Callable[[t.Callable[..., t.Any]], t.Callable[..., t.Any]]:
    def decorator(func: t.Callable[..., t.Any]) -> t.Callable[..., t.Any]:
        @wraps(func)
        def wrapper(*args: t.Any, **kwargs: t.Any) -> t.Any:
            validator = SecureInputValidator(config)

            if validate_args:
                _validate_function_args(validator, args)

            if validate_kwargs:
                _validate_function_kwargs(validator, kwargs)

            return func(*args, **kwargs)

        return wrapper

    return decorator


def _validate_function_args(
    validator: SecureInputValidator, args: tuple[t.Any, ...]
) -> None:
    for i, arg in enumerate(args):
        if isinstance(arg, str):
            result = validator.sanitizer.sanitize_string(arg)
            if not result.valid:
                raise ExecutionError(
                    message=f"Validation failed for argument {i}: {result.error_message}",
                    error_code=ErrorCode.VALIDATION_ERROR,
                )


def _validate_function_kwargs(
    validator: SecureInputValidator, kwargs: dict[str, t.Any]
) -> None:
    for key, value in kwargs.items():
        if isinstance(value, str):
            result = validator.sanitizer.sanitize_string(value)
            if not result.valid:
                raise ExecutionError(
                    message=f"Validation failed for parameter {key}: {result.error_message}",
                    error_code=ErrorCode.VALIDATION_ERROR,
                )


def get_input_validator(
    config: ValidationConfig | None = None,
) -> SecureInputValidator:
    return SecureInputValidator(config)


def validate_and_sanitize_string(value: str, **kwargs: t.Any) -> str:
    validator = SecureInputValidator()
    result = validator.sanitizer.sanitize_string(value, **kwargs)

    if not result.valid:
        raise ExecutionError(
            message=f"String validation failed: {result.error_message}",
            error_code=ErrorCode.VALIDATION_ERROR,
        )

    return result.sanitized_value  # type: ignore[no-any-return]


def validate_and_sanitize_path(value: str | Path, **kwargs: t.Any) -> Path:
    validator = SecureInputValidator()
    result = validator.sanitizer.sanitize_path(value, **kwargs)

    if not result.valid:
        raise ExecutionError(
            message=f"Path validation failed: {result.error_message}",
            error_code=ErrorCode.VALIDATION_ERROR,
        )

    return Path(result.sanitized_value)


def validate_and_parse_json(value: str, **kwargs: t.Any) -> t.Any:
    validator = SecureInputValidator()
    result = validator.sanitizer.sanitize_json(value, **kwargs)

    if not result.valid:
        raise ExecutionError(
            message=f"JSON validation failed: {result.error_message}",
            error_code=ErrorCode.VALIDATION_ERROR,
        )

    return result.sanitized_value
