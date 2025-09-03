import threading
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from rich.console import Console

from crackerjack.core.enhanced_container import (
    DependencyResolver,
    EnhancedDependencyContainer,
    ServiceCollectionBuilder,
    ServiceDescriptor,
    ServiceLifetime,
    ServiceScope,
)
from crackerjack.models.protocols import (
    FileSystemInterface,
    GitInterface,
    HookManager,
    PublishManager,
    TestManagerProtocol,
)


class MockService:
    def __init__(self, value: str = "test") -> None:
        self.value = value
        self.disposed = False

    def dispose(self) -> None:
        self.disposed = True


class MockDependentService:
    def __init__(self, dependency: MockService) -> None:
        self.dependency = dependency


class TestServiceLifetime:
    def test_service_lifetime_values(self) -> None:
        assert ServiceLifetime.SINGLETON.value == "singleton"
        assert ServiceLifetime.TRANSIENT.value == "transient"
        assert ServiceLifetime.SCOPED.value == "scoped"

    def test_service_lifetime_enum_members(self) -> None:
        lifetimes = list(ServiceLifetime)
        assert len(lifetimes) == 3
        assert ServiceLifetime.SINGLETON in lifetimes
        assert ServiceLifetime.TRANSIENT in lifetimes
        assert ServiceLifetime.SCOPED in lifetimes


class TestServiceDescriptor:
    def test_descriptor_with_implementation(self) -> None:
        descriptor = ServiceDescriptor(
            interface=MockService,
            implementation=MockService,
            lifetime=ServiceLifetime.SINGLETON,
        )

        assert descriptor.interface == MockService
        assert descriptor.implementation == MockService
        assert descriptor.lifetime == ServiceLifetime.SINGLETON
        assert descriptor.factory is None
        assert descriptor.instance is None
        assert descriptor.created_count == 0
        assert descriptor.dependencies == []

    def test_descriptor_with_factory(self) -> None:
        def mock_factory():
            return MockService()

        descriptor = ServiceDescriptor(
            interface=MockService,
            factory=mock_factory,
            lifetime=ServiceLifetime.TRANSIENT,
        )

        assert descriptor.interface == MockService
        assert descriptor.implementation is None
        assert descriptor.factory == mock_factory
        assert descriptor.lifetime == ServiceLifetime.TRANSIENT

    def test_descriptor_with_instance(self) -> None:
        instance = MockService("test_instance")

        descriptor = ServiceDescriptor(
            interface=MockService,
            instance=instance,
            lifetime=ServiceLifetime.SINGLETON,
        )

        assert descriptor.interface == MockService
        assert descriptor.instance == instance
        assert descriptor.implementation is None
        assert descriptor.factory is None

    def test_descriptor_validation_error(self) -> None:
        with pytest.raises(
            ValueError,
            match="Must provide either implementation, factory, or instance",
        ):
            ServiceDescriptor(interface=MockService)

    def test_descriptor_with_dependencies(self) -> None:
        descriptor = ServiceDescriptor(
            interface=MockDependentService,
            implementation=MockDependentService,
            dependencies=[MockService],
            lifetime=ServiceLifetime.TRANSIENT,
        )

        assert descriptor.dependencies == [MockService]


