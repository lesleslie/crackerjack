import asyncio
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
from crackerjack.core.workflow_orchestrator import (
    WorkflowPipeline,
    WorkflowResult,
    _workflow_result_success,
    _adapt_options
)


def test_workflow_result_dataclass():
    """Test the WorkflowResult dataclass."""
    result = WorkflowResult(success=True, details={"key": "value"})

    assert result.success is True
    assert result.details == {"key": "value"}


def test_adapt_options():
    """Test the _adapt_options function."""
    test_obj = {"some": "options"}
    result = _adapt_options(test_obj)

    assert result is test_obj  # Should return the same object


def test_workflow_result_success():
    """Test the _workflow_result_success function."""
    # Test with successful results
    success_result = {"results": {"hook1": True, "hook2": "success"}}
    assert _workflow_result_success(success_result) is True

    # Test with mixed results (one failure makes it fail)
    mixed_result = {"results": {"hook1": True, "hook2": False}}
    assert _workflow_result_success(mixed_result) is False

    # Test with no results key
    no_results = {"other_key": "value"}
    assert _workflow_result_success(no_results) is True

    # Test with empty results
    empty_results = {"results": {}}
    assert _workflow_result_success(empty_results) is True

    # Test with None
    assert _workflow_result_success(None) is True


@patch('crackerjack.core.workflow_orchestrator.load_settings')
@patch('crackerjack.core.workflow_orchestrator.SessionCoordinator')
@patch('crackerjack.core.workflow_orchestrator.PhaseCoordinator')
def test_workflow_pipeline_initialization(mock_phase_coord, mock_session_coord, mock_load_settings):
    """Test WorkflowPipeline initialization."""
    from crackerjack.config import CrackerjackSettings

    mock_settings = Mock(spec=CrackerjackSettings)
    mock_load_settings.return_value = mock_settings

    pkg_path = Path("/tmp/test")
    console = Mock()

    pipeline = WorkflowPipeline(
        console=console,
        pkg_path=pkg_path,
        settings=mock_settings
    )

    assert pipeline.console == console
    assert pipeline.pkg_path == pkg_path
    assert pipeline.settings == mock_settings
    assert pipeline.session is not None
    assert pipeline.phases is not None


@patch('crackerjack.core.workflow_orchestrator.load_settings')
@patch('crackerjack.core.workflow_orchestrator.SessionCoordinator')
@patch('crackerjack.core.workflow_orchestrator.PhaseCoordinator')
@patch('crackerjack.core.workflow_orchestrator.build_oneiric_runtime')
@patch('crackerjack.core.workflow_orchestrator.register_crackerjack_workflow')
@pytest.mark.asyncio
async def test_run_complete_workflow_success(
    mock_register_wf,
    mock_build_runtime,
    mock_phase_coord,
    mock_session_coord,
    mock_load_settings
):
    """Test running a complete workflow successfully."""
    from crackerjack.config import CrackerjackSettings

    # Use real settings instance instead of mock for nested attributes
    mock_settings = CrackerjackSettings()
    mock_load_settings.return_value = mock_settings

    mock_runtime = Mock()
    mock_runtime.workflow_bridge = Mock()
    mock_runtime.workflow_bridge.execute_dag = AsyncMock(return_value={"results": {"hook1": True}})
    mock_build_runtime.return_value = mock_runtime

    pipeline = WorkflowPipeline(settings=mock_settings)

    # Mock session coordinator methods
    pipeline.session.initialize_session_tracking = Mock()
    pipeline.session.finalize_session = Mock()

    # Mock phase coordinator
    pipeline.phases.run_fast_hooks_only = Mock(return_value=True)

    options = {"test": "options"}
    result = await pipeline.run_complete_workflow(options)

    assert result is True
    mock_build_runtime.assert_called_once()
    mock_register_wf.assert_called_once()
    pipeline.session.finalize_session.assert_called_once()


@patch('crackerjack.core.workflow_orchestrator.load_settings')
@patch('crackerjack.core.workflow_orchestrator.SessionCoordinator')
@patch('crackerjack.core.workflow_orchestrator.PhaseCoordinator')
@patch('crackerjack.core.workflow_orchestrator.build_oneiric_runtime')
@patch('crackerjack.core.workflow_orchestrator.register_crackerjack_workflow')
@pytest.mark.asyncio
async def test_run_complete_workflow_failure(
    mock_register_wf,
    mock_build_runtime,
    mock_phase_coord,
    mock_session_coord,
    mock_load_settings
):
    """Test running a complete workflow with failure."""
    from crackerjack.config import CrackerjackSettings

    # Use real settings instance instead of mock for nested attributes
    mock_settings = CrackerjackSettings()
    mock_load_settings.return_value = mock_settings

    mock_runtime = Mock()
    mock_runtime.workflow_bridge = Mock()
    mock_runtime.workflow_bridge.execute_dag = AsyncMock(side_effect=Exception("Workflow failed"))
    mock_build_runtime.return_value = mock_runtime

    pipeline = WorkflowPipeline(settings=mock_settings)

    # Mock session coordinator methods
    pipeline.session.initialize_session_tracking = Mock()
    pipeline.session.finalize_session = Mock()

    options = {"test": "options"}
    result = await pipeline.run_complete_workflow(options)

    assert result is False
    pipeline.session.finalize_session.assert_called_once_with(pipeline.session.start_time, success=False)


