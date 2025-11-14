"""Unit tests for timeout_manager.

Tests timeout strategies, circuit breakers, retry logic,
and async timeout management.
"""

import asyncio
import time
from unittest.mock import Mock, patch

import pytest

from crackerjack.core.timeout_manager import (
    AsyncTimeoutManager,
    CircuitBreakerState,
    CircuitBreakerStateData,
    TimeoutConfig,
    TimeoutError,
    TimeoutStrategy,
    configure_timeouts,
    get_performance_report,
    get_timeout_manager,
    timeout_async,
)


@pytest.mark.unit
class TestTimeoutStrategyEnum:
    """Test TimeoutStrategy enum."""

    def test_timeout_strategy_values(self):
        """Test TimeoutStrategy enum values."""
        assert TimeoutStrategy.FAIL_FAST == "fail_fast"
        assert TimeoutStrategy.RETRY_WITH_BACKOFF == "retry_with_backoff"
        assert TimeoutStrategy.CIRCUIT_BREAKER == "circuit_breaker"
        assert TimeoutStrategy.GRACEFUL_DEGRADATION == "graceful_degradation"


@pytest.mark.unit
class TestCircuitBreakerStateEnum:
    """Test CircuitBreakerState enum."""

    def test_circuit_breaker_state_values(self):
        """Test CircuitBreakerState enum values."""
        assert CircuitBreakerState.CLOSED == "closed"
        assert CircuitBreakerState.OPEN == "open"
        assert CircuitBreakerState.HALF_OPEN == "half_open"


@pytest.mark.unit
class TestTimeoutConfig:
    """Test TimeoutConfig dataclass."""

    def test_default_config(self):
        """Test default configuration."""
        config = TimeoutConfig()

        assert config.default_timeout == 30.0
        assert config.max_retries == 3
        assert config.base_retry_delay == 1.0
        assert config.max_retry_delay == 60.0
        assert config.backoff_multiplier == 2.0
        assert config.failure_threshold == 5
        assert config.recovery_timeout == 60.0
        assert config.half_open_max_calls == 3

    def test_operation_timeouts_defaults(self):
        """Test default operation timeouts."""
        config = TimeoutConfig()

        assert config.operation_timeouts["fast_hooks"] == 60.0
        assert config.operation_timeouts["comprehensive_hooks"] == 300.0
        assert config.operation_timeouts["test_execution"] == 600.0
        assert config.operation_timeouts["ai_agent_processing"] == 180.0
        assert config.operation_timeouts["file_operations"] == 10.0
        assert config.operation_timeouts["network_operations"] == 15.0
        assert config.operation_timeouts["websocket_broadcast"] == 5.0
        assert config.operation_timeouts["workflow_iteration"] == 900.0
        assert config.operation_timeouts["complete_workflow"] == 3600.0

    def test_custom_config(self):
        """Test custom configuration."""
        config = TimeoutConfig(
            default_timeout=60.0,
            max_retries=5,
            base_retry_delay=2.0,
            failure_threshold=10,
        )

        assert config.default_timeout == 60.0
        assert config.max_retries == 5
        assert config.base_retry_delay == 2.0
        assert config.failure_threshold == 10

    def test_custom_operation_timeouts(self):
        """Test custom operation timeouts."""
        custom_timeouts = {"custom_operation": 120.0}
        config = TimeoutConfig(operation_timeouts=custom_timeouts)

        assert config.operation_timeouts["custom_operation"] == 120.0


@pytest.mark.unit
class TestCircuitBreakerStateData:
    """Test CircuitBreakerStateData dataclass."""

    def test_default_state_data(self):
        """Test default circuit breaker state."""
        state = CircuitBreakerStateData()

        assert state.state == CircuitBreakerState.CLOSED
        assert state.failure_count == 0
        assert state.last_failure_time == 0.0
        assert state.half_open_calls == 0

    def test_custom_state_data(self):
        """Test custom circuit breaker state."""
        state = CircuitBreakerStateData(
            state=CircuitBreakerState.OPEN,
            failure_count=5,
            last_failure_time=123.45,
            half_open_calls=2,
        )

        assert state.state == CircuitBreakerState.OPEN
        assert state.failure_count == 5
        assert state.last_failure_time == 123.45
        assert state.half_open_calls == 2


