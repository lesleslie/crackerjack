import asyncio
import os
import tempfile
import time
import typing as t
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest
from pytest import Config, Item, Parser

# Import crackerjack modules for testing
from crackerjack.core.container import DependencyContainer
from crackerjack.models.protocols import (
    HookManager,
    PublishManager,
    TestManagerProtocol,
)
from crackerjack.services.filesystem import FileSystemService
from crackerjack.services.git import GitService
from crackerjack.services.unified_config import CrackerjackConfig


def pytest_configure(config: Config) -> None:
    config.addinivalue_line(
        "markers",
        "benchmark: mark test as a benchmark (disables parallel execution)",
    )
    if not hasattr(config, "workerinput"):
        pass


def pytest_addoption(parser: Parser) -> None:
    parser.addoption(
        "--benchmark",
        action="store_true",
        default=False,
        help="Run benchmark tests and disable parallelism",
    )


def pytest_collection_modifyitems(config: Config, items: list[Item]) -> None:
    benchmark_mode = t.cast("bool", config.getoption("--benchmark"))
    has_benchmark_tests = any(item.get_closest_marker("benchmark") for item in items)
    if benchmark_mode or has_benchmark_tests:
        has_worker = hasattr(config, "workerinput")
        try:
            num_processes = t.cast("int", config.getoption("numprocesses"))
            has_multi_processes = num_processes > 0
        except Exception:
            has_multi_processes = False
        if has_worker or has_multi_processes:
            config.option.numprocesses = 0


@pytest.hookimpl(trylast=True)
def pytest_runtest_setup(item: t.Any) -> None:
    item._start_time = time.time()


@pytest.hookimpl(trylast=True)
def pytest_runtest_teardown(item: t.Any) -> None:
    if hasattr(item, "_start_time"):
        duration = time.time() - item._start_time
        if duration > 10:
            pass
        else:
            pass


@pytest.hookimpl(trylast=True)
def pytest_runtest_protocol(item: t.Any) -> None:
    Path(".current_test").write_text(f"Current test: {item.name}")


def pytest_benchmark_compare_machine_info(
    machine_info: dict[str, t.Any],
    compared_benchmark: t.Any,
) -> bool:
    return True


def pytest_benchmark_generate_commit_info(config: Config) -> dict[str, t.Any]:
    return {"id": "current", "time": time.time(), "project_name": "crackerjack"}


# ============================================================================
# Test Fixtures and Factories
# ============================================================================


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    yield loop
    loop.close()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as temp_path:
        yield Path(temp_path)


@pytest.fixture
def temp_project_dir(temp_dir):
    """Create a temporary project directory structure."""
    project_dir = temp_dir / "test_project"
    project_dir.mkdir()

    # Create basic project structure
    (project_dir / "src").mkdir()
    (project_dir / "tests").mkdir()
    (project_dir / "pyproject.toml").write_text(
        """
[project]
name = "test-project"
version = "0.1.0"
description = "Test project"
    """.strip(),
    )

    # Create git repository
    os.chdir(project_dir)
    os.system("git init")
    os.system("git config user.email 'test@example.com'")
    os.system("git config user.name 'Test User'")

    return project_dir


@pytest.fixture
def mock_container():
    """Create a mock dependency injection container."""
    container = Mock(spec=DependencyContainer)

    # Mock services
    container.file_system_service.return_value = Mock(spec=FileSystemService)
    container.git_service.return_value = Mock(spec=GitService)

    # Mock managers
    container.hook_manager.return_value = Mock(spec=HookManager)
    container.test_manager.return_value = Mock(spec=TestManagerProtocol)
    container.publish_manager.return_value = Mock(spec=PublishManager)

    return container


@pytest.fixture
def sample_config():
    """Create sample crackerjack configuration."""
    return CrackerjackConfig(
        package_path=Path.cwd(),
        test_timeout=60,
        test_workers=2,
        skip_hooks=False,
    )


@pytest.fixture
def mock_hook_manager():
    """Create a mock hook manager."""
    manager = Mock(spec=HookManager)
    manager.run_fast_hooks.return_value = (True, [])
    manager.run_comprehensive_hooks.return_value = (True, [])
    manager.get_hook_results.return_value = []
    return manager


