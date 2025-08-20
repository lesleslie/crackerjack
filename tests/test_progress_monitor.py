#!/usr/bin/env python3

import asyncio
import json
import tempfile
import time
from pathlib import Path

from rich.console import Console

console = Console()


async def test_progress_flow():
    with tempfile.TemporaryDirectory() as temp_dir:
        progress_dir = Path(temp_dir) / "progress"
        progress_dir.mkdir(exist_ok=True)

        job_id = "test-job-123"
        progress_file = progress_dir / f"job-{job_id}.json"

        console.print("[cyan]Testing Progress Monitor Data Flow[/cyan]")
        console.print(f"Progress directory: {progress_dir}")
        console.print(f"Progress file: {progress_file}")

        console.print("\n[yellow]1. Simulating MCP server writing progress...[/yellow]")
        progress_data = {
            "job_id": job_id,
            "status": "running",
            "iteration": 1,
            "max_iterations": 10,
            "current_stage": "fast_hooks",
            "stage_progress": 50,
            "stage_total": 100,
            "overall_progress": 15,
            "message": "Running fast hooks...",
            "timestamp": time.time(),
            "project_path": str(Path.cwd()),
        }

        with progress_file.open("w") as f:
            json.dump(progress_data, f, indent=2)

        console.print(
            f"✅ Written progress data: {json.dumps(progress_data, indent=2)}"
        )

        console.print("\n[yellow]2. Testing AsyncProgressMonitor...[/yellow]")

        try:
            from crackerjack.mcp.file_monitor import WATCHDOG_AVAILABLE

            console.print(f"Watchdog available: {WATCHDOG_AVAILABLE}")
        except ImportError as e:
            console.print(f"[red]Failed to import file_monitor module: {e}[/red]")
            return

        from crackerjack.mcp.file_monitor import AsyncProgressMonitor

        monitor = AsyncProgressMonitor(progress_dir)

        callback_called = False
        received_data = None

        def progress_callback(data):
            nonlocal callback_called, received_data
            callback_called = True
            received_data = data
            console.print(
                f"[green]✅ Callback received data: {json.dumps(data, indent=2)}[/green]"
            )

        monitor.subscribe(job_id, progress_callback)

        console.print(f"Subscribers for {job_id}: {job_id in monitor.subscribers}")
        console.print(
            f"Observer state: {monitor.observer is not None if hasattr(monitor, 'observer') else 'N/A'}"
        )

        await monitor.start()

        await asyncio.sleep(0.5)

        console.print("\n[yellow]3. Updating progress file...[/yellow]")
        progress_data["stage_progress"] = 75
        progress_data["message"] = "Fast hooks almost done..."
        progress_data["timestamp"] = time.time()

        with progress_file.open("w") as f:
            json.dump(progress_data, f, indent=2)

        await asyncio.sleep(2.0)

        if callback_called:
            console.print("\n[green]✅ SUCCESS: Callback was triggered![/green]")
            console.print(f"Received data matches: {received_data == progress_data}")
        else:
            console.print("\n[red]❌ FAILURE: Callback was NOT triggered![/red]")

            console.print("\n[yellow]Trying PollingProgressMonitor...[/yellow]")
            from crackerjack.mcp.file_monitor import PollingProgressMonitor

            polling_monitor = PollingProgressMonitor(progress_dir)
            polling_monitor.subscribe(job_id, progress_callback)
            await polling_monitor.start()

            progress_data["stage_progress"] = 90
            with progress_file.open("w") as f:
                json.dump(progress_data, f, indent=2)

            await asyncio.sleep(2.0)

            if callback_called:
                console.print("[green]✅ Polling monitor worked![/green]")
            else:
                console.print("[red]❌ Polling monitor also failed![/red]")

            await polling_monitor.stop()

        await monitor.stop()

        console.print("\n[yellow]4. Testing WebSocket server integration...[/yellow]")
        console.print("To test WebSocket: ")
        console.print(
            "1. Start WebSocket server: python -m crackerjack --websocket-server"
        )
        console.print("2. Connect to: ws://localhost:8675/ws/progress/test-job-123")
        console.print("3. You should receive the progress updates")


if __name__ == "__main__":
    asyncio.run(test_progress_flow())
