import os
import signal
import sys
import time
import typing as t
from pathlib import Path

from rich.console import Console

from .secure_subprocess import execute_secure_subprocess
from .security_logger import get_security_logger


def find_mcp_server_processes() -> list[dict[str, t.Any]]:
    """Find running MCP server processes using secure subprocess execution."""
    security_logger = get_security_logger()

    try:
        # Use secure subprocess execution with validation
        result = execute_secure_subprocess(
            command=["ps", "aux"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10.0,  # 10 second timeout for process listing
        )

        return _parse_mcp_processes(result.stdout)

    except Exception as e:
        security_logger.log_subprocess_failure(
            command=["ps", "aux"],
            exit_code=-1,
            error_output=str(e),
        )
        return []


def _parse_mcp_processes(stdout: str) -> list[dict[str, t.Any]]:
    """Parse MCP server processes from ps command output."""
    processes: list[dict[str, t.Any]] = []
    str(Path.cwd())

    for line in stdout.splitlines():
        if _is_mcp_server_process(line):
            process_info = _extract_process_info(line)
            if process_info:
                processes.append(process_info)

    return processes


def _is_mcp_server_process(line: str) -> bool:
    """Check if a line represents an MCP server process."""
    return (
        "crackerjack" in line
        and "--start-mcp-server" in line
        and "python" in line.lower()
    )


def _extract_process_info(line: str) -> dict[str, t.Any] | None:
    """Extract process information from a ps output line."""
    parts = line.split()
    if len(parts) < 11:
        return None

    try:
        pid = int(parts[1])
        # Find where the command actually starts (usually after the time field)
        command_start_index = _find_command_start_index(parts)

        return {
            "pid": pid,
            "command": " ".join(parts[command_start_index:]),
            "user": parts[0],
            "cpu": parts[2],
            "mem": parts[3],
        }
    except (ValueError, IndexError):
        return None


def _find_command_start_index(parts: list[str]) -> int:
    """Find the index where the command starts in ps output."""
    command_start_index = 10
    for i, part in enumerate(parts):
        if part.endswith("python") or "Python" in part:
            command_start_index = i
            break
    return command_start_index


def find_websocket_server_processes() -> list[dict[str, t.Any]]:
    """Find running WebSocket server processes using secure subprocess execution."""
    security_logger = get_security_logger()

    try:
        # Use secure subprocess execution with validation
        result = execute_secure_subprocess(
            command=["ps", "aux"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10.0,  # 10 second timeout for process listing
        )

        processes: list[dict[str, t.Any]] = []

        for line in result.stdout.splitlines():
            if "crackerjack" in line and "- - start - websocket-server" in line:
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

    except Exception as e:
        security_logger.log_subprocess_failure(
            command=["ps", "aux"],
            exit_code=-1,
            error_output=str(e),
        )
        return []


def stop_process(pid: int, force: bool = False) -> bool:
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
    if console is None:
        console = Console()

    processes = find_mcp_server_processes()

    if not processes:
        console.print("[yellow]⚠️ No MCP server processes found[/ yellow]")
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
    if console is None:
        console = Console()

    processes = find_websocket_server_processes()

    if not processes:
        console.print("[yellow]⚠️ No WebSocket server processes found[/ yellow]")
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
    if console is None:
        console = Console()

    mcp_success = stop_mcp_server(console)
    websocket_success = stop_websocket_server(console)

    return mcp_success and websocket_success


def restart_mcp_server(
    websocket_port: int | None = None,
    console: Console | None = None,
) -> bool:
    if console is None:
        console = Console()

    console.print("[bold cyan]🔄 Restarting MCP server...[/ bold cyan]")

    stop_mcp_server(console)

    console.print("⏳ Waiting for cleanup...")
    time.sleep(2)

    console.print("🚀 Starting new MCP server...")
    try:
        # Build command with proper argument formatting
        cmd = [sys.executable, "-m", "crackerjack", "--start-mcp-server"]
        if websocket_port:
            cmd.extend(["--websocket-port", str(websocket_port)])

        # Use secure subprocess execution for server restart
        import subprocess

        subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

        # Log the secure server start
        security_logger = get_security_logger()
        security_logger.log_subprocess_execution(
            command=cmd,
            purpose="mcp_server_restart",
        )

        console.print("✅ MCP server restart initiated")
        return True

    except Exception as e:
        console.print(f"❌ Failed to restart MCP server: {e}")
        return False


def list_server_status(console: Console | None = None) -> None:
    if console is None:
        console = Console()

    console.print("[bold cyan]📊 Crackerjack Server Status[/ bold cyan]")

    mcp_processes = find_mcp_server_processes()
    websocket_processes = find_websocket_server_processes()

    if mcp_processes:
        console.print("\n[bold green]MCP Servers: [/ bold green]")
        for proc in mcp_processes:
            console.print(
                f" • PID {proc['pid']} - CPU: {proc['cpu']}%-Memory: {proc['mem']}%",
            )
            console.print(f" Command: {proc['command']}")
    else:
        console.print("\n[yellow]MCP Servers: None running[/ yellow]")

    if websocket_processes:
        console.print("\n[bold green]WebSocket Servers: [/ bold green]")
        for proc in websocket_processes:
            console.print(
                f" • PID {proc['pid']} - CPU: {proc['cpu']}%-Memory: {proc['mem']}%",
            )
            console.print(f" Command: {proc['command']}")
    else:
        console.print("\n[yellow]WebSocket Servers: None running[/ yellow]")

    if not mcp_processes and not websocket_processes:
        console.print("\n[dim]No crackerjack servers currently running[/ dim]")
