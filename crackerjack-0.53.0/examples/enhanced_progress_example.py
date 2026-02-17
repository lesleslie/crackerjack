import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from crackerjack.mcp.progress_monitor import (
        WEBSOCKET_AVAILABLE,
    )
    from rich.console import Console
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure crackerjack is properly installed and dependencies are available")
    sys.exit(1)


async def demo_websocket_monitoring() -> None:
    console = Console()

    console.print("[bold cyan]🚀 Enhanced Progress Monitoring Demo[ / bold cyan]")
    console.print(
        "[dim]This example shows the new WebSocket - based real - time progress display[ / dim]\n"
    )

    if not WEBSOCKET_AVAILABLE:
        console.print("[red]❌ WebSocket support not available[ / red]")
        console.print("[yellow]Install with: pip install websockets[ / yellow]")
        return

    console.print("[green]✅ WebSocket support available[ / green]")
    console.print("[cyan]Features enabled: [ / cyan]")
    console.print(" 🌐 Real - time progress streaming")
    console.print(" 🎨 Rich progress bars and displays")
    console.print(" 📊 Live stage progress updates")
    console.print(" 🔄 Automatic fallback to polling mode")
    console.print(" 🛑 Graceful interrupt handling\n")

    console.print("[bold blue]Usage Examples: [ / bold blue]")
    console.print("[cyan]1. Monitor a specific job by ID: [ / cyan]")
    console.print(" python - m crackerjack.mcp.progress_monitor abc123 - def456")
    console.print()
    console.print("[cyan]2. Monitor with custom WebSocket URL: [ / cyan]")
    console.print(
        " python - m crackerjack.mcp.progress_monitor abc123 - def456 ws: / / localhost: 8000"
    )
    console.print()
    console.print("[cyan]3. Use in Python code: [ / cyan]")
    console.print(
        " from crackerjack.mcp.progress_monitor import monitor_job_standalone"
    )
    console.print(" await monitor_job_standalone('job_id')")
    console.print()

    console.print("[bold blue]Architecture Features: [ / bold blue]")
    console.print(
        "🔗 [cyan]WebSocket Streaming: [ / cyan] Real - time progress updates via WebSocket"
    )
    console.print(
        "📊 [cyan]Rich Display: [ / cyan] Beautiful progress bars and formatted output"
    )
    console.print(
        "🔄 [cyan]Fallback Mode: [ / cyan] Automatic fallback to polling if WebSocket fails"
    )
    console.print(
        "🎯 [cyan]Stage Tracking: [ / cyan] Detailed progress for each stage (hooks, tests, etc.)"
    )
    console.print(
        "⚡ [cyan]Low Latency: [ / cyan] Sub - second progress updates vs 2 - second polling"
    )
    console.print()

    console.print(
        "[bold green]🎉 Enhanced progress monitoring is ready to use ! [ / bold green]"
    )
    console.print(
        "[dim]Start the MCP server with WebSocket support to see it in action[ / dim]"
    )


async def demo_api_integration() -> None:
    console = Console()

    console.print("\n[bold cyan]📋 API Integration Example[ / bold cyan]")
    console.print(
        "[dim]This shows how to use the enhanced monitoring in your code[ / dim]\n"
    )

    class MockClient:
        async def call_tool(self, tool_name: str, params: dict) -> dict:
            if tool_name == "execute_crackerjack":
                return {
                    "success": True,
                    "job_id": "demo - 123 - 456",
                    "message": "Job started successfully",
                }
            return {}

    console.print(
        "[yellow]💡 Note: This is a demo - replace MockClient with real MCP client[ / yellow]"
    )
    console.print()

    try:
        MockClient()
        console.print(
            "[cyan]Example: Starting enhanced progress monitoring...[ / cyan]"
        )

        console.print("[green]✅ Would start job with WebSocket monitoring[ / green]")
        console.print(
            "[blue]📡 Would connect to ws: / / localhost: 8000 / ws / progress / demo - 123 - 456[ / blue]"
        )
        console.print(
            "[magenta]🎨 Would display real - time Rich progress bars[ / magenta]"
        )

    except Exception as e:
        console.print(f"[red]❌ Demo error: {e}[ / red]")


def main() -> None:
    try:
        asyncio.run(demo_websocket_monitoring())
        asyncio.run(demo_api_integration())
    except KeyboardInterrupt:
        print("\n🛑 Demo interrupted")
    except Exception as e:
        print(f"❌ Demo error: {e}")


if __name__ == "__main__":
    main()
