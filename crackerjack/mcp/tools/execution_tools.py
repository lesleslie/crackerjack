import asyncio
import json
import time
import typing as t
import uuid
from contextlib import suppress

from crackerjack.mcp.context import get_context

from .progress_tools import _update_progress


def register_execution_tools(mcp_app: t.Any) -> None:
    _register_execute_crackerjack_tool(mcp_app)
    _register_smart_error_analysis_tool(mcp_app)
    _register_init_crackerjack_tool(mcp_app)


def _register_execute_crackerjack_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def execute_crackerjack(args: str, kwargs: str) -> str:
        context = get_context()
        validation_error = await _validate_context_and_rate_limit(context)
        if validation_error:
            return validation_error

        job_id = str(uuid.uuid4())[:8]

        kwargs_result = _parse_kwargs(kwargs)
        if "error" in kwargs_result:
            return json.dumps(kwargs_result)

        extra_kwargs = kwargs_result["kwargs"]

        # Run the workflow directly instead of in background
        try:
            result = await _execute_crackerjack_sync(
                job_id,
                args,
                extra_kwargs,
                context,
            )
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {
                    "job_id": job_id,
                    "status": "failed",
                    "error": f"Execution failed: {e}",
                },
                indent=2,
            )


def _register_smart_error_analysis_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def smart_error_analysis(use_cache: bool = True) -> str:
        context = get_context()
        if not context:
            return '{"error": "Server context not available"}'

        try:
            from crackerjack.services.debug import get_ai_agent_debugger

            get_ai_agent_debugger()

            cached_patterns = _get_cached_patterns(context, use_cache)
            analysis = _build_error_analysis(use_cache, cached_patterns)

            return json.dumps(analysis, indent=2)

        except Exception as e:
            return f'{{"error": "Smart error analysis failed: {e}"}}'


async def _validate_context_and_rate_limit(context: t.Any) -> str | None:
    if not context:
        return '{"error": "Server context not available"}'

    # Rate limiting is optional - skip if not configured
    if context.rate_limiter:
        allowed, details = await context.rate_limiter.check_request_allowed("default")
        if not allowed:
            return f'{{"error": "Rate limit exceeded: {details.get("reason", "unknown")}", "success": false}}'

    return None


def _handle_task_exception(job_id: str, task: asyncio.Task) -> None:
    """Handle exceptions from background tasks."""
    import tempfile
    from pathlib import Path

    try:
        exception = task.exception()
        if exception:
            # Log the exception to a debug file
            debug_file = (
                Path(tempfile.gettempdir()) / f"crackerjack-task-error-{job_id}.log"
            )
            with debug_file.open("w") as f:
                f.write(
                    f"Background task {job_id} failed with exception: {exception}\n",
                )
                f.write(f"Exception type: {type(exception)}\n")
                import traceback

                f.write(
                    f"Traceback:\n{traceback.format_exception(type(exception), exception, exception.__traceback__)}\n",
                )
    except Exception as e:
        # If we can't even log the error, at least try to create a simple file
        with suppress(Exception):
            debug_file = (
                Path(tempfile.gettempdir()) / f"crackerjack-logging-error-{job_id}.log"
            )
            with debug_file.open("w") as f:
                f.write(f"Failed to log task exception: {e}\n")


def _parse_kwargs(kwargs: str) -> dict[str, t.Any]:
    try:
        return {"kwargs": json.loads(kwargs) if kwargs.strip() else {}}
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in kwargs: {e}"}


def _get_cached_patterns(context: t.Any, use_cache: bool) -> list[t.Any]:
    if use_cache and hasattr(context, "error_cache"):
        return getattr(context.error_cache, "patterns", [])
    return []


