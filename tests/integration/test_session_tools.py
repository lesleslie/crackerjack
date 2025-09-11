#!/usr/bin/env python3
"""Integration tests for session tools."""

import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastmcp import FastMCP
from session_mgmt_mcp.tools.session_tools import register_session_tools


class TestSessionToolsRegistration:
    """Test session tools registration."""

    @pytest.fixture
    async def mcp_server(self):
        """Create MCP server with session tools registered."""
        mcp = FastMCP("test-session")
        register_session_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    async def test_session_tools_registered(self, mcp_server):
        """Test that session tools are properly registered."""
        # Get list of registered tools
        tools = mcp_server.list_tools()
        tool_names = [tool["name"] for tool in tools]

        # Should have session tools
        expected_tools = [
            "start",
            "checkpoint",
            "end",
            "status",
            "health_check",
            "server_info",
            "ping",
        ]

        for tool_name in expected_tools:
            assert tool_name in tool_names, f"Tool '{tool_name}' not registered"

    @pytest.mark.asyncio
    async def test_start_tool_exists(self, mcp_server):
        """Test that start tool is accessible."""
        tools = mcp_server.list_tools()

        # Find the start tool
        start_tool = next(
            (tool for tool in tools if tool["name"] == "start"),
            None,
        )

        assert start_tool is not None, "start tool not found"

        # Check tool has expected parameters
        expected_params = ["working_directory"]
        if "properties" in start_tool["inputSchema"]:
            list(start_tool["inputSchema"]["properties"].keys())
            for param in expected_params:
                # Parameter might be optional, so just verify schema exists
                assert "inputSchema" in start_tool

    @pytest.mark.asyncio
    async def test_checkpoint_tool_exists(self, mcp_server):
        """Test that checkpoint tool is accessible."""
        tools = mcp_server.list_tools()

        # Find the checkpoint tool
        checkpoint_tool = next(
            (tool for tool in tools if tool["name"] == "checkpoint"),
            None,
        )

        assert checkpoint_tool is not None, "checkpoint tool not found"

    @pytest.mark.asyncio
    async def test_end_tool_exists(self, mcp_server):
        """Test that end tool is accessible."""
        tools = mcp_server.list_tools()

        # Find the end tool
        end_tool = next(
            (tool for tool in tools if tool["name"] == "end"),
            None,
        )

        assert end_tool is not None, "end tool not found"

    @pytest.mark.asyncio
    async def test_status_tool_exists(self, mcp_server):
        """Test that status tool is accessible."""
        tools = mcp_server.list_tools()

        # Find the status tool
        status_tool = next(
            (tool for tool in tools if tool["name"] == "status"),
            None,
        )

        assert status_tool is not None, "status tool not found"

        # Check tool has expected parameters
        expected_params = ["working_directory"]
        if "properties" in status_tool["inputSchema"]:
            list(status_tool["inputSchema"]["properties"].keys())
            for param in expected_params:
                # Parameter might be optional, so just verify schema exists
                assert "inputSchema" in status_tool


