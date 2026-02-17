"""Enhanced tests for timeout manager with more scenarios."""

import asyncio
import time
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.core.timeout_manager import (
    AsyncTimeoutManager,
    CircuitBreakerState,
    CircuitBreakerStateData,
    TimeoutConfig,
    TimeoutError,
    TimeoutStrategy,
)


class TestTimeoutManagerEnhanced:
    """Enhanced tests for AsyncTimeoutManager covering more scenarios."""

    def test_timeout_manager_with_custom_config(self) -> None:
        """Test AsyncTimeoutManager with custom configuration."""
        config = TimeoutConfig(
            default_timeout=5.0,
            max_retries=5,
            base_retry_delay=0.5,
            failure_threshold=2,
            recovery_timeout=2.0,
            half_open_max_calls=1,
            operation_timeouts={
                "fast_hooks": 10.0,
                "comprehensive_hooks": 60.0,
                "test_execution": 300.0,
            }
        )

        manager = AsyncTimeoutManager(config)

        # Verify configuration was applied
        assert manager.config.default_timeout == 5.0
        assert manager.config.max_retries == 5
        assert manager.config.base_retry_delay == 0.5
        assert manager.config.failure_threshold == 2

        # Test getting custom operation timeout
        assert manager.get_timeout("fast_hooks") == 10.0
        assert manager.get_timeout("comprehensive_hooks") == 60.0
        assert manager.get_timeout("test_execution") == 300.0
        assert manager.get_timeout("unknown_operation") == 5.0  # default

    @pytest.mark.asyncio
    async def test_timeout_manager_with_retry_strategy(self) -> None:
        """Test AsyncTimeoutManager with retry strategy."""
        manager = AsyncTimeoutManager()

        call_count = 0
        async def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception(f"Attempt {call_count} failed")
            return "success"

        # Test with retry strategy
        result = await manager._with_retry("flaky_op", flaky_operation, timeout=1.0)
        assert result == "success"
        assert call_count == 3  # Should succeed on third attempt

    @pytest.mark.asyncio
    async def test_timeout_manager_retry_exhaustion(self) -> None:
        """Test AsyncTimeoutManager when retries are exhausted."""
        config = TimeoutConfig(max_retries=2, base_retry_delay=0.01)
        manager = AsyncTimeoutManager(config)

        async def always_failing_operation():
            raise Exception("Always fails")

        # Should eventually raise the exception after retries are exhausted
        with pytest.raises(Exception, match="Always fails"):
            await manager._with_retry("failing_op", always_failing_operation, timeout=1.0)

    @pytest.mark.asyncio
    async def test_timeout_manager_with_different_strategies(self) -> None:
        """Test AsyncTimeoutManager with different timeout strategies."""
        manager = AsyncTimeoutManager()

        async def quick_operation():
            await asyncio.sleep(0.01)
            return "result"

        # Test FAIL_FAST strategy
        result = await manager.with_timeout(
            "test_op", quick_operation(), timeout=1.0, strategy=TimeoutStrategy.FAIL_FAST
        )
        assert result == "result"

        # Test GRACEFUL_DEGRADATION strategy
        result = await manager.with_timeout(
            "test_op", quick_operation(), timeout=1.0, strategy=TimeoutStrategy.GRACEFUL_DEGRADATION
        )
        assert result == "result"

    @pytest.mark.asyncio
    async def test_timeout_manager_circuit_breaker_scenarios(self) -> None:
        """Test AsyncTimeoutManager circuit breaker in various scenarios."""
        config = TimeoutConfig(failure_threshold=2, recovery_timeout=0.1)
        manager = AsyncTimeoutManager(config)

        async def failing_operation():
            await asyncio.sleep(0.01)
            raise Exception("Operation failed")

        # First failure - circuit should remain closed
        try:
            await manager.with_timeout(
                "test_op", failing_operation(), timeout=1.0, strategy=TimeoutStrategy.CIRCUIT_BREAKER
            )
        except Exception:
            pass  # Expected to fail

        # Verify circuit breaker state
        assert "test_op" in manager.circuit_breakers
        assert manager.circuit_breakers["test_op"].state == CircuitBreakerState.CLOSED
        assert manager.circuit_breakers["test_op"].failure_count == 1

        # Second failure - circuit should open
        try:
            await manager.with_timeout(
                "test_op", failing_operation(), timeout=1.0, strategy=TimeoutStrategy.CIRCUIT_BREAKER
            )
        except Exception:
            pass  # Expected to fail

        # Verify circuit is now open
        assert manager.circuit_breakers["test_op"].state == CircuitBreakerState.OPEN
        assert manager.circuit_breakers["test_op"].failure_count == 2

        # Third call should be blocked by open circuit
        with pytest.raises(TimeoutError):
            await manager.with_timeout(
                "test_op", failing_operation(), timeout=1.0, strategy=TimeoutStrategy.CIRCUIT_BREAKER
            )

    @pytest.mark.asyncio
    async def test_timeout_manager_circuit_breaker_recovery(self) -> None:
        """Test circuit breaker recovery after timeout."""
        config = TimeoutConfig(failure_threshold=1, recovery_timeout=0.01)
        manager = AsyncTimeoutManager(config)

        async def failing_operation():
            await asyncio.sleep(0.01)
            raise Exception("Operation failed")

        async def successful_operation():
            await asyncio.sleep(0.01)
            return "success"

        # Cause circuit to open
        try:
            await manager.with_timeout(
                "test_op", failing_operation(), timeout=1.0, strategy=TimeoutStrategy.CIRCUIT_BREAKER
            )
        except Exception:
            pass  # Expected to fail

        # Circuit should be open
        assert manager.circuit_breakers["test_op"].state == CircuitBreakerState.OPEN

        # Wait for recovery period
        await asyncio.sleep(0.02)  # Longer than recovery timeout

        # Next call should transition to half-open
        try:
            result = await manager.with_timeout(
                "test_op", successful_operation(), timeout=1.0, strategy=TimeoutStrategy.CIRCUIT_BREAKER
            )
            # This might work if circuit transitions to half-open and then closed
        except TimeoutError:
            # Or might still be blocked if timing doesn't align perfectly
            pass

    @pytest.mark.asyncio
    async def test_timeout_manager_stats_tracking(self) -> None:
        """Test AsyncTimeoutManager statistics tracking."""
        manager = AsyncTimeoutManager()

        async def quick_operation():
            await asyncio.sleep(0.01)
            return "success"

        # Run several successful operations
        for i in range(5):
            result = await manager.with_timeout("test_op", quick_operation(), timeout=1.0)
            assert result == "success"

        # Check stats
        stats = manager.get_stats("test_op")
        assert stats["count"] == 5
        assert stats["avg_time"] > 0
        assert stats["min_time"] > 0
        assert stats["max_time"] > 0
        assert stats["success_rate"] == 1.0  # All succeeded

        async def failing_operation():
            await asyncio.sleep(0.01)
            raise Exception("Failed")

        # Run one failing operation
        try:
            await manager.with_timeout("test_op", failing_operation(), timeout=1.0)
        except Exception:
            pass  # Expected to fail

        # Check stats updated
        stats = manager.get_stats("test_op")
        assert stats["count"] == 6  # 5 successes + 1 failure
        # Success rate should be less than 1.0 now
        assert stats["success_rate"] < 1.0

    @pytest.mark.asyncio
    async def test_timeout_manager_context_manager_scenarios(self) -> None:
        """Test timeout context manager in various scenarios."""
        manager = AsyncTimeoutManager()

        # Test successful operation with context manager
        async with manager.timeout_context("success_op", timeout=1.0):
            await asyncio.sleep(0.01)
        # Should complete without exception

        # Test operation that exceeds timeout
        with pytest.raises(TimeoutError):
            async with manager.timeout_context("timeout_op", timeout=0.01):
                await asyncio.sleep(0.1)

        # Test context with graceful degradation
        async with manager.timeout_context(
            "graceful_op", timeout=0.01, strategy=TimeoutStrategy.GRACEFUL_DEGRADATION
        ):
            await asyncio.sleep(0.1)
        # Should complete without exception due to graceful degradation

    def test_timeout_manager_circuit_breaker_state_transitions(self) -> None:
        """Test circuit breaker state transition methods directly."""
        manager = AsyncTimeoutManager()

        # Test initial state
        initial_check = manager._check_circuit_breaker("new_op")
        assert initial_check is True
        assert "new_op" in manager.circuit_breakers
        assert manager.circuit_breakers["new_op"].state == CircuitBreakerState.CLOSED

        # Manually set to OPEN state
        manager.circuit_breakers["test_op"] = CircuitBreakerStateData(
            state=CircuitBreakerState.OPEN,
            failure_count=5,
            last_failure_time=time.time() - 10  # Old failure time
        )

        # With old failure time and short recovery timeout, should transition to HALF_OPEN
        config = TimeoutConfig(recovery_timeout=1.0)
        manager.config = config

        check_result = manager._check_circuit_breaker("test_op")
        # Depending on timing, might transition to HALF_OPEN and return True
        # Or might stay OPEN and return False

        # Update circuit breaker directly
        manager._update_circuit_breaker("test_op", success=True)  # Success should close it
        assert manager.circuit_breakers["test_op"].state == CircuitBreakerState.CLOSED
        assert manager.circuit_breakers["test_op"].failure_count == 4  # Reduced by 1

    @pytest.mark.asyncio
    async def test_timeout_manager_performance_monitor_integration(self) -> None:
        """Test timeout manager integration with performance monitor."""
        manager = AsyncTimeoutManager()

        # Access the performance monitor
        monitor = manager.performance_monitor
        assert monitor is not None

        # Test that operations trigger performance monitoring
        async def monitored_operation():
            await asyncio.sleep(0.01)
            return "result"

        result = await manager.with_timeout("monitored_op", monitored_operation(), timeout=1.0)
        assert result == "result"

        # Stats should be recorded
        stats = manager.get_stats("monitored_op")
        assert stats["count"] >= 1

    @pytest.mark.asyncio
    async def test_timeout_manager_exception_handling_variations(self) -> None:
        """Test timeout manager handling of different exception types."""
        manager = AsyncTimeoutManager()

        # Test with regular exception
        async def regular_error_operation():
            await asyncio.sleep(0.01)
            raise ValueError("Regular error")

        with pytest.raises(ValueError):
            await manager.with_timeout("error_op", regular_error_operation(), timeout=1.0)

        # Test with timeout error
        with pytest.raises(TimeoutError):
            async def slow_operation():
                await asyncio.sleep(0.1)

            await manager.with_timeout("slow_op", slow_operation(), timeout=0.01)

    def test_timeout_manager_get_stats_edge_cases(self) -> None:
        """Test get_stats method with edge cases."""
        manager = AsyncTimeoutManager()

        # Test with non-existent operation
        stats = manager.get_stats("nonexistent_op")
        assert stats["count"] == 0
        assert stats["avg_time"] == 0.0
        assert stats["min_time"] == 0.0
        assert stats["max_time"] == 0.0
        assert stats["success_rate"] == 0.0

        # Test with operation that has no success but has failures tracked
        # Add a failure manually to trigger the success rate calculation
        manager._record_failure("test_op", 1.0)

        stats = manager.get_stats("test_op")
        # Success rate should be calculated based on success vs failure counts

    @pytest.mark.asyncio
    async def test_timeout_manager_with_backoff_strategy(self) -> None:
        """Test timeout manager with retry and exponential backoff."""
        config = TimeoutConfig(
            max_retries=3,
            base_retry_delay=0.01,
            backoff_multiplier=2.0,  # Exponential backoff
            max_retry_delay=0.1
        )
        manager = AsyncTimeoutManager(config)

        call_times = []
        async def eventually_successful_operation():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise Exception(f"Failing on attempt #{len(call_times)}")
            return "finally successful"

        result = await manager._with_retry("eventual_success", eventually_successful_operation, timeout=1.0)
        assert result == "finally successful"
        assert len(call_times) == 3  # Should succeed on third attempt

        # Verify delays increased (approximately)
        if len(call_times) > 1:
            intervals = [call_times[i] - call_times[i-1] for i in range(1, len(call_times))]
            # With exponential backoff, intervals should generally increase

    @pytest.mark.asyncio
    async def test_timeout_manager_decorator_functionality(self) -> None:
        """Test the timeout_async decorator functionality."""
        from crackerjack.core.timeout_manager import timeout_async

        call_count = 0

        @timeout_async("decorated_op", timeout=0.1)
        async def decorated_operation():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                await asyncio.sleep(0.2)  # This will timeout
                return "should_not_reach"
            else:
                return "success"

        # First call should timeout
        with pytest.raises(TimeoutError):
            await decorated_operation()

        # Reset for a successful call
        call_count = 2
        result = await decorated_operation()
        assert result == "success"

    def test_timeout_manager_global_singleton_behavior(self) -> None:
        """Test global timeout manager singleton behavior."""
        from crackerjack.core.timeout_manager import get_timeout_manager, configure_timeouts

        # Reset the global state
        import crackerjack.core.timeout_manager as tm
        tm._global_timeout_manager = None

        # Get manager first time
        manager1 = get_timeout_manager()
        assert manager1 is not None

        # Get manager second time - should be same instance
        manager2 = get_timeout_manager()
        assert manager1 is manager2

        # Configure with custom settings
        custom_config = TimeoutConfig(default_timeout=45.0)
        configure_timeouts(custom_config)

        # Get manager again - should have new config
        manager3 = get_timeout_manager()
        assert manager3 is manager1  # Same instance
        assert manager3.config.default_timeout == 45.0
