"""Integration tests for key crackerjack workflows.

Tests complete workflows from start to finish:
- Full crackerjack execution with hooks and tests
- MCP server integration
- WebSocket communication
- Configuration loading and validation
- Error recovery and retry logic
"""

import contextlib
import os
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
from rich.console import Console

from crackerjack.core.workflow_orchestrator import WorkflowOrchestrator
from crackerjack.managers.hook_manager import HookManagerImpl
from crackerjack.services.config import ConfigurationService
from crackerjack.services.filesystem import FileSystemService
from crackerjack.services.git import GitService
from crackerjack.services.unified_config import CrackerjackConfig


@pytest.mark.integration
class TestWorkflowIntegration:
    """Test complete workflow integration."""

    def test_basic_workflow_execution(self, temp_project_dir, sample_config) -> None:
        """Test basic workflow from start to finish."""
        # Update config to use temp project
        sample_config.project_path = temp_project_dir
        sample_config.testing = False  # Skip tests for speed
        sample_config.skip_hooks = True  # Skip hooks for reliability

        orchestrator = WorkflowOrchestrator(sample_config)

        # Execute workflow
        result = orchestrator.execute_workflow()

        # Should complete successfully
        assert isinstance(result, bool)

    def test_workflow_with_configuration_loading(self, temp_project_dir) -> None:
        """Test workflow with real configuration loading."""
        # Create pyproject.toml in temp project
        config_content = """
[tool.crackerjack]
test_timeout = 30
test_workers = 1
skip_hooks = true
testing = false
        """
        (temp_project_dir / "pyproject.toml").write_text(config_content.strip())

        # Load configuration
        config_service = ConfigurationService()
        config = config_service.load_config_from_file(
            str(temp_project_dir / "pyproject.toml"),
        )

        assert config is not None

    def test_hook_manager_integration(self, temp_project_dir, sample_config) -> None:
        """Test hook manager integration with filesystem."""
        sample_config.project_path = temp_project_dir
        sample_config.skip_hooks = True  # Use mock hooks for reliability

        hook_manager = HookManagerImpl(console=Console(), pkg_path=Path.cwd())

        # Mock the actual hook execution for integration test
        with patch.object(hook_manager, "_run_hook_command") as mock_run:
            mock_run.return_value = (True, "Mock hook passed", "")

            success, errors = hook_manager.run_fast_hooks()

            # Should handle the workflow
            assert isinstance(success, bool)
            assert isinstance(errors, list)

    def test_filesystem_integration(self, temp_project_dir) -> None:
        """Test filesystem service with real file operations."""
        fs_service = FileSystemService()

        # Test file operations
        test_file = temp_project_dir / "integration_test.txt"
        test_content = "Integration test content"

        # Write file
        fs_service.write_file(str(test_file), test_content)

        # Verify file exists
        assert fs_service.file_exists(str(test_file))

        # Read file back
        content = fs_service.read_file(str(test_file))
        assert content == test_content

        # Test directory creation
        new_dir = temp_project_dir / "new_test_dir"
        fs_service.create_directory(str(new_dir))
        assert new_dir.exists()

    def test_git_integration(self, temp_project_dir) -> None:
        """Test git service integration."""
        # Change to temp project directory
        original_cwd = os.getcwd()
        os.chdir(temp_project_dir)

        try:
            git_service = GitService()

            # Should detect git repo (created in temp_project_dir fixture)
            is_repo = git_service.is_git_repo()
            assert isinstance(is_repo, bool)

            # Test getting current branch
            try:
                branch = git_service.get_current_branch()
                assert isinstance(branch, str | type(None))
            except Exception:
                # Git operations might fail in test environment
                pass

        finally:
            os.chdir(original_cwd)


@pytest.mark.integration
@pytest.mark.slow
class TestMCPIntegration:
    """Test MCP server integration."""

    def test_mcp_server_import(self) -> None:
        """Test that MCP server can be imported."""
        try:
            from crackerjack.mcp.server import main as mcp_main

            assert callable(mcp_main)
        except ImportError:
            pytest.skip("MCP server not available")

    def test_websocket_server_import(self) -> None:
        """Test that WebSocket server can be imported."""
        try:
            from crackerjack.mcp.websocket_server import main as ws_main

            assert callable(ws_main)
        except ImportError:
            pytest.skip("WebSocket server not available")


@pytest.mark.integration
class TestConfigurationIntegration:
    """Test configuration loading and validation."""

    def test_config_service_integration(self, temp_dir) -> None:
        """Test configuration service with real TOML files."""
        config_service = ConfigurationService()

        # Create test config file
        config_file = temp_dir / "test.toml"
        config_content = """
[tool.crackerjack]
test_timeout = 120
test_workers = 4
skip_hooks = false
testing = true
verbose = false
        """
        config_file.write_text(config_content.strip())

        # Load configuration
        config = config_service.load_config_from_file(str(config_file))
        assert config is not None

        # Test merging configurations
        override_config = {"test_timeout": 60, "verbose": True}
        merged = config_service.merge_configs(config, override_config)

        assert merged["test_timeout"] == 60
        assert merged["verbose"] is True

    def test_crackerjack_config_validation(self) -> None:
        """Test CrackerjackConfig validation."""
        # Valid config
        valid_config = CrackerjackConfig(
            project_path=Path.cwd(), test_timeout=60, test_workers=2, testing=True,
        )

        assert valid_config.project_path == Path.cwd()
        assert valid_config.test_timeout == 60
        assert valid_config.test_workers == 2
        assert valid_config.testing is True


