from __future__ import annotations


def test_websocket_server_uses_mcp_common_contracts() -> None:
    from crackerjack.contracts import WebSocketServer
    from crackerjack.websocket.server import (
        WebSocketServer as CrackerjackWebSocketServer,
    )

    assert CrackerjackWebSocketServer is WebSocketServer


def test_health_handler_uses_mcp_common_contracts() -> None:
    from crackerjack.cli.handlers.health import ComponentHealth
    from crackerjack.contracts import ComponentHealth as SharedComponentHealth

    assert ComponentHealth is SharedComponentHealth
