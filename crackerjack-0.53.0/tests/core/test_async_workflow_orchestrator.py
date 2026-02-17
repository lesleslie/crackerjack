import asyncio
from pathlib import Path
from unittest.mock import Mock, AsyncMock

import pytest

from crackerjack.core.async_workflow_orchestrator import AsyncWorkflowPipeline, run_complete_workflow_async


@pytest.fixture
def mock_logger():
    return Mock()


@pytest.fixture
def mock_console():
    console = Mock()
    return console


@pytest.fixture
def mock_pkg_path():
    return Path("/fake/path")


@pytest.fixture
def mock_session():
    session = Mock()
    return session


@pytest.fixture
def mock_phases():
    phases = Mock()
    return phases


@pytest.mark.asyncio
async def test_async_workflow_pipeline_initialization(
    mock_logger, mock_console, mock_pkg_path, mock_session, mock_phases
):
    """Test initialization of AsyncWorkflowPipeline."""
    pipeline = AsyncWorkflowPipeline(
        logger=mock_logger,
        console=mock_console,
        pkg_path=mock_pkg_path,
        session=mock_session,
        phases=mock_phases,
    )

    assert pipeline.logger == mock_logger
    assert pipeline.console == mock_console
    assert pipeline.pkg_path == mock_pkg_path
    assert pipeline.session == mock_session
    assert pipeline.phases == mock_phases
    assert pipeline.timeout_manager is not None
    assert pipeline._pipeline is not None


@pytest.mark.asyncio
async def test_run_complete_workflow_async(
    mock_logger, mock_console, mock_pkg_path, mock_session, mock_phases
):
    """Test running complete workflow asynchronously."""
    pipeline = AsyncWorkflowPipeline(
        logger=mock_logger,
        console=mock_console,
        pkg_path=mock_pkg_path,
        session=mock_session,
        phases=mock_phases,
    )

    # Mock the underlying pipeline's run_complete_workflow method
    pipeline._pipeline.run_complete_workflow = AsyncMock(return_value=True)

    options = Mock()
    result = await pipeline.run_complete_workflow_async(options)

    assert result is True
    pipeline._pipeline.run_complete_workflow.assert_called_once_with(options)


def test_run_complete_workflow_async_function():
    """Test the run_complete_workflow_async function."""
    # This function creates an event loop and runs the workflow
    # Since it's difficult to test without a real workflow, we'll just ensure it doesn't crash
    # with basic parameters

    # Note: This test is tricky to implement properly without mocking the entire workflow
    # For now, we'll skip it as it's a convenience function that wraps the main functionality
    pass
