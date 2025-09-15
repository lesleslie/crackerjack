import json
import time
import typing as t
from contextlib import suppress

from crackerjack.mcp.context import get_context
from crackerjack.services.bounded_status_operations import (
    execute_bounded_status_operation,
)
from crackerjack.services.secure_status_formatter import (
    StatusVerbosity,
    format_secure_status,
    get_secure_status_formatter,
)
from crackerjack.services.status_authentication import (
    authenticate_status_request,
    get_status_authenticator,
)
from crackerjack.services.status_security_manager import (
    get_status_security_manager,
    secure_status_operation,
    validate_status_request,
)
from crackerjack.services.thread_safe_status_collector import (
    get_thread_safe_status_collector,
)
from crackerjack.services.websocket_resource_limiter import (
    get_websocket_resource_limiter,
)


def _suggest_agent_for_context(state_manager: t.Any) -> dict[str, t.Any]:
    suggestions = {
        "recommended_agent": None,
        "reason": "",
        "usage": "",
        "priority": "MEDIUM",
    }

    with suppress(Exception):
        recent_errors = getattr(state_manager, "recent_errors", [])
        stage_statuses = _get_stage_status_dict(state_manager)

        if stage_statuses.get("tests") == "failed" or any(
            "test" in str(error).lower() for error in recent_errors
        ):
            suggestions.update(
                {
                    "recommended_agent": "crackerjack - test-specialist",
                    "reason": "Test failures detected-specialist needed for debugging and fixes",
                    "usage": 'Task tool with subagent_type ="crackerjack - test-specialist"',
                    "priority": "HIGH",
                }
            )

        elif any(
            "security" in str(error).lower() or "bandit" in str(error).lower()
            for error in recent_errors
        ):
            suggestions.update(
                {
                    "recommended_agent": "security-auditor",
                    "reason": "Security issues detected-immediate audit required",
                    "usage": 'Task tool with subagent_type ="security-auditor"',
                    "priority": "HIGH",
                }
            )

        elif any("complex" in str(error).lower() for error in recent_errors):
            suggestions.update(
                {
                    "recommended_agent": "crackerjack-architect",
                    "reason": "Complexity issues detected-architectural review needed",
                    "usage": 'Task tool with subagent_type ="crackerjack-architect"',
                    "priority": "HIGH",
                }
            )

        else:
            suggestions.update(
                {
                    "recommended_agent": "crackerjack-architect",
                    "reason": "Python project-ensure crackerjack compliance from the start",
                    "usage": 'Task tool with subagent_type ="crackerjack-architect"',
                    "priority": "MEDIUM",
                }
            )

    return suggestions


def _create_error_response(message: str, success: bool = False) -> str:
    import json

    return json.dumps({"error": message, "success": success})


def _get_stage_status_dict(state_manager: t.Any) -> dict[str, str]:
    stages = ["fast", "comprehensive", "tests", "cleaning"]
    return {stage: state_manager.get_stage_status(stage) for stage in stages}


def _get_session_info(state_manager: t.Any) -> dict[str, t.Any]:
    return {
        "total_iterations": getattr(state_manager, "iteration_count", 0),
        "current_iteration": getattr(state_manager, "current_iteration", 0),
        "session_active": getattr(state_manager, "session_active", False),
    }


async def _determine_next_action(state_manager: t.Any) -> dict[str, t.Any]:
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


async def _build_server_stats(context: t.Any) -> dict[str, t.Any]:
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
            "temp_files_count": len(list[t.Any](context.progress_dir.glob("*.json")))
            if context.progress_dir.exists()
            else 0,
            "progress_dir": str(context.progress_dir),
        },
        "timestamp": time.time(),
    }


def _add_state_manager_stats(stats: dict[str, t.Any], state_manager: t.Any) -> None:
    if state_manager:
        stats["state_manager"] = {
            "iteration_count": getattr(state_manager, "iteration_count", 0),
            "session_active": getattr(state_manager, "session_active", False),
            "issues_count": len(getattr(state_manager, "issues", [])),
        }


def _get_active_jobs(context: t.Any) -> list[dict[str, t.Any]]:
    jobs: list[dict[str, t.Any]] = []
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


async def _get_comprehensive_status_secure(
    client_id: str = "mcp_client",
    client_ip: str = "127.0.0.1",
    auth_header: str | None = None,
    verbosity: StatusVerbosity = StatusVerbosity.STANDARD,
) -> dict[str, t.Any]:
    auth_manager = get_status_authenticator()
    try:
        credentials = await authenticate_status_request(
            auth_header, client_ip, "get_comprehensive_status"
        )

        if not auth_manager.is_operation_allowed(
            "get_comprehensive_status", credentials.access_level
        ):
            return {"error": "Insufficient privileges for comprehensive status"}

    except Exception as e:
        return {"error": f"Authentication failed: {e}"}

    try:
        await validate_status_request(client_id, "get_comprehensive_status", {})
    except Exception as e:
        return {"error": f"Security validation failed: {e}"}

    try:
        result: dict[str, t.Any] = await execute_bounded_status_operation(
            "status_collection",
            client_id,
            _collect_comprehensive_status_internal,
            client_id,
            verbosity,
        )
        return result
    except Exception as e:
        return {"error": f"Resource limit exceeded: {e}"}


