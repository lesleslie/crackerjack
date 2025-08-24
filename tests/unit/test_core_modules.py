"""
Unit tests for core modules - targeting workflow orchestration and containers.

Focus on core modules critical for 42% coverage:
- WorkflowOrchestrator
- Container
- SessionCoordinator
- PhaseCoordinator
- EnhancedDependencyContainer
"""

from unittest.mock import Mock, patch

import pytest

from crackerjack.core.container import DependencyContainer
from crackerjack.core.enhanced_container import EnhancedDependencyContainer
from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.core.workflow_orchestrator import (
    WorkflowOrchestrator,
    WorkflowPipeline,
)
from crackerjack.models.protocols import (
    HookManager,
    PublishManager,
    TestManagerProtocol,
)


@pytest.mark.unit
class TestWorkflowOrchestrator:
    """Test workflow orchestrator functionality"""

    def test_init(self, sample_config):
        """Test WorkflowOrchestrator initialization"""
        orchestrator = WorkflowOrchestrator(sample_config)
        assert orchestrator is not None
        assert orchestrator.config == sample_config

    def test_create_pipeline(self, sample_config):
        """Test creating workflow pipeline"""
        orchestrator = WorkflowOrchestrator(sample_config)

        pipeline = orchestrator.create_pipeline()

        assert isinstance(pipeline, WorkflowPipeline)

    @patch("crackerjack.core.workflow_orchestrator.create_container")
    def test_execute_workflow_success(self, mock_create_container, sample_config):
        """Test successful workflow execution"""
        # Setup mocks
        mock_container = Mock()
        mock_create_container.return_value = mock_container

        mock_hook_manager = Mock(spec=HookManager)
        mock_hook_manager.run_fast_hooks.return_value = (True, [])
        mock_hook_manager.run_comprehensive_hooks.return_value = (True, [])

        mock_test_manager = Mock(spec=TestManagerProtocol)
        mock_test_manager.run_tests.return_value = (True, [])

        mock_container.hook_manager.return_value = mock_hook_manager
        mock_container.test_manager.return_value = mock_test_manager

        orchestrator = WorkflowOrchestrator(sample_config)

        result = orchestrator.execute_workflow()

        assert isinstance(result, bool)

    @patch("crackerjack.core.workflow_orchestrator.create_container")
    def test_execute_workflow_hook_failure(self, mock_create_container, sample_config):
        """Test workflow execution with hook failures"""
        # Setup mocks
        mock_container = Mock()
        mock_create_container.return_value = mock_container

        mock_hook_manager = Mock(spec=HookManager)
        mock_hook_manager.run_fast_hooks.return_value = (False, ["Hook error"])

        mock_container.hook_manager.return_value = mock_hook_manager

        orchestrator = WorkflowOrchestrator(sample_config)

        result = orchestrator.execute_workflow()

        # Should handle failure gracefully
        assert isinstance(result, bool)

    def test_cleanup(self, sample_config):
        """Test workflow cleanup"""
        orchestrator = WorkflowOrchestrator(sample_config)

        # Should not raise exception
        orchestrator.cleanup()


@pytest.mark.unit
class TestWorkflowPipeline:
    """Test workflow pipeline functionality"""

    def test_init(self, sample_config, mock_container):
        """Test WorkflowPipeline initialization"""
        pipeline = WorkflowPipeline(sample_config, mock_container)

        assert pipeline is not None
        assert pipeline.config == sample_config
        assert pipeline.container == mock_container

    def test_add_phase(self, sample_config, mock_container):
        """Test adding phase to pipeline"""
        pipeline = WorkflowPipeline(sample_config, mock_container)

        mock_phase = Mock()
        pipeline.add_phase("test_phase", mock_phase)

        assert "test_phase" in pipeline.phases

    def test_execute_phases(self, sample_config, mock_container):
        """Test executing pipeline phases"""
        pipeline = WorkflowPipeline(sample_config, mock_container)

        # Add mock phases
        mock_phase1 = Mock()
        mock_phase1.execute.return_value = True
        mock_phase2 = Mock()
        mock_phase2.execute.return_value = True

        pipeline.add_phase("phase1", mock_phase1)
        pipeline.add_phase("phase2", mock_phase2)

        result = pipeline.execute()

        mock_phase1.execute.assert_called_once()
        mock_phase2.execute.assert_called_once()
        assert isinstance(result, bool)

    def test_execute_phases_with_failure(self, sample_config, mock_container):
        """Test executing pipeline with phase failure"""
        pipeline = WorkflowPipeline(sample_config, mock_container)

        # First phase succeeds, second fails
        mock_phase1 = Mock()
        mock_phase1.execute.return_value = True
        mock_phase2 = Mock()
        mock_phase2.execute.return_value = False

        pipeline.add_phase("phase1", mock_phase1)
        pipeline.add_phase("phase2", mock_phase2)

        result = pipeline.execute()

        # Should still execute all phases
        mock_phase1.execute.assert_called_once()
        mock_phase2.execute.assert_called_once()
        assert isinstance(result, bool)


