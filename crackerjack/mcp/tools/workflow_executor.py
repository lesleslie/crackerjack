import asyncio
import time
import typing as t
import uuid

from crackerjack.mcp.context import get_context

from .progress_tools import _update_progress


async def execute_crackerjack_workflow(
    args: str, kwargs: dict[str, t.Any]
) -> dict[str, t.Any]:
    job_id = str(uuid.uuid4())[:8]

    # Configure extended timeout for long-running test operations
    execution_timeout = kwargs.get("execution_timeout", 900)  # 15 minutes default
    if kwargs.get("test", False) or kwargs.get("testing", False):
        execution_timeout = max(execution_timeout, 1200)  # 20 minutes for test runs

    try:
        # Add overall execution timeout with keep-alive
        return await asyncio.wait_for(
            _execute_crackerjack_sync(job_id, args, kwargs, get_context()),
            timeout=execution_timeout,
        )
    except TimeoutError:
        return {
            "job_id": job_id,
            "status": "timeout",
            "error": f"Execution timed out after {execution_timeout} seconds",
            "timestamp": time.time(),
        }
    except Exception as e:
        import traceback

        error_details = traceback.format_exc()
        return {
            "job_id": job_id,
            "status": "failed",
            "error": f"Execution failed: {e}",
            "traceback": error_details,
            "timestamp": time.time(),
        }


async def _execute_crackerjack_sync(
    job_id: str,
    args: str,
    kwargs: dict[str, t.Any],
    context: t.Any,
) -> dict[str, t.Any]:
    setup_result = await _initialize_execution(job_id, args, kwargs, context)
    if setup_result.get("status") == "failed":
        return setup_result

    orchestrator_result = await _setup_orchestrator(
        job_id, args, kwargs, setup_result["working_dir"], context
    )
    if orchestrator_result.get("status") == "failed":
        return orchestrator_result

    orchestrator = orchestrator_result["orchestrator"]

    return await _run_workflow_iterations(job_id, orchestrator, kwargs, context)


