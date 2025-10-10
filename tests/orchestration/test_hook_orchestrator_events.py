from __future__ import annotations

import pytest

from acb.events import EventHandlerResult

from crackerjack.config.hooks import HookDefinition, HookStrategy
from crackerjack.events import WorkflowEvent, WorkflowEventBus
from crackerjack.orchestration.hook_orchestrator import HookOrchestratorAdapter


@pytest.mark.asyncio
async def test_hook_orchestrator_emits_events() -> None:
    bus = WorkflowEventBus()
    captured: list[str] = []

    async def recorder(event) -> EventHandlerResult:
        captured.append(event.metadata.event_type)
        return EventHandlerResult(success=True)

    subscribed_events = {
        WorkflowEvent.HOOK_STRATEGY_STARTED,
        WorkflowEvent.HOOK_STRATEGY_COMPLETED,
        WorkflowEvent.HOOK_EXECUTION_STARTED,
        WorkflowEvent.HOOK_EXECUTION_COMPLETED,
    }

    for event in subscribed_events:
        bus.subscribe(event, recorder)

    orchestrator = HookOrchestratorAdapter(event_bus=bus)
    await orchestrator.init()

    strategy = HookStrategy(
        name="test-strategy",
        hooks=[HookDefinition(name="demo", command=[])],
        parallel=False,
    )

    results = await orchestrator.execute_strategy(strategy, execution_mode="acb")

    assert len(results) == 1
    assert results[0].name == "demo"
    assert WorkflowEvent.HOOK_STRATEGY_STARTED.value in captured
    assert WorkflowEvent.HOOK_EXECUTION_STARTED.value in captured
    assert WorkflowEvent.HOOK_EXECUTION_COMPLETED.value in captured
    assert WorkflowEvent.HOOK_STRATEGY_COMPLETED.value in captured
