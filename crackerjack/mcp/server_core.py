import os
import subprocess
import time
import typing as t
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Final

from mcp_common.ui import ServerPanels
from rich.console import Console

from crackerjack.runtime import (
    RuntimeHealthSnapshot,
    write_pid_file,
    write_runtime_health,
)

# Get Rich Console instance
console = Console()

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

from .context import (
    MCPServerConfig,
    MCPServerContext,
    clear_context,
    set_context,
)
from .rate_limiter import RateLimitConfig
from .tools import (
    initialize_skills,
    register_core_tools,
    register_execution_tools,
    register_intelligence_tools,
    register_monitoring_tools,
    register_proactive_tools,
    register_progress_tools,
    register_semantic_tools,
    register_skill_tools,
    register_utility_tools,
)


def _load_mcp_config(project_path: Path) -> dict[str, t.Any]:
    pyproject_path = project_path / "pyproject.toml"

    if not pyproject_path.exists() or not tomli:
        return {
            "http_port": 8676,
            "http_host": "127.0.0.1",
            "http_enabled": False,
        }

    try:
        with pyproject_path.open("rb") as f:
            pyproject_data = tomli.load(f)

        crackerjack_config = pyproject_data.get("tool", {}).get("crackerjack", {})

        return {
            "http_port": crackerjack_config.get("mcp_http_port", 8676),
            "http_host": crackerjack_config.get("mcp_http_host", "127.0.0.1"),
            "http_enabled": crackerjack_config.get("mcp_http_enabled", False),
        }
    except Exception as e:
        console.print(
            f"[yellow]Warning: Failed to load MCP config from pyproject.toml: {e}[/yellow]"
        )
        return {
            "http_port": 8676,
            "http_host": "127.0.0.1",
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


# Export ASGI app for uvicorn (standardized startup pattern)
# Create a default server instance for uvicorn
_default_config = {"http_port": 8676, "http_host": "127.0.0.1"}
_default_mcp_app = create_mcp_server(_default_config)
http_app = _default_mcp_app.http_app if _default_mcp_app else None


def handle_mcp_server_command(
    start: bool = False,
    stop: bool = False,
    restart: bool = False,
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
            main(".", http_mode, http_port)
        except Exception as e:
            console.print(f"[red]Failed to start MCP server: {e}[/ red]")


def _initialize_context(context: MCPServerContext) -> None:
    set_context(context)

    context.safe_print("MCP Server context initialized")


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
) -> MCPServerContext:
    config = MCPServerConfig(
        project_path=project_path,
        rate_limit_config=RateLimitConfig(),
    )

    context = MCPServerContext(config)
    context.console = console

    _initialize_context(context)
    return context


def _print_server_info(
    project_path: Path,
    mcp_config: dict[str, t.Any],
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


def _show_server_startup_info(
    project_path: Path,
    mcp_config: dict[str, t.Any],
    http_mode: bool,
) -> None:
    """Show server startup information."""
    _print_server_info(project_path, mcp_config, http_mode)

    # Show final success panel before starting the server
    if mcp_config.get("http_enabled", False) or http_mode:
        http_endpoint = (
            f"http://{mcp_config['http_host']}:{mcp_config['http_port']}/mcp"
        )
    else:
        http_endpoint = None

    # Final startup success panel via mcp-common
    ServerPanels.startup_success(
        server_name="Crackerjack MCP",
        endpoint=http_endpoint,
    )


def main(
    project_path_arg: str = ".",
    http_mode: bool = False,
    http_port: int | None = None,
) -> None:
    if not MCP_AVAILABLE:
        return

    # Define runtime directory for Oneiric snapshots
    runtime_dir = Path(".oneiric_cache")

    try:
        project_path, mcp_config = _initialize_project_and_config(
            project_path_arg, http_port, http_mode
        )

        _setup_server_context(project_path)

        mcp_app = _create_and_validate_server(mcp_config)
        if not mcp_app:
            return

        # Initialize skill system with project context
        console.print("[cyan]Initializing skill system...[/ cyan]")
        try:
            initialize_skills(project_path, mcp_app)
            register_skill_tools(mcp_app)
            console.print("[green]✅ Skill system initialized[/ green]")
        except Exception as e:
            console.print(
                f"[yellow]⚠️  Skill system initialization failed: {e}[/ yellow]"
            )
            # Don't fail server startup if skills fail

        _show_server_startup_info(project_path, mcp_config, http_mode)

        # Write Oneiric runtime health snapshots before starting server
        pid = os.getpid()
        snapshot = RuntimeHealthSnapshot(
            orchestrator_pid=pid,
            watchers_running=True,
            lifecycle_state={
                "server_status": "running",
                "start_time": datetime.now().isoformat(),
                "http_mode": http_mode,
                "http_port": mcp_config.get("http_port") if http_mode else None,
            },
        )
        write_runtime_health(runtime_dir / "runtime_health.json", snapshot)
        write_pid_file(runtime_dir / "server.pid", pid)

        _run_mcp_server(mcp_app, mcp_config, http_mode)

    except KeyboardInterrupt:
        console.print("Server stopped by user")
    except Exception as e:
        console.print(f"Server error: {e}")
        import traceback

        traceback.print_exc()
    finally:
        # Update health snapshot on shutdown
        with suppress(Exception):
            snapshot = RuntimeHealthSnapshot(
                orchestrator_pid=os.getpid(),
                watchers_running=False,
                lifecycle_state={
                    "server_status": "stopped",
                    "shutdown_time": datetime.now().isoformat(),
                },
            )
            write_runtime_health(runtime_dir / "runtime_health.json", snapshot)

        clear_context()


if __name__ == "__main__":
    import sys

    project_path = "."
    http_mode = "--http" in sys.argv
    http_port = None

    non_flag_args = [arg for arg in sys.argv[1:] if not arg.startswith("--")]
    if non_flag_args:
        project_path = non_flag_args[0]

    if "--http-port" in sys.argv:
        port_idx = sys.argv.index("--http-port")
        if port_idx + 1 < len(sys.argv):
            http_port = int(sys.argv[port_idx + 1])

    main(project_path, http_mode, http_port)
