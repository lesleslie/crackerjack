#!/usr/bin/env python3
"""Typer-based CLI for Session Management MCP Server.

Provides CLI interface matching crackerjack's server management pattern
with boolean options instead of subcommands.
"""

import os
import subprocess
import sys
import time
import warnings
from pathlib import Path

# Suppress transformers warnings about PyTorch/TensorFlow
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
warnings.filterwarnings("ignore", message=".*PyTorch.*TensorFlow.*Flax.*")

import psutil
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = typer.Typer(
    name="session-mgmt-mcp",
    help="Session Management MCP Server - CLI matching crackerjack pattern",
    no_args_is_help=True,
)

# Constants for typer.Option to fix FBT003 boolean positional values
DEFAULT_FALSE = False

console = Console()


def find_server_processes() -> list[psutil.Process]:
    """Find running session-mgmt-mcp server processes."""
    processes = []
    for proc in psutil.process_iter(["pid", "name", "cmdline"]):
        try:
            cmdline = proc.info["cmdline"] or []
            cmdline_str = " ".join(cmdline)

            # Look for various patterns that indicate a session-mgmt-mcp server
            is_session_mcp = (
                "session_mgmt_mcp" in cmdline_str or "session-mgmt-mcp" in cmdline_str
            )

            # Check if it's running a server (various ways to start)
            is_server = (
                "server.py" in cmdline_str
                or "session_mgmt_mcp.server" in cmdline_str
                or "--http" in cmdline_str
                or
                # Check if it's bound to our ports (for HTTP mode)
                any(
                    conn.laddr.port in [8678, 8677]
                    for conn in proc.net_connections()
                    if conn.laddr
                )
            )

            # Exclude CLI processes that are not servers
            is_cli_only = (
                "--start-mcp-server" in cmdline_str
                or "--stop-mcp-server" in cmdline_str
                or "--status" in cmdline_str
                or "--version" in cmdline_str
            )

            if is_session_mcp and is_server and not is_cli_only:
                processes.append(proc)

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return processes


def get_server_status() -> dict:
    """Get comprehensive server status information."""
    processes = find_server_processes()
    status = {
        "running": len(processes) > 0,
        "process_count": len(processes),
        "processes": [],
        "http_port": 8678,
        "websocket_port": 8677,
    }

    for proc in processes:
        try:
            status["processes"].append(
                {
                    "pid": proc.pid,
                    "memory_mb": proc.memory_info().rss / 1024 / 1024,
                    "cpu_percent": proc.cpu_percent(),
                    "create_time": proc.create_time(),
                }
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    return status


def show_status() -> None:
    """Show comprehensive server status information."""
    server_status = get_server_status()

    # Create status table
    table = Table(title="Session Management MCP Server Status")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")

    status_color = "green" if server_status["running"] else "red"
    status_text = "Running" if server_status["running"] else "Stopped"
    table.add_row("Status", f"[{status_color}]{status_text}[/{status_color}]")
    table.add_row("Process Count", str(server_status["process_count"]))
    table.add_row("HTTP Port", str(server_status["http_port"]))
    table.add_row("WebSocket Port", str(server_status["websocket_port"]))

    if server_status["running"]:
        table.add_row(
            "HTTP Endpoint", f"http://127.0.0.1:{server_status['http_port']}/mcp"
        )
        table.add_row(
            "WebSocket Monitor", f"ws://127.0.0.1:{server_status['websocket_port']}"
        )

    console.print(table)

    # Show process details if running
    if server_status["processes"]:
        process_table = Table(title="Running Processes")
        process_table.add_column("PID", style="cyan")
        process_table.add_column("Memory (MB)", style="yellow")
        process_table.add_column("CPU %", style="magenta")

        for proc_info in server_status["processes"]:
            process_table.add_row(
                str(proc_info["pid"]),
                f"{proc_info['memory_mb']:.1f}",
                f"{proc_info['cpu_percent']:.1f}",
            )

        console.print(process_table)


def start_mcp_server(
    port: int | None = None,
    websocket_port: int | None = None,
    verbose: bool = False,
) -> None:
    """Start the session management MCP server."""
    server_status = get_server_status()

    if server_status["running"]:
        console.print(
            Panel(
                f"[yellow]⚠️  Server already running with {server_status['process_count']} process(es)[/yellow]",
                title="Server Status",
            )
        )

        console.print("[yellow]⚠️  Stopping existing server first...[/yellow]")
        stop_mcp_server()
        time.sleep(2)

    console.print("[blue]🚀 Starting Session Management MCP Server...[/blue]")

    try:
        # Start server in HTTP mode so it can be properly detected by process monitoring
        # Use the configured ports or defaults
        http_port = port or 8678
        ws_port = websocket_port or 8677

        cmd = [
            sys.executable,
            "-c",
            f"from session_mgmt_mcp.server import main; main(http_mode=True, http_port={http_port})",
        ]

        process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL if not verbose else None,
            stderr=subprocess.DEVNULL if not verbose else None,
            start_new_session=True,
        )

        # Wait a moment for server to start and bind to ports
        console.print("[cyan]⏳ Waiting for server to start...[/cyan]")
        time.sleep(4)

        # Check if process is still running
        if process.poll() is not None:  # Process has exited
            console.print(
                f"[red]❌ Server process exited with code {process.returncode}[/red]"
            )
            if not verbose:
                console.print(
                    "[yellow]💡 Try --verbose flag to see startup errors[/yellow]"
                )
            raise typer.Exit(1)

        # Check if server is detected by our process monitoring
        final_status = get_server_status()
        if final_status["running"]:
            console.print(
                Panel(
                    f"[green]✅ Server started successfully![/green]\n"
                    f"🌐 HTTP Endpoint: http://127.0.0.1:{http_port}/mcp\n"
                    f"🔌 WebSocket Monitor: ws://127.0.0.1:{ws_port}\n"
                    f"📊 Process ID: {final_status['processes'][0]['pid']}",
                    title="Session Management MCP Server",
                )
            )
        else:
            console.print(
                Panel(
                    "[yellow]⚠️ Server process is running but not responding on expected ports[/yellow]\n"
                    f"Process might be starting in STDIO mode instead of HTTP mode.\n"
                    f"Process ID: {process.pid}",
                    title="Warning",
                )
            )

    except Exception as e:
        console.print(f"[red]❌ Failed to start server: {e}[/red]")
        if not verbose:
            console.print("[yellow]💡 Try --verbose flag for more details[/yellow]")
        raise typer.Exit(1)

    return True


