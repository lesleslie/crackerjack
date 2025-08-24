#!/usr/bin/env python3

import asyncio

from rich.console import Console

from crackerjack.mcp.progress_monitor import run_progress_monitor


async def test() -> None:
    console = Console()
    console.print("[yellow]Starting enhanced monitor test...[/yellow]")

    try:
        await asyncio.wait_for(
            run_progress_monitor(enable_watchdog=False), timeout=10.0,
        )
    except TimeoutError:
        console.print("\n[yellow]Monitor timed out after 10 seconds[/yellow]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Monitor stopped[/yellow]")


if __name__ == "__main__":
    asyncio.run(test())
