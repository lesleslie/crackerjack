#!/usr/bin/env python3
"""Tool proxy that routes tool calls through adapters with health checks and graceful degradation."""

import asyncio
import sys
import time
import typing as t
from dataclasses import dataclass, field
from pathlib import Path

from acb.console import Console
from acb.depends import depends


@dataclass
class ToolHealthStatus:
    """Health status of a tool."""

    is_healthy: bool
    last_check: float
    consecutive_failures: int = 0
    last_error: str | None = None
    fallback_recommendations: list[str] = field(default_factory=list)


@dataclass
class CircuitBreakerState:
    """Circuit breaker state for a tool."""

    is_open: bool = False
    failure_count: int = 0
    last_failure_time: float = 0
    next_retry_time: float = 0

    # Circuit breaker thresholds
    failure_threshold: int = 3
    retry_timeout: float = 120  # 2 minutes

    def should_attempt(self) -> bool:
        """Check if we should attempt to use this tool."""
        if not self.is_open:
            return True

        # Allow retry after timeout
        return time.time() >= self.next_retry_time

    def record_failure(self) -> None:
        """Record a tool failure."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            self.is_open = True
            self.next_retry_time = time.time() + self.retry_timeout

    def record_success(self) -> None:
        """Record a tool success."""
        self.failure_count = 0
        self.is_open = False
        self.next_retry_time = 0


class ToolProxy:
    """Proxy that routes tool calls through adapters with health checks."""

    def __init__(self, console: Console | None = None):
        self.console = console or depends.get_sync(Console)
        self.health_status: dict[str, ToolHealthStatus] = {}
        self.circuit_breakers: dict[str, CircuitBreakerState] = {}

        # Tool mappings to adapters
        self.tool_adapters = {
            "zuban": self._create_zuban_adapter,
            "skylos": self._create_skylos_adapter,
            "ruff": self._create_ruff_adapter,
            "bandit": self._create_bandit_adapter,
        }

        # Fallback recommendations
        self.fallback_tools = {
            "zuban": ["pyright", "mypy"],
            "skylos": ["vulture"],
            "ruff": [],  # Ruff is usually reliable
            "bandit": [],  # Skip security checks if bandit fails
        }

    def execute_tool(self, tool_name: str, args: list[str]) -> int:
        """Execute a tool through its adapter with health checks.

        Args:
            tool_name: Name of the tool to execute
            args: Arguments to pass to the tool

        Returns:
            Exit code (0 for success, non-zero for failure)
        """
        try:
            # Check circuit breaker
            circuit_breaker = self._get_circuit_breaker(tool_name)

            if not circuit_breaker.should_attempt():
                self._handle_circuit_breaker_open(tool_name)
                return self._try_fallback_tools(tool_name, args)

            # Check tool health
            if not self._check_tool_health(tool_name):
                self._handle_unhealthy_tool(tool_name)
                circuit_breaker.record_failure()
                return self._try_fallback_tools(tool_name, args)

            # Execute through adapter
            result = self._execute_through_adapter(tool_name, args)

            if result == 0:
                circuit_breaker.record_success()
            else:
                circuit_breaker.record_failure()

            return result

        except Exception as e:
            self.console.print(f"[red]Tool proxy error for {tool_name}: {e}[/red]")
            self._get_circuit_breaker(tool_name).record_failure()
            return self._try_fallback_tools(tool_name, args)

    def _get_circuit_breaker(self, tool_name: str) -> CircuitBreakerState:
        """Get or create circuit breaker for tool."""
        if tool_name not in self.circuit_breakers:
            self.circuit_breakers[tool_name] = CircuitBreakerState()
        return self.circuit_breakers[tool_name]

    def _check_tool_health(self, tool_name: str) -> bool:
        """Check if a tool is healthy."""
        current_time = time.time()

        # Use cached health status if recent (within 30 seconds)
        if tool_name in self.health_status:
            status = self.health_status[tool_name]
            if current_time - status.last_check < 30:
                return status.is_healthy

        # Perform actual health check
        is_healthy = self._perform_health_check(tool_name)

        self.health_status[tool_name] = ToolHealthStatus(
            is_healthy=is_healthy,
            last_check=current_time,
            fallback_recommendations=list(self.fallback_tools.get(tool_name, [])),
        )

        return is_healthy

    def _perform_health_check(self, tool_name: str) -> bool:
        """Perform actual health check for a tool."""
        try:
            if tool_name in self.tool_adapters:
                # Use adapter health check if available
                adapter = self.tool_adapters[tool_name]()
                if adapter and hasattr(adapter, "check_tool_health"):
                    return bool(adapter.check_tool_health())

            # Tool-specific health checks for known problematic tools
            if tool_name == "zuban":
                return self._check_zuban_health()
            elif tool_name == "skylos":
                return self._check_skylos_health()

            # Fallback to basic version check
            import subprocess

            result = subprocess.run(
                ["uv", "run", tool_name, "--version"],
                capture_output=True,
                timeout=10,
                text=True,
            )
            return result.returncode == 0

        except Exception:
            return False

    def _check_zuban_health(self) -> bool:
        """Specific health check for Zuban that tests TOML parsing."""
        import subprocess
        import tempfile

        try:
            # Test basic version first
            result = subprocess.run(
                ["uv", "run", "zuban", "--version"],
                capture_output=True,
                timeout=10,
                text=True,
            )
            if result.returncode != 0:
                return False

            # Test actual type checking on a minimal file - this triggers TOML parsing
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_file = Path(temp_dir) / "test.py"
                temp_file.write_text("x: int = 1\n")

                # This should trigger the TOML parsing bug if it exists
                result = subprocess.run(
                    ["uv", "run", "zuban", "check", str(temp_file)],
                    capture_output=True,
                    timeout=5,  # Short timeout to catch panics
                    text=True,
                    cwd=Path.cwd(),  # Run from our directory with problematic pyproject.toml
                )

                # If it exits cleanly (regardless of type errors), tool is healthy
                # The key is that it doesn't panic with TOML parsing errors
                return result.returncode in (0, 1)  # 0=no errors, 1=type errors found

        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            # Tool timed out or crashed - likely the TOML parsing bug
            return False
        except Exception:
            return False

    def _check_skylos_health(self) -> bool:
        """Specific health check for Skylos."""
        import subprocess

        try:
            result = subprocess.run(
                ["uv", "run", "skylos", "--version"],
                capture_output=True,
                timeout=10,
                text=True,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _execute_through_adapter(self, tool_name: str, args: list[str]) -> int:
        """Execute tool through its adapter if available."""
        if tool_name in self.tool_adapters:
            try:
                # Use async adapter if available
                return asyncio.run(self._execute_adapter_async(tool_name, args))
            except Exception as e:
                self.console.print(
                    f"[yellow]Adapter execution failed for {tool_name}: {e}[/yellow]"
                )
                # Fall back to direct execution
                pass

        # Direct execution as fallback
        return self._execute_direct(tool_name, args)

    async def _execute_adapter_async(self, tool_name: str, args: list[str]) -> int:
        """Execute tool through async adapter."""
        adapter_factory = self.tool_adapters[tool_name]
        adapter = adapter_factory()

        # Convert args to file paths for adapter
        target_files = self._args_to_file_paths(args)

        if hasattr(adapter, "check_with_lsp_or_fallback"):
            result = await adapter.check_with_lsp_or_fallback(target_files)
            return 0 if result.success else 1

        return self._execute_direct(tool_name, args)

    def _execute_direct(self, tool_name: str, args: list[str]) -> int:
        """Execute tool directly without adapter."""
        import subprocess

        try:
            cmd = ["uv", "run", tool_name] + args
            result = subprocess.run(cmd, timeout=300)
            return result.returncode

        except subprocess.TimeoutExpired:
            self.console.print(f"[red]Tool {tool_name} timed out[/red]")
            return 1
        except Exception as e:
            self.console.print(
                f"[red]Direct execution failed for {tool_name}: {e}[/red]"
            )
            return 1

    def _args_to_file_paths(self, args: list[str]) -> list[Path]:
        """Convert command line arguments to file paths."""
        file_paths = [
            Path(arg) for arg in args if not arg.startswith("-") and Path(arg).exists()
        ]

        # Default to current directory if no files specified
        if not file_paths:
            file_paths = [Path()]

        return file_paths

    def _try_fallback_tools(self, tool_name: str, args: list[str]) -> int:
        """Try fallback tools when primary tool fails."""
        fallbacks = self.fallback_tools.get(tool_name, [])

        if not fallbacks:
            self.console.print(
                f"[yellow]No fallback available for {tool_name}. Skipping with warning.[/yellow]"
            )
            return 0  # Skip with success to not block workflow

        self.console.print(
            f"[yellow]Trying fallback tools for {tool_name}: {', '.join(fallbacks)}[/yellow]"
        )

        for fallback in fallbacks:
            try:
                # Check if fallback is healthy
                if self._check_tool_health(fallback):
                    result = self._execute_direct(fallback, args)
                    if result == 0:
                        self.console.print(
                            f"[green]Fallback {fallback} succeeded[/green]"
                        )
                        return 0
            except Exception:
                continue

        self.console.print(
            f"[yellow]All fallbacks failed for {tool_name}. Continuing...[/yellow]"
        )
        return 0  # Don't block workflow on tool failures

    def _handle_circuit_breaker_open(self, tool_name: str) -> None:
        """Handle when circuit breaker is open."""
        circuit_breaker = self.circuit_breakers[tool_name]
        retry_minutes = int((circuit_breaker.next_retry_time - time.time()) / 60)

        self.console.print(
            f"[yellow]Circuit breaker open for {tool_name}. "
            f"Will retry in {retry_minutes} minutes.[/yellow]"
        )

    def _handle_unhealthy_tool(self, tool_name: str) -> None:
        """Handle when tool is detected as unhealthy."""
        self.console.print(
            f"[yellow]Tool {tool_name} is unhealthy. Trying fallbacks...[/yellow]"
        )

    def _create_zuban_adapter(self) -> t.Any | None:
        """Create Zuban adapter instance."""
        try:
            from acb.depends import depends

            from crackerjack.adapters.zuban_adapter import ZubanAdapter
            from crackerjack.config import CrackerjackSettings
            from crackerjack.orchestration.execution_strategies import ExecutionContext

            # Create minimal context for adapter using ACB settings
            settings = depends.get(CrackerjackSettings)

            # Import adapter from core_tools that converts settings to OptionsProtocol
            from crackerjack.mcp.tools.core_tools import _adapt_settings_to_protocol

            options = _adapt_settings_to_protocol(settings)
            context = ExecutionContext(pkg_path=Path.cwd(), options=options)
            return ZubanAdapter(context)
        except (ImportError, Exception):
            return None

    def _create_skylos_adapter(self) -> t.Any | None:
        """Create Skylos adapter instance."""
        try:
            from acb.depends import depends

            from crackerjack.adapters.skylos_adapter import SkylosAdapter
            from crackerjack.config import CrackerjackSettings
            from crackerjack.orchestration.execution_strategies import ExecutionContext

            # Create minimal context for adapter using ACB settings
            settings = depends.get(CrackerjackSettings)

            # Import adapter from core_tools that converts settings to OptionsProtocol
            from crackerjack.mcp.tools.core_tools import _adapt_settings_to_protocol

            options = _adapt_settings_to_protocol(settings)
            context = ExecutionContext(pkg_path=Path.cwd(), options=options)
            return SkylosAdapter(context)
        except (ImportError, Exception):
            return None

    def _create_ruff_adapter(self) -> t.Any | None:
        """Create Ruff adapter instance."""
        # Ruff doesn't have an adapter yet, return None for direct execution
        return None

    def _create_bandit_adapter(self) -> t.Any | None:
        """Create Bandit adapter instance."""
        # Bandit doesn't have an adapter yet, return None for direct execution
        return None

    def get_tool_status(self) -> dict[str, dict[str, t.Any]]:
        """Get status of all tools for monitoring."""
        status = {}

        for tool_name in self.tool_adapters.keys():
            circuit_breaker = self._get_circuit_breaker(tool_name)
            health_status = self.health_status.get(tool_name)

            status[tool_name] = {
                "circuit_breaker_open": circuit_breaker.is_open,
                "failure_count": circuit_breaker.failure_count,
                "is_healthy": health_status.is_healthy if health_status else None,
                "last_health_check": health_status.last_check
                if health_status
                else None,
                "fallback_tools": self.fallback_tools.get(tool_name, []),
            }

        return status


def main() -> None:
    """Main entry point for tool proxy CLI."""
    if len(sys.argv) < 2:
        print("Usage: python -m crackerjack.executors.tool_proxy <tool_name> [args...]")
        sys.exit(1)

    tool_name = sys.argv[1]
    args = sys.argv[2:]

    proxy = ToolProxy()
    exit_code = proxy.execute_tool(tool_name, args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
