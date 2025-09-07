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
    """Security-aware hook manager that tracks security-critical failures."""

    def get_security_critical_failures(self, results: list[t.Any]) -> list[t.Any]:
        """Extract security-critical failures from hook results.

        Args:
            results: List of hook results from run_fast_hooks or run_comprehensive_hooks

        Returns:
            List of results that are security-critical and failed
        """
        ...

    def has_security_critical_failures(self, results: list[t.Any]) -> bool:
        """Check if any security-critical hooks failed.

        Args:
            results: List of hook results

        Returns:
            True if any CRITICAL security level hooks failed
        """
        ...

    def get_security_audit_report(
        self, fast_results: list[t.Any], comprehensive_results: list[t.Any]
    ) -> dict[str, t.Any]:
        """Generate security audit report for publishing decisions.

        Args:
            fast_results: Results from fast hooks
            comprehensive_results: Results from comprehensive hooks

        Returns:
            Dict containing security status, failed critical checks, and recommendations
        """
        ...


@t.runtime_checkable
class CoverageRatchetProtocol(t.Protocol):
    """Protocol for coverage ratchet service."""

    def get_baseline_coverage(self) -> float: ...

    def update_baseline_coverage(self, new_coverage: float) -> bool: ...

    def is_coverage_regression(self, current_coverage: float) -> bool: ...

    def get_coverage_improvement_needed(self) -> float: ...

    def get_status_report(self) -> dict[str, t.Any]: ...

    def get_coverage_report(self) -> str | None: ...

    def check_and_update_coverage(self) -> dict[str, t.Any]: ...


@t.runtime_checkable
class ConfigurationServiceProtocol(t.Protocol):
    """Protocol for configuration service."""

    def update_precommit_config(self, options: OptionsProtocol) -> bool: ...

    def update_pyproject_config(self, options: OptionsProtocol) -> bool: ...

    def get_temp_config_path(self) -> str | None: ...


@t.runtime_checkable
class SecurityServiceProtocol(t.Protocol):
    """Protocol for security service."""

    def validate_file_safety(self, path: str | Path) -> bool: ...

    def check_hardcoded_secrets(self, content: str) -> list[dict[str, t.Any]]: ...

    def is_safe_subprocess_call(self, cmd: list[str]) -> bool: ...

    def create_secure_command_env(self) -> dict[str, str]: ...

    def mask_tokens(self, text: str) -> str: ...

    def validate_token_format(self, token: str, token_type: str) -> bool: ...


@t.runtime_checkable
class InitializationServiceProtocol(t.Protocol):
    """Protocol for initialization service."""

    def initialize_project(self, project_path: str | Path) -> bool: ...

    def validate_project_structure(self) -> bool: ...

    def setup_git_hooks(self) -> bool: ...


@t.runtime_checkable
class UnifiedConfigurationServiceProtocol(t.Protocol):
    """Protocol for unified configuration service."""

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
    """Protocol for smart configuration file merging."""

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
    """Protocol for managing hook-specific locks to prevent concurrent execution."""

    def requires_lock(self, hook_name: str) -> bool:
        """Check if a hook requires sequential execution.

        Args:
            hook_name: Name of the hook to check

        Returns:
            True if the hook requires a lock for sequential execution
        """
        ...

    async def acquire_hook_lock(self, hook_name: str) -> t.AsyncContextManager[None]:
        """Acquire a lock for the specified hook if it requires one.

        Args:
            hook_name: Name of the hook to lock

        Returns:
            Async context manager for lock acquisition
        """
        ...

    def get_lock_stats(self) -> dict[str, t.Any]:
        """Get statistics about lock usage for monitoring.

        Returns:
            Dict containing lock statistics per hook
        """
        ...

    def add_hook_to_lock_list(self, hook_name: str) -> None:
        """Add a hook to the list requiring sequential execution.

        Args:
            hook_name: Name of the hook to add
        """
        ...

    def remove_hook_from_lock_list(self, hook_name: str) -> None:
        """Remove a hook from the list requiring sequential execution.

        Args:
            hook_name: Name of the hook to remove
        """
        ...

    def is_hook_currently_locked(self, hook_name: str) -> bool:
        """Check if a hook is currently locked.

        Args:
            hook_name: Name of the hook to check

        Returns:
            True if the hook is currently locked
        """
        ...

    def enable_global_lock(self, enabled: bool = True) -> None:
        """Enable or disable global lock functionality.

        Args:
            enabled: Whether to enable global locking
        """
        ...

    def is_global_lock_enabled(self) -> bool:
        """Check if global lock functionality is enabled.

        Returns:
            True if global locking is enabled
        """
        ...

    def get_global_lock_path(self, hook_name: str) -> Path:
        """Get the filesystem path for a hook's global lock file.

        Args:
            hook_name: Name of the hook

        Returns:
            Path to the lock file for the hook
        """
        ...

    def cleanup_stale_locks(self, max_age_hours: float = 2.0) -> int:
        """Clean up stale lock files older than max_age_hours.

        Args:
            max_age_hours: Maximum age in hours before a lock is considered stale

        Returns:
            Number of stale locks cleaned up
        """
        ...

    def get_global_lock_stats(self) -> dict[str, t.Any]:
        """Get comprehensive statistics about global lock usage.

        Returns:
            Dictionary containing global lock statistics and metrics
        """
        ...
