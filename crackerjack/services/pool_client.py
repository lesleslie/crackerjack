from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from rich.console import Console

logger = logging.getLogger(__name__)


class CrackerjackPoolClient:
    def __init__(
        self,
        mcp_server_url: str = "http://localhost: 8680",
        timeout: int = 300,
    ) -> None:
        self.mcp_server_url = mcp_server_url
        self.timeout = timeout
        self.pool_id: str | None = None
        self.console = Console()

    async def spawn_scanner_pool(
        self,
        min_workers: int = 2,
        max_workers: int = 8,
        pool_type: str = "mahavishnu",
        worker_type: str = "terminal-qwen",
        pool_name: str = "crackerjack-quality-scanners",
    ) -> str:
        self.console.print(f"[cyan]🔧 Spawning {pool_type} pool: {pool_name}[/cyan]")
        self.console.print(f"   • Workers: {min_workers}-{max_workers} ({worker_type})")

        result = await self._call_mcp_tool(
            "pool_spawn",
            pool_type=pool_type,
            name=pool_name,
            min_workers=min_workers,
            max_workers=max_workers,
            worker_type=worker_type,
        )

        if result.get("status") == "created":
            self.pool_id = result["pool_id"]
            self.console.print(f"[green]✅ Pool spawned: {self.pool_id}[/green]")
            return self.pool_id
        else:
            error_msg = result.get("error", "Unknown error")
            raise RuntimeError(f"Failed to spawn pool: {error_msg}")

    async def execute_tool_scan(
        self,
        tool_name: str,
        files: list[Path],
        timeout: int | None = None,
    ) -> dict[str, Any]:
        if not self.pool_id:
            raise RuntimeError("Pool not spawned. Call spawn_scanner_pool() first.")

        exec_timeout = timeout or self.timeout

        cmd = self._build_tool_command(tool_name, files)

        self.console.print(
            f"[blue]🔍 Executing {tool_name} on {len(files)} files[/blue]"
        )

        result = await self._call_mcp_tool(
            "pool_execute",
            pool_id=self.pool_id,
            prompt=f"Execute: {' '.join(map(str, cmd))}",
            timeout=exec_timeout,
        )

        return result

    async def list_pools(self) -> list[dict[str, Any]]:
        result = await self._call_mcp_tool("pool_list")

        pools = result.get("pools", [])
        self.console.print(f"[cyan]📋 Active pools: {len(pools)}[/cyan]")

        return pools

    async def get_pool_health(self, pool_id: str | None = None) -> dict[str, Any]:
        if pool_id:
            result = await self._call_mcp_tool(
                "pool_health",
                pool_id=pool_id,
            )
            self.console.print(
                f"[cyan]💓 Pool {pool_id} health: {result.get('status', 'unknown')}[/cyan]"
            )
            return result

        return await self._call_mcp_tool("pool_health")

    async def close_pool(self, pool_id: str | None = None) -> None:
        if pool_id:
            self.console.print(f"[yellow]🔒 Closing pool: {pool_id}[/yellow]")
            result = await self._call_mcp_tool(
                "pool_close",
                pool_id=pool_id,
            )
        else:
            self.console.print("[yellow]🔒 Closing all pools[/yellow]")
            result = await self._call_mcp_tool("pool_close_all")

        if result.get("status") == "closed":
            if pool_id:
                self.pool_id = None
            self.console.print("[green]✅ Pool(s) closed[/green]")

    async def _call_mcp_tool(
        self,
        tool_name: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        # TODO: Implement actual MCP JSON-RPC communication

        mock_responses = {
            "pool_spawn": {
                "status": "created",
                "pool_id": "test-pool-123",
            },
            "pool_execute": {
                "status": "completed",
                "output": "Mock execution output",
                "exit_code": 0,
            },
            "pool_list": {
                "pools": [
                    {
                        "pool_id": "test-pool-123",
                        "name": "test-pool",
                        "pool_type": "mahavishnu",
                        "workers": 8,
                    }
                ]
            },
            "pool_health": {
                "status": "healthy",
                "pools_active": 1,
            },
            "pool_close": {
                "status": "closed",
            },
            "pool_close_all": {
                "status": "closed",
            },
        }

        if tool_name in mock_responses:
            return mock_responses[tool_name]  # type: ignore

        logger.warning(f"Unknown tool: {tool_name}, returning mock response")
        return {
            "status": "error",
            "error": f"Unknown tool: {tool_name}",
        }

    def _build_tool_command(self, tool_name: str, files: list[Path]) -> list[str]:
        commands = {
            "refurb": ["refurb", *map(str, files)],
            "complexipy": ["complexipy", *map(str, files), "--path", "."],
            "skylos": ["skylos", *map(str, files)],
            "vulture": ["vulture", *map(str, files)],
            "ruff": ["ruff", "check", *map(str, files)],
            "mypy": ["mypy", *map(str, files)],
            "pylint": ["pylint", *map(str, files)],
            "semgrep": ["semgrep", "--config", "auto", *map(str, files)],
            "bandit": ["bandit", "-r", *map(str, files)],
        }

        return commands.get(tool_name, [])

    async def cleanup(self) -> None:
        if self.pool_id:
            await self.close_pool()
            self.console.print("[dim]Cleanup complete[/dim]")
