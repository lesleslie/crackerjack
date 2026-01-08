import tempfile
import time
import typing as t
from contextlib import suppress
from enum import Enum
from pathlib import Path

from crackerjack.models.protocols import SecureStatusFormatterProtocol, ServiceProtocol

from .regex_patterns import SAFE_PATTERNS, CompiledPatternCache, sanitize_internal_urls
from .security_logger import get_security_logger


class StatusVerbosity(str, Enum):
    MINIMAL = "minimal"
    STANDARD = "standard"
    DETAILED = "detailed"
    FULL = "full"


class SecureStatusFormatter(SecureStatusFormatterProtocol, ServiceProtocol):
    SENSITIVE_PATTERNS = {
        "absolute_paths": [
            r"(/[^/\s]*){2, }",
            rf"{tempfile.gettempdir()}/[^\s]*",
            r"/var/[^\s]*",
            r"/home/[^\s]*",
        ],
        "internal_urls": [
            r"https?: //localhost: \d+",
            r"https?: //127\.0\.0\.1: \d+",
            r"https?: //0\.0\.0\.0: \d+",
            r"ws: //localhost: \d+",
            r"ws: //127\.0\.0\.1: \d+",
        ],
        "secrets": [
            r"[A-Za-z0-9]{20, }",
            r"[A-Za-z0-9+/]{32, }={0, 2}",
        ],
        "system_ids": [
            r"pid: \d+",
            r"process_id: \s*\d+",
        ],
    }

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
        self.project_root = project_root or Path.cwd()
        self.security_logger = get_security_logger()

    def initialize(self) -> None:
        pass

    def cleanup(self) -> None:
        pass

    def health_check(self) -> bool:
        return True

    def shutdown(self) -> None:
        pass

    def metrics(self) -> dict[str, t.Any]:
        return {}

    def is_healthy(self) -> bool:
        return True

    def register_resource(self, resource: t.Any) -> None:
        pass

    def cleanup_resource(self, resource: t.Any) -> None:
        pass

    def record_error(self, error: Exception) -> None:
        pass

    def increment_requests(self) -> None:
        pass

    def get_custom_metric(self, name: str) -> t.Any:
        return None

    def set_custom_metric(self, name: str, value: t.Any) -> None:
        pass

    def format_status(
        self,
        status_data: dict[str, t.Any],
        verbosity: StatusVerbosity = StatusVerbosity.STANDARD,
        user_context: str | None = None,
    ) -> dict[str, t.Any]:
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
        self.security_logger.log_status_access_attempt(
            endpoint="status_data",
            verbosity_level=verbosity.value,
            user_context=user_context,
            data_keys=list[t.Any](status_data.keys()),
        )

    def _prepare_data_for_sanitization(
        self, status_data: dict[str, t.Any]
    ) -> dict[str, t.Any]:
        return self._deep_copy_dict(status_data)  # type: ignore[no-any-return]

    def _apply_all_sanitization_steps(
        self, data: dict[str, t.Any], verbosity: StatusVerbosity
    ) -> dict[str, t.Any]:
        data = self._apply_verbosity_filter(data, verbosity)
        return self._sanitize_sensitive_data(data, verbosity)

    def _add_security_metadata(
        self, data: dict[str, t.Any], verbosity: StatusVerbosity
    ) -> dict[str, t.Any]:
        data["_security"] = {
            "sanitized": True,
            "verbosity": verbosity.value,
            "timestamp": self._get_timestamp(),
        }
        return data

    def _apply_verbosity_filter(
        self, data: dict[str, t.Any], verbosity: StatusVerbosity
    ) -> dict[str, t.Any]:
        if verbosity == StatusVerbosity.MINIMAL:
            remove_keys = self.SENSITIVE_KEYS["remove_minimal"]
        elif verbosity == StatusVerbosity.STANDARD:
            remove_keys = self.SENSITIVE_KEYS["remove_standard"]
        else:
            remove_keys = set()

        for key in list[t.Any](data.keys()):
            if key in remove_keys:
                del data[key]

        for key, value in data.items():
            if isinstance(value, dict):
                data[key] = self._apply_verbosity_filter(value, verbosity)

        return data

    def _sanitize_sensitive_data(
        self, data: dict[str, t.Any], verbosity: StatusVerbosity
    ) -> dict[str, t.Any]:
        return self._sanitize_recursive(data, verbosity)  # type: ignore[no-any-return]

    def _sanitize_recursive(self, obj: t.Any, verbosity: StatusVerbosity) -> t.Any:
        if isinstance(obj, dict):
            sanitized = {}
            for key, value in obj.items():
                sanitized_key = self._sanitize_string(key, verbosity)

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
        if verbosity == StatusVerbosity.FULL:
            return text

        return self._apply_string_sanitization_pipeline(text, verbosity)

    def _apply_string_sanitization_pipeline(
        self, text: str, verbosity: StatusVerbosity
    ) -> str:
        sanitized = self._sanitize_internal_urls(text)
        sanitized = self._sanitize_paths(sanitized)
        return self._apply_secret_masking_if_needed(sanitized, verbosity)

    def _apply_secret_masking_if_needed(
        self, text: str, verbosity: StatusVerbosity
    ) -> str:
        if verbosity == StatusVerbosity.MINIMAL:
            return self._mask_potential_secrets(text)
        return text

    def _sanitize_paths(self, text: str) -> str:
        unix_path_pattern = SAFE_PATTERNS.get("detect_absolute_unix_paths")

        if not unix_path_pattern:
            return self._sanitize_paths_fallback(text)

        return text

    def _sanitize_paths_fallback(self, text: str) -> str:
        path_patterns = [
            r"/[a-zA-Z0-9_\-\.\/]+",
            r"[A-Z]: [\\\/][a-zA-Z0-9_\-\.\\\/]+",
        ]

        for pattern_str in path_patterns:
            text = self._process_path_pattern(text, pattern_str)

        return text

    def _process_path_pattern(self, text: str, pattern_str: str) -> str:
        with suppress(Exception):
            compiled = CompiledPatternCache.get_compiled_pattern(pattern_str)
            matches = compiled.findall(text)

            for match in matches:
                if len(match) > 3:
                    text = self._replace_path_match(text, match)

        return text

    def _replace_path_match(self, text: str, match: str) -> str:
        try:
            abs_path = Path(match)
            if abs_path.is_absolute():
                return self._convert_to_relative_or_redact(text, match, abs_path)
        except (ValueError, OSError):
            text = text.replace(match, "[REDACTED_PATH]")

        return text

    def _convert_to_relative_or_redact(
        self, text: str, match: str, abs_path: Path
    ) -> str:
        try:
            rel_path = abs_path.relative_to(self.project_root)
            return text.replace(match, f"./{rel_path}")
        except (ValueError, OSError):
            return text.replace(match, "[REDACTED_PATH]")

    def _sanitize_internal_urls(self, text: str) -> str:
        return sanitize_internal_urls(text)

    def _mask_potential_secrets(self, text: str) -> str:
        if self._should_skip_secret_masking(text):
            return text

        patterns_to_check = self._get_validated_secret_patterns()

        if patterns_to_check:
            return self._apply_validated_secret_patterns(text, patterns_to_check)
        return self._apply_fallback_secret_patterns(text)

    def _should_skip_secret_masking(self, text: str) -> bool:
        return "[INTERNAL_URL]" in text or "[REDACTED_PATH]" in text

    def _get_validated_secret_patterns(self) -> list[t.Any]:
        patterns = []
        long_alphanumeric = SAFE_PATTERNS.get("detect_long_alphanumeric_tokens")
        base64_like = SAFE_PATTERNS.get("detect_base64_like_strings")

        if long_alphanumeric:
            patterns.append(long_alphanumeric)
        if base64_like:
            patterns.append(base64_like)

        return patterns

    def _apply_validated_secret_patterns(self, text: str, patterns: list[t.Any]) -> str:
        for pattern in patterns:
            try:
                text = self._mask_pattern_matches(text, pattern.findall(text))
            except Exception:
                continue
        return text

    def _apply_fallback_secret_patterns(self, text: str) -> str:
        for pattern_str in self.SENSITIVE_PATTERNS["secrets"]:
            try:
                compiled = CompiledPatternCache.get_compiled_pattern(pattern_str)
                text = self._mask_pattern_matches(text, compiled.findall(text))
            except Exception:
                continue
        return text

    def _mask_pattern_matches(self, text: str, matches: list[str]) -> str:
        for match in matches:
            if self._should_mask_match(match):
                masked = self._create_masked_string(match)
                text = text.replace(match, masked)
        return text

    def _should_mask_match(self, match: str) -> bool:
        if len(match) <= 16:
            return False

        return not any(x in match for x in (": //", "/", "\\", "."))

    def _create_masked_string(self, text: str) -> str:
        return text[:4] + "*" * (len(text) - 8) + text[-4:]

    def _mask_sensitive_value(self, value: str) -> str:
        if len(value) <= 4:
            return "***"
        elif len(value) <= 8:
            return value[0] + "*" * (len(value) - 1)
        return value[:2] + "*" * (len(value) - 4) + value[-2:]

    def _deep_copy_dict(self, obj: t.Any) -> t.Any:
        if isinstance(obj, dict):
            return {key: self._deep_copy_dict(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy_dict(item) for item in obj]
        return obj

    def _get_timestamp(self) -> float:
        return time.time()

    def format_error_response(
        self,
        error_message: str,
        verbosity: StatusVerbosity = StatusVerbosity.STANDARD,
        include_details: bool = False,
    ) -> dict[str, t.Any]:
        error_type = self._classify_error(error_message)

        if verbosity == StatusVerbosity.MINIMAL:
            return self._create_minimal_error_response(error_type)

        return self._create_detailed_error_response(
            error_message, error_type, verbosity, include_details
        )

    def _create_minimal_error_response(self, error_type: str) -> dict[str, t.Any]:
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
        return include_details and verbosity in (
            StatusVerbosity.DETAILED,
            StatusVerbosity.FULL,
        )

    def _classify_error(self, error_message: str) -> str:
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


_secure_formatter: SecureStatusFormatter | None = None


def get_secure_status_formatter(
    project_root: Path | None = None,
) -> SecureStatusFormatter:
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
    return get_secure_status_formatter(project_root).format_status(
        status_data, verbosity, user_context
    )
