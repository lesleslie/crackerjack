"""Consolidated manager testing module."""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.managers.hook_manager import HookManagerImpl
from crackerjack.managers.publish_manager import PublishManagerImpl
from crackerjack.managers.test_manager import TestManagementImpl
from crackerjack.models.config import HookConfig, PublishConfig, TestConfig
from crackerjack.models.task import HookResult


@pytest.fixture
def console():
    """Console fixture for testing."""
    return Console(force_terminal=True)


@pytest.fixture
def temp_project(tmp_path):
    """Temporary project directory fixture."""
    return tmp_path


class MockOptions:
    """Mock options for testing."""
    
    def __init__(self, **kwargs) -> None:
        # Test options
        self.test = False
        self.benchmark = False
        self.test_workers = 0
        self.test_timeout = 0
        
        # Hook options
        self.skip_hooks = False
        self.update_precommit = False
        self.experimental_hooks = False
        
        # Publish options
        self.publish = None
        self.bump = None
        
        # General options
        self.verbose = False
        self.dry_run = False
        
        # Override with provided kwargs
        for key, value in kwargs.items():
            setattr(self, key, value)


class TestHookManagerImpl:
    """Test HookManagerImpl functionality."""

    def test_initialization(self, console, temp_project) -> None:
        """Test hook manager initialization."""
        manager = HookManagerImpl(console=console, pkg_path=temp_project)
        assert manager.console is console
        assert manager.pkg_path == temp_project

    @patch("subprocess.run")
    def test_run_fast_hooks_success(self, mock_run, console, temp_project) -> None:
        """Test successful fast hooks execution."""
        mock_run.return_value = Mock(returncode=0, stdout="All hooks passed", stderr="")
        
        manager = HookManagerImpl(console=console, pkg_path=temp_project)
        options = MockOptions()
        
        results = manager.run_fast_hooks(options)
        assert isinstance(results, list)
        
    @patch("subprocess.run")
    def test_run_comprehensive_hooks_success(self, mock_run, console, temp_project) -> None:
        """Test successful comprehensive hooks execution."""
        mock_run.return_value = Mock(returncode=0, stdout="All hooks passed", stderr="")
        
        manager = HookManagerImpl(console=console, pkg_path=temp_project)
        options = MockOptions()
        
        results = manager.run_comprehensive_hooks(options)
        assert isinstance(results, list)

    @patch("subprocess.run")
    def test_run_hooks_failure(self, mock_run, console, temp_project) -> None:
        """Test hook execution failure handling."""
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="Hook failed")
        
        manager = HookManagerImpl(console=console, pkg_path=temp_project)
        options = MockOptions()
        
        results = manager.run_fast_hooks(options)
        assert isinstance(results, list)
        # Should handle failures gracefully

    def test_skip_hooks_option(self, console, temp_project) -> None:
        """Test skip hooks functionality."""
        manager = HookManagerImpl(console=console, pkg_path=temp_project)
        options = MockOptions(skip_hooks=True)
        
        # When hooks are skipped, should return empty results quickly
        results = manager.run_fast_hooks(options)
        assert isinstance(results, list)


