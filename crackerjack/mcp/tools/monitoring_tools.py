import json
import time
import typing as t

from ..context import get_context


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

    try:
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
                    }
                )
            except (json.JSONDecodeError, KeyError):
                continue
    except Exception:
        pass

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
        from ...services.server_manager import (
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
        except Exception:
            pass

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
                    [j for j in active_jobs if j["status"] == "running"]
                ),
                "completed_count": len(
                    [j for j in active_jobs if j["status"] == "completed"]
                ),
                "failed_count": len(
                    [j for j in active_jobs if j["status"] == "failed"]
                ),
                "details": active_jobs,
            },
            "server_stats": _build_server_stats(context),
            "timestamp": time.time(),
        }

        # Add state manager stats
        state_manager = getattr(context, "state_manager", None)
        _add_state_manager_stats(status["server_stats"], state_manager)

        return status

    except Exception as e:
        return {"error": f"Failed to get comprehensive status: {e}"}


def register_monitoring_tools(mcp_app: t.Any) -> None:
    _register_stage_status_tool(mcp_app)
    _register_next_action_tool(mcp_app)
    _register_server_stats_tool(mcp_app)
    _register_comprehensive_status_tool(mcp_app)


def _register_stage_status_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def get_stage_status() -> str:
        context = get_context()
        if not context:
            return '{"error": "Server context not available"}'

        try:
            state_manager = getattr(context, "state_manager", None)
            if not state_manager:
                return '{"error": "State manager not available"}'

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
            return '{"error": "Server context not available"}'

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
            return '{"error": "Server context not available"}'

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
