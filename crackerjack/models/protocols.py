import subprocess
import typing as t
from pathlib import Path
from typing import TYPE_CHECKING

from crackerjack.config.hooks import HookDefinition
from crackerjack.config.settings import CrackerjackSettings
from crackerjack.models.results import ExecutionResult, ParallelExecutionResult


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
    commit: bool
    interactive: bool
    no_config_updates: bool
    verbose: bool
    clean: bool
    test: bool
    benchmark: bool
    benchmark_regression: bool = False
    benchmark_regression_threshold: float = 0.1
    test_workers: int = 0
    test_timeout: int = 0
    publish: t.Any | None
    bump: t.Any | None
    all: t.Any | None
    ai_agent: bool = False
    start_mcp_server: bool = False
    create_pr: bool = False
    skip_hooks: bool = False
    async_mode: bool = False
    experimental_hooks: bool = False
    enable_pyrefly: bool = False
    enable_ty: bool = False
    cleanup: t.Any | None = None
    no_git_tags: bool = False
    skip_version_check: bool = False
    cleanup_pypi: bool = False
    coverage: bool = False
    keep_releases: int = 10
    track_progress: bool = False
    fast: bool = False
    comp: bool = False
    fast_iteration: bool = False
    tool: str | None = None
    changed_only: bool = False
    advanced_batch: str | None = None
    monitor_dashboard: str | None = None
    skip_config_merge: bool = False
    disable_global_locks: bool = False
    global_lock_timeout: int = 600
    strip_code: bool = False
    run_tests: bool = False
    global_lock_cleanup: bool = True
    global_lock_dir: str | None = None
    generate_docs: bool = False
    docs_format: str = "markdown"
    validate_docs: bool = False
    update_docs_index: bool = False


@t.runtime_checkable
class ConsoleInterface(t.Protocol):
    def print(self, *args: t.Any, **kwargs: t.Any) -> None: ...

    def input(self, _: str = "") -> str: ...

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

        def push_with_tags(self) -> bool: ...

        def get_commit_message_suggestions(
            self, changed_files: list[str]
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
        self, results: t.Any, elapsed_time: float | None = None
    ) -> t.Any: ...

    if TYPE_CHECKING:

        def get_hook_count(self, suite_name: str) -> int: ...

        _progress_callback: t.Callable[[int, int], None] | None
        _progress_start_callback: t.Callable[[int, int], None] | None


@t.runtime_checkable
class SecurityAwareHookManager(HookManager, t.Protocol):
    def get_security_critical_failures(self, results: list[t.Any]) -> list[t.Any]: ...

    def has_security_critical_failures(self, results: list[t.Any]) -> bool: ...

    def get_security_audit_report(
        self, fast_results: list[t.Any], comprehensive_results: list[t.Any]
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
        self, source_paths: list[Path]
    ) -> dict[str, t.Any]: ...

    def generate_documentation(
        self, template_name: str, context: dict[str, t.Any]
    ) -> str: ...

    def validate_documentation(self, doc_paths: list[Path]) -> list[dict[str, str]]: ...

    def update_documentation_index(self) -> bool: ...

    def get_documentation_coverage(self) -> dict[str, t.Any]: ...


@t.runtime_checkable
class APIExtractorProtocol(t.Protocol):
    def extract_from_python_files(self, files: list[Path]) -> dict[str, t.Any]: ...

    def extract_protocol_definitions(self, protocol_file: Path) -> dict[str, t.Any]: ...

    def extract_service_interfaces(
        self, service_files: list[Path]
    ) -> dict[str, t.Any]: ...

    def extract_cli_commands(self, cli_files: list[Path]) -> dict[str, t.Any]: ...

    def extract_mcp_tools(self, mcp_files: list[Path]) -> dict[str, t.Any]: ...


@t.runtime_checkable
class DocumentationGeneratorProtocol(t.Protocol):
    def generate_api_reference(self, api_data: dict[str, t.Any]) -> str: ...

    def generate_user_guide(self, template_context: dict[str, t.Any]) -> str: ...

    def generate_changelog_update(
        self, version: str, changes: dict[str, t.Any]
    ) -> str: ...

    def render_template(
        self, template_path: Path, context: dict[str, t.Any]
    ) -> str: ...

    def generate_cross_references(
        self, api_data: dict[str, t.Any]
    ) -> dict[str, list[str]]: ...


