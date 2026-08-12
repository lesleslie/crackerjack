from __future__ import annotations

import asyncio
import os

import httpx
import typer
from rich.console import Console

from crackerjack.skills.health import DEFAULT_SESSION_BUDDY_URL, DEFAULT_TIMEOUT_SECONDS

app = typer.Typer(
    name="skills",
    help=(
        "Skill-distillation operational tools. Refresh runs `distill_skills_now` "
        "and is intended for cron use; `audit skills` is for interactive/CI use."
    ),
    no_args_is_help=True,
)
console = Console()


@app.callback()
def _skills_callback() -> None:
    """Skills subcommand group: makes `refresh` invocable by name on its own."""


async def _post_json(url: str, *, json: dict, timeout: float) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout) as client:
        return await client.post(url, json=json)


def _distill_payload() -> dict[str, object]:
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": "distill_skills_now",
            "arguments": {},
        },
    }


@app.command()
def refresh(
    session_buddy_url: str | None = typer.Option(
        None,
        "--session-buddy-url",
        help="Override Session-Buddy MCP URL.",
    ),
    timeout_seconds: float = typer.Option(
        DEFAULT_TIMEOUT_SECONDS,
        "--timeout",
        help="Per-request timeout in seconds.",
    ),
) -> None:
    """Call `distill_skills_now` on Session-Buddy. Cron-friendly."""
    url = session_buddy_url or os.environ.get(
        "SESSION_BUDDY_MCP_URL", DEFAULT_SESSION_BUDDY_URL
    )
    payload = _distill_payload()

    try:
        resp = asyncio.run(_post_json(url, json=payload, timeout=timeout_seconds))
        resp.raise_for_status()
    except (httpx.HTTPError, OSError) as exc:
        console.print(f"[red][skill-coverage] refresh failed: {exc}[/red]")
        raise typer.Exit(1) from exc

    console.print(f"[green][skill-coverage] OK: distill_skills_now → {url}[/green]")


__all__ = ["_distill_payload", "_post_json", "app"]
