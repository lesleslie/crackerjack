"""Tests for WorkflowPipeline methods."""

import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.core.workflow_orchestrator import WorkflowPipeline


@pytest.fixture
def mock_console() -> MagicMock:
    """Create a mock console for testing."""
    console = MagicMock()
    console.print = MagicMock()
    return console


@pytest.fixture
def mock_session() -> MagicMock:
    """Create a mock session coordinator for testing."""
    session = MagicMock()
    session.initialize_session_tracking = MagicMock()
    session.finalize_session = MagicMock()
    session.start_time = 12345.0
    return session


@pytest.fixture
def mock_phases() -> MagicMock:
    """Create a mock phase coordinator for testing."""
    phases = MagicMock()
    phases.run_fast_hooks_only = AsyncMock(return_value=True)
    phases.run_comprehensive_hooks_only = AsyncMock(return_value=True)
    phases.run_testing_phase = MagicMock(return_value=True)
    phases.run_cleaning_phase = MagicMock(return_value=True)
    return phases


@pytest.fixture
def mock_settings() -> MagicMock:
    """Create mock settings for testing."""
    settings = MagicMock()
    settings.execution.verbose = False
    return settings


@pytest.fixture
def pipeline(
    mock_console: MagicMock,
    mock_session: MagicMock,
    mock_phases: MagicMock,
    mock_settings: MagicMock,
) -> WorkflowPipeline:
    """Create a WorkflowPipeline instance for testing."""
    return WorkflowPipeline(
        console=mock_console,
        pkg_path=Path("/tmp/test_project"),
        session=mock_session,
        phases=mock_phases,
        settings=mock_settings,
        logger=logging.getLogger("test_logger"),
    )


@pytest.fixture
def mock_options() -> MagicMock:
    """Create mock options for testing."""
    options = MagicMock()
    options.clean = False
    options.skip_hooks = False
    options.test = False
    options.run_tests = False
    return options


class TestRunCompleteWorkflow:
    """Test run_complete_workflow method."""

    @pytest.mark.asyncio
    async def test_run_complete_workflow_success(
        self,
        pipeline: WorkflowPipeline,
        mock_options: MagicMock,
    ) -> None:
        """Test run_complete_workflow successful execution."""
        with (
            patch(
                "crackerjack.core.workflow_orchestrator.build_oneiric_runtime"
            ) as mock_runtime,
            patch(
                "crackerjack.core.workflow_orchestrator.register_crackerjack_workflow"
            ),
        ):
            mock_runtime_instance = MagicMock()
            mock_runtime_instance.workflow_bridge.execute_dag = AsyncMock(
                return_value={"results": {"step1": True, "step2": True}}
            )
            mock_runtime.return_value = mock_runtime_instance

            result = await pipeline.run_complete_workflow(mock_options)

            assert result is True
            pipeline.session.initialize_session_tracking.assert_called_once_with(
                mock_options
            )
            pipeline.session.finalize_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_complete_workflow_with_exception(
        self,
        pipeline: WorkflowPipeline,
        mock_options: MagicMock,
    ) -> None:
        """Test run_complete_workflow handles exceptions."""
        with (
            patch(
                "crackerjack.core.workflow_orchestrator.build_oneiric_runtime"
            ) as mock_runtime,
            patch(
                "crackerjack.core.workflow_orchestrator.register_crackerjack_workflow"
            ),
        ):
            mock_runtime_instance = MagicMock()
            mock_runtime_instance.workflow_bridge.execute_dag = AsyncMock(
                side_effect=RuntimeError("Workflow failed")
            )
            mock_runtime.return_value = mock_runtime_instance

            result = await pipeline.run_complete_workflow(mock_options)

            assert result is False
            pipeline.session.finalize_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_complete_workflow_partial_failure(
        self,
        pipeline: WorkflowPipeline,
        mock_options: MagicMock,
    ) -> None:
        """Test run_complete_workflow with partial step failure."""
        with (
            patch(
                "crackerjack.core.workflow_orchestrator.build_oneiric_runtime"
            ) as mock_runtime,
            patch(
                "crackerjack.core.workflow_orchestrator.register_crackerjack_workflow"
            ),
        ):
            mock_runtime_instance = MagicMock()
            mock_runtime_instance.workflow_bridge.execute_dag = AsyncMock(
                return_value={"results": {"step1": True, "step2": False}}
            )
            mock_runtime.return_value = mock_runtime_instance

            result = await pipeline.run_complete_workflow(mock_options)

            assert result is False


class TestRunCompleteWorkflowSync:
    """Test run_complete_workflow_sync method."""

    def test_run_complete_workflow_sync_calls_async(
        self,
        pipeline: WorkflowPipeline,
        mock_options: MagicMock,
    ) -> None:
        """Test run_complete_workflow_sync executes the async workflow."""
        with (
            patch(
                "crackerjack.core.workflow_orchestrator.build_oneiric_runtime"
            ) as mock_runtime,
            patch(
                "crackerjack.core.workflow_orchestrator.register_crackerjack_workflow"
            ),
        ):
            mock_runtime_instance = MagicMock()
            mock_runtime_instance.workflow_bridge.execute_dag = AsyncMock(
                return_value={"results": {}}
            )
            mock_runtime.return_value = mock_runtime_instance

            result = pipeline.run_complete_workflow_sync(mock_options)

            assert result is True


