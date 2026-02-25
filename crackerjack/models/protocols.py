import contextlib
import subprocess
import typing as t
from pathlib import Path
from typing import TYPE_CHECKING

from crackerjack.config.settings import CrackerjackSettings

if t.TYPE_CHECKING:
    from crackerjack.agents.base import AgentContext, FixResult, Issue
    from crackerjack.models.qa_config import QACheckConfig
    from crackerjack.models.qa_results import QAResult


@t.runtime_checkable
class ServiceProtocol(t.Protocol):
    def initialize(self) -> None: ...

    def cleanup(self) -> None: ...

    def health_check(self) -> bool: ...

    def shutdown(self) -> None: ...

    def metrics(self) -> dict[str, t.Any]: ...

    def is_healthy(self) -> bool: ...

    def register_resource(self, resource: t.Any) -> None: ...

    def cleanup_resource(self, resource: t.Any) -> None: ...

    def record_error(self, error: Exception) -> None: ...

    def increment_requests(self) -> None: ...

    def get_custom_metric(self, name: str) -> t.Any: ...

    def set_custom_metric(self, name: str, value: t.Any) -> None: ...


@t.runtime_checkable
class CommandRunner(t.Protocol):
    def execute_command(
        self,
        cmd: list[str],
        **kwargs: t.Any,
    ) -> subprocess.CompletedProcess[str]: ...


@t.runtime_checkable
class OptionsProtocol(t.Protocol):
    test: bool
    """Run test suite."""

    run_tests: bool
    """Alias for test. Run test suite."""

    test_workers: int = 0
    """Number of test workers (0 = auto-detect, 1 = sequential, N = explicit)."""

    test_timeout: int = 0
    """Test timeout in seconds (0 = no timeout)."""

    benchmark: bool
    """Run benchmarks."""

    benchmark_regression: bool = False
    """Check for benchmark regressions."""

    benchmark_regression_threshold: float = 0.1
    """Threshold for benchmark regression (default: 10%)."""

    fast: bool
    """Run fast hooks only (~5 seconds)."""

    comp: bool
    """Run comprehensive hooks (~30 seconds)."""

    skip_hooks: bool
    """Skip all hooks."""

    tool: str | None = None
    """Run specific tool only."""

    changed_only: bool
    """Run checks on changed files only."""

    advanced_batch: str | None = None
    """Advanced batch processing options."""

    ai_agent: bool = False
    """Enable AI agent for suggestions."""

    ai_fix_max_iterations: int = 10
    """Maximum AI fix iterations (default: 10)."""

    publish: t.Any | None
    """Publish package to PyPI."""

    bump: t.Any | None
    """Bump version (major, minor, patch)."""

    all: t.Any | None
    """Run all operations (tests, hooks, publish)."""

    create_pr: bool
    """Create pull request after publishing."""

    keep_releases: int = 10
    """Number of releases to keep (default: 10)."""

    cleanup_pypi: bool = False
    """Cleanup old PyPI releases."""

    no_git_tags: bool
    """Skip git tag creation."""

    skip_version_check: bool
    """Skip version check."""

    coverage: bool
    """Generate coverage report."""

    commit: bool
    """Commit changes after successful run."""

    interactive: bool
    """Interactive mode (confirm actions)."""

    no_config_updates: bool
    """Skip automatic config updates."""

    skip_config_merge: bool
    """Skip config merging."""

    verbose: bool
    """Verbose output."""

    track_progress: bool
    """Track and display progress."""

    clean: bool
    """Clean temporary files and caches."""

    cleanup: t.Any | None
    """Cleanup old releases/artifacts."""

    async_mode: bool
    """Enable async mode."""

    experimental_hooks: bool
    """Enable experimental hooks."""

    enable_pyrefly: bool
    """Enable pyrefly type checker."""

    enable_ty: bool
    """Enable ty type checker."""

    disable_global_locks: bool
    """Disable global locks."""

    global_lock_timeout: int = 600
    """Global lock timeout in seconds (default: 600)."""

    global_lock_cleanup: bool = True
    """Enable global lock cleanup."""

    global_lock_dir: str | None
    """Global lock directory path."""

    strip_code: bool
    """Strip debugging code."""

    xcode_tests: bool
    """Run Xcode tests."""

    xcode_project: str = "app/MdInjectApp/MdInjectApp.xcodeproj"
    """Xcode project path."""

    xcode_scheme: str = "MdInjectApp"
    """Xcode scheme name."""

    xcode_configuration: str = "Debug"
    """Xcode build configuration."""

    xcode_destination: str = "platform=macOS"
    """Xcode test destination."""

    fast_iteration: bool
    """Fast iteration mode (skip non-essentials)."""

    monitor_dashboard: str | None
    """Monitor dashboard URL."""

    start_mcp_server: bool = False
    """Start MCP server."""

    generate_docs: bool
    """Generate documentation."""

    docs_format: str = "markdown"
    """Documentation format (markdown, html, etc.)."""

    validate_docs: bool
    """Validate documentation."""

    update_docs_index: bool
    """Update documentation index."""


