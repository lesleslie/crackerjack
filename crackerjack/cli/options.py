import typing as t
import warnings
from enum import Enum

import typer
from pydantic import BaseModel, field_validator, model_validator


class BumpOption(str, Enum):
    patch = "patch"
    minor = "minor"
    major = "major"
    interactive = "interactive"

    def __str__(self) -> str:
        return self.value


class Options(BaseModel):
    commit: bool = False
    interactive: bool = False
    no_config_updates: bool = False
    update_precommit: bool = False
    publish: BumpOption | None = None
    bump: BumpOption | None = None
    verbose: bool = False
    debug: bool = False
    clean: bool = False
    test: bool = False
    benchmark: bool = False
    test_workers: int = 0
    test_timeout: int = 0
    all: BumpOption | None = None
    ai_agent: bool = False
    start_mcp_server: bool = False
    stop_mcp_server: bool = False
    restart_mcp_server: bool = False
    create_pr: bool = False
    skip_hooks: bool = False
    fast: bool = False
    comp: bool = False
    async_mode: bool = False
    experimental_hooks: bool = False
    enable_pyrefly: bool = False
    enable_ty: bool = False
    cleanup: t.Any | None = None
    no_git_tags: bool = False
    skip_version_check: bool = False
    cleanup_pypi: bool = False
    keep_releases: int = 10
    track_progress: bool = False
    orchestrated: bool = False
    boost_coverage: bool = True
    coverage: bool = False
    orchestration_strategy: str = "adaptive"
    orchestration_progress: str = "granular"
    orchestration_ai_mode: str = "single-agent"
    monitor: bool = False
    enhanced_monitor: bool = False
    watchdog: bool = False
    start_websocket_server: bool = False
    stop_websocket_server: bool = False
    restart_websocket_server: bool = False
    websocket_port: int | None = None
    dev: bool = False
    dashboard: bool = False
    max_iterations: int = 5
    enterprise_batch: str | None = None
    monitor_dashboard: str | None = None
    coverage_status: bool = False
    coverage_goal: float | None = None
    no_coverage_ratchet: bool = False
    skip_config_merge: bool = False
    disable_global_locks: bool = False
    global_lock_timeout: int = 600
    global_lock_cleanup: bool = True
    global_lock_dir: str | None = None
    quick: bool = False
    thorough: bool = False
    clear_cache: bool = False
    cache_stats: bool = False

    # Semantic field names (new primary interface)
    strip_code: bool | None = None  # Replaces clean
    run_tests: bool | None = None  # Replaces test
    ai_fix: bool | None = None  # Replaces ai_agent
    full_release: BumpOption | None = None  # Replaces all
    show_progress: bool | None = None  # Replaces track_progress
    advanced_monitor: bool | None = None  # Replaces enhanced_monitor
    coverage_report: bool | None = None  # Replaces coverage_status
    clean_releases: bool | None = None  # Replaces cleanup_pypi

    @model_validator(mode="after")
    def handle_legacy_mappings(self) -> "Options":
        """Handle backward compatibility for deprecated flags."""
        # Map clean -> strip_code
        if self.clean and self.strip_code is None:
            self.strip_code = True
            warnings.warn(
                "--clean is deprecated, use --strip-code",
                DeprecationWarning,
                stacklevel=3,
            )
        elif self.strip_code is not None:
            self.clean = self.strip_code

        # Map test -> run_tests
        if self.test and self.run_tests is None:
            self.run_tests = True
            warnings.warn(
                "--test is deprecated, use --run-tests",
                DeprecationWarning,
                stacklevel=3,
            )
        elif self.run_tests is not None:
            self.test = self.run_tests

        # Map ai_agent -> ai_fix
        if self.ai_agent and self.ai_fix is None:
            self.ai_fix = True
            warnings.warn(
                "--ai-agent is deprecated, use --ai-fix",
                DeprecationWarning,
                stacklevel=3,
            )
        elif self.ai_fix is not None:
            self.ai_agent = self.ai_fix

        # Map all -> full_release
        if self.all and self.full_release is None:
            self.full_release = self.all
            warnings.warn(
                "--all is deprecated, use --full-release",
                DeprecationWarning,
                stacklevel=3,
            )
        elif self.full_release is not None:
            self.all = self.full_release

        # Map track_progress -> show_progress
        if self.track_progress and self.show_progress is None:
            self.show_progress = True
        elif self.show_progress is not None:
            self.track_progress = self.show_progress

        # Map enhanced_monitor -> advanced_monitor
        if self.enhanced_monitor and self.advanced_monitor is None:
            self.advanced_monitor = True
        elif self.advanced_monitor is not None:
            self.enhanced_monitor = self.advanced_monitor

        # Map coverage_status -> coverage_report
        if self.coverage_status and self.coverage_report is None:
            self.coverage_report = True
        elif self.coverage_report is not None:
            self.coverage_status = self.coverage_report

        # Map cleanup_pypi -> clean_releases
        if self.cleanup_pypi and self.clean_releases is None:
            self.clean_releases = True
        elif self.clean_releases is not None:
            self.cleanup_pypi = self.clean_releases

        return self

    @property
    def effective_max_iterations(self) -> int:
        if self.quick:
            return 3
        if self.thorough:
            return 8
        return self.max_iterations

    @classmethod
    @field_validator("publish", "bump", "full_release", mode="before")
    def validate_bump_options(cls, value: t.Any) -> BumpOption | None:
        if value is None:
            return None
        if value == "":
            return BumpOption.interactive
        try:
            return BumpOption(value.lower())
        except ValueError:
            valid_options = ", ".join([o.value for o in BumpOption])
            msg = f"Invalid bump option: {value}. Must be one of: {valid_options}"
            raise ValueError(
                msg,
            )


