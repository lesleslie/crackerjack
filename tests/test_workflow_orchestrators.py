import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from crackerjack.core.async_workflow_orchestrator import AsyncWorkflowOrchestrator
from crackerjack.core.workflow_orchestrator import (
    WorkflowOrchestrator,
    WorkflowPipeline,
)
from crackerjack.errors import CrackerjackError, ErrorCode
from crackerjack.models.config import WorkflowOptions


class TestWorkflowOrchestrator:
    @pytest.fixture
    def mock_console(self):
        from rich.console import Console

        return Console()

    @pytest.fixture
    def mock_pkg_path(self, tmp_path):
        return tmp_path

    @pytest.fixture
    def workflow_orchestrator(self, mock_console, mock_pkg_path):
        with patch("crackerjack.core.container.create_container"):
            return WorkflowOrchestrator(console=mock_console, pkg_path=mock_pkg_path)

    def test_init(self, workflow_orchestrator, mock_console, mock_pkg_path) -> None:
        assert workflow_orchestrator.console == mock_console
        assert workflow_orchestrator.pkg_path == mock_pkg_path
        assert workflow_orchestrator.container is not None

    def test_execute_with_options(self, workflow_orchestrator) -> None:
        options = WorkflowOptions()
        options.cleaning.clean = True
        options.testing.test = True

        with patch.object(workflow_orchestrator, "pipeline") as mock_pipeline:
            mock_pipeline.run_complete_workflow.return_value = True

            result = workflow_orchestrator.run_complete_workflow(options)

            assert result is True
            mock_pipeline.run_complete_workflow.assert_called_once_with(options)

    def test_execute_with_error_handling(self, workflow_orchestrator) -> None:
        options = WorkflowOptions()

        with patch.object(workflow_orchestrator, "pipeline") as mock_pipeline:
            mock_pipeline.run_complete_workflow.side_effect = CrackerjackError(
                "Test error", ErrorCode.UNKNOWN_ERROR
            )

            with pytest.raises(CrackerjackError):
                workflow_orchestrator.run_complete_workflow(options)

    def test_cleanup_on_completion(self, workflow_orchestrator) -> None:
        options = WorkflowOptions()

        with patch.object(workflow_orchestrator, "pipeline") as mock_pipeline:
            mock_pipeline.run_complete_workflow.return_value = True

            result = workflow_orchestrator.run_complete_workflow(options)

            assert result is True

    def test_get_container(self, workflow_orchestrator) -> None:
        container = workflow_orchestrator.container

        assert container is not None

    def test_workflow_execution_with_mocked_phases(self, workflow_orchestrator) -> None:
        options = WorkflowOptions()
        options.cleaning.clean = True
        options.testing.test = True
        options.git.commit = True

        with patch.object(workflow_orchestrator, "pipeline") as mock_pipeline:
            mock_pipeline.run_complete_workflow.return_value = True

            result = workflow_orchestrator.run_complete_workflow(options)

            assert result is True
            mock_pipeline.run_complete_workflow.assert_called_once_with(options)

    def test_workflow_with_complex_options(self, workflow_orchestrator) -> None:
        options = WorkflowOptions()
        options.cleaning.clean = True
        options.testing.test = True
        options.testing.benchmark = True
        options.publishing.publish = "patch"
        options.git.commit = True
        options.execution.verbose = True

        with patch.object(workflow_orchestrator, "pipeline") as mock_pipeline:
            mock_pipeline.run_complete_workflow.return_value = True

            result = workflow_orchestrator.run_complete_workflow(options)

            assert result is True

            call_args = mock_pipeline.run_complete_workflow.call_args[0][0]
            assert call_args.clean is True
            assert call_args.test is True
            assert call_args.benchmark is True
            assert call_args.publish == "patch"


