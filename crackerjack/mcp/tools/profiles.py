"""Tool profile registration groups for Crackerjack MCP server.

Maps ToolProfile levels to specific register_*() call lists, controlling
which tools are exposed at startup based on the CRACKERJACK_TOOL_PROFILE
environment variable.

Profile tiers:
    MINIMAL:  Health probes only (always-on via mandatory_groups).
    STANDARD: Adds core, execution, utility, and doc tools.
    FULL:     All groups including eventbridge, progress, semantic, monitoring,
              otel, pycharm, proactive.

The dispatch surface (PROFILE_REGISTRATIONS + REGISTRATION_MAP +
CRACKERJACK_MANDATORY_GROUPS) is consumed by
``mcp_common.tools.dispatch._apply_tool_profile`` when called from
``crackerjack.mcp.server_core.create_mcp_server``.

W2a migration: replaces the legacy ``crackerjack.mcp.tools.discover_tools``
module (236 lines: TOOL_REGISTRY + DEFERRED_TOOLS + register_discover_tools)
with the W0 helper. Health probes are mandatory at every profile tier so
load balancers / orchestrators can always reach them. The
``crackerjack_discovery`` discovery_fn override preserves the historical
query filter behavior (case-insensitive substring on name + description).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from mcp_common.tools import ToolProfile
from mcp_common.tools.dispatch import ALL_TOOLS

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from fastmcp import FastMCP


MINIMAL_REGISTRATIONS: list[str | Callable[[FastMCP], Awaitable[None] | None]] = []

STANDARD_REGISTRATIONS: list[str | Callable[[FastMCP], Awaitable[None] | None]] = [
    "core_tools",
    "execution_tools",
    "utility_tools",
    "doc_tools",
]

FULL_REGISTRATIONS: list[str | Callable[[FastMCP], Awaitable[None] | None]] = [
    *STANDARD_REGISTRATIONS,
    "eventbridge_tools",
    "monitoring_tools",
    "otel_tools",
    "progress_tools",
    "proactive_tools",
    "pycharm_tools",
    "semantic_tools",
]

PROFILE_REGISTRATIONS: dict[
    ToolProfile,
    list[str | Callable[[FastMCP], Awaitable[None] | None]] | type[ALL_TOOLS],
] = {
    ToolProfile.MINIMAL: MINIMAL_REGISTRATIONS,
    ToolProfile.STANDARD: STANDARD_REGISTRATIONS,
    ToolProfile.FULL: FULL_REGISTRATIONS,
}


# ---------------------------------------------------------------------------
# W0 apply_tool_profile dispatch surface.
#
# REGISTRATION_MAP routes each group key from PROFILE_REGISTRATIONS to a
# per-group registration callable (taking the FastMCP app). Lazy import keeps
# this module importable without all per-group register modules being
# resolved at module load (avoids circular imports).
# CRACKERJACK_MANDATORY_GROUPS is a set of registration_map keys whose
# registrars run AFTER per-profile dispatch at every profile (always-on).
# The W0 helper raises if a mandatory key is missing from the map.
# ---------------------------------------------------------------------------
def _build_registration_map() -> dict[str, Callable[[FastMCP], Awaitable[None] | None]]:
    """Build the {group_key: register_fn(app)} map.

    Local import keeps ``crackerjack.mcp.tools.profiles`` importable without
    forcing every per-group register module to load at import time.
    """
    from crackerjack.mcp.tools.core_tools import register_core_tools
    from crackerjack.mcp.tools.doc_tools import register_doc_tools
    from crackerjack.mcp.tools.eventbridge_tools_wrapper import (
        register_crackerjack_eventbridge,
    )
    from crackerjack.mcp.tools.execution_tools import register_execution_tools
    from crackerjack.mcp.tools.health_tools_wrapper import (
        register_crackerjack_health,
    )
    from crackerjack.mcp.tools.monitoring_tools import register_monitoring_tools
    from crackerjack.mcp.tools.otel_tools import register_otel_tools
    from crackerjack.mcp.tools.proactive_tools import register_proactive_tools
    from crackerjack.mcp.tools.progress_tools import register_progress_tools
    from crackerjack.mcp.tools.pycharm_tools import register_pycharm_tools
    from crackerjack.mcp.tools.semantic_tools import register_semantic_tools
    from crackerjack.mcp.tools.utility_tools import register_utility_tools

    return {
        "core_tools": register_core_tools,
        "doc_tools": register_doc_tools,
        "eventbridge_tools": register_crackerjack_eventbridge,
        "execution_tools": register_execution_tools,
        "health_tools": register_crackerjack_health,
        "monitoring_tools": register_monitoring_tools,
        "otel_tools": register_otel_tools,
        "proactive_tools": register_proactive_tools,
        "progress_tools": register_progress_tools,
        "pycharm_tools": register_pycharm_tools,
        "semantic_tools": register_semantic_tools,
        "utility_tools": register_utility_tools,
    }


REGISTRATION_MAP: dict[str, Callable[[FastMCP], Awaitable[None] | None]] = (
    _build_registration_map()
)


# Always-on groups: registered at every profile level in addition to the
# per-profile list. Health checks must be reachable from any profile tier
# (load balancers / orchestrators depend on them).
CRACKERJACK_MANDATORY_GROUPS: set[str] = {"health_tools"}


def register_all_tool_groups(server: FastMCP) -> None:
    """Bulk register all Crackerjack tool groups (called at FULL profile).

    Used as ``register_all_fn`` for the W0 helper. Iterates every group in
    REGISTRATION_MAP so adding a new group in profiles.py does not require
    a separate edit here.
    """
    from crackerjack.mcp.tools.core_tools import register_core_tools
    from crackerjack.mcp.tools.doc_tools import register_doc_tools
    from crackerjack.mcp.tools.eventbridge_tools_wrapper import (
        register_crackerjack_eventbridge,
    )
    from crackerjack.mcp.tools.execution_tools import register_execution_tools
    from crackerjack.mcp.tools.health_tools_wrapper import (
        register_crackerjack_health,
    )
    from crackerjack.mcp.tools.monitoring_tools import register_monitoring_tools
    from crackerjack.mcp.tools.otel_tools import register_otel_tools
    from crackerjack.mcp.tools.proactive_tools import register_proactive_tools
    from crackerjack.mcp.tools.progress_tools import register_progress_tools
    from crackerjack.mcp.tools.pycharm_tools import register_pycharm_tools
    from crackerjack.mcp.tools.semantic_tools import register_semantic_tools
    from crackerjack.mcp.tools.utility_tools import register_utility_tools

    register_core_tools(server)
    register_doc_tools(server)
    register_crackerjack_eventbridge(server)
    register_execution_tools(server)
    register_crackerjack_health(server)
    register_monitoring_tools(server)
    register_otel_tools(server)
    register_proactive_tools(server)
    register_progress_tools(server)
    register_pycharm_tools(server)
    register_semantic_tools(server)
    register_utility_tools(server)


__all__ = [
    "CRACKERJACK_MANDATORY_GROUPS",
    "FULL_REGISTRATIONS",
    "MINIMAL_REGISTRATIONS",
    "PROFILE_REGISTRATIONS",
    "REGISTRATION_MAP",
    "STANDARD_REGISTRATIONS",
    "register_all_tool_groups",
]
