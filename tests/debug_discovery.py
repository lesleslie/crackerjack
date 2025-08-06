# !/ usr / bin / env python3

import asyncio

import aiohttp
from rich.console import Console

console = Console()


async def test_discovery():
    websocket_url = "ws: // localhost: 8675"
    http_url = websocket_url.replace("ws: // ", "http: // ")

    console.print(f"[cyan]Testing job discovery at: {http_url}[ / cyan]")

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{http_url} / ", timeout=aiohttp.ClientTimeout(total=2)
            ) as response:
                console.print(f"[green]Status: {response.status}[ / green]")

                if response.status == 200:
                    data = await response.json()
                    console.print("[yellow]Full response: [ / yellow]")
                    import json

                    console.print(json.dumps(data, indent=2))

                    active_jobs = data.get("active_jobs", [])
                    console.print(f"[cyan]Active jobs found: {active_jobs}[ / cyan]")

                    if active_jobs:
                        console.print("[green]✅ Discovery should work ! [ / green]")
                    else:
                        console.print("[red]❌ No active jobs found[ / red]")
                else:
                    console.print(f"[red]HTTP error: {response.status}[ / red]")

    except Exception as e:
        console.print(f"[red]Error: {e}[ / red]")


if __name__ == "__main__":
    asyncio.run(test_discovery())