class TestWorkflowPipeline:
    @pytest.fixture
    def mock_container(self):
        container = Mock()

        container.get_session_coordinator.return_value = Mock()
        container.get_phase_coordinator.return_value = Mock()
        container.get_hook_manager.return_value = Mock()
        container.get_test_manager.return_value = Mock()
        container.get_publish_manager.return_value = Mock()
        container.get_git_service.return_value = Mock()
        container.get_filesystem_service.return_value = Mock()

        return container

    @pytest.fixture
    def workflow_pipeline(self, mock_container):
        from pathlib import Path
        from unittest.mock import Mock

        from rich.console import Console

        console = Console()
        pkg_path = Path(" / test / project")
        session = Mock()
        phases = Mock()

        return WorkflowPipeline(
            console=console, pkg_path=pkg_path, session=session, phases=phases
        )

    def test_init(self, workflow_pipeline, mock_container) -> None:
        assert workflow_pipeline.console is not None
        assert workflow_pipeline.pkg_path is not None
        assert workflow_pipeline.session is not None
        assert workflow_pipeline.phases is not None

    def test_execute_full_workflow(self, workflow_pipeline, mock_container) -> None:
        options = WorkflowOptions()
        options.cleaning.clean = True
        options.testing.test = True
        options.git.commit = True

        workflow_pipeline.session.initialize_session_tracking = Mock()
        workflow_pipeline.session.track_task = Mock()
        workflow_pipeline.session.cleanup_resources = Mock()
        workflow_pipeline.session.finalize_session = Mock()

        workflow_pipeline.phases.run_configuration_phase = Mock()
        workflow_pipeline.phases.run_cleaning_phase = Mock(return_value=True)
        workflow_pipeline.phases.run_fast_hooks_only = Mock(return_value=True)
        workflow_pipeline.phases.run_testing_phase = Mock(return_value=True)
        workflow_pipeline.phases.run_comprehensive_hooks_only = Mock(return_value=True)
        workflow_pipeline.phases.run_publishing_phase = Mock(return_value=True)
        workflow_pipeline.phases.run_commit_phase = Mock(return_value=True)

        result = workflow_pipeline.run_complete_workflow(options)

        assert result is True
        workflow_pipeline.session.initialize_session_tracking.assert_called_once()
        workflow_pipeline.phases.run_configuration_phase.assert_called_once()
        workflow_pipeline.phases.run_cleaning_phase.assert_called_once()
        workflow_pipeline.phases.run_fast_hooks_only.assert_called_once()
        workflow_pipeline.phases.run_comprehensive_hooks_only.assert_called_once()
        workflow_pipeline.phases.run_testing_phase.assert_called_once()
        workflow_pipeline.phases.run_publishing_phase.assert_called_once()
        workflow_pipeline.phases.run_commit_phase.assert_called_once()

    def test_execute_partial_workflow(self, workflow_pipeline, mock_container) -> None:
        options = WorkflowOptions()
        options.cleaning.clean = False
        options.testing.test = True
        options.git.commit = False

        workflow_pipeline.session.initialize_session_tracking = Mock()
        workflow_pipeline.session.track_task = Mock()
        workflow_pipeline.session.cleanup_resources = Mock()
        workflow_pipeline.session.finalize_session = Mock()

        workflow_pipeline.phases.run_configuration_phase = Mock()
        workflow_pipeline.phases.run_cleaning_phase = Mock(return_value=True)
        workflow_pipeline.phases.run_fast_hooks_only = Mock(return_value=True)
        workflow_pipeline.phases.run_testing_phase = Mock(return_value=True)
        workflow_pipeline.phases.run_comprehensive_hooks_only = Mock(return_value=True)
        workflow_pipeline.phases.run_publishing_phase = Mock(return_value=True)
        workflow_pipeline.phases.run_commit_phase = Mock(return_value=True)

        result = workflow_pipeline.run_complete_workflow(options)

        assert result is True

        workflow_pipeline.phases.run_fast_hooks_only.assert_called_once()
        workflow_pipeline.phases.run_comprehensive_hooks_only.assert_called_once()
        workflow_pipeline.phases.run_testing_phase.assert_called_once()

    def test_execute_with_phase_failure(
        self, workflow_pipeline, mock_container
    ) -> None:
        options = WorkflowOptions()
        options.testing.test = True

        workflow_pipeline.session.initialize_session_tracking = Mock()
        workflow_pipeline.session.track_task = Mock()
        workflow_pipeline.session.cleanup_resources = Mock()
        workflow_pipeline.session.finalize_session = Mock()

        workflow_pipeline.phases.run_configuration_phase = Mock()
        workflow_pipeline.phases.run_cleaning_phase = Mock(return_value=False)

        result = workflow_pipeline.run_complete_workflow(options)
        assert result is False

    def test_cleanup_called_on_success(self, workflow_pipeline, mock_container) -> None:
        options = WorkflowOptions()
        options.cleaning.clean = True

        workflow_pipeline.session.initialize_session_tracking = Mock()
        workflow_pipeline.session.track_task = Mock()
        workflow_pipeline.session.cleanup_resources = Mock()
        workflow_pipeline.session.finalize_session = Mock()

        workflow_pipeline.phases.run_configuration_phase = Mock()
        workflow_pipeline.phases.run_cleaning_phase = Mock(return_value=True)
        workflow_pipeline.phases.run_fast_hooks_only = Mock(return_value=True)
        workflow_pipeline.phases.run_testing_phase = Mock(return_value=True)
        workflow_pipeline.phases.run_comprehensive_hooks_only = Mock(return_value=True)
        workflow_pipeline.phases.run_publishing_phase = Mock(return_value=True)
        workflow_pipeline.phases.run_commit_phase = Mock(return_value=True)

        workflow_pipeline.run_complete_workflow(options)

        workflow_pipeline.session.cleanup_resources.assert_called_once()

    def test_cleanup_called_on_failure(self, workflow_pipeline, mock_container) -> None:
        options = WorkflowOptions()
        options.testing.test = True

        workflow_pipeline.session.initialize_session_tracking = Mock()
        workflow_pipeline.session.track_task = Mock()
        workflow_pipeline.session.cleanup_resources = Mock()
        workflow_pipeline.session.finalize_session = Mock()

        workflow_pipeline.phases.run_configuration_phase = Mock()
        workflow_pipeline.phases.run_cleaning_phase = Mock(return_value=False)

        result = workflow_pipeline.run_complete_workflow(options)

        assert result is False
        workflow_pipeline.session.cleanup_resources.assert_called_once()

    def test_workflow_pipeline_state_management(
        self, workflow_pipeline, mock_container
    ) -> None:
        options = WorkflowOptions()
        options.testing.test = True
        options.execution.verbose = True

        workflow_pipeline.session.initialize_session_tracking = Mock()
        workflow_pipeline.session.track_task = Mock()
        workflow_pipeline.session.cleanup_resources = Mock()
        workflow_pipeline.session.finalize_session = Mock()

        workflow_pipeline.phases.run_configuration_phase = Mock()
        workflow_pipeline.phases.run_cleaning_phase = Mock(return_value=True)
        workflow_pipeline.phases.run_fast_hooks_only = Mock(return_value=True)
        workflow_pipeline.phases.run_testing_phase = Mock(return_value=True)
        workflow_pipeline.phases.run_comprehensive_hooks_only = Mock(return_value=True)
        workflow_pipeline.phases.run_publishing_phase = Mock(return_value=True)
        workflow_pipeline.phases.run_commit_phase = Mock(return_value=True)

        result = workflow_pipeline.run_complete_workflow(options)

        assert result is True
        workflow_pipeline.session.initialize_session_tracking.assert_called_once()


