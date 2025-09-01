"""Workflow execution engine for MCP tools.

This module handles the core workflow execution logic, including orchestrator setup,
iteration management, and result handling. Split from execution_tools.py for better
separation of concerns.
"""

import asyncio
import time
import typing as t
import uuid

from crackerjack.mcp.context import get_context

from .progress_tools import _update_progress


async def execute_crackerjack_workflow(
    args: str, kwargs: dict[str, t.Any]
) -> dict[str, t.Any]:
    """Execute the main crackerjack workflow with progress tracking."""
    job_id = str(uuid.uuid4())[:8]

    try:
        return await _execute_crackerjack_sync(job_id, args, kwargs, get_context())
    except Exception as e:
        return {
            "job_id": job_id,
            "status": "failed",
            "error": f"Execution failed: {e}",
            "timestamp": time.time(),
        }


async def _execute_crackerjack_sync(
    job_id: str,
    args: str,
    kwargs: dict[str, t.Any],
    context: t.Any,
) -> dict[str, t.Any]:
    """Execute crackerjack workflow synchronously with progress tracking."""
    # Initialize execution environment
    setup_result = await _initialize_execution(job_id, args, kwargs, context)
    if setup_result.get("status") == "failed":
        return setup_result

    # Set up orchestrator
    orchestrator_result = await _setup_orchestrator(
        job_id, args, kwargs, setup_result["working_dir"], context
    )
    if orchestrator_result.get("status") == "failed":
        return orchestrator_result

    orchestrator = orchestrator_result["orchestrator"]

    # Run workflow iterations
    return await _run_workflow_iterations(job_id, orchestrator, kwargs, context)


async def _initialize_execution(
    job_id: str,
    args: str,
    kwargs: dict[str, t.Any],
    context: t.Any,
) -> dict[str, t.Any]:
    """Initialize execution environment and validate parameters."""
    await _update_progress(
        job_id,
        {
            "type": "initialization",
            "status": "starting",
            "message": "Initializing crackerjack execution...",
        },
        context,
    )

    # Validate working directory
    working_dir = kwargs.get("working_directory", ".")
    from pathlib import Path

    working_path = Path(working_dir)
    if not working_path.exists():
        return {
            "status": "failed",
            "error": f"Working directory does not exist: {working_dir}",
            "job_id": job_id,
        }

    await _update_progress(
        job_id,
        {
            "type": "initialization",
            "status": "ready",
            "working_directory": str(working_path.absolute()),
        },
        context,
    )

    return {
        "status": "initialized",
        "working_dir": working_path.absolute(),
        "job_id": job_id,
    }


async def _setup_orchestrator(
    job_id: str,
    args: str,
    kwargs: dict[str, t.Any],
    working_dir: t.Any,
    context: t.Any,
) -> dict[str, t.Any]:
    """Set up the appropriate orchestrator based on configuration."""
    await _update_progress(
        job_id,
        {
            "type": "setup",
            "status": "creating_orchestrator",
            "message": "Setting up workflow orchestrator...",
        },
        context,
    )

    use_advanced = kwargs.get("advanced_orchestration", True)

    try:
        if use_advanced:
            orchestrator = await _create_advanced_orchestrator(
                working_dir, kwargs, context
            )
        else:
            orchestrator = _create_standard_orchestrator(working_dir, kwargs)

        return {
            "status": "ready",
            "orchestrator": orchestrator,
            "job_id": job_id,
        }

    except Exception as e:
        return {
            "status": "failed",
            "error": f"Failed to create orchestrator: {e}",
            "job_id": job_id,
        }


async def _create_advanced_orchestrator(
    working_dir: t.Any, kwargs: dict[str, t.Any], context: t.Any
) -> t.Any:
    """Create advanced async orchestrator with dependency injection."""
    from pathlib import Path

    from crackerjack.core.async_workflow_orchestrator import AsyncWorkflowOrchestrator
    from crackerjack.core.enhanced_container import EnhancedContainer

    container = EnhancedContainer()

    # Register services with the container
    await _register_core_services(container, Path(working_dir))

    orchestrator = AsyncWorkflowOrchestrator(
        pkg_path=Path(working_dir),
        container=container,
    )

    return orchestrator


def _create_standard_orchestrator(
    working_dir: t.Any, kwargs: dict[str, t.Any]
) -> t.Any:
    """Create standard synchronous orchestrator."""
    from pathlib import Path

    from crackerjack.core.workflow_orchestrator import WorkflowOrchestrator

    return WorkflowOrchestrator(pkg_path=Path(working_dir))


