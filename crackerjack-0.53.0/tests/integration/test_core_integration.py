"""Integration tests for core workflow components."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.config import CrackerjackSettings
from crackerjack.core.console import CrackerjackConsole
from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.core.workflow_orchestrator import WorkflowPipeline


class TestCoreIntegration:
    """Test integration between core components."""

    def test_session_phase_coordinator_integration(self) -> None:
        """Test integration between SessionCoordinator and PhaseCoordinator."""
        # Create a shared console and package path
        console = CrackerjackConsole()
        pkg_path = Path("/tmp/test_integration")

        # Create coordinators with shared resources
        session = SessionCoordinator(console=console, pkg_path=pkg_path)
        phase = PhaseCoordinator(
            console=console,
            pkg_path=pkg_path,
            session=session,
        )

        # Verify they share the same session
        assert phase.session is session

        # Test that phase operations update session tracking
        options = MagicMock()
        options.track_progress = True

        # Initialize session tracking
        session.initialize_session_tracking(options)

        # Verify session tracker exists
        assert session.session_tracker is not None

    def test_workflow_pipeline_phase_integration(self) -> None:
        """Test integration between WorkflowPipeline and PhaseCoordinator."""
        console = CrackerjackConsole()
        pkg_path = Path("/tmp/test_wf_integration")
        settings = CrackerjackSettings()

        # Create pipeline with custom phase coordinator
        phase_coordinator = PhaseCoordinator(
            console=console,
            pkg_path=pkg_path,
        )
        session_coordinator = SessionCoordinator(
            console=console,
            pkg_path=pkg_path,
        )

        pipeline = WorkflowPipeline(
            console=console,
            pkg_path=pkg_path,
            settings=settings,
            session=session_coordinator,
            phases=phase_coordinator,
        )

        # Verify the pipeline has the correct coordinators
        assert pipeline.phases is phase_coordinator
        assert pipeline.session is session_coordinator

    def test_session_tracking_through_pipeline(self) -> None:
        """Test that session tracking works through the pipeline."""
        console = CrackerjackConsole()
        pkg_path = Path("/tmp/test_tracking")

        session = SessionCoordinator(console=console, pkg_path=pkg_path)
        phase = PhaseCoordinator(
            console=console,
            pkg_path=pkg_path,
            session=session,
        )

        # Enable tracking
        options = MagicMock()
        options.track_progress = True

        # Initialize session tracking
        session.initialize_session_tracking(options)

        # Track a task through the session
        task_id = session.track_task("test_task", "Test Task", "Test details")

        # Verify the task was tracked
        assert task_id == "test_task"
        if session.session_tracker:
            assert "test_task" in session.session_tracker.tasks

    def test_phase_coordinator_task_tracking(self) -> None:
        """Test that phase coordinator integrates with session task tracking."""
        console = CrackerjackConsole()
        pkg_path = Path("/tmp/test_phase_tracking")

        session = SessionCoordinator(console=console, pkg_path=pkg_path)
        phase = PhaseCoordinator(
            console=console,
            pkg_path=pkg_path,
            session=session,
        )

        # Enable tracking
        options = MagicMock()
        options.track_progress = True

        # Initialize session tracking
        session.initialize_session_tracking(options)

        # Simulate a phase operation that should update session tracking
        session.track_task("phase_task", "Phase Task", "Phase details")

        # Verify the task was tracked in the session
        if session.session_tracker:
            assert "phase_task" in session.session_tracker.tasks


@pytest.mark.asyncio
class TestAsyncCoreIntegration:
    """Test async integration between core components."""

    async def test_async_workflow_pipeline_integration(self) -> None:
        """Test async workflow pipeline integration."""
        from crackerjack.core.async_workflow_orchestrator import AsyncWorkflowPipeline

        console = CrackerjackConsole()
        pkg_path = Path("/tmp/test_async_integration")

        session = SessionCoordinator(console=console, pkg_path=pkg_path)
        phase = PhaseCoordinator(
            console=console,
            pkg_path=pkg_path,
            session=session,
        )
        logger = MagicMock()

        async_pipeline = AsyncWorkflowPipeline(
            logger=logger,
            console=console,
            pkg_path=pkg_path,
            session=session,
            phases=phase,
        )

        # Verify the async pipeline has the correct components
        assert async_pipeline.session is session
        assert async_pipeline.phases is phase

        # Mock the underlying pipeline's run method
        with patch.object(async_pipeline._pipeline, 'run_complete_workflow', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = True

            options = {"test": True}
            result = await async_pipeline.run_complete_workflow_async(options)

            assert result is True
            mock_run.assert_called_once_with(options)

    async def test_async_workflow_with_session_tracking(self) -> None:
        """Test async workflow with session tracking."""
        from crackerjack.core.async_workflow_orchestrator import AsyncWorkflowPipeline

        console = CrackerjackConsole()
        pkg_path = Path("/tmp/test_async_session")

        session = SessionCoordinator(console=console, pkg_path=pkg_path)
        phase = PhaseCoordinator(
            console=console,
            pkg_path=pkg_path,
            session=session,
        )
        logger = MagicMock()

        async_pipeline = AsyncWorkflowPipeline(
            logger=logger,
            console=console,
            pkg_path=pkg_path,
            session=session,
            phases=phase,
        )

        # Enable session tracking
        options = MagicMock()
        options.track_progress = True

        session.initialize_session_tracking(options)

        # Mock the underlying pipeline's run method
        with patch.object(async_pipeline._pipeline, 'run_complete_workflow', new_callable=AsyncMock) as mock_run:
            mock_run.return_value = True

            wf_options = {"test": True}
            result = await async_pipeline.run_complete_workflow_async(wf_options)

            assert result is True
            # Verify that session tracking was active
            assert session.session_tracker is not None


class TestCoreComponentFactories:
    """Test factories and creation patterns for core components."""

    def test_create_workflow_pipeline_with_defaults(self) -> None:
        """Test creating a workflow pipeline with default components."""
        pipeline = WorkflowPipeline()

        # Verify default components were created
        assert isinstance(pipeline.console, CrackerjackConsole)
        assert isinstance(pipeline.session, SessionCoordinator)
        assert isinstance(pipeline.phases, PhaseCoordinator)
        assert isinstance(pipeline.settings, CrackerjackSettings)

    def test_create_phase_coordinator_with_defaults(self) -> None:
        """Test creating a phase coordinator with default components."""
        phase = PhaseCoordinator()

        # Verify default components were created
        assert isinstance(phase.console, CrackerjackConsole)
        assert isinstance(phase.session, SessionCoordinator)
        assert phase.hook_manager is not None
        assert phase.test_manager is not None
        assert phase.publish_manager is not None

    def test_create_session_coordinator_with_defaults(self) -> None:
        """Test creating a session coordinator with default components."""
        session = SessionCoordinator()

        # Verify default components were created
        assert isinstance(session.console, CrackerjackConsole)
        assert session.pkg_path == Path.cwd()
        assert session.session_id is not None


class TestCoreErrorHandlingIntegration:
    """Test error handling integration between core components."""

    def test_session_error_handling(self) -> None:
        """Test that session coordinator handles errors gracefully."""
        session = SessionCoordinator()

        # Test that methods don't crash when session tracker is None
        # These should not raise exceptions
        session.complete_task("nonexistent_task", "details", ["file.py"])
        session.fail_task("nonexistent_task", "error", "details")
        session.update_task("nonexistent_task", "status", details="details")

        # Test summary methods
        summary = session.get_session_summary()
        assert "tasks_count" in summary

    def test_phase_coordinator_error_handling(self) -> None:
        """Test that phase coordinator handles errors gracefully."""
        phase = PhaseCoordinator()

        # Test that methods don't crash when required services are mocked
        options = MagicMock()
        options.skip_hooks = True

        # These should not raise exceptions even with minimal setup
        result = phase.run_hooks_phase(options)
        assert result is True

        result = phase.run_fast_hooks_only(options)
        assert result is True

        options.skip_hooks = False
        options.test = False
        options.run_tests = False
        result = phase.run_testing_phase(options)
        assert result is True
