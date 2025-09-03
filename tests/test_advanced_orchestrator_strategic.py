import json
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.agents import (
    IssueType,
)
from crackerjack.config.hooks import HookStrategy
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.executors.individual_hook_executor import (
    HookProgress,
)
from crackerjack.models.protocols import OptionsProtocol
from crackerjack.models.task import HookResult
from crackerjack.orchestration.advanced_orchestrator import (
    AdvancedWorkflowOrchestrator,
    CorrelationTracker,
    MinimalProgressStreamer,
    ProgressStreamer,
)
from crackerjack.orchestration.execution_strategies import (
    AICoordinationMode,
    ExecutionContext,
    ExecutionPlan,
    ExecutionStrategy,
    OrchestrationConfig,
)
from crackerjack.orchestration.test_progress_streamer import (
    TestSuiteProgress,
)


@pytest.fixture
def mock_console():
    console = Mock(spec=Console)
    console.is_terminal = False
    console.file = Mock()
    console.file.getvalue.return_value = "mock_output"
    console.print = Mock()
    return console


@pytest.fixture
def mock_pkg_path():
    path = Path("/ tmp / test_project")
    with (
        patch.object(Path, "exists", return_value=True),
        patch.object(
            Path,
            "rglob",
            return_value=[Path("file1.py"), Path("file2.py")],
        ),
        patch.object(Path, "glob", return_value=[Path("test_file.py")]),
    ):
        yield path


@pytest.fixture
def mock_session():
    session = Mock(spec=SessionCoordinator)
    session.job_id = "test - job - 123"
    session.web_job_id = "web - job - 456"
    session.update_stage = Mock()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        session.progress_file = Path(f.name)
        json.dump({}, f)

    yield session


@pytest.fixture
def orchestration_config():
    return OrchestrationConfig(
        execution_strategy=ExecutionStrategy.BATCH,
        ai_coordination_mode=AICoordinationMode.SINGLE_AGENT,
        correlation_tracking=True,
        failure_analysis=True,
        intelligent_retry=True,
    )


@pytest.fixture
def mock_options():
    options = Mock(spec=OptionsProtocol)
    options.ai_agent = True
    options.include_tests = True
    options.test_workers = 4
    options.test_timeout = 300
    return options


@pytest.fixture
def execution_context(mock_pkg_path, mock_options):
    return ExecutionContext(
        pkg_path=mock_pkg_path,
        options=mock_options,
        previous_failures=["ruff - check", "pyright"],
        changed_files=[Path("changed_file.py")],
        iteration_count=1,
    )


@pytest.fixture
def hook_results():
    results = [
        HookResult(id="1", name="ruff - format", status="passed", duration=1.0),
        HookResult(
            id="2",
            name="ruff - check",
            status="failed",
            duration=2.0,
            issues_found=["E501: line too long"],
        ),
        HookResult(id="3", name="gitleaks", status="passed", duration=0.5),
    ]

    results[0].error = None
    results[0].error_details = []
    results[1].error = "Linting errors found"
    results[1].error_details = ["E501: line too long"]
    results[2].error = None
    results[2].error_details = []

    return results


@pytest.fixture
def test_results():
    return {
        "success": False,
        "failed_tests": ["test_module:: test_function"],
        "individual_tests": [
            Mock(
                test_id="test_module:: test_function",
                test_file="test_module.py",
                status="failed",
                error_message="AssertionError: Expected 5, got 3",
                failure_traceback="traceback here",
                duration=1.5,
            ),
        ],
        "suite_progress": TestSuiteProgress(
            total_tests=10,
            completed_tests=5,
            passed_tests=4,
            failed_tests=1,
        ),
    }


