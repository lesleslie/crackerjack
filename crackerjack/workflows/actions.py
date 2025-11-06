"""ACB workflow action handlers for crackerjack.

This module provides action handler functions that wrap existing crackerjack
phase execution logic for use with ACB workflows. These handlers are registered
with the CrackerjackWorkflowEngine and called during workflow execution.

Action handlers follow ACB's async callable signature:
    async def action_name(
        context: dict[str, Any],
        step_id: str,
        **params
    ) -> Any
"""

from __future__ import annotations

import asyncio
import time
import typing as t

from acb.depends import Inject, depends

from crackerjack.core.workflow_orchestrator import WorkflowPipeline
from crackerjack.events.workflow_bus import WorkflowEvent, WorkflowEventBus
from crackerjack.models.protocols import OptionsProtocol

if t.TYPE_CHECKING:
    pass


async def run_configuration(
    context: dict[str, t.Any],
    step_id: str,
    **params: t.Any,
) -> dict[str, t.Any]:
    """Execute configuration phase.

    This action wraps the configuration phase logic, which typically
    updates dependencies and performs pre-flight checks.

    Args:
        context: Workflow execution context with "options" key
        step_id: Step identifier (unused, for ACB compatibility)
        **params: Additional step parameters

    Returns:
        dict with configuration results
    """
    options: OptionsProtocol = context.get("options")  # type: ignore[assignment]
    if not options:
        msg = "Missing 'options' in workflow context"
        raise ValueError(msg)

    # Configuration phase is typically skipped in current implementation
    # but we include it for workflow completeness
    return {
        "phase": "config",
        "success": True,
        "message": "Configuration phase skipped (no automated updates defined)",
    }


@depends.inject  # type: ignore[misc]
async def run_fast_hooks(
    context: dict[str, t.Any],
    step_id: str,
    event_bus: Inject[WorkflowEventBus] = None,
    **params: t.Any,
) -> dict[str, t.Any]:
    """Execute fast hooks phase.

    Fast hooks include:
    - Formatters (ruff, mdformat)
    - Import sorting (ruff)
    - Basic static analysis

    This action wraps the existing fast hooks execution logic from
    WorkflowPipeline passed explicitly in context.

    Args:
        context: Workflow execution context with "options" and "pipeline" keys
        step_id: Step identifier (unused, for ACB compatibility)
        event_bus: WorkflowEventBus for event emission (injected)
        **params: Additional step parameters

    Returns:
        dict with fast hooks execution results

    Raises:
        RuntimeError: If fast hooks execution fails
    """
    options: OptionsProtocol = context.get("options")  # type: ignore[assignment]
    if not options:
        msg = "Missing 'options' in workflow context"
        raise ValueError(msg)

    # Phase 4.1: Get pipeline from context instead of DI injection
    pipeline: WorkflowPipeline | None = context.get("pipeline")  # type: ignore[assignment]
    if not pipeline:
        msg = "WorkflowPipeline not available in context"
        raise RuntimeError(msg)

    # Phase 7.2: Emit start event
    start_time = time.time()
    if event_bus:
        await event_bus.publish(
            WorkflowEvent.HOOK_STRATEGY_STARTED,
            {"step_id": step_id, "strategy": "fast", "timestamp": start_time},
        )

    # Phase 4.2: DI context now preserved with Inject[] pattern (not depends())
    # Use asyncio.to_thread to avoid blocking event loop with synchronous operations
    try:
        success = await asyncio.to_thread(
            pipeline._run_fast_hooks_phase,
            options,
        )
    except Exception as exc:
        # Phase 7.2: Emit failure event
        if event_bus:
            await event_bus.publish(
                WorkflowEvent.HOOK_STRATEGY_FAILED,
                {
                    "step_id": step_id,
                    "strategy": "fast",
                    "error": str(exc),
                    "timestamp": time.time(),
                    "duration": time.time() - start_time,
                },
            )
        raise

    if not success:
        # Phase 7.2: Emit failure event
        if event_bus:
            await event_bus.publish(
                WorkflowEvent.HOOK_STRATEGY_FAILED,
                {
                    "step_id": step_id,
                    "strategy": "fast",
                    "timestamp": time.time(),
                    "duration": time.time() - start_time,
                },
            )
        msg = "Fast hooks execution failed"
        raise RuntimeError(msg)

    # Phase 7.2: Emit completion event
    if event_bus:
        await event_bus.publish(
            WorkflowEvent.HOOK_STRATEGY_COMPLETED,
            {
                "step_id": step_id,
                "strategy": "fast",
                "success": True,
                "timestamp": time.time(),
                "duration": time.time() - start_time,
            },
        )

    return {
        "phase": "fast_hooks",
        "success": True,
        "message": "Fast hooks completed successfully",
    }