@pytest.mark.unit
class TestTimeoutError:
    """Test TimeoutError exception."""

    def test_timeout_error_message(self):
        """Test timeout error message formatting."""
        error = TimeoutError("test_op", 30.0, 35.5)

        assert error.operation == "test_op"
        assert error.timeout == 30.0
        assert error.elapsed == 35.5
        assert "test_op" in str(error)
        assert "30" in str(error)

    def test_timeout_error_without_elapsed(self):
        """Test timeout error without elapsed time."""
        error = TimeoutError("test_op", 30.0)

        assert error.operation == "test_op"
        assert error.timeout == 30.0
        assert error.elapsed == 0.0


@pytest.mark.unit
class TestAsyncTimeoutManagerInitialization:
    """Test AsyncTimeoutManager initialization."""

    def test_initialization_default(self):
        """Test default initialization."""
        manager = AsyncTimeoutManager()

        assert isinstance(manager.config, TimeoutConfig)
        assert manager.circuit_breakers == {}
        assert manager.operation_stats == {}

    def test_initialization_with_config(self):
        """Test initialization with custom config."""
        config = TimeoutConfig(default_timeout=60.0)
        manager = AsyncTimeoutManager(config)

        assert manager.config == config
        assert manager.config.default_timeout == 60.0

    def test_get_timeout_custom_operation(self):
        """Test getting timeout for custom operation."""
        config = TimeoutConfig()
        manager = AsyncTimeoutManager(config)

        timeout = manager.get_timeout("fast_hooks")

        assert timeout == 60.0

    def test_get_timeout_unknown_operation(self):
        """Test getting timeout for unknown operation."""
        manager = AsyncTimeoutManager()

        timeout = manager.get_timeout("unknown_operation")

        assert timeout == 30.0  # default_timeout


@pytest.mark.unit
class TestAsyncTimeoutManagerPerformanceMonitor:
    """Test performance monitor integration."""

    def test_performance_monitor_lazy_loading(self):
        """Test performance monitor is lazily loaded."""
        manager = AsyncTimeoutManager()

        # Access the performance monitor
        monitor = manager.performance_monitor

        assert monitor is not None

    def test_performance_monitor_fallback_to_dummy(self):
        """Test fallback to dummy monitor when import fails."""
        manager = AsyncTimeoutManager()

        # Performance monitor should use dummy if real one unavailable
        monitor = manager.performance_monitor

        # Dummy monitor methods should be callable
        start_time = monitor.record_operation_start("test_op")
        assert isinstance(start_time, float)

        monitor.record_operation_success("test_op", start_time)
        monitor.record_operation_failure("test_op", start_time)

        stats = monitor.get_summary_stats()
        assert isinstance(stats, dict)


@pytest.mark.unit
class TestAsyncTimeoutManagerTimeoutContext:
    """Test timeout context manager."""

    @pytest.mark.asyncio
    async def test_timeout_context_success(self):
        """Test timeout context with successful operation."""
        manager = AsyncTimeoutManager()

        async with manager.timeout_context("test_op", timeout=1.0):
            await asyncio.sleep(0.1)

        # Should complete without error

    @pytest.mark.asyncio
    async def test_timeout_context_timeout(self):
        """Test timeout context with timeout."""
        manager = AsyncTimeoutManager()

        with pytest.raises(TimeoutError) as exc_info:
            async with manager.timeout_context("test_op", timeout=0.1):
                await asyncio.sleep(1.0)

        assert exc_info.value.operation == "test_op"

    @pytest.mark.asyncio
    async def test_timeout_context_uses_config_timeout(self):
        """Test timeout context uses configured timeout."""
        config = TimeoutConfig(operation_timeouts={"custom_op": 0.1})
        manager = AsyncTimeoutManager(config)

        with pytest.raises(TimeoutError):
            async with manager.timeout_context("custom_op"):
                await asyncio.sleep(1.0)

    @pytest.mark.asyncio
    async def test_timeout_context_caps_excessive_timeout(self):
        """Test timeout context caps excessive timeout."""
        manager = AsyncTimeoutManager()

        # Should cap at 7200s and log warning
        with patch("crackerjack.core.timeout_manager.logger") as mock_logger:
            async with manager.timeout_context("test_op", timeout=10000.0):
                await asyncio.sleep(0.01)

            mock_logger.warning.assert_called_once()
            assert "Capping excessive timeout" in mock_logger.warning.call_args[0][0]

    @pytest.mark.asyncio
    async def test_timeout_context_graceful_degradation(self):
        """Test timeout context with graceful degradation."""
        manager = AsyncTimeoutManager()

        # Should not raise error with graceful degradation
        async with manager.timeout_context(
            "test_op", timeout=0.1, strategy=TimeoutStrategy.GRACEFUL_DEGRADATION
        ):
            await asyncio.sleep(1.0)

        # Should complete without raising


