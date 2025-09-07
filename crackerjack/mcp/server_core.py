import subprocess
import time
import typing as t
from pathlib import Path
from typing import Final

from rich.console import Console

try:
    import tomli
except ImportError:
    tomli = None

try:
    from fastmcp import FastMCP

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


def _load_mcp_config(project_path: Path) -> dict[str, t.Any]:
    """Load MCP server configuration from pyproject.toml."""
    pyproject_path = project_path / "pyproject.toml"

    if not pyproject_path.exists() or not tomli:
        return {
            "http_port": 8676,
            "http_host": "127.0.0.1",
            "websocket_port": 8675,
            "http_enabled": False,
        }

    try:
        with pyproject_path.open("rb") as f:
            pyproject_data = tomli.load(f)

        crackerjack_config = pyproject_data.get("tool", {}).get("crackerjack", {})

        return {
            "http_port": crackerjack_config.get("mcp_http_port", 8676),
            "http_host": crackerjack_config.get("mcp_http_host", "127.0.0.1"),
            "websocket_port": crackerjack_config.get("mcp_websocket_port", 8675),
            "http_enabled": crackerjack_config.get("mcp_http_enabled", False),
        }
    except Exception as e:
        console.print(
            f"[yellow]Warning: Failed to load MCP config from pyproject.toml: {e}[/yellow]"
        )
        return {
            "http_port": 8676,
            "http_host": "127.0.0.1",
            "websocket_port": 8675,
            "http_enabled": False,
        }


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

    from crackerjack.services.regex_patterns import is_valid_job_id

    return is_valid_job_id(job_id)


async def _start_websocket_server() -> bool:
    context = get_context()
    if context:
        return await context.start_websocket_server()
    return False


def create_mcp_server(config: dict[str, t.Any] | None = None) -> t.Any | None:
    if not MCP_AVAILABLE or FastMCP is None:
        return None

    if config is None:
        config = {"http_port": 8676, "http_host": "127.0.0.1"}

    mcp_app = FastMCP("crackerjack-mcp-server", streamable_http_path="/mcp")

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
    http_mode: bool = False,
    http_port: int | None = None,
) -> None:
    if stop or restart:
        console.print("[yellow]Stopping MCP servers...[/ yellow]")

        try:
            result = subprocess.run(
                ["pkill", "- f", "crackerjack - mcp-server"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                console.print("[green]✅ MCP servers stopped[/ green]")
            else:
                console.print("[dim]No MCP servers were running[/ dim]")
        except subprocess.TimeoutExpired:
            console.print("[red]Timeout stopping MCP servers[/ red]")
        except Exception as e:
            console.print(f"[red]Error stopping MCP servers: {e}[/ red]")

        if stop:
            return

        time.sleep(2)

    if start or restart:
        console.print("[green]Starting MCP server...[/ green]")
        try:
            main(".", websocket_port, http_mode, http_port)
        except Exception as e:
            console.print(f"[red]Failed to start MCP server: {e}[/ red]")


def _initialize_context(context: MCPServerContext) -> None:
    set_context(context)

    context.safe_print("MCP Server context initialized")


def _stop_websocket_server() -> None:
    from contextlib import suppress

    with suppress(RuntimeError):
        context = get_context()
        if context and hasattr(context, "_stop_websocket_server"):
            pass


def _merge_config_with_args(
    mcp_config: dict[str, t.Any],
    http_port: int | None,
    http_mode: bool,
) -> dict[str, t.Any]:
    """Merge MCP configuration with command line arguments."""
    if http_port:
        mcp_config["http_port"] = http_port
    if http_mode:
        mcp_config["http_enabled"] = True
    return mcp_config


def _setup_server_context(
    project_path: Path,
    websocket_port: int | None,
) -> MCPServerContext:
    """Set up and initialize the MCP server context."""
    config = MCPServerConfig(
        project_path=project_path,
        rate_limit_config=RateLimitConfig(),
    )

    context = MCPServerContext(config)
    context.console = console

    if websocket_port:
        context.websocket_server_port = websocket_port

    _initialize_context(context)
    return context


def _print_server_info(
    project_path: Path,
    mcp_config: dict[str, t.Any],
    websocket_port: int | None,
    http_mode: bool,
) -> None:
    """Print server startup information."""
    console.print("[green]Starting Crackerjack MCP Server...[/ green]")
    console.print(f"Project path: {project_path}")

    if mcp_config.get("http_enabled", False) or http_mode:
        console.print(
            f"[cyan]HTTP Mode: http://{mcp_config['http_host']}:{mcp_config['http_port']}/mcp[/ cyan]"
        )
    else:
        console.print("[cyan]STDIO Mode[/ cyan]")

    if websocket_port:
        console.print(f"WebSocket port: {websocket_port}")


def _run_mcp_server(
    mcp_app: t.Any, mcp_config: dict[str, t.Any], http_mode: bool
) -> None:
    """Execute the MCP server with appropriate transport mode."""
    console.print("[yellow]MCP app created, about to run...[/ yellow]")

    try:
        if mcp_config.get("http_enabled", False) or http_mode:
            host = mcp_config.get("http_host", "127.0.0.1")
            port = mcp_config.get("http_port", 8676)
            mcp_app.run(transport="streamable-http", host=host, port=port)
        else:
            mcp_app.run()
    except Exception as e:
        console.print(f"[red]MCP run failed: {e}[/ red]")
        import traceback

        traceback.print_exc()
        raise


def main(
    project_path_arg: str = ".",
    websocket_port: int | None = None,
    http_mode: bool = False,
    http_port: int | None = None,
) -> None:
    if not MCP_AVAILABLE:
        return

    try:
        project_path = Path(project_path_arg).resolve()

        # Load and merge configuration
        mcp_config = _load_mcp_config(project_path)
        mcp_config = _merge_config_with_args(mcp_config, http_port, http_mode)

        # Set up server context
        _setup_server_context(project_path, websocket_port)

        # Create MCP server
        mcp_app = create_mcp_server(mcp_config)
        if not mcp_app:
            console.print("[red]Failed to create MCP server[/ red]")
            return

        # Print server information
        _print_server_info(project_path, mcp_config, websocket_port, http_mode)

        # Run the server
        _run_mcp_server(mcp_app, mcp_config, http_mode)

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

    # Initialize defaults
    project_path = "."
    websocket_port = None
    http_mode = "--http" in sys.argv
    http_port = None

    # Parse project path from non-flag arguments
    non_flag_args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    if non_flag_args:
        project_path = non_flag_args[0]
        if len(non_flag_args) > 1 and non_flag_args[1].isdigit():
            websocket_port = int(non_flag_args[1])

    # Parse HTTP port flag
    if "--http-port" in sys.argv:
        port_idx = sys.argv.index("--http-port")
        if port_idx + 1 < len(sys.argv):
            http_port = int(sys.argv[port_idx + 1])

    main(project_path, websocket_port, http_mode, http_port)
