#!/usr/bin/env python3
"""Integration tests for MCP Crackerjack tools.

These tests verify that the MCP tools properly integrate with CrackerjackIntegration
and handle the exact scenarios that caused the original issue.
"""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastmcp import FastMCP
from session_mgmt_mcp.tools.crackerjack_tools import register_crackerjack_tools


class TestMCPCrackerjackToolRegistration:
    """Test MCP tool registration and basic functionality."""

    @pytest.fixture
    async def mcp_server(self):
        """Create MCP server with crackerjack tools registered."""
        mcp = FastMCP("test-crackerjack")
        register_crackerjack_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    async def test_tools_registered(self, mcp_server):
        """Test that crackerjack tools are properly registered."""
        # Get list of registered tools
        tools = mcp_server.list_tools()
        tool_names = [tool["name"] for tool in tools]

        # Should have crackerjack tools
        expected_tools = ["execute_crackerjack_command", "crackerjack_run"]

        for tool_name in expected_tools:
            assert tool_name in tool_names, f"Tool '{tool_name}' not registered"

    @pytest.mark.asyncio
    async def test_execute_crackerjack_command_tool_exists(self, mcp_server):
        """Test that execute_crackerjack_command tool is accessible."""
        tools = mcp_server.list_tools()

        # Find the execute_crackerjack_command tool
        execute_tool = next(
            (tool for tool in tools if tool["name"] == "execute_crackerjack_command"),
            None,
        )

        assert execute_tool is not None, "execute_crackerjack_command tool not found"

        # Check tool has expected parameters
        expected_params = [
            "command",
            "args",
            "working_directory",
            "timeout",
            "ai_agent_mode",
        ]
        tool_params = list(execute_tool["inputSchema"]["properties"].keys())

        for param in expected_params:
            assert param in tool_params, f"Parameter '{param}' missing from tool schema"


class TestMCPToolExecution:
    """Test actual MCP tool execution scenarios."""

    @pytest.fixture
    async def mcp_server(self):
        """Create MCP server with crackerjack tools."""
        mcp = FastMCP("test-crackerjack")
        register_crackerjack_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch(
        "session_mgmt_mcp.crackerjack_integration.CrackerjackIntegration.execute_crackerjack_command"
    )
    async def test_execute_crackerjack_command_tool_execution(
        self, mock_execute, mcp_server
    ):
        """Test execute_crackerjack_command MCP tool execution."""
        # Setup mock result
        from datetime import datetime

        from session_mgmt_mcp.crackerjack_integration import CrackerjackResult

        mock_result = CrackerjackResult(
            command="lint",
            exit_code=0,
            stdout="All checks passed",
            stderr="",
            execution_time=1.5,
            timestamp=datetime.now(),
            working_directory=".",
            parsed_data={},
            quality_metrics={"lint_score": 95.0},
            test_results=[],
            memory_insights=["Code quality looks good"],
        )
        mock_execute.return_value = mock_result

        # Get the tool function
        tools = {tool["name"]: tool for tool in mcp_server.list_tools()}
        tools["execute_crackerjack_command"]

        # Execute the tool via MCP
        result = await mcp_server.call_tool(
            "execute_crackerjack_command", {"command": "lint", "working_directory": "."}
        )

        # Verify the integration method was called correctly
        mock_execute.assert_called_once_with(
            "lint",
            None,  # args split to None when empty
            ".",  # working_directory
            300,  # default timeout
            False,  # default ai_agent_mode
        )

        # Verify result format (should be formatted string)
        assert isinstance(result, str)
        assert "Crackerjack lint executed" in result
        assert "Status: Success" in result
        assert "All checks passed" in result

    @pytest.mark.asyncio
    @patch(
        "session_mgmt_mcp.crackerjack_integration.CrackerjackIntegration.execute_crackerjack_command"
    )
    async def test_tool_handles_execution_error(self, mock_execute, mcp_server):
        """Test MCP tool handles CrackerjackIntegration errors gracefully."""
        # Setup mock to raise the original error
        mock_execute.side_effect = AttributeError(
            "'CrackerjackIntegration' object has no attribute 'execute_command'"
        )

        # Execute the tool
        result = await mcp_server.call_tool(
            "execute_crackerjack_command", {"command": "lint"}
        )

        # Should handle the error gracefully and return error message
        assert isinstance(result, str)
        assert "Crackerjack execution failed" in result
        assert "execute_command" in result

    @pytest.mark.asyncio
    @patch(
        "session_mgmt_mcp.crackerjack_integration.CrackerjackIntegration.execute_crackerjack_command"
    )
    async def test_tool_with_args_and_options(self, mock_execute, mcp_server):
        """Test MCP tool with various arguments and options."""
        from datetime import datetime

        from session_mgmt_mcp.crackerjack_integration import CrackerjackResult

        mock_result = CrackerjackResult(
            command="test",
            exit_code=0,
            stdout="Tests passed",
            stderr="",
            execution_time=5.0,
            timestamp=datetime.now(),
            working_directory="/tmp",
            parsed_data={},
            quality_metrics={"test_pass_rate": 100.0},
            test_results=[],
            memory_insights=["All tests are passing"],
        )
        mock_execute.return_value = mock_result

        # Execute with various options
        result = await mcp_server.call_tool(
            "execute_crackerjack_command",
            {
                "command": "test",
                "args": "--verbose --parallel",
                "working_directory": "/tmp",
                "timeout": 120,
                "ai_agent_mode": True,
            },
        )

        # Verify integration was called with correct parameters
        mock_execute.assert_called_once_with(
            "test",
            ["--verbose", "--parallel"],  # args should be split
            "/tmp",
            120,
            True,
        )

        # Verify result includes metrics and insights
        assert (
            "test_pass_rate: 100.0" in result.lower()
            or "Test Pass Rate: 100.0" in result
        )
        assert "All tests are passing" in result

    @pytest.mark.asyncio
    @patch(
        "session_mgmt_mcp.crackerjack_integration.CrackerjackIntegration.execute_crackerjack_command"
    )
    async def test_crackerjack_run_tool(self, mock_execute, mcp_server):
        """Test the crackerjack_run MCP tool."""
        from datetime import datetime

        from session_mgmt_mcp.crackerjack_integration import CrackerjackResult

        mock_result = CrackerjackResult(
            command="check",
            exit_code=0,
            stdout="Check completed",
            stderr="",
            execution_time=3.0,
            timestamp=datetime.now(),
            working_directory=".",
            parsed_data={},
            quality_metrics={"complexity_score": 85.0},
            test_results=[],
            memory_insights=["Code complexity is acceptable"],
        )
        mock_execute.return_value = mock_result

        # Execute crackerjack_run tool
        result = await mcp_server.call_tool("crackerjack_run", {"command": "check"})

        # Should call the integration method
        mock_execute.assert_called_once()

        # Should format result as enhanced run
        assert "Enhanced Crackerjack Run" in result
        assert "Check completed" in result


