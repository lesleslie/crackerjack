"""Strategic test coverage for orchestration/advanced_orchestrator.py - Advanced workflow orchestration."""

import pytest
import time
from pathlib import Path
from unittest.mock import Mock, patch
from rich.console import Console

from crackerjack.orchestration.advanced_orchestrator import (
    CorrelationTracker,
    MinimalProgressStreamer,
    ProgressStreamer,
    AdvancedWorkflowOrchestrator,
)
from crackerjack.models.task import HookResult
from crackerjack.executors.individual_hook_executor import HookProgress


class MockSessionCoordinator:
    """Mock session coordinator for testing."""
    
    def __init__(self):
        self.web_job_id = None
        self.progress_file = None
        self.current_stage = None
        self.current_substage = None
    
    def update_stage(self, stage: str, substage: str = ""):
        self.current_stage = stage
        self.current_substage = substage


class MockOrchestrationConfig:
    """Mock orchestration config for testing."""
    
    def __init__(self):
        self.max_iterations = 10
        self.ai_coordination_mode = "auto"
        self.strategy = "adaptive"


class TestCorrelationTracker:
    """Test CorrelationTracker class."""

    def test_tracker_initialization(self):
        """Test correlation tracker initialization."""
        tracker = CorrelationTracker()
        
        assert tracker.iteration_data == []
        assert tracker.failure_patterns == {}
        assert tracker.fix_success_rates == {}

    def test_record_iteration_basic(self):
        """Test recording basic iteration data."""
        tracker = CorrelationTracker()
        
        # Create mock hook results with proper attributes
        ruff_result = Mock()
        ruff_result.name = "ruff"
        ruff_result.status = "passed"
        ruff_result.error_details = []
        
        mypy_result = Mock()
        mypy_result.name = "mypy"
        mypy_result.status = "failed"
        mypy_result.error_details = []
        
        hook_results = [ruff_result, mypy_result]
        test_results = {"failed_tests": ["test_example"]}
        ai_fixes = ["fix_type_annotations"]
        
        tracker.record_iteration(1, hook_results, test_results, ai_fixes)
        
        assert len(tracker.iteration_data) == 1
        iteration = tracker.iteration_data[0]
        assert iteration["iteration"] == 1
        assert iteration["failed_hooks"] == ["mypy"]
        assert iteration["test_failures"] == ["test_example"]
        assert iteration["ai_fixes_applied"] == ["fix_type_annotations"]

    def test_record_iteration_with_error_details(self):
        """Test recording iteration with error details."""
        tracker = CorrelationTracker()
        
        # Create mock hook results with error details
        hook_result = Mock(name="bandit", status="failed")
        hook_result.error_details = ["security_issue_1", "security_issue_2"]
        
        hook_results = [hook_result]
        test_results = {}
        ai_fixes = []
        
        tracker.record_iteration(1, hook_results, test_results, ai_fixes)
        
        iteration = tracker.iteration_data[0]
        assert iteration["total_errors"] == 2

    def test_record_iteration_non_dict_test_results(self):
        """Test recording iteration with non-dict test results."""
        tracker = CorrelationTracker()
        
        ruff_result = Mock()
        ruff_result.name = "ruff"
        ruff_result.status = "passed"
        # Mock objects need error_details attribute for total_errors calculation
        ruff_result.error_details = []
        
        hook_results = [ruff_result]
        test_results = "string_result"  # Non-dict
        ai_fixes = []
        
        tracker.record_iteration(1, hook_results, test_results, ai_fixes)
        
        iteration = tracker.iteration_data[0]
        assert iteration["test_failures"] == []

    def test_analyze_failure_patterns(self):
        """Test failure pattern analysis."""
        tracker = CorrelationTracker()
        
        # Record first iteration with failures
        mypy_result1 = Mock()
        mypy_result1.name = "mypy"
        mypy_result1.status = "failed"
        mypy_result1.error_details = []
        
        ruff_result1 = Mock()
        ruff_result1.name = "ruff"
        ruff_result1.status = "passed"
        ruff_result1.error_details = []
        
        hook_results1 = [mypy_result1, ruff_result1]
        tracker.record_iteration(1, hook_results1, {}, [])
        
        # Record second iteration with recurring failure
        mypy_result2 = Mock()
        mypy_result2.name = "mypy"
        mypy_result2.status = "failed"  # Recurring
        mypy_result2.error_details = []
        
        bandit_result = Mock()
        bandit_result.name = "bandit"
        bandit_result.status = "failed"  # New failure
        bandit_result.error_details = []
        
        hook_results2 = [mypy_result2, bandit_result]
        tracker.record_iteration(2, hook_results2, {}, [])
        
        # Should detect pattern
        assert "mypy" in tracker.failure_patterns
        assert len(tracker.failure_patterns["mypy"]) > 0

    def test_get_problematic_hooks(self):
        """Test getting problematic hooks."""
        tracker = CorrelationTracker()
        
        # Record multiple iterations with recurring failures
        for i in range(3):
            mypy_result = Mock()
            mypy_result.name = "mypy"
            mypy_result.status = "failed"
            mypy_result.error_details = []
            
            hook_results = [mypy_result]
            tracker.record_iteration(i + 1, hook_results, {}, [])
        
        problematic = tracker.get_problematic_hooks()
        assert "mypy" in problematic

    def test_get_correlation_data(self):
        """Test getting correlation data."""
        tracker = CorrelationTracker()
        
        # Record some iterations
        for i in range(5):
            test_result = Mock()
            test_result.name = "test"
            test_result.status = "passed"
            test_result.error_details = []
            hook_results = [test_result]
            tracker.record_iteration(i + 1, hook_results, {}, [])
        
        data = tracker.get_correlation_data()
        
        assert data["iteration_count"] == 5
        assert "failure_patterns" in data
        assert "problematic_hooks" in data
        assert "recent_trends" in data
        assert len(data["recent_trends"]) == 3  # Last 3 iterations

    def test_get_correlation_data_few_iterations(self):
        """Test correlation data with few iterations."""
        tracker = CorrelationTracker()
        
        # Record only 2 iterations
        for i in range(2):
            test_result = Mock()
            test_result.name = "test"
            test_result.status = "passed"
            test_result.error_details = []
            hook_results = [test_result]
            tracker.record_iteration(i + 1, hook_results, {}, [])
        
        data = tracker.get_correlation_data()
        assert len(data["recent_trends"]) == 2  # All iterations