def _build_error_analysis(
    use_cache: bool,
    cached_patterns: list[t.Any],
) -> dict[str, t.Any]:
    analysis = {
        "analysis_type": "smart_error_analysis",
        "use_cache": use_cache,
        "cached_patterns_count": len(cached_patterns),
        "common_patterns": [
            {
                "type": "import_error",
                "frequency": "high",
                "typical_fix": "Check import paths and dependencies",
            },
            {
                "type": "type_annotation_missing",
                "frequency": "medium",
                "typical_fix": "Add proper type hints to functions and methods",
            },
            {
                "type": "test_failure",
                "frequency": "medium",
                "typical_fix": "Review test expectations and implementation",
            },
        ],
        "recommendations": [
            "Run fast hooks first to fix formatting issues",
            "Execute tests to identify functional problems",
            "Run comprehensive hooks for quality analysis",
        ],
    }

    if cached_patterns:
        analysis["cached_patterns"] = cached_patterns[:5]

    return analysis


async def _execute_crackerjack_sync(
    job_id: str,
    args: str,
    kwargs: dict[str, t.Any],
    context: t.Any,
) -> dict[str, t.Any]:
    if not context:
        return {"job_id": job_id, "status": "failed", "error": "No context available"}

    max_iterations = kwargs.get("max_iterations", 10)
    current_iteration = 1

    try:
        await _initialize_execution(job_id, max_iterations, current_iteration, context)

        orchestrator, use_advanced_orchestrator = await _setup_orchestrator(
            job_id,
            max_iterations,
            current_iteration,
            kwargs,
            context,
        )

        return await _run_workflow_iterations(
            job_id,
            max_iterations,
            orchestrator,
            use_advanced_orchestrator,
            kwargs,
        )

    except Exception as e:
        _update_progress(
            job_id=job_id,
            status="failed",
            iteration=current_iteration,
            max_iterations=max_iterations,
            overall_progress=0,
            current_stage="error",
            message=f"Execution failed: {e}",
        )
        context.safe_print(f"Execution failed: {e}")
        return {"job_id": job_id, "status": "failed", "error": str(e)}


async def _initialize_execution(
    job_id: str,
    max_iterations: int,
    current_iteration: int,
    context: t.Any,
) -> None:
    """Initialize execution with status checks and service preparation."""
    _update_progress(
        job_id=job_id,
        status="running",
        iteration=current_iteration,
        max_iterations=max_iterations,
        overall_progress=2,
        current_stage="initialization",
        message="Initializing crackerjack execution",
    )

    # Check comprehensive status first to prevent conflicts and perform cleanup
    status_result = await _check_status_and_prepare(job_id, context)
    if status_result.get("should_abort", False):
        msg = f"Execution aborted: {status_result['reason']}"
        raise RuntimeError(msg)

    _update_progress(
        job_id=job_id,
        status="running",
        iteration=current_iteration,
        max_iterations=max_iterations,
        overall_progress=5,
        current_stage="status_verified",
        message="Status check complete - no conflicts detected",
    )

    # Clean up stale jobs first
    await _cleanup_stale_jobs(context)

    # Auto-start required services
    await _ensure_services_running(job_id, context)

    _update_progress(
        job_id=job_id,
        status="running",
        iteration=current_iteration,
        max_iterations=max_iterations,
        overall_progress=10,
        current_stage="services_ready",
        message="Services initialized successfully",
    )


async def _setup_orchestrator(
    job_id: str,
    max_iterations: int,
    current_iteration: int,
    kwargs: dict[str, t.Any],
    context: t.Any,
) -> tuple[t.Any, bool]:
    """Set up the appropriate orchestrator (force standard for MCP compatibility)."""
    # Force standard orchestrator for MCP server to ensure proper progress reporting
    context.safe_print("Using Standard WorkflowOrchestrator for MCP compatibility")
    orchestrator = _create_standard_orchestrator(job_id, kwargs, context)
    use_advanced_orchestrator = False

    # Update progress to show orchestrator mode
    orchestrator_type = "Standard Orchestrator (MCP Compatible)"
    _update_progress(
        job_id=job_id,
        status="running",
        iteration=current_iteration,
        max_iterations=max_iterations,
        overall_progress=15,
        current_stage="orchestrator_ready",
        message=f"Initialized {orchestrator_type}",
    )

    return orchestrator, use_advanced_orchestrator


