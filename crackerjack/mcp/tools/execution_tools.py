import asyncio
import json
import typing as t
import uuid

from ..context import get_context
from .progress_tools import _update_progress


def register_execution_tools(mcp_app: t.Any) -> None:
    _register_execute_crackerjack_tool(mcp_app)
    _register_smart_error_analysis_tool(mcp_app)


def _register_execute_crackerjack_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def execute_crackerjack(args: str, kwargs: str) -> str:
        context = get_context()
        validation_error = _validate_context_and_rate_limit(context)
        if validation_error:
            return validation_error

        job_id = str(uuid.uuid4())[:8]

        kwargs_result = _parse_kwargs(kwargs)
        if "error" in kwargs_result:
            return json.dumps(kwargs_result)

        extra_kwargs = kwargs_result["kwargs"]
        asyncio.create_task(_execute_crackerjack_background(job_id, args, extra_kwargs))

        return json.dumps(
            {
                "job_id": job_id,
                "status": "started",
                "message": f"Crackerjack execution started with job ID: {job_id}",
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
            from ...services.debug import get_ai_agent_debugger

            get_ai_agent_debugger()

            cached_patterns = _get_cached_patterns(context, use_cache)
            analysis = _build_error_analysis(use_cache, cached_patterns)

            return json.dumps(analysis, indent=2)

        except Exception as e:
            return f'{{"error": "Smart error analysis failed: {e}"}}'


async def _validate_context_and_rate_limit(context: t.Any) -> str | None:
    if not context:
        return '{"error": "Server context not available"}'

    if not context.rate_limiter:
        return '{"error": "Rate limiter not initialized", "success": false}'

    allowed, details = await context.rate_limiter.check_request_allowed()
    if not allowed:
        return f'{{"error": "Rate limit exceeded: {details.get("reason", "unknown")}", "success": false}}'

    return None


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
    use_cache: bool, cached_patterns: list[t.Any]
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


async def _execute_crackerjack_background(
    job_id: str, args: str, kwargs: dict[str, t.Any]
) -> None:
    context = get_context()
    if not context:
        return

    max_iterations = kwargs.get("max_iterations", 10)
    current_iteration = 1

    try:
        _update_progress(
            job_id=job_id,
            status="running",
            iteration=current_iteration,
            max_iterations=max_iterations,
            overall_progress=10,
            current_stage="initialization",
            message="Starting crackerjack execution",
        )

        from ...core.workflow_orchestrator import WorkflowOrchestrator
        from ...models.config import WorkflowOptions

        orchestrator = WorkflowOrchestrator(
            console=context.console,
            pkg_path=context.project_path,
            dry_run=kwargs.get("dry_run", False),
            web_job_id=job_id,
        )

        success = False
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

            options = WorkflowOptions()
            options.testing.test = kwargs.get("test", True)
            options.ai_agent = kwargs.get("ai_agent", True)
            options.skip_hooks = kwargs.get("skip_hooks", False)

            try:
                success = orchestrator.run_complete_workflow(options)

                if success:
                    _update_progress(
                        job_id=job_id,
                        status="completed",
                        iteration=current_iteration,
                        max_iterations=max_iterations,
                        overall_progress=100,
                        current_stage="completed",
                        message=f"Successfully completed after {iteration} iterations",
                    )
                    break
                else:
                    if iteration < max_iterations:
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
                        continue

            except Exception as e:
                context.safe_print(f"Iteration {iteration} failed with error: {e}")
                if iteration >= max_iterations:
                    break
                await asyncio.sleep(1)

        if not success:
            _update_progress(
                job_id=job_id,
                status="failed",
                iteration=current_iteration,
                max_iterations=max_iterations,
                overall_progress=80,
                current_stage="failed",
                message=f"Failed after {max_iterations} iterations",
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
        context.safe_print(f"Background execution failed: {e}")
