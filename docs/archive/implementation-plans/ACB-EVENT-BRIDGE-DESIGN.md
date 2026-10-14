# ACB Event Bridge Architecture Design

## Overview

This document defines the **EventBridgeAdapter** pattern for bridging ACB workflow events with crackerjack's existing `WorkflowEventBus` system during the migration period.

## Problem Statement

Crackerjack has a rich event-driven architecture with 15+ custom event types:

```python
# Current WorkflowEventBus events (crackerjack/events/workflow_bus.py)
class WorkflowEvent(str, Enum):
    # Workflow lifecycle
    WORKFLOW_STARTED = "workflow.started"
    WORKFLOW_COMPLETED = "workflow.completed"
    WORKFLOW_FAILED = "workflow.failed"

    # Phase events
    CONFIG_PHASE_COMPLETED = "config.phase.completed"
    QUALITY_PHASE_STARTED = "quality.phase.started"
    QUALITY_PHASE_COMPLETED = "quality.phase.completed"

    # Hook events
    FAST_HOOKS_STARTED = "fast.hooks.started"
    FAST_HOOKS_COMPLETED = "fast.hooks.completed"
    COMPREHENSIVE_HOOKS_STARTED = "comprehensive.hooks.started"
    COMPREHENSIVE_HOOKS_COMPLETED = "comprehensive.hooks.completed"

    # Cleaning events
    CLEANING_STARTED = "cleaning.started"
    CLEANING_COMPLETED = "cleaning.completed"

    # Test events
    TEST_WORKFLOW_STARTED = "test.workflow.started"
    TEST_WORKFLOW_COMPLETED = "test.workflow.completed"

    # Publishing
    PUBLISH_PHASE_COMPLETED = "publish.phase.completed"
    COMMIT_PHASE_COMPLETED = "commit.phase.completed"
```

**Consumers of these events**:

- Progress monitors and UI panels
- Performance tracking and metrics
- Telemetry and logging
- Session state management
- MCP WebSocket streaming

**Challenge**: ACB `BasicWorkflowEngine` emits different events:

- `workflow.step.started`
- `workflow.step.completed`
- `workflow.step.failed`
- Generic, not crackerjack-specific

**Goal**: Maintain backward compatibility while leveraging ACB workflows.

## Solution: EventBridgeAdapter

### Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│         ACB BasicWorkflowEngine                          │
│  • workflow.step.started                                 │
│  • workflow.step.completed                               │
│  • workflow.step.failed                                  │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│            EventBridgeAdapter                            │
│  • Listens to ACB workflow events                        │
│  • Translates to crackerjack WorkflowEvent types         │
│  • Emits to existing WorkflowEventBus                    │
│  • Maintains event payload compatibility                 │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│         WorkflowEventBus (Existing)                      │
│  • WORKFLOW_STARTED                                      │
│  • FAST_HOOKS_COMPLETED                                  │
│  • COMPREHENSIVE_HOOKS_STARTED                           │
│  • ... (all 15+ event types)                            │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────────────┐
│         Event Consumers (Unchanged)                      │
│  • Progress monitors                                     │
│  • Performance tracking                                  │
│  • MCP WebSocket streaming                               │
│  • Telemetry and logging                                 │
└─────────────────────────────────────────────────────────┘
```

### Implementation

#### 1. EventBridgeAdapter Class

```python
# crackerjack/workflows/event_bridge.py

from dataclasses import dataclass
from typing import Any

from acb.depends import depends, Inject
from acb.events import Event

from crackerjack.events.workflow_bus import WorkflowEvent, WorkflowEventBus


@dataclass
class StepEventMapping:
    """Maps ACB workflow step IDs to crackerjack WorkflowEvent types."""

    step_id: str
    started_event: WorkflowEvent | None
    completed_event: WorkflowEvent | None
    failed_event: WorkflowEvent | None