@depends.inject  # type: ignore[misc]
async def run_code_cleaning(
    context: dict[str, t.Any],
    step_id: str,
    event_bus: Inject[WorkflowEventBus] = None,
    **params: t.Any,
) -> dict[str, t.Any]:
    """Execute code cleaning phase.

    Code cleaning includes:
    - Unused import removal
    - Dead code elimination
    - Code formatting fixes

    This action wraps the existing cleaning execution logic from
    WorkflowPipeline passed explicitly in context.

    Args:
        context: Workflow execution context with "options" and "pipeline" keys
        step_id: Step identifier (unused, for ACB compatibility)
        event_bus: WorkflowEventBus for event emission (injected)
        **params: Additional step parameters

    Returns:
        dict with cleaning execution results (or skip result if strip_code=False)

    Raises:
        RuntimeError: If cleaning execution fails
    """
    options: OptionsProtocol = context.get("options")  # type: ignore[assignment]
    if not options:
        msg = "Missing 'options' in workflow context"
        raise ValueError(msg)

    # Skip code cleaning unless -x/--strip-code flag is set
    if not getattr(options, "strip_code", False):
        return {
            "phase": "cleaning",
            "success": True,
            "skipped": True,
            "reason": "Code cleaning only runs with -x/--strip-code flag",
        }

    # Phase 4.1: Get pipeline from context instead of DI injection
    pipeline: WorkflowPipeline | None = context.get("pipeline")  # type: ignore[assignment]
    if not pipeline:
        msg = "WorkflowPipeline not available in context"
        raise RuntimeError(msg)

    # Phase 7.2: Emit start event
    start_time = time.time()
    if event_bus:
        await event_bus.publish(
            WorkflowEvent.QUALITY_PHASE_STARTED,
            {"step_id": step_id, "phase": "cleaning", "timestamp": start_time},
        )

    # Phase 4.2: DI context now preserved with Inject[] pattern (not depends())
    # Use asyncio.to_thread to avoid blocking event loop with synchronous operations
    try:
        success = await asyncio.to_thread(
            pipeline._run_code_cleaning_phase,
            options,
        )
    except Exception as exc:
        # Phase 7.2: Emit failure event
        if event_bus:
            await event_bus.publish(
                WorkflowEvent.WORKFLOW_FAILED,
                {
                    "step_id": step_id,
                    "phase": "cleaning",
                    "error": str(exc),
                    "timestamp": time.time(),
                    "duration": time.time() - start_time,
                },
            )
        raise

    if not success:
        # Phase 7.2: Emit failure event
        if event_bus:
            await event_bus.publish(
                WorkflowEvent.WORKFLOW_FAILED,
                {
                    "step_id": step_id,
                    "phase": "cleaning",
                    "timestamp": time.time(),
                    "duration": time.time() - start_time,
                },
            )
        msg = "Code cleaning execution failed"
        raise RuntimeError(msg)

    # Phase 7.2: Emit completion event
    if event_bus:
        await event_bus.publish(
            WorkflowEvent.QUALITY_PHASE_COMPLETED,
            {
                "step_id": step_id,
                "phase": "cleaning",
                "success": True,
                "timestamp": time.time(),
                "duration": time.time() - start_time,
            },
        )

    return {
        "phase": "cleaning",
        "success": True,
        "message": "Code cleaning completed successfully",
    }


