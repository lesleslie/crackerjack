#!/usr/bin/env python3
"""Simple functional tests for session management tools.

These tests verify the core functionality without complex fixture dependencies.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
from session_mgmt_mcp.tools.memory_tools import register_memory_tools
from session_mgmt_mcp.tools.search_tools import register_search_tools

# Import the actual tools
from session_mgmt_mcp.tools.session_tools import register_session_tools


class MockMCP:
    """Simple mock MCP server for testing."""

    def __init__(self):
        self.tools = {}

    def tool(self, *args, **kwargs):
        """Mock tool decorator."""

        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


@pytest.fixture
def mock_mcp():
    """Create a mock MCP server."""
    return MockMCP()


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.mark.asyncio
async def test_session_init_and_end(mock_mcp, temp_dir):
    """Test basic session initialization and ending."""
    # Register tools
    register_session_tools(mock_mcp)
    register_memory_tools(mock_mcp)
    register_search_tools(mock_mcp)

    # Get the tools
    init_tool = mock_mcp.tools.get("init")
    end_tool = mock_mcp.tools.get("end")

    assert init_tool is not None, "init tool should be registered"
    assert end_tool is not None, "end tool should be registered"

    # Test initialization
    with patch.dict("os.environ", {"PWD": str(temp_dir)}):
        init_result = await init_tool(working_directory=str(temp_dir))

    assert isinstance(init_result, str), "init should return a string"
    assert len(init_result) > 0, "init result should not be empty"

    # Test ending
    end_result = await end_tool()
    assert isinstance(end_result, str), "end should return a string"
    assert len(end_result) > 0, "end result should not be empty"


@pytest.mark.asyncio
async def test_reflection_storage_and_search(mock_mcp, temp_dir):
    """Test storing and searching reflections."""
    # Register tools
    register_session_tools(mock_mcp)
    register_memory_tools(mock_mcp)
    register_search_tools(mock_mcp)

    # Get the tools
    store_tool = mock_mcp.tools.get("store_reflection")
    search_tool = mock_mcp.tools.get("quick_search")

    assert store_tool is not None, "store_reflection tool should be registered"
    assert search_tool is not None, "quick_search tool should be registered"

    # Test storing a reflection
    store_result = await store_tool(
        content="This is a test reflection for storage", tags=["test", "storage"]
    )

    assert isinstance(store_result, str), "store_reflection should return a string"
    assert len(store_result) > 0, "store result should not be empty"

    # Test searching for the reflection
    search_result = await search_tool(
        query="test reflection",
        min_score=0.1,  # Low threshold for testing
    )

    assert isinstance(search_result, str), "quick_search should return a string"
    assert len(search_result) > 0, "search result should not be empty"


@pytest.mark.asyncio
async def test_checkpoint_tool(mock_mcp, temp_dir):
    """Test the checkpoint tool."""
    # Register tools
    register_session_tools(mock_mcp)
    register_memory_tools(mock_mcp)
    register_search_tools(mock_mcp)

    # Get the tool
    checkpoint_tool = mock_mcp.tools.get("checkpoint")

    assert checkpoint_tool is not None, "checkpoint tool should be registered"

    # Test checkpoint
    checkpoint_result = await checkpoint_tool()

    assert isinstance(checkpoint_result, str), "checkpoint should return a string"
    assert len(checkpoint_result) > 0, "checkpoint result should not be empty"


@pytest.mark.asyncio
async def test_status_tool(mock_mcp, temp_dir):
    """Test the status tool."""
    # Register tools
    register_session_tools(mock_mcp)
    register_memory_tools(mock_mcp)
    register_search_tools(mock_mcp)

    # Get the tool
    status_tool = mock_mcp.tools.get("status")

    assert status_tool is not None, "status tool should be registered"

    # Test status
    with patch.dict("os.environ", {"PWD": str(temp_dir)}):
        status_result = await status_tool(working_directory=str(temp_dir))

    assert isinstance(status_result, str), "status should return a string"
    assert len(status_result) > 0, "status result should not be empty"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