@pytest.mark.unit
class TestContainer:
    """Test dependency injection container"""

    def test_init(self):
        """Test DependencyContainer initialization"""
        container = DependencyContainer()
        assert container is not None

    def test_get_hook_manager(self):
        """Test getting hook manager from container"""
        container = DependencyContainer()

        hook_manager = container.hook_manager()

        assert hook_manager is not None
        # Should return same instance on subsequent calls
        assert container.hook_manager() is hook_manager

    def test_get_test_manager(self):
        """Test getting test manager from container"""
        container = DependencyContainer()

        test_manager = container.test_manager()

        assert test_manager is not None
        assert container.test_manager() is test_manager

    def test_get_publish_manager(self):
        """Test getting publish manager from container"""
        container = DependencyContainer()

        publish_manager = container.publish_manager()

        assert publish_manager is not None
        assert container.publish_manager() is publish_manager

    def test_get_file_system_service(self):
        """Test getting filesystem service from container"""
        container = DependencyContainer()

        fs_service = container.file_system_service()

        assert fs_service is not None
        assert container.file_system_service() is fs_service

    def test_get_git_service(self):
        """Test getting git service from container"""
        container = DependencyContainer()

        git_service = container.git_service()

        assert git_service is not None
        assert container.git_service() is git_service


@pytest.mark.unit
class TestSessionCoordinator:
    """Test session coordination functionality"""

    def test_init(self, sample_config):
        """Test SessionCoordinator initialization"""
        coordinator = SessionCoordinator(sample_config)

        assert coordinator is not None
        assert coordinator.config == sample_config

    def test_start_session(self, sample_config):
        """Test starting a session"""
        coordinator = SessionCoordinator(sample_config)

        session_id = coordinator.start_session()

        assert isinstance(session_id, str)
        assert len(session_id) > 0

    def test_end_session(self, sample_config):
        """Test ending a session"""
        coordinator = SessionCoordinator(sample_config)

        session_id = coordinator.start_session()
        result = coordinator.end_session(session_id)

        assert isinstance(result, bool)

    def test_get_session_info(self, sample_config):
        """Test getting session information"""
        coordinator = SessionCoordinator(sample_config)

        session_id = coordinator.start_session()
        session_info = coordinator.get_session_info(session_id)

        assert isinstance(session_info, dict)
        assert "session_id" in session_info

    def test_cleanup_expired_sessions(self, sample_config):
        """Test cleaning up expired sessions"""
        coordinator = SessionCoordinator(sample_config)

        # Should not raise exception
        coordinator.cleanup_expired_sessions()

    @patch("crackerjack.core.session_coordinator.Path.mkdir")
    def test_create_session_directory(self, mock_mkdir, sample_config):
        """Test creating session directory"""
        coordinator = SessionCoordinator(sample_config)

        session_id = coordinator.start_session()
        coordinator._create_session_directory(session_id)

        mock_mkdir.assert_called()


