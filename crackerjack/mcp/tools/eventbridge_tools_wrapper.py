"""Wrapper for ``register_eventbridge_tools`` that honors ``crackerjack.yaml``.

The ``eventbridge_tools`` group is only registered when
``crackerjack.yaml::eventbridge.enabled=true`` (default ``false``).
This wrapper defers the setting read to call time so it stays compatible
with the W0 helper, which calls ``register_fn(server)`` with no extra args.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from crackerjack.mcp.tools.eventbridge_tools import register_eventbridge_tools

if TYPE_CHECKING:
    from fastmcp import FastMCP


def _eventbridge_enabled() -> bool:
    """Return ``crackerjack.yaml::eventbridge.enabled`` (default ``False``)."""
    try:
        from crackerjack.config import CrackerjackSettings

        settings = CrackerjackSettings()
    except Exception:
        return False
    return bool(
        getattr(
            getattr(settings, "eventbridge", None),
            "enabled",
            False,
        ),
    )


def register_crackerjack_eventbridge(mcp_app: FastMCP) -> None:
    """Register ``publish_to_eventbridge`` only when explicitly enabled.

    No-op when the setting is unset/false. This preserves the
    pre-W2a conditional-registration behavior.
    """
    if not _eventbridge_enabled():
        return
    register_eventbridge_tools(mcp_app, publisher=None, enabled=True)


__all__ = ["register_crackerjack_eventbridge"]
