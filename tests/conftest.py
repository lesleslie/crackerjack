"""Test configuration for new Crackerjack features."""

import tempfile
from collections.abc import Generator
from logging import Logger
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from rich.console import Console


def pytest_configure(config) -> None:
    config.addinivalue_line("markers", "performance: mark test as a performance test")
    config.addinivalue_line("markers", "integration: mark test as an integration test")


@pytest.fixture
def sample_test_data():
    """Sample test data for new feature tests."""
    return {
        "files": [
            {"name": "test.py", "content": "print('hello world')"},
            {"name": "main.py", "content": "def main(): pass"},
        ],
        "hooks": [
            {"name": "black", "status": "passed"},
            {"name": "ruff", "status": "failed", "error": "Import not found"},
        ],
        "test_results": [
            {"name": "test_example", "status": "passed", "duration": 0.1},
            {"name": "test_failure", "status": "failed", "error": "AssertionError"},
        ],
    }


@pytest.fixture
def mock_console() -> MagicMock:
    """Fixture providing a mock console for tests."""
    return MagicMock(spec=Console)


# ============================================================================
# Pattern 1: DI-Aware Fixtures for Manager Classes
# ============================================================================
# These fixtures support testing DI-based manager classes. They register
# mock services so managers can be instantiated without passing parameters.
# ============================================================================


@pytest.fixture
def mock_git_service() -> MagicMock:
    """Mock GitServiceProtocol for manager tests."""
    return MagicMock()


@pytest.fixture
def mock_version_analyzer() -> MagicMock:
    """Mock VersionAnalyzerProtocol for manager tests."""
    return MagicMock()


@pytest.fixture
def mock_changelog_generator() -> MagicMock:
    """Mock ChangelogGeneratorProtocol for manager tests."""
    return MagicMock()


@pytest.fixture
def mock_filesystem() -> MagicMock:
    """Mock FileSystemInterface for manager tests."""
    return MagicMock()


@pytest.fixture
def mock_security_service() -> MagicMock:
    """Mock SecurityServiceProtocol for manager tests."""
    return MagicMock()


@pytest.fixture
def mock_regex_patterns() -> MagicMock:
    """Mock RegexPatternsProtocol for manager tests."""
    return MagicMock()


@pytest.fixture
def mock_logger() -> MagicMock:
    """Mock Logger for manager tests."""
    return MagicMock(spec=Logger)