@t.runtime_checkable
class DocumentationValidatorProtocol(t.Protocol):
    def validate_links(self, doc_content: str) -> list[dict[str, str]]: ...

    def check_documentation_freshness(
        self, api_data: dict[str, t.Any], doc_paths: list[Path]
    ) -> dict[str, t.Any]: ...

    def validate_cross_references(
        self, docs: dict[str, str]
    ) -> list[dict[str, str]]: ...

    def calculate_coverage_metrics(
        self, api_data: dict[str, t.Any], existing_docs: dict[str, str]
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
class QAAdapterProtocol(t.Protocol):
    settings: t.Any | None

    async def init(self) -> None: ...

    async def check(
        self,
        files: list[Path] | None = None,
        config: t.Any | None = None,
    ) -> t.Any: ...

    async def validate_config(self, config: t.Any) -> bool: ...

    def get_default_config(self) -> t.Any: ...

    async def health_check(self) -> dict[str, t.Any]: ...

    @property
    def adapter_name(self) -> str: ...

    @property
    def module_id(self) -> t.Any: ...


@t.runtime_checkable
class QAOrchestratorProtocol(t.Protocol):
    async def run_checks(
        self,
        stage: str = "fast",
        files: list[Path] | None = None,
    ) -> list[t.Any]: ...

    async def run_all_checks(
        self,
        files: list[Path] | None = None,
    ) -> dict[str, t.Any]: ...

    def register_adapter(self, adapter: QAAdapterProtocol) -> None: ...

    def get_adapter(self, name: str) -> QAAdapterProtocol | None: ...


@t.runtime_checkable
class ExecutionStrategyProtocol(t.Protocol):
    async def execute(
        self,
        hooks: list[t.Any],
        max_parallel: int = 3,
        timeout: int = 300,
    ) -> list[t.Any]: ...

    def get_execution_order(
        self,
        hooks: list[t.Any],
    ) -> list[list[t.Any]]: ...


@t.runtime_checkable
class CacheStrategyProtocol(t.Protocol):
    async def get(self, key: str) -> t.Any | None: ...

    async def set(self, key: str, result: t.Any, ttl: int = 3600) -> None: ...

    def compute_key(self, hook: t.Any, files: list[Path]) -> str: ...


@t.runtime_checkable
class HookOrchestratorProtocol(t.Protocol):
    async def init(self) -> None: ...

    async def execute_strategy(
        self,
        strategy: t.Any,
        execution_mode: str | None = None,
        execution_context: t.Any | None = None,
    ) -> list[t.Any]: ...

    @property
    def module_id(self) -> t.Any: ...

    @property
    def adapter_name(self) -> str: ...


@t.runtime_checkable
class PerformanceMonitorProtocol(t.Protocol):
    def start_workflow(self, workflow_id: str) -> None: ...

    def end_workflow(self, workflow_id: str, success: bool = True) -> t.Any: ...

    def start_phase(self, workflow_id: str, phase_name: str) -> None: ...

    def end_phase(
        self, workflow_id: str, phase_name: str, success: bool = True
    ) -> t.Any: ...

    def get_performance_summary(
        self, last_n_workflows: int = 10
    ) -> dict[str, t.Any]: ...

    def get_benchmark_trends(self) -> dict[str, dict[str, t.Any]]: ...


@t.runtime_checkable
class MemoryOptimizerProtocol(t.Protocol):
    def record_checkpoint(self, name: str = "") -> float: ...

    def get_stats(self) -> dict[str, t.Any]: ...


@t.runtime_checkable
class PerformanceCacheProtocol(t.Protocol):
    def get(self, key: str) -> ExecutionResult | None: ...

    def set(self, key: str, value: ExecutionResult, ttl: int = 3600) -> None: ...

    def invalidate(self, key: str) -> bool: ...

    def clear_all(self) -> None: ...


@t.runtime_checkable
class QualityBaselineProtocol(t.Protocol):
    def get_current_baseline(self) -> dict[str, t.Any]: ...

    def update_baseline(self, metrics: dict[str, t.Any]) -> bool: ...

    def compare(self, current: dict[str, t.Any]) -> dict[str, t.Any]: ...


@t.runtime_checkable
class ParallelExecutorProtocol(t.Protocol):
    async def execute_parallel(
        self,
        tasks: list[t.Any],
        max_workers: int = 3,
    ) -> list[t.Any]: ...

    def get_results(self) -> list[t.Any]: ...


@t.runtime_checkable
class ParallelHookExecutorProtocol(ServiceProtocol, t.Protocol):
    async def execute_hooks_parallel(
        self,
        hooks: list[HookDefinition],
        hook_runner: t.Callable[[HookDefinition], t.Awaitable[ExecutionResult]],
    ) -> ParallelExecutionResult: ...


@t.runtime_checkable
class AsyncCommandExecutorProtocol(ServiceProtocol, t.Protocol):
    async def execute_command(
        self,
        command: list[str],
        cwd: Path | None = None,
        timeout: int = 60,
        cache_ttl: int = 120,
    ) -> ExecutionResult: ...

    async def execute_commands_batch(
        self,
        commands: list[tuple[list[str], Path | None]],
        timeout: int = 60,
    ) -> list[ExecutionResult]: ...


@t.runtime_checkable
class PerformanceBenchmarkProtocol(t.Protocol):
    def run_benchmark(self, operation: str) -> dict[str, t.Any]: ...

    def get_report(self) -> dict[str, t.Any]: ...

    def compare_benchmarks(
        self,
        baseline: dict[str, t.Any],
        current: dict[str, t.Any],
    ) -> dict[str, t.Any]: ...


@t.runtime_checkable
class PerformanceBenchmarkServiceProtocol(ServiceProtocol, t.Protocol):
    async def run_benchmark_suite(self) -> t.Any | None: ...

    def export_results(self, suite: t.Any, output_path: Path) -> None: ...


@t.runtime_checkable
class DebugServiceProtocol(ServiceProtocol, t.Protocol):
    def start_debug_session(self, session_id: str) -> None: ...

    @property
    def enabled(self) -> bool: ...

    def log_workflow_phase(
        self,
        phase: str,
        status: str,
        details: dict[str, t.Any] | None = None,
        duration: float | None = None,
    ) -> None: ...

    def set_workflow_success(self, success: bool) -> None: ...

    def print_debug_summary(self) -> None: ...

    def log_iteration_start(self, iteration_number: int) -> None: ...

    def log_iteration_end(self, iteration_number: int, success: bool) -> None: ...

    def log_test_failures(self, count: int) -> None: ...

    def log_test_fixes(self, count: int) -> None: ...

    def log_hook_failures(self, count: int) -> None: ...

    def log_hook_fixes(self, count: int) -> None: ...


@t.runtime_checkable
class QualityIntelligenceProtocol(ServiceProtocol, t.Protocol):
    def analyze_quality_trends(self) -> dict[str, t.Any]: ...

    def predict_quality_issues(self) -> list[dict[str, t.Any]]: ...

    def recommend_improvements(self) -> list[dict[str, t.Any]]: ...

    def get_intelligence_report(self) -> dict[str, t.Any]: ...


@t.runtime_checkable
class CoverageRatchetServiceProtocol(ServiceProtocol, t.Protocol):
    def get_current_coverage(self) -> float: ...

    def get_coverage_history(self) -> list[dict[str, t.Any]]: ...

    def check_coverage_increase(self) -> bool: ...

    def get_next_milestone(self) -> float | None: ...

    def update_coverage_baseline(self, new_baseline: float) -> bool: ...


@t.runtime_checkable
class ServerManagerProtocol(ServiceProtocol, t.Protocol):
    def find_processes(self, process_name: str) -> list[dict[str, t.Any]]: ...

    def start_server(self, command: list[str]) -> bool: ...

    def stop_server(self, process_id: int) -> bool: ...

    def restart_server(self, command: list[str]) -> bool: ...

    def get_server_status(self) -> dict[str, t.Any]: ...


@t.runtime_checkable
class LogManagementProtocol(ServiceProtocol, t.Protocol):
    def get_log_manager(self) -> t.Any: ...

    def setup_structured_logging(
        self,
        *,
        level: str = "INFO",
        json_output: bool = False,
        log_file: Path | None = None,
    ) -> None: ...

    def write_log(self, message: str, level: str = "INFO") -> None: ...

    def get_logs(
        self, filter_criteria: dict[str, t.Any] | None = None
    ) -> list[dict[str, t.Any]]: ...


@t.runtime_checkable
class RegexPatternsProtocol(t.Protocol):
    def update_pyproject_version(self, content: str, new_version: str) -> str: ...

    def remove_coverage_fail_under(self, content: str) -> str: ...

    def update_version_in_changelog(self, content: str, new_version: str) -> str: ...

    def mask_tokens_in_text(self, text: str) -> str: ...


@t.runtime_checkable
class SecureStatusFormatterProtocol(t.Protocol):
    def format_status(
        self,
        status_data: dict[str, t.Any],
        verbosity: t.Any,
        user_context: str | None = None,
    ) -> dict[str, t.Any]: ...

    def format_error_response(
        self,
        error_message: str,
        verbosity: t.Any,
        include_details: bool = False,
    ) -> dict[str, t.Any]: ...


@t.runtime_checkable
class GitServiceProtocol(t.Protocol):
    def get_current_branch(self) -> str: ...

    def get_commit_history(self, since_commit: str | None = None) -> list[str]: ...

    def create_new_branch(self, branch_name: str) -> bool: ...

    def commit_changes(self, message: str) -> bool: ...

    def push_changes(self) -> bool: ...

    def create_pull_request(self, title: str, body: str) -> bool: ...

    def get_changed_files_since(self, since: str, project_root: Path) -> list[str]: ...

    def get_staged_files(self) -> list[str]: ...

    def get_unstaged_files(self, project_root: Path) -> list[Path]: ...


@t.runtime_checkable
class SmartFileFilterProtocol(ServiceProtocol, t.Protocol):
    def get_changed_files(self, since: str = "HEAD") -> list[Path]: ...

    def get_staged_files(self) -> list[Path]: ...

    def get_unstaged_files(self) -> list[Path]: ...

    def filter_by_pattern(self, files: list[Path], pattern: str) -> list[Path]: ...

    def filter_by_tool(self, files: list[Path], tool: str) -> list[Path]: ...

    def get_all_modified_files(self) -> list[Path]: ...

    def filter_by_extensions(
        self, files: list[Path], extensions: list[str]
    ) -> list[Path]: ...

    def get_python_files(self, files: list[Path]) -> list[Path]: ...

    def get_markdown_files(self, files: list[Path]) -> list[Path]: ...


@t.runtime_checkable
class SafeFileModifierProtocol(ServiceProtocol, t.Protocol):
    async def apply_fix(
        self,
        file_path: str,
        fixed_content: str,
        dry_run: bool = False,
        create_backup: bool = True,
    ) -> dict[str, t.Any]: ...


@t.runtime_checkable
class VersionAnalyzerProtocol(t.Protocol):
    async def recommend_version_bump(
        self, since_version: str | None = None
    ) -> t.Any: ...


@t.runtime_checkable
class HealthMetricsServiceProtocol(ServiceProtocol, t.Protocol):
    def collect_current_metrics(self) -> t.Any: ...

    def analyze_project_health(self, save_metrics: bool = True) -> t.Any: ...

    def report_health_status(self, health: t.Any) -> None: ...

    def get_health_trend_summary(self, days: int = 30) -> dict[str, t.Any]: ...


@t.runtime_checkable
class ChangelogGeneratorProtocol(t.Protocol):
    def generate_changelog_from_commits(
        self, changelog_path: Path, version: str, since_version: str | None = None
    ) -> bool: ...


@t.runtime_checkable
class CoverageBadgeServiceProtocol(ServiceProtocol, t.Protocol):
    def update_readme_coverage_badge(self, coverage_percent: float) -> bool: ...

    def should_update_badge(self, coverage_percent: float) -> bool: ...


@t.runtime_checkable
class AgentCoordinatorProtocol(ServiceProtocol, t.Protocol):
    def initialize_agents(self) -> None: ...

    async def handle_issues(self, issues: list[t.Any]) -> t.Any: ...

    async def handle_issues_proactively(self, issues: list[t.Any]) -> t.Any: ...

    def get_agent_capabilities(self) -> dict[str, dict[str, t.Any]]: ...

    def set_proactive_mode(self, enabled: bool) -> None: ...


@t.runtime_checkable
class AgentTrackerProtocol(t.Protocol):
    def register_agents(self, agent_types: list[str]) -> None: ...

    def set_coordinator_status(self, status: str) -> None: ...

    def track_agent_processing(
        self, agent_name: str, issue: t.Any, confidence: float
    ) -> None: ...

    def track_agent_complete(self, agent_name: str, result: t.Any) -> None: ...

    def get_agent_stats(self) -> dict[str, t.Any]: ...


@t.runtime_checkable
class AgentDebuggerProtocol(t.Protocol):
    def log_agent_activity(
        self,
        agent_name: str,
        activity: str,
        **metadata: t.Any,
    ) -> None: ...

    def get_activity_log(
        self, agent_name: str | None = None, limit: int = 100
    ) -> list[dict[str, t.Any]]: ...

    def enable_verbose_mode(self, enabled: bool = True) -> None: ...


@t.runtime_checkable
class ServiceWatchdogProtocol(ServiceProtocol, t.Protocol):
    def register_service(self, config: t.Any) -> None: ...

    async def start(self) -> None: ...

    async def stop(self) -> None: ...

    async def restart_service(self, service_name: str) -> bool: ...

    def get_service_status(self, service_name: str) -> t.Any | None: ...

    def get_all_services_status(self) -> dict[str, t.Any]: ...

    async def check_service_health(self, service_name: str) -> bool: ...


@t.runtime_checkable
class TimeoutManagerProtocol(t.Protocol):
    def get_timeout(self, operation: str) -> float: ...

    def set_timeout(self, operation: str, timeout: float) -> None: ...

    def get_strategy(self, operation: str) -> t.Any: ...

    def apply_timeout(
        self,
        operation: str,
        func: t.Callable[..., t.Any],
        *args: t.Any,
        **kwargs: t.Any,
    ) -> t.Any: ...