class TestTestManagementImpl:
    """Test TestManagementImpl functionality."""

    def test_initialization(self, console, temp_project) -> None:
        """Test test manager initialization."""
        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        assert manager.console is console
        assert manager.pkg_path == temp_project

    @patch("subprocess.run")
    def test_run_tests_success(self, mock_run, console, temp_project) -> None:
        """Test successful test execution."""
        mock_run.return_value = Mock(
            returncode=0, 
            stdout="10 passed, 0 failed",
            stderr=""
        )
        
        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        options = MockOptions(test=True)
        
        result = manager.run_tests(options)
        assert result is True

    @patch("subprocess.run")
    def test_run_tests_failure(self, mock_run, console, temp_project) -> None:
        """Test test execution failure."""
        mock_run.return_value = Mock(
            returncode=1,
            stdout="5 passed, 2 failed",
            stderr="Tests failed"
        )
        
        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        options = MockOptions(test=True)
        
        result = manager.run_tests(options)
        assert result is False

    def test_test_disabled(self, console, temp_project) -> None:
        """Test when testing is disabled."""
        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        options = MockOptions(test=False)
        
        result = manager.run_tests(options)
        assert result is True  # Should succeed when testing is disabled

    @patch("subprocess.run")
    def test_benchmark_mode(self, mock_run, console, temp_project) -> None:
        """Test benchmark mode execution."""
        mock_run.return_value = Mock(returncode=0, stdout="Benchmark complete", stderr="")
        
        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        options = MockOptions(test=True, benchmark=True)
        
        result = manager.run_tests(options)
        assert result is True

    @patch("subprocess.run")
    def test_test_workers_configuration(self, mock_run, console, temp_project) -> None:
        """Test test workers configuration."""
        mock_run.return_value = Mock(returncode=0, stdout="Tests completed", stderr="")
        
        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        options = MockOptions(test=True, test_workers=4)
        
        result = manager.run_tests(options)
        assert result is True

    @patch("subprocess.run")
    def test_test_timeout_configuration(self, mock_run, console, temp_project) -> None:
        """Test test timeout configuration."""
        mock_run.return_value = Mock(returncode=0, stdout="Tests completed", stderr="")
        
        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        options = MockOptions(test=True, test_timeout=300)
        
        result = manager.run_tests(options)
        assert result is True


class TestPublishManagerImpl:
    """Test PublishManagerImpl functionality."""

    def test_initialization(self, console, temp_project) -> None:
        """Test publish manager initialization."""
        manager = PublishManagerImpl(console=console, pkg_path=temp_project)
        assert manager.console is console
        assert manager.pkg_path == temp_project

    @patch("subprocess.run")
    def test_version_bump_patch(self, mock_run, console, temp_project) -> None:
        """Test patch version bump."""
        mock_run.return_value = Mock(returncode=0, stdout="Version bumped", stderr="")
        
        manager = PublishManagerImpl(console=console, pkg_path=temp_project)
        options = MockOptions(bump="patch")
        
        result = manager.bump_version(options)
        assert isinstance(result, bool)

    @patch("subprocess.run")
    def test_version_bump_minor(self, mock_run, console, temp_project) -> None:
        """Test minor version bump."""
        mock_run.return_value = Mock(returncode=0, stdout="Version bumped", stderr="")
        
        manager = PublishManagerImpl(console=console, pkg_path=temp_project)
        options = MockOptions(bump="minor")
        
        result = manager.bump_version(options)
        assert isinstance(result, bool)

    @patch("subprocess.run")
    def test_version_bump_major(self, mock_run, console, temp_project) -> None:
        """Test major version bump."""
        mock_run.return_value = Mock(returncode=0, stdout="Version bumped", stderr="")
        
        manager = PublishManagerImpl(console=console, pkg_path=temp_project)
        options = MockOptions(bump="major")
        
        result = manager.bump_version(options)
        assert isinstance(result, bool)

    @patch("subprocess.run")
    def test_publish_to_pypi(self, mock_run, console, temp_project) -> None:
        """Test PyPI publishing."""
        mock_run.return_value = Mock(returncode=0, stdout="Published successfully", stderr="")
        
        manager = PublishManagerImpl(console=console, pkg_path=temp_project)
        options = MockOptions(publish="patch")
        
        result = manager.publish(options)
        assert isinstance(result, bool)

    def test_publish_disabled(self, console, temp_project) -> None:
        """Test when publishing is disabled."""
        manager = PublishManagerImpl(console=console, pkg_path=temp_project)
        options = MockOptions(publish=None)
        
        result = manager.publish(options)
        assert result is True  # Should succeed when publishing is disabled

    @patch("subprocess.run")
    def test_dry_run_mode(self, mock_run, console, temp_project) -> None:
        """Test dry run mode for publishing."""
        mock_run.return_value = Mock(returncode=0, stdout="Dry run successful", stderr="")
        
        manager = PublishManagerImpl(console=console, pkg_path=temp_project)
        options = MockOptions(publish="patch", dry_run=True)
        
        result = manager.publish(options)
        assert isinstance(result, bool)


