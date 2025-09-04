"""MCP server testing helpers and utilities.

Provides utilities for testing MCP tools, server functionality,
and message handling.
"""

import asyncio
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch


class MCPTestClient:
    """Test client for MCP server operations."""

    def __init__(self, mcp_server) -> None:
        self.mcp_server = mcp_server
        self.tools = {}
        self.call_history = []

    async def list_tools(self) -> list[dict[str, Any]]:
        """List available MCP tools."""
        # Get tools from the MCP server
        tools = []
        if hasattr(self.mcp_server, "list_tools"):
            tools = await self.mcp_server.list_tools()
        return tools

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Call an MCP tool with arguments."""
        call_record = {
            "tool_name": tool_name,
            "arguments": arguments,
            "timestamp": asyncio.get_event_loop().time(),
        }
        self.call_history.append(call_record)

        # Mock tool execution
        if hasattr(self.mcp_server, "call_tool"):
            result = await self.mcp_server.call_tool(tool_name, arguments)
        else:
            result = {"success": True, "data": f"Mock result for {tool_name}"}

        call_record["result"] = result
        return result

    def get_call_history(self, tool_name: str | None = None) -> list[dict[str, Any]]:
        """Get history of tool calls, optionally filtered by tool name."""
        if tool_name:
            return [
                call for call in self.call_history if call["tool_name"] == tool_name
            ]
        return self.call_history

    def clear_history(self):
        """Clear call history."""
        self.call_history.clear()


class MCPTestEnvironment:
    """Complete test environment for MCP server testing."""

    def __init__(self) -> None:
        self.temp_dirs = []
        self.mock_patches = []
        self.test_data = {}

    def setup_temp_workspace(self) -> Path:
        """Setup temporary workspace for testing."""
        temp_dir = Path(tempfile.mkdtemp(prefix="mcp_test_"))
        self.temp_dirs.append(temp_dir)

        # Create basic structure
        (temp_dir / "Projects").mkdir()
        (temp_dir / ".claude").mkdir()
        (temp_dir / ".claude" / "data").mkdir()
        (temp_dir / "logs").mkdir()

        return temp_dir

    def setup_mock_git_repo(self, path: Path):
        """Setup mock git repository for testing."""
        git_dir = path / ".git"
        git_dir.mkdir(exist_ok=True)

        # Create mock git files
        (git_dir / "HEAD").write_text("ref: refs/heads/main")
        (git_dir / "config").write_text("""[core]
	repositoryformatversion = 0
	filemode = true
	bare = false
	logallrefupdates = true