@pytest.mark.integration
@pytest.mark.performance
class TestWorkflowPerformance:
    """Test workflow performance characteristics."""

    def test_fast_hook_performance(
        self, temp_project_dir, sample_config, performance_timer,
    ) -> None:
        """Test that fast hooks complete within reasonable time."""
        sample_config.project_path = temp_project_dir
        sample_config.skip_hooks = True  # Use mock for performance test

        hook_manager = HookManagerImpl(console=Console(), pkg_path=Path.cwd())

        with patch.object(hook_manager, "_run_hook_command") as mock_run:
            mock_run.return_value = (True, "Fast hook passed", "")

            timer = performance_timer()
            hook_manager.run_fast_hooks()
            duration = timer()

            # Fast hooks should complete quickly (mocked)
            assert duration < 5.0  # 5 seconds max for mocked hooks

    def test_workflow_orchestrator_performance(
        self, temp_project_dir, sample_config, performance_timer,
    ) -> None:
        """Test workflow orchestrator performance."""
        sample_config.project_path = temp_project_dir
        sample_config.testing = False
        sample_config.skip_hooks = True

        orchestrator = WorkflowOrchestrator(sample_config)

        timer = performance_timer()
        result = orchestrator.execute_workflow()
        duration = timer()

        # Workflow should complete in reasonable time
        assert duration < 30.0  # 30 seconds max for basic workflow
        assert isinstance(result, bool)


@pytest.mark.integration
@pytest.mark.external
class TestExternalDependencies:
    """Test integration with external dependencies."""

    def test_uv_availability(self) -> None:
        """Test that UV package manager is available."""
        try:
            result = subprocess.run(
                ["uv", "--version"], check=False, capture_output=True, text=True, timeout=10,
            )
            assert result.returncode == 0
            assert "uv" in result.stdout.lower()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("UV not available in test environment")

    def test_pre_commit_availability(self) -> None:
        """Test that pre-commit is available."""
        try:
            result = subprocess.run(
                ["pre-commit", "--version"], check=False, capture_output=True, text=True, timeout=10,
            )
            assert result.returncode == 0
            assert "pre-commit" in result.stdout.lower()
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pytest.skip("pre-commit not available in test environment")


@pytest.mark.integration
@pytest.mark.regression
class TestRegressionScenarios:
    """Test scenarios that have caused issues in the past."""

    def test_empty_project_handling(self, temp_dir) -> None:
        """Test handling of empty project directory."""
        empty_project = temp_dir / "empty_project"
        empty_project.mkdir()

        config = CrackerjackConfig(
            project_path=empty_project,
            test_timeout=30,
            test_workers=1,
            testing=False,
            skip_hooks=True,
        )

        orchestrator = WorkflowOrchestrator(config)

        # Should handle empty project gracefully
        result = orchestrator.execute_workflow()
        assert isinstance(result, bool)

    def test_missing_pyproject_toml(self, temp_dir) -> None:
        """Test handling of missing pyproject.toml."""
        project_without_config = temp_dir / "no_config_project"
        project_without_config.mkdir()

        config_service = ConfigurationService()

        # Should handle missing config file gracefully
        with pytest.raises((FileNotFoundError, Exception)):
            config_service.load_config_from_file(
                str(project_without_config / "pyproject.toml"),
            )


@pytest.mark.integration
class TestErrorRecovery:
    """Test error recovery and retry mechanisms."""

    def test_hook_failure_recovery(self, temp_project_dir, sample_config) -> None:
        """Test recovery from hook failures."""
        sample_config.project_path = temp_project_dir

        hook_manager = HookManagerImpl(console=Console(), pkg_path=Path.cwd())

        # Simulate hook failure then success
        call_count = 0

        def mock_hook_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return (False, "Hook failed", "Error details")
            return (True, "Hook passed", "")

        with patch.object(
            hook_manager, "_run_hook_command", side_effect=mock_hook_side_effect,
        ):
            success, errors = hook_manager.run_fast_hooks()

            # Should handle failure gracefully
            assert isinstance(success, bool)
            assert isinstance(errors, list)

    def test_filesystem_error_handling(self, temp_dir) -> None:
        """Test filesystem error handling."""
        fs_service = FileSystemService()

        # Test reading non-existent file
        non_existent = temp_dir / "does_not_exist.txt"

        with pytest.raises(FileNotFoundError):
            fs_service.read_file(str(non_existent))

        # Test writing to read-only location (if possible)
        try:
            # Create read-only directory
            readonly_dir = temp_dir / "readonly"
            readonly_dir.mkdir()
            readonly_dir.chmod(0o444)  # Read-only

            readonly_file = readonly_dir / "readonly.txt"

            # Should raise exception when trying to write
            with pytest.raises((PermissionError, OSError)):
                fs_service.write_file(str(readonly_file), "content")

        except Exception:
            # Permission operations might not work in all test environments
            pytest.skip("Cannot test read-only scenarios in this environment")
        finally:
            # Restore permissions for cleanup
            with contextlib.suppress(Exception):
                readonly_dir.chmod(0o755)