CLI_OPTIONS = {
    "commit": typer.Option(
        False,
        "-c",
        "--commit",
        help="Commit and push changes to Git.",
    ),
    "interactive": typer.Option(
        False,
        "-i",
        "--interactive",
        help="Use the interactive Rich UI for a better experience.",
    ),
    "no_config_updates": typer.Option(
        False,
        "-n",
        "--no-config-updates",
        help="Do not update configuration files.",
    ),
    "update_precommit": typer.Option(
        False,
        "-u",
        "--update-precommit",
        help="Update pre-commit hooks configuration.",
    ),
    "verbose": typer.Option(False, "-v", "--verbose", help="Enable verbose output."),
    "debug": typer.Option(False, "--debug", help="Enable debug output."),
    "publish": typer.Option(
        None,
        "-p",
        "--publish",
        help=(
            "Bump version and publish to PyPI (patch, minor, major). "
            "Use 'interactive' to be prompted for version selection."
        ),
        case_sensitive=False,
    ),
    "bump": typer.Option(
        None,
        "-b",
        "--bump",
        help="Bump version (patch, minor, major).",
        case_sensitive=False,
    ),
    "clean": typer.Option(
        False,
        "-x",
        "--clean",
        help="Remove docstrings, line comments, and unnecessary whitespace from source code with automatic backup protection (doesn't affect test files).",
    ),
    "test": typer.Option(False, "-t", "--test", help="Run tests."),
    "benchmark": typer.Option(
        False,
        "--benchmark",
        help="Run tests in benchmark mode (disables parallel execution).",
    ),
    "test_workers": typer.Option(
        0,
        "--test-workers",
        help=(
            "Number of parallel workers for running tests "
            "(0 = auto-detect, 1 = disable parallelization)."
        ),
    ),
    "test_timeout": typer.Option(
        0,
        "--test-timeout",
        help=(
            "Timeout in seconds for individual tests "
            "(0 = use default based on project size)."
        ),
    ),
    "skip_hooks": typer.Option(
        False,
        "-s",
        "--skip-hooks",
        help="Skip running pre-commit hooks (useful with -t).",
    ),
    "fast": typer.Option(
        False,
        "--fast",
        help="Run only fast hooks (formatting and basic checks).",
    ),
    "comp": typer.Option(
        False,
        "--comp",
        help=(
            "Run only comprehensive hooks (type checking, security, "
            "complexity analysis)."
        ),
    ),
    "all": typer.Option(
        None,
        "-a",
        "--all",
        help="Run with `-x -t -p <patch|minor|major> -c` development options).",
        case_sensitive=False,
    ),
    "create_pr": typer.Option(
        False,
        "-r",
        "--pr",
        "--new-pull-request",
        help="Create a new pull request to the upstream repository.",
    ),
    "ai_agent": typer.Option(
        False,
        "--ai-agent",
        help="Enable AI agent mode with autonomous auto-fixing.",
    ),
    "start_mcp_server": typer.Option(
        False,
        "--start-mcp-server",
        help="Start MCP server for AI agent integration.",
    ),
    "stop_mcp_server": typer.Option(
        False,
        "--stop-mcp-server",
        help="Stop all running MCP servers.",
    ),
    "restart_mcp_server": typer.Option(
        False,
        "--restart-mcp-server",
        help="Restart MCP server (stop and start again).",
    ),
    "async_mode": typer.Option(
        False,
        "--async",
        help="Enable async mode for faster file operations (experimental).",
        hidden=True,
    ),
    "experimental_hooks": typer.Option(
        False,
        "--experimental-hooks",
        help="Enable experimental pre-commit hooks (includes pyrefly and ty).",
    ),
    "enable_pyrefly": typer.Option(
        False,
        "--enable-pyrefly",
        help=(
            "Enable pyrefly experimental type checking "
            "(requires experimental hooks mode)."
        ),
    ),
    "enable_ty": typer.Option(
        False,
        "--enable-ty",
        help=(
            "Enable ty experimental type verification "
            "(requires experimental hooks mode)."
        ),
    ),
    "no_git_tags": typer.Option(
        False,
        "--no-git-tags",
        help=(
            "Skip creating git tags during version bumping "
            "(tags are created by default)."
        ),
    ),
    "skip_version_check": typer.Option(
        False,
        "--skip-version-check",
        help=(
            "Skip version consistency verification between pyproject.toml and git tags."
        ),
    ),
    "start_websocket_server": typer.Option(
        False,
        "--start-websocket-server",
        help="Start WebSocket progress server on port 8675.",
    ),
    "stop_websocket_server": typer.Option(
        False,
        "--stop-websocket-server",
        help="Stop all running WebSocket servers.",
    ),
    "restart_websocket_server": typer.Option(
        False,
        "--restart-websocket-server",
        help="Restart WebSocket server (stop and start again).",
    ),
    "websocket_port": typer.Option(
        None,
        "--websocket-port",
        help="Port for WebSocket server when using --start-mcp-server (e.g., 8675).",
    ),
    "watchdog": typer.Option(
        False,
        "--watchdog",
        help=(
            "Start service watchdog to monitor and auto-restart "
            "MCP and WebSocket servers."
        ),
    ),
    "monitor": typer.Option(
        False,
        "--monitor",
        help=(
            "Start multi-project progress monitor with WebSocket polling, "
            "watchdog services, and autodiscovery."
        ),
    ),
    "enhanced_monitor": typer.Option(
        False,
        "--enhanced-monitor",
        help=(
            "Start enhanced progress monitor with advanced MetricCard widgets "
            "and modern web UI patterns."
        ),
    ),
    "dev": typer.Option(
        False,
        "--dev",
        help=(
            "Enable development mode for progress monitors "
            "(enables textual --dev mode)."
        ),
    ),
    "dashboard": typer.Option(
        False,
        "--dashboard",
        help=(
            "Start the comprehensive dashboard with system metrics, "
            "job tracking, and performance monitoring."
        ),
    ),
    "max_iterations": typer.Option(
        5,
        "--max-iterations",
        help="Maximum number of iterations for AI agent auto-fixing workflows (default: 5).",
    ),
    "ai_debug": typer.Option(
        False,
        "--ai-debug",
        help="Enable verbose debugging for AI agent mode (implies --ai-agent).",
    ),
    "job_id": typer.Option(
        None,
        "--job-id",
        help="Job ID for WebSocket progress tracking (internal use).",
        hidden=True,
    ),
    "orchestrated": typer.Option(
        False,
        "--orchestrated",
        help="Enable advanced orchestrated workflow mode with intelligent execution strategies, granular progress tracking, and multi-agent AI coordination.",
    ),
    "orchestration_strategy": typer.Option(
        "adaptive",
        "--orchestration-strategy",
        help="Execution strategy for orchestrated mode: batch, individual, adaptive, selective (default: adaptive).",
    ),
    "orchestration_progress": typer.Option(
        "granular",
        "--orchestration-progress",
        help="Progress tracking level: basic, detailed, granular, streaming (default: granular).",
    ),
    "orchestration_ai_mode": typer.Option(
        "single-agent",
        "--orchestration-ai-mode",
        help=(
            "AI coordination mode: single-agent, multi-agent, coordinator "
            "(default: single-agent)."
        ),
    ),
    "coverage_status": typer.Option(
        False,
        "--coverage-status",
        help="Show current coverage ratchet status and progress toward 100%.",
    ),
    "coverage_goal": typer.Option(
        None,
        "--coverage-goal",
        help="Set explicit coverage target for this session (e.g., 15.0).",
    ),
    "no_coverage_ratchet": typer.Option(
        False,
        "--no-coverage-ratchet",
        help="Disable coverage ratchet system temporarily (for experiments).",
    ),
    "boost_coverage": typer.Option(
        True,
        "--boost-coverage/--no-boost-coverage",
        help=(
            "Automatically improve test coverage after successful "
            "workflow execution (default: True)."
        ),
    ),
    "disable_global_locks": typer.Option(
        False,
        "--disable-global-locks",
        help=(
            "Disable global locking (allow concurrent hook execution across sessions)."
        ),
    ),
    "global_lock_timeout": typer.Option(
        600,
        "--global-lock-timeout",
        help="Global lock timeout in seconds (default: 600).",
    ),
    "global_lock_cleanup": typer.Option(
        True,
        "--cleanup-stale-locks/--no-cleanup-stale-locks",
        help="Clean up stale global lock files before execution (default: True).",
    ),
    "global_lock_dir": typer.Option(
        None,
        "--global-lock-dir",
        help="Custom directory for global lock files (default: ~/.crackerjack/locks).",
    ),
    "quick": typer.Option(
        False,
        "--quick",
        help="Quick mode: Run with maximum 3 iterations (ideal for CI/CD).",
    ),
    "thorough": typer.Option(
        False,
        "--thorough",
        help="Thorough mode: Run with maximum 8 iterations (for complex refactoring).",
    ),
    "clear_cache": typer.Option(
        False,
        "--clear-cache",
        help="Clear all caches (hook results, file hashes, agent decisions) and exit.",
    ),
    "cache_stats": typer.Option(
        False,
        "--cache-stats",
        help="Display cache statistics (hit rates, sizes, entries) and exit.",
    ),
    # New semantic CLI options with backward compatibility
    "strip_code": typer.Option(
        None,
        "--strip-code",
        help="Remove docstrings, line comments, and unnecessary whitespace from source code with automatic backup protection (doesn't affect test files). [Semantic alias for --clean]",
    ),
    "run_tests": typer.Option(
        None,
        "--run-tests",
        help=(
            "Execute the test suite with automatic worker detection "
            "and timeout handling. [Semantic alias for --test]"
        ),
    ),
    "ai_fix": typer.Option(
        None,
        "--ai-fix",
        help=(
            "Enable AI-powered automatic fixing of code quality issues "
            "and test failures. [Semantic alias for --ai-agent]"
        ),
    ),
    "full_release": typer.Option(
        None,
        "--full-release",
        help="Complete release workflow: strip code, run tests, bump version, and publish. Equivalent to `-x -t -p <version> -c`. [Semantic alias for --all]",
        case_sensitive=False,
    ),
    "show_progress": typer.Option(
        None,
        "--show-progress",
        help=(
            "Display detailed progress tracking during execution. "
            "[Semantic alias for --track-progress]"
        ),
    ),
    "advanced_monitor": typer.Option(
        None,
        "--advanced-monitor",
        help=(
            "Enable advanced monitoring dashboard with detailed metrics "
            "and analytics. [Semantic alias for --enhanced-monitor]"
        ),
    ),
    "coverage_report": typer.Option(
        None,
        "--coverage-report",
        help=(
            "Display comprehensive coverage analysis and report. "
            "[Semantic alias for --coverage-status]"
        ),
    ),
    "clean_releases": typer.Option(
        None,
        "--clean-releases",
        help=(
            "Clean up old releases from PyPI, keeping only the most recent "
            "versions. [Semantic alias for --cleanup-pypi]"
        ),
    ),
    "generate_docs": typer.Option(
        False,
        "--generate-docs",
        help=(
            "Generate comprehensive API documentation from source code "
            "with AST analysis and cross-references."
        ),
    ),
    "docs_format": typer.Option(
        "markdown",
        "--docs-format",
        help="Documentation output format: 'markdown' (default), 'rst', or 'html'.",
    ),
    "validate_docs": typer.Option(
        False,
        "--validate-docs",
        help="Validate existing documentation for completeness and consistency.",
    ),
}


