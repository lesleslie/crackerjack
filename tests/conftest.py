#!/usr/bin/env python3
"""Global test configuration and fixtures for session-mgmt-mcp tests."""

import asyncio
import os
import tempfile
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import duckdb
import numpy as np
import pytest
from fastmcp import FastMCP
from session_mgmt_mcp.reflection_tools import ReflectionDatabase


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop]:
    """Create session-scoped event loop for async tests."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    yield loop

    # Clean up pending tasks
    if not loop.is_closed():
        # Cancel all pending tasks
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()

        # Wait for tasks to be cancelled
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

        loop.close()


@pytest.fixture
async def temp_db_path() -> AsyncGenerator[str]:
    """Provide temporary database path that's cleaned up after test."""
    with tempfile.NamedTemporaryFile(suffix=".duckdb", delete=False) as tmp:
        db_path = tmp.name

    yield db_path

    # Cleanup
    try:
        db_path_obj = Path(db_path)
        if db_path_obj.exists():
            db_path_obj.unlink()
    except (OSError, PermissionError):
        # On Windows, file might still be locked
        pass


@pytest.fixture
async def temp_claude_dir() -> AsyncGenerator[Path]:
    """Provide temporary ~/.claude directory structure."""
    with tempfile.TemporaryDirectory() as temp_dir:
        claude_dir = Path(temp_dir) / ".claude"
        claude_dir.mkdir()

        # Create expected subdirectories
        (claude_dir / "data").mkdir()
        (claude_dir / "logs").mkdir()

        # Patch the home directory
        with patch.dict(os.environ, {"HOME": str(Path(temp_dir))}):
            with patch(
                "os.path.expanduser",
                lambda path: path.replace("~", str(Path(temp_dir))),
            ):
                yield claude_dir


@pytest.fixture
async def reflection_db(temp_db_path: str) -> AsyncGenerator[ReflectionDatabase]:
    """Provide initialized ReflectionDatabase instance."""
    db = ReflectionDatabase(db_path=temp_db_path)

    try:
        await db.initialize()
        yield db
    finally:
        db.close()


@pytest.fixture
async def reflection_db_with_data(
    reflection_db: ReflectionDatabase,
) -> AsyncGenerator[ReflectionDatabase]:
    """Provide ReflectionDatabase with test data."""
    # Add some test conversations
    test_conversations = [
        "How do I implement async/await patterns in Python?",
        "Setting up pytest fixtures for database testing",
        "Best practices for MCP server development",
        "DuckDB vector operations and similarity search",
        "FastMCP tool registration and async handlers",
    ]

    conversation_ids = []
    for content in test_conversations:
        conv_id = await reflection_db.store_conversation(
            content, {"project": "test-project"}
        )
        conversation_ids.append(conv_id)

    # Add some test reflections
    test_reflections = [
        (
            "Always use context managers for database connections",
            ["database", "patterns"],
        ),
        (
            "Async fixtures require careful setup in pytest",
            ["testing", "async", "pytest"],
        ),
        ("MCP tools should handle errors gracefully", ["mcp", "error-handling"]),
    ]

    reflection_ids = []
    for content, tags in test_reflections:
        refl_id = await reflection_db.store_reflection(content, tags)
        reflection_ids.append(refl_id)

    # Store IDs for test reference
    reflection_db._test_conversation_ids = conversation_ids
    reflection_db._test_reflection_ids = reflection_ids

    return reflection_db


@pytest.fixture
def mock_onnx_session() -> Mock:
    """Provide mock ONNX session for embedding tests."""
    mock_session = Mock()
    # Mock returns a 384-dimensional vector
    rng = np.random.default_rng(42)
    mock_session.run.return_value = [rng.random((1, 384)).astype(np.float32)]
    return mock_session


@pytest.fixture
def mock_tokenizer() -> Mock:
    """Provide mock tokenizer for embedding tests."""
    mock_tokenizer = Mock()
    mock_tokenizer.return_value = {
        "input_ids": [[1, 2, 3, 4, 5]],
        "attention_mask": [[1, 1, 1, 1, 1]],
    }
    return mock_tokenizer


@pytest.fixture
async def mock_mcp_server() -> AsyncGenerator[Mock]:
    """Provide mock MCP server for testing."""
    mock_server = Mock(spec=FastMCP)
    mock_server.tool = Mock()
    mock_server.prompt = Mock()

    # Mock async context manager behavior
    mock_server.__aenter__ = AsyncMock(return_value=mock_server)
    mock_server.__aexit__ = AsyncMock(return_value=None)

    return mock_server


