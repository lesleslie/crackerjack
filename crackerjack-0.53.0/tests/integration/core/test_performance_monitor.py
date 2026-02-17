"""Tests for performance_monitor.py."""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from rich.console import Console

from crackerjack.core.performance_monitor import (
    AsyncPerformanceMonitor,
    OperationMetrics,
    TimeoutEvent,
    get_performance_monitor,
    reset_performance_monitor,
)


class TestOperationMetrics:
    """Test suite for OperationMetrics dataclass."""

    def test_initialization(self):
        """Test OperationMetrics initializes correctly."""
        metrics = OperationMetrics(operation_name="test_operation")
        assert metrics.operation_name == "test_operation"
        assert metrics.total_calls == 0
        assert metrics.successful_calls == 0
        assert metrics.failed_calls == 0
        assert metrics.timeout_calls == 0
        assert metrics.total_time == 0.0
        assert metrics.min_time == float("inf")
        assert metrics.max_time == 0.0
        assert len(metrics.recent_times) == 0

    def test_success_rate_no_calls(self):
        """Test success rate with no calls."""
        metrics = OperationMetrics(operation_name="test")
        assert metrics.success_rate == 0.0

    def test_success_rate_with_calls(self):
        """Test success rate calculation."""
        metrics = OperationMetrics(operation_name="test")
        metrics.total_calls = 10
        metrics.successful_calls = 8
        assert metrics.success_rate == 80.0

    def test_average_time_no_calls(self):
        """Test average time with no successful calls."""
        metrics = OperationMetrics(operation_name="test")
        assert metrics.average_time == 0.0

    def test_average_time_with_calls(self):
        """Test average time calculation."""
        metrics = OperationMetrics(operation_name="test")
        metrics.total_time = 10.0
        metrics.successful_calls = 5
        assert metrics.average_time == 2.0

    def test_recent_average_time_empty(self):
        """Test recent average time with no data."""
        metrics = OperationMetrics(operation_name="test")
        assert metrics.recent_average_time == 0.0

    def test_recent_average_time_with_data(self):
        """Test recent average time calculation."""
        metrics = OperationMetrics(operation_name="test")
        metrics.recent_times.extend([1.0, 2.0, 3.0])
        assert metrics.recent_average_time == 2.0


class TestTimeoutEvent:
    """Test suite for TimeoutEvent dataclass."""

    def test_initialization(self):
        """Test TimeoutEvent initializes correctly."""
        event = TimeoutEvent(
            operation="test_op",
            expected_timeout=30.0,
            actual_duration=35.0,
            timestamp=time.time(),
            error_message="Timeout exceeded",
        )
        assert event.operation == "test_op"
        assert event.expected_timeout == 30.0
        assert event.actual_duration == 35.0
        assert event.error_message == "Timeout exceeded"


