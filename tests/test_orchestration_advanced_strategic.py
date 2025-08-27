"""Strategic tests for AdvancedWorkflowOrchestrator to boost coverage from 11.52% to target 42%.

This test file targets crackerjack/orchestration/advanced_orchestrator.py (338 statements, 0% coverage).
Expected impact: ~1.5% overall coverage increase with 60-80% module coverage.

Focus areas:
1. CorrelationTracker - failure pattern analysis and problematic hook detection
2. ProgressStreamer - WebSocket progress updates and stage management
3. AdvancedWorkflowOrchestrator - orchestrated workflow execution
4. Multi-agent system initialization and coordination
5. Fast hooks with autofix cycles
6. AI analysis and batch fixing
7. Execution plan adaptation and strategy switching
"""

from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.agents import (
    IssueType,
)
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.models.protocols import OptionsProtocol
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


def create_mock_hook_result(
    name: str,
    status: str,
    error: str | None = None,
    error_details: list[str] | None = None,
):
    """Helper to create mock hook results that match advanced_orchestrator expectations."""
    hook_result = Mock()
    hook_result.name = name
    hook_result.status = status
    hook_result.error = error
    hook_result.error_details = error_details or []
    return hook_result


class TestCorrelationTracker:
    """Test correlation tracking for failure pattern analysis."""

    @pytest.fixture
    def correlation_tracker(self):
        return CorrelationTracker()

    @pytest.fixture
    def hook_results(self):
        """Sample hook results for testing."""
        return [
            create_mock_hook_result("ruff-format", "passed"),
            create_mock_hook_result(
                "ruff-check", "failed", "Import error", ["Missing import statement"]
            ),
            create_mock_hook_result(
                "pyright",
                "failed",
                "Type error",
                ["Missing type annotation", "Type mismatch"],
            ),
        ]

    @pytest.fixture
    def test_results(self):
        """Sample test results for testing."""
        return {
            "success": False,
            "failed_tests": ["test_module.py::test_function"],
        }

    def test_initialization(self, correlation_tracker):
        """Test CorrelationTracker initialization."""
        assert correlation_tracker.iteration_data == []
        assert correlation_tracker.failure_patterns == {}
        assert correlation_tracker.fix_success_rates == {}

    def test_record_single_iteration(
        self, correlation_tracker, hook_results, test_results
    ):
        """Test recording a single iteration."""
        ai_fixes = ["Fixed import error", "Added type annotation"]

        correlation_tracker.record_iteration(1, hook_results, test_results, ai_fixes)

        assert len(correlation_tracker.iteration_data) == 1
        data = correlation_tracker.iteration_data[0]

        assert data["iteration"] == 1
        assert data["failed_hooks"] == ["ruff-check", "pyright"]
        assert data["test_failures"] == ["test_module.py::test_function"]
        assert data["ai_fixes_applied"] == ai_fixes
        assert data["total_errors"] == 3  # 1 + 2 error_details from failed hooks
        assert isinstance(data["timestamp"], float)

    def test_failure_pattern_analysis(
        self, correlation_tracker, hook_results, test_results
    ):
        """Test failure pattern analysis across multiple iterations."""
        ai_fixes = ["Fix attempt"]

        # Record first iteration
        correlation_tracker.record_iteration(1, hook_results, test_results, ai_fixes)

        # Record second iteration with same failures
        correlation_tracker.record_iteration(2, hook_results, test_results, ai_fixes)

        # Check patterns are detected
        assert "ruff-check" in correlation_tracker.failure_patterns
        assert "pyright" in correlation_tracker.failure_patterns
        assert len(correlation_tracker.failure_patterns["ruff-check"]) == 1
        assert "iteration_2" in correlation_tracker.failure_patterns["ruff-check"]

    def test_get_problematic_hooks(
        self, correlation_tracker, hook_results, test_results
    ):
        """Test identification of problematic hooks."""
        ai_fixes = []

        # Record multiple iterations with recurring failures
        correlation_tracker.record_iteration(1, hook_results, test_results, ai_fixes)
        correlation_tracker.record_iteration(2, hook_results, test_results, ai_fixes)
        correlation_tracker.record_iteration(3, hook_results, test_results, ai_fixes)

        problematic = correlation_tracker.get_problematic_hooks()
        assert "ruff-check" in problematic
        assert "pyright" in problematic

    def test_get_correlation_data(
        self, correlation_tracker, hook_results, test_results
    ):
        """Test correlation data extraction."""
        ai_fixes = ["Applied fix"]
        correlation_tracker.record_iteration(1, hook_results, test_results, ai_fixes)

        data = correlation_tracker.get_correlation_data()

        assert data["iteration_count"] == 1
        assert "failure_patterns" in data
        assert "problematic_hooks" in data
        assert "recent_trends" in data
        assert len(data["recent_trends"]) == 1

    def test_recent_trends_limiting(
        self, correlation_tracker, hook_results, test_results
    ):
        """Test that recent trends are limited to last 3 iterations."""
        ai_fixes = []

        # Record 5 iterations
        for i in range(1, 6):
            correlation_tracker.record_iteration(
                i, hook_results, test_results, ai_fixes
            )

        data = correlation_tracker.get_correlation_data()
        assert len(data["recent_trends"]) == 3
        assert data["recent_trends"][0]["iteration"] == 3
        assert data["recent_trends"][-1]["iteration"] == 5


