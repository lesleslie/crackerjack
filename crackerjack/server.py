import asyncio
import contextlib
import logging
import os
from datetime import UTC, datetime

from crackerjack.config.settings import CrackerjackSettings
from crackerjack.runtime import RuntimeHealthSnapshot

logger = logging.getLogger(__name__)


class CrackerjackServer:
    def __init__(self, settings: CrackerjackSettings) -> None:
        self.settings = settings
        self.running = False
        self.adapters: list = []
        self.start_time: datetime | None = None
        self._server_task: asyncio.Task | None = None

    async def start(self) -> None:
        logger.info("Starting Crackerjack MCP server...")
        self.running = True
        self.start_time = datetime.now(UTC)

        await self._init_qa_adapters()

        logger.info(f"Server started with {len(self.adapters)} QA adapters")

        try:
            while self.running:
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            logger.info("Server main loop cancelled")
            raise

    async def _init_qa_adapters(self) -> None:
        self.adapters = []
        enabled_names: list[str] = []

        await self._initialize_adapters(enabled_names)

        logger.info(
            f"Initialized {len(self.adapters)} QA adapters: {', '.join(enabled_names)}",
        )

    async def _initialize_adapters(self, enabled_names: list[str]) -> None:
        await self._init_adapter_if_enabled("ruff_enabled", True, "Ruff", enabled_names)

        await self._init_adapter_if_enabled(
            "bandit_enabled",
            True,
            "Bandit",
            enabled_names,
        )

        await self._init_adapter_if_enabled(
            "semgrep_enabled",
            False,
            "Semgrep",
            enabled_names,
        )

        zuban_enabled = getattr(
            getattr(self.settings, "zuban_lsp", None),
            "enabled",
            True,
        )
        if zuban_enabled:
            await self._init_zuban_adapter(enabled_names)

        await self._init_adapter_if_enabled(
            "refurb_enabled",
            True,
            "Refurb",
            enabled_names,
        )

        await self._init_adapter_if_enabled(
            "skylos_enabled",
            True,
            "Skylos",
            enabled_names,
        )

        await self._init_claude_adapter(enabled_names)

    async def _init_adapter_if_enabled(
        self,
        setting_name: str,
        default_value: bool,
        adapter_name: str,
        enabled_names: list[str],
    ) -> None:
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

    async def _init_zuban_adapter(self, enabled_names: list[str]) -> None:
        try:
            from crackerjack.adapters.type.zuban import ZubanAdapter

            zuban = ZubanAdapter()
            await zuban.init()
            self.adapters.append(zuban)
            enabled_names.append("Zuban")
            logger.debug("Zuban adapter initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize Zuban adapter: {e}")

    async def _init_claude_adapter(self, enabled_names: list[str]) -> None:
        ai_settings = getattr(self.settings, "ai", None)
        if ai_settings and getattr(ai_settings, "ai_agent", False):
            try:
                from crackerjack.adapters.ai.claude import ClaudeCodeFixer

                claude = ClaudeCodeFixer()
                await claude.init()
                self.adapters.append(claude)
                enabled_names.append("Claude AI")
                logger.debug("Claude AI adapter initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Claude AI adapter: {e}")

    def _get_adapter_class(self, adapter_name: str):
        if adapter_name == "Ruff":
            from crackerjack.adapters.format.ruff import RuffAdapter

            return RuffAdapter
        if adapter_name == "Bandit":
            from crackerjack.adapters.sast.bandit import BanditAdapter

            return BanditAdapter
        if adapter_name == "Semgrep":
            from crackerjack.adapters.sast.semgrep import SemgrepAdapter

            return SemgrepAdapter
        if adapter_name == "Refurb":
            from crackerjack.adapters.refactor.refurb import RefurbAdapter

            return RefurbAdapter
        if adapter_name == "Skylos":
            from crackerjack.adapters.refactor.skylos import SkylosAdapter

            return SkylosAdapter
        return None

    def stop(self) -> None:
        logger.info("Stopping Crackerjack MCP server...")
        self.running = False

        for adapter in self.adapters:
            if hasattr(adapter, "cleanup"):
                try:
                    adapter.cleanup()
                except Exception as e:
                    logger.warning(f"Error cleaning up adapter {adapter}: {e}")

        logger.info("Server stopped")

    def get_health_snapshot(self) -> RuntimeHealthSnapshot:
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
                        getattr(self.settings, "ai", None),
                        "ai_agent",
                        False,
                    ),
                    "auto_fix": getattr(
                        getattr(self.settings, "ai", None),
                        "autofix",
                        False,
                    ),
                    "test_workers": getattr(
                        getattr(self.settings, "testing", None),
                        "test_workers",
                        0,
                    ),
                    "verbose": getattr(
                        getattr(self.settings, "execution", None),
                        "verbose",
                        False,
                    ),
                },
            },
        )

    def _get_enabled_adapter_flags(self) -> dict[str, bool]:
        return {
            "ruff": getattr(self.settings, "ruff_enabled", True),
            "bandit": getattr(self.settings, "bandit_enabled", True),
            "semgrep": getattr(self.settings, "semgrep_enabled", False),
            "mypy": getattr(self.settings, "mypy_enabled", True),
            "zuban": getattr(
                getattr(self.settings, "zuban_lsp", None),
                "enabled",
                True,
            ),
            "pytest": hasattr(self.settings, "testing"),
        }

    async def run_in_background(self):
        self._server_task = asyncio.create_task(self.start())
        return self._server_task

    async def shutdown(self) -> None:
        self.stop()
        if self._server_task and not self._server_task.done():
            self._server_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._server_task