class TestErrorHandlingAndRecovery:
    """Test error handling scenarios that caused the original issues."""

    @pytest.fixture
    async def mcp_server(self):
        """Create MCP server with crackerjack tools."""
        mcp = FastMCP("test-error-handling")
        register_crackerjack_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    async def test_missing_execute_command_error(self, mcp_server):
        """Test handling of missing execute_command method error."""
        # Simulate the exact error we encountered
        with patch(
            "session_mgmt_mcp.crackerjack_integration.CrackerjackIntegration"
        ) as mock_class:
            # Create instance that's missing execute_command
            mock_instance = Mock()
            # Deliberately don't add execute_command method
            mock_class.return_value = mock_instance

            # This should be handled gracefully
            result = await mcp_server.call_tool(
                "execute_crackerjack_command", {"command": "lint"}
            )

            # Should return error message, not crash
            assert isinstance(result, str)
            assert "failed" in result.lower() or "error" in result.lower()

    @pytest.mark.asyncio
    async def test_import_error_handling(self, mcp_server):
        """Test handling of import errors."""
        # Simulate ImportError when importing CrackerjackIntegration
        with patch(
            "builtins.__import__",
            side_effect=ImportError("No module named 'crackerjack_integration'"),
        ):
            result = await mcp_server.call_tool(
                "execute_crackerjack_command", {"command": "lint"}
            )

            # Should handle import error gracefully
            assert "not available" in result.lower() or "install" in result.lower()

    @pytest.mark.asyncio
    @patch(
        "session_mgmt_mcp.crackerjack_integration.CrackerjackIntegration.execute_crackerjack_command"
    )
    async def test_timeout_error_handling(self, mock_execute, mcp_server):
        """Test handling of timeout errors."""
        # Simulate timeout
        mock_execute.side_effect = TimeoutError("Command timed out")

        result = await mcp_server.call_tool(
            "execute_crackerjack_command", {"command": "test", "timeout": 1}
        )

        # Should handle timeout gracefully
        assert isinstance(result, str)
        assert "failed" in result.lower() or "timeout" in result.lower()

    @pytest.mark.asyncio
    @patch(
        "session_mgmt_mcp.crackerjack_integration.CrackerjackIntegration.execute_crackerjack_command"
    )
    async def test_command_structure_error_handling(self, mock_execute, mcp_server):
        """Test handling of command structure errors (the original crackerjack error)."""
        from datetime import datetime

        from session_mgmt_mcp.crackerjack_integration import CrackerjackResult

        # Simulate the original error: "Got unexpected extra argument (lint)"
        mock_result = CrackerjackResult(
            command="lint",
            exit_code=2,  # Error exit code
            stdout="",
            stderr="Usage: crackerjack [OPTIONS]\nTry 'crackerjack --help' for help.\n╭─ Error ──────────────╮\n│ Got unexpected extra argument (lint) │",
            execution_time=0.1,
            timestamp=datetime.now(),
            working_directory=".",
            parsed_data={},
            quality_metrics={},
            test_results=[],
            memory_insights=["Command structure error detected"],
        )
        mock_execute.return_value = mock_result

        result = await mcp_server.call_tool(
            "execute_crackerjack_command", {"command": "lint"}
        )

        # Should show the error but not crash
        assert "Status: Failed" in result
        assert "exit code: 2" in result
        # Should include the error message
        assert "unexpected extra argument" in result