@t.runtime_checkable
class ConsoleInterface(t.Protocol):
    def print(self, *args: t.Any, **kwargs: t.Any) -> None: ...

    def input(self, prompt: str = "") -> str: ...

    if TYPE_CHECKING:

        async def aprint(self, *args: t.Any, **kwargs: t.Any) -> None: ...


@t.runtime_checkable
class FileSystemInterface(t.Protocol):
    def read_file(self, path: str | t.Any) -> str: ...

    def write_file(self, path: str | t.Any, content: str) -> None: ...

    def exists(self, path: str | t.Any) -> bool: ...

    def mkdir(self, path: str | t.Any, parents: bool = False) -> None: ...


@t.runtime_checkable
class GitInterface(t.Protocol):
    def is_git_repo(self) -> bool: ...

    def get_changed_files(self) -> list[str]: ...

    def commit(self, message: str) -> bool: ...

    def push(self) -> bool: ...

    def add_files(self, files: list[str]) -> bool: ...

    def add_all_files(self) -> bool: ...

    if TYPE_CHECKING:

        def get_staged_files(self) -> list[str]: ...

        def get_changed_files_by_extension(
            self,
            extensions: list[str],
            include_staged: bool = True,
            include_unstaged: bool = True,
        ) -> list[Path]: ...

        def get_changed_files_since(
            self, since: str, project_root: Path
        ) -> list[str]: ...

        def get_unstaged_files(self) -> list[str]: ...

        def push_with_tags(self) -> bool: ...

        def get_commit_message_suggestions(
            self,
            changed_files: list[str],
        ) -> list[str]: ...

        def get_unpushed_commit_count(self) -> int: ...

        def get_current_commit_hash(self) -> str | None: ...

        def reset_hard(self, commit_hash: str) -> bool: ...


@t.runtime_checkable
class HookManager(t.Protocol):
    def run_fast_hooks(self) -> list[t.Any]: ...

    def run_comprehensive_hooks(self) -> list[t.Any]: ...

    def install_hooks(self) -> bool: ...

    def set_config_path(self, path: str | t.Any) -> None: ...

    def get_hook_summary(
        self,
        results: t.Any,
        elapsed_time: float | None = None,
    ) -> t.Any: ...

    if TYPE_CHECKING:

        def get_hook_count(self, suite_name: str) -> int: ...

        _progress_callback: t.Callable[[int, int], None] | None
        """Optional callback for progress updates (current, total)."""

        _progress_start_callback: t.Callable[[int, int], None] | None
        """Optional callback for progress start (total, estimated_time)."""


@t.runtime_checkable
class SecurityAwareHookManager(HookManager, t.Protocol):
    def get_security_critical_failures(self, results: list[t.Any]) -> list[t.Any]: ...

    def has_security_critical_failures(self, results: list[t.Any]) -> bool: ...

    def get_security_audit_report(
        self,
        fast_results: list[t.Any],
        comprehensive_results: list[t.Any],
    ) -> dict[str, t.Any]: ...


