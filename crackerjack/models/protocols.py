"""Protocol definitions for crackerjack's protocol-based architecture.

This module defines 61 protocols with 278 methods that form the foundation of
crackerjack's modular, loosely-coupled architecture. Protocols enable
structural subtyping (duck typing with type safety) without requiring
inheritance.

Key Design Principles:
    - Protocol-based dependency injection
    - Loose coupling between components
    - Easy testing with mock implementations
    - Clear interface contracts
    - Runtime type safety with @runtime_checkable

Usage:
    Import protocols from this module for type hints and compliance checks.
    Never import concrete classes when protocols are available.

Example:
    from crackerjack.models.protocols import ServiceProtocol, ConsoleInterface

    def use_service(service: ServiceProtocol) -> None:
        service.initialize()
        try:
            service.do_work()
        finally:
            service.cleanup()

Protocol Categories:
    1. Core Infrastructure (5): ServiceProtocol, CommandRunner, OptionsProtocol, etc.
    2. Service Extensions (23): TestManagerProtocol, CoverageRatchetProtocol, etc.
    3. Quality Assurance (5): QAAdapterProtocol, QAOrchestratorProtocol, etc.
    4. Hook Management (4): HookManager, SecurityAwareHookManager, etc.
    5. Performance & Monitoring (8): PerformanceMonitorProtocol, etc.
    6. Documentation System (4): APIExtractorProtocol, DocumentationGeneratorProtocol, etc.
    7. Agent System (3): AgentTrackerProtocol, AgentDebuggerProtocol, etc.
    8. Git Operations (2): GitInterface, GitServiceProtocol
    9. Utility Protocols (7): LoggerProtocol, ConfigManagerProtocol, etc.

See Also:
    - Protocol Reference Guide: docs/reference/PROTOCOL_REFERENCE_GUIDE.md
    - Architecture Documentation: CLAUDE.md
"""

import contextlib
import subprocess
import typing as t
from pathlib import Path
from typing import TYPE_CHECKING

from crackerjack.config.settings import CrackerjackSettings

if t.TYPE_CHECKING:
    from crackerjack.agents.base import FixResult, Issue
    from crackerjack.models.qa_results import QAResult
    from crackerjack.services.backup_service import BackupMetadata
    from crackerjack.services.documentation_cleanup import DocumentationCleanupResult


# =============================================================================
# CORE INFRASTRUCTURE PROTOCOLS (5 protocols)
# =============================================================================


@t.runtime_checkable
class ServiceProtocol(t.Protocol):
    """Base protocol for all long-lived services in crackerjack.

    Services are objects that provide functionality to other components and
    require lifecycle management (initialization, cleanup, health monitoring).

    Lifecycle:
        1. Service is instantiated via constructor injection
        2. initialize() is called once to set up resources
        3. Service operates until cleanup() is called
        4. cleanup() releases all resources
        5. shutdown() performs graceful shutdown

    Thread Safety:
        Implementation-dependent. Services must document their thread safety.

    Common Implementations:
        - TestManager: Test execution service
        - CoverageRatchet: Coverage tracking service
        - SecurityService: Security checking service

    Example:
        class MyService:
            def __init__(self, config: Config) -> None:
                self.config = config
                self._initialized = False

            def initialize(self) -> None:
                if not self._initialized:
                    self._setup_resources()
                    self._initialized = True

            def cleanup(self) -> None:
                if self._initialized:
                    self._release_resources()
                    self._initialized = False

            def health_check(self) -> bool:
                return self._initialized
    """

    def initialize(self) -> None:
        """Initialize the service and set up resources.

        This method is called once after the service is instantiated.
        It should be idempotent - calling it multiple times should have
        no adverse effects.

        Raises:
            RuntimeError: If initialization fails.
            TimeoutError: If initialization times out.
        """
        ...

    def cleanup(self) -> None:
        """Clean up resources used by the service.

        This method is called when the service is no longer needed.
        It should release all resources (file handles, network connections,
        thread pools, etc.) and bring the service to a clean state.

        After cleanup() is called, the service should not be used again
        unless initialize() is called first.

        Thread Safety:
            Should be safe to call from multiple threads.
        """
        ...

    def health_check(self) -> bool:
        """Check if the service is healthy and ready to use.

        Returns:
            True if service is healthy, False otherwise.

        Note:
            This method should not raise exceptions. Return False on error.
        """
        ...

    def shutdown(self) -> None:
        """Perform graceful shutdown of the service.

        This is called when the application is shutting down.
        It should call cleanup() and perform any additional shutdown tasks.

        Thread Safety:
            Should be safe to call from multiple threads.
        """
        ...

    def metrics(self) -> dict[str, t.Any]:
        """Get service metrics for monitoring.

        Returns:
            Dictionary of metric names to values. Common metrics include:
            - request_count: Number of requests handled
            - error_count: Number of errors encountered
            - uptime_seconds: Service uptime in seconds
            - custom metrics: Service-specific metrics

        Example:
            {
                "request_count": 1234,
                "error_count": 5,
                "uptime_seconds": 3600,
            }
        """
        ...

    def is_healthy(self) -> bool:
        """Alias for health_check().

        Returns:
            True if service is healthy, False otherwise.

        Note:
            This method provides an alternative name for health_check()
            for convenience and readability.
        """
        ...

    def register_resource(self, resource: t.Any) -> None:
        """Register a resource for automatic cleanup.

        Resources registered here will be automatically cleaned up
        when cleanup() is called.

        Args:
            resource: Any resource that needs cleanup (file handle,
                     network connection, etc.)

        Example:
            file_handle = open("log.txt", "w")
            service.register_resource(file_handle)
            # Will be automatically closed on cleanup()
        """
        ...

    def cleanup_resource(self, resource: t.Any) -> None:
        """Clean up a specific resource immediately.

        Args:
            resource: The resource to clean up.

        Note:
            This removes the resource from the managed resources list
            and cleans it up immediately.
        """
        ...

    def record_error(self, error: Exception) -> None:
        """Record an error for metrics and monitoring.

        Args:
            error: The exception that occurred.

        Note:
            Errors are tracked in metrics() under "error_count".
        """
        ...

    def increment_requests(self) -> None:
        """Increment the request counter.

        Note:
            Requests are tracked in metrics() under "request_count".
        """
        ...

    def get_custom_metric(self, name: str) -> t.Any:
        """Get a custom metric value.

        Args:
            name: Metric name.

        Returns:
            The metric value, or None if not found.

        Example:
            cache_hit_rate = service.get_custom_metric("cache_hit_rate")
        """
        ...

    def set_custom_metric(self, name: str, value: t.Any) -> None:
        """Set a custom metric value.

        Args:
            name: Metric name.
            value: Metric value (can be int, float, str, etc.)

        Example:
            service.set_custom_metric("cache_hit_rate", 0.85)
        """
        ...


@t.runtime_checkable
class CommandRunner(t.Protocol):
    """Protocol for running subprocess commands.

    This protocol abstracts subprocess execution for testing and portability.

    Thread Safety:
        Implementation-dependent.

    Example:
        runner: CommandRunner = CommandRunnerImpl()
        result = runner.execute_command(["git", "status"])
        print(result.stdout)
    """

    def execute_command(
        self,
        cmd: list[str],
        **kwargs: t.Any,
    ) -> subprocess.CompletedProcess[str]:
        """Execute a subprocess command.

        Args:
            cmd: Command and arguments as a list of strings.
            **kwargs: Additional arguments passed to subprocess.run().
                     Common options:
                     - cwd: Working directory
                     - env: Environment variables
                     - timeout: Timeout in seconds
                     - check: Raise exception on non-zero exit

        Returns:
            CompletedProcess with stdout, stderr, returncode.

        Raises:
            subprocess.TimeoutExpired: If command times out.
            subprocess.CalledProcessError: If check=True and command fails.
            FileNotFoundError: If command not found.

        Example:
            result = runner.execute_command(
                ["ruff", "check", "test.py"],
                cwd="/path/to/project",
                timeout=60,
            )
            if result.returncode != 0:
                print(f"Errors: {result.stderr}")
        """
        ...


@t.runtime_checkable
class OptionsProtocol(t.Protocol):
    """Container for CLI options and configuration.

    This protocol holds all command-line options and configuration flags
    passed to crackerjack. It provides a single source of truth for
    configuration throughout the application.

    Thread Safety:
        Safe to read from multiple threads after initialization.
        Should not be modified after initialization.

    Example:
        options: OptionsProtocol = parse_cli_args()
        if options.verbose:
            console.print("Verbose mode enabled")
        if options.run_tests:
            test_manager.run_tests(options)
    """

    # Test options
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

    # Quality check options
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

    # AI options
    ai_agent: bool = False
    """Enable AI agent for suggestions."""

    ai_fix_max_iterations: int = 5
    """Maximum AI fix iterations (default: 5)."""

    # Publishing options
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

    # Coverage options
    coverage: bool
    """Generate coverage report."""

    # Configuration options
    commit: bool
    """Commit changes after successful run."""

    interactive: bool
    """Interactive mode (confirm actions)."""

    no_config_updates: bool
    """Skip automatic config updates."""

    skip_config_merge: bool
    """Skip config merging."""

    # Verbose options
    verbose: bool
    """Verbose output."""

    track_progress: bool
    """Track and display progress."""

    # Clean options
    clean: bool
    """Clean temporary files and caches."""

    cleanup: t.Any | None
    """Cleanup old releases/artifacts."""

    # Async options
    async_mode: bool
    """Enable async mode."""

    # Experimental options
    experimental_hooks: bool
    """Enable experimental hooks."""

    enable_pyrefly: bool
    """Enable pyrefly type checker."""

    enable_ty: bool
    """Enable ty type checker."""

    # Lock options
    disable_global_locks: bool
    """Disable global locks."""

    global_lock_timeout: int = 600
    """Global lock timeout in seconds (default: 600)."""

    global_lock_cleanup: bool = True
    """Enable global lock cleanup."""

    global_lock_dir: str | None
    """Global lock directory path."""

    # Code options
    strip_code: bool
    """Strip debugging code."""

    # Xcode options
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

    # Fast iteration
    fast_iteration: bool
    """Fast iteration mode (skip non-essentials)."""

    # Monitoring
    monitor_dashboard: str | None
    """Monitor dashboard URL."""

    # Server options
    start_mcp_server: bool = False
    """Start MCP server."""

    # Documentation options
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
    """Abstract console output for terminal, logs, testing, etc.

    This protocol provides a generic interface for console output,
    allowing different implementations (Rich console, mock console, etc.)
    to be used interchangeably.

    Thread Safety:
        Implementation-dependent. Rich Console is thread-safe.

    Common Implementations:
        - CrackerjackConsole: Rich-based colored console
        - MockConsole: In-memory console for testing

    Example:
        console: ConsoleInterface = CrackerjackConsole()
        console.print("[green]Success![/green]")
        user_input = console.input("Enter value: ")
    """

    def print(self, *args: t.Any, **kwargs: t.Any) -> None:
        """Print output to console.

        Args:
            *args: Arguments to print (same as built-in print).
            **kwargs: Keyword arguments (same as built-in print).

        Note:
            Implementations can support Rich markup for colors/styling.
            Example: console.print("[green]Success![/green]")
        """
        ...

    def input(self, prompt: str = "") -> str:
        """Get user input from console.

        Args:
            prompt: Prompt string to display.

        Returns:
            User input as string.

        Example:
            name = console.input("Enter name: ")
            console.print(f"Hello, {name}!")
        """
        ...

    if TYPE_CHECKING:

        async def aprint(self, *args: t.Any, **kwargs: t.Any) -> None:
            """Async print (TYPE_CHECKING only).

            This method is only available for type checking.
            Implementations should provide this if they support async printing.
            """
            ...


