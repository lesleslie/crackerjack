"""Crackerjack-facing facade for shared MCP/common primitives.

This keeps Crackerjack imports centralized while remaining compatible with the
currently released mcp-common package.
"""

from __future__ import annotations

from mcp_common.auth.core import create_service_token, verify_token
from mcp_common.health import ComponentHealth
from mcp_common.server.telemetry import FastMCPOpenTelemetryMiddleware
from mcp_common.websocket import (
    EventTypes,
    MessageType,
    WebSocketMessage,
    WebSocketProtocol,
    WebSocketServer,
)

__all__ = [
    "ComponentHealth",
    "EventTypes",
    "FastMCPOpenTelemetryMiddleware",
    "MessageType",
    "WebSocketMessage",
    "WebSocketProtocol",
    "WebSocketServer",
    "create_service_token",
    "verify_token",
]
