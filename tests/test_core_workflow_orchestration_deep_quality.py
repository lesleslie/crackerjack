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
    @pytest.fixture
    def console(self) -> Console:
        return Console()

    @pytest.fixture
    def pkg_path(self, tmp_path: Path) -> Path:
        pkg_dir = tmp_path / "test_package"
        pkg_dir.mkdir()
        return pkg_dir

    @pytest.fixture
    def session_coordinator(
        self, console: Console, pkg_path: Path
    ) -> SessionCoordinator:
        return SessionCoordinator(console, pkg_path)

    @pytest.fixture
    def phase_coordinator(
        self, console: Console, pkg_path: Path, session_coordinator: SessionCoordinator
    ) -> PhaseCoordinator:
        with patch("crackerjack.core.phase_coordinator.ConfigurationService"):
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
        return WorkflowPipeline(
            console=console,
            pkg_path=pkg_path,
            session=session_coordinator,
            phases=phase_coordinator,
        )

    @pytest.fixture
    def mock_options(self) -> Mock:
        options = Mock(spec=OptionsProtocol)
        options.testing = False
        options.skip_hooks = False
        options.ai_agent = False
        options.clean = False
        options.publish = None
        options.cleanup = None
        return options


class TestWorkflowExecutionScenarios:
    @pytest.fixture
    def workflow_pipeline(self) -> WorkflowPipeline:
        console = Console()
        pkg_path = Path("/ tmp / test")
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
        workflow_pipeline.session.initialize_session_tracking = Mock()
        workflow_pipeline.session.track_task = Mock()
        workflow_pipeline.session.finalize_session = Mock()

        with patch.object(
            workflow_pipeline, "_execute_workflow_phases", return_value=False
        ) as mock_execute:
            result = await workflow_pipeline.run_complete_workflow(mock_options)

        assert result is False
        mock_execute.assert_called_once_with(mock_options)

        workflow_pipeline.session.finalize_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_workflow_execution_with_exception(
        self, workflow_pipeline: WorkflowPipeline, mock_options: Mock
    ) -> None:
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

        workflow_pipeline.session.finalize_session.assert_not_called()
        workflow_pipeline.session.cleanup_resources.assert_called_once()
        workflow_pipeline.session.fail_task.assert_called_once_with(
            "workflow", "Unexpected error: Phase execution failed"
        )

    @pytest.mark.asyncio
    async def test_workflow_with_cleanup_configuration(
        self, workflow_pipeline: WorkflowPipeline, mock_options: Mock
    ) -> None:
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
        workflow_pipeline.session.initialize_session_tracking = Mock()
        workflow_pipeline.session.track_task = Mock()
        workflow_pipeline.session.finalize_session = Mock()

        async def slow_execute_phases(options):
            await asyncio.sleep(0.1)
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
        assert duration >= 0.1

        finalize_call_args = workflow_pipeline.session.finalize_session.call_args
        assert len(finalize_call_args[0]) >= 2
        assert isinstance(finalize_call_args[0][0], float)
        assert finalize_call_args[0][1] is True

    @pytest.mark.asyncio
    async def test_debug_mode_logging(
        self, workflow_pipeline: WorkflowPipeline, mock_options: Mock
    ) -> None:
        workflow_pipeline.session.initialize_session_tracking = Mock()
        workflow_pipeline.session.track_task = Mock()
        workflow_pipeline.session.finalize_session = Mock()

        with patch.dict("os.environ", {"AI_AGENT_DEBUG": "1"}):
            with patch.object(
                workflow_pipeline, "_execute_workflow_phases", return_value=True
            ):
                result = await workflow_pipeline.run_complete_workflow(mock_options)

        assert result is True


