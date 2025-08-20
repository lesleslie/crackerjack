import typing as t

from ..context import get_context
from ..rate_limiter import RateLimitConfig


async def _validate_stage_request(context, rate_limiter) -> str | None:
    if not context:
        return '{"error": "Server context not available", "success": false}'
    allowed, details = await rate_limiter.check_request_allowed()
    if not allowed:
        return f'{{"error": "Rate limit exceeded: {details.get("reason", "unknown")}", "success": false}}'
    return None


def _parse_stage_args(args: str, kwargs: str) -> tuple[str, dict] | str:
    stage = args.strip().lower()
    valid_stages = {"fast", "comprehensive", "tests", "cleaning"}

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
    from ...models.config import WorkflowOptions

    options = WorkflowOptions()
    if stage == "fast":
        options.skip_hooks = False
    elif stage == "comprehensive":
        options.skip_hooks = False
    elif stage == "tests":
        options.testing.test = True
    elif stage == "cleaning":
        options.cleaning.clean = True
    return options


def _execute_stage(orchestrator, stage: str, options) -> bool:
    if stage == "fast":
        return orchestrator.run_fast_hooks_only(options)
    elif stage == "comprehensive":
        return orchestrator.run_comprehensive_hooks_only(options)
    elif stage == "tests":
        return orchestrator.run_testing_phase(options)
    elif stage == "cleaning":
        return orchestrator.run_cleaning_phase(options)
    return False


def register_core_tools(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def run_crackerjack_stage(args: str, kwargs: str) -> str:
        context = get_context()
        rate_limiter = context.rate_limiter or RateLimitConfig() if context else None

        validation_error = await _validate_stage_request(context, rate_limiter)
        if validation_error:
            return validation_error

        try:
            from ...core.workflow_orchestrator import WorkflowOrchestrator

            parse_result = _parse_stage_args(args, kwargs)
            if isinstance(parse_result, str):
                return parse_result

            stage, extra_kwargs = parse_result

            orchestrator = WorkflowOrchestrator(
                console=context.console,
                pkg_path=context.project_path,
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
    return suggestions.get(error_type, "No specific suggestion available")


def _detect_errors_and_suggestions(
    text: str, include_suggestions: bool
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
            from ...services.debug import get_ai_agent_debugger

            debugger = get_ai_agent_debugger()
            if not debugger.enabled:
                return '{"analysis": "Debugging not enabled", "suggestions": []}'

            analysis_text = output or "No specific output provided"
            detected_errors, suggestions = _detect_errors_and_suggestions(
                analysis_text, include_suggestions
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
