import pytest
from pathlib import Path

from crackerjack.core.container import DependencyContainer, create_container
from crackerjack.models.protocols import (
    ConsoleInterface,
    FileSystemInterface,
    GitInterface,
    HookManager,
    PublishManager,
    TestManagerProtocol,
)


class MockConsole(ConsoleInterface):
    def print(self, *args, **kwargs):
        pass

    def print_error(self, *args, **kwargs):
        pass

    def print_success(self, *args, **kwargs):
        pass

    def print_warning(self, *args, **kwargs):
        pass


def test_dependency_container_initialization():
    """Test that DependencyContainer initializes with empty dictionaries."""
    container = DependencyContainer()
    assert container._services == {}
    assert container._singletons == {}


def test_register_singleton():
    """Test registering a singleton service."""
    container = DependencyContainer()

    class TestService:
        pass

    container.register_singleton(str, TestService())

    assert "str" in container._singletons


def test_register_transient():
    """Test registering a transient service."""
    container = DependencyContainer()

    def create_service():
        return "test"

    container.register_transient(str, create_service)

    assert "str" in container._services
    assert container._services["str"] == create_service


def test_get_singleton_service():
    """Test retrieving a singleton service."""
    container = DependencyContainer()

    service_instance = "test_singleton"
    container.register_singleton(str, service_instance)

    retrieved = container.get(str)
    assert retrieved == service_instance


def test_get_transient_service():
    """Test retrieving a transient service."""
    container = DependencyContainer()

    def create_service():
        return "transient_service"

    container.register_transient(str, create_service)

    retrieved = container.get(str)
    assert retrieved == "transient_service"


def test_get_nonexistent_service():
    """Test that getting a nonexistent service raises ValueError."""
    container = DependencyContainer()

    with pytest.raises(ValueError, match="Service str not registered"):
        container.get(str)


def test_create_default_container():
    """Test creating a default container with all services."""
    container = DependencyContainer()
    mock_console = MockConsole()
    pkg_path = Path(__file__).parent

    result = container.create_default_container(
        console=mock_console,
        pkg_path=pkg_path,
        dry_run=False,
        verbose=False
    )

    # Verify that the container returns instances of registered services
    assert isinstance(result, DependencyContainer)

    # Check that services were registered
    fs_service = result.get(FileSystemInterface)
    assert fs_service is not None

    git_service = result.get(GitInterface)
    assert git_service is not None

    hook_manager = result.get(HookManager)
    assert hook_manager is not None

    test_manager = result.get(TestManagerProtocol)
    assert test_manager is not None

    publish_manager = result.get(PublishManager)
    assert publish_manager is not None


def test_create_container_function():
    """Test the create_container function."""
    container = create_container()

    # Verify that the container has the expected services
    fs_service = container.get(FileSystemInterface)
    assert fs_service is not None

    # Test with custom parameters
    mock_console = MockConsole()
    pkg_path = Path(__file__).parent
    container_with_params = create_container(
        console=mock_console,
        pkg_path=pkg_path,
        dry_run=True,
        verbose=True
    )

    # Verify that the container was created successfully
    assert container_with_params is not None