class TestRealIntegration:
    """Test with real CrackerjackIntegration (mocked subprocess calls)."""

    @pytest.fixture
    async def mcp_server(self):
        """Create MCP server with real crackerjack tools."""
        mcp = FastMCP("test-real-integration")
        register_crackerjack_tools(mcp)
        return mcp

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_real_integration_with_mocked_subprocess(
        self, mock_create_subprocess, mcp_server
    ):
        """Test with real CrackerjackIntegration but mocked subprocess calls."""
        # Setup mock subprocess
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"All hooks passed successfully", b"")
        mock_process.returncode = 0
        mock_create_subprocess.return_value = mock_process

        # Execute the tool
        result = await mcp_server.call_tool(
            "execute_crackerjack_command", {"command": "lint", "working_directory": "."}
        )

        # Verify subprocess was called with correct command structure
        mock_create_subprocess.assert_called_once()
        call_args = mock_create_subprocess.call_args

        # Should call with crackerjack --fast, NOT crackerjack lint
        expected_cmd = ["crackerjack", "--fast"]
        assert call_args[0] == tuple(expected_cmd), (
            f"Expected {expected_cmd}, got {call_args[0]}"
        )

        # Verify working directory
        assert call_args[1]["cwd"] == "."

        # Verify result format
        assert "Status: Success" in result
        assert "All hooks passed successfully" in result

    @pytest.mark.asyncio
    @patch("asyncio.create_subprocess_exec")
    async def test_all_command_mappings(self, mock_create_subprocess, mcp_server):
        """Test all command mappings work correctly."""
        mock_process = AsyncMock()
        mock_process.communicate.return_value = (b"success", b"")
        mock_process.returncode = 0
        mock_create_subprocess.return_value = mock_process

        # Test command mappings
        test_cases = [
            ("lint", ["crackerjack", "--fast"]),
            ("check", ["crackerjack", "--comp"]),
            ("test", ["crackerjack", "--test"]),
            ("format", ["crackerjack", "--fast"]),
            ("typecheck", ["crackerjack", "--comp"]),
            ("clean", ["crackerjack", "--clean"]),
            ("all", ["crackerjack", "--all"]),
        ]

        for command, expected_cmd in test_cases:
            mock_create_subprocess.reset_mock()

            result = await mcp_server.call_tool(
                "execute_crackerjack_command", {"command": command}
            )

            # Verify correct command was called
            call_args = mock_create_subprocess.call_args
            assert call_args[0] == tuple(expected_cmd), (
                f"Command '{command}' mapped incorrectly: expected {expected_cmd}, got {call_args[0]}"
            )

            # Verify result
            assert "Status: Success" in result

    @pytest.mark.asyncio
    @patch("subprocess.run")
    async def test_execute_command_method_called_correctly(self, mock_run, mcp_server):
        """Test that execute_command method works when called by external code."""
        # This simulates how crackerjack might call the execute_command method
        from session_mgmt_mcp.crackerjack_integration import CrackerjackIntegration

        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = "success"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        # Direct call to execute_command (as crackerjack would do)
        integration = CrackerjackIntegration()
        result = integration.execute_command(["crackerjack", "--help"])

        # Should work without AttributeError
        assert isinstance(result, dict)
        assert result["success"] is True
        assert result["returncode"] == 0


class TestProtocolCompliance:
    """Test compliance with external protocols."""

    def test_command_runner_protocol_compliance(self):
        """Test that CrackerjackIntegration implements CommandRunner protocol."""
        from session_mgmt_mcp.crackerjack_integration import CrackerjackIntegration

        integration = CrackerjackIntegration()

        # Should have execute_command method with correct signature
        assert hasattr(integration, "execute_command")

        import inspect

        sig = inspect.signature(integration.execute_command)

        # Should accept cmd: list[str]
        assert "cmd" in sig.parameters
        assert sig.parameters["cmd"].annotation == list[str]

    def test_can_be_used_as_command_runner(self):
        """Test that instance can be used where CommandRunner is expected."""
        from session_mgmt_mcp.crackerjack_integration import CrackerjackIntegration

        def use_command_runner(runner):
            """Function that expects a CommandRunner-like object."""
            # This is how external code might use it
            return runner.execute_command(["test", "command"])

        integration = CrackerjackIntegration()

        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "test"
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            # Should work without errors
            result = use_command_runner(integration)
            assert isinstance(result, dict)


if __name__ == "__main__":
    pytest.main([__file__])
