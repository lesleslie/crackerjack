"""Wrapper for mcp_common ``register_health_tools`` with Crackerjack-specific args.

Kept separate from ``profiles.py`` so the latter can lazy-import this
wrapper without pulling in ``crackerjack.mcp.server_core`` (which would
create a circular import at module load).
"""

from __future__ import annotations

import time
from importlib.metadata import version as pkg_version
from typing import TYPE_CHECKING, Final

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
    """
    register_health_tools(
        mcp_app,
        service_name="crackerjack",
        version=_crackerjack_version(),
        start_time=SERVICE_START_TIME,
        dependencies=_HEALTH_DEPENDENCIES,
    )


__all__ = ["register_crackerjack_health"]