class EventBridgeAdapter:
    """Bridges ACB workflow events to crackerjack WorkflowEventBus.

    This adapter translates generic ACB workflow step events into
    crackerjack-specific event types for backward compatibility.

    Example:
        ACB: workflow.step.started (step_id="fast_hooks")
        →
        Crackerjack: FAST_HOOKS_STARTED
    """

    # Step ID to event type mapping
    STEP_MAPPINGS: dict[str, StepEventMapping] = {
        "config": StepEventMapping(
            step_id="config",
            started_event=None,  # No started event for config
            completed_event=WorkflowEvent.CONFIG_PHASE_COMPLETED,
            failed_event=WorkflowEvent.WORKFLOW_FAILED,
        ),
        "fast_hooks": StepEventMapping(
            step_id="fast_hooks",
            started_event=WorkflowEvent.FAST_HOOKS_STARTED,
            completed_event=WorkflowEvent.FAST_HOOKS_COMPLETED,
            failed_event=WorkflowEvent.WORKFLOW_FAILED,
        ),
        "cleaning": StepEventMapping(
            step_id="cleaning",
            started_event=WorkflowEvent.CLEANING_STARTED,
            completed_event=WorkflowEvent.CLEANING_COMPLETED,
            failed_event=WorkflowEvent.WORKFLOW_FAILED,
        ),
        "comprehensive": StepEventMapping(
            step_id="comprehensive",
            started_event=WorkflowEvent.COMPREHENSIVE_HOOKS_STARTED,
            completed_event=WorkflowEvent.COMPREHENSIVE_HOOKS_COMPLETED,
            failed_event=WorkflowEvent.WORKFLOW_FAILED,
        ),
        "test_workflow": StepEventMapping(
            step_id="test_workflow",
            started_event=WorkflowEvent.TEST_WORKFLOW_STARTED,
            completed_event=WorkflowEvent.TEST_WORKFLOW_COMPLETED,
            failed_event=WorkflowEvent.WORKFLOW_FAILED,
        ),
    }

    @depends.inject
    def __init__(
        self,
        event_bus: Inject[WorkflowEventBus],
    ) -> None:
        """Initialize event bridge with WorkflowEventBus."""
        self.event_bus = event_bus

    async def on_workflow_started(
        self,
        workflow_id: str,
        context: dict[str, Any],
    ) -> None:
        """Handle ACB workflow started event."""
        await self.event_bus.publish(
            WorkflowEvent.WORKFLOW_STARTED,
            {"workflow_id": workflow_id, "context": context},
        )

    async def on_workflow_completed(
        self,
        workflow_id: str,
        result: Any,
    ) -> None:
        """Handle ACB workflow completed event."""
        await self.event_bus.publish(
            WorkflowEvent.WORKFLOW_COMPLETED,
            {"workflow_id": workflow_id, "result": result},
        )

    async def on_workflow_failed(
        self,
        workflow_id: str,
        error: Exception,
    ) -> None:
        """Handle ACB workflow failed event."""
        await self.event_bus.publish(
            WorkflowEvent.WORKFLOW_FAILED,
            {"workflow_id": workflow_id, "error": str(error)},
        )

    async def on_step_started(
        self,
        step_id: str,
        step_name: str,
        context: dict[str, Any],
    ) -> None:
        """Translate ACB step started event to crackerjack event."""
        mapping = self.STEP_MAPPINGS.get(step_id)
        if not mapping:
            # Unknown step, emit generic quality phase started
            await self.event_bus.publish(
                WorkflowEvent.QUALITY_PHASE_STARTED,
                {"step_id": step_id, "step_name": step_name},
            )
            return

        if mapping.started_event:
            await self.event_bus.publish(
                mapping.started_event,
                {"step_id": step_id, "step_name": step_name, "context": context},
            )

    async def on_step_completed(
        self,
        step_id: str,
        step_name: str,
        result: Any,
        duration_seconds: float,
    ) -> None:
        """Translate ACB step completed event to crackerjack event."""
        mapping = self.STEP_MAPPINGS.get(step_id)
        if not mapping:
            # Unknown step, emit generic quality phase completed
            await self.event_bus.publish(
                WorkflowEvent.QUALITY_PHASE_COMPLETED,
                {
                    "step_id": step_id,
                    "step_name": step_name,
                    "duration": duration_seconds,
                },
            )
            return

        if mapping.completed_event:
            await self.event_bus.publish(
                mapping.completed_event,
                {
                    "step_id": step_id,
                    "step_name": step_name,
                    "result": result,
                    "duration": duration_seconds,
                },
            )

    async def on_step_failed(
        self,
        step_id: str,
        step_name: str,
        error: Exception,
        duration_seconds: float,
    ) -> None:
        """Translate ACB step failed event to crackerjack event."""
        mapping = self.STEP_MAPPINGS.get(step_id)
        event_type = mapping.failed_event if mapping else WorkflowEvent.WORKFLOW_FAILED

        await self.event_bus.publish(
            event_type,
            {
                "step_id": step_id,
                "step_name": step_name,
                "error": str(error),
                "duration": duration_seconds,
            },
        )
