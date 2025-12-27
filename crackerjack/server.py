"""Crackerjack MCP server with QA tooling integration.

Phase 3 Implementation: Server class for Oneiric runtime integration.
"""

import asyncio
import logging
import os
from datetime import UTC, datetime
from pathlib import Path

from crackerjack.config.settings import CrackerjackSettings

logger = logging.getLogger(__name__)


class CrackerjackServer:
    """Crackerjack MCP server with integrated QA adapters.

    Manages QA adapter lifecycle and provides health snapshots for monitoring.
    Designed to integrate with Oneiric runtime orchestration.

    Phase 3 Implementation Notes:
    - Uses existing ACB-based CrackerjackSettings (settings migration deferred to Phase 4)
    - Adapter initialization is stubbed (full implementation in Phase 4)
    - Health snapshot provides Oneiric-compatible status data
    """

    def __init__(self, settings: CrackerjackSettings):
        """Initialize server with settings.

        Args:
            settings: CrackerjackSettings instance (ACB-based for Phase 3)
        """
        self.settings = settings
        self.running = False
        self.adapters: list = []  # QA adapters (will be populated in Phase 4)
        self.start_time: datetime | None = None
        self._server_task: asyncio.Task | None = None

    async def start(self):
        """Start server with QA adapter initialization.

        This method initializes QA adapters based on settings and runs the server
        main loop. The loop keeps the process alive until stopped.

        Raises:
            asyncio.CancelledError: If the server task is cancelled
        """
        logger.info("Starting Crackerjack MCP server...")
        self.running = True
        self.start_time = datetime.now(UTC)

        # Initialize QA adapters based on settings
        await self._init_qa_adapters()

        logger.info(f"Server started with {len(self.adapters)} QA adapters")

        # Server main loop (keeps process alive)
        try:
            while self.running:
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            logger.info("Server main loop cancelled")
            raise

    async def _init_qa_adapters(self):
        """Initialize enabled QA adapters.

        TODO(Phase 4): Actual adapter initialization will be implemented in Phase 4
        when QA adapters are ported to Oneiric pattern.

        For Phase 3, this method logs which adapters would be enabled based on
        the settings flags, but does not actually instantiate adapter objects.
        """
        enabled_adapters = []

        # Check all tool enablement flags from settings
        if getattr(self.settings, "ruff_enabled", True):
            enabled_adapters.append("Ruff")

        if getattr(self.settings, "bandit_enabled", True):
            enabled_adapters.append("Bandit")

        if getattr(self.settings, "semgrep_enabled", False):
            enabled_adapters.append("Semgrep")

        if getattr(self.settings, "mypy_enabled", True):
            enabled_adapters.append("Mypy")

        # Rust-powered tools
        zuban_enabled = getattr(
            getattr(self.settings, "zuban_lsp", None), "enabled", True
        )
        if zuban_enabled:
            enabled_adapters.append("Zuban")

        # Check for other adapters that may exist in settings
        if hasattr(self.settings, "testing"):
            enabled_adapters.append("Pytest")

        logger.info(f"QA adapters enabled (Phase 3 - not yet instantiated): {', '.join(enabled_adapters)}")
        logger.info("TODO(Phase 4): Implement actual adapter instantiation")

        # Phase 4 will populate self.adapters with actual adapter instances

    def stop(self):
        """Stop server gracefully.

        Stops the server main loop and cleans up all initialized adapters.
        """
        logger.info("Stopping Crackerjack MCP server...")
        self.running = False

        # Cleanup adapters
        for adapter in self.adapters:
            if hasattr(adapter, "cleanup"):
                try:
                    adapter.cleanup()
                except Exception as e:
                    logger.warning(f"Error cleaning up adapter {adapter}: {e}")

        logger.info("Server stopped")

    def get_health_snapshot(self) -> dict:
        """Generate health snapshot for monitoring.

        Returns health data compatible with Oneiric runtime health format.
        This snapshot can be used by monitoring systems and the --health --probe
        command for liveness/readiness checks.

        Returns:
            dict: Health snapshot with server status, uptime, and adapter health
        """
        uptime = (
            (datetime.now(UTC) - self.start_time).total_seconds()
            if self.start_time
            else 0.0
        )

        return {
            "server_status": "running" if self.running else "stopped",
            "uptime_seconds": uptime,
            "process_id": os.getpid(),
            "qa_adapters": {
                "total": len(self.adapters),
                "healthy": sum(
                    1 for a in self.adapters if getattr(a, "healthy", True)
                ),
                "enabled_flags": self._get_enabled_adapter_flags(),
            },
            "settings": {
                "qa_mode": getattr(self.settings, "qa_mode", False),
                "ai_agent": getattr(getattr(self.settings, "ai", None), "ai_agent", False),
                "auto_fix": getattr(getattr(self.settings, "ai", None), "autofix", False),
                "test_workers": getattr(
                    getattr(self.settings, "testing", None), "test_workers", 0
                ),
                "verbose": getattr(
                    getattr(self.settings, "execution", None), "verbose", False
                ),
            },
        }

    def _get_enabled_adapter_flags(self) -> dict[str, bool]:
        """Get dict of adapter enablement flags from settings.

        Returns:
            dict: Mapping of adapter names to their enabled status
        """
        return {
            "ruff": getattr(self.settings, "ruff_enabled", True),
            "bandit": getattr(self.settings, "bandit_enabled", True),
            "semgrep": getattr(self.settings, "semgrep_enabled", False),
            "mypy": getattr(self.settings, "mypy_enabled", True),
            "zuban": getattr(
                getattr(self.settings, "zuban_lsp", None), "enabled", True
            ),
            "pytest": hasattr(self.settings, "testing"),
        }

    async def run_in_background(self):
        """Run server in background task.

        Returns:
            asyncio.Task: The background task running the server
        """
        self._server_task = asyncio.create_task(self.start())
        return self._server_task

    async def shutdown(self):
        """Async shutdown for graceful cleanup.

        Stops the server and cancels the background task if running.
        """
        self.stop()
        if self._server_task and not self._server_task.done():
            self._server_task.cancel()
            try:
                await self._server_task
            except asyncio.CancelledError:
                pass
