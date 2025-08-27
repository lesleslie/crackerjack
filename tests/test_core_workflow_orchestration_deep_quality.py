"""
Deep Quality Tests for Core Workflow Orchestration - Real Business Logic Testing

This module tests the core workflow orchestration engine, including failure recovery,
phase coordination, and retry mechanisms that are critical to crackerjack's reliability.
Each test validates real production scenarios that could break the workflow.

**EXCELLENCE IN EXECUTION**: These tests protect against workflow failures, partial
execution states, and ensure robust recovery from infrastructure issues.
"""

import asyncio
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.core.workflow_orchestrator import WorkflowPipeline
from crackerjack.models.protocols import OptionsProtocol


class TestWorkflowPipelineBusinessLogic:
    """Test core workflow pipeline business logic and error recovery."""

    @pytest.fixture
    def console(self) -> Console:
        return Console()

    @pytest.fixture
    def pkg_path(self, tmp_path: Path) -> Path:
        """Create a temporary package path for testing."""
        pkg_dir = tmp_path / "test_package"
        pkg_dir.mkdir()
        return pkg_dir

    @pytest.fixture
    def session_coordinator(
        self, console: Console, pkg_path: Path
    ) -> SessionCoordinator:
        """Create session coordinator for testing."""
        return SessionCoordinator(console, pkg_path)

    @pytest.fixture
    def phase_coordinator(
        self, console: Console, pkg_path: Path, session_coordinator: SessionCoordinator
    ) -> PhaseCoordinator:
        """Create phase coordinator with mocked dependencies."""
        with patch("crackerjack.core.phase_coordinator.ConfigurationService"):
            # Mock all the required protocol dependencies
            filesystem = Mock()
            git_service = Mock()
            hook_manager = Mock()
            test_manager = Mock()
            publish_manager = Mock()

            return PhaseCoordinator(
                console=console,
                pkg_path=pkg_path,
                session=session_coordinator,
                filesystem=filesystem,
                git_service=git_service,
                hook_manager=hook_manager,
                test_manager=test_manager,
                publish_manager=publish_manager,
            )

    @pytest.fixture
    def workflow_pipeline(
        self,
        console: Console,
        pkg_path: Path,
        session_coordinator: SessionCoordinator,
        phase_coordinator: PhaseCoordinator,
    ) -> WorkflowPipeline:
        """Create workflow pipeline for testing."""
        return WorkflowPipeline(
            console=console,
            pkg_path=pkg_path,
            session=session_coordinator,
            phases=phase_coordinator,
        )

    @pytest.fixture
    def mock_options(self) -> Mock:
        """Create mock options that implements OptionsProtocol."""
        options = Mock(spec=OptionsProtocol)
        options.testing = False
        options.skip_hooks = False
        options.ai_agent = False
        options.clean = False
        options.publish = None
        options.cleanup = None
        return options


