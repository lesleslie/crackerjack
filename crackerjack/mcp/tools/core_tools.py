import typing as t

from acb.depends import depends

from crackerjack.config import CrackerjackSettings
from crackerjack.mcp.context import MCPServerContext, get_context
from crackerjack.mcp.rate_limiter import RateLimitMiddleware
from crackerjack.services.input_validator import (
    SecureInputValidator,
    get_input_validator,
)

if t.TYPE_CHECKING:
    from crackerjack.core.workflow_orchestrator import WorkflowOrchestrator


async def create_task_with_subagent(
    description: str,
    prompt: str,
    subagent_type: str,
) -> dict[str, t.Any]:
    try:
        validator = get_input_validator()

        desc_result = validator.validate_command_args(description)
        if not desc_result.valid:
            return {
                "success": False,
                "error": f"Invalid description: {desc_result.error_message}",
                "validation_type": desc_result.validation_type,
            }

        prompt_result = validator.validate_command_args(prompt)
        if not prompt_result.valid:
            return {
                "success": False,
                "error": f"Invalid prompt: {prompt_result.error_message}",
                "validation_type": prompt_result.validation_type,
            }

        subagent_result = validator.sanitizer.sanitize_string(
            subagent_type, max_length=100, strict_alphanumeric=True
        )
        if not subagent_result.valid:
            return {
                "success": False,
                "error": f"Invalid subagent_type: {subagent_result.error_message}",
                "validation_type": subagent_result.validation_type,
            }

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


async def _validate_stage_request(
    context: MCPServerContext | None, rate_limiter: RateLimitMiddleware | None
) -> str | None:
    if not context:
        return '{"error": "Server context not available", "success": false}'

    if rate_limiter and hasattr(rate_limiter, "check_request_allowed"):
        allowed, details = await rate_limiter.check_request_allowed()
        if not allowed:
            return f'{{"error": "Rate limit exceeded: {details.get("reason", "unknown")}", "success": false}}'
    return None


def _parse_stage_args(args: str, kwargs: str) -> tuple[str, dict[str, t.Any]] | str:
    try:
        validator = get_input_validator()

        stage_validation = _validate_stage_argument(validator, args)
        if isinstance(stage_validation, str):
            return stage_validation
        stage = stage_validation

        kwargs_validation = _validate_kwargs_argument(validator, kwargs)
        if isinstance(kwargs_validation, str):
            return kwargs_validation
        extra_kwargs = kwargs_validation

        return stage, extra_kwargs

    except Exception as e:
        return f'{{"error": "Stage argument parsing failed: {e}", "success": false}}'


def _validate_stage_argument(validator: SecureInputValidator, args: str) -> str:
    stage_result = validator.sanitizer.sanitize_string(
        args.strip(), max_length=50, strict_alphanumeric=True
    )
    if not stage_result.valid:
        return f'{{"error": "Invalid stage argument: {stage_result.error_message}", "success": false}}'

    stage: str = str(stage_result.sanitized_value).lower()
    valid_stages = {"fast", "comprehensive", "tests", "cleaning", "init"}

    if stage not in valid_stages:
        return f'{{"error": "Invalid stage: {stage}. Valid stages: {valid_stages}", "success": false}}'

    return stage


def _validate_kwargs_argument(
    validator: SecureInputValidator, kwargs: str
) -> dict[str, t.Any] | str:
    extra_kwargs: dict[str, t.Any] = {}
    if not kwargs.strip():
        return extra_kwargs

    kwargs_result = validator.validate_json_payload(kwargs.strip())
    if not kwargs_result.valid:
        return f'{{"error": "Invalid JSON in kwargs: {kwargs_result.error_message}", "success": false}}'

    extra_kwargs = kwargs_result.sanitized_value

    if not isinstance(extra_kwargs, dict):
        return f'{{"error": "kwargs must be a JSON object, got {type(extra_kwargs).__name__}", "success": false}}'

    return extra_kwargs


def _configure_stage_options(stage: str) -> CrackerjackSettings:
    """Configure settings for a specific stage using ACB dependency injection.

    Note: Returns a copy of global settings with stage-specific overrides.
    The global settings remain unchanged.
    """
    # Get base settings from DI
    base_settings = depends.get(CrackerjackSettings)

    # Create a new settings instance with stage-specific values
    # We copy the base settings and override specific fields
    settings_dict = base_settings.model_dump()

    if stage in {"fast", "comprehensive"}:
        settings_dict["skip_hooks"] = False
    elif stage == "tests":
        settings_dict["run_tests"] = (
            True  # Note: field renamed from 'test' to 'run_tests'
        )
    elif stage == "cleaning":
        settings_dict["clean"] = True
    elif stage == "init":
        settings_dict["skip_hooks"] = True

    return CrackerjackSettings(**settings_dict)


