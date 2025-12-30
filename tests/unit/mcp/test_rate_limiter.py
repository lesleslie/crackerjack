"""Unit tests for MCP rate_limiter.

Tests rate limiting, resource monitoring, job slot management,
and comprehensive middleware functionality.
"""

import asyncio
import time
from pathlib import Path
from unittest.mock import patch

import pytest

from crackerjack.mcp.rate_limiter import (
    RateLimitConfig,
    RateLimitMiddleware,
    RateLimiter,
    ResourceMonitor,
)


@pytest.mark.unit
class TestRateLimitConfig:
    """Test RateLimitConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RateLimitConfig()

        assert config.requests_per_minute == 30
        assert config.requests_per_hour == 300
        assert config.max_concurrent_jobs == 5
        assert config.max_job_duration_minutes == 30
        assert config.max_file_size_mb == 100
        assert config.max_progress_files == 1000
        assert config.max_cache_entries == 10000
        assert config.max_state_history == 100

    def test_custom_config(self):
        """Test custom configuration values."""
        config = RateLimitConfig(
            requests_per_minute=60,
            requests_per_hour=600,
            max_concurrent_jobs=10,
            max_job_duration_minutes=60,
        )

        assert config.requests_per_minute == 60
        assert config.requests_per_hour == 600
        assert config.max_concurrent_jobs == 10
        assert config.max_job_duration_minutes == 60


@pytest.mark.unit
class TestRateLimiterInitialization:
    """Test RateLimiter initialization."""

    def test_initialization_default(self):
        """Test default initialization."""
        limiter = RateLimiter()

        assert limiter.requests_per_minute == 30
        assert limiter.requests_per_hour == 300
        assert len(limiter.minute_windows) == 0
        assert len(limiter.hour_windows) == 0

    def test_initialization_custom_limits(self):
        """Test initialization with custom limits."""
        limiter = RateLimiter(requests_per_minute=60, requests_per_hour=600)

        assert limiter.requests_per_minute == 60
        assert limiter.requests_per_hour == 600


@pytest.mark.unit
class TestRateLimiterIsAllowed:
    """Test RateLimiter is_allowed method."""

    @pytest.mark.asyncio
    async def test_is_allowed_first_request(self):
        """Test first request is allowed."""
        limiter = RateLimiter(requests_per_minute=30, requests_per_hour=300)

        allowed, info = await limiter.is_allowed("client1")

        assert allowed is True
        assert info["allowed"] is True
        assert info["minute_requests_remaining"] == 29
        assert info["hour_requests_remaining"] == 299

    @pytest.mark.asyncio
    async def test_is_allowed_within_limits(self):
        """Test requests within limits are allowed."""
        limiter = RateLimiter(requests_per_minute=5, requests_per_hour=10)

        # Make 4 requests
        for _ in range(4):
            allowed, _ = await limiter.is_allowed("client1")
            assert allowed is True

        # 5th request should still be allowed
        allowed, info = await limiter.is_allowed("client1")
        assert allowed is True
        assert info["minute_requests_remaining"] == 0

    @pytest.mark.asyncio
    async def test_is_allowed_minute_limit_exceeded(self):
        """Test request denied when minute limit exceeded."""
        limiter = RateLimiter(requests_per_minute=3, requests_per_hour=100)

        # Fill up minute limit
        for _ in range(3):
            allowed, _ = await limiter.is_allowed("client1")
            assert allowed is True

        # Next request should be denied
        allowed, info = await limiter.is_allowed("client1")

        assert allowed is False
        assert info["reason"] == "minute_limit_exceeded"
        assert info["limit"] == 3
        assert info["window"] == "1 minute"
        assert info["retry_after"] == 60

    @pytest.mark.asyncio
    async def test_is_allowed_hour_limit_exceeded(self):
        """Test request denied when hour limit exceeded."""
        limiter = RateLimiter(requests_per_minute=100, requests_per_hour=3)

        # Fill up hour limit
        for _ in range(3):
            allowed, _ = await limiter.is_allowed("client1")
            assert allowed is True

        # Next request should be denied
        allowed, info = await limiter.is_allowed("client1")

        assert allowed is False
        assert info["reason"] == "hour_limit_exceeded"
        assert info["limit"] == 3
        assert info["window"] == "1 hour"
        assert info["retry_after"] == 3600

    @pytest.mark.asyncio
    async def test_is_allowed_different_clients(self):
        """Test different clients have separate limits."""
        limiter = RateLimiter(requests_per_minute=2, requests_per_hour=10)

        # Client 1 makes 2 requests
        for _ in range(2):
            allowed, _ = await limiter.is_allowed("client1")
            assert allowed is True

        # Client 2 should still be able to make requests
        allowed, _ = await limiter.is_allowed("client2")
        assert allowed is True


@pytest.mark.unit
class TestRateLimiterCleanup:
    """Test RateLimiter cleanup functionality."""

    @pytest.mark.asyncio
    async def test_cleanup_windows_removes_expired_entries(self):
        """Test cleanup removes expired entries."""
        limiter = RateLimiter(requests_per_minute=5, requests_per_hour=10)

        # Make requests
        await limiter.is_allowed("client1")

        # Manually set old timestamp
        limiter.minute_windows["client1"][0] = time.time() - 70  # Older than 60s

        # Cleanup
        limiter._cleanup_windows(time.time())

        # Old entry should be removed
        assert len(limiter.minute_windows.get("client1", [])) == 0

    @pytest.mark.asyncio
    async def test_cleanup_windows_removes_empty_client_windows(self):
        """Test cleanup removes empty client windows."""
        limiter = RateLimiter(requests_per_minute=5, requests_per_hour=10)

        # Make request
        await limiter.is_allowed("client1")

        # Set old timestamps
        limiter.minute_windows["client1"][0] = time.time() - 70
        limiter.hour_windows["client1"][0] = time.time() - 3700

        # Cleanup
        limiter._cleanup_windows(time.time())

        # Client windows should be removed
        assert "client1" not in limiter.minute_windows
        assert "client1" not in limiter.hour_windows


@pytest.mark.unit
class TestRateLimiterStats:
    """Test RateLimiter statistics."""

    @pytest.mark.asyncio
    async def test_get_stats_empty(self):
        """Test stats with no requests."""
        limiter = RateLimiter(requests_per_minute=30, requests_per_hour=300)

        stats = limiter.get_stats()

        assert stats["active_clients"] == 0
        assert stats["global_minute_requests"] == 0
        assert stats["global_hour_requests"] == 0
        assert stats["limits"]["requests_per_minute"] == 30
        assert stats["limits"]["requests_per_hour"] == 300

    @pytest.mark.asyncio
    async def test_get_stats_with_requests(self):
        """Test stats with active requests."""
        limiter = RateLimiter(requests_per_minute=30, requests_per_hour=300)

        await limiter.is_allowed("client1")
        await limiter.is_allowed("client2")
        await limiter.is_allowed("client1")

        stats = limiter.get_stats()

        assert stats["active_clients"] == 2
        assert stats["global_minute_requests"] == 3
        assert stats["global_hour_requests"] == 3


@pytest.mark.unit
class TestResourceMonitorInitialization:
    """Test ResourceMonitor initialization."""

    def test_initialization(self):
        """Test ResourceMonitor initialization."""
        config = RateLimitConfig()

        monitor = ResourceMonitor(config)

        assert monitor.config == config
        assert monitor.active_jobs == {}
        assert monitor.job_locks._value == config.max_concurrent_jobs


@pytest.mark.unit
class TestResourceMonitorJobSlots:
    """Test ResourceMonitor job slot management."""

    @pytest.mark.asyncio
    async def test_acquire_job_slot_success(self):
        """Test acquiring job slot successfully."""
        config = RateLimitConfig(max_concurrent_jobs=5)
        monitor = ResourceMonitor(config)

        acquired = await monitor.acquire_job_slot("job1")

        assert acquired is True
        assert "job1" in monitor.active_jobs
        assert len(monitor.active_jobs) == 1

    @pytest.mark.asyncio
    async def test_acquire_job_slot_multiple(self):
        """Test acquiring multiple job slots."""
        config = RateLimitConfig(max_concurrent_jobs=3)
        monitor = ResourceMonitor(config)

        for i in range(3):
            acquired = await monitor.acquire_job_slot(f"job{i}")
            assert acquired is True

        assert len(monitor.active_jobs) == 3

    @pytest.mark.asyncio
    async def test_acquire_job_slot_at_limit(self):
        """Test acquiring job slot when at limit."""
        config = RateLimitConfig(max_concurrent_jobs=2)
        monitor = ResourceMonitor(config)

        # Fill up slots
        await monitor.acquire_job_slot("job1")
        await monitor.acquire_job_slot("job2")

        # Next acquisition should timeout
        acquired = await monitor.acquire_job_slot("job3")

        assert acquired is False

    @pytest.mark.asyncio
    async def test_release_job_slot(self):
        """Test releasing job slot."""
        config = RateLimitConfig(max_concurrent_jobs=5)
        monitor = ResourceMonitor(config)

        await monitor.acquire_job_slot("job1")
        await monitor.release_job_slot("job1")

        assert "job1" not in monitor.active_jobs

    @pytest.mark.asyncio
    async def test_release_job_slot_nonexistent(self):
        """Test releasing non-existent job slot."""
        config = RateLimitConfig(max_concurrent_jobs=5)
        monitor = ResourceMonitor(config)

        # Should not raise error
        await monitor.release_job_slot("nonexistent")


@pytest.mark.unit
class TestResourceMonitorStaleJobs:
    """Test ResourceMonitor stale job cleanup."""

    @pytest.mark.asyncio
    async def test_cleanup_stale_jobs_none(self):
        """Test cleanup with no stale jobs."""
        config = RateLimitConfig(max_job_duration_minutes=30)
        monitor = ResourceMonitor(config)

        await monitor.acquire_job_slot("job1")

        cleaned = await monitor.cleanup_stale_jobs()

        assert cleaned == 0
        assert "job1" in monitor.active_jobs

    @pytest.mark.asyncio
    async def test_cleanup_stale_jobs_found(self):
        """Test cleanup with stale jobs."""
        config = RateLimitConfig(max_job_duration_minutes=1)
        monitor = ResourceMonitor(config)

        # Acquire job and make it stale
        await monitor.acquire_job_slot("job1")
        monitor.active_jobs["job1"] = time.time() - 70  # 70 seconds ago

        cleaned = await monitor.cleanup_stale_jobs()

        assert cleaned == 1
        assert "job1" not in monitor.active_jobs


@pytest.mark.unit
class TestResourceMonitorFileValidation:
    """Test ResourceMonitor file validation."""

    def test_check_file_size_nonexistent(self, tmp_path):
        """Test file size check for non-existent file."""
        config = RateLimitConfig(max_file_size_mb=10)
        monitor = ResourceMonitor(config)

        file_path = tmp_path / "nonexistent.txt"

        result = monitor.check_file_size(file_path)

        assert result is True

    def test_check_file_size_under_limit(self, tmp_path):
        """Test file size check for file under limit."""
        config = RateLimitConfig(max_file_size_mb=10)
        monitor = ResourceMonitor(config)

        file_path = tmp_path / "test.txt"
        file_path.write_text("small content")

        result = monitor.check_file_size(file_path)

        assert result is True

    def test_check_file_size_over_limit(self, tmp_path):
        """Test file size check for file over limit."""
        config = RateLimitConfig(max_file_size_mb=0.001)  # Very small limit
        monitor = ResourceMonitor(config)

        file_path = tmp_path / "test.txt"
        file_path.write_text("x" * 10000)  # Large content

        result = monitor.check_file_size(file_path)

        assert result is False

    def test_check_progress_files_limit_nonexistent_dir(self, tmp_path):
        """Test progress files limit with non-existent directory."""
        config = RateLimitConfig(max_progress_files=10)
        monitor = ResourceMonitor(config)

        progress_dir = tmp_path / "nonexistent"

        result = monitor.check_progress_files_limit(progress_dir)

        assert result is True

    def test_check_progress_files_limit_under_limit(self, tmp_path):
        """Test progress files limit under limit."""
        config = RateLimitConfig(max_progress_files=10)
        monitor = ResourceMonitor(config)

        progress_dir = tmp_path
        for i in range(5):
            (progress_dir / f"job-{i}.json").write_text("{}")

        result = monitor.check_progress_files_limit(progress_dir)

        assert result is True


@pytest.mark.unit
class TestResourceMonitorStats:
    """Test ResourceMonitor statistics."""

    @pytest.mark.asyncio
    async def test_get_stats_empty(self):
        """Test stats with no active jobs."""
        config = RateLimitConfig(max_concurrent_jobs=5)
        monitor = ResourceMonitor(config)

        stats = monitor.get_stats()

        assert stats["active_jobs"] == 0
        assert stats["max_concurrent_jobs"] == 5
        assert stats["available_slots"] == 5
        assert stats["job_details"] == {}

    @pytest.mark.asyncio
    async def test_get_stats_with_jobs(self):
        """Test stats with active jobs."""
        config = RateLimitConfig(max_concurrent_jobs=5)
        monitor = ResourceMonitor(config)

        await monitor.acquire_job_slot("job1")
        await monitor.acquire_job_slot("job2")

        stats = monitor.get_stats()

        assert stats["active_jobs"] == 2
        assert stats["available_slots"] == 3
        assert "job1" in stats["job_details"]
        assert "job2" in stats["job_details"]


@pytest.mark.unit
class TestRateLimitMiddlewareInitialization:
    """Test RateLimitMiddleware initialization."""

    def test_initialization_default(self):
        """Test default initialization."""
        middleware = RateLimitMiddleware()

        assert isinstance(middleware.config, RateLimitConfig)
        assert isinstance(middleware.rate_limiter, RateLimiter)
        assert isinstance(middleware.resource_monitor, ResourceMonitor)
        assert middleware._running is False

    def test_initialization_custom_config(self):
        """Test initialization with custom config."""
        config = RateLimitConfig(requests_per_minute=60)

        middleware = RateLimitMiddleware(config)

        assert middleware.config == config
        assert middleware.rate_limiter.requests_per_minute == 60


@pytest.mark.unit
class TestRateLimitMiddlewareLifecycle:
    """Test RateLimitMiddleware start/stop."""

    @pytest.mark.asyncio
    async def test_start_middleware(self):
        """Test starting middleware."""
        middleware = RateLimitMiddleware()

        await middleware.start()

        assert middleware._running is True
        assert middleware._cleanup_task is not None

        await middleware.stop()

    @pytest.mark.asyncio
    async def test_stop_middleware(self):
        """Test stopping middleware."""
        middleware = RateLimitMiddleware()

        await middleware.start()
        await middleware.stop()

        assert middleware._running is False
        assert middleware._cleanup_task.cancelled()


@pytest.mark.unit
class TestRateLimitMiddlewareOperations:
    """Test RateLimitMiddleware operations."""

    @pytest.mark.asyncio
    async def test_check_request_allowed(self):
        """Test checking if request is allowed."""
        middleware = RateLimitMiddleware()

        allowed, info = await middleware.check_request_allowed("client1")

        assert allowed is True

    @pytest.mark.asyncio
    async def test_acquire_job_resources(self):
        """Test acquiring job resources."""
        middleware = RateLimitMiddleware()

        acquired = await middleware.acquire_job_resources("job1")

        assert acquired is True

    @pytest.mark.asyncio
    async def test_release_job_resources(self):
        """Test releasing job resources."""
        middleware = RateLimitMiddleware()

        await middleware.acquire_job_resources("job1")
        await middleware.release_job_resources("job1")

        # Should not raise error

    def test_validate_file_size(self, tmp_path):
        """Test validating file size."""
        middleware = RateLimitMiddleware()

        file_path = tmp_path / "test.txt"
        file_path.write_text("small")

        result = middleware.validate_file_size(file_path)

        assert result is True

    def test_validate_progress_files(self, tmp_path):
        """Test validating progress files."""
        middleware = RateLimitMiddleware()

        result = middleware.validate_progress_files(tmp_path)

        assert result is True


@pytest.mark.unit
class TestRateLimitMiddlewareStats:
    """Test RateLimitMiddleware comprehensive stats."""

    @pytest.mark.asyncio
    async def test_get_comprehensive_stats(self):
        """Test getting comprehensive stats."""
        middleware = RateLimitMiddleware()

        await middleware.check_request_allowed("client1")
        await middleware.acquire_job_resources("job1")

        stats = middleware.get_comprehensive_stats()

        assert "rate_limiting" in stats
        assert "resource_usage" in stats
        assert "config" in stats
        assert stats["rate_limiting"]["active_clients"] == 1
        assert stats["resource_usage"]["active_jobs"] == 1


@pytest.mark.unit
class TestRateLimitMiddlewareCleanupLoop:
    """Test RateLimitMiddleware cleanup loop."""

    @pytest.mark.asyncio
    async def test_cleanup_loop_runs(self):
        """Test cleanup loop executes."""
        middleware = RateLimitMiddleware()

        # Patch sleep to avoid long wait
        with patch("asyncio.sleep", new_callable=lambda: asyncio.sleep):
            await middleware.start()

            # Give loop time to start
            await asyncio.sleep(0.01)

            await middleware.stop()

    @pytest.mark.asyncio
    async def test_cleanup_loop_handles_exceptions(self):
        """Test cleanup loop handles exceptions gracefully."""
        middleware = RateLimitMiddleware()

        # Make cleanup_stale_jobs raise exception
        original_cleanup = middleware.resource_monitor.cleanup_stale_jobs

        async def failing_cleanup():
            raise RuntimeError("Test error")

        middleware.resource_monitor.cleanup_stale_jobs = failing_cleanup

        original_sleep = asyncio.sleep
        with patch(
            "asyncio.sleep",
            side_effect=[RuntimeError("Test error"), asyncio.CancelledError()],
        ):
            await middleware.start()
            await original_sleep(0.01)
            await middleware.stop()

        # Restore original
        middleware.resource_monitor.cleanup_stale_jobs = original_cleanup
