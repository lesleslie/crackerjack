"""Unit tests for TestManager.

Tests test execution, coverage management, validation,
and progress tracking functionality.
"""

import json
import subprocess
from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch

import pytest

from crackerjack.managers.test_manager import TestManager


@pytest.mark.unit
class TestTestManagerInitialization:
    """Test TestManager initialization."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for TestManager."""
        return {
            "console": Mock(),
            "coverage_ratchet": Mock(),
            "coverage_badge": Mock(),
            "command_builder": Mock(),
            "lsp_client": None,
        }

    def test_initialization_with_dependencies(self, mock_dependencies, tmp_path):
        """Test TestManager initializes with injected dependencies."""
        with patch("crackerjack.managers.test_manager.root_path", tmp_path):
            with patch("crackerjack.managers.test_manager.TestExecutor"):
                manager = TestManager(**mock_dependencies)

                assert manager.console == mock_dependencies["console"]
                assert manager.coverage_ratchet == mock_dependencies["coverage_ratchet"]
                assert manager.command_builder == mock_dependencies["command_builder"]
                assert manager.pkg_path == tmp_path

    def test_initialization_sets_defaults(self, mock_dependencies, tmp_path):
        """Test TestManager sets default values."""
        with patch("crackerjack.managers.test_manager.root_path", tmp_path):
            with patch("crackerjack.managers.test_manager.TestExecutor"):
                manager = TestManager(**mock_dependencies)

                assert manager._last_test_failures == []
                assert manager._progress_callback is None
                assert manager.coverage_ratchet_enabled is True
                assert manager.use_lsp_diagnostics is True

    def test_initialization_creates_executor(self, mock_dependencies, tmp_path):
        """Test TestManager creates TestExecutor."""
        with patch("crackerjack.managers.test_manager.root_path", tmp_path):
            with patch("crackerjack.managers.test_manager.TestExecutor") as mock_executor:
                manager = TestManager(**mock_dependencies)

                mock_executor.assert_called_once()
                assert manager.executor is not None


@pytest.mark.unit
class TestTestManagerConfiguration:
    """Test TestManager configuration methods."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create TestManager instance for testing."""
        with patch("crackerjack.managers.test_manager.root_path", tmp_path):
            with patch("crackerjack.managers.test_manager.TestExecutor"):
                return TestManager(
                    console=Mock(),
                    coverage_ratchet=Mock(),
                    coverage_badge=Mock(),
                    command_builder=Mock(),
                )

    def test_set_progress_callback(self, manager):
        """Test setting progress callback."""
        callback = Mock()

        manager.set_progress_callback(callback)

        assert manager._progress_callback == callback

    def test_set_progress_callback_none(self, manager):
        """Test clearing progress callback."""
        manager._progress_callback = Mock()

        manager.set_progress_callback(None)

        assert manager._progress_callback is None

    def test_set_coverage_ratchet_enabled(self, manager):
        """Test enabling coverage ratchet."""
        manager.set_coverage_ratchet_enabled(True)

        assert manager.coverage_ratchet_enabled is True
        manager.console.print.assert_called()

    def test_set_coverage_ratchet_disabled(self, manager):
        """Test disabling coverage ratchet."""
        manager.set_coverage_ratchet_enabled(False)

        assert manager.coverage_ratchet_enabled is False
        manager.console.print.assert_called()


