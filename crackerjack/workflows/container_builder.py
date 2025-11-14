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
        self._register_level3_5_publishing_services()
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
        """Register Level 1 primitives: Console, Config, Logger, Path.

        These are the foundation services with no dependencies (except Config
        which uses the current directory by default).
        """
        # Console - Configure width from settings for progress bars
        if not self._console:
            self._console = Console()
            # Set console width from configuration
            from crackerjack.config import get_console_width

            self._console.width = get_console_width()
        depends.set(Console, self._console)
        self._registered.add("Console")

        # Path - project root path for dependency injection
        depends.set(Path, self._root_path)
        self._registered.add("Path")

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

        # WorkflowEventBus - event-driven workflow coordination (Phase 7.1)
        from crackerjack.events.workflow_bus import WorkflowEventBus

        event_bus = WorkflowEventBus()
        depends.set(WorkflowEventBus, event_bus)
        self._registered.add("WorkflowEventBus")

        # EventBusWebSocketBridge - WebSocket streaming for real-time updates (Phase 7.3)
        from crackerjack.mcp.websocket.event_bridge import EventBusWebSocketBridge

        ws_bridge = EventBusWebSocketBridge()
        depends.set(EventBusWebSocketBridge, ws_bridge)
        self._registered.add("EventBusWebSocketBridge")

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

    def _register_level3_5_publishing_services(self) -> None:
        """Register Level 3.5 publishing services needed by PublishManager.

        These services must be registered before Level 4 managers can be instantiated.
        """
        from crackerjack.models.protocols import (
            ChangelogGeneratorProtocol,
            GitServiceProtocol,
            SecurityServiceProtocol,
            VersionAnalyzerProtocol,
        )
        from crackerjack.services.changelog_automation import ChangelogGenerator
        from crackerjack.services.security import SecurityService
        from crackerjack.services.version_analyzer import VersionAnalyzer

        # SecurityService - no dependencies
        security_service = SecurityService()
        depends.set(SecurityServiceProtocol, security_service)
        self._registered.add("SecurityServiceProtocol")

        # GitService as GitServiceProtocol - reuse Level 3 instance
        from crackerjack.models.protocols import GitInterface

        git_service = depends.get_sync(GitInterface)
        depends.set(GitServiceProtocol, git_service)
        self._registered.add("GitServiceProtocol")

        # ChangelogGenerator - uses @depends.inject (Console, GitServiceProtocol)
        changelog_generator = ChangelogGenerator()
        depends.set(ChangelogGeneratorProtocol, changelog_generator)
        self._registered.add("ChangelogGeneratorProtocol")

        # VersionAnalyzer - uses @depends.inject (Console, GitService)
        # Note: git_service parameter doesn't use Inject[] type hint, so we pass it manually
        # VersionAnalyzer internally creates ChangelogGenerator()
        version_analyzer = VersionAnalyzer(git_service=git_service)
        depends.set(VersionAnalyzerProtocol, version_analyzer)
        self._registered.add("VersionAnalyzerProtocol")

        # RegexPatternsProtocol - service wrapper for module functions
        from crackerjack.models.protocols import RegexPatternsProtocol
        from crackerjack.services.regex_patterns import RegexPatternsService

        regex_patterns_service = RegexPatternsService()
        depends.set(RegexPatternsProtocol, regex_patterns_service)
        self._registered.add("RegexPatternsProtocol")

    def _register_level4_managers(self) -> None:
        """Register Level 4 managers: HookManager, TestManager, etc.

        These depend on Level 1-3.5 services.
        """
        from crackerjack.managers.hook_manager import HookManagerImpl
        from crackerjack.models.protocols import HookManager

        # HookManager - simplest, just needs pkg_path + options
        # Retrieves Console internally via depends.get_sync
        hook_manager = HookManagerImpl(
            pkg_path=self._root_path,
            verbose=getattr(self.options, "verbose", False),
            quiet=getattr(self.options, "quiet", False),
            enable_lsp_optimization=getattr(
                self.options, "enable_lsp_optimization", False
            ),
            enable_tool_proxy=getattr(self.options, "enable_tool_proxy", True),
        )
        depends.set(HookManager, hook_manager)
        self._registered.add("HookManager")

        # Level 4.5: Register TestManager dependencies
        self._register_level4_5_test_manager_dependencies()

        # TestCommandBuilder - needed by TestManager
        from crackerjack.managers.test_command_builder import TestCommandBuilder

        test_command_builder = TestCommandBuilder()
        depends.set(TestCommandBuilder, test_command_builder)
        self._registered.add("TestCommandBuilder")

        # TestManager - uses @depends.inject (all Level 4.5 dependencies registered)
        from crackerjack.managers.test_manager import TestManager
        from crackerjack.models.protocols import TestManagerProtocol

        test_manager = TestManager()
        depends.set(TestManagerProtocol, test_manager)
        self._registered.add("TestManagerProtocol")

        # PublishManager - uses @depends.inject (all Level 3.5 dependencies registered)
        from crackerjack.managers.publish_manager import PublishManagerImpl
        from crackerjack.models.protocols import PublishManager

        # Instantiate with NO parameters to trigger full DI resolution
        # The @depends.inject decorator will inject all dependencies including console, pkg_path
        publish_manager = PublishManagerImpl()
        depends.set(PublishManager, publish_manager)
        self._registered.add("PublishManager")

    def _register_level4_5_test_manager_dependencies(self) -> None:
        """Register Level 4.5: TestManager dependencies.

        These services must be registered before TestManager can be instantiated.
        """
        from crackerjack.models.protocols import (
            CoverageBadgeServiceProtocol,
            CoverageRatchetProtocol,
        )
        from crackerjack.services.coverage_badge_service import CoverageBadgeService
        from crackerjack.services.coverage_ratchet import CoverageRatchetService
        from crackerjack.services.lsp_client import LSPClient

        # CoverageRatchetService - uses @depends.inject (pkg_path, Console)
        coverage_ratchet = CoverageRatchetService(pkg_path=self._root_path)
        depends.set(CoverageRatchetProtocol, coverage_ratchet)
        self._registered.add("CoverageRatchetProtocol")

        # CoverageBadgeService - uses @depends.inject (Console, project_root)
        coverage_badge = CoverageBadgeService(project_root=self._root_path)
        depends.set(CoverageBadgeServiceProtocol, coverage_badge)
        self._registered.add("CoverageBadgeServiceProtocol")

        # LSPClient - uses @depends.inject (Console only)
        lsp_client = LSPClient()
        depends.set(LSPClient, lsp_client)
        self._registered.add("LSPClient")

    def _register_level5_executors(self) -> None:
        """Register Level 5 executors: ParallelHookExecutor, AsyncCommandExecutor.

        These depend on Logger (Level 1) and PerformanceCacheProtocol (Level 2).
        """
        from crackerjack.services.parallel_executor import (
            AsyncCommandExecutor,
            ExecutionStrategy,
            ParallelHookExecutor,
        )

        # ParallelHookExecutor - uses @depends.inject (Logger, PerformanceCache)
        parallel_executor = ParallelHookExecutor(
            max_workers=3,
            timeout_seconds=300,
            strategy=ExecutionStrategy.PARALLEL_SAFE,
        )
        depends.set(ParallelHookExecutor, parallel_executor)
        self._registered.add("ParallelHookExecutor")

        # AsyncCommandExecutor - uses @depends.inject (Logger, PerformanceCache)
        async_executor = AsyncCommandExecutor(max_workers=4, cache_results=True)
        depends.set(AsyncCommandExecutor, async_executor)
        self._registered.add("AsyncCommandExecutor")

    def _register_level6_coordinators(self) -> None:
        """Register Level 6 coordinators: SessionCoordinator, PhaseCoordinator.

        These depend on Level 1-5 services.
        """
        from crackerjack.core.phase_coordinator import PhaseCoordinator
        from crackerjack.core.session_coordinator import SessionCoordinator
        from crackerjack.models.protocols import ConfigMergeServiceProtocol
        from crackerjack.services.config_merge import ConfigMergeService

        # ConfigMergeService - needed by PhaseCoordinator
        # Uses @depends.inject (Console, FileSystemInterface, GitInterface, Logger)
        config_merge_service = ConfigMergeService()
        depends.set(ConfigMergeServiceProtocol, config_merge_service)
        self._registered.add("ConfigMergeServiceProtocol")

        # SessionCoordinator - uses @depends.inject (Console, pkg_path)
        session_coordinator = SessionCoordinator(
            pkg_path=self._root_path, web_job_id=None
        )
        depends.set(SessionCoordinator, session_coordinator)
        self._registered.add("SessionCoordinator")

        # PhaseCoordinator - uses @depends.inject (all Level 1-5 services)
        # Depends on SessionCoordinator (registered above)
        phase_coordinator = PhaseCoordinator(pkg_path=self._root_path)
        depends.set(PhaseCoordinator, phase_coordinator)
        self._registered.add("PhaseCoordinator")

    def _register_level7_pipeline(self) -> None:
        """Register Level 7 pipeline: WorkflowPhaseExecutor and WorkflowPipeline.

        This is the top-level service that depends on all previous levels.
        """
        from crackerjack.core.workflow.workflow_phase_executor import (
            WorkflowPhaseExecutor,
        )
        from crackerjack.core.workflow_orchestrator import WorkflowPipeline

        # Since WorkflowPhaseExecutor has @depends.inject on its __init__ method,
        # Bevy should automatically handle creating instances when WorkflowPipeline
        # requests it via dependency injection. But we still need to make sure
        # Bevy recognizes it as a class it can instantiate using its @depends.inject
        # decorated constructor.
        # For this to work, all of WorkflowPhaseExecutor's dependencies must be in the container:
        # - Console (Level 1) ✓
        # - LoggerProtocol (Level 1) ✓
        # - Path (Level 1) ✓
        # - DebugServiceProtocol (Level 2) ✓
        # - QualityIntelligenceProtocol (Level 2 or 4.5) ✓
        # If all dependencies are available, Bevy's @depends.inject should work automatically.
        # But let's explicitly signal that this type can be handled by Bevy's injection system.

        # Register the type with Bevy so it knows it can create instances when requested
        # The Bevy system should handle the @depends.inject automatically when this type is requested
        depends.set(WorkflowPhaseExecutor, WorkflowPhaseExecutor)
        self._registered.add("WorkflowPhaseExecutor")

        # WorkflowPipeline - uses @depends.inject (all Level 1-6 services + WorkflowPhaseExecutor)
        # Auto-wires: Console, Config, PerformanceMonitor, MemoryOptimizer,
        # PerformanceCache, Debugger, Logger, SessionCoordinator, PhaseCoordinator, WorkflowPhaseExecutor
        # Optional: QualityIntelligence, PerformanceBenchmarks
        workflow_pipeline = WorkflowPipeline()
        depends.set(WorkflowPipeline, workflow_pipeline)
        self._registered.add("WorkflowPipeline")