def create_options(
    commit: bool,
    interactive: bool,
    no_config_updates: bool,
    update_precommit: bool,
    verbose: bool,
    debug: bool,
    publish: BumpOption | None,
    all: BumpOption | None,
    bump: BumpOption | None,
    clean: bool,
    test: bool,
    benchmark: bool,
    test_workers: int,
    test_timeout: int,
    skip_hooks: bool,
    fast: bool,
    comp: bool,
    create_pr: bool,
    ai_agent: bool,
    async_mode: bool,
    experimental_hooks: bool,
    enable_pyrefly: bool,
    enable_ty: bool,
    no_git_tags: bool,
    skip_version_check: bool,
    orchestrated: bool,
    orchestration_strategy: str,
    orchestration_progress: str,
    orchestration_ai_mode: str,
    dev: bool,
    dashboard: bool,
    max_iterations: int,
    coverage_status: bool,
    coverage_goal: float | None,
    no_coverage_ratchet: bool,
    boost_coverage: bool,
    disable_global_locks: bool,
    global_lock_timeout: int,
    global_lock_cleanup: bool,
    global_lock_dir: str | None,
    quick: bool,
    thorough: bool,
    clear_cache: bool,
    cache_stats: bool,
    generate_docs: bool,
    docs_format: str,
    validate_docs: bool,
    # New semantic parameters
    strip_code: bool | None = None,
    run_tests: bool | None = None,
    ai_fix: bool | None = None,
    full_release: BumpOption | None = None,
    show_progress: bool | None = None,
    advanced_monitor: bool | None = None,
    coverage_report: bool | None = None,
    clean_releases: bool | None = None,
) -> Options:
    return Options(
        commit=commit,
        interactive=interactive,
        no_config_updates=no_config_updates,
        update_precommit=update_precommit,
        verbose=verbose,
        debug=debug,
        publish=publish,
        bump=bump,
        clean=clean,
        test=test,
        benchmark=benchmark,
        test_workers=test_workers,
        test_timeout=test_timeout,
        skip_hooks=skip_hooks,
        fast=fast,
        comp=comp,
        all=all,
        ai_agent=ai_agent,
        create_pr=create_pr,
        async_mode=async_mode,
        experimental_hooks=experimental_hooks,
        enable_pyrefly=enable_pyrefly,
        enable_ty=enable_ty,
        no_git_tags=no_git_tags,
        skip_version_check=skip_version_check,
        orchestrated=orchestrated,
        orchestration_strategy=orchestration_strategy,
        orchestration_progress=orchestration_progress,
        orchestration_ai_mode=orchestration_ai_mode,
        dev=dev,
        dashboard=dashboard,
        max_iterations=max_iterations,
        coverage_status=coverage_status,
        coverage_goal=coverage_goal,
        no_coverage_ratchet=no_coverage_ratchet,
        boost_coverage=boost_coverage,
        disable_global_locks=disable_global_locks,
        global_lock_timeout=global_lock_timeout,
        global_lock_cleanup=global_lock_cleanup,
        global_lock_dir=global_lock_dir,
        quick=quick,
        thorough=thorough,
        clear_cache=clear_cache,
        cache_stats=cache_stats,
        # New semantic parameters
        strip_code=strip_code,
        run_tests=run_tests,
        ai_fix=ai_fix,
        full_release=full_release,
        show_progress=show_progress,
        advanced_monitor=advanced_monitor,
        coverage_report=coverage_report,
        clean_releases=clean_releases,
    )
