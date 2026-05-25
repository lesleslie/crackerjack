"""Unit tests for validation rate limiting."""

from __future__ import annotations

from collections import deque
from unittest.mock import Mock, patch

import pytest

import crackerjack.services.validation_rate_limiter as validation_rate_limiter_module
from crackerjack.services.validation_rate_limiter import (
    ValidationRateLimit,
    ValidationRateLimiter,
    get_validation_rate_limiter,
)


@pytest.fixture
def rate_limiter() -> ValidationRateLimiter:
    logger = Mock()
    with patch(
        "crackerjack.services.validation_rate_limiter.get_security_logger",
        return_value=logger,
    ):
        yield ValidationRateLimiter()


def test_record_failure_blocks_client_and_clears_window(rate_limiter: ValidationRateLimiter) -> None:
    logger = rate_limiter._logger

    with patch("crackerjack.services.validation_rate_limiter.time.time", return_value=100.0):
        assert rate_limiter.record_failure("client-1", "command_injection") is False
        assert rate_limiter.record_failure("client-1", "command_injection") is False
        assert rate_limiter.record_failure("client-1", "command_injection") is True

        assert rate_limiter.is_blocked("client-1") is True
        assert rate_limiter.get_remaining_attempts("client-1", "command_injection") == 0
        assert rate_limiter._failure_windows["client-1"] == deque()

    logger.log_rate_limit_exceeded.assert_called_once()


def test_client_stats_and_block_expiration(rate_limiter: ValidationRateLimiter) -> None:
    rate_limiter._failure_windows["client-2"] = deque([99000.0, 99800.0, 99950.0])
    rate_limiter._blocked_until["client-2"] = 120000.0
    rate_limiter._blocked_until["client-3"] = 90000.0
    rate_limiter._failure_windows["client-3"] = deque([0.0, 1.0])

    with patch("crackerjack.services.validation_rate_limiter.time.time", return_value=100000.0):
        stats = rate_limiter.get_client_stats("client-2")
        block_time_remaining = rate_limiter.get_block_time_remaining("client-2")
        removed = rate_limiter.cleanup_expired_data()

    assert stats["client_id"] == "client-2"
    assert stats["is_blocked"] is True
    assert stats["total_failures"] == 3
    assert stats["recent_failures"] == 2
    assert block_time_remaining == 20000
    assert removed == 3
    assert "client-3" not in rate_limiter._blocked_until
    assert "client-3" not in rate_limiter._failure_windows


def test_update_rate_limits_and_all_stats(rate_limiter: ValidationRateLimiter) -> None:
    rate_limiter.update_rate_limits("custom", 7, 33, 44)
    rate_limiter._failure_windows["client-4"] = deque([900.0, 970.0])
    rate_limiter._blocked_until["client-5"] = 1100.0

    with patch("crackerjack.services.validation_rate_limiter.time.time", return_value=1000.0):
        stats = rate_limiter.get_all_stats()

    custom_limit = rate_limiter._limits["custom"]
    assert custom_limit.max_failures == 7
    assert custom_limit.window_seconds == 33
    assert custom_limit.block_duration == 44
    assert stats["total_clients_tracked"] == 1
    assert stats["currently_blocked"] == 1
    assert stats["rate_limits"]["custom"]["max_failures"] == 7
    assert stats["blocked_clients"][0]["client_id"] == "client-5"
    assert stats["active_clients"][0]["client_id"] == "client-4"


def test_get_validation_rate_limiter_singleton() -> None:
    validation_rate_limiter_module._rate_limiter = None

    first = get_validation_rate_limiter()
    second = get_validation_rate_limiter()

    assert first is second