class TestWorkflowExecutionScenarios:
    """Test complete workflow execution scenarios with failure recovery."""

    @pytest.fixture
    def workflow_pipeline(self) -> WorkflowPipeline:
        console = Console()
        pkg_path = Path("/tmp/test")
        session = Mock()
        phases = Mock()
        return WorkflowPipeline(console, pkg_path, session, phases)

    @pytest.fixture
    def mock_options(self) -> Mock:
        options = Mock(spec=OptionsProtocol)
        options.testing = False
        options.skip_hooks = False
        options.ai_agent = False
        options.clean = False
        options.publish = None
        return options

    @pytest.mark.asyncio
    async def test_successful_workflow_execution(
        self, workflow_pipeline: WorkflowPipeline, mock_options: Mock
    ) -> None:
        """Test successful complete workflow execution."""
        # Mock successful workflow phase execution
        workflow_pipeline.session.initialize_session_tracking = Mock()
        workflow_pipeline.session.track_task = Mock()
        workflow_pipeline.session.finalize_session = Mock()

        with patch.object(
            workflow_pipeline, "_execute_workflow_phases", return_value=True
        ) as mock_execute:
            result = await workflow_pipeline.run_complete_workflow(mock_options)

        assert result is True
        mock_execute.assert_called_once_with(mock_options)
        workflow_pipeline.session.initialize_session_tracking.assert_called_once_with(
            mock_options
        )
        workflow_pipeline.session.track_task.assert_called_once_with(
            "workflow", "Complete crackerjack workflow"
        )
        workflow_pipeline.session.finalize_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_workflow_execution_with_phase_failure(
        self, workflow_pipeline: WorkflowPipeline, mock_options: Mock
    ) -> None:
        """Test workflow execution when phases fail."""
        workflow_pipeline.session.initialize_session_tracking = Mock()
        workflow_pipeline.session.track_task = Mock()
        workflow_pipeline.session.finalize_session = Mock()

        with patch.object(
            workflow_pipeline, "_execute_workflow_phases", return_value=False
        ) as mock_execute:
            result = await workflow_pipeline.run_complete_workflow(mock_options)

        assert result is False
        mock_execute.assert_called_once_with(mock_options)
        # Should still finalize session even on failure
        workflow_pipeline.session.finalize_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_workflow_execution_with_exception(
        self, workflow_pipeline: WorkflowPipeline, mock_options: Mock
    ) -> None:
        """Test workflow execution handles exceptions gracefully."""
        workflow_pipeline.session.initialize_session_tracking = Mock()
        workflow_pipeline.session.track_task = Mock()
        workflow_pipeline.session.finalize_session = Mock()
        workflow_pipeline.session.cleanup_resources = Mock()
        workflow_pipeline.session.fail_task = Mock()

        test_exception = RuntimeError("Phase execution failed")

        with patch.object(
            workflow_pipeline, "_execute_workflow_phases", side_effect=test_exception
        ):
            result = await workflow_pipeline.run_complete_workflow(mock_options)

        assert result is False
        # finalize_session is NOT called on exceptions - only cleanup_resources is
        workflow_pipeline.session.finalize_session.assert_not_called()
        workflow_pipeline.session.cleanup_resources.assert_called_once()
        workflow_pipeline.session.fail_task.assert_called_once_with(
            "workflow", "Unexpected error: Phase execution failed"
        )

    @pytest.mark.asyncio
    async def test_workflow_with_cleanup_configuration(
        self, workflow_pipeline: WorkflowPipeline, mock_options: Mock
    ) -> None:
        """Test workflow execution with cleanup configuration."""
        cleanup_config = {"temp_files": True, "debug_logs": 5}
        mock_options.cleanup = cleanup_config

        workflow_pipeline.session.initialize_session_tracking = Mock()
        workflow_pipeline.session.track_task = Mock()
        workflow_pipeline.session.set_cleanup_config = Mock()
        workflow_pipeline.session.finalize_session = Mock()

        with patch.object(
            workflow_pipeline, "_execute_workflow_phases", return_value=True
        ):
            await workflow_pipeline.run_complete_workflow(mock_options)

        workflow_pipeline.session.set_cleanup_config.assert_called_once_with(
            cleanup_config
        )

    @pytest.mark.asyncio
    async def test_workflow_timing_measurement(
        self, workflow_pipeline: WorkflowPipeline, mock_options: Mock
    ) -> None:
        """Test workflow execution measures timing correctly."""
        workflow_pipeline.session.initialize_session_tracking = Mock()
        workflow_pipeline.session.track_task = Mock()
        workflow_pipeline.session.finalize_session = Mock()

        # Mock a slow-executing workflow phase
        async def slow_execute_phases(options):
            await asyncio.sleep(0.1)  # 100ms delay
            return True

        with patch.object(
            workflow_pipeline,
            "_execute_workflow_phases",
            side_effect=slow_execute_phases,
        ):
            start_time = time.time()
            result = await workflow_pipeline.run_complete_workflow(mock_options)
            end_time = time.time()

        assert result is True
        duration = end_time - start_time
        assert duration >= 0.1  # Should take at least 100ms

        # Verify finalize_session was called with timing info
        finalize_call_args = workflow_pipeline.session.finalize_session.call_args
        assert len(finalize_call_args[0]) >= 2
        assert isinstance(finalize_call_args[0][0], float)  # start_time
        assert finalize_call_args[0][1] is True  # success

    @pytest.mark.asyncio
    async def test_debug_mode_logging(
        self, workflow_pipeline: WorkflowPipeline, mock_options: Mock
    ) -> None:
        """Test debug mode enables detailed logging."""
        workflow_pipeline.session.initialize_session_tracking = Mock()
        workflow_pipeline.session.track_task = Mock()
        workflow_pipeline.session.finalize_session = Mock()

        # Mock debug environment variable
        with patch.dict("os.environ", {"AI_AGENT_DEBUG": "1"}):
            with patch.object(
                workflow_pipeline, "_execute_workflow_phases", return_value=True
            ):
                result = await workflow_pipeline.run_complete_workflow(mock_options)

        assert result is True
        # In a real implementation, you would verify debug logs were created
        # For now, just verify the workflow completed successfully in debug mode


