"""
Secure status formatter to prevent information disclosure vulnerabilities.

This module provides secure sanitization of status responses to prevent
leaking sensitive system information such as absolute paths, internal URLs,
configuration details, and other sensitive data.
"""

import re
import typing as t
from enum import Enum
from pathlib import Path

from .security_logger import get_security_logger


class StatusVerbosity(str, Enum):
    """Status output verbosity levels for security-aware responses."""

    MINIMAL = "minimal"  # Only essential operational status
    STANDARD = "standard"  # Standard operational information (default)
    DETAILED = "detailed"  # More detailed information for debugging
    FULL = "full"  # Complete information (for internal use only)


class SecureStatusFormatter:
    """
    Secure status formatter with configurable verbosity levels.

    Sanitizes sensitive information while preserving necessary operational data.
    """

    # Patterns for sensitive information that should be masked or removed
    SENSITIVE_PATTERNS = {
        # Absolute system paths (replace with relative paths)
        "absolute_paths": [
            r"(/[^/\s]*){2,}",  # Paths like /Users/username/...
            r"/tmp/[^\s]*",  # Temp directory paths
            r"/var/[^\s]*",  # Var directory paths
            r"/home/[^\s]*",  # Home directory paths
        ],
        # URLs with localhost/internal IPs
        "internal_urls": [
            r"https?://localhost:\d+",
            r"https?://127\.0\.0\.1:\d+",
            r"https?://0\.0\.0\.0:\d+",
            r"ws://localhost:\d+",
            r"ws://127\.0\.0\.1:\d+",
        ],
        # Tokens and API keys
        "secrets": [
            r"[A-Za-z0-9]{20,}",  # Long alphanumeric strings (potential tokens)
            r"[A-Za-z0-9+/]{32,}={0,2}",  # Base64-like strings
        ],
        # Process IDs and system identifiers
        "system_ids": [
            r"pid:\d+",
            r"process_id:\s*\d+",
        ],
    }

    # Sensitive keys that should be masked or removed
    SENSITIVE_KEYS = {
        "remove_minimal": {
            "progress_dir",
            "temp_files_count",
            "rate_limiter",
            "config",
            "traceback",
            "processes",
        },
        "remove_standard": {"progress_dir", "traceback"},
        "mask": {
            "project_path",
            "websocket_url",
            "monitor_url",
            "api_key",
            "token",
            "secret",
            "password",
            "auth",
        },
    }

    def __init__(self, project_root: Path | None = None):
        """
        Initialize secure status formatter.

        Args:
            project_root: Project root path for relative path conversion
        """
        self.project_root = project_root or Path.cwd()
        self.security_logger = get_security_logger()

    def format_status(
        self,
        status_data: dict[str, t.Any],
        verbosity: StatusVerbosity = StatusVerbosity.STANDARD,
        user_context: str | None = None,
    ) -> dict[str, t.Any]:
        """
        Format status data with security sanitization.

        Args:
            status_data: Raw status data to sanitize
            verbosity: Output verbosity level
            user_context: Optional user context for logging

        Returns:
            Sanitized status data appropriate for the verbosity level
        """
        # Log status access attempt
        self.security_logger.log_status_access_attempt(
            endpoint="status_data",
            verbosity_level=verbosity.value,
            user_context=user_context,
            data_keys=list(status_data.keys()),
        )

        # Deep copy to avoid modifying original
        sanitized = self._deep_copy_dict(status_data)

        # Apply verbosity-based filtering
        sanitized = self._apply_verbosity_filter(sanitized, verbosity)

        # Sanitize sensitive information
        sanitized = self._sanitize_sensitive_data(sanitized, verbosity)

        # Add security metadata
        sanitized["_security"] = {
            "sanitized": True,
            "verbosity": verbosity.value,
            "timestamp": self._get_timestamp(),
        }

        return sanitized

    def _apply_verbosity_filter(
        self, data: dict[str, t.Any], verbosity: StatusVerbosity
    ) -> dict[str, t.Any]:
        """Apply verbosity-based key filtering."""

        # Keys to remove based on verbosity level
        if verbosity == StatusVerbosity.MINIMAL:
            remove_keys = self.SENSITIVE_KEYS["remove_minimal"]
        elif verbosity == StatusVerbosity.STANDARD:
            remove_keys = self.SENSITIVE_KEYS["remove_standard"]
        else:
            remove_keys = set()  # Keep all keys for DETAILED/FULL

        # Remove sensitive keys
        for key in list(data.keys()):
            if key in remove_keys:
                del data[key]

        # Recursively apply to nested dictionaries
        for key, value in data.items():
            if isinstance(value, dict):
                data[key] = self._apply_verbosity_filter(value, verbosity)

        return data

    def _sanitize_sensitive_data(
        self, data: dict[str, t.Any], verbosity: StatusVerbosity
    ) -> dict[str, t.Any]:
        """Sanitize sensitive data based on patterns and keys."""

        return self._sanitize_recursive(data, verbosity)

    def _sanitize_recursive(self, obj: t.Any, verbosity: StatusVerbosity) -> t.Any:
        """Recursively sanitize data structures."""

        if isinstance(obj, dict):
            sanitized = {}
            for key, value in obj.items():
                # Sanitize the key
                sanitized_key = self._sanitize_string(key, verbosity)

                # Sanitize the value
                if (
                    key in self.SENSITIVE_KEYS["mask"]
                    and verbosity != StatusVerbosity.FULL
                ):
                    sanitized[sanitized_key] = self._mask_sensitive_value(str(value))
                else:
                    sanitized[sanitized_key] = self._sanitize_recursive(
                        value, verbosity
                    )

            return sanitized

        elif isinstance(obj, list):
            return [self._sanitize_recursive(item, verbosity) for item in obj]

        elif isinstance(obj, str):
            return self._sanitize_string(obj, verbosity)

        else:
            return obj

    def _sanitize_string(self, text: str, verbosity: StatusVerbosity) -> str:
        """Sanitize string content based on verbosity level."""

        if verbosity == StatusVerbosity.FULL:
            return text  # No sanitization for full verbosity

        sanitized = text

        # Sanitize internal URLs FIRST (before other processing)
        sanitized = self._sanitize_internal_urls(sanitized)

        # Sanitize absolute paths (convert to relative)
        sanitized = self._sanitize_paths(sanitized)

        # Mask potential secrets (after URLs are already replaced)
        if verbosity == StatusVerbosity.MINIMAL:
            sanitized = self._mask_potential_secrets(sanitized)

        return sanitized

    def _sanitize_paths(self, text: str) -> str:
        """Convert absolute paths to relative paths where possible."""

        # More comprehensive path pattern that catches absolute paths
        path_patterns = [
            r"/[a-zA-Z0-9_\-\.\/]+",  # Unix-style absolute paths
            r"[A-Z]:[\\\/][a-zA-Z0-9_\-\.\\\/]+",  # Windows-style absolute paths
        ]

        for pattern in path_patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                if len(match) > 3:  # Only process paths longer than 3 chars
                    try:
                        abs_path = Path(match)
                        if abs_path.is_absolute():
                            # Try to make relative to project root
                            try:
                                rel_path = abs_path.relative_to(self.project_root)
                                text = text.replace(match, f"./{rel_path}")
                            except (ValueError, OSError):
                                # If not within project, mask it
                                text = text.replace(match, "[REDACTED_PATH]")
                    except (ValueError, OSError):
                        # If path operations fail, mask it
                        text = text.replace(match, "[REDACTED_PATH]")

        return text

    def _sanitize_internal_urls(self, text: str) -> str:
        """Replace internal URLs with generic placeholders."""

        # More comprehensive URL patterns
        url_patterns = [
            r"https?://localhost:\d+[^\s]*",
            r"https?://127\.0\.0\.1:\d+[^\s]*",
            r"https?://0\.0\.0\.0:\d+[^\s]*",
            r"ws://localhost:\d+[^\s]*",
            r"ws://127\.0\.0\.1:\d+[^\s]*",
            r"http://localhost[^\s]*",
            r"ws://localhost[^\s]*",
        ]

        for pattern in url_patterns:
            text = re.sub(pattern, "[INTERNAL_URL]", text)

        return text

    def _mask_potential_secrets(self, text: str) -> str:
        """Mask strings that might be secrets."""

        # Don't mask if it contains already sanitized content
        if "[INTERNAL_URL]" in text or "[REDACTED_PATH]" in text:
            return text

        for pattern in self.SENSITIVE_PATTERNS["secrets"]:
            # Only mask if the string looks like a token (long alphanumeric)
            matches = re.findall(pattern, text)
            for match in matches:
                if len(match) > 16:  # Only mask long strings
                    # Don't mask if it looks like a URL or path component
                    if not any(x in match for x in ["://", "/", "\\", "."]):
                        masked = match[:4] + "*" * (len(match) - 8) + match[-4:]
                        text = text.replace(match, masked)

        return text

    def _mask_sensitive_value(self, value: str) -> str:
        """Mask a known sensitive value."""

        if len(value) <= 4:
            return "***"
        elif len(value) <= 8:
            return value[0] + "*" * (len(value) - 1)
        else:
            return value[:2] + "*" * (len(value) - 4) + value[-2:]

    def _deep_copy_dict(self, obj: t.Any) -> t.Any:
        """Deep copy a dictionary-like object safely."""

        if isinstance(obj, dict):
            return {key: self._deep_copy_dict(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy_dict(item) for item in obj]
        else:
            return obj

    def _get_timestamp(self) -> float:
        """Get current timestamp."""
        import time

        return time.time()

    def format_error_response(
        self,
        error_message: str,
        verbosity: StatusVerbosity = StatusVerbosity.STANDARD,
        include_details: bool = False,
    ) -> dict[str, t.Any]:
        """
        Format error responses without leaking system details.

        Args:
            error_message: Original error message
            verbosity: Output verbosity level
            include_details: Whether to include error details

        Returns:
            Sanitized error response
        """

        # Generic error messages for production use
        generic_messages = {
            "connection": "Service temporarily unavailable. Please try again later.",
            "validation": "Invalid request parameters.",
            "permission": "Access denied.",
            "resource": "Requested resource not found.",
            "internal": "An internal error occurred. Please contact support.",
        }

        # Determine error type and use appropriate generic message
        error_type = self._classify_error(error_message)

        if verbosity == StatusVerbosity.MINIMAL:
            return {
                "success": False,
                "error": generic_messages.get(error_type, generic_messages["internal"]),
                "timestamp": self._get_timestamp(),
            }

        # For higher verbosity levels, include sanitized original message
        sanitized_message = self._sanitize_string(error_message, verbosity)

        response = {
            "success": False,
            "error": sanitized_message,
            "error_type": error_type,
            "timestamp": self._get_timestamp(),
        }

        if include_details and verbosity in (
            StatusVerbosity.DETAILED,
            StatusVerbosity.FULL,
        ):
            response["details"] = {
                "verbosity": verbosity.value,
                "sanitized": verbosity != StatusVerbosity.FULL,
            }

        return response

    def _classify_error(self, error_message: str) -> str:
        """Classify error message type for appropriate handling."""

        error_patterns = {
            "connection": ["connection", "timeout", "refused", "unavailable"],
            "validation": ["invalid", "validation", "format", "parameter"],
            "permission": ["permission", "access", "denied", "unauthorized"],
            "resource": ["not found", "missing", "does not exist"],
        }

        error_lower = error_message.lower()

        for error_type, patterns in error_patterns.items():
            if any(pattern in error_lower for pattern in patterns):
                return error_type

        return "internal"


# Singleton instance for global use
_secure_formatter: SecureStatusFormatter | None = None


def get_secure_status_formatter(
    project_root: Path | None = None,
) -> SecureStatusFormatter:
    """Get the global secure status formatter instance."""

    global _secure_formatter
    if _secure_formatter is None:
        _secure_formatter = SecureStatusFormatter(project_root)
    return _secure_formatter


def format_secure_status(
    status_data: dict[str, t.Any],
    verbosity: StatusVerbosity = StatusVerbosity.STANDARD,
    project_root: Path | None = None,
    user_context: str | None = None,
) -> dict[str, t.Any]:
    """
    Convenience function for secure status formatting.

    Args:
        status_data: Raw status data to sanitize
        verbosity: Output verbosity level
        project_root: Project root for relative path conversion
        user_context: Optional user context for logging

    Returns:
        Sanitized status data
    """

    formatter = get_secure_status_formatter(project_root)
    return formatter.format_status(status_data, verbosity, user_context)