@depends.inject  # type: ignore[misc]
async def run_comprehensive_hooks(
    context: dict[str, t.Any],
    step_id: str,
    event_bus: Inject[WorkflowEventBus] = None,
    **params: t.Any,
) -> dict[str, t.Any]:
    """Execute comprehensive hooks phase.

    Comprehensive hooks include:
    - Type checking (zuban)
    - Security scanning (bandit, gitleaks)
    - Complexity analysis (skylos)
    - Additional static analysis

    This action wraps the existing comprehensive hooks execution logic from
    WorkflowPipeline passed explicitly in context.

    Args:
        context: Workflow execution context with "options" and "pipeline" keys
        step_id: Step identifier (unused, for ACB compatibility)
        event_bus: WorkflowEventBus for event emission (injected)
        **params: Additional step parameters

    Returns:
        dict with comprehensive hooks execution results

    Raises:
        RuntimeError: If comprehensive hooks execution fails
    """
    options: OptionsProtocol = context.get("options")  # type: ignore[assignment]
    if not options:
        msg = "Missing 'options' in workflow context"
        raise ValueError(msg)

    # Phase 4.1: Get pipeline from context instead of DI injection
    pipeline: WorkflowPipeline | None = context.get("pipeline")  # type: ignore[assignment]
    if not pipeline:
        msg = "WorkflowPipeline not available in context"
        raise RuntimeError(msg)

    # Phase 7.2: Emit start event
    start_time = time.time()
    if event_bus:
        await event_bus.publish(
            WorkflowEvent.HOOK_STRATEGY_STARTED,
            {"step_id": step_id, "strategy": "comprehensive", "timestamp": start_time},
        )

    # Phase 4.2: DI context now preserved with Inject[] pattern (not depends())
    # Use asyncio.to_thread to avoid blocking event loop with synchronous operations
    try:
        success = await asyncio.to_thread(
            pipeline._run_comprehensive_hooks_phase,
            options,
        )
    except Exception as exc:
        # Phase 7.2: Emit failure event
        if event_bus:
            await event_bus.publish(
                WorkflowEvent.HOOK_STRATEGY_FAILED,
                {
                    "step_id": step_id,
                    "strategy": "comprehensive",
                    "error": str(exc),
                    "timestamp": time.time(),
                    "duration": time.time() - start_time,
                },
            )
        raise

    if not success:
        # Phase 7.2: Emit failure event
        if event_bus:
            await event_bus.publish(
                WorkflowEvent.HOOK_STRATEGY_FAILED,
                {
                    "step_id": step_id,
                    "strategy": "comprehensive",
                    "timestamp": time.time(),
                    "duration": time.time() - start_time,
                },
            )
        msg = "Comprehensive hooks execution failed"
        raise RuntimeError(msg)

    # Phase 7.2: Emit completion event
    if event_bus:
        await event_bus.publish(
            WorkflowEvent.HOOK_STRATEGY_COMPLETED,
            {
                "step_id": step_id,
                "strategy": "comprehensive",
                "success": True,
                "timestamp": time.time(),
                "duration": time.time() - start_time,
            },
        )

    return {
        "phase": "comprehensive",
        "success": True,
        "message": "Comprehensive hooks completed successfully",
    }


@depends.inject  # type: ignore[misc]
async def run_test_workflow(
    context: dict[str, t.Any],
    step_id: str,
    event_bus: Inject[WorkflowEventBus] = None,
    **params: t.Any,
) -> dict[str, t.Any]:
    """Execute test workflow.

    This action runs the test suite using pytest with configured options.

    Args:
        context: Workflow execution context with "options" and "pipeline" keys
        step_id: Step identifier (unused, for ACB compatibility)
        event_bus: WorkflowEventBus for event emission (injected)
        **params: Additional step parameters

    Returns:
        dict with test execution results

    Raises:
        RuntimeError: If test execution fails
    """
    options: OptionsProtocol = context.get("options")  # type: ignore[assignment]
    if not options:
        msg = "Missing 'options' in workflow context"
        raise ValueError(msg)

    # Phase 4.1: Get pipeline from context instead of DI injection
    pipeline: WorkflowPipeline | None = context.get("pipeline")  # type: ignore[assignment]
    if not pipeline:
        msg = "WorkflowPipeline not available in context"
        raise RuntimeError(msg)

    # Phase 7.2: Emit start event
    start_time = time.time()
    if event_bus:
        await event_bus.publish(
            WorkflowEvent.QUALITY_PHASE_STARTED,
            {"step_id": step_id, "phase": "testing", "timestamp": start_time},
        )

    # Phase 4.2: DI context now preserved with Inject[] pattern (not depends())
    # Use asyncio.to_thread to avoid blocking event loop with synchronous operations
    try:
        success = await asyncio.to_thread(
            pipeline._run_testing_phase,
            options,
        )
    except Exception as exc:
        # Phase 7.2: Emit failure event
        if event_bus:
            await event_bus.publish(
                WorkflowEvent.WORKFLOW_FAILED,
                {
                    "step_id": step_id,
                    "phase": "testing",
                    "error": str(exc),
                    "timestamp": time.time(),
                    "duration": time.time() - start_time,
                },
            )
        raise

    if not success:
        # Phase 7.2: Emit failure event
        if event_bus:
            await event_bus.publish(
                WorkflowEvent.WORKFLOW_FAILED,
                {
                    "step_id": step_id,
                    "phase": "testing",
                    "timestamp": time.time(),
                    "duration": time.time() - start_time,
                },
            )
        msg = "Test workflow execution failed"
        raise RuntimeError(msg)

    # Phase 7.2: Emit completion event
    if event_bus:
        await event_bus.publish(
            WorkflowEvent.QUALITY_PHASE_COMPLETED,
            {
                "step_id": step_id,
                "phase": "testing",
                "success": True,
                "timestamp": time.time(),
                "duration": time.time() - start_time,
            },
        )

    return {
        "phase": "test_workflow",
        "success": True,
        "message": "Test workflow completed successfully",
    }