@pytest.mark.unit
class TestTestManagerTestExecution:
    """Test test execution methods."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create TestManager with mocked executor."""
        with patch("crackerjack.managers.test_manager.root_path", tmp_path):
            with patch("crackerjack.managers.test_manager.TestExecutor") as mock_executor_cls:
                mock_executor = Mock()
                mock_executor_cls.return_value = mock_executor

                manager = TestManager(
                    console=Mock(),
                    coverage_ratchet=Mock(),
                    coverage_badge=Mock(),
                    command_builder=Mock(),
                )
                return manager

    def test_run_tests_early_return_when_disabled(self, manager):
        """Test run_tests returns early when tests disabled."""
        options = Mock()
        options.test = False

        result = manager.run_tests(options)

        assert result is True
        # Should not execute tests
        manager.executor.execute_with_progress.assert_not_called()

    def test_run_tests_success(self, manager):
        """Test successful test execution."""
        options = Mock()
        options.test = True

        # Mock successful execution
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "10 tests passed"
        mock_result.stderr = ""

        manager.command_builder.build_command.return_value = ["pytest"]
        manager.command_builder.get_optimal_workers.return_value = 4
        manager.executor.execute_with_progress.return_value = mock_result

        with patch.object(manager, "_handle_test_success", return_value=True):
            result = manager.run_tests(options)

            assert result is True

    def test_run_tests_failure(self, manager):
        """Test handling test execution failure."""
        options = Mock()
        options.test = True

        # Mock failed execution
        mock_result = Mock()
        mock_result.returncode = 1
        mock_result.stdout = "5 tests failed"
        mock_result.stderr = "Error output"

        manager.command_builder.build_command.return_value = ["pytest"]
        manager.command_builder.get_optimal_workers.return_value = 4
        manager.executor.execute_with_progress.return_value = mock_result

        with patch.object(manager, "_handle_test_failure", return_value=False):
            result = manager.run_tests(options)

            assert result is False

    def test_run_tests_exception_handling(self, manager):
        """Test run_tests handles exceptions."""
        options = Mock()
        options.test = True

        manager.command_builder.build_command.side_effect = Exception("Test error")

        with patch.object(manager, "_handle_test_error", return_value=False):
            result = manager.run_tests(options)

            assert result is False

    def test_run_specific_tests_success(self, manager):
        """Test running specific tests successfully."""
        test_pattern = "tests/test_module.py::test_function"

        mock_result = Mock()
        mock_result.returncode = 0

        manager.command_builder.build_specific_test_command.return_value = ["pytest", test_pattern]
        manager.executor.execute_with_progress.return_value = mock_result

        result = manager.run_specific_tests(test_pattern)

        assert result is True
        manager.console.print.assert_called()

    def test_run_specific_tests_failure(self, manager):
        """Test running specific tests with failures."""
        test_pattern = "tests/test_module.py"

        mock_result = Mock()
        mock_result.returncode = 1

        manager.command_builder.build_specific_test_command.return_value = ["pytest", test_pattern]
        manager.executor.execute_with_progress.return_value = mock_result

        result = manager.run_specific_tests(test_pattern)

        assert result is False


@pytest.mark.unit
class TestTestManagerValidation:
    """Test test environment validation."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create TestManager instance."""
        with patch("crackerjack.managers.test_manager.root_path", tmp_path):
            with patch("crackerjack.managers.test_manager.TestExecutor"):
                return TestManager(
                    console=Mock(),
                    coverage_ratchet=Mock(),
                    coverage_badge=Mock(),
                    command_builder=Mock(),
                )

    def test_validate_test_environment_no_tests(self, manager):
        """Test validation fails when no tests found."""
        with patch.object(manager, "has_tests", return_value=False):
            result = manager.validate_test_environment()

            assert result is False
            manager.console.print.assert_called()

    def test_validate_test_environment_success(self, manager):
        """Test successful environment validation."""
        with patch.object(manager, "has_tests", return_value=True):
            manager.command_builder.build_validation_command.return_value = ["pytest", "--collect-only"]

            with patch("crackerjack.managers.test_manager.subprocess.run") as mock_run:
                mock_result = Mock()
                mock_result.returncode = 0
                mock_run.return_value = mock_result

                result = manager.validate_test_environment()

                assert result is True

    def test_validate_test_environment_failure(self, manager):
        """Test validation handles failures."""
        with patch.object(manager, "has_tests", return_value=True):
            manager.command_builder.build_validation_command.return_value = ["pytest", "--collect-only"]

            with patch("crackerjack.managers.test_manager.subprocess.run") as mock_run:
                mock_result = Mock()
                mock_result.returncode = 1
                mock_result.stderr = "Validation error"
                mock_run.return_value = mock_result

                result = manager.validate_test_environment()

                assert result is False