@t.runtime_checkable
class FileSystemInterface(t.Protocol):
    """Abstract file operations for testing and portability.

    This protocol provides a generic interface for file system operations,
    allowing different implementations (real filesystem, in-memory mock, etc.)
    to be used interchangeably.

    Thread Safety:
        Implementation-dependent.

    Common Implementations:
        - RealFileSystem: Actual file system operations
        - MockFileSystem: In-memory file system for testing

    Example:
        fs: FileSystemInterface = RealFileSystem()
        if fs.exists("/path/to/file.txt"):
            content = fs.read_file("/path/to/file.txt")
            fs.write_file("/path/to/output.txt", content.upper())
    """

    def read_file(self, path: str | t.Any) -> str:
        """Read file contents.

        Args:
            path: File path as string or Path-like object.

        Returns:
            File contents as string.

        Raises:
            FileNotFoundError: If file doesn't exist.
            PermissionError: If lacking read permissions.
            UnicodeDecodeError: If file cannot be decoded.

        Example:
            content = fs.read_file("/path/to/file.txt")
            print(content)
        """
        ...

    def write_file(self, path: str | t.Any, content: str) -> None:
        """Write content to file.

        Args:
            path: File path as string or Path-like object.
            content: Content to write.

        Raises:
            PermissionError: If lacking write permissions.
            OSError: If directory doesn't exist.

        Example:
            fs.write_file("/path/to/file.txt", "Hello, world!")
        """
        ...

    def exists(self, path: str | t.Any) -> bool:
        """Check if file or directory exists.

        Args:
            path: Path to check.

        Returns:
            True if path exists, False otherwise.

        Example:
            if fs.exists("/path/to/file.txt"):
                print("File exists")
        """
        ...

    def mkdir(self, path: str | t.Any, parents: bool = False) -> None:
        """Create directory.

        Args:
            path: Directory path to create.
            parents: If True, create parent directories (like mkdir -p).

        Raises:
            FileExistsError: If directory already exists.
            PermissionError: If lacking write permissions.

        Example:
            fs.mkdir("/path/to/dir", parents=True)
        """
        ...


@t.runtime_checkable
class GitInterface(t.Protocol):
    """Protocol for Git operations.

    Provides a generic interface for Git version control operations,
    allowing different implementations (actual Git, mock Git for testing, etc.)
    to be used interchangeably.

    Thread Safety:
        Implementation-dependent.

    Example:
        git: GitInterface = GitService()
        if git.is_git_repo():
            changed_files = git.get_changed_files()
            git.add_files(changed_files)
            git.commit("Update tests")
            git.push()
    """

    def is_git_repo(self) -> bool:
        """Check if current directory is a Git repository.

        Returns:
            True if in a Git repository, False otherwise.

        Example:
            if git.is_git_repo():
                print("In a Git repository")
        """
        ...

    def get_changed_files(self) -> list[str]:
        """Get list of changed files.

        Returns:
            List of changed file paths (relative to repo root).

        Example:
            files = git.get_changed_files()
            print(f"Changed files: {files}")
        """
        ...

    def commit(self, message: str) -> bool:
        """Commit changes with message.

        Args:
            message: Commit message.

        Returns:
            True if commit succeeded, False otherwise.

        Example:
            success = git.commit("Update tests")
            if success:
                print("Committed successfully")
        """
        ...

    def push(self) -> bool:
        """Push commits to remote.

        Returns:
            True if push succeeded, False otherwise.

        Example:
            if git.push():
                print("Pushed successfully")
        """
        ...

    def add_files(self, files: list[str]) -> bool:
        """Stage specific files.

        Args:
            files: List of file paths to stage.

        Returns:
            True if files were staged, False otherwise.

        Example:
            git.add_files(["test1.py", "test2.py"])
        """
        ...

    def add_all_files(self) -> bool:
        """Stage all changed files.

        Returns:
            True if files were staged, False otherwise.

        Example:
            git.add_all_files()
        """
        ...

    if TYPE_CHECKING:

        def get_staged_files(self) -> list[str]:
            """Get list of staged files.

            Returns:
                List of staged file paths.

            Example:
                staged = git.get_staged_files()
                print(f"Staged files: {staged}")
            """
            ...

        def get_changed_files_by_extension(
            self,
            extensions: list[str],
            include_staged: bool = True,
            include_unstaged: bool = True,
        ) -> list[Path]:
            """Get changed files filtered by extension.

            Args:
                extensions: List of extensions to filter (e.g., [".py", ".md"]).
                include_staged: Include staged files.
                include_unstaged: Include unstaged files.

            Returns:
                List of Path objects for changed files.

            Example:
                py_files = git.get_changed_files_by_extension([".py"])
                print(f"Changed Python files: {py_files}")
            """
            ...

        def push_with_tags(self) -> bool:
            """Push commits and tags to remote.

            Returns:
                True if push succeeded, False otherwise.

            Example:
                if git.push_with_tags():
                    print("Pushed with tags successfully")
            """
            ...

        def get_commit_message_suggestions(
            self,
            changed_files: list[str],
        ) -> list[str]:
            """Generate commit message suggestions based on changed files.

            Args:
                changed_files: List of changed file paths.

            Returns:
                List of commit message suggestions.

            Example:
                suggestions = git.get_commit_message_suggestions(files)
                print(suggestions)
            """
            ...

        def get_unpushed_commit_count(self) -> int:
            """Get count of unpushed commits.

            Returns:
                Number of commits not yet pushed to remote.

            Example:
                count = git.get_unpushed_commit_count()
                print(f"{count} unpushed commits")
            """
            ...

        def get_current_commit_hash(self) -> str | None:
            """Get current commit hash.

            Returns:
                Commit hash string, or None if not in a Git repo.

            Example:
                commit_hash = git.get_current_commit_hash()
                print(f"Current commit: {commit_hash}")
            """
            ...

        def reset_hard(self, commit_hash: str) -> bool:
            """Hard reset to commit.

            Args:
                commit_hash: Commit hash to reset to.

            Returns:
                True if reset succeeded, False otherwise.

            Warning:
                This destroys all uncommitted changes!

            Example:
                git.reset_hard("abc123")
            """
            ...


# =============================================================================
# SERVICE PROTOCOLS (23 protocols)
# These extend ServiceProtocol with domain-specific functionality.
# =============================================================================


@t.runtime_checkable
class HookManager(t.Protocol):
    """Protocol for managing and executing quality check hooks.

    Hooks are quality tools (ruff, mypy, pytest, etc.) that run on code
    to ensure standards compliance. This protocol manages hook execution,
    configuration, and result summarization.

    Thread Safety:
        Hook execution should be thread-safe if configured properly.

    Example:
        manager: HookManager = HookManagerImpl()
        results = manager.run_fast_hooks()
        summary = manager.get_hook_summary(results, elapsed_time=5.2)
    """

    def run_fast_hooks(self) -> list[t.Any]:
        """Run fast hooks (~5 seconds).

        Returns:
            List of hook results.

        Example:
            results = manager.run_fast_hooks()
            for result in results:
                if not result.success:
                    print(f"Hook failed: {result.name}")
        """
        ...

    def run_comprehensive_hooks(self) -> list[t.Any]:
        """Run comprehensive hooks (~30 seconds).

        Returns:
            List of hook results.

        Example:
            results = manager.run_comprehensive_hooks()
        """
        ...

    def install_hooks(self) -> bool:
        """Install hooks for the project.

        Returns:
            True if installation succeeded, False otherwise.

        Example:
            if manager.install_hooks():
                print("Hooks installed successfully")
        """
        ...

    def set_config_path(self, path: str | t.Any) -> None:
        """Set path to hook configuration file.

        Args:
            path: Path to configuration file.

        Example:
            manager.set_config_path("/path/to/hooks.yaml")
        """
        ...

    def get_hook_summary(
        self,
        results: t.Any,
        elapsed_time: float | None = None,
    ) -> t.Any:
        """Get summary of hook results.

        Args:
            results: Hook results from run_fast_hooks or run_comprehensive_hooks.
            elapsed_time: Optional elapsed time in seconds.

        Returns:
            Hook summary object.

        Example:
            summary = manager.get_hook_summary(results, elapsed_time=10.5)
            print(summary.formatted_output)
        """
        ...

    if TYPE_CHECKING:

        def get_hook_count(self, suite_name: str) -> int:
            """Get number of hooks in suite.

            Args:
                suite_name: Name of hook suite (e.g., "fast", "comprehensive").

            Returns:
                Number of hooks in suite.

            Example:
                count = manager.get_hook_count("fast")
                print(f"Fast hooks: {count}")
            """
            ...

        _progress_callback: t.Callable[[int, int], None] | None
        """Optional callback for progress updates (current, total)."""

        _progress_start_callback: t.Callable[[int, int], None] | None
        """Optional callback for progress start (total, estimated_time)."""


@t.runtime_checkable
class SecurityAwareHookManager(HookManager, t.Protocol):
    """Protocol for security-focused hook management.

    Extends HookManager with security-specific functionality for
    identifying and handling security-critical failures.

    Example:
        manager: SecurityAwareHookManager = SecurityAwareHookManagerImpl()
        results = manager.run_comprehensive_hooks()
        critical_failures = manager.get_security_critical_failures(results)
    """

    def get_security_critical_failures(self, results: list[t.Any]) -> list[t.Any]:
        """Get security-critical failures from results.

        Args:
            results: List of hook results.

        Returns:
            List of security-critical failures.

        Example:
            critical = manager.get_security_critical_failures(results)
            if critical:
                print("SECURITY ISSUES FOUND!")
        """
        ...

    def has_security_critical_failures(self, results: list[t.Any]) -> bool:
        """Check if results contain security-critical failures.

        Args:
            results: List of hook results.

        Returns:
            True if security-critical failures exist, False otherwise.

        Example:
            if manager.has_security_critical_failures(results):
                print("Security issues detected!")
        """
        ...

    def get_security_audit_report(
        self,
        fast_results: list[t.Any],
        comprehensive_results: list[t.Any],
    ) -> dict[str, t.Any]:
        """Generate security audit report from hook results.

        Args:
            fast_results: Results from fast hooks.
            comprehensive_results: Results from comprehensive hooks.

        Returns:
            Security audit report dictionary.

        Example:
            report = manager.get_security_audit_report(fast, comp)
            print(report["summary"])
        """
        ...


