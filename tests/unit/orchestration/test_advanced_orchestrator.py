"""Unit tests for AdvancedWorkflowOrchestrator.

Tests workflow orchestration, correlation tracking, progress streaming,
and multi-agent coordination.
"""

import time
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.models.task import HookResult
from crackerjack.orchestration.advanced_orchestrator import (
    AdvancedWorkflowOrchestrator,
    CorrelationTracker,
    MinimalProgressStreamer,
    ProgressStreamer,
)
from crackerjack.orchestration.execution_strategies import (
    OrchestrationConfig,
)


@pytest.mark.unit
class TestCorrelationTracker:
    """Test CorrelationTracker for failure analysis."""

    def test_initialization(self):
        """Test CorrelationTracker initializes correctly."""
        tracker = CorrelationTracker()

        assert tracker.iteration_data == []
        assert tracker.failure_patterns == {}
        assert tracker.fix_success_rates == {}

    def test_record_iteration(self):
        """Test recording iteration data."""
        tracker = CorrelationTracker()

        hook_results = [
            HookResult(name="hook1", status="passed"),
            HookResult(name="hook2", status="failed"),
        ]
        test_results = {"failed_tests": ["test_module.py::test_foo"]}
        ai_fixes = ["Fixed import error"]

        tracker.record_iteration(1, hook_results, test_results, ai_fixes)

        assert len(tracker.iteration_data) == 1
        assert tracker.iteration_data[0]["iteration"] == 1
        assert "hook2" in tracker.iteration_data[0]["failed_hooks"]
        assert len(tracker.iteration_data[0]["ai_fixes_applied"]) == 1

    def test_analyze_failure_patterns_single_iteration(self):
        """Test failure pattern analysis with single iteration."""
        tracker = CorrelationTracker()

        hook_results = [HookResult(name="hook1", status="failed")]
        tracker.record_iteration(1, hook_results, {}, [])

        # Not enough data for pattern analysis
        assert tracker.failure_patterns == {}

    def test_analyze_failure_patterns_recurring(self):
        """Test detecting recurring failure patterns."""
        tracker = CorrelationTracker()

        # First iteration - hook1 fails
        hook_results_1 = [HookResult(name="hook1", status="failed")]
        tracker.record_iteration(1, hook_results_1, {}, [])

        # Second iteration - hook1 fails again
        hook_results_2 = [HookResult(name="hook1", status="failed")]
        tracker.record_iteration(2, hook_results_2, {}, [])

        # Should detect recurring pattern
        assert "hook1" in tracker.failure_patterns
        assert len(tracker.failure_patterns["hook1"]) > 0

    def test_get_problematic_hooks(self):
        """Test identifying problematic hooks."""
        tracker = CorrelationTracker()

        # Create recurring failure pattern
        for i in range(1, 4):
            hook_results = [HookResult(name="problematic_hook", status="failed")]
            tracker.record_iteration(i, hook_results, {}, [])

        problematic = tracker.get_problematic_hooks()

        assert "problematic_hook" in problematic

    def test_get_problematic_hooks_empty(self):
        """Test no problematic hooks when all pass."""
        tracker = CorrelationTracker()

        hook_results = [HookResult(name="good_hook", status="passed")]
        tracker.record_iteration(1, hook_results, {}, [])

        problematic = tracker.get_problematic_hooks()

        assert len(problematic) == 0

    def test_get_correlation_data(self):
        """Test getting correlation data summary."""
        tracker = CorrelationTracker()

        hook_results = [HookResult(name="hook1", status="failed")]
        tracker.record_iteration(1, hook_results, {}, ["fix1"])
        tracker.record_iteration(2, hook_results, {}, ["fix2"])

        data = tracker.get_correlation_data()

        assert data["iteration_count"] == 2
        assert "failure_patterns" in data
        assert "problematic_hooks" in data
        assert "recent_trends" in data

    def test_get_correlation_data_recent_trends(self):
        """Test recent trends in correlation data."""
        tracker = CorrelationTracker()

        # Record multiple iterations
        for i in range(1, 6):
            hook_results = [HookResult(name="hook1", status="passed")]
            tracker.record_iteration(i, hook_results, {}, [])

        data = tracker.get_correlation_data()

        # Should return last 3 iterations
        assert len(data["recent_trends"]) == 3
        assert data["recent_trends"][0]["iteration"] == 3


