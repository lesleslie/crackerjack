"""Tests for the skip-hooks functionality."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.managers.hook_manager import HookManagerImpl
from crackerjack.models.protocols import OptionsProtocol


class MockOptions:
    """Mock options class for testing."""
    
    def __init__(self, skip_hooks=False, test=False, commit=False, publish=None, all=None, bump=None):
        self.skip_hooks = skip_hooks
        self.test = test
        self.commit = commit
        self.publish = publish
        self.all = all
        self.bump = bump
        # Add other required attributes with default values
        self.verbose = False
        self.fast = False
        self.comp = False
        self.clean = False
        self.no_config_updates = False
        self.update_precommit = False
        self.interactive = False
        self.debug = False
        self.benchmark = False
        self.test_workers = 0
        self.test_timeout = 0
        self.start_mcp_server = False
        self.stop_mcp_server = False
        self.restart_mcp_server = False
        self.create_pr = False
        self.async_mode = False
        self.experimental_hooks = False
        self.enable_pyrefly = False
        self.enable_ty = False
        self.cleanup = None
        self.no_git_tags = False
        self.skip_version_check = False
        self.cleanup_pypi = False
        self.keep_releases = 10
        self.track_progress = False
        self.orchestrated = False
        self.boost_coverage = True
        self.coverage = False
        self.orchestration_strategy = "adaptive"
        self.orchestration_progress = "granular"
        self.orchestration_ai_mode = "single-agent"
        self.monitor = False
        self.enhanced_monitor = False
        self.watchdog = False
        self.start_websocket_server = False
        self.stop_websocket_server = False
        self.restart_websocket_server = False
        self.websocket_port = None
        self.start_zuban_lsp = False
        self.stop_zuban_lsp = False
        self.restart_zuban_lsp = False
        self.no_zuban_lsp = False
        self.zuban_lsp_port = 8677
        self.zuban_lsp_mode = "tcp"
        self.zuban_lsp_timeout = 30
        self.enable_lsp_hooks = False
        self.dev = False
        self.dashboard = False
        self.unified_dashboard = False
        self.unified_dashboard_port = None
        self.max_iterations = 5
        self.enterprise_batch = None
        self.monitor_dashboard = None
        self.coverage_status = False
        self.coverage_goal = None
        self.no_coverage_ratchet = False
        self.skip_config_merge = False
        self.disable_global_locks = False
        self.global_lock_timeout = 600
        self.global_lock_cleanup = True
        self.global_lock_dir = None
        self.quick = False
        self.thorough = False
        self.clear_cache = False
        self.cache_stats = False
        self.strip_code = None
        self.ai_fix = None
        self.full_release = None
        self.show_progress = None
        self.advanced_monitor = None
        self.coverage_report = None
        self.clean_releases = None
        self.generate_docs = False
        self.docs_format = "markdown"
        self.validate_docs = False
        self.generate_changelog = False
        self.changelog_version = None
        self.changelog_since = None
        self.changelog_dry_run = False
        self.auto_version = False
        self.version_since = None
        self.accept_version = False
        self.smart_commit = True
        self.heatmap = False
        self.heatmap_type = "error_frequency"
        self.heatmap_output = None
        self.anomaly_detection = False
        self.anomaly_sensitivity = 2.0
        self.anomaly_report = None
        self.predictive_analytics = False
        self.prediction_periods = 10
        self.analytics_dashboard = None
        self.enterprise_optimizer = False
        self.enterprise_profile = None
        self.enterprise_report = None
        self.mkdocs_integration = False
        self.mkdocs_serve = False
        self.mkdocs_theme = "material"
        self.mkdocs_output = None
        self.contextual_ai = False
        self.ai_recommendations = 5
        self.ai_help_query = None
        self.check_config_updates = False
        self.apply_config_updates = False
        self.diff_config = None
        self.config_interactive = False
        self.refresh_cache = False


@pytest.fixture
def console():
    """Create a console fixture."""
    return Console()


@pytest.fixture
def pkg_path():
    """Create a package path fixture."""
    return Path.cwd()


@pytest.fixture
def hook_manager(console, pkg_path):
    """Create a hook manager fixture."""
    return HookManagerImpl(console, pkg_path)


@pytest.fixture
def phase_coordinator(console, pkg_path, hook_manager):
    """Create a phase coordinator fixture."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        temp_path = Path(tmp_dir)
        
        # Mock required dependencies
        mock_filesystem = Mock()
        mock_git_service = Mock()
        mock_test_manager = Mock()
        mock_publish_manager = Mock()
        mock_config_merge_service = Mock()
        
        return PhaseCoordinator(
            console=console,
            pkg_path=temp_path,
            session=Mock(),
            filesystem=mock_filesystem,
            git_service=mock_git_service,
            hook_manager=hook_manager,
            test_manager=mock_test_manager,
            publish_manager=mock_publish_manager,
            config_merge_service=mock_config_merge_service,
        )


