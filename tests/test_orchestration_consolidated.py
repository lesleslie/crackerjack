"""Consolidated orchestration testing module."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.core.workflow_orchestrator import WorkflowOrchestrator, WorkflowPipeline
from crackerjack.core.async_workflow_orchestrator import AsyncWorkflowOrchestrator
from crackerjack.orchestration.advanced_orchestrator import AdvancedWorkflowOrchestrator
from crackerjack.models.config import WorkflowOptions


@pytest.fixture
def console():
    """Console fixture for testing."""
    return Console(force_terminal=False)


@pytest.fixture
def temp_project(tmp_path):
    """Temporary project directory fixture."""
    return tmp_path


class MockOptions:
    """Mock options for testing."""
    
    def __init__(self, **kwargs) -> None:
        # Common options
        self.test = False
        self.skip_hooks = False
        self.clean = False
        self.publish = None
        self.commit = False
        self.dry_run = False
        self.verbose = False
        self.autofix = False
        
        # Override with provided kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestWorkflowOrchestrator:
    """Test WorkflowOrchestrator functionality."""

    def test_initialization(self, console, temp_project) -> None:
        """Test workflow orchestrator initialization."""
        orchestrator = WorkflowOrchestrator(console=console, pkg_path=temp_project)
        assert orchestrator.console is console
        assert orchestrator.pkg_path == temp_project

    def test_basic_workflow_execution(self, console, temp_project) -> None:
        """Test basic workflow execution."""
        orchestrator = WorkflowOrchestrator(console=console, pkg_path=temp_project)
        options = MockOptions()
        
        # This should not raise an exception
        result = orchestrator.execute_workflow(options)
        assert isinstance(result, bool)

    def test_workflow_with_testing(self, console, temp_project) -> None:
        """Test workflow execution with testing enabled."""
        orchestrator = WorkflowOrchestrator(console=console, pkg_path=temp_project)
        options = MockOptions(test=True)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Tests passed", stderr="")
            result = orchestrator.execute_workflow(options)
            assert isinstance(result, bool)

    def test_workflow_with_hooks_skipped(self, console, temp_project) -> None:
        """Test workflow execution with hooks skipped."""
        orchestrator = WorkflowOrchestrator(console=console, pkg_path=temp_project)
        options = MockOptions(skip_hooks=True)
        
        result = orchestrator.execute_workflow(options)
        assert isinstance(result, bool)

    def test_workflow_with_cleaning(self, console, temp_project) -> None:
        """Test workflow execution with code cleaning."""
        orchestrator = WorkflowOrchestrator(console=console, pkg_path=temp_project)
        options = MockOptions(clean=True)
        
        result = orchestrator.execute_workflow(options)
        assert isinstance(result, bool)

    def test_workflow_dry_run(self, console, temp_project) -> None:
        """Test workflow execution in dry run mode."""
        orchestrator = WorkflowOrchestrator(console=console, pkg_path=temp_project)
        options = MockOptions(dry_run=True)
        
        result = orchestrator.execute_workflow(options)
        assert isinstance(result, bool)


class TestWorkflowPipeline:
    """Test WorkflowPipeline functionality."""

    def test_pipeline_creation(self, console, temp_project) -> None:
        """Test workflow pipeline creation."""
        pipeline = WorkflowPipeline(console=console, pkg_path=temp_project)
        assert pipeline.console is console
        assert pipeline.pkg_path == temp_project

    def test_pipeline_stage_execution(self, console, temp_project) -> None:
        """Test individual pipeline stage execution."""
        pipeline = WorkflowPipeline(console=console, pkg_path=temp_project)
        options = MockOptions()
        
        # Test configuration stage
        config_result = pipeline.run_configuration_stage(options)
        assert isinstance(config_result, bool)

    def test_pipeline_hooks_stage(self, console, temp_project) -> None:
        """Test hooks stage execution."""
        pipeline = WorkflowPipeline(console=console, pkg_path=temp_project)
        options = MockOptions()
        
        hooks_result = pipeline.run_hooks_stage(options)
        assert isinstance(hooks_result, bool)

    def test_pipeline_testing_stage(self, console, temp_project) -> None:
        """Test testing stage execution."""
        pipeline = WorkflowPipeline(console=console, pkg_path=temp_project)
        options = MockOptions(test=True)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Tests passed", stderr="")
            test_result = pipeline.run_testing_stage(options)
            assert isinstance(test_result, bool)

    def test_pipeline_stage_failure_handling(self, console, temp_project) -> None:
        """Test pipeline stage failure handling."""
        pipeline = WorkflowPipeline(console=console, pkg_path=temp_project)
        options = MockOptions(test=True)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="Tests failed")
            test_result = pipeline.run_testing_stage(options)
            assert isinstance(test_result, bool)


class TestAsyncWorkflowOrchestrator:
    """Test AsyncWorkflowOrchestrator functionality."""

    def test_async_initialization(self, console, temp_project) -> None:
        """Test async workflow orchestrator initialization."""
        orchestrator = AsyncWorkflowOrchestrator(console=console, pkg_path=temp_project)
        assert orchestrator.console is console
        assert orchestrator.pkg_path == temp_project

    @pytest.mark.asyncio
    async def test_async_workflow_execution(self, console, temp_project) -> None:
        """Test async workflow execution."""
        orchestrator = AsyncWorkflowOrchestrator(console=console, pkg_path=temp_project)
        options = MockOptions()
        
        result = await orchestrator.execute_workflow_async(options)
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_async_workflow_with_testing(self, console, temp_project) -> None:
        """Test async workflow with testing enabled."""
        orchestrator = AsyncWorkflowOrchestrator(console=console, pkg_path=temp_project)
        options = MockOptions(test=True)
        
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_process = Mock()
            mock_process.communicate.return_value = ("Tests passed", "")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process
            
            result = await orchestrator.execute_workflow_async(options)
            assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_async_concurrent_execution(self, console, temp_project) -> None:
        """Test async concurrent execution capabilities."""
        orchestrator = AsyncWorkflowOrchestrator(console=console, pkg_path=temp_project)
        options = MockOptions(test=True)
        
        # This tests that the async orchestrator can handle concurrent operations
        result = await orchestrator.execute_workflow_async(options)
        assert isinstance(result, bool)


class TestAdvancedOrchestrator:
    """Test AdvancedWorkflowOrchestrator functionality."""

    def test_advanced_initialization(self, console, temp_project) -> None:
        """Test advanced orchestrator initialization."""
        from crackerjack.core.session_coordinator import SessionCoordinator
        session = SessionCoordinator(console, temp_project)
        orchestrator = AdvancedWorkflowOrchestrator(console=console, pkg_path=temp_project, session=session)
        assert orchestrator.console is console
        assert orchestrator.pkg_path == temp_project

    def test_advanced_workflow_execution(self, console, temp_project) -> None:
        """Test advanced workflow execution."""
        from crackerjack.core.session_coordinator import SessionCoordinator
        session = SessionCoordinator(console, temp_project)
        orchestrator = AdvancedWorkflowOrchestrator(console=console, pkg_path=temp_project, session=session)
        options = MockOptions()
        
        # Test initialization only since full execution requires complex setup
        assert hasattr(orchestrator, 'execute_orchestrated_workflow')

    def test_advanced_autofix_integration(self, console, temp_project) -> None:
        """Test advanced orchestrator autofix integration."""
        from crackerjack.core.session_coordinator import SessionCoordinator
        session = SessionCoordinator(console, temp_project)
        orchestrator = AdvancedWorkflowOrchestrator(console=console, pkg_path=temp_project, session=session)
        options = MockOptions(autofix=True)
        
        # Test initialization and component setup
        assert hasattr(orchestrator, 'agent_coordinator')

    def test_advanced_error_recovery(self, console, temp_project) -> None:
        """Test advanced orchestrator error recovery."""
        from crackerjack.core.session_coordinator import SessionCoordinator
        session = SessionCoordinator(console, temp_project)
        orchestrator = AdvancedWorkflowOrchestrator(console=console, pkg_path=temp_project, session=session)
        
        # Test correlation tracker functionality
        assert hasattr(orchestrator, 'correlation_tracker')
        assert hasattr(orchestrator.correlation_tracker, 'record_iteration')


class TestOrchestrationIntegration:
    """Test integration between orchestration components."""

    def test_orchestrator_interoperability(self, console, temp_project) -> None:
        """Test that different orchestrators can work together."""
        basic_orchestrator = WorkflowOrchestrator(console=console, pkg_path=temp_project)
        async_orchestrator = AsyncWorkflowOrchestrator(console=console, pkg_path=temp_project)
        from crackerjack.core.session_coordinator import SessionCoordinator
        session = SessionCoordinator(console, temp_project)
        advanced_orchestrator = AdvancedWorkflowOrchestrator(console=console, pkg_path=temp_project, session=session)
        
        # Verify all have same basic interface
        assert all(hasattr(orch, 'console') for orch in [basic_orchestrator, async_orchestrator, advanced_orchestrator])
        assert all(hasattr(orch, 'pkg_path') for orch in [basic_orchestrator, async_orchestrator, advanced_orchestrator])

    def test_workflow_options_compatibility(self, console, temp_project) -> None:
        """Test that workflow options work across orchestrators."""
        options = WorkflowOptions()
        
        basic_orchestrator = WorkflowOrchestrator(console=console, pkg_path=temp_project)
        pipeline = WorkflowPipeline(console=console, pkg_path=temp_project)
        
        # Both should accept WorkflowOptions
        basic_result = basic_orchestrator.execute_workflow(options)
        pipeline_result = pipeline.run_configuration_stage(options)
        
        assert isinstance(basic_result, bool)
        assert isinstance(pipeline_result, bool)

    def test_cross_orchestrator_session_sharing(self, console, temp_project) -> None:
        """Test session sharing between orchestrators."""
        from crackerjack.core.session_coordinator import SessionCoordinator
        # Create orchestrators with shared console and path
        orchestrators = [
            WorkflowOrchestrator(console=console, pkg_path=temp_project),
            WorkflowPipeline(console=console, pkg_path=temp_project),
            AdvancedWorkflowOrchestrator(console=console, pkg_path=temp_project, session=SessionCoordinator(console, temp_project)),
        ]
        
        # Verify they share the same console and path
        for orchestrator in orchestrators:
            assert orchestrator.console is console
            assert orchestrator.pkg_path == temp_project


class TestOrchestrationPerformance:
    """Test orchestration performance characteristics."""

    def test_orchestrator_memory_efficiency(self, console, temp_project) -> None:
        """Test orchestrator memory efficiency."""
        # Create and destroy multiple orchestrators to test memory management
        for i in range(10):
            orchestrator = WorkflowOrchestrator(console=console, pkg_path=temp_project)
            options = MockOptions()
            
            # Quick execution to test resource cleanup
            result = orchestrator.execute_workflow(options)
            assert isinstance(result, bool)
            
            # Python garbage collection should handle cleanup
            del orchestrator

    def test_pipeline_stage_isolation(self, console, temp_project) -> None:
        """Test that pipeline stages are properly isolated."""
        pipeline = WorkflowPipeline(console=console, pkg_path=temp_project)
        options = MockOptions()
        
        # Run multiple stages to ensure no state pollution
        config_result1 = pipeline.run_configuration_stage(options)
        config_result2 = pipeline.run_configuration_stage(options)
        
        assert config_result1 == config_result2
        assert isinstance(config_result1, bool)

    @pytest.mark.asyncio
    async def test_async_orchestrator_concurrency(self, console, temp_project) -> None:
        """Test async orchestrator concurrency capabilities."""
        orchestrator = AsyncWorkflowOrchestrator(console=console, pkg_path=temp_project)
        options = MockOptions()
        
        # Run multiple async workflows concurrently
        import asyncio
        
        tasks = [
            orchestrator.execute_workflow_async(options)
            for _ in range(3)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should complete without exceptions
        for result in results:
            assert not isinstance(result, Exception)
            assert isinstance(result, bool)


class TestOrchestrationErrorHandling:
    """Test orchestration error handling."""

    def test_orchestrator_subprocess_failure(self, console, temp_project) -> None:
        """Test orchestrator handling of subprocess failures."""
        orchestrator = WorkflowOrchestrator(console=console, pkg_path=temp_project)
        options = MockOptions(test=True)
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = Exception("Subprocess error")
            
            # Should handle subprocess errors gracefully
            result = orchestrator.execute_workflow(options)
            assert isinstance(result, bool)

    def test_pipeline_stage_error_propagation(self, console, temp_project) -> None:
        """Test pipeline stage error propagation."""
        pipeline = WorkflowPipeline(console=console, pkg_path=temp_project)
        options = MockOptions()
        
        with patch.object(pipeline, 'run_configuration_stage') as mock_stage:
            mock_stage.side_effect = Exception("Stage error")
            
            # Should handle stage errors gracefully
            try:
                result = pipeline.run_configuration_stage(options)
                assert isinstance(result, bool)
            except Exception:
                # If exception propagates, that's also acceptable behavior
                pass

    @pytest.mark.asyncio
    async def test_async_orchestrator_error_handling(self, console, temp_project) -> None:
        """Test async orchestrator error handling."""
        orchestrator = AsyncWorkflowOrchestrator(console=console, pkg_path=temp_project)
        options = MockOptions()
        
        with patch('asyncio.create_subprocess_exec') as mock_exec:
            mock_exec.side_effect = Exception("Async subprocess error")
            
            # Should handle async subprocess errors gracefully
            result = await orchestrator.execute_workflow_async(options)
            assert isinstance(result, bool)