async def _create_advanced_orchestrator(
    job_id: str,
    kwargs: dict[str, t.Any],
    context: t.Any,
) -> t.Any:
    """Create and configure the advanced orchestrator."""
    from crackerjack.core.session_coordinator import SessionCoordinator
    from crackerjack.orchestration.advanced_orchestrator import (
        AdvancedWorkflowOrchestrator,
    )
    from crackerjack.orchestration.execution_strategies import (
        AICoordinationMode,
        AIIntelligence,
        ExecutionStrategy,
        OrchestrationConfig,
        ProgressLevel,
        StreamingMode,
    )

    # Create optimal orchestration configuration for maximum efficiency
    optimal_config = OrchestrationConfig(
        execution_strategy=ExecutionStrategy.ADAPTIVE,
        progress_level=ProgressLevel.DETAILED,
        streaming_mode=StreamingMode.WEBSOCKET,
        ai_coordination_mode=AICoordinationMode.COORDINATOR,
        ai_intelligence=AIIntelligence.ADAPTIVE,
        # Enable advanced features
        correlation_tracking=True,
        failure_analysis=True,
        intelligent_retry=True,
        # Maximize parallelism for hook and test fixing
        max_parallel_hooks=3,
        max_parallel_tests=4,
        timeout_multiplier=1.0,
        # Enhanced debugging and monitoring
        debug_level="standard",
        log_individual_outputs=False,
        preserve_temp_files=False,
    )

    # Initialize advanced orchestrator with optimal config
    session = SessionCoordinator(
        context.console,
        context.config.project_path,
        web_job_id=job_id,
    )
    orchestrator = AdvancedWorkflowOrchestrator(
        console=context.console,
        pkg_path=context.config.project_path,
        session=session,
        config=optimal_config,
    )

    # Override MCP mode if debug flag is set
    if kwargs.get("debug", False):
        orchestrator.individual_executor.set_mcp_mode(False)
        context.safe_print("🐛 Debug mode enabled - full output mode")

    return orchestrator


def _create_standard_orchestrator(
    job_id: str,
    kwargs: dict[str, t.Any],
    context: t.Any,
) -> t.Any:
    """Create the standard fallback orchestrator."""
    from crackerjack.core.workflow_orchestrator import WorkflowOrchestrator

    return WorkflowOrchestrator(
        console=context.console,
        pkg_path=context.config.project_path,
        dry_run=kwargs.get("dry_run", False),
        web_job_id=job_id,
    )


async def _run_workflow_iterations(
    job_id: str,
    max_iterations: int,
    orchestrator: t.Any,
    use_advanced_orchestrator: bool,
    kwargs: dict[str, t.Any],
) -> dict[str, t.Any]:
    """Run the main workflow iteration loop."""
    success = False
    current_iteration = 1

    for iteration in range(1, max_iterations + 1):
        current_iteration = iteration

        _update_progress(
            job_id=job_id,
            status="running",
            iteration=current_iteration,
            max_iterations=max_iterations,
            overall_progress=int((iteration / max_iterations) * 80),
            current_stage=f"iteration_{iteration}",
            message=f"Running iteration {iteration} / {max_iterations}",
        )

        options = _create_workflow_options(kwargs)

        try:
            success = await _execute_single_iteration(
                orchestrator,
                use_advanced_orchestrator,
                options,
            )

            if success:
                return _create_success_result(
                    job_id,
                    current_iteration,
                    max_iterations,
                    iteration,
                )

            if iteration < max_iterations:
                await _handle_iteration_retry(
                    job_id,
                    current_iteration,
                    max_iterations,
                    iteration,
                )
                continue

        except Exception as e:
            if not await _handle_iteration_error(iteration, max_iterations, e):
                break

    return _create_failure_result(job_id, current_iteration, max_iterations)


