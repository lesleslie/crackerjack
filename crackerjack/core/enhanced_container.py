import inspect
import threading
import typing as t
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, TypeVar

from rich.console import Console

from crackerjack.models.protocols import (
    ConfigMergeServiceProtocol,
    ConfigurationServiceProtocol,
    CoverageRatchetProtocol,
    FileSystemInterface,
    GitInterface,
    HookManager,
    InitializationServiceProtocol,
    PublishManager,
    SecurityServiceProtocol,
    TestManagerProtocol,
    UnifiedConfigurationServiceProtocol,
)
from crackerjack.services.logging import get_logger

T = TypeVar("T")
FactoryFunc = Callable[..., T]


class ServiceLifetime(Enum):
    SINGLETON = "singleton"
    TRANSIENT = "transient"
    SCOPED = "scoped"


@dataclass
class ServiceDescriptor:
    interface: type
    implementation: type | None = None
    factory: Callable[..., Any] | None = None
    lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT
    instance: Any | None = None
    created_count: int = 0
    dependencies: list[type] = field(default_factory=list)

    def __post_init__(self):
        if self.implementation is self.factory is self.instance is None:
            msg = "Must provide either implementation, factory, or instance"
            raise ValueError(msg)


class ServiceScope:
    def __init__(self, name: str) -> None:
        self.name = name
        self._instances: dict[str, Any] = {}
        self._lock = threading.Lock()
        self.logger = get_logger("crackerjack.container.scope")

    def get_instance(self, key: str) -> Any | None:
        with self._lock:
            return self._instances.get(key)

    def set_instance(self, key: str, instance: Any) -> None:
        with self._lock:
            self._instances[key] = instance
            self.logger.debug("Scoped instance created", scope=self.name, service=key)

    def dispose(self) -> None:
        with self._lock:
            for key, instance in self._instances.items():
                if hasattr(instance, "dispose"):
                    try:
                        instance.dispose()
                    except Exception as e:
                        self.logger.exception(
                            "Error disposing service",
                            service=key,
                            error=str(e),
                        )

            self._instances.clear()
            self.logger.info("Service scope disposed", scope=self.name)


class DependencyResolver:
    def __init__(self, container: "EnhancedDependencyContainer") -> None:
        self.container = container
        self.logger = get_logger("crackerjack.container.resolver")

    def create_instance(
        self,
        descriptor: ServiceDescriptor,
        scope: ServiceScope | None = None,
    ) -> Any:
        if descriptor.instance is not None:
            return descriptor.instance

        if descriptor.factory is not None:
            return self._create_from_factory(descriptor.factory)

        if descriptor.implementation is not None:
            return self._create_from_class(descriptor.implementation)

        msg = f"Cannot create instance for {descriptor.interface}"
        raise ValueError(msg)

    def _create_from_factory(self, factory: Callable[..., Any]) -> Any:
        sig = inspect.signature(factory)
        kwargs = {}

        for param_name, param in sig.parameters.items():
            if param.annotation != inspect.Parameter.empty:
                try:
                    dependency = self.container.get(param.annotation)
                    kwargs[param_name] = dependency
                except Exception as e:
                    if param.default == inspect.Parameter.empty:
                        self.logger.warning(
                            "Could not inject dependency",
                            parameter=param_name,
                            type=param.annotation,
                            error=str(e),
                        )
                    else:
                        self.logger.debug(
                            "Could not inject optional dependency, using default",
                            parameter=param_name,
                            type=param.annotation,
                            default=param.default,
                        )

        return factory(**kwargs)

    def _create_from_class(self, implementation: type) -> Any:
        try:
            kwargs = self._build_constructor_kwargs(implementation)
            return self._instantiate_with_logging(implementation, kwargs)
        except Exception as e:
            self.logger.exception(
                "Failed to create instance",
                implementation_class=implementation.__name__,
                error=str(e),
            )
            raise

    def _build_constructor_kwargs(self, implementation: type) -> dict[str, Any]:
        init_sig = inspect.signature(implementation.__init__)
        kwargs: dict[str, Any] = {}

        for param_name, param in init_sig.parameters.items():
            if param_name == "self":
                continue

            if param.annotation != inspect.Parameter.empty:
                self._resolve_parameter_dependency(
                    kwargs, param_name, param, implementation.__name__
                )

        return kwargs

    def _resolve_parameter_dependency(
        self,
        kwargs: dict[str, Any],
        param_name: str,
        param: inspect.Parameter,
        class_name: str,
    ) -> None:
        try:
            dependency = self.container.get(param.annotation)
            kwargs[param_name] = dependency
        except Exception as e:
            if param.default == inspect.Parameter.empty:
                self.logger.exception(
                    "Required dependency not available",
                    implementation_class=class_name,
                    parameter=param_name,
                    type=param.annotation,
                    error=str(e),
                )
                raise
            self.logger.debug(
                "Optional dependency not available, using default",
                parameter=param_name,
                type=param.annotation,
            )

    def _instantiate_with_logging(
        self, implementation: type, kwargs: dict[str, Any]
    ) -> Any:
        instance = implementation(**kwargs)
        self.logger.debug(
            "Instance created with DI",
            implementation_class=implementation.__name__,
        )
        return instance


