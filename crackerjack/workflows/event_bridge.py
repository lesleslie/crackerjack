"""EventBridge adapter for ACB workflow integration.

This module provides the EventBridgeAdapter class that translates ACB workflow
events into crackerjack-specific WorkflowEventBus events, maintaining backward
compatibility during the migration to ACB workflows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from acb.depends import Inject, depends

from crackerjack.events.workflow_bus import WorkflowEvent, WorkflowEventBus


@dataclass
class StepEventMapping:
    """Maps ACB workflow step IDs to crackerjack WorkflowEvent types.

    This mapping ensures that ACB workflow step events are translated to the
    appropriate crackerjack event types for backward compatibility.
    """

    step_id: str
    started_event: WorkflowEvent | None
    completed_event: WorkflowEvent | None
    failed_event: WorkflowEvent | None


class EventBridgeAdapter:
    """Bridges ACB workflow events to crackerjack WorkflowEventBus.

    This adapter translates generic ACB workflow step events into
    crackerjack-specific event types for backward compatibility with
    existing event consumers (progress monitors, telemetry, etc.).

    Example:
        ACB: workflow.step.started (step_id="fast_hooks")
        →
        Crackerjack: FAST_HOOKS_STARTED

    The adapter is stateless and adds minimal overhead (<1% of execution time).
    """

    # Step ID to event type mapping
    # Note: Using generic QUALITY_PHASE_STARTED/COMPLETED events since
    # WorkflowEvent enum doesn't have specific hook events
    STEP_MAPPINGS: dict[str, StepEventMapping] = {
        "config": StepEventMapping(
            step_id="config",
            started_event=WorkflowEvent.CONFIG_PHASE_STARTED,
            completed_event=WorkflowEvent.CONFIG_PHASE_COMPLETED,
            failed_event=WorkflowEvent.WORKFLOW_FAILED,
        ),
        "fast_hooks": StepEventMapping(
            step_id="fast_hooks",
            started_event=WorkflowEvent.QUALITY_PHASE_STARTED,
            completed_event=WorkflowEvent.QUALITY_PHASE_COMPLETED,
            failed_event=WorkflowEvent.WORKFLOW_FAILED,
        ),
        "cleaning": StepEventMapping(
            step_id="cleaning",
            started_event=WorkflowEvent.QUALITY_PHASE_STARTED,
            completed_event=WorkflowEvent.QUALITY_PHASE_COMPLETED,
            failed_event=WorkflowEvent.WORKFLOW_FAILED,
        ),
        "comprehensive": StepEventMapping(
            step_id="comprehensive",
            started_event=WorkflowEvent.QUALITY_PHASE_STARTED,
            completed_event=WorkflowEvent.QUALITY_PHASE_COMPLETED,
            failed_event=WorkflowEvent.WORKFLOW_FAILED,
        ),
        "test_workflow": StepEventMapping(
            step_id="test_workflow",
            started_event=WorkflowEvent.QUALITY_PHASE_STARTED,
            completed_event=WorkflowEvent.QUALITY_PHASE_COMPLETED,
            failed_event=WorkflowEvent.WORKFLOW_FAILED,
        ),
    }

    @depends.inject  # type: ignore[misc]
    def __init__(
        self,
        event_bus: Inject[WorkflowEventBus] = None,
    ) -> None:
        """Initialize event bridge with WorkflowEventBus.

        Args:
            event_bus: Crackerjack event bus for publishing translated events
        """
        self.event_bus = event_bus

    async def on_workflow_started(
        self,
        workflow_id: str,
        context: dict[str, Any],
    ) -> None:
        """Handle ACB workflow started event.

        Args:
            workflow_id: Unique identifier for the workflow
            context: Workflow execution context
        """
        await self.event_bus.publish(
            WorkflowEvent.WORKFLOW_STARTED,
            {"workflow_id": workflow_id, "context": context},
        )

    async def on_workflow_completed(
        self,
        workflow_id: str,
        result: Any,
    ) -> None:
        """Handle ACB workflow completed event.

        Args:
            workflow_id: Unique identifier for the workflow
            result: Workflow execution result
        """
        await self.event_bus.publish(
            WorkflowEvent.WORKFLOW_COMPLETED,
            {"workflow_id": workflow_id, "result": result},
        )

    async def on_workflow_failed(
        self,
        workflow_id: str,
        error: Exception,
    ) -> None:
        """Handle ACB workflow failed event.

        Args:
            workflow_id: Unique identifier for the workflow
            error: Exception that caused the failure
        """
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
        """Translate ACB step started event to crackerjack event.

        Args:
            step_id: Unique identifier for the step
            step_name: Human-readable step name
            context: Step execution context
        """
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
        """Translate ACB step completed event to crackerjack event.

        Args:
            step_id: Unique identifier for the step
            step_name: Human-readable step name
            result: Step execution result
            duration_seconds: Time taken to execute the step
        """
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
                    # Include both legacy and ACB formats for transition
                    "phase": step_name,
                    "success": True,
                },
            )

    async def on_step_failed(
        self,
        step_id: str,
        step_name: str,
        error: Exception,
        duration_seconds: float,
    ) -> None:
        """Translate ACB step failed event to crackerjack event.

        Args:
            step_id: Unique identifier for the step
            step_name: Human-readable step name
            error: Exception that caused the failure
            duration_seconds: Time taken before failure
        """
        mapping = self.STEP_MAPPINGS.get(step_id)
        event_type = mapping.failed_event if mapping else WorkflowEvent.WORKFLOW_FAILED

        await self.event_bus.publish(
            event_type,
            {
                "step_id": step_id,
                "step_name": step_name,
                "error": str(error),
                "duration": duration_seconds,
                # Include legacy format
                "phase": step_name,
                "success": False,
            },
        )