class TestMinimalProgressStreamer:
    """Test MinimalProgressStreamer class."""

    def test_minimal_streamer_initialization(self):
        """Test minimal progress streamer initialization."""
        streamer = MinimalProgressStreamer()
        
        # Should initialize without error
        assert streamer is not None

    def test_update_stage(self):
        """Test stage update method."""
        streamer = MinimalProgressStreamer()
        
        # Should not raise error
        streamer.update_stage("testing", "unit_tests")

    def test_update_hook_progress(self):
        """Test hook progress update method."""
        streamer = MinimalProgressStreamer()
        progress = Mock()
        
        # Should not raise error
        streamer.update_hook_progress(progress)

    def test_stream_update(self):
        """Test internal stream update method."""
        streamer = MinimalProgressStreamer()
        
        # Should not raise error
        streamer._stream_update({"test": "data"})


class TestProgressStreamer:
    """Test ProgressStreamer class."""

    @pytest.fixture
    def mock_config(self):
        """Create mock orchestration config."""
        return MockOrchestrationConfig()

    @pytest.fixture
    def mock_session(self):
        """Create mock session coordinator."""
        return MockSessionCoordinator()

    @pytest.fixture
    def progress_streamer(self, mock_config, mock_session):
        """Create progress streamer with mocks."""
        return ProgressStreamer(mock_config, mock_session)

    def test_streamer_initialization(self, progress_streamer, mock_config, mock_session):
        """Test progress streamer initialization."""
        assert progress_streamer.config is mock_config
        assert progress_streamer.session is mock_session
        assert progress_streamer.current_stage == "initialization"
        assert progress_streamer.current_substage == ""
        assert progress_streamer.hook_progress == {}

    def test_update_stage(self, progress_streamer):
        """Test stage update."""
        progress_streamer.update_stage("testing", "unit_tests")
        
        assert progress_streamer.current_stage == "testing"
        assert progress_streamer.current_substage == "unit_tests"

    def test_update_hook_progress(self, progress_streamer):
        """Test hook progress update."""
        progress = Mock()
        progress.hook_name = "ruff"
        progress.to_dict.return_value = {"status": "running"}
        
        progress_streamer.update_hook_progress(progress)
        
        assert "ruff" in progress_streamer.hook_progress
        assert progress_streamer.hook_progress["ruff"] is progress

    def test_stream_update(self, progress_streamer, mock_session):
        """Test stream update functionality."""
        update_data = {"type": "test", "hook_name": "mypy"}
        
        progress_streamer._stream_update(update_data)
        
        # Should update session
        assert mock_session.current_stage == "initialization"

    def test_update_websocket_progress_no_file(self, progress_streamer, mock_session):
        """Test websocket progress update without file."""
        # No progress file set
        mock_session.web_job_id = "test_job"
        update_data = {"type": "test"}
        
        # Should not raise error even without progress file
        progress_streamer._update_websocket_progress(update_data)

    def test_update_websocket_progress_with_file(self, progress_streamer, mock_session, tmp_path):
        """Test websocket progress update with file."""
        progress_file = tmp_path / "progress.json"
        mock_session.web_job_id = "test_job"
        mock_session.progress_file = progress_file
        
        # Create initial progress file
        progress_file.write_text('{"initial": "data"}')
        
        progress_streamer.current_stage = "testing"
        progress_streamer.current_substage = "unit_tests"
        
        update_data = {"type": "test", "message": "update"}
        
        progress_streamer._update_websocket_progress(update_data)
        
        # Should update file
        assert progress_file.exists()
        import json
        data = json.loads(progress_file.read_text())
        assert data["current_stage"] == "testing"
        assert data["current_substage"] == "unit_tests"


