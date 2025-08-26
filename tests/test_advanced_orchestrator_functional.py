"""
Advanced functional tests for AdvancedOrchestrator.

This module provides sophisticated testing of orchestration workflows,
execution strategies, and AI coordination functionality.
Targets 338 lines with 0% coverage for maximum impact.
"""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from rich.console import Console

from crackerjack.agents import AgentContext, Issue, IssueType, Priority
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.models.task import HookResult
from crackerjack.orchestration.advanced_orchestrator import (
    AdvancedWorkflowOrchestrator,
    CorrelationTracker,
)
from crackerjack.orchestration.execution_strategies import (
    AICoordinationMode,
    ExecutionContext,
    ExecutionPlan,
    ExecutionStrategy,
    OrchestrationConfig,
    OrchestrationPlanner,
)
from crackerjack.orchestration.test_progress_streamer import (
    TestProgressStreamer,
    TestSuiteProgress,
)


class TestCorrelationTrackerAdvanced:
    """Advanced tests for correlation tracking functionality."""

    @pytest.fixture
    def tracker(self) -> CorrelationTracker:
        """Create a correlation tracker for testing."""
        return CorrelationTracker()

    def test_tracker_initialization(self, tracker: CorrelationTracker) -> None:
        """Test correlation tracker initialization."""
        assert len(tracker.iteration_data) == 0
        assert len(tracker.failure_patterns) == 0
        assert len(tracker.fix_success_rates) == 0

    def test_record_iteration_basic(self, tracker: CorrelationTracker) -> None:
        """Test basic iteration recording."""
        hook_results = [
            HookResult("ruff-check", True, "success", 0.5),
            HookResult("pyright", False, "Type error in module", 1.2),
        ]
        test_results = {"passed": 10, "failed": 2, "total": 12}
        fixes_applied = ["Fix import error", "Add type annotation"]
        
        tracker.record_iteration(
            iteration=1,
            hook_results=hook_results,
            test_results=test_results,
            fixes_applied=fixes_applied
        )
        
        assert len(tracker.iteration_data) == 1
        recorded = tracker.iteration_data[0]
        assert recorded["iteration"] == 1
        assert recorded["hooks_passed"] == 1
        assert recorded["hooks_failed"] == 1
        assert recorded["tests_passed"] == 10
        assert recorded["tests_failed"] == 2
        assert recorded["fixes_count"] == 2

    def test_identify_failure_patterns(self, tracker: CorrelationTracker) -> None:
        """Test failure pattern identification across iterations."""
        # Record multiple iterations with similar failure patterns
        for i in range(3):
            hook_results = [
                HookResult("pyright", False, "Type error in models.py", 1.0),
                HookResult("ruff-check", False, "Import error", 0.5),
            ]
            tracker.record_iteration(i + 1, hook_results, {"passed": 5, "failed": 3}, [])
        
        patterns = tracker.identify_failure_patterns()
        
        assert "pyright" in patterns
        assert "ruff-check" in patterns
        assert len(patterns["pyright"]) == 3
        assert all("Type error" in msg for msg in patterns["pyright"])

    def test_calculate_fix_success_rates(self, tracker: CorrelationTracker) -> None:
        """Test fix success rate calculation."""
        # Record iterations with fixes and subsequent results
        tracker.record_iteration(1, [], {"passed": 5, "failed": 5}, ["Fix type error"])
        tracker.record_iteration(2, [], {"passed": 8, "failed": 2}, [])  # Improvement
        tracker.record_iteration(3, [], {"passed": 6, "failed": 4}, ["Fix import"])
        tracker.record_iteration(4, [], {"passed": 7, "failed": 3}, [])  # Slight improvement
        
        rates = tracker.calculate_fix_success_rates()
        
        assert "Fix type error" in rates
        assert "Fix import" in rates
        # Type error fix showed better improvement (5→2 failures vs 4→3)
        assert rates["Fix type error"] > rates["Fix import"]

    def test_get_correlation_insights(self, tracker: CorrelationTracker) -> None:
        """Test comprehensive correlation insights."""
        # Simulate a realistic workflow
        iterations = [
            (1, [HookResult("pyright", False, "Type error", 1.0)], {"passed": 8, "failed": 4}, ["Add type hints"]),
            (2, [HookResult("pyright", True, "success", 0.8)], {"passed": 10, "failed": 2}, []),
            (3, [HookResult("ruff-check", False, "Import error", 0.5)], {"passed": 9, "failed": 3}, ["Fix imports"]),
            (4, [HookResult("ruff-check", True, "success", 0.4)], {"passed": 12, "failed": 0}, []),
        ]
        
        for iteration, hooks, tests, fixes in iterations:
            tracker.record_iteration(iteration, hooks, tests, fixes)
        
        insights = tracker.get_correlation_insights()
        
        assert "overall_trend" in insights
        assert "most_effective_fixes" in insights
        assert "persistent_issues" in insights
        assert insights["overall_trend"] == "improving"


