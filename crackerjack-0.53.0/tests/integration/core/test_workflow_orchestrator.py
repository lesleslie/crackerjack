"""Tests for workflow_orchestrator.py."""

import sqlite3
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.config import CrackerjackSettings
from crackerjack.core.workflow_orchestrator import (
    WorkflowPipeline,
    WorkflowResult,
    _adapt_options,
    _workflow_result_success,
)


@pytest.fixture
def mock_settings(tmp_path):
    """Create mock settings with execution.verbose=True."""
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
    mock = MagicMock(spec=SessionCoordinator)
    mock.start_time = 0.0
    return mock


@pytest.fixture
def mock_phases():
    """Create mock phase coordinator."""
    from crackerjack.core.phase_coordinator import PhaseCoordinator
    mock = MagicMock(spec=PhaseCoordinator)
    return mock


@pytest.fixture
def pipeline(tmp_path, mock_console, mock_settings, mock_session, mock_phases):
    """Create WorkflowPipeline instance for testing."""
    return WorkflowPipeline(
        console=mock_console,
        pkg_path=tmp_path,
        settings=mock_settings,
        session=mock_session,
        phases=mock_phases,
    )


class TestWorkflowResult:
    """Test suite for WorkflowResult dataclass."""

    def test_initialization(self):
        """Test WorkflowResult initializes correctly."""
        result = WorkflowResult(success=True, details={"key": "value"})
        assert result.success is True
        assert result.details == {"key": "value"}