@t.runtime_checkable
class CoverageRatchetProtocol(ServiceProtocol, t.Protocol):
    """Protocol for coverage ratchet system (enforce coverage never decreases).

    The ratchet system ensures code coverage never decreases below
    the current baseline. If coverage drops, it's considered a regression.

    Thread Safety:
        Should be thread-safe for read operations.

    Example:
        ratchet: CoverageRatchetProtocol = CoverageRatchet()
        current = 85.0
        if ratchet.is_coverage_regression(current):
            baseline = ratchet.get_baseline_coverage()
            print(f"Coverage regression! {current}% < {baseline}%")
    """

    def get_baseline_coverage(self) -> float:
        """Get current baseline coverage percentage.

        Returns:
            Baseline coverage as float (0-100).

        Example:
            baseline = ratchet.get_baseline_coverage()
            print(f"Current baseline: {baseline}%")
        """
        ...

    def update_baseline_coverage(self, new_coverage: float) -> bool:
        """Update baseline to new coverage (only if higher).

        Args:
            new_coverage: New coverage percentage (0-100).

        Returns:
            True if baseline updated, False otherwise.

        Example:
            if ratchet.update_baseline_coverage(90.0):
                print("Baseline increased to 90%")
        """
        ...

    def is_coverage_regression(self, current_coverage: float) -> bool:
        """Check if current coverage is below baseline.

        Args:
            current_coverage: Current coverage percentage (0-100).

        Returns:
            True if coverage regression detected, False otherwise.

        Example:
            if ratchet.is_coverage_regression(80.0):
                print("Coverage regression detected!")
        """
        ...

    def get_coverage_improvement_needed(self) -> float:
        """Get coverage percentage needed to reach baseline.

        Returns:
            Coverage percentage needed to match baseline.

        Example:
            needed = ratchet.get_coverage_improvement_needed()
            print(f"Need {needed}% more coverage")
        """
        ...

    def get_status_report(self) -> dict[str, t.Any]:
        """Get ratchet status report.

        Returns:
            Status report dictionary with baseline, current status, etc.

        Example:
            report = ratchet.get_status_report()
            print(report["summary"])
        """
        ...

    def get_coverage_report(self) -> str | None:
        """Get detailed coverage report.

        Returns:
            Coverage report string, or None if unavailable.

        Example:
            report = ratchet.get_coverage_report()
            if report:
                print(report)
        """
        ...

    def check_and_update_coverage(self) -> dict[str, t.Any]:
        """Check coverage and update baseline if improved.

        Returns:
            Result dictionary with coverage status and whether baseline updated.

        Example:
            result = ratchet.check_and_update_coverage()
            print(result["status"])
        """
        ...


@t.runtime_checkable
class SecurityServiceProtocol(ServiceProtocol, t.Protocol):
    """Protocol for security checks and validation.

    Provides security-focused operations like file safety validation,
    secret detection, and secure subprocess execution.

    Thread Safety:
        Should be thread-safe.

    Example:
        security: SecurityServiceProtocol = SecurityService()
        if security.validate_file_safety("/path/to/file.txt"):
            content = read_file("/path/to/file.txt")
            secrets = security.check_hardcoded_secrets(content)
            if secrets:
                print("Secrets found!")
    """

    def validate_file_safety(self, path: str | Path) -> bool:
        """Check if file is safe to modify.

        Args:
            path: File path to validate.

        Returns:
            True if file is safe to modify, False otherwise.

        Note:
            Checks for system files, sensitive configs, etc.

        Example:
            if security.validate_file_safety(path):
                modify_file(path)
        """
        ...

    def check_hardcoded_secrets(self, content: str) -> list[dict[str, t.Any]]:
        """Check content for hardcoded secrets.

        Args:
            content: Text content to check.

        Returns:
            List of found secrets with line numbers and types.

        Example:
            secrets = security.check_hardcoded_secrets(content)
            for secret in secrets:
                print(f"Secret at line {secret['line']}: {secret['type']}")
        """
        ...

    def is_safe_subprocess_call(self, cmd: list[str]) -> bool:
        """Check if subprocess command is safe to execute.

        Args:
            cmd: Command and arguments.

        Returns:
            True if command is safe, False otherwise.

        Note:
            Checks for shell injection, unsafe flags, etc.

        Example:
            if security.is_safe_subprocess_call(["git", "status"]):
                run_command(["git", "status"])
        """
        ...

    def create_secure_command_env(self) -> dict[str, str]:
        """Create secure environment for subprocess commands.

        Returns:
            Environment variables dictionary with security hardening.

        Example:
            env = security.create_secure_command_env()
            subprocess.run(cmd, env=env)
        """
        ...

    def mask_tokens(self, text: str) -> str:
        """Mask sensitive tokens in text.

        Args:
            text: Text to mask.

        Returns:
            Text with tokens replaced with placeholders.

        Example:
            masked = security.mask_tokens("API_KEY=abc123")
            # Returns: "API_KEY=***"
        """
        ...

    def validate_token_format(self, token: str, token_type: str) -> bool:
        """Validate token format.

        Args:
            token: Token string to validate.
            token_type: Type of token (e.g., "api_key", "jwt").

        Returns:
            True if token format is valid, False otherwise.

        Example:
            if security.validate_token_format(token, "jwt"):
                print("Valid JWT token")
        """
        ...


@t.runtime_checkable
class InitializationServiceProtocol(ServiceProtocol, t.Protocol):
    """Protocol for project initialization and setup.

    Handles initial project setup, validation, and git hooks installation.

    Example:
        init: InitializationServiceProtocol = InitializationService()
        if init.initialize_project("/path/to/project"):
            print("Project initialized")
    """

    def initialize_project(self, project_path: str | Path) -> bool:
        """Initialize a new crackerjack project.

        Args:
            project_path: Path to project directory.

        Returns:
            True if initialization succeeded, False otherwise.

        Example:
            if init.initialize_project("/path/to/project"):
                print("Project initialized")
        """
        ...

    def validate_project_structure(self) -> bool:
        """Validate current project structure.

        Returns:
            True if structure is valid, False otherwise.

        Example:
            if init.validate_project_structure():
                print("Project structure valid")
        """
        ...

    def setup_git_hooks(self) -> bool:
        """Set up git hooks for the project.

        Returns:
            True if hooks were installed, False otherwise.

        Example:
            if init.setup_git_hooks():
                print("Git hooks installed")
        """
        ...


@t.runtime_checkable
class SmartSchedulingServiceProtocol(ServiceProtocol, t.Protocol):
    """Protocol for intelligent task scheduling.

    Determines when to run periodic tasks like project initialization.

    Example:
        scheduler: SmartSchedulingServiceProtocol = SmartSchedulingService()
        if scheduler.should_scheduled_init():
            scheduler.record_init_timestamp()
    """

    def should_scheduled_init(self) -> bool:
        """Check if scheduled initialization should run.

        Returns:
            True if initialization should run, False otherwise.

        Note:
            Uses timing heuristics to determine optimal init time.
        """
        ...

    def record_init_timestamp(self) -> None:
        """Record initialization timestamp.

        Note:
            Used for scheduling future initializations.
        """
        ...


@t.runtime_checkable
class UnifiedConfigurationServiceProtocol(ServiceProtocol, t.Protocol):
    """Protocol for unified configuration management.

    Provides centralized access to all configuration settings including
    logging, hook execution, and testing configurations.

    Example:
        config: UnifiedConfigurationServiceProtocol = UnifiedConfigurationService()
        settings = config.get_config()
        logging_config = config.get_logging_config()
    """

    def get_config(self, reload: bool = False) -> CrackerjackSettings:
        """Get crackerjack configuration settings.

        Args:
            reload: Force reload configuration from files.

        Returns:
            CrackerjackSettings object with all configuration.

        Example:
            settings = config.get_config()
            print(settings.verbose)
        """
        ...

    def get_logging_config(self) -> dict[str, t.Any]:
        """Get logging configuration.

        Returns:
            Logging configuration dictionary.

        Example:
            log_config = config.get_logging_config()
            logging.config.dictConfig(log_config)
        """
        ...

    def get_hook_execution_config(self) -> dict[str, t.Any]:
        """Get hook execution configuration.

        Returns:
            Hook execution configuration dictionary.

        Example:
            hook_config = config.get_hook_execution_config()
            print(hook_config["max_parallel"])
        """
        ...

    def get_testing_config(self) -> dict[str, t.Any]:
        """Get testing configuration.

        Returns:
            Testing configuration dictionary.

        Example:
            test_config = config.get_testing_config()
            print(test_config["workers"])
        """
        ...

    @staticmethod
    def get_cache_config() -> dict[str, t.Any]:
        """Get cache configuration.

        Returns:
            Cache configuration dictionary.

        Example:
            cache_config = UnifiedConfigurationServiceProtocol.get_cache_config()
            print(cache_config["dir"])
        """
        ...

    def validate_current_config(self) -> bool:
        """Validate current configuration.

        Returns:
            True if configuration is valid, False otherwise.

        Example:
            if config.validate_current_config():
                print("Configuration valid")
        """
        ...


@t.runtime_checkable
class ConfigIntegrityServiceProtocol(ServiceProtocol, t.Protocol):
    """Protocol for configuration integrity validation.

    Ensures configuration files are valid and consistent.

    Example:
        integrity: ConfigIntegrityServiceProtocol = ConfigIntegrityService()
        if integrity.check_config_integrity():
            print("Configuration is valid")
    """

    def check_config_integrity(self) -> bool:
        """Check if configuration files are valid and consistent.

        Returns:
            True if configuration is valid, False otherwise.

        Example:
            if integrity.check_config_integrity():
                print("Configuration valid")
        """
        ...


@t.runtime_checkable
class TestManagerProtocol(ServiceProtocol, t.Protocol):
    """Protocol for test execution and coverage management.

    Manages running tests, collecting results, and measuring code coverage.

    Thread Safety:
        Should be thread-safe.

    Example:
        test_manager: TestManagerProtocol = TestManager(console)
        success = test_manager.run_tests(options)
        if not success:
            failures = test_manager.get_test_failures()
            print(f"Failed: {failures}")
    """

    def run_tests(self, options: OptionsProtocol) -> bool:
        """Run test suite.

        Args:
            options: OptionsProtocol with test configuration.

        Returns:
            True if all tests passed, False otherwise.

        Example:
            success = test_manager.run_tests(options)
            if success:
                print("All tests passed!")
        """
        ...

    def get_test_failures(self) -> list[str]:
        """Get list of failed test names.

        Returns:
            List of failed test names.

        Example:
            failures = test_manager.get_test_failures()
            for test in failures:
                print(f"Failed: {test}")
        """
        ...

    def validate_test_environment(self) -> bool:
        """Validate test environment is set up correctly.

        Returns:
            True if environment is valid, False otherwise.

        Example:
            if test_manager.validate_test_environment():
                print("Test environment valid")
        """
        ...

    def get_coverage(self) -> dict[str, t.Any]:
        """Get coverage metrics.

        Returns:
            Coverage metrics dictionary with keys like percent, covered_lines, etc.

        Example:
            coverage = test_manager.get_coverage()
            print(f"Coverage: {coverage['percent']}%")
        """
        ...


