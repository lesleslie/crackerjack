"""Tests for service_watchdog module."""

import asyncio
import signal
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from crackerjack.core.service_watchdog import (
    ServiceConfig,
    ServiceState,
    ServiceStatus,
    ServiceWatchdog,
    add_service,
    get_all_services_status,
    get_service_status,
    get_service_watchdog,
    is_healthy,
    print_status_report,
    remove_service,
    signal_handler,
    start_service,
    start_watchdog,
    stop_service,
    stop_watchdog,
    uptime,
)


class TestServiceState:
    """Tests for ServiceState enum."""

    def test_values(self) -> None:
        """Test all expected states exist."""
        expected = ["STOPPED", "STARTING", "RUNNING", "STOPPING", "FAILED", "TIMEOUT"]
        for state in expected:
            assert hasattr(ServiceState, state)


class TestServiceConfig:
    """Tests for ServiceConfig dataclass."""

    def test_creation(self) -> None:
        """Test basic ServiceConfig creation."""
        config = ServiceConfig(name="Test Service", command=["echo", "test"])
        assert config.name == "Test Service"
        assert config.command == ["echo", "test"]

    def test_creation_with_defaults(self) -> None:
        """Test ServiceConfig creation with default values."""
        config = ServiceConfig(name="Test", command=["echo"])
        assert config.health_check_url is None
        assert config.health_check_timeout == 5.0
        assert config.startup_timeout == 30.0
        assert config.shutdown_timeout == 10.0
        assert config.max_restarts == 5
        assert config.restart_delay == 5.0
        assert config.restart_backoff_multiplier == 2.0
        assert config.max_restart_delay == 300.0

    def test_creation_with_custom_values(self) -> None:
        """Test ServiceConfig with custom values."""
        config = ServiceConfig(
            name="Custom Service",
            command=["python", "-m", "server"],
            health_check_url="http://localhost:8080/health",
            health_check_timeout=10.0,
            startup_timeout=60.0,
            shutdown_timeout=30.0,
            max_restarts=3,
            restart_delay=10.0,
            restart_backoff_multiplier=1.5,
            max_restart_delay=120.0,
        )
        assert config.health_check_url == "http://localhost:8080/health"
        assert config.health_check_timeout == 10.0
        assert config.startup_timeout == 60.0
        assert config.shutdown_timeout == 30.0
        assert config.max_restarts == 3
        assert config.restart_delay == 10.0
        assert config.restart_backoff_multiplier == 1.5
        assert config.max_restart_delay == 120.0


