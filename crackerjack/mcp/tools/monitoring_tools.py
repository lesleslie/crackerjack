import json
import time
import typing as t
from contextlib import suppress

from crackerjack.mcp.context import get_context


def _suggest_agent_for_context(state_manager) -> dict[str, t.Any]:
    """Suggest appropriate agents based on current development context."""
    suggestions = {
        "recommended_agent": None,
        "reason": "",
        "usage": "",
        "priority": "MEDIUM",
    }

    # Check for errors or failures that need specific agents
    with suppress(Exception):
        recent_errors = getattr(state_manager, "recent_errors", [])
        stage_statuses = _get_stage_status_dict(state_manager)

        # Test failures suggest test specialist
        if stage_statuses.get("tests") == "failed" or any(
            "test" in str(error).lower() for error in recent_errors
        ):
            suggestions.update(
                {
                    "recommended_agent": "crackerjack-test-specialist",
                    "reason": "Test failures detected - specialist needed for debugging and fixes",
                    "usage": 'Task tool with subagent_type="crackerjack-test-specialist"',
                    "priority": "HIGH",
                }
            )
        # Security issues suggest security auditor
        elif any(
            "security" in str(error).lower() or "bandit" in str(error).lower()
            for error in recent_errors
        ):
            suggestions.update(
                {
                    "recommended_agent": "security-auditor",
                    "reason": "Security issues detected - immediate audit required",
                    "usage": 'Task tool with subagent_type="security-auditor"',
                    "priority": "HIGH",
                }
            )
        # Complexity issues suggest architect
        elif any("complex" in str(error).lower() for error in recent_errors):
            suggestions.update(
                {
                    "recommended_agent": "crackerjack-architect",
                    "reason": "Complexity issues detected - architectural review needed",
                    "usage": 'Task tool with subagent_type="crackerjack-architect"',
                    "priority": "HIGH",
                }
            )
        # Default recommendation for Python projects
        else:
            suggestions.update(
                {
                    "recommended_agent": "crackerjack-architect",
                    "reason": "Python project - ensure crackerjack compliance from the start",
                    "usage": 'Task tool with subagent_type="crackerjack-architect"',
                    "priority": "MEDIUM",
                }
            )

    return suggestions


def _create_error_response(message: str, success: bool = False) -> str:
    """Utility function to create standardized error responses."""
    import json

    return json.dumps({"error": message, "success": success})


def _get_stage_status_dict(state_manager) -> dict[str, str]:
    stages = ["fast", "comprehensive", "tests", "cleaning"]
    return {stage: state_manager.get_stage_status(stage) for stage in stages}


def _get_session_info(state_manager) -> dict[str, t.Any]:
    return {
        "total_iterations": getattr(state_manager, "iteration_count", 0),
        "current_iteration": getattr(state_manager, "current_iteration", 0),
        "session_active": getattr(state_manager, "session_active", False),
    }


def _determine_next_action(state_manager) -> dict[str, t.Any]:
    stage_priorities = [
        ("fast", "Fast hooks not completed"),
        ("tests", "Tests not completed"),
        ("comprehensive", "Comprehensive hooks not completed"),
    ]

    for stage, reason in stage_priorities:
        if state_manager.get_stage_status(stage) != "completed":
            return {
                "recommended_action": "run_stage",
                "parameters": {"stage": stage},
                "reason": reason,
            }

    return {
        "recommended_action": "complete",
        "parameters": {},
        "reason": "All stages completed successfully",
    }


def _build_server_stats(context) -> dict[str, t.Any]:
    return {
        "server_info": {
            "project_path": str(context.config.project_path),
            "websocket_port": getattr(context, "websocket_server_port", None),
            "websocket_active": getattr(context, "websocket_server_process", None)
            is not None,
        },
        "rate_limiting": {
            "enabled": context.rate_limiter is not None,
            "config": context.rate_limiter.config.__dict__
            if context.rate_limiter
            else None,
        },
        "resource_usage": {
            "temp_files_count": len(list(context.progress_dir.glob("*.json")))
            if context.progress_dir.exists()
            else 0,
            "progress_dir": str(context.progress_dir),
        },
        "timestamp": time.time(),
    }


def _add_state_manager_stats(stats: dict, state_manager) -> None:
    if state_manager:
        stats["state_manager"] = {
            "iteration_count": getattr(state_manager, "iteration_count", 0),
            "session_active": getattr(state_manager, "session_active", False),
            "issues_count": len(getattr(state_manager, "issues", [])),
        }