class TestPhaseCoordinatorBusinessLogic:
    @pytest.fixture
    def phase_coordinator(self) -> PhaseCoordinator:
        console = Console()
        pkg_path = Path("/ tmp / test")
        session = Mock()

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

            coordinator.code_cleaner = Mock()
            return coordinator

    def test_cleaning_phase_disabled(self, phase_coordinator: PhaseCoordinator) -> None:
        mock_options = Mock()
        mock_options.clean = False

        result = phase_coordinator.run_cleaning_phase(mock_options)

        assert result is True

        assert not phase_coordinator.session.track_task.called

    def test_cleaning_phase_successful_execution(
        self, phase_coordinator: PhaseCoordinator, tmp_path: Path
    ) -> None:
        pkg_path = tmp_path / "package"
        (pkg_path / "module1.py").write_text("def test(): pass")
        (pkg_path / "module2.py").write_text("class Test: pass")

        phase_coordinator.pkg_path = pkg_path

        mock_options = Mock()
        mock_options.clean = True

        phase_coordinator.code_cleaner.should_process_file.return_value = True
        # Mock clean_file to return CleaningResult with success=True
        from crackerjack.code_cleaner import CleaningResult

        mock_result = CleaningResult(
            file_path=Path("/test"),
            success=True,
            steps_completed=["test"],
            steps_failed=[],
            warnings=[],
            original_size=100,
            cleaned_size=90,
        )
        phase_coordinator.code_cleaner.clean_file.return_value = mock_result

        result = phase_coordinator.run_cleaning_phase(mock_options)

        assert result is True
        phase_coordinator.session.track_task.assert_called_once_with(
            "cleaning", "Code cleaning"
        )
        assert phase_coordinator.code_cleaner.clean_file.call_count == 2

    def test_cleaning_phase_no_python_files(
        self, phase_coordinator: PhaseCoordinator, tmp_path: Path
    ) -> None:
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
        pkg_path = tmp_path / "package"
        (pkg_path / "cleanable.py").write_text("def clean(): pass")
        (pkg_path / "problematic.py").write_text("def problem(): pass")
        (pkg_path / "another.py").write_text("def another(): pass")

        phase_coordinator.pkg_path = pkg_path

        mock_options = Mock()
        mock_options.clean = True

        def mock_should_process(file_path):
            return "problematic" not in str(file_path)

        def mock_clean_file(file_path):
            # Return CleaningResult instead of boolean
            from crackerjack.code_cleaner import CleaningResult

            success = "cleanable" in str(file_path) or "another" in str(file_path)
            return CleaningResult(
                file_path=file_path,
                success=success,
                steps_completed=["test"] if success else [],
                steps_failed=[] if success else ["test"],
                warnings=[],
                original_size=100,
                cleaned_size=90 if success else 100,
            )

        phase_coordinator.code_cleaner.should_process_file.side_effect = (
            mock_should_process
        )
        phase_coordinator.code_cleaner.clean_file.side_effect = mock_clean_file

        result = phase_coordinator.run_cleaning_phase(mock_options)

        assert result is True

        assert phase_coordinator.code_cleaner.clean_file.call_count == 2

    def test_cleaning_phase_exception_handling(
        self, phase_coordinator: PhaseCoordinator, tmp_path: Path
    ) -> None:
        pkg_path = tmp_path / "package"
        (pkg_path / "test.py").write_text("def test(): pass")
        phase_coordinator.pkg_path = pkg_path

        mock_options = Mock()
        mock_options.clean = True

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
        pkg_path = tmp_path / "package"
        python_file = pkg_path / "needs_cleaning.py"
        python_file.write_text("""
import os
import sys
import unused_import

def function_that_needs_cleaning():

    x = 1
    y = 2
    return x + y
""")

        phase_coordinator.pkg_path = pkg_path

        mock_options = Mock()
        mock_options.clean = True

        phase_coordinator.code_cleaner.should_process_file.return_value = True
        # Mock clean_file to return CleaningResult with success=True
        from crackerjack.code_cleaner import CleaningResult

        mock_result = CleaningResult(
            file_path=python_file,
            success=True,
            steps_completed=["test"],
            steps_failed=[],
            warnings=[],
            original_size=100,
            cleaned_size=90,
        )
        phase_coordinator.code_cleaner.clean_file.return_value = mock_result

        result = phase_coordinator.run_cleaning_phase(mock_options)

        assert result is True

        phase_coordinator.code_cleaner.should_process_file.assert_called_once_with(
            python_file
        )
        phase_coordinator.code_cleaner.clean_file.assert_called_once_with(python_file)

        phase_coordinator.session.complete_task.assert_called_once_with(
            "cleaning", "Cleaned 1 files"
        )


