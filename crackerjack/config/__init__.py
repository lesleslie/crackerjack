import logging
from contextlib import suppress

from .hooks import (
    COMPREHENSIVE_STRATEGY,
    FAST_STRATEGY,
    HookConfigLoader,
    HookDefinition,
    HookStage,
    HookStrategy,
    RetryPolicy,
)
from .loader import load_settings, load_settings_async
from .mcp_settings_adapter import CrackerjackMCPSettings
from .settings import CrackerjackSettings

logger = logging.getLogger(__name__)


def get_console_width() -> int:
    with suppress(Exception):
        settings = load_settings(CrackerjackSettings)
        width = getattr(getattr(settings, "console", None), "width", None)
        if isinstance(width, int) and width > 0:
            return width

    with suppress(Exception):
        from pathlib import Path as _P

        import tomli

        pyproj = _P("pyproject.toml")
        if pyproj.exists():
            with pyproj.open("rb") as f:
                data = tomli.load(f)
            width = (
                data.get("tool", {}).get("crackerjack", {}).get("terminal_width", None)
            )
            if isinstance(width, int) and width > 0:
                return width

    return 70


settings_instance = load_settings(CrackerjackSettings)

# TODO(Phase 3): Legacy logger registration removed in Phase 2


def register_services() -> None:
    logger.info("register_services skipped (legacy DI removed)")


__all__ = [
    "COMPREHENSIVE_STRATEGY",
    "FAST_STRATEGY",
    "HookConfigLoader",
    "HookDefinition",
    "HookStage",
    "HookStrategy",
    "RetryPolicy",
    "CrackerjackSettings",
    "CrackerjackMCPSettings",
    "load_settings",
    "load_settings_async",
    "register_services",
    "get_console_width",
]
