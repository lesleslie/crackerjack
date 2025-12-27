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

        Phase 4 Implementation: Instantiates QA adapters based on settings flags.
        All adapters are ACB-free and use standard Python patterns with async init().
        """
        self.adapters = []

        # Import adapter classes (all adapters are now ACB-free)
        from crackerjack.adapters.format.ruff import RuffAdapter
        from crackerjack.adapters.sast.bandit import BanditAdapter
        from crackerjack.adapters.sast.semgrep import SemgrepAdapter
        from crackerjack.adapters.type.zuban import ZubanAdapter
        from crackerjack.adapters.refactor.refurb import RefurbAdapter
        from crackerjack.adapters.refactor.skylos import SkylosAdapter
        from crackerjack.adapters.ai.claude import ClaudeCodeFixer

        # Track enabled adapters for logging
        enabled_names = []

        # Format/Lint: Ruff (enabled by default)
        if getattr(self.settings, "ruff_enabled", True):
            try:
                ruff = RuffAdapter()
                await ruff.init()
                self.adapters.append(ruff)
                enabled_names.append("Ruff")
                logger.debug("Ruff adapter initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Ruff adapter: {e}")

        # Security: Bandit (enabled by default)
        if getattr(self.settings, "bandit_enabled", True):
            try:
                bandit = BanditAdapter()
                await bandit.init()
                self.adapters.append(bandit)
                enabled_names.append("Bandit")
                logger.debug("Bandit adapter initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Bandit adapter: {e}")

        # SAST: Semgrep (disabled by default - requires API key)
        if getattr(self.settings, "semgrep_enabled", False):
            try:
                semgrep = SemgrepAdapter()
                await semgrep.init()
                self.adapters.append(semgrep)
                enabled_names.append("Semgrep")
                logger.debug("Semgrep adapter initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Semgrep adapter: {e}")

        # Type Check: Zuban (Rust-powered, enabled by default)
        zuban_enabled = getattr(
            getattr(self.settings, "zuban_lsp", None), "enabled", True
        )
        if zuban_enabled:
            try:
                zuban = ZubanAdapter()
                await zuban.init()
                self.adapters.append(zuban)
                enabled_names.append("Zuban")
                logger.debug("Zuban adapter initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Zuban adapter: {e}")

        # Refactor: Refurb (enabled by default)
        if getattr(self.settings, "refurb_enabled", True):
            try:
                refurb = RefurbAdapter()
                await refurb.init()
                self.adapters.append(refurb)
                enabled_names.append("Refurb")
                logger.debug("Refurb adapter initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Refurb adapter: {e}")

        # Refactor: Skylos (dead code detection, enabled by default)
        if getattr(self.settings, "skylos_enabled", True):
            try:
                skylos = SkylosAdapter()
                await skylos.init()
                self.adapters.append(skylos)
                enabled_names.append("Skylos")
                logger.debug("Skylos adapter initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Skylos adapter: {e}")

        # AI: Claude (requires API key, disabled by default)
        ai_settings = getattr(self.settings, "ai", None)
        if ai_settings and getattr(ai_settings, "ai_agent", False):
            try:
                # Claude adapter requires settings passed to constructor
                from crackerjack.adapters.ai.claude import ClaudeCodeFixerSettings
                from pydantic import SecretStr

                # Extract API key from settings
                api_key = getattr(ai_settings, "anthropic_api_key", None)
                if api_key:
                    claude_settings = ClaudeCodeFixerSettings(
                        anthropic_api_key=SecretStr(api_key)
                    )
                    claude = ClaudeCodeFixer(settings=claude_settings)
                    await claude.init()
                    self.adapters.append(claude)
                    enabled_names.append("Claude AI")
                    logger.debug("Claude AI adapter initialized")
                else:
                    logger.warning("Claude AI enabled but no API key configured")
            except Exception as e:
                logger.warning(f"Failed to initialize Claude AI adapter: {e}")

        logger.info(f"Initialized {len(self.adapters)} QA adapters: {', '.join(enabled_names)}")

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