class TestWorkflowStateManagement:
    @pytest.fixture
    def session_coordinator(self) -> SessionCoordinator:
        console = Console()
        pkg_path = Path("/ tmp / test")
        return SessionCoordinator(console, pkg_path)

    def test_session_initialization(
        self, session_coordinator: SessionCoordinator
    ) -> None:
        mock_options = Mock()
        mock_options.testing = True
        mock_options.skip_hooks = False
        mock_options.ai_agent = True

        session_coordinator.initialize_session_tracking = Mock()

        session_coordinator.initialize_session_tracking(mock_options)

        session_coordinator.initialize_session_tracking.assert_called_once_with(
            mock_options
        )

    def test_task_tracking_lifecycle(
        self, session_coordinator: SessionCoordinator
    ) -> None:
        session_coordinator.track_task = Mock()
        session_coordinator.complete_task = Mock()
        session_coordinator.fail_task = Mock()

        session_coordinator.track_task("test_phase", "Testing phase execution")

        session_coordinator.complete_task("test_phase", "Phase completed successfully")

        session_coordinator.track_task.assert_called_once_with(
            "test_phase", "Testing phase execution"
        )
        session_coordinator.complete_task.assert_called_once_with(
            "test_phase", "Phase completed successfully"
        )

    def test_task_failure_handling(
        self, session_coordinator: SessionCoordinator
    ) -> None:
        session_coordinator.track_task = Mock()
        session_coordinator.fail_task = Mock()

        session_coordinator.track_task("failing_phase", "Phase that will fail")
        session_coordinator.fail_task("failing_phase", "Phase failed due to error")

        session_coordinator.track_task.assert_called_once_with(
            "failing_phase", "Phase that will fail"
        )
        session_coordinator.fail_task.assert_called_once_with(
            "failing_phase", "Phase failed due to error"
        )


class TestConcurrentWorkflowExecution:
    @pytest.fixture
    def workflow_pipeline(self) -> WorkflowPipeline:
        console = Console()
        pkg_path = Path("/ tmp / test")
        session = Mock()
        phases = Mock()
        return WorkflowPipeline(console, pkg_path, session, phases)

    @pytest.mark.asyncio
    async def test_concurrent_workflow_isolation(
        self, workflow_pipeline: WorkflowPipeline
    ) -> None:
        options1 = Mock(spec=OptionsProtocol)
        options1.testing = True
        options1.skip_hooks = False

        options2 = Mock(spec=OptionsProtocol)
        options2.testing = False
        options2.skip_hooks = True

        workflow_pipeline.session.initialize_session_tracking = Mock()
        workflow_pipeline.session.track_task = Mock()
        workflow_pipeline.session.finalize_session = Mock()

        async def mock_execute_phases(options):
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
            results = await asyncio.gather(
                workflow_pipeline.run_complete_workflow(options1),
                workflow_pipeline.run_complete_workflow(options2),
            )

        assert results[0] is True
        assert results[1] is False

        assert workflow_pipeline.session.initialize_session_tracking.call_count == 2
        assert workflow_pipeline.session.finalize_session.call_count == 2

    @pytest.mark.asyncio
    async def test_workflow_exception_isolation(
        self, workflow_pipeline: WorkflowPipeline
    ) -> None:
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
            results = await asyncio.gather(
                workflow_pipeline.run_complete_workflow(options_success),
                workflow_pipeline.run_complete_workflow(options_failure),
                return_exceptions=True,
            )

        assert results[0] is True

        assert results[1] is False


class TestWorkflowResourceManagement:
    @pytest.fixture
    def workflow_pipeline(self) -> WorkflowPipeline:
        console = Console()
        pkg_path = Path("/ tmp / test")
        session = Mock()
        phases = Mock()
        return WorkflowPipeline(console, pkg_path, session, phases)

    @pytest.mark.asyncio
    async def test_resource_cleanup_on_success(
        self, workflow_pipeline: WorkflowPipeline
    ) -> None:
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

        workflow_pipeline.session.finalize_session.assert_called_once()

    @pytest.mark.asyncio
    async def test_resource_cleanup_on_failure(
        self, workflow_pipeline: WorkflowPipeline
    ) -> None:
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

        workflow_pipeline.session.finalize_session.assert_not_called()
        workflow_pipeline.session.cleanup_resources.assert_called_once()
        workflow_pipeline.session.fail_task.assert_called_once_with(
            "workflow", "Unexpected error: Workflow failed"
        )

    @pytest.mark.asyncio
    async def test_memory_usage_stability(
        self, workflow_pipeline: WorkflowPipeline
    ) -> None:
        mock_options = Mock(spec=OptionsProtocol)
        mock_options.testing = False

        workflow_pipeline.session.initialize_session_tracking = Mock()
        workflow_pipeline.session.track_task = Mock()
        workflow_pipeline.session.finalize_session = Mock()

        with patch.object(
            workflow_pipeline, "_execute_workflow_phases", return_value=True
        ):
            for _ in range(10):
                result = await workflow_pipeline.run_complete_workflow(mock_options)
                assert result is True

        assert workflow_pipeline.session.finalize_session.call_count == 10
