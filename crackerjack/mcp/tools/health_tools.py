
from __future__ import annotations

import time
from typing import Any

from dataclasses import dataclass


# TODO: Remove when mcp-common adds these exports


@dataclass
class DependencyConfig:

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


SERVICE_NAME = "crackerjack"
SERVICE_VERSION = "0.1.0"
SERVICE_START_TIME = time.time()


DEFAULT_DEPENDENCIES: dict[str, DependencyConfig] = {
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


def register_health_tools_crackerjack(mcp_app: Any) -> None:
    register_health_tools(
        mcp=mcp_app,
        service_name=SERVICE_NAME,
        version=SERVICE_VERSION,
        start_time=SERVICE_START_TIME,
        dependencies=DEFAULT_DEPENDENCIES,
    )


__all__ = ["register_health_tools_crackerjack"]
