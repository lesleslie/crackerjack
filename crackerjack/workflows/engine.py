"""ACB workflow engine integration for crackerjack.

This module provides the CrackerjackWorkflowEngine class that extends
ACB's BasicWorkflowEngine with event bridge support for backward compatibility.
"""

from __future__ import annotations

import typing as t

from acb.depends import Inject, depends
from acb.workflows import (
    BasicWorkflowEngine,
    StepResult,
    StepState,
    WorkflowDefinition,
    WorkflowResult,
    WorkflowState,
    WorkflowStep,
)

from crackerjack.workflows.event_bridge import EventBridgeAdapter


class CrackerjackWorkflowEngine(BasicWorkflowEngine):
    """ACB workflow engine with event bridge for backward compatibility.

    This engine extends BasicWorkflowEngine to emit crackerjack-specific
    events via EventBridgeAdapter while leveraging ACB's parallel execution
    capabilities.

    Key Features:
        - Automatic parallel step execution (dependency-based)
        - Event bridge for backward compatibility
        - Built-in retry logic with exponential backoff
        - State management and timing
        - DI-based action handlers

    Example:
        ```python
        @depends.inject
        async def handle_workflow(
            engine: Inject[CrackerjackWorkflowEngine],
            options: Options,
        ) -> None:
            workflow = FAST_HOOKS_WORKFLOW
            result = await engine.execute(workflow, context={"options": options})
            if result.state != WorkflowState.COMPLETED:
                raise SystemExit(1)
        ```
    """

    @depends.inject  # type: ignore[misc]
    def __init__(
        self,
        event_bridge: Inject[EventBridgeAdapter] = None,
        max_concurrent_steps: int = 5,
    ) -> None:
        """Initialize workflow engine with event bridge.

        Args:
            event_bridge: EventBridge adapter for event translation
            max_concurrent_steps: Maximum number of steps to run in parallel

        Note:
            Logger is automatically initialized by BasicWorkflowEngine parent class
        """
        super().__init__(max_concurrent_steps=max_concurrent_steps)
        self.event_bridge = event_bridge

    async def execute(
        self,
        workflow: WorkflowDefinition,
        context: dict[str, t.Any] | None = None,
    ) -> WorkflowResult:
        """Execute workflow with event bridge notifications.

        This method wraps ACB's execute() to emit crackerjack-specific events
        for backward compatibility with existing event consumers.

        Args:
            workflow: Workflow definition to execute
            context: Optional execution context

        Returns:
            WorkflowResult with state, steps, timing, and errors
        """
        context = context or {}

        # Emit workflow started event
        await self.event_bridge.on_workflow_started(
            workflow.workflow_id,
            context,
        )

        try:
            # Execute using ACB's parallel execution logic
            result = await super().execute(workflow, context)

            # Emit workflow completed/failed event
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
            # Emit workflow failed event
            await self.event_bridge.on_workflow_failed(workflow.workflow_id, e)
            raise

    async def _execute_step_with_retry(
        self,
        step: WorkflowStep,
        context: dict[str, t.Any],
    ) -> StepResult:
        """Execute step with event emissions.

        This method wraps ACB's _execute_step_with_retry() to emit
        crackerjack-specific step events.

        Args:
            step: Workflow step to execute
            context: Execution context

        Returns:
            StepResult with state, output, timing, and errors
        """
        # Emit step started event
        await self.event_bridge.on_step_started(
            step.step_id,
            step.name,
            context,
        )

        try:
            # Execute step using parent logic (includes retry)
            result = await super()._execute_step_with_retry(step, context)

            # Emit step completed/failed event
            if result.state == StepState.COMPLETED:
                await self.event_bridge.on_step_completed(
                    step.step_id,
                    step.name,
                    result.output,
                    (result.duration_ms or 0)
                    / 1000.0,  # Convert milliseconds to seconds
                )
            else:
                error = Exception(result.error or "Step failed")
                await self.event_bridge.on_step_failed(
                    step.step_id,
                    step.name,
                    error,
                    (result.duration_ms or 0)
                    / 1000.0,  # Convert milliseconds to seconds
                )

            return result

        except Exception as e:
            # Emit step failed event
            await self.event_bridge.on_step_failed(
                step.step_id,
                step.name,
                e,
                0.0,
            )
            raise