class TestAdvancedWorkflowOrchestrator:
    """Test AdvancedWorkflowOrchestrator class."""

    @pytest.fixture
    def mock_console(self):
        """Create mock console."""
        return Mock(spec=Console)

    @pytest.fixture
    def mock_session(self):
        """Create mock session coordinator."""
        return MockSessionCoordinator()

    @pytest.fixture
    def mock_config(self):
        """Create mock orchestration config."""
        return MockOrchestrationConfig()

    @pytest.fixture
    def orchestrator(self, mock_console, mock_session, mock_config):
        """Create orchestrator with mocked dependencies."""
        pkg_path = Path("/test")
        
        with patch('crackerjack.orchestration.advanced_orchestrator.HookConfigLoader') as mock_loader, \
             patch('crackerjack.orchestration.advanced_orchestrator.HookExecutor') as mock_batch, \
             patch('crackerjack.orchestration.advanced_orchestrator.IndividualHookExecutor') as mock_individual, \
             patch('crackerjack.orchestration.advanced_orchestrator.TestManagementImpl') as mock_test:
            
            return AdvancedWorkflowOrchestrator(
                console=mock_console,
                pkg_path=pkg_path,
                session=mock_session,
                config=mock_config
            )

    def test_orchestrator_initialization(self, orchestrator, mock_console, mock_session, mock_config):
        """Test orchestrator initialization."""
        assert orchestrator.console is mock_console
        assert orchestrator.pkg_path == Path("/test")
        assert orchestrator.session is mock_session
        assert orchestrator.config is mock_config

    def test_orchestrator_initialization_default_config(self, mock_console, mock_session):
        """Test orchestrator initialization with default config."""
        pkg_path = Path("/test")
        
        with patch('crackerjack.orchestration.advanced_orchestrator.HookConfigLoader'), \
             patch('crackerjack.orchestration.advanced_orchestrator.HookExecutor'), \
             patch('crackerjack.orchestration.advanced_orchestrator.IndividualHookExecutor'), \
             patch('crackerjack.orchestration.advanced_orchestrator.TestManagementImpl'), \
             patch('crackerjack.orchestration.advanced_orchestrator.OrchestrationConfig') as mock_config_class:
            
            mock_config_class.return_value = mock_config_class
            
            orchestrator = AdvancedWorkflowOrchestrator(
                console=mock_console,
                pkg_path=pkg_path,
                session=mock_session
            )
            
            # Should create default config
            assert orchestrator.config is not None

    def test_orchestrator_has_required_components(self, orchestrator):
        """Test that orchestrator has required components."""
        assert hasattr(orchestrator, 'hook_config_loader')
        assert hasattr(orchestrator, 'batch_executor')
        assert hasattr(orchestrator, 'individual_executor')
        assert hasattr(orchestrator, 'test_manager')

    def test_orchestrator_components_initialization(self, orchestrator):
        """Test orchestrator components are properly initialized."""
        # All major components should be initialized
        assert orchestrator.hook_config_loader is not None
        assert orchestrator.batch_executor is not None
        assert orchestrator.individual_executor is not None
        assert orchestrator.test_manager is not None


