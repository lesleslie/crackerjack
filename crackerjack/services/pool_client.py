"""Mahavishnu Pool Client for Crackerjack quality scanning.

This module provides a client for interacting with Mahavishnu worker pools
to accelerate quality tool execution through parallel processing.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from pathlib import Path
from rich.console import Console

logger = logging.getLogger(__name__)


class CrackerjackPoolClient:
    """Client for Mahavishnu pool execution.

    This client manages communication with Mahavishnu MCP server to spawn
    worker pools and execute quality tools in parallel.
    """

    def __init__(
        self,
        mcp_server_url: str = "http://localhost:8680",
        timeout: int = 300,
    ) -> None:
        """Initialize the pool client.

        Args:
            mcp_server_url: URL of Mahavishnu MCP server
            timeout: Default timeout for tool execution (seconds)
        """
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
        """Spawn a worker pool for quality scanning.

        Args:
            min_workers: Minimum workers to spawn
            max_workers: Maximum workers for scaling
            pool_type: Type of pool (mahavishnu, session-buddy, kubernetes)
            worker_type: Type of workers (terminal-qwen, terminal-claude, container)
            pool_name: Name for the pool

        Returns:
            Pool ID for subsequent operations

        Raises:
            RuntimeError: If pool spawn fails
        """
        self.console.print(
            f"[cyan]🔧 Spawning {pool_type} pool: {pool_name}[/cyan]"
        )
        self.console.print(
            f"   • Workers: {min_workers}-{max_workers} ({worker_type})"
        )

        # Call Mahavishnu MCP tool: pool_spawn
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
            self.console.print(
                f"[green]✅ Pool spawned: {self.pool_id}[/green]"
            )
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
        """Execute a quality tool on specific files using pool.

        Args:
            tool_name: Tool to run (refurb, complexipy, skylos, etc.)
            files: List of files to scan
            timeout: Override default timeout

        Returns:
            Tool execution result with status, output, errors

        Raises:
            RuntimeError: If pool not spawned or execution fails
        """
        if not self.pool_id:
            raise RuntimeError(
                "Pool not spawned. Call spawn_scanner_pool() first."
            )

        exec_timeout = timeout or self.timeout

        # Build command for tool
        cmd = self._build_tool_command(tool_name, files)

        self.console.print(
            f"[blue]🔍 Executing {tool_name} on {len(files)} files[/blue]"
        )

        # Execute via mahavishnu pool
        result = await self._call_mcp_tool(
            "pool_execute",
            pool_id=self.pool_id,
            prompt=f"Execute: {' '.join(map(str, cmd))}",
            timeout=exec_timeout,
        )

        return result

    async def list_pools(self) -> list[dict[str, Any]]:
        """List all active pools.

        Returns:
            List of pool information dictionaries
        """
        result = await self._call_mcp_tool("pool_list")

        pools = result.get("pools", [])
        self.console.print(
            f"[cyan]📋 Active pools: {len(pools)}[/cyan]"
        )

        return pools

    async def get_pool_health(self, pool_id: str | None = None) -> dict[str, Any]:
        """Get health status of a pool.

        Args:
            pool_id: Pool ID to check (None for all pools)

        Returns:
            Health status dictionary
        """
        if pool_id:
            result = await self._call_mcp_tool(
                "pool_health",
                pool_id=pool_id,
            )
            self.console.print(
                f"[cyan]💓 Pool {pool_id} health: {result.get('status', 'unknown')}[/cyan]"
            )
            return result
        else:
            # Health check for all pools
            return await self._call_mcp_tool("pool_health")

    async def close_pool(self, pool_id: str | None = None) -> None:
        """Close a specific pool or all pools.

        Args:
            pool_id: Pool ID to close (None for all pools)
        """
        if pool_id:
            self.console.print(
                f"[yellow]🔒 Closing pool: {pool_id}[/yellow]"
            )
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
        """Call Mahavishnu MCP tool.

        This is a placeholder implementation. The actual implementation would
        use the MCP client protocol to communicate with the Mahavishnu server.
        """
        # TODO: Implement actual MCP JSON-RPC communication
        # For now, return mock responses

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
            return mock_responses[tool_name]

        # Fallback for unknown tools
        logger.warning(f"Unknown tool: {tool_name}, returning mock response")
        return {
            "status": "error",
            "error": f"Unknown tool: {tool_name}",
        }

    def _build_tool_command(self, tool_name: str, files: list[Path]) -> list[str]:
        """Build command line for tool execution.

        Args:
            tool_name: Tool to run
            files: Files to scan

        Returns:
            Command line as list of strings
        """
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
        """Cleanup resources.

        Close pool if open during cleanup.
        """
        if self.pool_id:
            await self.close_pool()
            self.console.print("[dim]Cleanup complete[/dim]")
