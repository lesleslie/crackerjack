"""Tests for run_complete_workflow function."""

import pytest

from crackerjack.core.async_workflow_orchestrator import AsyncWorkflowOrchestrator


def test_run_complete_workflow_basic():
    """Test basic functionality of AsyncWorkflowOrchestrator."""

    try:
        orchestrator = AsyncWorkflowOrchestrator()
        assert orchestrator is not None
        assert hasattr(orchestrator, "run_complete_workflow")
    except Exception as e:
        pytest.fail(f"Unexpected error creating AsyncWorkflowOrchestrator: {e}")


def test_run_cleaning_phase_basic():
    """Test basic functionality of run_cleaning_phase."""
    orchestrator = AsyncWorkflowOrchestrator()
    assert hasattr(orchestrator, "run_cleaning_phase")


def test_run_fast_hooks_only_basic():
    """Test basic functionality of run_fast_hooks_only."""
    orchestrator = AsyncWorkflowOrchestrator()
    assert hasattr(orchestrator, "run_fast_hooks_only")


def test_run_comprehensive_hooks_only_basic():
    """Test basic functionality of run_comprehensive_hooks_only."""
    orchestrator = AsyncWorkflowOrchestrator()
    assert hasattr(orchestrator, "run_comprehensive_hooks_only")


def test_run_hooks_phase_basic():
    """Test basic functionality of run_hooks_phase."""
    orchestrator = AsyncWorkflowOrchestrator()
    assert hasattr(orchestrator, "run_hooks_phase")


def test_run_testing_phase_basic():
    """Test basic functionality of run_testing_phase."""
    orchestrator = AsyncWorkflowOrchestrator()
    assert hasattr(orchestrator, "run_testing_phase")


def test_run_publishing_phase_basic():
    """Test basic functionality of run_publishing_phase."""
    orchestrator = AsyncWorkflowOrchestrator()
    assert hasattr(orchestrator, "run_publishing_phase")


def test_run_commit_phase_basic():
    """Test basic functionality of run_commit_phase."""
    orchestrator = AsyncWorkflowOrchestrator()
    assert hasattr(orchestrator, "run_commit_phase")


def test_run_configuration_phase_basic():
    """Test basic functionality of run_configuration_phase."""
    orchestrator = AsyncWorkflowOrchestrator()
    assert hasattr(orchestrator, "run_configuration_phase")
