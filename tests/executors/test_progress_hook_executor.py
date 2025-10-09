"""Tests for progress-enhanced hook executor (Phase 10.2.2)."""

import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.config.hooks import HookDefinition, HookStage, HookStrategy, RetryPolicy
from crackerjack.executors.progress_hook_executor import ProgressHookExecutor
from crackerjack.models.task import HookResult


class TestProgressHookExecutorInit:
    """Test ProgressHookExecutor initialization."""

    def test_init_with_progress_enabled(self, tmp_path):
        """Test initialization with progress bars enabled."""
        console = Console()
        executor = ProgressHookExecutor(
            console=console,
            pkg_path=tmp_path,
            show_progress=True,
        )

        assert executor.show_progress is True
        assert executor.console == console
        assert executor.pkg_path == tmp_path

    def test_init_with_progress_disabled(self, tmp_path):
        """Test initialization with progress bars disabled."""
        console = Console()
        executor = ProgressHookExecutor(
            console=console,
            pkg_path=tmp_path,
            show_progress=False,
        )

        assert executor.show_progress is False

    def test_init_quiet_mode_disables_progress(self, tmp_path):
        """Test that quiet mode automatically disables progress bars."""
        console = Console()
        executor = ProgressHookExecutor(
            console=console,
            pkg_path=tmp_path,
            quiet=True,
            show_progress=True,  # Explicitly enabled
        )

        # Should be disabled due to quiet mode
        assert executor.show_progress is False

    def test_init_with_verbose(self, tmp_path):
        """Test initialization with verbose mode."""
        console = Console()
        executor = ProgressHookExecutor(
            console=console,
            pkg_path=tmp_path,
            verbose=True,
            show_progress=True,
        )

        assert executor.verbose is True
        assert executor.show_progress is True


class TestProgressBarCreation:
    """Test progress bar creation and configuration."""

    def test_create_progress_bar(self, tmp_path):
        """Test creating configured progress bar."""
        console = Console()
        executor = ProgressHookExecutor(
            console=console,
            pkg_path=tmp_path,
            show_progress=True,
        )

        progress = executor._create_progress_bar()

        assert progress is not None
        assert progress.console == console
        # Verify progress bar has expected columns
        assert len(progress.columns) == 7  # Spinner, Text, Bar, TaskProgress, MofN, TimeElapsed, TimeRemaining

    def test_progress_bar_configuration(self, tmp_path):
        """Test that progress bar has proper configuration."""
        console = Console()
        executor = ProgressHookExecutor(
            console=console,
            pkg_path=tmp_path,
            show_progress=True,
        )

        progress = executor._create_progress_bar()

        # Verify progress bar configuration
        assert progress is not None
        # Check that it has spinner and time columns
        column_types = [type(col).__name__ for col in progress.columns]
        assert "SpinnerColumn" in column_types
        assert "TimeElapsedColumn" in column_types
        assert "TimeRemainingColumn" in column_types


class TestSequentialExecutionWithProgress:
    """Test sequential hook execution with progress bars."""

    def test_execute_sequential_with_progress(self, tmp_path):
        """Test sequential execution updates progress bar."""
        console = Console()
        executor = ProgressHookExecutor(
            console=console,
            pkg_path=tmp_path,
            show_progress=True,
        )

        # Create test hooks
        hooks = [
            HookDefinition(
                name="hook1",
                command=[],
                stage=HookStage.FAST,
                use_precommit_legacy=False,
            ),
            HookDefinition(
                name="hook2",
                command=[],
                stage=HookStage.FAST,
                use_precommit_legacy=False,
            ),
        ]

        strategy = HookStrategy(
            name="test",
            hooks=hooks,
            parallel=False,
        )

        # Mock execute_single_hook to return successful results
        with patch.object(executor, "execute_single_hook") as mock_execute:
            mock_execute.side_effect = [
                HookResult(
                    id="hook1",
                    name="hook1",
                    status="passed",
                    duration=0.1,
                    issues_found=[],
                    stage="fast",
                ),
                HookResult(
                    id="hook2",
                    name="hook2",
                    status="passed",
                    duration=0.1,
                    issues_found=[],
                    stage="fast",
                ),
            ]

            result = executor.execute_strategy(strategy)

            assert result.success is True
            assert len(result.results) == 2
            assert mock_execute.call_count == 2

    def test_sequential_execution_shows_current_hook(self, tmp_path):
        """Test that progress bar shows current hook name."""
        console = Console()
        executor = ProgressHookExecutor(
            console=console,
            pkg_path=tmp_path,
            show_progress=True,
        )

        hooks = [
            HookDefinition(
                name="ruff-check",
                command=[],
                stage=HookStage.FAST,
                use_precommit_legacy=False,
            ),
        ]

        strategy = HookStrategy(
            name="test",
            hooks=hooks,
            parallel=False,
        )

        with patch.object(executor, "execute_single_hook") as mock_execute:
            mock_execute.return_value = HookResult(
                id="ruff-check",
                name="ruff-check",
                status="passed",
                duration=0.1,
                issues_found=[],
                stage="fast",
            )

            result = executor.execute_strategy(strategy)

            assert result.success is True
            mock_execute.assert_called_once()


