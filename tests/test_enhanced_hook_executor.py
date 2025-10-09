"""Tests for Phase 10.4.3: Enhanced Hook Executor Integration."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.config.hooks import HookDefinition, HookStage, SecurityLevel
from crackerjack.services.enhanced_hook_executor import (
    EnhancedHookExecutor,
    ExecutionSummary,
    HookResult,
)


class TestHookResult:
    """Test HookResult dataclass."""

    def test_hook_result_initialization(self):
        """Test HookResult can be initialized."""
        result = HookResult(
            hook_name="test-hook",
            success=True,
            output="All tests passed",
            error=None,
            execution_time=1.5,
            files_processed=10,
            files_cached=7,
            cache_hit_rate=70.0,
        )

        assert result.hook_name == "test-hook"
        assert result.success is True
        assert result.output == "All tests passed"
        assert result.error is None
        assert result.execution_time == 1.5
        assert result.files_processed == 10
        assert result.files_cached == 7
        assert result.cache_hit_rate == 70.0

    def test_hook_result_with_error(self):
        """Test HookResult with error."""
        result = HookResult(
            hook_name="test-hook",
            success=False,
            output="",
            error="Tool execution failed",
        )

        assert result.success is False
        assert result.error == "Tool execution failed"


class TestExecutionSummary:
    """Test ExecutionSummary dataclass."""

    def test_execution_summary_initialization(self):
        """Test ExecutionSummary can be initialized."""
        summary = ExecutionSummary(
            total_hooks=5,
            hooks_run=3,
            hooks_skipped=2,
            hooks_succeeded=2,
            hooks_failed=1,
            total_execution_time=10.5,
            filter_effectiveness=40.0,
            cache_effectiveness=70.0,
        )

        assert summary.total_hooks == 5
        assert summary.hooks_run == 3
        assert summary.hooks_skipped == 2
        assert summary.hooks_succeeded == 2
        assert summary.hooks_failed == 1
        assert summary.total_execution_time == 10.5
        assert summary.filter_effectiveness == 40.0
        assert summary.cache_effectiveness == 70.0


class TestEnhancedHookExecutor:
    """Test EnhancedHookExecutor class."""

    @pytest.fixture
    def executor(self, tmp_path: Path) -> EnhancedHookExecutor:
        """Create EnhancedHookExecutor with temp cache dir."""
        return EnhancedHookExecutor(cache_dir=tmp_path / "cache")

    @pytest.fixture
    def sample_hooks(self) -> list[HookDefinition]:
        """Create sample hook definitions."""
        return [
            HookDefinition(
                name="ruff-check",
                command=["uv", "run", "ruff", "check", "."],
                timeout=10,
                stage=HookStage.FAST,
                security_level=SecurityLevel.MEDIUM,
                use_precommit_legacy=False,
            ),
            HookDefinition(
                name="bandit",
                command=["uv", "run", "bandit", "-c", "pyproject.toml", "-r", "crackerjack"],
                timeout=19,
                stage=HookStage.COMPREHENSIVE,
                security_level=SecurityLevel.CRITICAL,
                use_precommit_legacy=False,
            ),
            HookDefinition(
                name="zuban",
                command=["uv", "run", "zuban", "check", "--config-file", "mypy.ini", "./crackerjack"],
                timeout=32,
                stage=HookStage.COMPREHENSIVE,
                security_level=SecurityLevel.CRITICAL,
                use_precommit_legacy=False,
            ),
        ]

    def test_executor_initialization(self, tmp_path: Path):
        """Test EnhancedHookExecutor initializes correctly."""
        executor = EnhancedHookExecutor(cache_dir=tmp_path / "cache")

        assert executor.cache_dir == tmp_path / "cache"
        assert executor.cache_dir.exists()
        assert executor.profiler is not None
        assert executor.executor is not None
        assert executor.filter is None  # Created during execute_hooks

    def test_executor_default_cache_dir(self):
        """Test EnhancedHookExecutor uses default cache_dir when not provided."""
        executor = EnhancedHookExecutor()

        expected_dir = Path.cwd() / ".crackerjack" / "cache"
        assert executor.cache_dir == expected_dir

    @patch("subprocess.run")
    def test_execute_hooks_no_filter(
        self,
        mock_run,
        executor: EnhancedHookExecutor,
        sample_hooks: list[HookDefinition],
    ):
        """Test execute_hooks with no filtering."""
        # Mock successful subprocess runs
        mock_run.return_value = Mock(returncode=0, stdout="OK", stderr="")

        summary = executor.execute_hooks(sample_hooks)

        assert summary.total_hooks == 3
        assert summary.hooks_run == 3
        assert summary.hooks_skipped == 0
        assert summary.hooks_succeeded == 3
        assert summary.hooks_failed == 0
        assert summary.filter_effectiveness == 0.0  # No filtering

    @patch("subprocess.run")
    def test_execute_hooks_with_tool_filter(
        self,
        mock_run,
        executor: EnhancedHookExecutor,
        sample_hooks: list[HookDefinition],
    ):
        """Test execute_hooks with --tool filter."""
        # Mock successful subprocess runs
        mock_run.return_value = Mock(returncode=0, stdout="OK", stderr="")

        summary = executor.execute_hooks(
            sample_hooks,
            tool_filter="ruff-check",
        )

        assert summary.total_hooks == 3
        assert summary.hooks_run == 1  # Only ruff-check
        assert summary.hooks_skipped == 2  # bandit and zuban skipped
        assert summary.hooks_succeeded == 1
        assert summary.hooks_failed == 0
        assert summary.filter_effectiveness == pytest.approx(66.67, abs=0.01)

    @patch("subprocess.run")
    def test_execute_hooks_with_failures(
        self,
        mock_run,
        executor: EnhancedHookExecutor,
        sample_hooks: list[HookDefinition],
    ):
        """Test execute_hooks with some failures."""
        # First call succeeds, second fails, third succeeds
        mock_run.side_effect = [
            Mock(returncode=0, stdout="OK", stderr=""),
            Mock(returncode=1, stdout="", stderr="Error in bandit"),
            Mock(returncode=0, stdout="OK", stderr=""),
        ]

        summary = executor.execute_hooks(sample_hooks)

        assert summary.total_hooks == 3
        assert summary.hooks_run == 3
        assert summary.hooks_succeeded == 2
        assert summary.hooks_failed == 1

    def test_execute_hooks_force_rerun(
        self,
        executor: EnhancedHookExecutor,
        sample_hooks: list[HookDefinition],
    ):
        """Test execute_hooks with force_rerun."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="OK", stderr="")

            # First run
            summary1 = executor.execute_hooks(sample_hooks)
            assert summary1.cache_effectiveness == 0.0  # No cache on first run

            # Second run with cache
            summary2 = executor.execute_hooks(sample_hooks)
            # Cache effectiveness would be > 0 if file-level caching was implemented

            # Third run with force_rerun (skip cache)
            summary3 = executor.execute_hooks(sample_hooks, force_rerun=True)
            assert summary3.cache_effectiveness == 0.0  # Cache bypassed

    def test_generate_report_basic(
        self,
        executor: EnhancedHookExecutor,
    ):
        """Test generate_report creates formatted output."""
        summary = ExecutionSummary(
            total_hooks=3,
            hooks_run=2,
            hooks_skipped=1,
            hooks_succeeded=2,
            hooks_failed=0,
            total_execution_time=5.5,
            filter_effectiveness=33.3,
            cache_effectiveness=50.0,
            results=[
                HookResult(
                    hook_name="ruff-check",
                    success=True,
                    output="OK",
                    execution_time=2.0,
                    cache_hit_rate=60.0,
                ),
                HookResult(
                    hook_name="bandit",
                    success=True,
                    output="OK",
                    execution_time=3.5,
                    cache_hit_rate=40.0,
                ),
            ],
        )

        report = executor.generate_report(summary)

        assert "# Hook Execution Summary" in report
        assert "**Total Hooks:** 3" in report
        assert "**Hooks Run:** 2" in report
        assert "**Hooks Skipped:** 1" in report
        assert "**Succeeded:** 2" in report
        assert "**Failed:** 0" in report
        assert "**Total Time:** 5.50s" in report
        assert "Filter Effectiveness" in report
        assert "33.3%" in report
        assert "Cache Effectiveness" in report
        assert "50.0%" in report

    def test_generate_report_with_failures(
        self,
        executor: EnhancedHookExecutor,
    ):
        """Test generate_report includes failure markers."""
        summary = ExecutionSummary(
            total_hooks=2,
            hooks_run=2,
            hooks_skipped=0,
            hooks_succeeded=1,
            hooks_failed=1,
            total_execution_time=5.0,
            results=[
                HookResult(
                    hook_name="ruff-check",
                    success=True,
                    output="OK",
                    execution_time=2.0,
                ),
                HookResult(
                    hook_name="bandit",
                    success=False,
                    output="",
                    error="Security issues found",
                    execution_time=3.0,
                ),
            ],
        )

        report = executor.generate_report(summary)

        assert "✅" in report  # Success marker
        assert "❌" in report  # Failure marker
        assert "ruff-check" in report
        assert "bandit" in report