async def _register_core_services(container: t.Any, working_dir: t.Any) -> None:
    """Register core services with the dependency injection container."""
    from rich.console import Console

    from crackerjack.core.enhanced_container import ServiceLifetime
    from crackerjack.managers.hook_manager import AsyncHookManager
    from crackerjack.managers.publish_manager import PublishManager
    from crackerjack.managers.test_manager import TestManager
    from crackerjack.models.protocols import (
        HookManagerProtocol,
        PublishManagerProtocol,
        TestManagerProtocol,
    )
    from crackerjack.services.enhanced_filesystem import EnhancedFileSystemService

    console = Console()

    # Register managers
    container.register_service(
        HookManagerProtocol,
        AsyncHookManager(console, working_dir),
        ServiceLifetime.SINGLETON,
    )

    container.register_service(
        TestManagerProtocol,
        TestManager(console, working_dir),
        ServiceLifetime.SINGLETON,
    )

    container.register_service(
        PublishManagerProtocol,
        PublishManager(console, working_dir),
        ServiceLifetime.SINGLETON,
    )

    # Register filesystem service
    container.register_service(
        EnhancedFileSystemService,
        EnhancedFileSystemService(),
        ServiceLifetime.SINGLETON,
    )


async def _run_workflow_iterations(
    job_id: str,
    orchestrator: t.Any,
    kwargs: dict[str, t.Any],
    context: t.Any,
) -> dict[str, t.Any]:
    """Run workflow iterations until completion or max attempts."""
    options = _create_workflow_options(kwargs)
    max_iterations = kwargs.get("max_iterations", 10)

    for iteration in range(max_iterations):
        await _update_progress(
            job_id,
            {
                "type": "iteration",
                "iteration": iteration + 1,
                "max_iterations": max_iterations,
                "status": "running",
            },
            context,
        )

        try:
            success = await _execute_single_iteration(
                job_id, orchestrator, options, iteration, context
            )

            if success:
                return _create_success_result(job_id, iteration + 1, context)

            # Handle retry logic
            if iteration < max_iterations - 1:
                await _handle_iteration_retry(job_id, iteration, context)

        except Exception as e:
            return await _handle_iteration_error(job_id, iteration, e, context)

    return _create_failure_result(job_id, max_iterations, context)


def _create_workflow_options(kwargs: dict[str, t.Any]) -> t.Any:
    """Create workflow options from kwargs."""
    from types import SimpleNamespace

    # Create options object with default values
    options = SimpleNamespace()
    options.test_mode = kwargs.get("test_mode", True)
    options.ai_agent = kwargs.get("ai_agent", True)
    options.interactive = kwargs.get("interactive", False)
    options.benchmark = kwargs.get("benchmark", False)
    options.skip_hooks = kwargs.get("skip_hooks", False)
    options.verbose = kwargs.get("verbose", True)

    return options


async def _execute_single_iteration(
    job_id: str,
    orchestrator: t.Any,
    options: t.Any,
    iteration: int,
    context: t.Any,
) -> bool:
    """Execute a single workflow iteration."""
    if hasattr(orchestrator, "execute_workflow"):
        return await orchestrator.execute_workflow(options)
    # Fallback for synchronous orchestrators
    return orchestrator.run(options)


def _create_success_result(
    job_id: str, iterations: int, context: t.Any
) -> dict[str, t.Any]:
    """Create success result with completion data."""
    return {
        "job_id": job_id,
        "status": "completed",
        "iterations": iterations,
        "result": "All quality checks passed successfully",
        "timestamp": time.time(),
        "success": True,
    }


async def _handle_iteration_retry(job_id: str, iteration: int, context: t.Any) -> None:
    """Handle retry logic between iterations."""
    await _update_progress(
        job_id,
        {
            "type": "iteration",
            "iteration": iteration + 1,
            "status": "retrying",
            "message": f"Issues found in iteration {iteration + 1}, retrying...",
        },
        context,
    )

    # Brief pause between iterations
    await asyncio.sleep(1)


async def _handle_iteration_error(
    job_id: str, iteration: int, error: Exception, context: t.Any
) -> dict[str, t.Any]:
    """Handle errors during iteration execution."""
    await _update_progress(
        job_id,
        {
            "type": "error",
            "iteration": iteration + 1,
            "error": str(error),
            "status": "failed",
        },
        context,
    )

    return {
        "job_id": job_id,
        "status": "failed",
        "error": f"Iteration {iteration + 1} failed: {error}",
        "timestamp": time.time(),
        "success": False,
    }


def _create_failure_result(
    job_id: str, max_iterations: int, context: t.Any
) -> dict[str, t.Any]:
    """Create failure result when max iterations exceeded."""
    return {
        "job_id": job_id,
        "status": "failed",
        "error": f"Maximum iterations ({max_iterations}) reached without success",
        "timestamp": time.time(),
        "success": False,
    }
