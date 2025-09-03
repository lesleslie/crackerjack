"""
Secure subprocess execution with environment sanitization and command validation.

This module provides production-ready security for all subprocess operations in Crackerjack,
implementing comprehensive validation, sanitization, and logging to prevent injection attacks.
"""

import os
import re
import subprocess
import time
import typing as t
from pathlib import Path

from .security_logger import SecurityEventLevel, SecurityEventType, get_security_logger


class SecurityError(Exception):
    """Raised when a security violation is detected."""

    pass


class CommandValidationError(SecurityError):
    """Raised when command validation fails."""

    pass


class EnvironmentValidationError(SecurityError):
    """Raised when environment validation fails."""

    pass


class SubprocessSecurityConfig:
    """Configuration for secure subprocess execution."""

    def __init__(
        self,
        max_command_length: int = 10000,
        max_arg_length: int = 4096,
        max_env_var_length: int = 32768,
        max_env_vars: int = 1000,
        allowed_executables: set[str] | None = None,
        blocked_executables: set[str] | None = None,
        max_timeout: float = 3600,  # 1 hour max
        enable_path_validation: bool = True,
        enable_command_logging: bool = True,
    ):
        self.max_command_length = max_command_length
        self.max_arg_length = max_arg_length
        self.max_env_var_length = max_env_var_length
        self.max_env_vars = max_env_vars
        self.allowed_executables = allowed_executables or set()
        self.blocked_executables = blocked_executables or {
            "rm",
            "rmdir",
            "del",
            "format",
            "fdisk",
            "mkfs",
            "dd",
            "shred",
            "wipe",
            "nc",
            "netcat",
            "telnet",
            "ftp",
            "tftp",
            "curl",
            "wget",
            "ssh",
            "scp",
            "rsync",
            "sudo",
            "su",
            "doas",
            "eval",
            "exec",
            "source",
            ".",
            "bash",
            "sh",
            "zsh",
            "fish",
            "csh",
        }
        self.max_timeout = max_timeout
        self.enable_path_validation = enable_path_validation
        self.enable_command_logging = enable_command_logging


