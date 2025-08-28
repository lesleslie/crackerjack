import json
import time
import typing as t
from contextlib import suppress
from pathlib import Path

from crackerjack.mcp.context import get_context


def _create_error_response(message: str, success: bool = False) -> str:
    """Utility function to create standardized error responses."""
    return json.dumps({"error": message, "success": success}, indent=2)


def register_utility_tools(mcp_app: t.Any) -> None:
    """Register utility slash command tools."""
    _register_clean_tool(mcp_app)
    _register_config_tool(mcp_app)
    _register_analyze_tool(mcp_app)


def _clean_file_if_old(
    file_path: Path, cutoff_time: float, dry_run: bool, file_type: str
) -> dict | None:
    """Clean a single file if it's older than cutoff time."""
    with suppress(OSError):
        if file_path.stat().st_mtime < cutoff_time:
            file_size = file_path.stat().st_size
            if not dry_run:
                file_path.unlink()
            return {"path": str(file_path), "size": file_size, "type": file_type}
    return None


def _clean_temp_files(cutoff_time: float, dry_run: bool) -> tuple[list[dict], int]:
    """Clean temporary files older than cutoff time."""
    import tempfile

    cleaned_files = []
    total_size = 0
    temp_dir = Path(tempfile.gettempdir())

    patterns = ("crackerjack-*.log", "crackerjack-task-error-*.log", ".coverage.*")
    for pattern in patterns:
        for file_path in temp_dir.glob(pattern):
            file_info = _clean_file_if_old(file_path, cutoff_time, dry_run, "temp")
            if file_info:
                cleaned_files.append(file_info)
                total_size += file_info["size"]

    return cleaned_files, total_size


def _clean_progress_files(
    context: t.Any, cutoff_time: float, dry_run: bool
) -> tuple[list[dict], int]:
    """Clean progress files older than cutoff time."""
    cleaned_files = []
    total_size = 0

    if context.progress_dir.exists():
        for progress_file in context.progress_dir.glob("*.json"):
            file_info = _clean_file_if_old(
                progress_file, cutoff_time, dry_run, "progress"
            )
            if file_info:
                cleaned_files.append(file_info)
                total_size += file_info["size"]

    return cleaned_files, total_size


def _parse_cleanup_options(kwargs: str) -> tuple[dict, str | None]:
    """Parse and validate cleanup options from kwargs string."""
    try:
        extra_kwargs = json.loads(kwargs) if kwargs.strip() else {}
        return extra_kwargs, None
    except json.JSONDecodeError as e:
        return {}, f"Invalid JSON in kwargs: {e}"


def _register_clean_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def clean_crackerjack(args: str = "", kwargs: str = "{}") -> str:
        """Clean up temporary files, stale progress data, and cached resources.

        Args:
            args: Optional cleanup scope: 'temp', 'progress', 'cache', 'all' (default)
            kwargs: JSON with options like {"dry_run": true, "older_than": 24}
        """
        context = get_context()
        if not context:
            return _create_error_response("Server context not available")

        clean_config = _parse_clean_configuration(args, kwargs)
        if "error" in clean_config:
            return _create_error_response(clean_config["error"])

        try:
            cleanup_results = _execute_cleanup_operations(context, clean_config)
            return _create_cleanup_response(clean_config, cleanup_results)
        except Exception as e:
            return _create_error_response(f"Cleanup failed: {e}")


def _parse_clean_configuration(args: str, kwargs: str) -> dict:
    """Parse and validate cleanup configuration from arguments."""
    extra_kwargs, parse_error = _parse_cleanup_options(kwargs)
    if parse_error:
        return {"error": parse_error}

    return {
        "scope": args.strip().lower() or "all",
        "dry_run": extra_kwargs.get("dry_run", False),
        "older_than_hours": extra_kwargs.get("older_than", 24),
    }


def _execute_cleanup_operations(context: t.Any, clean_config: dict) -> dict:
    """Execute the cleanup operations based on configuration."""
    from datetime import datetime, timedelta

    cutoff_time = (
        datetime.now() - timedelta(hours=clean_config["older_than_hours"])
    ).timestamp()
    all_cleaned_files = []
    total_size = 0

    # Clean temp files
    if clean_config["scope"] in ("temp", "all"):
        temp_files, temp_size = _clean_temp_files(cutoff_time, clean_config["dry_run"])
        all_cleaned_files.extend(temp_files)
        total_size += temp_size

    # Clean progress files
    if clean_config["scope"] in ("progress", "all"):
        progress_files, progress_size = _clean_progress_files(
            context, cutoff_time, clean_config["dry_run"]
        )
        all_cleaned_files.extend(progress_files)
        total_size += progress_size

    # Clean cache files (if any caching is implemented)
    if clean_config["scope"] in ("cache", "all"):
        # Placeholder for future cache cleaning
        pass

    return {"all_cleaned_files": all_cleaned_files, "total_size": total_size}


def _create_cleanup_response(clean_config: dict, cleanup_results: dict) -> str:
    """Create the cleanup response JSON."""
    all_cleaned_files = cleanup_results["all_cleaned_files"]

    return json.dumps(
        {
            "success": True,
            "command": "clean_crackerjack",
            "dry_run": clean_config["dry_run"],
            "scope": clean_config["scope"],
            "older_than_hours": clean_config["older_than_hours"],
            "files_cleaned": len(all_cleaned_files),
            "total_size_bytes": cleanup_results["total_size"],
            "files": all_cleaned_files
            if len(all_cleaned_files) <= 50
            else all_cleaned_files[:50],
        },
        indent=2,
    )


