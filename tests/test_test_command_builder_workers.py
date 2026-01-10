"""Comprehensive tests for test worker calculation in TestCommandBuilder."""

import multiprocessing
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import psutil
import pytest

from crackerjack.config.settings import CrackerjackSettings, TestSettings
from crackerjack.managers.test_command_builder import TestCommandBuilder


class MockOptions:
    """Mock OptionsProtocol for testing."""

    def __init__(self, test_workers: int = 0, benchmark: bool = False, verbose: bool = False) -> None:
        self.test_workers = test_workers
        self.benchmark = benchmark
        self.verbose = verbose


@pytest.fixture
def builder(tmp_path):
    """Create a TestCommandBuilder instance for testing."""
    return TestCommandBuilder(pkg_path=tmp_path)


@pytest.fixture
def builder_with_console(tmp_path):
    """Create a TestCommandBuilder with mock console."""
    mock_console = MagicMock()
    builder = TestCommandBuilder(pkg_path=tmp_path)
    builder.console = mock_console
    return builder, mock_console


@pytest.fixture
def mock_settings():
    """Create mock CrackerjackSettings with testing configuration."""
    settings = CrackerjackSettings()
    settings.testing = TestSettings()
    settings.testing.auto_detect_workers = True
    settings.testing.max_workers = 8
    settings.testing.min_workers = 2
    settings.testing.memory_per_worker_gb = 2.0
    return settings


class TestGetOptimalWorkers:
    """Test suite for get_optimal_workers() method."""

    def test_explicit_worker_count_respected(self, builder) -> None:
        """Explicit worker count overrides auto-detection."""
        options = MockOptions(test_workers=4)
        assert builder.get_optimal_workers(options) == 4

    def test_sequential_execution_with_one_worker(self, builder) -> None:
        """test_workers=1 forces sequential execution."""
        options = MockOptions(test_workers=1)
        assert builder.get_optimal_workers(options) == 1

    def test_auto_detect_returns_auto_string(self, builder, mock_settings) -> None:
        """Auto-detect with flag enabled returns 'auto' for pytest-xdist."""
        builder.settings = mock_settings
        options = MockOptions(test_workers=0)
        result = builder.get_optimal_workers(options)
        assert result == "auto"

    def test_auto_detect_disabled_returns_one(self, builder, mock_settings) -> None:
        """Auto-detect disabled returns 1 (legacy behavior)."""
        mock_settings.testing.auto_detect_workers = False
        builder.settings = mock_settings
        options = MockOptions(test_workers=0)
        result = builder.get_optimal_workers(options)
        assert result == 1

    def test_fractional_workers_divides_correctly(self, builder) -> None:
        """Negative values divide CPU count."""
        with patch("multiprocessing.cpu_count", return_value=8):
            with patch("psutil.virtual_memory") as mock_mem:
                # Mock sufficient memory (16GB available)
                mock_mem.return_value.available = 16 * 1024**3
                options = MockOptions(test_workers=-2)
                result = builder.get_optimal_workers(options)
                assert result == 4  # 8 // 2 = 4

    def test_fractional_workers_respects_minimum(self, builder) -> None:
        """Fractional calculation respects minimum of 1."""
        with patch("multiprocessing.cpu_count", return_value=2):
            options = MockOptions(test_workers=-4)
            result = builder.get_optimal_workers(options)
            assert result == 1  # max(1, 2 // 4) = 1

    def test_emergency_rollback_env_var(self, builder_with_console) -> None:
        """CRACKERJACK_DISABLE_AUTO_WORKERS=1 forces sequential."""
        builder, mock_console = builder_with_console
        with patch.dict(os.environ, {"CRACKERJACK_DISABLE_AUTO_WORKERS": "1"}):
            options = MockOptions(test_workers=0)
            result = builder.get_optimal_workers(options)
            assert result == 1
            mock_console.print.assert_called()

    def test_cpu_count_failure_returns_safe_default(self, builder_with_console) -> None:
        """Gracefully handles multiprocessing.cpu_count() failure."""
        builder, mock_console = builder_with_console
        with patch("multiprocessing.cpu_count", side_effect=NotImplementedError):
            options = MockOptions(test_workers=-2)  # Use fractional to trigger cpu_count call
            result = builder.get_optimal_workers(options)
            assert result == 2  # Safe fallback
            mock_console.print.assert_called()

    def test_general_exception_returns_safe_default(self, builder_with_console) -> None:
        """Any exception returns safe default of 2."""
        builder, mock_console = builder_with_console
        with patch("multiprocessing.cpu_count", side_effect=RuntimeError("Test error")):
            options = MockOptions(test_workers=-2)  # Use fractional to trigger cpu_count call
            result = builder.get_optimal_workers(options)
            assert result == 2
            mock_console.print.assert_called()


