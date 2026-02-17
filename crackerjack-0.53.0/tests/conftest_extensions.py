"""Test utilities and fixtures for Crackerjack tests."""

import asyncio
import tempfile
from pathlib import Path
from typing import Any, Dict, Generator, List
from unittest.mock import MagicMock

import pytest
from _pytest.fixtures import FixtureRequest

from crackerjack.config import CrackerjackSettings
from crackerjack.core.console import CrackerjackConsole
from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.core.timeout_manager import AsyncTimeoutManager, TimeoutConfig
from crackerjack.core.workflow_orchestrator import WorkflowPipeline


class TestUtilities:
    """Utility functions for tests."""

    @staticmethod
    def create_mock_options(**kwargs: Any) -> MagicMock:
        """Create a mock options object with specified attributes."""
        options = MagicMock()
        for key, value in kwargs.items():
            setattr(options, key, value)
        return options

    @staticmethod
    def create_temp_project_structure() -> Path:
        """Create a temporary project structure for testing."""
        temp_dir = Path(tempfile.mkdtemp(prefix="crackerjack_test_project_"))

        # Create basic project files
        pyproject_content = """[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "test-project"
version = "0.1.0"
description = "Test project for crackerjack"
requires-python = ">=3.13"
"""
        (temp_dir / "pyproject.toml").write_text(pyproject_content)

        # Create a basic Python file
        (temp_dir / "main.py").write_text("#!/usr/bin/env python3\n\ndef main():\n    print('Hello, world!')\n\nif __name__ == '__main__':\n    main()\n")

        # Create a basic test file
        (temp_dir / "test_main.py").write_text("def test_main():\n    assert True\n")

        return temp_dir

    @staticmethod
    def create_mock_settings(**kwargs: Any) -> CrackerjackSettings:
        """Create a mock settings object with specified attributes."""
        settings = CrackerjackSettings()
        for key, value in kwargs.items():
            if hasattr(settings, key):
                setattr(getattr(settings, key), value)
        return settings

    @staticmethod
    def run_async(coro):
        """Run an async coroutine in a sync context."""
        try:
            loop = asyncio.get_running_loop()
            # If we're already in a loop, schedule the coroutine in a new thread
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        except RuntimeError:
            # No event loop running, safe to use asyncio.run
            return asyncio.run(coro)


@pytest.fixture
def temp_project_path() -> Generator[Path, None, None]:
    """Create a temporary project path for testing."""
    temp_path = TestUtilities.create_temp_project_structure()
    yield temp_path
    import shutil
    shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def mock_options() -> MagicMock:
    """Create a mock options object."""
    return TestUtilities.create_mock_options()


@pytest.fixture
def mock_console() -> MagicMock:
    """Create a mock console."""
    return MagicMock()


@pytest.fixture
def sample_timeout_config() -> TimeoutConfig:
    """Create a sample timeout configuration."""
    return TimeoutConfig(
        default_timeout=10.0,
        max_retries=2,
        base_retry_delay=0.1,
        failure_threshold=3,
        recovery_timeout=1.0,
        half_open_max_calls=2,
    )


@pytest.fixture
def async_timeout_manager(sample_timeout_config: TimeoutConfig) -> AsyncTimeoutManager:
    """Create an AsyncTimeoutManager instance."""
    return AsyncTimeoutManager(config=sample_timeout_config)


@pytest.fixture
def session_coordinator(mock_console: MagicMock, temp_project_path: Path) -> SessionCoordinator:
    """Create a SessionCoordinator instance."""
    return SessionCoordinator(
        console=mock_console,
        pkg_path=temp_project_path,
    )


@pytest.fixture
def phase_coordinator(
    mock_console: MagicMock,
    temp_project_path: Path,
    session_coordinator: SessionCoordinator
) -> PhaseCoordinator:
    """Create a PhaseCoordinator instance."""
    return PhaseCoordinator(
        console=mock_console,
        pkg_path=temp_project_path,
        session=session_coordinator,
    )


@pytest.fixture
def workflow_pipeline(
    mock_console: MagicMock,
    temp_project_path: Path,
    session_coordinator: SessionCoordinator,
    phase_coordinator: PhaseCoordinator
) -> WorkflowPipeline:
    """Create a WorkflowPipeline instance."""
    settings = CrackerjackSettings()
    return WorkflowPipeline(
        console=mock_console,
        pkg_path=temp_project_path,
        settings=settings,
        session=session_coordinator,
        phases=phase_coordinator,
    )


@pytest.fixture
def test_data() -> Dict[str, Any]:
    """Provide sample test data."""
    return {
        "simple_dict": {"key1": "value1", "key2": "value2"},
        "simple_list": [1, 2, 3, 4, 5],
        "nested_dict": {
            "level1": {
                "level2": {
                    "value": "deep_value"
                }
            }
        },
        "mixed_list": [
            {"name": "item1", "value": 10},
            {"name": "item2", "value": 20},
        ]
    }


@pytest.fixture
def mock_settings() -> CrackerjackSettings:
    """Create a mock settings object."""
    return CrackerjackSettings()


@pytest.fixture
def async_test_utility():
    """Provide utility for running async code in tests."""
    return TestUtilities.run_async


