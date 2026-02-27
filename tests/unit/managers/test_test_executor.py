"""Unit tests for TestExecutor.

Tests test execution, process management, progress tracking,
and xdist fallback functionality.
"""

import subprocess
from unittest.mock import Mock, patch

import pytest

from crackerjack.managers.test_executor import TestExecutor


@pytest.mark.unit
class TestTestExecutorInitialization:
    """Test TestExecutor initialization."""

    def test_initialization(self, tmp_path) -> None:
        """Test TestExecutor initializes correctly."""
        from rich.console import Console

        console = Console()
        executor = TestExecutor(console, tmp_path)

        assert executor.console == console
        assert executor.pkg_path == tmp_path


@pytest.mark.unit
class TestTestExecutorProjectDetection:
    """Test project directory detection."""

    def test_detect_target_project_dir_no_pytest(self, tmp_path) -> None:
        """Test detection when no pytest in command."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)
        cmd = ["python", "-m", "module"]

        result = executor._detect_target_project_dir(cmd)

        assert result == tmp_path

    def test_detect_target_project_dir_pytest_no_args(self, tmp_path) -> None:
        """Test detection with pytest but no test args."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)
        cmd = ["python", "-m", "pytest"]

        result = executor._detect_target_project_dir(cmd)

        assert result == tmp_path

    def test_detect_target_project_dir_with_test_file(self, tmp_path) -> None:
        """Test detection with explicit test file."""
        from rich.console import Console

        # Create test file in subdirectory
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        test_file = test_dir / "test_example.py"
        test_file.touch()

        executor = TestExecutor(Console(), tmp_path)
        cmd = ["pytest", str(test_file)]

        result = executor._detect_target_project_dir(cmd)

        # Should return parent of test directory
        assert result == tmp_path

    def test_find_pytest_index(self, tmp_path) -> None:
        """Test finding pytest index in command."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)

        # The implementation returns i + 1 for the position after "pytest"
        # pytest at position 0
        idx = executor._find_pytest_index(["pytest", "-v"])
        assert idx == 1  # Returns position after pytest

        # pytest at position 2
        idx = executor._find_pytest_index(["python", "-m", "pytest", "-v"])
        assert idx == 3  # Returns position after pytest

        # No pytest
        idx = executor._find_pytest_index(["python", "-m", "module"])
        assert idx == -1

    def test_find_project_from_test_args_with_file(self, tmp_path) -> None:
        """Test finding project from test file path."""
        from rich.console import Console

        # Create test structure
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        test_file = test_dir / "test_example.py"
        test_file.touch()

        executor = TestExecutor(Console(), tmp_path)
        args = [str(test_file), "-v"]

        result = executor._find_project_from_test_args(args)

        # Should return parent of test file
        assert result == tmp_path

    def test_find_project_from_test_args_with_directory(self, tmp_path) -> None:
        """Test finding project from test directory."""
        from rich.console import Console

        # Create test structure
        test_dir = tmp_path / "tests"
        test_dir.mkdir()

        executor = TestExecutor(Console(), tmp_path)
        args = [str(test_dir), "-v"]

        result = executor._find_project_from_test_args(args)

        # Should return parent of test directory
        assert result == tmp_path

    def test_find_project_from_test_args_with_flags(self, tmp_path) -> None:
        """Test finding project with command flags."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)
        args = ["-v", "-s", "--tb=short"]

        result = executor._find_project_from_test_args(args)

        # Should return pkg_path when no valid path found
        assert result == tmp_path

    def test_get_project_dir_from_path_file(self, tmp_path) -> None:
        """Test getting project dir from file path."""
        from rich.console import Console

        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        test_file = test_dir / "test_example.py"
        test_file.touch()

        executor = TestExecutor(Console(), tmp_path)

        result = executor._get_project_dir_from_path(test_file)

        # File: tests/test_example.py -> tests -> tmp_path
        assert result == tmp_path

    def test_get_project_dir_from_path_directory(self, tmp_path) -> None:
        """Test getting project dir from directory path."""
        from rich.console import Console

        test_dir = tmp_path / "tests"
        test_dir.mkdir()

        executor = TestExecutor(Console(), tmp_path)

        result = executor._get_project_dir_from_path(test_dir)

        # Directory: tests/ -> tmp_path
        assert result == tmp_path


@pytest.mark.unit
class TestTestExecutorProgress:
    """Test progress initialization and management."""

    def test_initialize_progress(self, tmp_path) -> None:
        """Test progress initialization."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)

        progress = executor._initialize_progress()

        assert progress.start_time > 0
        assert progress.is_collecting is True

    def test_pre_collect_tests(self, tmp_path) -> None:
        """Test pre-collection returns 0 (stub)."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)
        cmd = ["pytest", "-v"]

        count = executor._pre_collect_tests(cmd)

        # Stub implementation returns 0
        assert count == 0