class TestServiceScope:
    def test_scope_creation(self) -> None:
        scope = ServiceScope("test_scope")

        assert scope.name == "test_scope"
        assert scope._instances == {}

    def test_scope_instance_management(self) -> None:
        scope = ServiceScope("test")
        service = MockService("scoped")

        assert scope.get_instance("test_key") is None

        scope.set_instance("test_key", service)

        retrieved = scope.get_instance("test_key")
        assert retrieved is service
        assert retrieved.value == "scoped"

    def test_scope_dispose(self) -> None:
        scope = ServiceScope("test")
        service1 = MockService("service1")
        service2 = MockService("service2")

        scope.set_instance("key1", service1)
        scope.set_instance("key2", service2)

        scope.dispose()

        assert service1.disposed
        assert service2.disposed

        assert scope._instances == {}

    def test_scope_dispose_with_error(self) -> None:
        scope = ServiceScope("test")

        failing_service = Mock()
        failing_service.dispose.side_effect = Exception("Dispose error")

        scope.set_instance("failing", failing_service)

        scope.dispose()

        assert scope._instances == {}

    def test_scope_thread_safety(self) -> None:
        scope = ServiceScope("threaded")
        results = []

        def worker(worker_id) -> None:
            service = MockService(f"worker_{worker_id}")
            scope.set_instance(f"key_{worker_id}", service)
            retrieved = scope.get_instance(f"key_{worker_id}")
            results.append(retrieved.value)

        threads = []
        for i in range(5):
            thread = threading.Thread(target=worker, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        assert len(results) == 5
        assert "worker_0" in results
        assert "worker_4" in results


class TestDependencyResolver:
    @pytest.fixture
    def container(self):
        return EnhancedDependencyContainer("test")

    @pytest.fixture
    def resolver(self, container):
        return DependencyResolver(container)

    def test_resolver_creation(self, container) -> None:
        resolver = DependencyResolver(container)
        assert resolver.container is container

    def test_create_instance_with_instance(self, resolver) -> None:
        instance = MockService("pre_created")
        descriptor = ServiceDescriptor(interface=MockService, instance=instance)

        result = resolver.create_instance(descriptor)
        assert result is instance

    def test_create_instance_with_factory(self, resolver) -> None:
        def mock_factory():
            return MockService("from_factory")

        descriptor = ServiceDescriptor(interface=MockService, factory=mock_factory)

        result = resolver.create_instance(descriptor)
        assert isinstance(result, MockService)
        assert result.value == "from_factory"

    def test_create_instance_with_implementation(self, resolver) -> None:
        descriptor = ServiceDescriptor(
            interface=MockService,
            implementation=MockService,
        )

        result = resolver.create_instance(descriptor)
        assert isinstance(result, MockService)

    def test_create_instance_with_dependency_injection(
        self, resolver, container
    ) -> None:
        container.register_singleton(MockService, implementation=MockService)

        descriptor = ServiceDescriptor(
            interface=MockDependentService,
            implementation=MockDependentService,
        )

        result = resolver.create_instance(descriptor)
        assert isinstance(result, MockDependentService)
        assert isinstance(result.dependency, MockService)

    def test_create_instance_invalid_descriptor(self, resolver) -> None:
        descriptor = ServiceDescriptor.__new__(ServiceDescriptor)
        descriptor.interface = MockService
        descriptor.implementation = None
        descriptor.factory = None
        descriptor.instance = None
        descriptor.lifetime = ServiceLifetime.TRANSIENT
        descriptor.created_count = 0
        descriptor.dependencies = []

        with pytest.raises(ValueError, match="Cannot create instance"):
            resolver.create_instance(descriptor)

    def test_factory_with_dependencies(self, resolver, container) -> None:
        container.register_singleton(MockService, implementation=MockService)

        def factory_with_dep(dependency: MockService):
            return MockDependentService(dependency)

        descriptor = ServiceDescriptor(
            interface=MockDependentService,
            factory=factory_with_dep,
        )

        result = resolver.create_instance(descriptor)
        assert isinstance(result, MockDependentService)
        assert isinstance(result.dependency, MockService)


class TestEnhancedDependencyContainer:
    def test_container_creation(self) -> None:
        container = EnhancedDependencyContainer("test_container")

        assert container.name == "test_container"
        assert container._services == {}
        assert container._singletons == {}
        assert container._current_scope is None
        assert isinstance(container.resolver, DependencyResolver)

    def test_register_singleton(self) -> None:
        container = EnhancedDependencyContainer()

        result = container.register_singleton(MockService, implementation=MockService)

        assert result is container

        assert container.is_registered(MockService)

        key = container._get_service_key(MockService)
        descriptor = container._services[key]
        assert descriptor.interface == MockService
        assert descriptor.implementation == MockService
        assert descriptor.lifetime == ServiceLifetime.SINGLETON

    def test_register_transient(self) -> None:
        container = EnhancedDependencyContainer()

        def mock_factory():
            return MockService()

        result = container.register_transient(MockService, factory=mock_factory)

        assert result is container
        assert container.is_registered(MockService)

        key = container._get_service_key(MockService)
        descriptor = container._services[key]
        assert descriptor.factory == mock_factory
        assert descriptor.lifetime == ServiceLifetime.TRANSIENT

    def test_register_scoped(self) -> None:
        container = EnhancedDependencyContainer()

        result = container.register_scoped(MockService, implementation=MockService)

        assert result is container
        assert container.is_registered(MockService)

        key = container._get_service_key(MockService)
        descriptor = container._services[key]
        assert descriptor.lifetime == ServiceLifetime.SCOPED

    def test_get_singleton_service(self) -> None:
        container = EnhancedDependencyContainer()
        container.register_singleton(MockService, implementation=MockService)

        instance1 = container.get(MockService)
        assert isinstance(instance1, MockService)

        instance2 = container.get(MockService)
        assert instance1 is instance2

    def test_get_transient_service(self) -> None:
        container = EnhancedDependencyContainer()
        container.register_transient(MockService, implementation=MockService)

        instance1 = container.get(MockService)
        instance2 = container.get(MockService)

        assert isinstance(instance1, MockService)
        assert isinstance(instance2, MockService)
        assert instance1 is not instance2

    def test_get_scoped_service(self) -> None:
        container = EnhancedDependencyContainer()
        container.register_scoped(MockService, implementation=MockService)

        scope = container.create_scope("test_scope")

        instance1 = container.get(MockService, scope)
        assert isinstance(instance1, MockService)

        instance2 = container.get(MockService, scope)
        assert instance1 is instance2

    def test_get_scoped_service_without_scope(self) -> None:
        container = EnhancedDependencyContainer()
        container.register_scoped(MockService, implementation=MockService)

        with pytest.raises(ValueError, match="requires an active scope"):
            container.get(MockService)

    def test_get_unregistered_service(self) -> None:
        container = EnhancedDependencyContainer()

        with pytest.raises(ValueError, match="Service MockService not registered"):
            container.get(MockService)

    def test_get_optional_service(self) -> None:
        container = EnhancedDependencyContainer()

        result = container.get_optional(MockService, "default")
        assert result == "default"

        container.register_singleton(MockService, implementation=MockService)
        result = container.get_optional(MockService)
        assert isinstance(result, MockService)

    def test_is_registered(self) -> None:
        container = EnhancedDependencyContainer()

        assert not container.is_registered(MockService)

        container.register_singleton(MockService, implementation=MockService)
        assert container.is_registered(MockService)

    def test_create_scope(self) -> None:
        container = EnhancedDependencyContainer()

        scope = container.create_scope("custom_scope")
        assert isinstance(scope, ServiceScope)
        assert scope.name == "custom_scope"

    def test_set_current_scope(self) -> None:
        container = EnhancedDependencyContainer()
        scope = ServiceScope("test")

        container.set_current_scope(scope)
        assert container._current_scope is scope

        container.set_current_scope(None)
        assert container._current_scope is None

    def test_get_service_info(self) -> None:
        container = EnhancedDependencyContainer()
        container.register_singleton(MockService, implementation=MockService)
        container.register_transient(
            MockDependentService,
            implementation=MockDependentService,
        )

        info = container.get_service_info()

        assert len(info) == 2

        singleton_key = container._get_service_key(MockService)
        singleton_info = info[singleton_key]
        assert singleton_info["interface"] == "MockService"
        assert singleton_info["implementation"] == "MockService"
        assert singleton_info["lifetime"] == "singleton"
        assert singleton_info["created_count"] == 0
        assert singleton_info["has_instance"] is False

    def test_dispose_container(self) -> None:
        container = EnhancedDependencyContainer()
        container.register_singleton(MockService, implementation=MockService)

        instance = container.get(MockService)
        assert isinstance(instance, MockService)

        scope = ServiceScope("test")
        container.set_current_scope(scope)

        container.dispose()

        assert container._singletons == {}
        assert container._current_scope is None

    def test_context_manager(self) -> None:
        with EnhancedDependencyContainer("context_test") as container:
            container.register_singleton(MockService, implementation=MockService)
            assert container.name == "context_test"

    def test_service_key_generation(self) -> None:
        container = EnhancedDependencyContainer()

        key = container._get_service_key(MockService)
        expected = f"{MockService.__module__}.{MockService.__name__}"
        assert key == expected


class TestServiceCollectionBuilder:
    def test_builder_creation(self) -> None:
        container = EnhancedDependencyContainer()
        builder = ServiceCollectionBuilder(container)

        assert builder.container is container
        assert builder.console is None
        assert builder.pkg_path is None
        assert builder.dry_run is False

    def test_builder_configuration(self) -> None:
        container = EnhancedDependencyContainer()
        console = Console()
        pkg_path = Path("/ test")

        builder = ServiceCollectionBuilder(container)
        result = (
            builder.with_console(console).with_package_path(pkg_path).with_dry_run(True)
        )

        assert result is builder

        assert builder.console is console
        assert builder.pkg_path == pkg_path
        assert builder.dry_run is True

    def test_builder_build(self) -> None:
        container = EnhancedDependencyContainer()
        builder = ServiceCollectionBuilder(container)

        result = builder.build()
        assert result is container

    def test_add_core_services(self) -> None:
        container = EnhancedDependencyContainer()
        console = Console()
        pkg_path = Path("/ test")

        builder = ServiceCollectionBuilder(container)

        with (
            patch("crackerjack.services.enhanced_filesystem.EnhancedFileSystemService"),
            patch("crackerjack.services.git.GitService"),
            patch("crackerjack.managers.async_hook_manager.AsyncHookManager"),
            patch("crackerjack.managers.test_manager.TestManagementImpl"),
            patch("crackerjack.managers.publish_manager.PublishManagerImpl"),
        ):
            result = (
                builder.with_console(console)
                .with_package_path(pkg_path)
                .add_core_services()
            )

            assert result is builder

            assert container.is_registered(FileSystemInterface)
            assert container.is_registered(GitInterface)
            assert container.is_registered(HookManager)
            assert container.is_registered(TestManagerProtocol)
            assert container.is_registered(PublishManager)

    def test_add_configuration_services(self) -> None:
        container = EnhancedDependencyContainer()
        console = Console()
        pkg_path = Path("/ test")

        builder = ServiceCollectionBuilder(container)
        result = builder.with_console(console).with_package_path(pkg_path)

        assert result is builder
        assert builder.console is console
        assert builder.pkg_path == pkg_path


class TestCreateEnhancedContainer:
    def test_container_creation_basic(self) -> None:
        container = EnhancedDependencyContainer("test")
        assert isinstance(container, EnhancedDependencyContainer)
        assert container.name == "test"

    def test_service_collection_builder_basic(self) -> None:
        container = EnhancedDependencyContainer("builder_test")
        console = Console()
        pkg_path = Path("/ test")

        builder = ServiceCollectionBuilder(container)
        result = (
            builder.with_console(console).with_package_path(pkg_path).with_dry_run(True)
        )

        assert result is builder
        assert builder.container is container
        assert builder.console is console
        assert builder.pkg_path == pkg_path
        assert builder.dry_run is True

    def test_builder_build_returns_container(self) -> None:
        container = EnhancedDependencyContainer("build_test")
        builder = ServiceCollectionBuilder(container)

        result = builder.build()
        assert result is container


class TestIntegrationScenarios:
    def test_full_dependency_injection_scenario(self) -> None:
        container = EnhancedDependencyContainer("integration_test")

        container.register_singleton(MockService, implementation=MockService)
        container.register_transient(
            MockDependentService,
            implementation=MockDependentService,
        )

        dependent = container.get(MockDependentService)

        assert isinstance(dependent, MockDependentService)
        assert isinstance(dependent.dependency, MockService)

        dependent2 = container.get(MockDependentService)
        assert dependent.dependency is dependent2.dependency

    def test_scoped_service_lifecycle(self) -> None:
        container = EnhancedDependencyContainer("scope_test")
        container.register_scoped(MockService, implementation=MockService)

        scope1 = container.create_scope("scope1")
        scope2 = container.create_scope("scope2")

        service1a = container.get(MockService, scope1)
        service1b = container.get(MockService, scope1)
        service2 = container.get(MockService, scope2)

        assert service1a is service1b

        assert service1a is not service2

        scope1.dispose()
        scope2.dispose()

        assert service1a.disposed
        assert service2.disposed

    def test_builder_pattern_integration(self) -> None:
        console = Console()
        pkg_path = Path("/ test")

        container = (
            ServiceCollectionBuilder(EnhancedDependencyContainer("builder_test"))
            .with_console(console)
            .with_package_path(pkg_path)
            .with_dry_run(True)
            .build()
        )

        assert container.name == "builder_test"
        assert isinstance(container, EnhancedDependencyContainer)

        builder = ServiceCollectionBuilder(container)
        builder.with_console(console).with_package_path(pkg_path)
        assert builder.console is console
        assert builder.pkg_path == pkg_path
