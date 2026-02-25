"""Unit tests for hook executor components."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from crackerjack.executors.hook_executor import HookExecutionResult, HookExecutor
from crackerjack.models.task import HookResult
from crackerjack.config.hooks import HookStrategy


class TestHookExecutionResult:
    """Test HookExecutionResult class."""

    def test_initialization(self) -> None:
        """Test HookExecutionResult initialization."""
        results = [
            HookResult(
                id="1",
                name="hook1",
                status="passed",
                duration=1.0,
                issues_found=[],
                stage="fast",
            ),
            HookResult(
                id="2",
                name="hook2",
                status="failed",
                duration=2.0,
                issues_found=["error"],
                stage="fast",
            ),
        ]

        result = HookExecutionResult(
            strategy_name="test",
            results=results,
            total_duration=6.0,
            success=False,
            cache_hits=5,
            cache_misses=3,
            performance_gain=25.0,
        )

        assert result.strategy_name == "test"
        assert len(result.results) == 2
        assert result.total_duration == 6.0
        assert result.success is False

    def test_failed_count(self) -> None:
        """Test failed_count property."""
        results = [
            HookResult(id="1", name="hook1", status="passed", duration=1.0, issues_found=[], stage="fast"),
            HookResult(id="2", name="hook2", status="failed", duration=2.0, issues_found=["error"], stage="fast"),
            HookResult(id="3", name="hook3", status="failed", duration=1.5, issues_found=["error2"], stage="fast"),
        ]

        result = HookExecutionResult(
            strategy_name="test",
            results=results,
            total_duration=6.0,
            success=False,
            cache_hits=5,
            cache_misses=3,
            performance_gain=25.0,
        )

        assert result.failed_count == 2

    def test_passed_count(self) -> None:
        """Test passed_count property."""
        results = [
            HookResult(id="1", name="hook1", status="passed", duration=1.0, issues_found=[], stage="fast"),
            HookResult(id="2", name="hook2", status="failed", duration=2.0, issues_found=["error"], stage="fast"),
            HookResult(id="3", name="hook3", status="passed", duration=1.5, issues_found=[], stage="fast"),
        ]

        result = HookExecutionResult(
            strategy_name="test",
            results=results,
            total_duration=6.0,
            success=False,
            cache_hits=5,
            cache_misses=3,
            performance_gain=25.0,
        )

        assert result.passed_count == 2

    def test_cache_hit_rate(self) -> None:
        """Test cache_hit_rate property."""
        result = HookExecutionResult(
            strategy_name="test",
            results=[],
            total_duration=6.0,
            success=False,
            cache_hits=6,
            cache_misses=4,
            performance_gain=25.0,
        )

        assert result.cache_hit_rate == 60.0  # 6/(6+4)*100

    def test_performance_summary(self) -> None:
        """Test performance_summary property."""
        results = [
            HookResult(id="1", name="hook1", status="passed", duration=1.0, issues_found=[], stage="fast"),
            HookResult(id="2", name="hook2", status="failed", duration=2.0, issues_found=["error"], stage="fast"),
        ]

        result = HookExecutionResult(
            strategy_name="test",
            results=results,
            total_duration=6.0,
            success=False,
            cache_hits=6,
            cache_misses=4,
            performance_gain=25.0,
        )

        summary = result.performance_summary
        assert summary["total_hooks"] == 2
        assert summary["passed"] == 1
        assert summary["failed"] == 1
        assert summary["cache_hit_rate_percent"] == 60.0
        # Note: performance_gain is a separate field, not in performance_summary


class TestHookExecutorInitialization:
    """Test HookExecutor initialization."""

    def test_initialization_defaults(self) -> None:
        """Test HookExecutor initialization with defaults."""
        console = MagicMock()
        pkg_path = Path("/tmp/test")

        executor = HookExecutor(console=console, pkg_path=pkg_path)

        assert executor.console is console
        assert executor.pkg_path == pkg_path
        assert executor._progress_callback is None
        assert executor._progress_start_callback is None
        assert executor._total_hooks == 0
        assert executor._started_hooks == 0
        assert executor._completed_hooks == 0

    def test_initialization_with_params(self) -> None:
        """Test HookExecutor initialization with parameters."""
        console = MagicMock()
        pkg_path = Path("/tmp/test")

        executor = HookExecutor(
            console=console,
            pkg_path=pkg_path,
            verbose=True,
            quiet=False,
            debug=True,
            use_incremental=True,
        )

        assert executor.console is console
        assert executor.pkg_path == pkg_path
        assert executor.verbose is True
        assert executor.debug is True
        assert executor.use_incremental is True


class TestHookExecutorMethods:
    """Test HookExecutor methods."""

    def test_set_progress_callbacks(self) -> None:
        """Test set_progress_callbacks method."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))
        start_cb = MagicMock()
        completed_cb = MagicMock()

        executor.set_progress_callbacks(
            started_cb=start_cb,
            completed_cb=completed_cb,
            total=5,
        )

        assert executor._progress_start_callback is start_cb
        assert executor._progress_callback is completed_cb
        assert executor._total_hooks == 5

    def test_execute_strategy(self) -> None:
        """Test execute_strategy method."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))
        strategy = MagicMock(spec=HookStrategy)
        strategy.name = "test"
        strategy.parallel = False
        strategy.hooks = []

        # Mock the internal methods
        with patch.object(executor, '_execute_hooks', return_value=[]), \
             patch.object(executor, '_create_execution_result') as mock_create_result:

            mock_create_result.return_value = HookExecutionResult(
                strategy_name="test",
                results=[],
                total_duration=0.0,
                success=True,
                cache_hits=0,
                cache_misses=0,
                performance_gain=0.0,
            )

            result = executor.execute_strategy(strategy)

            # Verify the result is as expected
            assert isinstance(result, HookExecutionResult)
            mock_create_result.assert_called_once()

    def test_execute_single_hook(self) -> None:
        """Test execute_single_hook method."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))
        hook = MagicMock()
        hook.name = "test-hook"
        hook.stage = MagicMock()
        hook.stage.value = "fast"

        # Mock the internal methods
        with patch.object(executor, '_run_hook_subprocess') as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = ""
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            result = executor.execute_single_hook(hook)

            # Verify the result
            mock_run.assert_called_once_with(hook)
            assert isinstance(result, HookResult)

    def test_is_concurrent(self) -> None:
        """Test is_concurrent method."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))
        strategy = MagicMock(spec=HookStrategy)

        # Set the parallel attribute on the strategy
        strategy.parallel = True
        strategy.hooks = [MagicMock(), MagicMock()]

        result = executor.is_concurrent(strategy)
        assert result is True

        # Test with parallel=False
        strategy.parallel = False
        result = executor.is_concurrent(strategy)
        assert result is False

        # Test with single hook
        strategy.parallel = True
        strategy.hooks = [MagicMock()]
        result = executor.is_concurrent(strategy)
        assert result is False


class TestHookExecutorInternalMethods:
    """Test HookExecutor internal methods."""

    def test_calculate_issues_count(self) -> None:
        """Test _calculate_issues_count method."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))

        # Test with issues
        result = executor._calculate_issues_count("failed", ["issue1", "issue2"])
        assert result == 2

        # Test with no issues
        result = executor._calculate_issues_count("passed", [])
        assert result == 0

        # Test with multiple issues
        result = executor._calculate_issues_count("failed", ["a", "b", "c", "d"])
        assert result == 4

    def test_create_timeout_result(self) -> None:
        """Test _create_timeout_result method."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))
        hook = MagicMock()
        hook.name = "test-hook"
        hook.stage = MagicMock()
        hook.stage.value = "fast"
        hook.timeout = 10.0

        # Mock _extract_issues_from_process_output since the implementation calls it without args
        with patch('time.time', return_value=5.0),              patch.object(executor, '_extract_issues_from_process_output', return_value=[]):
            result = executor._create_timeout_result(
                hook=hook,
                start_time=0.0,
                partial_output="partial output",
                partial_stderr="partial stderr",
            )

        assert result.id == "test-hook"
        assert result.name == "test-hook"
        assert result.status == "timeout"
        assert result.stage == "fast"
        assert result.is_timeout is True

    def test_create_error_result(self) -> None:
        """Test _create_error_result method."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))
        hook = MagicMock()
        hook.name = "test-hook"
        hook.stage = MagicMock()
        hook.stage.value = "fast"

        with patch('time.time', return_value=5.0):
            result = executor._create_error_result(
                hook=hook,
                start_time=0.0,
                error=Exception("Test error"),
            )

        assert result.id == "test-hook"
        assert result.name == "test-hook"
        assert result.status == "error"
        assert result.stage == "fast"
        assert "Test error" in result.error_message

    def test_determine_initial_status(self) -> None:
        """Test _determine_initial_status method."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))

        hook = MagicMock()
        hook.name = "test-hook"
        hook.is_formatting = False

        # Test with returncode 0
        result = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        status = executor._determine_initial_status(hook, result)
        assert status == "passed"

        # Test with returncode != 0
        result = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")
        status = executor._determine_initial_status(hook, result)
        assert status == "failed"

    def test_extract_issues_from_process_output(self) -> None:
        """Test _extract_issues_from_process_output method."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))

        hook = MagicMock()
        hook.name = "ruff-check"

        result = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="file1.py:10:1 error: something wrong\nfile2.py:5:2 warning: something else",
            stderr="",
        )

        # For regular tools with failed status
        issues = executor._extract_issues_from_process_output(hook, result, "failed")
        assert isinstance(issues, list)

        # For passed status
        issues = executor._extract_issues_from_process_output(hook, result, "passed")
        assert issues == []

    def test_parse_hook_output(self) -> None:
        """Test _parse_hook_output method."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))

        # Test with a known hook type
        result = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="All good",
            stderr="",
        )
        parsed = executor._parse_hook_output(result, "ruff-check")
        assert isinstance(parsed, dict)
        assert "files_processed" in parsed

        # Test with different hook type
        result = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="Error occurred",
            stderr="",
        )
        parsed = executor._parse_hook_output(result, "unknown-hook")
        assert isinstance(parsed, dict)
        assert "files_processed" in parsed

    def test_get_changed_files_for_hook(self) -> None:
        """Test _get_changed_files_for_hook method."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))
        hook = MagicMock()
        hook.name = "ruff-check"
        hook.accepts_file_paths = False

        # When use_incremental is False or hook doesn't accept file paths
        executor.use_incremental = False
        result = executor._get_changed_files_for_hook(hook)
        # Should return None when not using incremental mode
        assert result is None

    def test_create_run_hook_func(self) -> None:
        """Test _create_run_hook_func method."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))
        hook = MagicMock()
        hook.name = "test-hook"

        results: list[HookResult] = []
        other_hooks = [hook]

        func = executor._create_run_hook_func(results, other_hooks)

        # The function should be callable
        assert callable(func)

    def test_handle_retries(self) -> None:
        """Test _handle_retries method."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))
        results = [
            HookResult(id="1", name="hook1", status="passed", duration=1.0, issues_found=[], stage="fast"),
            HookResult(id="2", name="hook2", status="failed", duration=2.0, issues_found=["error"], stage="fast"),
        ]
        strategy = MagicMock(spec=HookStrategy)
        strategy.retry_policy = MagicMock()
        strategy.retry_policy.value = "none"

        # Mock the retry methods
        with patch.object(executor, '_retry_failed_hooks', return_value=results):
            result = executor._handle_retries(strategy, results)

            assert isinstance(result, list)

    def test_print_summary(self) -> None:
        """Test _print_summary method."""
        console = MagicMock()
        executor = HookExecutor(console=console, pkg_path=Path("/tmp"))
        results = [
            HookResult(id="1", name="hook1", status="passed", duration=1.0, issues_found=[], stage="fast"),
            HookResult(id="2", name="hook2", status="passed", duration=2.0, issues_found=[], stage="fast"),
        ]

        strategy = MagicMock(spec=HookStrategy)
        strategy.name = "fast"
        strategy.parallel = False
        strategy.hooks = [MagicMock(), MagicMock()]

        # Just ensure it doesn't crash with success=True
        executor._print_summary(strategy, results, success=True, performance_gain=5.0)

        # Verify console.print was called
        assert console.print.called


class TestHookExecutorEdgeCases:
    """Test HookExecutor edge cases and error conditions."""

    def test_execute_strategy_with_empty_strategy(self) -> None:
        """Test execute_strategy with empty strategy."""
        console = MagicMock()
        executor = HookExecutor(console=console, pkg_path=Path("/tmp"))
        strategy = MagicMock(spec=HookStrategy)
        strategy.name = "test"
        strategy.hooks = []  # Empty hooks list
        strategy.parallel = False

        result = executor.execute_strategy(strategy)

        # Should return a result even with no hooks
        assert isinstance(result, HookExecutionResult)

    def test_execute_single_hook_with_invalid_hook(self) -> None:
        """Test execute_single_hook with invalid hook."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))
        hook = MagicMock()
        hook.name = "test-hook"
        hook.stage = MagicMock()
        hook.stage.value = "fast"

        # Mock to simulate an error during execution
        with patch.object(executor, '_run_hook_subprocess', side_effect=Exception("Test error")):
            result = executor.execute_single_hook(hook)

            # Should handle the error gracefully and return an error result
            assert isinstance(result, HookResult)
            assert result.status == "error"
