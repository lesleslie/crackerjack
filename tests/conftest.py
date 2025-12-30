"""Test configuration for new Crackerjack features."""

from contextlib import contextmanager
import builtins
from pathlib import Path
from typing import Any, Generator
from unittest.mock import MagicMock
import tempfile

import pytest
from rich.console import Console


def pytest_configure(config):
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


@contextmanager
def acb_depends_context(injection_map: dict[type, Any]) -> Generator[None, None, None]:
    """Legacy no-op context manager (ACB removed)."""
    yield


@pytest.fixture
def mock_console() -> MagicMock:
    """Fixture providing a mock console for tests."""
    return MagicMock(spec=Console)


@pytest.fixture
def acb_di_fixture(mock_console: MagicMock) -> Generator[dict[type, Any], None, None]:
    """Fixture providing ACB dependency injection setup for tests.

    Usage:
        def test_something(acb_di_fixture):
            # DI is automatically set up
            coordinator = SessionCoordinator(console=acb_di_fixture[Console], ...)
    """
    with acb_depends_context({Console: mock_console}):
        yield {Console: mock_console}


# ============================================================================
# Pattern 1: DI-Aware Fixtures for Manager Classes
# ============================================================================
# These fixtures support testing ACB-based manager classes that use
# @depends.inject decorator. They register mock services with the DI
# system so managers can be instantiated without passing parameters.
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
def temp_pkg_path() -> Generator[Path, None, None]:
    """Temporary package path for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture(autouse=True)
def reset_hook_lock_manager_singleton():
    """Reset HookLockManager singleton before and after each test.

    This fixture automatically runs for all tests and ensures that
    HookLockManager starts fresh for each test, preventing state leakage
    from other tests. The singleton pattern is preserved but the instance
    is reset between tests.
    """
    # Import here to avoid circular imports
    from crackerjack.executors.hook_lock_manager import HookLockManager

    # Get existing instance if any and cancel its heartbeat tasks to prevent resource leaks
    try:
        existing_instance = HookLockManager._instance
        if existing_instance is not None:
            import asyncio
            # Cancel any existing heartbeat tasks to prevent resource leaks
            for task in existing_instance._heartbeat_tasks.values():
                if task and not task.done():
                    task.cancel()
                    # Wait briefly for task cancellation to complete
                    try:
                        asyncio.get_event_loop().run_until_complete(task)  # This will raise CancelledError
                    except (asyncio.CancelledError, RuntimeError):
                        # Expected when task is cancelled
                        pass
            # Clear the heartbeat tasks dictionary
            existing_instance._heartbeat_tasks.clear()
            # Clear active locks
            existing_instance._active_global_locks.clear()
    except Exception:
        # If no instance exists or any other error, continue
        pass

    # Reset singleton before test
    HookLockManager._instance = None
    HookLockManager._initialized = False

    yield

    # Reset singleton after test
    HookLockManager._instance = None
    HookLockManager._initialized = False


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
) -> Generator[tuple[dict[type, Any], Path], None, None]:
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

    yield injection_map, temp_pkg_path


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
) -> Generator[tuple[dict[type, Any], Path], None, None]:
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
    from crackerjack.services.monitoring.performance_cache import (
        FileSystemCache,
        GitOperationCache,
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

    yield injection_map, temp_pkg_path