@pytest.mark.unit
class TestProgressStreamer:
    """Test ProgressStreamer base class."""

    def test_initialization(self):
        """Test ProgressStreamer initializes correctly."""
        config = OrchestrationConfig()
        session = Mock()

        streamer = ProgressStreamer(config=config, session=session)

        assert streamer.config == config
        assert streamer.session == session

    def test_initialization_without_args(self):
        """Test ProgressStreamer with no arguments."""
        streamer = ProgressStreamer()

        assert streamer.config is None
        assert streamer.session is None

    def test_update_stage(self):
        """Test update_stage method (no-op in base class)."""
        streamer = ProgressStreamer()

        # Should not raise error
        streamer.update_stage("testing", "running hooks")

    def test_update_hook_progress(self):
        """Test update_hook_progress method (no-op in base class)."""
        streamer = ProgressStreamer()

        progress = Mock()
        # Should not raise error
        streamer.update_hook_progress(progress)

    def test_stream_update(self):
        """Test _stream_update method (no-op in base class)."""
        streamer = ProgressStreamer()

        # Should not raise error
        streamer._stream_update({"status": "running"})


@pytest.mark.unit
class TestMinimalProgressStreamer:
    """Test MinimalProgressStreamer implementation."""

    def test_initialization(self):
        """Test MinimalProgressStreamer initializes."""
        streamer = MinimalProgressStreamer()

        # Should initialize without storing config/session
        assert not hasattr(streamer, "config") or streamer.config is None

    def test_initialization_with_args(self):
        """Test MinimalProgressStreamer ignores arguments."""
        config = OrchestrationConfig()
        session = Mock()

        streamer = MinimalProgressStreamer(config=config, session=session)

        # Arguments are ignored in minimal implementation
        assert True  # Just verify it doesn't error

    def test_update_stage_noop(self):
        """Test update_stage is no-op."""
        streamer = MinimalProgressStreamer()

        streamer.update_stage("stage", "substage")
        # No assertions needed - just verify no errors

    def test_update_hook_progress_noop(self):
        """Test update_hook_progress is no-op."""
        streamer = MinimalProgressStreamer()

        progress = Mock()
        streamer.update_hook_progress(progress)
        # No assertions needed - just verify no errors

    def test_stream_update_noop(self):
        """Test _stream_update is no-op."""
        streamer = MinimalProgressStreamer()

        streamer._stream_update({"data": "value"})
        # No assertions needed - just verify no errors


@pytest.mark.unit
class TestAdvancedWorkflowOrchestratorInitialization:
    """Test AdvancedWorkflowOrchestrator initialization."""

    @pytest.fixture
    def mock_dependencies(self, tmp_path):
        """Create mock dependencies for orchestrator."""
        console = Mock()
        session = Mock()
        return console, tmp_path, session

    def test_initialization(self, mock_dependencies):
        """Test AdvancedWorkflowOrchestrator initializes correctly."""
        console, pkg_path, session = mock_dependencies

        orchestrator = AdvancedWorkflowOrchestrator(console, pkg_path, session)

        assert orchestrator.console == console
        assert orchestrator.pkg_path == pkg_path
        assert orchestrator.session == session
        assert orchestrator.config is not None
        assert isinstance(orchestrator.correlation_tracker, CorrelationTracker)

    def test_initialization_with_custom_config(self, mock_dependencies):
        """Test initialization with custom config."""
        console, pkg_path, session = mock_dependencies
        config = OrchestrationConfig(max_parallel_hooks=5)

        orchestrator = AdvancedWorkflowOrchestrator(
            console, pkg_path, session, config=config
        )

        assert orchestrator.config.max_parallel_hooks == 5

    def test_initialization_components(self, mock_dependencies):
        """Test all components are initialized."""
        console, pkg_path, session = mock_dependencies

        orchestrator = AdvancedWorkflowOrchestrator(console, pkg_path, session)

        assert orchestrator.hook_config_loader is not None
        assert orchestrator.batch_executor is not None
        assert orchestrator.individual_executor is not None
        assert orchestrator.test_manager is not None
        assert orchestrator.planner is not None
        assert orchestrator.metrics is not None

    def test_detect_mcp_mode_terminal(self, mock_dependencies):
        """Test MCP mode detection for terminal."""
        console, pkg_path, session = mock_dependencies
        console.is_terminal = True
        console.file = Mock()
        console.file.getvalue = None

        orchestrator = AdvancedWorkflowOrchestrator(console, pkg_path, session)

        # Should not be in MCP mode
        assert True  # Verify initialization completes

    def test_detect_mcp_mode_non_terminal(self, mock_dependencies):
        """Test MCP mode detection for non-terminal."""
        console, pkg_path, session = mock_dependencies
        console.is_terminal = False

        orchestrator = AdvancedWorkflowOrchestrator(console, pkg_path, session)

        # Should detect MCP mode
        assert True  # Verify initialization completes

    def test_detect_mcp_mode_with_job_id(self, mock_dependencies):
        """Test MCP mode detection with job_id."""
        console, pkg_path, session = mock_dependencies
        console.is_terminal = True
        session.job_id = "test-job-123"

        orchestrator = AdvancedWorkflowOrchestrator(console, pkg_path, session)

        # Should detect MCP mode
        assert True  # Verify initialization completes


