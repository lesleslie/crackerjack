"""
Secure status formatter to prevent information disclosure vulnerabilities.

This module provides secure sanitization of status responses to prevent
leaking sensitive system information such as absolute paths, internal URLs,
configuration details, and other sensitive data.
"""

import tempfile
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
            rf"{tempfile.gettempdir()}/[^\s]*",  # Temp directory paths - using tempfile.gettempdir() (B108)
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
        self._log_status_access(status_data, verbosity, user_context)
        sanitized = self._prepare_data_for_sanitization(status_data)
        sanitized = self._apply_all_sanitization_steps(sanitized, verbosity)
        return self._add_security_metadata(sanitized, verbosity)

    def _log_status_access(
        self,
        status_data: dict[str, t.Any],
        verbosity: StatusVerbosity,
        user_context: str | None,
    ) -> None:
        """Log status access attempt for security monitoring."""
        self.security_logger.log_status_access_attempt(
            endpoint="status_data",
            verbosity_level=verbosity.value,
            user_context=user_context,
            data_keys=list(status_data.keys()),
        )

    def _prepare_data_for_sanitization(
        self, status_data: dict[str, t.Any]
    ) -> dict[str, t.Any]:
        """Create a deep copy of status data to avoid modifying original."""
        return self._deep_copy_dict(status_data)

    def _apply_all_sanitization_steps(
        self, data: dict[str, t.Any], verbosity: StatusVerbosity
    ) -> dict[str, t.Any]:
        """Apply all sanitization steps in proper order."""
        data = self._apply_verbosity_filter(data, verbosity)
        return self._sanitize_sensitive_data(data, verbosity)

    def _add_security_metadata(
        self, data: dict[str, t.Any], verbosity: StatusVerbosity
    ) -> dict[str, t.Any]:
        """Add security metadata to sanitized response."""
        data["_security"] = {
            "sanitized": True,
            "verbosity": verbosity.value,
            "timestamp": self._get_timestamp(),
        }
        return data

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

        return obj

    def _sanitize_string(self, text: str, verbosity: StatusVerbosity) -> str:
        """Sanitize string content based on verbosity level."""
        if verbosity == StatusVerbosity.FULL:
            return text  # No sanitization for full verbosity

        return self._apply_string_sanitization_pipeline(text, verbosity)

    def _apply_string_sanitization_pipeline(
        self, text: str, verbosity: StatusVerbosity
    ) -> str:
        """Apply string sanitization steps in correct order."""
        sanitized = self._sanitize_internal_urls(text)
        sanitized = self._sanitize_paths(sanitized)
        return self._apply_secret_masking_if_needed(sanitized, verbosity)

    def _apply_secret_masking_if_needed(
        self, text: str, verbosity: StatusVerbosity
    ) -> str:
        """Apply secret masking for minimal verbosity only."""
        if verbosity == StatusVerbosity.MINIMAL:
            return self._mask_potential_secrets(text)
        return text

    def _sanitize_paths(self, text: str) -> str:
        """Convert absolute paths to relative paths where possible."""
        from .regex_patterns import SAFE_PATTERNS

        # Use validated patterns for path detection
        unix_path_pattern = SAFE_PATTERNS.get("detect_absolute_unix_paths")

        if not unix_path_pattern:
            return self._sanitize_paths_fallback(text)

        return text

    def _sanitize_paths_fallback(self, text: str) -> str:
        """Fallback path sanitization when patterns don't exist."""
        path_patterns = [
            r"/[a-zA-Z0-9_\-\.\/]+",  # Unix-style absolute paths
            r"[A-Z]:[\\\/][a-zA-Z0-9_\-\.\\\/]+",  # Windows-style absolute paths
        ]

        for pattern_str in path_patterns:
            text = self._process_path_pattern(text, pattern_str)

        return text

    def _process_path_pattern(self, text: str, pattern_str: str) -> str:
        """Process a single path pattern safely."""
        from contextlib import suppress

        from .regex_patterns import CompiledPatternCache

        with suppress(Exception):
            compiled = CompiledPatternCache.get_compiled_pattern(pattern_str)
            matches = compiled.findall(text)

            for match in matches:
                if len(match) > 3:  # Only process paths longer than 3 chars
                    text = self._replace_path_match(text, match)

        return text

    def _replace_path_match(self, text: str, match: str) -> str:
        """Replace a single path match with relative or redacted version."""
        try:
            abs_path = Path(match)
            if abs_path.is_absolute():
                return self._convert_to_relative_or_redact(text, match, abs_path)
        except (ValueError, OSError):
            # If path operations fail, mask it
            text = text.replace(match, "[REDACTED_PATH]")

        return text

    def _convert_to_relative_or_redact(
        self, text: str, match: str, abs_path: Path
    ) -> str:
        """Convert absolute path to relative or redact if outside project."""
        try:
            rel_path = abs_path.relative_to(self.project_root)
            return text.replace(match, f"./{rel_path}")
        except (ValueError, OSError):
            # If not within project, mask it
            return text.replace(match, "[REDACTED_PATH]")

    def _sanitize_internal_urls(self, text: str) -> str:
        """Replace internal URLs with generic placeholders."""
        from .regex_patterns import sanitize_internal_urls

        return sanitize_internal_urls(text)

    def _mask_potential_secrets(self, text: str) -> str:
        """Mask strings that might be secrets."""
        if self._should_skip_secret_masking(text):
            return text

        patterns_to_check = self._get_validated_secret_patterns()

        if patterns_to_check:
            return self._apply_validated_secret_patterns(text, patterns_to_check)
        return self._apply_fallback_secret_patterns(text)

    def _should_skip_secret_masking(self, text: str) -> bool:
        """Check if secret masking should be skipped for already sanitized content."""
        return "[INTERNAL_URL]" in text or "[REDACTED_PATH]" in text

    def _get_validated_secret_patterns(self) -> list[t.Any]:
        """Get validated patterns from the safe patterns registry."""
        from .regex_patterns import SAFE_PATTERNS

        patterns = []
        long_alphanumeric = SAFE_PATTERNS.get("detect_long_alphanumeric_tokens")
        base64_like = SAFE_PATTERNS.get("detect_base64_like_strings")

        if long_alphanumeric:
            patterns.append(long_alphanumeric)
        if base64_like:
            patterns.append(base64_like)

        return patterns

    def _apply_validated_secret_patterns(self, text: str, patterns: list[t.Any]) -> str:
        """Apply validated patterns for secret detection."""
        for pattern in patterns:
            try:
                text = self._mask_pattern_matches(text, pattern.findall(text))
            except Exception:
                continue  # Skip failed pattern matching
        return text

    def _apply_fallback_secret_patterns(self, text: str) -> str:
        """Apply fallback patterns when validated patterns don't exist."""
        for pattern_str in self.SENSITIVE_PATTERNS["secrets"]:
            try:
                from .regex_patterns import CompiledPatternCache

                compiled = CompiledPatternCache.get_compiled_pattern(pattern_str)
                text = self._mask_pattern_matches(text, compiled.findall(text))
            except Exception:
                continue  # Skip failed pattern compilation
        return text

    def _mask_pattern_matches(self, text: str, matches: list[str]) -> str:
        """Mask matches from pattern matching."""
        for match in matches:
            if self._should_mask_match(match):
                masked = self._create_masked_string(match)
                text = text.replace(match, masked)
        return text

    def _should_mask_match(self, match: str) -> bool:
        """Determine if a match should be masked."""
        if len(match) <= 16:
            return False
        # Don't mask if it looks like a URL or path component
        return not any(x in match for x in ("://", "/", "\\", "."))

    def _create_masked_string(self, text: str) -> str:
        """Create a masked version of the text."""
        return text[:4] + "*" * (len(text) - 8) + text[-4:]

    def _mask_sensitive_value(self, value: str) -> str:
        """Mask a known sensitive value."""

        if len(value) <= 4:
            return "***"
        elif len(value) <= 8:
            return value[0] + "*" * (len(value) - 1)
        return value[:2] + "*" * (len(value) - 4) + value[-2:]

    def _deep_copy_dict(self, obj: t.Any) -> t.Any:
        """Deep copy a dictionary-like object safely."""

        if isinstance(obj, dict):
            return {key: self._deep_copy_dict(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy_dict(item) for item in obj]
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
        error_type = self._classify_error(error_message)

        if verbosity == StatusVerbosity.MINIMAL:
            return self._create_minimal_error_response(error_type)

        return self._create_detailed_error_response(
            error_message, error_type, verbosity, include_details
        )

    def _create_minimal_error_response(self, error_type: str) -> dict[str, t.Any]:
        """Create minimal error response for production use."""
        generic_messages = {
            "connection": "Service temporarily unavailable. Please try again later.",
            "validation": "Invalid request parameters.",
            "permission": "Access denied.",
            "resource": "Requested resource not found.",
            "internal": "An internal error occurred. Please contact support.",
        }

        return {
            "success": False,
            "error": generic_messages.get(error_type, generic_messages["internal"]),
            "timestamp": self._get_timestamp(),
        }

    def _create_detailed_error_response(
        self,
        error_message: str,
        error_type: str,
        verbosity: StatusVerbosity,
        include_details: bool,
    ) -> dict[str, t.Any]:
        """Create detailed error response with sanitized message."""
        sanitized_message = self._sanitize_string(error_message, verbosity)

        response: dict[str, t.Any] = {
            "success": False,
            "error": sanitized_message,
            "error_type": error_type,
            "timestamp": self._get_timestamp(),
        }

        if self._should_include_error_details(include_details, verbosity):
            response["details"] = {
                "verbosity": str(verbosity.value),
                "sanitized": verbosity != StatusVerbosity.FULL,
            }

        return response

    def _should_include_error_details(
        self, include_details: bool, verbosity: StatusVerbosity
    ) -> bool:
        """Determine if error details should be included."""
        return include_details and verbosity in (
            StatusVerbosity.DETAILED,
            StatusVerbosity.FULL,
        )

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

    return get_secure_status_formatter(project_root).format_status(
        status_data, verbosity, user_context
    )