class EnhancedDependencyContainer:
    def __init__(self, name: str = "default") -> None:
        self.name = name
        self._services: dict[str, ServiceDescriptor] = {}
        self._singletons: dict[str, Any] = {}
        self._lock = threading.Lock()
        self._current_scope: ServiceScope | None = None
        self.resolver = DependencyResolver(self)
        self.logger = get_logger("crackerjack.container")

    def register_singleton(
        self,
        interface: type,
        implementation: type | None = None,
        factory: Callable[..., Any] | None = None,
        instance: Any | None = None,
    ) -> "EnhancedDependencyContainer":
        key = self._get_service_key(interface)

        descriptor = ServiceDescriptor(
            interface=interface,
            implementation=implementation,
            factory=factory,
            instance=instance,
            lifetime=ServiceLifetime.SINGLETON,
        )

        with self._lock:
            self._services[key] = descriptor

        self.logger.debug("Singleton registered", interface=interface.__name__)
        return self

    def register_transient(
        self,
        interface: type,
        implementation: type | None = None,
        factory: Callable[..., Any] | None = None,
    ) -> "EnhancedDependencyContainer":
        key = self._get_service_key(interface)

        descriptor = ServiceDescriptor(
            interface=interface,
            implementation=implementation,
            factory=factory,
            lifetime=ServiceLifetime.TRANSIENT,
        )

        with self._lock:
            self._services[key] = descriptor

        self.logger.debug("Transient registered", interface=interface.__name__)
        return self

    def register_scoped(
        self,
        interface: type,
        implementation: type | None = None,
        factory: Callable[..., Any] | None = None,
    ) -> "EnhancedDependencyContainer":
        key = self._get_service_key(interface)

        descriptor = ServiceDescriptor(
            interface=interface,
            implementation=implementation,
            factory=factory,
            lifetime=ServiceLifetime.SCOPED,
        )

        with self._lock:
            self._services[key] = descriptor

        self.logger.debug("Scoped registered", interface=interface.__name__)
        return self

    def get(self, interface: type, scope: ServiceScope | None = None) -> Any:
        key = self._get_service_key(interface)

        with self._lock:
            if key not in self._services:
                msg = f"Service {interface.__name__} not registered"
                raise ValueError(msg)

            descriptor = self._services[key]

        return self._create_service_instance(descriptor, scope or self._current_scope)

    def get_optional(self, interface: type, default: Any = None) -> Any:
        try:
            return self.get(interface)
        except ValueError:
            return default

    def is_registered(self, interface: type) -> bool:
        key = self._get_service_key(interface)
        return key in self._services

    def create_scope(self, name: str = "scope") -> ServiceScope:
        return ServiceScope(name)

    def set_current_scope(self, scope: ServiceScope | None) -> None:
        self._current_scope = scope

    def get_service_info(self) -> dict[str, Any]:
        info = {}

        with self._lock:
            for key, descriptor in self._services.items():
                info[key] = {
                    "interface": descriptor.interface.__name__,
                    "implementation": descriptor.implementation.__name__
                    if descriptor.implementation
                    else None,
                    "lifetime": descriptor.lifetime.value,
                    "created_count": descriptor.created_count,
                    "has_instance": descriptor.instance is not None,
                }

        return info

    def dispose(self) -> None:
        with self._lock:
            for key, instance in self._singletons.items():
                if hasattr(instance, "dispose"):
                    try:
                        instance.dispose()
                    except Exception as e:
                        self.logger.exception(
                            "Error disposing singleton",
                            service=key,
                            error=str(e),
                        )

            self._singletons.clear()

            if self._current_scope:
                self._current_scope.dispose()
                self._current_scope = None

        self.logger.info("Container disposed", name=self.name)

    def _create_service_instance(
        self,
        descriptor: ServiceDescriptor,
        scope: ServiceScope | None = None,
    ) -> Any:
        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            return self._get_or_create_singleton(descriptor)
        if descriptor.lifetime == ServiceLifetime.SCOPED:
            return self._get_or_create_scoped(descriptor, scope)

        return self._create_transient_instance(descriptor)

    def _get_or_create_singleton(self, descriptor: ServiceDescriptor) -> Any:
        key = self._get_service_key(descriptor.interface)

        if key in self._singletons:
            return self._singletons[key]

        instance = self.resolver.create_instance(descriptor)
        self._singletons[key] = instance
        descriptor.created_count += 1

        self.logger.debug("Singleton created", interface=descriptor.interface.__name__)
        return instance

    def _get_or_create_scoped(
        self,
        descriptor: ServiceDescriptor,
        scope: ServiceScope | None,
    ) -> Any:
        if scope is None:
            msg = f"Scoped service {descriptor.interface.__name__} requires an active scope"
            raise ValueError(
                msg,
            )

        key = self._get_service_key(descriptor.interface)
        instance = scope.get_instance(key)

        if instance is None:
            instance = self.resolver.create_instance(descriptor, scope)
            scope.set_instance(key, instance)
            descriptor.created_count += 1

        return instance

    def _create_transient_instance(self, descriptor: ServiceDescriptor) -> Any:
        instance = self.resolver.create_instance(descriptor)
        descriptor.created_count += 1
        return instance

    def _get_service_key(self, interface: type) -> str:
        return f"{interface.__module__}.{interface.__name__}"

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        _exc_tb: t.Any,
    ) -> None:
        self.dispose()