@pytest.mark.unit
class TestTestExecutorEnvironment:
    """Test environment setup for test execution."""

    def test_setup_test_environment(self, tmp_path) -> None:
        """Test test environment setup."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)

        env = executor._setup_test_environment()

        assert "COVERAGE_FILE" in env
        assert "PYTEST_CURRENT_TEST" in env
        assert env["PYTEST_CURRENT_TEST"] == ""
        # Coverage file should be in cache dir
        assert ".cache" in env["COVERAGE_FILE"]
        assert "crackerjack" in env["COVERAGE_FILE"]

    def test_setup_coverage_env(self, tmp_path) -> None:
        """Test coverage environment setup."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)

        env = executor._setup_coverage_env()

        assert "COVERAGE_FILE" in env
        # Coverage file should be in cache dir
        assert ".cache" in env["COVERAGE_FILE"]
        assert "crackerjack" in env["COVERAGE_FILE"]


@pytest.mark.unit
class TestTestExecutorXdistFallback:
    """Test xdist fallback logic."""

    def test_should_try_xdist_fallback_disabled(self, tmp_path) -> None:
        """Test fallback when setting disabled."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)

        # Patch where load_settings is imported FROM (crackerjack.config)
        with patch("crackerjack.config.load_settings") as mock_load:
            from crackerjack.config.settings import CrackerjackSettings

            mock_settings = CrackerjackSettings()
            mock_settings.testing.xdist_fallback_to_sequential = False

            mock_load.return_value = mock_settings

            cmd = ["pytest", "-n", "4", "tests/"]
            result = executor._should_try_xdist_fallback(cmd)

            assert result is False

    def test_should_try_xdist_fallback_no_n_flag(self, tmp_path) -> None:
        """Test fallback when no -n flag."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)

        with patch("crackerjack.config.load_settings") as mock_load:
            from crackerjack.config.settings import CrackerjackSettings

            mock_settings = CrackerjackSettings()
            mock_settings.testing.xdist_fallback_to_sequential = True

            mock_load.return_value = mock_settings

            cmd = ["pytest", "-v"]
            result = executor._should_try_xdist_fallback(cmd)

            assert result is False

    def test_should_try_xdist_fallback_single_worker(self, tmp_path) -> None:
        """Test fallback with single worker."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)

        with patch("crackerjack.config.load_settings") as mock_load:
            from crackerjack.config.settings import CrackerjackSettings

            mock_settings = CrackerjackSettings()
            mock_settings.testing.xdist_fallback_to_sequential = True

            mock_load.return_value = mock_settings

            cmd = ["pytest", "-n", "1", "tests/"]
            result = executor._should_try_xdist_fallback(cmd)

            assert result is False

    def test_should_try_xdist_fallback_enabled(self, tmp_path) -> None:
        """Test fallback when conditions met."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)

        with patch("crackerjack.config.load_settings") as mock_load:
            from crackerjack.config.settings import CrackerjackSettings

            mock_settings = CrackerjackSettings()
            mock_settings.testing.xdist_fallback_to_sequential = True

            mock_load.return_value = mock_settings

            cmd = ["pytest", "-n", "4", "tests/"]
            result = executor._should_try_xdist_fallback(cmd)

            assert result is True

    def test_get_optimal_worker_count_from_cmd_auto(self, tmp_path) -> None:
        """Test getting worker count with 'auto'."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)
        cmd = ["pytest", "-n", "auto", "tests/"]

        count = executor._get_optimal_worker_count_from_cmd(cmd)

        assert count == 4  # Mocked value for 'auto'

    def test_get_optimal_worker_count_from_cmd_numeric(self, tmp_path) -> None:
        """Test getting worker count with number."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)
        cmd = ["pytest", "-n", "8", "tests/"]

        count = executor._get_optimal_worker_count_from_cmd(cmd)

        assert count == 8

    def test_get_optimal_worker_count_from_cmd_invalid(self, tmp_path) -> None:
        """Test getting worker count with invalid value."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)
        cmd = ["pytest", "-n", "invalid", "tests/"]

        count = executor._get_optimal_worker_count_from_cmd(cmd)

        assert count == 1  # Fallback

    def test_get_optimal_worker_count_from_cmd_no_n_flag(self, tmp_path) -> None:
        """Test getting worker count without -n flag."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)
        cmd = ["pytest", "-v"]

        count = executor._get_optimal_worker_count_from_cmd(cmd)

        assert count == 1

    def test_remove_xdist_from_cmd(self, tmp_path) -> None:
        """Test removing xdist from command."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)
        cmd = ["pytest", "-n", "4", "--dist=loadfile", "-v", "tests/"]

        result = executor._remove_xdist_from_cmd(cmd)

        assert "-n" not in result
        assert "4" not in result
        assert "--dist=loadfile" not in result
        assert "pytest" in result
        assert "-v" in result
        assert "tests/" in result

    def test_did_xdist_timeout_negative_returncode(self, tmp_path) -> None:
        """Test timeout detection with negative returncode."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)

        result = Mock()
        result.returncode = -9
        result.stdout = ""
        result.stderr = ""

        progress = Mock()
        progress.passed = 0
        progress.failed = 0
        progress.skipped = 0
        progress.errors = 0

        did_timeout = executor._did_xdist_timeout(result, progress)

        assert did_timeout is True

    def test_did_xdist_timeout_completed_tests(self, tmp_path) -> None:
        """Test timeout detection when tests completed."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)

        result = Mock()
        result.returncode = -9
        result.stdout = ""
        result.stderr = ""

        progress = Mock()
        progress.passed = 10
        progress.failed = 0
        progress.skipped = 0
        progress.errors = 0

        did_timeout = executor._did_xdist_timeout(result, progress)

        assert did_timeout is False

    def test_did_xdist_timeout_error_indicators(self, tmp_path) -> None:
        """Test timeout detection via error indicators."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)

        result = Mock()
        result.returncode = 1
        result.stdout = "worker crashed"
        result.stderr = ""

        progress = Mock()
        progress.passed = 0
        progress.failed = 0
        progress.skipped = 0
        progress.errors = 0

        did_timeout = executor._did_xdist_timeout(result, progress)

        assert did_timeout is True