class TestSkipHooksFunctionality:
    """Test cases for the skip-hooks functionality."""

    def test_run_fast_hooks_only_with_skip_hooks(self, phase_coordinator):
        """Test that run_fast_hooks_only skips execution when skip_hooks is True."""
        options = MockOptions(skip_hooks=True)
        
        # Mock the hook manager
        with patch.object(phase_coordinator.hook_manager, 'run_fast_hooks') as mock_run:
            result = phase_coordinator.run_fast_hooks_only(options)
            
            # Verify that the method returns True immediately
            assert result is True
            
            # Verify that run_fast_hooks was never called
            mock_run.assert_not_called()

    def test_run_fast_hooks_only_without_skip_hooks(self, phase_coordinator):
        """Test that run_fast_hooks_only executes when skip_hooks is False."""
        options = MockOptions(skip_hooks=False)
        
        # Mock the hook manager to return successful results
        mock_result = Mock()
        mock_result.status = "passed"
        with patch.object(phase_coordinator.hook_manager, 'run_fast_hooks') as mock_run:
            mock_run.return_value = [mock_result]
            
            result = phase_coordinator.run_fast_hooks_only(options)
            
            # Verify that the method was called and returned True
            assert result is True
            mock_run.assert_called_once()

    def test_run_comprehensive_hooks_only_with_skip_hooks(self, phase_coordinator):
        """Test that run_comprehensive_hooks_only skips execution when skip_hooks is True."""
        options = MockOptions(skip_hooks=True)
        
        # Mock the hook manager
        with patch.object(phase_coordinator.hook_manager, 'run_comprehensive_hooks') as mock_run:
            result = phase_coordinator.run_comprehensive_hooks_only(options)
            
            # Verify that the method returns True immediately
            assert result is True
            
            # Verify that run_comprehensive_hooks was never called
            mock_run.assert_not_called()

    def test_run_comprehensive_hooks_only_without_skip_hooks(self, phase_coordinator):
        """Test that run_comprehensive_hooks_only executes when skip_hooks is False."""
        options = MockOptions(skip_hooks=False)
        
        # Mock the hook manager to return successful results
        mock_result = Mock()
        mock_result.status = "passed"
        with patch.object(phase_coordinator.hook_manager, 'run_comprehensive_hooks') as mock_run:
            mock_run.return_value = [mock_result]
            
            result = phase_coordinator.run_comprehensive_hooks_only(options)
            
            # Verify that the method was called and returned True
            assert result is True
            mock_run.assert_called_once()

    def test_run_hooks_phase_with_skip_hooks(self, phase_coordinator):
        """Test that run_hooks_phase skips execution when skip_hooks is True."""
        options = MockOptions(skip_hooks=True)
        
        # Mock the hook execution methods
        with patch.object(phase_coordinator, 'run_fast_hooks_only') as mock_fast, \
             patch.object(phase_coordinator, 'run_comprehensive_hooks_only') as mock_comp:
            
            result = phase_coordinator.run_hooks_phase(options)
            
            # Verify that the method returns True immediately
            assert result is True
            
            # Verify that neither hook method was called
            mock_fast.assert_not_called()
            mock_comp.assert_not_called()

    def test_run_hooks_phase_without_skip_hooks(self, phase_coordinator):
        """Test that run_hooks_phase executes when skip_hooks is False."""
        options = MockOptions(skip_hooks=False)
        
        # Mock the hook execution methods to return successful results
        with patch.object(phase_coordinator, 'run_fast_hooks_only') as mock_fast, \
             patch.object(phase_coordinator, 'run_comprehensive_hooks_only') as mock_comp:
            mock_fast.return_value = True
            mock_comp.return_value = True
            
            result = phase_coordinator.run_hooks_phase(options)
            
            # Verify that the method was called and returned True
            assert result is True
            mock_fast.assert_called_once_with(options)
            mock_comp.assert_called_once_with(options)

    def test_integration_skip_hooks_end_to_end(self, phase_coordinator):
        """Test the end-to-end behavior of skip_hooks option."""
        # Test with skip_hooks=True
        options_with_skip = MockOptions(skip_hooks=True, test=True)
        
        with patch.object(phase_coordinator.hook_manager, 'run_fast_hooks') as mock_fast, \
             patch.object(phase_coordinator.hook_manager, 'run_comprehensive_hooks') as mock_comp:
            
            # Run a workflow that would normally execute hooks
            phase_coordinator.run_hooks_phase(options_with_skip)
            
            # Verify that no hooks were executed
            mock_fast.assert_not_called()
            mock_comp.assert_not_called()
        
        # Test with skip_hooks=False
        options_without_skip = MockOptions(skip_hooks=False, test=True)
        
        with patch.object(phase_coordinator.hook_manager, 'run_fast_hooks') as mock_fast, \
             patch.object(phase_coordinator.hook_manager, 'run_comprehensive_hooks') as mock_comp:
            # Mock successful hook results
            mock_fast_result = Mock()
            mock_fast_result.status = "passed"
            mock_comp_result = Mock()
            mock_comp_result.status = "passed"
            mock_fast.return_value = [mock_fast_result]
            mock_comp.return_value = [mock_comp_result]
            
            # Run a workflow that should execute hooks
            result = phase_coordinator.run_hooks_phase(options_without_skip)
            
            # Verify that hooks were executed
            assert mock_fast.call_count == 1
            assert mock_comp.call_count == 1
            assert result is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])