import subprocess
import time
import typing as t
from contextlib import suppress
from pathlib import Path
from typing import Final
from uuid import UUID, uuid4

from acb import console as acb_console
from acb.depends import depends
from mcp_common.ui import ServerPanels

# Get the actual Console instance
console = acb_console.console

try:
    import tomli
except ImportError:
    tomli = None  # type: ignore[assignment]

try:
    from fastmcp import FastMCP

    _mcp_available = True
except ImportError:
    _mcp_available = False
    FastMCP = None  # type: ignore[misc,assignment,no-redef]

# Import FastMCP rate limiting middleware (Phase 3 Security Hardening)
try:
    from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware

    RATE_LIMITING_AVAILABLE = True
except ImportError:
    RATE_LIMITING_AVAILABLE = False

MCP_AVAILABLE: Final[bool] = _mcp_available

# Phase 9.1: ACB Integration - Module registration for dependency injection
MODULE_ID: Final[UUID] = uuid4()
MODULE_STATUS: Final[str] = "stable"

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
    register_semantic_tools,
    register_utility_tools,
)

# console imported from acb


def _load_mcp_config(project_path: Path) -> dict[str, t.Any]:
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

    # Add rate limiting middleware (Phase 3 Security Hardening)
    if RATE_LIMITING_AVAILABLE:
        rate_limiter = RateLimitingMiddleware(
            max_requests_per_second=12.0,  # Sustainable rate for code quality operations
            burst_capacity=35,  # Allow bursts for test/lint operations
            global_limit=True,  # Protect the crackerjack server globally
        )
        # Use public API (Phase 3.1 C1 fix: standardize middleware access)
        mcp_app.add_middleware(rate_limiter)

    from crackerjack.slash_commands import get_slash_command_path

    @mcp_app.prompt(
        "run",
        description="Run Crackerjack quality checks with customizable options (hooks, tests, AI fixing)",
    )
    async def get_crackerjack_run_prompt() -> str:
        try:
            command_path = get_slash_command_path("run")
            return command_path.read_text()
        except Exception as e:
            msg = f"Failed to read run command: {e}"
            raise ValueError(msg)

    @mcp_app.prompt(
        "init",
        description="Initialize Crackerjack in a new project (creates pyproject.toml config, pre-commit hooks)",
    )
    async def get_crackerjack_init_prompt() -> str:
        try:
            command_path = get_slash_command_path("init")
            return command_path.read_text()
        except Exception as e:
            msg = f"Failed to read init command: {e}"
            raise ValueError(msg)

    @mcp_app.prompt(
        "status",
        description="Get comprehensive Crackerjack status (hooks, coverage, git state, server health)",
    )
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
    register_semantic_tools(mcp_app)
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
                ["pkill", "-f", "crackerjack-mcp-server"],
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
    if http_port:
        mcp_config["http_port"] = http_port
    if http_mode:
        mcp_config["http_enabled"] = True
    return mcp_config


def _setup_server_context(
    project_path: Path,
    websocket_port: int | None,
) -> MCPServerContext:
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
    if mcp_config.get("http_enabled", False) or http_mode:
        mode = "HTTP"
        http_endpoint = (
            f"http://{mcp_config['http_host']}:{mcp_config['http_port']}/mcp"
        )
    else:
        mode = "STDIO"
        http_endpoint = None
    # Use mcp-common ServerPanels info panel
    items: dict[str, str] = {
        "Project": project_path.name,
        "Mode": mode,
    }
    if http_endpoint:
        items["HTTP"] = http_endpoint
    if websocket_port:
        items["WebSocket Port"] = str(websocket_port)
    ServerPanels.info(
        title="Server Configuration",
        message="Starting Crackerjack MCP Server...",
        items=items,
    )


def _run_mcp_server(
    mcp_app: t.Any, mcp_config: dict[str, t.Any], http_mode: bool
) -> None:
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


def _initialize_project_and_config(
    project_path_arg: str,
    http_port: int | None,
    http_mode: bool,
) -> tuple[Path, dict[str, t.Any]]:
    """Initialize project path and config."""
    project_path = Path(project_path_arg).resolve()
    mcp_config = _load_mcp_config(project_path)
    mcp_config = _merge_config_with_args(mcp_config, http_port, http_mode)
    return project_path, mcp_config


