"""Wrapper for mcp_common ``register_health_tools`` with Crackerjack-specific args.

Kept separate from ``profiles.py`` so the latter can lazy-import this
wrapper without pulling in ``crackerjack.mcp.server_core`` (which would
create a circular import at module load).
"""

from __future__ import annotations

import time
from importlib.metadata import version as pkg_version
from typing import TYPE_CHECKING, Any, Final

from mcp_common.health import DependencyConfig, register_health_tools

if TYPE_CHECKING:
    from fastmcp import FastMCP


_HEALTH_DEPENDENCIES: dict[str, DependencyConfig] = {
    "session_buddy": DependencyConfig(
        host="localhost",
        port=8678,
        required=False,
        timeout_seconds=10,
    ),
    "mahavishnu": DependencyConfig(
        host="localhost",
        port=8680,
        required=False,
        timeout_seconds=10,
    ),
}


SERVICE_START_TIME: Final[float] = time.time()


def _crackerjack_version() -> str:
    try:
        return pkg_version("crackerjack")
    except Exception:
        return "0.0.0-unknown"


def register_crackerjack_health(mcp_app: FastMCP) -> None:
    """Register mcp_common health probes with Crackerjack-specific args.

    Mirrors the wiring previously hard-coded in ``create_mcp_server`` so
    every profile tier (MINIMAL/STANDARD/FULL) exposes the same health
    probes (``get_liveness``, ``get_readiness``, ``health_check_service``,
    ``health_check_all``, ``wait_for_dependency``, ``wait_for_all_dependencies``).

    Also registers :func:`crackerjack_get_health` — the MCP-tool
    counterpart of the ``/health`` HTTP route. Both surfaces route
    through :func:`crackerjack.mcp.health.build_health_envelope` so
    they agree on the same feed-state (REQ-HC-003 in
    ``docs/plans/2026-10-09-mcp-health-check-enrichment.md``).
    """
    register_health_tools(
        mcp_app,
        service_name="crackerjack",
        version=_crackerjack_version(),
        start_time=SERVICE_START_TIME,
        dependencies=_HEALTH_DEPENDENCIES,
    )

    @mcp_app.tool()  # type: ignore[untyped-decorator]
    async def crackerjack_get_health() -> dict[str, Any]:
        """Return the canonical HealthSnapshot envelope for Crackerjack.

        Wire-shape matches the ``/health`` HTTP route on the same
        server. Operators can call this MCP tool to get the same
        feed-state the HTTP route returns without needing a separate
        HTTP client.

        The status field is one of ``healthy`` / ``warming_up`` /
        ``degraded`` / ``failed``; ``degraded_feeds`` lists the
        per-feed names where ``healthy=False`` (per plan §1
        acceptance gate).
        """
        from crackerjack.mcp.health import build_health_envelope

        envelope = build_health_envelope()
        if envelope is None:
            # Pre-init warm-up window. The HTTP route translates this
            # to a 503; the MCP tool can't return a status code, so
            # it returns a degraded envelope in the body and lets
            # callers branch on ``status``.
            return {
                "status": "degraded",
                "checks": {
                    "skills_signer": {
                        "status": "degraded",
                        "healthy": False,
                        "reason_codes": ["not_initialized"],
                    },
                },
                "reason_codes": ["not_initialized"],
                "degraded_feeds": ["skills_signer"],
            }
        return envelope


__all__ = ["register_crackerjack_health"]
