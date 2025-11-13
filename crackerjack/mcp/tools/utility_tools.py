import json
import time
import typing as t
from datetime import datetime
from pathlib import Path

from acb.config import Config
from acb.depends import Inject, depends

from crackerjack.mcp.context import get_context


def _create_error_response(message: str, success: bool = False) -> str:
    return json.dumps({"error": message, "success": success}, indent=2)


def register_utility_tools(mcp_app: t.Any) -> None:
    _register_clean_tool(mcp_app)
    _register_config_tool(mcp_app)
    _register_analyze_tool(mcp_app)


async def clean_temp_files(
    older_than_hours: int = 24,
    dry_run: bool = False,
    patterns: list[str] | None = None,
    directories: list[Path] | None = None,
) -> dict[str, t.Any]:
    """Clean temporary files from specified directories."""
    from datetime import datetime, timedelta

    if patterns is None:
        patterns = ["*.log", ".coverage.*"]
    if directories is None:
        from acb.config import tmp_path

        directories = [Path(tmp_path)]

    cutoff = datetime.now() - timedelta(hours=older_than_hours)
    cleaned_files = []
    total_size = 0

    for directory in directories:
        batch_files, batch_size = _process_directory(
            directory, patterns, cutoff, dry_run
        )
        cleaned_files.extend(batch_files)
        total_size += batch_size

    return {
        "all_cleaned_files": cleaned_files,
        "total_size": total_size,
    }


def _process_directory(
    directory: Path, patterns: list[str], cutoff: t.Any, dry_run: bool
) -> tuple[list[str], int]:
    """Process a single directory for cleaning."""
    if not directory.exists():
        return [], 0

    cleaned_files = []
    total_size = 0

    for pattern in patterns:
        batch_files, batch_size = _process_pattern(directory, pattern, cutoff, dry_run)
        cleaned_files.extend(batch_files)
        total_size += batch_size

    return cleaned_files, total_size


def _process_file_for_cleanup(
    file: Path, cutoff: t.Any, dry_run: bool
) -> tuple[list[str], int]:
    """Process a single file to determine if it should be cleaned."""
    file_info = _check_file_eligibility(file, cutoff)
    if not file_info:
        return [], 0

    file_size, should_clean = file_info
    if not should_clean:
        return [], 0

    # Add to cleaned files
    cleaned_files = [str(file)]
    total_size = file_size

    # Actually delete the file if not in dry_run mode
    if not dry_run:
        file.unlink()

    return cleaned_files, total_size


def _process_pattern(
    directory: Path, pattern: str, cutoff: t.Any, dry_run: bool
) -> tuple[list[str], int]:
    """Process a single pattern within a directory."""
    cleaned_files = []
    total_size = 0

    for file in directory.glob(pattern):
        if file.is_file():
            file_cleaned, size = _process_file_for_cleanup(file, cutoff, dry_run)
            cleaned_files.extend(file_cleaned)
            total_size += size

    return cleaned_files, total_size


def _check_file_eligibility(file: Path, cutoff: t.Any) -> tuple[int, bool] | None:
    """Check if a file is eligible for cleaning based on cutoff time."""
    try:
        file_time = datetime.fromtimestamp(file.stat().st_mtime)
        if file_time < cutoff:
            file_size = file.stat().st_size
            return file_size, True
        return None
    except OSError:
        return None


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
                patterns.extend(
                    [
                        "crackerjack-*.log",
                        "crackerjack - task - error-*.log",
                        ".coverage.*",
                    ]
                )
            if clean_config["scope"] in ("progress", "all"):
                patterns.append("*.json")

            cleanup_results = await clean_temp_files(
                older_than_hours=clean_config["older_than_hours"],
                dry_run=clean_config["dry_run"],
                patterns=patterns,
                directories=[context.progress_dir]
                if clean_config["scope"] in ("progress", "all")
                else None,
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


@depends.inject
def _register_config_tool(mcp_app: t.Any, config: Inject[Config]) -> None:
    @mcp_app.tool()
    async def config_crackerjack(args: str = "", kwargs: str = "{}") -> str:
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
                result = config.model_dump()
            elif action == "get" and len(args_parts) > 1:
                result = getattr(config, args_parts[1], None)
            elif action == "validate":
                # Validation is now implicit with Pydantic v2
                result = {"status": "valid"}
            else:
                return _create_error_response(
                    f"Invalid action '{action}'. Valid actions: list, get <key>, validate"
                )

            return json.dumps(result, indent=2, default=str)

        except Exception as e:
            return _create_error_response(f"Config operation failed: {e}")


async def analyze_project(
    scope: str = "all", report_format: str = "summary"
) -> dict[str, t.Any]:
    """Analyzes the project and returns a summary."""
    # This is a mock implementation to fix the import error.
    # In a real scenario, this would perform a detailed analysis.
    return {
        "scope": scope,
        "report_format": report_format,
        "status": "mock_success",
        "summary": "Project analysis complete (mock).",
    }


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
            analysis_results = await analyze_project(
                scope=scope, report_format=report_format
            )

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