class TestExecuteWorkflow:
    """Test execute_workflow method."""

    def test_execute_workflow_delegates_to_sync(
        self,
        pipeline: WorkflowPipeline,
        mock_options: MagicMock,
    ) -> None:
        """Test execute_workflow delegates to run_complete_workflow_sync."""
        with (
            patch(
                "crackerjack.core.workflow_orchestrator.build_oneiric_runtime"
            ) as mock_runtime,
            patch(
                "crackerjack.core.workflow_orchestrator.register_crackerjack_workflow"
            ),
        ):
            mock_runtime_instance = MagicMock()
            mock_runtime_instance.workflow_bridge.execute_dag = AsyncMock(
                return_value={"results": {}}
            )
            mock_runtime.return_value = mock_runtime_instance

            result = pipeline.execute_workflow(mock_options)

            assert result is True


class TestRunFastHooksOnly:
    """Test run_fast_hooks_only method."""

    @pytest.mark.asyncio
    async def test_run_fast_hooks_only_success(
        self,
        pipeline: WorkflowPipeline,
        mock_options: MagicMock,
        mock_phases: MagicMock,
    ) -> None:
        """Test run_fast_hooks_only successful execution."""
        result = await pipeline.run_fast_hooks_only(mock_options)

        assert result is True
        mock_phases.run_fast_hooks_only.assert_called_once_with(mock_options)

    @pytest.mark.asyncio
    async def test_run_fast_hooks_only_failure(
        self,
        pipeline: WorkflowPipeline,
        mock_options: MagicMock,
        mock_phases: MagicMock,
    ) -> None:
        """Test run_fast_hooks_only when hooks fail."""
        mock_phases.run_fast_hooks_only.return_value = False

        result = await pipeline.run_fast_hooks_only(mock_options)

        assert result is False


class TestRunComprehensiveHooksOnly:
    """Test run_comprehensive_hooks_only method."""

    @pytest.mark.asyncio
    async def test_run_comprehensive_hooks_only_success(
        self,
        pipeline: WorkflowPipeline,
        mock_options: MagicMock,
        mock_phases: MagicMock,
    ) -> None:
        """Test run_comprehensive_hooks_only successful execution."""
        result = await pipeline.run_comprehensive_hooks_only(mock_options)

        assert result is True
        mock_phases.run_comprehensive_hooks_only.assert_called_once_with(mock_options)

    @pytest.mark.asyncio
    async def test_run_comprehensive_hooks_only_failure(
        self,
        pipeline: WorkflowPipeline,
        mock_options: MagicMock,
        mock_phases: MagicMock,
    ) -> None:
        """Test run_comprehensive_hooks_only when hooks fail."""
        mock_phases.run_comprehensive_hooks_only.return_value = False

        result = await pipeline.run_comprehensive_hooks_only(mock_options)

        assert result is False


class TestRunTestingPhase:
    """Test run_testing_phase method."""

    def test_run_testing_phase_success(
        self,
        pipeline: WorkflowPipeline,
        mock_options: MagicMock,
        mock_phases: MagicMock,
    ) -> None:
        """Test run_testing_phase successful execution."""
        result = pipeline.run_testing_phase(mock_options)

        assert result is True
        mock_phases.run_testing_phase.assert_called_once_with(mock_options)

    def test_run_testing_phase_failure(
        self,
        pipeline: WorkflowPipeline,
        mock_options: MagicMock,
        mock_phases: MagicMock,
    ) -> None:
        """Test run_testing_phase when tests fail."""
        mock_phases.run_testing_phase.return_value = False

        result = pipeline.run_testing_phase(mock_options)

        assert result is False


class TestRunCleaningPhase:
    """Test run_cleaning_phase method."""

    def test_run_cleaning_phase_success(
        self,
        pipeline: WorkflowPipeline,
        mock_options: MagicMock,
        mock_phases: MagicMock,
    ) -> None:
        """Test run_cleaning_phase successful execution."""
        result = pipeline.run_cleaning_phase(mock_options)

        assert result is True
        mock_phases.run_cleaning_phase.assert_called_once_with(mock_options)

    def test_run_cleaning_phase_failure(
        self,
        pipeline: WorkflowPipeline,
        mock_options: MagicMock,
        mock_phases: MagicMock,
    ) -> None:
        """Test run_cleaning_phase when cleaning fails."""
        mock_phases.run_cleaning_phase.return_value = False

        result = pipeline.run_cleaning_phase(mock_options)

        assert result is False


class TestWorkflowResultSuccess:
    """Test _workflow_result_success helper function."""

    def test_empty_results(self) -> None:
        """Test with empty results dict."""
        from crackerjack.core.workflow_orchestrator import _workflow_result_success

        result = _workflow_result_success({})
        assert result is True

    def test_all_true_values(self) -> None:
        """Test with all True values."""
        from crackerjack.core.workflow_orchestrator import _workflow_result_success

        result = _workflow_result_success({"results": {"a": True, "b": True}})
        assert result is True

    def test_has_false_value(self) -> None:
        """Test with False value in results."""
        from crackerjack.core.workflow_orchestrator import _workflow_result_success

        result = _workflow_result_success({"results": {"a": True, "b": False}})
        assert result is False

    def test_none_results(self) -> None:
        """Test with None results."""
        from crackerjack.core.workflow_orchestrator import _workflow_result_success

        result = _workflow_result_success(None)
        assert result is True

    def test_non_dict_result(self) -> None:
        """Test with non-dict result."""
        from crackerjack.core.workflow_orchestrator import _workflow_result_success

        result = _workflow_result_success("not a dict")
        assert result is True


class TestAdaptOptions:
    """Test _adapt_options helper function."""

    def test_adapt_options_returns_same(self) -> None:
        """Test that _adapt_options returns the options unchanged."""
        from crackerjack.core.workflow_orchestrator import _adapt_options

        options = MagicMock()
        result = _adapt_options(options)
        assert result is options
