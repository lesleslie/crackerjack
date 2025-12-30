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
    """Return the preferred console width from settings or pyproject.

    Priority:
    1) ACB settings (CrackerjackSettings.console.width)
    2) pyproject.toml [tool.crackerjack].terminal_width
    3) Default: 70
    """
    # 1) Try loaded settings (no DI)
    with suppress(Exception):
        settings = load_settings(CrackerjackSettings)
        width = getattr(getattr(settings, "console", None), "width", None)
        if isinstance(width, int) and width > 0:
            return width

    # 2) Try pyproject.toml
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

    # 3) Default
    return 70


# Load settings from YAML files using layered configuration
# Note: settings_instance is module-level and can be imported directly
settings_instance = load_settings(CrackerjackSettings)

# TODO(Phase 3): ACB Logger registration removed in Phase 2
# Will be replaced with Oneiric dependency management in Phase 3
# from crackerjack.utils.dependency_guard import (
#     ensure_logger_dependency,
#     validate_dependency_registration,
# )
#
# ensure_logger_dependency()
#
# # Explicitly set logger instances if not already set properly
# try:
#     if isinstance(current_logger, tuple) and len(current_logger) == 0:
#         logger_instance = Logger()
#         depends.set(Logger, logger_instance)
#         depends.set(LoggerProtocol, logger_instance)
#     else:
#         depends.set(LoggerProtocol, current_logger)
# except Exception:
#     logger_instance = Logger()
#     depends.set(Logger, logger_instance)
#     depends.set(LoggerProtocol, logger_instance)


def register_services() -> None:
    """Placeholder for legacy DI setup (ACB removed)."""
    logger.info("register_services skipped (ACB DI removed)")


# Service registration is called explicitly by application entry point
# to avoid circular import issues during module initialization.
# Call register_services() after all modules are loaded, typically in __main__.py

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