def _create_workflow_options(kwargs: dict[str, t.Any]) -> t.Any:
    """Create WorkflowOptions from kwargs."""
    from crackerjack.models.config import WorkflowOptions

    options = WorkflowOptions()
    options.testing.test = kwargs.get("test", True)
    options.ai_agent = kwargs.get("ai_agent", True)
    options.skip_hooks = kwargs.get("skip_hooks", False)
    return options


async def _execute_single_iteration(
    orchestrator: t.Any,
    use_advanced_orchestrator: bool,
    options: t.Any,
) -> bool:
    """Execute a single workflow iteration."""
    if use_advanced_orchestrator:
        return await orchestrator.execute_orchestrated_workflow(options)
    return await orchestrator.run_complete_workflow(options)


def _create_success_result(
    job_id: str,
    current_iteration: int,
    max_iterations: int,
    iteration: int,
) -> dict[str, t.Any]:
    """Create success result dictionary."""
    _update_progress(
        job_id=job_id,
        status="completed",
        iteration=current_iteration,
        max_iterations=max_iterations,
        overall_progress=100,
        current_stage="completed",
        message=f"Successfully completed after {iteration} iterations",
    )
    return {
        "job_id": job_id,
        "status": "completed",
        "iteration": current_iteration,
        "message": f"Successfully completed after {iteration} iterations",
    }


async def _handle_iteration_retry(
    job_id: str,
    current_iteration: int,
    max_iterations: int,
    iteration: int,
) -> None:
    """Handle iteration retry logic."""
    _update_progress(
        job_id=job_id,
        status="running",
        iteration=current_iteration,
        max_iterations=max_iterations,
        overall_progress=int((iteration / max_iterations) * 80),
        current_stage="retrying",
        message=f"Iteration {iteration} failed, retrying...",
    )
    await asyncio.sleep(1)


async def _handle_iteration_error(
    iteration: int,
    max_iterations: int,
    error: Exception,
) -> bool:
    """Handle iteration errors. Returns True to continue, False to break."""
    if iteration >= max_iterations:
        return False
    await asyncio.sleep(1)
    return True


def _create_failure_result(
    job_id: str,
    current_iteration: int,
    max_iterations: int,
) -> dict[str, t.Any]:
    """Create failure result dictionary."""
    _update_progress(
        job_id=job_id,
        status="failed",
        iteration=current_iteration,
        max_iterations=max_iterations,
        overall_progress=80,
        current_stage="failed",
        message=f"Failed after {max_iterations} iterations",
    )
    return {
        "job_id": job_id,
        "status": "failed",
        "iteration": current_iteration,
        "message": f"Failed after {max_iterations} iterations",
    }