@t.runtime_checkable
class CoverageRatchetProtocol(ServiceProtocol, t.Protocol):
    def get_baseline_coverage(self) -> float: ...

    def update_baseline_coverage(self, new_coverage: float) -> bool: ...

    def is_coverage_regression(self, current_coverage: float) -> bool: ...

    def get_coverage_improvement_needed(self) -> float: ...

    def get_status_report(self) -> dict[str, t.Any]: ...

    def get_coverage_report(self) -> str | None: ...

    def check_and_update_coverage(self) -> dict[str, t.Any]: ...


@t.runtime_checkable
class SecurityServiceProtocol(ServiceProtocol, t.Protocol):
    def validate_file_safety(self, path: str | Path) -> bool: ...

    def check_hardcoded_secrets(self, content: str) -> list[dict[str, t.Any]]: ...

    def is_safe_subprocess_call(self, cmd: list[str]) -> bool: ...

    def create_secure_command_env(self) -> dict[str, str]: ...

    def mask_tokens(self, text: str) -> str: ...

    def validate_token_format(self, token: str, token_type: str) -> bool: ...


@t.runtime_checkable
class InitializationServiceProtocol(ServiceProtocol, t.Protocol):
    def initialize_project(self, project_path: str | Path) -> bool: ...

    def validate_project_structure(self) -> bool: ...

    def setup_git_hooks(self) -> bool: ...


@t.runtime_checkable
class SmartSchedulingServiceProtocol(ServiceProtocol, t.Protocol):
    def should_scheduled_init(self) -> bool: ...

    def record_init_timestamp(self) -> None: ...


@t.runtime_checkable
class UnifiedConfigurationServiceProtocol(ServiceProtocol, t.Protocol):
    def get_config(self, reload: bool = False) -> CrackerjackSettings: ...

    def get_logging_config(self) -> dict[str, t.Any]: ...

    def get_hook_execution_config(self) -> dict[str, t.Any]: ...

    def get_testing_config(self) -> dict[str, t.Any]: ...

    @staticmethod
    def get_cache_config() -> dict[str, t.Any]: ...

    def validate_current_config(self) -> bool: ...


@t.runtime_checkable
class ConfigIntegrityServiceProtocol(ServiceProtocol, t.Protocol):
    def check_config_integrity(self) -> bool: ...


@t.runtime_checkable
class TestManagerProtocol(ServiceProtocol, t.Protocol):
    def run_tests(self, options: OptionsProtocol) -> bool: ...

    def get_test_failures(self) -> list[str]: ...

    def validate_test_environment(self) -> bool: ...

    def get_coverage(self) -> dict[str, t.Any]: ...


@t.runtime_checkable
class BoundedStatusOperationsProtocol(ServiceProtocol, t.Protocol):
    async def execute_bounded_operation(
        self,
        operation_type: str,
        client_id: str,
        operation_func: t.Callable[..., t.Awaitable[t.Any]],
        *args: t.Any,
        **kwargs: t.Any,
    ) -> t.Any: ...

    def get_operation_status(self) -> dict[str, t.Any]: ...

    def reset_circuit_breaker(self, operation_type: str) -> bool: ...


@t.runtime_checkable
class PublishManager(t.Protocol):
    def bump_version(self, version_type: str) -> str: ...

    def publish_package(self) -> bool: ...

    def validate_auth(self) -> bool: ...

    def create_git_tag(self, version: str) -> bool: ...

    def create_git_tag_local(self, version: str) -> bool: ...

    def cleanup_old_releases(self, keep_releases: int) -> None: ...


@t.runtime_checkable
class ConfigMergeServiceProtocol(ServiceProtocol, t.Protocol):
    def smart_merge_pyproject(
        self,
        source_content: dict[str, t.Any],
        target_path: str | t.Any,
        project_name: str,
    ) -> dict[str, t.Any]: ...

    def smart_merge_pre_commit_config(
        self,
        source_content: dict[str, t.Any],
        target_path: str | t.Any,
        project_name: str,
    ) -> dict[str, t.Any]: ...

    def smart_append_file(
        self,
        source_content: str,
        target_path: str | t.Any,
        start_marker: str,
        end_marker: str,
        force: bool = False,
    ) -> str: ...

    def smart_merge_gitignore(
        self,
        patterns: list[str],
        target_path: str | t.Any,
    ) -> str: ...

    def write_pyproject_config(
        self,
        config: dict[str, t.Any],
        target_path: str | t.Any,
    ) -> None: ...

    def write_pre_commit_config(
        self,
        config: dict[str, t.Any],
        target_path: str | t.Any,
    ) -> None: ...