async def _collect_comprehensive_status_internal(
    client_id: str = "mcp_client",
    verbosity: StatusVerbosity = StatusVerbosity.STANDARD,
) -> dict[str, t.Any]:
    collector = get_thread_safe_status_collector()

    try:
        snapshot = await collector.collect_comprehensive_status(
            client_id=client_id,
        )

        status = {
            "services": snapshot.services,
            "jobs": snapshot.jobs,
            "server_stats": snapshot.server_stats,
            "collection_info": {
                "timestamp": snapshot.timestamp,
                "duration": snapshot.collection_duration,
                "is_complete": snapshot.is_complete,
                "errors": snapshot.errors,
            },
        }

        context = None
        with suppress(RuntimeError):
            context = get_context()

        if context:
            state_manager = getattr(context, "state_manager", None)
            if state_manager:
                status["agent_suggestions"] = _suggest_agent_for_context(state_manager)

        return status

    except Exception as e:
        return {"error": f"Failed to collect comprehensive status: {e}"}


async def _get_comprehensive_status() -> dict[str, t.Any]:
    return await _get_comprehensive_status_secure()


def register_monitoring_tools(mcp_app: t.Any) -> None:
    _register_stage_status_tool(mcp_app)
    _register_next_action_tool(mcp_app)
    _register_server_stats_tool(mcp_app)
    _register_comprehensive_status_tool(mcp_app)
    _register_command_help_tool(mcp_app)
    _register_filtered_status_tool(mcp_app)


def _register_stage_status_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()  # type: ignore[misc]  # type: ignore[misc]
    async def get_stage_status() -> str:
        client_id = "mcp_client"

        try:
            await validate_status_request(client_id, "get_stage_status", {})

            context = get_context()
            if not context:
                return _create_error_response("Server context not available")

            state_manager = getattr(context, "state_manager", None)
            if not state_manager:
                return _create_error_response("State manager not available")

            result = await execute_bounded_status_operation(
                "stage_status",
                client_id,
                _build_stage_status,
                state_manager,
            )

            return json.dumps(result, indent=2)

        except Exception as e:
            return f'{{"error": "Failed to get stage status: {e}"}}'


async def _build_stage_status(state_manager: t.Any) -> dict[str, t.Any]:
    return {
        "stages": _get_stage_status_dict(state_manager),
        "session": _get_session_info(state_manager),
        "timestamp": time.time(),
    }


def _register_next_action_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()  # type: ignore[misc]  # type: ignore[misc]
    async def get_next_action() -> str:
        client_id = "mcp_client"

        try:
            await validate_status_request(client_id, "get_next_action", {})

            context = get_context()
            if not context:
                return _create_error_response("Server context not available")

            state_manager = getattr(context, "state_manager", None)
            if not state_manager:
                return '{"recommended_action": "initialize", "reason": "No state manager available"}'

            action = await execute_bounded_status_operation(
                "next_action",
                client_id,
                _determine_next_action,
                state_manager,
            )

            return json.dumps(action, indent=2)

        except Exception as e:
            return f'{{"error": "Failed to determine next action: {e}"}}'


def _register_server_stats_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()  # type: ignore[misc]  # type: ignore[misc]
    async def get_server_stats() -> str:
        client_id = "mcp_client"

        try:
            await validate_status_request(client_id, "get_server_stats", {})

            async with await secure_status_operation(
                client_id, "get_server_stats", timeout=15.0
            ):
                context = get_context()
                if not context:
                    formatter = get_secure_status_formatter()
                    error_response = formatter.format_error_response(
                        "Server context not available",
                    )
                    return json.dumps(error_response, indent=2)

                raw_stats = await execute_bounded_status_operation(
                    "server_stats",
                    client_id,
                    _build_server_stats_secure,
                    context,
                )

                secure_stats = format_secure_status(
                    raw_stats,
                    project_root=context.config.project_path,
                    user_context="mcp_client",
                )

                return json.dumps(secure_stats, indent=2)

        except Exception as e:
            formatter = get_secure_status_formatter()
            error_response = formatter.format_error_response(
                str(e),
            )
            return json.dumps(error_response, indent=2)


async def _build_server_stats_secure(context: t.Any) -> dict[str, t.Any]:
    stats = await _build_server_stats(context)

    state_manager = getattr(context, "state_manager", None)
    _add_state_manager_stats(stats, state_manager)

    security_manager = get_status_security_manager()
    stats["security_status"] = security_manager.get_security_status()

    with suppress(Exception):
        resource_limiter = get_websocket_resource_limiter()
        stats["websocket_resources"] = resource_limiter.get_resource_status()

    return stats