async def _ensure_services_running(job_id: str, context: t.Any) -> None:
    """Ensure WebSocket server and watchdog are running before starting workflow."""
    import subprocess

    _update_progress(
        job_id=job_id,
        status="running",
        current_stage="service_startup",
        message="Checking required services...",
    )

    # Check if WebSocket server is running
    websocket_running = False
    with suppress(Exception):
        from crackerjack.services.server_manager import find_websocket_server_processes

        websocket_processes = find_websocket_server_processes()
        websocket_running = len(websocket_processes) > 0

    if not websocket_running:
        _update_progress(
            job_id=job_id,
            status="running",
            current_stage="service_startup",
            message="Starting WebSocket server...",
        )

        try:
            # Start WebSocket server in background
            subprocess.Popen(
                ["python", "-m", "crackerjack", "--start-websocket-server"],
                cwd=context.config.project_path,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

            # Wait for server to start
            for _i in range(10):
                with suppress(Exception):
                    websocket_processes = find_websocket_server_processes()
                    if websocket_processes:
                        context.safe_print("✅ WebSocket server started successfully")
                        break
                await asyncio.sleep(0.5)
            else:
                context.safe_print("⚠️ WebSocket server may not have started properly")

        except Exception as e:
            context.safe_print(f"⚠️ Failed to start WebSocket server: {e}")
    else:
        context.safe_print("✅ WebSocket server already running")


async def _check_status_and_prepare(job_id: str, context: t.Any) -> dict[str, t.Any]:
    """Check comprehensive system status and prepare for execution."""
    _update_progress(
        job_id=job_id,
        status="running",
        current_stage="status_check",
        message="🔍 Checking system status to prevent conflicts...",
    )

    try:
        status_info = await _get_status_info()
        if "error" in status_info:
            return _handle_status_error(status_info, context)

        cleanup_performed = []

        # Check for conflicting jobs
        _check_active_jobs(status_info, context)

        # Check and flag resource cleanup needs
        cleanup_performed.extend(_check_resource_cleanup(status_info, context))

        # Check service health
        _check_service_health(status_info, context)

        context.safe_print("✅ Status check complete - ready to proceed")

        return {
            "should_abort": False,
            "reason": "",
            "status_info": status_info,
            "cleanup_performed": cleanup_performed,
        }

    except Exception as e:
        return _handle_status_exception(e, context)


async def _get_status_info() -> dict[str, t.Any]:
    """Get comprehensive system status."""
    from .monitoring_tools import _get_comprehensive_status

    return await _get_comprehensive_status()


def _handle_status_error(
    status_info: dict[str, t.Any],
    context: t.Any,
) -> dict[str, t.Any]:
    """Handle status check failure."""
    context.safe_print(f"⚠️ Status check failed: {status_info['error']}")
    return {
        "should_abort": False,
        "reason": "",
        "status_info": status_info,
        "cleanup_performed": [],
    }


def _check_active_jobs(status_info: dict[str, t.Any], context: t.Any) -> None:
    """Check for active jobs that might conflict."""
    active_jobs = [
        j
        for j in status_info.get("jobs", {}).get("details", [])
        if j.get("status") == "running"
    ]

    if active_jobs:
        _handle_conflicting_jobs(active_jobs, context)
    else:
        context.safe_print("✅ No active jobs detected - safe to proceed")


def _handle_conflicting_jobs(
    active_jobs: list[dict[str, t.Any]],
    context: t.Any,
) -> None:
    """Handle conflicting active jobs."""
    # For now, assume all jobs could conflict (future: check project paths)
    conflicting_jobs = active_jobs

    if conflicting_jobs:
        job_ids = [j.get("job_id", "unknown") for j in conflicting_jobs]
        context.safe_print(
            f"⚠️ Found {len(conflicting_jobs)} active job(s): {', '.join(job_ids[:3])}",
        )
        context.safe_print(
            "   Running concurrent crackerjack instances may cause file conflicts",
        )
        context.safe_print("   Proceeding with caution...")


def _check_resource_cleanup(status_info: dict[str, t.Any], context: t.Any) -> list[str]:
    """Check if resource cleanup is needed."""
    cleanup_performed = []

    temp_files_count = (
        status_info.get("server_stats", {})
        .get("resource_usage", {})
        .get("temp_files_count", 0)
    )

    if temp_files_count > 50:
        context.safe_print(
            f"🗑️ Found {temp_files_count} temporary files - cleanup recommended",
        )
        cleanup_performed.append("temp_files_flagged")

    return cleanup_performed


def _check_service_health(status_info: dict[str, t.Any], context: t.Any) -> None:
    """Check health of required services."""
    services = status_info.get("services", {})
    mcp_running = services.get("mcp_server", {}).get("running", False)
    websocket_running = services.get("websocket_server", {}).get("running", False)

    if not mcp_running:
        context.safe_print("⚠️ MCP server not running - will auto-start if needed")

    if not websocket_running:
        context.safe_print("📡 WebSocket server not running - will auto-start")


def _handle_status_exception(error: Exception, context: t.Any) -> dict[str, t.Any]:
    """Handle status check exceptions."""
    context.safe_print(f"⚠️ Status check encountered error: {error}")
    return {
        "should_abort": False,
        "reason": "",
        "status_info": {"error": str(error)},
        "cleanup_performed": [],
    }


async def _cleanup_stale_jobs(context: t.Any) -> None:
    """Clean up stale job files with unknown IDs or stuck in processing state."""
    if not context.progress_dir.exists():
        return

    current_time = time.time()
    cleaned_count = 0

    with suppress(Exception):
        for progress_file in context.progress_dir.glob("job-*.json"):
            try:
                import json

                progress_data = json.loads(progress_file.read_text())

                # Check if job is stale (older than 30 minutes and stuck)
                last_update = progress_data.get("updated_at", 0)
                age_minutes = (current_time - last_update) / 60

                is_stale = (
                    age_minutes > 30  # Older than 30 minutes
                    or progress_data.get("job_id") == "unknown"  # Unknown job ID
                    or "analyzing_failures: processing"
                    in progress_data.get("status", "")  # Stuck in processing
                )

                if is_stale:
                    progress_file.unlink()
                    cleaned_count += 1

            except (json.JSONDecodeError, OSError):
                # Clean up malformed files
                with suppress(OSError):
                    progress_file.unlink()
                    cleaned_count += 1

    if cleaned_count > 0:
        context.safe_print(f"🗑️ Cleaned up {cleaned_count} stale job files")


def _register_init_crackerjack_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def init_crackerjack(args: str = "", kwargs: str = "{}") -> str:
        """Initialize or update crackerjack configuration in current project.

        Args:
            args: Optional target path (defaults to current directory)
            kwargs: JSON string with options like {"force": true}

        Returns:
            JSON string with initialization results
        """
        context = get_context()
        if not context:
            return _create_init_error_response("Server context not available")

        target_path, force, parse_error = _parse_init_arguments(args, kwargs)
        if parse_error:
            return parse_error

        try:
            results = _execute_initialization(context, target_path, force)
            return _create_init_success_response(results, target_path, force)
        except Exception as e:
            return _create_init_exception_response(e, target_path)


def _create_init_error_response(message: str) -> str:
    """Create standardized error response for initialization."""
    return json.dumps({"error": message, "success": False}, indent=2)


def _parse_init_arguments(args: str, kwargs: str) -> tuple[t.Any, bool, str | None]:
    """Parse and validate initialization arguments."""
    from pathlib import Path

    target_path = args.strip() or None

    try:
        extra_kwargs = json.loads(kwargs) if kwargs.strip() else {}
    except json.JSONDecodeError as e:
        return None, False, _create_init_error_response(f"Invalid JSON in kwargs: {e}")

    force = extra_kwargs.get("force", False)

    # Determine target path
    if target_path:
        target_path = Path(target_path).resolve()
    else:
        target_path = Path.cwd()

    # Validate target path exists
    if not target_path.exists():
        return (
            None,
            False,
            _create_init_error_response(f"Target path does not exist: {target_path}"),
        )

    return target_path, force, None


def _execute_initialization(
    context: t.Any, target_path: t.Any, force: bool
) -> dict[str, t.Any]:
    """Execute the initialization process."""
    from crackerjack.services.filesystem import FileSystemService
    from crackerjack.services.git import GitService
    from crackerjack.services.initialization import InitializationService

    # Initialize services
    filesystem = FileSystemService()
    git_service = GitService(context.console, context.config.project_path)
    init_service = InitializationService(
        context.console, filesystem, git_service, context.config.project_path
    )

    # Run initialization
    return init_service.initialize_project(target_path=target_path, force=force)


def _create_init_success_response(
    results: dict[str, t.Any], target_path: t.Any, force: bool
) -> str:
    """Create success response with summary information."""
    results["command"] = "init_crackerjack"
    results["target_path"] = str(target_path)
    results["force"] = force
    return json.dumps(results, indent=2)


def _create_init_exception_response(error: Exception, target_path: t.Any) -> str:
    """Create exception response for initialization failures."""
    error_result = {
        "error": f"Initialization failed: {error}",
        "success": False,
        "command": "init_crackerjack",
        "target_path": str(target_path) if target_path else "current_directory",
    }
    return json.dumps(error_result, indent=2)