@t.runtime_checkable
class HookLockManagerProtocol(t.Protocol):
    def requires_lock(self, hook_name: str) -> bool: ...

    def acquire_hook_lock(self, hook_name: str) -> t.AsyncContextManager[None]: ...

    def get_lock_stats(self) -> dict[str, t.Any]: ...

    def add_hook_to_lock_list(self, hook_name: str) -> None: ...

    def remove_hook_from_lock_list(self, hook_name: str) -> None: ...

    def is_hook_currently_locked(self, hook_name: str) -> bool: ...

    def enable_global_lock(self, enabled: bool = True) -> None: ...

    def is_global_lock_enabled(self) -> bool: ...

    def get_global_lock_path(self, hook_name: str) -> Path: ...

    def cleanup_stale_locks(self, max_age_hours: float = 2.0) -> int: ...

    def get_global_lock_stats(self) -> dict[str, t.Any]: ...


@t.runtime_checkable
class DocumentationServiceProtocol(ServiceProtocol, t.Protocol):
    def extract_api_documentation(
        self,
        source_paths: list[Path],
    ) -> dict[str, t.Any]: ...

    def generate_documentation(
        self,
        template_name: str,
        context: dict[str, t.Any],
    ) -> str: ...

    def validate_documentation(self, doc_paths: list[Path]) -> list[dict[str, str]]: ...

    def update_documentation_index(self) -> bool: ...

    def get_documentation_coverage(self) -> dict[str, t.Any]: ...


@t.runtime_checkable
class APIExtractorProtocol(t.Protocol):
    def extract_from_python_files(self, files: list[Path]) -> dict[str, t.Any]: ...

    def extract_protocol_definitions(self, protocol_file: Path) -> dict[str, t.Any]: ...

    def extract_service_interfaces(
        self,
        service_files: list[Path],
    ) -> dict[str, t.Any]: ...

    def extract_cli_commands(self, cli_files: list[Path]) -> dict[str, t.Any]: ...

    def extract_mcp_tools(self, mcp_files: list[Path]) -> dict[str, t.Any]: ...


@t.runtime_checkable
class DocumentationGeneratorProtocol(t.Protocol):
    def generate_api_reference(self, api_data: dict[str, t.Any]) -> str: ...

    def generate_user_guide(self, template_context: dict[str, t.Any]) -> str: ...

    def generate_changelog_update(
        self,
        version: str,
        changes: dict[str, t.Any],
    ) -> str: ...

    def render_template(
        self,
        template_path: Path,
        context: dict[str, t.Any],
    ) -> str: ...

    def generate_cross_references(
        self,
        api_data: dict[str, t.Any],
    ) -> dict[str, list[str]]: ...


@t.runtime_checkable
class DocumentationValidatorProtocol(t.Protocol):
    def validate_links(self, doc_content: str) -> list[dict[str, str]]: ...

    def check_documentation_freshness(
        self,
        api_data: dict[str, t.Any],
        doc_paths: list[Path],
    ) -> dict[str, t.Any]: ...

    def validate_cross_references(
        self,
        docs: dict[str, str],
    ) -> list[dict[str, str]]: ...

    def calculate_coverage_metrics(
        self,
        api_data: dict[str, t.Any],
        existing_docs: dict[str, str],
    ) -> dict[str, float]: ...


@t.runtime_checkable
class LoggerProtocol(t.Protocol):
    def info(self, message: str, *args: t.Any, **kwargs: t.Any) -> None: ...

    def warning(self, message: str, *args: t.Any, **kwargs: t.Any) -> None: ...

    def error(self, message: str, *args: t.Any, **kwargs: t.Any) -> None: ...

    def debug(self, message: str, *args: t.Any, **kwargs: t.Any) -> None: ...

    def exception(self, message: str, *args: t.Any, **kwargs: t.Any) -> None: ...