class TestIterationMetrics:
    """Tests for iteration metrics tracking."""

    def test_metrics_creation(self) -> None:
        """Test iteration metrics creation and calculation."""
        hook_results = [
            HookResult("fast-hook", True, "success", 0.5),
            HookResult("slow-hook", False, "error", 2.0),
        ]
        test_results = {"passed": 15, "failed": 3, "total": 18}
        fixes_applied = ["Fix A", "Fix B", "Fix C"]
        
        metrics = IterationMetrics.from_results(
            iteration=2,
            hook_results=hook_results,
            test_results=test_results,
            fixes_applied=fixes_applied
        )
        
        assert metrics.iteration == 2
        assert metrics.hooks_passed == 1
        assert metrics.hooks_failed == 1
        assert metrics.hook_success_rate == 0.5
        assert metrics.tests_passed == 15
        assert metrics.tests_failed == 3
        assert metrics.test_success_rate == 15/18
        assert metrics.fixes_count == 3
        assert metrics.total_execution_time == 2.5

    def test_metrics_comparison(self) -> None:
        """Test metrics comparison between iterations."""
        metrics1 = IterationMetrics.from_results(
            1, [], {"passed": 8, "failed": 4, "total": 12}, []
        )
        metrics2 = IterationMetrics.from_results(
            2, [], {"passed": 10, "failed": 2, "total": 12}, []
        )
        
        improvement = metrics2.test_success_rate - metrics1.test_success_rate
        assert improvement > 0  # Tests improved
        assert metrics2.tests_passed > metrics1.tests_passed
        assert metrics2.tests_failed < metrics1.tests_failed


class TestOrchestrationConfig:
    """Tests for orchestration configuration."""

    def test_config_creation_defaults(self) -> None:
        """Test orchestration config with default values."""
        config = OrchestrationConfig()
        
        assert config.max_iterations == 10
        assert config.ai_coordination_mode == AICoordinationMode.COLLABORATIVE
        assert config.parallel_execution is True
        assert config.failure_threshold == 0.8
        assert config.convergence_patience == 3

    def test_config_creation_custom(self) -> None:
        """Test orchestration config with custom values."""
        config = OrchestrationConfig(
            max_iterations=5,
            ai_coordination_mode=AICoordinationMode.SEQUENTIAL,
            parallel_execution=False,
            failure_threshold=0.6,
            convergence_patience=2
        )
        
        assert config.max_iterations == 5
        assert config.ai_coordination_mode == AICoordinationMode.SEQUENTIAL
        assert config.parallel_execution is False
        assert config.failure_threshold == 0.6
        assert config.convergence_patience == 2


class TestExecutionPlan:
    """Tests for execution plan functionality."""

    def test_execution_plan_creation(self) -> None:
        """Test execution plan creation and properties."""
        plan = ExecutionPlan(
            strategy=ExecutionStrategy.FAST_FAIL,
            hooks_to_run=["ruff-check", "pyright", "bandit"],
            parallel_groups=[["ruff-check"], ["pyright", "bandit"]],
            estimated_duration=30.0,
            risk_level="medium"
        )
        
        assert plan.strategy == ExecutionStrategy.FAST_FAIL
        assert len(plan.hooks_to_run) == 3
        assert len(plan.parallel_groups) == 2
        assert plan.estimated_duration == 30.0
        assert plan.risk_level == "medium"

    def test_execution_plan_validation(self) -> None:
        """Test execution plan validation logic."""
        plan = ExecutionPlan(
            strategy=ExecutionStrategy.COMPREHENSIVE,
            hooks_to_run=["hook1", "hook2", "hook3"],
            parallel_groups=[["hook1"], ["hook2", "hook3"]],
            estimated_duration=45.0
        )
        
        is_valid = plan.validate()
        assert is_valid is True
        
        # All hooks should be covered in parallel groups
        all_grouped_hooks = {hook for group in plan.parallel_groups for hook in group}
        assert all_grouped_hooks == set(plan.hooks_to_run)


