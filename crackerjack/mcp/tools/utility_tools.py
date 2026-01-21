import json
import tempfile
import time
import typing as t
from datetime import datetime
from pathlib import Path

from crackerjack.mcp.context import get_context


def _create_error_response(message: str, success: bool = False) -> str:
    return json.dumps({"error": message, "success": success}, indent=2)


def register_utility_tools(mcp_app: t.Any) -> None:
    _register_clean_tool(mcp_app)
    _register_config_tool(mcp_app)
    _register_analyze_tool(mcp_app)
    _register_claude_md_validator_tool(mcp_app)


async def clean_temp_files(
    older_than_hours: int = 24,
    dry_run: bool = False,
    patterns: list[str] | None = None,
    directories: list[Path] | None = None,
) -> dict[str, t.Any]:
    from datetime import datetime, timedelta

    if patterns is None:
        patterns = ["*.log", ".coverage.*"]
    if directories is None:
        directories = [Path(tempfile.gettempdir())]

    cutoff = datetime.now() - timedelta(hours=older_than_hours)
    cleaned_files = []
    total_size = 0

    for directory in directories:
        batch_files, batch_size = _process_directory(
            directory,
            patterns,
            cutoff,
            dry_run,
        )
        cleaned_files.extend(batch_files)
        total_size += batch_size

    return {
        "all_cleaned_files": cleaned_files,
        "total_size": total_size,
    }


def _process_directory(
    directory: Path,
    patterns: list[str],
    cutoff: t.Any,
    dry_run: bool,
) -> tuple[list[str], int]:
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
    file: Path,
    cutoff: t.Any,
    dry_run: bool,
) -> tuple[list[str], int]:
    file_info = _check_file_eligibility(file, cutoff)
    if not file_info:
        return [], 0

    file_size, should_clean = file_info
    if not should_clean:
        return [], 0

    cleaned_files = [str(file)]
    total_size = file_size

    if not dry_run:
        file.unlink()

    return cleaned_files, total_size


def _process_pattern(
    directory: Path,
    pattern: str,
    cutoff: t.Any,
    dry_run: bool,
) -> tuple[list[str], int]:
    cleaned_files = []
    total_size = 0

    for file in directory.glob(pattern):
        if file.is_file():
            file_cleaned, size = _process_file_for_cleanup(file, cutoff, dry_run)
            cleaned_files.extend(file_cleaned)
            total_size += size

    return cleaned_files, total_size


def _check_file_eligibility(file: Path, cutoff: t.Any) -> tuple[int, bool] | None:
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
                        "crackerjack-task-error-*.log",
                        ".coverage.*",
                    ],
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


def _parse_cleanup_options(kwargs: str) -> tuple[dict[str, t.Any], str | None]:
    try:
        extra_kwargs: dict[str, t.Any] = json.loads(kwargs) if kwargs.strip() else {}
        return extra_kwargs, None
    except json.JSONDecodeError as e:
        return {}, f"Invalid JSON in kwargs: {e}"


def _clean_temp_files(cutoff_time: float, dry_run: bool) -> tuple[list[str], int]:
    from pathlib import Path

    cleaned: list[str] = []
    total_size = 0
    tmp_dir = Path(tempfile.gettempdir())

    if not tmp_dir.exists():
        return cleaned, total_size

    for file_path in tmp_dir.glob("**/*"):
        if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
            size = file_path.stat().st_size
            if not dry_run:
                file_path.unlink(missing_ok=True)
            cleaned.append(str(file_path))
            total_size += size

    return cleaned, total_size


def _clean_progress_files(
    context: t.Any,
    cutoff_time: float,
    dry_run: bool,
) -> tuple[list[str], int]:
    cleaned: list[str] = []
    total_size = 0

    if not hasattr(context, "progress_dir") or not context.progress_dir.exists():
        return cleaned, total_size

    for file_path in context.progress_dir.glob("**/*"):
        if file_path.is_file() and file_path.stat().st_mtime < cutoff_time:
            size = file_path.stat().st_size
            if not dry_run:
                file_path.unlink(missing_ok=True)
            cleaned.append(str(file_path))
            total_size += size

    return cleaned, total_size


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
    context: t.Any,
    clean_config: dict[str, t.Any],
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
            context,
            cutoff_time,
            clean_config["dry_run"],
        )
        all_cleaned_files.extend(progress_files)
        total_size += progress_size

    if clean_config["scope"] in ("cache", "all"):
        pass

    return {"all_cleaned_files": all_cleaned_files, "total_size": total_size}