```

#### 2. CrackerjackWorkflowEngine Integration

```python
# crackerjack/workflows/engine.py

from acb.workflows import BasicWorkflowEngine, WorkflowDefinition, WorkflowResult
from acb.depends import depends, Inject

from crackerjack.workflows.event_bridge import EventBridgeAdapter


class CrackerjackWorkflowEngine(BasicWorkflowEngine):
    """ACB workflow engine with event bridge for backward compatibility.

    This engine extends BasicWorkflowEngine to emit crackerjack-specific
    events via EventBridgeAdapter while leveraging ACB's parallel execution.
    """

    @depends.inject
    def __init__(
        self,
        event_bridge: Inject[EventBridgeAdapter],
        max_concurrent_steps: int = 5,
    ) -> None:
        """Initialize workflow engine with event bridge."""
        super().__init__(max_concurrent_steps=max_concurrent_steps)
        self.event_bridge = event_bridge

    async def execute(
        self,
        workflow: WorkflowDefinition,
        context: dict[str, Any] | None = None,
    ) -> WorkflowResult:
        """Execute workflow with event bridge notifications."""
        context = context or {}

        # Emit workflow started
        await self.event_bridge.on_workflow_started(
            workflow.workflow_id,
            context,
        )

        try:
            # Execute using ACB's parallel execution logic
            result = await super().execute(workflow, context)

            # Emit workflow completed/failed
            if result.state == WorkflowState.COMPLETED:
                await self.event_bridge.on_workflow_completed(
                    workflow.workflow_id,
                    result,
                )
            else:
                error = Exception(f"Workflow failed: {result.error}")
                await self.event_bridge.on_workflow_failed(
                    workflow.workflow_id,
                    error,
                )

            return result

        except Exception as e:
            await self.event_bridge.on_workflow_failed(workflow.workflow_id, e)
            raise

    async def _execute_step_with_retry(
        self,
        step: WorkflowStep,
        context: dict[str, Any],
    ) -> StepResult:
        """Execute step with event emissions."""
        # Emit step started
        await self.event_bridge.on_step_started(
            step.step_id,
            step.name,
            context,
        )

        try:
            # Execute step using parent logic
            result = await super()._execute_step_with_retry(step, context)

            # Emit step completed/failed
            if result.state == StepState.COMPLETED:
                await self.event_bridge.on_step_completed(
                    step.step_id,
                    step.name,
                    result.output,
                    result.duration,
                )
            else:
                error = Exception(result.error or "Step failed")
                await self.event_bridge.on_step_failed(
                    step.step_id,
                    step.name,
                    error,
                    result.duration,
                )

            return result

        except Exception as e:
            # Emit step failed
            await self.event_bridge.on_step_failed(
                step.step_id,
                step.name,
                e,
                0.0,
            )
            raise
