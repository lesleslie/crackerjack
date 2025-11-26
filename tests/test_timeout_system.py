"""
Tests for the comprehensive timeout handling system.

This module tests the timeout manager, performance monitor,
and service watchdog components to ensure they prevent hanging.
"""

import asyncio
import time
from unittest.mock import Mock

import pytest

from crackerjack.core.performance_monitor import (
    AsyncPerformanceMonitor,
    get_performance_monitor,
)
from crackerjack.core.service_watchdog import (
    ServiceConfig,
    ServiceState,
    ServiceWatchdog,
)
from crackerjack.core.timeout_manager import (
    AsyncTimeoutManager,
    TimeoutConfig,
    TimeoutError,
    TimeoutStrategy,
    configure_timeouts,
    get_timeout_manager,
)


class TestTimeoutManager:
    """Test the AsyncTimeoutManager functionality."""

    def test_timeout_config_creation(self):
        """Test creating timeout configuration."""
        config = TimeoutConfig(
            default_timeout=30.0, operation_timeouts={"test_op": 10.0}, max_retries=5
        )
        assert config.default_timeout == 30.0
        assert config.operation_timeouts["test_op"] == 10.0
        assert config.max_retries == 5

    def test_timeout_manager_initialization(self):
        """Test timeout manager initialization."""
        config = TimeoutConfig(default_timeout=15.0)
        manager = AsyncTimeoutManager(config)

        assert manager.config.default_timeout == 15.0
        assert manager.get_timeout("unknown_operation") == 15.0
        assert len(manager.circuit_breakers) == 0

    def test_get_operation_timeout(self):
        """Test getting operation-specific timeouts."""
        config = TimeoutConfig(
            default_timeout=10.0,
            operation_timeouts={
                "fast_operation": 5.0,
                "slow_operation": 60.0,
            },
        )
        manager = AsyncTimeoutManager(config)

        assert manager.get_timeout("fast_operation") == 5.0
        assert manager.get_timeout("slow_operation") == 60.0
        assert manager.get_timeout("unknown_operation") == 10.0

    @pytest.mark.asyncio
    async def test_timeout_context_success(self):
        """Test successful operation with timeout context."""
        manager = AsyncTimeoutManager()

        async def quick_operation():
            await asyncio.sleep(0.1)
            return "success"

        async with manager.timeout_context("test_op", timeout=1.0):
            result = await quick_operation()
            assert result == "success"

    @pytest.mark.asyncio
    async def test_timeout_context_timeout(self):
        """Test timeout context with operation that times out."""
        manager = AsyncTimeoutManager()

        async def slow_operation():
            await asyncio.sleep(2.0)
            return "should not reach here"

        with pytest.raises(TimeoutError) as exc_info:
            async with manager.timeout_context("test_op", timeout=0.5):
                await slow_operation()

        assert exc_info.value.operation == "test_op"
        assert exc_info.value.timeout == 0.5

    @pytest.mark.asyncio
    async def test_with_timeout_success(self):
        """Test with_timeout method success."""
        manager = AsyncTimeoutManager()

        async def quick_operation():
            await asyncio.sleep(0.1)
            return "completed"

        result = await manager.with_timeout(
            "test_op",
            quick_operation(),
            timeout=1.0,
            strategy=TimeoutStrategy.FAIL_FAST,
        )
        assert result == "completed"

    @pytest.mark.asyncio
    async def test_with_timeout_failure(self):
        """Test with_timeout method with timeout."""
        manager = AsyncTimeoutManager()

        async def slow_operation():
            await asyncio.sleep(1.0)
            return "should not complete"

        with pytest.raises(TimeoutError):
            await manager.with_timeout(
                "test_op",
                slow_operation(),
                timeout=0.2,
                strategy=TimeoutStrategy.FAIL_FAST,
            )

    @pytest.mark.asyncio
    async def test_retry_strategy(self):
        """Test that retry strategy is recognized (implementation limitation note)."""
        manager = AsyncTimeoutManager(
            TimeoutConfig(max_retries=2, base_retry_delay=0.1)
        )

        async def simple_operation():
            return "completed"

        # Test that retry strategy doesn't break the timeout mechanism
        # Note: Current implementation falls back to regular timeout for retry strategy
        result = await manager.with_timeout(
            "test_op",
            simple_operation(),
            timeout=1.0,
            strategy=TimeoutStrategy.RETRY_WITH_BACKOFF,
        )
        assert result == "completed"

    def test_circuit_breaker_state_tracking(self):
        """Test circuit breaker state management."""
        manager = AsyncTimeoutManager(TimeoutConfig(failure_threshold=2))

        # Initially closed (should allow operations)
        assert manager._check_circuit_breaker("test_op") is True

        # Record failures
        manager._update_circuit_breaker("test_op", False)
        assert manager._check_circuit_breaker("test_op") is True  # Still closed

        manager._update_circuit_breaker("test_op", False)
        assert manager._check_circuit_breaker("test_op") is False  # Should be open now

    def test_global_timeout_manager(self):
        """Test global timeout manager functionality."""
        # Get global instance
        manager1 = get_timeout_manager()
        manager2 = get_timeout_manager()

        # Should be same instance
        assert manager1 is manager2

        # Test configuration
        custom_config = TimeoutConfig(default_timeout=25.0)
        configure_timeouts(custom_config)

        manager3 = get_timeout_manager()
        assert manager3.config.default_timeout == 25.0