class TestIntegrationScenarios:
    """Integration test scenarios for advanced orchestrator."""

    def test_correlation_tracker_workflow(self):
        """Test correlation tracker in a typical workflow."""
        tracker = CorrelationTracker()
        
        # Simulate multiple iterations of a workflow
        iterations = [
            (["mypy", "ruff"], {"failed_tests": ["test_1"]}, ["fix_types"]),
            (["mypy"], {"failed_tests": []}, ["fix_imports"]),
            ([], {"failed_tests": []}, []),
        ]
        
        for i, (failed_hooks, test_results, fixes) in enumerate(iterations):
            hook_results = []
            # Create failed hooks
            for hook in failed_hooks:
                failed_result = Mock()
                failed_result.name = hook
                failed_result.status = "failed"
                failed_result.error_details = []
                hook_results.append(failed_result)
            
            # Add a passing hook
            passing_result = Mock()
            passing_result.name = "passing"
            passing_result.status = "passed"
            passing_result.error_details = []
            hook_results.append(passing_result)
            
            tracker.record_iteration(i + 1, hook_results, test_results, fixes)
        
        # Should track improvement over iterations
        assert len(tracker.iteration_data) == 3
        assert tracker.iteration_data[0]["failed_hooks"] == ["mypy", "ruff"]
        assert tracker.iteration_data[1]["failed_hooks"] == ["mypy"]
        assert tracker.iteration_data[2]["failed_hooks"] == []

    def test_progress_streamer_coordination(self):
        """Test progress streamer coordination."""
        config = MockOrchestrationConfig()
        session = MockSessionCoordinator()
        streamer = ProgressStreamer(config, session)
        
        # Simulate workflow progression
        streamer.update_stage("hooks", "fast_hooks")
        
        # Add hook progress
        progress = Mock()
        progress.hook_name = "ruff"
        progress.to_dict.return_value = {"status": "running", "progress": 0.5}
        
        streamer.update_hook_progress(progress)
        
        # Update to next stage
        streamer.update_stage("tests", "unit_tests")
        
        assert streamer.current_stage == "tests"
        assert "ruff" in streamer.hook_progress

    def test_orchestrator_component_interaction(self):
        """Test orchestrator component interaction."""
        console = Mock(spec=Console)
        session = MockSessionCoordinator()
        config = MockOrchestrationConfig()
        pkg_path = Path("/test")
        
        with patch('crackerjack.orchestration.advanced_orchestrator.HookConfigLoader') as mock_loader, \
             patch('crackerjack.orchestration.advanced_orchestrator.HookExecutor') as mock_batch, \
             patch('crackerjack.orchestration.advanced_orchestrator.IndividualHookExecutor') as mock_individual, \
             patch('crackerjack.orchestration.advanced_orchestrator.TestManagementImpl') as mock_test:
            
            orchestrator = AdvancedWorkflowOrchestrator(
                console=console,
                pkg_path=pkg_path,
                session=session,
                config=config
            )
            
            # Verify components were created with correct parameters
            mock_loader.assert_called_once()
            mock_batch.assert_called_once_with(console, pkg_path)
            mock_individual.assert_called_once_with(console, pkg_path)
            mock_test.assert_called_once_with(console, pkg_path)

    def test_minimal_vs_full_progress_streamer(self):
        """Test minimal vs full progress streamer functionality."""
        minimal = MinimalProgressStreamer()
        
        config = MockOrchestrationConfig()
        session = MockSessionCoordinator()
        full = ProgressStreamer(config, session)
        
        # Both should handle the same interface
        minimal.update_stage("test")
        full.update_stage("test")
        
        progress = Mock()
        progress.hook_name = "test"
        progress.to_dict.return_value = {}
        
        minimal.update_hook_progress(progress)
        full.update_hook_progress(progress)
        
        # Full streamer should maintain state
        assert full.current_stage == "test"
        assert "test" in full.hook_progress