def _create_cleanup_response(
    clean_config: dict[str, t.Any],
    cleanup_results: dict[str, t.Any],
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


def _register_config_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def config_crackerjack(args: str = "", kwargs: str = "{}") -> str:
        from crackerjack.config import CrackerjackSettings

        context = get_context()
        if not context:
            return _create_error_response("Server context not available")

        _extra_kwargs, parse_error = _parse_cleanup_options(kwargs)
        if parse_error:
            return _create_error_response(parse_error)

        args_parts = args.strip().split() if args.strip() else ["list"]
        action = args_parts[0].lower()

        try:
            from crackerjack.config import load_settings

            config = load_settings(CrackerjackSettings)
            if action == "list":
                result = config.model_dump()
            elif action == "get" and len(args_parts) > 1:
                result = getattr(config, args_parts[1], None)
            elif action == "validate":
                result = {"status": "valid"}
            else:
                return _create_error_response(
                    f"Invalid action '{action}'. Valid actions: list, get <key>, validate",
                )

            return json.dumps(result, indent=2, default=str)

        except Exception as e:
            return _create_error_response(f"Config operation failed: {e}")


async def analyze_project(
    scope: str = "all",
    report_format: str = "summary",
) -> dict[str, t.Any]:
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
                scope=scope,
                report_format=report_format,
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


def _register_claude_md_validator_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def validate_claude_md(args: str = "", kwargs: str = "{}") -> str:
        context = get_context()
        if not context:
            return _create_error_response("Server context not available")

        extra_kwargs, parse_error = _parse_cleanup_options(kwargs)
        if parse_error:
            return _create_error_response(parse_error)

        update_if_needed = "--update" in args or extra_kwargs.get("update", False)
        project_path_str = extra_kwargs.get("project_path", "")
        project_path = Path(project_path_str) if project_path_str else Path.cwd()

        try:
            validation_result = _perform_claude_md_validation(project_path)

            if not validation_result["valid"] and update_if_needed:
                update_result = _update_claude_md_if_needed(
                    project_path,
                    context,
                )
                validation_result["update_attempted"] = True
                validation_result["update_result"] = update_result

            return json.dumps(
                {
                    "success": True,
                    "command": "validate_claude_md",
                    "project_path": str(project_path),
                    "timestamp": time.time(),
                    "validation": validation_result,
                },
                indent=2,
            )

        except Exception as e:
            return _create_error_response(f"CLAUDE.md validation failed: {e}")


def _check_claude_md_missing(file_path: Path) -> dict[str, t.Any] | None:
    if file_path.exists():
        return None
    return {
        "valid": False,
        "issues": ["CLAUDE.md file not found"],
        "suggestions": [
            "Run 'python -m crackerjack init' to create CLAUDE.md",
        ],
        "file_path": str(file_path),
    }


def _check_integration_markers(
    content: str, file_path: Path
) -> tuple[list[str], list[str]]:
    issues = []
    suggestions = []
    crackerjack_start_marker = "<!-- CRACKERJACK INTEGRATION START -->"

    if crackerjack_start_marker not in content:
        issues.append("Missing crackerjack integration section")
        suggestions.append(
            "Run 'python -m crackerjack init --force' to add crackerjack section"
        )
        return issues, suggestions

    return issues, suggestions


def _check_quality_principles(
    crackerjack_section: str,
) -> tuple[list[str], list[str]]:
    issues = []
    suggestions = []
    essential_principles = [
        (
            "Check yourself before you wreck yourself",
            "Self-validation principle",
        ),
        (
            "Take the time to do things right the first time",
            "Quality-first principle",
        ),
        ("Coverage ratchet", "Coverage quality system"),
        ("Cognitive complexity", "Complexity enforcement"),
    ]

    for principle, description in essential_principles:
        if principle not in crackerjack_section:
            issues.append(f"Missing: {description}")
            suggestions.append(
                f"Ensure '{principle}' is in CLAUDE.md crackerjack section"
            )

    return issues, suggestions


def _extract_crackerjack_section(content: str) -> str | None:
    crackerjack_start_marker = "<!-- CRACKERJACK INTEGRATION START -->"
    crackerjack_end_marker = "<!-- CRACKERJACK INTEGRATION END -->"

    start_idx = content.find(crackerjack_start_marker)
    end_idx = content.find(crackerjack_end_marker)

    if start_idx != -1 and end_idx != -1:
        return content[start_idx : end_idx + len(crackerjack_end_marker)]
    return None


def _perform_claude_md_validation(project_path: Path) -> dict[str, t.Any]:
    claude_md = project_path / "CLAUDE.md"

    missing_result = _check_claude_md_missing(claude_md)
    if missing_result is not None:
        return missing_result

    content = claude_md.read_text()
    issues = []
    suggestions = []

    marker_issues, marker_suggestions = _check_integration_markers(content, claude_md)
    issues.extend(marker_issues)
    suggestions.extend(marker_suggestions)

    if not marker_issues:
        crackerjack_section = _extract_crackerjack_section(content)
        if crackerjack_section:
            principle_issues, principle_suggestions = _check_quality_principles(
                crackerjack_section
            )
            issues.extend(principle_issues)
            suggestions.extend(principle_suggestions)

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "suggestions": suggestions,
        "file_path": str(claude_md),
    }


def _update_claude_md_if_needed(
    project_path: Path,
    context: t.Any,
) -> dict[str, t.Any]:
    try:
        from crackerjack.services.initialization import InitializationService

        init_service = InitializationService(
            console=context.console if hasattr(context, "console") else None,
        )

        result = init_service.initialize_project_full(
            target_path=project_path,
            force=True,
            interactive=False,
        )

        return {
            "success": result.get("success", False),
            "files_updated": result.get("files_copied", []),
            "errors": result.get("errors", []),
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
        }
