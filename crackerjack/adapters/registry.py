from __future__ import annotations

import logging
import typing as t
from importlib import metadata

from crackerjack.adapters._qa_adapter_base import QAAdapterBase
from crackerjack.adapters.base import LanguageAdapter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Legacy QAAdapterBase registry (preserved for backward compatibility).
# Only consumed by tests/adapters/test_adapter_registry.py.
# New LanguageAdapter discovery lives below — see discover_adapters().
# ---------------------------------------------------------------------------


class AdapterRegistry:
    _adapters: dict[str, type[QAAdapterBase]] = {}

    @classmethod
    def register(cls, name: str, adapter_class: type[QAAdapterBase]) -> None:
        if name in cls._adapters:
            logger.warning(
                f"QAAdapterBase '{name}' already registered, skipping duplicate registration"
            )
            return

        cls._adapters[name] = adapter_class
        logger.debug(f"Registered adapter: {name}")

    @classmethod
    def create(cls, name: str, settings: t.Any | None = None) -> QAAdapterBase:
        if name not in cls._adapters:
            available = ", ".join(sorted(cls._adapters.keys()))
            raise ValueError(f"Unknown adapter: {name}. Available: {available}")

        adapter_class = cls._adapters[name]
        return adapter_class(settings)  # type: ignore

    @classmethod
    def is_registered(cls, name: str) -> bool:
        return name in cls._adapters

    @classmethod
    def list_adapters(cls) -> list[str]:
        return sorted(cls._adapters.keys())

    @classmethod
    def get_adapter_info(cls, name: str) -> dict[str, t.Any] | None:
        if name not in cls._adapters:
            return None

        adapter_class = cls._adapters[name]
        return {
            "name": name,
            "class": adapter_class.__name__,
            "module": adapter_class.__module__,
        }


def get_adapter_registry() -> AdapterRegistry:
    return AdapterRegistry()


# ---------------------------------------------------------------------------
# Phase 1 — multi-language extension entry-point discovery.
# Spec: dd9d9c05. Reads the crackerjack.language_adapters entry-point group,
# validates each loaded object via isinstance(LanguageAdapter), and logs
# (does not raise) on broken third-party adapters so a bad external package
# cannot brick crackerjack.
# ---------------------------------------------------------------------------


def _entry_points() -> metadata.EntryPoints:
    """Entry points under the crackerjack.language_adapters group.

    Indirected through a module-level function so tests can patch it.
    """
    return metadata.entry_points(group="crackerjack.language_adapters")


def discover_adapters() -> dict[str, LanguageAdapter]:
    """Discover and instantiate language adapters via entry points.

    Invalid adapters (import errors, missing protocol methods) are
    logged and skipped — they must not brick crackerjack.
    """
    adapters: dict[str, LanguageAdapter] = {}

    for ep in _entry_points():
        try:
            obj = ep.load()
        except Exception as exc:
            logger.warning(
                "adapter entry point %s failed to import: %s",
                ep.name,
                exc,
            )
            continue

        if not isinstance(obj, LanguageAdapter):
            logger.warning(
                "adapter entry point %s did not return a LanguageAdapter (got %s)",
                ep.name,
                type(obj).__name__,
            )
            continue

        adapters[obj.name] = obj

    return adapters


__all__ = [
    "AdapterRegistry",
    "discover_adapters",
    "get_adapter_registry",
]