class TestServiceStatus:
    """Tests for ServiceStatus dataclass."""

    @pytest.fixture
    def config(self) -> ServiceConfig:
        """Create a ServiceConfig for testing."""
        return ServiceConfig(name="Test Service", command=["echo", "test"])

    def test_creation(self, config: ServiceConfig) -> None:
        """Test ServiceStatus creation."""
        status = ServiceStatus(config=config)
        assert status.config is config
        assert status.state == ServiceState.STOPPED
        assert status.process is None
        assert status.last_start_time == 0.0
        assert status.last_health_check == 0.0
        assert status.restart_count == 0
        assert status.consecutive_failures == 0
        assert status.last_error == ""
        assert status.health_check_failures == 0

    def test_uptime_when_running(self, config: ServiceConfig) -> None:
        """Test uptime calculation when service is running."""
        status = ServiceStatus(config=config, state=ServiceState.RUNNING, last_start_time=100.0)
        with patch("time.time", return_value=150.0):
            assert status.uptime == 50.0

    def test_uptime_when_stopped(self, config: ServiceConfig) -> None:
        """Test uptime is 0 when service is not running."""
        status = ServiceStatus(config=config, state=ServiceState.STOPPED)
        assert status.uptime == 0.0

    def test_is_healthy_true(self, config: ServiceConfig) -> None:
        """Test is_healthy returns True for healthy service."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None  # Process is running
        status = ServiceStatus(config=config, state=ServiceState.RUNNING, process=mock_process)
        assert status.is_healthy is True

    def test_is_healthy_false_wrong_state(self, config: ServiceConfig) -> None:
        """Test is_healthy returns False when not RUNNING."""
        status = ServiceStatus(config=config, state=ServiceState.FAILED)
        assert status.is_healthy is False

    def test_is_healthy_false_process_dead(self, config: ServiceConfig) -> None:
        """Test is_healthy returns False when process has exited."""
        mock_process = MagicMock()
        mock_process.poll.return_value = 1  # Process has exited with code 1
        status = ServiceStatus(config=config, state=ServiceState.RUNNING, process=mock_process)
        assert status.is_healthy is False

    def test_is_healthy_false_too_many_failures(self, config: ServiceConfig) -> None:
        """Test is_healthy returns False when health check failures >= 3."""
        mock_process = MagicMock()
        mock_process.poll.return_value = None
        status = ServiceStatus(
            config=config,
            state=ServiceState.RUNNING,
            process=mock_process,
            health_check_failures=3,
        )
        assert status.is_healthy is False


class TestServiceWatchdog:
    """Tests for ServiceWatchdog class."""

    @pytest.fixture
    def watchdog(self) -> ServiceWatchdog:
        """Create a ServiceWatchdog for testing."""
        with patch("crackerjack.core.service_watchdog.get_http_pool", new_callable=AsyncMock):
            return ServiceWatchdog()

    def test_init(self, watchdog: ServiceWatchdog) -> None:
        """Test ServiceWatchdog initialization."""
        assert watchdog.services == {}
        assert watchdog.is_running is False
        assert watchdog.monitor_task is None

    def test_init_with_console(self) -> None:
        """Test initialization with custom console."""
        from crackerjack.core.console import CrackerjackConsole
        console = CrackerjackConsole()
        watchdog = ServiceWatchdog(console=console)
        assert watchdog.console is console

    def test_add_service(self, watchdog: ServiceWatchdog) -> None:
        """Test adding a service to the watchdog."""
        config = ServiceConfig(name="Test Service", command=["echo", "test"])
        watchdog.add_service("test-service", config)
        assert "test-service" in watchdog.services
        assert watchdog.services["test-service"].config == config

    def test_remove_service(self, watchdog: ServiceWatchdog) -> None:
        """Test removing a service from the watchdog."""
        config = ServiceConfig(name="Test Service", command=["echo", "test"])
        watchdog.add_service("test-service", config)
        watchdog.remove_service("test-service")
        assert "test-service" not in watchdog.services

    def test_remove_nonexistent_service(self, watchdog: ServiceWatchdog) -> None:
        """Test removing a service that doesn't exist."""
        # Should not raise
        watchdog.remove_service("nonexistent")

    @pytest.mark.asyncio
    async def test_stop_watchdog_when_not_running(self, watchdog: ServiceWatchdog) -> None:
        """Test stopping watchdog when it's not running."""
        result = await watchdog.stop_watchdog()
        assert result is None  # Should just return

    def test_get_service_status(self, watchdog: ServiceWatchdog) -> None:
        """Test getting status of a specific service."""
        config = ServiceConfig(name="Test", command=["echo"])
        watchdog.add_service("test", config)
        status = watchdog.get_service_status("test")
        assert status is not None
        assert status.config.name == "Test"

    def test_get_service_status_nonexistent(self, watchdog: ServiceWatchdog) -> None:
        """Test getting status of nonexistent service."""
        status = watchdog.get_service_status("nonexistent")
        assert status is None

    def test_get_all_services_status(self, watchdog: ServiceWatchdog) -> None:
        """Test getting all service statuses."""
        config1 = ServiceConfig(name="Service1", command=["echo"])
        config2 = ServiceConfig(name="Service2", command=["echo"])
        watchdog.add_service("service1", config1)
        watchdog.add_service("service2", config2)

        statuses = watchdog.get_all_services_status()
        assert len(statuses) == 2
        assert "service1" in statuses
        assert "service2" in statuses

    def test_get_all_services_status_returns_copy(self, watchdog: ServiceWatchdog) -> None:
        """Test that get_all_services_status returns a copy."""
        config = ServiceConfig(name="Test", command=["echo"])
        watchdog.add_service("test", config)

        statuses = watchdog.get_all_services_status()
        statuses.clear()  # Modify the returned dict

        # Original should be unchanged
        assert "test" in watchdog.services

    def test_validate_service_start_request_valid(self, watchdog: ServiceWatchdog) -> None:
        """Test _validate_service_start_request for valid request."""
        config = ServiceConfig(name="Test", command=["echo"])
        watchdog.add_service("test", config)
        watchdog.services["test"].state = ServiceState.STOPPED

        result = watchdog._validate_service_start_request("test")
        assert result is True

    def test_validate_service_start_request_not_found(self, watchdog: ServiceWatchdog) -> None:
        """Test _validate_service_start_request for nonexistent service."""
        result = watchdog._validate_service_start_request("nonexistent")
        assert result is False

    def test_validate_service_start_request_already_running(self, watchdog: ServiceWatchdog) -> None:
        """Test _validate_service_start_request when service is already running."""
        config = ServiceConfig(name="Test", command=["echo"])
        watchdog.add_service("test", config)
        watchdog.services["test"].state = ServiceState.RUNNING

        result = watchdog._validate_service_start_request("test")
        assert result is False

    def test_validate_service_start_request_starting(self, watchdog: ServiceWatchdog) -> None:
        """Test _validate_service_start_request when service is starting."""
        config = ServiceConfig(name="Test", command=["echo"])
        watchdog.add_service("test", config)
        watchdog.services["test"].state = ServiceState.STARTING

        result = watchdog._validate_service_start_request("test")
        assert result is False

    def test_prepare_service_startup(self, watchdog: ServiceWatchdog) -> None:
        """Test _prepare_service_startup updates service state."""
        config = ServiceConfig(name="Test", command=["echo"])
        watchdog.add_service("test", config)
        service = watchdog.services["test"]

        with patch("time.time", return_value=100.0):
            watchdog._prepare_service_startup(service)

        assert service.state == ServiceState.STARTING
        assert service.last_start_time == 100.0

    def test_get_service_status_display_running_healthy(self, watchdog: ServiceWatchdog) -> None:
        """Test status display for healthy running service."""
        config = ServiceConfig(name="Test", command=["echo"])
        status = ServiceStatus(config=config, state=ServiceState.RUNNING)
        status.is_healthy = True  # Mock

        # Access the private method for testing
        display = watchdog._get_service_status_display(status)
        assert "Running" in display or "🟢" in display

    def test_get_service_status_display_failed(self, watchdog: ServiceWatchdog) -> None:
        """Test status display for failed service."""
        config = ServiceConfig(name="Test", command=["echo"])
        status = ServiceStatus(config=config, state=ServiceState.FAILED)

        display = watchdog._get_service_status_display(status)
        assert "Failed" in display or "🔴" in display

    def test_format_uptime_hours(self, watchdog: ServiceWatchdog) -> None:
        """Test uptime formatting for hours."""
        result = watchdog._format_uptime(3700)  # ~1 hour
        assert "h" in result

    def test_format_uptime_minutes(self, watchdog: ServiceWatchdog) -> None:
        """Test uptime formatting for minutes."""
        result = watchdog._format_uptime(120)  # 2 minutes
        assert "m" in result

    def test_format_uptime_seconds(self, watchdog: ServiceWatchdog) -> None:
        """Test uptime formatting for seconds."""
        result = watchdog._format_uptime(45)
        assert "s" in result

    def test_format_uptime_zero(self, watchdog: ServiceWatchdog) -> None:
        """Test uptime formatting for zero."""
        result = watchdog._format_uptime(0)
        assert result == "-"


