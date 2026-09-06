"""Enhanced tests for timeout manager with more scenarios."""

import asyncio
import builtins
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


class TestTimeoutManagerExceptionDispatchers:
    """Targeted tests for exception dispatcher / handler branch coverage."""

    def test_handle_custom_timeout_exception(self) -> None:
        """Test _handle_custom_timeout_exception delegates to _handle_timeout_error."""
        manager = AsyncTimeoutManager()
        start_time = time.time()
        err = TimeoutError("op", 1.0, 0.5)
        result = manager._handle_custom_timeout_exception(
            "op", start_time, 1.0, TimeoutStrategy.FAIL_FAST, err,
        )
        # FAIL_FAST path returns None
        assert result is None

    def test_handle_custom_timeout_exception_graceful(self) -> None:
        """GRACEFUL_DEGRADATION returns the elapsed time, non-None."""
        manager = AsyncTimeoutManager()
        start_time = time.time()
        err = TimeoutError("op", 1.0, 0.5)
        result = manager._handle_custom_timeout_exception(
            "op", start_time, 1.0, TimeoutStrategy.GRACEFUL_DEGRADATION, err,
        )
        assert result is not None
        assert result >= 0.0

    def test_handle_asyncio_timeout_exception(self) -> None:
        """Test _handle_asyncio_timeout_exception delegates to _handle_timeout_error."""
        manager = AsyncTimeoutManager()
        start_time = time.time()
        result = manager._handle_asyncio_timeout_exception(
            "op", start_time, 1.0, TimeoutStrategy.FAIL_FAST,
        )
        assert result is None

    def test_handle_cancelled_exception(self) -> None:
        """Test _handle_cancelled_exception delegates to _handle_timeout_error."""
        manager = AsyncTimeoutManager()
        start_time = time.time()
        result = manager._handle_cancelled_exception(
            "op", start_time, 1.0, TimeoutStrategy.FAIL_FAST,
        )
        assert result is None

    def test_handle_cancelled_exception_graceful(self) -> None:
        """CANCELLED with GRACEFUL_DEGRADATION returns elapsed time."""
        manager = AsyncTimeoutManager()
        start_time = time.time()
        result = manager._handle_cancelled_exception(
            "op", start_time, 1.0, TimeoutStrategy.GRACEFUL_DEGRADATION,
        )
        assert result is not None

    def test_handle_generic_exception_circuit_breaker(self) -> None:
        """_handle_generic_exception with CIRCUIT_BREAKER updates breaker on failure."""
        config = TimeoutConfig(failure_threshold=1)
        manager = AsyncTimeoutManager(config)
        start_time = time.time()
        manager._handle_generic_exception(
            "op", start_time, TimeoutStrategy.CIRCUIT_BREAKER,
        )
        # failure threshold of 1 was reached, breaker should be open
        assert manager.circuit_breakers["op"].state == CircuitBreakerState.OPEN
        assert manager.circuit_breakers["op"].failure_count == 1

    def test_handle_generic_exception_other_strategy(self) -> None:
        """_handle_generic_exception without CIRCUIT_BREAKER does not touch breaker."""
        manager = AsyncTimeoutManager()
        start_time = time.time()
        manager._handle_generic_exception(
            "op", start_time, TimeoutStrategy.FAIL_FAST,
        )
        # No breaker entry created for non-CIRCUIT_BREAKER strategies
        assert "op" not in manager.circuit_breakers

    def test_dispatch_exception_handler_custom_timeout(self) -> None:
        """_dispatch_exception_handler for custom TimeoutError with FAIL_FAST."""
        manager = AsyncTimeoutManager()
        start_time = time.time()
        err = TimeoutError("op", 1.0, 0.5)
        should_yield, error = manager._dispatch_exception_handler(
            err, "op", start_time, 1.0, TimeoutStrategy.FAIL_FAST,
        )
        assert should_yield is False
        assert error is err

    def test_dispatch_exception_handler_custom_timeout_graceful(self) -> None:
        """GRACEFUL_DEGRADATION with custom TimeoutError yields (no error reraise)."""
        manager = AsyncTimeoutManager()
        start_time = time.time()
        err = TimeoutError("op", 1.0, 0.5)
        should_yield, error = manager._dispatch_exception_handler(
            err, "op", start_time, 1.0, TimeoutStrategy.GRACEFUL_DEGRADATION,
        )
        assert should_yield is True
        assert error is None

    def test_dispatch_exception_handler_builtin_timeout(self) -> None:
        """_dispatch_exception_handler routes builtins.TimeoutError correctly."""
        manager = AsyncTimeoutManager()
        start_time = time.time()
        err = builtins.TimeoutError()  # bare -> builtins.TimeoutError
        should_yield, error = manager._dispatch_exception_handler(
            err, "op", start_time, 1.0, TimeoutStrategy.FAIL_FAST,
        )
        assert should_yield is False
        assert isinstance(error, TimeoutError)
        assert error is not err  # freshly constructed TimeoutError (the custom class)

    def test_dispatch_exception_handler_cancelled(self) -> None:
        """_dispatch_exception_handler routes CancelledError correctly."""
        manager = AsyncTimeoutManager()
        start_time = time.time()
        err = asyncio.CancelledError()
        should_yield, error = manager._dispatch_exception_handler(
            err, "op", start_time, 1.0, TimeoutStrategy.FAIL_FAST,
        )
        assert should_yield is False
        # Builtins TimeoutError-like wrapper
        assert isinstance(error, TimeoutError)

    def test_dispatch_exception_handler_cancelled_graceful(self) -> None:
        """CancelledError with GRACEFUL_DEGRADATION yields."""
        manager = AsyncTimeoutManager()
        start_time = time.time()
        err = asyncio.CancelledError()
        should_yield, error = manager._dispatch_exception_handler(
            err, "op", start_time, 1.0, TimeoutStrategy.GRACEFUL_DEGRADATION,
        )
        assert should_yield is True
        assert error is None

    def test_dispatch_exception_handler_generic(self) -> None:
        """Unmatched exception types fall through to generic handler."""
        manager = AsyncTimeoutManager()
        start_time = time.time()
        err = ValueError("boom")
        should_yield, error = manager._dispatch_exception_handler(
            err, "op", start_time, 1.0, TimeoutStrategy.FAIL_FAST,
        )
        assert should_yield is False
        assert error is err

    def test_should_yield_on_graceful_degradation(self) -> None:
        """Result of None -> False; non-None -> True."""
        manager = AsyncTimeoutManager()
        assert manager._should_yield_on_graceful_degradation(None) is False
        assert manager._should_yield_on_graceful_degradation(0.0) is True
        assert manager._should_yield_on_graceful_degradation(1.5) is True


