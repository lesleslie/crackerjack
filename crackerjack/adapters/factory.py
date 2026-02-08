import logging
import os
import typing as t
from pathlib import Path

from crackerjack.models.protocols import AdapterFactoryProtocol, AdapterProtocol

logger = logging.getLogger(__name__)

if t.TYPE_CHECKING:
    pass


class DefaultAdapterFactory(AdapterFactoryProtocol):
    TOOL_TO_ADAPTER_NAME: t.ClassVar[dict[str, str]] = {
        "ruff": "Ruff",
        "bandit": "Bandit",
        "semgrep": "Semgrep",
        "refurb": "Refurb",
        "skylos": "Skylos",
        "zuban": "Zuban",
    }

    def __init__(
        self,
        settings: t.Any | None = None,
        pkg_path: Path | None = None,
    ) -> None:
        self.settings = settings
        self.pkg_path = pkg_path or Path.cwd()

    def _is_ai_agent_enabled(self) -> bool:
        return os.environ.get("AI_AGENT") == "1"

    def _enable_tool_native_fixes(
        self,
        adapter_name: str,
        settings: t.Any | None,
    ) -> t.Any:
        if not self._is_ai_agent_enabled():
            return settings

        if adapter_name == "Ruff" and settings is not None:
            if hasattr(settings, "fix_enabled"):
                settings.fix_enabled = True
                logger.info("Tool-native fixes enabled for Ruff (fix_enabled=True)")

        return settings

    def tool_has_adapter(self, tool_name: str) -> bool:
        return tool_name in self.TOOL_TO_ADAPTER_NAME

    def get_adapter_name(self, tool_name: str) -> str | None:
        return self.TOOL_TO_ADAPTER_NAME.get(tool_name)

    def create_adapter(
        self,
        adapter_name: str,
        settings: t.Any | None = None,
    ) -> AdapterProtocol:

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