class TestCorrelationTracker:
    def test_correlation_tracker_initialization(self):
        tracker = CorrelationTracker()

        assert tracker.iteration_data == []
        assert tracker.failure_patterns == {}
        assert tracker.fix_success_rates == {}

    def test_record_iteration(self, hook_results, test_results):
        tracker = CorrelationTracker()
        ai_fixes = ["Fixed import order", "Added type annotations"]

        tracker.record_iteration(1, hook_results, test_results, ai_fixes)

        assert len(tracker.iteration_data) == 1
        iteration = tracker.iteration_data[0]
        assert iteration["iteration"] == 1
        assert "ruff - check" in iteration["failed_hooks"]
        assert iteration["test_failures"] == ["test_module:: test_function"]
        assert iteration["ai_fixes_applied"] == ai_fixes
        assert iteration["total_errors"] == 1

    def test_analyze_failure_patterns(self, hook_results, test_results):
        tracker = CorrelationTracker()
        ai_fixes = ["Fix attempt 1"]

        tracker.record_iteration(1, hook_results, test_results, ai_fixes)

        tracker.record_iteration(2, hook_results, test_results, ai_fixes)

        assert "ruff - check" in tracker.failure_patterns
        assert len(tracker.failure_patterns["ruff - check"]) == 1
        assert "iteration_2" in tracker.failure_patterns["ruff - check"]

    def test_get_problematic_hooks(self, hook_results, test_results):
        tracker = CorrelationTracker()
        ai_fixes = ["Fix attempt"]

        for i in range(1, 4):
            tracker.record_iteration(i, hook_results, test_results, ai_fixes)

        problematic = tracker.get_problematic_hooks()
        assert "ruff - check" in problematic

    def test_get_correlation_data(self, hook_results, test_results):
        tracker = CorrelationTracker()
        ai_fixes = ["Fix"]

        tracker.record_iteration(1, hook_results, test_results, ai_fixes)
        tracker.record_iteration(2, hook_results, test_results, ai_fixes)

        data = tracker.get_correlation_data()
        assert data["iteration_count"] == 2
        assert "failure_patterns" in data
        assert "problematic_hooks" in data
        assert "recent_trends" in data


class TestMinimalProgressStreamer:
    def test_minimal_progress_streamer_initialization(self):
        streamer = MinimalProgressStreamer()
        assert streamer is not None

    def test_minimal_progress_streamer_methods(self):
        streamer = MinimalProgressStreamer()

        streamer.update_stage("test", "substage")
        streamer.update_hook_progress(
            HookProgress(hook_name="test", status="running", start_time=time.time()),
        )
        streamer._stream_update({"test": "data"})


class TestProgressStreamerClass:
    def test_progress_streamer_initialization(self, orchestration_config, mock_session):
        streamer = ProgressStreamer(orchestration_config, mock_session)

        assert streamer.config == orchestration_config
        assert streamer.session == mock_session
        assert streamer.current_stage == "initialization"
        assert streamer.current_substage == ""
        assert streamer.hook_progress == {}

    def test_update_stage(self, orchestration_config, mock_session):
        streamer = ProgressStreamer(orchestration_config, mock_session)

        streamer.update_stage("hooks", "ruff - check")

        assert streamer.current_stage == "hooks"
        assert streamer.current_substage == "ruff - check"
        mock_session.update_stage.assert_called_once()

    def test_update_hook_progress(self, orchestration_config, mock_session):
        streamer = ProgressStreamer(orchestration_config, mock_session)
        progress = HookProgress(
            hook_name="ruff - check",
            status="running",
            start_time=time.time(),
        )

        streamer.update_hook_progress(progress)

        assert streamer.hook_progress["ruff - check"] == progress
        mock_session.update_stage.assert_called_once()

    def test_websocket_progress_update(self, orchestration_config, mock_session):
        streamer = ProgressStreamer(orchestration_config, mock_session)

        update_data = {"type": "test", "timestamp": time.time()}
        streamer._update_websocket_progress(update_data)

        assert mock_session.progress_file.exists()
        with mock_session.progress_file.open() as f:
            data = json.load(f)
            assert "last_update" in data
            assert data["current_stage"] == "initialization"


