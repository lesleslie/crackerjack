"""ACB Dependency Injection Configuration for Crackerjack.

This module centralizes all service registrations with ACB's depends system,
replacing the custom EnhancedDependencyContainer with ACB's lightweight DI.

Key Benefits:
- Eliminates 1,200+ lines of manual DI boilerplate
- Automatic dependency resolution
- Built-in singleton management
- Thread-safe by default
- Easier testing with mock injection

Usage:
    from crackerjack.core.acb_di_config import configure_acb_dependencies

    configure_acb_dependencies(
        console=console,
        pkg_path=pkg_path,
        dry_run=False,
        verbose=False,
    )

    # Services now available via depends.get()
    from acb.depends import depends
    filesystem = depends.get(FileSystemInterface)
"""

import typing as t
from pathlib import Path

from acb.depends import depends
from rich.console import Console

from crackerjack.data.repository import (
    DependencyMonitorRepository,
    HealthMetricsRepository,
    QualityBaselineRepository,
)
from crackerjack.events import (
    WorkflowEventBus,
    WorkflowEventTelemetry,
    register_default_subscribers,
)
from crackerjack.models.protocols import (
    ConfigMergeServiceProtocol,
    CoverageRatchetProtocol,
    FileSystemInterface,
    GitInterface,
    HookManager,
    PublishManager,
    SecurityServiceProtocol,
    TestManagerProtocol,
)


class ACBDependencyRegistry:
    """Registry for tracking ACB-registered dependencies.

    Enables proper cleanup in tests and provides introspection capabilities.
    """

    _registered_types: t.ClassVar[set[type]] = set()
    _registered_instances: t.ClassVar[dict[type, t.Any]] = {}

    @classmethod
    def register(cls, interface: type, instance: t.Any) -> None:
        """Register a dependency with ACB and track it."""
        depends.set(interface, instance)
        cls._registered_types.add(interface)
        cls._registered_instances[interface] = instance

    @classmethod
    def clear_all(cls) -> None:
        """Clear all registered dependencies.

        Useful for testing to ensure clean state between tests.
        """
        cls._registered_types.clear()
        cls._registered_instances.clear()
        # Note: ACB doesn't provide a clear_all() method
        # Dependencies will be garbage collected when instances are released

    @classmethod
    def get_registered_types(cls) -> set[type]:
        """Get all registered dependency types."""
        return cls._registered_types.copy()

    @classmethod
    def is_configured(cls) -> bool:
        """Check if dependencies have been configured."""
        return len(cls._registered_types) > 0


