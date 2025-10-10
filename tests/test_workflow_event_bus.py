from __future__ import annotations

import asyncio

import pytest

from acb.events import EventHandlerResult

from crackerjack.events import (
    WorkflowEvent,
    WorkflowEventBus,
    WorkflowEventTelemetry,
)


@pytest.mark.asyncio
async def test_workflow_event_bus_delivers_specific_events() -> None:
    bus = WorkflowEventBus()
    received: list[str] = []

    async def handler(event) -> EventHandlerResult:
        received.append(event.metadata.event_type)
        return EventHandlerResult(success=True)

    bus.subscribe(WorkflowEvent.WORKFLOW_STARTED, handler)

    await bus.publish(WorkflowEvent.WORKFLOW_STARTED, {"workflow_id": "abc"})

    assert received == [WorkflowEvent.WORKFLOW_STARTED.value]


@pytest.mark.asyncio
async def test_workflow_event_bus_wildcard_subscription() -> None:
    bus = WorkflowEventBus()
    received: list[str] = []

    async def handler(event) -> EventHandlerResult:
        received.append(event.metadata.event_type)
        return EventHandlerResult(success=True)

    bus.subscribe(None, handler)

    await bus.publish(WorkflowEvent.WORKFLOW_COMPLETED, {"workflow_id": "abc", "success": True})

    assert received == [WorkflowEvent.WORKFLOW_COMPLETED.value]


@pytest.mark.asyncio
async def test_workflow_event_bus_unsubscribe() -> None:
    bus = WorkflowEventBus()
    latch = asyncio.Event()

    async def handler(event) -> EventHandlerResult:  # pragma: no cover - should not run
        latch.set()
        return EventHandlerResult(success=True)

    subscription_id = bus.subscribe(WorkflowEvent.WORKFLOW_FAILED, handler)
    assert bus.unsubscribe(subscription_id) is True

    await bus.publish(WorkflowEvent.WORKFLOW_FAILED, {"workflow_id": "abc"})

    assert not latch.is_set()


def test_workflow_event_bus_register_logging_handler_idempotent() -> None:
    bus = WorkflowEventBus()
    bus.register_logging_handler()
    first_count = len(bus.list_subscriptions())

    bus.register_logging_handler()
    second_count = len(bus.list_subscriptions())

    assert first_count == second_count


@pytest.mark.asyncio
async def test_workflow_event_telemetry_snapshot() -> None:
    bus = WorkflowEventBus()
    telemetry = WorkflowEventTelemetry(max_history=5)
    bus.subscribe(None, telemetry.handle_event)

    await bus.publish(WorkflowEvent.WORKFLOW_STARTED, {"workflow_id": "123"})
    await bus.publish(WorkflowEvent.WORKFLOW_COMPLETED, {"workflow_id": "123", "success": True})

    snapshot = await telemetry.snapshot()
    assert snapshot["counts"][WorkflowEvent.WORKFLOW_STARTED.value] == 1
    assert snapshot["counts"][WorkflowEvent.WORKFLOW_COMPLETED.value] == 1
    assert len(snapshot["recent_events"]) == 2


@pytest.mark.asyncio
async def test_workflow_event_bus_retries_on_failure() -> None:
    bus = WorkflowEventBus()
    attempts = 0

    async def flaky_handler(event) -> EventHandlerResult:
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise RuntimeError("transient failure")
        return EventHandlerResult(success=True, metadata={"attempts": attempts})

    bus.subscribe(
        WorkflowEvent.WORKFLOW_STARTED,
        flaky_handler,
        max_retries=2,
        retry_backoff=0.0,
    )

    result = await bus.publish(WorkflowEvent.WORKFLOW_STARTED, {"workflow_id": "wf"})
    assert attempts == 3
    assert result.results[0].success is True
    assert result.results[0].metadata["attempts"] == 3


@pytest.mark.asyncio
async def test_workflow_event_bus_propagates_after_retry_limit() -> None:
    bus = WorkflowEventBus()

    async def failing_handler(event) -> EventHandlerResult:
        raise RuntimeError("persistent failure")

    bus.subscribe(
        WorkflowEvent.WORKFLOW_STARTED,
        failing_handler,
        max_retries=1,
        retry_backoff=0.0,
    )

    dispatch_result = await bus.publish(WorkflowEvent.WORKFLOW_STARTED, {})
    assert dispatch_result.results[0].success is False
    assert "persistent failure" in dispatch_result.results[0].error_message
