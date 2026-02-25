from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from rich.console import Console

from crackerjack.config import CrackerjackSettings
from crackerjack.models.protocols import HookResult
from crackerjack.services.pool_client import CrackerjackPoolClient

logger = logging.getLogger(__name__)


try:
    from crackerjack.services.memory_aware_scanner import MemoryAwareScanner

    MEMORY_AWARE_AVAILABLE = True
except ImportError:
    MEMORY_AWARE_AVAILABLE = False
    logger.debug("MemoryAwareScanner not available, memory integration disabled")


class PoolBasedHooks:
    def __init__(
        self,
        settings: CrackerjackSettings,
        console: Console | None = None,
    ) -> None:
        self.settings = settings
        self.console = console or Console()
        self.pool_client = CrackerjackPoolClient(
            mcp_server_url=getattr(settings, "pool_scanning", {}).get(
                "mcp_server_url", "http://localhost: 8680"
            ),
        )

        self.memory_scanner = None
        if MEMORY_AWARE_AVAILABLE:
            pool_settings = getattr(settings, "pool_scanning", {})
            memory_settings = pool_settings.get("memory", {})

            if memory_settings.get("enabled", True):
                self.memory_scanner = MemoryAwareScanner(
                    console=self.console,
                    cache_duration=memory_settings.get("cache_duration", 86400),
                )
                self.console.print("[cyan]✅ Memory-aware scanner initialized[/cyan]")

    async def run_complexipy_with_pool(
        self,
        options: Any,
    ) -> HookResult:
        if not getattr(self.settings, "pool_scanning", {}).get("enabled", False):
            return HookResult(
                success=True,
                stdout="Pool scanning disabled, skipping complexipy",
                stderr="",
                exit_code=0,
            )

        pkg_path = Path(getattr(options, "pkg_path", "."))
        files = self._get_files_to_scan(pkg_path, "complexipy")

        if not files:
            return HookResult(
                success=True,
                stdout="No changes to scan",
                stderr="",
                exit_code=0,
            )

        try:
            if not self.pool_client.pool_id:
                pool_config = getattr(self.settings, "pool_scanning", {}).get(
                    "pool", {}
                )

                await self.pool_client.spawn_scanner_pool(
                    min_workers=pool_config.get("min_workers", 2),
                    max_workers=pool_config.get("max_workers", 8),
                    worker_type=pool_config.get("worker_type", "terminal-qwen"),
                )

            result = await self.pool_client.execute_tool_scan(
                "complexipy",
                files,
            )

            success = result.get("status") == "completed"
            output = result.get("output", "")
            error = result.get("error", "")

            return HookResult(
                success=success,
                stdout=output,
                stderr=error,
                exit_code=0 if success else 1,
            )

        except Exception as e:
            logger.error(f"Complexipy pool execution failed: {e}")
            return HookResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=1,
            )

    async def run_skylos_with_pool(
        self,
        options: Any,
    ) -> HookResult:
        if not getattr(self.settings, "pool_scanning", {}).get("enabled", False):
            return HookResult(
                success=True,
                stdout="Pool scanning disabled, skipping skylos",
                stderr="",
                exit_code=0,
            )

        pkg_path = Path(getattr(options, "pkg_path", "."))
        files = self._get_files_to_scan(pkg_path, "skylos")

        if not files:
            return HookResult(
                success=True,
                stdout="No changes to scan",
                stderr="",
                exit_code=0,
            )

        try:
            if not self.pool_client.pool_id:
                pool_config = getattr(self.settings, "pool_scanning", {}).get(
                    "pool", {}
                )

                await self.pool_client.spawn_scanner_pool(
                    min_workers=pool_config.get("min_workers", 2),
                    max_workers=pool_config.get("max_workers", 8),
                    worker_type=pool_config.get("worker_type", "terminal-qwen"),
                )

            result = await self.pool_client.execute_tool_scan(
                "skylos",
                files,
            )

            success = result.get("status") == "completed"
            output = result.get("output", "")
            error = result.get("error", "")

            return HookResult(
                success=success,
                stdout=output,
                stderr=error,
                exit_code=0 if success else 1,
            )

        except Exception as e:
            logger.error(f"Skylos pool execution failed: {e}")
            return HookResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=1,
            )

    async def _scan_with_memory(
        self,
        tool_name: str,
        files: list[Path],
        memory_client: Any = None,
    ) -> dict[str, Any]:
        if self.memory_scanner and memory_client:
            return await self.memory_scanner.scan_with_memory(
                tool_name=tool_name,
                files=files,
                memory_client=memory_client,
            )

        return {
                "files_to_scan": files,
                "skipped_files": [],
                "cached": False,
                "metrics": {
                    "total_files": len(files),
                },
            }

    async def run_refurb_with_pool(
        self,
        options: Any,
    ) -> HookResult:

        if not getattr(self.settings, "pool_scanning", {}).get("enabled", False):
            return HookResult(
                success=True,
                stdout="Pool scanning disabled, skipping refurb",
                stderr="",
                exit_code=0,
            )

        pkg_path = Path(getattr(options, "pkg_path", "."))
        files = self._get_files_to_scan(pkg_path, "refurb")

        if not files:
            return HookResult(
                success=True,
                stdout="No changes to scan",
                stderr="",
                exit_code=0,
            )

        try:
            if not self.pool_client.pool_id:
                pool_config = getattr(self.settings, "pool_scanning", {}).get(
                    "pool", {}
                )

                await self.pool_client.spawn_scanner_pool(
                    min_workers=pool_config.get("min_workers", 2),
                    max_workers=pool_config.get("max_workers", 8),
                    worker_type=pool_config.get("worker_type", "terminal-qwen"),
                    pool_name=pool_config.get("name", "crackerjack-quality-scanners"),
                )

            pool_settings = getattr(self.settings, "pool_scanning", {})
            pool_settings.get("memory", {}).get("enabled", False)

            # TODO: This would come from session-buddy integration
            memory_client = None

            scan_result = await self._scan_with_memory(
                "refurb",
                files,
                memory_client,
            )

            files_to_scan = scan_result.get("files_to_scan", files)
            skipped_files = scan_result.get("skipped_files", [])

            if skipped_files:
                self.console.print(
                    f"[dim]✓ Skipped {len(skipped_files)} files via memory cache[/dim]"
                )

            if not files_to_scan:
                return HookResult(
                    success=True,
                    stdout=f"All files skipped via cache (total: {len(files)})",
                    stderr="",
                    exit_code=0,
                )

            result = await self.pool_client.execute_tool_scan(
                "refurb",
                files_to_scan,
            )

            success = result.get("status") == "completed"
            output = result.get("output", "")
            error = result.get("error", "")

            return HookResult(
                success=success,
                stdout=output,
                stderr=error,
                exit_code=0 if success else 1,
            )

        except Exception as e:
            logger.error(f"Refurb pool execution failed: {e}")
            return HookResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=1,
            )

    async def run_ruff_with_pool(
        self,
        options: Any,
    ) -> HookResult:
        if not getattr(self.settings, "pool_scanning", {}).get("enabled", False):
            return HookResult(
                success=True,
                stdout="Pool scanning disabled, skipping ruff",
                stderr="",
                exit_code=0,
            )

        pooled_tools = getattr(self.settings, "pool_scanning", {}).get(
            "pooled_tools", []
        )

        if "ruff" not in pooled_tools:
            from crackerjack.hooks.fast import run_ruff

            return await run_ruff(options)

        pkg_path = Path(getattr(options, "pkg_path", "."))
        files = self._get_files_to_scan(pkg_path, "ruff")

        if not files:
            return HookResult(
                success=True,
                stdout="No changes to scan",
                stderr="",
                exit_code=0,
            )

        try:
            if not self.pool_client.pool_id:
                pool_config = getattr(self.settings, "pool_scanning", {}).get(
                    "pool", {}
                )

                await self.pool_client.spawn_scanner_pool(
                    min_workers=pool_config.get("min_workers", 2),
                    max_workers=pool_config.get("max_workers", 8),
                    worker_type=pool_config.get("worker_type", "terminal-qwen"),
                )

            result = await self.pool_client.execute_tool_scan(
                "ruff",
                files,
            )

            success = result.get("status") == "completed"
            output = result.get("output", "")
            error = result.get("error", "")

            return HookResult(
                success=success,
                stdout=output,
                stderr=error,
                exit_code=0 if success else 1,
            )

        except Exception as e:
            logger.error(f"Ruff pool execution failed: {e}")
            return HookResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=1,
            )

    def _get_files_to_scan(self, pkg_path: Path, tool_name: str) -> list[Path]:

        python_files = list(pkg_path.rglob("*.py"))

        logger.debug(f"Tool {tool_name}: Found {len(python_files)} files to scan")

        return python_files

    async def cleanup(self) -> None:
        await self.pool_client.cleanup()
        self.console.print("[dim]Pool hooks cleanup complete[/dim]")