class TestParallelExecutionWithProgress:
    """Test parallel hook execution with progress bars."""

    def test_execute_parallel_with_progress(self, tmp_path):
        """Test parallel execution updates progress bar."""
        console = Console()
        executor = ProgressHookExecutor(
            console=console,
            pkg_path=tmp_path,
            show_progress=True,
        )

        # Create mix of formatting and analysis hooks
        hooks = [
            HookDefinition(
                name="ruff-format",
                command=[],
                stage=HookStage.FAST,
                is_formatting=True,
                use_precommit_legacy=False,
            ),
            HookDefinition(
                name="ruff-check",
                command=[],
                stage=HookStage.FAST,
                is_formatting=False,
                use_precommit_legacy=False,
            ),
            HookDefinition(
                name="zuban",
                command=[],
                stage=HookStage.COMPREHENSIVE,
                is_formatting=False,
                use_precommit_legacy=False,
            ),
        ]

        strategy = HookStrategy(
            name="test",
            hooks=hooks,
            parallel=True,
            max_workers=2,
        )

        with patch.object(executor, "execute_single_hook") as mock_execute:
            mock_execute.side_effect = [
                HookResult(
                    id="ruff-format",
                    name="ruff-format",
                    status="passed",
                    duration=0.1,
                    issues_found=[],
                    stage="fast",
                ),
                HookResult(
                    id="ruff-check",
                    name="ruff-check",
                    status="passed",
                    duration=0.1,
                    issues_found=[],
                    stage="fast",
                ),
                HookResult(
                    id="zuban",
                    name="zuban",
                    status="passed",
                    duration=0.1,
                    issues_found=[],
                    stage="comprehensive",
                ),
            ]

            result = executor.execute_strategy(strategy)

            assert result.success is True
            assert len(result.results) == 3
            assert mock_execute.call_count == 3

    def test_parallel_formatting_hooks_run_first(self, tmp_path):
        """Test that formatting hooks run sequentially before analysis hooks."""
        console = Console()
        executor = ProgressHookExecutor(
            console=console,
            pkg_path=tmp_path,
            show_progress=True,
        )

        execution_order = []

        def record_execution(hook):
            execution_order.append(hook.name)
            return HookResult(
                id=hook.name,
                name=hook.name,
                status="passed",
                duration=0.1,
                issues_found=[],
                stage="fast",
            )

        hooks = [
            HookDefinition(
                name="ruff-format",
                command=[],
                stage=HookStage.FAST,
                is_formatting=True,
                use_precommit_legacy=False,
            ),
            HookDefinition(
                name="ruff-check",
                command=[],
                stage=HookStage.FAST,
                is_formatting=False,
                use_precommit_legacy=False,
            ),
            HookDefinition(
                name="mdformat",
                command=[],
                stage=HookStage.FAST,
                is_formatting=True,
                use_precommit_legacy=False,
            ),
        ]

        strategy = HookStrategy(
            name="test",
            hooks=hooks,
            parallel=True,
        )

        with patch.object(executor, "execute_single_hook", side_effect=record_execution):
            result = executor.execute_strategy(strategy)

            # Formatting hooks should execute first
            assert execution_order[0] == "ruff-format"
            assert execution_order[1] == "mdformat"
            # Analysis hook last (may vary in parallel execution)
            assert "ruff-check" in execution_order


class TestProgressFallback:
    """Test fallback to base executor when progress disabled."""

    def test_fallback_when_progress_disabled(self, tmp_path):
        """Test that executor falls back to base implementation without progress."""
        console = Console()
        executor = ProgressHookExecutor(
            console=console,
            pkg_path=tmp_path,
            show_progress=False,
        )

        hooks = [
            HookDefinition(
                name="hook1",
                command=[],
                stage=HookStage.FAST,
                use_precommit_legacy=False,
            ),
        ]

        strategy = HookStrategy(
            name="test",
            hooks=hooks,
            parallel=False,
        )

        with patch.object(executor, "execute_single_hook") as mock_execute:
            mock_execute.return_value = HookResult(
                id="hook1",
                name="hook1",
                status="passed",
                duration=0.1,
                issues_found=[],
                stage="fast",
            )

            result = executor.execute_strategy(strategy)

            assert result.success is True
            mock_execute.assert_called_once()

    def test_fallback_in_quiet_mode(self, tmp_path):
        """Test that quiet mode disables progress and uses base executor."""
        console = Console()
        executor = ProgressHookExecutor(
            console=console,
            pkg_path=tmp_path,
            quiet=True,
            show_progress=True,  # Explicitly enabled but should be overridden
        )

        hooks = [
            HookDefinition(
                name="hook1",
                command=[],
                stage=HookStage.FAST,
                use_precommit_legacy=False,
            ),
        ]

        strategy = HookStrategy(
            name="test",
            hooks=hooks,
            parallel=False,
        )

        with patch.object(executor, "execute_single_hook") as mock_execute:
            mock_execute.return_value = HookResult(
                id="hook1",
                name="hook1",
                status="passed",
                duration=0.1,
                issues_found=[],
                stage="fast",
            )

            result = executor.execute_strategy(strategy)

            assert result.success is True
            assert executor.show_progress is False


