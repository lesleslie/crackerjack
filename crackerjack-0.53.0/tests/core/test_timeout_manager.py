import asyncio
import pytest
from unittest.mock import Mock, patch
from crackerjack.core.timeout_manager import (
    AsyncTimeoutManager,
    TimeoutConfig,
    TimeoutStrategy,
    CircuitBreakerState,
    CircuitBreakerStateData,
    TimeoutError,
    timeout_async,
    get_timeout_manager,
    configure_timeouts,
    get_performance_report,
    _DummyPerformanceMonitor
)


def test_dummy_performance_monitor():
    """Test the dummy performance monitor."""
    monitor = _DummyPerformanceMonitor()

    # Test all methods
    start_time = monitor.record_operation_start("test_op")
    assert isinstance(start_time, float)

    monitor.record_operation_success("test_op", start_time)
    monitor.record_operation_failure("test_op", start_time)
    monitor.record_operation_timeout("test_op", start_time, 10.0, "test error")
    monitor.record_circuit_breaker_event("test_op", True)

    summary = monitor.get_summary_stats()
    assert summary == {}

    metrics = monitor.get_all_metrics()
    assert metrics == {}

    alerts = monitor.get_performance_alerts()
    assert alerts == []

    recent_events = monitor.get_recent_timeout_events(5)
    assert recent_events == []


def test_timeout_config_defaults():
    """Test default values in TimeoutConfig."""
    config = TimeoutConfig()

    assert config.default_timeout == 30.0
    assert config.max_retries == 3
    assert config.base_retry_delay == 1.0
    assert config.max_retry_delay == 60.0
    assert config.backoff_multiplier == 2.0
    assert config.failure_threshold == 5
    assert config.recovery_timeout == 60.0
    assert config.half_open_max_calls == 3

    # Check operation timeouts
    expected_ops = [
        "fast_hooks", "comprehensive_hooks", "test_execution",
        "ai_agent_processing", "file_operations", "network_operations",
        "workflow_iteration", "complete_workflow"
    ]
    for op in expected_ops:
        assert op in config.operation_timeouts


def test_circuit_breaker_state_enum():
    """Test CircuitBreakerState enum values."""
    assert CircuitBreakerState.CLOSED.value == "closed"
    assert CircuitBreakerState.OPEN.value == "open"
    assert CircuitBreakerState.HALF_OPEN.value == "half_open"


def test_circuit_breaker_state_data_defaults():
    """Test default values in CircuitBreakerStateData."""
    state_data = CircuitBreakerStateData()

    assert state_data.state == CircuitBreakerState.CLOSED
    assert state_data.failure_count == 0
    assert state_data.last_failure_time == 0.0
    assert state_data.half_open_calls == 0


def test_timeout_error():
    """Test TimeoutError exception."""
    error = TimeoutError("op1", 10.0, 5.0)

    assert error.operation == "op1"
    assert error.timeout == 10.0
    assert error.elapsed == 5.0
    assert "Operation 'op1' timed out after 10.0s" in str(error)


def test_async_timeout_manager_initialization():
    """Test AsyncTimeoutManager initialization."""
    config = TimeoutConfig(default_timeout=45.0)
    manager = AsyncTimeoutManager(config)

    assert manager.config == config
    assert manager.circuit_breakers == {}
    assert manager.operation_stats == {}
    assert manager._performance_monitor is None


def test_get_timeout():
    """Test getting timeout for operations."""
    config = TimeoutConfig(
        default_timeout=45.0,
        operation_timeouts={"fast_hooks": 120.0}
    )
    manager = AsyncTimeoutManager(config)

    # Test custom operation timeout
    assert manager.get_timeout("fast_hooks") == 120.0

    # Test default timeout
    assert manager.get_timeout("unknown_op") == 45.0


@pytest.mark.asyncio
async def test_timeout_context_success():
    """Test timeout context manager with successful operation."""
    manager = AsyncTimeoutManager()

    async with manager.timeout_context("test_op", timeout=1.0):
        # Simulate a quick operation
        await asyncio.sleep(0.01)

    # Check that stats were recorded
    stats = manager.get_stats("test_op")
    assert stats["count"] >= 1