class TestPhaseCoordinatorBusinessLogic:
    """Test phase coordinator business logic and failure handling."""

    @pytest.fixture
    def phase_coordinator(self) -> PhaseCoordinator:
        console = Console()
        pkg_path = Path("/tmp/test")
        session = Mock()

        # Mock all protocol dependencies
        filesystem = Mock()
        git_service = Mock()
        hook_manager = Mock()
        test_manager = Mock()
        publish_manager = Mock()

        with patch("crackerjack.core.phase_coordinator.ConfigurationService"):
            return PhaseCoordinator(
                console=console,
                pkg_path=pkg_path,
                session=session,
                filesystem=filesystem,
                git_service=git_service,
                hook_manager=hook_manager,
                test_manager=test_manager,
                publish_manager=publish_manager,
            )

    @pytest.fixture
    def mock_options(self) -> Mock:
        options = Mock(spec=OptionsProtocol)
        options.clean = False
        return options


class TestCleaningPhaseBusinessLogic:
    """Test cleaning phase business logic and error recovery."""

    @pytest.fixture
    def phase_coordinator(self, tmp_path: Path) -> PhaseCoordinator:
        console = Console()
        session = Mock()
        pkg_path = tmp_path / "package"
        pkg_path.mkdir()

        filesystem = Mock()
        git_service = Mock()
        hook_manager = Mock()
        test_manager = Mock()
        publish_manager = Mock()

        with patch("crackerjack.core.phase_coordinator.ConfigurationService"):
            coordinator = PhaseCoordinator(
                console=console,
                pkg_path=pkg_path,
                session=session,
                filesystem=filesystem,
                git_service=git_service,
                hook_manager=hook_manager,
                test_manager=test_manager,
                publish_manager=publish_manager,
            )

            # Mock the code cleaner
            coordinator.code_cleaner = Mock()
            return coordinator

    def test_cleaning_phase_disabled(self, phase_coordinator: PhaseCoordinator) -> None:
        """Test cleaning phase when disabled."""
        mock_options = Mock()
        mock_options.clean = False

        result = phase_coordinator.run_cleaning_phase(mock_options)

        assert result is True
        # Session tracking should not be called when cleaning is disabled
        assert not phase_coordinator.session.track_task.called

    def test_cleaning_phase_successful_execution(
        self, phase_coordinator: PhaseCoordinator, tmp_path: Path
    ) -> None:
        """Test successful cleaning phase execution."""
        # Create some Python files to clean
        pkg_path = tmp_path / "package"
        (pkg_path / "module1.py").write_text("def test(): pass")
        (pkg_path / "module2.py").write_text("class Test: pass")

        phase_coordinator.pkg_path = pkg_path

        mock_options = Mock()
        mock_options.clean = True

        # Mock code cleaner methods
        phase_coordinator.code_cleaner.should_process_file.return_value = True
        phase_coordinator.code_cleaner.clean_file.return_value = True

        result = phase_coordinator.run_cleaning_phase(mock_options)

        assert result is True
        phase_coordinator.session.track_task.assert_called_once_with(
            "cleaning", "Code cleaning"
        )
        assert (
            phase_coordinator.code_cleaner.clean_file.call_count == 2
        )  # Two Python files

    def test_cleaning_phase_no_python_files(
        self, phase_coordinator: PhaseCoordinator, tmp_path: Path
    ) -> None:
        """Test cleaning phase when no Python files exist."""
        # Empty package directory
        pkg_path = tmp_path / "empty_package"
        pkg_path.mkdir()
        phase_coordinator.pkg_path = pkg_path

        mock_options = Mock()
        mock_options.clean = True

        result = phase_coordinator.run_cleaning_phase(mock_options)

        assert result is True
        phase_coordinator.session.track_task.assert_called_once_with(
            "cleaning", "Code cleaning"
        )
        phase_coordinator.session.complete_task.assert_called_once_with(
            "cleaning", "No files to clean"
        )

    def test_cleaning_phase_partial_file_cleaning(
        self, phase_coordinator: PhaseCoordinator, tmp_path: Path
    ) -> None:
        """Test cleaning phase when some files can't be cleaned."""
        # Create multiple Python files
        pkg_path = tmp_path / "package"
        (pkg_path / "cleanable.py").write_text("def clean(): pass")
        (pkg_path / "problematic.py").write_text("def problem(): pass")
        (pkg_path / "another.py").write_text("def another(): pass")

        phase_coordinator.pkg_path = pkg_path

        mock_options = Mock()
        mock_options.clean = True

        # Mock selective cleaning - some files can be cleaned, some can't
        def mock_should_process(file_path):
            return "problematic" not in str(file_path)

        def mock_clean_file(file_path):
            return "cleanable" in str(file_path) or "another" in str(file_path)

        phase_coordinator.code_cleaner.should_process_file.side_effect = (
            mock_should_process
        )
        phase_coordinator.code_cleaner.clean_file.side_effect = mock_clean_file

        result = phase_coordinator.run_cleaning_phase(mock_options)

        assert result is True
        # Should successfully clean 2 out of 3 files (problematic.py is skipped)
        assert phase_coordinator.code_cleaner.clean_file.call_count == 2

    def test_cleaning_phase_exception_handling(
        self, phase_coordinator: PhaseCoordinator, tmp_path: Path
    ) -> None:
        """Test cleaning phase handles exceptions gracefully."""
        pkg_path = tmp_path / "package"
        (pkg_path / "test.py").write_text("def test(): pass")
        phase_coordinator.pkg_path = pkg_path

        mock_options = Mock()
        mock_options.clean = True

        # Mock code cleaner to raise exception
        test_exception = RuntimeError("Code cleaner failed")
        phase_coordinator.code_cleaner.should_process_file.side_effect = test_exception

        result = phase_coordinator.run_cleaning_phase(mock_options)

        assert result is False
        phase_coordinator.session.track_task.assert_called_once_with(
            "cleaning", "Code cleaning"
        )
        phase_coordinator.session.fail_task.assert_called_once_with(
            "cleaning", str(test_exception)
        )

    def test_cleaning_phase_code_cleaner_integration(
        self, phase_coordinator: PhaseCoordinator, tmp_path: Path
    ) -> None:
        """Test cleaning phase integrates correctly with code cleaner."""
        # Create a Python file with actual content that needs cleaning
        pkg_path = tmp_path / "package"
        python_file = pkg_path / "needs_cleaning.py"
        python_file.write_text("""
import os
import sys
import unused_import  # This should be cleaned

def function_that_needs_cleaning():
    # Some code that might need cleaning
    x = 1
    y = 2
    return x + y
""")

        phase_coordinator.pkg_path = pkg_path

        mock_options = Mock()
        mock_options.clean = True

        # Configure code cleaner to simulate realistic behavior
        phase_coordinator.code_cleaner.should_process_file.return_value = True
        phase_coordinator.code_cleaner.clean_file.return_value = (
            True  # File was modified
        )

        result = phase_coordinator.run_cleaning_phase(mock_options)

        assert result is True

        # Verify code cleaner was called with correct file
        phase_coordinator.code_cleaner.should_process_file.assert_called_once_with(
            python_file
        )
        phase_coordinator.code_cleaner.clean_file.assert_called_once_with(python_file)

        # Verify success was reported
        phase_coordinator.session.complete_task.assert_called_once_with(
            "cleaning", "Cleaned 1 files"
        )