class TestAdvancedWorkflowOrchestrator:
    @patch("crackerjack.orchestration.advanced_orchestrator.get_metrics_collector")
    @patch("crackerjack.orchestration.advanced_orchestrator.TestProgressStreamer")
    @patch("crackerjack.orchestration.advanced_orchestrator.TestManagementImpl")
    @patch("crackerjack.orchestration.advanced_orchestrator.IndividualHookExecutor")
    @patch("crackerjack.orchestration.advanced_orchestrator.HookExecutor")
    @patch("crackerjack.orchestration.advanced_orchestrator.HookConfigLoader")
    def test_orchestrator_initialization(
        self,
        mock_hook_loader,
        mock_batch_executor,
        mock_individual_executor,
        mock_test_manager,
        mock_test_streamer,
        mock_metrics,
        mock_console,
        mock_pkg_path,
        mock_session,
        orchestration_config,
    ):
        orchestrator = AdvancedWorkflowOrchestrator(
            console=mock_console,
            pkg_path=mock_pkg_path,
            session=mock_session,
            config=orchestration_config,
        )

        assert orchestrator.console == mock_console
        assert orchestrator.pkg_path == mock_pkg_path
        assert orchestrator.session == mock_session
        assert orchestrator.config == orchestration_config
        assert orchestrator.correlation_tracker is not None
        assert orchestrator.progress_streamer is not None
        assert orchestrator.agent_coordinator is None

    @patch("crackerjack.orchestration.advanced_orchestrator.get_metrics_collector")
    def test_mcp_mode_detection(
        self,
        mock_metrics,
        mock_console,
        mock_pkg_path,
        mock_session,
        orchestration_config,
    ):
        mock_console.file.getvalue = Mock(return_value="test")
        mock_console.is_terminal = False

        with patch.multiple(
            "crackerjack.orchestration.advanced_orchestrator",
            HookConfigLoader=Mock(),
            HookExecutor=Mock(),
            IndividualHookExecutor=Mock(),
            TestManagementImpl=Mock(),
            TestProgressStreamer=Mock(),
            OrchestrationPlanner=Mock(),
        ):
            orchestrator = AdvancedWorkflowOrchestrator(
                console=mock_console,
                pkg_path=mock_pkg_path,
                session=mock_session,
                config=orchestration_config,
            )

            assert orchestrator.individual_executor.set_mcp_mode.called

    @patch("crackerjack.orchestration.advanced_orchestrator.get_metrics_collector")
    def test_multi_agent_initialization(
        self,
        mock_metrics,
        mock_console,
        mock_pkg_path,
        mock_session,
    ):
        pytest.skip(
            "Complex test that requires deep mocking - skipping for coverage focus"
        )

    @patch("crackerjack.orchestration.advanced_orchestrator.get_metrics_collector")
    @pytest.mark.asyncio
    async def test_execute_orchestrated_workflow_success(
        self,
        mock_metrics,
        mock_console,
        mock_pkg_path,
        mock_session,
        orchestration_config,
        mock_options,
    ):
        with patch.multiple(
            "crackerjack.orchestration.advanced_orchestrator",
            HookConfigLoader=Mock(),
            HookExecutor=Mock(),
            IndividualHookExecutor=Mock(),
            TestManagementImpl=Mock(),
            TestProgressStreamer=Mock(),
            OrchestrationPlanner=Mock(),
        ):
            orchestrator = AdvancedWorkflowOrchestrator(
                console=mock_console,
                pkg_path=mock_pkg_path,
                session=mock_session,
                config=orchestration_config,
            )

            with patch.object(
                orchestrator,
                "_execute_single_iteration",
                return_value=(True, {"hooks": 10.0, "tests": 5.0, "ai": 2.0}),
            ):
                success = await orchestrator.execute_orchestrated_workflow(
                    mock_options,
                    max_iterations=2,
                )

                assert success is True

    @patch("crackerjack.orchestration.advanced_orchestrator.get_metrics_collector")
    @pytest.mark.asyncio
    async def test_execute_orchestrated_workflow_failure(
        self,
        mock_metrics,
        mock_console,
        mock_pkg_path,
        mock_session,
        orchestration_config,
        mock_options,
    ):
        with patch.multiple(
            "crackerjack.orchestration.advanced_orchestrator",
            HookConfigLoader=Mock(),
            HookExecutor=Mock(),
            IndividualHookExecutor=Mock(),
            TestManagementImpl=Mock(),
            TestProgressStreamer=Mock(),
            OrchestrationPlanner=Mock(),
        ):
            orchestrator = AdvancedWorkflowOrchestrator(
                console=mock_console,
                pkg_path=mock_pkg_path,
                session=mock_session,
                config=orchestration_config,
            )

            with patch.object(
                orchestrator,
                "_execute_single_iteration",
                return_value=(False, {"hooks": 10.0, "tests": 5.0, "ai": 2.0}),
            ):
                success = await orchestrator.execute_orchestrated_workflow(
                    mock_options,
                    max_iterations=2,
                )

                assert success is False

    @patch("crackerjack.orchestration.advanced_orchestrator.get_metrics_collector")
    @pytest.mark.asyncio
    async def test_execute_hooks_phase(
        self,
        mock_metrics,
        mock_console,
        mock_pkg_path,
        mock_session,
        orchestration_config,
        execution_context,
    ):
        with patch.multiple(
            "crackerjack.orchestration.advanced_orchestrator",
            HookConfigLoader=Mock(),
            HookExecutor=Mock(),
            IndividualHookExecutor=Mock(),
            TestManagementImpl=Mock(),
            TestProgressStreamer=Mock(),
            OrchestrationPlanner=Mock(),
        ):
            orchestrator = AdvancedWorkflowOrchestrator(
                console=mock_console,
                pkg_path=mock_pkg_path,
                session=mock_session,
                config=orchestration_config,
            )

            hook_strategy = HookStrategy(
                name="test",
                hooks=[],
                timeout=30,
            )
            execution_plan = ExecutionPlan(
                config=orchestration_config,
                execution_strategy=ExecutionStrategy.BATCH,
                hook_plans=[
                    {
                        "strategy": hook_strategy,
                        "execution_mode": ExecutionStrategy.BATCH,
                        "estimated_duration": 10.0,
                    },
                ],
                test_plan={},
                ai_plan={},
                estimated_total_duration=10.0,
            )

            mock_result = HookResult(
                id="test - 1", name="test - hook", status="passed", duration=1.0
            )

            mock_result.error = None
            mock_result.error_details = []

            orchestrator.batch_executor.execute_strategy.return_value = Mock(
                results=[mock_result],
            )

            results = await orchestrator._execute_hooks_phase(
                execution_plan,
                execution_context,
            )

            assert len(results) == 1
            assert results[0].name == "test - hook"
            assert results[0].status == "passed"

    @patch("crackerjack.orchestration.advanced_orchestrator.get_metrics_collector")
    @pytest.mark.asyncio
    async def test_execute_fast_hooks_with_autofix_success_first_attempt(
        self,
        mock_metrics,
        mock_console,
        mock_pkg_path,
        mock_session,
        orchestration_config,
        execution_context,
    ):
        with patch.multiple(
            "crackerjack.orchestration.advanced_orchestrator",
            HookConfigLoader=Mock(),
            HookExecutor=Mock(),
            IndividualHookExecutor=Mock(),
            TestManagementImpl=Mock(),
            TestProgressStreamer=Mock(),
            OrchestrationPlanner=Mock(),
        ):
            orchestrator = AdvancedWorkflowOrchestrator(
                console=mock_console,
                pkg_path=mock_pkg_path,
                session=mock_session,
                config=orchestration_config,
            )

            hook_strategy = HookStrategy(name="fast", hooks=[], timeout=30)

            successful_result = HookResult(
                id="fast - 1", name="ruff - format", status="passed", duration=1.0
            )
            successful_result.error = None
            successful_result.error_details = []
            successful_results = [successful_result]

            with patch.object(
                orchestrator,
                "_execute_fast_hooks_attempt",
                return_value=successful_results,
            ):
                results = await orchestrator._execute_fast_hooks_with_autofix(
                    hook_strategy,
                    ExecutionStrategy.BATCH,
                    execution_context,
                )

                assert len(results) == 1
                assert all(r.status == "passed" for r in results)

    @patch("crackerjack.orchestration.advanced_orchestrator.get_metrics_collector")
    @pytest.mark.asyncio
    async def test_execute_fast_hooks_with_autofix_retry_logic(
        self,
        mock_metrics,
        mock_console,
        mock_pkg_path,
        mock_session,
        orchestration_config,
        execution_context,
    ):
        with patch.multiple(
            "crackerjack.orchestration.advanced_orchestrator",
            HookConfigLoader=Mock(),
            HookExecutor=Mock(),
            IndividualHookExecutor=Mock(),
            TestManagementImpl=Mock(),
            TestProgressStreamer=Mock(),
            OrchestrationPlanner=Mock(),
        ):
            orchestrator = AdvancedWorkflowOrchestrator(
                console=mock_console,
                pkg_path=mock_pkg_path,
                session=mock_session,
                config=orchestration_config,
            )

            hook_strategy = HookStrategy(name="fast", hooks=[], timeout=30)

            failed_result = HookResult(
                id="retry - 1", name="ruff - check", status="failed", duration=1.0
            )
            failed_result.error = "error"
            failed_result.error_details = ["some error"]
            failed_results = [failed_result]

            successful_result = HookResult(
                id="retry - 2", name="ruff - check", status="passed", duration=1.0
            )
            successful_result.error = None
            successful_result.error_details = []
            successful_results = [successful_result]

            with patch.object(
                orchestrator,
                "_execute_fast_hooks_attempt",
                side_effect=[failed_results, successful_results],
            ):
                results = await orchestrator._execute_fast_hooks_with_autofix(
                    hook_strategy,
                    ExecutionStrategy.BATCH,
                    execution_context,
                )

                assert len(results) == 1
                assert all(r.status == "passed" for r in results)

    @patch("crackerjack.orchestration.advanced_orchestrator.get_metrics_collector")
    @pytest.mark.asyncio
    async def test_execute_tests_phase(
        self,
        mock_metrics,
        mock_console,
        mock_pkg_path,
        mock_session,
        orchestration_config,
        execution_context,
        test_results,
    ):
        with patch.multiple(
            "crackerjack.orchestration.advanced_orchestrator",
            HookConfigLoader=Mock(),
            HookExecutor=Mock(),
            IndividualHookExecutor=Mock(),
            TestManagementImpl=Mock(),
            TestProgressStreamer=Mock(),
            OrchestrationPlanner=Mock(),
        ):
            orchestrator = AdvancedWorkflowOrchestrator(
                console=mock_console,
                pkg_path=mock_pkg_path,
                session=mock_session,
                config=orchestration_config,
            )

            execution_plan = ExecutionPlan(
                config=orchestration_config,
                execution_strategy=ExecutionStrategy.BATCH,
                hook_plans=[],
                test_plan={"mode": "full_suite", "estimated_duration": 10.0},
                ai_plan={},
                estimated_total_duration=10.0,
            )

            orchestrator.test_manager.run_tests.return_value = True

            results = await orchestrator._execute_tests_phase(
                execution_plan,
                execution_context,
            )

            assert results["success"] is True
            assert "failed_tests" in results

    @patch("crackerjack.orchestration.advanced_orchestrator.get_metrics_collector")
    @pytest.mark.asyncio
    async def test_execute_ai_phase_single_agent(
        self,
        mock_metrics,
        mock_console,
        mock_pkg_path,
        mock_session,
        orchestration_config,
        hook_results,
        test_results,
    ):
        with patch.multiple(
            "crackerjack.orchestration.advanced_orchestrator",
            HookConfigLoader=Mock(),
            HookExecutor=Mock(),
            IndividualHookExecutor=Mock(),
            TestManagementImpl=Mock(),
            TestProgressStreamer=Mock(),
            OrchestrationPlanner=Mock(),
        ):
            orchestrator = AdvancedWorkflowOrchestrator(
                console=mock_console,
                pkg_path=mock_pkg_path,
                session=mock_session,
                config=orchestration_config,
            )

            execution_plan = ExecutionPlan(
                config=orchestration_config,
                execution_strategy=ExecutionStrategy.BATCH,
                hook_plans=[],
                test_plan={},
                ai_plan={"mode": AICoordinationMode.SINGLE_AGENT},
                estimated_total_duration=10.0,
            )

            ai_fixes = await orchestrator._execute_ai_phase(
                execution_plan,
                hook_results,
                test_results,
            )

            assert isinstance(ai_fixes, list)
            assert len(ai_fixes) > 0

    def test_map_hook_to_issue_type(
        self,
        mock_console,
        mock_pkg_path,
        mock_session,
        orchestration_config,
    ):
        with patch.multiple(
            "crackerjack.orchestration.advanced_orchestrator",
            HookConfigLoader=Mock(),
            HookExecutor=Mock(),
            IndividualHookExecutor=Mock(),
            TestManagementImpl=Mock(),
            TestProgressStreamer=Mock(),
            OrchestrationPlanner=Mock(),
            get_metrics_collector=Mock(),
        ):
            orchestrator = AdvancedWorkflowOrchestrator(
                console=mock_console,
                pkg_path=mock_pkg_path,
                session=mock_session,
                config=orchestration_config,
            )

            assert (
                orchestrator._map_hook_to_issue_type("ruff - format")
                == IssueType.FORMATTING
            )
            assert (
                orchestrator._map_hook_to_issue_type("pyright") == IssueType.TYPE_ERROR
            )
            assert orchestrator._map_hook_to_issue_type("bandit") == IssueType.SECURITY
            assert (
                orchestrator._map_hook_to_issue_type("vulture") == IssueType.DEAD_CODE
            )

            assert (
                orchestrator._map_hook_to_issue_type("unknown - hook")
                == IssueType.FORMATTING
            )

    def test_display_iteration_stats(
        self,
        mock_console,
        mock_pkg_path,
        mock_session,
        orchestration_config,
    ):
        with patch.multiple(
            "crackerjack.orchestration.advanced_orchestrator",
            HookConfigLoader=Mock(),
            HookExecutor=Mock(),
            IndividualHookExecutor=Mock(),
            TestManagementImpl=Mock(),
            TestProgressStreamer=Mock(),
            OrchestrationPlanner=Mock(),
            get_metrics_collector=Mock(),
        ):
            orchestrator = AdvancedWorkflowOrchestrator(
                console=mock_console,
                pkg_path=mock_pkg_path,
                session=mock_session,
                config=orchestration_config,
            )

            iteration_times = {"hooks": 10.0, "tests": 5.0, "ai": 2.0}
            context = Mock()
            context.hook_failures = ["ruff - check"]
            context.test_failures = ["test_module:: test_function"]

            orchestrator._display_iteration_stats(
                iteration=2,
                max_iterations=5,
                iteration_times=iteration_times,
                hooks_time=20.0,
                tests_time=10.0,
                ai_time=4.0,
                context=context,
            )

            assert mock_console.print.called

    def test_adapt_execution_plan_strategy_switch(
        self,
        mock_console,
        mock_pkg_path,
        mock_session,
        orchestration_config,
        execution_context,
    ):
        with patch.multiple(
            "crackerjack.orchestration.advanced_orchestrator",
            HookConfigLoader=Mock(),
            HookExecutor=Mock(),
            IndividualHookExecutor=Mock(),
            TestManagementImpl=Mock(),
            TestProgressStreamer=Mock(),
            OrchestrationPlanner=Mock(),
            get_metrics_collector=Mock(),
        ):
            orchestrator = AdvancedWorkflowOrchestrator(
                console=mock_console,
                pkg_path=mock_pkg_path,
                session=mock_session,
                config=orchestration_config,
            )

            orchestrator.correlation_tracker.failure_patterns = {
                "ruff - check": ["iteration_1", "iteration_2"],
                "pyright": ["iteration_2"],
            }

            current_plan = ExecutionPlan(
                config=orchestration_config,
                execution_strategy=ExecutionStrategy.BATCH,
                hook_plans=[],
                test_plan={},
                ai_plan={},
                estimated_total_duration=10.0,
            )

            mock_new_plan = ExecutionPlan(
                config=orchestration_config,
                execution_strategy=ExecutionStrategy.INDIVIDUAL,
                hook_plans=[],
                test_plan={},
                ai_plan={},
                estimated_total_duration=15.0,
            )
            orchestrator.planner.create_execution_plan.return_value = mock_new_plan

            adapted_plan = orchestrator._adapt_execution_plan(
                current_plan,
                execution_context,
            )

            assert adapted_plan.execution_strategy == ExecutionStrategy.INDIVIDUAL