def stop_mcp_server() -> bool:
    """Stop all running session management MCP servers."""
    processes = find_server_processes()

    if not processes:
        console.print(
            Panel(
                "[yellow]⚠️ No running server processes found[/yellow]\n"
                "Server may already be stopped or running in STDIO mode.",
                title="Server Status",
            )
        )
        return True  # Not an error if already stopped

    console.print(f"[blue]🛑 Stopping {len(processes)} server process(es)...[/blue]")

    stopped_count = 0
    for proc in processes:
        try:
            console.print(f"[cyan]Stopping process {proc.pid}...[/cyan]")

            # Try graceful termination first
            proc.terminate()

            # Wait up to 5 seconds for graceful shutdown
            try:
                proc.wait(timeout=5)
                console.print(
                    f"[green]✅ Process {proc.pid} terminated gracefully[/green]"
                )
                stopped_count += 1
            except psutil.TimeoutExpired:
                # Force kill if graceful shutdown failed
                console.print(
                    f"[yellow]⚡ Force killing process {proc.pid}...[/yellow]"
                )
                proc.kill()
                proc.wait()
                console.print(f"[green]✅ Process {proc.pid} force killed[/green]")
                stopped_count += 1

        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            console.print(f"[red]❌ Failed to stop process {proc.pid}: {e}[/red]")

    if stopped_count > 0:
        console.print(
            Panel(
                f"[green]✅ Successfully stopped {stopped_count} process(es)[/green]",
                title="Server Stopped",
            )
        )
    else:
        console.print("[red]❌ Failed to stop any processes[/red]")
        return False

    return True


def restart_mcp_server(
    port: int | None = None,
    websocket_port: int | None = None,
    verbose: bool = False,
) -> bool:
    """Restart the session management MCP server (stop and start)."""
    console.print(
        Panel(
            "[blue]🔄 Restarting Session Management MCP Server...[/blue]",
            title="Server Restart",
        )
    )

    # Stop existing servers
    console.print("[cyan]📴 Stopping existing servers...[/cyan]")
    stop_mcp_server()

    # Wait for cleanup
    console.print("[cyan]⏳ Waiting for cleanup...[/cyan]")
    time.sleep(2)

    # Start new server
    console.print("[cyan]🚀 Starting fresh server instance...[/cyan]")
    return start_mcp_server(port=port, websocket_port=websocket_port, verbose=verbose)


def show_version() -> None:
    """Show version information."""
    console.print(
        Panel(
            "[cyan]Session Management MCP Server[/cyan]\n"
            "[yellow]Version: 2.0.0[/yellow]\n"
            "[green]FastMCP-based server for Claude session management[/green]",
            title="Version Information",
        )
    )


