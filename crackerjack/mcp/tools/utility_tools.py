import json
import time
import typing as t
from contextlib import suppress
from pathlib import Path

from crackerjack.mcp.context import get_context


def _create_error_response(message: str, success: bool = False) -> str:
    return json.dumps({"error": message, "success": success}, indent=2)


def register_utility_tools(mcp_app: t.Any) -> None:
    _register_clean_tool(mcp_app)
    _register_config_tool(mcp_app)
    _register_analyze_tool(mcp_app)


from acb.actions.system import clean_temp_files


def _register_clean_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def clean_crackerjack(args: str = "", kwargs: str = "{}") -> str:
        context = get_context()
        if not context:
            return _create_error_response("Server context not available")

        clean_config = _parse_clean_configuration(args, kwargs)
        if "error" in clean_config:
            return _create_error_response(clean_config["error"])

        try:
            patterns = []
            if clean_config["scope"] in ("temp", "all"):
                patterns.extend(["crackerjack-*.log", "crackerjack - task - error-*.log", ".coverage.*"])
            if clean_config["scope"] in ("progress", "all"):
                patterns.append("*.json")

            cleanup_results = await clean_temp_files(
                older_than_hours=clean_config["older_than_hours"],
                dry_run=clean_config["dry_run"],
                patterns=patterns,
                directories=[context.progress_dir] if clean_config["scope"] in ("progress", "all") else None
            )
            return _create_cleanup_response(clean_config, cleanup_results)
        except Exception as e:
            return _create_error_response(f"Cleanup failed: {e}")



def _parse_clean_configuration(args: str, kwargs: str) -> dict[str, t.Any]:
    extra_kwargs, parse_error = _parse_cleanup_options(kwargs)
    if parse_error:
        return {"error": parse_error}

    return {
        "scope": args.strip().lower() or "all",
        "dry_run": extra_kwargs.get("dry_run", False),
        "older_than_hours": extra_kwargs.get("older_than", 24),
    }


def _execute_cleanup_operations(
    context: t.Any, clean_config: dict[str, t.Any]
) -> dict[str, t.Any]:
    from datetime import datetime, timedelta

    cutoff_time = (
        datetime.now() - timedelta(hours=clean_config["older_than_hours"])
    ).timestamp()
    all_cleaned_files = []
    total_size = 0

    if clean_config["scope"] in ("temp", "all"):
        temp_files, temp_size = _clean_temp_files(cutoff_time, clean_config["dry_run"])
        all_cleaned_files.extend(temp_files)
        total_size += temp_size

    if clean_config["scope"] in ("progress", "all"):
        progress_files, progress_size = _clean_progress_files(
            context, cutoff_time, clean_config["dry_run"]
        )
        all_cleaned_files.extend(progress_files)
        total_size += progress_size

    if clean_config["scope"] in ("cache", "all"):
        pass

    return {"all_cleaned_files": all_cleaned_files, "total_size": total_size}


def _create_cleanup_response(
    clean_config: dict[str, t.Any], cleanup_results: dict[str, t.Any]
) -> str:
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


from acb.actions.config import get_config_value, get_config_values, validate_config


def _register_config_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def config_crackerjack(args: str = "", kwargs: str = "{}") -> str:
        context = get_context()
        if not context:
            return _create_error_response("Server context not available")

        extra_kwargs, parse_error = _parse_cleanup_options(kwargs)
        if parse_error:
            return _create_error_response(parse_error)

        args_parts = args.strip().split() if args.strip() else ["list[t.Any]"]
        action = args_parts[0].lower()

        try:
            if action == "list[t.Any]":
                result = await get_config_values()
            elif action == "get" and len(args_parts) > 1:
                result = await get_config_value(args_parts[1])
            elif action == "validate":
                result = await validate_config()
            else:
                return _create_error_response(
                    f"Invalid action '{action}'. Valid actions: list[t.Any], get < key >, validate"
                )

            return json.dumps(result, indent=2)

        except Exception as e:
            return _create_error_response(f"Config operation failed: {e}")



from acb.actions.project import analyze_project


def _register_analyze_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def analyze_crackerjack(args: str = "", kwargs: str = "{}") -> str:
        context = get_context()
        if not context:
            return _create_error_response("Server context not available")

        extra_kwargs, parse_error = _parse_cleanup_options(kwargs)
        if parse_error:
            return _create_error_response(parse_error)

        scope = args.strip().lower() or "all"
        report_format = extra_kwargs.get("report_format", "summary")

        try:
            analysis_results = await analyze_project(scope=scope, report_format=report_format)

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