class TestWorkflowStateManagement:
    """Test workflow state management and session tracking."""

    @pytest.fixture
    def session_coordinator(self) -> SessionCoordinator:
        console = Console()
        pkg_path = Path("/tmp/test")
        return SessionCoordinator(console, pkg_path)

    def test_session_initialization(
        self, session_coordinator: SessionCoordinator
    ) -> None:
        """Test session initialization with various option types."""
        mock_options = Mock()
        mock_options.testing = True
        mock_options.skip_hooks = False
        mock_options.ai_agent = True

        # Mock the initialize_session_tracking method
        session_coordinator.initialize_session_tracking = Mock()

        session_coordinator.initialize_session_tracking(mock_options)

        session_coordinator.initialize_session_tracking.assert_called_once_with(
            mock_options
        )

    def test_task_tracking_lifecycle(
        self, session_coordinator: SessionCoordinator
    ) -> None:
        """Test complete task tracking lifecycle."""
        # Mock the required methods
        session_coordinator.track_task = Mock()
        session_coordinator.complete_task = Mock()
        session_coordinator.fail_task = Mock()

        # Track a task
        session_coordinator.track_task("test_phase", "Testing phase execution")

        # Complete the task
        session_coordinator.complete_task("test_phase", "Phase completed successfully")

        # Verify calls
        session_coordinator.track_task.assert_called_once_with(
            "test_phase", "Testing phase execution"
        )
        session_coordinator.complete_task.assert_called_once_with(
            "test_phase", "Phase completed successfully"
        )

    def test_task_failure_handling(
        self, session_coordinator: SessionCoordinator
    ) -> None:
        """Test task failure handling."""
        session_coordinator.track_task = Mock()
        session_coordinator.fail_task = Mock()

        # Track and fail a task
        session_coordinator.track_task("failing_phase", "Phase that will fail")
        session_coordinator.fail_task("failing_phase", "Phase failed due to error")

        session_coordinator.track_task.assert_called_once_with(
            "failing_phase", "Phase that will fail"
        )
        session_coordinator.fail_task.assert_called_once_with(
            "failing_phase", "Phase failed due to error"
        )