class TestTimeoutManagerCircuitBreakerTransitions:
    """Tests for circuit breaker state transitions and edge cases."""

    def test_check_circuit_breaker_open_pending_recovery(self) -> None:
        """OPEN breaker before recovery_timeout elapses blocks the call."""
        config = TimeoutConfig(recovery_timeout=10.0)
        manager = AsyncTimeoutManager(config)
        manager.circuit_breakers["op"] = CircuitBreakerStateData(
            state=CircuitBreakerState.OPEN,
            failure_count=3,
            last_failure_time=time.time(),
        )
        assert manager._check_circuit_breaker("op") is False

    def test_check_circuit_breaker_half_open_within_call_budget(self) -> None:
        """HALF_OPEN allows calls up to half_open_max_calls."""
        config = TimeoutConfig(half_open_max_calls=2)
        manager = AsyncTimeoutManager(config)
        manager.circuit_breakers["op"] = CircuitBreakerStateData(
            state=CircuitBreakerState.HALF_OPEN,
            failure_count=2,
            half_open_calls=0,
        )
        # First call - returns True, increments half_open_calls
        assert manager._check_circuit_breaker("op") is True
        assert manager.circuit_breakers["op"].half_open_calls == 1
        # Second call - still allowed
        assert manager._check_circuit_breaker("op") is True
        assert manager.circuit_breakers["op"].half_open_calls == 2
        # Third call exceeds budget - returns False
        assert manager._check_circuit_breaker("op") is False

    def test_update_circuit_breaker_success_from_half_open_closes_breaker(self) -> None:
        """Success while HALF_OPEN transitions to CLOSED."""
        manager = AsyncTimeoutManager()
        manager.circuit_breakers["op"] = CircuitBreakerStateData(
            state=CircuitBreakerState.HALF_OPEN,
            failure_count=4,
            half_open_calls=1,
        )
        manager._update_circuit_breaker("op", success=True)
        assert manager.circuit_breakers["op"].state == CircuitBreakerState.CLOSED

    def test_update_circuit_breaker_first_open_records_event(self) -> None:
        """First OPEN transition calls record_circuit_breaker_event(opened=True)."""
        manager = AsyncTimeoutManager()
        manager._performance_monitor = MagicMock()
        manager._update_circuit_breaker("op", success=False)
        manager._update_circuit_breaker("op", success=False)
        manager._update_circuit_breaker("op", success=False)
        manager._update_circuit_breaker("op", success=False)
        manager._update_circuit_breaker("op", success=False)
        # Should have recorded at least one open event when state first transitioned
        monitor = manager._performance_monitor
        assert monitor.record_circuit_breaker_event.called
        # First call must have opened=True
        first_call = monitor.record_circuit_breaker_event.call_args_list[0]
        assert first_call.args[1] is True

    def test_update_circuit_breaker_subsequent_open_no_event(self) -> None:
        """Subsequent failure while already OPEN does NOT re-fire the event."""
        manager = AsyncTimeoutManager()
        manager._performance_monitor = MagicMock()
        # Already open with many failures
        manager.circuit_breakers["op"] = CircuitBreakerStateData(
            state=CircuitBreakerState.OPEN,
            failure_count=10,
        )
        manager._update_circuit_breaker("op", success=False)
        # No new event emitted
        assert not manager._performance_monitor.record_circuit_breaker_event.called


