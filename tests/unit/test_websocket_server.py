from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from crackerjack.websocket import CrackerjackWebSocketServer


@pytest.mark.asyncio
async def test_quality_gate_status_returns_contract_shape() -> None:
    qc_manager = MagicMock()
    qc_manager.get_quality_gate_report = MagicMock(
        return_value={
            "fast_hooks": True,
            "tests": False,
            "comprehensive": False,
            "coverage": 82.5,
            "errors": ["tests failed"],
            "checks": [
                {
                    "name": "tests",
                    "passed": False,
                    "severity": "required",
                    "score": 82.5,
                    "threshold": 90.0,
                }
            ],
            "repository": "demo-project",
            "profile": "standard",
        }
    )

    server = CrackerjackWebSocketServer(qc_manager=qc_manager)

    status = await server._get_quality_gate_status("demo-project")

    assert status["project"] == "demo-project"
    assert status["repository"] == "demo-project"
    assert status["status"] == "failed"
    assert status["passed"] is False
    assert status["blocking_failure"] is True
    assert status["gates"][0]["name"] == "tests"
    assert status["checks"][0]["name"] == "tests"
    assert status["checks"][0]["severity"] == "required"


@pytest.mark.asyncio
async def test_broadcast_quality_gate_checked_includes_report_contract() -> None:
    qc_manager = MagicMock()
    server = CrackerjackWebSocketServer(qc_manager=qc_manager)
    server.broadcast_to_room = AsyncMock()

    await server.broadcast_quality_gate_checked(
        "demo-project",
        "tests",
        "passed",
        97.5,
        90.0,
    )

    room, event = server.broadcast_to_room.call_args.args
    assert room == "quality:demo-project"
    assert event.event == "quality_gate.checked"
    assert event.data["project"] == "demo-project"
    assert event.data["gate_name"] == "tests"
    assert event.data["quality_gate_report"]["repository"] == "demo-project"
    assert event.data["quality_gate_report"]["passed"] is True
    assert event.data["quality_gate_report"]["checks"][0]["name"] == "tests"