@pytest.mark.unit
class TestTestExecutorOutputParsing:
    """Test test output parsing."""

    def test_handle_collection_completion(self, tmp_path) -> None:
        """Test handling collection completion."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)
        progress = Mock()
        progress.update = Mock()

        line = "collected 150 items"

        handled = executor._handle_collection_completion(line, progress)

        assert handled is True
        assert progress.update.called

    def test_handle_collection_with_tests(self, tmp_path) -> None:
        """Test handling collection with 'tests' keyword."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)
        progress = Mock()
        progress.update = Mock()

        line = "150 tests collected"

        handled = executor._handle_collection_completion(line, progress)

        assert handled is True

    def test_handle_session_start(self, tmp_path) -> None:
        """Test handling session start."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)
        progress = Mock()
        progress.update = Mock()
        progress.collection_status = ""

        line = "test session starts"

        handled = executor._handle_session_events(line, progress)

        assert handled is True
        # The implementation calls progress.update(), not direct assignment
        assert progress.update.called

    def test_handle_test_execution_passed(self, tmp_path) -> None:
        """Test handling passed test."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)
        progress = Mock()
        progress.passed = 0
        progress.update = Mock()

        # The implementation looks for " PASSED " (with spaces)
        line = "tests/test_example.py::test_func PASSED "

        handled = executor._handle_test_execution(line, progress)

        assert handled is True
        progress.update.assert_called()

    def test_handle_test_execution_failed(self, tmp_path) -> None:
        """Test handling failed test."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)
        progress = Mock()
        progress.failed = 0
        progress.update = Mock()

        # The implementation looks for " FAILED " (with spaces)
        line = "tests/test_example.py::test_func FAILED "

        handled = executor._handle_test_execution(line, progress)

        assert handled is True

    def test_handle_test_execution_skipped(self, tmp_path) -> None:
        """Test handling skipped test."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)
        progress = Mock()
        progress.skipped = 0
        progress.update = Mock()

        # The implementation looks for " SKIPPED " (with spaces)
        line = "tests/test_example.py::test_func SKIPPED "

        handled = executor._handle_test_execution(line, progress)

        assert handled is True

    def test_handle_test_execution_error(self, tmp_path) -> None:
        """Test handling error test."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)
        progress = Mock()
        progress.errors = 0
        progress.update = Mock()

        # The implementation looks for " ERROR " (with spaces)
        line = "tests/test_example.py::test_func ERROR "

        handled = executor._handle_test_execution(line, progress)

        assert handled is True

    def test_handle_running_test(self, tmp_path) -> None:
        """Test handling running test."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)
        progress = Mock()
        progress.update = Mock()

        # RUNNING tests have ":: " (with space after double colon) and "RUNNING" or "test_"
        line = "tests/test_example.py:: test_func RUNNING"

        handled = executor._handle_test_execution(line, progress)

        assert handled is True
        assert progress.update.called


