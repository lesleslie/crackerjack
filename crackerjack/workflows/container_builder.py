"""DI container builder for ACB workflow integration.

This module provides WorkflowContainerBuilder which handles the complex task of
registering all WorkflowPipeline dependencies with ACB's DI container in the
correct initialization order.

The builder follows a level-based registration strategy:
- Level 1: Primitives (Console, Config, Logger)
- Level 2: Core Services (MemoryOptimizer, Caches, etc.)
- Level 3: Filesystem & Git Services
- Level 4: Managers (HookManager, TestManager, etc.)
- Level 5: Executors (ParallelHookExecutor, AsyncCommandExecutor)
- Level 6: Coordinators (SessionCoordinator, PhaseCoordinator)
- Level 7: Pipeline (WorkflowPipeline)

Example:
    ```python
    from crackerjack.workflows.container_builder import WorkflowContainerBuilder

    # Build container with all services
    builder = WorkflowContainerBuilder(options)
    builder.build()

    # Verify all services available
    health = builder.health_check()
    if not health["all_available"]:
        print(f"Missing: {health['missing']}")

    # Get WorkflowPipeline
    from acb.depends import depends

    pipeline = depends.get_sync(WorkflowPipeline)
    ```
"""

from __future__ import annotations

import typing as t
from pathlib import Path

from acb.config import Config
from acb.console import Console
from acb.depends import depends

if t.TYPE_CHECKING:
    from crackerjack.models.protocols import OptionsProtocol