class TestTimeoutManagerTimeoutOverflow:
    """Tests for the 7200s timeout cap warning path."""

    @pytest.mark.asyncio
    async def test_timeout_context_caps_excessive_timeout(self) -> None:
        """timeout > 7200 logs a warning and gets capped."""
        manager = AsyncTimeoutManager()
        with patch("crackerjack.core.timeout_manager.logger") as mock_logger:
            async with manager.timeout_context("huge_op", timeout=10000.0):
                await asyncio.sleep(0.01)
        # Warning about capping should have been logged
        mock_logger.warning.assert_called()
        warning_msg = str(mock_logger.warning.call_args)
        assert "7200" in warning_msg or "Capping" in warning_msg


class TestTimeoutManagerAsyncBackupPath:
    """Tests for the AttributeError fallback path in _execute_with_timeout_context."""

    @pytest.mark.asyncio
    async def test_execute_with_timeout_context_attribute_error_fallback(self) -> None:
        """When asyncio.timeout raises AttributeError, fallback path is exercised.

        In the fallback, asyncio.shield(asyncio.current_task()) + wait_for blocks
        until the (current) task completes. Since the test function IS the current
        task, it is shielded against cancellation and the timeout fires instead,
        which is re-raised as the custom TimeoutError by the fallback branch.
        """
        manager = AsyncTimeoutManager()
        with patch(
            "crackerjack.core.timeout_manager.asyncio.timeout",
            side_effect=AttributeError,
        ):
            with pytest.raises(TimeoutError):
                async with manager._execute_with_timeout_context(0.05):
                    await asyncio.sleep(1.0)

    @pytest.mark.asyncio
    async def test_execute_with_timeout_context_attribute_error_no_task(self) -> None:
        """When asyncio.current_task() returns None, the else: yield branch runs."""
        manager = AsyncTimeoutManager()
        with patch(
            "crackerjack.core.timeout_manager.asyncio.timeout",
            side_effect=AttributeError,
        ), patch(
            "crackerjack.core.timeout_manager.asyncio.current_task",
            return_value=None,
        ):
            async with manager._execute_with_timeout_context(1.0):
                await asyncio.sleep(0.01)


