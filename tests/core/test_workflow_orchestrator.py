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
# Regression tests for the ratchet bug fix.
#
# Bug: ``_clear_oneiric_cache`` hardcoded a sqlite path under
# ``pkg_path/.oneiric_cache/workflow_checkpoints.sqlite`` that oneiric never
# reads (oneiric stores at ``Path.cwd()/.crackerjack/oneiric_cache/...``).
# Consequence: a partial workflow failure left a checkpoint on disk; the
# next invocation skipped already-completed phases silently.
#
# Fix: delegate to ``runtime.workflow_bridge._checkpoint_store.clear(...)``
# so the same database oneiric actually consults is wiped. The tests below
# pin (a) the new signature, (b) the absence of the hardcoded path, and
# (c) the runtime handshake wiring in ``run_complete_workflow``.
# ---------------------------------------------------------------------------


def test_clear_oneiric_cache_delegates_to_checkpoint_store() -> None:
    """``_clear_oneiric_cache`` must wipe the store oneiric actually reads.

    Regression for the ratchet bug: a hard-coded sqlite path under
    ``pkg_path/.oneiric_cache`` silently diverged from oneiric's real
    checkpoint location. The fix is to call
    ``runtime.workflow_bridge._checkpoint_store.clear("crackerjack")``
    instead.
    """
    with (
        patch('crackerjack.core.workflow_orchestrator.SessionCoordinator'),
        patch('crackerjack.core.workflow_orchestrator.PhaseCoordinator'),
    ):
        from crackerjack.config import CrackerjackSettings

        pipeline = WorkflowPipeline(settings=CrackerjackSettings())

    mock_runtime = Mock()
    mock_store = Mock()
    mock_runtime.workflow_bridge._checkpoint_store = mock_store

    pipeline._clear_oneiric_cache(mock_runtime)

    mock_store.clear.assert_called_once_with("crackerjack")


def test_clear_oneiric_cache_does_not_target_hardcoded_path(tmp_path) -> None:
    """The hardcoded ``.oneiric_cache`` path must NOT be touched.

    Pin the source-level absence of the old path string so a future
    regression cannot reintroduce the ratchet by rewriting the body.
    """
    from pathlib import Path

    source = (
        Path(__file__).resolve().parent.parent.parent
        / "crackerjack" / "core" / "workflow_orchestrator.py"
    ).read_text()

    # The old implementation connected to this exact sqlite file. If a
    # contributor reverts the fix, the test fails immediately.
    assert ".oneiric_cache" not in source
    assert (
        "workflow_checkpoints.sqlite" not in source
    ), "hard-coded oneiric checkpoint path should not appear in orchestrator"

    # ..and the new delegate must be present. The body aliases the bridge
    # attribute through ``checkpoint_store``, so grep for that, not the
    # attribute name itself.
    assert (
        "_checkpoint_store" in source
    ), "orchestrator must read checkpoint store from the runtime bridge"
    assert (
        'clear("crackerjack")' in source
    ), "orchestrator must clear the crackerjack workflow key"


def test_clear_oneiric_cache_returns_silently_when_store_is_none() -> None:
    """A missing ``_checkpoint_store`` (checkpointing disabled) is a no-op.

    Oneiric sets ``_checkpoint_store = None`` when checkpointing is
    disabled. The previous implementation opened sqlite unconditionally; the
    new path must no-op cleanly.
    """
    with (
        patch('crackerjack.core.workflow_orchestrator.SessionCoordinator'),
        patch('crackerjack.core.workflow_orchestrator.PhaseCoordinator'),
    ):
        from crackerjack.config import CrackerjackSettings

        pipeline = WorkflowPipeline(settings=CrackerjackSettings())

    mock_runtime = Mock()
    mock_runtime.workflow_bridge._checkpoint_store = None

    # Must not raise.
    pipeline._clear_oneiric_cache(mock_runtime)


def test_clear_oneiric_cache_swallows_store_errors() -> None:
    """Clear-store failures must log a warning, not crash the run."""
    with (
        patch('crackerjack.core.workflow_orchestrator.SessionCoordinator'),
        patch('crackerjack.core.workflow_orchestrator.PhaseCoordinator'),
    ):
        from crackerjack.config import CrackerjackSettings

        pipeline = WorkflowPipeline(settings=CrackerjackSettings())

    mock_runtime = Mock()
    mock_store = Mock()
    mock_store.clear.side_effect = RuntimeError("store down")
    mock_runtime.workflow_bridge._checkpoint_store = mock_store

    # Should not raise even though the underlying store blew up.
    pipeline._clear_oneiric_cache(mock_runtime)
    mock_store.clear.assert_called_once_with("crackerjack")


@patch('crackerjack.core.workflow_orchestrator.load_settings')
@patch('crackerjack.core.workflow_orchestrator.SessionCoordinator')
@patch('crackerjack.core.workflow_orchestrator.PhaseCoordinator')
@patch('crackerjack.core.workflow_orchestrator.build_oneiric_runtime')
@patch('crackerjack.core.workflow_orchestrator.register_crackerjack_workflow')
@pytest.mark.asyncio
async def test_run_complete_workflow_clears_cache_via_runtime(
    mock_register_wf,
    mock_build_runtime,
    mock_phase_coord,
    mock_session_coord,
    mock_load_settings,
) -> None:
    """``run_complete_workflow`` must wire the runtime into the clear call.

    The ratchet fix introduced ``_clear_oneiric_cache(runtime)``. This test
    ensures the handshake stays intact: every public workflow entrypoint
    passes the freshly-built runtime through to the clear step, so there is
    exactly one path the developer can break without immediate noise.
    """
    from crackerjack.config import CrackerjackSettings

    mock_settings = CrackerjackSettings()
    mock_load_settings.return_value = mock_settings

    mock_runtime = Mock()
    mock_runtime.workflow_bridge = Mock()
    mock_runtime.workflow_bridge._checkpoint_store = None
    mock_runtime.workflow_bridge.execute_dag = AsyncMock(
        return_value={"results": {"hook1": True}}
    )
    mock_build_runtime.return_value = mock_runtime

    pipeline = WorkflowPipeline(settings=mock_settings)
    pipeline.session.initialize_session_tracking = Mock()
    pipeline.session.finalize_session = Mock()
    pipeline._clear_oneiric_cache = Mock()

    await pipeline.run_complete_workflow({"test": "options"})

    # The fix calls _clear_oneiric_cache with the runtime as its sole
    # non-self argument so the checkpoint store wire-up can see the same
    # database oneiric reads.
    pipeline._clear_oneiric_cache.assert_called_once_with(mock_runtime)


# Define AsyncMock for older Python versions if needed
class AsyncMock(Mock):
    async def __call__(self, *args, **kwargs):
        return super(AsyncMock, self).__call__(*args, **kwargs)