@pytest.mark.unit
class TestTestManagerCoverage:
    """Test coverage management."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create TestManager instance."""
        with patch("crackerjack.managers.test_manager.root_path", tmp_path):
            with patch("crackerjack.managers.test_manager.TestExecutor"):
                manager = TestManager(
                    console=Mock(),
                    coverage_ratchet=Mock(),
                    coverage_badge=Mock(),
                    command_builder=Mock(),
                )
                manager.pkg_path = tmp_path
                return manager

    def test_get_coverage_ratchet_status(self, manager):
        """Test getting coverage ratchet status."""
        expected_status = {"status": "active", "coverage": 85.5}
        manager.coverage_ratchet.get_status_report.return_value = expected_status

        result = manager.get_coverage_ratchet_status()

        assert result == expected_status

    def test_get_coverage_report_success(self, manager):
        """Test getting coverage report."""
        expected_report = "Coverage: 85.5%"
        manager.coverage_ratchet.get_coverage_report.return_value = expected_report

        result = manager.get_coverage_report()

        assert result == expected_report

    def test_get_coverage_report_exception(self, manager):
        """Test get_coverage_report handles exceptions."""
        manager.coverage_ratchet.get_coverage_report.side_effect = Exception("Error")

        result = manager.get_coverage_report()

        assert result is None

    def test_get_coverage_from_file_success(self, manager, tmp_path):
        """Test extracting coverage from coverage.json."""
        coverage_data = {
            "totals": {
                "percent_covered": 85.5,
                "num_statements": 1000,
                "covered_lines": 855,
            }
        }

        coverage_json = tmp_path / "coverage.json"
        coverage_json.write_text(json.dumps(coverage_data))

        result = manager._get_coverage_from_file()

        assert result == 85.5

    def test_get_coverage_from_file_not_exists(self, manager):
        """Test get_coverage_from_file when file doesn't exist."""
        result = manager._get_coverage_from_file()

        assert result is None

    def test_get_coverage_from_file_invalid_json(self, manager, tmp_path):
        """Test get_coverage_from_file with invalid JSON."""
        coverage_json = tmp_path / "coverage.json"
        coverage_json.write_text("invalid json {")

        result = manager._get_coverage_from_file()

        assert result is None

    def test_get_coverage_from_file_alternative_format(self, manager, tmp_path):
        """Test extracting coverage from alternative format."""
        coverage_data = {
            "percent_covered": 90.0,
        }

        coverage_json = tmp_path / "coverage.json"
        coverage_json.write_text(json.dumps(coverage_data))

        result = manager._get_coverage_from_file()

        assert result == 90.0

    def test_get_coverage_from_files_section(self, manager, tmp_path):
        """Test calculating coverage from files section."""
        coverage_data = {
            "files": {
                "file1.py": {
                    "summary": {
                        "num_statements": 100,
                        "covered_lines": 80,
                    }
                },
                "file2.py": {
                    "summary": {
                        "num_statements": 200,
                        "covered_lines": 160,
                    }
                },
            }
        }

        coverage_json = tmp_path / "coverage.json"
        coverage_json.write_text(json.dumps(coverage_data))

        result = manager._get_coverage_from_file()

        # (80 + 160) / (100 + 200) * 100 = 80.0
        assert result == 80.0

    def test_get_coverage_with_ratchet_data(self, manager):
        """Test get_coverage using ratchet data."""
        manager.coverage_ratchet.get_status_report.return_value = {
            "status": "active",
            "current_coverage": 85.5,
        }

        with patch.object(manager, "_get_coverage_from_file", return_value=None):
            result = manager.get_coverage()

            assert "current_coverage" in result or "coverage_percent" in result

    def test_get_coverage_with_direct_data(self, manager):
        """Test get_coverage using direct file data when ratchet not initialized."""
        manager.coverage_ratchet.get_status_report.return_value = {
            "status": "not_initialized"
        }

        with patch.object(manager, "_get_coverage_from_file", return_value=88.0):
            result = manager.get_coverage()

            assert result["coverage_percent"] == 88.0
            assert result["source"] == "coverage.json"

    def test_get_coverage_not_initialized_no_direct(self, manager):
        """Test get_coverage when ratchet not initialized and no direct data."""
        manager.coverage_ratchet.get_status_report.return_value = {
            "status": "not_initialized"
        }

        with patch.object(manager, "_get_coverage_from_file", return_value=None):
            result = manager.get_coverage()

            assert result["status"] == "not_initialized"
            assert result["coverage_percent"] == 0.0