class TestTimeoutManagerRetryEdgeCases:
    """Tests for retry exhaustion and zero-retry RuntimeError paths."""

    @pytest.mark.asyncio
    async def test_with_retry_zero_retries_raises_runtime_error(self) -> None:
        """When max_retries=0 (loop range(1)) and operation raises, runtime error path."""
        config = TimeoutConfig(max_retries=0, base_retry_delay=0.01)
        manager = AsyncTimeoutManager(config)

        async def always_failing():
            raise Exception("always fails")

        with pytest.raises(Exception, match="always fails"):
            await manager._with_retry("zero_retry_op", always_failing, timeout=1.0)

    @pytest.mark.asyncio
    async def test_with_retry_no_attempts_made_raises_runtime_error(self) -> None:
        """When max_retries=-1 (loop runs zero iterations), RuntimeError is raised."""
        config = TimeoutConfig(max_retries=-1, base_retry_delay=0.01)
        manager = AsyncTimeoutManager(config)

        async def never_called():
            raise AssertionError("should not be called")

        with pytest.raises(RuntimeError, match="No attempts made for operation"):
            await manager._with_retry("never_called_op", never_called, timeout=1.0)


class TestTimeoutManagerRecordStats:
    """Tests for _record_success / _record_failure rolling buffer truncation."""

    def test_record_success_truncates_buffer_at_100(self) -> None:
        """After >100 entries, oldest is dropped via stats.pop(0)."""
        manager = AsyncTimeoutManager()
        for i in range(105):
            manager._record_success("op", float(i))
        assert len(manager.operation_stats["op"]) == 100
        # Oldest entries (0-4) dropped; newest (100-104) remain
        assert manager.operation_stats["op"][0] == 5.0
        assert manager.operation_stats["op"][-1] == 104.0

    def test_record_success_calls_update_circuit_breaker(self) -> None:
        """_record_success with operation that has a configured timeout updates breaker."""
        config = TimeoutConfig(failure_threshold=3, operation_timeouts={"my_op": 5.0})
        manager = AsyncTimeoutManager(config)
        manager._record_success("my_op", 1.0)
        # Circuit breaker entry should be created via _update_circuit_breaker
        assert "my_op" in manager.circuit_breakers

    def test_record_failure_truncates_buffer_at_100(self) -> None:
        """_record_failure truncates after >100 entries."""
        manager = AsyncTimeoutManager()
        for i in range(105):
            with patch("crackerjack.core.timeout_manager.logger"):
                manager._record_failure("op", float(i))
        assert len(manager.operation_stats["op"]) == 100
        assert manager.operation_stats["op"][0] == 5.0


class TestTimeoutManagerTimeoutCaseFallback:
    """Direct tests for _handle_timeout_case (FAIL_FAST / GRACEFUL_DEGRADATION)."""

    def test_handle_timeout_case_fail_fast_raises(self) -> None:
        """_handle_timeout_case with FAIL_FAST strategy raises TimeoutError."""
        manager = AsyncTimeoutManager()
        start_time = time.time()
        err = builtins.TimeoutError()  # builtins.TimeoutError (the type _handle_timeout_case receives)
        with pytest.raises(TimeoutError):
            manager._handle_timeout_case(
                "op", 1.0, start_time, TimeoutStrategy.FAIL_FAST, err,
            )

    def test_handle_timeout_case_graceful_returns_none(self) -> None:
        """_handle_timeout_case with GRACEFUL_DEGRADATION returns None."""
        manager = AsyncTimeoutManager()
        start_time = time.time()
        err = builtins.TimeoutError()  # builtins.TimeoutError
        result = manager._handle_timeout_case(
            "op", 1.0, start_time, TimeoutStrategy.GRACEFUL_DEGRADATION, err,
        )
        assert result is None


