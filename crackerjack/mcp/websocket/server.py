import signal
import subprocess
import tempfile
import time
from pathlib import Path

import uvicorn
from rich.console import Console

from .app import create_websocket_app
from .jobs import JobManager

console = Console()


class WebSocketServer:
    def __init__(self, port: int = 8675) -> None:
        self.port = port
        self.progress_dir = Path(tempfile.gettempdir()) / "crackerjack-mcp-progress"
        self.is_running = True
        self.job_manager: JobManager | None = None
        self.app = None

    def setup(self) -> None:
        self.progress_dir.mkdir(exist_ok=True)

        self.job_manager = JobManager(self.progress_dir)

        self.app = create_websocket_app(self.job_manager, self.progress_dir)

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, _signum: int, _frame) -> None:
        console.print("\n[yellow]Shutting down WebSocket server...[/yellow]")
        self.is_running = False

    def run(self) -> None:
        try:
            self.setup()
            console.print(
                f"[green]Starting WebSocket server on port {self.port}[/green]",
            )
            console.print(f"Progress directory: {self.progress_dir}")
            console.print("Press Ctrl + C to stop")

            config = uvicorn.Config(
                app=self.app,
                port=self.port,
                host="127.0.0.1",
                log_level="info",
            )

            server = uvicorn.Server(config)
            server.run()

        except KeyboardInterrupt:
            console.print("\n[yellow]Server stopped by user[/yellow]")
        except Exception as e:
            console.print(f"[red]Server error: {e}[/red]")
        finally:
            pass  # Cleanup handled by FastAPI lifespan


def handle_websocket_server_command(
    start: bool = False,
    stop: bool = False,
    restart: bool = False,
    port: int = 8675,
) -> None:
    """Handle WebSocket server start/stop/restart commands."""
    if stop or restart:
        console.print("[yellow]Stopping WebSocket servers...[/yellow]")
        # Kill any existing uvicorn processes running on the port
        try:
            result = subprocess.run(
                ["pkill", "-f", f"uvicorn.*:{port}"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                console.print("[green]✅ WebSocket servers stopped[/green]")
            else:
                console.print("[dim]No WebSocket servers were running[/dim]")
        except subprocess.TimeoutExpired:
            console.print("[red]Timeout stopping WebSocket servers[/red]")
        except Exception as e:
            console.print(f"[red]Error stopping WebSocket servers: {e}[/red]")

        if stop:
            return

        # For restart, wait a moment before starting again
        time.sleep(2)

    if start or restart:
        console.print(f"[green]Starting WebSocket server on port {port}...[/green]")
        try:
            server = WebSocketServer(port)
            server.run()
        except Exception as e:
            console.print(f"[red]Failed to start WebSocket server: {e}[/red]")


def main(port: int = 8675) -> None:
    server = WebSocketServer(port)
    server.run()


if __name__ == "__main__":
    import sys

    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8675
    main(port)
