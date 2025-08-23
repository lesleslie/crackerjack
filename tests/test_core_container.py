"""Strategic test coverage for core/container.py - Dependency injection system."""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
from rich.console import Console

from crackerjack.core.container import DependencyContainer, create_container
from crackerjack.models.protocols import (
    FileSystemInterface,
    GitInterface,
    HookManager,
    PublishManager,
    TestManagerProtocol,
)


class TestDependencyContainer:
    """Test dependency injection container functionality."""

    def test_container_initialization(self):
        """Test basic container initialization."""
        container = DependencyContainer()
        
        assert container._services == {}
        assert container._singletons == {}

    def test_register_singleton(self):
        """Test singleton registration and retrieval."""
        container = DependencyContainer()
        mock_service = Mock()
        
        container.register_singleton(FileSystemInterface, mock_service)
        
        assert container.get(FileSystemInterface) is mock_service
        # Second call should return same instance
        assert container.get(FileSystemInterface) is mock_service

    def test_register_transient(self):
        """Test transient service registration."""
        container = DependencyContainer()
        
        def mock_factory():
            return Mock()
        
        container.register_transient(GitInterface, mock_factory)
        
        service1 = container.get(GitInterface)
        service2 = container.get(GitInterface)
        
        # Should get different instances each time
        assert service1 is not service2

    def test_get_unregistered_service_raises_error(self):
        """Test that getting unregistered service raises ValueError."""
        container = DependencyContainer()
        
        with pytest.raises(ValueError, match="Service HookManager not registered"):
            container.get(HookManager)

    def test_singleton_takes_precedence_over_transient(self):
        """Test that singleton registration overrides transient."""
        container = DependencyContainer()
        singleton_service = Mock()
        transient_factory = Mock(return_value=Mock())
        
        container.register_transient(FileSystemInterface, transient_factory)
        container.register_singleton(FileSystemInterface, singleton_service)
        
        result = container.get(FileSystemInterface)
        
        assert result is singleton_service
        assert transient_factory.call_count == 0

    @patch('crackerjack.services.filesystem.FileSystemService')
    @patch('crackerjack.services.git.GitService')
    @patch('crackerjack.managers.hook_manager.HookManagerImpl')
    @patch('crackerjack.managers.test_manager.TestManagementImpl')
    @patch('crackerjack.managers.publish_manager.PublishManagerImpl')
    def test_create_default_container(
        self,
        mock_publish_manager,
        mock_test_manager,
        mock_hook_manager,
        mock_git_service,
        mock_filesystem_service,
    ):
        """Test default container creation with all dependencies."""
        container = DependencyContainer()
        console = Mock(spec=Console)
        pkg_path = Path("/test/path")
        
        result = container.create_default_container(
            console=console, pkg_path=pkg_path, dry_run=True
        )
        
        assert result is container
        
        # Test that all services can be retrieved
        filesystem = container.get(FileSystemInterface)
        git = container.get(GitInterface)
        hooks = container.get(HookManager)
        tests = container.get(TestManagerProtocol)
        publish = container.get(PublishManager)
        
        assert filesystem is not None
        assert git is not None
        assert hooks is not None
        assert tests is not None
        assert publish is not None

    def test_create_default_container_with_defaults(self):
        """Test default container creation with default parameters."""
        container = DependencyContainer()
        
        with patch.multiple(
            'crackerjack.services.filesystem',
            FileSystemService=Mock(),
        ), patch.multiple(
            'crackerjack.services.git',
            GitService=Mock(),
        ), patch.multiple(
            'crackerjack.managers.hook_manager',
            HookManagerImpl=Mock(),
        ), patch.multiple(
            'crackerjack.managers.test_manager',
            TestManagementImpl=Mock(),
        ), patch.multiple(
            'crackerjack.managers.publish_manager',
            PublishManagerImpl=Mock(),
        ):
            result = container.create_default_container()
            
            assert result is container

    @patch('crackerjack.services.filesystem.FileSystemService')
    @patch('crackerjack.services.git.GitService')
    @patch('crackerjack.managers.hook_manager.HookManagerImpl')
    @patch('crackerjack.managers.test_manager.TestManagementImpl')
    @patch('crackerjack.managers.publish_manager.PublishManagerImpl')
    def test_transient_services_get_new_instances(
        self,
        mock_publish_manager,
        mock_test_manager,
        mock_hook_manager,
        mock_git_service,
        mock_filesystem_service,
    ):
        """Test that transient services create new instances each time."""
        # Create different instances for each call
        mock_git_service.side_effect = lambda **kwargs: Mock()
        mock_hook_manager.side_effect = lambda **kwargs: Mock()
        
        container = DependencyContainer()
        container.create_default_container()
        
        # Get services multiple times
        git1 = container.get(GitInterface)
        git2 = container.get(GitInterface)
        
        hooks1 = container.get(HookManager)
        hooks2 = container.get(HookManager)
        
        # Should be different instances for transient services
        assert git1 is not git2
        assert hooks1 is not hooks2

    @patch('crackerjack.services.filesystem.FileSystemService')
    def test_singleton_services_reuse_instances(self, mock_filesystem_service):
        """Test that singleton services reuse the same instance."""
        container = DependencyContainer()
        container.create_default_container()
        
        # Get filesystem service multiple times
        fs1 = container.get(FileSystemInterface)
        fs2 = container.get(FileSystemInterface)
        
        # Should be same instance for singleton
        assert fs1 is fs2