class ServiceCollectionBuilder:
    def __init__(self, container: EnhancedDependencyContainer) -> None:
        self.container = container
        self.console: Console | None = None
        self.pkg_path: Path | None = None
        self.dry_run: bool = False
        self.verbose: bool = False

    def with_console(self, console: Console) -> "ServiceCollectionBuilder":
        self.console = console
        return self

    def with_package_path(self, pkg_path: Path) -> "ServiceCollectionBuilder":
        self.pkg_path = pkg_path
        return self

    def with_dry_run(self, dry_run: bool) -> "ServiceCollectionBuilder":
        self.dry_run = dry_run
        return self

    def with_verbose(self, verbose: bool) -> "ServiceCollectionBuilder":
        self.verbose = verbose
        return self

    def add_core_services(self) -> "ServiceCollectionBuilder":
        console = self.console or Console(force_terminal=True)
        pkg_path = self.pkg_path or Path.cwd()

        from crackerjack.services.enhanced_filesystem import EnhancedFileSystemService

        self.container.register_singleton(
            FileSystemInterface,
            factory=EnhancedFileSystemService,
        )

        from crackerjack.services.git import GitService

        self.container.register_transient(
            GitInterface,
            factory=lambda: GitService(console=console, pkg_path=pkg_path),
        )

        from crackerjack.managers.hook_manager import HookManagerImpl

        self.container.register_transient(
            HookManager,
            factory=lambda: HookManagerImpl(
                console=console, pkg_path=pkg_path, verbose=self.verbose
            ),
        )

        from crackerjack.managers.test_manager import TestManagementImpl

        self.container.register_transient(
            TestManagerProtocol,
            factory=lambda: TestManagementImpl(console=console, pkg_path=pkg_path),
        )

        from crackerjack.managers.publish_manager import PublishManagerImpl

        # Use factory without parameters to trigger @depends.inject decorator
        # The decorator will inject all dependencies from the DI container
        self.container.register_transient(
            PublishManager,
            factory=PublishManagerImpl,
        )

        return self

    def add_service_protocols(self) -> "ServiceCollectionBuilder":
        console = self.console or Console(force_terminal=True)
        pkg_path = self.pkg_path or Path.cwd()

        def create_coverage_ratchet() -> CoverageRatchetProtocol:
            from crackerjack.services.coverage_ratchet import CoverageRatchetService

            return CoverageRatchetService(pkg_path, console)

        self.container.register_transient(
            CoverageRatchetProtocol,
            factory=create_coverage_ratchet,
        )

        def create_configuration_service() -> ConfigurationServiceProtocol:
            from crackerjack.services.config import ConfigurationService

            return ConfigurationService(console=console, pkg_path=pkg_path)

        self.container.register_transient(
            ConfigurationServiceProtocol,
            factory=create_configuration_service,
        )

        def create_security_service() -> SecurityServiceProtocol:
            from crackerjack.services.security import SecurityService

            return SecurityService()

        self.container.register_transient(
            SecurityServiceProtocol,
            factory=create_security_service,
        )

        def create_initialization_service() -> InitializationServiceProtocol:
            from crackerjack.services.filesystem import FileSystemService
            from crackerjack.services.git import GitService
            from crackerjack.services.initialization import InitializationService

            filesystem = FileSystemService()
            git_service = GitService(console, pkg_path)
            service = InitializationService(console, filesystem, git_service, pkg_path)
            # Cast to protocol type to ensure correct typing
            return t.cast(InitializationServiceProtocol, service)

        self.container.register_transient(
            InitializationServiceProtocol,
            factory=create_initialization_service,
        )

        return self

    def add_configuration_services(self) -> "ServiceCollectionBuilder":
        console = self.console or Console(force_terminal=True)
        pkg_path = self.pkg_path or Path.cwd()

        from crackerjack.services.unified_config import UnifiedConfigurationService

        self.container.register_singleton(
            UnifiedConfigurationService,
            factory=lambda: UnifiedConfigurationService(console, pkg_path),
        )

        self.container.register_singleton(
            UnifiedConfigurationServiceProtocol,
            factory=lambda: self.container.get(UnifiedConfigurationService),
        )

        from crackerjack.services.config_merge import ConfigMergeService

        def create_config_merge_service() -> ConfigMergeService:
            filesystem = self.container.get(FileSystemInterface)
            git_service = self.container.get(GitInterface)
            return ConfigMergeService(
                console=console,
                filesystem=filesystem,
                git_service=git_service,
            )

        self.container.register_transient(
            ConfigMergeServiceProtocol,
            factory=create_config_merge_service,
        )

        return self

    def build(self) -> EnhancedDependencyContainer:
        return self.container


def create_enhanced_container(
    console: Console | None = None,
    pkg_path: Path | None = None,
    dry_run: bool = False,
    verbose: bool = False,
    name: str = "crackerjack",
) -> EnhancedDependencyContainer:
    container = EnhancedDependencyContainer(name)

    builder = ServiceCollectionBuilder(container)
    builder.with_console(console or Console(force_terminal=True))
    builder.with_package_path(pkg_path or Path.cwd())
    builder.with_dry_run(dry_run)
    builder.with_verbose(verbose)

    builder.add_core_services()
    builder.add_configuration_services()

    return builder.build()
