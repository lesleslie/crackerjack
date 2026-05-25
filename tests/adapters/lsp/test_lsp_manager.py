"""Tests for RustToolHookManager."""

import asyncio
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from crackerjack.adapters.lsp._manager import RustToolHookManager
from crackerjack.adapters.lsp._base import ToolResult


class MockAdapter:
    """Mock adapter for testing."""

    def __init__(self, name="mock", available=True, json_support=False):
        self._name = name
        self._available = available
        self._json_support = json_support
        self._version = "1.0.0"

    def get_tool_name(self):
        return self._name

    def supports_json_output(self):
        return self._json_support

    def get_tool_version(self):
        return self._version

    def validate_tool_available(self):
        return self._available

    async def run(self, target_files):
        return ToolResult(success=True, issues=[])


class TestRustToolHookManager:
    """Test RustToolHookManager."""

    def test_initialization(self):
        """Test manager initialization."""
        mock_context = Mock()
        manager = RustToolHookManager(mock_context)

        assert manager.context == mock_context
        assert "skylos" in manager.adapters
        assert "zuban" in manager.adapters

    def test_initialization_creates_adapters(self):
        """Test adapters are initialized during construction."""
        mock_context = Mock()
        manager = RustToolHookManager(mock_context)

        from crackerjack.adapters.lsp.skylos import SkylosAdapter
        from crackerjack.adapters.lsp.zuban import ZubanAdapter

        assert isinstance(manager.adapters["skylos"], SkylosAdapter)
        assert isinstance(manager.adapters["zuban"], ZubanAdapter)

    @pytest.mark.asyncio
    async def test_run_all_tools_no_tools_available(self):
        """Test run_all_tools when no tools are available."""
        mock_context = Mock()
        manager = RustToolHookManager(mock_context)

        for name in manager.adapters:
            manager.adapters[name].validate_tool_available = Mock(return_value=False)

        results = await manager.run_all_tools()

        assert "error" in results
        assert results["error"].success is False
        assert "No Rust tools are available" in results["error"].error

    @pytest.mark.asyncio
    async def test_run_all_tools_with_available_tools(self):
        """Test run_all_tools with available tools."""
        mock_context = Mock()
        mock_context.working_directory = Path("/test")
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        manager = RustToolHookManager(mock_context)

        for name in manager.adapters:
            manager.adapters[name].validate_tool_available = Mock(return_value=True)
            manager.adapters[name].get_command_args = Mock(return_value=["echo", "test"])

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"output", b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            for name in manager.adapters:
                manager.adapters[name].parse_output = Mock(
                    return_value=ToolResult(success=True, issues=[])
                )

            results = await manager.run_all_tools()

            assert "skylos" in results or "zuban" in results

    @pytest.mark.asyncio
    async def test_run_all_tools_handles_exception(self):
        """Test run_all_tools handles exceptions gracefully."""
        mock_context = Mock()
        mock_context.working_directory = Path("/test")
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False

        manager = RustToolHookManager(mock_context)

        for name in manager.adapters:
            manager.adapters[name].validate_tool_available = Mock(return_value=True)
            manager.adapters[name].get_command_args = Mock(return_value=["invalid"])

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_subprocess.side_effect = Exception("Process error")

            results = await manager.run_all_tools()

            for name in ["skylos", "zuban"]:
                if name in results:
                    assert results[name].success is False

    @pytest.mark.asyncio
    async def test_run_single_tool_unknown(self):
        """Test run_single_tool with unknown tool name."""
        mock_context = Mock()
        manager = RustToolHookManager(mock_context)

        result = await manager.run_single_tool("unknown_tool")

        assert result.success is False
        assert "Unknown tool" in result.error

    @pytest.mark.asyncio
    async def test_run_single_tool_not_available(self):
        """Test run_single_tool when tool not available."""
        mock_context = Mock()
        manager = RustToolHookManager(mock_context)

        manager.adapters["skylos"].validate_tool_available = Mock(return_value=False)

        result = await manager.run_single_tool("skylos")

        assert result.success is False
        assert "not available" in result.error

    @pytest.mark.asyncio
    async def test_run_single_tool_success(self):
        """Test run_single_tool success path."""
        mock_context = Mock()
        mock_context.working_directory = Path("/test")
        mock_context.ai_agent_mode = False
        mock_context.ai_debug_mode = False
        mock_context.interactive = False

        manager = RustToolHookManager(mock_context)
        manager.adapters["skylos"].validate_tool_available = Mock(return_value=True)
        manager.adapters["skylos"].get_command_args = Mock(return_value=["echo", "test"])

        with patch("asyncio.create_subprocess_exec") as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.communicate = AsyncMock(return_value=(b"output", b""))
            mock_process.returncode = 0
            mock_subprocess.return_value = mock_process

            manager.adapters["skylos"].parse_output = Mock(
                return_value=ToolResult(success=True, issues=[])
            )

            result = await manager.run_single_tool("skylos")

            assert result.success is True

    @pytest.mark.asyncio
    async def test_run_single_tool_executes_all_adapters(self):
        """Test run_single_tool finds correct adapter."""
        mock_context = Mock()
        manager = RustToolHookManager(mock_context)

        manager.adapters["skylos"].validate_tool_available = Mock(return_value=True)
        manager.adapters["zuban"].validate_tool_available = Mock(return_value=True)

        assert await manager.run_single_tool("skylos") is not None
        assert await manager.run_single_tool("zuban") is not None

    def test_get_available_tools_all_available(self):
        """Test get_available_tools when all tools available."""
        mock_context = Mock()
        manager = RustToolHookManager(mock_context)

        for name in manager.adapters:
            manager.adapters[name].validate_tool_available = Mock(return_value=True)

        tools = manager.get_available_tools()

        assert "skylos" in tools
        assert "zuban" in tools

    def test_get_available_tools_none_available(self):
        """Test get_available_tools when no tools available."""
        mock_context = Mock()
        manager = RustToolHookManager(mock_context)

        for name in manager.adapters:
            manager.adapters[name].validate_tool_available = Mock(return_value=False)

        tools = manager.get_available_tools()

        assert len(tools) == 0

    def test_get_tool_info(self):
        """Test get_tool_info returns correct structure."""
        mock_context = Mock()
        manager = RustToolHookManager(mock_context)

        for name in manager.adapters:
            manager.adapters[name].validate_tool_available = Mock(return_value=True)
            manager.adapters[name].supports_json_output = Mock(return_value=True)
            manager.adapters[name].get_tool_version = Mock(return_value="1.0.0")
            manager.adapters[name].get_tool_name = Mock(return_value=name)

        info = manager.get_tool_info()

        assert "skylos" in info
        assert "zuban" in info
        for tool_info in info.values():
            assert "available" in tool_info
            assert "supports_json" in tool_info
            assert "version" in tool_info
            assert "tool_name" in tool_info

    def test_create_consolidated_report_empty(self):
        """Test create_consolidated_report with empty results."""
        mock_context = Mock()
        manager = RustToolHookManager(mock_context)

        report = manager.create_consolidated_report({})

        assert report["overall_success"] is True
        assert report["total_issues"] == 0
        assert report["total_errors"] == 0
        assert report["total_warnings"] == 0

    def test_create_consolidated_report_with_success(self):
        """Test create_consolidated_report with successful results."""
        mock_context = Mock()
        manager = RustToolHookManager(mock_context)

        from crackerjack.adapters.lsp._base import Issue

        results = {
            "skylos": ToolResult(
                success=True,
                issues=[Issue(Path("a.py"), 1, "warning", severity="warning")],
                execution_time=1.0,
            ),
            "zuban": ToolResult(success=True, issues=[], execution_time=0.5),
        }

        report = manager.create_consolidated_report(results)

        assert report["overall_success"] is True
        assert report["total_issues"] == 1
        assert report["total_errors"] == 0
        assert report["total_warnings"] == 1
        assert report["total_time"] == 1.5

    def test_create_consolidated_report_with_failure(self):
        """Test create_consolidated_report with failed results."""
        mock_context = Mock()
        manager = RustToolHookManager(mock_context)

        from crackerjack.adapters.lsp._base import Issue

        results = {
            "skylos": ToolResult(
                success=True,
                issues=[Issue(Path("a.py"), 1, "warning", severity="warning")],
                execution_time=1.0,
            ),
            "zuban": ToolResult(
                success=False,
                issues=[Issue(Path("b.py"), 1, "error", severity="error")],
                execution_time=0.5,
            ),
        }

        report = manager.create_consolidated_report(results)

        assert report["overall_success"] is False
        assert report["total_issues"] == 2
        assert report["total_errors"] == 1
        assert report["total_warnings"] == 1

    def test_create_consolidated_report_with_error_entry(self):
        """Test create_consolidated_report handles error entry."""
        mock_context = Mock()
        manager = RustToolHookManager(mock_context)

        results = {
            "error": ToolResult(success=False, error="No tools available"),
            "skylos": ToolResult(success=True, issues=[], execution_time=1.0),
        }

        report = manager.create_consolidated_report(results)

        assert report["overall_success"] is False
        assert "error" in report["tools_run"]

    def test_create_consolidated_report_includes_execution_times(self):
        """Test create_consolidated_report includes execution times."""
        mock_context = Mock()
        manager = RustToolHookManager(mock_context)

        results = {
            "skylos": ToolResult(success=True, issues=[], execution_time=2.5),
            "zuban": ToolResult(success=True, issues=[], execution_time=1.5),
        }

        report = manager.create_consolidated_report(results)

        assert "skylos" in report["execution_times"]
        assert "zuban" in report["execution_times"]
        assert report["execution_times"]["skylos"] == 2.5
        assert report["execution_times"]["zuban"] == 1.5
        assert report["total_time"] == 4.0

    def test_create_consolidated_report_results_by_tool(self):
        """Test create_consolidated_report includes results by tool."""
        mock_context = Mock()
        manager = RustToolHookManager(mock_context)

        results = {
            "skylos": ToolResult(success=True, issues=[], execution_time=1.0),
        }

        report = manager.create_consolidated_report(results)

        assert "results_by_tool" in report
        assert "skylos" in report["results_by_tool"]