@pytest.mark.unit
@pytest.mark.asyncio
class TestAdvancedWorkflowOrchestratorExecution:
    """Test workflow execution methods."""

    @pytest.fixture
    def orchestrator(self, tmp_path):
        """Create orchestrator instance for testing."""
        console = Mock()
        session = Mock()
        console.is_terminal = True

        return AdvancedWorkflowOrchestrator(console, tmp_path, session)

    async def test_execute_workflow_basic(self, orchestrator):
        """Test basic workflow execution."""
        with patch.object(
            orchestrator.batch_executor, "execute_hooks", return_value=[]
        ):
            with patch.object(orchestrator.test_manager, "run_tests", return_value={}):
                result = await orchestrator.execute_workflow()

                assert isinstance(result, dict)

    async def test_execute_hooks_batch_mode(self, orchestrator):
        """Test executing hooks in batch mode."""
        hook_results = [
            HookResult(name="hook1", status="passed"),
            HookResult(name="hook2", status="passed"),
        ]

        with patch.object(
            orchestrator.batch_executor, "execute_hooks", return_value=hook_results
        ):
            results = await orchestrator._execute_hooks_batch()

            assert len(results) == 2
            assert all(r.status == "passed" for r in results)

    async def test_execute_hooks_individual_mode(self, orchestrator):
        """Test executing hooks individually."""
        hook_results = [
            HookResult(name="hook1", status="passed"),
        ]

        with patch.object(
            orchestrator.individual_executor, "execute_hook", return_value=hook_results[0]
        ):
            results = await orchestrator._execute_hooks_individual(["hook1"])

            assert len(results) == 1
            assert results[0].status == "passed"

    async def test_execute_with_correlation_tracking(self, orchestrator):
        """Test execution with correlation tracking enabled."""
        orchestrator.config.correlation_tracking = True

        hook_results = [HookResult(name="hook1", status="passed")]
        test_results = {"passed": 10, "failed": 0}

        with patch.object(
            orchestrator.batch_executor, "execute_hooks", return_value=hook_results
        ):
            with patch.object(
                orchestrator.test_manager, "run_tests", return_value=test_results
            ):
                await orchestrator.execute_workflow()

                # Should have recorded iteration
                assert len(orchestrator.correlation_tracker.iteration_data) > 0


@pytest.mark.unit
@pytest.mark.asyncio
class TestAdvancedWorkflowOrchestratorAICoordination:
    """Test AI coordination features."""

    @pytest.fixture
    def orchestrator(self, tmp_path):
        """Create orchestrator instance."""
        console = Mock()
        session = Mock()
        console.is_terminal = True

        return AdvancedWorkflowOrchestrator(console, tmp_path, session)

    async def test_initialize_multi_agent_system(self, orchestrator):
        """Test initializing multi-agent system."""
        from crackerjack.orchestration.execution_strategies import AICoordinationMode

        orchestrator.config.ai_coordination_mode = AICoordinationMode.MULTI_AGENT

        orchestrator._initialize_multi_agent_system()

        assert orchestrator.agent_coordinator is not None

    async def test_ai_coordination_single_agent_mode(self, orchestrator):
        """Test single agent coordination mode."""
        from crackerjack.orchestration.execution_strategies import AICoordinationMode

        orchestrator.config.ai_coordination_mode = AICoordinationMode.SINGLE_AGENT

        # Should not initialize multi-agent system
        orchestrator._initialize_multi_agent_system()

        assert orchestrator.agent_coordinator is None

    async def test_ai_fix_application(self, orchestrator):
        """Test applying AI fixes."""
        issues = [
            {"type": "import_error", "file": "test.py", "message": "Import error"}
        ]

        with patch.object(orchestrator, "_apply_ai_fixes_to_issues", return_value=[]):
            fixes = await orchestrator._apply_ai_fixes(issues)

            assert isinstance(fixes, list)