def _get_active_jobs(context) -> list[dict[str, t.Any]]:
    """Get information about active jobs from progress files."""
    jobs = []
    if not context.progress_dir.exists():
        return jobs

    with suppress(Exception):
        for progress_file in context.progress_dir.glob("job-*.json"):
            try:
                progress_data = json.loads(progress_file.read_text())
                jobs.append(
                    {
                        "job_id": progress_data.get("job_id", "unknown"),
                        "status": progress_data.get("status", "unknown"),
                        "iteration": progress_data.get("iteration", 0),
                        "max_iterations": progress_data.get("max_iterations", 10),
                        "current_stage": progress_data.get("current_stage", "unknown"),
                        "overall_progress": progress_data.get("overall_progress", 0),
                        "stage_progress": progress_data.get("stage_progress", 0),
                        "message": progress_data.get("message", ""),
                        "timestamp": progress_data.get("timestamp", ""),
                        "error_counts": progress_data.get("error_counts", {}),
                    },
                )
            except (json.JSONDecodeError, KeyError):
                continue

    return jobs


async def _get_comprehensive_status() -> dict[str, t.Any]:
    """Get comprehensive status of MCP server, WebSocket server, and active jobs."""
    try:
        context = get_context()
    except RuntimeError:
        context = None

    if not context:
        return {"error": "Server context not available"}

    try:
        # Get server status
        from crackerjack.services.server_manager import (
            find_mcp_server_processes,
            find_websocket_server_processes,
        )

        mcp_processes = find_mcp_server_processes()
        websocket_processes = find_websocket_server_processes()

        # Get active jobs
        active_jobs = _get_active_jobs(context)

        # Get WebSocket server status from context
        websocket_status = None
        try:
            websocket_status = await context.get_websocket_server_status()
        except (ConnectionError, TimeoutError) as e:
            websocket_status = {"error": f"Connection failed: {e}"}
        except Exception as e:
            websocket_status = {"error": f"Status unavailable: {e}"}

        # Build comprehensive status
        status = {
            "services": {
                "mcp_server": {
                    "running": len(mcp_processes) > 0,
                    "processes": mcp_processes,
                },
                "websocket_server": {
                    "running": len(websocket_processes) > 0,
                    "processes": websocket_processes,
                    "port": getattr(context, "websocket_server_port", 8675),
                    "status": websocket_status,
                },
            },
            "jobs": {
                "active_count": len(
                    [j for j in active_jobs if j["status"] == "running"],
                ),
                "completed_count": len(
                    [j for j in active_jobs if j["status"] == "completed"],
                ),
                "failed_count": len(
                    [j for j in active_jobs if j["status"] == "failed"],
                ),
                "details": active_jobs,
            },
            "server_stats": _build_server_stats(context),
            "timestamp": time.time(),
        }

        # Add state manager stats
        state_manager = getattr(context, "state_manager", None)
        _add_state_manager_stats(status["server_stats"], state_manager)

        # Add agent suggestions based on current context
        if state_manager:
            status["agent_suggestions"] = _suggest_agent_for_context(state_manager)

        return status

    except Exception as e:
        return {"error": f"Failed to get comprehensive status: {e}"}


def register_monitoring_tools(mcp_app: t.Any) -> None:
    _register_stage_status_tool(mcp_app)
    _register_next_action_tool(mcp_app)
    _register_server_stats_tool(mcp_app)
    _register_comprehensive_status_tool(mcp_app)
    _register_command_help_tool(mcp_app)
    _register_filtered_status_tool(mcp_app)


def _register_stage_status_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def get_stage_status() -> str:
        context = get_context()
        if not context:
            return _create_error_response("Server context not available")

        try:
            state_manager = getattr(context, "state_manager", None)
            if not state_manager:
                return _create_error_response("State manager not available")

            result = {
                "stages": _get_stage_status_dict(state_manager),
                "session": _get_session_info(state_manager),
                "timestamp": time.time(),
            }

            return json.dumps(result, indent=2)

        except Exception as e:
            return f'{{"error": "Failed to get stage status: {e}"}}'


def _register_next_action_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def get_next_action() -> str:
        context = get_context()
        if not context:
            return _create_error_response("Server context not available")

        try:
            state_manager = getattr(context, "state_manager", None)
            if not state_manager:
                return '{"recommended_action": "initialize", "reason": "No state manager available"}'

            action = _determine_next_action(state_manager)
            return json.dumps(action, indent=2)

        except Exception as e:
            return f'{{"error": "Failed to determine next action: {e}"}}'


def _register_server_stats_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def get_server_stats() -> str:
        context = get_context()
        if not context:
            return _create_error_response("Server context not available")

        try:
            stats = _build_server_stats(context)
            state_manager = getattr(context, "state_manager", None)
            _add_state_manager_stats(stats, state_manager)

            return json.dumps(stats, indent=2)

        except Exception as e:
            return f'{{"error": "Failed to get server stats: {e}"}}'