def _execute_stage(
    orchestrator: "WorkflowOrchestrator", stage: str, settings: CrackerjackSettings
) -> bool:
    # Convert CrackerjackSettings to OptionsProtocol
    adapted_options = _adapt_settings_to_protocol(settings)

    if stage == "fast":
        return orchestrator.run_fast_hooks_only(adapted_options)
    if stage == "comprehensive":
        return orchestrator.run_comprehensive_hooks_only(adapted_options)
    if stage == "tests":
        return orchestrator.run_testing_phase(adapted_options)
    if stage == "cleaning":
        return orchestrator.run_cleaning_phase(adapted_options)
    return False


def _adapt_settings_to_protocol(settings: CrackerjackSettings) -> t.Any:
    """Adapt CrackerjackSettings to match OptionsProtocol."""
    return _AdaptedOptions(settings)  # type: ignore


class _AdaptedOptions:
    """Adapter class to convert CrackerjackSettings to OptionsProtocol.

    Since CrackerjackSettings uses flat field structure, this adapter
    is much simpler than the old nested WorkflowOptions version.
    """

    def __init__(self, settings: CrackerjackSettings):
        self.settings = settings

    # Git properties
    @property
    def commit(self) -> bool:
        return self.settings.commit

    @property
    def create_pr(self) -> bool:
        return self.settings.create_pr

    # Execution properties
    @property
    def interactive(self) -> bool:
        return self.settings.interactive

    @property
    def no_config_updates(self) -> bool:
        return self.settings.no_config_updates

    @property
    def verbose(self) -> bool:
        return self.settings.verbose

    @property
    def async_mode(self) -> bool:
        return self.settings.async_mode

    # Testing properties
    @property
    def test(self) -> bool:
        return self.settings.run_tests  # Note: Field renamed in CrackerjackSettings

    @property
    def benchmark(self) -> bool:
        return self.settings.benchmark

    @property
    def test_workers(self) -> int:
        return self.settings.test_workers

    @property
    def test_timeout(self) -> int:
        return self.settings.test_timeout

    # Publishing properties
    @property
    def publish(self) -> t.Any | None:
        return self.settings.publish_version

    @property
    def bump(self) -> t.Any | None:
        return self.settings.bump_version

    @property
    def all(self) -> t.Any | None:
        return self.settings.all_workflow

    @property
    def no_git_tags(self) -> bool:
        return self.settings.no_git_tags

    @property
    def skip_version_check(self) -> bool:
        return self.settings.skip_version_check

    # AI properties
    @property
    def ai_agent(self) -> bool:
        return self.settings.ai_agent

    @property
    def start_mcp_server(self) -> bool:
        return self.settings.start_mcp_server

    # Hook properties
    @property
    def skip_hooks(self) -> bool:
        return self.settings.skip_hooks

    @property
    def update_precommit(self) -> bool:
        return self.settings.update_precommit

    @property
    def experimental_hooks(self) -> bool:
        return self.settings.experimental_hooks

    @property
    def enable_pyrefly(self) -> bool:
        return self.settings.enable_pyrefly

    @property
    def enable_ty(self) -> bool:
        return self.settings.enable_ty

    # Cleaning properties
    @property
    def clean(self) -> bool:
        return self.settings.clean

    # Progress properties
    @property
    def track_progress(self) -> bool:
        return self.settings.progress_enabled

    # Default/static properties (not in settings, keep defaults)
    @property
    def cleanup(self) -> t.Any | None:
        return None

    @property
    def cleanup_pypi(self) -> bool:
        return False

    @property
    def coverage(self) -> bool:
        return self.settings.coverage_enabled

    @property
    def keep_releases(self) -> int:
        return 10

    @property
    def fast(self) -> bool:
        return False


from acb.console import Console
from acb.depends import Inject

from crackerjack.services.filesystem import FileSystemService
from crackerjack.services.git import GitService
from crackerjack.services.initialization import InitializationService


def _execute_init_stage(
    orchestrator: "WorkflowOrchestrator", console: Inject[Console]
) -> bool:
    try:
        from pathlib import Path

        pkg_path = orchestrator.pkg_path

        filesystem = FileSystemService()
        git_service = GitService(pkg_path)

        init_service = InitializationService(filesystem, git_service, pkg_path)

        results = init_service.initialize_project_full(target_path=Path.cwd())

        success_result: bool = bool(results.get("success", False))
        return success_result

    except Exception as e:
        if hasattr(orchestrator, "console"):
            orchestrator.console.print(f"[red]❌[/ red] Initialization failed: {e}")
        return False


def register_core_tools(mcp_app: t.Any) -> None:
    @mcp_app.tool()  # type: ignore[misc]
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

    detected_errors: list[str] = []
    suggestions: list[str] = []

    for error_type, pattern in _get_error_patterns():
        if re.search(pattern, text, re.IGNORECASE):
            detected_errors.append(error_type)
            if include_suggestions:
                suggestions.append(_get_error_suggestion(error_type))

    return detected_errors, suggestions


def register_analyze_errors_tool(mcp_app: t.Any) -> None:
    @mcp_app.tool()  # type: ignore[misc]
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