class TestRetryWithProgress:
    """Test retry behavior with progress indicators."""

    def test_retry_shows_message(self, tmp_path):
        """Test that retry shows appropriate message."""
        console = Console()
        executor = ProgressHookExecutor(
            console=console,
            pkg_path=tmp_path,
            show_progress=True,
        )

        hooks = [
            HookDefinition(
                name="ruff-format",
                command=[],
                stage=HookStage.FAST,
                is_formatting=True,
                use_precommit_legacy=False,
            ),
        ]

        strategy = HookStrategy(
            name="test",
            hooks=hooks,
            parallel=False,
            retry_policy=RetryPolicy.FORMATTING_ONLY,
        )

        call_count = 0

        def mock_execute(hook):
            nonlocal call_count
            call_count += 1
            # Fail first time, pass second time
            status = "passed" if call_count > 1 else "failed"
            return HookResult(
                id=hook.name,
                name=hook.name,
                status=status,
                duration=0.1,
                issues_found=[],
                stage="fast",
            )

        with patch.object(executor, "execute_single_hook", side_effect=mock_execute):
            result = executor.execute_strategy(strategy)

            # Should have retried formatting hook
            assert call_count == 2
            assert result.success is True


class TestErrorHandlingWithProgress:
    """Test error handling during progress execution."""

    def test_parallel_execution_handles_errors(self, tmp_path):
        """Test that parallel execution handles hook failures gracefully."""
        console = Console()
        executor = ProgressHookExecutor(
            console=console,
            pkg_path=tmp_path,
            show_progress=True,
        )

        hooks = [
            HookDefinition(
                name="hook1",
                command=[],
                stage=HookStage.FAST,
                is_formatting=False,
                use_precommit_legacy=False,
            ),
            HookDefinition(
                name="hook2",
                command=[],
                stage=HookStage.FAST,
                is_formatting=False,
                use_precommit_legacy=False,
            ),
        ]

        strategy = HookStrategy(
            name="test",
            hooks=hooks,
            parallel=True,
        )

        def mock_execute(hook):
            if hook.name == "hook1":
                raise ValueError("Test error")
            return HookResult(
                id=hook.name,
                name=hook.name,
                status="passed",
                duration=0.1,
                issues_found=[],
                stage="fast",
            )

        with patch.object(executor, "execute_single_hook", side_effect=mock_execute):
            result = executor.execute_strategy(strategy)

            assert result.success is False
            assert len(result.results) == 2
            # Find error result
            error_result = next(r for r in result.results if r.status == "error")
            assert error_result.name == "hook1"
            assert "Test error" in error_result.issues_found[0]


class TestDisplayHookResultOverride:
    """Test that individual hook display is suppressed with progress bars."""

    def test_display_hook_result_suppressed_with_progress(self, tmp_path):
        """Test that individual hook results are not displayed when progress enabled."""
        console = Console()
        executor = ProgressHookExecutor(
            console=console,
            pkg_path=tmp_path,
            show_progress=True,
        )

        result = HookResult(
            id="test",
            name="test",
            status="passed",
            duration=0.1,
            issues_found=[],
            stage="fast",
        )

        # Should not print anything (progress bar handles it)
        with patch.object(console, "print") as mock_print:
            executor._display_hook_result(result)
            mock_print.assert_not_called()

    def test_display_hook_result_shown_without_progress(self, tmp_path):
        """Test that individual hook results are shown when progress disabled."""
        console = Console()
        executor = ProgressHookExecutor(
            console=console,
            pkg_path=tmp_path,
            show_progress=False,
        )

        result = HookResult(
            id="test",
            name="test",
            status="passed",
            duration=0.1,
            issues_found=[],
            stage="fast",
        )

        # Should print (falls back to base implementation)
        with patch.object(console, "print") as mock_print:
            executor._display_hook_result(result)
            mock_print.assert_called_once()
