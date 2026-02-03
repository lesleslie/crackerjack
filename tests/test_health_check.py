"""Unit tests for health check system."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from crackerjack.models.health_check import (
    ComponentHealth,
    HealthCheckProtocol,
    HealthCheckResult,
    SystemHealthReport,
    health_check_wrapper,
)


class TestHealthCheckResult:
    """Tests for HealthCheckResult model."""

    def test_healthy_result(self) -> None:
        """Test creating a healthy result."""
        result = HealthCheckResult.healthy(
            message="Component is healthy",
            component_name="TestComponent",
            details={"version": "1.0.0"},
            check_duration_ms=50.0,
        )

        assert result.status == "healthy"
        assert result.message == "Component is healthy"
        assert result.component_name == "TestComponent"
        assert result.details == {"version": "1.0.0"}
        assert result.check_duration_ms == 50.0
        assert result.exit_code == 0

    def test_degraded_result(self) -> None:
        """Test creating a degraded result."""
        result = HealthCheckResult.degraded(
            message="Component is degraded",
            component_name="TestComponent",
            details={"warning": "High memory usage"},
        )

        assert result.status == "degraded"
        assert result.message == "Component is degraded"
        assert result.exit_code == 1

    def test_unhealthy_result(self) -> None:
        """Test creating an unhealthy result."""
        result = HealthCheckResult.unhealthy(
            message="Component is unhealthy",
            component_name="TestComponent",
            details={"error": "Connection failed"},
        )

        assert result.status == "unhealthy"
        assert result.message == "Component is unhealthy"
        assert result.exit_code == 2

    def test_to_dict(self) -> None:
        """Test converting result to dictionary."""
        result = HealthCheckResult.healthy(
            message="Test",
            component_name="TestComponent",
        )

        data = result.to_dict()

        assert data["status"] == "healthy"
        assert data["message"] == "Test"
        assert data["component_name"] == "TestComponent"
        # Verify timestamp is present and valid ISO format
        assert data["timestamp"]
        datetime.fromisoformat(data["timestamp"])  # Will raise if invalid


class TestComponentHealth:
    """Tests for ComponentHealth model."""

    def test_from_all_healthy(self) -> None:
        """Test component health with all healthy results."""
        results = {
            "comp1": HealthCheckResult.healthy("OK", "comp1"),
            "comp2": HealthCheckResult.healthy("OK", "comp2"),
            "comp3": HealthCheckResult.healthy("OK", "comp3"),
        }

        health = ComponentHealth.from_results("test_category", results)

        assert health.category == "test_category"
        assert health.overall_status == "healthy"
        assert health.total == 3
        assert health.healthy == 3
        assert health.degraded == 0
        assert health.unhealthy == 0
        assert health.exit_code == 0

    def test_from_some_degraded(self) -> None:
        """Test component health with some degraded results."""
        results = {
            "comp1": HealthCheckResult.healthy("OK", "comp1"),
            "comp2": HealthCheckResult.degraded("Warning", "comp2"),
            "comp3": HealthCheckResult.healthy("OK", "comp3"),
        }

        health = ComponentHealth.from_results("test_category", results)

        assert health.overall_status == "degraded"
        assert health.total == 3
        assert health.healthy == 2
        assert health.degraded == 1
        assert health.unhealthy == 0
        assert health.exit_code == 1

    def test_from_some_unhealthy(self) -> None:
        """Test component health with some unhealthy results."""
        results = {
            "comp1": HealthCheckResult.healthy("OK", "comp1"),
            "comp2": HealthCheckResult.unhealthy("Error", "comp2"),
            "comp3": HealthCheckResult.degraded("Warning", "comp3"),
        }

        health = ComponentHealth.from_results("test_category", results)

        assert health.overall_status == "unhealthy"
        assert health.total == 3
        assert health.healthy == 1
        assert health.degraded == 1
        assert health.unhealthy == 1
        assert health.exit_code == 2

    def test_to_dict(self) -> None:
        """Test converting component health to dictionary."""
        results = {
            "comp1": HealthCheckResult.healthy("OK", "comp1"),
        }

        health = ComponentHealth.from_results("test", results)
        data = health.to_dict()

        assert data["category"] == "test"
        assert data["overall_status"] == "healthy"
        assert data["total"] == 1
        assert "components" in data
        assert "comp1" in data["components"]


class TestSystemHealthReport:
    """Tests for SystemHealthReport model."""

    def test_from_all_healthy_categories(self) -> None:
        """Test system health with all healthy categories."""
        adapters = ComponentHealth.from_results(
            "adapters",
            {
                "ruff": HealthCheckResult.healthy("OK", "ruff"),
                "mypy": HealthCheckResult.healthy("OK", "mypy"),
            },
        )
        managers = ComponentHealth.from_results(
            "managers",
            {
                "hook": HealthCheckResult.healthy("OK", "hook"),
                "test": HealthCheckResult.healthy("OK", "test"),
            },
        )
        services = ComponentHealth.from_results(
            "services",
            {
                "git": HealthCheckResult.healthy("OK", "git"),
            },
        )

        report = SystemHealthReport.from_category_health(
            {
                "adapters": adapters,
                "managers": managers,
                "services": services,
            }
        )

        assert report.overall_status == "healthy"
        assert report.exit_code == 0
        assert "5 components healthy" in report.summary
        assert len(report.categories) == 3

    def test_from_degraded_category(self) -> None:
        """Test system health with degraded category."""
        adapters = ComponentHealth.from_results(
            "adapters",
            {
                "ruff": HealthCheckResult.healthy("OK", "ruff"),
                "mypy": HealthCheckResult.degraded("Warning", "mypy"),
            },
        )
        managers = ComponentHealth.from_results(
            "managers",
            {
                "hook": HealthCheckResult.healthy("OK", "hook"),
            },
        )

        report = SystemHealthReport.from_category_health(
            {
                "adapters": adapters,
                "managers": managers,
            }
        )

        assert report.overall_status == "degraded"
        assert report.exit_code == 1

    def test_from_unhealthy_category(self) -> None:
        """Test system health with unhealthy category."""
        adapters = ComponentHealth.from_results(
            "adapters",
            {
                "ruff": HealthCheckResult.healthy("OK", "ruff"),
                "mypy": HealthCheckResult.unhealthy("Error", "mypy"),
            },
        )

        report = SystemHealthReport.from_category_health({"adapters": adapters})

        assert report.overall_status == "unhealthy"
        assert report.exit_code == 2

    def test_to_dict(self) -> None:
        """Test converting system health report to dictionary."""
        adapters = ComponentHealth.from_results(
            "adapters",
            {"ruff": HealthCheckResult.healthy("OK", "ruff")},
        )

        report = SystemHealthReport.from_category_health({"adapters": adapters})
        data = report.to_dict()

        assert data["overall_status"] == "healthy"
        assert "categories" in data
        assert "adapters" in data["categories"]
        assert "timestamp" in data


class TestHealthCheckWrapper:
    """Tests for health_check_wrapper function."""

    def test_successful_check(self) -> None:
        """Test wrapper with successful health check."""
        def check_func() -> HealthCheckResult:
            return HealthCheckResult.healthy("OK", "TestComponent")

        result = health_check_wrapper("TestComponent", check_func)

        assert result.status == "healthy"
        assert result.component_name == "TestComponent"

    def test_exception_handling(self) -> None:
        """Test wrapper with exception in health check."""
        def check_func() -> HealthCheckResult:
            raise ValueError("Test error")

        result = health_check_wrapper("TestComponent", check_func)

        assert result.status == "unhealthy"
        assert result.component_name == "TestComponent"
        assert "Test error" in result.message
        assert result.details["error_type"] == "ValueError"

    def test_component_name_fallback(self) -> None:
        """Test wrapper sets component_name if missing."""
        def check_func() -> HealthCheckResult:
            return HealthCheckResult.healthy("OK")

        result = health_check_wrapper("TestComponent", check_func)

        assert result.component_name == "TestComponent"


class TestHealthCheckProtocol:
    """Tests for HealthCheckProtocol protocol."""

    def test_protocol_compliance(self) -> None:
        """Test that a class implementing the protocol is recognized."""

        class MockComponent:
            def health_check(self) -> HealthCheckResult:
                return HealthCheckResult.healthy("OK", "MockComponent")

            def is_healthy(self) -> bool:
                return True

        component = MockComponent()
        assert isinstance(component, HealthCheckProtocol)
        assert component.health_check().status == "healthy"
        assert component.is_healthy() is True


class TestHealthCheckCLI:
    """Tests for CLI health check handler."""

    def test_health_check_exit_codes(self) -> None:
        """Test that exit codes are correct for different statuses."""
        assert HealthCheckResult.healthy("OK").exit_code == 0
        assert HealthCheckResult.degraded("Warning").exit_code == 1
        assert HealthCheckResult.unhealthy("Error").exit_code == 2

    def test_component_health_exit_codes(self) -> None:
        """Test that component health exit codes are correct."""
        healthy = ComponentHealth(
            category="test",
            overall_status="healthy",
            total=1,
            healthy=1,
            degraded=0,
            unhealthy=0,
        )
        assert healthy.exit_code == 0

        degraded = ComponentHealth(
            category="test",
            overall_status="degraded",
            total=1,
            healthy=0,
            degraded=1,
            unhealthy=0,
        )
        assert degraded.exit_code == 1

        unhealthy = ComponentHealth(
            category="test",
            overall_status="unhealthy",
            total=1,
            healthy=0,
            degraded=0,
            unhealthy=1,
        )
        assert unhealthy.exit_code == 2

    def test_system_health_exit_codes(self) -> None:
        """Test that system health exit codes are correct."""
        healthy_report = SystemHealthReport(
            overall_status="healthy",
            categories={},
        )
        assert healthy_report.exit_code == 0

        degraded_report = SystemHealthReport(
            overall_status="degraded",
            categories={},
        )
        assert degraded_report.exit_code == 1

        unhealthy_report = SystemHealthReport(
            overall_status="unhealthy",
            categories={},
        )
        assert unhealthy_report.exit_code == 2

    def test_json_output_format(self) -> None:
        """Test JSON output format is valid."""
        result = HealthCheckResult.healthy(
            message="Test",
            component_name="TestComponent",
            details={"version": "1.0"},
        )

        data = result.to_dict()
        json_str = json.dumps(data)

        # Ensure it's valid JSON
        parsed = json.loads(json_str)
        assert parsed["status"] == "healthy"
        assert parsed["message"] == "Test"
        assert parsed["component_name"] == "TestComponent"
        assert parsed["details"]["version"] == "1.0"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
