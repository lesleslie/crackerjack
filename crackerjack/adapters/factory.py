from __future__ import annotations

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
        "pyrefly": "Pyrefly",
        "ty": "Ty",
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

    def _create_default_settings(self, adapter_name: str) -> t.Any:
        if adapter_name == "Ruff":
            from crackerjack.adapters.format.ruff import RuffSettings

            return RuffSettings()  # type: ignore
        if adapter_name == "Bandit":
            from crackerjack.adapters._tool_adapter_base import ToolAdapterSettings

            return ToolAdapterSettings(tool_name="bandit")
        if adapter_name == "Semgrep":
            from crackerjack.adapters._tool_adapter_base import ToolAdapterSettings

            return ToolAdapterSettings(tool_name="semgrep")
        if adapter_name == "Refurb":
            from crackerjack.adapters._tool_adapter_base import ToolAdapterSettings

            return ToolAdapterSettings(tool_name="refurb")
        if adapter_name == "Skylos":
            from crackerjack.adapters._tool_adapter_base import ToolAdapterSettings

            return ToolAdapterSettings(tool_name="skylos")
        if adapter_name == "Zuban":
            from crackerjack.adapters._tool_adapter_base import ToolAdapterSettings

            return ToolAdapterSettings(tool_name="zuban")
        if adapter_name == "Pyrefly":
            from crackerjack.adapters.type.pyrefly import PyreflySettings

            return PyreflySettings()
        if adapter_name == "Ty":
            from crackerjack.adapters.type.ty import TySettings

            return TySettings()
        return None

    def tool_has_adapter(self, tool_name: str) -> bool:
        return tool_name in self.TOOL_TO_ADAPTER_NAME

    def get_adapter_name(self, tool_name: str) -> str | None:
        return self.TOOL_TO_ADAPTER_NAME.get(tool_name)

    def create_adapter(
        self,
        adapter_name: str,
        settings: t.Any | None = None,
    ) -> AdapterProtocol:
        settings = self._resolve_settings(adapter_name, settings)
        settings = self._enable_tool_native_fixes(adapter_name, settings)

        adapter = self._instantiate_adapter(adapter_name, settings)
        if adapter is not None:
            return adapter

        if adapter_name in ("Claude AI", "FallbackChain"):
            from crackerjack.adapters.ai.unified import FallbackChainCodeFixer

            return t.cast(AdapterProtocol, FallbackChainCodeFixer())

        raise ValueError(f"Unknown adapter: {adapter_name}")

    def _resolve_settings(
        self,
        adapter_name: str,
        settings: t.Any | None,
    ) -> t.Any | None:
        if settings is None and self.settings is not None:
            return self.settings
        if settings is None and self._is_ai_agent_enabled():
            return self._create_default_settings(adapter_name)
        return settings

    def _instantiate_adapter(
        self,
        adapter_name: str,
        settings: t.Any | None,
    ) -> AdapterProtocol | None:
        adapters = {
            "Ruff": ("format.ruff", "RuffAdapter"),
            "Bandit": ("sast.bandit", "BanditAdapter"),
            "Semgrep": ("sast.semgrep", "SemgrepAdapter"),
            "Refurb": ("refactor.refurb", "RefurbAdapter"),
            "Skylos": ("refactor.skylos", "SkylosAdapter"),
            "Zuban": ("type.zuban", "ZubanAdapter"),
            "Pyrefly": ("type.pyrefly", "PyreflyAdapter"),
            "Ty": ("type.ty", "TyAdapter"),
        }

        if adapter_name not in adapters:
            return None

        module_path, class_name = adapters[adapter_name]
        module = __import__(
            f"crackerjack.adapters.{module_path}", fromlist=[class_name]
        )
        adapter_class = getattr(module, class_name)
        return adapter_class(settings)
