import json
import typing as t

from crackerjack.mcp.context import get_context

from .error_analyzer import analyze_errors_with_caching
from .workflow_executor import execute_crackerjack_workflow


def register_execution_tools(mcp_app: t.Any) -> None:
    _register_execute_crackerjack_tool(mcp_app)
    _register_smart_error_analysis_tool(mcp_app)
    _register_init_crackerjack_tool(mcp_app)
    _register_agent_suggestions_tool(mcp_app)


def _register_execute_crackerjack_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()  # type: ignore[misc]
    async def execute_crackerjack(args: str, kwargs: str) -> str:
        try:
            context = get_context()
            validation_error = await _handle_context_validation(context)
            if validation_error:
                return validation_error

            kwargs_result = _parse_kwargs(kwargs)
            if "error" in kwargs_result:
                return json.dumps(kwargs_result)

            extra_kwargs = _prepare_execution_kwargs(kwargs_result["kwargs"])
            result = await execute_crackerjack_workflow(args, extra_kwargs)
            return json.dumps(result, indent=2)
        except TypeError as e:
            return _handle_type_error(e)
        except Exception as e:
            return _handle_general_error(e)


async def _handle_context_validation(context: t.Any) -> str | None:
    """Handle context validation with proper error handling."""
    from datetime import datetime

    try:
        validation_error = await _validate_context_and_rate_limit(context)
        if validation_error:
            return validation_error
        return None
    except TypeError as e:
        if "NoneType" in str(e) and "await" in str(e):
            return json.dumps(
                {
                    "status": "failed",
                    "error": "Context validation failed: rate limiter returned None. "
                    "MCP server may not be properly initialized.",
                    "timestamp": datetime.now().isoformat(),
                    "details": str(e),
                }
            )
        raise


def _prepare_execution_kwargs(kwargs: dict[str, t.Any]) -> dict[str, t.Any]:
    """Prepare execution kwargs with appropriate timeout defaults."""
    if "execution_timeout" not in kwargs:
        if kwargs.get("test", False) or kwargs.get("testing", False):
            kwargs["execution_timeout"] = 1200
        else:
            kwargs["execution_timeout"] = 900
    return kwargs


def _handle_type_error(error: TypeError) -> str:
    """Handle TypeError with specific async execution error details."""
    import traceback
    from datetime import datetime

    if "NoneType" in str(error) and "await" in str(error):
        return json.dumps(
            {
                "status": "failed",
                "error": f"Async execution error: A function returned None instead of an awaitable. {error}",
                "traceback": traceback.format_exc(),
                "timestamp": datetime.now().isoformat(),
            }
        )
    raise error


def _handle_general_error(error: Exception) -> str:
    """Handle general execution errors with traceback."""
    import traceback
    from datetime import datetime

    context = get_context()
    return json.dumps(
        {
            "status": "failed",
            "error": f"Execution failed: {error}",
            "traceback": traceback.format_exc(),
            "timestamp": context.get_current_time()
            if context and hasattr(context, "get_current_time")
            else datetime.now().isoformat(),
        }
    )


def _register_smart_error_analysis_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()  # type: ignore[misc]
    async def smart_error_analysis(use_cache: bool = True) -> str:
        context = get_context()

        try:
            analysis = analyze_errors_with_caching(context, use_cache)
            return json.dumps(analysis, indent=2)
        except Exception as e:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Error analysis failed: {e}",
                    "recommendations": [],
                }
            )


def _register_init_crackerjack_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()  # type: ignore[misc]
    def init_crackerjack(args: str = "", kwargs: str = "{}") -> str:
        try:
            target_path, force, error = _parse_init_arguments(args, kwargs)
            if error:
                return _create_init_error_response(error)

            result = _execute_initialization(target_path, force)
            return _create_init_success_response(result)

        except Exception as e:
            return _create_init_exception_response(e, args)


def _register_agent_suggestions_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()  # type: ignore[misc]
    def suggest_agents(
        task_description: str = "",
        project_type: str = "python",
        current_context: str = "",
    ) -> str:
        try:
            recommendations = _generate_agent_recommendations(
                task_description, project_type, current_context
            )
            return json.dumps(recommendations, indent=2)
        except Exception as e:
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Agent suggestion failed: {e}",
                    "recommendations": {},
                }
            )


async def _validate_context_and_rate_limit(context: t.Any) -> str | None:
    if not context:
        return json.dumps({"status": "error", "message": "MCP context not available"})

    if hasattr(context, "rate_limiter"):
        from contextlib import suppress

        with suppress(Exception):
            allowed, details = await context.rate_limiter.check_request_allowed(
                "execute_crackerjack"
            )
            if not allowed:
                return json.dumps(
                    {
                        "status": "error",
                        "message": f"Rate limit exceeded: {details}. Please wait before retrying.",
                    }
                )

    return None


def _parse_kwargs(kwargs: str) -> dict[str, t.Any]:
    try:
        return {"kwargs": json.loads(kwargs) if kwargs.strip() else {}}
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in kwargs: {e}"}