class TestMinimalProgressStreamer:
    """Test minimal progress streamer fallback."""

    @pytest.fixture
    def minimal_streamer(self):
        return MinimalProgressStreamer()

    def test_initialization(self, minimal_streamer):
        """Test minimal progress streamer initialization."""
        assert minimal_streamer is not None

    def test_update_stage_no_op(self, minimal_streamer):
        """Test that stage updates are no-ops."""
        # Should not raise any exceptions
        minimal_streamer.update_stage("test_stage", "test_substage")

    def test_update_hook_progress_no_op(self, minimal_streamer):
        """Test that hook progress updates are no-ops."""
        from crackerjack.executors.individual_hook_executor import HookProgress

        progress = Mock(spec=HookProgress)
        progress.hook_name = "test-hook"

        # Should not raise any exceptions
        minimal_streamer.update_hook_progress(progress)

    def test_stream_update_no_op(self, minimal_streamer):
        """Test that stream updates are no-ops."""
        # Should not raise any exceptions
        minimal_streamer._stream_update({"test": "data"})


class TestProgressStreamer:
    """Test progress streaming with WebSocket integration."""

    @pytest.fixture
    def mock_session(self):
        session = Mock(spec=SessionCoordinator)
        session.web_job_id = "test-job-123"
        session.progress_file = Path("/tmp/test-progress.json")
        return session

    @pytest.fixture
    def config(self):
        return OrchestrationConfig()

    @pytest.fixture
    def progress_streamer(self, config, mock_session):
        return ProgressStreamer(config, mock_session)

    def test_initialization(self, progress_streamer):
        """Test progress streamer initialization."""
        assert progress_streamer.current_stage == "initialization"
        assert progress_streamer.current_substage == ""
        assert progress_streamer.hook_progress == {}

    def test_update_stage(self, progress_streamer, mock_session):
        """Test stage updates."""
        progress_streamer.update_stage("hooks", "fast_hooks")

        assert progress_streamer.current_stage == "hooks"
        assert progress_streamer.current_substage == "fast_hooks"
        mock_session.update_stage.assert_called_once()

    def test_update_hook_progress(self, progress_streamer, mock_session):
        """Test hook progress updates."""
        from crackerjack.executors.individual_hook_executor import HookProgress

        progress = Mock(spec=HookProgress)
        progress.hook_name = "ruff-check"
        progress.to_dict.return_value = {"status": "running", "progress": 50}

        progress_streamer.update_hook_progress(progress)

        assert "ruff-check" in progress_streamer.hook_progress
        mock_session.update_stage.assert_called_once()

    @patch("builtins.open")
    @patch("json.load")
    @patch("json.dump")
    def test_websocket_progress_update_existing_file(
        self, mock_json_dump, mock_json_load, mock_open, progress_streamer
    ):
        """Test WebSocket progress update with existing progress file."""
        progress_streamer.session.progress_file.exists = Mock(return_value=True)
        mock_json_load.return_value = {"existing": "data"}

        update_data = {"type": "stage_update", "stage": "hooks"}
        progress_streamer._update_websocket_progress(update_data)

        # Should have attempted to read and write the file
        assert mock_open.call_count >= 1
        mock_json_dump.assert_called_once()

    @patch("builtins.open")
    @patch("json.dump")
    def test_websocket_progress_update_new_file(
        self, mock_json_dump, mock_open, progress_streamer
    ):
        """Test WebSocket progress update with new progress file."""
        progress_streamer.session.progress_file.exists = Mock(return_value=False)

        update_data = {"type": "hook_progress", "hook_name": "test-hook"}
        progress_streamer._update_websocket_progress(update_data)

        # Should still attempt to write even with no existing file
        mock_json_dump.assert_called_once()

    def test_websocket_progress_update_exception_handling(self, progress_streamer):
        """Test that WebSocket progress update handles exceptions gracefully."""
        # Remove progress_file to trigger exception
        delattr(progress_streamer.session, "progress_file")

        update_data = {"type": "error_trigger"}
        # Should not raise exception due to suppress()
        progress_streamer._update_websocket_progress(update_data)