@pytest.mark.unit
class TestTestManagerStats:
    """Test statistics and information methods."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create TestManager instance."""
        with patch("crackerjack.managers.test_manager.root_path", tmp_path):
            with patch("crackerjack.managers.test_manager.TestExecutor"):
                return TestManager(
                    console=Mock(),
                    coverage_ratchet=Mock(),
                    coverage_badge=Mock(),
                    command_builder=Mock(),
                )

    def test_get_test_stats(self, manager):
        """Test getting test statistics."""
        manager._last_test_failures = ["test1", "test2", "test3"]

        with patch.object(manager, "has_tests", return_value=True):
            stats = manager.get_test_stats()

            assert stats["has_tests"] is True
            assert stats["coverage_ratchet_enabled"] is True
            assert stats["last_failures_count"] == 3

    def test_get_test_failures(self, manager):
        """Test getting test failures."""
        failures = ["test_a failed", "test_b failed"]
        manager._last_test_failures = failures.copy()

        result = manager.get_test_failures()

        assert result == failures
        # Should return a copy, not the original list
        assert result is not manager._last_test_failures

    def test_get_test_command(self, manager):
        """Test getting test command."""
        options = Mock()
        expected_cmd = ["pytest", "-v", "--cov"]
        manager.command_builder.build_command.return_value = expected_cmd

        result = manager.get_test_command(options)

        assert result == expected_cmd
        manager.command_builder.build_command.assert_called_once_with(options)


@pytest.mark.unit
class TestTestManagerHelpers:
    """Test helper methods."""

    @pytest.fixture
    def manager(self, tmp_path):
        """Create TestManager instance."""
        with patch("crackerjack.managers.test_manager.root_path", tmp_path):
            with patch("crackerjack.managers.test_manager.TestExecutor"):
                return TestManager(
                    console=Mock(),
                    coverage_ratchet=Mock(),
                    coverage_badge=Mock(),
                    command_builder=Mock(),
                )

    def test_handle_no_ratchet_status_with_coverage(self, manager):
        """Test handling no ratchet status when coverage available."""
        result = manager._handle_no_ratchet_status(85.5)

        assert result["status"] == "coverage_available"
        assert result["coverage_percent"] == 85.5
        assert result["source"] == "coverage.json"

    def test_handle_no_ratchet_status_without_coverage(self, manager):
        """Test handling no ratchet status when coverage not available."""
        result = manager._handle_no_ratchet_status(None)

        assert result["status"] == "not_initialized"
        assert result["coverage_percent"] == 0.0

    def test_get_final_coverage_prefers_direct(self, manager):
        """Test final coverage prefers direct coverage."""
        result = manager._get_final_coverage(80.0, 85.5)

        assert result == 85.5

    def test_get_final_coverage_uses_ratchet_fallback(self, manager):
        """Test final coverage uses ratchet when no direct coverage."""
        result = manager._get_final_coverage(80.0, None)

        assert result == 80.0
