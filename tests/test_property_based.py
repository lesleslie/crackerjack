"""Property-based tests using Hypothesis for core functionality."""

from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from crackerjack.core.timeout_manager import (
    AsyncTimeoutManager,
    CircuitBreakerState,
    CircuitBreakerStateData,
    TimeoutConfig,
    TimeoutError,
    TimeoutStrategy,
    get_timeout_manager,
)


# Property-based tests for TimeoutConfig
@given(
    default_timeout=st.floats(min_value=1.0, max_value=3600.0),
    max_retries=st.integers(min_value=0, max_value=10),
    base_retry_delay=st.floats(min_value=0.1, max_value=10.0),
    failure_threshold=st.integers(min_value=1, max_value=20),
)
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_timeout_config_properties(
    default_timeout: float,
    max_retries: int,
    base_retry_delay: float,
    failure_threshold: int,
) -> None:
    """Property-based test for TimeoutConfig."""
    config = TimeoutConfig(
        default_timeout=default_timeout,
        max_retries=max_retries,
        base_retry_delay=base_retry_delay,
        failure_threshold=failure_threshold,
    )

    assert config.default_timeout == default_timeout
    assert config.max_retries == max_retries
    assert config.base_retry_delay == base_retry_delay
    assert config.failure_threshold == failure_threshold

    # Operation timeouts should always contain the default operations
    default_ops = [
        "fast_hooks",
        "comprehensive_hooks",
        "test_execution",
        "ai_agent_processing",
        "file_operations",
        "network_operations",
        "workflow_iteration",
        "complete_workflow",
    ]

    for op in default_ops:
        assert op in config.operation_timeouts


# Property-based tests for CircuitBreakerStateData
@given(
    state=st.sampled_from(list(CircuitBreakerState)),
    failure_count=st.integers(min_value=0, max_value=100),
    last_failure_time=st.floats(min_value=0.0, max_value=1e10),
    half_open_calls=st.integers(min_value=0, max_value=10),
)
def test_circuit_breaker_state_data_properties(
    state: CircuitBreakerState,
    failure_count: int,
    last_failure_time: float,
    half_open_calls: int,
) -> None:
    """Property-based test for CircuitBreakerStateData."""
    data = CircuitBreakerStateData(
        state=state,
        failure_count=failure_count,
        last_failure_time=last_failure_time,
        half_open_calls=half_open_calls,
    )

    assert data.state == state
    assert data.failure_count == failure_count
    assert data.last_failure_time == last_failure_time
    assert data.half_open_calls == half_open_calls


# Property-based tests for AsyncTimeoutManager
@given(
    default_timeout=st.floats(min_value=1.0, max_value=100.0),
    operation_name=st.text(alphabet=st.characters(min_codepoint=65, max_codepoint=90), min_size=1, max_size=20),
)
def test_async_timeout_manager_get_timeout_property(
    default_timeout: float,
    operation_name: str,
) -> None:
    """Property-based test for AsyncTimeoutManager.get_timeout."""
    config = TimeoutConfig(default_timeout=default_timeout)
    manager = AsyncTimeoutManager(config)

    # Test that getting a known operation timeout works
    known_op_timeout = manager.get_timeout("fast_hooks")
    assert known_op_timeout == 60.0  # Default for fast_hooks

    # Test that getting an unknown operation returns the default
    unknown_op_timeout = manager.get_timeout(operation_name)
    assert unknown_op_timeout == default_timeout


# Property-based test for TimeoutError
@given(
    operation=st.text(min_size=1, max_size=50),
    timeout=st.floats(min_value=0.1, max_value=100.0),
    elapsed=st.floats(min_value=0.0, max_value=200.0),
)
def test_timeout_error_properties(
    operation: str,
    timeout: float,
    elapsed: float,
) -> None:
    """Property-based test for TimeoutError properties."""
    error = TimeoutError(operation, timeout, elapsed)

    assert error.operation == operation
    assert error.timeout == timeout
    assert error.elapsed == elapsed
    assert operation in str(error)
    assert str(int(timeout)) in str(error)


# Property-based test for timeout strategies enum
@given(strategy=st.sampled_from(list(TimeoutStrategy)))
def test_timeout_strategy_values(strategy: TimeoutStrategy) -> None:
    """Property-based test for TimeoutStrategy enum values."""
    assert isinstance(strategy.value, str)
    assert len(strategy.value) > 0
    # Verify all strategies have different values
    all_strategies = list(TimeoutStrategy)
    all_values = [s.value for s in all_strategies]
    assert len(all_values) == len(set(all_values))


# Property-based test for circuit breaker states enum
@given(state=st.sampled_from(list(CircuitBreakerState)))
def test_circuit_breaker_state_values(state: CircuitBreakerState) -> None:
    """Property-based test for CircuitBreakerState enum values."""
    assert isinstance(state.value, str)
    assert len(state.value) > 0
    # Verify all states have different values
    all_states = list(CircuitBreakerState)
    all_values = [s.value for s in all_states]
    assert len(all_values) == len(set(all_values))


# Property-based test for global timeout manager
@given(
    timeout_val=st.floats(min_value=1.0, max_value=50.0),
)
def test_global_timeout_manager_property(timeout_val: float) -> None:
    """Property-based test for global timeout manager singleton."""
    # Reset the global timeout manager to ensure clean state
    import crackerjack.core.timeout_manager as tm
    tm._global_timeout_manager = None

    manager1 = get_timeout_manager()
    manager2 = get_timeout_manager()

    # Both calls should return the same instance (singleton)
    assert manager1 is manager2

    # Test that the manager works consistently
    timeout1 = manager1.get_timeout("test_op")
    timeout2 = manager2.get_timeout("test_op")

    assert timeout1 == timeout2