@t.runtime_checkable
class BoundedStatusOperationsProtocol(ServiceProtocol, t.Protocol):
    """Protocol for circuit breaker pattern implementation.

    Prevents cascading failures by blocking operations after repeated failures.

    Thread Safety:
        Must be thread-safe.

    Example:
        circuit: BoundedStatusOperationsProtocol = CircuitBreaker()
        result = await circuit.execute_bounded_operation(
            "api_call",
            lambda: make_api_call(),
        )
    """

    async def execute_bounded_operation(
        self,
        operation_type: str,
        client_id: str,
        operation_func: t.Callable[..., t.Awaitable[t.Any]],
        *args: t.Any,
        **kwargs: t.Any,
    ) -> t.Any:
        """Execute operation with circuit breaker protection.

        Args:
            operation_type: Type of operation (e.g., "api_call", "db_query").
            client_id: Client identifier for tracking.
            operation_func: Async function to execute.
            *args: Arguments to pass to operation_func.
            **kwargs: Keyword arguments to pass to operation_func.

        Returns:
            Result from operation_func.

        Raises:
            CircuitBreakerOpen: If circuit is open (too many failures).

        Example:
            result = await circuit.execute_bounded_operation(
                "api_call",
                "client123",
                lambda: api.get_data(),
            )
        """
        ...

    def get_operation_status(self) -> dict[str, t.Any]:
        """Get circuit breaker status.

        Returns:
            Status dictionary with state, failure count, etc.

        Example:
            status = circuit.get_operation_status()
            print(f"Circuit state: {status['state']}")
        """
        ...

    def reset_circuit_breaker(self, operation_type: str) -> bool:
        """Reset circuit breaker for operation type.

        Args:
            operation_type: Operation type to reset.

        Returns:
            True if reset succeeded, False otherwise.

        Example:
            circuit.reset_circuit_breaker("api_call")
        """
        ...


@t.runtime_checkable
class PublishManager(t.Protocol):
    """Protocol for managing package publishing.

    Handles version bumping, PyPI publishing, git tagging, and cleanup.

    Example:
        publisher: PublishManager = PublishManager()
        new_version = publisher.bump_version("patch")
        publisher.create_git_tag(new_version)
        publisher.publish_package()
    """

    def bump_version(self, version_type: str) -> str:
        """Bump version number.

        Args:
            version_type: Type of bump ("major", "minor", "patch").

        Returns:
            New version string.

        Example:
            new_version = publisher.bump_version("patch")
            print(f"New version: {new_version}")
        """
        ...

    def publish_package(self) -> bool:
        """Publish package to PyPI.

        Returns:
            True if publishing succeeded, False otherwise.

        Example:
            if publisher.publish_package():
                print("Published successfully")
        """
        ...

    def validate_auth(self) -> bool:
        """Validate PyPI authentication.

        Returns:
            True if authentication is valid, False otherwise.

        Example:
            if publisher.validate_auth():
                print("Authentication valid")
        """
        ...

    def create_git_tag(self, version: str) -> bool:
        """Create and push git tag.

        Args:
            version: Version string for tag.

        Returns:
            True if tag created and pushed, False otherwise.

        Example:
            if publisher.create_git_tag("1.2.3"):
                print("Tag created")
        """
        ...

    def create_git_tag_local(self, version: str) -> bool:
        """Create git tag locally (don't push).

        Args:
            version: Version string for tag.

        Returns:
            True if tag created, False otherwise.

        Example:
            if publisher.create_git_tag_local("1.2.3"):
                print("Local tag created")
        """
        ...

    def cleanup_old_releases(self, keep_releases: int) -> None:
        """Cleanup old PyPI releases.

        Args:
            keep_releases: Number of recent releases to keep.

        Example:
            publisher.cleanup_old_releases(10)
        """
        ...


@t.runtime_checkable
class ConfigMergeServiceProtocol(ServiceProtocol, t.Protocol):
    """Protocol for intelligent configuration file merging.

    Handles merging of pyproject.toml, pre-commit configs, gitignore, etc.

    Example:
        merger: ConfigMergeServiceProtocol = ConfigMergeService()
        merged = merger.smart_merge_pyproject(source_content, target_path, "myproject")
        merger.write_pyproject_config(merged, target_path)
    """

    def smart_merge_pyproject(
        self,
        source_content: dict[str, t.Any],
        target_path: str | t.Any,
        project_name: str,
    ) -> dict[str, t.Any]:
        """Merge pyproject.toml content intelligently.

        Args:
            source_content: Source configuration dictionary.
            target_path: Path to target pyproject.toml.
            project_name: Name of project.

        Returns:
            Merged configuration dictionary.

        Example:
            merged = merger.smart_merge_pyproject(
                {"tool": {"ruff": {...}}},
                "/path/to/pyproject.toml",
                "myproject",
            )
        """
        ...

    def smart_merge_pre_commit_config(
        self,
        source_content: dict[str, t.Any],
        target_path: str | t.Any,
        project_name: str,
    ) -> dict[str, t.Any]:
        """Merge pre-commit config intelligently.

        Args:
            source_content: Source configuration dictionary.
            target_path: Path to target .pre-commit-config.yaml.
            project_name: Name of project.

        Returns:
            Merged configuration dictionary.

        Example:
            merged = merger.smart_merge_pre_commit_config(
                {"repos": [...]},
                "/path/to/.pre-commit-config.yaml",
                "myproject",
            )
        """
        ...

    def smart_append_file(
        self,
        source_content: str,
        target_path: str | t.Any,
        start_marker: str,
        end_marker: str,
        force: bool = False,
    ) -> str:
        """Append content between markers.

        Args:
            source_content: Content to append.
            target_path: Path to target file.
            start_marker: Start marker (e.g., "# CRACKERJACK START").
            end_marker: End marker (e.g., "# CRACKERJACK END").
            force: Overwrite existing content between markers.

        Returns:
            Updated file content.

        Example:
            content = merger.smart_append_file(
                "export MY_VAR=1",
                "/path/to/.env",
                "# CRACKERJACK START",
                "# CRACKERJACK END",
            )
        """
        ...

    def smart_merge_gitignore(
        self,
        patterns: list[str],
        target_path: str | t.Any,
    ) -> str:
        """Merge .gitignore patterns.

        Args:
            patterns: List of gitignore patterns to add.
            target_path: Path to .gitignore file.

        Returns:
            Updated .gitignore content.

        Example:
            content = merger.smart_merge_gitignore(
                ["*.pyc", ".env"],
                "/path/to/.gitignore",
            )
        """
        ...

    def write_pyproject_config(
        self,
        config: dict[str, t.Any],
        target_path: str | t.Any,
    ) -> None:
        """Write pyproject.toml configuration.

        Args:
            config: Configuration dictionary.
            target_path: Path to write file.

        Example:
            merger.write_pyproject_config(merged, "/path/to/pyproject.toml")
        """
        ...

    def write_pre_commit_config(
        self,
        config: dict[str, t.Any],
        target_path: str | t.Any,
    ) -> None:
        """Write pre-commit configuration.

        Args:
            config: Configuration dictionary.
            target_path: Path to write file.

        Example:
            merger.write_pre_commit_config(merged, "/path/to/.pre-commit-config.yaml")
        """
        ...


@t.runtime_checkable
class HookLockManagerProtocol(t.Protocol):
    """Protocol for managing hook execution locks.

    Prevents concurrent hook execution across processes using file-based locks.

    Thread Safety:
        Lock operations are thread-safe and process-safe.

    Example:
        lock_mgr: HookLockManagerProtocol = HookLockManager()
        if lock_mgr.requires_lock("ruff"):
            async with lock_mgr.acquire_hook_lock("ruff"):
                await run_ruff()
    """

    def requires_lock(self, hook_name: str) -> bool:
        """Check if hook requires locking.

        Args:
            hook_name: Name of hook.

        Returns:
            True if lock is required, False otherwise.

        Example:
            if lock_mgr.requires_lock("ruff"):
                print("Ruff requires locking")
        """
        ...

    def acquire_hook_lock(self, hook_name: str) -> t.AsyncContextManager[None]:
        """Acquire hook lock as async context manager.

        Args:
            hook_name: Name of hook to lock.

        Returns:
            Async context manager that releases lock on exit.

        Example:
            async with lock_mgr.acquire_hook_lock("ruff"):
                await run_ruff()
        """
        ...

    def get_lock_stats(self) -> dict[str, t.Any]:
        """Get lock statistics.

        Returns:
            Lock statistics dictionary.

        Example:
            stats = lock_mgr.get_lock_stats()
            print(f"Active locks: {stats['active']}")
        """
        ...

    def add_hook_to_lock_list(self, hook_name: str) -> None:
        """Add hook to lock list.

        Args:
            hook_name: Name of hook to add.

        Example:
            lock_mgr.add_hook_to_lock_list("mypy")
        """
        ...

    def remove_hook_from_lock_list(self, hook_name: str) -> None:
        """Remove hook from lock list.

        Args:
            hook_name: Name of hook to remove.

        Example:
            lock_mgr.remove_hook_from_lock_list("mypy")
        """
        ...

    def is_hook_currently_locked(self, hook_name: str) -> bool:
        """Check if hook is currently locked.

        Args:
            hook_name: Name of hook.

        Returns:
            True if hook is locked, False otherwise.

        Example:
            if lock_mgr.is_hook_currently_locked("ruff"):
                print("Ruff is locked")
        """
        ...

    def enable_global_lock(self, enabled: bool = True) -> None:
        """Enable or disable global locking.

        Args:
            enabled: True to enable, False to disable.

        Example:
            lock_mgr.enable_global_lock(True)
        """
        ...

    def is_global_lock_enabled(self) -> bool:
        """Check if global lock is enabled.

        Returns:
            True if global lock enabled, False otherwise.

        Example:
            if lock_mgr.is_global_lock_enabled():
                print("Global lock enabled")
        """
        ...

    def get_global_lock_path(self, hook_name: str) -> Path:
        """Get global lock file path for hook.

        Args:
            hook_name: Name of hook.

        Returns:
            Path to lock file.

        Example:
            lock_path = lock_mgr.get_global_lock_path("ruff")
            print(f"Lock file: {lock_path}")
        """
        ...

    def cleanup_stale_locks(self, max_age_hours: float = 2.0) -> int:
        """Cleanup stale lock files.

        Args:
            max_age_hours: Maximum lock age in hours.

        Returns:
            Number of locks cleaned up.

        Example:
            cleaned = lock_mgr.cleanup_stale_locks(max_age_hours=2.0)
            print(f"Cleaned {cleaned} stale locks")
        """
        ...

    def get_global_lock_stats(self) -> dict[str, t.Any]:
        """Get global lock statistics.

        Returns:
            Global lock statistics dictionary.

        Example:
            stats = lock_mgr.get_global_lock_stats()
            print(f"Global locks: {stats['count']}")
        """
        ...


# =============================================================================
# DOCUMENTATION SYSTEM PROTOCOLS (4 protocols)
# =============================================================================


