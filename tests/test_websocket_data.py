#!/usr/bin/env python3

import asyncio
import json
import time
from pathlib import Path

from rich.console import Console

console = Console()


async def test_websocket_flow():
    progress_dir = Path.home() / ".cache" / "crackerjack" / "progress"
    progress_dir.mkdir(parents=True, exist_ok=True)

    job_id = "websocket-test-123"
    progress_file = progress_dir / f"job-{job_id}.json"

    console.print("[cyan]Testing WebSocket Data Flow[/cyan]")
    console.print(f"Progress directory: {progress_dir}")
    console.print(f"Progress file: {progress_file}")

    console.print("\n[yellow]1. Writing initial progress data...[/yellow]")
    progress_data = {
        "job_id": job_id,
        "status": "running",
        "iteration": 1,
        "max_iterations": 10,
        "current_stage": "fast_hooks",
        "stage_progress": 25,
        "stage_total": 100,
        "stage_percentage": 25,
        "overall_progress": 10,
        "message": "Starting fast hooks...",
        "timestamp": time.time(),
        "project_path": str(Path.cwd()),
        "error_counts": {
            "hook_errors": 0,
            "hook_failures": 0,
            "test_failures": 0,
            "test_errors": 0,
        },
        "stage_status": {
            "fast_hooks": "running",
            "tests": "pending",
            "comprehensive_hooks": "pending",
        },
    }

    with progress_file.open("w") as f:
        json.dump(progress_data, f, indent=2)

    console.print("✅ Written initial progress data")

    console.print("\n[yellow]2. Instructions to test:[/yellow]")
    console.print("1. Start WebSocket server in another terminal: ")
    console.print(" python -m crackerjack --start-websocket-server")
    console.print("\n2. Start progress monitor in another terminal: ")
    console.print(f" python -m crackerjack.mcp.progress_monitor {job_id}")
    console.print("\n3. Or use the Textual dashboard: ")
    console.print(" python -m crackerjack --monitor")
    console.print("\n4. Press Enter to start updating progress...")

    input()

    stages = [
        ("fast_hooks", 50, 20, "Running ruff checks..."),
        ("fast_hooks", 75, 25, "Running trailing whitespace fixes..."),
        ("fast_hooks", 100, 30, "Fast hooks completed!"),
        ("tests", 25, 40, "Starting pytest..."),
        ("tests", 50, 50, "Running test suite..."),
        ("tests", 75, 60, "Tests almost done..."),
        ("tests", 100, 70, "Tests completed!"),
        ("comprehensive_hooks", 50, 85, "Running pyright..."),
        ("comprehensive_hooks", 100, 100, "All checks passed!"),
    ]

    for stage, stage_progress, overall_progress, message in stages:
        console.print(f"\n[cyan]Updating: {message}[/cyan]")

        if stage == "fast_hooks" and stage_progress == 100:
            progress_data["stage_status"]["fast_hooks"] = "passed"
        elif stage == "tests" and stage_progress == 100:
            progress_data["stage_status"]["tests"] = "passed"
        elif stage == "comprehensive_hooks" and stage_progress == 100:
            progress_data["stage_status"]["comprehensive_hooks"] = "passed"

        progress_data.update(
            {
                "current_stage": stage,
                "stage_progress": stage_progress,
                "stage_percentage": stage_progress,
                "overall_progress": overall_progress,
                "message": message,
                "timestamp": time.time(),
            }
        )

        with progress_file.open("w") as f:
            json.dump(progress_data, f, indent=2)

        await asyncio.sleep(2)

    progress_data["status"] = "completed"
    progress_data["message"] = "🎉 All checks passed!"

    with progress_file.open("w") as f:
        json.dump(progress_data, f, indent=2)

    console.print(
        "\n[green]✅ Test completed! Check if the monitor showed the updates.[/green]"
    )
    console.print("\nPress Enter to clean up...")
    input()

    if progress_file.exists():
        progress_file.unlink()
        console.print("🧹 Cleaned up test file")


if __name__ == "__main__":
    asyncio.run(test_websocket_flow())
