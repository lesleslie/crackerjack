"""Rich panel utilities for MCP server operations with consistent styling."""

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.text import Text


class ServerPanels:
    """Rich panel utilities for server operations with 74-char width limit."""

    WIDTH = 74  # Match session-mgmt-mcp width constraint

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def restart_header(self) -> None:
        """Display server restart header panel."""
        panel = Panel(
            "🔄 Restarting Crackerjack MCP Server...",
            width=self.WIDTH,
            title="Server Restart",
            style="cyan",
        )
        self.console.print(panel)

    def stop_servers(self, count: int) -> None:
        """Display stopping servers status."""
        self.console.print("📴 Stopping existing servers...")
        self.console.print(f"🛑 Stopping {count} server process(es)...")

    def process_stopped(self, pid: int) -> None:
        """Display process stopped message."""
        self.console.print(f"Stopping process {pid}...")
        self.console.print(f"✅ Process {pid} terminated gracefully")

    def stop_complete(self, count: int) -> None:
        """Display stop completion panel."""
        panel = Panel(
            f"✅ Successfully stopped {count} process(es)",
            width=self.WIDTH,
            title="Server Stopped",
            style="green",
        )
        self.console.print(panel)

    def cleanup_wait(self) -> None:
        """Display cleanup waiting message."""
        self.console.print("⏳ Waiting for cleanup...")

    def starting_server(self) -> None:
        """Display starting server message."""
        self.console.print("🚀 Starting fresh server instance...")
        self.console.print("🚀 Starting Crackerjack MCP Server...")
        self.console.print("⏳ Waiting for server to start...")

    def success_panel(
        self,
        http_endpoint: str | None = None,
        websocket_monitor: str | None = None,
        process_id: int | None = None,
    ) -> None:
        """Display success panel with server details."""
        content = Text()
        content.append("✅ Server started successfully!\n", style="green bold")

        if http_endpoint:
            content.append(f"🌐 HTTP Endpoint: {http_endpoint}\n", style="cyan")

        if websocket_monitor:
            content.append(f"🔌 WebSocket Monitor: {websocket_monitor}\n", style="cyan")

        if process_id:
            content.append(f"📊 Process ID: {process_id}", style="cyan")

        panel = Panel(
            content,
            width=self.WIDTH,
            title="Crackerjack MCP Server",
            style="green",
        )
        self.console.print(panel)

    def failure_panel(self, error: str) -> None:
        """Display failure panel with error details."""
        panel = Panel(
            f"❌ Server failed to start: {error}",
            width=self.WIDTH,
            title="Server Error",
            style="red",
        )
        self.console.print(panel)

    def start_panel(
        self,
        project_path: Path,
        mode: str = "STDIO",
        http_endpoint: str | None = None,
        websocket_port: int | None = None,
    ) -> None:
        """Display server start panel with configuration details."""
        content = Text()
        content.append("🚀 Starting Crackerjack MCP Server...\n", style="green bold")
        content.append(f"📁 Project: {project_path.name}\n", style="cyan")
        content.append(f"🔗 Mode: {mode}\n", style="cyan")

        if http_endpoint:
            content.append(f"🌐 HTTP: {http_endpoint}\n", style="cyan")

        if websocket_port:
            content.append(f"🔌 WebSocket: {websocket_port}", style="cyan")

        panel = Panel(
            content,
            width=self.WIDTH,
            title="Server Configuration",
            style="green",
        )
        self.console.print(panel)


def create_server_panels(console: Console | None = None) -> ServerPanels:
    """Factory function to create ServerPanels instance."""
    return ServerPanels(console)