class MockFactory:
    """Factory for creating various mock objects."""

    @staticmethod
    def create_mock_git_service() -> MagicMock:
        """Create a mock GitService."""
        mock = MagicMock()
        mock.get_current_branch.return_value = "main"
        mock.is_repo_dirty.return_value = False
        mock.get_uncommitted_files.return_value = []
        return mock

    @staticmethod
    def create_mock_filesystem_service() -> MagicMock:
        """Create a mock FileSystemService."""
        mock = MagicMock()
        mock.read_file.return_value = "# Sample file content"
        mock.write_file.return_value = True
        mock.file_exists.return_value = True
        mock.list_directory.return_value = ["file1.py", "file2.py"]
        return mock

    @staticmethod
    def create_mock_hook_manager() -> MagicMock:
        """Create a mock HookManager."""
        mock = MagicMock()
        mock.run_fast_hooks.return_value = True
        mock.run_comprehensive_hooks.return_value = True
        return mock

    @staticmethod
    def create_mock_test_manager() -> MagicMock:
        """Create a mock TestManager."""
        mock = MagicMock()
        mock.run_tests.return_value = True
        mock.validate_test_environment.return_value = True
        mock.get_coverage.return_value = {"total_coverage": 95.0}
        return mock

    @staticmethod
    def create_mock_publish_manager() -> MagicMock:
        """Create a mock PublishManager."""
        mock = MagicMock()
        mock.publish_package.return_value = True
        mock.validate_publish_prerequisites.return_value = True
        return mock


@pytest.fixture
def mock_factory() -> MockFactory:
    """Provide a mock factory."""
    return MockFactory()


@pytest.fixture
def mock_git_service(mock_factory: MockFactory) -> MagicMock:
    """Create a mock GitService."""
    return mock_factory.create_mock_git_service()


@pytest.fixture
def mock_filesystem_service(mock_factory: MockFactory) -> MagicMock:
    """Create a mock FileSystemService."""
    return mock_factory.create_mock_filesystem_service()


@pytest.fixture
def mock_hook_manager(mock_factory: MockFactory) -> MagicMock:
    """Create a mock HookManager."""
    return mock_factory.create_mock_hook_manager()


@pytest.fixture
def mock_test_manager(mock_factory: MockFactory) -> MagicMock:
    """Create a mock TestManager."""
    return mock_factory.create_mock_test_manager()


@pytest.fixture
def mock_publish_manager(mock_factory: MockFactory) -> MagicMock:
    """Create a mock PublishManager."""
    return mock_factory.create_mock_publish_manager()


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "unit: marks tests as unit tests"
    )
    config.addinivalue_line(
        "markers", "integration: marks tests as integration tests"
    )
    config.addinivalue_line(
        "markers", "performance: marks tests as performance tests"
    )
    config.addinivalue_line(
        "markers", "e2e: marks tests as end-to-end tests"
    )


class TestAssertions:
    """Custom test assertions."""

    @staticmethod
    def assert_contains_subset(actual: Dict[str, Any], expected_subset: Dict[str, Any]) -> None:
        """Assert that actual dictionary contains the expected subset."""
        for key, value in expected_subset.items():
            assert key in actual, f"Key '{key}' not found in actual dictionary"
            assert actual[key] == value, f"Value mismatch for key '{key}': expected {value}, got {actual[key]}"

    @staticmethod
    def assert_async_operation_times_out(coro, timeout: float = 0.1) -> None:
        """Assert that an async operation times out."""
        import asyncio
        try:
            # Try to run the coroutine with a short timeout
            result = asyncio.run(asyncio.wait_for(coro, timeout=timeout))
            # If we reach here, the operation didn't timeout as expected
            raise AssertionError(f"Expected operation to timeout after {timeout}s, but it completed with result: {result}")
        except asyncio.TimeoutError:
            # This is expected
            pass

    @staticmethod
    def assert_async_operation_completes_successfully(coro, expected_result=None) -> None:
        """Assert that an async operation completes successfully."""
        import asyncio
        try:
            result = asyncio.run(coro)
            if expected_result is not None:
                assert result == expected_result
        except Exception as e:
            raise AssertionError(f"Expected operation to complete successfully, but it raised: {e}")


@pytest.fixture
def test_assertions() -> TestAssertions:
    """Provide custom test assertions."""
    return TestAssertions()


class TimingHelper:
    """Helper for timing operations."""

    @staticmethod
    def time_execution(func, *args, **kwargs) -> tuple[Any, float]:
        """Time the execution of a function."""
        start_time = asyncio.get_event_loop().time() if asyncio._get_running_loop() else time.time()
        result = func(*args, **kwargs)
        end_time = asyncio.get_event_loop().time() if asyncio._get_running_loop() else time.time()
        return result, end_time - start_time

    @staticmethod
    async def time_async_execution(coro) -> tuple[Any, float]:
        """Time the execution of an async coroutine."""
        start_time = asyncio.get_event_loop().time()
        result = await coro
        end_time = asyncio.get_event_loop().time()
        return result, end_time - start_time


@pytest.fixture
def timing_helper() -> TimingHelper:
    """Provide timing helper utilities."""
    return TimingHelper()
