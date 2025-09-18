import typing as t
import warnings
from enum import Enum

import click
import typer
from pydantic import BaseModel, field_validator, model_validator


def parse_bump_option_with_flag_support(
    ctx: click.Context, param: click.Parameter, value: str | None
) -> str | None:
    """Parse bump option that supports both flag usage (-p) and value usage (-p patch)."""
    if value is None:
        return None

    # If the value starts with a dash, it's likely another flag that typer mistakenly captured
    if value.startswith("-"):
        # Map of consumed flags to their corresponding parameter names
        flag_mapping = {
            "-c": "commit",
            "--commit": "commit",
            "-v": "verbose",
            "--verbose": "verbose",
            "-s": "skip_hooks",
            "--skip-hooks": "skip_hooks",
            "-i": "interactive",
            "--interactive": "interactive",
            "-n": "no_config_updates",
            "--no-config-updates": "no_config_updates",
            "-u": "update_precommit",
            "--update-precommit": "update_precommit",
            "-t": "run_tests",
            "--run-tests": "run_tests",
            "-x": "strip_code",
            "--strip-code": "strip_code",
            "--debug": "debug",
        }

        # Handle any consumed flag
        if value in flag_mapping:
            param_name = flag_mapping[value]
            # Set the parameter directly in the context
            if not hasattr(ctx, "params"):
                ctx.params = {}
            ctx.params[param_name] = True

            # CRITICAL FIX: Remove the consumed flag from sys.argv to prevent double processing
            import sys

            if value in sys.argv:
                sys.argv.remove(value)

        # Default to interactive mode when used as a flag
        return "interactive"

    return value


class BumpOption(str, Enum):
    patch = "patch"
    minor = "minor"
    major = "major"
    interactive = "interactive"
    auto = "auto"

    def __str__(self) -> str:
        return str(self.value)