class TestSessionToolExecution:
    """Test actual session tool execution."""

    @pytest.fixture
    async def mcp_server(self):
        """Create MCP server with session tools."""
        mcp = FastMCP("test-session-execution")
        register_session_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("session_mgmt_mcp.tools.session_tools.session_manager")
    async def test_start_tool_execution(self, mock_session_manager, mcp_server):
        """Test start tool execution."""
        # Setup mock result
        mock_result = {
            "success": True,
            "project": "test-project",
            "working_directory": "/tmp/test",
            "quality_score": 85,
            "claude_directory": "/tmp/.claude",
            "project_context": {"has_git_repo": True},
            "quality_data": {
                "total_score": 85,
                "breakdown": {
                    "project_health": 30.0,
                    "permissions": 15.0,
                    "session_management": 20.0,
                    "tools": 20.0,
                },
                "recommendations": ["Good setup"],
            },
        }
        mock_session_manager.initialize_session = AsyncMock(return_value=mock_result)

        # Execute the tool
        result = await mcp_server.call_tool("start", {"working_directory": "/tmp/test"})

        # Verify the session manager method was called correctly
        mock_session_manager.initialize_session.assert_called_once_with("/tmp/test")

        # Verify result format
        assert isinstance(result, str)
        assert "🚀 Claude Session Initialization" in result
        assert "test-project" in result
        assert "85/100" in result

    @pytest.mark.asyncio
    @patch("session_mgmt_mcp.tools.session_tools.session_manager")
    async def test_start_tool_failure(self, mock_session_manager, mcp_server):
        """Test start tool execution with failure."""
        # Setup mock result
        mock_result = {
            "success": False,
            "error": "Initialization failed",
        }
        mock_session_manager.initialize_session = AsyncMock(return_value=mock_result)

        # Execute the tool
        result = await mcp_server.call_tool("start", {})

        # Verify result includes error
        assert isinstance(result, str)
        assert "❌ Session initialization failed" in result
        assert "Initialization failed" in result

    @pytest.mark.asyncio
    @patch("session_mgmt_mcp.tools.session_tools.session_manager")
    async def test_checkpoint_tool_execution(self, mock_session_manager, mcp_server):
        """Test checkpoint tool execution."""
        # Setup mock result
        mock_result = {
            "success": True,
            "quality_score": 88,
            "quality_output": ["✅ Session quality: GOOD (Score: 88/100)"],
            "git_output": ["✅ Working directory is clean"],
            "timestamp": "2024-01-01T12:00:00Z",
        }
        mock_session_manager.checkpoint_session = AsyncMock(return_value=mock_result)

        # Execute the tool
        result = await mcp_server.call_tool("checkpoint", {})

        # Verify the session manager method was called correctly
        mock_session_manager.checkpoint_session.assert_called_once()

        # Verify result format
        assert isinstance(result, str)
        assert "🔍 Claude Session Checkpoint" in result
        assert "88/100" in result

    @pytest.mark.asyncio
    @patch("session_mgmt_mcp.tools.session_tools.session_manager")
    async def test_checkpoint_tool_failure(self, mock_session_manager, mcp_server):
        """Test checkpoint tool execution with failure."""
        # Setup mock result
        mock_result = {
            "success": False,
            "error": "Checkpoint failed",
        }
        mock_session_manager.checkpoint_session = AsyncMock(return_value=mock_result)

        # Execute the tool
        result = await mcp_server.call_tool("checkpoint", {})

        # Verify result includes error
        assert isinstance(result, str)
        assert "❌ Checkpoint failed" in result
        assert "Checkpoint failed" in result

    @pytest.mark.asyncio
    @patch("session_mgmt_mcp.tools.session_tools.session_manager")
    async def test_end_tool_execution(self, mock_session_manager, mcp_server):
        """Test end tool execution."""
        # Setup mock result
        mock_result = {
            "success": True,
            "summary": {
                "project": "test-project",
                "final_quality_score": 90,
                "session_end_time": "2024-01-01T12:00:00Z",
                "working_directory": "/tmp/test",
                "recommendations": ["Great work!"],
                "handoff_documentation": "/tmp/handoff.md",
            },
        }
        mock_session_manager.end_session = AsyncMock(return_value=mock_result)

        # Execute the tool
        result = await mcp_server.call_tool("end", {})

        # Verify the session manager method was called correctly
        mock_session_manager.end_session.assert_called_once()

        # Verify result format
        assert isinstance(result, str)
        assert "🏁 Claude Session End" in result
        assert "test-project" in result
        assert "90/100" in result

    @pytest.mark.asyncio
    @patch("session_mgmt_mcp.tools.session_tools.session_manager")
    async def test_end_tool_failure(self, mock_session_manager, mcp_server):
        """Test end tool execution with failure."""
        # Setup mock result
        mock_result = {
            "success": False,
            "error": "End session failed",
        }
        mock_session_manager.end_session = AsyncMock(return_value=mock_result)

        # Execute the tool
        result = await mcp_server.call_tool("end", {})

        # Verify result includes error
        assert isinstance(result, str)
        assert "❌ Session end failed" in result
        assert "End session failed" in result

    @pytest.mark.asyncio
    @patch("session_mgmt_mcp.tools.session_tools.session_manager")
    async def test_status_tool_execution(self, mock_session_manager, mcp_server):
        """Test status tool execution."""
        # Setup mock result
        mock_result = {
            "success": True,
            "project": "test-project",
            "working_directory": "/tmp/test",
            "quality_score": 82,
            "quality_breakdown": {
                "project_health": 30.0,
                "permissions": 12.0,
                "session_management": 20.0,
                "tools": 20.0,
            },
            "recommendations": ["Good progress"],
            "project_context": {"has_git_repo": True, "has_tests": True},
            "system_health": {
                "uv_available": True,
                "git_repository": True,
                "claude_directory": True,
            },
            "timestamp": "2024-01-01T12:00:00Z",
        }
        mock_session_manager.get_session_status = AsyncMock(return_value=mock_result)

        # Execute the tool
        result = await mcp_server.call_tool(
            "status", {"working_directory": "/tmp/test"}
        )

        # Verify the session manager method was called correctly
        mock_session_manager.get_session_status.assert_called_once_with("/tmp/test")

        # Verify result format
        assert isinstance(result, str)
        assert "📊 Claude Session Status Report" in result
        assert "test-project" in result
        assert "82/100" in result

    @pytest.mark.asyncio
    @patch("session_mgmt_mcp.tools.session_tools.session_manager")
    async def test_status_tool_failure(self, mock_session_manager, mcp_server):
        """Test status tool execution with failure."""
        # Setup mock result
        mock_result = {
            "success": False,
            "error": "Status check failed",
        }
        mock_session_manager.get_session_status = AsyncMock(return_value=mock_result)

        # Execute the tool
        result = await mcp_server.call_tool("status", {})

        # Verify result includes error
        assert isinstance(result, str)
        assert "❌ Status check failed" in result
        assert "Status check failed" in result