""")

        # Create some test files
        (path / "README.md").write_text("# Test Repository")
        (path / "src").mkdir(exist_ok=True)
        (path / "src" / "main.py").write_text("print('Hello, World!')")

    def add_mock_patch(self, target: str, **kwargs):
        """Add a mock patch to be cleaned up later."""
        patcher = patch(target, **kwargs)
        mock = patcher.start()
        self.mock_patches.append(patcher)
        return mock

    def cleanup(self):
        """Cleanup test environment."""
        # Stop all patches
        for patcher in self.mock_patches:
            patcher.stop()
        self.mock_patches.clear()

        # Remove temporary directories
        import shutil

        for temp_dir in self.temp_dirs:
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
        self.temp_dirs.clear()


async def simulate_session_workflow(
    mcp_client: MCPTestClient,
    project_path: str = "/tmp/test-project",
) -> dict[str, Any]:
    """Simulate a complete session management workflow."""
    workflow_results = {
        "init": None,
        "checkpoint": None,
        "end": None,
        "status_checks": [],
        "errors": [],
    }

    try:
        # 1. Initialize session
        init_result = await mcp_client.call_tool(
            "init",
            {"working_directory": project_path},
        )
        workflow_results["init"] = init_result

        # 2. Check status
        status_result = await mcp_client.call_tool("status", {})
        workflow_results["status_checks"].append(status_result)

        # 3. Create checkpoint
        checkpoint_result = await mcp_client.call_tool("checkpoint", {})
        workflow_results["checkpoint"] = checkpoint_result

        # 4. Check status again
        status_result = await mcp_client.call_tool("status", {})
        workflow_results["status_checks"].append(status_result)

        # 5. End session
        end_result = await mcp_client.call_tool("end", {})
        workflow_results["end"] = end_result

    except Exception as e:
        workflow_results["errors"].append(str(e))

    return workflow_results


def create_mock_reflection_database():
    """Create mock reflection database for testing."""
    mock_db = AsyncMock()

    # Mock database methods
    mock_db.store_reflection = AsyncMock(return_value=True)
    mock_db.search_reflections = AsyncMock(return_value=[])
    mock_db.get_reflection_stats = AsyncMock(
        return_value={"total_reflections": 0, "projects": 0, "date_range": None},
    )

    return mock_db


def create_test_session_permissions():
    """Create test session permissions manager."""
    from session_mgmt_mcp.server import SessionPermissionsManager

    permissions = SessionPermissionsManager()

    # Setup test state
    permissions.trusted_operations = {"test_operation", "safe_operation"}
    permissions.auto_checkpoint = True
    permissions.checkpoint_frequency = 300

    return permissions


class MockMCPServer:
    """Mock MCP server for testing."""

    def __init__(self) -> None:
        self.tools = {
            "init": self._mock_init,
            "checkpoint": self._mock_checkpoint,
            "end": self._mock_end,
            "status": self._mock_status,
            "reflect_on_past": self._mock_reflect_on_past,
            "store_reflection": self._mock_store_reflection,
        }
        self.state = {"initialized": False, "checkpoints": [], "reflections": []}

    async def list_tools(self):
        """List available tools."""
        return [
            {"name": name, "description": f"Mock {name} tool"} for name in self.tools
        ]

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]):
        """Call a tool."""
        if tool_name not in self.tools:
            return {"error": f"Tool {tool_name} not found"}

        handler = self.tools[tool_name]
        return await handler(arguments)

    async def _mock_init(self, args):
        """Mock init tool."""
        self.state["initialized"] = True
        return {
            "success": True,
            "working_directory": args.get("working_directory", "/tmp/test"),
            "quality_score": 0.85,
            "health_checks": {
                "database": True,
                "permissions": True,
                "toolkit_integration": True,
                "uv_available": True,
            },
        }

    async def _mock_checkpoint(self, args):
        """Mock checkpoint tool."""
        checkpoint = {
            "timestamp": asyncio.get_event_loop().time(),
            "quality_score": 0.90,
        }
        self.state["checkpoints"].append(checkpoint)

        return {
            "success": True,
            "checkpoint_created": True,
            "quality_score": checkpoint["quality_score"],
        }

    async def _mock_end(self, args):
        """Mock end tool."""
        return {
            "success": True,
            "session_ended": True,
            "handoff_created": True,
            "final_score": 0.88,
        }

    async def _mock_status(self, args):
        """Mock status tool."""
        return {
            "session_active": self.state["initialized"],
            "checkpoints_count": len(self.state["checkpoints"]),
            "reflections_count": len(self.state["reflections"]),
            "health_status": "healthy",
        }

    async def _mock_reflect_on_past(self, args):
        """Mock reflect on past tool."""
        query = args.get("query", "")
        return {
            "results": [
                {
                    "content": f'Mock reflection matching "{query}"',
                    "score": 0.95,
                    "project": "test-project",
                },
            ],
            "total_results": 1,
        }

    async def _mock_store_reflection(self, args):
        """Mock store reflection tool."""
        reflection = {
            "content": args.get("content", ""),
            "tags": args.get("tags", []),
            "timestamp": asyncio.get_event_loop().time(),
        }
        self.state["reflections"].append(reflection)

        return {"success": True, "reflection_id": len(self.state["reflections"])}


# Test assertion helpers


def assert_tool_call_made(
    mcp_client: MCPTestClient,
    tool_name: str,
    expected_args: dict | None = None,
):
    """Assert that a specific tool call was made."""
    calls = mcp_client.get_call_history(tool_name)
    assert len(calls) > 0, f"Expected tool '{tool_name}' to be called"

    if expected_args:
        latest_call = calls[-1]
        for key, expected_value in expected_args.items():
            assert key in latest_call["arguments"], (
                f"Expected argument '{key}' in tool call"
            )
            assert latest_call["arguments"][key] == expected_value, (
                f"Expected {key}={expected_value}, got {latest_call['arguments'][key]}"
            )


def assert_successful_tool_call(mcp_client: MCPTestClient, tool_name: str):
    """Assert that a tool call was successful."""
    calls = mcp_client.get_call_history(tool_name)
    assert len(calls) > 0, f"Expected tool '{tool_name}' to be called"

    latest_call = calls[-1]
    result = latest_call["result"]
    assert "error" not in result or not result["error"], (
        f"Tool call failed with error: {result.get('error')}"
    )


def assert_tool_call_count(
    mcp_client: MCPTestClient,
    tool_name: str,
    expected_count: int,
):
    """Assert the number of times a tool was called."""
    calls = mcp_client.get_call_history(tool_name)
    assert len(calls) == expected_count, (
        f"Expected {expected_count} calls to '{tool_name}', got {len(calls)}"
    )


# Performance testing helpers


class MCPPerformanceTracker:
    """Track performance metrics for MCP operations."""

    def __init__(self) -> None:
        self.metrics = {}
        self.start_times = {}

    def start_operation(self, operation_name: str):
        """Start tracking an operation."""
        self.start_times[operation_name] = asyncio.get_event_loop().time()

    def end_operation(self, operation_name: str):
        """End tracking an operation and record metrics."""
        if operation_name not in self.start_times:
            return

        duration = asyncio.get_event_loop().time() - self.start_times[operation_name]

        if operation_name not in self.metrics:
            self.metrics[operation_name] = []

        self.metrics[operation_name].append(duration)
        del self.start_times[operation_name]

    def get_average_duration(self, operation_name: str) -> float | None:
        """Get average duration for an operation."""
        if operation_name not in self.metrics or not self.metrics[operation_name]:
            return None

        durations = self.metrics[operation_name]
        return sum(durations) / len(durations)

    def get_operation_stats(self, operation_name: str) -> dict[str, float]:
        """Get comprehensive stats for an operation."""
        if operation_name not in self.metrics or not self.metrics[operation_name]:
            return {}

        durations = self.metrics[operation_name]
        return {
            "count": len(durations),
            "average": sum(durations) / len(durations),
            "min": min(durations),
            "max": max(durations),
            "total": sum(durations),
        }