@pytest.fixture
def clean_environment() -> Generator[dict[str, Any]]:
    """Provide clean environment with common patches."""
    original_env = os.environ.copy()

    # Set up test environment
    test_env = {
        "TESTING": "1",
        "LOG_LEVEL": "DEBUG",
    }

    # Remove potentially problematic env vars
    env_to_remove = ["PWD", "OLDPWD", "VIRTUAL_ENV"]

    try:
        # Update environment
        os.environ.update(test_env)
        for key in env_to_remove:
            os.environ.pop(key, None)

        yield test_env

    finally:
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)


@pytest.fixture
async def async_client() -> AsyncGenerator[Mock]:
    """Provide async client for MCP communication testing."""
    client = Mock()

    # Mock async methods
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.call_tool = AsyncMock()
    client.list_tools = AsyncMock(return_value=[])

    return client


@pytest.fixture
def sample_embedding() -> np.ndarray:
    """Provide sample embedding vector for testing."""
    # Create a consistent sample embedding
    rng = np.random.default_rng(42)
    return rng.random((384,)).astype(np.float32)


@pytest.fixture
def mock_embeddings_disabled():
    """Fixture to disable embeddings for testing fallback behavior."""
    with patch("session_mgmt_mcp.reflection_tools.ONNX_AVAILABLE", False):
        yield


@pytest.fixture
async def duckdb_connection() -> AsyncGenerator[duckdb.DuckDBPyConnection]:
    """Provide in-memory DuckDB connection for testing."""
    conn = duckdb.connect(":memory:")

    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def mock_file_operations():
    """Mock file system operations for testing."""
    mocks = {}

    with (
        patch("pathlib.Path.mkdir") as mock_mkdir,
        patch("pathlib.Path.exists") as mock_exists,
        patch("pathlib.Path.unlink") as mock_unlink,
        patch("os.path.exists") as mock_os_exists,
    ):
        mock_exists.return_value = True
        mock_os_exists.return_value = True

        mocks["mkdir"] = mock_mkdir
        mocks["exists"] = mock_exists
        mocks["unlink"] = mock_unlink
        mocks["os_exists"] = mock_os_exists

        yield mocks


# Async test markers and utilities
@pytest.fixture(autouse=True)
def detect_asyncio_leaks():
    """Automatically detect asyncio task leaks in tests."""
    # Only check for leaks if there's a running event loop
    try:
        initial_tasks = len(asyncio.all_tasks())
    except RuntimeError:
        # No event loop running, skip leak detection
        yield
        return

    yield

    # Check for task leaks after test
    try:
        final_tasks = asyncio.all_tasks()
        if len(final_tasks) > initial_tasks:
            # Allow a small buffer for cleanup tasks
            if len(final_tasks) > initial_tasks + 2:
                task_names = [task.get_name() for task in final_tasks]
                pytest.fail(f"Potential task leak detected. Active tasks: {task_names}")
    except RuntimeError:
        # Event loop closed, no need to check
        pass


@pytest.fixture
def performance_baseline() -> dict[str, float]:
    """Provide performance baselines for benchmark tests."""
    return {
        "db_insert_time": 0.1,  # 100ms per insert
        "embedding_generation": 0.5,  # 500ms per embedding
        "search_query": 0.2,  # 200ms per search
        "bulk_operation": 1.0,  # 1s for bulk operations
    }


# Helper functions for test data generation
def generate_test_conversation(
    content: str = "Test conversation content",
    project: str = "test-project",
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Generate test conversation data."""
    return {
        "content": content,
        "project": project,
        "timestamp": timestamp or "2024-01-01T12:00:00Z",
    }


def generate_test_reflection(
    content: str = "Test reflection content",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Generate test reflection data."""
    return {
        "content": content,
        "tags": tags or ["test"],
    }


# Pytest configuration hooks
def pytest_configure(config):
    """Configure pytest with custom settings."""
    # Register custom markers
    config.addinivalue_line(
        "markers", "async_test: mark test as requiring async event loop"
    )
    config.addinivalue_line("markers", "db_test: mark test as requiring database")
    config.addinivalue_line(
        "markers", "embedding_test: mark test as requiring embeddings"
    )
    config.addinivalue_line("markers", "mcp_test: mark test as MCP server test")


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on markers and environment."""
    # Add async marker to all async tests
    for item in items:
        if asyncio.iscoroutinefunction(item.function):
            item.add_marker(pytest.mark.async_test)

        # Add markers based on test file location
        if "integration" in str(item.fspath):
            item.add_marker("integration")
        elif "unit" in str(item.fspath):
            item.add_marker("unit")
        elif "functional" in str(item.fspath):
            item.add_marker("functional")


# Async test timeout configuration
pytestmark = pytest.mark.asyncio(scope="function")
