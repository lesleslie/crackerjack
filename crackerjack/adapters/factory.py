from __future__ import annotations

import logging
import os
import typing as t
from pathlib import Path

from crackerjack.models.protocols import AdapterFactoryProtocol, AdapterProtocol

logger = logging.getLogger(__name__)


class DefaultAdapterFactory(AdapterFactoryProtocol):
    TOOL_TO_ADAPTER_NAME: t.ClassVar[dict[str, str]] = {
        "ruff": "Ruff",
        "bandit": "Bandit",
        "semgrep": "Semgrep",
        "refurb": "Refurb",
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
        """Build the adapter's *own* settings object for ``adapter_name``.

        Each adapter declares its settings as a narrowed type (e.g.
        ``BanditSettings``) and reads adapter-specific fields off it, so the
        default must be that exact class. Handing back a plain
        ``ToolAdapterSettings`` makes the adapter blow up on the first
        adapter-specific field access.
        """
        if adapter_name == "Ruff":
            from crackerjack.adapters.format.ruff import RuffSettings

            return RuffSettings()
        if adapter_name == "Bandit":
            from crackerjack.adapters.sast.bandit import BanditSettings

            return BanditSettings()
        if adapter_name == "Semgrep":
            from crackerjack.adapters.sast.semgrep import SemgrepSettings

            return SemgrepSettings()
        if adapter_name == "Refurb":
            from crackerjack.adapters.refactor.refurb import RefurbSettings

            return RefurbSettings()
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
        """Pick the settings object to hand to the adapter.

        The factory-level ``settings`` is only usable when it is itself a
        tool settings object. Callers such as the MCP server construct the
        factory with the *application* settings (``CrackerjackSettings``),
        which are not adapter settings at all — injecting those left every
        adapter raising ``AttributeError`` on its first settings access, and
        the caller swallowed that into a warning, so the adapter silently
        never worked.
        """
        if settings is not None:
            return settings

        from crackerjack.adapters._tool_adapter_base import ToolAdapterSettings

        if isinstance(self.settings, ToolAdapterSettings):
            return self.settings
        if self._is_ai_agent_enabled():
            return self._create_default_settings(adapter_name)
        return None

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