class TestCreateContainerFunction:
    """Test the create_container factory function."""

    @patch('crackerjack.core.container.DependencyContainer')
    def test_create_container_function(self, mock_container_class):
        """Test create_container factory function."""
        mock_container = Mock()
        mock_container_class.return_value = mock_container
        mock_container.create_default_container.return_value = mock_container
        
        console = Mock(spec=Console)
        pkg_path = Path("/test")
        
        result = create_container(console=console, pkg_path=pkg_path, dry_run=True)
        
        mock_container_class.assert_called_once()
        mock_container.create_default_container.assert_called_once_with(
            console=console, pkg_path=pkg_path, dry_run=True
        )
        assert result is mock_container

    @patch('crackerjack.core.container.DependencyContainer')
    def test_create_container_with_defaults(self, mock_container_class):
        """Test create_container with default parameters."""
        mock_container = Mock()
        mock_container_class.return_value = mock_container
        mock_container.create_default_container.return_value = mock_container
        
        result = create_container()
        
        mock_container.create_default_container.assert_called_once_with(
            console=None, pkg_path=None, dry_run=False
        )
        assert result is mock_container


class TestContainerIntegration:
    """Integration tests for the dependency container."""

    def test_container_service_name_resolution(self):
        """Test that service names are resolved correctly."""
        container = DependencyContainer()
        mock_service = Mock()
        
        # Test interface name resolution
        container.register_singleton(FileSystemInterface, mock_service)
        
        # Should retrieve by interface name
        assert container.get(FileSystemInterface) is mock_service

    def test_factory_function_execution(self):
        """Test that factory functions are executed correctly."""
        container = DependencyContainer()
        call_count = 0
        
        def factory():
            nonlocal call_count
            call_count += 1
            return Mock(id=call_count)
        
        container.register_transient(GitInterface, factory)
        
        service1 = container.get(GitInterface)
        service2 = container.get(GitInterface)
        
        assert call_count == 2
        assert service1.id == 1
        assert service2.id == 2

    def test_mixed_registration_types(self):
        """Test container with both singleton and transient registrations."""
        container = DependencyContainer()
        
        singleton_service = Mock(type="singleton")
        transient_factory = Mock(return_value=Mock(type="transient"))
        
        container.register_singleton(FileSystemInterface, singleton_service)
        container.register_transient(GitInterface, transient_factory)
        
        # Both should work
        fs = container.get(FileSystemInterface)
        git = container.get(GitInterface)
        
        assert fs.type == "singleton"
        assert git.type == "transient"