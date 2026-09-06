"""Tests for crackerjack/contracts.py re-export shim.

This module re-exports names from mcp_common so crackerjack callers can use a
single import path. The test verifies each name in ``__all__`` resolves to the
expected upstream symbol.
"""

from __future__ import annotations

import pytest

from crackerjack import contracts


@pytest.mark.parametrize(
    "name",
    [
        "ComponentHealth",
        "EventTypes",
        "FastMCPOpenTelemetryMiddleware",
        "MessageType",
        "WebSocketMessage",
        "WebSocketProtocol",
        "WebSocketServer",
        "create_service_token",
        "verify_token",
    ],
)
def test_contracts_reexports_named_attribute(name: str) -> None:
    """Every name in __all__ is accessible as a module attribute."""
    assert hasattr(contracts, name)


def test_contracts_reexports_match_all_attribute() -> None:
    """``__all__`` matches the set of names actually exported."""
    assert set(contracts.__all__) <= set(dir(contracts))


def test_contracts_exposes_expected_third_party_classes() -> None:
    """Re-exported types come from mcp_common packages, not local copies."""
    from mcp_common.health import ComponentHealth as _ComponentHealth
    from mcp_common.server.telemetry import (
        FastMCPOpenTelemetryMiddleware as _FastMCPMiddleware,
    )
    from mcp_common.websocket import (
        WebSocketMessage as _WebSocketMessage,
        WebSocketProtocol as _WebSocketProtocol,
        WebSocketServer as _WebSocketServer,
    )

    assert contracts.ComponentHealth is _ComponentHealth
    assert contracts.FastMCPOpenTelemetryMiddleware is _FastMCPMiddleware
    assert contracts.WebSocketMessage is _WebSocketMessage
    assert contracts.WebSocketProtocol is _WebSocketProtocol
    assert contracts.WebSocketServer is _WebSocketServer