class TestWorkflowPipeline:
    """Test suite for WorkflowPipeline."""

    def test_initialization_default_console(self, tmp_path, mock_settings):
        """Test initialization with default console."""
        pipeline = WorkflowPipeline(pkg_path=tmp_path, settings=mock_settings)
        assert pipeline.console is not None
        assert pipeline.pkg_path == tmp_path
        assert pipeline.settings is not None
        assert pipeline.session is not None
        assert pipeline.phases is not None

    def test_initialization_with_all_deps(
        self, mock_console, mock_settings, mock_session, mock_phases, tmp_path
    ):
        """Test initialization with all dependencies injected."""
        pipeline = WorkflowPipeline(
            console=mock_console,
            pkg_path=tmp_path,
            settings=mock_settings,
            session=mock_session,
            phases=mock_phases,
        )
        assert pipeline.console == mock_console
        assert pipeline.pkg_path == tmp_path
        assert pipeline.settings == mock_settings
        assert pipeline.session == mock_session
        assert pipeline.phases == mock_phases

    def test_initialize_workflow_session(self, pipeline):
        """Test workflow session initialization."""
        options = MagicMock()
        pipeline._initialize_workflow_session(options)
        pipeline.session.initialize_session_tracking.assert_called_once_with(options)

    def test_clear_oneiric_cache_no_database(self, pipeline, tmp_path):
        """Test cache clearing when database doesn't exist."""
        # Database doesn't exist, should not crash
        pipeline._clear_oneiric_cache()
        # Just verify no exception raised

    def test_clear_oneiric_cache_with_database(self, pipeline, tmp_path):
        """Test cache clearing with existing database."""
        cache_dir = tmp_path / ".oneiric_cache"
        cache_dir.mkdir(parents=True)
        cache_db = cache_dir / "workflow_checkpoints.sqlite"

        # Create database and tables
        conn = sqlite3.connect(cache_db)
        cursor = conn.cursor()
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS workflow_checkpoints "
            "(workflow_key TEXT, run_id TEXT)"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS workflow_executions "
            "(workflow_key TEXT, run_id TEXT)"
        )
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS workflow_execution_nodes "
            "(run_id TEXT, node_id TEXT)"
        )
        cursor.execute(
            "INSERT INTO workflow_checkpoints VALUES ('crackerjack', 'test-run-1')"
        )
        cursor.execute(
            "INSERT INTO workflow_executions VALUES ('crackerjack', 'test-run-1')"
        )
        cursor.execute(
            "INSERT INTO workflow_execution_nodes VALUES ('test-run-1', 'node-1')"
        )
        conn.commit()
        conn.close()

        # Clear cache
        pipeline._clear_oneiric_cache()

        # Verify cache was cleared (tables should be empty)
        conn = sqlite3.connect(cache_db)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM workflow_checkpoints WHERE workflow_key = ?", ("crackerjack",))
        count = cursor.fetchone()[0]
        assert count == 0

        cursor.execute("SELECT COUNT(*) FROM workflow_executions WHERE workflow_key = ?", ("crackerjack",))
        count = cursor.fetchone()[0]
        assert count == 0

        conn.close()

    def test_clear_oneiric_cache_handles_corruption(self, pipeline, tmp_path):
        """Test cache clearing handles corrupted database gracefully."""
        cache_dir = tmp_path / ".oneiric_cache"
        cache_dir.mkdir(parents=True)
        cache_db = cache_dir / "workflow_checkpoints.sqlite"

        # Create invalid/corrupted database
        cache_db.write_text("corrupted data")

        # Should not crash
        pipeline._clear_oneiric_cache()

    def test_run_fast_hooks_only(self, pipeline):
        """Test running fast hooks only."""
        options = MagicMock()
        pipeline.phases.run_fast_hooks_only = MagicMock(return_value=True)

        result = pipeline.run_fast_hooks_only(options)
        assert result is True
        pipeline.phases.run_fast_hooks_only.assert_called_once_with(options)

    def test_run_comprehensive_hooks_only(self, pipeline):
        """Test running comprehensive hooks only."""
        options = MagicMock()
        pipeline.phases.run_comprehensive_hooks_only = MagicMock(return_value=True)

        result = pipeline.run_comprehensive_hooks_only(options)
        assert result is True
        pipeline.phases.run_comprehensive_hooks_only.assert_called_once_with(options)

    def test_run_testing_phase(self, pipeline):
        """Test running testing phase."""
        options = MagicMock()
        mock_method = MagicMock(return_value=True)
        pipeline.phases.run_testing_phase = mock_method

        result = pipeline.run_testing_phase(options)
        assert result is True
        mock_method.assert_called_once_with(options)

    def test_run_cleaning_phase(self, pipeline):
        """Test running cleaning phase."""
        options = MagicMock()
        mock_method = MagicMock(return_value=True)
        pipeline.phases.run_cleaning_phase = mock_method

        result = pipeline.run_cleaning_phase(options)
        assert result is True
        mock_method.assert_called_once_with(options)

    @pytest.mark.asyncio
    async def test_run_complete_workflow_success(self, pipeline):
        """Test complete workflow execution with success."""
        options = MagicMock()

        # Mock the Oneiric runtime
        mock_runtime = MagicMock()
        mock_runtime.workflow_bridge.execute_dag = AsyncMock(
            return_value={"results": {"task1": True, "task2": True}}
        )

        with patch(
            "crackerjack.core.workflow_orchestrator.build_oneiric_runtime",
            return_value=mock_runtime,
        ):
            result = await pipeline.run_complete_workflow(options)

        assert result is True
        pipeline.session.initialize_session_tracking.assert_called_once_with(options)
        pipeline.session.finalize_session.assert_called_once()
        # Verify session.finalize_session was called with success=True
        call_args = pipeline.session.finalize_session.call_args
        assert call_args[0][1] is True  # Second argument is success

    @pytest.mark.asyncio
    async def test_run_complete_workflow_failure(self, pipeline):
        """Test complete workflow execution with failure."""
        options = MagicMock()

        # Mock the Oneiric runtime to return failure
        mock_runtime = MagicMock()
        mock_runtime.workflow_bridge.execute_dag = AsyncMock(
            return_value={"results": {"task1": True, "task2": False}}
        )

        with patch(
            "crackerjack.core.workflow_orchestrator.build_oneiric_runtime",
            return_value=mock_runtime,
        ):
            result = await pipeline.run_complete_workflow(options)

        assert result is False

    @pytest.mark.asyncio
    async def test_run_complete_workflow_exception(self, pipeline, mock_settings):
        """Test complete workflow execution with exception."""
        options = MagicMock()

        # Mock the Oneiric runtime to raise exception
        mock_runtime = MagicMock()
        mock_runtime.workflow_bridge.execute_dag = AsyncMock(
            side_effect=RuntimeError("Workflow error")
        )

        with patch(
            "crackerjack.core.workflow_orchestrator.build_oneiric_runtime",
            return_value=mock_runtime,
        ):
            result = await pipeline.run_complete_workflow(options)

        assert result is False
        # Verify session was finalized with failure
        pipeline.session.finalize_session.assert_called_once()
        call_args = pipeline.session.finalize_session.call_args
        assert call_args[0][1] is False

    @pytest.mark.asyncio
    async def test_run_complete_workflow_verbose_logging(self, pipeline, mock_settings):
        """Test verbose logging in workflow execution."""
        # Enable verbose mode
        mock_settings.execution.verbose = True
        options = MagicMock()

        # Mock the Oneiric runtime to raise exception
        mock_runtime = MagicMock()
        mock_runtime.workflow_bridge.execute_dag = AsyncMock(
            side_effect=RuntimeError("Test error")
        )

        with patch(
            "crackerjack.core.workflow_orchestrator.build_oneiric_runtime",
            return_value=mock_runtime,
        ):
            result = await pipeline.run_complete_workflow(options)

        assert result is False

    @pytest.mark.asyncio
    async def test_run_complete_workflow_non_verbose_logging(self, pipeline):
        """Test non-verbose logging in workflow execution."""
        # Disable verbose mode
        pipeline.settings.execution.verbose = False
        options = MagicMock()

        # Mock the Oneiric runtime to raise exception
        mock_runtime = MagicMock()
        mock_runtime.workflow_bridge.execute_dag = AsyncMock(
            side_effect=RuntimeError("Test error")
        )

        with patch(
            "crackerjack.core.workflow_orchestrator.build_oneiric_runtime",
            return_value=mock_runtime,
        ):
            result = await pipeline.run_complete_workflow(options)

        assert result is False

    def test_execute_workflow_sync_wrapper(self, pipeline):
        """Test sync wrapper for workflow execution."""
        options = MagicMock()

        # Mock the async method
        pipeline.run_complete_workflow = AsyncMock(return_value=True)

        result = pipeline.execute_workflow(options)
        assert result is True

    def test_run_complete_workflow_sync(self, pipeline):
        """Test sync version of complete workflow."""
        options = MagicMock()

        # Mock the async method
        pipeline.run_complete_workflow = AsyncMock(return_value=True)

        result = pipeline.run_complete_workflow_sync(options)
        assert result is True


