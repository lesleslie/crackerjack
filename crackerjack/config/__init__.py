from contextlib import suppress
from pathlib import Path

from acb.console import Console
from acb.depends import depends
from acb.logger import Logger

# Import protocols for service registration
from crackerjack.models.protocols import (
    ChangelogGeneratorProtocol,
    CoverageBadgeServiceProtocol,
    CoverageRatchetProtocol,
    DebugServiceProtocol,
    GitServiceProtocol,
    LoggerProtocol,
    MemoryOptimizerProtocol,
    PerformanceBenchmarkProtocol,
    PerformanceCacheProtocol,
    PerformanceMonitorProtocol,
    QualityBaselineProtocol,
    QualityIntelligenceProtocol,
    VersionAnalyzerProtocol,
)
from crackerjack.services.changelog_automation import ChangelogGenerator
from crackerjack.services.coverage_badge_service import CoverageBadgeService
from crackerjack.services.coverage_ratchet import CoverageRatchetService

# Import service implementations
from crackerjack.services.debug import get_ai_agent_debugger
from crackerjack.services.git import GitService
from crackerjack.services.lsp_client import LSPClient
from crackerjack.services.memory_optimizer import MemoryOptimizer
from crackerjack.services.monitoring.performance_benchmarks import (
    PerformanceBenchmarkService,
)
from crackerjack.services.monitoring.performance_cache import (
    FileSystemCache,
    GitOperationCache,
    get_filesystem_cache,
    get_git_cache,
    get_performance_cache,
)
from crackerjack.services.monitoring.performance_monitor import get_performance_monitor
from crackerjack.services.parallel_executor import (
    AsyncCommandExecutor,
    ParallelHookExecutor,
    get_async_executor,
    get_parallel_executor,
)
from crackerjack.services.quality.quality_baseline_enhanced import (
    EnhancedQualityBaselineService,
)
from crackerjack.services.quality.quality_intelligence import (
    QualityIntelligenceService,
)
from crackerjack.services.version_analyzer import VersionAnalyzer

from .hooks import (
    COMPREHENSIVE_STRATEGY,
    FAST_STRATEGY,
    HookConfigLoader,
    HookDefinition,
    HookStage,
    HookStrategy,
    RetryPolicy,
)
from .loader import load_settings, load_settings_async
from .settings import CrackerjackSettings


def get_console_width() -> int:
    """Return the preferred console width from settings or pyproject.

    Priority:
    1) ACB settings (CrackerjackSettings.console.width)
    2) pyproject.toml [tool.crackerjack].terminal_width
    3) Default: 70
    """
    # 1) Try ACB settings via DI
    with suppress(Exception):
        settings = depends.get_sync(CrackerjackSettings)
        width = getattr(getattr(settings, "console", None), "width", None)
        if isinstance(width, int) and width > 0:
            return width

    # 2) Try pyproject.toml
    with suppress(Exception):
        from pathlib import Path as _P

        import tomli

        pyproj = _P("pyproject.toml")
        if pyproj.exists():
            with pyproj.open("rb") as f:
                data = tomli.load(f)
            width = (
                data.get("tool", {}).get("crackerjack", {}).get("terminal_width", None)
            )
            if isinstance(width, int) and width > 0:
                return width

    # 3) Default
    return 70


# Load settings from YAML files using layered configuration
settings_instance = load_settings(CrackerjackSettings)
depends.set(CrackerjackSettings, settings_instance)

# Register ACB Logger (auto-registers itself, but set explicitly for clarity)
logger_instance = Logger()
depends.set(Logger, logger_instance)
depends.set(LoggerProtocol, logger_instance)  # Also register as LoggerProtocol


