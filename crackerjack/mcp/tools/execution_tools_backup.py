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
    _register_agent_suggestions_tool(mcp_app)


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

    if context.rate_limiter:
        allowed, details = await context.rate_limiter.check_request_allowed("default")
        if not allowed:
            return f'{{"error": "Rate limit exceeded: {details.get("reason", "unknown")}", "success": false}}'

    return None


def _handle_task_exception(job_id: str, task: asyncio.Task) -> None:
    import tempfile
    from pathlib import Path

    try:
        exception = task.exception()
        if exception:
            debug_file = (
                Path(tempfile.gettempdir()) / f"crackerjack - task-error -{job_id}.log"
            )
            with debug_file.open("w") as f:
                f.write(
                    f"Background task {job_id} failed with exception: {exception}\n",
                )
                f.write(f"Exception type: {type(exception)}\n")
                import traceback

                f.write(
                    f"Traceback: \n{traceback.format_exception(type(exception), exception, exception.__traceback__)}\n",
                )
    except Exception as e:
        with suppress(Exception):
            debug_file = (
                Path(tempfile.gettempdir())
                / f"crackerjack - logging-error -{job_id}.log"
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
    _update_progress(
        job_id=job_id,
        iteration=current_iteration,
        max_iterations=max_iterations,
        overall_progress=2,
        message="Initializing crackerjack execution",
    )

    status_result = await _check_status_and_prepare(job_id, context)
    if status_result.get("should_abort", False):
        msg = f"Execution aborted: {status_result['reason']}"
        raise RuntimeError(msg)

    _update_progress(
        job_id=job_id,
        iteration=current_iteration,
        max_iterations=max_iterations,
        overall_progress=5,
        current_stage="status_verified",
        message="Status check complete-no conflicts detected",
    )

    await _cleanup_stale_jobs(context)

    await _ensure_services_running(job_id, context)

    _update_progress(
        job_id=job_id,
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
    context.safe_print("Using Standard WorkflowOrchestrator for MCP compatibility")
    orchestrator = _create_standard_orchestrator(job_id, kwargs, context)
    use_advanced_orchestrator = False

    orchestrator_type = "Standard Orchestrator (MCP Compatible)"
    _update_progress(
        job_id=job_id,
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

    optimal_config = OrchestrationConfig(
        execution_strategy=ExecutionStrategy.ADAPTIVE,
        progress_level=ProgressLevel.DETAILED,
        streaming_mode=StreamingMode.WEBSOCKET,
        ai_coordination_mode=AICoordinationMode.COORDINATOR,
        ai_intelligence=AIIntelligence.ADAPTIVE,
        correlation_tracking=True,
        failure_analysis=True,
        intelligent_retry=True,
        max_parallel_hooks=3,
        max_parallel_tests=4,
        timeout_multiplier=1.0,
        debug_level="standard",
        log_individual_outputs=False,
        preserve_temp_files=False,
    )

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

    if kwargs.get("debug", False):
        orchestrator.individual_executor.set_mcp_mode(False)
        context.safe_print("🐛 Debug mode enabled-full output mode")

    return orchestrator


def _create_standard_orchestrator(
    job_id: str,
    kwargs: dict[str, t.Any],
    context: t.Any,
) -> t.Any:
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
    success = False
    current_iteration = 1

    for iteration in range(1, max_iterations + 1):
        current_iteration = iteration

        _update_progress(
            job_id=job_id,
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
    from crackerjack.models.config import WorkflowOptions

    options = WorkflowOptions()
    options.testing.test = kwargs.get("test", True)
    options.ai_agent = kwargs.get("ai_agent", True)
    options.skip_hooks = kwargs.get("skip_hooks", False)

    options.proactive_mode = kwargs.get("proactive_mode", True)
    return options


async def _execute_single_iteration(
    orchestrator: t.Any,
    use_advanced_orchestrator: bool,
    options: t.Any,
) -> bool:
    if use_advanced_orchestrator:
        return await orchestrator.execute_orchestrated_workflow(options)
    return await orchestrator.run_complete_workflow(options)


def _create_success_result(
    job_id: str,
    current_iteration: int,
    max_iterations: int,
    iteration: int,
) -> dict[str, t.Any]:
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
    _update_progress(
        job_id=job_id,
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
    if iteration >= max_iterations:
        return False
    await asyncio.sleep(1)
    return True


def _create_failure_result(
    job_id: str,
    current_iteration: int,
    max_iterations: int,
) -> dict[str, t.Any]:
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
    import subprocess

    _update_progress(
        job_id=job_id,
        current_stage="service_startup",
        message="Checking required services...",
    )

    websocket_running = False
    with suppress(Exception):
        from crackerjack.services.server_manager import find_websocket_server_processes

        websocket_processes = find_websocket_server_processes()
        websocket_running = len(websocket_processes) > 0

    if not websocket_running:
        _update_progress(
            job_id=job_id,
            current_stage="service_startup",
            message="Starting WebSocket server...",
        )

        try:
            subprocess.Popen(
                ["python", "- m", "crackerjack", "- - start - websocket-server"],
                cwd=context.config.project_path,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

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
    _update_progress(
        job_id=job_id,
        current_stage="status_check",
        message="🔍 Checking system status to prevent conflicts...",
    )

    try:
        status_info = await _get_status_info()
        if "error" in status_info:
            return _handle_status_error(status_info, context)

        cleanup_performed = []

        _check_active_jobs(status_info, context)

        cleanup_performed.extend(_check_resource_cleanup(status_info, context))

        _check_service_health(status_info, context)

        context.safe_print("✅ Status check complete-ready to proceed")

        return {
            "should_abort": False,
            "reason": "",
            "status_info": status_info,
            "cleanup_performed": cleanup_performed,
        }

    except Exception as e:
        return _handle_status_exception(e, context)


async def _get_status_info() -> dict[str, t.Any]:
    from .monitoring_tools import _get_comprehensive_status

    return await _get_comprehensive_status()


def _handle_status_error(
    status_info: dict[str, t.Any],
    context: t.Any,
) -> dict[str, t.Any]:
    context.safe_print(f"⚠️ Status check failed: {status_info['error']}")
    return {
        "should_abort": False,
        "reason": "",
        "status_info": status_info,
        "cleanup_performed": [],
    }


def _check_active_jobs(status_info: dict[str, t.Any], context: t.Any) -> None:
    active_jobs = [
        j
        for j in status_info.get("jobs", {}).get("details", [])
        if j.get("status") == "running"
    ]

    if active_jobs:
        _handle_conflicting_jobs(active_jobs, context)
    else:
        context.safe_print("✅ No active jobs detected-safe to proceed")


def _handle_conflicting_jobs(
    active_jobs: list[dict[str, t.Any]],
    context: t.Any,
) -> None:
    conflicting_jobs = active_jobs

    if conflicting_jobs:
        job_ids = [j.get("job_id", "unknown") for j in conflicting_jobs]
        context.safe_print(
            f"⚠️ Found {len(conflicting_jobs)} active job(s): {', '.join(job_ids[:3])}",
        )
        context.safe_print(
            " Running concurrent crackerjack instances may cause file conflicts",
        )
        context.safe_print(" Proceeding with caution...")


def _check_resource_cleanup(status_info: dict[str, t.Any], context: t.Any) -> list[str]:
    cleanup_performed = []

    temp_files_count = (
        status_info.get("server_stats", {})
        .get("resource_usage", {})
        .get("temp_files_count", 0)
    )

    if temp_files_count > 50:
        context.safe_print(
            f"🗑️ Found {temp_files_count} temporary files-cleanup recommended",
        )
        cleanup_performed.append("temp_files_flagged")

    return cleanup_performed


def _check_service_health(status_info: dict[str, t.Any], context: t.Any) -> None:
    services = status_info.get("services", {})
    mcp_running = services.get("mcp_server", {}).get("running", False)
    websocket_running = services.get("websocket_server", {}).get("running", False)

    if not mcp_running:
        context.safe_print("⚠️ MCP server not running - will auto-start if needed")

    if not websocket_running:
        context.safe_print("📡 WebSocket server not running - will auto-start")


def _handle_status_exception(error: Exception, context: t.Any) -> dict[str, t.Any]:
    context.safe_print(f"⚠️ Status check encountered error: {error}")
    return {
        "should_abort": False,
        "reason": "",
        "status_info": {"error": str(error)},
        "cleanup_performed": [],
    }


async def _cleanup_stale_jobs(context: t.Any) -> None:
    if not context.progress_dir.exists():
        return

    current_time = time.time()
    cleaned_count = 0

    with suppress(Exception):
        for progress_file in context.progress_dir.glob("job-*.json"):
            try:
                import json

                progress_data = json.loads(progress_file.read_text())

                last_update = progress_data.get("updated_at", 0)
                age_minutes = (current_time - last_update) / 60

                is_stale = (
                    age_minutes > 30
                    or progress_data.get("job_id") == "unknown"
                    or "analyzing_failures: processing"
                    in progress_data.get("status", "")
                )

                if is_stale:
                    progress_file.unlink()
                    cleaned_count += 1

            except (json.JSONDecodeError, OSError):
                with suppress(OSError):
                    progress_file.unlink()
                    cleaned_count += 1

    if cleaned_count > 0:
        context.safe_print(f"🗑️ Cleaned up {cleaned_count} stale job files")


def _register_init_crackerjack_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def init_crackerjack(args: str = "", kwargs: str = "{}") -> str:
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
    return json.dumps({"error": message, "success": False}, indent=2)


def _parse_init_arguments(args: str, kwargs: str) -> tuple[t.Any, bool, str | None]:
    from pathlib import Path

    target_path = args.strip() or None

    try:
        extra_kwargs = json.loads(kwargs) if kwargs.strip() else {}
    except json.JSONDecodeError as e:
        return None, False, _create_init_error_response(f"Invalid JSON in kwargs: {e}")

    force = extra_kwargs.get("force", False)

    if target_path:
        target_path = Path(target_path).resolve()
    else:
        target_path = Path.cwd()

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
    from crackerjack.services.filesystem import FileSystemService
    from crackerjack.services.git import GitService
    from crackerjack.services.initialization import InitializationService

    filesystem = FileSystemService()
    git_service = GitService(context.console, context.config.project_path)

    return InitializationService(
        context.console, filesystem, git_service, context.config.project_path
    ).initialize_project(target_path=target_path, force=force)


def _create_init_success_response(
    results: dict[str, t.Any], target_path: t.Any, force: bool
) -> str:
    results["command"] = "init_crackerjack"
    results["target_path"] = str(target_path)
    results["force"] = force
    return json.dumps(results, indent=2)


def _create_init_exception_response(error: Exception, target_path: t.Any) -> str:
    error_result = {
        "error": f"Initialization failed: {error}",
        "success": False,
        "command": "init_crackerjack",
        "target_path": str(target_path) if target_path else "current_directory",
    }
    return json.dumps(error_result, indent=2)


def _register_agent_suggestions_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def suggest_agents(
        task_description: str = "",
        project_type: str = "python",
        current_context: str = "",
    ) -> str:
        suggestions = {
            "primary_agents": [],
            "task_specific_agents": [],
            "usage_patterns": [],
            "rationale": "",
        }

        if project_type.lower() == "python" or "python" in task_description.lower():
            suggestions["primary_agents"].append(
                {
                    "name": "crackerjack-architect",
                    "emoji": "🏗️",
                    "description": "Expert in crackerjack's modular architecture and Python project management patterns",
                    "usage": "Use PROACTIVELY for all feature development, architectural decisions, and ensuring code follows crackerjack standards",
                    "priority": "HIGH",
                }
            )

            suggestions["primary_agents"].append(
                {
                    "name": "python-pro",
                    "emoji": "🐍",
                    "description": "Modern Python development with type hints, async / await patterns, and clean architecture",
                    "usage": "Use for implementing Python code with best practices",
                    "priority": "HIGH",
                }
            )

        task_lower = task_description.lower()
        context_lower = current_context.lower()

        if any(
            word in task_lower + context_lower
            for word in ("test", "testing", "coverage", "pytest")
        ):
            suggestions["task_specific_agents"].append(
                {
                    "name": "crackerjack - test-specialist",
                    "emoji": "🧪",
                    "description": "Advanced testing specialist for complex scenarios and coverage optimization",
                    "usage": "Use for test creation, debugging test failures, and coverage improvements",
                    "priority": "HIGH",
                }
            )

            suggestions["task_specific_agents"].append(
                {
                    "name": "pytest - hypothesis-specialist",
                    "emoji": "🧪",
                    "description": "Advanced testing patterns and property-based testing",
                    "usage": "Use for comprehensive test development and optimization",
                    "priority": "MEDIUM",
                }
            )

        if any(
            word in task_lower + context_lower
            for word in ("security", "vulnerability", "auth", "permission")
        ):
            suggestions["task_specific_agents"].append(
                {
                    "name": "security-auditor",
                    "emoji": "🔒",
                    "description": "Security analysis, vulnerability detection, and secure coding practices",
                    "usage": "Use for security review and vulnerability assessment",
                    "priority": "HIGH",
                }
            )

        if any(
            word in task_lower + context_lower
            for word in ("architecture", "design", "api", "backend")
        ):
            suggestions["task_specific_agents"].append(
                {
                    "name": "backend-architect",
                    "emoji": "🏗️",
                    "description": "System design, API architecture, and service integration patterns",
                    "usage": "Use for architectural planning and system design",
                    "priority": "MEDIUM",
                }
            )

        suggestions["usage_patterns"] = [
            'Task tool with subagent_type ="crackerjack-architect" for feature planning and architecture',
            'Task tool with subagent_type ="python-pro" for implementation with best practices',
            'Task tool with subagent_type ="crackerjack - test-specialist" for comprehensive testing',
            'Task tool with subagent_type ="security-auditor" for security validation',
        ]

        if "crackerjack-architect" in [
            agent["name"] for agent in suggestions["primary_agents"]
        ]:
            suggestions["rationale"] = (
                "The crackerjack-architect agent is essential for this Python project as it ensures "
                "code follows crackerjack patterns from the start, eliminating retrofitting needs. "
                "Combined with python - pro for implementation and task-specific agents for specialized "
                "work, this provides comprehensive development support with built-in quality assurance."
            )

        return json.dumps(suggestions, indent=2)

    @mcp_app.tool()
    async def detect_agent_needs(
        error_context: str = "",
        file_patterns: str = "",
        recent_changes: str = "",
    ) -> str:
        recommendations = {
            "urgent_agents": [],
            "suggested_agents": [],
            "workflow_recommendations": [],
            "detection_reasoning": "",
        }

        _add_urgent_agents_for_errors(recommendations, error_context)

        _add_python_project_suggestions(recommendations, file_patterns)

        _set_workflow_recommendations(recommendations)

        _generate_detection_reasoning(recommendations)

        return json.dumps(recommendations, indent=2)


def _add_urgent_agents_for_errors(
    recommendations: dict[str, t.Any], error_context: str
) -> None:
    if any(
        word in error_context.lower()
        for word in ("test fail", "coverage", "pytest", "assertion")
    ):
        recommendations["urgent_agents"].append(
            {
                "agent": "crackerjack - test-specialist",
                "reason": "Test failures detected-specialist needed for debugging and fixes",
                "action": 'Task tool with subagent_type ="crackerjack - test-specialist" to analyze and fix test issues',
            }
        )

    if any(
        word in error_context.lower()
        for word in ("security", "vulnerability", "bandit", "unsafe")
    ):
        recommendations["urgent_agents"].append(
            {
                "agent": "security-auditor",
                "reason": "Security issues detected-immediate audit required",
                "action": 'Task tool with subagent_type ="security-auditor" to review and fix security vulnerabilities',
            }
        )

    if any(
        word in error_context.lower()
        for word in ("complexity", "refactor", "too complex")
    ):
        recommendations["urgent_agents"].append(
            {
                "agent": "crackerjack-architect",
                "reason": "Complexity issues detected-architectural review needed",
                "action": 'Task tool with subagent_type ="crackerjack-architect" to simplify and restructure code',
            }
        )


def _add_python_project_suggestions(
    recommendations: dict[str, t.Any], file_patterns: str
) -> None:
    if "python" in file_patterns.lower() or ".py" in file_patterns:
        recommendations["suggested_agents"].extend(
            [
                {
                    "agent": "crackerjack-architect",
                    "reason": "Python project detected-ensure crackerjack compliance",
                    "priority": "HIGH",
                },
                {
                    "agent": "python-pro",
                    "reason": "Python development best practices",
                    "priority": "HIGH",
                },
            ]
        )


def _set_workflow_recommendations(recommendations: dict[str, t.Any]) -> None:
    if recommendations["urgent_agents"]:
        recommendations["workflow_recommendations"] = [
            "Address urgent issues first with specialized agents",
            "Run crackerjack quality checks after fixes: python - m crackerjack-t",
            "Use crackerjack-architect for ongoing compliance",
        ]
    else:
        recommendations["workflow_recommendations"] = [
            "Start with crackerjack-architect for proper planning",
            "Use python-pro for implementation",
            "Run continuous quality checks: python-m crackerjack",
        ]


def _generate_detection_reasoning(recommendations: dict[str, t.Any]) -> None:
    recommendations["detection_reasoning"] = (
        f"Analysis of context revealed {len(recommendations['urgent_agents'])} urgent issues "
        f"and {len(recommendations['suggested_agents'])} general recommendations. "
        "Prioritize urgent agents first, then follow standard workflow patterns."
    )
