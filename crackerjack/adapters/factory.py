import logging
import os
import typing as t
from pathlib import Path

from crackerjack.models.protocols import AdapterFactoryProtocol, AdapterProtocol

logger = logging.getLogger(__name__)

if t.TYPE_CHECKING:
    pass


class DefaultAdapterFactory(AdapterFactoryProtocol):
    def __init__(
        self,
        settings: t.Any | None = None,
        pkg_path: Path | None = None,
    ) -> None:
        self.settings = settings
        self.pkg_path = pkg_path or Path.cwd()

    def _is_ai_agent_enabled(self) -> bool:
        """Check if AI agent mode is enabled (--ai-fix flag)."""
        return os.environ.get("AI_AGENT") == "1"

    def _enable_tool_native_fixes(
        self,
        adapter_name: str,
        settings: t.Any | None,
    ) -> t.Any:
        """Enable tool-native --fix options when AI agent mode is active.

        This implements the architectural improvement where tools run their
        own fix options FIRST, then report only issues that couldn't be fixed.
        """
        if not self._is_ai_agent_enabled():
            return settings

        # Enable fix mode for adapters that support it
        if adapter_name == "Ruff" and settings is not None:
            # Enable both check and format fix modes
            if hasattr(settings, "fix_enabled"):
                settings.fix_enabled = True
                logger.info("Tool-native fixes enabled for Ruff (fix_enabled=True)")

        return settings

    def create_adapter(
        self,
        adapter_name: str,
        settings: t.Any | None = None,
    ) -> AdapterProtocol:
        # Enable tool-native fixes when AI agent mode is active
        settings = self._enable_tool_native_fixes(adapter_name, settings)

        if adapter_name == "Ruff":
            from crackerjack.adapters.format.ruff import RuffAdapter

            return RuffAdapter(settings)
        if adapter_name == "Bandit":
            from crackerjack.adapters.sast.bandit import BanditAdapter

            return BanditAdapter(settings)
        if adapter_name == "Semgrep":
            from crackerjack.adapters.sast.semgrep import SemgrepAdapter

            return SemgrepAdapter(settings)
        if adapter_name == "Refurb":
            from crackerjack.adapters.refactor.refurb import RefurbAdapter

            return RefurbAdapter(settings)
        if adapter_name == "Skylos":
            from crackerjack.adapters.refactor.skylos import SkylosAdapter

            return SkylosAdapter(settings)

        if adapter_name == "Zuban":
            from crackerjack.adapters.lsp.zuban import ZubanAdapter
            from crackerjack.config.execution import ExecutionContext

            context = ExecutionContext(
                pkg_path=self.pkg_path,
                settings=self.settings,
            )
            return t.cast(AdapterProtocol, ZubanAdapter(context))

        if adapter_name == "Claude AI":
            from crackerjack.adapters.ai.claude import ClaudeCodeFixer

            return t.cast(AdapterProtocol, ClaudeCodeFixer())

        raise ValueError(f"Unknown adapter: {adapter_name}")