class TestAsyncPerformanceMonitor:
    """Test suite for AsyncPerformanceMonitor."""

    @pytest.fixture
    def monitor(self):
        """Create monitor instance for testing."""
        return AsyncPerformanceMonitor()

    def test_initialization(self, monitor):
        """Test monitor initializes with correct defaults."""
        assert len(monitor.metrics) == 0
        assert len(monitor.timeout_events) == 0
        assert monitor.start_time > 0
        assert len(monitor.circuit_breaker_events) == 0
        assert "default" in monitor.performance_thresholds
        assert "fast_hooks" in monitor.performance_thresholds

    def test_performance_thresholds_defaults(self, monitor):
        """Test default performance thresholds are set."""
        defaults = monitor.performance_thresholds["default"]
        assert "warning_time" in defaults
        assert "critical_time" in defaults
        assert "min_success_rate" in defaults
        assert defaults["warning_time"] == 30.0
        assert defaults["critical_time"] == 60.0
        assert defaults["min_success_rate"] == 80.0

    def test_performance_thresholds_custom(self, monitor):
        """Test custom thresholds for specific operations."""
        fast_hooks = monitor.performance_thresholds["fast_hooks"]
        assert fast_hooks["warning_time"] == 30.0
        assert fast_hooks["critical_time"] == 90.0
        assert fast_hooks["min_success_rate"] == 95.0

    def test_record_operation_start(self, monitor):
        """Test recording operation start time."""
        start = monitor.record_operation_start("test_op")
        assert start > 0
        assert isinstance(start, float)

    def test_record_operation_success(self, monitor):
        """Test recording successful operation."""
        start_time = time.time()
        monitor.record_operation_success("test_op", start_time)

        metrics = monitor.get_operation_metrics("test_op")
        assert metrics is not None
        assert metrics.total_calls == 1
        assert metrics.successful_calls == 1
        assert metrics.failed_calls == 0
        assert metrics.total_time > 0

    def test_record_operation_failure(self, monitor):
        """Test recording failed operation."""
        start_time = time.time()
        monitor.record_operation_failure("test_op", start_time)

        metrics = monitor.get_operation_metrics("test_op")
        assert metrics is not None
        assert metrics.total_calls == 1
        assert metrics.successful_calls == 0
        assert metrics.failed_calls == 1

    def test_record_operation_timeout(self, monitor):
        """Test recording timeout event."""
        start_time = time.time()
        monitor.record_operation_timeout("test_op", start_time, 30.0, "Timeout error")

        metrics = monitor.get_operation_metrics("test_op")
        assert metrics is not None
        assert metrics.timeout_calls == 1

        timeouts = monitor.get_recent_timeout_events()
        assert len(timeouts) == 1
        assert timeouts[0].operation == "test_op"

    def test_get_operation_metrics_existing(self, monitor):
        """Test getting metrics for existing operation."""
        start_time = time.time()
        monitor.record_operation_success("test_op", start_time)

        metrics = monitor.get_operation_metrics("test_op")
        assert metrics is not None
        assert metrics.operation_name == "test_op"

    def test_get_operation_metrics_nonexistent(self, monitor):
        """Test getting metrics for non-existent operation."""
        metrics = monitor.get_operation_metrics("nonexistent")
        assert metrics is None

    def test_get_all_metrics(self, monitor):
        """Test getting all metrics."""
        start_time = time.time()
        monitor.record_operation_success("op1", start_time)
        monitor.record_operation_success("op2", start_time)

        all_metrics = monitor.get_all_metrics()
        assert len(all_metrics) == 2
        assert "op1" in all_metrics
        assert "op2" in all_metrics

    def test_get_recent_timeout_events_default_limit(self, monitor):
        """Test getting recent timeout events with default limit."""
        start_time = time.time()
        for i in range(15):
            monitor.record_operation_timeout(f"op{i}", start_time, 30.0)

        recent = monitor.get_recent_timeout_events()
        assert len(recent) == 10  # Default limit

    def test_get_recent_timeout_events_custom_limit(self, monitor):
        """Test getting recent timeout events with custom limit."""
        start_time = time.time()
        for i in range(15):
            monitor.record_operation_timeout(f"op{i}", start_time, 30.0)

        recent = monitor.get_recent_timeout_events(limit=5)
        assert len(recent) == 5

    def test_get_performance_alerts_success_rate_warning(self, monitor):
        """Test alert for low success rate (warning)."""
        start_time = time.time()
        # Record 10 calls with 7 successes (70% rate, below 80% threshold)
        for _ in range(7):
            monitor.record_operation_success("test_op", start_time)
        for _ in range(3):
            monitor.record_operation_failure("test_op", start_time)

        alerts = monitor.get_performance_alerts()
        assert len(alerts) > 0
        success_rate_alerts = [a for a in alerts if a["type"] == "success_rate"]
        assert len(success_rate_alerts) > 0
        assert success_rate_alerts[0]["severity"] == "warning"

    def test_get_performance_alerts_success_rate_critical(self, monitor):
        """Test alert for very low success rate (critical)."""
        start_time = time.time()
        # Record 10 calls with 4 successes (40% rate, below 50% threshold)
        for _ in range(4):
            monitor.record_operation_success("test_op", start_time)
        for _ in range(6):
            monitor.record_operation_failure("test_op", start_time)

        alerts = monitor.get_performance_alerts()
        success_rate_alerts = [a for a in alerts if a["type"] == "success_rate"]
        assert len(success_rate_alerts) > 0
        assert success_rate_alerts[0]["severity"] == "critical"

    def test_get_performance_alerts_response_time_warning(self, monitor):
        """Test alert for slow response time (warning)."""
        start_time = time.time()
        # Record operation that took 40 seconds (above 30s warning threshold)
        monitor.record_operation_success("test_op", start_time - 40)

        alerts = monitor.get_performance_alerts()
        response_time_alerts = [a for a in alerts if a["type"] == "response_time"]
        assert len(response_time_alerts) > 0
        assert response_time_alerts[0]["severity"] == "warning"

    def test_get_performance_alerts_response_time_critical(self, monitor):
        """Test alert for very slow response time (critical)."""
        start_time = time.time()
        # Record operation that took 70 seconds (above 60s critical threshold)
        monitor.record_operation_success("test_op", start_time - 70)

        alerts = monitor.get_performance_alerts()
        response_time_alerts = [a for a in alerts if a["type"] == "response_time"]
        assert len(response_time_alerts) > 0
        assert response_time_alerts[0]["severity"] == "critical"

    def test_get_performance_alerts_no_alerts(self, monitor):
        """Test no alerts when performance is good."""
        start_time = time.time()
        # Record fast, successful operations
        for _ in range(10):
            monitor.record_operation_success("test_op", start_time)

        alerts = monitor.get_performance_alerts()
        assert len(alerts) == 0

    def test_get_summary_stats(self, monitor):
        """Test summary statistics calculation."""
        start_time = time.time()
        monitor.record_operation_success("op1", start_time)
        monitor.record_operation_success("op1", start_time)
        monitor.record_operation_failure("op1", start_time)
        monitor.record_operation_timeout("op2", start_time, 30.0)

        stats = monitor.get_summary_stats()
        assert stats["total_operations"] == 4
        assert stats["total_successes"] == 2
        assert stats["total_failures"] == 1
        assert stats["total_timeouts"] == 1
        assert stats["unique_operations"] == 2
        assert stats["overall_success_rate"] == 50.0
        assert stats["uptime_seconds"] > 0

    def test_get_summary_stats_no_operations(self, monitor):
        """Test summary stats with no operations."""
        stats = monitor.get_summary_stats()
        assert stats["total_operations"] == 0
        assert stats["total_successes"] == 0
        assert stats["overall_success_rate"] == 0.0

    def test_export_metrics_json(self, monitor, tmp_path):
        """Test JSON export functionality."""
        start_time = time.time()
        monitor.record_operation_success("test_op", start_time)
        monitor.record_operation_timeout("test_op", start_time, 30.0)

        filepath = tmp_path / "metrics.json"
        monitor.export_metrics_json(filepath)

        assert filepath.exists()
        data = json.loads(filepath.read_text())
        assert "summary" in data
        assert "operations" in data
        assert "recent_timeout_events" in data
        assert "performance_alerts" in data

    def test_export_metrics_json_file_creation(self, monitor, tmp_path):
        """Test JSON export creates file."""
        filepath = tmp_path / "test_metrics.json"
        monitor.export_metrics_json(filepath)
        assert filepath.is_file()

    def test_print_performance_report(self, monitor, capsys):
        """Test performance report generation."""
        start_time = time.time()
        monitor.record_operation_success("test_op", start_time)

        console = Console(force_terminal=False)
        monitor.print_performance_report(console)
        # Just verify it doesn't crash - actual output testing is complex

    def test_print_performance_report_with_alerts(self, monitor):
        """Test report with performance alerts."""
        start_time = time.time()
        # Record slow operation to trigger alert
        monitor.record_operation_success("test_op", start_time - 70)

        console = Console(force_terminal=False)
        monitor.print_performance_report(console)
        # Verify no crashes

    def test_print_performance_report_with_timeouts(self, monitor):
        """Test report with timeout events."""
        start_time = time.time()
        monitor.record_operation_timeout("test_op", start_time, 30.0)

        console = Console(force_terminal=False)
        monitor.print_performance_report(console)
        # Verify no crashes

    def test_record_circuit_breaker_event(self, monitor):
        """Test circuit breaker event recording."""
        monitor.record_circuit_breaker_event("test_op", opened=True)
        assert "test_op" in monitor.circuit_breaker_events
        assert len(monitor.circuit_breaker_events["test_op"]) == 1

    def test_circuit_breaker_event_not_opened(self, monitor):
        """Test circuit breaker event not recorded when not opened."""
        monitor.record_circuit_breaker_event("test_op", opened=False)
        assert "test_op" not in monitor.circuit_breaker_events or len(
            monitor.circuit_breaker_events["test_op"]
        ) == 0

    def test_recent_times_maxlen(self, monitor):
        """Test recent_times deque enforces max length."""
        start_time = time.time()
        # Record more than 100 operations
        for i in range(150):
            monitor.record_operation_success("test_op", start_time + i * 0.01)

        metrics = monitor.get_operation_metrics("test_op")
        assert len(metrics.recent_times) <= 100

    def test_thread_safety_metrics_recording(self, monitor):
        """Test concurrent access to metrics is thread-safe."""
        import threading

        start_time = time.time()
        threads = []

        def record_operations():
            for _ in range(50):
                monitor.record_operation_success("test_op", start_time)

        for _ in range(4):
            thread = threading.Thread(target=record_operations)
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        metrics = monitor.get_operation_metrics("test_op")
        assert metrics.total_calls == 200


class TestGlobalPerformanceMonitor:
    """Test suite for global performance monitor functions."""

    def test_get_performance_monitor_singleton(self):
        """Test global monitor is a singleton."""
        monitor1 = get_performance_monitor()
        monitor2 = get_performance_monitor()
        assert monitor1 is monitor2

    def test_reset_performance_monitor(self):
        """Test reset functionality creates new instance."""
        monitor1 = get_performance_monitor()
        monitor1.record_operation_success("test", time.time())

        reset_performance_monitor()
        monitor2 = get_performance_monitor()

        assert monitor1 is not monitor2
        assert monitor2.get_operation_metrics("test") is None
