import json
import logging
import time
import typing as t
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from threading import Lock

from acb.console import Console
from acb.depends import depends
from rich.panel import Panel
from rich.table import Table

logger = logging.getLogger("crackerjack.performance_monitor")


@dataclass
class OperationMetrics:
    operation_name: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    timeout_calls: int = 0
    total_time: float = 0.0
    min_time: float = float("inf")
    max_time: float = 0.0
    recent_times: deque[float] = field(default_factory=lambda: deque(maxlen=100))

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return (self.successful_calls / self.total_calls) * 100

    @property
    def average_time(self) -> float:
        if self.successful_calls == 0:
            return 0.0
        return self.total_time / self.successful_calls

    @property
    def recent_average_time(self) -> float:
        if not self.recent_times:
            return 0.0
        return sum(self.recent_times) / len(self.recent_times)


@dataclass
class TimeoutEvent:
    operation: str
    expected_timeout: float
    actual_duration: float
    timestamp: float
    error_message: str = ""


class AsyncPerformanceMonitor:
    def __init__(self, max_timeout_events: int = 1000) -> None:
        self.metrics: dict[str, OperationMetrics] = {}
        self.timeout_events: deque[TimeoutEvent] = deque(maxlen=max_timeout_events)
        self._lock = Lock()
        self.start_time = time.time()

        self.circuit_breaker_events: dict[str, list[float]] = defaultdict(list)

        self.performance_thresholds: dict[str, dict[str, float]] = {
            "default": {
                "warning_time": 30.0,
                "critical_time": 60.0,
                "min_success_rate": 80.0,
            },
            "fast_hooks": {
                "warning_time": 30.0,
                "critical_time": 90.0,
                "min_success_rate": 95.0,
            },
            "comprehensive_hooks": {
                "warning_time": 120.0,
                "critical_time": 300.0,
                "min_success_rate": 90.0,
            },
            "test_execution": {
                "warning_time": 300.0,
                "critical_time": 600.0,
                "min_success_rate": 85.0,
            },
            "ai_agent_processing": {
                "warning_time": 60.0,
                "critical_time": 180.0,
                "min_success_rate": 75.0,
            },
            "network_operations": {
                "warning_time": 5.0,
                "critical_time": 15.0,
                "min_success_rate": 95.0,
            },
            "file_operations": {
                "warning_time": 3.0,
                "critical_time": 10.0,
                "min_success_rate": 98.0,
            },
        }

    def record_operation_start(self, operation: str) -> float:
        return time.time()

    def record_operation_success(self, operation: str, start_time: float) -> None:
        duration = time.time() - start_time

        with self._lock:
            if operation not in self.metrics:
                self.metrics[operation] = OperationMetrics(operation)

            metrics = self.metrics[operation]
            metrics.total_calls += 1
            metrics.successful_calls += 1
            metrics.total_time += duration
            metrics.min_time = min(metrics.min_time, duration)
            metrics.max_time = max(metrics.max_time, duration)
            metrics.recent_times.append(duration)

    def record_operation_failure(self, operation: str, start_time: float) -> None:
        duration = time.time() - start_time

        with self._lock:
            if operation not in self.metrics:
                self.metrics[operation] = OperationMetrics(operation)

            metrics = self.metrics[operation]
            metrics.total_calls += 1
            metrics.failed_calls += 1
            metrics.total_time += duration
            metrics.min_time = min(metrics.min_time, duration)
            metrics.max_time = max(metrics.max_time, duration)
            metrics.recent_times.append(duration)

    def record_operation_timeout(
        self,
        operation: str,
        start_time: float,
        expected_timeout: float,
        error_message: str = "",
    ) -> None:
        duration = time.time() - start_time

        with self._lock:
            if operation not in self.metrics:
                self.metrics[operation] = OperationMetrics(operation)

            metrics = self.metrics[operation]
            metrics.total_calls += 1
            metrics.timeout_calls += 1

            timeout_event = TimeoutEvent(
                operation=operation,
                expected_timeout=expected_timeout,
                actual_duration=duration,
                timestamp=time.time(),
                error_message=error_message,
            )
            self.timeout_events.append(timeout_event)

    def record_circuit_breaker_event(self, operation: str, opened: bool) -> None:
        with self._lock:
            if opened:
                self.circuit_breaker_events[operation].append(time.time())

    def get_operation_metrics(self, operation: str) -> OperationMetrics | None:
        with self._lock:
            return self.metrics.get(operation)

    def get_all_metrics(self) -> dict[str, OperationMetrics]:
        with self._lock:
            return self.metrics.copy()

    def get_recent_timeout_events(self, limit: int = 10) -> list[TimeoutEvent]:
        with self._lock:
            return list[t.Any](self.timeout_events)[-limit:]

    def get_performance_alerts(self) -> list[dict[str, t.Any]]:
        alerts = []

        with self._lock:
            for operation, metrics in self.metrics.items():
                thresholds = self.performance_thresholds.get(
                    operation, self.performance_thresholds["default"]
                )

                if metrics.success_rate < thresholds["min_success_rate"]:
                    alerts.append(
                        {
                            "type": "success_rate",
                            "operation": operation,
                            "current_value": metrics.success_rate,
                            "threshold": thresholds["min_success_rate"],
                            "severity": "critical"
                            if metrics.success_rate < 50
                            else "warning",
                        }
                    )

                avg_time = metrics.recent_average_time
                if avg_time > thresholds["critical_time"]:
                    alerts.append(
                        {
                            "type": "response_time",
                            "operation": operation,
                            "current_value": avg_time,
                            "threshold": thresholds["critical_time"],
                            "severity": "critical",
                        }
                    )
                elif avg_time > thresholds["warning_time"]:
                    alerts.append(
                        {
                            "type": "response_time",
                            "operation": operation,
                            "current_value": avg_time,
                            "threshold": thresholds["warning_time"],
                            "severity": "warning",
                        }
                    )

        return alerts

    def get_summary_stats(self) -> dict[str, t.Any]:
        with self._lock:
            total_calls = sum(m.total_calls for m in self.metrics.values())
            total_successes = sum(m.successful_calls for m in self.metrics.values())
            total_timeouts = sum(m.timeout_calls for m in self.metrics.values())
            total_failures = sum(m.failed_calls for m in self.metrics.values())

            uptime = time.time() - self.start_time

            return {
                "uptime_seconds": uptime,
                "total_operations": total_calls,
                "total_successes": total_successes,
                "total_timeouts": total_timeouts,
                "total_failures": total_failures,
                "overall_success_rate": (total_successes / total_calls * 100)
                if total_calls > 0
                else 0.0,
                "timeout_rate": (total_timeouts / total_calls * 100)
                if total_calls > 0
                else 0.0,
                "operations_per_minute": (total_calls / (uptime / 60))
                if uptime > 0
                else 0.0,
                "unique_operations": len(self.metrics),
                "circuit_breaker_trips": len(self.circuit_breaker_events),
            }

    def export_metrics_json(self, filepath: Path) -> None:
        with self._lock:
            data = {
                "summary": self.get_summary_stats(),
                "operations": {
                    name: {
                        "total_calls": m.total_calls,
                        "successful_calls": m.successful_calls,
                        "failed_calls": m.failed_calls,
                        "timeout_calls": m.timeout_calls,
                        "success_rate": m.success_rate,
                        "average_time": m.average_time,
                        "recent_average_time": m.recent_average_time,
                        "min_time": m.min_time if m.min_time != float("inf") else 0,
                        "max_time": m.max_time,
                    }
                    for name, m in self.metrics.items()
                },
                "recent_timeout_events": [
                    {
                        "operation": event.operation,
                        "expected_timeout": event.expected_timeout,
                        "actual_duration": event.actual_duration,
                        "timestamp": event.timestamp,
                        "error_message": event.error_message,
                    }
                    for event in list[t.Any](self.timeout_events)[-50:]
                ],
                "performance_alerts": self.get_performance_alerts(),
            }

        filepath.write_text(json.dumps(data, indent=2))

    def print_performance_report(self, console: Console | None = None) -> None:
        if console is None:
            console = depends.get_sync(Console)

        console.print("\n[bold blue]🔍 Async Performance Monitor Report[/bold blue]")
        console.print("=" * 60)

        summary = self.get_summary_stats()
        console.print(f"⏱️ Uptime: {summary['uptime_seconds']: .1f}s")
        console.print(f"📊 Total Operations: {summary['total_operations']}")
        console.print(f"✅ Success Rate: {summary['overall_success_rate']: .1f}%")
        console.print(f"⏰ Timeout Rate: {summary['timeout_rate']: .1f}%")
        console.print(f"🚀 Operations/min: {summary['operations_per_minute']: .1f}")

        if self.metrics:
            console.print("\n[bold]Operation Metrics: [/bold]")
            table = Table()
            table.add_column("Operation")
            table.add_column("Calls")
            table.add_column("Success %")
            table.add_column("Avg Time")
            table.add_column("Recent Avg")
            table.add_column("Timeouts")

            with self._lock:
                for name, metrics in sorted(self.metrics.items()):
                    table.add_row(
                        name,
                        str(metrics.total_calls),
                        f"{metrics.success_rate: .1f}%",
                        f"{metrics.average_time: .2f}s",
                        f"{metrics.recent_average_time: .2f}s",
                        str(metrics.timeout_calls),
                    )

            console.print(Panel(table, title="Operation Metrics", border_style="cyan"))

        alerts = self.get_performance_alerts()
        if alerts:
            console.print("\n[bold red]⚠️ Performance Alerts: [/bold red]")
            for alert in alerts:
                severity_emoji = "🔴" if alert["severity"] == "critical" else "🟡"
                console.print(
                    f"{severity_emoji} {alert['operation']}: {alert['type']} "
                    f"{alert['current_value']: .1f} (threshold: {alert['threshold']: .1f})"
                )

        recent_timeouts = self.get_recent_timeout_events(5)
        if recent_timeouts:
            console.print("\n[bold yellow]⏰ Recent Timeouts: [/bold yellow]")
            for timeout in recent_timeouts:
                console.print(
                    f" • {timeout.operation}: {timeout.actual_duration: .1f}s "
                    f"(expected: {timeout.expected_timeout: .1f}s)"
                )


_global_performance_monitor: AsyncPerformanceMonitor | None = None


def get_performance_monitor() -> AsyncPerformanceMonitor:
    global _global_performance_monitor
    if _global_performance_monitor is None:
        _global_performance_monitor = AsyncPerformanceMonitor()
    return _global_performance_monitor


def reset_performance_monitor() -> None:
    global _global_performance_monitor
    _global_performance_monitor = AsyncPerformanceMonitor()
