"""Tests for async_workflow_orchestrator.py."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.config import CrackerjackSettings
from crackerjack.core.async_workflow_orchestrator import (
    AsyncWorkflowPipeline,
    run_complete_workflow_async,
)
from crackerjack.core.workflow_orchestrator import WorkflowPipeline


@pytest.fixture
def mock_settings(tmp_path):
    """Create mock settings."""
    settings = CrackerjackSettings(pkg_path=tmp_path)
    return settings


@pytest.fixture
def mock_console():
    """Create mock console."""
    from rich.console import Console
    return Console()


@pytest.fixture
def mock_session():
    """Create mock session coordinator."""
    from crackerjack.core.session_coordinator import SessionCoordinator

    return MagicMock(spec=SessionCoordinator)


@pytest.fixture
def mock_phases():
    """Create mock phase coordinator."""
    from crackerjack.core.phase_coordinator import PhaseCoordinator

    return MagicMock(spec=PhaseCoordinator)


@pytest.fixture
def mock_logger():
    """Create mock logger."""
    import logging

    return logging.getLogger("test_async_workflow_orchestrator")


class TestAsyncWorkflowPipeline:
    """Test suite for AsyncWorkflowPipeline."""

    @pytest.fixture
    def pipeline(
        self, mock_console, mock_settings, mock_session, mock_phases, mock_logger, tmp_path
    ):
        """Create AsyncWorkflowPipeline instance for testing."""
        return AsyncWorkflowPipeline(
            logger=mock_logger,
            console=mock_console,
            pkg_path=tmp_path,
            session=mock_session,
            phases=mock_phases,
        )

    def test_initialization(self, pipeline, mock_console, mock_settings, mock_session):
        """Test AsyncWorkflowPipeline initializes correctly."""
        assert pipeline.logger is not None
        assert pipeline.console == mock_console
        assert pipeline.pkg_path is not None
        assert pipeline.session is not None
        assert pipeline.phases is not None

    def test_timeout_manager_initialization(self, pipeline):
        """Test timeout manager is initialized."""
        assert pipeline.timeout_manager is not None
        from crackerjack.core.timeout_manager import AsyncTimeoutManager

        assert isinstance(pipeline.timeout_manager, AsyncTimeoutManager)

    def test_workflow_pipeline_delegation(self, pipeline):
        """Test internal WorkflowPipeline is created."""
        assert pipeline._pipeline is not None
        assert isinstance(pipeline._pipeline, WorkflowPipeline)

    @pytest.mark.asyncio
    async def test_run_complete_workflow_async_success(self, pipeline):
        """Test successful async workflow execution."""
        # Mock the underlying pipeline to return success
        pipeline._pipeline.run_complete_workflow = AsyncMock(return_value=True)

        options = MagicMock()
        result = await pipeline.run_complete_workflow_async(options)

        assert result is True
        pipeline._pipeline.run_complete_workflow.assert_called_once_with(options)

    @pytest.mark.asyncio
    async def test_run_complete_workflow_async_failure(self, pipeline):
        """Test async workflow execution with failure."""
        # Mock the underlying pipeline to return failure
        pipeline._pipeline.run_complete_workflow = AsyncMock(return_value=False)

        options = MagicMock()
        result = await pipeline.run_complete_workflow_async(options)

        assert result is False
        pipeline._pipeline.run_complete_workflow.assert_called_once_with(options)

    @pytest.mark.asyncio
    async def test_run_complete_workflow_async_exception(self, pipeline):
        """Test async workflow execution with exception."""
        # Mock the underlying pipeline to raise exception
        pipeline._pipeline.run_complete_workflow = AsyncMock(
            side_effect=RuntimeError("Workflow failed")
        )

        options = MagicMock()
        with pytest.raises(RuntimeError, match="Workflow failed"):
            await pipeline.run_complete_workflow_async(options)

        pipeline._pipeline.run_complete_workflow.assert_called_once_with(options)


class TestRunCompleteWorkflowAsyncFunction:
    """Test suite for run_complete_workflow_async standalone function."""

    @pytest.mark.asyncio
    async def test_run_complete_workflow_async_function_success(self, tmp_path):
        """Test standalone function with successful workflow."""
        options = MagicMock()

        # Mock WorkflowPipeline creation and execution
        with patch(
            "crackerjack.core.async_workflow_orchestrator.WorkflowPipeline"
        ) as mock_pipeline_class:
            mock_pipeline = MagicMock()
            mock_pipeline.run_complete_workflow = AsyncMock(return_value=True)
            mock_pipeline_class.return_value = mock_pipeline

            result = await run_complete_workflow_async._runner()(options)

            assert result is True
            mock_pipeline.run_complete_workflow.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_complete_workflow_async_function_failure(self, tmp_path):
        """Test standalone function with failed workflow."""
        options = MagicMock()

        # Mock WorkflowPipeline creation and execution
        with patch(
            "crackerjack.core.async_workflow_orchestrator.WorkflowPipeline"
        ) as mock_pipeline_class:
            mock_pipeline = MagicMock()
            mock_pipeline.run_complete_workflow = AsyncMock(return_value=False)
            mock_pipeline_class.return_value = mock_pipeline

            result = await run_complete_workflow_async._runner()(options)

            assert result is False
            mock_pipeline.run_complete_workflow.assert_called_once()

    def test_run_complete_workflow_sync_wrapper(self):
        """Test the sync wrapper function."""
        options = MagicMock()

        # This test verifies the function exists and is callable
        # Actual execution is tested in async tests above
        assert callable(run_complete_workflow_async)