class Options(BaseModel):
    commit: bool = False
    interactive: bool = False
    no_config_updates: bool = False
    update_precommit: bool = False
    publish: BumpOption | None = None
    all: BumpOption | None = None
    bump: BumpOption | None = None
    verbose: bool = False
    debug: bool = False
    benchmark: bool = False
    test_workers: int = 0
    test_timeout: int = 0
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
    start_zuban_lsp: bool = False
    stop_zuban_lsp: bool = False
    restart_zuban_lsp: bool = False
    no_zuban_lsp: bool = False
    zuban_lsp_port: int = 8677
    zuban_lsp_mode: str = "tcp"
    zuban_lsp_timeout: int = 30
    enable_lsp_hooks: bool = False
    dev: bool = False
    dashboard: bool = False
    unified_dashboard: bool = False
    unified_dashboard_port: int | None = None
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
    run_tests: bool = False  # Replaces test
    ai_fix: bool | None = None  # Replaces ai_agent
    full_release: str | None = None  # Replaces all
    show_progress: bool | None = None  # Replaces track_progress
    advanced_monitor: bool | None = None  # Replaces enhanced_monitor
    coverage_report: bool | None = None  # Replaces coverage_status
    clean_releases: bool | None = None  # Replaces cleanup_pypi

    # Documentation and changelog generation fields
    generate_docs: bool = False
    docs_format: str = "markdown"
    validate_docs: bool = False
    generate_changelog: bool = False
    changelog_version: str | None = None
    changelog_since: str | None = None
    changelog_dry_run: bool = False
    auto_version: bool = False
    version_since: str | None = None
    accept_version: bool = False

    # Intelligent features
    smart_commit: bool = True  # Default enabled for advanced services integration

    # Analytics and visualization features
    heatmap: bool = False
    heatmap_type: str = "error_frequency"
    heatmap_output: str | None = None
    anomaly_detection: bool = False
    anomaly_sensitivity: float = 2.0
    anomaly_report: str | None = None
    predictive_analytics: bool = False
    prediction_periods: int = 10
    analytics_dashboard: str | None = None

    # Configuration management features
    check_config_updates: bool = False
    apply_config_updates: bool = False
    diff_config: str | None = None
    config_interactive: bool = False
    refresh_cache: bool = False

    # Enterprise features
    enterprise_optimizer: bool = False
    enterprise_profile: str | None = None
    enterprise_report: str | None = None
    mkdocs_integration: bool = False
    mkdocs_serve: bool = False
    mkdocs_theme: str = "material"
    mkdocs_output: str | None = None
    contextual_ai: bool = False
    ai_recommendations: int = 5
    ai_help_query: str | None = None

    def _map_legacy_flag(
        self, old_attr: str, new_attr: str, deprecation_msg: str | None = None
    ) -> None:
        """Helper to map legacy flag to new flag with optional deprecation warning."""
        old_value = getattr(self, old_attr)
        new_value = getattr(self, new_attr)

        if old_value and new_value is None:
            setattr(self, new_attr, old_value)
            if deprecation_msg:
                warnings.warn(deprecation_msg, DeprecationWarning, stacklevel=4)
        elif new_value is not None:
            setattr(self, old_attr, new_value)

    @model_validator(mode="after")
    def handle_legacy_mappings(self) -> "Options":
        """Handle backward compatibility for deprecated flags."""
        # Map flags without deprecation warnings
        self._map_legacy_flag("all", "full_release")
        self._map_legacy_flag("track_progress", "show_progress")
        self._map_legacy_flag("enhanced_monitor", "advanced_monitor")
        self._map_legacy_flag("coverage_status", "coverage_report")
        self._map_legacy_flag("cleanup_pypi", "clean_releases")

        return self

    @property
    def test(self) -> bool:
        """Compatibility property for run_tests field."""
        return self.run_tests

    @test.setter
    def test(self, value: bool) -> None:
        """Setter for test property."""
        self.run_tests = value

    @property
    def ai_agent(self) -> bool:
        """Compatibility property for ai_fix field."""
        return bool(self.ai_fix)

    @ai_agent.setter
    def ai_agent(self, value: bool) -> None:
        """Setter for ai_agent property."""
        self.ai_fix = value if self.ai_fix is not None else value

    @property
    def clean(self) -> bool:
        """Compatibility property for strip_code field."""
        return bool(self.strip_code)

    @clean.setter
    def clean(self, value: bool) -> None:
        """Setter for clean property."""
        self.strip_code = value

    @property
    def update_docs_index(self) -> bool:
        """Compatibility property for generate_docs field."""
        return self.generate_docs

    @update_docs_index.setter
    def update_docs_index(self, value: bool) -> None:
        """Setter for update_docs_index property."""
        self.generate_docs = value

    @property
    def effective_max_iterations(self) -> int:
        if self.quick:
            return 2
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

        # Handle case where typer parsed a flag as the value (e.g., -p -c becomes value="-c")
        if isinstance(value, str) and value.startswith("-"):
            return BumpOption.interactive

        try:
            return BumpOption(value.lower())
        except ValueError:
            valid_options = ", ".join([o.value for o in BumpOption])
            msg = f"Invalid bump option: {value}. Must be one of: {valid_options}"
            raise ValueError(
                msg,
            )

    @classmethod
    @field_validator("zuban_lsp_mode", mode="before")
    def validate_zuban_lsp_mode(cls, value: t.Any) -> str:
        if value is None:
            return "tcp"
        valid_modes = ["tcp", "stdio"]
        if value.lower() not in valid_modes:
            msg = f"Invalid zuban LSP mode: {value}. Must be one of: {', '.join(valid_modes)}"
            raise ValueError(msg)
        return str(value).lower()


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
        callback=parse_bump_option_with_flag_support,
        is_flag=False,
        flag_value="interactive",
        help=(
            "Bump version and publish to PyPI (patch, minor, major, auto). "
            "Use 'interactive' to be prompted for version selection. "
            "Use 'auto' to automatically use AI recommendations. "
            "When used as a flag (-p), defaults to 'interactive'."
        ),
        case_sensitive=False,
    ),
    "all": typer.Option(
        None,
        "-a",
        "--all",
        callback=parse_bump_option_with_flag_support,
        help="Full release workflow: bump version, run quality checks, and publish (patch, minor, major, auto). When used as a flag (-a), defaults to 'interactive'.",
        case_sensitive=False,
    ),
    "bump": typer.Option(
        None,
        "-b",
        "--bump",
        callback=parse_bump_option_with_flag_support,
        help="Bump version (patch, minor, major, auto). When used as a flag (-b), defaults to 'interactive'.",
        case_sensitive=False,
    ),
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
    "create_pr": typer.Option(
        False,
        "-r",
        "--pr",
        "--new-pull-request",
        help="Create a new pull request to the upstream repository.",
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
    "start_zuban_lsp": typer.Option(
        False,
        "--start-zuban-lsp",
        help="Start Zuban LSP server for real-time type checking.",
    ),
    "stop_zuban_lsp": typer.Option(
        False,
        "--stop-zuban-lsp",
        help="Stop all running Zuban LSP servers.",
    ),
    "restart_zuban_lsp": typer.Option(
        False,
        "--restart-zuban-lsp",
        help="Restart Zuban LSP server (stop and start again).",
    ),
    "no_zuban_lsp": typer.Option(
        False,
        "--no-zuban-lsp",
        help="Disable automatic Zuban LSP server startup.",
    ),
    "zuban_lsp_port": typer.Option(
        8677,
        "--zuban-lsp-port",
        help="Port for Zuban LSP server (default: 8677).",
    ),
    "zuban_lsp_mode": typer.Option(
        "tcp",
        "--zuban-lsp-mode",
        help="Transport mode for Zuban LSP: tcp or stdio (default: tcp).",
    ),
    "zuban_lsp_timeout": typer.Option(
        30,
        "--zuban-lsp-timeout",
        help="Timeout in seconds for LSP server operations (default: 30).",
    ),
    "enable_lsp_hooks": typer.Option(
        False,
        "--enable-lsp-hooks",
        help="Enable LSP-optimized hook execution for faster type checking.",
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
    "unified_dashboard": typer.Option(
        False,
        "--unified-dashboard",
        help=(
            "Start the unified monitoring dashboard with real-time WebSocket streaming, "
            "web UI, and comprehensive system metrics aggregation."
        ),
    ),
    "unified_dashboard_port": typer.Option(
        None,
        "--unified-dashboard-port",
        help="Port for unified dashboard server (default: 8675).",
    ),
    "max_iterations": typer.Option(
        5,
        "--max-iterations",
        help="Maximum number of iterations for AI agent auto-fixing workflows (default: 5).",
    ),
    "ai_debug": typer.Option(
        False,
        "--ai-debug",
        help="Enable verbose debugging for AI auto-fixing mode (implies --ai-fix).",
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
        "-x",
        "--strip-code",
        help="Remove docstrings, line comments, and unnecessary whitespace from source code with automatic backup protection (doesn't affect test files).",
    ),
    "run_tests": typer.Option(
        False,
        "-t",
        "--run-tests",
        help=(
            "Execute the test suite with automatic worker detection "
            "and timeout handling."
        ),
    ),
    "ai_fix": typer.Option(
        None,
        "--ai-fix",
        help=(
            "Enable AI-powered automatic fixing of code quality issues "
            "and test failures."
        ),
    ),
    "full_release": typer.Option(
        None,
        "-a",
        "--full-release",
        callback=parse_bump_option_with_flag_support,
        help="Complete release workflow: strip code, run tests, bump version, and publish (patch, minor, major, auto). Equivalent to `-x -t -p <version> -c`. When used as a flag (-a), defaults to 'interactive'.",
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
    "generate_changelog": typer.Option(
        False,
        "--generate-changelog",
        help="Generate changelog entries from git commits.",
    ),
    "changelog_version": typer.Option(
        None,
        "--changelog-version",
        help="Version number for changelog generation (default: next version).",
    ),
    "changelog_since": typer.Option(
        None,
        "--changelog-since",
        help="Generate changelog since this version/tag (default: last release).",
    ),
    "changelog_dry_run": typer.Option(
        False,
        "--changelog-dry-run",
        help="Preview changelog generation without writing to file.",
    ),
    "auto_version": typer.Option(
        False,
        "--auto-version",
        help="Automatically analyze changes and recommend version bump.",
    ),
    "version_since": typer.Option(
        None,
        "--version-since",
        help="Analyze changes since this version/tag for version bump recommendation.",
    ),
    "accept_version": typer.Option(
        False,
        "--accept-version",
        help="Automatically accept version bump recommendation without confirmation.",
    ),
    "smart_commit": typer.Option(
        True,  # Now enabled by default for advanced services integration
        "--smart-commit/--basic-commit",
        help="Generate intelligent commit messages using AI analysis (default: enabled). Use --basic-commit for simple messages.",
    ),
    "heatmap": typer.Option(
        False,
        "--heatmap",
        help="Generate visual heat map analysis of code quality patterns and error distributions.",
    ),
    "heatmap_type": typer.Option(
        "error_frequency",
        "--heatmap-type",
        help="Type of heat map to generate: error_frequency, complexity, quality_metrics, test_failures.",
    ),
    "heatmap_output": typer.Option(
        None,
        "--heatmap-output",
        help="Output file path for heat map data (JSON/CSV) or HTML visualization.",
    ),
    "anomaly_detection": typer.Option(
        False,
        "--anomaly-detection",
        help="Enable ML-based anomaly detection for quality metrics monitoring.",
    ),
    "anomaly_sensitivity": typer.Option(
        2.0,
        "--anomaly-sensitivity",
        help="Sensitivity level for anomaly detection (1.0=very sensitive, 3.0=less sensitive).",
    ),
    "anomaly_report": typer.Option(
        None,
        "--anomaly-report",
        help="Output file path for anomaly detection report (JSON format).",
    ),
    "predictive_analytics": typer.Option(
        False,
        "--predictive-analytics",
        help="Enable predictive analytics for quality metrics forecasting and trend analysis.",
    ),
    "prediction_periods": typer.Option(
        10,
        "--prediction-periods",
        help="Number of future periods to predict (default: 10).",
    ),
    "analytics_dashboard": typer.Option(
        None,
        "--analytics-dashboard",
        help="Output file path for analytics dashboard (HTML format).",
    ),
    # Enterprise features
    "enterprise_optimizer": typer.Option(
        False,
        "--enterprise-optimizer",
        help="Enable enterprise-scale optimization engine with resource monitoring and scaling analysis.",
    ),
    "enterprise_profile": typer.Option(
        None,
        "--enterprise-profile",
        help="Enterprise optimization profile: balanced, performance, memory, throughput.",
    ),
    "enterprise_report": typer.Option(
        None,
        "--enterprise-report",
        help="Output file path for enterprise optimization report (JSON format).",
    ),
    "mkdocs_integration": typer.Option(
        False,
        "--mkdocs-integration",
        help="Generate complete MkDocs documentation site with Material theme and automation.",
    ),
    "mkdocs_serve": typer.Option(
        False,
        "--mkdocs-serve",
        help="Start MkDocs development server after building documentation site.",
    ),
    "mkdocs_theme": typer.Option(
        "material",
        "--mkdocs-theme",
        help="MkDocs theme to use for documentation generation (default: material).",
    ),
    "mkdocs_output": typer.Option(
        None,
        "--mkdocs-output",
        help="Output directory for MkDocs site generation (default: ./docs_site).",
    ),
    "contextual_ai": typer.Option(
        False,
        "--contextual-ai",
        help="Enable contextual AI assistant with project-specific recommendations and insights.",
    ),
    "ai_recommendations": typer.Option(
        5,
        "--ai-recommendations",
        help="Maximum number of AI recommendations to display (default: 5).",
    ),
    "ai_help_query": typer.Option(
        None,
        "--ai-help-query",
        help="Get contextual help for specific query using AI assistant.",
    ),
    # Configuration management features
    "check_config_updates": typer.Option(
        False,
        "--check-config-updates",
        help="Check for available configuration template updates.",
    ),
    "apply_config_updates": typer.Option(
        False,
        "--apply-config-updates",
        help="Apply available configuration template updates.",
    ),
    "diff_config": typer.Option(
        None,
        "--diff-config",
        help="Show diff preview for a specific configuration type.",
    ),
    "config_interactive": typer.Option(
        False,
        "--config-interactive",
        help="Apply configuration updates interactively with confirmations.",
    ),
    "refresh_cache": typer.Option(
        False,
        "--refresh-cache",
        help="Refresh pre-commit cache to ensure fresh environment.",
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
    bump: BumpOption | None,
    benchmark: bool,
    test_workers: int,
    test_timeout: int,
    skip_hooks: bool,
    fast: bool,
    comp: bool,
    create_pr: bool,
    async_mode: bool,
    experimental_hooks: bool,
    enable_pyrefly: bool,
    enable_ty: bool,
    start_zuban_lsp: bool,
    stop_zuban_lsp: bool,
    restart_zuban_lsp: bool,
    no_zuban_lsp: bool,
    zuban_lsp_port: int,
    zuban_lsp_mode: str,
    zuban_lsp_timeout: int,
    enable_lsp_hooks: bool,
    no_git_tags: bool,
    skip_version_check: bool,
    orchestrated: bool,
    orchestration_strategy: str,
    orchestration_progress: str,
    orchestration_ai_mode: str,
    dev: bool,
    dashboard: bool,
    unified_dashboard: bool,
    unified_dashboard_port: int | None,
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
    generate_changelog: bool,
    changelog_version: str | None,
    changelog_since: str | None,
    changelog_dry_run: bool,
    auto_version: bool,
    version_since: str | None,
    accept_version: bool,
    smart_commit: bool,
    heatmap: bool,
    heatmap_type: str,
    heatmap_output: str | None,
    anomaly_detection: bool,
    anomaly_sensitivity: float,
    anomaly_report: str | None,
    predictive_analytics: bool,
    prediction_periods: int,
    analytics_dashboard: str | None,
    # Enterprise features
    enterprise_optimizer: bool,
    enterprise_profile: str | None,
    enterprise_report: str | None,
    mkdocs_integration: bool,
    mkdocs_serve: bool,
    mkdocs_theme: str,
    mkdocs_output: str | None,
    contextual_ai: bool,
    ai_recommendations: int,
    ai_help_query: str | None,
    check_config_updates: bool,
    apply_config_updates: bool,
    diff_config: str | None,
    config_interactive: bool,
    refresh_cache: bool,
    # New semantic parameters
    strip_code: bool | None = None,
    run_tests: bool = False,
    ai_fix: bool | None = None,
    full_release: str | None = None,
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
        benchmark=benchmark,
        test_workers=test_workers,
        test_timeout=test_timeout,
        skip_hooks=skip_hooks,
        fast=fast,
        comp=comp,
        create_pr=create_pr,
        async_mode=async_mode,
        experimental_hooks=experimental_hooks,
        enable_pyrefly=enable_pyrefly,
        enable_ty=enable_ty,
        start_zuban_lsp=start_zuban_lsp,
        stop_zuban_lsp=stop_zuban_lsp,
        restart_zuban_lsp=restart_zuban_lsp,
        no_zuban_lsp=no_zuban_lsp,
        zuban_lsp_port=zuban_lsp_port,
        zuban_lsp_mode=zuban_lsp_mode,
        zuban_lsp_timeout=zuban_lsp_timeout,
        enable_lsp_hooks=enable_lsp_hooks,
        no_git_tags=no_git_tags,
        skip_version_check=skip_version_check,
        orchestrated=orchestrated,
        orchestration_strategy=orchestration_strategy,
        orchestration_progress=orchestration_progress,
        orchestration_ai_mode=orchestration_ai_mode,
        dev=dev,
        dashboard=dashboard,
        unified_dashboard=unified_dashboard,
        unified_dashboard_port=unified_dashboard_port,
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
        generate_docs=generate_docs,
        docs_format=docs_format,
        validate_docs=validate_docs,
        generate_changelog=generate_changelog,
        changelog_version=changelog_version,
        changelog_since=changelog_since,
        changelog_dry_run=changelog_dry_run,
        auto_version=auto_version,
        version_since=version_since,
        accept_version=accept_version,
        smart_commit=smart_commit,
        heatmap=heatmap,
        heatmap_type=heatmap_type,
        heatmap_output=heatmap_output,
        anomaly_detection=anomaly_detection,
        anomaly_sensitivity=anomaly_sensitivity,
        anomaly_report=anomaly_report,
        predictive_analytics=predictive_analytics,
        prediction_periods=prediction_periods,
        analytics_dashboard=analytics_dashboard,
        # Enterprise features
        enterprise_optimizer=enterprise_optimizer,
        enterprise_profile=enterprise_profile,
        enterprise_report=enterprise_report,
        mkdocs_integration=mkdocs_integration,
        mkdocs_serve=mkdocs_serve,
        mkdocs_theme=mkdocs_theme,
        mkdocs_output=mkdocs_output,
        contextual_ai=contextual_ai,
        ai_recommendations=ai_recommendations,
        ai_help_query=ai_help_query,
        check_config_updates=check_config_updates,
        apply_config_updates=apply_config_updates,
        diff_config=diff_config,
        config_interactive=config_interactive,
        refresh_cache=refresh_cache,
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