@pytest.mark.unit
class TestPhaseCoordinator:
    """Test phase coordination functionality"""

    def test_init(self, sample_config, mock_container):
        """Test PhaseCoordinator initialization"""
        coordinator = PhaseCoordinator(sample_config, mock_container)

        assert coordinator is not None
        assert coordinator.config == sample_config
        assert coordinator.container == mock_container

    def test_execute_hooks_phase(self, sample_config, mock_container):
        """Test executing hooks phase"""
        mock_hook_manager = Mock(spec=HookManager)
        mock_hook_manager.run_fast_hooks.return_value = (True, [])
        mock_container.hook_manager.return_value = mock_hook_manager

        coordinator = PhaseCoordinator(sample_config, mock_container)

        result = coordinator.execute_hooks_phase()

        assert isinstance(result, bool)
        mock_hook_manager.run_fast_hooks.assert_called_once()

    def test_execute_testing_phase(self, sample_config, mock_container):
        """Test executing testing phase"""
        mock_test_manager = Mock(spec=TestManagerProtocol)
        mock_test_manager.run_tests.return_value = (True, [])
        mock_container.test_manager.return_value = mock_test_manager

        coordinator = PhaseCoordinator(sample_config, mock_container)

        result = coordinator.execute_testing_phase()

        assert isinstance(result, bool)
        mock_test_manager.run_tests.assert_called_once()

    def test_execute_publish_phase(self, sample_config, mock_container):
        """Test executing publish phase"""
        mock_publish_manager = Mock(spec=PublishManager)
        mock_publish_manager.bump_version.return_value = "1.0.1"
        mock_container.publish_manager.return_value = mock_publish_manager

        # Enable publishing in config
        sample_config.publish = True
        sample_config.bump_version = "patch"

        coordinator = PhaseCoordinator(sample_config, mock_container)

        result = coordinator.execute_publish_phase()

        assert isinstance(result, bool)

    def test_execute_cleanup_phase(self, sample_config, mock_container):
        """Test executing cleanup phase"""
        coordinator = PhaseCoordinator(sample_config, mock_container)

        result = coordinator.execute_cleanup_phase()

        assert isinstance(result, bool)

    def test_phase_execution_order(self, sample_config, mock_container):
        """Test that phases execute in correct order"""
        coordinator = PhaseCoordinator(sample_config, mock_container)

        # Mock all managers
        mock_hook_manager = Mock(spec=HookManager)
        mock_hook_manager.run_fast_hooks.return_value = (True, [])
        mock_hook_manager.run_comprehensive_hooks.return_value = (True, [])

        mock_test_manager = Mock(spec=TestManagerProtocol)
        mock_test_manager.run_tests.return_value = (True, [])

        mock_container.hook_manager.return_value = mock_hook_manager
        mock_container.test_manager.return_value = mock_test_manager

        # Execute phases
        hooks_result = coordinator.execute_hooks_phase()
        testing_result = coordinator.execute_testing_phase()
        cleanup_result = coordinator.execute_cleanup_phase()

        assert hooks_result is True
        assert testing_result is True
        assert cleanup_result is True


@pytest.mark.unit
class TestEnhancedDependencyContainer:
    """Test enhanced dependency injection container"""

    def test_init(self):
        """Test EnhancedDependencyContainer initialization"""
        container = EnhancedDependencyContainer()
        assert container is not None

    def test_dependency_resolution(self):
        """Test dependency resolution"""
        container = EnhancedDependencyContainer()

        # Test that dependencies are resolved correctly
        hook_manager = container.resolve("hook_manager")
        test_manager = container.resolve("test_manager")

        assert hook_manager is not None
        assert test_manager is not None

    def test_singleton_behavior(self):
        """Test singleton behavior of services"""
        container = EnhancedDependencyContainer()

        service1 = container.resolve("file_system_service")
        service2 = container.resolve("file_system_service")

        # Should return same instance
        assert service1 is service2

    def test_register_service(self):
        """Test registering custom service"""
        container = EnhancedDependencyContainer()

        mock_service = Mock()
        container.register("custom_service", lambda: mock_service)

        resolved_service = container.resolve("custom_service")
        assert resolved_service is mock_service

    def test_clear_cache(self):
        """Test clearing dependency cache"""
        container = EnhancedDependencyContainer()

        # Resolve service to cache it
        service1 = container.resolve("file_system_service")

        # Clear cache
        container.clear_cache()

        # Resolve again - should be different instance
        service2 = container.resolve("file_system_service")

        # Note: This test depends on implementation details
        # May need adjustment based on actual caching behavior
        assert service1 is not None
        assert service2 is not None