def show_logs(lines: int = 50, follow: bool = False) -> None:
    """Show server logs."""
    log_dir = Path.home() / ".cache" / "claude" / "session_management"
    log_pattern = "session_management_*.log"

    if not log_dir.exists():
        console.print("[red]❌ Log directory not found[/red]")
        raise typer.Exit(1)

    log_files = list(log_dir.glob(log_pattern))
    if not log_files:
        console.print("[red]❌ No log files found[/red]")
        raise typer.Exit(1)

    # Get the most recent log file
    latest_log = max(log_files, key=lambda f: f.stat().st_mtime)
    console.print(f"[cyan]📄 Showing logs from: {latest_log}[/cyan]")

    try:
        if follow:
            subprocess.run(
                ["tail", "-f", "-n", str(lines), str(latest_log)], check=False
            )
        else:
            subprocess.run(["tail", "-n", str(lines), str(latest_log)], check=False)
    except KeyboardInterrupt:
        console.print("\n[yellow]📝 Log following stopped[/yellow]")
    except FileNotFoundError:
        console.print("[red]❌ 'tail' command not found[/red]")


def show_config() -> None:
    """Show current server configuration."""
    config_table = Table(title="Server Configuration")
    config_table.add_column("Setting", style="cyan")
    config_table.add_column("Value", style="green")

    # Read configuration from pyproject.toml
    try:
        import tomli

        project_root = Path(__file__).parent.parent
        pyproject_path = project_root / "pyproject.toml"

        if pyproject_path.exists():
            with open(pyproject_path, "rb") as f:
                data = tomli.load(f)

            config = data.get("tool", {}).get("session-mgmt-mcp", {})

            config_table.add_row("HTTP Port", str(config.get("mcp_http_port", 8678)))
            config_table.add_row("HTTP Host", config.get("mcp_http_host", "127.0.0.1"))
            config_table.add_row(
                "WebSocket Port", str(config.get("websocket_monitor_port", 8677))
            )
            config_table.add_row("HTTP Enabled", str(config.get("http_enabled", True)))

        else:
            config_table.add_row("Status", "[red]pyproject.toml not found[/red]")

    except ImportError:
        config_table.add_row("Status", "[red]tomli not available[/red]")
    except Exception as e:
        config_table.add_row("Error", f"[red]{e}[/red]")

    console.print(config_table)


@app.command()
def main(
    start_mcp_server: bool = typer.Option(
        DEFAULT_FALSE,
        "--start-mcp-server",
        help="Start MCP server for session management",
    ),
    stop_mcp_server: bool = typer.Option(
        DEFAULT_FALSE,
        "--stop-mcp-server",
        help="Stop all running MCP servers",
    ),
    restart_mcp_server: bool = typer.Option(
        DEFAULT_FALSE,
        "--restart-mcp-server",
        help="Restart MCP server (stop and start again)",
    ),
    status: bool = typer.Option(
        DEFAULT_FALSE,
        "--status",
        help="Show comprehensive server status information",
    ),
    version: bool = typer.Option(
        DEFAULT_FALSE,
        "--version",
        help="Show version information",
    ),
    config: bool = typer.Option(
        DEFAULT_FALSE,
        "--config",
        help="Show current server configuration",
    ),
    logs: bool = typer.Option(
        DEFAULT_FALSE,
        "--logs",
        help="Show server logs",
    ),
    port: int | None = typer.Option(
        None,
        "--port",
        help="HTTP server port (for start/restart)",
    ),
    websocket_port: int | None = typer.Option(
        None,
        "--websocket-port",
        help="WebSocket monitor port (for start/restart)",
    ),
    verbose: bool = typer.Option(
        DEFAULT_FALSE,
        "--verbose",
        help="Enable verbose output",
    ),
) -> None:
    """Session Management MCP Server - CLI matching crackerjack pattern."""
    # Handle server management commands (like crackerjack)
    if start_mcp_server:
        start_mcp_server_func(port=port, websocket_port=websocket_port, verbose=verbose)
        return

    if stop_mcp_server:
        stop_mcp_server_func()
        return

    if restart_mcp_server:
        restart_mcp_server_func(
            port=port, websocket_port=websocket_port, verbose=verbose
        )
        return

    # Handle status/info commands
    if status:
        show_status()
        return

    if version:
        show_version()
        return

    if config:
        show_config()
        return

    if logs:
        show_logs()
        return

    # If no options provided, show help
    console.print(
        "[yellow]No command specified. Use --help for available options.[/yellow]"
    )


# Rename functions to avoid conflicts with parameter names
start_mcp_server_func = start_mcp_server
stop_mcp_server_func = stop_mcp_server
restart_mcp_server_func = restart_mcp_server


if __name__ == "__main__":
    app()