def _create_and_validate_server(mcp_config: dict[str, t.Any]) -> t.Any | None:
    """Create and validate the MCP server."""
    mcp_app = create_mcp_server(mcp_config)
    if not mcp_app:
        console.print("[red]Failed to create MCP server[/ red]")
    return mcp_app


def _start_websocket_if_needed(websocket_port: int | None) -> None:
    """Start WebSocket server if needed."""
    if websocket_port:
        import asyncio

        try:
            asyncio.run(_start_websocket_server())
            console.print(
                f"[green]✅ WebSocket server auto-started on port {websocket_port}[/green]"
            )
        except Exception as e:
            console.print(f"[yellow]⚠️ WebSocket server auto-start failed: {e}[/yellow]")


def _show_server_startup_info(
    project_path: Path,
    mcp_config: dict[str, t.Any],
    websocket_port: int | None,
    http_mode: bool,
) -> None:
    """Show server startup information."""
    _print_server_info(project_path, mcp_config, websocket_port, http_mode)

    # Show final success panel before starting the server
    if mcp_config.get("http_enabled", False) or http_mode:
        http_endpoint = (
            f"http://{mcp_config['http_host']}:{mcp_config['http_port']}/mcp"
        )
    else:
        http_endpoint = None

    websocket_monitor = f"ws://127.0.0.1:{websocket_port}" if websocket_port else None

    # Final startup success panel via mcp-common
    if websocket_monitor:
        ServerPanels.startup_success(
            server_name="Crackerjack MCP",
            endpoint=http_endpoint,
            websocket_monitor=websocket_monitor,  # type: ignore[arg-type]
        )
    else:
        ServerPanels.startup_success(
            server_name="Crackerjack MCP",
            endpoint=http_endpoint,
        )


def main(
    project_path_arg: str = ".",
    websocket_port: int | None = None,
    http_mode: bool = False,
    http_port: int | None = None,
) -> None:
    if not MCP_AVAILABLE:
        return

    try:
        project_path, mcp_config = _initialize_project_and_config(
            project_path_arg, http_port, http_mode
        )

        _setup_server_context(project_path, websocket_port)

        mcp_app = _create_and_validate_server(mcp_config)
        if not mcp_app:
            return

        _show_server_startup_info(project_path, mcp_config, websocket_port, http_mode)

        _start_websocket_if_needed(websocket_port)

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

    project_path = "."
    websocket_port = None
    http_mode = "--http" in sys.argv
    http_port = None

    non_flag_args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    if non_flag_args:
        project_path = non_flag_args[0]
        if len(non_flag_args) > 1 and non_flag_args[1].isdigit():
            websocket_port = int(non_flag_args[1])

    if "--http-port" in sys.argv:
        port_idx = sys.argv.index("--http-port")
        if port_idx + 1 < len(sys.argv):
            http_port = int(sys.argv[port_idx + 1])

    main(project_path, websocket_port, http_mode, http_port)


# Phase 9.1: ACB Integration - Service wrapper for dependency injection
class MCPServerService:
    """Service wrapper for MCP server to enable ACB dependency injection.

    This class wraps the MCP server creation and management functions,
    providing a clean interface for dependency injection via ACB.
    """

    def __init__(self) -> None:
        """Initialize MCP server service."""
        self.module_id = MODULE_ID
        self.module_status = MODULE_STATUS

    def create_server(self, config: dict[str, t.Any] | None = None) -> t.Any | None:
        """Create MCP server instance with optional configuration.

        Args:
            config: Server configuration dictionary

        Returns:
            FastMCP server instance or None if MCP unavailable
        """
        return create_mcp_server(config)

    def start_server(
        self,
        project_path: str = ".",
        websocket_port: int | None = None,
        http_mode: bool = False,
        http_port: int | None = None,
    ) -> None:
        """Start MCP server with specified configuration.

        Args:
            project_path: Path to project directory
            websocket_port: Optional WebSocket server port
            http_mode: Enable HTTP mode instead of STDIO
            http_port: Optional HTTP server port
        """
        main(project_path, websocket_port, http_mode, http_port)

    @property
    def is_available(self) -> bool:
        """Check if MCP server functionality is available.

        Returns:
            True if FastMCP library is installed and available
        """
        return MCP_AVAILABLE


# Phase 9.1: ACB Integration - Register service with dependency injection system
with suppress(Exception):
    depends.set(MCPServerService)
