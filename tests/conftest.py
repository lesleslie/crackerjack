"""Global pytest configuration and fixtures for session-mgmt-mcp testing.

This module provides comprehensive test fixtures for:
- MCP server testing
- Database operations
- Session management
- Authentication and permissions
- Performance benchmarking
"""

import asyncio
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import duckdb
import pytest

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from session_mgmt_mcp.reflection_tools import ReflectionDatabase

# Import with fallback for testing environments
try:
    from session_mgmt_mcp.server import SessionPermissionsManager, mcp
except ImportError:
    print("Warning: FastMCP not available in test environment, using mocks")

    # Create mock SessionPermissionsManager for testing
    class SessionPermissionsManager:
        def __init__(self, session_id="test") -> None:
            self.session_id = session_id
            self.trusted_operations = set()

        def is_operation_trusted(self, operation):
            return operation in self.trusted_operations

        def add_trusted_operation(self, operation):
            self.trusted_operations.add(operation)

    # Create mock mcp object
    class MockMCP:
        def tool(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def prompt(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

    mcp = MockMCP()
# Import test fixtures with error handling
try:
    from tests.fixtures.data_factories import (
        ProjectDataFactory,
        ReflectionDataFactory,
        SessionDataFactory,
        UserDataFactory,
    )
except ImportError:
    # Create minimal mocks for testing when fixtures aren't available
    print("Warning: Test fixtures not available, using minimal mocks")

    class ProjectDataFactory:
        @staticmethod
        def build(**kwargs):
            return {"name": "test-project", "path": "/tmp/test"}

    class ReflectionDataFactory:
        @staticmethod
        def build(**kwargs):
            return {"content": "test reflection", "tags": ["test"]}

    class SessionDataFactory:
        @staticmethod
        def build(**kwargs):
            return {"session_id": "test-123", "active": True}

    class UserDataFactory:
        @staticmethod
        def build(**kwargs):
            return {"user_id": "test-user", "name": "Test User"}


# Pytest configuration
def pytest_configure(config):
    """Configure pytest with custom settings and markers."""
    config.addinivalue_line(
        "markers",
        "vcr: mark test to use VCR cassettes for HTTP recording",
    )
    config.addinivalue_line(
        "markers",
        "freeze_time: mark test to freeze time for deterministic testing",
    )
    config.addinivalue_line(
        "markers",
        "temp_dir: mark test that requires temporary directory",
    )


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for the test session."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    if not loop.is_closed():
        loop.close()


# Environment and Configuration Fixtures
@pytest.fixture(scope="session")
def test_env_vars():
    """Set test environment variables."""
    original_env = os.environ.copy()

    # Set test environment
    test_vars = {
        "TESTING": "true",
        "CLAUDE_SESSION_TEST_MODE": "true",
        "PWD": str(Path("/tmp/test-session-mgmt")),
        "PYTHONPATH": str(project_root),
    }

    for key, value in test_vars.items():
        os.environ[key] = value

    yield test_vars

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def temp_working_dir():
    """Create temporary working directory for tests."""
    temp_path = Path(tempfile.mkdtemp(prefix="session_mgmt_test_"))
    original_cwd = Path.cwd()

    try:
        os.chdir(temp_path)
        yield temp_path
    finally:
        os.chdir(original_cwd)
        shutil.rmtree(temp_path, ignore_errors=True)


@pytest.fixture
def temp_home_dir():
    """Create temporary home directory structure."""
    temp_home = Path(tempfile.mkdtemp(prefix="test_home_"))

    # Create necessary subdirectories
    (temp_home / ".claude").mkdir()
    (temp_home / ".claude" / "data").mkdir()
    (temp_home / "Projects").mkdir()
    (temp_home / "Projects" / "claude").mkdir()
    (temp_home / "Projects" / "claude" / "logs").mkdir()

    with patch.dict(os.environ, {"HOME": str(temp_home)}):
        yield temp_home

    shutil.rmtree(temp_home, ignore_errors=True)


# Database Fixtures
@pytest.fixture
def temp_database():
    """Create temporary DuckDB database for testing."""
    db_path = Path(tempfile.mkdtemp()) / "test.db"
    db_connection = duckdb.connect(str(db_path))

    yield db_connection

    db_connection.close()
    if db_path.exists():
        db_path.unlink()
        db_path.parent.rmdir()


@pytest.fixture
async def reflection_database(temp_home_dir):
    """Create ReflectionDatabase instance for testing."""
    db_path = temp_home_dir / ".claude" / "data" / "test_reflections.db"
    db = ReflectionDatabase(str(db_path))

    # Initialize database schema
    await db._ensure_tables()

    yield db

    # Cleanup
    try:
        if db.conn:
            db.conn.close()
        if db_path.exists():
            db_path.unlink()
    except Exception:
        pass


# Session Management Fixtures
@pytest.fixture
def session_permissions():
    """Create SessionPermissionsManager instance."""
    manager = SessionPermissionsManager()

    # Reset to clean state
    manager.trusted_operations.clear()
    manager.auto_checkpoint = False
    manager.checkpoint_frequency = 300

    yield manager

    # Cleanup
    manager.trusted_operations.clear()


@pytest.fixture
def mock_mcp_server():
    """Mock MCP server for testing tools."""
    mock_server = Mock()
    mock_server.list_tools = Mock(return_value=[])
    mock_server.call_tool = AsyncMock()

    return mock_server


@pytest.fixture
async def mcp_test_client():
    """Create test client for MCP server."""
    # Import the actual MCP instance
    return mcp

    # Setup any necessary test configuration


# Data Factory Fixtures
@pytest.fixture
def session_data():
    """Generate test session data."""
    return SessionDataFactory()


@pytest.fixture
def reflection_data():
    """Generate test reflection data."""
    return ReflectionDataFactory()


@pytest.fixture
def user_data():
    """Generate test user data."""
    return UserDataFactory()


@pytest.fixture
def project_data():
    """Generate test project data."""
    return ProjectDataFactory()


@pytest.fixture
def sample_reflections():
    """Sample reflection data for testing."""
    return [
        {
            "content": "Implemented user authentication system with JWT tokens",
            "tags": ["authentication", "jwt", "security"],
            "project": "test-project",
            "timestamp": datetime.now(),
        },
        {
            "content": "Fixed database connection pooling issue causing timeouts",
            "tags": ["database", "performance", "bug-fix"],
            "project": "test-project",
            "timestamp": datetime.now() - timedelta(hours=1),
        },
        {
            "content": "Refactored API endpoints to use async/await pattern",
            "tags": ["api", "async", "refactoring"],
            "project": "another-project",
            "timestamp": datetime.now() - timedelta(days=1),
        },
    ]


# Mock Fixtures
@pytest.fixture
def mock_subprocess():
    """Mock subprocess operations."""
    with patch("subprocess.run") as mock_run, patch("subprocess.Popen") as mock_popen:
        # Configure common successful responses
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = "success"
        mock_run.return_value.stderr = ""

        mock_process = Mock()
        mock_process.returncode = 0
        mock_process.stdout = "success"
        mock_process.stderr = ""
        mock_popen.return_value = mock_process

        yield {"run": mock_run, "popen": mock_popen}


@pytest.fixture
def mock_file_operations():
    """Mock file system operations."""
    with (
        patch("pathlib.Path.exists") as mock_exists,
        patch("pathlib.Path.is_file") as mock_is_file,
        patch("pathlib.Path.is_dir") as mock_is_dir,
        patch("builtins.open", create=True) as mock_open,
    ):
        mock_exists.return_value = True
        mock_is_file.return_value = True
        mock_is_dir.return_value = False

        yield {
            "exists": mock_exists,
            "is_file": mock_is_file,
            "is_dir": mock_is_dir,
            "open": mock_open,
        }


@pytest.fixture
def mock_git_operations():
    """Mock git operations."""
    with patch("subprocess.run") as mock_run:

        def git_side_effect(*args, **kwargs):
            cmd = args[0] if args else []

            if "git status --porcelain" in " ".join(cmd):
                mock_run.return_value.stdout = "M file.py\n?? new_file.py"
                mock_run.return_value.returncode = 0
            elif "git commit" in " ".join(cmd):
                mock_run.return_value.stdout = "[main abc1234] Test commit"
                mock_run.return_value.returncode = 0
            elif "git log" in " ".join(cmd):
                mock_run.return_value.stdout = "abc1234 Test commit message"
                mock_run.return_value.returncode = 0
            else:
                mock_run.return_value.stdout = "success"
                mock_run.return_value.returncode = 0

            return mock_run.return_value

        mock_run.side_effect = git_side_effect
        yield mock_run


# Performance Testing Fixtures
@pytest.fixture
def performance_monitor():
    """Monitor for performance testing."""
    import time

    import psutil

    class PerformanceMonitor:
        def __init__(self) -> None:
            self.process = psutil.Process()
            self.start_time = None
            self.start_memory = None

        def start_monitoring(self) -> None:
            self.start_time = time.time()
            self.start_memory = self.process.memory_info().rss / 1024 / 1024  # MB

        def stop_monitoring(self):
            end_time = time.time()
            end_memory = self.process.memory_info().rss / 1024 / 1024  # MB

            return {
                "duration": end_time - self.start_time,
                "memory_delta": end_memory - self.start_memory,
                "peak_memory": end_memory,
            }

    return PerformanceMonitor()


# Time-based Testing Fixtures
@pytest.fixture
def freeze_time():
    """Freeze time for consistent testing."""
    from freezegun import freeze_time as _freeze_time

    with _freeze_time("2024-01-15 12:00:00") as frozen_time:
        yield frozen_time


@pytest.fixture
def current_timestamp():
    """Provide consistent timestamp for testing."""
    return datetime(2024, 1, 15, 12, 0, 0)


# Cleanup Fixtures
@pytest.fixture(autouse=True)
def cleanup_after_test():
    """Automatic cleanup after each test."""
    yield

    # Clean up any temporary files or state
    temp_dirs = Path("/tmp").glob("session_mgmt_test_*")
    for temp_dir in temp_dirs:
        if temp_dir.is_dir():
            shutil.rmtree(temp_dir, ignore_errors=True)


# Integration Test Fixtures
@pytest.fixture
def integration_test_env(temp_working_dir, temp_home_dir, test_env_vars):
    """Complete integration test environment."""
    # Create realistic project structure
    project_dir = temp_working_dir / "test-project"
    project_dir.mkdir()

    # Create basic files
    (project_dir / "README.md").write_text("# Test Project")
    (project_dir / "src").mkdir()
    (project_dir / "src" / "main.py").write_text("print('Hello, World!')")
    (project_dir / "tests").mkdir()
    (project_dir / "pyproject.toml").write_text("""
[project]
name = "test-project"
version = "0.1.0"
""")

    # Initialize git repository
    os.chdir(project_dir)

    return {
        "project_dir": project_dir,
        "home_dir": temp_home_dir,
        "working_dir": temp_working_dir,
    }


# Concurrency Testing Fixtures
@pytest.fixture
def concurrent_executor():
    """Executor for concurrent testing."""
    from concurrent.futures import ThreadPoolExecutor

    executor = ThreadPoolExecutor(max_workers=10)
    yield executor
    executor.shutdown(wait=True)


# Error Injection Fixtures
@pytest.fixture
def error_injector():
    """Inject controlled errors for testing error handling."""

    class ErrorInjector:
        def __init__(self) -> None:
            self.should_fail = False
            self.error_type = Exception
            self.error_message = "Injected test error"

        def maybe_raise(self) -> None:
            if self.should_fail:
                raise self.error_type(self.error_message)

        def configure(
            self,
            should_fail=True,
            error_type=Exception,
            message="Test error",
        ) -> None:
            self.should_fail = should_fail
            self.error_type = error_type
            self.error_message = message

    return ErrorInjector()


# Async Testing Utilities
@pytest.fixture
def async_mock():
    """Create async mock for testing async functions."""
    return AsyncMock()


@pytest.fixture
async def async_context_manager():
    """Async context manager for testing."""

    class AsyncContextManager:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    return AsyncContextManager()