class TestAdvancedWorkflowOrchestrator:
    """Test advanced workflow orchestrator."""

    @pytest.fixture
    def mock_console(self):
        console = Mock()
        console.file = Mock()
        console.file.getvalue = Mock()  # Make it look like StringIO for MCP detection
        console.is_terminal = False
        return console

    @pytest.fixture
    def pkg_path(self, tmp_path):
        return tmp_path / "test_package"

    @pytest.fixture
    def mock_session(self):
        session = Mock(spec=SessionCoordinator)
        session.job_id = "test-job-456"
        session.web_job_id = "web-job-789"
        return session

    @pytest.fixture
    def config(self):
        return OrchestrationConfig(
            ai_coordination_mode=AICoordinationMode.SINGLE_AGENT,
            execution_strategy=ExecutionStrategy.BATCH,
        )

    @pytest.fixture
    def orchestrator(self, mock_console, pkg_path, mock_session, config):
        with patch.multiple(
            "crackerjack.orchestration.advanced_orchestrator",
            HookConfigLoader=Mock(),
            HookExecutor=Mock(),
            IndividualHookExecutor=Mock(),
            TestManagementImpl=Mock(),
            TestProgressStreamer=Mock(),
            OrchestrationPlanner=Mock(),
            get_metrics_collector=Mock(return_value=Mock()),
        ):
            return AdvancedWorkflowOrchestrator(
                mock_console, pkg_path, mock_session, config
            )

    def test_initialization(self, orchestrator):
        """Test orchestrator initialization."""
        assert orchestrator.console is not None
        assert orchestrator.pkg_path is not None
        assert orchestrator.session is not None
        assert orchestrator.config is not None
        assert orchestrator.correlation_tracker is not None
        assert orchestrator.progress_streamer is not None

    def test_mcp_mode_detection_with_stringio_console(
        self, mock_console, pkg_path, mock_session
    ):
        """Test MCP mode detection with StringIO console."""
        with patch.multiple(
            "crackerjack.orchestration.advanced_orchestrator",
            HookConfigLoader=Mock(),
            HookExecutor=Mock(),
            IndividualHookExecutor=Mock(),
            TestManagementImpl=Mock(),
            TestProgressStreamer=Mock(),
            OrchestrationPlanner=Mock(),
            get_metrics_collector=Mock(return_value=Mock()),
        ):
            # Console with StringIO (MCP mode)
            mock_console.file.getvalue = Mock()
            mock_console.is_terminal = False

            orchestrator = AdvancedWorkflowOrchestrator(
                mock_console, pkg_path, mock_session
            )

            # Should detect MCP mode and configure individual executor
            orchestrator.individual_executor.set_mcp_mode.assert_called_once_with(True)

    def test_mcp_mode_detection_with_job_id(self, mock_console, pkg_path, mock_session):
        """Test MCP mode detection with job ID."""
        with patch.multiple(
            "crackerjack.orchestration.advanced_orchestrator",
            HookConfigLoader=Mock(),
            HookExecutor=Mock(),
            IndividualHookExecutor=Mock(),
            TestManagementImpl=Mock(),
            TestProgressStreamer=Mock(),
            OrchestrationPlanner=Mock(),
            get_metrics_collector=Mock(return_value=Mock()),
        ):
            # Session with job_id (MCP mode)
            mock_session.job_id = "test-job"

            orchestrator = AdvancedWorkflowOrchestrator(
                mock_console, pkg_path, mock_session
            )

            # Should detect MCP mode
            orchestrator.individual_executor.set_mcp_mode.assert_called_once_with(True)

    def test_multi_agent_system_initialization(self, orchestrator):
        """Test multi-agent system initialization."""
        orchestrator.config.ai_coordination_mode = AICoordinationMode.MULTI_AGENT

        with (
            patch(
                "crackerjack.orchestration.advanced_orchestrator.AgentContext"
            ) as mock_context,
            patch(
                "crackerjack.orchestration.advanced_orchestrator.AgentCoordinator"
            ) as mock_coord,
        ):
            mock_coordinator_instance = Mock()
            mock_coordinator_instance.get_agent_capabilities.return_value = {
                "RefactoringAgent": {"supported_types": ["COMPLEXITY", "DEAD_CODE"]},
                "SecurityAgent": {"supported_types": ["SECURITY"]},
            }
            mock_coord.return_value = mock_coordinator_instance

            orchestrator._initialize_multi_agent_system()

            mock_context.assert_called_once()
            mock_coord.assert_called_once()
            mock_coordinator_instance.initialize_agents.assert_called_once()
            assert orchestrator.agent_coordinator == mock_coordinator_instance

    def test_display_iteration_stats(self, orchestrator):
        """Test iteration statistics display."""
        iteration_times = {"hooks": 5.2, "tests": 12.5, "ai": 3.1}
        context = Mock()
        context.hook_failures = ["ruff-check", "pyright"]
        context.test_failures = ["test_file.py::test_method"]

        # Should not raise exception
        orchestrator._display_iteration_stats(
            iteration=2,
            max_iterations=10,
            iteration_times=iteration_times,
            hooks_time=10.5,
            tests_time=25.0,
            ai_time=6.2,
            context=context,
        )

        # Verify console was used for output
        assert orchestrator.console.print.call_count > 0

    def test_hook_to_issue_type_mapping(self, orchestrator):
        """Test hook name to issue type mapping."""
        mappings = [
            ("ruff-format", IssueType.FORMATTING),
            ("ruff-check", IssueType.FORMATTING),
            ("pyright", IssueType.TYPE_ERROR),
            ("bandit", IssueType.SECURITY),
            ("vulture", IssueType.DEAD_CODE),
            ("refurb", IssueType.COMPLEXITY),
            ("creosote", IssueType.DEPENDENCY),
            ("gitleaks", IssueType.SECURITY),
            ("trailing-whitespace", IssueType.FORMATTING),
            ("unknown-hook", IssueType.FORMATTING),  # Default fallback
        ]

        for hook_name, expected_type in mappings:
            result = orchestrator._map_hook_to_issue_type(hook_name)
            assert result == expected_type

    @pytest.mark.asyncio
    async def test_execute_single_iteration_success(self, orchestrator):
        """Test successful single iteration execution."""
        mock_plan = Mock(spec=ExecutionPlan)
        mock_context = Mock(spec=ExecutionContext)
        mock_context.iteration_count = 1

        # Mock successful execution
        passed_hook = Mock()
        passed_hook.name = "ruff-check"
        passed_hook.status = "passed"
        passed_hook.error = None
        passed_hook.error_details = []

        with (
            patch.object(
                orchestrator, "_execute_hooks_phase", return_value=[passed_hook]
            ) as mock_hooks,
            patch.object(
                orchestrator,
                "_execute_tests_phase",
                return_value={"success": True, "failed_tests": []},
            ) as mock_tests,
        ):
            success, times = await orchestrator._execute_single_iteration(
                mock_plan, mock_context, 1
            )

            assert success is True
            assert "hooks" in times
            assert "tests" in times
            assert "ai" in times

            mock_hooks.assert_called_once_with(mock_plan, mock_context)
            mock_tests.assert_called_once_with(mock_plan, mock_context)

    @pytest.mark.asyncio
    async def test_execute_single_iteration_with_failures(self, orchestrator):
        """Test single iteration with failures requiring AI analysis."""
        mock_plan = Mock(spec=ExecutionPlan)
        mock_context = Mock(spec=ExecutionContext)

        # Mock failed execution
        failed_hook = Mock()
        failed_hook.name = "ruff-check"
        failed_hook.status = "failed"
        failed_hook.error = "Import error"
        failed_hook.error_details = ["Missing import statement"]

        with (
            patch.object(
                orchestrator, "_execute_hooks_phase", return_value=[failed_hook]
            ) as mock_hooks,
            patch.object(
                orchestrator,
                "_execute_tests_phase",
                return_value={"success": False, "failed_tests": ["test.py::test_func"]},
            ) as mock_tests,
            patch.object(
                orchestrator, "_execute_ai_phase", return_value=["Fixed import error"]
            ) as mock_ai,
        ):
            success, times = await orchestrator._execute_single_iteration(
                mock_plan, mock_context, 1
            )

            assert success is False
            assert times["ai"] > 0

            mock_hooks.assert_called_once()
            mock_tests.assert_called_once()
            mock_ai.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_fast_hooks_with_autofix_success_first_attempt(
        self, orchestrator
    ):
        """Test fast hooks succeed on first attempt."""
        strategy = Mock()
        execution_mode = ExecutionStrategy.INDIVIDUAL
        context = Mock()

        # Create mock passing result
        passing_result = Mock()
        passing_result.name = "ruff-format"
        passing_result.status = "passed"
        passing_result.error = None
        passing_results = [passing_result]

        with patch.object(
            orchestrator, "_execute_fast_hooks_attempt", return_value=passing_results
        ):
            results = await orchestrator._execute_fast_hooks_with_autofix(
                strategy, execution_mode, context
            )

            assert results == passing_results
            assert all(r.status == "passed" for r in results)

    @pytest.mark.asyncio
    async def test_execute_fast_hooks_with_autofix_success_second_attempt(
        self, orchestrator
    ):
        """Test fast hooks succeed on second attempt."""
        strategy = Mock()
        execution_mode = ExecutionStrategy.INDIVIDUAL
        context = Mock()

        # Create mock failing result
        failing_result = Mock()
        failing_result.name = "ruff-format"
        failing_result.status = "failed"
        failing_result.error = "Error"
        failing_results = [failing_result]

        # Create mock passing result
        passing_result = Mock()
        passing_result.name = "ruff-format"
        passing_result.status = "passed"
        passing_result.error = None
        passing_results = [passing_result]

        with patch.object(
            orchestrator,
            "_execute_fast_hooks_attempt",
            side_effect=[failing_results, passing_results],
        ):
            results = await orchestrator._execute_fast_hooks_with_autofix(
                strategy, execution_mode, context
            )

            assert results == passing_results
            assert all(r.status == "passed" for r in results)

    @pytest.mark.asyncio
    async def test_execute_fast_hooks_with_autofix_requires_ai_fix(self, orchestrator):
        """Test fast hooks require AI autofix cycle."""
        strategy = Mock()
        execution_mode = ExecutionStrategy.INDIVIDUAL
        context = Mock()

        # Create mock failing result
        failing_result = Mock()
        failing_result.name = "ruff-check"
        failing_result.status = "failed"
        failing_result.error = "Import error"
        failing_results = [failing_result]

        with (
            patch.object(
                orchestrator,
                "_execute_fast_hooks_attempt",
                return_value=failing_results,
            ),
            patch.object(
                orchestrator, "_trigger_autofix_for_fast_hooks"
            ) as mock_autofix,
        ):
            results = await orchestrator._execute_fast_hooks_with_autofix(
                strategy, execution_mode, context
            )

            # Should trigger autofix cycle
            mock_autofix.assert_called_once_with(failing_results)
            assert results == failing_results

    @pytest.mark.asyncio
    async def test_trigger_autofix_for_fast_hooks(self, orchestrator):
        """Test AI autofix trigger for fast hooks."""
        # Create mock failing result
        failed_result = Mock()
        failed_result.name = "ruff-check"
        failed_result.status = "failed"
        failed_result.error = "Error"
        failed_results = [failed_result]

        with patch.object(
            orchestrator, "_execute_ai_phase", return_value=["Applied fix"]
        ) as mock_ai:
            await orchestrator._trigger_autofix_for_fast_hooks(failed_results)

            mock_ai.assert_called_once()
            # Verify it creates mock test results and execution plan
            args = mock_ai.call_args[0]
            assert len(args) == 3  # plan, hook_results, test_results

    @pytest.mark.asyncio
    async def test_execute_multi_agent_analysis(self, orchestrator):
        """Test multi-agent analysis execution."""
        # Set up multi-agent coordinator
        orchestrator.agent_coordinator = Mock()
        mock_result = Mock()
        mock_result.fixes_applied = ["Fixed complexity", "Removed dead code"]
        mock_result.confidence = 0.85
        mock_result.remaining_issues = []
        mock_result.recommendations = ["Use better variable names"]
        orchestrator.agent_coordinator.handle_issues = AsyncMock(
            return_value=mock_result
        )

        # Create mock failing hook result
        failed_hook = Mock()
        failed_hook.name = "refurb"
        failed_hook.status = "failed"
        failed_hook.error = "Complexity"
        failed_hooks = [failed_hook]
        failed_tests = ["test.py::test_func"]
        failed_individual_tests = []
        correlation_data = {"problematic_hooks": []}

        ai_fixes = await orchestrator._execute_multi_agent_analysis(
            failed_hooks, failed_tests, failed_individual_tests, correlation_data
        )

        assert len(ai_fixes) >= 2  # Should include fixes and recommendations
        assert "Fixed complexity" in ai_fixes
        orchestrator.agent_coordinator.handle_issues.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_single_agent_analysis(self, orchestrator):
        """Test single agent analysis (mock implementation)."""
        # Create mock failing hook result
        failed_hook = Mock()
        failed_hook.name = "ruff-check"
        failed_hook.status = "failed"
        failed_hook.error = "Error"
        failed_hooks = [failed_hook]
        failed_tests = ["test.py::test_func"]
        failed_individual_tests = []
        correlation_data = {}

        ai_fixes = await orchestrator._execute_single_agent_analysis(
            failed_hooks, failed_tests, failed_individual_tests, correlation_data
        )

        assert len(ai_fixes) == 4
        assert "[Single Agent]" in ai_fixes[0]

    def test_adapt_execution_plan_with_problematic_hooks(self, orchestrator):
        """Test execution plan adaptation based on problematic hooks."""
        orchestrator.correlation_tracker.failure_patterns = {
            "ruff-check": ["iteration_1", "iteration_2"]
        }

        current_plan = Mock(spec=ExecutionPlan)
        current_plan.execution_strategy = ExecutionStrategy.BATCH
        context = Mock()

        with patch.object(orchestrator, "planner") as mock_planner:
            mock_planner.create_execution_plan.return_value = Mock()

            orchestrator._adapt_execution_plan(current_plan, context)

            # Should switch to individual execution
            assert (
                orchestrator.config.execution_strategy == ExecutionStrategy.INDIVIDUAL
            )
            mock_planner.create_execution_plan.assert_called_once()

    def test_print_final_analysis_with_data(self, orchestrator):
        """Test final analysis printing with correlation data."""
        orchestrator.correlation_tracker.iteration_data = [
            {
                "iteration": 1,
                "failed_hooks": ["ruff-check"],
                "total_errors": 2,
            },
            {
                "iteration": 2,
                "failed_hooks": ["ruff-check", "pyright"],
                "total_errors": 3,
            },
        ]
        orchestrator.correlation_tracker.failure_patterns = {
            "ruff-check": ["iteration_1", "iteration_2"]
        }

        # Should not raise exception
        orchestrator._print_final_analysis()

        # Verify console output was generated
        assert orchestrator.console.print.call_count > 0

    def test_print_final_analysis_no_data(self, orchestrator):
        """Test final analysis printing with no data."""
        # Empty correlation tracker - should return early
        orchestrator._print_final_analysis()

        # Should have minimal console output (early return)
        assert orchestrator.console.print.call_count == 0

    def test_fallback_to_minimal_progress_streamer(
        self, mock_console, pkg_path, mock_session
    ):
        """Test fallback to minimal progress streamer on initialization error."""
        config = OrchestrationConfig()

        with (
            patch.multiple(
                "crackerjack.orchestration.advanced_orchestrator",
                HookConfigLoader=Mock(),
                HookExecutor=Mock(),
                IndividualHookExecutor=Mock(),
                TestManagementImpl=Mock(),
                TestProgressStreamer=Mock(),
                OrchestrationPlanner=Mock(),
                get_metrics_collector=Mock(return_value=Mock()),
            ),
            patch(
                "crackerjack.orchestration.advanced_orchestrator.ProgressStreamer",
                side_effect=Exception("Mock initialization error"),
            ),
        ):
            orchestrator = AdvancedWorkflowOrchestrator(
                mock_console, pkg_path, mock_session, config
            )

            # Should fall back to MinimalProgressStreamer
            assert isinstance(orchestrator.progress_streamer, MinimalProgressStreamer)
            # Should show warning message
            mock_console.print.assert_called()


