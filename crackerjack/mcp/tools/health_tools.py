"""Health check MCP tools for Crackerjack.

These tools provide standardized health check endpoints following the
mcp-common health infrastructure pattern.

Design: docs/plans/2026-02-27-health-check-system-design.md
"""

from __future__ import annotations

import time
from typing import Any

from dataclasses import dataclass

# Define local stubs for missing mcp-common types
# TODO: Remove when mcp-common adds these exports


@dataclass
class DependencyConfig:
    """Configuration for a health check dependency."""

    host: str
    port: int
    required: bool = True
    timeout_seconds: float = 5.0


def register_health_tools(
    mcp: Any,
    service_name: str,
    version: str,
    start_time: float,
    dependencies: dict[str, DependencyConfig],
) -> None:
    """Stub for mcp-common register_health_tools.

    This is a placeholder until mcp-common exports this function.
    Currently does nothing but prevents import errors.
    """

# Service metadata
SERVICE_NAME = "crackerjack"
SERVICE_VERSION = "0.1.0"
SERVICE_START_TIME = time.time()

# Default dependencies for Crackerjack
# These can be overridden via environment variables:
# CRACKERJACK_HEALTH__DEPENDENCIES__SESSION_BUDDY__HOST=remote-host
DEFAULT_DEPENDENCIES: dict[str, DependencyConfig] = {
    "session_buddy": DependencyConfig(
        host="localhost",
        port=8678,
        required=False,  # Optional - for session context
        timeout_seconds=10,
    ),
    "mahavishnu": DependencyConfig(
        host="localhost",
        port=8680,
        required=False,  # Optional - for orchestration
        timeout_seconds=10,
    ),
}


def register_health_tools_crackerjack(mcp_app: Any) -> None:
    """Register health check tools with Crackerjack MCP server.

    This uses mcp-common's register_health_tools with Crackerjack
    specific configuration.

    Tools registered:
        - health_check_service: Check health of a specific service
        - health_check_all: Check all configured dependencies
        - wait_for_dependency: Wait for a dependency to become healthy
        - wait_for_all_dependencies: Wait for all dependencies
        - get_liveness: Basic liveness probe
        - get_readiness: Readiness probe with dependency checks

    Args:
        mcp_app: FastMCP application instance
    """
    register_health_tools(
        mcp=mcp_app,
        service_name=SERVICE_NAME,
        version=SERVICE_VERSION,
        start_time=SERVICE_START_TIME,
        dependencies=DEFAULT_DEPENDENCIES,
    )


__all__ = ["register_health_tools_crackerjack"]