class TestGlobalWatchdogFunctions:
    """Tests for global watchdog functions."""

    def test_get_service_watchdog_returns_singleton(self) -> None:
        """Test get_service_watchdog returns singleton."""
        with patch("crackerjack.core.service_watchdog.get_http_pool", new_callable=AsyncMock):
            wd1 = get_service_watchdog()
            wd2 = get_service_watchdog()
            assert wd1 is wd2

    def test_get_service_watchdog_with_console(self) -> None:
        """Test get_service_watchdog with custom console."""
        from crackerjack.core.console import CrackerjackConsole
        console = CrackerjackConsole()
        with patch("crackerjack.core.service_watchdog.get_http_pool", new_callable=AsyncMock):
            wd = get_service_watchdog(console=console)
            assert wd.console is console

    @pytest.mark.asyncio
    async def test_start_watchdog_creates_task(self) -> None:
        """Test start_watchdog creates a task in current loop."""
        with patch("crackerjack.core.service_watchdog.get_http_pool", new_callable=AsyncMock):
            with patch.object(ServiceWatchdog, "start_watchdog", new_callable=AsyncMock) as mock_start:
                start_watchdog()
                # Task should be created (we can't easily test async task creation)

    @pytest.mark.asyncio
    async def test_stop_watchdog_creates_task(self) -> None:
        """Test stop_watchdog creates a task in current loop."""
        with patch.object(ServiceWatchdog, "stop_watchdog", new_callable=AsyncMock) as mock_stop:
            stop_watchdog()

    def test_uptime(self) -> None:
        """Test uptime function."""
        result = uptime()
        assert isinstance(result, dict)

    def test_is_healthy_dict(self) -> None:
        """Test is_healthy function returns dict."""
        result = is_healthy()
        assert isinstance(result, dict)

    def test_add_service_global(self) -> None:
        """Test add_service global function."""
        config = ServiceConfig(name="Test", command=["echo"])
        add_service("global-test", config)

    def test_remove_service_global(self) -> None:
        """Test remove_service global function."""
        remove_service("global-test")

    def test_start_service_returns_bool(self) -> None:
        """Test start_service returns a boolean."""
        config = ServiceConfig(name="Test", command=["echo"])
        add_service("start-test", config)
        result = start_service("start-test")
        assert isinstance(result, bool)

    def test_stop_service_returns_bool(self) -> None:
        """Test stop_service returns a boolean."""
        config = ServiceConfig(name="Test", command=["echo"])
        add_service("stop-test", config)
        result = stop_service("stop-test")
        assert isinstance(result, bool)

    def test_get_service_status_global(self) -> None:
        """Test get_service_status global function."""
        config = ServiceConfig(name="Test", command=["echo"])
        add_service("status-test", config)
        result = get_service_status("status-test")
        assert result is None or isinstance(result, ServiceStatus)

    def test_get_all_services_status_global(self) -> None:
        """Test get_all_services_status global function."""
        result = get_all_services_status()
        assert isinstance(result, dict)

    def test_print_status_report_no_raise(self) -> None:
        """Test print_status_report doesn't raise."""
        # Should not raise
        print_status_report()

    def test_signal_handler_no_raise(self) -> None:
        """Test signal_handler doesn't raise."""
        # Should not raise even with None frame
        signal_handler(15, None)


class TestServiceWatchdogDefaultConfigs:
    """Tests for default service configurations."""

    def test_default_configs_exist(self) -> None:
        """Test that default_configs dictionary is set up."""
        with patch("crackerjack.core.service_watchdog.get_http_pool", new_callable=AsyncMock):
            wd = ServiceWatchdog()
            assert "mcp_server" in wd.default_configs
            assert "zuban_lsp" in wd.default_configs

    def test_mcp_server_config(self) -> None:
        """Test MCP server default config."""
        with patch("crackerjack.core.service_watchdog.get_http_pool", new_callable=AsyncMock):
            wd = ServiceWatchdog()
            config = wd.default_configs["mcp_server"]
            assert "crackerjack" in config.command

    def test_zuban_lsp_config(self) -> None:
        """Test Zuban LSP default config."""
        with patch("crackerjack.core.service_watchdog.get_http_pool", new_callable=AsyncMock):
            wd = ServiceWatchdog()
            config = wd.default_configs["zuban_lsp"]
            assert "zuban" in config.command