class TestIntegration:
    """Integration tests for realistic execution scenarios."""

    @pytest.fixture
    def executor(self, tmp_path: Path) -> EnhancedHookExecutor:
        """Create executor with temp cache."""
        return EnhancedHookExecutor(cache_dir=tmp_path / "cache")

    def test_full_workflow_with_filtering(
        self,
        executor: EnhancedHookExecutor,
    ):
        """Test complete workflow: filter, execute, report."""
        hooks = [
            HookDefinition(
                name="ruff-check",
                command=["echo", "ruff-check"],  # Use echo for testing
                timeout=10,
                stage=HookStage.FAST,
                security_level=SecurityLevel.MEDIUM,
                use_precommit_legacy=False,
            ),
            HookDefinition(
                name="bandit",
                command=["echo", "bandit"],  # Use echo for testing
                timeout=19,
                stage=HookStage.COMPREHENSIVE,
                security_level=SecurityLevel.CRITICAL,
                use_precommit_legacy=False,
            ),
        ]

        # Execute with tool filter
        summary = executor.execute_hooks(
            hooks,
            tool_filter="ruff-check",
        )

        assert summary.hooks_run == 1
        assert summary.hooks_skipped == 1

        # Generate report
        report = executor.generate_report(summary)
        assert "ruff-check" in report
        assert "Filter Effectiveness" in report

    def test_profiler_integration(
        self,
        executor: EnhancedHookExecutor,
    ):
        """Test profiler tracks execution metrics."""
        hooks = [
            HookDefinition(
                name="ruff-check",
                command=["echo", "OK"],
                timeout=10,
                stage=HookStage.FAST,
                security_level=SecurityLevel.MEDIUM,
                use_precommit_legacy=False,
            ),
        ]

        # Execute multiple times to build profiler data
        for _ in range(3):
            executor.execute_hooks(hooks)

        # Check profiler has results
        assert "ruff-check" in executor.profiler.results
        profile_result = executor.profiler.results["ruff-check"]
        assert profile_result.runs == 3
        assert profile_result.mean_time > 0

    def test_time_savings_estimation(
        self,
        executor: EnhancedHookExecutor,
    ):
        """Test filter effectiveness calculation."""
        hooks = [
            HookDefinition(
                name=f"tool-{i}",
                command=["echo", "OK"],
                timeout=10,
                stage=HookStage.FAST,
                security_level=SecurityLevel.MEDIUM,
                use_precommit_legacy=False,
            )
            for i in range(5)
        ]

        # Run all hooks
        summary_all = executor.execute_hooks(hooks)
        assert summary_all.filter_effectiveness == 0.0

        # Run only one hook
        summary_filtered = executor.execute_hooks(
            hooks,
            tool_filter="tool-0",
        )
        assert summary_filtered.filter_effectiveness == 80.0  # 4 out of 5 filtered
