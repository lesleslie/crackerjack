"""Advanced MCP server testing fixtures with async patterns.

Provides comprehensive fixtures for testing the session management MCP server
with proper async/await patterns, mock FastMCP instances, and database isolation.
"""

import asyncio
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from session_mgmt_mcp.reflection_tools import ReflectionDatabase


class MockFastMCP:
    """Mock FastMCP server for testing MCP tools."""

    def __init__(self) -> None:
        self.tools = {}
        self.prompts = {}
        self.resources = {}

    def tool(self, name: str | None = None, description: str | None = None):
        """Mock tool decorator."""

        def decorator(func):
            tool_name = name or func.__name__
            self.tools[tool_name] = func
            return func

        return decorator

    def prompt(self, name: str | None = None, description: str | None = None):
        """Mock prompt decorator."""

        def decorator(func):
            prompt_name = name or func.__name__
            self.prompts[prompt_name] = func
            return func

        return decorator


@pytest.fixture
def mock_mcp_server():
    """Mock MCP server instance for testing."""
    return MockFastMCP()


@pytest.fixture
async def isolated_database():
    """Create isolated test database."""
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test.db"

        # Create isolated ReflectionDatabase
        db = ReflectionDatabase(str(db_path))
        await db.initialize()

        yield db

        # Cleanup
        await db.close()


@pytest.fixture
def mock_session_permissions():
    """Mock session permissions manager."""
    with patch("session_mgmt_mcp.server.SessionPermissionsManager") as mock_class:
        mock_instance = Mock()
        mock_instance.is_operation_trusted.return_value = True
        mock_instance.trust_operation.return_value = None
        mock_instance.get_trusted_operations.return_value = set()
        mock_instance.get_permission_summary.return_value = {
            "trusted_operations": 0,
            "permission_level": "basic",
        }
        mock_class.return_value = mock_instance
        yield mock_instance


@pytest.fixture
def sample_conversation_data():
    """Sample conversation data for testing."""
    return {
        "conversation_id": "test-conv-123",
        "user_query": "How do I test async functions?",
        "assistant_response": "Use pytest-asyncio with @pytest.mark.asyncio",
        "timestamp": datetime.now().isoformat(),
        "project": "session-mgmt-mcp",
        "session_id": "test-session-456",
        "embedding": [0.1] * 384,  # Mock embedding vector
    }


@pytest.fixture
def sample_reflection_data():
    """Sample reflection data for testing."""
    return {
        "content": "Testing async MCP tools requires proper fixture isolation",
        "tags": ["testing", "async", "mcp"],
        "project": "session-mgmt-mcp",
        "timestamp": datetime.now().isoformat(),
        "embedding": [0.2] * 384,  # Mock embedding vector
    }


@pytest.fixture
async def populated_test_database(
    isolated_database,
    sample_conversation_data,
    sample_reflection_data,
):
    """Database with test data populated."""
    db = isolated_database

    # Add sample conversation
    await db.store_conversation(
        conversation_id=sample_conversation_data["conversation_id"],
        user_query=sample_conversation_data["user_query"],
        assistant_response=sample_conversation_data["assistant_response"],
        project=sample_conversation_data["project"],
        session_id=sample_conversation_data["session_id"],
    )

    # Add sample reflection
    await db.store_reflection(
        content=sample_reflection_data["content"],
        tags=sample_reflection_data["tags"],
        project=sample_reflection_data["project"],
    )

    return db


@pytest.fixture
def mock_embedding_service():
    """Mock embedding service for testing."""
    with patch("session_mgmt_mcp.reflection_tools.generate_embedding") as mock:
        # Return consistent mock embeddings
        mock.return_value = [0.1] * 384
        yield mock


@pytest.fixture
def temporary_project_structure():
    """Create temporary project structure for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        project_root = Path(temp_dir)

        # Create basic project structure
        (project_root / "src").mkdir()
        (project_root / "tests").mkdir()
        (project_root / ".git").mkdir()
        (project_root / "pyproject.toml").write_text("""
[project]
name = "test-project"
version = "0.1.0"
""")
        (project_root / "README.md").write_text("# Test Project")

        yield project_root


class AsyncTestCase:
    """Base class for async test cases with common utilities."""

    @pytest.fixture(autouse=True)
    def setup_async_test(self):
        """Auto-setup for async tests."""
        self.mock_calls = []

    async def assert_async_called_with(self, mock_async_func, *args, **kwargs):
        """Assert async mock was called with specific arguments."""
        mock_async_func.assert_called_with(*args, **kwargs)

    async def wait_for_condition(self, condition_func, timeout=5.0):
        """Wait for a condition to become true with timeout."""
        end_time = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < end_time:
            if await condition_func():
                return True
            await asyncio.sleep(0.1)
        return False


@pytest.fixture
def async_test_utils():
    """Utility functions for async testing."""
    return AsyncTestCase()


@pytest.fixture
def performance_metrics_collector():
    """Collect performance metrics during tests."""
    metrics = {"database_operations": [], "memory_usage": [], "execution_times": {}}

    def record_db_operation(operation: str, duration: float) -> None:
        metrics["database_operations"].append(
            {
                "operation": operation,
                "duration": duration,
                "timestamp": datetime.now().isoformat(),
            },
        )

    def record_execution_time(operation: str, duration: float) -> None:
        metrics["execution_times"][operation] = duration

    metrics["record_db_operation"] = record_db_operation
    metrics["record_execution_time"] = record_execution_time

    return metrics