@t.runtime_checkable
class DocumentationServiceProtocol(ServiceProtocol, t.Protocol):
    """Protocol for documentation generation and management.

    Handles API documentation extraction, generation, validation, and indexing.

    Example:
        docs: DocumentationServiceProtocol = DocumentationService()
        api_docs = docs.extract_api_documentation(source_paths)
        generated = docs.generate_documentation("api_reference", context)
        docs.update_documentation_index()
    """

    def extract_api_documentation(
        self,
        source_paths: list[Path],
    ) -> dict[str, t.Any]:
        """Extract API documentation from source files.

        Args:
            source_paths: List of source file paths.

        Returns:
            API documentation dictionary.

        Example:
            api_docs = docs.extract_api_documentation([
                Path("src/module.py"),
            ])
        """
        ...

    def generate_documentation(
        self,
        template_name: str,
        context: dict[str, t.Any],
    ) -> str:
        """Generate documentation from template.

        Args:
            template_name: Name of template.
            context: Template context data.

        Returns:
            Generated documentation content.

        Example:
            content = docs.generate_documentation(
                "api_reference",
                {"apis": api_docs},
            )
        """
        ...

    def validate_documentation(self, doc_paths: list[Path]) -> list[dict[str, str]]:
        """Validate documentation files.

        Args:
            doc_paths: List of documentation file paths.

        Returns:
            List of validation errors (empty if all valid).

        Example:
            errors = docs.validate_documentation([
                Path("docs/api.md"),
            ])
            if errors:
                for error in errors:
                    print(f"Error: {error}")
        """
        ...

    def update_documentation_index(self) -> bool:
        """Update documentation index.

        Returns:
            True if index updated, False otherwise.

        Example:
            if docs.update_documentation_index():
                print("Documentation index updated")
        """
        ...

    def get_documentation_coverage(self) -> dict[str, t.Any]:
        """Get documentation coverage metrics.

        Returns:
            Coverage metrics dictionary.

        Example:
            coverage = docs.get_documentation_coverage()
            print(f"API documentation: {coverage['api_percent']}%")
        """
        ...


@t.runtime_checkable
class APIExtractorProtocol(t.Protocol):
    """Protocol for extracting API information from source code.

    Parses source files to extract API definitions, protocols, and commands.

    Example:
        extractor: APIExtractorProtocol = APIExtractor()
        api_data = extractor.extract_from_python_files(files)
        protocols = extractor.extract_protocol_definitions(protocol_file)
    """

    def extract_from_python_files(self, files: list[Path]) -> dict[str, t.Any]:
        """Extract API information from Python files.

        Args:
            files: List of Python file paths.

        Returns:
            API data dictionary.

        Example:
            api_data = extractor.extract_from_python_files([
                Path("src/mymodule.py"),
            ])
        """
        ...

    def extract_protocol_definitions(self, protocol_file: Path) -> dict[str, t.Any]:
        """Extract protocol definitions from file.

        Args:
            protocol_file: Path to protocols file.

        Returns:
            Protocol definitions dictionary.

        Example:
            protocols = extractor.extract_protocol_definitions(
                Path("crackerjack/models/protocols.py"),
            )
        """
        ...

    def extract_service_interfaces(
        self,
        service_files: list[Path],
    ) -> dict[str, t.Any]:
        """Extract service interface information.

        Args:
            service_files: List of service file paths.

        Returns:
            Service interface data dictionary.

        Example:
            services = extractor.extract_service_interfaces([
                Path("crackerjack/services/test_manager.py"),
            ])
        """
        ...

    def extract_cli_commands(self, cli_files: list[Path]) -> dict[str, t.Any]:
        """Extract CLI command information.

        Args:
            cli_files: List of CLI file paths.

        Returns:
            CLI command data dictionary.

        Example:
            commands = extractor.extract_cli_commands([
                Path("crackerjack/cli.py"),
            ])
        """
        ...

    def extract_mcp_tools(self, mcp_files: list[Path]) -> dict[str, t.Any]:
        """Extract MCP tool information.

        Args:
            mcp_files: List of MCP file paths.

        Returns:
            MCP tool data dictionary.

        Example:
            tools = extractor.extract_mcp_tools([
                Path("crackerjack/mcp_tools.py"),
            ])
        """
        ...


@t.runtime_checkable
class DocumentationGeneratorProtocol(t.Protocol):
    """Protocol for generating documentation from extracted data.

    Creates API references, user guides, changelogs, etc.

    Example:
        generator: DocumentationGeneratorProtocol = DocumentationGenerator()
        api_ref = generator.generate_api_reference(api_data)
        user_guide = generator.generate_user_guide(context)
    """

    def generate_api_reference(self, api_data: dict[str, t.Any]) -> str:
        """Generate API reference documentation.

        Args:
            api_data: Extracted API data.

        Returns:
            Generated API reference content.

        Example:
            api_ref = generator.generate_api_reference(api_data)
        """
        ...

    def generate_user_guide(self, template_context: dict[str, t.Any]) -> str:
        """Generate user guide documentation.

        Args:
            template_context: Template context data.

        Returns:
            Generated user guide content.

        Example:
            guide = generator.generate_user_guide({"features": features})
        """
        ...

    def generate_changelog_update(
        self,
        version: str,
        changes: dict[str, t.Any],
    ) -> str:
        """Generate changelog update.

        Args:
            version: Version string.
            changes: Changes dictionary.

        Returns:
            Generated changelog content.

        Example:
            changelog = generator.generate_changelog_update(
                "1.2.3",
                {"features": ["New feature"]},
            )
        """
        ...

    def render_template(
        self,
        template_path: Path,
        context: dict[str, t.Any],
    ) -> str:
        """Render documentation template.

        Args:
            template_path: Path to template file.
            context: Template context data.

        Returns:
            Rendered content.

        Example:
            content = generator.render_template(
                Path("docs/templates/api.md"),
                {"api": api_data},
            )
        """
        ...

    def generate_cross_references(
        self,
        api_data: dict[str, t.Any],
    ) -> dict[str, list[str]]:
        """Generate cross-references between API elements.

        Args:
            api_data: Extracted API data.

        Returns:
            Cross-reference dictionary.

        Example:
            xrefs = generator.generate_cross_references(api_data)
            print(xrefs["MyClass"]["related_to"])
        """
        ...


@t.runtime_checkable
class DocumentationValidatorProtocol(t.Protocol):
    """Protocol for validating documentation quality and completeness.

    Checks links, freshness, cross-references, and coverage.

    Example:
        validator: DocumentationValidatorProtocol = DocumentationValidator()
        errors = validator.validate_links(doc_content)
        freshness = validator.check_documentation_freshness(api_data, doc_paths)
    """

    def validate_links(self, doc_content: str) -> list[dict[str, str]]:
        """Validate documentation links.

        Args:
            doc_content: Documentation content.

        Returns:
            List of link errors (empty if all valid).

        Example:
            errors = validator.validate_links(content)
            for error in errors:
                print(f"Broken link: {error['link']}")
        """
        ...

    def check_documentation_freshness(
        self,
        api_data: dict[str, t.Any],
        doc_paths: list[Path],
    ) -> dict[str, t.Any]:
        """Check if documentation matches current API.

        Args:
            api_data: Current API data.
            doc_paths: Documentation file paths.

        Returns:
            Freshness report dictionary.

        Example:
            report = validator.check_documentation_freshness(api_data, docs)
            print(f"Stale docs: {report['stale_count']}")
        """
        ...

    def validate_cross_references(
        self,
        docs: dict[str, str],
    ) -> list[dict[str, str]]:
        """Validate cross-references between documents.

        Args:
            docs: Dictionary of document names to content.

        Returns:
            List of reference errors (empty if all valid).

        Example:
            errors = validator.validate_cross_references({
                "api.md": api_content,
                "guide.md": guide_content,
            })
        """
        ...

    def calculate_coverage_metrics(
        self,
        api_data: dict[str, t.Any],
        existing_docs: dict[str, str],
    ) -> dict[str, float]:
        """Calculate documentation coverage metrics.

        Args:
            api_data: Current API data.
            existing_docs: Existing documentation.

        Returns:
            Coverage metrics dictionary.

        Example:
            metrics = validator.calculate_coverage_metrics(api_data, docs)
            print(f"Coverage: {metrics['overall']}%")
        """
        ...


# =============================================================================
# QUALITY ASSURANCE PROTOCOLS (5 protocols)
# =============================================================================