@t.runtime_checkable
class ConfigManagerProtocol(t.Protocol):
    def get(self, key: str, default: t.Any = None) -> t.Any: ...

    def set(self, key: str, value: t.Any) -> None: ...

    def save(self) -> bool: ...

    def load(self) -> bool: ...


@t.runtime_checkable
class FileSystemServiceProtocol(t.Protocol):
    def read_file(self, path: str | Path) -> str: ...

    def write_file(self, path: str | Path, content: str) -> None: ...

    def exists(self, path: str | Path) -> bool: ...

    def mkdir(self, path: str | Path, parents: bool = False) -> None: ...

    def ensure_directory(self, path: str | Path) -> None: ...


@t.runtime_checkable
class SafeFileModifierProtocol(t.Protocol):
    def modify_file(self, file_path: Path, new_content: str) -> None: ...


@t.runtime_checkable
class EnhancedFileSystemServiceProtocol(ServiceProtocol, t.Protocol):
    def read_file(self, path: str | Path) -> str: ...

    def write_file(self, path: str | Path, content: str) -> None: ...

    async def read_file_async(self, path: Path) -> str: ...

    async def write_file_async(self, path: Path, content: str) -> None: ...

    async def read_multiple_files(self, paths: list[Path]) -> dict[Path, str]: ...

    async def write_multiple_files(self, file_data: dict[Path, str]) -> None: ...

    def file_exists(self, path: str | Path) -> bool: ...

    def create_directory(self, path: str | Path) -> None: ...

    def delete_file(self, path: str | Path) -> None: ...

    def list_files(self, path: str | Path, pattern: str = "*") -> t.Iterator[Path]: ...

    async def flush_operations(self) -> None: ...

    def get_cache_stats(self) -> dict[str, t.Any]: ...

    def clear_cache(self) -> None: ...

    def exists(self, path: str | Path) -> bool: ...

    def mkdir(self, path: str | Path, parents: bool = False) -> None: ...


@t.runtime_checkable
class AdapterProtocol(t.Protocol):
    @property
    def adapter_name(self) -> str: ...

    async def init(self) -> None: ...

    async def check(
        self,
        files: list[Path] | None = None,
        config: "QACheckConfig | None" = None,
    ) -> "QAResult": ...

    async def health_check(self) -> dict[str, t.Any]: ...


QAAdapterProtocol = AdapterProtocol


@t.runtime_checkable
class QAOrchestratorProtocol(t.Protocol):
    async def register_adapter(self, adapter: "QAAdapterProtocol") -> None: ...

    def get_adapter(self, name: str) -> "QAAdapterProtocol | None": ...

    async def run_checks(
        self,
        stage: str = "fast",
        files: list["Path"] | None = None,
    ) -> list["QAResult"]: ...

    async def run_all_checks(
        self,
        files: list["Path"] | None = None,
    ) -> dict[str, t.Any]: ...


@t.runtime_checkable
class AdapterFactoryProtocol(t.Protocol):
    def create_adapter(
        self,
        adapter_name: str,
        settings: t.Any | None = None,
    ) -> "AdapterProtocol": ...


@t.runtime_checkable
class DebuggerProtocol(t.Protocol):
    enabled: bool

    @contextlib.contextmanager
    def debug_operation(self, operation: str, **kwargs: t.Any) -> t.Iterator[str]: ...

    def log_agent_activity(
        self,
        agent_name: str,
        activity: str,
        issue_id: str | None = None,
        confidence: float | None = None,
        result: dict[str, t.Any] | None = None,
        metadata: dict[str, t.Any] | None = None,
    ) -> None: ...

    def log_mcp_operation(
        self,
        operation_type: str,
        tool_name: str,
        params: dict[str, t.Any] | None = None,
        result: dict[str, t.Any] | None = None,
    ) -> None: ...