class TestExecutionIntegration:
    """Integration tests for execution flow."""

    @pytest.fixture
    def mock_options(self):
        options = Mock(spec=OptionsProtocol)
        options.include_tests = True
        options.experimental_hooks = False
        return options

    @pytest.mark.asyncio
    async def test_orchestrated_workflow_execution_structure(self):
        """Test orchestrated workflow execution structure without complex mocking."""
        # This tests the structure and flow without deep execution
        config = OrchestrationConfig()
        console = Mock()
        console.file = Mock()
        console.is_terminal = False
        pkg_path = Path("/tmp/test")
        session = Mock(spec=SessionCoordinator)
        session.job_id = "test-workflow"

        with patch.multiple(
            "crackerjack.orchestration.advanced_orchestrator",
            HookConfigLoader=Mock(),
            HookExecutor=Mock(),
            IndividualHookExecutor=Mock(),
            TestManagementImpl=Mock(),
            TestProgressStreamer=Mock(),
            OrchestrationPlanner=Mock(),
            get_metrics_collector=Mock(return_value=Mock()),
        ):
            orchestrator = AdvancedWorkflowOrchestrator(
                console, pkg_path, session, config
            )

            # Mock the internal methods to avoid complex setup
            with patch.object(
                orchestrator, "_execute_single_iteration", return_value=(True, {})
            ):
                options = Mock(spec=OptionsProtocol)

                result = await orchestrator.execute_orchestrated_workflow(
                    options, max_iterations=1
                )

                assert result is True
                # Verify workflow structure was followed
                assert console.print.call_count > 0

    def test_metrics_recording_integration(self):
        """Test that metrics recording is properly integrated."""
        config = OrchestrationConfig()
        console = Mock()
        pkg_path = Path("/tmp/test")
        session = Mock(spec=SessionCoordinator)
        mock_metrics = Mock()

        with patch.multiple(
            "crackerjack.orchestration.advanced_orchestrator",
            HookConfigLoader=Mock(),
            HookExecutor=Mock(),
            IndividualHookExecutor=Mock(),
            TestManagementImpl=Mock(),
            TestProgressStreamer=Mock(),
            OrchestrationPlanner=Mock(),
            get_metrics_collector=Mock(return_value=mock_metrics),
        ):
            orchestrator = AdvancedWorkflowOrchestrator(
                console, pkg_path, session, config
            )

            # Verify metrics collector is assigned
            assert orchestrator.metrics == mock_metrics
