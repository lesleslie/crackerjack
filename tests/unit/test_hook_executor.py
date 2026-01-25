"""Unit tests for hook executor components."""

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
        assert summary["performance_gain_percent"] == 25.0


class TestHookExecutorInitialization:
    """Test HookExecutor initialization."""

    def test_initialization_defaults(self) -> None:
        """Test HookExecutor initialization with defaults."""
        console = MagicMock()
        pkg_path = Path("/tmp/test")

        executor = HookExecutor(console=console, pkg_path=pkg_path)

        assert executor.console is console
        assert executor.pkg_path == pkg_path
        assert executor._progress_callbacks == {}
        assert executor._progress_total_hooks == 0
        assert executor._progress_completed_hooks == 0

    def test_initialization_with_params(self) -> None:
        """Test HookExecutor initialization with parameters."""
        console = MagicMock()
        pkg_path = Path("/tmp/test")
        progress_callbacks = {"start": MagicMock(), "update": MagicMock()}

        executor = HookExecutor(
            console=console,
            pkg_path=pkg_path,
            progress_callbacks=progress_callbacks,
        )

        assert executor.console is console
        assert executor.pkg_path == pkg_path
        assert executor._progress_callbacks == progress_callbacks


class TestHookExecutorMethods:
    """Test HookExecutor methods."""

    def test_set_progress_callbacks(self) -> None:
        """Test set_progress_callbacks method."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))
        callbacks = {"start": MagicMock(), "update": MagicMock()}

        executor.set_progress_callbacks(callbacks)

        assert executor._progress_callbacks == callbacks

    def test_execute_strategy(self) -> None:
        """Test execute_strategy method."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))
        strategy = MagicMock(spec=HookStrategy)

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

        # Mock the internal methods
        with patch.object(executor, '_run_hook_subprocess') as mock_run:
            mock_result = MagicMock()
            mock_run.return_value = mock_result

            result = executor.execute_single_hook(hook)

            # Verify the result
            mock_run.assert_called_once_with(hook)

    def test_is_concurrent(self) -> None:
        """Test is_concurrent method."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))
        strategy = MagicMock(spec=HookStrategy)

        # Set the concurrent attribute on the strategy
        strategy.concurrent = True

        result = executor.is_concurrent(strategy)
        assert result is True


class TestHookExecutorInternalMethods:
    """Test HookExecutor internal methods."""

    def test_calculate_issues_count(self) -> None:
        """Test _calculate_issues_count method."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))

        # Test with failed status and issues
        result = executor._calculate_issues_count("failed", ["issue1", "issue2"])
        assert result == 2

        # Test with passed status
        result = executor._calculate_issues_count("passed", ["issue1", "issue2"])
        assert result == 0

        # Test with timeout status
        result = executor._calculate_issues_count("timeout", ["issue1", "issue2"])
        assert result == 0

    def test_create_timeout_result(self) -> None:
        """Test _create_timeout_result method."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))
        hook = MagicMock()
        hook.id = "test-hook"
        hook.name = "Test Hook"
        hook.stage = "fast"

        result = executor._create_timeout_result(hook, 10.0)

        assert result.id == "test-hook"
        assert result.name == "Test Hook"
        assert result.status == "timeout"
        assert result.duration == 10.0
        assert result.stage == "fast"

    def test_create_error_result(self) -> None:
        """Test _create_error_result method."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))
        hook = MagicMock()
        hook.id = "test-hook"
        hook.name = "Test Hook"
        hook.stage = "fast"

        result = executor._create_error_result(hook, "Test error", 5.0)

        assert result.id == "test-hook"
        assert result.name == "Test Hook"
        assert result.status == "error"
        assert result.duration == 5.0
        assert result.stage == "fast"
        assert "Test error" in str(result.error)

    def test_determine_initial_status(self) -> None:
        """Test _determine_initial_status method."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))

        # Test with returncode 0
        result = executor._determine_initial_status(0, 10.0, 10.0)
        assert result == "passed"

        # Test with returncode != 0
        result = executor._determine_initial_status(1, 10.0, 10.0)
        assert result == "failed"

        # Test with timeout
        result = executor._determine_initial_status(0, 15.0, 10.0)  # elapsed > timeout
        assert result == "timeout"

    def test_extract_issues_from_process_output(self) -> None:
        """Test _extract_issues_from_process_output method."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))

        # Test with reporting tools
        output = "Issues found: 5 files need attention"
        result = executor._extract_issues_from_process_output(output, "ruff", True)
        # For reporting tools, it should parse differently
        assert isinstance(result, list)

        # Test with regular tools
        output = "file1.py:10:1 error: something wrong\nfile2.py:5:2 warning: something else"
        result = executor._extract_issues_from_process_output(output, "flake8", False)
        # For regular tools, it should parse differently
        assert isinstance(result, list)

    def test_parse_hook_output(self) -> None:
        """Test _parse_hook_output method."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))

        # Test with a known hook type
        result = executor._parse_hook_output(0, "All good", "ruff-check")
        assert isinstance(result, dict)
        assert "files_processed" in result

        # Test with different hook type
        result = executor._parse_hook_output(1, "Error occurred", "unknown-hook")
        assert isinstance(result, dict)
        assert "files_processed" in result

    def test_get_changed_files_for_hook(self) -> None:
        """Test _get_changed_files_for_hook method."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))
        hook = MagicMock()

        # Set up the hook to have files specified
        hook.files = ["file1.py", "file2.py"]
        hook.excludes = []
        hook.types = ["python"]

        result = executor._get_changed_files_for_hook(hook)

        # If hook has explicit files, should return those
        if hook.files:
            assert result is not None
            assert isinstance(result, list)
        else:
            # Otherwise, would return None or a list based on git changes
            assert result is None or isinstance(result, list)

    def test_create_run_hook_func(self) -> None:
        """Test _create_run_hook_func method."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))
        hook = MagicMock()

        func = executor._create_run_hook_func(hook)

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

        # Mock the retry methods
        with patch.object(executor, '_retry_failed_hooks', return_value=results):
            result = executor._handle_retries(results, strategy)

            assert isinstance(result, list)

    def test_print_summary(self) -> None:
        """Test _print_summary method."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))
        results = [
            HookResult(id="1", name="hook1", status="passed", duration=1.0, issues_found=[], stage="fast"),
            HookResult(id="2", name="hook2", status="failed", duration=2.0, issues_found=["error"], stage="fast"),
        ]

        # Just ensure it doesn't crash
        executor._print_summary(results, "fast", 5.0)


class TestHookExecutorEdgeCases:
    """Test HookExecutor edge cases and error conditions."""

    def test_execute_strategy_with_empty_strategy(self) -> None:
        """Test execute_strategy with empty strategy."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))
        strategy = MagicMock(spec=HookStrategy)
        strategy.hooks = []  # Empty hooks list

        result = executor.execute_strategy(strategy)

        # Should return a result even with no hooks
        assert isinstance(result, HookExecutionResult)

    def test_execute_single_hook_with_invalid_hook(self) -> None:
        """Test execute_single_hook with invalid hook."""
        executor = HookExecutor(console=MagicMock(), pkg_path=Path("/tmp"))
        hook = MagicMock()

        # Mock to simulate an error during execution
        with patch.object(executor, '_run_hook_subprocess', side_effect=Exception("Test error")):
            result = executor.execute_single_hook(hook)

            # Should handle the error gracefully and return an error result
            assert isinstance(result, HookResult)
            assert result.status == "error"