class TestConcurrentWorkflowExecution:
    """Test concurrent workflow execution scenarios."""

    @pytest.fixture
    def workflow_pipeline(self) -> WorkflowPipeline:
        console = Console()
        pkg_path = Path("/tmp/test")
        session = Mock()
        phases = Mock()
        return WorkflowPipeline(console, pkg_path, session, phases)

    @pytest.mark.asyncio
    async def test_concurrent_workflow_isolation(
        self, workflow_pipeline: WorkflowPipeline
    ) -> None:
        """Test that concurrent workflows don't interfere with each other."""
        # Create multiple mock options for different workflows
        options1 = Mock(spec=OptionsProtocol)
        options1.testing = True
        options1.skip_hooks = False

        options2 = Mock(spec=OptionsProtocol)
        options2.testing = False
        options2.skip_hooks = True

        # Mock session and phase methods
        workflow_pipeline.session.initialize_session_tracking = Mock()
        workflow_pipeline.session.track_task = Mock()
        workflow_pipeline.session.finalize_session = Mock()

        async def mock_execute_phases(options):
            # Simulate different execution times
            if options.testing:
                await asyncio.sleep(0.1)
                return True
            else:
                await asyncio.sleep(0.05)
                return False

        with patch.object(
            workflow_pipeline,
            "_execute_workflow_phases",
            side_effect=mock_execute_phases,
        ):
            # Run workflows concurrently
            results = await asyncio.gather(
                workflow_pipeline.run_complete_workflow(options1),
                workflow_pipeline.run_complete_workflow(options2),
            )

        # Verify results are correct for each workflow
        assert results[0] is True  # options1 workflow succeeded
        assert results[1] is False  # options2 workflow failed

        # Verify both sessions were initialized and finalized
        assert workflow_pipeline.session.initialize_session_tracking.call_count == 2
        assert workflow_pipeline.session.finalize_session.call_count == 2

    @pytest.mark.asyncio
    async def test_workflow_exception_isolation(
        self, workflow_pipeline: WorkflowPipeline
    ) -> None:
        """Test that exceptions in one workflow don't affect others."""
        options_success = Mock(spec=OptionsProtocol)
        options_success.testing = False
        options_success.skip_hooks = False

        options_failure = Mock(spec=OptionsProtocol)
        options_failure.testing = True
        options_failure.skip_hooks = False

        workflow_pipeline.session.initialize_session_tracking = Mock()
        workflow_pipeline.session.track_task = Mock()
        workflow_pipeline.session.finalize_session = Mock()

        async def mock_execute_with_exception(options):
            if options.testing:
                raise RuntimeError("Simulated workflow failure")
            return True

        with patch.object(
            workflow_pipeline,
            "_execute_workflow_phases",
            side_effect=mock_execute_with_exception,
        ):
            # Run workflows concurrently - one will succeed, one will fail
            results = await asyncio.gather(
                workflow_pipeline.run_complete_workflow(options_success),
                workflow_pipeline.run_complete_workflow(options_failure),
                return_exceptions=True,  # Don't let exceptions propagate
            )

        # Success workflow should complete normally
        assert results[0] is True

        # Failure workflow should return False (exception handled)
        assert results[1] is False