class SecureSubprocessExecutor:
    """Secure subprocess executor with comprehensive validation and logging."""

    def __init__(self, config: SubprocessSecurityConfig | None = None):
        self.config = config or SubprocessSecurityConfig()
        self.security_logger = get_security_logger()

        # Dangerous patterns for command injection detection
        self.dangerous_patterns = [
            r"[;&|`$(){}[\]<>*?~]",  # Shell metacharacters
            r"\.\./",  # Path traversal
            r"\$\{.*\}",  # Variable expansion
            r"`.*`",  # Command substitution
            r"\$\(.*\)",  # Command substitution
            r">\s*/",  # Redirect to system paths
            r"<\s*/",  # Redirect from system paths
        ]

        # Environment variables that should never be passed through
        self.dangerous_env_vars = {
            "LD_PRELOAD",
            "DYLD_INSERT_LIBRARIES",
            "DYLD_LIBRARY_PATH",
            "LD_LIBRARY_PATH",
            "PYTHONPATH",
            "PATH",
            "IFS",
            "PS4",
            "BASH_ENV",
            "ENV",
            "SHELLOPTS",
            "BASHOPTS",
        }

        # Minimal safe environment variables
        self.safe_env_vars = {
            "HOME",
            "USER",
            "USERNAME",
            "LOGNAME",
            "LANG",
            "LC_ALL",
            "LC_CTYPE",
            "TERM",
            "TMPDIR",
            "TMP",
            "TEMP",
        }

    def execute_secure(
        self,
        command: list[str],
        cwd: Path | str | None = None,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
        input_data: str | bytes | None = None,
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
        **kwargs: t.Any,
    ) -> subprocess.CompletedProcess[str]:
        """
        Execute a subprocess with comprehensive security validation.

        Args:
            command: Command and arguments as list
            cwd: Working directory (validated for path traversal)
            env: Environment variables (will be sanitized)
            timeout: Maximum execution time
            input_data: Input to pass to subprocess
            capture_output: Whether to capture stdout/stderr
            text: Whether to use text mode
            check: Whether to raise on non-zero exit
            **kwargs: Additional subprocess.run arguments

        Returns:
            CompletedProcess result

        Raises:
            SecurityError: If security validation fails
            CommandValidationError: If command validation fails
            EnvironmentValidationError: If environment validation fails
        """
        start_time = time.time()

        try:
            # Validate and sanitize all inputs
            validated_command = self._validate_command(command)
            validated_cwd = self._validate_cwd(cwd)
            sanitized_env = self._sanitize_environment(env)
            validated_timeout = self._validate_timeout(timeout)

            # Log the execution attempt
            if self.config.enable_command_logging:
                self.security_logger.log_subprocess_execution(
                    command=validated_command,
                    cwd=str(validated_cwd) if validated_cwd else None,
                    env_vars_count=len(sanitized_env),
                    timeout=validated_timeout,
                )

            # Execute the subprocess
            result = subprocess.run(
                validated_command,
                cwd=validated_cwd,
                env=sanitized_env,
                timeout=validated_timeout,
                input=input_data,
                capture_output=capture_output,
                text=text,
                check=check,
                **kwargs,
            )

            # Log success
            execution_time = time.time() - start_time
            if self.config.enable_command_logging:
                self.security_logger.log_security_event(
                    SecurityEventType.SUBPROCESS_EXECUTION,
                    SecurityEventLevel.LOW,
                    f"Subprocess completed successfully in {execution_time:.2f}s",
                    command_preview=validated_command[:3],
                    execution_time=execution_time,
                    exit_code=result.returncode,
                )

            return result

        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            self.security_logger.log_subprocess_timeout(
                command=command,
                timeout_seconds=validated_timeout or self.config.max_timeout,
                actual_duration=execution_time,
            )
            raise

        except subprocess.CalledProcessError as e:
            self.security_logger.log_subprocess_failure(
                command=command,
                exit_code=e.returncode,
                error_output=str(e.stderr)[:200] if e.stderr else "",
            )
            raise

        except Exception as e:
            self.security_logger.log_security_event(
                SecurityEventType.SUBPROCESS_FAILURE,
                SecurityEventLevel.HIGH,
                f"Unexpected subprocess error: {str(e)[:200]}",
                command_preview=command[:3] if command else [],
                error_type=type(e).__name__,
                error_message=str(e)[:200],
            )
            raise

    def _validate_command(self, command: list[str]) -> list[str]:
        """Validate command arguments for security issues."""
        if not command:
            raise CommandValidationError("Command cannot be empty")

        if not isinstance(command, list):
            raise CommandValidationError("Command must be a list of strings")

        # Check overall command length
        total_length = sum(len(arg) for arg in command)
        if total_length > self.config.max_command_length:
            raise CommandValidationError(
                f"Command too long: {total_length} > {self.config.max_command_length}"
            )

        validated_command = []
        issues = []

        for i, arg in enumerate(command):
            if not isinstance(arg, str):
                raise CommandValidationError(
                    f"Command argument {i} must be string, got {type(arg)}"
                )

            # Check argument length
            if len(arg) > self.config.max_arg_length:
                issues.append(
                    f"Argument {i} too long: {len(arg)} > {self.config.max_arg_length}"
                )
                continue

            # Check for injection patterns
            for pattern in self.dangerous_patterns:
                if re.search(pattern, arg):
                    issues.append(
                        f"Dangerous pattern '{pattern}' in argument {i}: {arg[:50]}"
                    )
                    continue

            validated_command.append(arg)

        # Check executable allowlist/blocklist
        if validated_command:
            executable = Path(validated_command[0]).name

            if (
                self.config.allowed_executables
                and executable not in self.config.allowed_executables
            ):
                issues.append(f"Executable '{executable}' not in allowlist")

            if executable in self.config.blocked_executables:
                issues.append(f"Executable '{executable}' is blocked")

        # Log validation results
        validation_passed = len(issues) == 0
        if self.config.enable_command_logging:
            self.security_logger.log_subprocess_command_validation(
                command=command,
                validation_result=validation_passed,
                issues=issues,
            )

        if issues:
            # Block dangerous commands
            self.security_logger.log_dangerous_command_blocked(
                command=command,
                reason="Command validation failed",
                dangerous_patterns=issues,
            )
            raise CommandValidationError(
                f"Command validation failed: {'; '.join(issues)}"
            )

        return validated_command

    def _validate_cwd(self, cwd: Path | str | None) -> Path | None:
        """Validate working directory for path traversal."""
        if cwd is None:
            return None

        if not self.config.enable_path_validation:
            return Path(cwd) if isinstance(cwd, str) else cwd

        cwd_path = Path(cwd) if isinstance(cwd, str) else cwd

        try:
            # Resolve to absolute path and check for traversal
            resolved_path = cwd_path.resolve()

            # Check for dangerous path components
            path_str = str(resolved_path)
            if ".." in path_str or path_str.startswith(
                ("/etc", "/usr/bin", "/bin", "/sbin")
            ):
                self.security_logger.log_path_traversal_attempt(
                    attempted_path=path_str,
                    base_directory=None,
                )
                raise CommandValidationError(f"Dangerous working directory: {path_str}")

            return resolved_path

        except (OSError, ValueError) as e:
            raise CommandValidationError(f"Invalid working directory '{cwd}': {e}")

    def _sanitize_environment(self, env: dict[str, str] | None) -> dict[str, str]:
        """Sanitize environment variables."""
        if env is None:
            env = os.environ.copy()

        original_count = len(env)
        filtered_vars = []
        sanitized_env = {}

        # Check total environment size
        if len(env) > self.config.max_env_vars:
            self.security_logger.log_security_event(
                SecurityEventType.INPUT_SIZE_EXCEEDED,
                SecurityEventLevel.HIGH,
                f"Too many environment variables: {len(env)} > {self.config.max_env_vars}",
                actual_count=len(env),
                max_count=self.config.max_env_vars,
            )
            raise EnvironmentValidationError(
                f"Too many environment variables: {len(env)} > {self.config.max_env_vars}"
            )

        for key, value in env.items():
            # Check key safety
            if key in self.dangerous_env_vars:
                filtered_vars.append(key)
                self.security_logger.log_environment_variable_filtered(
                    variable_name=key,
                    reason="dangerous environment variable",
                    value_preview=str(value)[:50] if value else None,
                )
                continue

            # Check value length
            if len(str(value)) > self.config.max_env_var_length:
                filtered_vars.append(key)
                self.security_logger.log_environment_variable_filtered(
                    variable_name=key,
                    reason=f"value too long: {len(str(value))} > {self.config.max_env_var_length}",
                    value_preview=str(value)[:50],
                )
                continue

            # Check for injection in values
            value_str = str(value)
            has_injection = False
            for pattern in self.dangerous_patterns[:3]:  # Check first 3 most dangerous
                if re.search(pattern, value_str):
                    filtered_vars.append(key)
                    self.security_logger.log_environment_variable_filtered(
                        variable_name=key,
                        reason=f"dangerous pattern '{pattern}' in value",
                        value_preview=value_str[:50],
                    )
                    has_injection = True
                    break

            if not has_injection:
                sanitized_env[key] = value_str

        # Ensure essential environment variables are present
        for safe_var in self.safe_env_vars:
            if safe_var not in sanitized_env and safe_var in os.environ:
                sanitized_env[safe_var] = os.environ[safe_var]

        # Log sanitization results
        if self.config.enable_command_logging:
            self.security_logger.log_subprocess_environment_sanitized(
                original_count=original_count,
                sanitized_count=len(sanitized_env),
                filtered_vars=filtered_vars,
            )

        return sanitized_env

    def _validate_timeout(self, timeout: float | None) -> float | None:
        """Validate timeout value."""
        if timeout is None:
            return None

        if timeout <= 0:
            raise CommandValidationError(f"Timeout must be positive: {timeout}")

        if timeout > self.config.max_timeout:
            self.security_logger.log_security_event(
                SecurityEventType.INPUT_SIZE_EXCEEDED,
                SecurityEventLevel.MEDIUM,
                f"Timeout too large: {timeout} > {self.config.max_timeout}",
                requested_timeout=timeout,
                max_timeout=self.config.max_timeout,
            )
            raise CommandValidationError(
                f"Timeout too large: {timeout} > {self.config.max_timeout}"
            )

        return timeout


# Global secure executor instance
_global_executor: SecureSubprocessExecutor | None = None


def get_secure_executor(
    config: SubprocessSecurityConfig | None = None,
) -> SecureSubprocessExecutor:
    """Get the global secure subprocess executor."""
    global _global_executor
    if _global_executor is None:
        _global_executor = SecureSubprocessExecutor(config)
    return _global_executor


def execute_secure_subprocess(
    command: list[str],
    **kwargs: t.Any,
) -> subprocess.CompletedProcess[str]:
    """
    Convenience function for secure subprocess execution.

    This is the recommended way to execute subprocesses in Crackerjack.
    """
    executor = get_secure_executor()
    return executor.execute_secure(command, **kwargs)