def _parse_init_arguments(args: str, kwargs: str) -> tuple[t.Any, bool, str | None]:
    try:
        target_path = args.strip() or "."
        kwargs_dict: dict[str, t.Any] = json.loads(kwargs) if kwargs.strip() else {}
        force = kwargs_dict.get("force") or False

        from pathlib import Path

        path_obj = Path(target_path)

        return path_obj, force, None

    except json.JSONDecodeError:
        return None, False, "Invalid JSON in kwargs parameter"
    except Exception as e:
        return None, False, f"Invalid arguments: {e}"


def _execute_initialization(target_path: t.Any, force: bool) -> dict[str, t.Any]:
    from acb.console import Console
    from acb.depends import Inject, depends

    from crackerjack.services.filesystem import FileSystemService
    from crackerjack.services.git import GitService
    from crackerjack.services.initialization import InitializationService

    @depends.inject
    def _execute_initialization(
        target_path: t.Any, force: bool, console: Inject[Console]
    ) -> dict[str, t.Any]:
        filesystem = FileSystemService()
        git_service = GitService(target_path)
        return InitializationService(
            filesystem, git_service, target_path
        ).initialize_project_full(force=force)


def _create_init_error_response(message: str) -> str:
    return json.dumps(
        {
            "status": "error",
            "message": message,
            "initialized": False,
        }
    )


def _create_init_success_response(result: dict[str, t.Any]) -> str:
    return json.dumps(
        {
            "status": "success",
            "message": "Crackerjack configuration initialized successfully",
            "result": result,
            "initialized": True,
        },
        indent=2,
    )


def _create_init_exception_response(error: Exception, target_path: t.Any) -> str:
    return json.dumps(
        {
            "status": "error",
            "message": f"Initialization failed: {error}",
            "target_path": str(target_path),
            "initialized": False,
        }
    )


def _generate_agent_recommendations(
    task_description: str, project_type: str, current_context: str
) -> dict[str, t.Any]:
    recommendations = {
        "status": "success",
        "task_analysis": {
            "description": task_description,
            "project_type": project_type,
            "context": current_context,
        },
        "suggested_agents": [],
        "workflow_recommendations": [],
        "reasoning": "",
    }

    suggestions = _analyze_task_for_agents(
        task_description, project_type, current_context
    )
    recommendations["suggested_agents"] = suggestions["agents"]
    recommendations["workflow_recommendations"] = suggestions["workflows"]
    recommendations["reasoning"] = suggestions["reasoning"]

    return recommendations


def _analyze_task_for_agents(
    task_description: str, project_type: str, current_context: str
) -> dict[str, t.Any]:
    agents = []
    workflows = []
    reasoning_parts = []

    task_lower = task_description.lower()
    current_context.lower()

    if any(keyword in task_lower for keyword in ("test", "quality", "fix", "error")):
        agents.extend(
            [
                {
                    "name": "TestCreationAgent",
                    "reason": "Task involves testing or quality assurance",
                    "confidence": 0.8,
                },
                {
                    "name": "RefactoringAgent",
                    "reason": "Code quality improvements often require refactoring",
                    "confidence": 0.7,
                },
            ]
        )
        reasoning_parts.append("Task involves testing or quality improvement")

    if any(
        keyword in task_lower for keyword in ("security", "vulnerability", "secure")
    ):
        agents.append(
            {
                "name": "SecurityAgent",
                "reason": "Task involves security considerations",
                "confidence": 0.9,
            }
        )
        reasoning_parts.append("Security concerns detected")

    if any(
        keyword in task_lower
        for keyword in ("performance", "optimize", "speed", "slow")
    ):
        agents.append(
            {
                "name": "PerformanceAgent",
                "reason": "Task involves performance optimization",
                "confidence": 0.8,
            }
        )
        reasoning_parts.append("Performance optimization required")

    if any(
        keyword in task_lower for keyword in ("document", "readme", "doc", "explain")
    ):
        agents.append(
            {
                "name": "DocumentationAgent",
                "reason": "Task involves documentation work",
                "confidence": 0.8,
            }
        )
        reasoning_parts.append("Documentation work identified")

    if any(
        keyword in task_lower
        for keyword in ("import", "dependency", "package", "module")
    ):
        agents.append(
            {
                "name": "ImportOptimizationAgent",
                "reason": "Task involves import or dependency management",
                "confidence": 0.7,
            }
        )
        reasoning_parts.append("Import / dependency work detected")

    if project_type == "python":
        workflows.extend(
            [
                "Run quality checks with AI agent auto-fixing",
                "Use comprehensive testing with coverage tracking",
                "Apply refactoring for code clarity",
            ]
        )

    if not agents:
        agents.append(
            {
                "name": "RefactoringAgent",
                "reason": "Default agent for general code improvement tasks",
                "confidence": 0.5,
            }
        )
        reasoning_parts.append("General code improvement task")

    reasoning = "; ".join(reasoning_parts)

    return {"agents": agents, "workflows": workflows, "reasoning": reasoning}