@t.runtime_checkable
class AgentTrackerProtocol(t.Protocol):
    def register_agents(self, agent_types: list[str]) -> None: ...

    def track_agent_processing(
        self,
        agent_type: str,
        issue: "Issue",
        confidence: float,
    ) -> None: ...

    def track_agent_complete(
        self,
        agent_type: str,
        result: "FixResult",
    ) -> None: ...

    def set_coordinator_status(self, status: str) -> None: ...

    def reset(self) -> None: ...


@t.runtime_checkable
class AgentCoordinatorProtocol(t.Protocol):
    async def handle_issues(self, issues: list["Issue"]) -> "FixResult": ...

    def initialize_agents(self) -> None: ...


@t.runtime_checkable
class MemoryOptimizerProtocol(t.Protocol):
    def optimize_memory(self) -> None: ...

    def register_lazy_object(self, lazy_obj: t.Any) -> None: ...

    def get_stats(self) -> dict[str, t.Any]: ...


@t.runtime_checkable
class PluginRegistryProtocol(t.Protocol):
    def register_plugin(self, plugin: t.Any) -> None: ...

    def activate_plugin(self, plugin_name: str) -> None: ...

    def deactivate_plugin(self, plugin_name: str) -> None: ...

    def get_plugin(self, plugin_name: str) -> t.Any | None: ...

    def get_plugins_by_type(self, plugin_type: t.Any) -> list[t.Any]: ...

    def list_plugins(self) -> list[str]: ...


@t.runtime_checkable
class AgentRegistryProtocol(t.Protocol):
    async def register_agent(
        self,
        agent_name: str,
        agent_class: type[t.Any],
    ) -> None: ...

    def get_agent(self, agent_name: str) -> t.Any | None: ...

    def list_agents(self) -> list[str]: ...

    async def create_agent(self, agent_name: str, context: t.Any) -> t.Any: ...


@t.runtime_checkable
class ReflectionLoopProtocol(t.Protocol):
    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def trigger_reflection(self) -> dict[str, t.Any]: ...

    def get_metrics(self) -> dict[str, t.Any]: ...

    def is_running(self) -> bool: ...


@t.runtime_checkable
class ChangelogGeneratorProtocol(t.Protocol):
    def generate_changelog_from_commits(
        self,
        changelog_path: Path,
        version: str,
        since_version: str | None = None,
    ) -> bool: ...

    def update_changelog(
        self,
        entries: list[t.Any],
        version: str | None = None,
    ) -> None: ...


GitServiceProtocol = GitInterface


@t.runtime_checkable
class RegexPatternsProtocol(t.Protocol):
    def update_pyproject_version(self, content: str, version: str) -> str: ...


@t.runtime_checkable
class VersionAnalyzerProtocol(t.Protocol):
    async def recommend_version_bump(
        self,
        entries: list[t.Any] | None = None,
    ) -> t.Any: ...

    def display_recommendation(self, recommendation: t.Any) -> None: ...


if t.TYPE_CHECKING:
    from crackerjack.config.hooks import HookDefinition


@t.runtime_checkable
class AsyncCommandExecutorProtocol(t.Protocol):
    async def execute_command(
        self,
        command: list[str],
        cwd: Path | None = None,
        timeout: int = 60,
    ) -> "ExecutionResult": ...


@t.runtime_checkable
class CoverageBadgeServiceProtocol(t.Protocol):
    def update_badge(self, coverage_percentage: float) -> bool: ...

    def should_update_badge(self, coverage_percent: float) -> bool: ...

    def update_readme_coverage_badge(self, coverage_percent: float) -> bool: ...


if t.TYPE_CHECKING:
    from crackerjack.config.hooks import HookDefinition
    from crackerjack.models.results import ExecutionResult, ParallelExecutionResult


@t.runtime_checkable
class ParallelHookExecutorProtocol(t.Protocol):
    async def execute_hooks_parallel(
        self,
        hooks: "list[HookDefinition]",
        hook_runner: t.Callable[["HookDefinition"], t.Awaitable["ExecutionResult"]],
    ) -> "ParallelExecutionResult": ...


