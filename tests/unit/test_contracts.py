from __future__ import annotations

import importlib


def test_contracts_re_export_expected_symbols() -> None:
    contracts = importlib.import_module("crackerjack.contracts")

    assert contracts.__all__ == [
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


def test_contracts_re_exports_are_importable() -> None:
    contracts = importlib.import_module("crackerjack.contracts")

    assert contracts.ComponentHealth is not None
    assert contracts.WebSocketServer is not None
    assert contracts.create_service_token is not None
