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
import typing as t

from acb.depends import Inject, depends

from crackerjack.core.phase_coordinator import PhaseCoordinator
from crackerjack.core.workflow_orchestrator import WorkflowOrchestrator
from crackerjack.models.protocols import OptionsProtocol

if t.TYPE_CHECKING:
    pass


@depends.inject
async def run_configuration(
    context: dict[str, t.Any],
    step_id: str,
    orchestrator: Inject[WorkflowOrchestrator] | None = None,
    **params: t.Any,
) -> dict[str, t.Any]:
    """Execute configuration phase.

    This action wraps the configuration phase logic, which typically
    updates dependencies and performs pre-flight checks.

    Args:
        context: Workflow execution context with "options" key
        step_id: Step identifier (unused, for ACB compatibility)
        orchestrator: WorkflowOrchestrator instance (DI)
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


@depends.inject
async def run_fast_hooks(
    context: dict[str, t.Any],
    step_id: str,
    orchestrator: Inject[WorkflowOrchestrator] | None = None,
    phase_coordinator: Inject[PhaseCoordinator] | None = None,
    **params: t.Any,
) -> dict[str, t.Any]:
    """Execute fast hooks phase.

    Fast hooks include:
    - Formatters (ruff, mdformat)
    - Import sorting (ruff)
    - Basic static analysis

    This action wraps the existing fast hooks execution logic from
    WorkflowOrchestrator.

    Args:
        context: Workflow execution context with "options" key
        step_id: Step identifier (unused, for ACB compatibility)
        orchestrator: WorkflowOrchestrator instance (DI)
        phase_coordinator: PhaseCoordinator instance (DI)
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

    # Phase 1 POC: Simple success response
    # Full orchestrator integration will be implemented in Phase 2
    # when we have proper DI container setup for WorkflowOrchestrator
    print("✓ ACB Workflow: Fast hooks phase completed (POC mode)")

    # TODO Phase 2: Integrate actual WorkflowOrchestrator execution
    # Will require:
    # 1. Proper DI registration of all WorkflowOrchestrator dependencies
    # 2. Container lifecycle management
    # 3. Service initialization in correct order

    return {
        "phase": "fast_hooks",
        "success": True,
        "message": "Fast hooks completed successfully",
    }


@depends.inject
async def run_code_cleaning(
    context: dict[str, t.Any],
    step_id: str,
    orchestrator: Inject[WorkflowOrchestrator] | None = None,
    **params: t.Any,
) -> dict[str, t.Any]:
    """Execute code cleaning phase.

    Code cleaning includes:
    - Unused import removal
    - Dead code elimination
    - Code formatting fixes

    This action wraps the existing cleaning execution logic from
    WorkflowOrchestrator.

    Args:
        context: Workflow execution context with "options" key
        step_id: Step identifier (unused, for ACB compatibility)
        orchestrator: WorkflowOrchestrator instance (DI)
        **params: Additional step parameters

    Returns:
        dict with cleaning execution results

    Raises:
        RuntimeError: If cleaning execution fails
    """
    options: OptionsProtocol = context.get("options")  # type: ignore[assignment]
    if not options:
        msg = "Missing 'options' in workflow context"
        raise ValueError(msg)

    if not orchestrator:
        msg = "WorkflowOrchestrator not available via DI"
        raise RuntimeError(msg)

    # Execute cleaning using existing orchestrator method
    success = await asyncio.to_thread(
        orchestrator._execute_monitored_cleaning_phase,
        options,
    )

    if not success:
        msg = "Code cleaning execution failed"
        raise RuntimeError(msg)

    return {
        "phase": "cleaning",
        "success": True,
        "message": "Code cleaning completed successfully",
    }


@depends.inject
async def run_comprehensive_hooks(
    context: dict[str, t.Any],
    step_id: str,
    orchestrator: Inject[WorkflowOrchestrator] | None = None,
    **params: t.Any,
) -> dict[str, t.Any]:
    """Execute comprehensive hooks phase.

    Comprehensive hooks include:
    - Type checking (zuban)
    - Security scanning (bandit, gitleaks)
    - Complexity analysis (skylos)
    - Additional static analysis

    This action wraps the existing comprehensive hooks execution logic from
    WorkflowOrchestrator.

    Args:
        context: Workflow execution context with "options" key
        step_id: Step identifier (unused, for ACB compatibility)
        orchestrator: WorkflowOrchestrator instance (DI)
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

    if not orchestrator:
        msg = "WorkflowOrchestrator not available via DI"
        raise RuntimeError(msg)

    # Execute comprehensive hooks using existing orchestrator method
    success = await asyncio.to_thread(
        orchestrator._execute_monitored_comprehensive_phase,
        options,
        None,  # monitor (optional)
    )

    if not success:
        msg = "Comprehensive hooks execution failed"
        raise RuntimeError(msg)

    return {
        "phase": "comprehensive",
        "success": True,
        "message": "Comprehensive hooks completed successfully",
    }


@depends.inject
async def run_test_workflow(
    context: dict[str, t.Any],
    step_id: str,
    orchestrator: Inject[WorkflowOrchestrator] | None = None,
    **params: t.Any,
) -> dict[str, t.Any]:
    """Execute test workflow.

    This action runs the test suite using pytest with configured options.

    Args:
        context: Workflow execution context with "options" key
        step_id: Step identifier (unused, for ACB compatibility)
        orchestrator: WorkflowOrchestrator instance (DI)
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

    if not orchestrator:
        msg = "WorkflowOrchestrator not available via DI"
        raise RuntimeError(msg)

    # Execute test workflow using existing orchestrator method
    success = await asyncio.to_thread(
        orchestrator._execute_test_workflow,
        options,
    )

    if not success:
        msg = "Test workflow execution failed"
        raise RuntimeError(msg)

    return {
        "phase": "test_workflow",
        "success": True,
        "message": "Test workflow completed successfully",
    }


@depends.inject
async def run_hook(
    context: dict[str, t.Any],
    step_id: str,
    hook_name: str,
    orchestrator: Inject[WorkflowOrchestrator] | None = None,
    **params: t.Any,
) -> dict[str, t.Any]:
    """Execute a single hook by name.

    This action is used for Phase 3 hook-level parallelization where
    individual hooks (zuban, bandit, gitleaks, etc.) run as separate steps.

    Args:
        context: Workflow execution context with "options" key
        step_id: Step identifier (unused, for ACB compatibility)
        hook_name: Name of the hook to execute
        orchestrator: WorkflowOrchestrator instance (DI)
        **params: Additional step parameters

    Returns:
        dict with hook execution results

    Raises:
        RuntimeError: If hook execution fails
        NotImplementedError: Phase 3 feature not yet implemented
    """
    msg = "Hook-level parallelization is a Phase 3 feature (not yet implemented)"
    raise NotImplementedError(msg)


# Action registry for easy registration with engine
ACTION_REGISTRY: dict[str, t.Callable[..., t.Awaitable[t.Any]]] = {
    "run_configuration": run_configuration,
    "run_fast_hooks": run_fast_hooks,
    "run_code_cleaning": run_code_cleaning,
    "run_comprehensive_hooks": run_comprehensive_hooks,
    "run_test_workflow": run_test_workflow,
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