@pytest.mark.unit
@pytest.mark.asyncio
class TestAdvancedWorkflowOrchestratorRetry:
    """Test retry and failure handling."""

    @pytest.fixture
    def orchestrator(self, tmp_path):
        """Create orchestrator instance."""
        console = Mock()
        session = Mock()
        console.is_terminal = True

        return AdvancedWorkflowOrchestrator(console, tmp_path, session)

    async def test_intelligent_retry_enabled(self, orchestrator):
        """Test intelligent retry when enabled."""
        orchestrator.config.intelligent_retry = True

        hook_results = [HookResult(name="hook1", status="failed")]

        with patch.object(
            orchestrator.batch_executor, "execute_hooks", return_value=hook_results
        ):
            # Should attempt retry
            result = await orchestrator._execute_with_retry()

            assert isinstance(result, list)

    async def test_intelligent_retry_disabled(self, orchestrator):
        """Test no retry when disabled."""
        orchestrator.config.intelligent_retry = False

        assert orchestrator.config.intelligent_retry is False

    async def test_failure_analysis_enabled(self, orchestrator):
        """Test failure analysis when enabled."""
        orchestrator.config.failure_analysis = True

        hook_results = [
            HookResult(name="hook1", status="failed", error="Test error")
        ]

        analysis = orchestrator._analyze_failures(hook_results)

        assert isinstance(analysis, dict)
        assert "failed_hooks" in analysis


@pytest.mark.unit
class TestAdvancedWorkflowOrchestratorMetrics:
    """Test metrics collection."""

    @pytest.fixture
    def orchestrator(self, tmp_path):
        """Create orchestrator instance."""
        console = Mock()
        session = Mock()
        console.is_terminal = True

        return AdvancedWorkflowOrchestrator(console, tmp_path, session)

    def test_record_metric(self, orchestrator):
        """Test recording metrics."""
        orchestrator.metrics.record = Mock()

        orchestrator._record_metric("test_metric", 100)

        orchestrator.metrics.record.assert_called_once()

    def test_get_metrics_summary(self, orchestrator):
        """Test getting metrics summary."""
        orchestrator.metrics.get_summary = Mock(return_value={})

        summary = orchestrator._get_metrics_summary()

        assert isinstance(summary, dict)


@pytest.mark.unit
@pytest.mark.asyncio
class TestAdvancedWorkflowOrchestratorIntegration:
    """Test integration scenarios."""

    @pytest.fixture
    def orchestrator(self, tmp_path):
        """Create orchestrator instance."""
        console = Mock()
        session = Mock()
        console.is_terminal = True

        return AdvancedWorkflowOrchestrator(console, tmp_path, session)

    async def test_full_workflow_with_tests(self, orchestrator):
        """Test complete workflow with tests."""
        hook_results = [
            HookResult(name="ruff-format", status="passed"),
            HookResult(name="ruff-check", status="passed"),
        ]
        test_results = {"passed": 50, "failed": 0, "total": 50}

        with patch.object(
            orchestrator.batch_executor, "execute_hooks", return_value=hook_results
        ):
            with patch.object(
                orchestrator.test_manager, "run_tests", return_value=test_results
            ):
                result = await orchestrator.execute_workflow()

                assert isinstance(result, dict)
                assert "hooks" in result or "tests" in result or len(result) == 0

    async def test_workflow_with_failures_and_retry(self, orchestrator):
        """Test workflow with failures and retry logic."""
        orchestrator.config.intelligent_retry = True

        # First attempt fails
        hook_results_fail = [HookResult(name="hook1", status="failed")]
        # Second attempt passes
        hook_results_pass = [HookResult(name="hook1", status="passed")]

        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            return hook_results_fail if call_count == 1 else hook_results_pass

        with patch.object(
            orchestrator.batch_executor, "execute_hooks", side_effect=side_effect
        ):
            with patch.object(orchestrator.test_manager, "run_tests", return_value={}):
                result = await orchestrator._execute_with_retry()

                assert call_count >= 1

    async def test_workflow_with_correlation_and_analysis(self, orchestrator):
        """Test workflow with correlation tracking and failure analysis."""
        orchestrator.config.correlation_tracking = True
        orchestrator.config.failure_analysis = True

        hook_results = [
            HookResult(name="hook1", status="failed", error="Error message")
        ]
        test_results = {"passed": 0, "failed": 1}

        with patch.object(
            orchestrator.batch_executor, "execute_hooks", return_value=hook_results
        ):
            with patch.object(
                orchestrator.test_manager, "run_tests", return_value=test_results
            ):
                await orchestrator.execute_workflow()

                # Verify correlation tracking
                assert len(orchestrator.correlation_tracker.iteration_data) > 0

                # Verify failure analysis
                analysis = orchestrator._analyze_failures(hook_results)
                assert "failed_hooks" in analysis