def _register_comprehensive_status_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def get_comprehensive_status() -> str:
        """Get comprehensive status of MCP server, WebSocket server, and active jobs.

        This is the main status tool used by the /crackerjack:status slash command.
        Provides information about:
        - MCP server status and processes
        - WebSocket server status and connections
        - Active, completed, and failed jobs
        - Progress information for running jobs
        - Error metrics and resolution counts
        - Service health and resource usage
        """
        try:
            status = await _get_comprehensive_status()
            return json.dumps(status, indent=2)
        except Exception as e:
            import traceback

            return f'{{"error": "Failed to get comprehensive status: {e}", "traceback": "{traceback.format_exc()}"}}'


def _register_command_help_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def list_slash_commands() -> str:
        """List all available crackerjack slash commands with descriptions and usage."""
        try:
            commands = {
                "/crackerjack:run": {
                    "description": "Run full iterative auto-fixing with AI agent, tests, progress tracking, and verbose output",
                    "usage": "Direct execution - no parameters needed",
                    "features": [
                        "Up to 10 iterations of quality improvement",
                        "Real-time WebSocket progress streaming",
                        "Advanced orchestrator with adaptive strategies",
                        "Automatic service management",
                        "Debug mode support",
                    ],
                },
                "/crackerjack:status": {
                    "description": "Get comprehensive system status including servers, jobs, and resource usage",
                    "usage": "Direct execution - no parameters needed",
                    "features": [
                        "MCP server health monitoring",
                        "WebSocket server status",
                        "Active job tracking",
                        "Resource usage metrics",
                        "Error counts and progress data",
                    ],
                },
                "/crackerjack:init": {
                    "description": "Initialize or update crackerjack configuration with smart configuration merging",
                    "usage": "Optional parameters: target_path (defaults to current directory)",
                    "kwargs": {
                        "force": "boolean - force overwrite existing configurations"
                    },
                    "features": [
                        "Smart merge preserving existing configurations",
                        "Universal Python project compatibility",
                        "pyproject.toml and pre-commit setup",
                        "Documentation and MCP configuration",
                        "Non-destructive configuration updates",
                    ],
                },
            }

            return json.dumps(
                {
                    "available_commands": list(commands.keys()),
                    "command_details": commands,
                    "total_commands": len(commands),
                },
                indent=2,
            )

        except Exception as e:
            return json.dumps(
                {"error": f"Failed to list slash commands: {e}", "success": False},
                indent=2,
            )


def _validate_status_components(components: str) -> tuple[set[str], str | None]:
    """Validate and parse status components."""
    valid_components = {"services", "jobs", "resources", "all"}
    requested = {c.strip().lower() for c in components.split(",")}

    invalid = requested - valid_components
    if invalid:
        return set(), f"Invalid components: {invalid}. Valid: {valid_components}"

    return requested, None


def _get_services_status() -> dict:
    """Get services status information."""
    from crackerjack.services.server_manager import (
        find_mcp_server_processes,
        find_websocket_server_processes,
    )

    mcp_processes = find_mcp_server_processes()
    websocket_processes = find_websocket_server_processes()

    return {
        "mcp_server": {
            "running": len(mcp_processes) > 0,
            "processes": mcp_processes,
        },
        "websocket_server": {
            "running": len(websocket_processes) > 0,
            "processes": websocket_processes,
        },
    }


def _get_resources_status(context: t.Any) -> dict:
    """Get resources status information."""
    temp_files_count = (
        len(list(context.progress_dir.glob("*.json")))
        if context.progress_dir.exists()
        else 0
    )

    return {
        "temp_files_count": temp_files_count,
        "progress_dir": str(context.progress_dir),
    }


def _build_filtered_status(requested: set[str], context: t.Any) -> dict:
    """Build filtered status based on requested components."""
    filtered_status = {"timestamp": time.time()}

    if "services" in requested:
        filtered_status["services"] = _get_services_status()

    if "jobs" in requested:
        filtered_status["jobs"] = {"active": _get_active_jobs(context)}

    if "resources" in requested:
        filtered_status["resources"] = _get_resources_status(context)

    return filtered_status


def _register_filtered_status_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def get_filtered_status(components: str = "all") -> str:
        """Get specific status components for better performance.

        Args:
            components: Comma-separated list of components to include:
                       'services', 'jobs', 'resources', 'all' (default)
        """
        try:
            requested, error = _validate_status_components(components)
            if error:
                return json.dumps({"error": error, "success": False}, indent=2)

            # If 'all' is requested, get everything
            if "all" in requested:
                status = await _get_comprehensive_status()
                return json.dumps(status, indent=2)

            context = get_context()
            if not context:
                return json.dumps(
                    {"error": "Server context not available", "success": False}
                )

            filtered_status = _build_filtered_status(requested, context)
            return json.dumps(filtered_status, indent=2)

        except Exception as e:
            return json.dumps(
                {"error": f"Failed to get filtered status: {e}", "success": False},
                indent=2,
            )
