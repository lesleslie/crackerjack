import os
import tempfile
import typing as t
import urllib.parse
from pathlib import Path

from ..errors import ErrorCode, ExecutionError
from .regex_patterns import validate_path_security
from .security_logger import SecurityEventLevel, SecurityEventType, get_security_logger


class SecurePathValidator:
    """Comprehensive path security validation to prevent directory traversal attacks."""

    MAX_FILE_SIZE = 100 * 1024 * 1024
    MAX_PATH_LENGTH = 4096

    # Enhanced dangerous components including encoded variations
    DANGEROUS_COMPONENTS = {
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

    # Pattern constants removed - now using centralized SAFE_PATTERNS for security validation

    @classmethod
    def validate_safe_path(
        cls, path: str | Path, base_directory: Path | None = None
    ) -> Path:
        """
        Comprehensive path validation to prevent directory traversal attacks.

        Args:
            path: Path to validate (string or Path object)
            base_directory: Optional base directory to constrain path within

        Returns:
            Validated and normalized Path object

        Raises:
            ExecutionError: If path contains malicious patterns or is invalid
        """
        # Convert to string for pattern checking
        path_str = str(path)

        # Check for null bytes and dangerous patterns
        cls._check_malicious_patterns(path_str)

        # Convert to Path and normalize
        try:
            path_obj = Path(path_str)
            normalized = cls.normalize_path(path_obj)
        except (ValueError, OSError) as e:
            raise ExecutionError(
                message=f"Invalid path format: {path_str}",
                error_code=ErrorCode.VALIDATION_ERROR,
            ) from e

        # Validate path length
        if len(str(normalized)) > cls.MAX_PATH_LENGTH:
            raise ExecutionError(
                message=f"Path too long: {len(str(normalized))} > {cls.MAX_PATH_LENGTH}",
                error_code=ErrorCode.VALIDATION_ERROR,
            )

        # Check dangerous components
        cls._check_dangerous_components(normalized)

        # Validate within base directory if specified
        if base_directory:
            if not cls.is_within_directory(normalized, base_directory):
                raise ExecutionError(
                    message=f"Path outside allowed directory: {normalized} not within {base_directory}",
                    error_code=ErrorCode.VALIDATION_ERROR,
                )

        return normalized

    @classmethod
    def validate_file_path(
        cls, file_path: Path, base_directory: Path | None = None
    ) -> Path:
        """Legacy method - redirects to validate_safe_path for consistency."""
        return cls.validate_safe_path(file_path, base_directory)

    @classmethod
    def secure_path_join(cls, base: Path, *parts: str) -> Path:
        """
        Safe alternative to Path.joinpath() that prevents directory traversal.

        Args:
            base: Base directory path
            *parts: Path components to join

        Returns:
            Safely joined path

        Raises:
            ExecutionError: If any part contains malicious patterns
        """
        # Validate base path
        validated_base = cls.validate_safe_path(base)

        # Validate each part for malicious patterns
        for part in parts:
            cls._check_malicious_patterns(part)
            # Don't allow absolute paths or parent directory references
            if Path(part).is_absolute():
                raise ExecutionError(
                    message=f"Absolute path not allowed in join: {part}",
                    error_code=ErrorCode.VALIDATION_ERROR,
                )

        # Join paths safely
        result = validated_base.joinpath(*parts)

        # Ensure result is still within base directory
        if not cls.is_within_directory(result, validated_base):
            raise ExecutionError(
                message=f"Joined path escapes base directory: {result} not within {validated_base}",
                error_code=ErrorCode.VALIDATION_ERROR,
            )

        return result

    @classmethod
    def normalize_path(cls, path: Path) -> Path:
        """
        Canonical path resolution with security checks.

        Args:
            path: Path to normalize

        Returns:
            Normalized path with symlinks resolved

        Raises:
            ExecutionError: If path resolution fails or contains malicious patterns
        """
        try:
            # Resolve symlinks and normalize
            resolved = path.resolve()

            # Additional validation after resolution
            cls._validate_resolved_path(resolved)

            return resolved

        except (OSError, RuntimeError) as e:
            raise ExecutionError(
                message=f"Path normalization failed for {path}: {e}",
                error_code=ErrorCode.VALIDATION_ERROR,
            ) from e

    @classmethod
    def is_within_directory(cls, path: Path, directory: Path) -> bool:
        """
        Verify that a path is contained within a directory.

        Args:
            path: Path to check
            directory: Directory that should contain the path

        Returns:
            True if path is within directory, False otherwise
        """
        try:
            # Resolve both paths to handle symlinks
            resolved_path = path.resolve()
            resolved_directory = directory.resolve()

            # Check if path is relative to directory
            resolved_path.relative_to(resolved_directory)
            return True

        except (ValueError, OSError):
            return False

    @classmethod
    def safe_resolve(cls, path: Path, base_directory: Path | None = None) -> Path:
        """
        Secure path resolution preventing symlink attacks.

        Args:
            path: Path to resolve
            base_directory: Optional base directory constraint

        Returns:
            Safely resolved path

        Raises:
            ExecutionError: If resolution fails or path escapes constraints
        """
        # First validate the input path
        validated_path = cls.validate_safe_path(path, base_directory)

        # Resolve with additional symlink attack prevention
        resolved = cls.normalize_path(validated_path)

        # Re-validate after resolution
        if base_directory and not cls.is_within_directory(resolved, base_directory):
            raise ExecutionError(
                message=f"Resolved path escapes base directory: {resolved} not within {base_directory}",
                error_code=ErrorCode.VALIDATION_ERROR,
            )

        return resolved

    @classmethod
    def _check_malicious_patterns(cls, path_str: str) -> None:
        """Check for directory traversal and null byte patterns using safe patterns."""
        security_logger = get_security_logger()

        # URL decode the path to catch encoded attacks
        try:
            decoded = urllib.parse.unquote(path_str, errors="strict")
        except UnicodeDecodeError:
            # If decoding fails, use original string but still check patterns
            decoded = path_str

        # Check both original and decoded versions using safe patterns
        for check_str in (path_str, decoded):
            validation_results = validate_path_security(check_str)

            # Check for null byte patterns
            if validation_results["null_bytes"]:
                detected_pattern = validation_results["null_bytes"][
                    0
                ]  # First detected pattern
                security_logger.log_security_event(
                    SecurityEventType.PATH_TRAVERSAL_ATTEMPT,
                    SecurityEventLevel.CRITICAL,
                    f"Null byte pattern detected in path: {path_str}",
                    file_path=path_str,
                    pattern_type="null_byte",
                    detected_pattern=detected_pattern,
                )
                raise ExecutionError(
                    message=f"Null byte pattern detected in path: {path_str}",
                    error_code=ErrorCode.VALIDATION_ERROR,
                )

            # Check for directory traversal patterns
            if validation_results["traversal_patterns"]:
                detected_pattern = validation_results["traversal_patterns"][
                    0
                ]  # First detected pattern
                security_logger.log_path_traversal_attempt(
                    attempted_path=path_str,
                    pattern_type="directory_traversal",
                    detected_pattern=detected_pattern,
                )
                raise ExecutionError(
                    message=f"Directory traversal pattern detected in path: {path_str}",
                    error_code=ErrorCode.VALIDATION_ERROR,
                )

    @classmethod
    def _validate_resolved_path(cls, path: Path) -> None:
        """Additional validation for resolved paths using safe patterns."""
        path_str = str(path)

        # Check for dangerous patterns that might appear after resolution using safe patterns
        validation_results = validate_path_security(path_str)

        # Check for parent directory references
        if validation_results["suspicious_patterns"]:
            if (
                "detect_parent_directory_in_path"
                in validation_results["suspicious_patterns"]
            ):
                raise ExecutionError(
                    message=f"Parent directory reference in resolved path: {path}",
                    error_code=ErrorCode.VALIDATION_ERROR,
                )

        # Check for suspicious traversal patterns in system directories
        suspicious_detected = [
            pattern
            for pattern in validation_results["suspicious_patterns"]
            if pattern
            in ("detect_suspicious_temp_traversal", "detect_suspicious_var_traversal")
        ]

        if suspicious_detected:
            raise ExecutionError(
                message=f"Suspicious path pattern detected: {path}",
                error_code=ErrorCode.VALIDATION_ERROR,
            )

    @classmethod
    def _check_dangerous_components(cls, path: Path) -> None:
        security_logger = get_security_logger()

        for part in path.parts:
            if part in cls.DANGEROUS_COMPONENTS:
                security_logger.log_dangerous_path_detected(
                    path=str(path),
                    dangerous_component=part,
                )
                raise ExecutionError(
                    message=f"Dangerous path component detected: {part}",
                    error_code=ErrorCode.VALIDATION_ERROR,
                )

    @classmethod
    def _validate_within_base_directory(cls, path: Path, base_directory: Path) -> None:
        base_resolved = base_directory.resolve()

        try:
            path.relative_to(base_resolved)
        except ValueError as e:
            raise ExecutionError(
                message=f"Path outside allowed directory: {path} not within {base_resolved}",
                error_code=ErrorCode.VALIDATION_ERROR,
            ) from e

    @classmethod
    def validate_file_size(cls, file_path: Path) -> None:
        try:
            file_size = file_path.stat().st_size
            if file_size > cls.MAX_FILE_SIZE:
                raise ExecutionError(
                    message=f"File too large: {file_size} bytes > {cls.MAX_FILE_SIZE} bytes limit",
                    error_code=ErrorCode.VALIDATION_ERROR,
                )
        except OSError as e:
            raise ExecutionError(
                message=f"Cannot check file size: {file_path}",
                error_code=ErrorCode.FILE_READ_ERROR,
            ) from e

    @classmethod
    def create_secure_backup_path(
        cls, original_path: Path, base_directory: Path | None = None
    ) -> Path:
        validated_original = cls.validate_file_path(original_path, base_directory)

        backup_path = validated_original.parent / f"{validated_original.name}.backup"

        validated_backup = cls.validate_file_path(backup_path, base_directory)

        return validated_backup

    @classmethod
    def create_secure_temp_file(
        cls,
        suffix: str = ".tmp",
        prefix: str = "crackerjack_",
        directory: Path | None = None,
        purpose: str = "general",
    ) -> t.Any:
        """
        Create a secure temporary file with proper permissions.

        Args:
            suffix: File suffix
            prefix: File prefix
            directory: Directory to create temp file in (validated if provided)
            purpose: Purpose description for security logging

        Returns:
            Secure temporary file handle

        Raises:
            ExecutionError: If temp file creation fails
        """
        security_logger = get_security_logger()

        # Validate directory if provided
        if directory:
            directory = cls.validate_safe_path(directory)

        try:
            temp_file = tempfile.NamedTemporaryFile(
                mode="w+b", suffix=suffix, prefix=prefix, dir=directory, delete=False
            )

            # Set restrictive permissions (owner read/write only)
            os.chmod(temp_file.name, 0o600)

            # Log secure temp file creation
            security_logger.log_temp_file_created(
                temp_path=temp_file.name,
                purpose=purpose,
            )

            return temp_file

        except OSError as e:
            raise ExecutionError(
                message=f"Failed to create secure temporary file: {e}",
                error_code=ErrorCode.FILE_WRITE_ERROR,
            ) from e


class AtomicFileOperations:
    @staticmethod
    def atomic_write(
        file_path: Path, content: str | bytes, base_directory: Path | None = None
    ) -> None:
        security_logger = get_security_logger()

        validated_path = SecurePathValidator.validate_safe_path(
            file_path, base_directory
        )

        temp_file = None
        try:
            temp_file = SecurePathValidator.create_secure_temp_file(
                prefix="atomic_write_",
                directory=validated_path.parent,
                purpose="atomic_file_write",
            )

            if isinstance(content, str):
                temp_file.write(content.encode("utf-8"))
            else:
                temp_file.write(content)

            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_file.close()

            temp_path = Path(temp_file.name)
            temp_path.replace(validated_path)

            # Log successful atomic operation
            security_logger.log_atomic_operation(
                operation="write",
                file_path=str(validated_path),
                success=True,
            )

        except Exception as e:
            if temp_file and hasattr(temp_file, "name"):
                temp_path = Path(temp_file.name)
                if temp_path.exists():
                    temp_path.unlink()

            # Log failed atomic operation
            security_logger.log_atomic_operation(
                operation="write",
                file_path=str(validated_path),
                success=False,
                error=str(e),
            )

            raise ExecutionError(
                message=f"Atomic write failed for {validated_path}: {e}",
                error_code=ErrorCode.FILE_WRITE_ERROR,
            ) from e

    @staticmethod
    def atomic_backup_and_write(
        file_path: Path, new_content: str | bytes, base_directory: Path | None = None
    ) -> Path:
        security_logger = get_security_logger()

        validated_path = SecurePathValidator.validate_safe_path(
            file_path, base_directory
        )

        if not validated_path.exists():
            raise ExecutionError(
                message=f"File does not exist: {validated_path}",
                error_code=ErrorCode.FILE_READ_ERROR,
            )

        SecurePathValidator.validate_file_size(validated_path)

        backup_path = SecurePathValidator.create_secure_backup_path(
            validated_path, base_directory
        )

        try:
            original_content = validated_path.read_bytes()

            AtomicFileOperations.atomic_write(
                backup_path, original_content, base_directory
            )

            AtomicFileOperations.atomic_write(
                validated_path, new_content, base_directory
            )

            # Log successful backup creation
            security_logger.log_backup_created(
                original_path=str(validated_path),
                backup_path=str(backup_path),
            )

            return backup_path

        except Exception as e:
            if backup_path.exists():
                backup_path.unlink()

            # Log failed backup operation
            security_logger.log_atomic_operation(
                operation="backup_and_write",
                file_path=str(validated_path),
                success=False,
                error=str(e),
            )

            raise ExecutionError(
                message=f"Atomic backup and write failed: {e}",
                error_code=ErrorCode.FILE_WRITE_ERROR,
            ) from e


class SubprocessPathValidator:
    """Specialized path validation for subprocess execution contexts."""

    # Paths that should never be accessible via subprocess
    FORBIDDEN_SUBPROCESS_PATHS = {
        "/etc/passwd",
        "/etc/shadow",
        "/etc/sudoers",
        "/etc/hosts",
        "/boot",
        "/sys",
        "/proc",
        "/dev",
        "/var/log",
        "/usr/bin/sudo",
        "/usr/bin/su",
        "/bin/su",
        "/bin/sudo",
        "/etc/ssh",
        "/root",
        "/var/spool/cron",
    }

    # Directory patterns removed - now using centralized SAFE_PATTERNS for security validation

    @classmethod
    def validate_subprocess_cwd(cls, cwd: Path | str | None) -> Path | None:
        """
        Validate working directory for subprocess execution.

        Args:
            cwd: Working directory path

        Returns:
            Validated Path object or None

        Raises:
            ExecutionError: If path is dangerous for subprocess execution
        """
        if cwd is None:
            return None

        # Use base path validation first
        validated_cwd = SecurePathValidator.validate_safe_path(cwd)

        # Additional subprocess-specific checks
        cwd_str = str(validated_cwd)

        # Check against forbidden paths
        if cwd_str in cls.FORBIDDEN_SUBPROCESS_PATHS:
            security_logger = get_security_logger()
            security_logger.log_dangerous_path_detected(
                path=cwd_str,
                dangerous_component="forbidden_subprocess_path",
                context="subprocess_cwd_validation",
            )
            raise ExecutionError(
                message=f"Forbidden subprocess working directory: {cwd_str}",
                error_code=ErrorCode.VALIDATION_ERROR,
            )

        # Check against dangerous directory patterns using safe patterns
        validation_results = validate_path_security(cwd_str)

        if validation_results["dangerous_directories"]:
            detected_pattern = validation_results["dangerous_directories"][
                0
            ]  # First detected pattern
            security_logger = get_security_logger()
            security_logger.log_dangerous_path_detected(
                path=cwd_str,
                dangerous_component=f"pattern:{detected_pattern}",
                context="subprocess_cwd_validation",
            )
            raise ExecutionError(
                message=f"Dangerous subprocess working directory pattern: {cwd_str}",
                error_code=ErrorCode.VALIDATION_ERROR,
            )

        return validated_cwd

    @classmethod
    def validate_executable_path(cls, executable: str | Path) -> Path:
        """
        Validate executable path for subprocess execution.

        Args:
            executable: Executable path or name

        Returns:
            Validated Path object

        Raises:
            ExecutionError: If executable is dangerous or invalid
        """
        exec_path = Path(executable)

        # If it's just a command name, don't validate as full path
        if not str(executable).startswith(("/", "./", "../")):
            return exec_path

        # For full paths, apply full validation
        validated_exec = SecurePathValidator.validate_safe_path(exec_path)

        # Additional checks for executable paths
        exec_str = str(validated_exec)

        # Check if trying to execute system-critical files
        dangerous_executables = {
            "/usr/bin/sudo",
            "/bin/sudo",
            "/usr/bin/su",
            "/bin/su",
            "/usr/bin/passwd",
            "/bin/passwd",
            "/usr/sbin/visudo",
            "/usr/bin/ssh",
            "/usr/bin/scp",
            "/usr/bin/rsync",
            "/bin/rm",
            "/usr/bin/rm",
            "/bin/rmdir",
            "/usr/bin/rmdir",
            "/sbin/reboot",
            "/sbin/shutdown",
            "/usr/sbin/reboot",
        }

        if exec_str in dangerous_executables:
            security_logger = get_security_logger()
            security_logger.log_dangerous_path_detected(
                path=exec_str,
                dangerous_component="dangerous_executable",
                context="subprocess_executable_validation",
            )
            raise ExecutionError(
                message=f"Dangerous executable blocked: {exec_str}",
                error_code=ErrorCode.VALIDATION_ERROR,
            )

        return validated_exec