@patch('crackerjack.core.workflow_orchestrator.load_settings')
@patch('crackerjack.core.workflow_orchestrator.SessionCoordinator')
@patch('crackerjack.core.workflow_orchestrator.PhaseCoordinator')
def test_run_complete_workflow_sync(mock_phase_coord, mock_session_coord, mock_load_settings):
    """Test the sync version of run_complete_workflow."""
    from crackerjack.config import CrackerjackSettings

    mock_settings = CrackerjackSettings()
    mock_load_settings.return_value = mock_settings

    pipeline = WorkflowPipeline(settings=mock_settings)

    # Mock the async method
    with patch.object(pipeline, 'run_complete_workflow', new_callable=AsyncMock) as mock_async_run:
        mock_async_run.return_value = True

        result = pipeline.run_complete_workflow_sync({"test": "options"})

        assert result is True
        mock_async_run.assert_called_once_with({"test": "options"})


@patch('crackerjack.core.workflow_orchestrator.load_settings')
@patch('crackerjack.core.workflow_orchestrator.SessionCoordinator')
@patch('crackerjack.core.workflow_orchestrator.PhaseCoordinator')
def test_execute_workflow(mock_phase_coord, mock_session_coord, mock_load_settings):
    """Test the execute_workflow method."""
    from crackerjack.config import CrackerjackSettings

    mock_settings = CrackerjackSettings()
    mock_load_settings.return_value = mock_settings

    pipeline = WorkflowPipeline(settings=mock_settings)

    # Mock the sync method
    with patch.object(pipeline, 'run_complete_workflow_sync') as mock_sync_run:
        mock_sync_run.return_value = True

        result = pipeline.execute_workflow({"test": "options"})

        assert result is True
        mock_sync_run.assert_called_once_with({"test": "options"})


@patch('crackerjack.core.workflow_orchestrator.load_settings')
@patch('crackerjack.core.workflow_orchestrator.SessionCoordinator')
@patch('crackerjack.core.workflow_orchestrator.PhaseCoordinator')
def test_initialize_workflow_session(mock_phase_coord, mock_session_coord, mock_load_settings):
    """Test initializing workflow session."""
    from crackerjack.config import CrackerjackSettings

    mock_settings = CrackerjackSettings()
    mock_load_settings.return_value = mock_settings

    pipeline = WorkflowPipeline(settings=mock_settings)

    options = {"test": "options"}
    pipeline._initialize_workflow_session(options)

    pipeline.session.initialize_session_tracking.assert_called_once_with(options)


@patch('crackerjack.core.workflow_orchestrator.load_settings')
@patch('crackerjack.core.workflow_orchestrator.SessionCoordinator')
@patch('crackerjack.core.workflow_orchestrator.PhaseCoordinator')
def test_run_fast_hooks_phase(mock_phase_coord, mock_session_coord, mock_load_settings):
    """Test running fast hooks phase."""
    from crackerjack.config import CrackerjackSettings

    mock_settings = CrackerjackSettings()
    mock_load_settings.return_value = mock_settings

    pipeline = WorkflowPipeline(settings=mock_settings)

    # Mock the phases run method
    pipeline.phases.run_fast_hooks_only = Mock(return_value=True)

    options = {"test": "options"}
    result = pipeline._run_fast_hooks_phase(options)

    assert result is True
    pipeline.phases.run_fast_hooks_only.assert_called_once_with(options)


# ---------------------------------------------------------------------------
# Policy test: workflow checkpointing is disabled at the orchestrator level.
#
# Crackerjack is a quality-gate workflow: every run re-executes every phase
# from a known-fresh state. Oneiric's persistent task checkpointing (Store
# 1) and execution tracing (Store 2) are gated by the same boolean; for
# crackerjack's use case both are dead weight — the in-memory DAG checkpoint
# in oneiric/runtime/dag.py is sufficient for within-run information flow,
# and a file-based SQLite store is not serverless-durable.
#
# The orchestrator is built with enable_workflow_checkpoints=False so
# _checkpoint_store and _execution_store are both None and all load/save/
# clear paths short-circuit. See
# .claude/decisions/2026-10-13-checkpoint-disabled.md for the policy.
# ---------------------------------------------------------------------------


def test_build_oneiric_runtime_disables_workflow_checkpointing() -> None:
    """Quality-gate workflow policy: orchestrator checkpointing is off.

    build_oneiric_runtime must construct the orchestrator with
    enable_workflow_checkpoints=False so that the bridge's persistent
    stores are both None. We mock the oneiric constructor chain so the
    test does not depend on pydantic-settings validation of OneiricSettings
    (which has a separate, pre-existing compatibility issue with
    pydantic v2.14+, tracked independently); the policy we pin is the
    kwarg passed to RuntimeOrchestrator, not the runtime's full
    construction.
    """
    with (
        patch("crackerjack.runtime.oneiric_workflow.OneiricSettings"),
        patch("crackerjack.runtime.oneiric_workflow.Resolver"),
        patch("crackerjack.runtime.oneiric_workflow.LifecycleManager"),
        patch(
            "crackerjack.runtime.oneiric_workflow.RuntimeOrchestrator"
        ) as mock_orchestrator,
        patch("crackerjack.runtime.oneiric_workflow._build_secrets_hook"),
        patch("crackerjack.runtime.oneiric_workflow.resolver_settings_from_config"),
    ):
        from crackerjack.runtime.oneiric_workflow import build_oneiric_runtime

        build_oneiric_runtime()

    # Pin the policy at the constructor call site: a future contributor
    # who removes enable_workflow_checkpoints=False (or flips it to True)
    # fails this test. The companion decision note
    # (.claude/decisions/2026-10-13-checkpoint-disabled.md) records why
    # the default is False for crackerjack specifically; other Bodai
    # consumers may differ.
    assert (
        mock_orchestrator.call_args.kwargs.get("enable_workflow_checkpoints")
        is False
    )


# Define AsyncMock for older Python versions if needed
class AsyncMock(Mock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)