@pytest.fixture
def temp_pkg_path() -> Generator[Path]:
    """Temporary package path for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture(autouse=True)
def reset_crackerjack_singletons():
    """Reset all Crackerjack singletons before and after each test.

    This fixture ensures complete test isolation by resetting all known global
    singletons, caches, and module-level state between tests. This prevents
    test pollution where state from one test affects another.

    Handles: HookLockManager, AsyncTimeoutManager, ServiceWatchdog, MetricsCollector,
    AsyncPerformanceMonitor, IntelligentAgentSystem, AgentOrchestrator,
    AdaptiveLearningSystem, AgentRegistry, IssueEmbedder, FallbackIssueEmbedder,
    HTTPConnectionPool, structlog, LRU caches, and oneiric modules.
    """
    # Import lazily to avoid expensive imports during test collection
    from tests.conftest_reset import reset_all_singletons

    reset_all_singletons()

    yield

    reset_all_singletons()


# Removed the expose_tool_functions_to_builtins fixture to reduce builtin injection.
# Tests should properly import the functions they need instead of relying on global injection.
# This makes tests more explicit, maintainable, and reduces potential naming conflicts.

@pytest.fixture
def publish_manager_di_context(
    mock_console: MagicMock,
    mock_logger: MagicMock,
    mock_git_service: MagicMock,
    mock_version_analyzer: MagicMock,
    mock_changelog_generator: MagicMock,
    mock_filesystem: MagicMock,
    mock_security_service: MagicMock,
    mock_regex_patterns: MagicMock,
    temp_pkg_path: Path,
) -> Generator[tuple[dict[type, Any], Path]]:
    """Set up DI context for PublishManagerImpl testing.

    Sets up all required dependencies and yields the injection map
    for use in tests. This enables instantiation of PublishManagerImpl
    without passing constructor parameters.

    The DI context is maintained for the duration of the fixture and test.

    Usage:
        def test_publish_manager(publish_manager_di_context):
            injection_map, pkg_path = publish_manager_di_context
            # Now can create PublishManagerImpl()
            manager = PublishManagerImpl()
    """
    from crackerjack.models.protocols import (
        ChangelogGeneratorProtocol,
        FileSystemInterface,
        GitServiceProtocol,
        RegexPatternsProtocol,
        SecurityServiceProtocol,
        VersionAnalyzerProtocol,
    )

    injection_map = {
        Console: mock_console,
        Logger: mock_logger,
        GitServiceProtocol: mock_git_service,
        VersionAnalyzerProtocol: mock_version_analyzer,
        ChangelogGeneratorProtocol: mock_changelog_generator,
        FileSystemInterface: mock_filesystem,
        SecurityServiceProtocol: mock_security_service,
        RegexPatternsProtocol: mock_regex_patterns,
        Path: temp_pkg_path,
    }

    return injection_map, temp_pkg_path


# Ensure an asyncio event loop exists for tests that use asyncio.Future() directly
@pytest.fixture(autouse=True)
def _ensure_event_loop():
    import asyncio
    try:
        asyncio.get_running_loop()
        yield
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            yield
        finally:
            # Keep the loop open to avoid disrupting other tests that may reuse it
            pass


@pytest.fixture
def mock_test_manager() -> MagicMock:
    """Mock TestManagerProtocol for orchestrator tests."""
    return MagicMock()


@pytest.fixture
def mock_publish_manager() -> MagicMock:
    """Mock PublishManager for orchestrator tests."""
    return MagicMock()


@pytest.fixture
def mock_hook_manager() -> MagicMock:
    """Mock HookManager for orchestrator tests."""
    return MagicMock()


@pytest.fixture
def mock_config_merge_service() -> MagicMock:
    """Mock ConfigMergeServiceProtocol for orchestrator tests."""
    return MagicMock()


@pytest.fixture
def mock_coverage_ratchet() -> MagicMock:
    """Mock CoverageRatchetProtocol for orchestrator tests."""
    return MagicMock()


@pytest.fixture
def mock_config_integrity_service() -> MagicMock:
    """Mock ConfigIntegrityServiceProtocol for orchestrator tests."""
    return MagicMock()


@pytest.fixture
def mock_coverage_badge_service() -> MagicMock:
    """Mock CoverageBadgeServiceProtocol for orchestrator tests."""
    return MagicMock()


@pytest.fixture
def mock_enhanced_filesystem_service() -> MagicMock:
    """Mock EnhancedFileSystemServiceProtocol for orchestrator tests."""
    return MagicMock()


@pytest.fixture
def mock_hook_lock_manager() -> MagicMock:
    """Mock HookLockManagerProtocol for orchestrator tests."""
    return MagicMock()


@pytest.fixture
def mock_smart_scheduling_service() -> MagicMock:
    """Mock SmartSchedulingServiceProtocol for orchestrator tests."""
    return MagicMock()


@pytest.fixture
def mock_unified_config_service() -> MagicMock:
    """Mock UnifiedConfigurationServiceProtocol for orchestrator tests."""
    return MagicMock()


@pytest.fixture
def mock_memory_optimizer() -> MagicMock:
    """Mock MemoryOptimizerProtocol for orchestrator tests."""
    return MagicMock()


@pytest.fixture
def mock_parallel_hook_executor() -> MagicMock:
    """Mock ParallelHookExecutor for orchestrator tests."""
    return MagicMock()


@pytest.fixture
def mock_async_command_executor() -> MagicMock:
    """Mock AsyncCommandExecutor for orchestrator tests."""
    return MagicMock()


@pytest.fixture
def mock_git_operation_cache() -> MagicMock:
    """Mock GitOperationCache for orchestrator tests."""
    return MagicMock()


@pytest.fixture
def mock_filesystem_cache() -> MagicMock:
    """Mock FileSystemCache for orchestrator tests."""
    return MagicMock()


@pytest.fixture
def workflow_orchestrator_di_context(
    mock_console: MagicMock,
    mock_logger: MagicMock,
    mock_filesystem: MagicMock,
    mock_git_service: MagicMock,
    mock_hook_manager: MagicMock,
    mock_test_manager: MagicMock,
    mock_publish_manager: MagicMock,
    mock_config_merge_service: MagicMock,
    mock_version_analyzer: MagicMock,
    mock_changelog_generator: MagicMock,
    mock_security_service: MagicMock,
    mock_regex_patterns: MagicMock,
    mock_coverage_ratchet: MagicMock,
    mock_config_integrity_service: MagicMock,
    mock_coverage_badge_service: MagicMock,
    mock_enhanced_filesystem_service: MagicMock,
    mock_hook_lock_manager: MagicMock,
    mock_smart_scheduling_service: MagicMock,
    mock_unified_config_service: MagicMock,
    mock_memory_optimizer: MagicMock,
    mock_parallel_hook_executor: MagicMock,
    mock_async_command_executor: MagicMock,
    mock_git_operation_cache: MagicMock,
    mock_filesystem_cache: MagicMock,
    temp_pkg_path: Path,
) -> Generator[tuple[dict[type, Any], Path]]:
    """Set up DI context for WorkflowOrchestrator testing.

    Registers all dependencies required by WorkflowOrchestrator and its
    coordinators (SessionCoordinator, PhaseCoordinator). This enables
    instantiation of WorkflowOrchestrator without complex setup.

    The DI context is maintained for the duration of the fixture and test.

    Usage:
        def test_workflow_orchestrator(workflow_orchestrator_di_context):
            injection_map, pkg_path = workflow_orchestrator_di_context
            # Now can create WorkflowOrchestrator(pkg_path=pkg_path)
            orchestrator = WorkflowOrchestrator(pkg_path=pkg_path)
    """
    # Handle missing monitoring module gracefully
    try:
        from crackerjack.services.monitoring.performance_cache import (
            FileSystemCache,
            GitOperationCache,
        )
    except ImportError:
        # Stub classes for missing module
        class FileSystemCache:
            pass
        class GitOperationCache:
            pass

    from crackerjack.models.protocols import (
        ChangelogGeneratorProtocol,
        ConfigIntegrityServiceProtocol,
        ConfigMergeServiceProtocol,
        CoverageBadgeServiceProtocol,
        CoverageRatchetProtocol,
        EnhancedFileSystemServiceProtocol,
        FileSystemInterface,
        GitInterface,
        GitServiceProtocol,
        HookLockManagerProtocol,
        HookManager,
        MemoryOptimizerProtocol,
        PublishManager,
        RegexPatternsProtocol,
        SecurityServiceProtocol,
        SmartSchedulingServiceProtocol,
        TestManagerProtocol,
        UnifiedConfigurationServiceProtocol,
        VersionAnalyzerProtocol,
    )
    from crackerjack.services.parallel_executor import (
        AsyncCommandExecutor,
        ParallelHookExecutor,
    )

    injection_map = {
        Console: mock_console,
        Logger: mock_logger,
        FileSystemInterface: mock_filesystem,
        GitInterface: mock_git_service,
        GitServiceProtocol: mock_git_service,
        HookManager: mock_hook_manager,
        TestManagerProtocol: mock_test_manager,
        PublishManager: mock_publish_manager,
        ConfigMergeServiceProtocol: mock_config_merge_service,
        VersionAnalyzerProtocol: mock_version_analyzer,
        ChangelogGeneratorProtocol: mock_changelog_generator,
        SecurityServiceProtocol: mock_security_service,
        RegexPatternsProtocol: mock_regex_patterns,
        CoverageRatchetProtocol: mock_coverage_ratchet,
        ConfigIntegrityServiceProtocol: mock_config_integrity_service,
        CoverageBadgeServiceProtocol: mock_coverage_badge_service,
        EnhancedFileSystemServiceProtocol: mock_enhanced_filesystem_service,
        HookLockManagerProtocol: mock_hook_lock_manager,
        SmartSchedulingServiceProtocol: mock_smart_scheduling_service,
        UnifiedConfigurationServiceProtocol: mock_unified_config_service,
        MemoryOptimizerProtocol: mock_memory_optimizer,
        ParallelHookExecutor: mock_parallel_hook_executor,
        AsyncCommandExecutor: mock_async_command_executor,
        GitOperationCache: mock_git_operation_cache,
        FileSystemCache: mock_filesystem_cache,
        Path: temp_pkg_path,
    }

    return injection_map, temp_pkg_path
