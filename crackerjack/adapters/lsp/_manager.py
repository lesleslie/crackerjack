"""Rust tool manager for unified execution and coordination."""

import asyncio
import time
import typing as t
from pathlib import Path

from ._base import BaseRustToolAdapter, ToolResult
from .skylos import SkylosAdapter
from .zuban import ZubanAdapter

if t.TYPE_CHECKING:
    from crackerjack.orchestration.execution_strategies import ExecutionContext


class RustToolHookManager:
    """Manager for coordinating Rust-based analysis tools."""

    def __init__(self, context: "ExecutionContext") -> None:
        """Initialize manager with execution context."""
        self.context = context
        self.adapters: dict[str, BaseRustToolAdapter] = {}
        self._initialize_adapters()

    def _initialize_adapters(self) -> None:
        """Initialize available Rust tool adapters."""
        # Dead code detection with Skylos
        self.adapters["skylos"] = SkylosAdapter(context=self.context)

        # Type checking with Zuban
        self.adapters["zuban"] = ZubanAdapter(context=self.context)

    async def run_all_tools(
        self, target_files: list[Path] | None = None
    ) -> dict[str, ToolResult]:
        """Run all available Rust tools in parallel."""
        target_files = target_files or []

        # Filter to available tools only
        available_adapters = {
            name: adapter
            for name, adapter in self.adapters.items()
            if adapter.validate_tool_available()
        }

        if not available_adapters:
            return {
                "error": ToolResult(
                    success=False,
                    error=(
                        "No Rust tools are available. "
                        "Install skylos and zuban with: uv add skylos zuban"
                    ),
                )
            }

        # Run tools in parallel
        tasks = [
            self._run_single_tool(name, adapter, target_files)
            for name, adapter in available_adapters.items()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        tool_results = {}
        for i, (name, _) in enumerate(available_adapters.items()):
            result = results[i]
            if isinstance(result, Exception):
                tool_results[name] = ToolResult(
                    success=False,
                    error=f"Tool execution failed: {result}",
                )
            elif isinstance(result, ToolResult):  # Explicit check for mypy
                tool_results[name] = result

        return tool_results

    async def run_single_tool(
        self, tool_name: str, target_files: list[Path] | None = None
    ) -> ToolResult:
        """Run a single Rust tool by name."""
        if tool_name not in self.adapters:
            return ToolResult(
                success=False,
                error=(
                    f"Unknown tool: {tool_name}. "
                    f"Available: {list[t.Any](self.adapters.keys())}"
                ),
            )

        adapter = self.adapters[tool_name]
        if not adapter.validate_tool_available():
            return ToolResult(
                success=False,
                error=(
                    f"Tool {tool_name} is not available. "
                    f"Install with: uv add {tool_name}"
                ),
            )

        return await self._run_single_tool(tool_name, adapter, target_files or [])

    async def _run_single_tool(
        self, name: str, adapter: BaseRustToolAdapter, target_files: list[Path]
    ) -> ToolResult:
        """Execute a single tool adapter."""
        start_time = time.time()

        try:
            # Get command arguments
            cmd_args = adapter.get_command_args(target_files)

            # Execute command
            process = await asyncio.create_subprocess_exec(
                *cmd_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                cwd=self.context.working_directory,
            )

            stdout, _ = await process.communicate()
            output = stdout.decode() if stdout else ""

            # Parse output
            result = adapter.parse_output(output)
            result.execution_time = time.time() - start_time

            return result

        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to execute {name}: {e}",
                execution_time=time.time() - start_time,
                tool_version=adapter.get_tool_version(),
            )

    def get_available_tools(self) -> list[str]:
        """Get list[t.Any] of available Rust tools."""
        return [
            name
            for name, adapter in self.adapters.items()
            if adapter.validate_tool_available()
        ]

    def get_tool_info(self) -> dict[str, dict[str, t.Any]]:
        """Get information about all configured tools."""
        info: dict[str, dict[str, t.Any]] = {}
        for name, adapter in self.adapters.items():
            info[name] = {
                "available": adapter.validate_tool_available(),
                "supports_json": adapter.supports_json_output(),
                "version": adapter.get_tool_version(),
                "tool_name": adapter.get_tool_name(),
            }
        return info

    def create_consolidated_report(
        self, results: dict[str, ToolResult]
    ) -> dict[str, t.Any]:
        """Create a consolidated report from multiple tool results."""
        total_issues = 0
        total_errors = 0
        total_warnings = 0
        all_success = True
        execution_times = {}

        for tool_name, result in results.items():
            if tool_name == "error":
                all_success = False
                continue

            total_issues += len(result.issues)
            total_errors += result.error_count
            total_warnings += result.warning_count
            execution_times[tool_name] = result.execution_time

            if not result.success:
                all_success = False

        return {
            "overall_success": all_success,
            "total_issues": total_issues,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
            "tools_run": list[t.Any](results.keys()),
            "execution_times": execution_times,
            "total_time": sum(execution_times.values()),
            "results_by_tool": {
                name: result.to_dict() for name, result in results.items()
            },
        }