class TestAsyncWorkflowOrchestrator:
    @pytest.fixture
    def mock_console(self):
        from rich.console import Console

        return Console()

    @pytest.fixture
    def mock_pkg_path(self):
        return Path(" / test / async_project")

    @pytest.fixture
    def async_orchestrator(self, mock_console, mock_pkg_path):
        with patch("crackerjack.core.container.create_container"):
            return AsyncWorkflowOrchestrator(
                console=mock_console, pkg_path=mock_pkg_path
            )

    def test_init(self, async_orchestrator, mock_console, mock_pkg_path) -> None:
        assert async_orchestrator.console == mock_console
        assert async_orchestrator.pkg_path == mock_pkg_path
        assert async_orchestrator.container is not None

    @pytest.mark.asyncio
    async def test_execute_async(self, async_orchestrator) -> None:
        options = WorkflowOptions()
        options.testing.test = True

        with patch.object(async_orchestrator, "container") as mock_container:
            mock_pipeline = AsyncMock()
            mock_container.get_async_workflow_pipeline.return_value = mock_pipeline
            mock_pipeline.execute_async.return_value = True

            result = await async_orchestrator.execute_async(options)

            assert result is True
            mock_container.get_async_workflow_pipeline.assert_called_once()
            mock_pipeline.execute_async.assert_called_once_with(options)

    @pytest.mark.asyncio
    async def test_execute_async_with_error(self, async_orchestrator) -> None:
        options = WorkflowOptions()

        with patch.object(async_orchestrator, "container") as mock_container:
            mock_pipeline = AsyncMock()
            mock_container.get_async_workflow_pipeline.return_value = mock_pipeline
            mock_pipeline.execute_async.side_effect = CrackerjackError(
                "Async error", ErrorCode.UNKNOWN_ERROR
            )

            with pytest.raises(CrackerjackError):
                await async_orchestrator.execute_async(options)

    @pytest.mark.asyncio
    async def test_concurrent_phase_execution(self, async_orchestrator) -> None:
        options = WorkflowOptions()
        options.cleaning.clean = True
        options.testing.test = True

        with patch.object(async_orchestrator, "container") as mock_container:
            mock_pipeline = AsyncMock()
            mock_container.get_async_workflow_pipeline.return_value = mock_pipeline

            async def mock_execute(opts) -> bool:
                await asyncio.sleep(0.1)
                return True

            mock_pipeline.execute_async.side_effect = mock_execute

            result = await async_orchestrator.execute_async(options)

            assert result is True

    @pytest.mark.asyncio
    async def test_async_cleanup_on_completion(self, async_orchestrator) -> None:
        options = WorkflowOptions()

        with patch.object(async_orchestrator, "container") as mock_container:
            mock_pipeline = AsyncMock()
            mock_container.get_async_workflow_pipeline.return_value = mock_pipeline
            mock_pipeline.execute_async.return_value = True
            mock_pipeline.cleanup_async = AsyncMock()

            result = await async_orchestrator.execute_async(options)

            assert result is True
            mock_pipeline.cleanup_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_async_workflow_with_progress_tracking(
        self, async_orchestrator
    ) -> None:
        options = WorkflowOptions()
        options.testing.test = True
        options.execution.verbose = True

        with patch.object(async_orchestrator, "container") as mock_container:
            mock_pipeline = AsyncMock()
            mock_progress_tracker = Mock()

            mock_container.get_async_workflow_pipeline.return_value = mock_pipeline
            mock_container.get_progress_tracker.return_value = mock_progress_tracker

            async def mock_execute_with_progress(opts) -> bool:
                mock_progress_tracker.update_progress("hooks", 25)
                await asyncio.sleep(0.05)
                mock_progress_tracker.update_progress("hooks", 50)
                await asyncio.sleep(0.05)
                mock_progress_tracker.update_progress("hooks", 100)
                return True

            mock_pipeline.execute_async.side_effect = mock_execute_with_progress

            result = await async_orchestrator.execute_async(options)

            assert result is True

            assert mock_progress_tracker.update_progress.call_count >= 3


