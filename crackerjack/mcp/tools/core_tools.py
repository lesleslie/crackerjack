import typing as t

from crackerjack.mcp.context import get_context
from crackerjack.services.input_validator import (
    get_input_validator,
)


async def create_task_with_subagent(
    description: str,
    prompt: str,
    subagent_type: str,
) -> dict[str, t.Any]:
    try:
        # Input validation with security checks
        validator = get_input_validator()

        # Validate description
        desc_result = validator.validate_command_args(description)
        if not desc_result.valid:
            return {
                "success": False,
                "error": f"Invalid description: {desc_result.error_message}",
                "validation_type": desc_result.validation_type,
            }

        # Validate prompt
        prompt_result = validator.validate_command_args(prompt)
        if not prompt_result.valid:
            return {
                "success": False,
                "error": f"Invalid prompt: {prompt_result.error_message}",
                "validation_type": prompt_result.validation_type,
            }

        # Validate subagent_type (should be safe identifier)
        subagent_result = validator.sanitizer.sanitize_string(
            subagent_type, max_length=100, strict_alphanumeric=True
        )
        if not subagent_result.valid:
            return {
                "success": False,
                "error": f"Invalid subagent_type: {subagent_result.error_message}",
                "validation_type": subagent_result.validation_type,
            }

        # Use sanitized values
        sanitized_description = desc_result.sanitized_value or description
        sanitized_prompt = prompt_result.sanitized_value or prompt
        sanitized_subagent = subagent_result.sanitized_value

        result = {
            "success": True,
            "description": sanitized_description,
            "prompt": sanitized_prompt,
            "subagent_type": sanitized_subagent,
            "result": f"Task would be executed by {sanitized_subagent}: {sanitized_prompt[:100]}...",
            "agent_type": "user"
            if sanitized_subagent
            not in ("general-purpose", "statusline-setup", "output-style-setup")
            else "system",
        }

        return result

    except Exception as e:
        return {
            "success": False,
            "error": f"Task creation failed: {e}",
            "description": description,
            "subagent_type": subagent_type,
        }


async def _validate_stage_request(context, rate_limiter) -> str | None:
    if not context:
        return '{"error": "Server context not available", "success": false}'

    if rate_limiter and hasattr(rate_limiter, "check_request_allowed"):
        allowed, details = await rate_limiter.check_request_allowed()
        if not allowed:
            return f'{{"error": "Rate limit exceeded: {details.get("reason", "unknown")}", "success": false}}'
    return None


def _parse_stage_args(args: str, kwargs: str) -> tuple[str, dict] | str:
    try:
        validator = get_input_validator()

        # Validate stage argument
        stage_validation = _validate_stage_argument(validator, args)
        if isinstance(stage_validation, str):
            return stage_validation
        stage = stage_validation

        # Validate and parse kwargs
        kwargs_validation = _validate_kwargs_argument(validator, kwargs)
        if isinstance(kwargs_validation, str):
            return kwargs_validation
        extra_kwargs = kwargs_validation

        return stage, extra_kwargs

    except Exception as e:
        return f'{{"error": "Stage argument parsing failed: {e}", "success": false}}'


def _validate_stage_argument(validator, args: str) -> str:
    """Validate and sanitize the stage argument."""
    stage_result = validator.sanitizer.sanitize_string(
        args.strip(), max_length=50, strict_alphanumeric=True
    )
    if not stage_result.valid:
        return f'{{"error": "Invalid stage argument: {stage_result.error_message}", "success": false}}'

    stage = stage_result.sanitized_value.lower()
    valid_stages = {"fast", "comprehensive", "tests", "cleaning", "init"}

    if stage not in valid_stages:
        return f'{{"error": "Invalid stage: {stage}. Valid stages: {valid_stages}", "success": false}}'

    return stage


def _validate_kwargs_argument(validator, kwargs: str) -> dict | str:
    """Validate and parse the kwargs argument."""
    extra_kwargs = {}
    if not kwargs.strip():
        return extra_kwargs

    kwargs_result = validator.validate_json_payload(kwargs.strip())
    if not kwargs_result.valid:
        return f'{{"error": "Invalid JSON in kwargs: {kwargs_result.error_message}", "success": false}}'

    extra_kwargs = kwargs_result.sanitized_value

    # Additional validation on JSON structure
    if not isinstance(extra_kwargs, dict):
        return f'{{"error": "kwargs must be a JSON object, got {type(extra_kwargs).__name__}", "success": false}}'

    return extra_kwargs


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
    try:
        from pathlib import Path

        from crackerjack.services.filesystem import FileSystemService
        from crackerjack.services.git import GitService
        from crackerjack.services.initialization import InitializationService

        console = orchestrator.console
        pkg_path = orchestrator.pkg_path

        filesystem = FileSystemService()
        git_service = GitService(console, pkg_path)

        init_service = InitializationService(console, filesystem, git_service, pkg_path)

        results = init_service.initialize_project_full(target_path=Path.cwd())

        return results.get("success", False)

    except Exception as e:
        if hasattr(orchestrator, "console"):
            orchestrator.console.print(f"[red]❌[/ red] Initialization failed: {e}")
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
        ("type_error", r"TypeError: | type object .* has no attribute"),
        ("import_error", r"ImportError: | ModuleNotFoundError: "),
        ("attribute_error", r"AttributeError: "),
        ("syntax_error", r"SyntaxError: | invalid syntax"),
        ("test_failure", r"FAILED | AssertionError: "),
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