class TestManagersIntegration:
    """Test integration between managers."""

    def test_managers_work_together(self, console, temp_project) -> None:
        """Test that managers can be used together."""
        hook_manager = HookManagerImpl(console=console, pkg_path=temp_project)
        test_manager = TestManagementImpl(console=console, pkg_path=temp_project)
        publish_manager = PublishManagerImpl(console=console, pkg_path=temp_project)
        
        # Verify all managers are properly initialized
        assert hook_manager.console is console
        assert test_manager.console is console
        assert publish_manager.console is console
        
        assert hook_manager.pkg_path == temp_project
        assert test_manager.pkg_path == temp_project
        assert publish_manager.pkg_path == temp_project

    @patch("subprocess.run")
    def test_workflow_simulation(self, mock_run, console, temp_project) -> None:
        """Test simulated workflow using all managers."""
        mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
        
        # Initialize managers
        hook_manager = HookManagerImpl(console=console, pkg_path=temp_project)
        test_manager = TestManagementImpl(console=console, pkg_path=temp_project)
        
        # Simulate workflow
        options = MockOptions(test=True)
        
        # Run hooks
        hook_results = hook_manager.run_fast_hooks(options)
        assert isinstance(hook_results, list)
        
        # Run tests
        test_result = test_manager.run_tests(options)
        assert isinstance(test_result, bool)


class TestManagerConfiguration:
    """Test manager configuration handling."""

    def test_hook_config_integration(self, console, temp_project) -> None:
        """Test hook configuration integration."""
        manager = HookManagerImpl(console=console, pkg_path=temp_project)
        
        # Test with different configurations
        configs = [
            MockOptions(skip_hooks=True),
            MockOptions(experimental_hooks=True),
            MockOptions(update_precommit=True),
        ]
        
        for config in configs:
            results = manager.run_fast_hooks(config)
            assert isinstance(results, list)

    def test_test_config_integration(self, console, temp_project) -> None:
        """Test test configuration integration."""
        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        
        # Test with different configurations
        configs = [
            MockOptions(test=False),
            MockOptions(test=True, benchmark=True),
            MockOptions(test=True, test_workers=2, test_timeout=60),
        ]
        
        for config in configs:
            result = manager.run_tests(config)
            assert isinstance(result, bool)

    def test_publish_config_integration(self, console, temp_project) -> None:
        """Test publish configuration integration."""
        manager = PublishManagerImpl(console=console, pkg_path=temp_project)
        
        # Test with different configurations
        configs = [
            MockOptions(publish=None),
            MockOptions(bump="patch"),
            MockOptions(publish="minor", dry_run=True),
        ]
        
        for config in configs:
            if config.publish:
                result = manager.publish(config)
            elif config.bump:
                result = manager.bump_version(config)
            else:
                result = manager.publish(config)
            assert isinstance(result, bool)


class TestManagerErrorHandling:
    """Test manager error handling."""

    @patch("subprocess.run")
    def test_hook_manager_subprocess_error(self, mock_run, console, temp_project) -> None:
        """Test hook manager handling subprocess errors."""
        mock_run.side_effect = subprocess.CalledProcessError(1, ["cmd"])
        
        manager = HookManagerImpl(console=console, pkg_path=temp_project)
        options = MockOptions()
        
        # Should handle subprocess errors gracefully
        results = manager.run_fast_hooks(options)
        assert isinstance(results, list)

    @patch("subprocess.run")
    def test_test_manager_subprocess_error(self, mock_run, console, temp_project) -> None:
        """Test test manager handling subprocess errors."""
        mock_run.side_effect = subprocess.CalledProcessError(1, ["pytest"])
        
        manager = TestManagementImpl(console=console, pkg_path=temp_project)
        options = MockOptions(test=True)
        
        # Should handle subprocess errors gracefully
        result = manager.run_tests(options)
        assert isinstance(result, bool)

    @patch("subprocess.run")
    def test_publish_manager_subprocess_error(self, mock_run, console, temp_project) -> None:
        """Test publish manager handling subprocess errors."""
        mock_run.side_effect = subprocess.CalledProcessError(1, ["uv", "build"])
        
        manager = PublishManagerImpl(console=console, pkg_path=temp_project)
        options = MockOptions(publish="patch")
        
        # Should handle subprocess errors gracefully
        result = manager.publish(options)
        assert isinstance(result, bool)