import asyncio
import socket
import subprocess
import sys
from pathlib import Path

from rich.console import Console


def is_mcp_server_running(host: str = "localhost", port: int = 5173) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        result = sock.connect_ex((host, port))
        return result == 0
    finally:
        sock.close()


async def ensure_mcp_server_running() -> subprocess.Popen[bytes] | None:
    console = Console()

    if is_mcp_server_running():
        console.print("[green]✅ MCP server already running[/ green]")
        return None

    console.print("[yellow]🚀 Starting MCP server...[/ yellow]")
    server_process = subprocess.Popen(
        [sys.executable, "-m", "crackerjack", "--start-mcp-server"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )

    for _i in range(20):
        if is_mcp_server_running():
            console.print("[green]✅ MCP server started successfully[/ green]")
            return server_process
        await asyncio.sleep(0.5)

    console.print("[red]❌ Failed to start MCP server[/ red]")
    server_process.terminate()
    msg = "Failed to start MCP server within timeout period"
    raise RuntimeError(msg)


async def run_with_mcp_server(command: str = "/ crackerjack: run") -> None:
    console = Console()

    server_process = await ensure_mcp_server_running()

    try:
        Path(__file__).parent.parent / "__main__.py"

        # stdio_client( # type: ignore

        class MockSession:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return

            async def send_request(self, request):
                return {"result": "mocked_response", "session_id": "mock_session"}

        async with MockSession():
            try:
                console.print(
                    f"[yellow]Command '{command}' - WebSocket monitoring removed in Phase 1[/yellow]"
                )
            except Exception as e:
                console.print(f"[bold red]Error: {e}[/ bold red]")
                sys.exit(1)
    finally:
        if server_process:
            console.print(
                "[yellow]Note: MCP server continues running in background[/ yellow]",
            )


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Run Crackerjack commands through MCP with progress monitoring",
    )
    parser.add_argument(
        "command",
        nargs="?",
        default="/ crackerjack: run",
        help="Command to execute (default: / crackerjack: run)",
    )
    args = parser.parse_args()

    try:
        asyncio.run(run_with_mcp_server(args.command))
    except KeyboardInterrupt:
        Console().print("\n[yellow]Operation cancelled by user[/ yellow]")
        sys.exit(1)


if __name__ == "__main__":
    main()
