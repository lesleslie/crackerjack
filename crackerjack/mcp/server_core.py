import subprocess
import time
import typing as t
from pathlib import Path
from typing import Final

from rich.console import Console

try:
    from mcp.server.fastmcp import FastMCP

    _mcp_available = True
except ImportError:
    _mcp_available = False
    FastMCP = None

MCP_AVAILABLE: Final[bool] = _mcp_available

from .context import (
    MCPServerConfig,
    MCPServerContext,
    clear_context,
    get_context,
    set_context,
)
from .rate_limiter import RateLimitConfig
from .tools import (
    register_core_tools,
    register_execution_tools,
    register_intelligence_tools,
    register_monitoring_tools,
    register_proactive_tools,
    register_progress_tools,
    register_utility_tools,
)

console = Console()


class MCPOptions:
    def __init__(self, **kwargs: t.Any) -> None:
        self.commit: bool = False
        self.interactive: bool = False
        self.no_config_updates: bool = False
        self.verbose: bool = False
        self.clean: bool = False
        self.test: bool = False
        self.autofix: bool = True
        self.skip_hooks: bool = False
        self.ai_agent: bool = False
        self.ai_debug: bool = False
        self.publish: str | None = None
        self.bump: str | None = None
        self.create_pr: bool = False
        self.testing: bool = False

        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)


def _validate_job_id(job_id: str) -> bool:
    if not job_id or not isinstance(job_id, str):
        return False
    if len(job_id) > 50:
        return False

    import re

    return bool(re.match(r"^[a-zA-Z0-9_-]+$", job_id))


async def _start_websocket_server() -> bool:
    context = get_context()
    if context:
        return await context.start_websocket_server()
    return False


def create_mcp_server() -> t.Any | None:
    if not MCP_AVAILABLE or FastMCP is None:
        return None

    mcp_app = FastMCP("crackerjack-mcp-server")

    from crackerjack.slash_commands import get_slash_command_path

    @mcp_app.prompt("run")
    async def get_crackerjack_run_prompt() -> str:
        try:
            command_path = get_slash_command_path("run")
            return command_path.read_text()
        except Exception as e:
            msg = f"Failed to read run command: {e}"
            raise ValueError(msg)

    @mcp_app.prompt("init")
    async def get_crackerjack_init_prompt() -> str:
        try:
            command_path = get_slash_command_path("init")
            return command_path.read_text()
        except Exception as e:
            msg = f"Failed to read init command: {e}"
            raise ValueError(msg)

    @mcp_app.prompt("status")
    async def get_crackerjack_status_prompt() -> str:
        try:
            command_path = get_slash_command_path("status")
            return command_path.read_text()
        except Exception as e:
            msg = f"Failed to read status command: {e}"
            raise ValueError(msg)

    register_core_tools(mcp_app)
    register_execution_tools(mcp_app)
    register_intelligence_tools(mcp_app)
    register_monitoring_tools(mcp_app)
    register_progress_tools(mcp_app)
    register_proactive_tools(mcp_app)
    register_utility_tools(mcp_app)

    return mcp_app


def handle_mcp_server_command(
    start: bool = False,
    stop: bool = False,
    restart: bool = False,
    websocket_port: int | None = None,
) -> None:
    """Handle MCP server start/stop/restart commands."""
    if stop or restart:
        console.print("[yellow]Stopping MCP servers...[/yellow]")
        # Kill any existing MCP server processes
        try:
            result = subprocess.run(
                ["pkill", "-f", "crackerjack-mcp-server"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                console.print("[green]✅ MCP servers stopped[/green]")
            else:
                console.print("[dim]No MCP servers were running[/dim]")
        except subprocess.TimeoutExpired:
            console.print("[red]Timeout stopping MCP servers[/red]")
        except Exception as e:
            console.print(f"[red]Error stopping MCP servers: {e}[/red]")

        if stop:
            return

        # For restart, wait a moment before starting again
        time.sleep(2)

    if start or restart:
        console.print("[green]Starting MCP server...[/green]")
        try:
            main(".", websocket_port)
        except Exception as e:
            console.print(f"[red]Failed to start MCP server: {e}[/red]")


def _initialize_context(context: MCPServerContext) -> None:
    set_context(context)

    context.safe_print("MCP Server context initialized")


def _stop_websocket_server() -> None:
    from contextlib import suppress

    with suppress(RuntimeError):
        # Context not initialized, nothing to stop
        context = get_context()
        if context and hasattr(context, "_stop_websocket_server"):
            # The websocket cleanup is handled asynchronously
            # and called from the context's cleanup handlers
            pass


def main(project_path_arg: str = ".", websocket_port: int | None = None) -> None:
    if not MCP_AVAILABLE:
        return

    try:
        project_path = Path(project_path_arg).resolve()

        config = MCPServerConfig(
            project_path=project_path,
            rate_limit_config=RateLimitConfig(),
        )

        context = MCPServerContext(config)
        context.console = console

        # Set custom WebSocket port if specified
        if websocket_port:
            context.websocket_server_port = websocket_port

        _initialize_context(context)

        mcp_app = create_mcp_server()
        if not mcp_app:
            console.print("[red]Failed to create MCP server[/red]")
            return

        console.print("[green]Starting Crackerjack MCP Server...[/green]")
        console.print(f"Project path: {project_path}")
        if websocket_port:
            console.print(f"WebSocket port: {websocket_port}")

        console.print("[yellow]MCP app created, about to run...[/yellow]")
        try:
            mcp_app.run()
        except Exception as e:
            console.print(f"[red]MCP run failed: {e}[/red]")
            import traceback

            traceback.print_exc()
            raise

    except KeyboardInterrupt:
        console.print("Server stopped by user")
    except Exception as e:
        console.print(f"Server error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        _stop_websocket_server()
        clear_context()


if __name__ == "__main__":
    import sys

    project_path = sys.argv[1] if len(sys.argv) > 1 else "."
    websocket_port = int(sys.argv[2]) if len(sys.argv) > 2 else None

    main(project_path, websocket_port)