class TestWorkflowOrchestrationIntegration:
    def test_sync_async_orchestrator_compatibility(self) -> None:
        mock_console = Console()
        pkg_path = Path(" / test / integration")

        sync_orchestrator = WorkflowOrchestrator(
            console=mock_console, pkg_path=pkg_path
        )
        async_orchestrator = AsyncWorkflowOrchestrator(
            console=mock_console, pkg_path=pkg_path
        )

        assert hasattr(sync_orchestrator, "execute")
        assert hasattr(async_orchestrator, "execute_async")
        assert sync_orchestrator.console == async_orchestrator.console
        assert sync_orchestrator.pkg_path == async_orchestrator.pkg_path

    def test_orchestrator_container_integration(self) -> None:
        mock_console = Console()
        pkg_path = Path(" / test / container")

        orchestrator = WorkflowOrchestrator(console=mock_console, pkg_path=pkg_path)
        container = orchestrator.get_container()

        assert container is not None
        assert hasattr(container, "get_workflow_pipeline")
        assert hasattr(container, "get_session_coordinator")
        assert hasattr(container, "get_phase_coordinator")

    def test_workflow_pipeline_dependency_injection(self) -> None:
        from rich.console import Console

        console = Console()
        pkg_path = Path(" / test / dependency_injection")
        session = Mock()
        phases = Mock()

        pipeline = WorkflowPipeline(
            console=console, pkg_path=pkg_path, session=session, phases=phases
        )

        assert pipeline.console == console
        assert pipeline.pkg_path == pkg_path
        assert pipeline.session == session
        assert pipeline.phases == phases

    def test_error_propagation_through_orchestration_layers(self) -> None:
        mock_console = Console()
        pkg_path = Path(" / test / error_propagation")

        orchestrator = WorkflowOrchestrator(console=mock_console, pkg_path=pkg_path)

        with patch.object(orchestrator, "container") as mock_container:
            mock_pipeline = Mock()
            mock_container.get_workflow_pipeline.return_value = mock_pipeline

            test_error = CrackerjackError("Pipeline error", ErrorCode.EXECUTION_ERROR)
            mock_pipeline.execute.side_effect = test_error

            with pytest.raises(CrackerjackError) as exc_info:
                orchestrator.execute(WorkflowOptions())

            assert exc_info.value == test_error

    def test_workflow_options_propagation(self) -> None:
        mock_console = Console()
        pkg_path = Path(" / test / options")

        orchestrator = WorkflowOrchestrator(console=mock_console, pkg_path=pkg_path)

        options = WorkflowOptions()
        options.cleaning.clean = True
        options.testing.test = True
        options.testing.benchmark = True
        options.publishing.publish = "minor"
        options.git.commit = True
        options.execution.verbose = True

        with patch.object(orchestrator, "container") as mock_container:
            mock_pipeline = Mock()
            mock_container.get_workflow_pipeline.return_value = mock_pipeline
            mock_pipeline.execute.return_value = True

            orchestrator.execute(options)

            mock_pipeline.execute.assert_called_once()
            passed_options = mock_pipeline.execute.call_args[0][0]

            assert passed_options.clean is True
            assert passed_options.test is True
            assert passed_options.benchmark is True
            assert passed_options.publish == "minor"
            assert passed_options.commit is True
            assert passed_options.verbose is True

    @pytest.mark.asyncio
    async def test_async_workflow_performance_characteristics(self) -> None:
        mock_console = Console()
        pkg_path = Path(" / test / performance")

        async_orchestrator = AsyncWorkflowOrchestrator(
            console=mock_console, pkg_path=pkg_path
        )

        with patch.object(async_orchestrator, "container") as mock_container:
            mock_pipeline = AsyncMock()
            mock_container.get_async_workflow_pipeline.return_value = mock_pipeline

            async def mock_execute(options) -> bool:
                await asyncio.sleep(0.1)
                return True

            mock_pipeline.execute_async.side_effect = mock_execute

            import time

            start_time = time.time()

            result = await async_orchestrator.execute_async(WorkflowOptions())

            end_time = time.time()
            execution_time = end_time - start_time

            assert result is True

            assert execution_time < 1.0