@pytest.mark.unit
class TestTestExecutorCleanup:
    """Test cleanup and thread management."""

    def test_cleanup_threads_all_alive(self, tmp_path) -> None:

        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)

        # Create mock threads that are alive
        threads = []
        for _ in range(3):
            t = Mock()
            t.is_alive.return_value = True
            threads.append(t)

        executor._cleanup_threads(threads)

        for t in threads:
            t.join.assert_called_once_with(timeout=1.0)

    def test_cleanup_threads_mixed_states(self, tmp_path) -> None:
        """Test cleaning up threads with mixed states."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)

        # Create mock threads
        threads = []
        for i in range(3):
            t = Mock()
            t.is_alive.return_value = i % 2 == 0  # Every other thread alive
            threads.append(t)

        executor._cleanup_threads(threads)

        # Only alive threads should be joined
        assert threads[0].join.called
        assert not threads[1].join.called
        assert threads[2].join.called


@pytest.mark.unit
class TestTestExecutorProgressTracking:
    """Test progress tracking and callbacks."""

    def test_emit_ai_progress(self, tmp_path) -> None:
        """Test AI progress emission."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)

        progress = Mock()
        progress.total_tests = 100
        progress.passed = 50
        progress.failed = 2
        progress.skipped = 1
        progress.errors = 0
        progress.completed = 53
        progress.current_test = "test_example"
        progress.elapsed_time = 10.0
        progress.is_collecting = False
        progress.is_complete = False
        progress.collection_status = "Running tests"
        progress.eta_seconds = None

        callback = Mock()

        executor._emit_ai_progress(progress, callback)

        callback.assert_called_once()
        call_args = callback.call_args[0][0]
        assert call_args["type"] == "test_progress"
        assert call_args["total_tests"] == 100
        assert call_args["passed"] == 50
        assert call_args["failed"] == 2

    def test_emit_ai_progress_with_eta(self, tmp_path) -> None:
        """Test AI progress emission includes ETA when available."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)

        progress = Mock()
        progress.total_tests = 100
        progress.passed = 50
        progress.failed = 0
        progress.skipped = 0
        progress.errors = 0
        progress.completed = 50
        progress.current_test = "test_example"
        progress.elapsed_time = 10.0
        progress.is_collecting = False
        progress.is_complete = False
        progress.collection_status = "Running tests"
        progress.eta_seconds = 10.0

        callback = Mock()

        executor._emit_ai_progress(progress, callback)

        call_args = callback.call_args[0][0]
        assert "eta_seconds" in call_args
        assert call_args["eta_seconds"] == 10.0

    def test_emit_ai_progress_callback_exception(self, tmp_path) -> None:
        """Test AI progress emission handles callback exceptions."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)

        progress = Mock()
        progress.total_tests = 100
        progress.passed = 50
        progress.failed = 0
        progress.skipped = 0
        progress.errors = 0
        progress.completed = 50
        progress.current_test = "test_example"
        progress.elapsed_time = 10.0
        progress.is_collecting = False
        progress.is_complete = False
        progress.collection_status = "Running tests"
        progress.eta_seconds = None

        def failing_callback(data):
            raise ValueError("Test error")

        # Should not raise exception
        executor._emit_ai_progress(progress, failing_callback)


@pytest.mark.unit
class TestTestExecutorWaitForCompletion:
    """Test process completion waiting."""

    def test_wait_for_process_completion_success(self, tmp_path) -> None:
        """Test waiting for process that completes successfully."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)

        process = Mock()
        process.wait.return_value = 0
        process.returncode = 0

        returncode = executor._wait_for_process_completion(process, timeout=30)

        assert returncode == 0
        process.wait.assert_called_once_with(timeout=30)

    def test_wait_for_process_completion_timeout(self, tmp_path) -> None:
        """Test waiting for process that times out."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)

        process = Mock()
        process.wait.side_effect = subprocess.TimeoutExpired("pytest", 30)

        returncode = executor._wait_for_process_completion(process, timeout=30)

        assert returncode == -1
        process.terminate.assert_called_once()

    def test_wait_for_process_completion_nonzero_exit(self, tmp_path) -> None:
        """Test waiting for process that exits with error."""
        from rich.console import Console

        executor = TestExecutor(Console(), tmp_path)

        process = Mock()
        process.wait.return_value = 1
        process.returncode = 1

        returncode = executor._wait_for_process_completion(process, timeout=30)

        assert returncode == 1
        assert not process.terminate.called