def _handle_config_list(context: t.Any) -> dict[str, t.Any]:
    """Handle config list action."""
    return {
        "project_path": str(context.config.project_path),
        "rate_limiter": {
            "enabled": context.rate_limiter is not None,
            "config": context.rate_limiter.config.__dict__
            if context.rate_limiter
            else None,
        },
        "progress_dir": str(context.progress_dir),
        "websocket_port": getattr(context, "websocket_server_port", None),
    }


def _handle_config_get(context: t.Any, key: str) -> dict[str, t.Any]:
    """Handle config get action."""
    value = getattr(context.config, key, None)
    if value is None:
        value = getattr(context, key, "Key not found")

    return {
        "success": True,
        "command": "config_crackerjack",
        "action": "get",
        "key": key,
        "value": str(value),
    }


def _handle_config_validate(context: t.Any) -> dict[str, t.Any]:
    """Handle config validate action."""
    validation_results = {
        "project_path_exists": context.config.project_path.exists(),
        "progress_dir_writable": context.progress_dir.exists()
        and context.progress_dir.is_dir(),
        "rate_limiter_configured": context.rate_limiter is not None,
    }

    all_valid = all(validation_results.values())

    return {
        "success": True,
        "command": "config_crackerjack",
        "action": "validate",
        "valid": all_valid,
        "checks": validation_results,
    }


def _register_config_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def config_crackerjack(args: str = "", kwargs: str = "{}") -> str:
        """View or update crackerjack configuration.

        Args:
            args: Action - 'get <key>', 'set <key=value>', 'list', or 'validate'
            kwargs: JSON with additional options
        """
        context = get_context()
        if not context:
            return _create_error_response("Server context not available")

        extra_kwargs, parse_error = _parse_cleanup_options(kwargs)
        if parse_error:
            return _create_error_response(parse_error)

        args_parts = args.strip().split() if args.strip() else ["list"]
        action = args_parts[0].lower()

        try:
            if action == "list":
                config_info = _handle_config_list(context)
                result = {
                    "success": True,
                    "command": "config_crackerjack",
                    "action": "list",
                    "configuration": config_info,
                }
            elif action == "get" and len(args_parts) > 1:
                result = _handle_config_get(context, args_parts[1])
            elif action == "validate":
                result = _handle_config_validate(context)
            else:
                return _create_error_response(
                    f"Invalid action '{action}'. Valid actions: list, get <key>, validate"
                )

            return json.dumps(result, indent=2)

        except Exception as e:
            return _create_error_response(f"Config operation failed: {e}")


def _run_hooks_analysis(orchestrator: t.Any, options: t.Any) -> dict:
    """Run hooks analysis and return results."""
    fast_result = orchestrator.run_fast_hooks_only(options)
    comprehensive_result = orchestrator.run_comprehensive_hooks_only(options)

    return {
        "fast_hooks": "passed" if fast_result else "failed",
        "comprehensive_hooks": "passed" if comprehensive_result else "failed",
    }


def _run_tests_analysis(orchestrator: t.Any, options: t.Any) -> dict:
    """Run tests analysis and return results."""
    test_result = orchestrator.run_testing_phase(options)
    return {"status": "passed" if test_result else "failed"}


def _create_analysis_orchestrator(context: t.Any) -> t.Any:
    """Create workflow orchestrator for analysis."""
    from crackerjack.core.workflow_orchestrator import WorkflowOrchestrator

    return WorkflowOrchestrator(
        console=context.console,
        pkg_path=context.config.project_path,
        dry_run=True,  # Analysis only, no changes
    )


def _register_analyze_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def analyze_crackerjack(args: str = "", kwargs: str = "{}") -> str:
        """Analyze code quality without making changes.

        Args:
            args: Analysis scope - 'hooks', 'tests', 'all' (default)
            kwargs: JSON with options like {"report_format": "summary"}
        """
        context = get_context()
        if not context:
            return _create_error_response("Server context not available")

        extra_kwargs, parse_error = _parse_cleanup_options(kwargs)
        if parse_error:
            return _create_error_response(parse_error)

        scope = args.strip().lower() or "all"
        report_format = extra_kwargs.get("report_format", "summary")

        try:
            from crackerjack.models.config import WorkflowOptions

            orchestrator = _create_analysis_orchestrator(context)
            options = WorkflowOptions()
            analysis_results = {}

            if scope in ("hooks", "all"):
                analysis_results["hooks"] = _run_hooks_analysis(orchestrator, options)

            if scope in ("tests", "all"):
                analysis_results["tests"] = _run_tests_analysis(orchestrator, options)

            return json.dumps(
                {
                    "success": True,
                    "command": "analyze_crackerjack",
                    "scope": scope,
                    "report_format": report_format,
                    "dry_run": True,
                    "timestamp": time.time(),
                    "analysis": analysis_results,
                },
                indent=2,
            )

        except Exception as e:
            return _create_error_response(f"Analysis failed: {e}")