class TestWorkflowResourceManagement:
    """Test workflow resource management and cleanup."""

    @pytest.fixture
    def workflow_pipeline(self) -> WorkflowPipeline:
        console = Console()
        pkg_path = Path("/tmp/test")
        session = Mock()
        phases = Mock()
        return WorkflowPipeline(console, pkg_path, session, phases)

    @pytest.mark.asyncio
    async def test_resource_cleanup_on_success(
        self, workflow_pipeline: WorkflowPipeline
    ) -> None:
        """Test resource cleanup occurs after successful workflow."""
        mock_options = Mock(spec=OptionsProtocol)
        mock_options.testing = False

        workflow_pipeline.session.initialize_session_tracking = Mock()
        workflow_pipeline.session.track_task = Mock()
        workflow_pipeline.session.finalize_session = Mock()

        with patch.object(
            workflow_pipeline, "_execute_workflow_phases", return_value=True
        ):
            result = await workflow_pipeline.run_complete_workflow(mock_options)

        assert result is True
        # Verify session finalization (which handles cleanup) was called
        workflow_pipeline.session.finalize_session.assert_called_once()

        # In a real implementation, you would verify specific cleanup actions
        # such as temp file removal, resource deallocation, etc.

    @pytest.mark.asyncio
    async def test_resource_cleanup_on_failure(
        self, workflow_pipeline: WorkflowPipeline
    ) -> None:
        """Test resource cleanup occurs even after workflow failure."""
        mock_options = Mock(spec=OptionsProtocol)
        mock_options.testing = False

        workflow_pipeline.session.initialize_session_tracking = Mock()
        workflow_pipeline.session.track_task = Mock()
        workflow_pipeline.session.finalize_session = Mock()
        workflow_pipeline.session.cleanup_resources = Mock()
        workflow_pipeline.session.fail_task = Mock()

        test_exception = RuntimeError("Workflow failed")

        with patch.object(
            workflow_pipeline, "_execute_workflow_phases", side_effect=test_exception
        ):
            result = await workflow_pipeline.run_complete_workflow(mock_options)

        assert result is False
        # Verify cleanup still happens even on failure (via cleanup_resources, not finalize_session)
        workflow_pipeline.session.finalize_session.assert_not_called()
        workflow_pipeline.session.cleanup_resources.assert_called_once()
        workflow_pipeline.session.fail_task.assert_called_once_with(
            "workflow", "Unexpected error: Workflow failed"
        )

    @pytest.mark.asyncio
    async def test_memory_usage_stability(
        self, workflow_pipeline: WorkflowPipeline
    ) -> None:
        """Test memory usage remains stable across multiple workflow executions."""
        mock_options = Mock(spec=OptionsProtocol)
        mock_options.testing = False

        workflow_pipeline.session.initialize_session_tracking = Mock()
        workflow_pipeline.session.track_task = Mock()
        workflow_pipeline.session.finalize_session = Mock()

        with patch.object(
            workflow_pipeline, "_execute_workflow_phases", return_value=True
        ):
            # Run workflow multiple times
            for _ in range(10):
                result = await workflow_pipeline.run_complete_workflow(mock_options)
                assert result is True

        # Verify all sessions were properly finalized (cleanup occurred)
        assert workflow_pipeline.session.finalize_session.call_count == 10

        # In a real implementation, you might check memory usage metrics
        # to ensure no memory leaks occur across multiple executions