def _register_comprehensive_status_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()  # type: ignore[misc]
    async def get_comprehensive_status() -> str:
        client_id = "mcp_client"
        client_ip = "127.0.0.1"

        try:
            async with await secure_status_operation(
                client_id,
                "get_comprehensive_status",
            ):
                raw_status = await _get_comprehensive_status_secure(
                    client_id=client_id,
                    client_ip=client_ip,
                )

                context = get_context()
                project_root = context.config.project_path if context else None

                secure_status = format_secure_status(
                    raw_status,
                    project_root=project_root,
                    user_context="mcp_client",
                )

                return json.dumps(secure_status, indent=2)

        except Exception as e:
            formatter = get_secure_status_formatter()
            error_response = formatter.format_error_response(
                str(e),
            )
            return json.dumps(error_response, indent=2)


def _register_command_help_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()  # type: ignore[misc]
    async def list_slash_commands() -> str:
        try:
            commands = {
                "/ crackerjack: run": {
                    "description": "Run full iterative auto-fixing with AI agent, tests, progress tracking, and verbose output",
                    "usage": "Direct execution-no parameters needed",
                    "features": [
                        "Up to 10 iterations of quality improvement",
                        "Real-time WebSocket progress streaming",
                        "Advanced orchestrator with adaptive strategies",
                        "Automatic service management",
                        "Debug mode support",
                    ],
                },
                "/ crackerjack: status": {
                    "description": "Get comprehensive system status including servers, jobs, and resource usage",
                    "usage": "Direct execution-no parameters needed",
                    "features": [
                        "MCP server health monitoring",
                        "WebSocket server status",
                        "Active job tracking",
                        "Resource usage metrics",
                        "Error counts and progress data",
                    ],
                },
                "/ crackerjack: init": {
                    "description": "Initialize or update crackerjack configuration with smart configuration merging",
                    "usage": "Optional parameters: target_path (defaults to current directory)",
                    "kwargs": {
                        "force": "boolean-force overwrite existing configurations"
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
                    "available_commands": list[t.Any](commands.keys()),
                    "command_details": commands,
                    "total_commands": len(commands),
                },
                indent=2,
            )

        except Exception as e:
            return json.dumps(
                {
                    "error": f"Failed to list[t.Any] slash commands: {e}",
                    "success": False,
                },
                indent=2,
            )


def _validate_status_components(components: str) -> tuple[set[str], str | None]:
    valid_components = {"services", "jobs", "resources", "all"}
    requested = {c.strip().lower() for c in components.split(", ")}

    invalid = requested - valid_components
    if invalid:
        return set(), f"Invalid components: {invalid}. Valid: {valid_components}"

    return requested, None


def _get_services_status() -> dict[str, t.Any]:
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


def _get_resources_status(context: t.Any) -> dict[str, t.Any]:
    temp_files_count = (
        len(list[t.Any](context.progress_dir.glob("*.json")))
        if context.progress_dir.exists()
        else 0
    )

    return {
        "temp_files_count": temp_files_count,
        "progress_dir": str(context.progress_dir),
    }


async def _build_filtered_status(
    requested: set[str], context: t.Any
) -> dict[str, t.Any]:
    filtered_status: dict[str, t.Any] = {"timestamp": time.time()}

    if "services" in requested:
        filtered_status["services"] = _get_services_status()

    if "jobs" in requested:
        filtered_status["jobs"] = {"active": _get_active_jobs(context)}

    if "resources" in requested:
        filtered_status["resources"] = _get_resources_status(context)

    return filtered_status


def _register_filtered_status_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()  # type: ignore[misc]
    async def get_filtered_status(components: str = "all") -> str:
        client_id = "mcp_client"

        try:
            await validate_status_request(
                client_id, "get_filtered_status", {"components": components}
            )

            return await _process_filtered_status_request(client_id, components)

        except Exception as e:
            return _format_status_error(str(e))


async def _process_filtered_status_request(client_id: str, components: str) -> str:
    requested, error = _validate_status_components(components)
    if error:
        return _format_status_error(error)

    async with await secure_status_operation(
        client_id, "get_filtered_status", timeout=20.0
    ):
        return await _collect_status_data(client_id, requested)


async def _collect_status_data(client_id: str, requested: set[str]) -> str:
    context = get_context()

    if "all" in requested:
        raw_status = await _get_comprehensive_status_secure(
            client_id=client_id,
        )
    else:
        if not context:
            return _format_status_error("Server context not available")

        raw_status = await execute_bounded_status_operation(
            "filtered_status",
            client_id,
            _build_filtered_status,
            requested,
            context,
        )

    return _apply_secure_formatting(raw_status, context)


def _apply_secure_formatting(raw_status: dict[str, t.Any], context: t.Any) -> str:
    project_root = context.config.project_path if context else None
    secure_status = format_secure_status(
        raw_status,
        project_root=project_root,
        user_context="mcp_client",
    )
    return json.dumps(secure_status, indent=2)


def _format_status_error(error_message: str) -> str:
    formatter = get_secure_status_formatter()
    return json.dumps(formatter.format_error_response(error_message), indent=2)