@pytest.mark.unit
class TestAsyncTimeoutManagerWithTimeout:
    """Test with_timeout method."""

    @pytest.mark.asyncio
    async def test_with_timeout_success(self):
        """Test with_timeout with successful operation."""
        manager = AsyncTimeoutManager()

        async def operation():
            await asyncio.sleep(0.1)
            return "success"

        result = await manager.with_timeout("test_op", operation(), timeout=1.0)

        assert result == "success"

    @pytest.mark.asyncio
    async def test_with_timeout_timeout(self):
        """Test with_timeout with timeout."""
        manager = AsyncTimeoutManager()

        async def operation():
            await asyncio.sleep(1.0)
            return "success"

        with pytest.raises(TimeoutError):
            await manager.with_timeout("test_op", operation(), timeout=0.1)

    @pytest.mark.asyncio
    async def test_with_timeout_graceful_degradation(self):
        """Test with_timeout with graceful degradation."""
        manager = AsyncTimeoutManager()

        async def operation():
            await asyncio.sleep(1.0)
            return "success"

        result = await manager.with_timeout(
            "test_op",
            operation(),
            timeout=0.1,
            strategy=TimeoutStrategy.GRACEFUL_DEGRADATION,
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_with_timeout_circuit_breaker_open(self):
        """Test with_timeout when circuit breaker is open."""
        config = TimeoutConfig(failure_threshold=1)
        manager = AsyncTimeoutManager(config)

        # First fail to open circuit breaker
        async def failing_operation():
            await asyncio.sleep(1.0)

        try:
            await manager.with_timeout(
                "test_op",
                failing_operation(),
                timeout=0.1,
                strategy=TimeoutStrategy.CIRCUIT_BREAKER,
            )
        except TimeoutError:
            pass

        # Second call should fail immediately due to open circuit
        with pytest.raises(TimeoutError):
            await manager.with_timeout(
                "test_op",
                failing_operation(),
                timeout=1.0,
                strategy=TimeoutStrategy.CIRCUIT_BREAKER,
            )


@pytest.mark.unit
class TestAsyncTimeoutManagerCircuitBreaker:
    """Test circuit breaker functionality."""

    def test_check_circuit_breaker_new_operation(self):
        """Test circuit breaker check for new operation."""
        manager = AsyncTimeoutManager()

        result = manager._check_circuit_breaker("new_op")

        assert result is True
        assert "new_op" in manager.circuit_breakers
        assert manager.circuit_breakers["new_op"].state == CircuitBreakerState.CLOSED

    def test_check_circuit_breaker_closed_state(self):
        """Test circuit breaker check when closed."""
        manager = AsyncTimeoutManager()
        manager.circuit_breakers["test_op"] = CircuitBreakerStateData(
            state=CircuitBreakerState.CLOSED
        )

        result = manager._check_circuit_breaker("test_op")

        assert result is True

    def test_check_circuit_breaker_open_state(self):
        """Test circuit breaker check when open."""
        manager = AsyncTimeoutManager()
        manager.circuit_breakers["test_op"] = CircuitBreakerStateData(
            state=CircuitBreakerState.OPEN, last_failure_time=time.time()
        )

        result = manager._check_circuit_breaker("test_op")

        assert result is False

    def test_check_circuit_breaker_open_to_half_open(self):
        """Test circuit breaker transitions from open to half-open."""
        config = TimeoutConfig(recovery_timeout=0.1)
        manager = AsyncTimeoutManager(config)

        # Set circuit breaker to open with old failure time
        manager.circuit_breakers["test_op"] = CircuitBreakerStateData(
            state=CircuitBreakerState.OPEN, last_failure_time=time.time() - 1.0
        )

        result = manager._check_circuit_breaker("test_op")

        assert result is True
        assert manager.circuit_breakers["test_op"].state == CircuitBreakerState.HALF_OPEN
        assert manager.circuit_breakers["test_op"].half_open_calls == 0

    def test_check_circuit_breaker_half_open_under_limit(self):
        """Test circuit breaker check when half-open under call limit."""
        manager = AsyncTimeoutManager()
        manager.circuit_breakers["test_op"] = CircuitBreakerStateData(
            state=CircuitBreakerState.HALF_OPEN, half_open_calls=1
        )

        result = manager._check_circuit_breaker("test_op")

        assert result is True
        assert manager.circuit_breakers["test_op"].half_open_calls == 2

    def test_check_circuit_breaker_half_open_at_limit(self):
        """Test circuit breaker check when half-open at call limit."""
        config = TimeoutConfig(half_open_max_calls=3)
        manager = AsyncTimeoutManager(config)
        manager.circuit_breakers["test_op"] = CircuitBreakerStateData(
            state=CircuitBreakerState.HALF_OPEN, half_open_calls=3
        )

        result = manager._check_circuit_breaker("test_op")

        assert result is False

    def test_update_circuit_breaker_success_closed(self):
        """Test updating circuit breaker on success when closed."""
        manager = AsyncTimeoutManager()
        manager.circuit_breakers["test_op"] = CircuitBreakerStateData(
            state=CircuitBreakerState.CLOSED, failure_count=2
        )

        manager._update_circuit_breaker("test_op", success=True)

        assert manager.circuit_breakers["test_op"].failure_count == 1

    def test_update_circuit_breaker_success_half_open(self):
        """Test updating circuit breaker on success when half-open."""
        manager = AsyncTimeoutManager()
        manager.circuit_breakers["test_op"] = CircuitBreakerStateData(
            state=CircuitBreakerState.HALF_OPEN, failure_count=3
        )

        manager._update_circuit_breaker("test_op", success=True)

        assert manager.circuit_breakers["test_op"].state == CircuitBreakerState.CLOSED
        assert manager.circuit_breakers["test_op"].failure_count == 0

    def test_update_circuit_breaker_failure(self):
        """Test updating circuit breaker on failure."""
        manager = AsyncTimeoutManager()
        manager.circuit_breakers["test_op"] = CircuitBreakerStateData(
            state=CircuitBreakerState.CLOSED, failure_count=0
        )

        manager._update_circuit_breaker("test_op", success=False)

        assert manager.circuit_breakers["test_op"].failure_count == 1
        assert manager.circuit_breakers["test_op"].last_failure_time > 0

    def test_update_circuit_breaker_opens_on_threshold(self):
        """Test circuit breaker opens when threshold reached."""
        config = TimeoutConfig(failure_threshold=3)
        manager = AsyncTimeoutManager(config)
        manager.circuit_breakers["test_op"] = CircuitBreakerStateData(
            state=CircuitBreakerState.CLOSED, failure_count=2
        )

        manager._update_circuit_breaker("test_op", success=False)

        assert manager.circuit_breakers["test_op"].state == CircuitBreakerState.OPEN
        assert manager.circuit_breakers["test_op"].failure_count == 3


@pytest.mark.unit
class TestAsyncTimeoutManagerStats:
    """Test statistics tracking."""

    def test_record_success(self):
        """Test recording successful operation."""
        manager = AsyncTimeoutManager()

        manager._record_success("test_op", 1.5)

        assert "test_op" in manager.operation_stats
        assert 1.5 in manager.operation_stats["test_op"]

    def test_record_success_limits_history(self):
        """Test success recording limits history to 100 entries."""
        manager = AsyncTimeoutManager()

        # Record 150 operations
        for i in range(150):
            manager._record_success("test_op", float(i))

        # Should only keep last 100
        assert len(manager.operation_stats["test_op"]) == 100
        assert 0.0 not in manager.operation_stats["test_op"]
        assert 149.0 in manager.operation_stats["test_op"]

    def test_record_failure(self):
        """Test recording failed operation."""
        manager = AsyncTimeoutManager()

        with patch("crackerjack.core.timeout_manager.logger") as mock_logger:
            manager._record_failure("test_op", 35.5)

            mock_logger.warning.assert_called_once()
            assert "test_op" in mock_logger.warning.call_args[0][0]

    def test_get_stats_no_data(self):
        """Test getting stats for operation with no data."""
        manager = AsyncTimeoutManager()

        stats = manager.get_stats("unknown_op")

        assert stats["count"] == 0
        assert stats["avg_time"] == 0.0
        assert stats["min_time"] == 0.0
        assert stats["max_time"] == 0.0
        assert stats["success_rate"] == 0.0

    def test_get_stats_with_data(self):
        """Test getting stats for operation with data."""
        manager = AsyncTimeoutManager()

        manager._record_success("test_op", 1.0)
        manager._record_success("test_op", 2.0)
        manager._record_success("test_op", 3.0)

        stats = manager.get_stats("test_op")

        assert stats["count"] == 3
        assert stats["avg_time"] == 2.0
        assert stats["min_time"] == 1.0
        assert stats["max_time"] == 3.0
        assert stats["success_rate"] > 0.0


@pytest.mark.unit
class TestTimeoutAsyncDecorator:
    """Test timeout_async decorator."""

    @pytest.mark.asyncio
    async def test_decorator_success(self):
        """Test decorator with successful operation."""

        @timeout_async("test_op", timeout=1.0)
        async def operation():
            await asyncio.sleep(0.1)
            return "success"

        result = await operation()

        assert result == "success"

    @pytest.mark.asyncio
    async def test_decorator_timeout(self):
        """Test decorator with timeout."""

        @timeout_async("test_op", timeout=0.1)
        async def operation():
            await asyncio.sleep(1.0)
            return "success"

        with pytest.raises(TimeoutError):
            await operation()

    @pytest.mark.asyncio
    async def test_decorator_with_strategy(self):
        """Test decorator with timeout strategy."""

        @timeout_async(
            "test_op", timeout=0.1, strategy=TimeoutStrategy.GRACEFUL_DEGRADATION
        )
        async def operation():
            await asyncio.sleep(1.0)
            return "success"

        result = await operation()

        assert result is None


@pytest.mark.unit
class TestGlobalTimeoutManager:
    """Test global timeout manager functions."""

    def test_get_timeout_manager_singleton(self):
        """Test get_timeout_manager returns singleton."""
        # Reset global state
        import crackerjack.core.timeout_manager as tm

        tm._global_timeout_manager = None

        manager1 = get_timeout_manager()
        manager2 = get_timeout_manager()

        assert manager1 is manager2

    def test_configure_timeouts(self):
        """Test configuring global timeout manager."""
        config = TimeoutConfig(default_timeout=60.0)

        configure_timeouts(config)

        manager = get_timeout_manager()
        assert manager.config.default_timeout == 60.0

    def test_get_performance_report_structure(self):
        """Test performance report structure."""
        # Reset and configure
        import crackerjack.core.timeout_manager as tm

        tm._global_timeout_manager = None
        configure_timeouts(TimeoutConfig())

        report = get_performance_report()

        assert "summary" in report
        assert "metrics" in report
        assert "alerts" in report
        assert "recent_timeouts" in report
        assert "circuit_breakers" in report

    def test_get_performance_report_with_data(self):
        """Test performance report with circuit breaker data."""
        import crackerjack.core.timeout_manager as tm

        tm._global_timeout_manager = None

        manager = get_timeout_manager()
        manager.circuit_breakers["test_op"] = CircuitBreakerStateData(
            state=CircuitBreakerState.OPEN, failure_count=5, last_failure_time=123.45
        )

        report = get_performance_report()

        assert "test_op" in report["circuit_breakers"]
        assert report["circuit_breakers"]["test_op"]["state"] == "open"
        assert report["circuit_breakers"]["test_op"]["failure_count"] == 5


@pytest.mark.unit
class TestAsyncTimeoutManagerRetry:
    """Test retry functionality."""

    @pytest.mark.asyncio
    async def test_with_retry_success_first_attempt(self):
        """Test retry succeeds on first attempt."""
        manager = AsyncTimeoutManager()
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            return "success"

        result = await manager._with_retry("test_op", operation, timeout=1.0)

        assert result == "success"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_with_retry_success_after_retries(self):
        """Test retry succeeds after initial failures."""
        manager = AsyncTimeoutManager()
        call_count = 0

        async def operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("test_op", 1.0)
            return "success"

        result = await manager._with_retry("test_op", operation, timeout=1.0)

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_with_retry_exhausts_retries(self):
        """Test retry exhausts all attempts."""
        config = TimeoutConfig(max_retries=2, base_retry_delay=0.01)
        manager = AsyncTimeoutManager(config)

        async def operation():
            raise TimeoutError("test_op", 1.0)

        with pytest.raises(TimeoutError):
            await manager._with_retry("test_op", operation, timeout=1.0)

    @pytest.mark.asyncio
    async def test_with_retry_backoff(self):
        """Test retry uses exponential backoff."""
        config = TimeoutConfig(
            max_retries=2, base_retry_delay=0.1, backoff_multiplier=2.0
        )
        manager = AsyncTimeoutManager(config)
        delays = []

        original_sleep = asyncio.sleep

        async def mock_sleep(delay):
            delays.append(delay)
            await original_sleep(0.01)  # Sleep briefly for test

        async def operation():
            raise TimeoutError("test_op", 1.0)

        with patch("asyncio.sleep", side_effect=mock_sleep):
            with pytest.raises(TimeoutError):
                await manager._with_retry("test_op", operation, timeout=1.0)

        # Should have delays: 0.1, 0.2 (exponential backoff)
        assert len(delays) == 2
        assert delays[0] == 0.1
        assert delays[1] == 0.2


@pytest.mark.unit
class TestAsyncTimeoutManagerIntegration:
    """Test integration scenarios."""

    @pytest.mark.asyncio
    async def test_complete_circuit_breaker_lifecycle(self):
        """Test complete circuit breaker lifecycle."""
        config = TimeoutConfig(
            failure_threshold=2, recovery_timeout=0.1, half_open_max_calls=2
        )
        manager = AsyncTimeoutManager(config)

        async def failing_operation():
            await asyncio.sleep(1.0)

        async def successful_operation():
            await asyncio.sleep(0.01)
            return "success"

        # 1. Closed state - operations succeed
        result = await manager.with_timeout(
            "test_op",
            successful_operation(),
            timeout=1.0,
            strategy=TimeoutStrategy.CIRCUIT_BREAKER,
        )
        assert result == "success"

        # 2. Trigger failures to open circuit
        for _ in range(2):
            try:
                await manager.with_timeout(
                    "test_op",
                    failing_operation(),
                    timeout=0.01,
                    strategy=TimeoutStrategy.CIRCUIT_BREAKER,
                )
            except TimeoutError:
                pass

        # 3. Circuit is now open - should fail immediately
        assert manager.circuit_breakers["test_op"].state == CircuitBreakerState.OPEN

        # 4. Wait for recovery timeout
        await asyncio.sleep(0.2)

        # 5. Circuit transitions to half-open
        result = await manager.with_timeout(
            "test_op",
            successful_operation(),
            timeout=1.0,
            strategy=TimeoutStrategy.CIRCUIT_BREAKER,
        )
        assert result == "success"

        # 6. Circuit closes after successful call
        assert manager.circuit_breakers["test_op"].state == CircuitBreakerState.CLOSED

    @pytest.mark.asyncio
    async def test_multiple_operations_tracking(self):
        """Test tracking multiple operations."""
        manager = AsyncTimeoutManager()

        async def op1():
            await asyncio.sleep(0.01)
            return "op1"

        async def op2():
            await asyncio.sleep(0.02)
            return "op2"

        # Execute multiple operations
        await manager.with_timeout("operation_1", op1(), timeout=1.0)
        await manager.with_timeout("operation_2", op2(), timeout=1.0)
        await manager.with_timeout("operation_1", op1(), timeout=1.0)

        # Check stats
        stats1 = manager.get_stats("operation_1")
        stats2 = manager.get_stats("operation_2")

        assert stats1["count"] == 2
        assert stats2["count"] == 1
