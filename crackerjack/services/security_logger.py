import json
import logging
import os
import time
import typing as t
from enum import Enum
from pathlib import Path

from pydantic import BaseModel


class SecurityEventType(str, Enum):
    PATH_TRAVERSAL_ATTEMPT = "path_traversal_attempt"
    FILE_SIZE_EXCEEDED = "file_size_exceeded"
    DANGEROUS_PATH_DETECTED = "dangerous_path_detected"
    BACKUP_CREATED = "backup_created"
    BACKUP_RESTORED = "backup_restored"
    BACKUP_DELETED = "backup_deleted"
    FILE_CLEANED = "file_cleaned"
    ATOMIC_OPERATION = "atomic_operation"
    VALIDATION_FAILED = "validation_failed"
    TEMP_FILE_CREATED = "temp_file_created"
    COMMAND_INJECTION_ATTEMPT = "command_injection_attempt"
    SQL_INJECTION_ATTEMPT = "sql_injection_attempt"
    CODE_INJECTION_ATTEMPT = "code_injection_attempt"
    INPUT_SIZE_EXCEEDED = "input_size_exceeded"
    INVALID_JSON_PAYLOAD = "invalid_json_payload"
    RATE_LIMIT_EXCEEDED = "rate_limit_exceeded"
    UNAUTHORIZED_ACCESS_ATTEMPT = "unauthorized_access_attempt"
    SUBPROCESS_EXECUTION = "subprocess_execution"
    SUBPROCESS_ENVIRONMENT_SANITIZED = "subprocess_environment_sanitized"
    SUBPROCESS_COMMAND_VALIDATION = "subprocess_command_validation"
    SUBPROCESS_TIMEOUT = "subprocess_timeout"
    SUBPROCESS_FAILURE = "subprocess_failure"
    DANGEROUS_COMMAND_BLOCKED = "dangerous_command_blocked"
    ENVIRONMENT_VARIABLE_FILTERED = "environment_variable_filtered"
    STATUS_ACCESS_ATTEMPT = "status_access_attempt"
    SENSITIVE_DATA_SANITIZED = "sensitive_data_sanitized"
    STATUS_INFORMATION_DISCLOSURE = "status_information_disclosure"

    ACCESS_DENIED = "access_denied"
    API_KEY_CREATED = "api_key_created"
    API_KEY_REVOKED = "api_key_revoked"
    AUTH_EXPIRED = "auth_expired"
    AUTH_FAILURE = "auth_failure"
    AUTH_SUCCESS = "auth_success"
    LOCAL_ACCESS_GRANTED = "local_access_granted"
    INSUFFICIENT_PRIVILEGES = "insufficient_privileges"

    CIRCUIT_BREAKER_CLOSED = "circuit_breaker_closed"
    CIRCUIT_BREAKER_HALF_OPEN = "circuit_breaker_half_open"
    CIRCUIT_BREAKER_OPEN = "circuit_breaker_open"
    CIRCUIT_BREAKER_RESET = "circuit_breaker_reset"

    COLLECTION_END = "collection_end"
    COLLECTION_ERROR = "collection_error"
    COLLECTION_START = "collection_start"
    STATUS_COLLECTED = "status_collected"
    FILE_READ_ERROR = "file_read_error"

    CONNECTION_CLOSED = "connection_closed"
    CONNECTION_ESTABLISHED = "connection_established"
    CONNECTION_IDLE = "connection_idle"
    CONNECTION_TIMEOUT = "connection_timeout"

    REQUEST_END = "request_end"
    REQUEST_START = "request_start"
    REQUEST_TIMEOUT = "request_timeout"

    RESOURCE_CLEANUP = "resource_cleanup"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    RESOURCE_LIMIT_EXCEEDED = "resource_limit_exceeded"
    SERVICE_CLEANUP = "service_cleanup"
    SERVICE_START = "service_start"
    SERVICE_STOP = "service_stop"

    MONITORING_ERROR = "monitoring_error"
    OPERATION_DURATION_EXCEEDED = "operation_duration_exceeded"
    OPERATION_FAILURE = "operation_failure"
    OPERATION_SUCCESS = "operation_success"
    OPERATION_TIMEOUT = "operation_timeout"

    INVALID_INPUT = "invalid_input"


class SecurityEventLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class SecurityEvent(BaseModel):
    timestamp: float
    event_type: SecurityEventType
    level: SecurityEventLevel
    message: str
    file_path: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    additional_data: dict[str, t.Any] = {}

    def to_dict(self) -> dict[str, t.Any]:
        return {
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "level": self.level.value,
            "message": self.message,
            "file_path": self.file_path,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "additional_data": self.additional_data,
        }


class SecurityLogger:
    def __init__(self, logger_name: str = "crackerjack.security"):
        self.logger = logging.getLogger(logger_name)
        self._setup_security_logger()

    def _setup_security_logger(self) -> None:
        debug_enabled = os.environ.get("CRACKERJACK_DEBUG", "0") == "1"

        # Set appropriate logger level based on debug mode
        if debug_enabled:
            self.logger.setLevel(logging.DEBUG)
        else:
            # Suppress all security logs during normal operation
            self.logger.setLevel(logging.CRITICAL + 10)

        if not self.logger.handlers:
            console_handler = logging.StreamHandler()

            if debug_enabled:
                console_handler.setLevel(logging.DEBUG)
            else:
                # Suppress all security logs during normal operation
                console_handler.setLevel(logging.CRITICAL + 10)

            formatter = logging.Formatter(
                "%(asctime)s - SECURITY - %(levelname)s - %(message)s"
            )
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

    def log_security_event(
        self,
        event_type: SecurityEventType,
        level: SecurityEventLevel,
        message: str,
        file_path: Path | str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        **additional_data: t.Any,
    ) -> None:
        event = SecurityEvent(
            timestamp=time.time(),
            event_type=event_type,
            level=level,
            message=message,
            file_path=str(file_path) if file_path else None,
            user_id=user_id,
            session_id=session_id,
            additional_data=additional_data,
        )

        log_level = self._get_logging_level(level)
        self.logger.log(
            log_level, json.dumps(event.to_dict()), extra={"security_event": True}
        )

    def _get_logging_level(self, level: SecurityEventLevel) -> int:
        level_mapping = {
            SecurityEventLevel.LOW: logging.DEBUG,
            SecurityEventLevel.MEDIUM: logging.INFO,
            SecurityEventLevel.HIGH: logging.WARNING,
            SecurityEventLevel.CRITICAL: logging.CRITICAL,
            SecurityEventLevel.INFO: logging.INFO,
            SecurityEventLevel.WARNING: logging.WARNING,
            SecurityEventLevel.ERROR: logging.ERROR,
        }
        return level_mapping[level]

    def log_path_traversal_attempt(
        self,
        attempted_path: Path | str,
        base_directory: Path | str | None = None,
        **kwargs: t.Any,
    ) -> None:
        self.log_security_event(
            SecurityEventType.PATH_TRAVERSAL_ATTEMPT,
            SecurityEventLevel.CRITICAL,
            f"Path traversal attempt detected: {attempted_path}",
            file_path=attempted_path,
            base_directory=str(base_directory) if base_directory else None,
            **kwargs,
        )

    def log_file_size_exceeded(
        self, file_path: Path | str, file_size: int, max_size: int, **kwargs: t.Any
    ) -> None:
        self.log_security_event(
            SecurityEventType.FILE_SIZE_EXCEEDED,
            SecurityEventLevel.HIGH,
            f"File size limit exceeded: {file_size} > {max_size}",
            file_path=file_path,
            file_size=file_size,
            max_size=max_size,
            **kwargs,
        )

    def log_dangerous_path_detected(
        self, path: Path | str, dangerous_component: str, **kwargs: t.Any
    ) -> None:
        self.log_security_event(
            SecurityEventType.DANGEROUS_PATH_DETECTED,
            SecurityEventLevel.HIGH,
            f"Dangerous path component detected: {dangerous_component} in {path}",
            file_path=path,
            dangerous_component=dangerous_component,
            **kwargs,
        )

    def log_backup_created(
        self, original_path: Path | str, backup_path: Path | str, **kwargs: t.Any
    ) -> None:
        self.log_security_event(
            SecurityEventType.BACKUP_CREATED,
            SecurityEventLevel.LOW,
            f"Backup created: {original_path} -> {backup_path}",
            file_path=original_path,
            backup_path=str(backup_path),
            **kwargs,
        )

    def log_file_cleaned(
        self, file_path: Path | str, steps_completed: list[str], **kwargs: t.Any
    ) -> None:
        self.log_security_event(
            SecurityEventType.FILE_CLEANED,
            SecurityEventLevel.LOW,
            f"File cleaned successfully: {file_path}",
            file_path=file_path,
            steps_completed=steps_completed,
            **kwargs,
        )

    def log_atomic_operation(
        self, operation: str, file_path: Path | str, success: bool, **kwargs: t.Any
    ) -> None:
        level = SecurityEventLevel.LOW if success else SecurityEventLevel.MEDIUM
        status = "successful" if success else "failed"

        self.log_security_event(
            SecurityEventType.ATOMIC_OPERATION,
            level,
            f"Atomic {operation} {status}: {file_path}",
            file_path=file_path,
            operation=operation,
            success=success,
            **kwargs,
        )

    def log_validation_failed(
        self, validation_type: str, file_path: Path | str, reason: str, **kwargs: t.Any
    ) -> None:
        self.log_security_event(
            SecurityEventType.VALIDATION_FAILED,
            SecurityEventLevel.MEDIUM,
            f"Validation failed ({validation_type}): {reason} for {file_path}",
            file_path=file_path,
            validation_type=validation_type,
            reason=reason,
            **kwargs,
        )

    def log_temp_file_created(
        self, temp_path: Path | str, purpose: str, **kwargs: t.Any
    ) -> None:
        self.log_security_event(
            SecurityEventType.TEMP_FILE_CREATED,
            SecurityEventLevel.LOW,
            f"Secure temp file created for {purpose}: {temp_path}",
            file_path=temp_path,
            purpose=purpose,
            **kwargs,
        )

    def log_rate_limit_exceeded(
        self, limit_type: str, current_count: int, max_allowed: int, **kwargs: t.Any
    ) -> None:
        self.log_security_event(
            SecurityEventType.RATE_LIMIT_EXCEEDED,
            SecurityEventLevel.HIGH,
            f"Rate limit exceeded for {limit_type}: {current_count} > {max_allowed}",
            limit_type=limit_type,
            current_count=current_count,
            max_allowed=max_allowed,
            **kwargs,
        )

    def log_subprocess_execution(
        self,
        command: list[str],
        cwd: str | None = None,
        env_vars_count: int = 0,
        **kwargs: t.Any,
    ) -> None:
        self.log_security_event(
            SecurityEventType.SUBPROCESS_EXECUTION,
            SecurityEventLevel.LOW,
            f"Subprocess executed: {' '.join(command[:3])}{'...' if len(command) > 3 else ''}",
            command=command[:10],
            cwd=cwd,
            env_vars_count=env_vars_count,
            **kwargs,
        )

    def log_subprocess_environment_sanitized(
        self,
        original_count: int,
        sanitized_count: int,
        filtered_vars: list[str],
        **kwargs: t.Any,
    ) -> None:
        self.log_security_event(
            SecurityEventType.SUBPROCESS_ENVIRONMENT_SANITIZED,
            SecurityEventLevel.LOW,
            f"Environment sanitized: {original_count} -> {sanitized_count} vars",
            original_count=original_count,
            sanitized_count=sanitized_count,
            filtered_vars=filtered_vars[:20],
            **kwargs,
        )

    def log_subprocess_command_validation(
        self,
        command: list[str],
        validation_result: bool,
        issues: list[str] | None = None,
        **kwargs: t.Any,
    ) -> None:
        level = SecurityEventLevel.LOW if validation_result else SecurityEventLevel.HIGH
        status = "passed" if validation_result else "failed"

        self.log_security_event(
            SecurityEventType.SUBPROCESS_COMMAND_VALIDATION,
            level,
            f"Command validation {status}: {' '.join(command[:2])}{'...' if len(command) > 2 else ''}",
            command_preview=command[:5],
            validation_result=validation_result,
            issues=issues,
            **kwargs,
        )

    def log_subprocess_timeout(
        self,
        command: list[str],
        timeout_seconds: float,
        actual_duration: float,
        **kwargs: t.Any,
    ) -> None:
        self.log_security_event(
            SecurityEventType.SUBPROCESS_TIMEOUT,
            SecurityEventLevel.MEDIUM,
            f"Subprocess timed out after {timeout_seconds}s: {' '.join(command[:2])}{'...' if len(command) > 2 else ''}",
            command_preview=command[:3],
            timeout_seconds=timeout_seconds,
            actual_duration=actual_duration,
            **kwargs,
        )

    def log_subprocess_failure(
        self, command: list[str], exit_code: int, error_output: str, **kwargs: t.Any
    ) -> None:
        self.log_security_event(
            SecurityEventType.SUBPROCESS_FAILURE,
            SecurityEventLevel.MEDIUM,
            f"Subprocess failed (exit code {exit_code}): {' '.join(command[:2])}{'...' if len(command) > 2 else ''}",
            command_preview=command[:3],
            exit_code=exit_code,
            error_preview=error_output[:200],
            **kwargs,
        )

    def log_dangerous_command_blocked(
        self,
        command: list[str],
        reason: str,
        dangerous_patterns: list[str],
        **kwargs: t.Any,
    ) -> None:
        self.log_security_event(
            SecurityEventType.DANGEROUS_COMMAND_BLOCKED,
            SecurityEventLevel.CRITICAL,
            f"Dangerous command blocked: {reason}",
            command_preview=command[:5],
            reason=reason,
            dangerous_patterns=dangerous_patterns,
            **kwargs,
        )

    def log_environment_variable_filtered(
        self,
        variable_name: str,
        reason: str,
        value_preview: str | None = None,
        **kwargs: t.Any,
    ) -> None:
        self.log_security_event(
            SecurityEventType.ENVIRONMENT_VARIABLE_FILTERED,
            SecurityEventLevel.LOW,
            f"Environment variable filtered: {variable_name} ({reason})",
            variable_name=variable_name,
            reason=reason,
            value_preview=value_preview[:50] if value_preview else None,
            **kwargs,
        )

    def log_status_access_attempt(
        self,
        endpoint: str,
        verbosity_level: str,
        user_context: str | None = None,
        data_keys: list[str] | None = None,
        **kwargs: t.Any,
    ) -> None:
        self.log_security_event(
            SecurityEventType.STATUS_ACCESS_ATTEMPT,
            SecurityEventLevel.LOW,
            f"Status access: {endpoint} (verbosity: {verbosity_level})",
            user_id=user_context,
            endpoint=endpoint,
            verbosity_level=verbosity_level,
            data_keys=data_keys or [],
            **kwargs,
        )

    def log_sensitive_data_sanitized(
        self,
        data_type: str,
        sanitization_count: int,
        verbosity_level: str,
        patterns_matched: list[str] | None = None,
        **kwargs: t.Any,
    ) -> None:
        self.log_security_event(
            SecurityEventType.SENSITIVE_DATA_SANITIZED,
            SecurityEventLevel.LOW,
            f"Sensitive data sanitized: {sanitization_count} {data_type} items",
            data_type=data_type,
            sanitization_count=sanitization_count,
            verbosity_level=verbosity_level,
            patterns_matched=patterns_matched or [],
            **kwargs,
        )

    def log_status_information_disclosure(
        self,
        disclosure_type: str,
        sensitive_info: str,
        endpoint: str,
        severity: str = "medium",
        **kwargs: t.Any,
    ) -> None:
        level_map = {
            "low": SecurityEventLevel.LOW,
            "medium": SecurityEventLevel.MEDIUM,
            "high": SecurityEventLevel.HIGH,
            "critical": SecurityEventLevel.CRITICAL,
        }

        self.log_security_event(
            SecurityEventType.STATUS_INFORMATION_DISCLOSURE,
            level_map.get(severity, SecurityEventLevel.MEDIUM),
            f"Potential information disclosure: {disclosure_type} in {endpoint}",
            disclosure_type=disclosure_type,
            sensitive_info_preview=sensitive_info[:100],
            endpoint=endpoint,
            severity=severity,
            **kwargs,
        )


_security_logger: SecurityLogger | None = None


def get_security_logger() -> SecurityLogger:
    global _security_logger
    if _security_logger is None:
        _security_logger = SecurityLogger()
    return _security_logger