def register_services() -> None:
    """Register all service instances with ACB dependency injection system.

    Services are registered at application initialization to ensure proper
    dependency ordering and lifecycle management. This follows ACB's pattern
    of centralizing service registration rather than having services register
    themselves or be instantiated in consumers.

    The order of registration is important to ensure that dependencies are met:
    1.  Core utility services (Debug, Performance Monitoring, Memory, Caching)
    2.  Specialized cache services (Git, Filesystem)
    3.  Quality-related services (Baseline, Intelligence)
    4.  Manager-layer services (Coverage, Git, Versioning, Changelog, LSP)
    """
    # 1. Register Debug Service
    # Uses factory function to handle environment detection
    debugger = get_ai_agent_debugger()
    depends.set(DebugServiceProtocol, debugger)

    # 2. Register Performance Monitor
    # Core performance tracking service
    performance_monitor = get_performance_monitor()
    depends.set(PerformanceMonitorProtocol, performance_monitor)

    # 3. Register Memory Optimizer
    # Memory management and optimization
    memory_optimizer = MemoryOptimizer.get_instance()
    depends.set(MemoryOptimizerProtocol, memory_optimizer)

    # 4. Register Performance Cache
    # Caching layer for performance optimization
    performance_cache = get_performance_cache()
    depends.set(PerformanceCacheProtocol, performance_cache)

    # 5. Register Performance Benchmark Service
    # The service should be registered automatically via @depends.inject
    # in the service implementation, but if not let's create and register it manually
    try:
        # First, try to get the already registered instance
        try:
            performance_benchmarks = depends.get_sync(PerformanceBenchmarkProtocol)
        except Exception:
            # If not registered, create it using proper DI
            console = depends.get_sync(Console)
            logger = depends.get_sync(
                Logger
            )  # Get the logger instead of LoggerProtocol
            pkg_path = Path.cwd()  # Use current directory as fallback
            performance_benchmarks = PerformanceBenchmarkService(
                console=console, logger=logger, pkg_path=pkg_path
            )
            # Register the newly created instance
            depends.set(PerformanceBenchmarkProtocol, performance_benchmarks)
    except Exception as e:
        # Log the error to help with debugging
        print(f"WARNING: Failed to register PerformanceBenchmarkService: {e}")
        # Performance benchmarking will be disabled
        pass

    # 6. Register Parallel Executor Services
    # For parallel and async hook execution
    parallel_executor = get_parallel_executor()
    depends.set(ParallelHookExecutor, parallel_executor)

    async_executor = get_async_executor()
    depends.set(AsyncCommandExecutor, async_executor)

    # 7. Register Specialized Cache Services
    # Git and filesystem caching
    git_cache = get_git_cache()
    depends.set(GitOperationCache, git_cache)

    filesystem_cache = get_filesystem_cache()
    depends.set(FileSystemCache, filesystem_cache)

    # 8. Register Quality Baseline Service
    # Foundation for quality tracking and intelligence
    with suppress(Exception):
        quality_baseline = EnhancedQualityBaselineService()
        depends.set(QualityBaselineProtocol, quality_baseline)

        # 9. Register Quality Intelligence Service
        # Depends on quality baseline service
        quality_intelligence = QualityIntelligenceService(quality_baseline)
        depends.set(QualityIntelligenceProtocol, quality_intelligence)

    # 10. Register Manager Layer Services
    # Services used by test_manager.py and publish_manager.py

    # Get console and pkg_path for service initialization
    with suppress(Exception):
        console = depends.get_sync(Console)
        pkg_path = depends.get_sync(Path)

        # 10a. Coverage Ratchet Service (protocol-based)
        coverage_ratchet = CoverageRatchetService(pkg_path)
        depends.set(CoverageRatchetProtocol, coverage_ratchet)

        # 10b. Coverage Badge Service (protocol-based)
        coverage_badge = depends.inject_sync(
            CoverageBadgeService, console=console, project_root=pkg_path
        )
        depends.set(CoverageBadgeServiceProtocol, coverage_badge)

        # 10c. Git Service (protocol-based, foundation for dependent services)
        git_service = GitService(pkg_path)
        depends.set(GitServiceProtocol, git_service)

        # 10d. Version Analyzer (protocol-based, depends on git_service)
        version_analyzer = VersionAnalyzer(git_service)
        depends.set(VersionAnalyzerProtocol, version_analyzer)

        # 10e. Changelog Generator (protocol-based, ACB DI injects dependencies)
        changelog_generator = ChangelogGenerator()
        depends.set(ChangelogGeneratorProtocol, changelog_generator)

        # 10f. LSP Client (concrete type - optional service with graceful fallback)
        with suppress(Exception):
            lsp_client = LSPClient()
            depends.set(LSPClient, lsp_client)


# Service registration is called explicitly by application entry point
# to avoid circular import issues during module initialization.
# Call register_services() after all modules are loaded, typically in __main__.py

__all__ = [
    "COMPREHENSIVE_STRATEGY",
    "FAST_STRATEGY",
    "HookConfigLoader",
    "HookDefinition",
    "HookStage",
    "HookStrategy",
    "RetryPolicy",
    "CrackerjackSettings",
    "load_settings",
    "load_settings_async",
    "register_services",
    "get_console_width",
]
