import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from crackerjack.mcp.context import MCPServerConfig, MCPServerContext
from crackerjack.mcp.rate_limiter import RateLimitConfig


class TestMCPServerProtocol:
    @pytest.fixture
    def temp_project_path(self, tmp_path):
        return tmp_path / "test_project"

    @pytest.fixture
    def mcp_config(self, temp_project_path):
        temp_project_path.mkdir(exist_ok=True)
        return MCPServerConfig(
            project_path=temp_project_path,
            stdio_mode=True,
            rate_limit_config=RateLimitConfig(),
        )

    @pytest.fixture
    def mcp_context(self, mcp_config):
        return MCPServerContext(mcp_config)

    def test_mcp_server_imports(self) -> None:
        from crackerjack.mcp.server import MCP_AVAILABLE, FastMCP, mcp_app

        assert MCP_AVAILABLE is True
        assert FastMCP is not None
        assert mcp_app is not None
        assert hasattr(mcp_app, "run")

    def test_mcp_context_initialization(self, mcp_context) -> None:
        assert mcp_context.config is not None
        assert mcp_context._initialized is False

        stats = mcp_context.get_context_stats()
        assert stats["initialized"] is False
        assert stats["stdio_mode"] is True
        assert "project_path" in stats

    @pytest.mark.asyncio
    async def test_mcp_context_lifecycle(self, mcp_context) -> None:
        await mcp_context.initialize()

        assert mcp_context._initialized is True
        assert mcp_context.console is not None
        assert mcp_context.progress_dir.exists()

        stats = mcp_context.get_context_stats()
        assert stats["initialized"] is True
        assert stats["components"]["batched_saver"] is True

        await mcp_context.shutdown()
        assert mcp_context._initialized is False

    def test_job_id_validation(self, mcp_context) -> None:
        assert mcp_context.validate_job_id("abc123-def456") is True
        assert mcp_context.validate_job_id("job_123") is True
        assert (
            mcp_context.validate_job_id("a1b2c3d4-e5f6-7890-1234-567890abcdef") is True
        )

        assert mcp_context.validate_job_id("") is False
        assert mcp_context.validate_job_id("../path/traversal") is False
        assert mcp_context.validate_job_id("/absolute/path") is False
        assert mcp_context.validate_job_id("job with spaces") is False
        assert mcp_context.validate_job_id("job\nwith\nnewlines") is False

    def test_progress_file_creation(self, mcp_context) -> None:
        job_id = "test-job-123"
        progress_file = mcp_context.create_progress_file_path(job_id)

        assert progress_file.name == f"job-{job_id}.json"
        assert progress_file.parent == mcp_context.progress_dir

        with pytest.raises(ValueError, match="Invalid job_id"):
            mcp_context.create_progress_file_path("../invalid")

    def test_safe_print_stdio_mode(self, mcp_context) -> None:
        mcp_context.safe_print("This should be suppressed")

    @pytest.mark.asyncio
    async def test_batched_state_saver(self, mcp_context) -> None:
        await mcp_context.initialize()

        save_called = False

        def test_save() -> None:
            nonlocal save_called
            save_called = True

        await mcp_context.schedule_state_save("test_save", test_save)

        await asyncio.sleep(1.5)

        assert save_called is True

        await mcp_context.shutdown()