```

### Event Mapping Table

| ACB Event | Step ID | Crackerjack Event |
|-----------|---------|-------------------|
| workflow.started | - | WORKFLOW_STARTED |
| workflow.completed | - | WORKFLOW_COMPLETED |
| workflow.failed | - | WORKFLOW_FAILED |
| step.started | config | (none) |
| step.completed | config | CONFIG_PHASE_COMPLETED |
| step.started | fast_hooks | FAST_HOOKS_STARTED |
| step.completed | fast_hooks | FAST_HOOKS_COMPLETED |
| step.started | cleaning | CLEANING_STARTED |
| step.completed | cleaning | CLEANING_COMPLETED |
| step.started | comprehensive | COMPREHENSIVE_HOOKS_STARTED |
| step.completed | comprehensive | COMPREHENSIVE_HOOKS_COMPLETED |
| step.started | test_workflow | TEST_WORKFLOW_STARTED |
| step.completed | test_workflow | TEST_WORKFLOW_COMPLETED |
| step.failed | * | WORKFLOW_FAILED |

### Usage Example

```python
# CLI handler integration


@depends.inject
async def handle_standard_mode_with_acb(
    options: Options,
    console: Inject[Console],
    event_bridge: Inject[EventBridgeAdapter],
) -> None:
    """Handle standard mode using ACB workflows with event bridge."""

    # Create workflow engine with event bridge
    engine = CrackerjackWorkflowEngine(
        event_bridge=event_bridge,
        max_concurrent_steps=3,
    )

    # Select workflow
    workflow = select_workflow_for_options(options)

    # Execute (events automatically emitted via bridge)
    result = await engine.execute(workflow, context={"options": options})

    # Event consumers receive familiar events:
    # - Progress monitors show "Fast Hooks Started" panel
    # - Telemetry logs FAST_HOOKS_COMPLETED event
    # - MCP WebSocket streams workflow progress
    # All working exactly as before!

    if result.state != WorkflowState.COMPLETED:
        raise SystemExit(1)
```

## Event Payload Compatibility

### Current Event Payloads

```python
# Current WorkflowEventBus event payloads
{
    "workflow_id": str,
    "phase": str,
    "duration": float,
    "success": bool,
    "error": str | None,
}
```

### ACB Step Event Payloads

```python
# ACB BasicWorkflowEngine step events
{
    "step_id": str,
    "step_name": str,
    "output": Any,
    "duration": float,
    "state": StepState,
    "error": str | None,
}
```

### EventBridge Translation

```python
# EventBridge translates ACB → Current format
async def on_step_completed(
    self,
    step_id: str,
    step_name: str,
    result: Any,
    duration_seconds: float,
) -> None:
    await self.event_bus.publish(
        mapping.completed_event,
        {
            # Map ACB fields to current format
            "workflow_id": step_id,
            "phase": step_name,
            "duration": duration_seconds,
            "success": True,
            "error": None,
            # Include ACB fields for future migration
            "step_id": step_id,
            "step_name": step_name,
            "result": result,
        },
    )
```

## Testing Strategy

### Unit Tests

```python
@pytest.mark.asyncio
async def test_event_bridge_step_started():
    """Test EventBridge translates step.started to FAST_HOOKS_STARTED."""
    event_bus = MockWorkflowEventBus()
    bridge = EventBridgeAdapter(event_bus=event_bus)

    await bridge.on_step_started(
        step_id="fast_hooks",
        step_name="Fast Hooks",
        context={},
    )

    assert event_bus.last_event == WorkflowEvent.FAST_HOOKS_STARTED
    assert event_bus.last_payload["step_id"] == "fast_hooks"


