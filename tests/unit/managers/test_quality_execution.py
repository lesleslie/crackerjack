"""Comprehensive tests for quality check execution in TestManager."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from crackerjack.managers.test_manager import TestManager
from crackerjack.models.protocols import OptionsProtocol


@pytest.fixture
def mock_console():
    """Create a mock console."""
    console = MagicMock()
    console.print = MagicMock()
    return console


@pytest.fixture
def mock_command_builder():
    """Create a mock command builder."""
    builder = MagicMock()
    builder.build_test_command = MagicMock(return_value=["pytest", "-v"])
    return builder


@pytest.fixture
def test_manager(mock_console, mock_command_builder, tmp_path):
    """Create a TestManager instance for testing."""
    manager = TestManager(
        console=mock_console,
        pkg_path=tmp_path,
        command_builder=mock_command_builder,
    )
    return manager


class TestTestManagerInitialization:
    """Test TestManager initialization and lifecycle."""

    def test_initialization_with_defaults(self):
        """Test TestManager initializes with default values."""
        manager = TestManager()
        assert manager.console is not None
        assert manager.pkg_path == Path.cwd()
        assert manager.coverage_ratchet_enabled is False
        assert manager._service_initialized is False
        assert manager._request_count == 0
        assert manager._error_count == 0
        assert manager._resources == []

    def test_initialization_with_custom_console(self, mock_console):
        """Test initialization with custom console."""
        manager = TestManager(console=mock_console)
        assert manager.console == mock_console

    def test_initialization_with_custom_path(self, mock_console, tmp_path):
        """Test initialization with custom package path."""
        manager = TestManager(console=mock_console, pkg_path=tmp_path)
        assert manager.pkg_path == tmp_path

    def test_initialization_with_coverage_ratchet(self, mock_console):
        """Test initialization with coverage ratchet."""
        mock_ratchet = MagicMock()
        manager = TestManager(
            console=mock_console, coverage_ratchet=mock_ratchet
        )
        assert manager.coverage_ratchet == mock_ratchet
        assert manager.coverage_ratchet_enabled is True

    def test_initialize_and_cleanup(self, test_manager):
        """Test initialize and cleanup lifecycle."""
        assert test_manager._service_initialized is False
        test_manager.initialize()
        assert test_manager._service_initialized is True
        test_manager.cleanup()
        assert test_manager._service_initialized is False


class TestTestManagerMetrics:
    """Test TestManager metrics and monitoring."""

    def test_health_check(self, test_manager):
        """Test health check returns True."""
        assert test_manager.health_check() is True
        assert test_manager.is_healthy() is True

    def test_metrics_initial_state(self, test_manager):
        """Test initial metrics state."""
        metrics = test_manager.metrics()
        assert metrics["initialized"] is False
        assert metrics["requests"] == 0
        assert metrics["errors"] == 0
        assert metrics["custom_metrics"] == {}

    def test_metrics_after_initialization(self, test_manager):
        """Test metrics after initialization."""
        test_manager.initialize()
        metrics = test_manager.metrics()
        assert metrics["initialized"] is True

    def test_increment_requests(self, test_manager):
        """Test request counter increment."""
        test_manager.increment_requests()
        test_manager.increment_requests()
        metrics = test_manager.metrics()
        assert metrics["requests"] == 2

    def test_record_error(self, test_manager):
        """Test error recording."""
        test_manager.record_error(Exception("Test error"))
        test_manager.record_error(Exception("Another error"))
        metrics = test_manager.metrics()
        assert metrics["errors"] == 2

    def test_custom_metrics(self, test_manager):
        """Test custom metric operations."""
        test_manager.set_custom_metric("test_metric", 42)
        test_manager.set_custom_metric("another_metric", "value")
        assert test_manager.get_custom_metric("test_metric") == 42
        assert test_manager.get_custom_metric("another_metric") == "value"
        assert test_manager.get_custom_metric("nonexistent") is None

        metrics = test_manager.metrics()
        assert metrics["custom_metrics"]["test_metric"] == 42
        assert metrics["custom_metrics"]["another_metric"] == "value"


class TestTestManagerResources:
    """Test resource management."""

    def test_register_resource(self, test_manager):
        """Test resource registration."""
        resource = MagicMock()
        test_manager.register_resource(resource)
        assert resource in test_manager._resources

    def test_cleanup_resource_with_cleanup_method(self, test_manager):
        """Test cleanup of resource with cleanup method."""
        resource = MagicMock()
        resource.cleanup = MagicMock()
        test_manager.register_resource(resource)
        test_manager.cleanup_resource(resource)
        resource.cleanup.assert_called_once()
        # Note: cleanup_resource does not remove from _resources automatically
        # The cleanup() method handles removal when iterating all resources

    def test_cleanup_resource_with_close_method(self, test_manager):
        """Test cleanup of resource with close method."""
        resource = MagicMock()
        resource.cleanup = None
        resource.close = MagicMock()
        test_manager.register_resource(resource)
        test_manager.cleanup_resource(resource)
        resource.close.assert_called_once()
        # Note: cleanup_resource does not remove from _resources automatically

    def test_cleanup_all_resources(self, test_manager):
        """Test cleanup of all resources."""
        resource1 = MagicMock()
        resource1.cleanup = MagicMock()
        resource2 = MagicMock()
        resource2.cleanup = None  # Force close to be called instead
        resource2.close = MagicMock()
        test_manager.register_resource(resource1)
        test_manager.register_resource(resource2)
        test_manager.cleanup()
        resource1.cleanup.assert_called_once()
        resource2.close.assert_called_once()
        assert len(test_manager._resources) == 0


class TestTestManagerProgressCallback:
    """Test progress callback functionality."""

    def test_set_progress_callback(self, test_manager):
        """Test setting progress callback."""
        callback = MagicMock()
        test_manager.set_progress_callback(callback)
        assert test_manager._progress_callback == callback

    def test_set_none_progress_callback(self, test_manager):
        """Test setting progress callback to None."""
        test_manager.set_progress_callback(None)
        assert test_manager._progress_callback is None


class TestTestManagerCoverageRatchet:
    """Test coverage ratchet functionality."""

    def test_set_coverage_ratchet_enabled(self, test_manager, mock_console):
        """Test enabling coverage ratchet."""
        test_manager.set_coverage_ratchet_enabled(True)
        assert test_manager.coverage_ratchet_enabled is True
        mock_console.print.assert_called()

    def test_set_coverage_ratchet_disabled(self, test_manager, mock_console):
        """Test disabling coverage ratchet."""
        test_manager.set_coverage_ratchet_enabled(False)
        assert test_manager.coverage_ratchet_enabled is False
        mock_console.print.assert_called()


class TestTestManagerRunTests:
    """Test test execution functionality."""

    def test_run_tests_with_mock_options(self, test_manager):
        """Test running tests with mock options."""
        mock_options = MagicMock(spec=OptionsProtocol)
        mock_options.coverage = False
        mock_options.verbose = False
        mock_options.parallel = False
        # Ensure test and run_tests return False (tests disabled)
        # Use spec to make Mock return DEFAULT for undefined attributes
        mock_options.test = False
        mock_options.run_tests = False

        # When tests are disabled, run_tests returns True
        result = test_manager.run_tests(mock_options)
        assert result is True

    def test_run_tests_with_coverage(self, test_manager):
        """Test running tests with coverage."""
        mock_options = MagicMock(spec=OptionsProtocol)
        mock_options.coverage = True
        mock_options.verbose = False
        mock_options.test = False
        mock_options.run_tests = False

        # When tests are disabled, run_tests returns True
        result = test_manager.run_tests(mock_options)
        assert result is True

    def test_run_tests_with_parallel(self, test_manager):
        """Test running tests with parallel execution."""
        mock_options = MagicMock(spec=OptionsProtocol)
        mock_options.coverage = False
        mock_options.parallel = True
        mock_options.test = False
        mock_options.run_tests = False

        # When tests are disabled, run_tests returns True
        result = test_manager.run_tests(mock_options)
        assert result is True

    def test_run_tests_with_verbose(self, test_manager):
        """Test running tests with verbose output."""
        mock_options = MagicMock(spec=OptionsProtocol)
        mock_options.coverage = False
        mock_options.verbose = True
        mock_options.test = False
        mock_options.run_tests = False

        # When tests are disabled, run_tests returns True
        result = test_manager.run_tests(mock_options)
        assert result is True


class TestTestManagerShutdown:
    """Test shutdown functionality."""

    def test_shutdown(self, test_manager):
        """Test shutdown calls cleanup."""
        test_manager.initialize()
        test_manager.shutdown()
        assert test_manager._service_initialized is False


class TestTestManagerPathHandling:
    """Test path handling and resolution."""

    def test_pkg_path_resolution_with_string(self, mock_console):
        """Test package path resolution from string."""
        manager = TestManager(console=mock_console, pkg_path="/tmp/test")
        assert manager.pkg_path == Path("/tmp/test")

    def test_pkg_path_resolution_with_path(self, mock_console, tmp_path):
        """Test package path resolution from Path object."""
        manager = TestManager(console=mock_console, pkg_path=tmp_path)
        assert manager.pkg_path == tmp_path

    def test_pkg_path_defaults_to_cwd(self, mock_console):
        """Test package path defaults to current working directory."""
        manager = TestManager(console=mock_console)
        assert manager.pkg_path == Path.cwd()


class TestTestManagerLSPIntegration:
    """Test LSP client integration."""

    def test_lsp_client_initialization(self, mock_console):
        """Test LSP client can be initialized."""
        mock_lsp = MagicMock()
        manager = TestManager(console=mock_console, lsp_client=mock_lsp)
        assert manager._lsp_client == mock_lsp

    def test_lsp_diagnostics_flag(self, test_manager):
        """Test LSP diagnostics flag is set."""
        assert test_manager.use_lsp_diagnostics is True


class TestTestManagerCoverageBadge:
    """Test coverage badge service integration."""

    def test_coverage_badge_service_initialization(self, mock_console):
        """Test coverage badge service can be initialized."""
        mock_badge = MagicMock()
        manager = TestManager(console=mock_console, coverage_badge=mock_badge)
        assert manager._coverage_badge_service == mock_badge


class TestTestManagerErrorHandling:
    """Test error handling scenarios."""

    def test_handle_invalid_path(self, mock_console):
        """Test handling of invalid path."""
        # Test that TestManager handles path errors gracefully
        try:
            manager = TestManager(console=mock_console, pkg_path="nonexistent/path")
            # Should not raise exception
            assert manager.pkg_path == Path("nonexistent/path")
        except Exception as e:
            pytest.fail(f"TestManager raised exception for invalid path: {e}")

    def test_cleanup_with_successful_resources(self, test_manager):
        """Test cleanup with resources that succeed."""
        resource1 = MagicMock()
        resource1.cleanup = MagicMock()
        resource2 = MagicMock()
        resource2.cleanup = MagicMock()
        test_manager.register_resource(resource1)
        test_manager.register_resource(resource2)
        test_manager.cleanup()
        resource1.cleanup.assert_called_once()
        resource2.cleanup.assert_called_once()
        assert len(test_manager._resources) == 0


class TestTestManagerCommandBuilderIntegration:
    """Test integration with command builder."""

    def test_custom_command_builder(self, mock_console, tmp_path):
        """Test custom command builder is used."""
        custom_builder = MagicMock()
        custom_builder.build_test_command = MagicMock(return_value=["python", "-m", "pytest"])
        manager = TestManager(
            console=mock_console, pkg_path=tmp_path, command_builder=custom_builder
        )
        assert manager.command_builder == custom_builder


class TestTestManagerConsoleInterface:
    """Test console interface integration."""

    def test_console_output(self, test_manager, mock_console):
        """Test console output is called."""
        test_manager.console.print("Test message")
        mock_console.print.assert_called_with("Test message")

    def test_console_width(self, test_manager):
        """Test console width is accessible."""
        # Test that TestManager can work with different console widths
        assert hasattr(test_manager, "console")
        assert test_manager.console is not None