class TestApplyMemoryLimit:
    """Test suite for _apply_memory_limit() method."""

    def test_memory_limit_when_sufficient(self, builder, mock_settings) -> None:
        """Workers not limited when memory is sufficient."""
        builder.settings = mock_settings

        with patch("psutil.virtual_memory") as mock_mem:
            # Simulate 16GB available memory (8 workers * 2GB = 16GB)
            mock_mem.return_value.available = 16 * 1024**3
            result = builder._apply_memory_limit(8)
            assert result == 8  # Not limited

    def test_memory_limit_when_insufficient(self, builder_with_console, mock_settings) -> None:
        """Workers limited when memory is insufficient."""
        builder, mock_console = builder_with_console
        builder.settings = mock_settings

        with patch("psutil.virtual_memory") as mock_mem:
            # Simulate 4GB available memory (should limit to 2 workers)
            mock_mem.return_value.available = 4 * 1024**3
            result = builder._apply_memory_limit(8)
            assert result == 2  # Limited by memory
            mock_console.print.assert_called()  # Warning logged

    def test_memory_limit_respects_minimum_one_worker(self, builder, mock_settings) -> None:
        """Always returns at least 1 worker."""
        builder.settings = mock_settings

        with patch("psutil.virtual_memory") as mock_mem:
            # Simulate very low memory (1GB available)
            mock_mem.return_value.available = 1 * 1024**3
            result = builder._apply_memory_limit(8)
            assert result == 1  # At least 1 worker

    def test_memory_limit_psutil_failure_fallback(self, builder) -> None:
        """Conservative fallback if psutil fails."""
        with patch("psutil.virtual_memory", side_effect=Exception("Test error")):
            result = builder._apply_memory_limit(8)
            assert result == 4  # Conservative fallback

    def test_memory_limit_custom_per_worker_gb(self, builder, mock_settings) -> None:
        """Respects custom memory_per_worker_gb setting."""
        mock_settings.testing.memory_per_worker_gb = 4.0  # 4GB per worker
        builder.settings = mock_settings

        with patch("psutil.virtual_memory") as mock_mem:
            # 8GB available memory → 2 workers (8 / 4 = 2)
            mock_mem.return_value.available = 8 * 1024**3
            result = builder._apply_memory_limit(8)
            assert result == 2


class TestAddWorkerOptions:
    """Test suite for _add_worker_options() method."""

    def test_auto_detection_adds_n_auto(self, builder_with_console, mock_settings) -> None:
        """Auto-detection adds -n auto --dist=loadfile."""
        builder, mock_console = builder_with_console
        builder.settings = mock_settings
        cmd = []
        options = MockOptions(test_workers=0)

        builder._add_worker_options(cmd, options)

        assert "-n" in cmd
        assert "auto" in cmd
        assert "--dist=loadfile" in cmd
        mock_console.print.assert_called()  # Logging

    def test_explicit_workers_adds_n_count(self, builder_with_console) -> None:
        """Explicit worker count adds -n <count> --dist=loadfile."""
        builder, mock_console = builder_with_console
        cmd = []
        options = MockOptions(test_workers=4)

        builder._add_worker_options(cmd, options)

        assert "-n" in cmd
        assert "4" in cmd
        assert "--dist=loadfile" in cmd
        mock_console.print.assert_called()

    def test_sequential_execution_no_n_flag(self, builder_with_console) -> None:
        """Sequential execution (workers=1) doesn't add -n flag."""
        builder, mock_console = builder_with_console
        cmd = []
        options = MockOptions(test_workers=1)

        builder._add_worker_options(cmd, options)

        assert "-n" not in cmd
        mock_console.print.assert_called()  # Still logs

    def test_benchmark_mode_skips_parallelization(self, builder_with_console) -> None:
        """Benchmark mode skips parallelization regardless of workers."""
        builder, mock_console = builder_with_console
        cmd = []
        options = MockOptions(test_workers=4, benchmark=True)

        builder._add_worker_options(cmd, options)

        assert "-n" not in cmd  # No parallelization for benchmarks
        mock_console.print.assert_called()  # Warning logged


class TestIntegration:
    """Integration tests for full command building."""

    def test_build_command_includes_worker_options(self, builder, mock_settings) -> None:
        """build_command() includes worker options."""
        builder.settings = mock_settings
        options = MockOptions(test_workers=0)

        cmd = builder.build_command(options)

        assert "-n" in cmd
        assert "auto" in cmd
        assert "--dist=loadfile" in cmd

    def test_fractional_workers_with_memory_limit(self, builder, mock_settings) -> None:
        """Fractional workers respects memory limit."""
        builder.settings = mock_settings

        with patch("multiprocessing.cpu_count", return_value=8):
            with patch("psutil.virtual_memory") as mock_mem:
                # 4GB available → limit to 2 workers
                mock_mem.return_value.available = 4 * 1024**3

                options = MockOptions(test_workers=-2)  # Request 4 workers (8/2)
                result = builder.get_optimal_workers(options)

                assert result == 2  # Limited by memory (4GB / 2GB = 2)

    def test_no_settings_uses_safe_defaults(self, builder) -> None:
        """Builder without settings uses safe defaults."""
        builder.settings = None  # No settings
        options = MockOptions(test_workers=0)

        result = builder.get_optimal_workers(options)

        # Without settings, auto_detect_workers defaults to False (legacy mode)
        assert result == 1


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_workers_with_no_options_attribute(self, builder) -> None:
        """Handles missing test_workers attribute gracefully."""
        options = MagicMock(spec=[])  # No test_workers attribute
        result = builder.get_optimal_workers(options)
        assert result == 2  # Safe default

    def test_negative_zero_workers(self, builder) -> None:
        """Handles -0 (negative zero) correctly."""
        options = MockOptions(test_workers=-0)
        # -0 == 0, so should trigger auto-detection or legacy mode
        result = builder.get_optimal_workers(options)
        assert result in [1, "auto"]  # Depends on settings

    def test_very_large_explicit_worker_count(self, builder) -> None:
        """Accepts very large explicit worker counts (no limit enforced)."""
        options = MockOptions(test_workers=100)
        result = builder.get_optimal_workers(options)
        assert result == 100  # Explicit values not limited

    def test_memory_limit_with_no_settings(self, builder) -> None:
        """_apply_memory_limit works without settings."""
        builder.settings = None

        with patch("psutil.virtual_memory") as mock_mem:
            mock_mem.return_value.available = 4 * 1024**3
            result = builder._apply_memory_limit(8)

            # Uses default 2GB per worker → 2 workers
            assert result == 2