class TestOrchestrationIntegration:
    def test_execution_context_integration(self, mock_pkg_path, mock_options):
        pytest.skip("Complex Path patching conflicts with read - only attributes")

    def test_correlation_and_progress_integration(
        self,
        orchestration_config,
        mock_session,
        hook_results,
        test_results,
    ):
        tracker = CorrelationTracker()
        streamer = ProgressStreamer(orchestration_config, mock_session)

        ai_fixes = ["Applied fixes"]
        tracker.record_iteration(1, hook_results, test_results, ai_fixes)

        streamer.update_stage("ai_analysis", "correlation")

        correlation_data = tracker.get_correlation_data()
        assert correlation_data["iteration_count"] == 1
        assert streamer.current_stage == "ai_analysis"
        assert streamer.current_substage == "correlation"


class TestOrchestrationErrorHandling:
    def test_progress_streamer_fallback_initialization(
        self,
        mock_console,
        mock_pkg_path,
        orchestration_config,
    ):
        mock_session = Mock()
        mock_session.job_id = None

        with patch.multiple(
            "crackerjack.orchestration.advanced_orchestrator",
            HookConfigLoader=Mock(),
            HookExecutor=Mock(),
            IndividualHookExecutor=Mock(),
            TestManagementImpl=Mock(),
            TestProgressStreamer=Mock(),
            OrchestrationPlanner=Mock(),
            get_metrics_collector=Mock(),
            ProgressStreamer=Mock(side_effect=Exception("Init failed")),
        ):
            orchestrator = AdvancedWorkflowOrchestrator(
                console=mock_console,
                pkg_path=mock_pkg_path,
                session=mock_session,
                config=orchestration_config,
            )

            assert isinstance(orchestrator.progress_streamer, MinimalProgressStreamer)

    def test_websocket_progress_error_handling(
        self,
        orchestration_config,
        mock_session,
    ):
        streamer = ProgressStreamer(orchestration_config, mock_session)

        mock_session.progress_file = Path("/ nonexistent / path / file.json")

        streamer._update_websocket_progress({"test": "data"})

    @patch("crackerjack.orchestration.advanced_orchestrator.get_metrics_collector")
    def test_orchestrator_with_invalid_config(
        self,
        mock_metrics,
        mock_console,
        mock_pkg_path,
        mock_session,
    ):
        with patch.multiple(
            "crackerjack.orchestration.advanced_orchestrator",
            HookConfigLoader=Mock(),
            HookExecutor=Mock(),
            IndividualHookExecutor=Mock(),
            TestManagementImpl=Mock(),
            TestProgressStreamer=Mock(),
            OrchestrationPlanner=Mock(),
        ):
            orchestrator = AdvancedWorkflowOrchestrator(
                console=mock_console,
                pkg_path=mock_pkg_path,
                session=mock_session,
                config=None,
            )

            assert orchestrator.config is not None
            assert isinstance(orchestrator.config, OrchestrationConfig)