@pytest.fixture
def mock_test_manager():
    """Create a mock test manager."""
    manager = Mock(spec=TestManagerProtocol)
    manager.run_tests.return_value = (True, [])
    manager.get_test_results.return_value = []
    manager.get_coverage_percentage.return_value = 85.0
    return manager


@pytest.fixture
def mock_publish_manager():
    """Create a mock publish manager."""
    manager = Mock(spec=PublishManager)
    manager.bump_version.return_value = "1.0.1"
    manager.create_git_tag.return_value = None
    manager.publish_to_pypi.return_value = True
    return manager


@pytest.fixture
def mock_filesystem():
    """Create a mock filesystem service."""
    fs = Mock(spec=FileSystemService)
    fs.read_file.return_value = "file content"
    fs.write_file.return_value = None
    fs.file_exists.return_value = True
    fs.create_directory.return_value = None
    return fs


@pytest.fixture
def mock_git():
    """Create a mock git service."""
    git = Mock(spec=GitService)
    git.is_git_repo.return_value = True
    git.get_current_branch.return_value = "main"
    git.has_uncommitted_changes.return_value = False
    git.create_commit.return_value = None
    git.push_to_remote.return_value = None
    return git


@pytest.fixture
async def async_mock_container():
    """Create an async mock container for async tests."""
    container = AsyncMock(spec=DependencyContainer)

    # Mock async services
    container.async_hook_manager.return_value = AsyncMock()
    container.async_test_manager.return_value = AsyncMock()

    return container


@pytest.fixture
def sample_test_data():
    """Sample test data for various test scenarios."""
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


# ============================================================================
# Test Data Factories
# ============================================================================


class ConfigFactory:
    """Factory for creating test configurations."""

    @staticmethod
    def create_basic_config(**overrides):
        """Create basic configuration with optional overrides."""
        defaults = {
            "package_path": Path.cwd(),
            "test_timeout": 60,
            "test_workers": 2,
        }
        defaults.update(overrides)
        return CrackerjackConfig(**defaults)

    @staticmethod
    def create_ci_config():
        """Create configuration optimized for CI environment."""
        return ConfigFactory.create_basic_config(
            test_workers=4,
            test_timeout=120,
            skip_hooks=False,
        )

    @staticmethod
    def create_dev_config():
        """Create configuration for development environment."""
        return ConfigFactory.create_basic_config(test_workers=1, skip_hooks=True)


class HookResultFactory:
    """Factory for creating hook test results."""

    @staticmethod
    def create_passed_result(hook_name: str):
        """Create a passing hook result."""
        return {
            "hook_name": hook_name,
            "status": "passed",
            "duration": 0.5,
            "output": f"{hook_name} passed successfully",
            "error": None,
        }

    @staticmethod
    def create_failed_result(hook_name: str, error_msg: str):
        """Create a failing hook result."""
        return {
            "hook_name": hook_name,
            "status": "failed",
            "duration": 1.2,
            "output": f"{hook_name} failed",
            "error": error_msg,
        }


class TestResultFactory:
    """Factory for creating test results."""

    @staticmethod
    def create_passed_test(test_name: str):
        """Create a passing test result."""
        return {
            "test_name": test_name,
            "status": "passed",
            "duration": 0.1,
            "output": "test passed",
            "error": None,
        }

    @staticmethod
    def create_failed_test(test_name: str, error_msg: str):
        """Create a failing test result."""
        return {
            "test_name": test_name,
            "status": "failed",
            "duration": 0.3,
            "output": "test failed",
            "error": error_msg,
        }


# ============================================================================
# Async Test Utilities
# ============================================================================


@pytest.fixture
async def async_timeout():
    """Fixture to handle async test timeouts."""

    async def _timeout(coro, timeout_seconds=10):
        try:
            return await asyncio.wait_for(coro, timeout=timeout_seconds)
        except TimeoutError:
            pytest.fail(f"Async operation timed out after {timeout_seconds}s")

    return _timeout


# ============================================================================
# Performance Test Utilities
# ============================================================================