@pytest.mark.asyncio
async def test_event_bridge_step_completed():
    """Test EventBridge translates step.completed to COMPREHENSIVE_HOOKS_COMPLETED."""
    event_bus = MockWorkflowEventBus()
    bridge = EventBridgeAdapter(event_bus=event_bus)

    await bridge.on_step_completed(
        step_id="comprehensive",
        step_name="Comprehensive Hooks",
        result={"success": True},
        duration_seconds=45.2,
    )

    assert event_bus.last_event == WorkflowEvent.COMPREHENSIVE_HOOKS_COMPLETED
    assert event_bus.last_payload["duration"] == 45.2
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_crackerjack_workflow_engine_emits_events():
    """Test CrackerjackWorkflowEngine emits crackerjack events via bridge."""
    event_bus = MockWorkflowEventBus()
    bridge = EventBridgeAdapter(event_bus=event_bus)
    engine = CrackerjackWorkflowEngine(event_bridge=bridge)

    # Define simple workflow
    workflow = WorkflowDefinition(
        workflow_id="test",
        steps=[
            WorkflowStep(step_id="fast_hooks", action="run_fast_hooks"),
        ],
    )

    # Execute workflow
    await engine.execute(workflow, context={})

    # Verify events emitted
    assert WorkflowEvent.WORKFLOW_STARTED in event_bus.emitted_events
    assert WorkflowEvent.FAST_HOOKS_STARTED in event_bus.emitted_events
    assert WorkflowEvent.FAST_HOOKS_COMPLETED in event_bus.emitted_events
    assert WorkflowEvent.WORKFLOW_COMPLETED in event_bus.emitted_events
```

## Migration Path

### Phase 1: Dual Event System

During migration, both ACB and current events are emitted:

```python
# EventBridge emits both formats
await self.event_bus.publish(
    WorkflowEvent.FAST_HOOKS_COMPLETED,
    {
        # Legacy format (for existing consumers)
        "phase": "fast_hooks",
        "duration": duration_seconds,
        "success": True,
        # ACB format (for future consumers)
        "step_id": step_id,
        "step_result": result,
    },
)
```

### Phase 2: Gradual Consumer Migration

Consumers gradually adopt ACB event format:

```python
# Old consumer (uses legacy format)
@event_bus.subscribe(WorkflowEvent.FAST_HOOKS_COMPLETED)
async def on_fast_hooks_done(payload: dict):
    duration = payload["duration"]  # Legacy field
    success = payload["success"]  # Legacy field


# New consumer (uses ACB format)
@event_bus.subscribe(WorkflowEvent.FAST_HOOKS_COMPLETED)
async def on_fast_hooks_done(payload: dict):
    step_result = payload["step_result"]  # ACB field
    duration = step_result.duration  # ACB format
```

### Phase 3: Remove EventBridge

Once all consumers migrated, remove EventBridge:

```python
# Direct ACB event usage
engine = BasicWorkflowEngine()  # No event bridge
result = await engine.execute(workflow)


# Consumers listen to ACB events directly
@acb_event_bus.subscribe("workflow.step.completed")
async def on_step_done(event: Event):
    # Pure ACB event handling
    step_result = event.payload["step_result"]
```

## Performance Considerations

**Event Overhead**: Minimal (~0.1ms per event translation)

**Memory**: `EventBridgeAdapter` is stateless (no memory overhead)

**Concurrency**: Event emissions are async and non-blocking

**Benchmarking**:

```python
# Include event overhead in Phase 1 benchmarks
baseline_time = measure_current_workflow()
acb_time = measure_acb_workflow_with_bridge()

# Expect <1% overhead from event bridge
assert (acb_time - baseline_time) / baseline_time < 0.01
```

## Success Criteria

✅ All existing event consumers continue working without changes
✅ Event payloads maintain backward compatibility
✅ EventBridge adds \<1% overhead
✅ 100% event coverage (all 15+ event types translated)
✅ Clean separation (ACB workflow logic isolated from events)

## Open Questions

1. **Should we emit both ACB and legacy events during transition?**
   → Yes, dual emission during Phase 1 for safety

1. **How do we handle custom event metadata?**
   → Include in payload under `metadata` key

1. **Should EventBridge be configurable (enable/disable)?**
   → Yes, add `enable_event_bridge` flag to CrackerjackWorkflowEngine

1. **Do we need event versioning?**
   → No, payload compatibility sufficient for now

## References

- Current EventBus: `crackerjack/events/workflow_bus.py`
- ACB Workflow Events: `/Users/les/Projects/acb/acb/workflows/engine.py` (lines 200-250)
- Progress Monitor Integration: `crackerjack/mcp/enhanced_progress_monitor.py`
