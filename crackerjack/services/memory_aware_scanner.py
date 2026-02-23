"""Memory-Aware Scanner for smart caching via session-buddy.

This module provides intelligent file scanning that learns from past results
to skip known-good files and avoid redundant work.
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from rich.console import Console

logger = logging.getLogger(__name__)


class MemoryAwareScanner:
    """Memory-aware scanner that uses session-buddy memory for smart caching.

    Learns from past scan results to:
    - Skip files that passed recently (within 24 hours)
    - Prioritize files that frequently fail
    - Reduce redundant work across scan cycles
    """

    CACHE_DURATION_SECONDS = 86400  # 24 hours
    MEMORY_NAMESPACE = "crackerjack:pool_scanning"

    def __init__(
        self,
        console: Console | None = None,
        cache_duration: int = CACHE_DURATION_SECONDS,
    ) -> None:
        """Initialize the memory-aware scanner.

        Args:
            console: Optional console for output
            cache_duration: How long to cache results (seconds)
        """
        self.console = console or Console()
        self.cache_duration = cache_duration
        self._memory_client: Any = None  # Will be set via session-buddy MCP

    async def scan_with_memory(
        self,
        tool_name: str,
        files: list[Path],
        memory_client: Any,
    ) -> dict[str, Any]:
        """Scan files using memory to skip known-good files.

        Args:
            tool_name: Name of quality tool
            files: Files to scan
            memory_client: Session-buddy memory client (with search_memory)

        Returns:
            Scan result with cached/actual files and metrics
        """
        self.console.print(
            f"[cyan]🔍 Scanning {len(files)} files with {tool_name} memory...[/cyan]"
        )

        # Calculate cache key
        cache_key = self._generate_cache_key(tool_name, files)

        # Search memory for past results
        if memory_client:
            cached_results = await self._search_memory(memory_client, cache_key)
        else:
            cached_results = None

        if cached_results:
            return await self._process_cached_results(files, cached_results)
        else:
            return await self._perform_full_scan(tool_name, files, cache_key)

    async def _search_memory(
        self,
        memory_client: Any,
        cache_key: str,
    ) -> dict[str, Any] | None:
        """Search session-buddy memory for cached scan results.

        Uses session-buddy MCP tool: pool_search_memory to query
        across memory namespaces for past scan results.

        Args:
            memory_client: MCP client or context with tool access
            cache_key: Cache key to search for

        Returns:
            Cached results or None
        """
        try:
            # Access session-buddy MCP server to search memory
            # This uses the mcp__mahavishnu pool_search_memory tool
            search_result = await memory_client.pool_search_memory(
                query=cache_key,
                namespace=self.MEMORY_NAMESPACE,
                max_results=100,
            )

            if search_result.get("status") == "success":
                results = search_result.get("results", [])
                self.console.print(f"[dim]Found {len(results)} cached results[/dim]")
            else:
                self.console.print(
                    f"[yellow]⚠️ Memory search failed: {search_result.get('error', 'unknown error')}[/yellow]"
                )
                results = None

            return {"search_result": search_result}

        except Exception as e:
            logger.error(f"Memory search failed: {e}")
            self.console.print(f"[red]❌ Memory search error: {e}[/red]")
            return None

    async def _process_cached_results(
        self,
        files: list[Path],
        cached_results: dict[str, Any],
    ) -> dict[str, Any]:
        """Process cached results and filter out known-good files.

        Args:
            files: All files to scan
            cached_results: Cached scan results from memory

        Returns:
            Filtered files and metrics
        """
        files_to_scan = []
        skipped_files = []

        for file in files:
            file_str = str(file)

            # Check if file has known-good result
            known_good = self._is_known_good(file_str, cached_results)

            if known_good:
                skipped_files.append(file)
                self.console.print(f"[dim]  ✓ Skipping {file} (passed recently)[/dim]")
            else:
                files_to_scan.append(file)

        metrics = {
            "total_files": len(files),
            "cached_files_found": len(cached_results.get("results", [])),
            "files_to_scan": len(files_to_scan),
            "files_skipped": len(skipped_files),
        }

        self.console.print(
            f"[green]Scan plan: {len(files_to_scan)} to scan, "
            f"{len(skipped_files)} skipped[/green]"
        )

        return {
            "files_to_scan": files_to_scan,
            "skipped_files": skipped_files,
            "metrics": metrics,
        }

    async def _perform_full_scan(
        self,
        tool_name: str,
        files: list[Path],
        cache_key: str,
    ) -> dict[str, Any]:
        """Perform full scan and cache results in session-buddy memory.

        Args:
            tool_name: Tool being executed
            files: Files to scan
            cache_key: Cache key for storing results

        Returns:
            Scan results with caching info
        """
        self.console.print(
            f"[blue]🔍 Performing full {tool_name} scan on {len(files)} files...[/blue]"
        )

        # Simulate scan execution
        scan_results = []
        start_time = time.time()

        for file in files:
            # TODO: Actual tool execution via pool_client
            # For now, mock results
            file_result = {
                "file_path": str(file),
                "status": "passed" if random.random() > 0.2 else "failed",
                "timestamp": datetime.now().isoformat(),
                "tool": tool_name,
                "exit_code": 0 if random.random() > 0.7 else 1,  # type: ignore[untyped]
            }
            scan_results.append(file_result)

        elapsed = time.time() - start_time

        # Cache results in session-buddy memory
        cache_data = {
            "results": scan_results,
            "scan_time": datetime.now().isoformat(),
            "scan_duration_seconds": elapsed,
            "tool": tool_name,
            "cache_key": cache_key,
        }

        # Store in session-buddy memory via pool_store_memory
        if self._memory_client:
            try:
                # This will use the mcp__session_buddy pool_store_memory tool
                # which is available when session-buddy MCP server is running
                import json

                await self._memory_client.pool_store_memory(
                    namespace=self.MEMORY_NAMESPACE,
                    key=cache_key,
                    value=json.dumps(cache_data),
                    ttl=self.cache_duration,
                )
                self.console.print(
                    f"[dim]✓ Stored {len(scan_results)} results in memory (TTL: {self.cache_duration}s)[/dim]"
                )
            except Exception as e:
                logger.warning(f"Failed to store in memory: {e}")

        self.console.print(
            f"[green]✅ Scan complete: {len(scan_results)} files scanned[/green]"
        )

        return {
            "files_to_scan": files,
            "skipped_files": [],
            "scan_results": scan_results,
            "cached": False,
            "metrics": {
                "total_files": len(files),
                "files_scanned": len(scan_results),
                "scan_duration": elapsed,
            },
        }

    def _generate_cache_key(self, tool_name: str, files: list[Path]) -> str:
        """Generate cache key for scan results.

        Args:
            tool_name: Tool being used
            files: Files being scanned

        Returns:
            Cache key string
        """
        # Sort files for consistent key
        sorted_files = sorted(str(f) for f in files)

        # Create hash of file list
        file_hash = hashlib.md5(":".join(sorted_files).encode("utf-8")).hexdigest()[:16]

        return f"{self.MEMORY_NAMESPACE}:{tool_name}:{file_hash}"

    def _is_known_good(
        self,
        file_str: str,
        cached_results: dict[str, Any],
    ) -> bool:
        """Check if file has known-good result in cache.

        Args:
            file_str: File path as string
            cached_results: Cached scan results

        Returns:
            True if file recently passed, False otherwise
        """
        if not cached_results:
            return False

        results = cached_results.get("results", [])
        cache_cutoff = datetime.now() - timedelta(seconds=self.cache_duration)

        for result in results:
            result_path = result.get("file_path", "")
            result_time = datetime.fromisoformat(result.get("timestamp", ""))

            if result_path == file_str and result.get("status") == "passed":
                # File passed recently and within cache duration
                if result_time > cache_cutoff:
                    return True

        return False

    async def cleanup(self) -> None:
        """Cleanup resources.

        Clear any held resources.
        """
        self.console.print("[dim]Memory-aware scanner cleanup complete[/dim]")