class TestMCPServerStartup:
    def test_mcp_server_process_starts(self) -> None:
        server_cmd = [sys.executable, "-m", "crackerjack", "--start-mcp-server"]

        process = subprocess.Popen(
            server_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=Path.cwd(),
        )

        try:
            time.sleep(1)

            assert process.poll() is None, "Server process exited unexpectedly"

        finally:
            process.terminate()
            process.wait(timeout=5)

    def test_mcp_server_protocol_response(self) -> None:
        server_cmd = [sys.executable, "-m", "crackerjack", "--start-mcp-server"]

        process = subprocess.Popen(
            server_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=Path.cwd(),
        )

        try:
            initialize_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"roots": {"listChanged": True}, "sampling": {}},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"},
                },
            }

            request_json = json.dumps(initialize_request) + "\n"
            process.stdin.write(request_json)
            process.stdin.flush()

            import select

            ready, _, _ = select.select([process.stdout], [], [], 10.0)

            assert ready, "No response received from server"

            response_line = process.stdout.readline()
            assert response_line.strip(), "Empty response received"

            response = json.loads(response_line)
            assert response.get("jsonrpc") == "2.0"
            assert response.get("id") == 1
            assert "result" in response
            assert "protocolVersion" in response["result"]
            assert "capabilities" in response["result"]
            assert "serverInfo" in response["result"]

        finally:
            process.terminate()
            process.wait(timeout=5)

    def test_mcp_server_tools_list(self) -> None:
        server_cmd = [sys.executable, "-m", "crackerjack", "--start-mcp-server"]

        process = subprocess.Popen(
            server_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=Path.cwd(),
        )

        try:
            initialize_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"roots": {"listChanged": True}},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"},
                },
            }

            process.stdin.write(json.dumps(initialize_request) + "\n")
            process.stdin.flush()

            import select

            ready, _, _ = select.select([process.stdout], [], [], 5.0)
            assert ready
            process.stdout.readline()

            initialized_notification = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
            }
            process.stdin.write(json.dumps(initialized_notification) + "\n")
            process.stdin.flush()
            time.sleep(0.5)

            tools_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            }

            process.stdin.write(json.dumps(tools_request) + "\n")
            process.stdin.flush()

            ready, _, _ = select.select([process.stdout], [], [], 5.0)
            assert ready, "No tools response received"

            tools_response_line = process.stdout.readline()
            tools_response = json.loads(tools_response_line)

            assert tools_response.get("jsonrpc") == "2.0"
            assert tools_response.get("id") == 2
            assert "result" in tools_response
            assert "tools" in tools_response["result"]

            tools = tools_response["result"]["tools"]
            assert len(tools) > 0, "No tools registered"

            tool_names = [tool["name"] for tool in tools]
            expected_tools = [
                "execute_crackerjack",
                "get_job_progress",
                "run_crackerjack_stage",
                "analyze_errors",
                "get_stage_status",
            ]

            for expected_tool in expected_tools:
                assert expected_tool in tool_names, f"Tool {expected_tool} not found"

        finally:
            process.terminate()
            process.wait(timeout=5)


class TestMCPServerTools:
    def test_mcp_options_creation(self) -> None:
        from crackerjack.mcp.server import MCPOptions

        options = MCPOptions()
        assert options.commit is False
        assert options.test is False
        assert options.ai_agent is True

        options = MCPOptions(test=True, verbose=True)
        assert options.test is True
        assert options.verbose is True

    def test_progress_tracking_functions(self) -> None:
        from crackerjack.mcp.server import _validate_job_id

        assert _validate_job_id("valid-job-123") is True
        assert _validate_job_id("") is False
        assert _validate_job_id("../invalid") is False

    @pytest.mark.asyncio
    async def test_context_initialization_in_server(self) -> None:
        from crackerjack.mcp.context import MCPServerConfig, MCPServerContext
        from crackerjack.mcp.server import _initialize_globals

        config = MCPServerConfig(project_path=Path.cwd())
        context = MCPServerContext(config)

        await context.initialize()

        _initialize_globals(context)

        from crackerjack.mcp.server import project_path

        assert project_path is not None

        await context.shutdown()


class TestMCPServerIntegration:
    def test_websocket_server_option(self) -> None:
        server_cmd = [sys.executable, "-m", "crackerjack", "--start-websocket-server"]

        process = subprocess.Popen(
            server_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=Path.cwd(),
        )

        try:
            time.sleep(2)

            if process.poll() is not None:
                stdout, stderr = process.communicate()
                assert "ImportError" not in stderr
                assert "ModuleNotFoundError" not in stderr

        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)

    def test_mcp_server_with_websocket_port(self) -> None:
        server_cmd = [
            sys.executable,
            "-m",
            "crackerjack",
            "--start-mcp-server",
            "--websocket-port",
            "8676",
        ]

        process = subprocess.Popen(
            server_cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=Path.cwd(),
        )

        try:
            time.sleep(2)

            if process.poll() is not None:
                stdout, stderr = process.communicate()

                if "Address already in use" not in stderr:
                    assert "ImportError" not in stderr
                    assert "ModuleNotFoundError" not in stderr

        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=5)

    def test_cli_entry_point_mcp_options(self) -> None:
        from crackerjack.__main__ import cli_options

        assert "start_mcp_server" in cli_options
        assert "start_websocket_server" in cli_options
        assert "websocket_port" in cli_options

        assert cli_options["start_mcp_server"].help is not None
        assert "MCP server" in cli_options["start_mcp_server"].help


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