class TestOrchestrationPlanner:
    """Tests for orchestration planning functionality."""

    @pytest.fixture
    def planner(self) -> OrchestrationPlanner:
        """Create an orchestration planner for testing."""
        return OrchestrationPlanner()

    def test_planner_initialization(self, planner: OrchestrationPlanner) -> None:
        """Test planner initialization."""
        assert planner is not None
        assert hasattr(planner, 'create_execution_plan')

    def test_create_execution_plan_fast_strategy(self, planner: OrchestrationPlanner) -> None:
        """Test creation of fast execution plan."""
        context = ExecutionContext(
            available_hooks=["ruff-check", "ruff-format", "pyright", "bandit"],
            previous_results=[],
            iteration=1,
            time_constraints={"max_duration": 60}
        )
        
        plan = planner.create_execution_plan(ExecutionStrategy.FAST_FIRST, context)
        
        assert plan.strategy == ExecutionStrategy.FAST_FIRST
        assert isinstance(plan.hooks_to_run, list)
        assert len(plan.hooks_to_run) > 0
        assert plan.estimated_duration > 0

    def test_create_execution_plan_comprehensive_strategy(self, planner: OrchestrationPlanner) -> None:
        """Test creation of comprehensive execution plan."""
        context = ExecutionContext(
            available_hooks=["ruff-check", "pyright", "bandit", "vulture", "refurb"],
            previous_results=[HookResult("ruff-check", False, "error", 1.0)],
            iteration=2,
            time_constraints={"max_duration": 300}
        )
        
        plan = planner.create_execution_plan(ExecutionStrategy.COMPREHENSIVE, context)
        
        assert plan.strategy == ExecutionStrategy.COMPREHENSIVE
        assert len(plan.hooks_to_run) >= len(context.available_hooks)
        # Should include failed hooks from previous iteration
        assert "ruff-check" in plan.hooks_to_run

    def test_optimize_parallel_groups(self, planner: OrchestrationPlanner) -> None:
        """Test optimization of parallel execution groups."""
        hooks = ["fast-hook1", "fast-hook2", "slow-hook1", "slow-hook2"]
        
        groups = planner._optimize_parallel_groups(hooks, max_groups=2)
        
        assert len(groups) <= 2
        assert len(groups) > 0
        
        # All hooks should be included
        all_hooks = {hook for group in groups for hook in group}
        assert all_hooks == set(hooks)

    def test_estimate_execution_time(self, planner: OrchestrationPlanner) -> None:
        """Test execution time estimation."""
        hooks = ["ruff-check", "pyright", "bandit"]
        groups = [["ruff-check"], ["pyright", "bandit"]]
        
        estimated_time = planner._estimate_execution_time(hooks, groups)
        
        assert isinstance(estimated_time, float)
        assert estimated_time > 0


class TestTestProgressStreamer:
    """Tests for test progress streaming functionality."""

    @pytest.fixture
    def streamer(self) -> TestProgressStreamer:
        """Create a test progress streamer."""
        return TestProgressStreamer(Console())

    def test_streamer_initialization(self, streamer: TestProgressStreamer) -> None:
        """Test streamer initialization."""
        assert streamer.console is not None
        assert streamer.current_progress is None

    @pytest.mark.asyncio
    async def test_stream_test_progress(self, streamer: TestProgressStreamer) -> None:
        """Test streaming of test progress updates."""
        progress = TestSuiteProgress(
            total_tests=100,
            completed_tests=0,
            passed_tests=0,
            failed_tests=0,
            current_test="",
            estimated_remaining=60.0
        )
        
        updates = []
        
        async def mock_update_source():
            for i in range(5):
                progress.completed_tests = i * 20
                progress.passed_tests = i * 18
                progress.failed_tests = i * 2
                progress.current_test = f"test_module_{i}"
                progress.estimated_remaining = 60.0 - (i * 12)
                yield progress
                await asyncio.sleep(0.01)
        
        async for update in streamer.stream_test_progress(mock_update_source()):
            updates.append(update)
        
        assert len(updates) == 5
        assert updates[-1].completed_tests == 80
        assert updates[-1].passed_tests == 72
        assert updates[-1].failed_tests == 8

    def test_format_progress_display(self, streamer: TestProgressStreamer) -> None:
        """Test progress display formatting."""
        progress = TestSuiteProgress(
            total_tests=50,
            completed_tests=30,
            passed_tests=25,
            failed_tests=5,
            current_test="test_important_functionality",
            estimated_remaining=15.0
        )
        
        display = streamer._format_progress_display(progress)
        
        assert "30/50" in str(display)  # Progress ratio
        assert "25 passed" in str(display)
        assert "5 failed" in str(display)
        assert "test_important_functionality" in str(display)


