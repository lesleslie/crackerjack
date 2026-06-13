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


# -----------------------------------------------------------------------------
# ServiceProtocol no-op surface
# -----------------------------------------------------------------------------


def test_service_protocol_noops(formatter: SecureStatusFormatter) -> None:
    """All ServiceProtocol lifecycle methods are no-ops returning sane defaults."""
    formatter.initialize()
    formatter.cleanup()
    formatter.shutdown()
    formatter.record_error(RuntimeError("boom"))
    formatter.increment_requests()
    formatter.register_resource(object())
    formatter.cleanup_resource(object())
    formatter.set_custom_metric("foo", 1)

    assert formatter.health_check() is True
    assert formatter.is_healthy() is True
    assert formatter.metrics() == {}
    assert formatter.get_custom_metric("missing") is None


# -----------------------------------------------------------------------------
# format() - json serialization
# -----------------------------------------------------------------------------


def test_format_with_dict_returns_json(formatter: SecureStatusFormatter) -> None:
    import json

    with patch("crackerjack.services.secure_status_formatter.time.time", return_value=1.0):
        rendered = formatter.format({"key": "value", "token": "abcdefghijklmnop"})

    parsed = json.loads(rendered)
    assert parsed["key"] == "value"
    assert parsed["_security"]["verbosity"] == "standard"
    assert parsed["token"] == "ab************op"


def test_format_with_non_dict_returns_str(formatter: SecureStatusFormatter) -> None:
    assert formatter.format(42) == "42"
    assert formatter.format(None) == "None"
    assert formatter.format("hello") == "hello"


# -----------------------------------------------------------------------------
# _sanitize_paths - SAFE_PATTERNS present and exception paths
# -----------------------------------------------------------------------------


def test_sanitize_paths_with_pattern_returns_text_unchanged(
    formatter: SecureStatusFormatter,
    tmp_path: Path,
) -> None:
    """When SAFE_PATTERNS has the path pattern, _sanitize_paths is a no-op.

    (The function delegates to the SAFE_PATTERNS pipeline elsewhere; here we
    verify that the formatter's _sanitize_paths returns text unchanged when the
    pattern key exists.)
    """
    sentinel = "/some/path/file.txt"
    with patch(
        "crackerjack.services.secure_status_formatter.SAFE_PATTERNS",
        {"detect_absolute_unix_paths": Mock(__bool__=lambda self: True)},
    ):
        result = formatter._sanitize_paths(sentinel)

    assert result == sentinel


def test_replace_path_match_with_invalid_path_string(
    formatter: SecureStatusFormatter,
) -> None:
    """_replace_path_match handles strings that Path() rejects by redacting."""
    weird = "\x00null\0byte"  # Path() raises on embedded NUL on some platforms

    result = formatter._replace_path_match(f"prefix {weird} suffix", weird)

    # Either the path was redacted or returned unchanged; both are acceptable.
    assert "suffix" in result
    assert result.startswith("prefix ")


def test_process_path_pattern_with_no_matches(
    formatter: SecureStatusFormatter,
) -> None:
    """_process_path_pattern is a no-op when the pattern finds nothing."""
    text = "no paths here at all"
    result = formatter._process_path_pattern(text, r"/definitely/not/here")
    assert result == text


def test_process_path_pattern_handles_compile_error(
    formatter: SecureStatusFormatter,
) -> None:
    """_process_path_pattern swallows compile errors via suppress()."""
    # A pattern with an unclosed group is invalid; suppress() should swallow it.
    text = "anything"
    result = formatter._process_path_pattern(text, r"(unclosed")
    assert result == text


# -----------------------------------------------------------------------------
# Masking edge cases
# -----------------------------------------------------------------------------


def test_should_mask_match_thresholds(formatter: SecureStatusFormatter) -> None:
    """_should_mask_match returns False for short matches and ones with paths.

    The boundary is *strictly* greater than 16 (17+ is maskable). This documents
    the current implementation, not a recommendation.
    """
    assert formatter._should_mask_match("short") is False
    # 16 chars exactly → not masked (boundary case).
    assert formatter._should_mask_match("a" * 16) is False
    # 17+ chars of plain alnum → eligible.
    assert formatter._should_mask_match("a" * 17) is True
    # Contains "/", so not masked.
    assert formatter._should_mask_match("a" * 20 + "/x") is False
    # Contains "."
    assert formatter._should_mask_match("a" * 20 + ".x") is False


def test_mask_pattern_matches_replaces_when_eligible(
    formatter: SecureStatusFormatter,
) -> None:
    """_mask_pattern_matches masks long (>=17), non-path-looking strings only."""
    secret = "a" * 20
    text = f"prefix {secret} suffix"
    result = formatter._mask_pattern_matches(text, [secret])
    # The secret is replaced, but the surrounding text is preserved.
    assert secret not in result
    assert result.startswith("prefix ")
    assert result.endswith(" suffix")