async def run_hook(
    context: dict[str, t.Any],
    step_id: str,
    hook_name: str,
    **params: t.Any,
) -> dict[str, t.Any]:
    """Execute a single hook by name.

    This action is used for Phase 3 hook-level parallelization where
    individual hooks (zuban, bandit, gitleaks, etc.) run as separate steps.

    Args:
        context: Workflow execution context with "options" key
        step_id: Step identifier (unused, for ACB compatibility)
        hook_name: Name of the hook to execute
        **params: Additional step parameters

    Returns:
        dict with hook execution results

    Raises:
        NotImplementedError: Phase 3 feature not yet implemented
    """
    msg = "Hook-level parallelization is a Phase 3 feature (not yet implemented)"
    raise NotImplementedError(msg)


@depends.inject  # type: ignore[misc]
async def run_commit_phase(
    context: dict[str, t.Any],
    step_id: str,
    event_bus: Inject[WorkflowEventBus] = None,
    **params: t.Any,
) -> dict[str, t.Any]:
    """Execute git commit phase.

    This action commits all changes to git and optionally pushes to remote.
    Only runs if options.commit is True.

    Args:
        context: Workflow execution context with "options" and "pipeline" keys
        step_id: Step identifier (unused, for ACB compatibility)
        event_bus: WorkflowEventBus for event emission (injected)
        **params: Additional step parameters

    Returns:
        dict with commit execution results

    Raises:
        RuntimeError: If commit execution fails
    """
    options: OptionsProtocol = context.get("options")  # type: ignore[assignment]
    if not options:
        msg = "Missing 'options' in workflow context"
        raise ValueError(msg)

    # Skip commit unless --commit flag is set
    if not getattr(options, "commit", False):
        return {
            "phase": "commit",
            "success": True,
            "skipped": True,
            "reason": "Commit phase only runs with --commit flag",
        }

    # Phase 4.1: Get pipeline from context instead of DI injection
    pipeline: WorkflowPipeline | None = context.get("pipeline")  # type: ignore[assignment]
    if not pipeline:
        msg = "WorkflowPipeline not available in context"
        raise RuntimeError(msg)

    # Phase 7.2: Emit start event
    start_time = time.time()
    if event_bus:
        await event_bus.publish(
            WorkflowEvent.QUALITY_PHASE_STARTED,
            {"step_id": step_id, "phase": "commit", "timestamp": start_time},
        )

    # Phase 4.2: DI context now preserved with Inject[] pattern (not depends())
    # Use asyncio.to_thread to avoid blocking event loop with synchronous operations
    try:
        success = await asyncio.to_thread(
            pipeline.phases.run_commit_phase,
            options,
        )
    except Exception as exc:
        # Phase 7.2: Emit failure event
        if event_bus:
            await event_bus.publish(
                WorkflowEvent.WORKFLOW_FAILED,
                {
                    "step_id": step_id,
                    "phase": "commit",
                    "error": str(exc),
                    "timestamp": time.time(),
                    "duration": time.time() - start_time,
                },
            )
        raise

    if not success:
        # Phase 7.2: Emit failure event
        if event_bus:
            await event_bus.publish(
                WorkflowEvent.WORKFLOW_FAILED,
                {
                    "step_id": step_id,
                    "phase": "commit",
                    "timestamp": time.time(),
                    "duration": time.time() - start_time,
                },
            )
        msg = "Git commit execution failed"
        raise RuntimeError(msg)

    # Phase 7.2: Emit completion event
    if event_bus:
        await event_bus.publish(
            WorkflowEvent.QUALITY_PHASE_COMPLETED,
            {
                "step_id": step_id,
                "phase": "commit",
                "success": True,
                "timestamp": time.time(),
                "duration": time.time() - start_time,
            },
        )

    return {
        "phase": "commit",
        "success": True,
        "message": "Git commit completed successfully",
    }