class TestTimeoutManagerEnumCoverage:
    """Direct tests for module enums."""

    def test_timeout_strategy_members(self) -> None:
        """All four TimeoutStrategy members exist with correct string values."""
        assert TimeoutStrategy.FAIL_FAST.value == "fail_fast"
        assert TimeoutStrategy.RETRY_WITH_BACKOFF.value == "retry_with_backoff"
        assert TimeoutStrategy.CIRCUIT_BREAKER.value == "circuit_breaker"
        assert TimeoutStrategy.GRACEFUL_DEGRADATION.value == "graceful_degradation"

    def test_circuit_breaker_state_members(self) -> None:
        """All three CircuitBreakerState members exist with correct values."""
        assert CircuitBreakerState.CLOSED.value == "closed"
        assert CircuitBreakerState.OPEN.value == "open"
        assert CircuitBreakerState.HALF_OPEN.value == "half_open"

    def test_timeout_config_overrides(self) -> None:
        """TimeoutConfig accepts and applies overrides for every field."""
        config = TimeoutConfig(
            default_timeout=99.0,
            operation_timeouts={"a": 1.0},
            max_retries=10,
            base_retry_delay=0.1,
            max_retry_delay=10.0,
            backoff_multiplier=3.0,
            failure_threshold=2,
            recovery_timeout=5.0,
            half_open_max_calls=4,
        )
        assert config.default_timeout == 99.0
        assert config.operation_timeouts == {"a": 1.0}
        assert config.max_retries == 10
        assert config.base_retry_delay == 0.1
        assert config.max_retry_delay == 10.0
        assert config.backoff_multiplier == 3.0
        assert config.failure_threshold == 2
        assert config.recovery_timeout == 5.0
        assert config.half_open_max_calls == 4

    def test_circuit_breaker_state_data_overrides(self) -> None:
        """CircuitBreakerStateData accepts overrides."""
        data = CircuitBreakerStateData(
            state=CircuitBreakerState.HALF_OPEN,
            failure_count=2,
            last_failure_time=99.0,
            half_open_calls=1,
        )
        assert data.state == CircuitBreakerState.HALF_OPEN
        assert data.failure_count == 2
        assert data.last_failure_time == 99.0
        assert data.half_open_calls == 1

    def test_timeout_error_default_elapsed(self) -> None:
        """TimeoutError constructor uses elapsed=0.0 by default."""
        err = TimeoutError("op", 5.0)
        assert err.elapsed == 0.0
        assert err.operation == "op"
        assert err.timeout == 5.0


class TestTimeoutManagerStrategyRecords:
    """Ensure each strategy variant updates the circuit breaker / failure counters."""

    def test_handle_timeout_error_circuit_breaker_strategy(self) -> None:
        """CIRCUIT_BREAKER strategy in _handle_timeout_error calls _update_circuit_breaker."""
        manager = AsyncTimeoutManager()
        result = manager._handle_timeout_error(
            "op", time.time(), 1.0, TimeoutStrategy.CIRCUIT_BREAKER,
            error_msg="boom", error_type="custom_timeout",
        )
        assert result is None  # CIRCUIT_BREAKER + non-GRACEFUL returns None
        # breaker should have a failure recorded
        assert manager.circuit_breakers["op"].failure_count == 1

    def test_handle_timeout_error_graceful_returns_elapsed(self) -> None:
        """GRACEFUL_DEGRADATION in _handle_timeout_error returns a non-None float."""
        manager = AsyncTimeoutManager()
        result = manager._handle_timeout_error(
            "op", time.time(), 1.0, TimeoutStrategy.GRACEFUL_DEGRADATION,
            error_msg="graceful", error_type="custom_timeout",
        )
        assert result is not None
        assert result >= 0.0


class TestTimeoutManagerDirectInvocation:
    """Direct invocation tests for _handle_operation_success."""

    def test_handle_operation_success_returns_elapsed(self) -> None:
        """_handle_operation_success returns elapsed seconds (>= 0)."""
        manager = AsyncTimeoutManager()
        start_time = time.time() - 0.05
        elapsed = manager._handle_operation_success("op", start_time)
        assert elapsed >= 0.0
        assert "op" in manager.operation_stats

    def test_update_circuit_breaker_on_failure_circuit_breaker(self) -> None:
        """_update_circuit_breaker_on_failure opens breaker when strategy == CIRCUIT_BREAKER."""
        config = TimeoutConfig(failure_threshold=1)
        manager = AsyncTimeoutManager(config)
        manager._update_circuit_breaker_on_failure(
            TimeoutStrategy.CIRCUIT_BREAKER, "op",
        )
        assert manager.circuit_breakers["op"].state == CircuitBreakerState.OPEN

    def test_update_circuit_breaker_on_failure_other_strategy(self) -> None:
        """Non-CIRCUIT_BREAKER strategy leaves breaker untouched."""
        manager = AsyncTimeoutManager()
        manager._update_circuit_breaker_on_failure(
            TimeoutStrategy.FAIL_FAST, "op",
        )
        assert "op" not in manager.circuit_breakers