class TestPerformanceMonitor:
    """Test the AsyncPerformanceMonitor functionality."""

    def test_performance_monitor_initialization(self):
        """Test performance monitor initialization."""
        monitor = AsyncPerformanceMonitor()

        assert len(monitor.metrics) == 0
        assert len(monitor.timeout_events) == 0
        assert monitor.start_time > 0

    def test_record_operation_success(self):
        """Test recording successful operations."""
        monitor = AsyncPerformanceMonitor()

        start_time = monitor.record_operation_start("test_op")
        time.sleep(0.1)  # Simulate work
        monitor.record_operation_success("test_op", start_time)

        metrics = monitor.get_operation_metrics("test_op")
        assert metrics is not None
        assert metrics.total_calls == 1
        assert metrics.successful_calls == 1
        assert metrics.failed_calls == 0
        assert metrics.success_rate == 100.0
        assert metrics.average_time > 0

    def test_record_operation_failure(self):
        """Test recording failed operations."""
        monitor = AsyncPerformanceMonitor()

        start_time = monitor.record_operation_start("test_op")
        time.sleep(0.1)
        monitor.record_operation_failure("test_op", start_time)

        metrics = monitor.get_operation_metrics("test_op")
        assert metrics is not None
        assert metrics.total_calls == 1
        assert metrics.successful_calls == 0
        assert metrics.failed_calls == 1
        assert metrics.success_rate == 0.0

    def test_record_operation_timeout(self):
        """Test recording timeout events."""
        monitor = AsyncPerformanceMonitor()

        start_time = monitor.record_operation_start("test_op")
        time.sleep(0.1)
        monitor.record_operation_timeout("test_op", start_time, 5.0, "Test timeout")

        metrics = monitor.get_operation_metrics("test_op")
        assert metrics.timeout_calls == 1

        timeout_events = monitor.get_recent_timeout_events(1)
        assert len(timeout_events) == 1
        assert timeout_events[0].operation == "test_op"
        assert timeout_events[0].expected_timeout == 5.0
        assert timeout_events[0].error_message == "Test timeout"

    def test_performance_alerts(self):
        """Test performance alert generation."""
        monitor = AsyncPerformanceMonitor()

        # Record some failures to trigger alerts
        for i in range(10):
            start_time = monitor.record_operation_start("failing_op")
            if i < 8:  # 80% failure rate
                monitor.record_operation_failure("failing_op", start_time)
            else:
                monitor.record_operation_success("failing_op", start_time)

        alerts = monitor.get_performance_alerts()
        assert len(alerts) > 0

        # Should have success rate alert
        success_rate_alerts = [a for a in alerts if a["type"] == "success_rate"]
        assert len(success_rate_alerts) > 0
        assert success_rate_alerts[0]["operation"] == "failing_op"

    def test_summary_stats(self):
        """Test summary statistics generation."""
        monitor = AsyncPerformanceMonitor()

        # Record some operations
        for i in range(5):
            start_time = monitor.record_operation_start("test_op")
            if i < 4:
                monitor.record_operation_success("test_op", start_time)
            else:
                monitor.record_operation_timeout("test_op", start_time, 1.0)

        stats = monitor.get_summary_stats()
        assert stats["total_operations"] == 5
        assert stats["total_successes"] == 4
        assert stats["total_timeouts"] == 1
        assert stats["overall_success_rate"] == 80.0
        assert stats["timeout_rate"] == 20.0
        assert stats["unique_operations"] == 1

    def test_global_performance_monitor(self):
        """Test global performance monitor."""
        monitor1 = get_performance_monitor()
        monitor2 = get_performance_monitor()

        # Should be same instance
        assert monitor1 is monitor2