@t.runtime_checkable
class HookExecutorProtocol(t.Protocol):
    def execute_strategy(
        self,
        strategy: t.Any,
    ) -> t.Any: ...

    def set_progress_callbacks(
        self,
        *,
        started_cb: t.Callable[[int, int], None] | None = None,
        completed_cb: t.Callable[[int, int], None] | None = None,
        total: int | None = None,
    ) -> None: ...


@t.runtime_checkable
class AsyncHookExecutorProtocol(t.Protocol):
    async def execute_strategy(
        self,
        strategy: t.Any,
    ) -> t.Any: ...


@t.runtime_checkable
class HookConfigLoaderProtocol(t.Protocol):
    def load_strategy(
        self,
        name: str,
        config_path: Path | None = None,
    ) -> t.Any: ...


@t.runtime_checkable
class PerformanceCacheProtocol(t.Protocol):
    def get(self, key: str) -> t.Any | None: ...

    def set(self, key: str, value: t.Any, ttl_seconds: int = 0) -> None: ...


@t.runtime_checkable
class QualityBaselineProtocol(t.Protocol):
    def get_baseline(self, git_hash: str | None = None) -> t.Any: ...

    def update_baseline(self, metrics: dict[str, t.Any]) -> bool: ...


@t.runtime_checkable
class QualityIntelligenceProtocol(t.Protocol):
    def analyze_trends(self, data: list[t.Any]) -> dict[str, t.Any]: ...


@t.runtime_checkable
class SecureStatusFormatterProtocol(t.Protocol):
    def format(self, status: t.Any) -> str: ...


@t.runtime_checkable
class SmartFileFilterProtocol(t.Protocol):
    def should_include(self, file_path: Path) -> bool: ...

    def filter_files(self, files: list[Path]) -> list[Path]: ...


@t.runtime_checkable
class SecureSubprocessExecutorProtocol(t.Protocol):
    allowed_git_patterns: list[str]

    def execute_secure(
        self,
        command: list[str],
        cwd: Path | str | None = None,
        env: dict[str, str] | None = None,
        timeout: float | None = None,
        input_data: str | bytes | None = None,
        capture_output: bool = True,
        text: bool = True,
        check: bool = False,
        **kwargs: t.Any,
    ) -> subprocess.CompletedProcess[str]: ...


@t.runtime_checkable
class AgentDelegatorProtocol(t.Protocol):
    if TYPE_CHECKING:

        async def delegate_to_type_specialist(
            self,
            issue: "Issue",
            context: "AgentContext",
        ) -> "FixResult": ...

        async def delegate_to_dead_code_remover(
            self,
            issue: "Issue",
            context: "AgentContext",
            confidence: float = 0.8,
        ) -> "FixResult": ...

        async def delegate_to_refurb_transformer(
            self,
            issue: "Issue",
            context: "AgentContext",
            refurb_code: str | None = None,
        ) -> "FixResult": ...

        async def delegate_to_performance_optimizer(
            self,
            issue: "Issue",
            context: "AgentContext",
        ) -> "FixResult": ...

        async def delegate_batch(
            self,
            issues: list["Issue"],
            context: "AgentContext",
        ) -> list["FixResult"]: ...

        def get_delegation_metrics(self) -> dict[str, t.Any]: ...


class DelegationMetrics(t.TypedDict):
    total_delegations: int
    successful_delegations: int
    failed_delegations: int
    average_latency_ms: float
    cache_hit_rate: float
    agents_used: dict[str, int]


@t.runtime_checkable
class MCPIntegrationProtocol(t.Protocol):
    if TYPE_CHECKING:

        async def search_regex(
            self,
            pattern: str,
            file_pattern: str | None = None,
        ) -> list[dict[str, t.Any]]: ...

        async def replace_text_in_file(
            self,
            file_path: str,
            search_text: str,
            replace_text: str,
        ) -> bool: ...

        async def get_file_problems(
            self,
            file_path: str,
            errors_only: bool = False,
        ) -> list[dict[str, t.Any]]: ...

        def is_available(self) -> bool: ...
