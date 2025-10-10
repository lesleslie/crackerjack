from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from acb.events import create_event

from crackerjack.events.telemetry import WorkflowEventTelemetry
from crackerjack.events.workflow_bus import WorkflowEvent, WorkflowEventBus


def _make_event(event_type: WorkflowEvent, payload: dict[str, object]) -> object:
    return create_event(event_type.value, "tests.workflow", payload)


@pytest.mark.asyncio
async def test_telemetry_persists_state(tmp_path: Path) -> None:
    state_file = tmp_path / "workflow_events.json"
    telemetry = WorkflowEventTelemetry(state_file=state_file)

    event = _make_event(
        WorkflowEvent.WORKFLOW_COMPLETED,
        {"workflow_id": "wf-1", "success": True},
    )

    result = await telemetry.handle_event(event)
    assert result.success is True

    # Wait for background persistence to complete.
    assert telemetry._persist_task is not None  # noqa: SLF001 - intentional check
    await telemetry._persist_task

    assert state_file.exists()
    data = json.loads(state_file.read_text())
    assert data["counts"]["workflow.completed"] == 1
    assert data["recent_events"][0]["payload"]["success"] is True

    await telemetry.shutdown()


@pytest.mark.asyncio
async def test_telemetry_reset_clears_state(tmp_path: Path) -> None:
    state_file = tmp_path / "workflow_events.json"
    telemetry = WorkflowEventTelemetry(state_file=state_file)

    event = _make_event(
        WorkflowEvent.WORKFLOW_FAILED,
        {"workflow_id": "wf-2", "error": "boom"},
    )

    await telemetry.handle_event(event)
    if telemetry._persist_task is not None:  # noqa: SLF001 - intentional check
        await telemetry._persist_task

    assert state_file.exists()
    await telemetry.reset()
    assert not state_file.exists()

    snapshot = await telemetry.snapshot()
    assert snapshot["counts"] == {}
    assert snapshot["recent_events"] == []
    assert snapshot["last_error"] is None

    await telemetry.shutdown()


@pytest.mark.asyncio
async def test_event_bus_handles_concurrent_workflows() -> None:
    bus = WorkflowEventBus()
    telemetry = WorkflowEventTelemetry()

    subscription_id = bus.subscribe(
        event_type=None,
        handler=telemetry.handle_event,
        description="tests.telemetry",
        max_concurrent=3,
    )
    assert subscription_id

    async def run_workflow(workflow_idx: int) -> None:
        await bus.publish(
            WorkflowEvent.WORKFLOW_STARTED,
            {"workflow_id": workflow_idx},
        )
        # Simulate some work before completion.
        await asyncio.sleep(0)
        await bus.publish(
            WorkflowEvent.WORKFLOW_COMPLETED,
            {"workflow_id": workflow_idx, "success": True},
        )

    await asyncio.gather(*(run_workflow(idx) for idx in range(5)))

    snapshot = await telemetry.snapshot()
    assert snapshot["counts"]["workflow.started"] == 5
    assert snapshot["counts"]["workflow.completed"] == 5
    assert len(snapshot["recent_events"]) >= 5

    await telemetry.shutdown()


@pytest.mark.asyncio
async def test_telemetry_rollup_scheduler(tmp_path: Path) -> None:
    state_file = tmp_path / "workflow_events.json"
    rollup_file = tmp_path / "rollups.jsonl"
    telemetry = WorkflowEventTelemetry(
        state_file=state_file,
        rollup_file=rollup_file,
        rollup_interval_seconds=0.05,
    )

    event = _make_event(
        WorkflowEvent.WORKFLOW_COMPLETED,
        {"workflow_id": "wf-rollup", "success": True},
    )
    await telemetry.handle_event(event)

    await asyncio.sleep(0.07)
    await telemetry.shutdown()

    assert rollup_file.exists()
    lines = [json.loads(line) for line in rollup_file.read_text().splitlines() if line]
    assert lines
    assert lines[0]["counts"]["workflow.completed"] == 1