@depends.inject  # type: ignore[misc]
async def run_publish_phase(
    context: dict[str, t.Any],
    step_id: str,
    event_bus: Inject[WorkflowEventBus] = None,
    **params: t.Any,
) -> dict[str, t.Any]:
    """Execute publishing phase (version bump and PyPI publish).

    This action bumps the version and publishes to PyPI.
    Only runs if options.publish, options.all, or options.bump is set.

    Args:
        context: Workflow execution context with "options" and "pipeline" keys
        step_id: Step identifier (unused, for ACB compatibility)
        event_bus: WorkflowEventBus for event emission (injected)
        **params: Additional step parameters

    Returns:
        dict with publish execution results

    Raises:
        RuntimeError: If publish execution fails
    """
    options: OptionsProtocol = context.get("options")  # type: ignore[assignment]
    if not options:
        msg = "Missing 'options' in workflow context"
        raise ValueError(msg)

    # Skip publish unless --publish, --all, or --bump flags are set
    if not any(
        [
            getattr(options, "publish", False),
            getattr(options, "all", False),
            getattr(options, "bump", False),
        ]
    ):
        return {
            "phase": "publish",
            "success": True,
            "skipped": True,
            "reason": "Publish phase only runs with --publish, --all, or --bump flags",
        }

    # Phase 4.1: Get pipeline from context instead of DI injection
    pipeline: WorkflowPipeline | None = context.get("pipeline")  # type: ignore[assignment]
    if not pipeline:
        msg = "WorkflowPipeline not available in context"
        raise RuntimeError(msg)

    # Phase 7.2: Emit start event
    start_time = time.time()
    if event_bus:
        await event_bus.publish(
            WorkflowEvent.QUALITY_PHASE_STARTED,
            {"step_id": step_id, "phase": "publish", "timestamp": start_time},
        )

    # Phase 4.2: DI context now preserved with Inject[] pattern (not depends())
    # Use asyncio.to_thread to avoid blocking event loop with synchronous operations
    try:
        success = await asyncio.to_thread(
            pipeline.phases.run_publishing_phase,
            options,
        )
    except Exception as exc:
        # Phase 7.2: Emit failure event
        if event_bus:
            await event_bus.publish(
                WorkflowEvent.WORKFLOW_FAILED,
                {
                    "step_id": step_id,
                    "phase": "publish",
                    "error": str(exc),
                    "timestamp": time.time(),
                    "duration": time.time() - start_time,
                },
            )
        raise

    if not success:
        # Phase 7.2: Emit failure event
        if event_bus:
            await event_bus.publish(
                WorkflowEvent.WORKFLOW_FAILED,
                {
                    "step_id": step_id,
                    "phase": "publish",
                    "timestamp": time.time(),
                    "duration": time.time() - start_time,
                },
            )
        msg = "Publishing execution failed"
        raise RuntimeError(msg)

    # Phase 7.2: Emit completion event
    if event_bus:
        await event_bus.publish(
            WorkflowEvent.QUALITY_PHASE_COMPLETED,
            {
                "step_id": step_id,
                "phase": "publish",
                "success": True,
                "timestamp": time.time(),
                "duration": time.time() - start_time,
            },
        )

    return {
        "phase": "publish",
        "success": True,
        "message": "Publishing completed successfully",
    }


# Action registry for easy registration with engine
ACTION_REGISTRY: dict[str, t.Callable[..., t.Awaitable[t.Any]]] = {
    "run_configuration": run_configuration,
    "run_fast_hooks": run_fast_hooks,
    "run_code_cleaning": run_code_cleaning,
    "run_comprehensive_hooks": run_comprehensive_hooks,
    "run_test_workflow": run_test_workflow,
    "run_commit_phase": run_commit_phase,
    "run_publish_phase": run_publish_phase,
    "run_hook": run_hook,
}


def register_actions(engine: CrackerjackWorkflowEngine) -> None:  # type: ignore[name-defined]
    """Register all action handlers with the workflow engine.

    This convenience function registers all action handlers from the
    ACTION_REGISTRY with the provided engine.

    Args:
        engine: CrackerjackWorkflowEngine instance to register actions with

    Example:
        ```python
        engine = CrackerjackWorkflowEngine()
        register_actions(engine)
        result = await engine.execute(FAST_HOOKS_WORKFLOW)
        ```
    """
    for action_name, action_func in ACTION_REGISTRY.items():
        engine.register_action(action_name, action_func)