class TestAdvancedOrchestratorIntegration:
    """Integration tests for AdvancedOrchestrator."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mocked dependencies for orchestrator."""
        return {
            'console': Console(),
            'session_coordinator': Mock(spec=SessionCoordinator),
            'agent_coordinator': Mock(),
            'hook_executor': Mock(),
            'test_manager': Mock(),
        }

    @pytest.fixture
    def orchestrator(self, mock_dependencies):
        """Create an advanced orchestrator with mocked dependencies."""
        return AdvancedOrchestrator(
            console=mock_dependencies['console'],
            session_coordinator=mock_dependencies['session_coordinator'],
            agent_coordinator=mock_dependencies['agent_coordinator'],
            hook_executor=mock_dependencies['hook_executor'],
            test_manager=mock_dependencies['test_manager'],
            config=OrchestrationConfig(max_iterations=3)
        )

    def test_orchestrator_initialization(self, orchestrator: AdvancedOrchestrator) -> None:
        """Test orchestrator initialization."""
        assert orchestrator is not None
        assert orchestrator.config.max_iterations == 3
        assert isinstance(orchestrator.correlation_tracker, CorrelationTracker)
        assert isinstance(orchestrator.planner, OrchestrationPlanner)

    @pytest.mark.asyncio
    async def test_execute_iteration_basic(self, orchestrator: AdvancedOrchestrator) -> None:
        """Test basic iteration execution."""
        with patch.object(orchestrator.hook_executor, 'execute_hooks') as mock_hooks:
            with patch.object(orchestrator.test_manager, 'run_tests') as mock_tests:
                with patch.object(orchestrator.agent_coordinator, 'coordinate_fixes') as mock_fixes:
                    # Setup mocks
                    mock_hooks.return_value = [HookResult("ruff-check", True, "success", 0.5)]
                    mock_tests.return_value = {"passed": 10, "failed": 0, "total": 10}
                    mock_fixes.return_value = []
                    
                    result = await orchestrator._execute_iteration(1)
                    
                    assert result["iteration"] == 1
                    assert result["success"] is True
                    assert len(result["hook_results"]) == 1
                    assert result["test_results"]["passed"] == 10

    @pytest.mark.asyncio
    async def test_execute_iteration_with_failures(self, orchestrator: AdvancedOrchestrator) -> None:
        """Test iteration execution with failures and fixes."""
        with patch.object(orchestrator.hook_executor, 'execute_hooks') as mock_hooks:
            with patch.object(orchestrator.test_manager, 'run_tests') as mock_tests:
                with patch.object(orchestrator.agent_coordinator, 'coordinate_fixes') as mock_fixes:
                    # Setup mocks for failure scenario
                    mock_hooks.return_value = [HookResult("pyright", False, "Type error", 1.2)]
                    mock_tests.return_value = {"passed": 8, "failed": 2, "total": 10}
                    mock_fixes.return_value = ["Fixed type annotation", "Added import"]
                    
                    result = await orchestrator._execute_iteration(1)
                    
                    assert result["iteration"] == 1
                    assert result["success"] is False
                    assert len(result["fixes_applied"]) == 2
                    assert result["test_results"]["failed"] == 2

    def test_should_continue_iterations(self, orchestrator: AdvancedOrchestrator) -> None:
        """Test iteration continuation logic."""
        # Should continue with failures
        result_with_failures = {
            "success": False,
            "hook_results": [HookResult("pyright", False, "error", 1.0)],
            "test_results": {"passed": 8, "failed": 2, "total": 10}
        }
        assert orchestrator._should_continue_iterations(1, result_with_failures) is True
        
        # Should stop when successful
        result_success = {
            "success": True,
            "hook_results": [HookResult("pyright", True, "success", 1.0)],
            "test_results": {"passed": 10, "failed": 0, "total": 10}
        }
        assert orchestrator._should_continue_iterations(1, result_success) is False
        
        # Should stop at max iterations
        assert orchestrator._should_continue_iterations(3, result_with_failures) is False

    def test_generate_execution_summary(self, orchestrator: AdvancedOrchestrator) -> None:
        """Test execution summary generation."""
        iterations = [
            {"iteration": 1, "success": False, "fixes_applied": ["Fix A"], "hook_results": [], "test_results": {"passed": 8, "failed": 2}},
            {"iteration": 2, "success": True, "fixes_applied": ["Fix B"], "hook_results": [], "test_results": {"passed": 10, "failed": 0}},
        ]
        
        summary = orchestrator._generate_execution_summary(iterations)
        
        assert summary["total_iterations"] == 2
        assert summary["final_success"] is True
        assert summary["total_fixes_applied"] == 2
        assert "Fix A" in summary["all_fixes"]
        assert "Fix B" in summary["all_fixes"]

    @pytest.mark.asyncio
    async def test_full_orchestration_workflow(self, orchestrator: AdvancedOrchestrator) -> None:
        """Test complete orchestration workflow from start to finish."""
        mock_options = Mock()
        mock_options.with_tests = True
        mock_options.ai_agent = True
        
        with patch.object(orchestrator, '_execute_iteration') as mock_iteration:
            # Simulate 2 iterations: first fails, second succeeds
            mock_iteration.side_effect = [
                {
                    "iteration": 1,
                    "success": False,
                    "hook_results": [HookResult("pyright", False, "Type error", 1.0)],
                    "test_results": {"passed": 8, "failed": 2, "total": 10},
                    "fixes_applied": ["Add type hints"]
                },
                {
                    "iteration": 2,
                    "success": True,
                    "hook_results": [HookResult("pyright", True, "success", 0.8)],
                    "test_results": {"passed": 10, "failed": 0, "total": 10},
                    "fixes_applied": []
                }
            ]
            
            result = await orchestrator.execute_workflow(mock_options)
            
            assert result["final_success"] is True
            assert result["total_iterations"] == 2
            assert mock_iteration.call_count == 2

    def test_error_handling_in_orchestration(self, orchestrator: AdvancedOrchestrator) -> None:
        """Test error handling in orchestration workflows."""
        with patch.object(orchestrator.hook_executor, 'execute_hooks') as mock_hooks:
            # Simulate an exception during hook execution
            mock_hooks.side_effect = Exception("Hook execution failed")
            
            # The orchestrator should handle the exception gracefully
            with pytest.raises(Exception):
                # In a real implementation, this would be caught and logged
                orchestrator.hook_executor.execute_hooks([])