@t.runtime_checkable
class LoggerProtocol(t.Protocol):
    """Protocol for logging operations.

    Provides standard logging interface with level-based filtering.

    Example:
        logger: LoggerProtocol = Logger()
        logger.info("Starting operation")
        logger.warning("Low disk space")
        logger.error("Operation failed")
    """

    def info(self, message: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Log info message.

        Args:
            message: Log message.
            *args: Message format arguments.
            **kwargs: Additional keyword arguments.

        Example:
            logger.info("Processing file: %s", filename)
        """
        ...

    def warning(self, message: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Log warning message.

        Args:
            message: Log message.
            *args: Message format arguments.
            **kwargs: Additional keyword arguments.

        Example:
            logger.warning("Deprecated feature used: %s", feature_name)
        """
        ...

    def error(self, message: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Log error message.

        Args:
            message: Log message.
            *args: Message format arguments.
            **kwargs: Additional keyword arguments.

        Example:
            logger.error("Failed to connect to database: %s", error)
        """
        ...

    def debug(self, message: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Log debug message.

        Args:
            message: Log message.
            *args: Message format arguments.
            **kwargs: Additional keyword arguments.

        Example:
            logger.debug("Variable value: %s", variable)
        """
        ...

    def exception(self, message: str, *args: t.Any, **kwargs: t.Any) -> None:
        """Log exception with traceback.

        Args:
            message: Log message.
            *args: Message format arguments.
            **kwargs: Additional keyword arguments.

        Note:
            Automatically includes exception traceback.

        Example:
            try:
                risky_operation()
            except Exception:
                logger.exception("Operation failed")
        """
        ...


@t.runtime_checkable
class ConfigManagerProtocol(t.Protocol):
    """Protocol for configuration management.

    Handles loading, saving, and accessing configuration.

    Example:
        config: ConfigManagerProtocol = ConfigManager()
        value = config.get("key", default="default")
        config.set("key", "value")
        config.save()
    """

    def get(self, key: str, default: t.Any = None) -> t.Any:
        """Get configuration value.

        Args:
            key: Configuration key.
            default: Default value if key not found.

        Returns:
            Configuration value, or default if not found.

        Example:
            timeout = config.get("timeout", default=30)
        """
        ...

    def set(self, key: str, value: t.Any) -> None:
        """Set configuration value.

        Args:
            key: Configuration key.
            value: Value to set.

        Example:
            config.set("timeout", 60)
        """
        ...

    def save(self) -> bool:
        """Save configuration to file.

        Returns:
            True if saved successfully, False otherwise.

        Example:
            if config.save():
                print("Configuration saved")
        """
        ...

    def load(self) -> bool:
        """Load configuration from file.

        Returns:
            True if loaded successfully, False otherwise.

        Example:
            if config.load():
                print("Configuration loaded")
        """
        ...


@t.runtime_checkable
class FileSystemServiceProtocol(t.Protocol):
    """Protocol for basic file system operations.

    Provides simple file and directory operations.

    Example:
        fs: FileSystemServiceProtocol = FileSystemService()
        if fs.exists("/path/to/file"):
            content = fs.read_file("/path/to/file")
            fs.write_file("/path/to/output", content)
    """

    def read_file(self, path: str | Path) -> str:
        """Read file contents.

        Args:
            path: File path.

        Returns:
            File contents as string.

        Raises:
            FileNotFoundError: If file doesn't exist.

        Example:
            content = fs.read_file("/path/to/file.txt")
        """
        ...

    def write_file(self, path: str | Path, content: str) -> None:
        """Write content to file.

        Args:
            path: File path.
            content: Content to write.

        Example:
            fs.write_file("/path/to/file.txt", "Hello, world!")
        """
        ...

    def exists(self, path: str | Path) -> bool:
        """Check if path exists.

        Args:
            path: File or directory path.

        Returns:
            True if path exists, False otherwise.

        Example:
            if fs.exists("/path/to/file"):
                print("File exists")
        """
        ...

    def mkdir(self, path: str | Path, parents: bool = False) -> None:
        """Create directory.

        Args:
            path: Directory path.
            parents: Create parent directories if True.

        Example:
            fs.mkdir("/path/to/dir", parents=True)
        """
        ...


@t.runtime_checkable
class SafeFileModifierProtocol(t.Protocol):
    """Protocol for safe file modification operations.

    The safe file modifier provides security checks to prevent accidental
    modification of sensitive files (.env, .git, keys, etc.).

    Thread Safety:
        Should be thread-safe for file operations.

    Lifecycle:
        - Initialize with forbidden patterns
        - Validate file paths before operations
        - Perform safe modifications

    Common Implementations:
        - SafeFileModifier: Main implementation with security checks

    Example:
        ```python
        modifier: SafeFileModifierProtocol = SafeFileModifier()
        modifier.modify_file(Path("src/main.py"), content)
        ```
    """

    def modify_file(self, file_path: Path, new_content: str) -> None:
        """Safely modify a file with security validation.

        Args:
            file_path: Path to file to modify.
            new_content: New file content.

        Raises:
            ValueError: If file path is forbidden.
            OSError: If file operation fails.

        Example:
            ```python
            modifier.modify_file(Path("src/main.py"), "new content")
            ```
        """
        ...


@t.runtime_checkable
class EnhancedFileSystemServiceProtocol(ServiceProtocol, t.Protocol):
    """Enhanced file system service with async and caching.

    Provides advanced file operations with async support and caching.

    Thread Safety:
        File operations should be thread-safe.
        Cache operations are thread-safe.

    Example:
        fs: EnhancedFileSystemServiceProtocol = EnhancedFileSystemService()
        content = await fs.read_file_async(Path("file.txt"))
        await fs.write_file_async(Path("output.txt"), content)
    """

    def read_file(self, path: str | Path) -> str:
        """Read file contents synchronously.

        Args:
            path: File path.

        Returns:
            File contents as string.

        Example:
            content = fs.read_file("/path/to/file.txt")
        """
        ...

    def write_file(self, path: str | Path, content: str) -> None:
        """Write content to file synchronously.

        Args:
            path: File path.
            content: Content to write.

        Example:
            fs.write_file("/path/to/file.txt", "Hello")
        """
        ...

    async def read_file_async(self, path: Path) -> str:
        """Read file contents asynchronously.

        Args:
            path: File path.

        Returns:
            File contents as string.

        Example:
            content = await fs.read_file_async(Path("file.txt"))
        """
        ...

    async def write_file_async(self, path: Path, content: str) -> None:
        """Write content to file asynchronously.

        Args:
            path: File path.
            content: Content to write.

        Example:
            await fs.write_file_async(Path("file.txt"), "Hello")
        """
        ...

    async def read_multiple_files(self, paths: list[Path]) -> dict[Path, str]:
        """Read multiple files concurrently.

        Args:
            paths: List of file paths.

        Returns:
            Dictionary mapping paths to contents.

        Example:
            contents = await fs.read_multiple_files([
                Path("file1.txt"),
                Path("file2.txt"),
            ])
        """
        ...

    async def write_multiple_files(self, file_data: dict[Path, str]) -> None:
        """Write multiple files concurrently.

        Args:
            file_data: Dictionary mapping paths to contents.

        Example:
            await fs.write_multiple_files({
                Path("file1.txt"): "Content 1",
                Path("file2.txt"): "Content 2",
            })
        """
        ...

    def file_exists(self, path: str | Path) -> bool:
        """Check if file exists.

        Args:
            path: File path.

        Returns:
            True if file exists, False otherwise.

        Example:
            if fs.file_exists("/path/to/file"):
                print("File exists")
        """
        ...

    def create_directory(self, path: str | Path) -> None:
        """Create directory with parents.

        Args:
            path: Directory path.

        Example:
            fs.create_directory("/path/to/dir")
        """
        ...

    def delete_file(self, path: str | Path) -> None:
        """Delete file.

        Args:
            path: File path.

        Raises:
            FileNotFoundError: If file doesn't exist.

        Example:
            fs.delete_file("/path/to/file.txt")
        """
        ...

    def list_files(self, path: str | Path, pattern: str = "*") -> t.Iterator[Path]:
        """List files in directory matching pattern.

        Args:
            path: Directory path.
            pattern: Glob pattern (default: "*").

        Yields:
            File paths matching pattern.

        Example:
            for file_path in fs.list_files("/path", "*.py"):
                print(file_path)
        """
        ...

    async def flush_operations(self) -> None:
        """Flush all pending async operations.

        Example:
            await fs.flush_operations()
        """
        ...

    def get_cache_stats(self) -> dict[str, t.Any]:
        """Get file cache statistics.

        Returns:
            Cache statistics dictionary.

        Example:
            stats = fs.get_cache_stats()
            print(f"Cache hit rate: {stats['hit_rate']}")
        """
        ...

    def clear_cache(self) -> None:
        """Clear file cache.

        Example:
            fs.clear_cache()
        """
        ...

    def exists(self, path: str | Path) -> bool:
        """Check if path exists.

        Args:
            path: File or directory path.

        Returns:
            True if path exists, False otherwise.

        Example:
            if fs.exists("/path"):
                print("Path exists")
        """
        ...

    def mkdir(self, path: str | Path, parents: bool = False) -> None:
        """Create directory.

        Args:
            path: Directory path.
            parents: Create parent directories if True.

        Example:
            fs.mkdir("/path/to/dir", parents=True)
        """
        ...


# =============================================================================
# ADAPTER PROTOCOLS (3 protocols)
# =============================================================================


@t.runtime_checkable
class AdapterProtocol(t.Protocol):
    """Protocol for QA and AI adapters in crackerjack.

    Adapters provide extensible integration points for various quality
    assurance tools and AI code fixing services.

    Thread Safety:
        Individual adapters may or may not be thread-safe.
        Server manages adapter lifecycle.

    Lifecycle:
        - Instantiate with optional settings
        - Call init() to set up resources
        - Use adapter for checks/fixes
        - Call cleanup() when done

    Common Implementations:
        - BaseToolAdapter: Ruff, Bandit, Semgrep, etc.
        - BaseCodeFixer: ClaudeCodeFixer (AI agent)
        - BaseRustToolAdapter: Zuban, Skylos (LSP tools)

    Example:
        ```python
        adapter: AdapterProtocol = RuffAdapter(settings)
        await adapter.init()
        result = await adapter.check(files)
        adapter.cleanup()
        ```
    """

    async def init(self) -> None:
        """Initialize the adapter and set up resources.

        This method is called once after the adapter is instantiated.
        It should set up any necessary resources (executables, configs, etc.).

        Raises:
            RuntimeError: If initialization fails.

        Example:
            ```python
            await adapter.init()
            assert adapter.is_ready
            ```
        """
        ...


# Alias for backward compatibility
QAAdapterProtocol = AdapterProtocol


@t.runtime_checkable
class QAOrchestratorProtocol(t.Protocol):
    """Protocol for QA check orchestration and parallel execution.

    The QA orchestrator manages multiple QA adapters, runs checks in
    parallel, and aggregates results.

    Thread Safety:
        Should be thread-safe for async operations.

    Lifecycle:
        - Register adapters
        - Run checks (fast/comprehensive stages)
        - Cache results for performance

    Common Implementations:
        - QAOrchestrator: Main orchestration implementation

    Example:
        ```python
        orchestrator = QAOrchestrator(config)
        await orchestrator.register_adapter(ruff_adapter)
        results = await orchestrator.run_checks(stage="fast", files=[...])
        ```
    """

    async def register_adapter(self, adapter: "QAAdapterProtocol") -> None:
        """Register a QA adapter with the orchestrator.

        Args:
            adapter: Adapter instance to register.

        Example:
            ```python
            await orchestrator.register_adapter(ruff_adapter)
            ```
        """
        ...

    def get_adapter(self, name: str) -> "QAAdapterProtocol | None":
        """Get a registered adapter by name.

        Args:
            name: Adapter name.

        Returns:
            Adapter instance or None if not found.

        Example:
            ```python
            ruff = orchestrator.get_adapter("Ruff")
            ```
        """
        ...

    async def run_checks(
        self,
        stage: str = "fast",
        files: list["Path"] | None = None,
    ) -> list["QAResult"]:
        """Run QA checks for a stage.

        Args:
            stage: Stage name ("fast" or "comprehensive").
            files: Optional list of files to check.

        Returns:
            List of QA results.

        Raises:
            ValueError: If stage name is invalid.

        Example:
            ```python
            results = await orchestrator.run_checks(stage="fast", files=[Path("src")])
            ```
        """
        ...

    async def run_all_checks(
        self,
        files: list["Path"] | None = None,
    ) -> dict[str, t.Any]:
        """Run all QA checks (both fast and comprehensive).

        Args:
            files: Optional list of files to check.

        Returns:
            Dictionary with fast_stage, comprehensive_stage, all_results, and summary.

        Example:
            ```python
            all_results = await orchestrator.run_all_checks(files=[Path("src")])
            ```
        """
        ...


@t.runtime_checkable
class AdapterFactoryProtocol(t.Protocol):
    """Protocol for creating adapter instances.

    The adapter factory abstracts adapter creation, allowing for
    dependency injection and dynamic adapter loading.

    Thread Safety:
        Should be thread-safe for adapter creation.

    Lifecycle:
        - Create adapter instances on demand
        - No state to manage

    Common Implementations:
        - DefaultAdapterFactory: Standard adapter factory
        - TestAdapterFactory: Mock factory for testing

    Example:
        ```python
        factory: AdapterFactoryProtocol = DefaultAdapterFactory()
        ruff_adapter = factory.create_adapter("Ruff", settings)
        await ruff_adapter.init()
        ```
    """

    def create_adapter(
        self,
        adapter_name: str,
        settings: t.Any | None = None,
    ) -> "AdapterProtocol":
        """Create an adapter instance by name.

        Args:
            adapter_name: Name of the adapter to create (e.g., "Ruff", "Bandit").
            settings: Optional settings for the adapter.

        Returns:
            An adapter instance.

        Raises:
            ValueError: If adapter name is unknown.
            RuntimeError: If adapter creation fails.

        Example:
            ```python
            adapter = factory.create_adapter("Ruff", ruff_settings)
            assert isinstance(adapter, RuffAdapter)
            ```
        """
        ...


# =============================================================================
# AGENT COORDINATION PROTOCOLS (2 protocols)
# =============================================================================


@t.runtime_checkable
class DebuggerProtocol(t.Protocol):
    """Protocol for AI agent debugging and diagnostic logging.

    The debugger provides detailed logging and tracing for AI agent
    operations, useful for development and troubleshooting.

    Thread Safety:
        Should be thread-safe for all operations.

    Lifecycle:
        - Initialize with enabled/disabled state
        - Log agent operations throughout execution
        - Optional debug log file output

    Common Implementations:
        - AIAgentDebugger: Full debugging implementation
        - NoOpDebugger: No-op implementation for production

    Example:
        ```python
        debugger = AIAgentDebugger(enabled=True, verbose=True)
        with debugger.debug_operation("fix_issue", issue_id=123):
            result = await agent.fix(issue)
        debugger.log_agent_activity("FormattingAgent", "issue_fixed", ...)
        ```
    """

    @contextlib.contextmanager
    def debug_operation(self, operation: str, **kwargs: t.Any) -> t.Iterator[str]:
        """Context manager for debugging an operation.

        Args:
            operation: Name of the operation being debugged.
            **kwargs: Additional metadata about the operation.

        Yields:
            Unique operation ID for tracking.

        Example:
            ```python
            with debugger.debug_operation("fix_issue", issue_id=123) as op_id:
                result = await agent.fix(issue)
            ```
        """
        ...

    def log_agent_activity(
        self,
        agent_name: str,
        activity: str,
        issue_id: str | None = None,
        confidence: float | None = None,
        result: dict[str, t.Any] | None = None,
        metadata: dict[str, t.Any] | None = None,
    ) -> None:
        """Log agent activity for monitoring.

        Args:
            agent_name: Name of the agent performing activity.
            activity: Description of the activity.
            issue_id: Optional issue identifier.
            confidence: Optional confidence level.
            result: Optional result dictionary.
            metadata: Additional context about the activity.

        Example:
            ```python
            debugger.log_agent_activity(
                "FormattingAgent",
                "issue_fixed",
                issue_id="ISSUE-123",
                confidence=0.95,
                metadata={"file": "main.py", "lines_changed": 5}
            )
            ```
        """
        ...

    def log_mcp_operation(
        self,
        operation_type: str,
        tool_name: str,
        params: dict[str, t.Any] | None = None,
        result: dict[str, t.Any] | None = None,
    ) -> None:
        """Log MCP tool operation.

        Args:
            operation_type: Type of MCP operation.
            tool_name: Name of the tool being called.
            params: Optional parameters passed to tool.
            result: Optional result from tool.

        Example:
            ```python
            debugger.log_mcp_operation(
                "tool_call",
                "execute_crackerjack",
                params={"command": "run"},
                result={"status": "success"}
            )
            ```
        """
        ...


@t.runtime_checkable
class AgentTrackerProtocol(t.Protocol):
    """Protocol for tracking AI agent execution and results.

    The agent tracker monitors agent performance, caches results, and
    provides statistics on agent behavior.

    Thread Safety:
        Should be thread-safe for all operations.

    Lifecycle:
        - Initialize with optional console
        - Track agent invocations
        - Cache results for performance
        - Reset when needed

    Common Implementations:
        - AgentTracker: Main tracking implementation

    Example:
        ```python
        tracker = AgentTracker()
        tracker.register_agents(["FormattingAgent", "SecurityAgent"])
        tracker.track_agent_processing("FormattingAgent", issue, 0.95)
        tracker.track_agent_complete("FormattingAgent", result)
        ```
    """

    def register_agents(self, agent_types: list[str]) -> None:
        """Register agent types with the tracker.

        Args:
            agent_types: List of agent type names.

        Example:
            ```python
            tracker.register_agents(["FormattingAgent", "SecurityAgent"])
            ```
        """
        ...

    def track_agent_processing(
        self,
        agent_type: str,
        issue: "Issue",
        confidence: float,
    ) -> None:
        """Track that an agent is processing an issue.

        Args:
            agent_type: Type of agent processing the issue.
            issue: The issue being processed.
            confidence: Agent confidence level for this issue.

        Example:
            ```python
            tracker.track_agent_processing("FormattingAgent", issue, 0.95)
            ```
        """
        ...

    def track_agent_complete(
        self,
        agent_type: str,
        result: "FixResult",
    ) -> None:
        """Track that an agent has completed processing an issue.

        Args:
            agent_type: Type of agent that completed.
            result: The fix result from the agent.

        Example:
            ```python
            tracker.track_agent_complete("FormattingAgent", fix_result)
            ```
        """
        ...

    def set_coordinator_status(self, status: str) -> None:
        """Set the coordinator's current status.

        Args:
            status: Status string (e.g., "active", "idle", "processing").

        Example:
            ```python
            tracker.set_coordinator_status("processing")
            ```
        """
        ...

    def reset(self) -> None:
        """Reset all tracking data.

        Clears all cached results and statistics.

        Example:
            ```python
            tracker.reset()  # Start fresh
            ```
        """
        ...


@t.runtime_checkable
class AgentCoordinatorProtocol(t.Protocol):
    """Protocol for AI agent coordination and issue fixing.

    The agent coordinator manages multiple AI agents and routes issues
    to appropriate specialists for automated fixing.

    Thread Safety:
        Should be thread-safe for concurrent issue handling.

    Lifecycle:
        - Initialize with agent context
        - Register agents for specialized issue types
        - Handle issues via async methods
        - Cleanup when complete

    Common Implementations:
        - AgentCoordinator: Main coordination implementation

    Example:
        ```python
        coordinator = AgentCoordinator(context, cache)
        await coordinator.initialize_agents()
        result = await coordinator.handle_issues(issues)
        ```
    """

    async def handle_issues(self, issues: list["Issue"]) -> "FixResult":
        """Handle a list of issues using registered AI agents.

        Args:
            issues: List of issues to fix.

        Returns:
            FixResult with overall success status and remaining issues.

        Raises:
            RuntimeError: If no agents are available.
            ValueError: If issues list is invalid.

        Example:
            ```python
            issues = [Issue(type=IssueType.FORMATTING, ...)]
            result = await coordinator.handle_issues(issues)
            if result.success:
                print("All issues fixed!")
            ```
        """
        ...

    def initialize_agents(self) -> None:
        """Initialize all registered AI agents.

        This method sets up the agent pool and prepares agents for use.

        Raises:
            RuntimeError: If agent initialization fails.

        Example:
            ```python
            coordinator.initialize_agents()
            assert len(coordinator.agents) > 0
            ```
        """
        ...


@t.runtime_checkable
class MemoryOptimizerProtocol(t.Protocol):
    """Protocol for memory optimization and resource management.

    The memory optimizer manages lazy objects, resource pools, and
    performs memory cleanup to prevent memory leaks.

    Thread Safety:
        Should be thread-safe for all operations.

    Lifecycle:
        - Register lazy objects and resource pools
        - Periodically optimize memory
        - Get statistics on memory usage

    Common Implementations:
        - MemoryOptimizer: Main optimization implementation

    Example:
        ```python
        optimizer = MemoryOptimizer()
        optimizer.register_lazy_object(my_lazy_loader)
        optimizer.optimize_memory()  # Free unused memory
        stats = optimizer.get_stats()
        ```
    """

    def optimize_memory(self) -> None:
        """Run memory optimization and cleanup.

        This method cleans up unused lazy objects, drains resource pools,
        and runs garbage collection to free memory.

        Example:
            ```python
            optimizer.optimize_memory()
            # Lazy objects are cleaned up, GC runs
            ```
        """
        ...

    def register_lazy_object(self, lazy_obj: t.Any) -> None:
        """Register a lazy object for memory tracking.

        Args:
            lazy_obj: Lazy object to track (typically LazyLoader instances).

        Example:
            ```python
            lazy_loader = LazyLoader(lambda: expensive_operation())
            optimizer.register_lazy_object(lazy_loader)
            ```
        """
        ...

    def get_stats(self) -> dict[str, t.Any]:
        """Get memory optimization statistics.

        Returns:
            Dictionary with stats like pool sizes, lazy object counts, etc.

        Example:
            ```python
            stats = optimizer.get_stats()
            print(f"Lazy objects: {stats['lazy_count']}")
            print(f"Pool size: {stats['pool_size']}")
            ```
        """
        ...


@t.runtime_checkable
class PluginRegistryProtocol(t.Protocol):
    """Protocol for plugin registration and lifecycle management.

    The plugin registry manages plugin discovery, registration, activation,
    and provides access to plugin metadata and instances.

    Thread Safety:
        Should be thread-safe for all operations.

    Lifecycle:
        - Register plugins during initialization
        - Activate/deactivate plugins as needed
        - Query plugin metadata and capabilities

    Common Implementations:
        - PluginRegistry: Main registry implementation in plugins/base.py

    Example:
        ```python
        registry = PluginRegistry()
        registry.register_plugin(my_plugin)
        registry.activate_plugin("my_plugin")
        plugins = registry.get_plugins_by_type(PluginType.QA)
        ```
    """

    def register_plugin(self, plugin: t.Any) -> None:
        """Register a plugin instance.

        Args:
            plugin: Plugin instance to register.

        Example:
            ```python
            registry.register_plugin(MyQAPlugin())
            ```
        """
        ...

    def activate_plugin(self, plugin_name: str) -> None:
        """Activate a registered plugin.

        Args:
            plugin_name: Name of the plugin to activate.

        Example:
            ```python
            registry.activate_plugin("ruff_adapter")
            ```
        """
        ...

    def deactivate_plugin(self, plugin_name: str) -> None:
        """Deactivate a plugin.

        Args:
            plugin_name: Name of the plugin to deactivate.

        Example:
            ```python
            registry.deactivate_plugin("ruff_adapter")
            ```
        """
        ...

    def get_plugin(self, plugin_name: str) -> t.Any | None:
        """Get a plugin by name.

        Args:
            plugin_name: Name of the plugin to retrieve.

        Returns:
            Plugin instance or None if not found.

        Example:
            ```python
            ruff = registry.get_plugin("ruff_adapter")
            if ruff:
                ruff.run_checks()
            ```
        """
        ...

    def get_plugins_by_type(self, plugin_type: t.Any) -> list[t.Any]:
        """Get all plugins of a specific type.

        Args:
            plugin_type: Type filter (e.g., PluginType.QA).

        Returns:
            List of plugin instances matching the type.

        Example:
            ```python
            from crackerjack.plugins.base import PluginType

            qa_plugins = registry.get_plugins_by_type(PluginType.QA)
            for plugin in qa_plugins:
                plugin.run_checks()
            ```
        """
        ...

    def list_plugins(self) -> list[str]:
        """List all registered plugin names.

        Returns:
            List of plugin names.

        Example:
            ```python
            plugins = registry.list_plugins()
            print(f"Registered plugins: {', '.join(plugins)}")
            ```
        """
        ...


@t.runtime_checkable
class AgentRegistryProtocol(t.Protocol):
    """Protocol for agent registration and discovery.

    The agent registry manages AI agent instances, handles agent creation
    and lifecycle, and provides lookup capabilities for agent coordination.

    Thread Safety:
        Should be thread-safe for all operations.

    Lifecycle:
        - Register agents during initialization
        - Create agent instances on demand
        - Track agent status and capabilities

    Common Implementations:
        - AgentRegistry: Main registry implementation in intelligence/agent_registry.py

    Example:
        ```python
        registry = await get_agent_registry()
        specialist = registry.get_agent("RefactoringAgent")
        if specialist:
            result = await specialist.analyze_and_fix(issue)
        ```
    """

    async def register_agent(
        self,
        agent_name: str,
        agent_class: type[t.Any],
    ) -> None:
        """Register an agent class.

        Args:
            agent_name: Name to register the agent under.
            agent_class: Agent class to register.

        Example:
            ```python
            await registry.register_agent(
                "RefactoringAgent",
                RefactoringAgent
            )
            ```
        """
        ...

    def get_agent(self, agent_name: str) -> t.Any | None:
        """Get an agent instance by name.

        Args:
            agent_name: Name of the agent to retrieve.

        Returns:
            Agent instance or None if not found.

        Example:
            ```python
            agent = registry.get_agent("RefactoringAgent")
            if agent:
                result = await agent.analyze_and_fix(issue)
            ```
        """
        ...

    def list_agents(self) -> list[str]:
        """List all registered agent names.

        Returns:
            List of agent names.

        Example:
            ```python
            agents = registry.list_agents()
            print(f"Available agents: {', '.join(agents)}")
            ```
        """
        ...

    async def create_agent(self, agent_name: str, context: t.Any) -> t.Any:
        """Create an agent instance with context.

        Args:
            agent_name: Name of the agent to create.
            context: Agent context (AgentContext or similar).

        Returns:
            Agent instance.

        Raises:
            ValueError: If agent name is unknown.

        Example:
            ```python
            agent = await registry.create_agent(
                "RefactoringAgent",
                agent_context
            )
            result = await agent.analyze_and_fix(issue)
            ```
        """
        ...


@t.runtime_checkable
class ReflectionLoopProtocol(t.Protocol):
    """Protocol for reflection and continuous learning cycles.

    The reflection loop manages periodic reflection cycles, collects
    performance metrics, and triggers adaptive improvements based
    on historical patterns.

    Thread Safety:
        Should be thread-safe for all operations.

    Lifecycle:
        - Start reflection loop during initialization
        - Run periodic reflection cycles
        - Collect and analyze metrics
        - Trigger adaptive improvements

    Common Implementations:
        - ReflectionLoop: Main implementation in reflection_loop.py

    Example:
        ```python
        loop = ReflectionLoop(context=settings)
        await loop.start()
        # Loop runs periodic reflections
        await loop.stop()
        ```
    """

    async def start(self) -> None:
        """Start the reflection loop.

        Begins periodic reflection cycles. The loop will run
        asynchronously and collect metrics over time.

        Example:
            ```python
            await loop.start()
            # Reflection cycles begin
            ```
        """
        ...

    async def stop(self) -> None:
        """Stop the reflection loop.

        Gracefully stops the reflection loop and finalizes
        any pending reflection cycles.

        Example:
            ```python
            await loop.stop()
            # Reflection cycles end
            ```
        """
        ...

    async def trigger_reflection(self) -> dict[str, t.Any]:
        """Trigger an immediate reflection cycle.

        Forces a reflection cycle to run immediately, regardless
        of the periodic schedule.

        Returns:
            Dictionary with reflection results and insights.

        Example:
            ```python
            insights = await loop.trigger_reflection()
            print(f"Patterns found: {insights['pattern_count']}")
            ```
        """
        ...

    def get_metrics(self) -> dict[str, t.Any]:
        """Get reflection loop metrics.

        Returns:
            Dictionary with metrics like cycle count, success rate, etc.

        Example:
            ```python
            metrics = loop.get_metrics()
            print(f"Reflection cycles: {metrics['cycle_count']}")
            print(f"Success rate: {metrics['success_rate']:.2%}")
            ```
        """
        ...

    def is_running(self) -> bool:
        """Check if the reflection loop is currently running.

        Returns:
            True if loop is running, False otherwise.

        Example:
            ```python
            if loop.is_running():
                print("Reflection loop is active")
            ```
        """
        ...


@t.runtime_checkable
class ChangelogGeneratorProtocol(t.Protocol):
    """Protocol for automatic changelog generation from git commits.

    The changelog generator analyzes git commits, generates changelog entries
    following conventional commit format, and updates CHANGELOG.md files.

    Thread Safety:
        Should be thread-safe for all operations.

    Lifecycle:
        - Parse git commits
        - Generate changelog entries
        - Update changelog file

    Common Implementations:
        - ChangelogGenerator: Main implementation in services/changelog_automation.py

    Example:
        ```python
        generator = ChangelogGenerator(project_path=Path.cwd())
        generator.generate_changelog_from_commits(since_version="v0.1.0")
        ```
    """

    def generate_changelog_from_commits(
        self,
        since_version: str | None = None,
        preview: bool = True,
    ) -> bool:
        """Generate changelog from git commits.

        Args:
            since_version: Starting version tag (None = all commits).
            preview: Whether to show preview before writing.

        Returns:
            True if changelog was generated successfully.

        Example:
            ```python
            success = generator.generate_changelog_from_commits(
                since_version="v0.1.0",
                preview=True
            )
            ```
        """
        ...

    def update_changelog(
        self,
        entries: list[t.Any],
        version: str | None = None,
    ) -> None:
        """Update changelog file with new entries.

        Args:
            entries: List of changelog entries to add.
            version: Optional version string for section header.

        Example:
            ```python
            entries = [ChangelogEntry(...)]
            generator.update_changelog(entries, version="v0.2.0")
            ```
        """
        ...


# Alias for backward compatibility
GitServiceProtocol = GitInterface


@t.runtime_checkable
class RegexPatternsProtocol(t.Protocol):
    """Protocol for regex pattern operations on project files.

    Provides methods for updating file contents using regex patterns,
    particularly for version updates and other structured modifications.

    Thread Safety:
        Should be thread-safe for all operations.

    Common Implementations:
        - RegexPatternsService: Main implementation in services/patterns/

    Example:
        ```python
        patterns = RegexPatternsService()
        updated = patterns.update_pyproject_version(content, "0.2.0")
        ```
    """

    def update_pyproject_version(self, content: str, version: str) -> str:
        """Update version in pyproject.toml content.

        Args:
            content: pyproject.toml file content.
            version: New version string (e.g., "0.2.0").

        Returns:
            Updated content with version replaced.

        Example:
            ```python
            updated = patterns.update_pyproject_version(
                'version = "0.1.0"',
                "0.2.0"
            )
            # Returns: 'version = "0.2.0"'
            ```
        """
        ...


@t.runtime_checkable
class VersionAnalyzerProtocol(t.Protocol):
    """Protocol for version bump analysis and recommendations.

    Analyzes changelog entries and recommends version bump types
    (major, minor, patch) following semantic versioning.

    Thread Safety:
        Should be thread-safe for all operations.

    Common Implementations:
        - VersionAnalyzer: Main implementation in services/version_analyzer.py

    Example:
        ```python
        analyzer = VersionAnalyzer(project_path=Path.cwd())
        recommendation = await analyzer.recommend_version_bump()
        analyzer.display_recommendation(recommendation)
        ```
    """

    async def recommend_version_bump(
        self,
        entries: list[t.Any] | None = None,
    ) -> t.Any:
        """Analyze changes and recommend version bump.

        Args:
            entries: Optional list of changelog entries to analyze.

        Returns:
            VersionBumpRecommendation with bump type and confidence.

        Example:
            ```python
            recommendation = await analyzer.recommend_version_bump()
            # Returns: VersionBumpRecommendation(bump_type='minor', confidence=0.9)
            ```
        """
        ...

    def display_recommendation(self, recommendation: t.Any) -> None:
        """Display version bump recommendation to console.

        Args:
            recommendation: VersionBumpRecommendation to display.

        Example:
            ```python
            analyzer.display_recommendation(recommendation)
            # Output: Recommended version bump: minor (0.1.0 → 0.2.0)
            ```
        """
        ...


# Additional missing protocols


@t.runtime_checkable
class AsyncCommandExecutorProtocol(t.Protocol):
    """Protocol for asynchronous command execution.

    Executes shell commands asynchronously with timeout and error handling.
    """

    async def execute(
        self,
        command: list[str],
        timeout: int = 300,
    ) -> t.Any:
        """Execute command asynchronously."""
        ...


@t.runtime_checkable
class CoverageBadgeServiceProtocol(t.Protocol):
    """Protocol for coverage badge generation and updates.

    Generates README badges from coverage data.
    """

    def update_badge(self, coverage_percentage: float) -> bool:
        """Update coverage badge in README."""
        ...


@t.runtime_checkable
class ParallelHookExecutorProtocol(t.Protocol):
    """Protocol for parallel hook execution.

    Executes multiple quality hooks in parallel with dependency management.
    """

    async def execute_hooks_parallel(
        self,
        hooks: list[t.Any],
        max_workers: int = 4,
    ) -> list[t.Any]:
        """Execute hooks in parallel."""
        ...


@t.runtime_checkable
class PerformanceCacheProtocol(t.Protocol):
    """Protocol for performance metrics caching.

    Caches performance metrics to avoid repeated expensive operations.
    """

    def get(self, key: str) -> t.Any | None:
        """Get cached value."""
        ...

    def set(self, key: str, value: t.Any) -> None:
        """Set cached value."""
        ...


@t.runtime_checkable
class QualityBaselineProtocol(t.Protocol):
    """Protocol for quality baseline management.

    Tracks and enforces quality metrics baselines.
    """

    def get_baseline(self, metric: str) -> float:
        """Get baseline value for metric."""
        ...

    def update_baseline(self, metric: str, value: float) -> None:
        """Update baseline value."""
        ...


@t.runtime_checkable
class QualityIntelligenceProtocol(t.Protocol):
    """Protocol for quality intelligence and analytics.

    Analyzes quality trends and provides insights.
    """

    def analyze_trends(self, data: list[t.Any]) -> dict[str, t.Any]:
        """Analyze quality trends."""
        ...


@t.runtime_checkable
class SecureStatusFormatterProtocol(t.Protocol):
    """Protocol for secure status formatting.

    Formats status messages with sensitive data redaction.
    """

    def format(self, status: t.Any) -> str:
        """Format status for display."""
        ...


@t.runtime_checkable
class SmartFileFilterProtocol(t.Protocol):
    """Protocol for intelligent file filtering.

    Filters files based on patterns, size, and other criteria.
    """

    def should_include(self, file_path: Path) -> bool:
        """Determine if file should be included."""
        ...

    def filter_files(self, files: list[Path]) -> list[Path]:
        """Filter list of files."""
        ...


# Backward compatibility aliases already defined in-line
# QAAdapterProtocol = AdapterProtocol (defined at line 2903)