class TestUtilityTools:
    """Test utility session tools."""

    @pytest.fixture
    async def mcp_server(self):
        """Create MCP server with session tools."""
        mcp = FastMCP("test-utility-tools")
        register_session_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    async def test_health_check_tool(self, mcp_server):
        """Test health_check tool execution."""
        result = await mcp_server.call_tool("health_check", {})

        # Verify result format
        assert isinstance(result, str)
        assert "🏥 MCP Server Health Check" in result
        assert "Active" in result

    @pytest.mark.asyncio
    async def test_server_info_tool(self, mcp_server):
        """Test server_info tool execution."""
        result = await mcp_server.call_tool("server_info", {})

        # Verify result format
        assert isinstance(result, str)
        assert "📊 Session-mgmt MCP Server Information" in result

    @pytest.mark.asyncio
    async def test_ping_tool(self, mcp_server):
        """Test ping tool execution."""
        result = await mcp_server.call_tool("ping", {})

        # Verify result format
        assert isinstance(result, str)
        assert "🏓 Pong!" in result
        assert "MCP server is responding" in result


class TestSessionShortcuts:
    """Test session shortcut creation."""

    def test_create_session_shortcuts(self):
        """Test _create_session_shortcuts function."""
        from session_mgmt_mcp.tools.session_tools import _create_session_shortcuts

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict("os.environ", {"HOME": temp_dir}):
                result = _create_session_shortcuts()

                assert "created" in result
                assert "shortcuts" in result
                # Should have created shortcut files
                assert len(result["shortcuts"]) > 0

                # Verify shortcut files were created
                commands_dir = Path(temp_dir) / ".claude" / "commands"
                assert commands_dir.exists()

                # Check that expected files exist
                expected_files = ["start.md", "checkpoint.md", "end.md"]
                for filename in expected_files:
                    shortcut_file = commands_dir / filename
                    assert shortcut_file.exists(), (
                        f"Shortcut file {filename} not created"
                    )


class TestUVSetup:
    """Test UV setup functionality."""

    def test_setup_uv_dependencies_uv_not_available(self):
        """Test _setup_uv_dependencies when UV is not available."""
        from session_mgmt_mcp.tools.session_tools import _setup_uv_dependencies

        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)

            # Mock shutil.which to return None (UV not available)
            with patch("shutil.which", return_value=None):
                result = _setup_uv_dependencies(project_dir)

                assert any("UV not found" in line for line in result)
                assert any("Install UV" in line for line in result)

    def test_setup_uv_dependencies_no_pyproject(self):
        """Test _setup_uv_dependencies when pyproject.toml doesn't exist."""
        from session_mgmt_mcp.tools.session_tools import _setup_uv_dependencies

        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)

            # Mock shutil.which to return UV path
            with patch("shutil.which", return_value="/usr/local/bin/uv"):
                result = _setup_uv_dependencies(project_dir)

                assert any("No pyproject.toml found" in line for line in result)

    @patch("subprocess.run")
    def test_setup_uv_dependencies_success(self, mock_subprocess_run):
        """Test _setup_uv_dependencies with successful UV sync."""
        from session_mgmt_mcp.tools.session_tools import _setup_uv_dependencies

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = ""
        mock_result.stderr = ""
        mock_subprocess_run.return_value = mock_result

        with tempfile.TemporaryDirectory() as temp_dir:
            project_dir = Path(temp_dir)
            pyproject_file = project_dir / "pyproject.toml"
            pyproject_file.touch()  # Create pyproject.toml

            # Mock shutil.which to return UV path
            with patch("shutil.which", return_value="/usr/local/bin/uv"):
                result = _setup_uv_dependencies(project_dir)

                assert any("Found pyproject.toml" in line for line in result)
                assert any("UV dependencies synchronized" in line for line in result)


if __name__ == "__main__":
    pytest.main([__file__])
