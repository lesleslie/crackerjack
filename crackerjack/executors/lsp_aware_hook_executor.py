import time
import typing as t
from contextlib import suppress
from pathlib import Path

from crackerjack.config.hooks import HookDefinition, HookStrategy
from crackerjack.executors.hook_executor import HookExecutionResult, HookExecutor
from crackerjack.models.task import HookResult
from crackerjack.services.lsp_client import LSPClient

# Conditional import for ToolProxy
try:
    from crackerjack.executors.tool_proxy import ToolProxy
except ImportError:
    ToolProxy = None  # type: ignore


class LSPAwareHookExecutor(HookExecutor):
    """Hook executor that can leverage LSP server for enhanced performance."""

    def __init__(
        self,
        pkg_path: Path,
        verbose: bool = False,
        quiet: bool = False,
        debug: bool = False,
        use_tool_proxy: bool = True,
        use_incremental: bool = False,
        git_service: t.Any | None = None,
    ) -> None:
        super().__init__(
            console, pkg_path, verbose, quiet, debug, use_incremental, git_service
        )
        self.lsp_client = LSPClient()
        self.use_tool_proxy = use_tool_proxy and ToolProxy is not None
        self.tool_proxy = ToolProxy() if self.use_tool_proxy else None
        self.debug = debug

    def execute_strategy(self, strategy: HookStrategy) -> HookExecutionResult:
        """Execute hook strategy with LSP optimization where possible."""
        start_time = time.time()
        results = []

        # Check if LSP server is available
        lsp_available = self._check_lsp_availability()

        # Execute hooks with LSP optimization and tool proxy resilience
        for hook in strategy.hooks:
            self._handle_progress_start(len(strategy.hooks))
            result = self._execute_single_hook_with_strategies(hook, lsp_available)
            results.append(result)
            self._handle_progress_completion(len(strategy.hooks))

        duration = time.time() - start_time
        success = all(result.status in ("passed", "skipped") for result in results)

        return HookExecutionResult(
            strategy_name=strategy.name,
            results=results,
            total_duration=duration,
            success=success,
            concurrent_execution=False,
        )

    def _check_lsp_availability(self) -> bool:
        """Check if LSP server is available and print info message."""
        lsp_available = self.lsp_client.is_server_running()

        if lsp_available and not self.quiet:
            server_info = self.lsp_client.get_server_info()
            if server_info:
                self.console.print(
                    f"🔍 LSP server available (PID: {server_info['pid']}), using optimized execution"
                )

        return lsp_available

    def _execute_single_hook_with_strategies(
        self, hook: HookDefinition, lsp_available: bool
    ) -> HookResult:
        """Execute a single hook using appropriate strategy."""
        if self._should_use_lsp_for_hook(hook, lsp_available):
            return self._execute_lsp_hook(hook)
        elif self._should_use_tool_proxy(hook):
            return self._execute_hook_with_proxy(hook)

        return self.execute_single_hook(hook)

    def _handle_progress_start(self, total_hooks: int | None = None) -> None:
        """Handle progress start callback."""
        with suppress(Exception):
            callback = getattr(self, "_progress_start_callback", None)
            if callback:
                # _total_hooks/_started_hooks are initialized by set_progress_callbacks on base class
                self._started_hooks += 1  # type: ignore[attr-defined]
                total = self._total_hooks or total_hooks  # type: ignore[attr-defined]
                if total:
                    callback(self._started_hooks, total)  # type: ignore[attr-defined]

    def _handle_progress_completion(self, total_hooks: int | None = None) -> None:
        """Handle progress completion callback."""
        with suppress(Exception):
            callback = getattr(self, "_progress_callback", None)
            if callback:
                self._completed_hooks += 1  # type: ignore[attr-defined]
                total = self._total_hooks or total_hooks  # type: ignore[attr-defined]
                if total:
                    callback(self._completed_hooks, total)  # type: ignore[attr-defined]

    def _should_use_lsp_for_hook(
        self, hook: HookDefinition, lsp_available: bool
    ) -> bool:
        """Determine if a hook should use LSP-based execution."""
        # Only use LSP for type-checking hooks when server is available
        return (
            lsp_available
            and hook.name == "zuban"
            and hook.stage.value == "comprehensive"
        )

    def _execute_lsp_hook(self, hook: HookDefinition) -> HookResult:
        """Execute a hook using LSP server with real-time feedback."""
        start_time = time.time()

        try:
            return self._perform_lsp_execution(hook, start_time)
        except Exception as e:
            return self._handle_lsp_execution_error(hook, start_time, e)

    def _perform_lsp_execution(
        self, hook: HookDefinition, start_time: float
    ) -> HookResult:
        """Perform the actual LSP execution."""
        if not self.quiet:
            self.console.print(
                f"🚀 Using LSP-optimized execution for {hook.name}", style="cyan"
            )

        # Use the new real-time feedback method
        diagnostics, summary = self.lsp_client.check_project_with_feedback(
            self.pkg_path, show_progress=not self.quiet
        )

        duration = time.time() - start_time
        has_errors = any(diags for diags in diagnostics.values())
        output = self._format_lsp_output(diagnostics, duration)

        self._display_lsp_results(hook, has_errors, output, summary)

        # Create hook result
        return self._create_lsp_hook_result(
            hook, duration, has_errors, output, diagnostics
        )

    def _create_lsp_hook_result(
        self,
        hook: HookDefinition,
        duration: float,
        has_errors: bool,
        output: str,
        diagnostics: dict,
    ) -> HookResult:
        """Create the HookResult for LSP execution."""
        # Ensure failed hooks always have at least 1 issue count
        issues_found = [output] if has_errors else []
        issues_count = max(len(issues_found), 1 if has_errors else 0)

        return HookResult(
            id=f"{hook.name}-lsp-{int(time.time())}",
            name=f"{hook.name}-lsp",
            status="failed" if has_errors else "passed",
            duration=duration,
            files_processed=len(diagnostics),
            issues_found=issues_found,
            issues_count=issues_count,
        )

    def _format_lsp_output(self, diagnostics: dict[str, t.Any], duration: float) -> str:
        """Format LSP diagnostic output with performance info."""
        output = self.lsp_client.format_diagnostics(diagnostics)
        file_count = len(self.lsp_client.get_project_files(self.pkg_path))
        perf_info = f"\n⚡ LSP-optimized check completed in {duration:.2f}s ({file_count} files)"
        return output + perf_info

    def _display_lsp_results(
        self, hook: HookDefinition, has_errors: bool, output: str, summary: str
    ) -> None:
        """Display LSP execution results."""
        if self.verbose or has_errors:
            if not self.quiet:
                self.console.print(f"🔍 {hook.name} (LSP):", style="bold blue")
                if has_errors:
                    self.console.print(output)
                else:
                    self.console.print(summary, style="green")

    def _handle_lsp_execution_error(
        self, hook: HookDefinition, start_time: float, error: Exception
    ) -> HookResult:
        """Handle LSP execution errors with fallback."""
        time.time() - start_time
        error_msg = f"LSP execution failed: {error}"

        if not self.quiet:
            self.console.print(f"❌ {hook.name} (LSP): {error_msg}", style="red")
            self.console.print(f"🔄 Falling back to regular {hook.name} execution")

        return self.execute_single_hook(hook)

    def _should_use_tool_proxy(self, hook: HookDefinition) -> bool:
        """Determine if a hook should use tool proxy for resilient execution."""
        if not self.use_tool_proxy or not self.tool_proxy:
            return False

        # Use tool proxy for known fragile tools
        fragile_tools = {"zuban", "skylos", "bandit"}
        return hook.name in fragile_tools

    def _execute_hook_with_proxy(self, hook: HookDefinition) -> HookResult:
        """Execute a hook using tool proxy for resilient execution."""
        start_time = time.time()

        try:
            return self._perform_proxy_execution(hook, start_time)
        except Exception as e:
            return self._handle_proxy_execution_error(hook, start_time, e)

    def _perform_proxy_execution(
        self, hook: HookDefinition, start_time: float
    ) -> HookResult:
        """Perform the actual proxy execution."""
        if not self.quiet:
            self.console.print(
                f"🛡️ Using resilient execution for {hook.name}", style="blue"
            )

        # Parse hook entry to extract tool name and args
        tool_name, args = self._parse_hook_entry(hook)

        # Execute through tool proxy
        if self.tool_proxy is not None:
            exit_code = self.tool_proxy.execute_tool(tool_name, args)
        else:
            exit_code = -1  # Error code when tool proxy is not available

        duration = time.time() - start_time
        status = "passed" if exit_code == 0 else "failed"

        # Get tool status for output
        tool_status = (
            self.tool_proxy.get_tool_status().get(tool_name, {})
            if self.tool_proxy is not None
            else {}
        )
        output = self._format_proxy_output(tool_name, tool_status, duration)

        # Ensure failed hooks always have at least 1 issue count
        issues_found = [output] if status == "failed" else []
        issues_count = max(len(issues_found), 1 if status == "failed" else 0)

        return HookResult(
            id=f"{hook.name}-proxy-{int(time.time())}",
            name=f"{hook.name}-proxy",
            status=status,
            duration=duration,
            files_processed=1,  # Placeholder value
            issues_found=issues_found,
            issues_count=issues_count,
        )

    def _handle_proxy_execution_error(
        self, hook: HookDefinition, start_time: float, error: Exception
    ) -> HookResult:
        """Handle proxy execution errors with fallback."""
        time.time() - start_time
        error_msg = f"Tool proxy execution failed: {error}"

        if not self.quiet:
            self.console.print(f"❌ {hook.name} (proxy): {error_msg}", style="red")
            self.console.print(f"🔄 Falling back to regular {hook.name} execution")

        # Fallback to regular execution
        return self.execute_single_hook(hook)

    def _parse_hook_entry(self, hook: HookDefinition) -> tuple[str, list[str]]:
        """Parse hook entry to extract tool name and arguments."""
        entry_str = " ".join(hook.command)
        entry_parts = entry_str.split()

        if len(entry_parts) < 3:  # e.g., "uv run zuban"
            raise ValueError(f"Invalid hook entry format: {entry_str}")

        # Extract tool name (assuming "uv run <tool>" format)
        if entry_parts[0] == "uv" and entry_parts[1] == "run":
            tool_name = entry_parts[2]
            args = entry_parts[3:] if len(entry_parts) > 3 else []
        else:
            # Direct tool execution
            tool_name = entry_parts[0]
            args = entry_parts[1:]

        return tool_name, args

    def _format_proxy_output(
        self, tool_name: str, tool_status: dict[str, t.Any], duration: float
    ) -> str:
        """Format tool proxy execution output."""
        status_info = []

        if tool_status.get("circuit_breaker_open"):
            status_info.append("Circuit breaker: OPEN")

        if tool_status.get("is_healthy") is False:
            status_info.append("Health check: FAILED")

        fallback_tools = tool_status.get("fallback_tools", [])
        if fallback_tools:
            status_info.append(f"Fallbacks: {', '.join(fallback_tools)}")

        status_str = f" ({', '.join(status_info)})" if status_info else ""

        return f"🛡️ Resilient execution completed in {duration:.2f}s{status_str}"

    def get_execution_mode_summary(self) -> dict[str, t.Any]:
        """Get summary of execution mode capabilities."""
        lsp_available = self.lsp_client.is_server_running()
        server_info = self.lsp_client.get_server_info() if lsp_available else None

        summary = {
            "lsp_server_available": lsp_available,
            "lsp_server_info": server_info,
            "optimization_enabled": lsp_available,
            "supported_hooks": ["zuban"] if lsp_available else [],
            "tool_proxy_enabled": self.use_tool_proxy,
            "resilient_tools": ["zuban", "skylos", "bandit"]
            if self.use_tool_proxy
            else [],
        }

        # Add tool proxy status if available
        if self.tool_proxy:
            summary["tool_status"] = self.tool_proxy.get_tool_status()

        return summary
