from __future__ import annotations

import logging
from importlib import metadata

from crackerjack.adapters.base import LanguageAdapter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Multi-language extension entry-point discovery.
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

        if isinstance(obj, type):
            # Entry point returned a class (not an instance); instantiate it.
            try:
                obj = obj()
            except Exception as exc:
                logger.warning(
                    "adapter entry point %s failed to instantiate: %s",
                    ep.name,
                    exc,
                )
                continue
        elif not isinstance(obj, LanguageAdapter):
            logger.warning(
                "adapter entry point %s did not return a LanguageAdapter (got %s)",
                ep.name,
                type(obj).__name__,
            )
            continue

        adapters[obj.name] = obj

    return adapters


__all__ = [
    "discover_adapters",
]
