import typing as t

from crackerjack.mcp.context import get_context


async def create_task_with_subagent(
    description: str,
    prompt: str,
    subagent_type: str,
) -> dict[str, t.Any]:
    """Create a task using a specific subagent type.

    This function provides integration with the Task tool for executing
    user agents and system agents through the intelligent agent system.

    Args:
        description: Description of the task
        prompt: The actual task prompt/content
        subagent_type: Type of subagent to use

    Returns:
        Dictionary with task execution results
    """
    try:
        # For now, return a placeholder result indicating the task would be executed
        # In a full implementation, this would integrate with the actual Task tool

        result = {
            "success": True,
            "description": description,
            "prompt": prompt,
            "subagent_type": subagent_type,
            "result": f"Task would be executed by {subagent_type}: {prompt[:100]}...",
            "agent_type": "user"
            if subagent_type
            not in ("general-purpose", "statusline-setup", "output-style-setup")
            else "system",
        }

        return result

    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "description": description,
            "subagent_type": subagent_type,
        }


async def _validate_stage_request(context, rate_limiter) -> str | None:
    if not context:
        return '{"error": "Server context not available", "success": false}'

    # Skip rate limiting if not configured
    if rate_limiter and hasattr(rate_limiter, "check_request_allowed"):
        allowed, details = await rate_limiter.check_request_allowed()
        if not allowed:
            return f'{{"error": "Rate limit exceeded: {details.get("reason", "unknown")}", "success": false}}'
    return None


def _parse_stage_args(args: str, kwargs: str) -> tuple[str, dict] | str:
    stage = args.strip().lower()
    valid_stages = {"fast", "comprehensive", "tests", "cleaning", "init"}

    if stage not in valid_stages:
        return f'{{"error": "Invalid stage: {stage}. Valid stages: {valid_stages}", "success": false}}'

    import json

    extra_kwargs = {}
    if kwargs.strip():
        try:
            extra_kwargs = json.loads(kwargs)
        except json.JSONDecodeError as e:
            return f'{{"error": "Invalid JSON in kwargs: {e}", "success": false}}'

    return stage, extra_kwargs


def _configure_stage_options(stage: str) -> "WorkflowOptions":
    from crackerjack.models.config import WorkflowOptions

    options = WorkflowOptions()
    if stage in {"fast", "comprehensive"}:
        options.skip_hooks = False
    elif stage == "tests":
        options.testing.test = True
    elif stage == "cleaning":
        options.cleaning.clean = True
    elif stage == "init":
        # Init stage doesn't use standard workflow options
        options.skip_hooks = True
    return options


def _execute_stage(orchestrator, stage: str, options) -> bool:
    if stage == "fast":
        return orchestrator.run_fast_hooks_only(options)
    if stage == "comprehensive":
        return orchestrator.run_comprehensive_hooks_only(options)
    if stage == "tests":
        return orchestrator.run_testing_phase(options)
    if stage == "cleaning":
        return orchestrator.run_cleaning_phase(options)
    if stage == "init":
        return _execute_init_stage(orchestrator)
    return False


def _execute_init_stage(orchestrator) -> bool:
    """Execute project initialization stage."""
    try:
        from pathlib import Path

        from crackerjack.services.filesystem import FileSystemService
        from crackerjack.services.git import GitService
        from crackerjack.services.initialization import InitializationService

        # Get orchestrator dependencies
        console = orchestrator.console
        pkg_path = orchestrator.pkg_path

        # Create service dependencies
        filesystem = FileSystemService()
        git_service = GitService(console, pkg_path)

        # Initialize the service
        init_service = InitializationService(console, filesystem, git_service, pkg_path)

        # Run initialization in current directory
        results = init_service.initialize_project(target_path=Path.cwd())

        return results.get("success", False)

    except Exception as e:
        if hasattr(orchestrator, "console"):
            orchestrator.console.print(f"[red]❌[/red] Initialization failed: {e}")
        return False


def register_core_tools(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def run_crackerjack_stage(args: str, kwargs: str) -> str:
        context = get_context()
        rate_limiter = context.rate_limiter if context else None

        validation_error = await _validate_stage_request(context, rate_limiter)
        if validation_error:
            return validation_error

        try:
            from crackerjack.core.workflow_orchestrator import WorkflowOrchestrator

            parse_result = _parse_stage_args(args, kwargs)
            if isinstance(parse_result, str):
                return parse_result

            stage, extra_kwargs = parse_result

            orchestrator = WorkflowOrchestrator(
                console=context.console,
                pkg_path=context.config.project_path,
                dry_run=extra_kwargs.get("dry_run", False),
            )

            options = _configure_stage_options(stage)
            success = _execute_stage(orchestrator, stage, options)

            return f'{{"success": {str(success).lower()}, "stage": "{stage}"}}'

        except Exception as e:
            context.safe_print(f"Error executing stage {args}: {e}")
            return f'{{"error": "Stage execution failed: {e}", "success": false}}'


def _get_error_patterns() -> list[tuple[str, str]]:
    return [
        ("type_error", r"TypeError:|type object .* has no attribute"),
        ("import_error", r"ImportError:|ModuleNotFoundError:"),
        ("attribute_error", r"AttributeError: "),
        ("syntax_error", r"SyntaxError:|invalid syntax"),
        ("test_failure", r"FAILED|AssertionError:"),
        ("hook_failure", r"hook .* failed"),
    ]


def _get_error_suggestion(error_type: str) -> str:
    suggestions = {
        "type_error": "Check type annotations and ensure proper imports",
        "import_error": "Verify module exists and is properly installed",
        "test_failure": "Review test assertions and expected behavior",
        "hook_failure": "Run hooks individually to identify specific failures",
    }
    return suggestions.get(error_type) or "No specific suggestion available"


def _detect_errors_and_suggestions(
    text: str,
    include_suggestions: bool,
) -> tuple[list[str], list[str]]:
    import re

    detected_errors = []
    suggestions = []

    for error_type, pattern in _get_error_patterns():
        if re.search(pattern, text, re.IGNORECASE):
            detected_errors.append(error_type)
            if include_suggestions:
                suggestions.append(_get_error_suggestion(error_type))

    return detected_errors, suggestions


def register_analyze_errors_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def analyze_errors(output: str = "", include_suggestions: bool = True) -> str:
        context = get_context()
        if not context:
            return '{"error": "Server context not available"}'

        try:
            from crackerjack.services.debug import get_ai_agent_debugger

            debugger = get_ai_agent_debugger()
            if not debugger.enabled:
                return '{"analysis": "Debugging not enabled", "suggestions": []}'

            analysis_text = output or "No specific output provided"
            detected_errors, suggestions = _detect_errors_and_suggestions(
                analysis_text,
                include_suggestions,
            )

            result = {
                "analysis": f"Detected {len(detected_errors)} error types",
                "error_types": detected_errors,
                "suggestions": suggestions if include_suggestions else [],
                "raw_output_length": len(analysis_text),
            }

            import json

            return json.dumps(result, indent=2)

        except Exception as e:
            return f'{{"error": "Error analysis failed: {e}"}}'
