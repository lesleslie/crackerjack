"""Refactored MCP execution tools with focused responsibilities.

This module provides the main MCP tool registration and high-level coordination.
Implementation details are delegated to specialized modules:
- workflow_executor.py: Core workflow execution logic
- error_analyzer.py: Error analysis and pattern detection
- (Additional initialization and suggestion modules as needed)

REFACTORING NOTE: Original execution_tools.py was 1110 lines with 30+ functions.
This refactored version is ~300 lines and delegates to focused modules.
"""

import json
import typing as t

from crackerjack.mcp.context import get_context

from .error_analyzer import analyze_errors_with_caching
from .workflow_executor import execute_crackerjack_workflow


def register_execution_tools(mcp_app: t.Any) -> None:
    """Register all execution-related MCP tools."""
    _register_execute_crackerjack_tool(mcp_app)
    _register_smart_error_analysis_tool(mcp_app)
    _register_init_crackerjack_tool(mcp_app)
    _register_agent_suggestions_tool(mcp_app)


def _register_execute_crackerjack_tool(mcp_app: t.Any) -> None:
    """Register the main crackerjack execution tool."""

    @mcp_app.tool()
    async def execute_crackerjack(args: str, kwargs: str) -> str:
        """Execute crackerjack workflow with AI agent auto-fixing."""
        context = get_context()

        # Validate context and rate limits
        validation_error = await _validate_context_and_rate_limit(context)
        if validation_error:
            return validation_error

        # Parse arguments
        kwargs_result = _parse_kwargs(kwargs)
        if "error" in kwargs_result:
            return json.dumps(kwargs_result)

        extra_kwargs = kwargs_result["kwargs"]

        # Execute workflow
        try:
            result = await execute_crackerjack_workflow(args, extra_kwargs)
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps(
                {
                    "status": "failed",
                    "error": f"Execution failed: {e}",
                    "timestamp": context.get_current_time()
                    if hasattr(context, "get_current_time")
                    else None,
                }
            )


def _register_smart_error_analysis_tool(mcp_app: t.Any) -> None:
    """Register the smart error analysis tool."""

    @mcp_app.tool()
    async def smart_error_analysis(use_cache: bool = True) -> str:
        """Analyze cached error patterns and provide intelligent recommendations."""
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
    """Register the crackerjack initialization tool."""

    @mcp_app.tool()
    def init_crackerjack(args: str = "", kwargs: str = "{}") -> str:
        """Initialize or update crackerjack configuration in current project."""
        try:
            target_path, force, error = _parse_init_arguments(args, kwargs)
            if error:
                return _create_init_error_response(error)

            result = _execute_initialization(target_path, force)
            return _create_init_success_response(result)

        except Exception as e:
            return _create_init_exception_response(e, args)


def _register_agent_suggestions_tool(mcp_app: t.Any) -> None:
    """Register the agent suggestions tool."""

    @mcp_app.tool()
    def suggest_agents(
        task_description: str = "",
        project_type: str = "python",
        current_context: str = "",
    ) -> str:
        """Suggest appropriate Claude Code agents based on task and context."""
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


# Helper functions for argument parsing and validation


async def _validate_context_and_rate_limit(context: t.Any) -> str | None:
    """Validate MCP context and check rate limits."""
    if not context:
        return json.dumps({"status": "error", "message": "MCP context not available"})

    # Check rate limits if available
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
    """Parse and validate kwargs string."""
    try:
        return {"kwargs": json.loads(kwargs) if kwargs.strip() else {}}
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON in kwargs: {e}"}


# Initialization helper functions


def _parse_init_arguments(args: str, kwargs: str) -> tuple[t.Any, bool, str | None]:
    """Parse and validate initialization arguments."""
    try:
        target_path = args.strip() or "."
        kwargs_dict = json.loads(kwargs) if kwargs.strip() else {}
        force = kwargs_dict.get("force") or False

        from pathlib import Path

        path_obj = Path(target_path)

        return path_obj, force, None

    except json.JSONDecodeError:
        return None, False, "Invalid JSON in kwargs parameter"
    except Exception as e:
        return None, False, f"Invalid arguments: {e}"


def _execute_initialization(target_path: t.Any, force: bool) -> dict[str, t.Any]:
    """Execute crackerjack initialization."""
    from rich.console import Console

    from crackerjack.services.initialization import InitializationService

    console = Console()

    return InitializationService(console, target_path).initialize_project(
        force_update=force
    )


def _create_init_error_response(message: str) -> str:
    """Create initialization error response."""
    return json.dumps(
        {
            "status": "error",
            "message": message,
            "initialized": False,
        }
    )


def _create_init_success_response(result: dict[str, t.Any]) -> str:
    """Create initialization success response."""
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
    """Create initialization exception response."""
    return json.dumps(
        {
            "status": "error",
            "message": f"Initialization failed: {error}",
            "target_path": str(target_path),
            "initialized": False,
        }
    )


# Agent suggestion helper functions


def _generate_agent_recommendations(
    task_description: str, project_type: str, current_context: str
) -> dict[str, t.Any]:
    """Generate agent recommendations based on task context."""
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

    # Analyze task and context
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
    """Analyze task description to determine appropriate agents."""
    agents = []
    workflows = []
    reasoning_parts = []

    task_lower = task_description.lower()
    current_context.lower()

    # Code quality and testing agents
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

    # Security-related tasks
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

    # Performance optimization
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

    # Documentation tasks
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

    # Import and dependency management
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
        reasoning_parts.append("Import/dependency work detected")

    # Project type specific suggestions
    if project_type == "python":
        workflows.extend(
            [
                "Run quality checks with AI agent auto-fixing",
                "Use comprehensive testing with coverage tracking",
                "Apply refactoring for code clarity",
            ]
        )

    # Default fallback
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