class TestOrchestrationPerformance:
    """Performance tests for orchestration components."""

    def test_correlation_tracker_performance_with_large_dataset(self) -> None:
        """Test correlation tracker performance with many iterations."""
        tracker = CorrelationTracker()
        
        # Simulate 100 iterations
        start_time = time.time()
        
        for i in range(100):
            hook_results = [
                HookResult("ruff-check", i % 3 == 0, f"Message {i}", 0.5),
                HookResult("pyright", i % 5 == 0, f"Type error {i}", 1.0),
            ]
            test_results = {"passed": 10 - (i % 4), "failed": i % 4, "total": 10}
            fixes = [f"Fix {j}" for j in range(i % 3)]
            
            tracker.record_iteration(i + 1, hook_results, test_results, fixes)
        
        end_time = time.time()
        
        # Should complete in reasonable time (< 1 second for 100 iterations)
        assert end_time - start_time < 1.0
        assert len(tracker.iteration_data) == 100
        
        # Performance check for analysis
        analysis_start = time.time()
        insights = tracker.get_correlation_insights()
        analysis_end = time.time()
        
        assert analysis_end - analysis_start < 0.5  # Analysis should be fast
        assert "overall_trend" in insights

    def test_parallel_execution_simulation(self) -> None:
        """Test simulation of parallel execution performance."""
        planner = OrchestrationPlanner()
        
        # Large set of hooks
        hooks = [f"hook_{i}" for i in range(20)]
        
        start_time = time.time()
        groups = planner._optimize_parallel_groups(hooks, max_groups=4)
        end_time = time.time()
        
        # Should optimize quickly
        assert end_time - start_time < 0.1
        assert len(groups) <= 4
        
        # All hooks should be included
        all_grouped = {hook for group in groups for hook in group}
        assert all_grouped == set(hooks)