def configure_acb_dependencies(
    console: Console,
    pkg_path: Path,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """Configure ACB dependency injection for all crackerjack services.

    This function replaces the manual EnhancedDependencyContainer with ACB's
    automatic dependency injection system. All services are registered as
    singletons and can be retrieved via depends.get().

    Args:
        console: Rich console for output
        pkg_path: Package path for services
        dry_run: Dry run mode flag (unused currently, for future use)
        verbose: Verbose output flag (unused currently, for future use)

    Example:
        >>> from pathlib import Path
        >>> from rich.console import Console
        >>> from acb.depends import depends
        >>>
        >>> console = Console()
        >>> pkg_path = Path.cwd()
        >>> configure_acb_dependencies(console, pkg_path)
        >>>
        >>> # Retrieve services
        >>> filesystem = depends.get(FileSystemInterface)
        >>> git_service = depends.get(GitInterface)
    """
    # Register core dependencies
    ACBDependencyRegistry.register(Console, console)

    # Create a custom type for package path to avoid conflicts with generic Path
    class PackagePath(Path):
        """Type wrapper for package path to enable DI."""

        pass

    pkg_path_typed = PackagePath(pkg_path)
    ACBDependencyRegistry.register(PackagePath, pkg_path_typed)

    # Register filesystem service (must be first - other services depend on it)
    from crackerjack.services.enhanced_filesystem import EnhancedFileSystemService

    filesystem = EnhancedFileSystemService()
    ACBDependencyRegistry.register(FileSystemInterface, filesystem)

    # Register git service (must be before publish manager which depends on it)
    from crackerjack.services.git import GitService

    git_service = GitService(console, pkg_path)
    ACBDependencyRegistry.register(GitInterface, git_service)

    # Register hook manager
    from crackerjack.managers.hook_manager import HookManagerImpl

    hook_manager = HookManagerImpl(console, pkg_path, verbose=verbose)
    ACBDependencyRegistry.register(HookManager, hook_manager)

    # Register test manager
    from crackerjack.managers.test_manager import TestManager

    test_manager = TestManager(console, pkg_path)
    ACBDependencyRegistry.register(TestManagerProtocol, test_manager)

    # Register publish manager (depends on git_service)
    from crackerjack.managers.publish_manager import PublishManagerImpl

    publish_manager = PublishManagerImpl(console, pkg_path, git_service)
    ACBDependencyRegistry.register(PublishManager, publish_manager)

    # Register config merge service (depends on filesystem)
    from crackerjack.services.config_merge import ConfigMergeService

    config_merge = ConfigMergeService(console, filesystem, git_service)
    ACBDependencyRegistry.register(ConfigMergeServiceProtocol, config_merge)

    # Register security service
    from crackerjack.services.security import SecurityService

    security = SecurityService()
    ACBDependencyRegistry.register(SecurityServiceProtocol, security)

    # Register coverage ratchet (note: reversed argument order vs others)
    from crackerjack.services.coverage_ratchet import CoverageRatchetService

    coverage_ratchet = CoverageRatchetService(pkg_path, console)
    ACBDependencyRegistry.register(CoverageRatchetProtocol, coverage_ratchet)

    # Register cache adapter (already using ACB internally)
    from crackerjack.services.acb_cache_adapter import ACBCrackerjackCache

    cache = ACBCrackerjackCache()
    ACBDependencyRegistry.register(ACBCrackerjackCache, cache)

    # Register SQL adapter for data access using state-backed SQLite storage
    import os

    default_state_dir = Path.home() / ".crackerjack" / "state"
    default_state_dir.mkdir(parents=True, exist_ok=True)
    default_db_path = default_state_dir / "crackerjack.db"
    default_db_url = f"sqlite:///{default_db_path}"

    os.environ.setdefault("SQL_DATABASE_URL", default_db_url)
    os.environ.setdefault("DATABASE_URL", default_db_url)

    # Import SQLAdapter directly instead of using import_adapter() to avoid async event loop issues
    from acb.adapters.sql.sqlite import SqlBase as SQLAdapter

    try:
        sql_adapter = depends.get(SQLAdapter)
    except Exception:
        # Instantiate SQLAdapter directly with explicit config
        sql_adapter = SQLAdapter()
        ACBDependencyRegistry.register(SQLAdapter, sql_adapter)
    else:
        ACBDependencyRegistry.register(SQLAdapter, sql_adapter)

    try:
        sql_settings = sql_adapter.config.sql  # type: ignore[attr-defined]
        configured_url = getattr(sql_settings, "database_url", None)
        if configured_url in (None, "sqlite:///:memory:", ""):
            sql_settings.database_url = default_db_url
            if hasattr(sql_settings, "_setup_drivers"):
                sql_settings._setup_drivers()  # type: ignore[attr-defined]
            if hasattr(sql_settings, "_setup_urls"):
                sql_settings._setup_urls()  # type: ignore[attr-defined]
    except Exception:
        pass

    event_bus = WorkflowEventBus()
    telemetry_state_file = default_state_dir / "workflow_events.json"
    telemetry = WorkflowEventTelemetry(state_file=telemetry_state_file)
    register_default_subscribers(event_bus, telemetry)
    ACBDependencyRegistry.register(WorkflowEventBus, event_bus)
    ACBDependencyRegistry.register(WorkflowEventTelemetry, telemetry)

    baseline_repository = QualityBaselineRepository(sql_adapter)
    ACBDependencyRegistry.register(QualityBaselineRepository, baseline_repository)
    health_repository = HealthMetricsRepository(sql_adapter)
    ACBDependencyRegistry.register(HealthMetricsRepository, health_repository)
    dependency_repository = DependencyMonitorRepository(sql_adapter)
    ACBDependencyRegistry.register(DependencyMonitorRepository, dependency_repository)



def get_console() -> Console:
    """Get the registered Console instance.

    Returns:
        Console: The registered Rich console

    Raises:
        RuntimeError: If dependencies haven't been configured
    """
    if not ACBDependencyRegistry.is_configured():
        msg = (
            "ACB dependencies not configured. Call configure_acb_dependencies() first."
        )
        raise RuntimeError(msg)

    return depends.get(Console)


def get_pkg_path() -> Path:
    """Get the registered package path.

    Returns:
        Path: The registered package path

    Raises:
        RuntimeError: If dependencies haven't been configured
    """
    if not ACBDependencyRegistry.is_configured():
        msg = (
            "ACB dependencies not configured. Call configure_acb_dependencies() first."
        )
        raise RuntimeError(msg)

    # Import the custom type here to avoid circular imports
    from crackerjack.core.acb_di_config import PackagePath

    return depends.get(PackagePath)


def is_configured() -> bool:
    """Check if ACB dependencies have been configured.

    Returns:
        bool: True if dependencies are configured, False otherwise
    """
    return ACBDependencyRegistry.is_configured()


def reset_dependencies() -> None:
    """Reset all ACB dependencies.

    This is primarily useful for testing to ensure clean state between tests.
    In production, dependencies are typically configured once at startup.

    Example:
        >>> # In pytest fixture
        >>> @pytest.fixture(autouse=True)
        >>> def reset_acb_deps():
        >>>     yield
        >>>     reset_dependencies()
    """
    ACBDependencyRegistry.clear_all()


# Type alias for package path
PackagePathType = type[Path]
