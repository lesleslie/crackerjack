"""Crackerjack MCP server with QA tooling integration.

Phase 3 Implementation: Server class for Oneiric runtime integration.
"""

import asyncio
import logging
import os
from datetime import UTC, datetime

from crackerjack.config.settings import CrackerjackSettings
from crackerjack.runtime import RuntimeHealthSnapshot

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
        enabled_names = []

        # Initialize adapters based on settings
        await self._initialize_adapters(enabled_names)

        logger.info(
            f"Initialized {len(self.adapters)} QA adapters: {', '.join(enabled_names)}"
        )

    async def _initialize_adapters(self, enabled_names: list[str]):
        """Initialize adapters based on settings."""
        # Format/Lint: Ruff (enabled by default)
        await self._init_adapter_if_enabled("ruff_enabled", True, "Ruff", enabled_names)

        # Security: Bandit (enabled by default)
        await self._init_adapter_if_enabled(
            "bandit_enabled", True, "Bandit", enabled_names
        )

        # SAST: Semgrep (disabled by default - requires API key)
        await self._init_adapter_if_enabled(
            "semgrep_enabled", False, "Semgrep", enabled_names
        )

        # Type Check: Zuban (Rust-powered, enabled by default)
        zuban_enabled = getattr(
            getattr(self.settings, "zuban_lsp", None), "enabled", True
        )
        if zuban_enabled:
            await self._init_zuban_adapter(enabled_names)

        # Refactor: Refurb (enabled by default)
        await self._init_adapter_if_enabled(
            "refurb_enabled", True, "Refurb", enabled_names
        )

        # Refactor: Skylos (dead code detection, enabled by default)
        await self._init_adapter_if_enabled(
            "skylos_enabled", True, "Skylos", enabled_names
        )

        # AI: Claude (requires API key, disabled by default)
        await self._init_claude_adapter(enabled_names)

    async def _init_adapter_if_enabled(
        self,
        setting_name: str,
        default_value: bool,
        adapter_name: str,
        enabled_names: list[str],
    ):
        """Initialize an adapter if it's enabled in settings."""
        if getattr(self.settings, setting_name, default_value):
            try:
                adapter_class = self._get_adapter_class(adapter_name)
                if adapter_class:
                    adapter = adapter_class()
                    await adapter.init()
                    self.adapters.append(adapter)
                    enabled_names.append(adapter_name)
                    logger.debug(f"{adapter_name} adapter initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize {adapter_name} adapter: {e}")

    async def _init_zuban_adapter(self, enabled_names: list[str]):
        """Initialize the Zuban adapter."""
        try:
            from crackerjack.adapters.type.zuban import ZubanAdapter

            zuban = ZubanAdapter()
            await zuban.init()
            self.adapters.append(zuban)
            enabled_names.append("Zuban")
            logger.debug("Zuban adapter initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Zuban adapter: {e}")

    async def _init_claude_adapter(self, enabled_names: list[str]):
        """Initialize the Claude AI adapter."""
        ai_settings = getattr(self.settings, "ai", None)
        if ai_settings and getattr(ai_settings, "ai_agent", False):
            try:
                # Claude adapter requires settings passed to constructor
                from pydantic import SecretStr

                from crackerjack.adapters.ai.claude import (
                    ClaudeCodeFixer,
                    ClaudeCodeFixerSettings,
                )

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

    def _get_adapter_class(self, adapter_name: str):
        """Get the adapter class by name."""
        if adapter_name == "Ruff":
            from crackerjack.adapters.format.ruff import RuffAdapter

            return RuffAdapter
        elif adapter_name == "Bandit":
            from crackerjack.adapters.sast.bandit import BanditAdapter

            return BanditAdapter
        elif adapter_name == "Semgrep":
            from crackerjack.adapters.sast.semgrep import SemgrepAdapter

            return SemgrepAdapter
        elif adapter_name == "Refurb":
            from crackerjack.adapters.refactor.refurb import RefurbAdapter

            return RefurbAdapter
        elif adapter_name == "Skylos":
            from crackerjack.adapters.refactor.skylos import SkylosAdapter

            return SkylosAdapter
        return None

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

    def get_health_snapshot(self) -> RuntimeHealthSnapshot:
        """Generate health snapshot for monitoring.

        Returns health data compatible with Oneiric runtime health format.
        This snapshot can be used by monitoring systems and the --health --probe
        command for liveness/readiness checks.

        Returns:
            RuntimeHealthSnapshot: Oneiric-compatible health snapshot
        """
        uptime = (
            (datetime.now(UTC) - self.start_time).total_seconds()
            if self.start_time
            else 0.0
        )

        return RuntimeHealthSnapshot(
            orchestrator_pid=os.getpid(),
            watchers_running=self.running,
            lifecycle_state={
                "server_status": "running" if self.running else "stopped",
                "uptime_seconds": uptime,
                "qa_adapters": {
                    "total": len(self.adapters),
                    "healthy": sum(
                        1 for a in self.adapters if getattr(a, "healthy", True)
                    ),
                    "enabled_flags": self._get_enabled_adapter_flags(),
                },
                "settings": {
                    "qa_mode": getattr(self.settings, "qa_mode", False),
                    "ai_agent": getattr(
                        getattr(self.settings, "ai", None), "ai_agent", False
                    ),
                    "auto_fix": getattr(
                        getattr(self.settings, "ai", None), "autofix", False
                    ),
                    "test_workers": getattr(
                        getattr(self.settings, "testing", None), "test_workers", 0
                    ),
                    "verbose": getattr(
                        getattr(self.settings, "execution", None), "verbose", False
                    ),
                },
            },
        )

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