@pytest.fixture
def performance_timer():
    """Fixture for timing performance tests."""
    times = []

    def _timer():
        start = time.perf_counter()

        def stop():
            end = time.perf_counter()
            duration = end - start
            times.append(duration)
            return duration

        return stop

    _timer.times = times
    return _timer


# ============================================================================
# Security Test Utilities
# ============================================================================


@pytest.fixture
def security_test_data():
    """Test data for security testing."""
    return {
        "malicious_inputs": [
            "'; DROP TABLE users; --",
            "<script>alert('xss')</script>",
            "../../../etc/passwd",
            "$(rm -rf /)",
        ],
        "valid_inputs": [
            "normal_input",
            "test@example.com",
            "valid_filename.txt",
        ],
    }


# ============================================================================
# CI/CD Test Configuration Utilities
# ============================================================================


@pytest.fixture(scope="session")
def ci_environment():
    """Detect and configure for CI environment."""
    ci_indicators = [
        "CI",
        "CONTINUOUS_INTEGRATION",
        "GITHUB_ACTIONS",
        "GITLAB_CI",
        "JENKINS_URL",
        "TRAVIS",
        "CIRCLECI",
        "BUILDKITE",
    ]

    is_ci = any(os.getenv(indicator) for indicator in ci_indicators)

    return {
        "is_ci": is_ci,
        "provider": _detect_ci_provider(),
        "parallel_safe": _is_parallel_safe(),
        "timeout_multiplier": 3 if is_ci else 1,  # Longer timeouts in CI
    }


def _detect_ci_provider() -> str:
    """Detect which CI provider is being used."""
    if os.getenv("GITHUB_ACTIONS"):
        return "github_actions"
    if os.getenv("GITLAB_CI"):
        return "gitlab_ci"
    if os.getenv("JENKINS_URL"):
        return "jenkins"
    if os.getenv("TRAVIS"):
        return "travis"
    if os.getenv("CIRCLECI"):
        return "circleci"
    return "unknown"


def _is_parallel_safe():
    """Determine if parallel test execution is safe."""
    # Some CI environments have issues with parallel execution
    provider = _detect_ci_provider()
    return provider not in ["travis", "unknown"]


@pytest.fixture
def ci_config_factory():
    """Factory for creating CI-optimized configurations."""

    def create_ci_config(ci_env, **overrides):
        base_config = {
            "test_timeout": 60 * ci_env["timeout_multiplier"],
            "test_workers": 2 if ci_env["parallel_safe"] else 1,
            "verbose": ci_env["is_ci"],  # More verbose in CI
            "skip_hooks": False,  # Run all hooks in CI
        }
        base_config.update(overrides)
        return ConfigFactory.create_basic_config(**base_config)

    return create_ci_config


# ============================================================================
# Test Execution Control
# ============================================================================


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Setup test environment before any tests run."""
    # Ensure clean test state
    if Path(".current_test").exists():
        Path(".current_test").unlink()

    # Set environment variables for testing
    os.environ["CRACKERJACK_TESTING"] = "1"

    yield

    # Cleanup after all tests
    if Path(".current_test").exists():
        Path(".current_test").unlink()

    os.environ.pop("CRACKERJACK_TESTING", None)


@pytest.fixture
def test_isolation():
    """Ensure test isolation by changing to temp directory."""
    original_cwd = os.getcwd()

    with tempfile.TemporaryDirectory() as temp_dir:
        os.chdir(temp_dir)
        yield Path(temp_dir)

    os.chdir(original_cwd)


# ============================================================================
# Coverage and Quality Utilities
# ============================================================================


@pytest.fixture
def coverage_tracker():
    """Track coverage improvements during test execution."""
    coverage_data = {"initial": 0, "final": 0, "target": 42}

    # Would integrate with coverage.py in real implementation
    def record_coverage(percentage):
        coverage_data["final"] = percentage
        return percentage >= coverage_data["target"]

    coverage_tracker.record = record_coverage
    coverage_tracker.data = coverage_data
    return coverage_tracker


@pytest.fixture
def quality_metrics():
    """Track quality metrics during testing."""
    return {
        "test_count": 0,
        "failure_count": 0,
        "skip_count": 0,
        "error_count": 0,
        "duration": 0.0,
    }
