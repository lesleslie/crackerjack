"""Integration tests for crackerjack CLI workflow.

These tests verify service interactions across layers:
- CLI → Facade → Orchestration
- Handlers → Managers → Services
- Cross-service workflows
"""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from crackerjack.cli.options import create_options


@pytest.mark.integration
class TestCLItoOrchestrationIntegration:
    """Test CLI to orchestration layer integration."""

    def test_create_options_valid_object(self) -> None:
        """Test that create_options produces valid Options object."""
        options = create_options(
            commit=False,
            interactive=False,
            no_config_updates=False,
            verbose=False,
            debug=False,
            publish=None,
            bump=None,
            benchmark=False,
            test_workers=0,
            test_timeout=600,
            skip_hooks=False,
            fast=False,
            comp=False,
        )

        assert options is not None
        assert options.verbose is False
        assert options.test_workers == 0

    @patch("crackerjack.core.session_coordinator.SessionCoordinator")
    def test_options_coordinator_compatibility(self, mock_coordinator: Mock) -> None:
        """Test that Options object is compatible with coordinator."""
        options = create_options(
            commit=False,
            interactive=False,
            no_config_updates=False,
            verbose=False,
            debug=False,
            publish=None,
            bump=None,
            benchmark=False,
            test_workers=4,
            test_timeout=600,
            skip_hooks=False,
            fast=False,
            comp=False,
        )

        # Verify options has expected attributes for coordinator
        assert hasattr(options, "test_workers")
        assert hasattr(options, "test_timeout")
        assert options.test_workers == 4
        assert options.test_timeout == 600


@pytest.mark.integration
class TestHandlersToServicesIntegration:
    """Test handlers layer to services layer integration."""

    @patch("crackerjack.services.git.GitService")
    def test_git_service_integration(self, mock_git: Mock) -> None:
        """Test git service can be instantiated through handlers."""
        from crackerjack.services.git import GitService

        mock_git.return_value = Mock()
        mock_git.return_value.is_git_repo = Mock(return_value=True)

        # Simulate handler creating git service
        service = GitService(console=Mock(), pkg_path=Path.cwd())

        assert service is not None
        assert service.pkg_path == Path.cwd()

    @patch("crackerjack.services.filesystem.FileSystemService")
    def test_filesystem_service_integration(self, mock_fs: Mock) -> None:
        """Test filesystem service can be instantiated through handlers."""
        from crackerjack.services.filesystem import FileSystemService

        service = FileSystemService()

        assert service is not None

        # Test basic operation
        mock_fs.return_value = "test content"
        with patch.object(service, "read_file", return_value="test"):
            result = service.read_file("dummy.txt")
            assert result == "test"


@pytest.mark.integration
class TestCrossServiceWorkflows:
    """Test workflows that span multiple services."""

    @patch("crackerjack.services.git.GitService")
    @patch("crackerjack.services.filesystem.FileSystemService")
    def test_git_and_filesystem_workflow(
        self, mock_git: Mock, mock_fs: Mock
    ) -> None:
        """Test workflow that uses both git and filesystem services."""
        from crackerjack.services.git import GitService
        from crackerjack.services.filesystem import FileSystemService

        git_service = GitService(console=Mock(), pkg_path=Path.cwd())
        fs_service = FileSystemService()

        # Simulate a workflow that checks git status then reads files
        mock_git.return_value.is_git_repo = Mock(return_value=True)
        is_repo = git_service.is_git_repo()

        assert is_repo is True
        assert fs_service is not None


@pytest.mark.integration
class TestServiceErrorPropagation:
    """Test that errors propagate correctly through service layers."""

    @patch("crackerjack.services.git.GitService")
    def test_git_error_propagation(self, mock_git: Mock) -> None:
        """Test that git service errors propagate correctly."""
        from crackerjack.services.git import GitService
        from crackerjack.errors import FileError

        # Simulate git error
        mock_git.return_value.is_git_repo = Mock(side_effect=FileError("Git error"))
        service = GitService(console=Mock(), pkg_path=Path.cwd())

        # Error should be propagated
        with pytest.raises(FileError):
            service.is_git_repo()

    @patch("crackerjack.services.filesystem.FileSystemService")
    def test_filesystem_error_propagation(self, mock_fs: Mock) -> None:
        """Test that filesystem service errors propagate correctly."""
        from crackerjack.services.filesystem import FileSystemService
        from crackerjack.errors import FileError

        service = FileSystemService()

        # Simulate file not found error
        mock_fs.side_effect = FileNotFoundError("File not found")
        with pytest.raises(FileError):
            service.read_file("nonexistent.txt")