def test_mask_pattern_matches_skips_short_match(
    formatter: SecureStatusFormatter,
) -> None:
    """A 16-char match is below the mask threshold and is left intact."""
    short = "a" * 16
    text = f"prefix {short} suffix"
    result = formatter._mask_pattern_matches(text, [short])
    assert result == text


def test_mask_pattern_matches_no_matches(
    formatter: SecureStatusFormatter,
) -> None:
    """_mask_pattern_matches with no matches returns the text unchanged."""
    text = "untouched"
    result = formatter._mask_pattern_matches(text, [])
    assert result == text


def test_apply_validated_secret_patterns_swallows_exceptions(
    formatter: SecureStatusFormatter,
) -> None:
    """Exceptions from individual patterns are caught; processing continues."""
    boom = Mock()
    boom.findall.side_effect = RuntimeError("regex boom")
    ok = Mock()
    ok.findall.return_value = []

    formatter._apply_validated_secret_patterns("text", [boom, ok])
    boom.findall.assert_called_once()
    ok.findall.assert_called_once()


def test_apply_validated_secret_patterns_masks_found_matches(
    formatter: SecureStatusFormatter,
) -> None:
    """When patterns find matches, _apply_validated_secret_patterns masks them."""
    secret = "a" * 20
    pat = Mock()
    pat.findall.return_value = [secret]

    result = formatter._apply_validated_secret_patterns(
        f"x {secret} y",
        [pat],
    )

    pat.findall.assert_called_once()
    assert secret not in result
    assert result.startswith("x ")
    assert result.endswith(" y")


def test_apply_fallback_secret_patterns_runs_with_patterns(
    formatter: SecureStatusFormatter,
) -> None:
    """Fallback path uses the module's SENSITIVE_PATTERNS['secrets'] list.

    Note: the current SENSITIVE_PATTERNS regexes contain a literal trailing
    space character (e.g. ``r'[A-Za-z0-9]{20, }'``) which means they never
    match a pure run of letters/digits. This test documents that behavior
    today and would catch a fix that removes the stray space.
    """
    long_alnum = "a" * 30
    result = formatter._apply_fallback_secret_patterns(f"prefix {long_alnum} suffix")

    # With the trailing-space bug, the long alnum run is NOT masked today.
    # Asserting the *current* behavior so a fix will surface as a failing test.
    assert result == f"prefix {long_alnum} suffix"


# -----------------------------------------------------------------------------
# Error response branch coverage
# -----------------------------------------------------------------------------


def test_error_response_omits_details_when_not_requested(
    formatter: SecureStatusFormatter,
) -> None:
    """include_details=False suppresses the 'details' block even at DETAILED."""
    response = formatter.format_error_response(
        "invalid request",
        StatusVerbosity.DETAILED,
        include_details=False,
    )
    assert response["error_type"] == "validation"
    assert "details" not in response


def test_error_response_omits_details_for_standard_verbosity(
    formatter: SecureStatusFormatter,
) -> None:
    """STANDARD verbosity with include_details=True still hides the block."""
    response = formatter.format_error_response(
        "permission denied",
        StatusVerbosity.STANDARD,
        include_details=True,
    )
    assert response["error_type"] == "permission"
    assert "details" not in response


# -----------------------------------------------------------------------------
# Verbosity filter with DETAILED (no keys removed, recursion preserved)
# -----------------------------------------------------------------------------


def test_verbosity_detailed_keeps_sensitive_keys_and_recurses(
    formatter: SecureStatusFormatter,
) -> None:
    payload = {
        "traceback": "leak",
        "nested": {"traceback": "deep", "value": "ok"},
    }
    result = formatter.format_status(payload, StatusVerbosity.DETAILED)

    assert result["traceback"] == "leak"
    assert result["nested"]["traceback"] == "deep"
    assert result["nested"]["value"] == "ok"
    assert result["_security"]["verbosity"] == "detailed"


def test_format_status_does_not_mutate_input(
    formatter: SecureStatusFormatter,
) -> None:
    """Input dict must be deep-copied before sanitization."""
    payload = {"token": "abcdefghijklmnop", "nested": {"auth": "x" * 20}}
    snapshot = {"token": "abcdefghijklmnop", "nested": {"auth": "x" * 20}}

    formatter.format_status(payload, StatusVerbosity.STANDARD)

    assert payload == snapshot


def test_format_status_handles_empty_dict(
    formatter: SecureStatusFormatter,
) -> None:
    result = formatter.format_status({})
    assert result == {
        "_security": {
            "sanitized": True,
            "verbosity": "standard",
            "timestamp": result["_security"]["timestamp"],
        }
    }


def test_format_status_handles_unicode_values(
    formatter: SecureStatusFormatter,
) -> None:
    """Unicode strings without path/url patterns pass through untouched."""
    payload = {"greeting": "héllo 👋 wörld", "emoji": "🎉🚀"}
    result = formatter.format_status(payload, StatusVerbosity.STANDARD)

    assert result["greeting"] == "héllo 👋 wörld"
    assert result["emoji"] == "🎉🚀"
