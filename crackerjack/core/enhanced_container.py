"""Enhanced dependency injection container with lifecycle management."""

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
    FileSystemInterface,
    GitInterface,
    HookManager,
    PublishManager,
    TestManagerProtocol,
)
from crackerjack.services.logging import get_logger

T = TypeVar("T")
FactoryFunc = Callable[..., T]


class ServiceLifetime(Enum):
    """Service lifetime enumeration."""

    SINGLETON = "singleton"
    TRANSIENT = "transient"
    SCOPED = "scoped"


@dataclass
class ServiceDescriptor:
    """Describes how to create a service instance."""

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
    """Represents a service scope for scoped services."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._instances: dict[str, Any] = {}
        self._lock = threading.Lock()
        self.logger = get_logger("crackerjack.container.scope")

    def get_instance(self, key: str) -> Any | None:
        """Get scoped instance."""
        with self._lock:
            return self._instances.get(key)

    def set_instance(self, key: str, instance: Any) -> None:
        """Set scoped instance."""
        with self._lock:
            self._instances[key] = instance
            self.logger.debug("Scoped instance created", scope=self.name, service=key)

    def dispose(self) -> None:
        """Dispose of all scoped instances."""
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
    """Resolves service dependencies through constructor injection."""

    def __init__(self, container: "EnhancedDependencyContainer") -> None:
        self.container = container
        self.logger = get_logger("crackerjack.container.resolver")

    def create_instance(
        self,
        descriptor: ServiceDescriptor,
        scope: ServiceScope | None = None,
    ) -> Any:
        """Create service instance with dependency injection."""
        if descriptor.instance is not None:
            return descriptor.instance

        if descriptor.factory is not None:
            return self._create_from_factory(descriptor.factory)

        if descriptor.implementation is not None:
            return self._create_from_class(descriptor.implementation)

        msg = f"Cannot create instance for {descriptor.interface}"
        raise ValueError(msg)

    def _create_from_factory(self, factory: Callable[..., Any]) -> Any:
        """Create instance using factory function."""
        sig = inspect.signature(factory)
        kwargs = {}

        for param_name, param in sig.parameters.items():
            if param.annotation != inspect.Parameter.empty:
                try:
                    dependency = self.container.get(param.annotation)
                    kwargs[param_name] = dependency
                except Exception as e:
                    self.logger.warning(
                        "Could not inject dependency",
                        parameter=param_name,
                        type=param.annotation,
                        error=str(e),
                    )

        return factory(**kwargs)

    def _create_from_class(self, implementation: type) -> Any:
        """Create instance using class constructor with dependency injection."""
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
        """Build constructor kwargs by resolving dependencies."""
        init_sig = inspect.signature(implementation.__init__)
        kwargs = {}

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
        """Resolve a single parameter dependency."""
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
        """Create instance and log the creation."""
        instance = implementation(**kwargs)
        self.logger.debug(
            "Instance created with DI",
            implementation_class=implementation.__name__,
        )
        return instance


class EnhancedDependencyContainer:
    """Enhanced dependency injection container with lifecycle management."""

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
        """Register a singleton service."""
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
        """Register a transient service."""
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
        """Register a scoped service."""
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
        """Get service instance."""
        key = self._get_service_key(interface)

        with self._lock:
            if key not in self._services:
                msg = f"Service {interface.__name__} not registered"
                raise ValueError(msg)

            descriptor = self._services[key]

        return self._create_service_instance(descriptor, scope or self._current_scope)

    def get_optional(self, interface: type, default: Any = None) -> Any:
        """Get service instance or return default if not registered."""
        try:
            return self.get(interface)
        except ValueError:
            return default

    def is_registered(self, interface: type) -> bool:
        """Check if service is registered."""
        key = self._get_service_key(interface)
        return key in self._services

    def create_scope(self, name: str = "scope") -> ServiceScope:
        """Create a new service scope."""
        return ServiceScope(name)

    def set_current_scope(self, scope: ServiceScope | None) -> None:
        """Set the current service scope."""
        self._current_scope = scope

    def get_service_info(self) -> dict[str, Any]:
        """Get information about registered services."""
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
        """Dispose of container and all singletons."""
        with self._lock:
            # Dispose singletons
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

            # Dispose current scope
            if self._current_scope:
                self._current_scope.dispose()
                self._current_scope = None

        self.logger.info("Container disposed", name=self.name)

    def _create_service_instance(
        self,
        descriptor: ServiceDescriptor,
        scope: ServiceScope | None = None,
    ) -> Any:
        """Create service instance based on lifetime."""
        if descriptor.lifetime == ServiceLifetime.SINGLETON:
            return self._get_or_create_singleton(descriptor)
        if descriptor.lifetime == ServiceLifetime.SCOPED:
            return self._get_or_create_scoped(descriptor, scope)
        # Transient
        return self._create_transient_instance(descriptor)

    def _get_or_create_singleton(self, descriptor: ServiceDescriptor) -> Any:
        """Get or create singleton instance."""
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
        """Get or create scoped instance."""
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
        """Create new transient instance."""
        instance = self.resolver.create_instance(descriptor)
        descriptor.created_count += 1
        return instance

    def _get_service_key(self, interface: type) -> str:
        """Get service key from interface type."""
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
    """Builder pattern for configuring services."""

    def __init__(self, container: EnhancedDependencyContainer) -> None:
        self.container = container
        self.console: Console | None = None
        self.pkg_path: Path | None = None
        self.dry_run: bool = False

    def with_console(self, console: Console) -> "ServiceCollectionBuilder":
        """Set console for services that need it."""
        self.console = console
        return self

    def with_package_path(self, pkg_path: Path) -> "ServiceCollectionBuilder":
        """Set package path for services that need it."""
        self.pkg_path = pkg_path
        return self

    def with_dry_run(self, dry_run: bool) -> "ServiceCollectionBuilder":
        """Set dry run mode."""
        self.dry_run = dry_run
        return self

    def add_core_services(self) -> "ServiceCollectionBuilder":
        """Add core Crackerjack services."""
        console = self.console or Console(force_terminal=True)
        pkg_path = self.pkg_path or Path.cwd()

        # Enhanced filesystem service
        from crackerjack.services.enhanced_filesystem import EnhancedFileSystemService

        self.container.register_singleton(
            FileSystemInterface,
            factory=EnhancedFileSystemService,
        )

        # Git service
        from crackerjack.services.git import GitService

        self.container.register_transient(
            GitInterface,
            factory=lambda: GitService(console=console, pkg_path=pkg_path),
        )

        # Async hook manager
        from crackerjack.managers.async_hook_manager import AsyncHookManager

        self.container.register_scoped(
            HookManager,
            factory=lambda: AsyncHookManager(console=console, pkg_path=pkg_path),
        )

        # Test manager
        from crackerjack.managers.test_manager import TestManagementImpl

        self.container.register_transient(
            TestManagerProtocol,
            factory=lambda: TestManagementImpl(console=console, pkg_path=pkg_path),
        )

        # Publish manager
        from crackerjack.managers.publish_manager import PublishManagerImpl

        self.container.register_transient(
            PublishManager,
            factory=lambda: PublishManagerImpl(
                console=console,
                pkg_path=pkg_path,
                dry_run=self.dry_run,
            ),
        )

        return self

    def add_configuration_services(self) -> "ServiceCollectionBuilder":
        """Add configuration services."""
        console = self.console or Console(force_terminal=True)
        pkg_path = self.pkg_path or Path.cwd()

        # Unified configuration service
        from crackerjack.services.unified_config import UnifiedConfigurationService

        self.container.register_singleton(
            UnifiedConfigurationService,
            factory=lambda: UnifiedConfigurationService(console, pkg_path),
        )

        return self

    def build(self) -> EnhancedDependencyContainer:
        """Build the configured container."""
        return self.container


def create_enhanced_container(
    console: Console | None = None,
    pkg_path: Path | None = None,
    dry_run: bool = False,
    name: str = "crackerjack",
) -> EnhancedDependencyContainer:
    """Create enhanced dependency injection container with default services."""
    container = EnhancedDependencyContainer(name)

    builder = ServiceCollectionBuilder(container)
    builder.with_console(console or Console(force_terminal=True))
    builder.with_package_path(pkg_path or Path.cwd())
    builder.with_dry_run(dry_run)

    builder.add_core_services()
    builder.add_configuration_services()

    return builder.build()