class WorkflowContainerBuilder:
    """Builds and initializes DI container for ACB workflows.

    Handles dependency registration in correct order, validates all services
    are available, and provides health checks for debugging.

    Attributes:
        options: CLI options containing configuration
        _console: Console instance (optional override for testing)
        _root_path: Project root path
        _registered: Set of registered service names for tracking
    """

    def __init__(
        self,
        options: OptionsProtocol,
        console: Console | None = None,
        root_path: Path | None = None,
    ) -> None:
        """Initialize builder with options and optional overrides.

        Args:
            options: CLI options containing configuration
            console: Optional console override (for testing)
            root_path: Optional root path override (for testing)
        """
        self.options = options
        self._console = console
        self._root_path = root_path or getattr(options, "project_root", Path.cwd())
        self._registered: set[str] = set()

    def build(self) -> None:
        """Build container by registering all services in dependency order.

        This method orchestrates the registration of all services required by
        WorkflowPipeline, ensuring proper initialization order.

        The registration is split into levels to ensure dependencies are
        available before services that need them.

        Raises:
            RuntimeError: If service registration fails
        """
        self._register_level1_primitives()
        self._register_level2_core_services()
        self._register_level3_filesystem_git()
        self._register_level4_managers()
        self._register_level5_executors()
        self._register_level6_coordinators()
        self._register_level7_pipeline()

    def health_check(self) -> dict[str, t.Any]:
        """Check which services are registered and available.

        Returns:
            dict with:
                - registered: set of service names that were registered
                - available: dict mapping service names to availability status
                - missing: list of expected but missing services
                - all_available: boolean indicating if all services are available
        """
        from crackerjack.models import protocols
        from crackerjack.services.monitoring.performance_cache import (
            FileSystemCache,
            GitOperationCache,
        )

        # All expected protocols/services
        expected = [
            # Level 1: Primitives
            ("Console", Console),
            ("Config", Config),
            ("LoggerProtocol", protocols.LoggerProtocol),
            # Level 2: Core Services
            ("MemoryOptimizerProtocol", protocols.MemoryOptimizerProtocol),
            ("PerformanceCacheProtocol", protocols.PerformanceCacheProtocol),
            ("DebugServiceProtocol", protocols.DebugServiceProtocol),
            ("PerformanceMonitorProtocol", protocols.PerformanceMonitorProtocol),
            # Level 3: Filesystem & Git
            ("FileSystemInterface", protocols.FileSystemInterface),
            ("GitInterface", protocols.GitInterface),
            ("GitOperationCache", GitOperationCache),
            ("FileSystemCache", FileSystemCache),
            # Add more as we implement them
        ]

        available = {}
        for name, protocol_type in expected:
            try:
                service = depends.get_sync(protocol_type)
                available[name] = service is not None
            except Exception:
                available[name] = False

        missing = [name for name, avail in available.items() if not avail]

        return {
            "registered": self._registered,
            "available": available,
            "missing": missing,
            "all_available": len(missing) == 0,
        }

    def _register_level1_primitives(self) -> None:
        """Register Level 1 primitives: Console, Config, Logger.

        These are the foundation services with no dependencies (except Config
        which uses the current directory by default).
        """
        # Console
        if not self._console:
            self._console = Console()
        depends.set(Console, self._console)
        self._registered.add("Console")

        # Config - ACB's Config auto-detects root_path from current directory
        config = Config()
        depends.set(Config, config)
        self._registered.add("Config")

        # Logger
        from crackerjack.models.protocols import LoggerProtocol
        from crackerjack.services.logging import get_logger

        logger = get_logger(__name__)
        depends.set(LoggerProtocol, logger)
        self._registered.add("LoggerProtocol")

    def _register_level2_core_services(self) -> None:
        """Register Level 2 core services: MemoryOptimizer, Caches, etc.

        These services use @depends.inject and will auto-inject their dependencies
        from the container. We just need to create instances and register them.
        """
        from crackerjack.models.protocols import (
            DebugServiceProtocol,
            MemoryOptimizerProtocol,
            PerformanceCacheProtocol,
            PerformanceMonitorProtocol,
        )

        # Memory Optimizer - uses @depends.inject, takes Logger
        from crackerjack.services.memory_optimizer import MemoryOptimizer

        memory_optimizer = MemoryOptimizer()
        depends.set(MemoryOptimizerProtocol, memory_optimizer)
        self._registered.add("MemoryOptimizerProtocol")

        # Performance Cache - in monitoring/
        from crackerjack.services.monitoring.performance_cache import PerformanceCache

        perf_cache = PerformanceCache()
        depends.set(PerformanceCacheProtocol, perf_cache)
        self._registered.add("PerformanceCacheProtocol")

        # Debug Service - AIAgentDebugger
        from crackerjack.services.debug import AIAgentDebugger

        debug_service = AIAgentDebugger()
        depends.set(DebugServiceProtocol, debug_service)
        self._registered.add("DebugServiceProtocol")

        # Performance Monitor - in monitoring/
        from crackerjack.services.monitoring.performance_monitor import (
            PerformanceMonitor,
        )

        perf_monitor = PerformanceMonitor()
        depends.set(PerformanceMonitorProtocol, perf_monitor)
        self._registered.add("PerformanceMonitorProtocol")

    def _register_level3_filesystem_git(self) -> None:
        """Register Level 3 filesystem and git services.

        These depend on Console (Level 1) and caches/logger from previous levels.
        """
        from crackerjack.models.protocols import (
            FileSystemInterface,
            GitInterface,
            LoggerProtocol,
            PerformanceCacheProtocol,
        )
        from crackerjack.services.filesystem import FileSystemService
        from crackerjack.services.git import GitService
        from crackerjack.services.monitoring.performance_cache import (
            FileSystemCache,
            GitOperationCache,
        )

        # FileSystemService - static methods, no dependencies
        filesystem = FileSystemService()
        depends.set(FileSystemInterface, filesystem)
        self._registered.add("FileSystemInterface")

        # GitService - uses @depends.inject with Console
        git_service = GitService(pkg_path=self._root_path)
        depends.set(GitInterface, git_service)
        self._registered.add("GitInterface")

        # Cache services need PerformanceCache (Level 2) and Logger (Level 1)
        perf_cache = depends.get_sync(PerformanceCacheProtocol)
        logger = depends.get_sync(LoggerProtocol)

        # GitOperationCache
        git_cache = GitOperationCache(cache=perf_cache, logger=logger)
        depends.set(GitOperationCache, git_cache)
        self._registered.add("GitOperationCache")

        # FileSystemCache
        filesystem_cache = FileSystemCache(cache=perf_cache, logger=logger)
        depends.set(FileSystemCache, filesystem_cache)
        self._registered.add("FileSystemCache")

    def _register_level4_managers(self) -> None:
        """Register Level 4 managers: HookManager, TestManager, etc.

        These depend on Level 1-3 services.
        """
        # TODO: Implement manager registration
        pass

    def _register_level5_executors(self) -> None:
        """Register Level 5 executors: ParallelHookExecutor, AsyncCommandExecutor.

        These depend on Level 1-4 services.
        """
        # TODO: Implement executor registration
        pass

    def _register_level6_coordinators(self) -> None:
        """Register Level 6 coordinators: SessionCoordinator, PhaseCoordinator.

        These depend on Level 1-5 services.
        """
        # TODO: Implement coordinator registration
        pass

    def _register_level7_pipeline(self) -> None:
        """Register Level 7 pipeline: WorkflowPipeline.

        This is the top-level service that depends on all previous levels.
        """
        # TODO: Implement pipeline registration
        pass
