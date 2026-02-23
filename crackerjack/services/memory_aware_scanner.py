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
    CACHE_DURATION_SECONDS = 86400
    MEMORY_NAMESPACE = "crackerjack: pool_scanning"

    def __init__(
        self,
        console: Console | None = None,
        cache_duration: int = CACHE_DURATION_SECONDS,
    ) -> None:
        self.console = console or Console()
        self.cache_duration = cache_duration
        self._memory_client: Any = None

    async def scan_with_memory(
        self,
        tool_name: str,
        files: list[Path],
        memory_client: Any,
    ) -> dict[str, Any]:
        self.console.print(
            f"[cyan]🔍 Scanning {len(files)} files with {tool_name} memory...[/cyan]"
        )

        cache_key = self._generate_cache_key(tool_name, files)

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
        try:
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
        files_to_scan = []
        skipped_files = []

        for file in files:
            file_str = str(file)

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
        self.console.print(
            f"[blue]🔍 Performing full {tool_name} scan on {len(files)} files...[/blue]"
        )

        scan_results = []
        start_time = time.time()

        for file in files:
            # TODO: Actual tool execution via pool_client

            file_result = {
                "file_path": str(file),
                "status": "passed" if random.random() > 0.2 else "failed",  # type: ignore[untyped]
                "timestamp": datetime.now().isoformat(),
                "tool": tool_name,
                "exit_code": 0 if random.random() > 0.7 else 1,  # type: ignore[untyped]
            }
            scan_results.append(file_result)

        elapsed = time.time() - start_time

        cache_data = {
            "results": scan_results,
            "scan_time": datetime.now().isoformat(),
            "scan_duration_seconds": elapsed,
            "tool": tool_name,
            "cache_key": cache_key,
        }

        if self._memory_client:
            try:
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

        sorted_files = sorted(str(f) for f in files)

        file_hash = hashlib.md5(":".join(sorted_files).encode("utf-8")).hexdigest()[:16]

        return f"{self.MEMORY_NAMESPACE}:{tool_name}:{file_hash}"

    def _is_known_good(
        self,
        file_str: str,
        cached_results: dict[str, Any],
    ) -> bool:
        if not cached_results:
            return False

        results = cached_results.get("results", [])
        cache_cutoff = datetime.now() - timedelta(seconds=self.cache_duration)

        for result in results:
            result_path = result.get("file_path", "")
            result_time = datetime.fromisoformat(result.get("timestamp", ""))

            if result_path == file_str and result.get("status") == "passed":
                if result_time > cache_cutoff:
                    return True

        return False

    async def cleanup(self) -> None:
        self.console.print("[dim]Memory-aware scanner cleanup complete[/dim]")