async def _initialize_execution(
    job_id: str,
    args: str,
    kwargs: dict[str, t.Any],
    context: t.Any,
) -> dict[str, t.Any]:
    _update_progress(
        job_id,
        {
            "type": "initialization",
            "status": "starting",
            "message": "Initializing crackerjack execution...",
        },
        context,
    )

    # Ensure WebSocket server is running for progress tracking
    await _ensure_websocket_server_running(job_id, context)

    working_dir = kwargs.get("working_directory", ".")
    from pathlib import Path

    working_path = Path(working_dir)
    if not working_path.exists():
        return {
            "status": "failed",
            "error": f"Working directory does not exist: {working_dir}",
            "job_id": job_id,
        }

    _update_progress(
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
    _update_progress(
        job_id,
        {
            "type": "setup",
            "status": "creating_orchestrator",
            "message": "Setting up workflow orchestrator...",
        },
        context,
    )

    use_advanced = kwargs.get("advanced_orchestration", False)

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
    from pathlib import Path

    from crackerjack.core.async_workflow_orchestrator import AsyncWorkflowOrchestrator
    from crackerjack.core.enhanced_container import EnhancedDependencyContainer

    container = EnhancedDependencyContainer()

    await _register_core_services(container, Path(working_dir))

    orchestrator = AsyncWorkflowOrchestrator(
        pkg_path=Path(working_dir),
        verbose=kwargs.get("verbose", False),
        debug=kwargs.get("debug", False),
    )

    return orchestrator


def _create_standard_orchestrator(
    working_dir: t.Any, kwargs: dict[str, t.Any]
) -> t.Any:
    from pathlib import Path

    from crackerjack.core.workflow_orchestrator import WorkflowOrchestrator

    return WorkflowOrchestrator(pkg_path=Path(working_dir))


async def _register_core_services(container: t.Any, working_dir: t.Any) -> None:
    from rich.console import Console

    from crackerjack.managers.hook_manager import AsyncHookManager
    from crackerjack.managers.publish_manager import PublishManagerImpl
    from crackerjack.managers.test_manager import TestManagementImpl
    from crackerjack.models.protocols import (
        FileSystemInterface,
        HookManager,
        PublishManager,
        TestManagerProtocol,
    )
    from crackerjack.services.enhanced_filesystem import EnhancedFileSystemService

    console = Console()

    container.register_singleton(
        HookManager,
        factory=lambda: AsyncHookManager(console, working_dir),
    )

    container.register_singleton(
        TestManagerProtocol,
        factory=lambda: TestManagementImpl(console, working_dir),
    )

    container.register_singleton(
        PublishManager,
        factory=lambda: PublishManagerImpl(console, working_dir),
    )

    container.register_singleton(
        FileSystemInterface,
        factory=EnhancedFileSystemService,
    )


async def _run_workflow_iterations(
    job_id: str,
    orchestrator: t.Any,
    kwargs: dict[str, t.Any],
    context: t.Any,
) -> dict[str, t.Any]:
    options = _create_workflow_options(kwargs)
    max_iterations = kwargs.get("max_iterations", 10)

    # Start keep-alive task to prevent TCP timeouts
    keep_alive_task = asyncio.create_task(_keep_alive_heartbeat(job_id, context))

    try:
        result = await _execute_iterations_loop(
            job_id, orchestrator, options, kwargs, max_iterations, context
        )
        return result
    finally:
        await _cleanup_keep_alive_task(keep_alive_task)


async def _execute_iterations_loop(
    job_id: str,
    orchestrator: t.Any,
    options: t.Any,
    kwargs: dict[str, t.Any],
    max_iterations: int,
    context: t.Any,
) -> dict[str, t.Any]:
    """Execute the main iterations loop."""
    for iteration in range(max_iterations):
        _update_iteration_progress(job_id, iteration, max_iterations, context)

        try:
            success = await _execute_single_iteration(
                job_id, orchestrator, options, iteration, context
            )

            if success:
                return await _handle_iteration_success(
                    job_id, iteration, orchestrator, kwargs, context
                )

            if iteration < max_iterations - 1:
                await _handle_iteration_retry(job_id, iteration, context)

        except Exception as e:
            return await _handle_iteration_error(job_id, iteration, e, context)

    return _create_failure_result(job_id, max_iterations, context)


def _update_iteration_progress(
    job_id: str, iteration: int, max_iterations: int, context: t.Any
) -> None:
    """Update progress for current iteration."""
    _update_progress(
        job_id,
        {
            "type": "iteration",
            "iteration": iteration + 1,
            "max_iterations": max_iterations,
            "status": "running",
        },
        context,
    )


async def _handle_iteration_success(
    job_id: str,
    iteration: int,
    orchestrator: t.Any,
    kwargs: dict[str, t.Any],
    context: t.Any,
) -> dict[str, t.Any]:
    """Handle successful iteration."""
    coverage_result = None
    if kwargs.get("boost_coverage", False):
        coverage_result = await _attempt_coverage_improvement(
            job_id, orchestrator, context
        )
    return _create_success_result(job_id, iteration + 1, context, coverage_result)


async def _cleanup_keep_alive_task(keep_alive_task: asyncio.Task[t.Any]) -> None:
    """Clean up the keep-alive task."""
    if not keep_alive_task.cancelled():
        keep_alive_task.cancel()
        try:
            await keep_alive_task
        except asyncio.CancelledError:
            pass


async def _keep_alive_heartbeat(job_id: str, context: t.Any) -> None:
    """Send periodic keep-alive messages to prevent TCP timeouts."""
    try:
        while True:
            # Send heartbeat every 60 seconds (well under 2-minute TCP timeout)
            await asyncio.sleep(60)
            _update_progress(
                job_id,
                {
                    "type": "keep_alive",
                    "status": "heartbeat",
                    "timestamp": time.time(),
                    "message": "Keep-alive heartbeat to prevent connection timeout",
                },
                context,
            )
    except asyncio.CancelledError:
        # Task was cancelled, cleanup
        _update_progress(
            job_id,
            {
                "type": "keep_alive",
                "status": "cancelled",
                "timestamp": time.time(),
            },
            context,
        )


def _create_workflow_options(kwargs: dict[str, t.Any]) -> t.Any:
    from types import SimpleNamespace

    options = SimpleNamespace()

    options.commit = kwargs.get("commit", False)
    options.interactive = kwargs.get("interactive", False)
    options.no_config_updates = kwargs.get("no_config_updates", False)
    options.verbose = kwargs.get("verbose", True)
    options.clean = kwargs.get("clean", False)
    options.test = kwargs.get("test_mode", True)
    options.benchmark = kwargs.get("benchmark", False)
    options.skip_hooks = kwargs.get("skip_hooks", False)
    options.ai_agent = kwargs.get("ai_agent", True)
    options.async_mode = kwargs.get("async_mode", True)

    options.test_workers = kwargs.get("test_workers", 0)
    options.test_timeout = kwargs.get("test_timeout", 0)

    options.publish = kwargs.get("publish")
    options.bump = kwargs.get("bump")
    options.all = kwargs.get("all")
    options.create_pr = kwargs.get("create_pr", False)
    options.no_git_tags = kwargs.get("no_git_tags", False)
    options.skip_version_check = kwargs.get("skip_version_check", False)
    options.cleanup_pypi = kwargs.get("cleanup_pypi", False)
    options.keep_releases = kwargs.get("keep_releases", 10)

    options.start_mcp_server = kwargs.get("start_mcp_server", False)

    options.update_precommit = kwargs.get("update_precommit", False)
    options.experimental_hooks = kwargs.get("experimental_hooks", False)
    options.enable_pyrefly = kwargs.get("enable_pyrefly", False)
    options.enable_ty = kwargs.get("enable_ty", False)

    options.cleanup = kwargs.get("cleanup")

    options.coverage = kwargs.get("coverage", False)
    options.track_progress = kwargs.get("track_progress", False)

    options.fast = kwargs.get("fast", False)
    options.comp = kwargs.get("comp", False)

    return options


async def _execute_single_iteration(
    job_id: str,
    orchestrator: t.Any,
    options: t.Any,
    iteration: int,
    context: t.Any,
) -> bool:
    try:
        if hasattr(orchestrator, "run_complete_workflow_async"):
            result = orchestrator.run_complete_workflow_async(options)
            if result is None:
                raise ValueError(
                    "Method run_complete_workflow_async returned None instead of awaitable"
                )
            return await result
        elif hasattr(orchestrator, "run_complete_workflow"):
            result = orchestrator.run_complete_workflow(options)
            if result is None:
                raise ValueError(
                    "Method run_complete_workflow returned None instead of awaitable"
                )
            return await result
        elif hasattr(orchestrator, "execute_workflow"):
            result = orchestrator.execute_workflow(options)
            if result is None:
                raise ValueError(
                    "Method execute_workflow returned None instead of awaitable"
                )
            return await result
        elif hasattr(orchestrator, "run"):
            return orchestrator.run(options)
        else:
            raise ValueError(
                f"Orchestrator {type(orchestrator)} has no recognized workflow execution method"
            )
    except Exception as e:
        raise RuntimeError(
            f"Error in _execute_single_iteration (iteration {iteration}): {e}"
        ) from e


def _create_success_result(
    job_id: str,
    iterations: int,
    context: t.Any,
    coverage_result: dict[str, t.Any] | None = None,
) -> dict[str, t.Any]:
    result = {
        "job_id": job_id,
        "status": "completed",
        "iterations": iterations,
        "result": "All quality checks passed successfully",
        "timestamp": time.time(),
        "success": True,
    }

    if coverage_result:
        result["coverage_improvement"] = coverage_result

    return result


async def _handle_iteration_retry(job_id: str, iteration: int, context: t.Any) -> None:
    _update_progress(
        job_id,
        {
            "type": "iteration",
            "iteration": iteration + 1,
            "status": "retrying",
            "message": f"Issues found in iteration {iteration + 1}, retrying...",
        },
        context,
    )

    await asyncio.sleep(1)


async def _handle_iteration_error(
    job_id: str, iteration: int, error: Exception, context: t.Any
) -> dict[str, t.Any]:
    _update_progress(
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


async def _attempt_coverage_improvement(
    job_id: str, orchestrator: t.Any, context: t.Any
) -> dict[str, t.Any]:
    try:
        _update_progress(
            job_id,
            {
                "type": "coverage_improvement",
                "status": "starting",
                "message": "Analyzing coverage for improvement opportunities...",
            },
            context,
        )

        project_path = getattr(orchestrator, "pkg_path", None)
        if not project_path:
            return {"status": "skipped", "reason": "No project path available"}

        from crackerjack.orchestration.coverage_improvement import (
            create_coverage_improvement_orchestrator,
        )

        coverage_orchestrator = await create_coverage_improvement_orchestrator(
            project_path,
            console=getattr(orchestrator, "console", None),
        )

        should_improve = await coverage_orchestrator.should_improve_coverage()
        if not should_improve:
            _update_progress(
                job_id,
                {
                    "type": "coverage_improvement",
                    "status": "skipped",
                    "message": "Coverage improvement not needed (already at 100 %)",
                },
                context,
            )
            return {"status": "skipped", "reason": "Coverage at 100 %"}

        from crackerjack.agents.base import AgentContext

        agent_context = AgentContext(project_path=project_path, console=None)

        _update_progress(
            job_id,
            {
                "type": "coverage_improvement",
                "status": "executing",
                "message": "Generating tests to improve coverage...",
            },
            context,
        )

        improvement_result = await coverage_orchestrator.execute_coverage_improvement(
            agent_context
        )

        if improvement_result["status"] == "completed":
            _update_progress(
                job_id,
                {
                    "type": "coverage_improvement",
                    "status": "completed",
                    "message": f"Coverage improvement: {len(improvement_result.get('fixes_applied', []))} tests created",
                    "fixes_applied": improvement_result.get("fixes_applied", []),
                    "files_modified": improvement_result.get("files_modified", []),
                },
                context,
            )
        else:
            _update_progress(
                job_id,
                {
                    "type": "coverage_improvement",
                    "status": "completed_with_issues",
                    "message": f"Coverage improvement attempted: {improvement_result.get('status', 'unknown')}",
                },
                context,
            )

        return improvement_result

    except Exception as e:
        _update_progress(
            job_id,
            {
                "type": "coverage_improvement",
                "status": "failed",
                "error": str(e),
                "message": f"Coverage improvement failed: {e}",
            },
            context,
        )

        return {
            "status": "failed",
            "error": str(e),
            "fixes_applied": [],
            "files_modified": [],
        }


def _create_failure_result(
    job_id: str, max_iterations: int, context: t.Any
) -> dict[str, t.Any]:
    return {
        "job_id": job_id,
        "status": "failed",
        "error": f"Maximum iterations ({max_iterations}) reached without success",
        "timestamp": time.time(),
        "success": False,
    }


async def _ensure_websocket_server_running(job_id: str, context: t.Any) -> None:
    """Ensure WebSocket server is running for progress tracking during crackerjack:run."""
    try:
        from crackerjack.mcp.progress_components import ServiceManager

        # Initialize and start services if needed
        service_manager = ServiceManager()
        await service_manager.ensure_services_running()

        _update_progress(
            job_id,
            {
                "type": "service_check",
                "status": "websocket_ready",
                "message": "WebSocket server ensured running for progress tracking",
            },
            context,
        )
    except Exception as e:
        # Don't fail the whole workflow if WebSocket server fails to start
        _update_progress(
            job_id,
            {
                "type": "service_check",
                "status": "websocket_warning",
                "message": f"WebSocket server auto-start failed: {e}. Progress tracking may be limited.",
            },
            context,
        )
