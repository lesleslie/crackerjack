import os
import signal
import subprocess
import sys
import time
import typing as t
from pathlib import Path

from rich.console import Console


def find_mcp_server_processes() -> list[dict[str, t.Any]]:
    """Find all running MCP server processes for this project."""
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            check=True,
        )

        processes: list[dict[str, t.Any]] = []
        str(Path.cwd())

        for line in result.stdout.splitlines():
            if "crackerjack" in line and "--start-mcp-server" in line:
                parts = line.split()
                if len(parts) >= 11:
                    try:
                        pid = int(parts[1])
                        processes.append(
                            {
                                "pid": pid,
                                "command": " ".join(parts[10:]),
                                "user": parts[0],
                                "cpu": parts[2],
                                "mem": parts[3],
                            },
                        )
                    except (ValueError, IndexError):
                        continue

        return processes

    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def find_websocket_server_processes() -> list[dict[str, t.Any]]:
    """Find all running WebSocket server processes for this project."""
    try:
        result = subprocess.run(
            ["ps", "aux"],
            capture_output=True,
            text=True,
            check=True,
        )

        processes: list[dict[str, t.Any]] = []

        for line in result.stdout.splitlines():
            if "crackerjack" in line and "--start-websocket-server" in line:
                parts = line.split()
                if len(parts) >= 11:
                    try:
                        pid = int(parts[1])
                        processes.append(
                            {
                                "pid": pid,
                                "command": " ".join(parts[10:]),
                                "user": parts[0],
                                "cpu": parts[2],
                                "mem": parts[3],
                            },
                        )
                    except (ValueError, IndexError):
                        continue

        return processes

    except (subprocess.CalledProcessError, FileNotFoundError):
        return []


def stop_process(pid: int, force: bool = False) -> bool:
    """Stop a process by PID."""
    try:
        if force:
            os.kill(pid, signal.SIGKILL)
        else:
            os.kill(pid, signal.SIGTERM)

        for _ in range(10):
            try:
                os.kill(pid, 0)
                time.sleep(0.5)
            except OSError:
                return True

        if not force:
            os.kill(pid, signal.SIGKILL)
            time.sleep(1)

        return True

    except (OSError, ProcessLookupError):
        return True


def stop_mcp_server(console: Console | None = None) -> bool:
    """Stop all MCP server processes."""
    if console is None:
        console = Console()

    processes = find_mcp_server_processes()

    if not processes:
        console.print("[yellow]⚠️ No MCP server processes found[/yellow]")
        return True

    success = True
    for proc in processes:
        console.print(f"🛑 Stopping MCP server process {proc['pid']}")
        if stop_process(proc["pid"]):
            console.print(f"✅ Stopped process {proc['pid']}")
        else:
            console.print(f"❌ Failed to stop process {proc['pid']}")
            success = False

    return success


def stop_websocket_server(console: Console | None = None) -> bool:
    """Stop all WebSocket server processes."""
    if console is None:
        console = Console()

    processes = find_websocket_server_processes()

    if not processes:
        console.print("[yellow]⚠️ No WebSocket server processes found[/yellow]")
        return True

    success = True
    for proc in processes:
        console.print(f"🛑 Stopping WebSocket server process {proc['pid']}")
        if stop_process(proc["pid"]):
            console.print(f"✅ Stopped process {proc['pid']}")
        else:
            console.print(f"❌ Failed to stop process {proc['pid']}")
            success = False

    return success


def stop_all_servers(console: Console | None = None) -> bool:
    """Stop all crackerjack server processes."""
    if console is None:
        console = Console()

    mcp_success = stop_mcp_server(console)
    websocket_success = stop_websocket_server(console)

    return mcp_success and websocket_success


def restart_mcp_server(
    websocket_port: int | None = None,
    console: Console | None = None,
) -> bool:
    """Restart the MCP server."""
    if console is None:
        console = Console()

    console.print("[bold cyan]🔄 Restarting MCP server...[/bold cyan]")

    stop_mcp_server(console)

    console.print("⏳ Waiting for cleanup...")
    time.sleep(2)

    console.print("🚀 Starting new MCP server...")
    try:
        cmd = [sys.executable, "-m", "crackerjack", "--start-mcp-server"]
        if websocket_port:
            cmd.extend(["--websocket-port", str(websocket_port)])

        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        console.print("✅ MCP server restart initiated")
        return True

    except Exception as e:
        console.print(f"❌ Failed to restart MCP server: {e}")
        return False


def list_server_status(console: Console | None = None) -> None:
    """List status of all crackerjack servers."""
    if console is None:
        console = Console()

    console.print("[bold cyan]📊 Crackerjack Server Status[/bold cyan]")

    mcp_processes = find_mcp_server_processes()
    websocket_processes = find_websocket_server_processes()

    if mcp_processes:
        console.print("\n[bold green]MCP Servers:[/bold green]")
        for proc in mcp_processes:
            console.print(
                f"  • PID {proc['pid']} - CPU: {proc['cpu']}% - Memory: {proc['mem']}%",
            )
            console.print(f"    Command: {proc['command']}")
    else:
        console.print("\n[yellow]MCP Servers: None running[/yellow]")

    if websocket_processes:
        console.print("\n[bold green]WebSocket Servers:[/bold green]")
        for proc in websocket_processes:
            console.print(
                f"  • PID {proc['pid']} - CPU: {proc['cpu']}% - Memory: {proc['mem']}%",
            )
            console.print(f"    Command: {proc['command']}")
    else:
        console.print("\n[yellow]WebSocket Servers: None running[/yellow]")

    if not mcp_processes and not websocket_processes:
        console.print("\n[dim]No crackerjack servers currently running[/dim]")
