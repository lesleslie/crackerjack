"""Tests for health_check module."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch
from typing import Any

import pytest

from crackerjack.models.enums import HealthStatus
from crackerjack.models.health_check import (
    ComponentHealth,
    HealthCheckProtocol,
    HealthCheckResult,
    SystemHealthReport,
    health_check_wrapper,
)


class TestHealthCheckResult:
    """Tests for HealthCheckResult dataclass."""

    def test_minimal_healthy_result(self) -> None:
        """Verify minimal healthy result creation."""
        result = HealthCheckResult(
            status=HealthStatus.HEALTHY,
            message="OK",
        )
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "OK"
        assert result.details == {}
        assert result.component_name == ""
        assert result.check_duration_ms is None

    def test_full_result_creation(self) -> None:
        """Verify result with all fields."""
        now = datetime.now(UTC)
        details = {"cpu": 50}
        result = HealthCheckResult(
            status=HealthStatus.DEGRADED,
            message="CPU high",
            details=details,
            timestamp=now,
            component_name="cpu-monitor",
            check_duration_ms=15.5,
        )
        assert result.status == HealthStatus.DEGRADED
        assert result.message == "CPU high"
        assert result.details == details
        assert result.timestamp == now
        assert result.component_name == "cpu-monitor"
        assert result.check_duration_ms == 15.5

    def test_healthy_factory_method(self) -> None:
        """Verify healthy() class method."""
        result = HealthCheckResult.healthy(
            message="All systems nominal",
            component_name="system",
            details={"uptime": 3600},
            check_duration_ms=5.0,
        )
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "All systems nominal"
        assert result.component_name == "system"
        assert result.details == {"uptime": 3600}
        assert result.check_duration_ms == 5.0

    def test_healthy_factory_defaults(self) -> None:
        """Verify healthy() default message."""
        result = HealthCheckResult.healthy()
        assert result.status == HealthStatus.HEALTHY
        assert result.message == "Component is healthy"
        assert result.component_name == ""
        assert result.details == {}

    def test_degraded_factory_method(self) -> None:
        """Verify degraded() class method."""
        result = HealthCheckResult.degraded(
            message="Response time elevated",
            component_name="api",
            details={"response_time_ms": 800},
        )
        assert result.status == HealthStatus.DEGRADED
        assert result.message == "Response time elevated"
        assert result.component_name == "api"
        assert result.details == {"response_time_ms": 800}

    def test_unhealthy_factory_method(self) -> None:
        """Verify unhealthy() class method."""
        result = HealthCheckResult.unhealthy(
            message="Database unavailable",
            component_name="database",
            details={"error": "connection timeout"},
        )
        assert result.status == HealthStatus.UNHEALTHY
        assert result.message == "Database unavailable"
        assert result.component_name == "database"
        assert result.details == {"error": "connection timeout"}

    def test_to_dict(self) -> None:
        """Verify to_dict serialization."""
        now = datetime.now(UTC)
        result = HealthCheckResult(
            status=HealthStatus.HEALTHY,
            message="OK",
            details={"value": 42},
            timestamp=now,
            component_name="test",
            check_duration_ms=10.5,
        )
        data = result.to_dict()

        assert data["status"] == "healthy"
        assert data["message"] == "OK"
        assert data["details"] == {"value": 42}
        assert data["timestamp"] == now.isoformat()
        assert data["component_name"] == "test"
        assert data["check_duration_ms"] == 10.5

    def test_exit_code_healthy(self) -> None:
        """Verify exit_code for healthy status."""
        result = HealthCheckResult.healthy()
        assert result.exit_code == 0

    def test_exit_code_degraded(self) -> None:
        """Verify exit_code for degraded status."""
        result = HealthCheckResult.degraded("Degraded")
        assert result.exit_code == 1

    def test_exit_code_unhealthy(self) -> None:
        """Verify exit_code for unhealthy status."""
        result = HealthCheckResult.unhealthy("Unhealthy")
        assert result.exit_code == 2

    def test_frozen_dataclass(self) -> None:
        """Verify result is immutable."""
        result = HealthCheckResult.healthy()
        with pytest.raises(AttributeError):
            result.message = "modified"


class TestComponentHealth:
    """Tests for ComponentHealth dataclass."""

    def test_minimal_component_health(self) -> None:
        """Verify minimal ComponentHealth creation."""
        health = ComponentHealth(
            category="database",
            overall_status=HealthStatus.HEALTHY,
            total=5,
            healthy=5,
            degraded=0,
            unhealthy=0,
        )
        assert health.category == "database"
        assert health.overall_status == HealthStatus.HEALTHY
        assert health.total == 5
        assert health.healthy == 5
        assert health.degraded == 0
        assert health.unhealthy == 0
        assert health.components == {}

    def test_from_results_all_healthy(self) -> None:
        """Verify from_results with all healthy components."""
        results = {
            "primary": HealthCheckResult.healthy("Primary DB OK"),
            "replica": HealthCheckResult.healthy("Replica OK"),
        }
        health = ComponentHealth.from_results("database", results)

        assert health.category == "database"
        assert health.total == 2
        assert health.healthy == 2
        assert health.degraded == 0
        assert health.unhealthy == 0
        assert health.overall_status == HealthStatus.HEALTHY

    def test_from_results_mixed_statuses(self) -> None:
        """Verify from_results with mixed statuses."""
        results = {
            "primary": HealthCheckResult.healthy("Primary OK"),
            "replica": HealthCheckResult.degraded("Replica slow"),
            "cache": HealthCheckResult.unhealthy("Cache down"),
        }
        health = ComponentHealth.from_results("services", results)

        assert health.total == 3
        assert health.healthy == 1
        assert health.degraded == 1
        assert health.unhealthy == 1
        assert health.overall_status == HealthStatus.UNHEALTHY

    def test_from_results_rollup_logic(self) -> None:
        """Verify from_results status rollup priorities."""
        # Unhealthy takes precedence
        results_unhealthy = {
            "a": HealthCheckResult.degraded("Degraded"),
            "b": HealthCheckResult.unhealthy("Unhealthy"),
        }
        assert (
            ComponentHealth.from_results("test", results_unhealthy).overall_status
            == HealthStatus.UNHEALTHY
        )

        # Degraded takes precedence over healthy
        results_degraded = {
            "a": HealthCheckResult.healthy("OK"),
            "b": HealthCheckResult.degraded("Degraded"),
        }
        assert (
            ComponentHealth.from_results("test", results_degraded).overall_status
            == HealthStatus.DEGRADED
        )

        # All healthy when no issues
        results_healthy = {
            "a": HealthCheckResult.healthy("OK"),
            "b": HealthCheckResult.healthy("OK"),
        }
        assert (
            ComponentHealth.from_results("test", results_healthy).overall_status
            == HealthStatus.HEALTHY
        )

    def test_from_results_empty(self) -> None:
        """Verify from_results with no components."""
        health = ComponentHealth.from_results("test", {})

        assert health.total == 0
        assert health.healthy == 0
        assert health.degraded == 0
        assert health.unhealthy == 0
        assert health.overall_status == HealthStatus.HEALTHY

    def test_to_dict(self) -> None:
        """Verify to_dict serialization."""
        results = {
            "primary": HealthCheckResult.healthy("OK", details={"version": "14"}),
            "replica": HealthCheckResult.degraded("Slow"),
        }
        health = ComponentHealth.from_results("db", results)
        data = health.to_dict()

        assert data["category"] == "db"
        assert data["overall_status"] == "degraded"
        assert data["total"] == 2
        assert data["healthy"] == 1
        assert data["degraded"] == 1
        assert data["unhealthy"] == 0
        assert "primary" in data["components"]
        assert "replica" in data["components"]
        assert data["components"]["primary"]["status"] == "healthy"
        assert data["components"]["replica"]["status"] == "degraded"

    def test_exit_code_healthy(self) -> None:
        """Verify exit_code for healthy component."""
        health = ComponentHealth(
            category="test",
            overall_status=HealthStatus.HEALTHY,
            total=1,
            healthy=1,
            degraded=0,
            unhealthy=0,
        )
        assert health.exit_code == 0

    def test_exit_code_degraded(self) -> None:
        """Verify exit_code for degraded component."""
        health = ComponentHealth(
            category="test",
            overall_status=HealthStatus.DEGRADED,
            total=2,
            healthy=1,
            degraded=1,
            unhealthy=0,
        )
        assert health.exit_code == 1

    def test_exit_code_unhealthy(self) -> None:
        """Verify exit_code for unhealthy component."""
        health = ComponentHealth(
            category="test",
            overall_status=HealthStatus.UNHEALTHY,
            total=1,
            healthy=0,
            degraded=0,
            unhealthy=1,
        )
        assert health.exit_code == 2


class TestSystemHealthReport:
    """Tests for SystemHealthReport dataclass."""

    def test_minimal_report(self) -> None:
        """Verify minimal SystemHealthReport creation."""
        report = SystemHealthReport(overall_status=HealthStatus.HEALTHY)
        assert report.overall_status == HealthStatus.HEALTHY
        assert report.categories == {}
        assert report.summary == ""
        assert report.metadata == {}

    def test_from_category_health_all_healthy(self) -> None:
        """Verify from_category_health with all healthy categories."""
        db_results = {
            "primary": HealthCheckResult.healthy("OK"),
            "replica": HealthCheckResult.healthy("OK"),
        }
        api_results = {
            "main": HealthCheckResult.healthy("OK"),
        }
        categories = {
            "database": ComponentHealth.from_results("database", db_results),
            "api": ComponentHealth.from_results("api", api_results),
        }
        report = SystemHealthReport.from_category_health(categories)

        assert report.overall_status == HealthStatus.HEALTHY
        assert report.summary == "All 3 components healthy"
        assert len(report.categories) == 2

    def test_from_category_health_mixed_categories(self) -> None:
        """Verify from_category_health with mixed category statuses."""
        db_results = {
            "primary": HealthCheckResult.healthy("OK"),
            "replica": HealthCheckResult.degraded("Slow"),
        }
        api_results = {
            "main": HealthCheckResult.unhealthy("Down"),
        }
        categories = {
            "database": ComponentHealth.from_results("database", db_results),
            "api": ComponentHealth.from_results("api", api_results),
        }
        report = SystemHealthReport.from_category_health(categories)

        assert report.overall_status == HealthStatus.UNHEALTHY
        assert "1 healthy" in report.summary
        assert "1 degraded" in report.summary
        assert "1 unhealthy" in report.summary

    def test_from_category_health_only_degraded(self) -> None:
        """Verify from_category_health with only degraded (no unhealthy)."""
        cat1_results = {"a": HealthCheckResult.healthy("OK")}
        cat2_results = {"b": HealthCheckResult.degraded("Slow")}
        categories = {
            "cat1": ComponentHealth.from_results("cat1", cat1_results),
            "cat2": ComponentHealth.from_results("cat2", cat2_results),
        }
        report = SystemHealthReport.from_category_health(categories)

        assert report.overall_status == HealthStatus.DEGRADED
        assert "1 healthy" in report.summary
        assert "1 degraded" in report.summary

    def test_from_category_health_summary_generation(self) -> None:
        """Verify summary text generation."""
        # Single healthy component
        results = {"a": HealthCheckResult.healthy()}
        categories = {"cat": ComponentHealth.from_results("cat", results)}
        report = SystemHealthReport.from_category_health(categories)
        assert report.summary == "All 1 components healthy"

        # Mixed components
        results = {
            "a": HealthCheckResult.healthy(),
            "b": HealthCheckResult.degraded("Slow"),
            "c": HealthCheckResult.unhealthy("Down"),
        }
        categories = {"cat": ComponentHealth.from_results("cat", results)}
        report = SystemHealthReport.from_category_health(categories)
        assert report.summary == "1 healthy, 1 degraded, 1 unhealthy"

        # No components - all healthy (0 == 0)
        report = SystemHealthReport.from_category_health({})
        assert report.summary == "All 0 components healthy"

    def test_from_category_health_with_metadata(self) -> None:
        """Verify from_category_health with metadata."""
        metadata = {"version": "1.0", "region": "us-east"}
        report = SystemHealthReport.from_category_health({}, metadata=metadata)
        assert report.metadata == metadata

    def test_to_dict(self) -> None:
        """Verify to_dict serialization."""
        db_results = {
            "primary": HealthCheckResult.healthy("OK", details={"version": "14"}),
        }
        categories = {
            "database": ComponentHealth.from_results("database", db_results),
        }
        report = SystemHealthReport.from_category_health(
            categories, metadata={"env": "prod"}
        )
        data = report.to_dict()

        assert data["overall_status"] == "healthy"
        assert "database" in data["categories"]
        assert data["metadata"] == {"env": "prod"}
        assert "summary" in data
        assert "timestamp" in data

    def test_exit_code_healthy(self) -> None:
        """Verify exit_code for healthy report."""
        report = SystemHealthReport(overall_status=HealthStatus.HEALTHY)
        assert report.exit_code == 0

    def test_exit_code_degraded(self) -> None:
        """Verify exit_code for degraded report."""
        report = SystemHealthReport(overall_status=HealthStatus.DEGRADED)
        assert report.exit_code == 1

    def test_exit_code_unhealthy(self) -> None:
        """Verify exit_code for unhealthy report."""
        report = SystemHealthReport(overall_status=HealthStatus.UNHEALTHY)
        assert report.exit_code == 2


class TestHealthCheckWrapper:
    """Tests for health_check_wrapper function."""

    def test_wrapper_successful_check(self) -> None:
        """Verify wrapper with successful health check."""
        check_result = HealthCheckResult.healthy("OK")
        mock_check = MagicMock(return_value=check_result)

        result = health_check_wrapper("test-component", mock_check)

        assert result.status == HealthStatus.HEALTHY
        assert result.message == "OK"
        assert result.component_name == "test-component"
        mock_check.assert_called_once()

    def test_wrapper_sets_component_name_if_missing(self) -> None:
        """Verify wrapper sets component_name if result doesn't have it."""
        check_result = HealthCheckResult.healthy("OK")
        mock_check = MagicMock(return_value=check_result)

        result = health_check_wrapper("my-component", mock_check)

        assert result.component_name == "my-component"

    def test_wrapper_preserves_component_name_if_set(self) -> None:
        """Verify wrapper preserves existing component_name."""
        check_result = HealthCheckResult.healthy("OK", component_name="original")
        mock_check = MagicMock(return_value=check_result)

        result = health_check_wrapper("new-name", mock_check)

        assert result.component_name == "original"

    def test_wrapper_handles_none_return(self) -> None:
        """Verify wrapper handles None return from check function."""
        mock_check = MagicMock(return_value=None)

        result = health_check_wrapper("test-component", mock_check)

        assert result.status == HealthStatus.UNHEALTHY
        assert "returned None" in result.message
        assert result.component_name == "test-component"
        assert "suggestion" in result.details

    def test_wrapper_handles_exception(self) -> None:
        """Verify wrapper handles exception from check function."""
        test_exception = ValueError("Connection failed")
        mock_check = MagicMock(side_effect=test_exception)

        result = health_check_wrapper("test-component", mock_check)

        assert result.status == HealthStatus.UNHEALTHY
        assert "exception" in result.message
        assert result.component_name == "test-component"
        assert result.details["error_type"] == "ValueError"
        assert "Connection failed" in result.details["error_message"]

    def test_wrapper_measures_duration_on_exception(self) -> None:
        """Verify wrapper measures duration when exception occurs."""
        import time

        def slow_failing_check() -> HealthCheckResult:
            time.sleep(0.01)
            raise RuntimeError("Check failed")

        result = health_check_wrapper("test", slow_failing_check)

        assert result.status == HealthStatus.UNHEALTHY
        assert result.check_duration_ms is not None
        assert result.check_duration_ms >= 10  # At least 10ms
        assert result.check_duration_ms < 500  # Reasonable upper bound

    def test_wrapper_preserves_result_duration(self) -> None:
        """Verify wrapper preserves duration from original result."""
        check_result = HealthCheckResult.healthy(
            check_duration_ms=5.0,
        )
        mock_check = MagicMock(return_value=check_result)

        result = health_check_wrapper("test", mock_check)

        # Wrapper's duration measurement should be added or preserved
        assert result.check_duration_ms is not None


class TestHealthCheckProtocol:
    """Tests for HealthCheckProtocol."""

    def test_protocol_implementation(self) -> None:
        """Verify protocol can be implemented."""

        class HealthCheckImpl:
            def health_check(self) -> HealthCheckResult:
                return HealthCheckResult.healthy()

            def is_healthy(self) -> bool:
                return True

        obj = HealthCheckImpl()
        assert isinstance(obj, HealthCheckProtocol)

    def test_protocol_runtime_checkable(self) -> None:
        """Verify protocol is runtime-checkable."""
        mock_obj = MagicMock(spec=HealthCheckProtocol)
        mock_obj.health_check.return_value = HealthCheckResult.healthy()

        # Should be checkable at runtime
        assert hasattr(mock_obj, "health_check")
        assert hasattr(mock_obj, "is_healthy")
