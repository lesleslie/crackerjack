import subprocess
import typing as t
from pathlib import Path


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
    test_workers: int = 0
    test_timeout: int = 0
    publish: t.Any | None
    bump: t.Any | None
    all: t.Any | None
    ai_agent: bool = False
    start_mcp_server: bool = False
    create_pr: bool = False
    skip_hooks: bool = False
    update_precommit: bool = False
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
    enterprise_batch: str | None = None
    monitor_dashboard: str | None = None
    skip_config_merge: bool = False
    disable_global_locks: bool = False
    global_lock_timeout: int = 600
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

    def get_staged_files(self) -> list[str]: ...

    def commit(self, message: str) -> bool: ...

    def push(self) -> bool: ...

    def add_files(self, files: list[str]) -> bool: ...

    def add_all_files(self) -> bool: ...

    def get_commit_message_suggestions(self, changed_files: list[str]) -> list[str]: ...

    def get_unpushed_commit_count(self) -> int: ...


@t.runtime_checkable
class HookManager(t.Protocol):
    def run_fast_hooks(self) -> list[t.Any]: ...

    def run_comprehensive_hooks(self) -> list[t.Any]: ...

    def install_hooks(self) -> bool: ...

    def set_config_path(self, path: str | t.Any) -> None: ...

    def get_hook_summary(self, results: t.Any) -> t.Any: ...


@t.runtime_checkable
class SecurityAwareHookManager(HookManager, t.Protocol):
    def get_security_critical_failures(self, results: list[t.Any]) -> list[t.Any]: ...

    def has_security_critical_failures(self, results: list[t.Any]) -> bool: ...

    def get_security_audit_report(
        self, fast_results: list[t.Any], comprehensive_results: list[t.Any]
    ) -> dict[str, t.Any]: ...


@t.runtime_checkable
class CoverageRatchetProtocol(t.Protocol):
    def get_baseline_coverage(self) -> float: ...

    def update_baseline_coverage(self, new_coverage: float) -> bool: ...

    def is_coverage_regression(self, current_coverage: float) -> bool: ...

    def get_coverage_improvement_needed(self) -> float: ...

    def get_status_report(self) -> dict[str, t.Any]: ...

    def get_coverage_report(self) -> str | None: ...

    def check_and_update_coverage(self) -> dict[str, t.Any]: ...


@t.runtime_checkable
class ConfigurationServiceProtocol(t.Protocol):
    def update_precommit_config(self, options: OptionsProtocol) -> bool: ...

    def update_pyproject_config(self, options: OptionsProtocol) -> bool: ...

    def get_temp_config_path(self) -> str | None: ...


@t.runtime_checkable
class SecurityServiceProtocol(t.Protocol):
    def validate_file_safety(self, path: str | Path) -> bool: ...

    def check_hardcoded_secrets(self, content: str) -> list[dict[str, t.Any]]: ...

    def is_safe_subprocess_call(self, cmd: list[str]) -> bool: ...

    def create_secure_command_env(self) -> dict[str, str]: ...

    def mask_tokens(self, text: str) -> str: ...

    def validate_token_format(self, token: str, token_type: str) -> bool: ...


@t.runtime_checkable
class InitializationServiceProtocol(t.Protocol):
    def initialize_project(self, project_path: str | Path) -> bool: ...

    def validate_project_structure(self) -> bool: ...

    def setup_git_hooks(self) -> bool: ...


@t.runtime_checkable
class UnifiedConfigurationServiceProtocol(t.Protocol):
    def merge_configurations(self) -> dict[str, t.Any]: ...

    def validate_configuration(self, config: dict[str, t.Any]) -> bool: ...

    def get_merged_config(self) -> dict[str, t.Any]: ...


@t.runtime_checkable
class TestManagerProtocol(t.Protocol):
    def run_tests(self, options: OptionsProtocol) -> bool: ...

    def get_test_failures(self) -> list[str]: ...

    def validate_test_environment(self) -> bool: ...

    def get_coverage(self) -> dict[str, t.Any]: ...


@t.runtime_checkable
class PublishManager(t.Protocol):
    def bump_version(self, version_type: str) -> str: ...

    def publish_package(self) -> bool: ...

    def validate_auth(self) -> bool: ...

    def create_git_tag(self, version: str) -> bool: ...

    def cleanup_old_releases(self, keep_releases: int) -> None: ...


@t.runtime_checkable
class ConfigMergeServiceProtocol(t.Protocol):
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

    async def acquire_hook_lock(
        self, hook_name: str
    ) -> t.AsyncContextManager[None]: ...

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
class DocumentationServiceProtocol(t.Protocol):
    """Service for automated documentation generation and maintenance."""

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
    """Protocol for extracting API documentation from source code."""

    def extract_from_python_files(self, files: list[Path]) -> dict[str, t.Any]: ...

    def extract_protocol_definitions(self, protocol_file: Path) -> dict[str, t.Any]: ...

    def extract_service_interfaces(
        self, service_files: list[Path]
    ) -> dict[str, t.Any]: ...

    def extract_cli_commands(self, cli_files: list[Path]) -> dict[str, t.Any]: ...

    def extract_mcp_tools(self, mcp_files: list[Path]) -> dict[str, t.Any]: ...


@t.runtime_checkable
class DocumentationGeneratorProtocol(t.Protocol):
    """Protocol for generating documentation from extracted data."""

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
    """Protocol for validating documentation quality and consistency."""

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
    """Protocol for structured logging interface."""

    def info(self, message: str, **kwargs: t.Any) -> None: ...

    def warning(self, message: str, **kwargs: t.Any) -> None: ...

    def error(self, message: str, **kwargs: t.Any) -> None: ...

    def debug(self, message: str, **kwargs: t.Any) -> None: ...


@t.runtime_checkable
class ConfigManagerProtocol(t.Protocol):
    """Protocol for configuration management."""

    def get(self, key: str, default: t.Any = None) -> t.Any: ...

    def set(self, key: str, value: t.Any) -> None: ...

    def save(self) -> bool: ...

    def load(self) -> bool: ...


@t.runtime_checkable
class FileSystemServiceProtocol(t.Protocol):
    """Protocol for file system operations."""

    def read_file(self, path: str | Path) -> str: ...

    def write_file(self, path: str | Path, content: str) -> None: ...

    def exists(self, path: str | Path) -> bool: ...

    def mkdir(self, path: str | Path, parents: bool = False) -> None: ...

    def ensure_directory(self, path: str | Path) -> None: ...
