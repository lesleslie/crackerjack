"""Unit tests for secure status formatting."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

import crackerjack.services.secure_status_formatter as secure_status_formatter_module
from crackerjack.services.secure_status_formatter import (
    SecureStatusFormatter,
    StatusVerbosity,
    format_secure_status,
    get_secure_status_formatter,
)


@pytest.fixture
def security_logger() -> Mock:
    return Mock()


@pytest.fixture
def formatter(tmp_path: Path, security_logger: Mock) -> SecureStatusFormatter:
    with patch(
        "crackerjack.services.secure_status_formatter.get_security_logger",
        return_value=security_logger,
    ):
        return SecureStatusFormatter(project_root=tmp_path)


def test_format_status_minimal_sanitizes_sensitive_values_and_adds_metadata(
    formatter: SecureStatusFormatter,
    security_logger: Mock,
    tmp_path: Path,
) -> None:
    payload = {
        "project_path": str(tmp_path / "project"),
        "progress_dir": "/tmp/crackerjack-progress",
        "traceback": "secret traceback",
        "token": "abcdefghijklmnopqrstu",
        "nested": {
            "auth": "supersecretvalue",
            "keep": "ok",
        },
        "items": ["plain", "abcdefghijklmnopqrstuvwxyz"],
    }

    with patch("crackerjack.services.secure_status_formatter.time.time", return_value=123.45):
        result = formatter.format_status(payload, StatusVerbosity.MINIMAL, user_context="cli")

    assert "progress_dir" not in result
    assert "traceback" not in result
    assert result["token"] == "ab*****************tu"
    assert result["nested"]["auth"] == "su************use"
    assert result["nested"]["keep"] == "ok"
    assert result["items"] == ["plain", "abcdefghijklmnopqrstuvwxyz"]
    assert result["_security"] == {
        "sanitized": True,
        "verbosity": "minimal",
        "timestamp": 123.45,
    }
    security_logger.log_status_access_attempt.assert_called_once()


def test_format_status_full_keeps_original_values(formatter: SecureStatusFormatter) -> None:
    payload = {"token": "abcdefghijklmnop", "path": "/tmp/example"}

    result = formatter.format_status(payload, StatusVerbosity.FULL)

    assert result["token"] == "abcdefghijklmnop"
    assert result["path"] == "/tmp/example"
    assert result["_security"]["verbosity"] == "full"


def test_string_sanitization_helpers(formatter: SecureStatusFormatter, tmp_path: Path) -> None:
    path_text = f"{tmp_path / 'nested' / 'file.txt'} and /var/tmp/secret.txt"

    with patch(
        "crackerjack.services.secure_status_formatter.SAFE_PATTERNS",
        {"detect_absolute_unix_paths": None},
    ):
        sanitized = formatter._sanitize_paths(path_text)

    assert "./nested/file.txt" in sanitized
    assert "[REDACTED_PATH]" in sanitized
    assert formatter._sanitize_string("plain", StatusVerbosity.FULL) == "plain"
    assert formatter._should_skip_secret_masking("[INTERNAL_URL] token") is True
    assert formatter._mask_sensitive_value("abcd") == "***"
    assert formatter._mask_sensitive_value("abcdefgh") == "a*******"
    assert formatter._create_masked_string("abcdefghijklmnop") == "abcd********mnop"


def test_error_response_formatting_and_classification(formatter: SecureStatusFormatter) -> None:
    assert formatter._classify_error("connection refused") == "connection"
    assert formatter._classify_error("invalid parameter") == "validation"
    assert formatter._classify_error("access denied") == "permission"
    assert formatter._classify_error("resource not found") == "resource"
    assert formatter._classify_error("unexpected failure") == "internal"

    with patch("crackerjack.services.secure_status_formatter.time.time", return_value=200.0):
        minimal = formatter.format_error_response(
            "connection refused on /tmp/secret",
            StatusVerbosity.MINIMAL,
        )
        detailed = formatter.format_error_response(
            "invalid parameter",
            StatusVerbosity.DETAILED,
            include_details=True,
        )

    assert minimal["success"] is False
    assert minimal["error"].startswith("Service temporarily unavailable")
    assert detailed["error_type"] == "validation"
    assert detailed["details"] == {"verbosity": "detailed", "sanitized": True}


def test_get_secure_status_formatter_singleton(tmp_path: Path, security_logger: Mock) -> None:
    secure_status_formatter_module._secure_formatter = None

    with patch(
        "crackerjack.services.secure_status_formatter.get_security_logger",
        return_value=security_logger,
    ):
        first = get_secure_status_formatter(tmp_path)
        second = get_secure_status_formatter(Path("/other"))

    assert first is second


def test_format_secure_status_wrapper(tmp_path: Path, security_logger: Mock) -> None:
    secure_status_formatter_module._secure_formatter = None

    with patch(
        "crackerjack.services.secure_status_formatter.get_security_logger",
        return_value=security_logger,
    ):
        result = format_secure_status({"value": "x"}, StatusVerbosity.MINIMAL, tmp_path)

    assert isinstance(result, dict)
    assert result["value"] == "x"