@pytest.mark.asyncio
async def test_timeout_context_timeout():
    """Test timeout context manager with timeout."""
    manager = AsyncTimeoutManager()

    with pytest.raises(TimeoutError):
        async with manager.timeout_context("slow_op", timeout=0.01):
            # This will exceed the timeout
            await asyncio.sleep(0.1)


@pytest.mark.asyncio
async def test_with_timeout_success():
    """Test with_timeout method with successful operation."""
    manager = AsyncTimeoutManager()

    async def quick_operation():
        await asyncio.sleep(0.01)
        return "success"

    result = await manager.with_timeout("quick_op", quick_operation(), timeout=1.0)
    assert result == "success"


@pytest.mark.asyncio
async def test_with_timeout_timeout():
    """Test with_timeout method with timeout."""
    manager = AsyncTimeoutManager()

    async def slow_operation():
        await asyncio.sleep(1.0)
        return "never_reached"

    with pytest.raises(TimeoutError):
        await manager.with_timeout("slow_op", slow_operation(), timeout=0.01)


@pytest.mark.asyncio
async def test_with_timeout_graceful_degradation():
    """Test with_timeout method with graceful degradation strategy."""
    manager = AsyncTimeoutManager()

    async def slow_operation():
        await asyncio.sleep(1.0)
        return "never_reached"

    result = await manager.with_timeout(
        "slow_op",
        slow_operation(),
        timeout=0.01,
        strategy=TimeoutStrategy.GRACEFUL_DEGRADATION
    )
    assert result is None


def test_circuit_breaker_initial_state():
    """Test initial state of circuit breaker."""
    manager = AsyncTimeoutManager()

    # Initially, circuit breaker should allow calls
    assert manager._check_circuit_breaker("new_op") is True


def test_circuit_breaker_states():
    """Test circuit breaker state transitions."""
    config = TimeoutConfig(
        failure_threshold=2,  # Lower threshold for testing
        recovery_timeout=0.1   # Short recovery time for testing
    )
    manager = AsyncTimeoutManager(config)

    # Cause failures to trip the circuit breaker
    manager._update_circuit_breaker("test_op", success=False)  # 1st failure
    manager._update_circuit_breaker("test_op", success=False)  # 2nd failure (threshold reached)

    # Circuit should now be open
    assert manager._check_circuit_breaker("test_op") is False

    # Wait for recovery time to pass
    import time
    time.sleep(0.2)

    # Circuit should transition to half-open
    assert manager._check_circuit_breaker("test_op") is True  # First call after recovery opens half-open state


@pytest.mark.asyncio
async def test_timeout_async_decorator():
    """Test the timeout_async decorator."""
    @timeout_async(operation="decorated_op", timeout=0.1)
    async def decorated_function():
        await asyncio.sleep(0.01)
        return "success"

    result = await decorated_function()
    assert result == "success"


@pytest.mark.asyncio
async def test_timeout_async_decorator_timeout():
    """Test the timeout_async decorator with timeout."""
    @timeout_async(operation="slow_decorated_op", timeout=0.01)
    async def slow_decorated_function():
        await asyncio.sleep(0.1)
        return "never_reached"

    with pytest.raises(TimeoutError):
        await slow_decorated_function()


def test_get_timeout_manager():
    """Test getting the global timeout manager."""
    manager1 = get_timeout_manager()
    manager2 = get_timeout_manager()

    # Should return the same instance
    assert manager1 is manager2


def test_configure_timeouts():
    """Test configuring timeouts globally."""
    config = TimeoutConfig(default_timeout=90.0)
    configure_timeouts(config)

    manager = get_timeout_manager()
    assert manager.config.default_timeout == 90.0


def test_get_performance_report():
    """Test getting performance report."""
    report = get_performance_report()

    # Check that the report has the expected structure
    assert "summary" in report
    assert "metrics" in report
    assert "alerts" in report
    assert "recent_timeouts" in report
    assert "circuit_breakers" in report


def test_record_success_and_failure():
    """Test recording success and failure stats."""
    manager = AsyncTimeoutManager()

    # Record a success
    manager._record_success("test_op", 0.1)

    # Record a failure
    with patch('crackerjack.core.timeout_manager.logger'):
        manager._record_failure("test_op", 0.5)

    # Check stats
    stats = manager.get_stats("test_op")
    assert stats["count"] == 1  # Only successful operations are counted in the stats