class TestServiceWatchdog:
    """Test the ServiceWatchdog functionality."""

    @pytest.fixture
    def watchdog(self):
        """Create a test watchdog instance."""
        return ServiceWatchdog()

    @pytest.fixture
    def test_service_config(self):
        """Create a test service configuration."""
        return ServiceConfig(
            name="Test Service",
            command=["echo", "test"],
            startup_timeout=5.0,
            shutdown_timeout=3.0,
            max_restarts=2,
        )

    def test_watchdog_initialization(self, watchdog):
        """Test watchdog initialization."""
        assert not watchdog.is_running
        assert len(watchdog.services) == 0
        assert watchdog.monitor_task is None

    def test_add_service(self, watchdog, test_service_config):
        """Test adding a service to watchdog."""
        watchdog.add_service("test_service", test_service_config)

        assert "test_service" in watchdog.services
        assert watchdog.services["test_service"].config.name == "Test Service"
        assert watchdog.services["test_service"].state == ServiceState.STOPPED

    def test_remove_service(self, watchdog, test_service_config):
        """Test removing a service from watchdog."""
        watchdog.add_service("test_service", test_service_config)
        watchdog.remove_service("test_service")

        assert "test_service" not in watchdog.services

    def test_service_status_properties(self, test_service_config):
        """Test service status properties."""
        from crackerjack.core.service_watchdog import ServiceStatus

        status = ServiceStatus(config=test_service_config)

        # Initially not healthy
        assert not status.is_healthy
        assert status.uptime == 0.0

        # Set to running
        status.state = ServiceState.RUNNING
        status.last_start_time = time.time() - 10
        assert status.uptime > 9  # Should be around 10 seconds

    @pytest.mark.asyncio
    async def test_start_stop_watchdog(self, watchdog):
        """Test starting and stopping the watchdog."""
        # Start watchdog
        await watchdog.start_watchdog()
        assert watchdog.is_running
        assert watchdog.monitor_task is not None

        # Should have default services
        assert len(watchdog.services) > 0

        # Stop watchdog
        await watchdog.stop_watchdog()
        assert not watchdog.is_running

    def test_get_service_status(self, watchdog, test_service_config):
        """Test getting service status."""
        watchdog.add_service("test_service", test_service_config)

        status = watchdog.get_service_status("test_service")
        assert status is not None
        assert status.config.name == "Test Service"

        # Non-existent service
        status = watchdog.get_service_status("nonexistent")
        assert status is None

    def test_get_all_services_status(self, watchdog, test_service_config):
        """Test getting all services status."""
        watchdog.add_service("test_service", test_service_config)

        all_status = watchdog.get_all_services_status()
        assert "test_service" in all_status
        assert len(all_status) >= 1


class TestAsyncWorkflowIntegration:
    """Test integration of timeout system with async workflows."""

    @pytest.mark.asyncio
    async def test_workflow_with_timeouts(self):
        """Test that workflows use timeout protection."""
        from pathlib import Path

        from rich.console import Console

        from crackerjack.core.async_workflow_orchestrator import AsyncWorkflowPipeline
        from crackerjack.core.phase_coordinator import PhaseCoordinator
        from crackerjack.core.session_coordinator import SessionCoordinator

        # Create mock objects
        console = Console()
        pkg_path = Path.cwd()
        session = Mock(spec=SessionCoordinator)
        phases = Mock(spec=PhaseCoordinator)

        # Setup session mock
        session.initialize_session_tracking = Mock()
        session.track_task = Mock()
        session.finalize_session = Mock()
        session.cleanup_resources = Mock()
        session.fail_task = Mock()

        # Create pipeline with mocked dependencies
        logger = Mock()
        pipeline = AsyncWorkflowPipeline(logger, console, pkg_path, session, phases)

        # Verify timeout manager is available
        assert pipeline.timeout_manager is not None
        assert hasattr(pipeline.timeout_manager, "timeout_context")
        assert hasattr(pipeline.timeout_manager, "with_timeout")


@pytest.mark.asyncio
async def test_comprehensive_timeout_prevention():
    """Integration test to verify timeout prevention works end-to-end."""
    manager = AsyncTimeoutManager(TimeoutConfig(default_timeout=1.0))

    # Test that hanging operations are prevented
    start_time = time.time()

    async def hanging_task():
        await asyncio.sleep(10)  # Would hang for 10 seconds
        return "should not complete"

    with pytest.raises(TimeoutError):
        await manager.with_timeout(
            "hanging_prevention_test",
            hanging_task(),
            strategy=TimeoutStrategy.FAIL_FAST,
        )

    elapsed = time.time() - start_time

    # Should complete in around 1 second (timeout), not 10 seconds
    assert elapsed < 2.0, f"Operation took {elapsed:.2f}s, should have timed out in ~1s"

    # Verify metrics were recorded
    monitor = manager.performance_monitor
    metrics = monitor.get_operation_metrics("hanging_prevention_test")

    assert metrics is not None
    assert metrics.timeout_calls == 1
    assert metrics.total_calls == 1
    assert metrics.success_rate == 0.0


def test_timeout_system_components_available():
    """Test that all timeout system components are properly available."""
    # Verify imports work
    from crackerjack.core.performance_monitor import (
        AsyncPerformanceMonitor,
        get_performance_monitor,
    )
    from crackerjack.core.service_watchdog import ServiceWatchdog
    from crackerjack.core.timeout_manager import (
        AsyncTimeoutManager,
        get_timeout_manager,
    )

    # Verify classes can be instantiated
    timeout_manager = AsyncTimeoutManager()
    performance_monitor = AsyncPerformanceMonitor()
    service_watchdog = ServiceWatchdog()

    assert timeout_manager is not None
    assert performance_monitor is not None
    assert service_watchdog is not None

    # Verify global instances work
    global_timeout_manager = get_timeout_manager()
    global_performance_monitor = get_performance_monitor()

    assert global_timeout_manager is not None
    assert global_performance_monitor is not None
