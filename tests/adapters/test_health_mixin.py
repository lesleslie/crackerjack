"""Tests for HealthCheckMixin.

Covers: crackerjack/adapters/health_mixin.py
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.adapters.health_mixin import HealthCheckMixin
from crackerjack.models.health_check import HealthCheckResult
from crackerjack.models.qa_config import QACheckConfig


class ConcreteHealthAdapter(HealthCheckMixin):
    """Concrete implementation of HealthCheckMixin for testing."""

    def __init__(self) -> None:
        self.tool_name = "test_tool"
        self.config = None
        self.pkg_path = None


class TestHealthCheckMixin:
    """Tests for HealthCheckMixin."""

    def test_tool_name_default_empty(self):
        adapter = HealthCheckMixin()
        assert adapter.tool_name == ""

    def test_config_default_none(self):
        adapter = HealthCheckMixin()
        assert adapter.config is None

    def test_pkg_path_default_none(self):
        adapter = HealthCheckMixin()
        assert adapter.pkg_path is None


class TestHealthCheck:
    """Tests for health_check method."""

    def test_healthy_when_all_checks_pass(self):
        adapter = ConcreteHealthAdapter()
        adapter.tool_name = "python"  # Exists on most systems

        result = adapter.health_check()

        assert result.status.value == "healthy"
        assert "healthy" in result.message.lower()
        assert result.details["tool_available"] is True
        assert result.details["config_valid"] is True
        assert result.check_duration_ms is not None
        assert result.check_duration_ms >= 0

    def test_unhealthy_when_tool_not_found(self):
        adapter = ConcreteHealthAdapter()
        adapter.tool_name = "nonexistent_tool_12345"

        result = adapter.health_check()

        assert result.status.value == "unhealthy"
        assert "not found" in result.message.lower()
        assert result.details["tool_available"] is False

    def test_degraded_when_config_invalid(self):
        adapter = ConcreteHealthAdapter()
        adapter.tool_name = "python"
        adapter.config = MagicMock(spec=[])  # Invalid config

        result = adapter.health_check()

        assert result.status.value == "degraded"
        assert "invalid" in result.message.lower() or "degraded" in result.message.lower()

    def test_degraded_when_pkg_path_inaccessible(self):
        adapter = ConcreteHealthAdapter()
        adapter.tool_name = "python"
        adapter.pkg_path = Path("/nonexistent/path/that/does/not/exist")

        result = adapter.health_check()

        assert result.status.value == "degraded"
        assert "not accessible" in result.message.lower()

    def test_check_duration_ms_is_recorded(self):
        adapter = ConcreteHealthAdapter()
        adapter.tool_name = "python"

        start = time.time()
        result = adapter.health_check()
        elapsed = (time.time() - start) * 1000

        assert result.check_duration_ms is not None
        assert result.check_duration_ms >= 0
        assert result.check_duration_ms <= elapsed + 10  # Allow small tolerance


class TestIsHealthy:
    """Tests for is_healthy method."""

    def test_returns_true_when_healthy(self):
        adapter = ConcreteHealthAdapter()
        adapter.tool_name = "python"

        assert adapter.is_healthy() is True

    def test_returns_false_when_unhealthy(self):
        adapter = ConcreteHealthAdapter()
        adapter.tool_name = "nonexistent_tool_xyz"

        assert adapter.is_healthy() is False


class TestCheckToolAvailable:
    """Tests for _check_tool_available method."""

    def test_returns_true_when_tool_in_path(self):
        adapter = ConcreteHealthAdapter()
        adapter.tool_name = "python"

        assert adapter._check_tool_available() is True

    def test_returns_false_when_tool_not_in_path(self):
        adapter = ConcreteHealthAdapter()
        adapter.tool_name = "nonexistent_tool_abc"

        assert adapter._check_tool_available() is False

    def test_returns_true_when_tool_name_empty(self):
        adapter = ConcreteHealthAdapter()
        adapter.tool_name = ""

        assert adapter._check_tool_available() is True


class TestCheckConfiguration:
    """Tests for _check_configuration method."""

    def test_returns_true_when_config_none(self):
        adapter = ConcreteHealthAdapter()
        adapter.config = None

        assert adapter._check_configuration() is True

    def test_returns_true_when_config_valid(self):
        adapter = ConcreteHealthAdapter()
        # Create a mock config with required attributes
        mock_config = MagicMock()
        mock_config.name = "test"
        mock_config.enabled = True
        adapter.config = mock_config

        assert adapter._check_configuration() is True

    def test_returns_false_when_config_invalid(self):
        adapter = ConcreteHealthAdapter()
        adapter.config = MagicMock(spec=[])  # Invalid - no name/enabled

        assert adapter._check_configuration() is False


class TestCheckPackagePath:
    """Tests for _check_package_path method."""

    def test_returns_true_when_pkg_path_none(self):
        adapter = ConcreteHealthAdapter()
        adapter.pkg_path = None

        assert adapter._check_package_path() is True

    def test_returns_true_when_pkg_path_exists(self):
        adapter = ConcreteHealthAdapter()
        adapter.pkg_path = Path("/tmp")

        assert adapter._check_package_path() is True

    def test_returns_false_when_pkg_path_not_exists(self):
        adapter = ConcreteHealthAdapter()
        adapter.pkg_path = Path("/nonexistent/path")

        assert adapter._check_package_path() is False


class TestGetToolVersion:
    """Tests for get_tool_version method."""

    def test_returns_none_by_default(self):
        adapter = ConcreteHealthAdapter()

        assert adapter.get_tool_version() is None


class TestHealthCheckMixinIntegration:
    """Integration tests for HealthCheckMixin."""

    def test_health_check_result_to_dict(self):
        adapter = ConcreteHealthAdapter()
        adapter.tool_name = "python"

        result = adapter.health_check()
        result_dict = result.to_dict()

        assert "status" in result_dict
        assert "message" in result_dict
        assert "details" in result_dict
        assert "timestamp" in result_dict
        assert "component_name" in result_dict
        assert "check_duration_ms" in result_dict

    def test_multiple_health_checks_return_consistent_results(self):
        adapter = ConcreteHealthAdapter()
        adapter.tool_name = "python"

        result1 = adapter.health_check()
        result2 = adapter.health_check()

        assert result1.status == result2.status
        assert result1.component_name == result2.component_name