class TestWorkflowResultSuccess:
    """Test suite for _workflow_result_success helper function."""

    def test_success_with_no_results(self):
        """Test success when no results dict."""
        result = _workflow_result_success({})
        assert result is True

    def test_success_with_none(self):
        """Test success when result is None."""
        result = _workflow_result_success(None)
        assert result is True

    def test_success_with_all_true(self):
        """Test success when all results are True."""
        result = _workflow_result_success({"results": {"task1": True, "task2": True}})
        assert result is True

    def test_success_with_all_false(self):
        """Test failure when all results are False."""
        result = _workflow_result_success({"results": {"task1": False, "task2": False}})
        assert result is False

    def test_success_with_mixed_results(self):
        """Test failure when some results are False."""
        result = _workflow_result_success(
            {"results": {"task1": True, "task2": False, "task3": True}}
        )
        assert result is False

    def test_success_with_non_dict_results(self):
        """Test success when results is not a dict."""
        result = _workflow_result_success("not a dict")
        assert result is True


class TestAdaptOptions:
    """Test suite for _adapt_options helper function."""

    def test_adapt_options_returns_input(self):
        """Test adapter returns input unchanged."""
        options = MagicMock()
        result = _adapt_options(options)
        assert result is options

    def test_adapt_options_with_none(self):
        """Test adapter handles None."""
        result = _adapt_options(None)
        assert result is None

    def test_adapt_options_with_dict(self):
        """Test adapter handles dict."""
        options = {"key": "value"}
        result = _adapt_options(options)
        assert result == options
