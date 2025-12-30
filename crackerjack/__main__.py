"""Crackerjack CLI entry point with Oneiric integration.

Phase 6 Implementation: MCPServerCLIFactory integration with restored main command
"""

import os
import sys

# Suppress ACB logger startup messages and stderr JSON unless --debug is provided
# Must happen before any ACB imports
if "--debug" not in sys.argv:
    os.environ["ACB_LOGGER_DEBUG_MODE"] = "0"
    os.environ["ACB_LOG_LEVEL"] = "WARNING"
    os.environ["ACB_DISABLE_STRUCTURED_STDERR"] = "1"  # No JSON to stderr by default

import subprocess
import typing as t

import typer
from mcp_common.cli import MCPServerCLIFactory
from rich.console import Console

from crackerjack import __version__
from crackerjack.cli import (
    CLI_OPTIONS,
    BumpOption,
    create_options,
)
from crackerjack.cli.cache_handlers import _handle_cache_commands
from crackerjack.cli.handlers import handle_config_updates
from crackerjack.cli.handlers.advanced import handle_advanced_optimizer
from crackerjack.cli.handlers.ai_features import handle_contextual_ai
from crackerjack.cli.handlers.analytics import (
    handle_anomaly_detection,
    handle_heatmap_generation,
    handle_predictive_analytics,
)
from crackerjack.cli.handlers.changelog import (
    handle_changelog_commands,
    handle_version_analysis,
    setup_debug_and_verbose_flags,
)
from crackerjack.cli.handlers.coverage import handle_coverage_status
from crackerjack.cli.handlers.documentation import (
    handle_documentation_commands,
    handle_mkdocs_integration,
)
from crackerjack.cli.handlers.main_handlers import (
    handle_interactive_mode,
    handle_standard_mode,
    setup_ai_agent_env,
)
from crackerjack.cli.lifecycle_handlers import (
    health_probe_handler,
    start_handler,
    stop_handler,
)
from crackerjack.cli.semantic_handlers import (
    handle_remove_from_semantic_index,
    handle_semantic_index,
    handle_semantic_search,
    handle_semantic_stats,
)
from crackerjack.config import CrackerjackSettings, load_settings
from crackerjack.config.mcp_settings_adapter import CrackerjackMCPSettings

# ============================================================================
# MCP Server Lifecycle (Oneiric Factory Pattern)
# ============================================================================

# Load settings for CLI factory
mcp_settings = CrackerjackMCPSettings.load_for_crackerjack()

factory = MCPServerCLIFactory(
    server_name="crackerjack",
    settings=mcp_settings,
    start_handler=start_handler,
    stop_handler=stop_handler,
    health_probe_handler=health_probe_handler,
)

app = factory.create_app()
app.info.help = "Crackerjack MCP Server CLI"

console = Console()


# ============================================================================
# Main Quality Workflow Command (Restored from Pre-Phase 6)
# ============================================================================


@app.command()
def run(
    commit: bool = CLI_OPTIONS["commit"],
    interactive: bool = CLI_OPTIONS["interactive"],
    no_config_updates: bool = CLI_OPTIONS["no_config_updates"],
    verbose: bool = CLI_OPTIONS["verbose"],
    debug: bool = CLI_OPTIONS["debug"],
    publish: BumpOption | None = CLI_OPTIONS["publish"],
    all: str | None = CLI_OPTIONS["all"],
    bump: BumpOption | None = CLI_OPTIONS["bump"],
    strip_code: bool = CLI_OPTIONS["strip_code"],
    run_tests: bool = CLI_OPTIONS["run_tests"],
    benchmark: bool = CLI_OPTIONS["benchmark"],
    test_workers: int = CLI_OPTIONS["test_workers"],
    test_timeout: int = CLI_OPTIONS["test_timeout"],
    skip_hooks: bool = CLI_OPTIONS["skip_hooks"],
    fast: bool = CLI_OPTIONS["fast"],
    comp: bool = CLI_OPTIONS["comp"],
    fast_iteration: bool = CLI_OPTIONS["fast_iteration"],
    tool: str | None = CLI_OPTIONS["tool"],
    changed_only: bool = CLI_OPTIONS["changed_only"],
    all_files: bool = CLI_OPTIONS["all_files"],
    create_pr: bool = CLI_OPTIONS["create_pr"],
    ai_fix: bool = CLI_OPTIONS["ai_fix"],
    start_mcp_server: bool = CLI_OPTIONS["start_mcp_server"],
    stop_mcp_server: bool = CLI_OPTIONS["stop_mcp_server"],
    restart_mcp_server: bool = CLI_OPTIONS["restart_mcp_server"],
    experimental_hooks: bool = CLI_OPTIONS["experimental_hooks"],
    enable_pyrefly: bool = CLI_OPTIONS["enable_pyrefly"],
    enable_ty: bool = CLI_OPTIONS["enable_ty"],
    no_git_tags: bool = CLI_OPTIONS["no_git_tags"],
    skip_version_check: bool = CLI_OPTIONS["skip_version_check"],
    start_zuban_lsp: bool = CLI_OPTIONS["start_zuban_lsp"],
    stop_zuban_lsp: bool = CLI_OPTIONS["stop_zuban_lsp"],
    restart_zuban_lsp: bool = CLI_OPTIONS["restart_zuban_lsp"],
    no_zuban_lsp: bool = CLI_OPTIONS["no_zuban_lsp"],
    zuban_lsp_port: int = CLI_OPTIONS["zuban_lsp_port"],
    zuban_lsp_mode: str = CLI_OPTIONS["zuban_lsp_mode"],
    zuban_lsp_timeout: int = CLI_OPTIONS["zuban_lsp_timeout"],
    enable_lsp_hooks: bool = CLI_OPTIONS["enable_lsp_hooks"],
    watchdog: bool = CLI_OPTIONS["watchdog"],
    monitor: bool = CLI_OPTIONS["monitor"],
    enhanced_monitor: bool = CLI_OPTIONS["enhanced_monitor"],
    ai_debug: bool = CLI_OPTIONS["ai_debug"],
    job_id: str | None = CLI_OPTIONS["job_id"],
    dev: bool = CLI_OPTIONS["dev"],
    max_iterations: int = CLI_OPTIONS["max_iterations"],
    coverage_status: bool = CLI_OPTIONS["coverage_status"],
    coverage_goal: float | None = CLI_OPTIONS["coverage_goal"],
    no_coverage_ratchet: bool = CLI_OPTIONS["no_coverage_ratchet"],
    boost_coverage: bool = CLI_OPTIONS["boost_coverage"],
    disable_global_locks: bool = CLI_OPTIONS["disable_global_locks"],
    global_lock_timeout: int = CLI_OPTIONS["global_lock_timeout"],
    global_lock_cleanup: bool = CLI_OPTIONS["global_lock_cleanup"],
    global_lock_dir: str | None = CLI_OPTIONS["global_lock_dir"],
    quick: bool = CLI_OPTIONS["quick"],
    thorough: bool = CLI_OPTIONS["thorough"],
    clear_cache: bool = CLI_OPTIONS["clear_cache"],
    cache_stats: bool = CLI_OPTIONS["cache_stats"],
    generate_docs: bool = CLI_OPTIONS["generate_docs"],
    docs_format: str = CLI_OPTIONS["docs_format"],
    validate_docs: bool = CLI_OPTIONS["validate_docs"],
    generate_changelog: bool = CLI_OPTIONS["generate_changelog"],
    changelog_version: str | None = CLI_OPTIONS["changelog_version"],
    changelog_since: str | None = CLI_OPTIONS["changelog_since"],
    changelog_dry_run: bool = CLI_OPTIONS["changelog_dry_run"],
    auto_version: bool = CLI_OPTIONS["auto_version"],
    version_since: str | None = CLI_OPTIONS["version_since"],
    accept_version: bool = CLI_OPTIONS["accept_version"],
    smart_commit: bool = CLI_OPTIONS["smart_commit"],
    heatmap: bool = CLI_OPTIONS["heatmap"],
    heatmap_type: str = CLI_OPTIONS["heatmap_type"],
    heatmap_output: str | None = CLI_OPTIONS["heatmap_output"],
    anomaly_detection: bool = CLI_OPTIONS["anomaly_detection"],
    anomaly_sensitivity: float = CLI_OPTIONS["anomaly_sensitivity"],
    anomaly_report: str | None = CLI_OPTIONS["anomaly_report"],
    predictive_analytics: bool = CLI_OPTIONS["predictive_analytics"],
    prediction_periods: int = CLI_OPTIONS["prediction_periods"],
    analytics_dashboard: str | None = CLI_OPTIONS["analytics_dashboard"],
    advanced_optimizer: bool = CLI_OPTIONS["advanced_optimizer"],
    advanced_profile: str | None = CLI_OPTIONS["advanced_profile"],
    advanced_report: str | None = CLI_OPTIONS["advanced_report"],
    mkdocs_integration: bool = CLI_OPTIONS["mkdocs_integration"],
    mkdocs_serve: bool = CLI_OPTIONS["mkdocs_serve"],
    mkdocs_theme: str = CLI_OPTIONS["mkdocs_theme"],
    mkdocs_output: str | None = CLI_OPTIONS["mkdocs_output"],
    contextual_ai: bool = CLI_OPTIONS["contextual_ai"],
    ai_recommendations: int = CLI_OPTIONS["ai_recommendations"],
    ai_help_query: str | None = CLI_OPTIONS["ai_help_query"],
    check_config_updates: bool = CLI_OPTIONS["check_config_updates"],
    apply_config_updates: bool = CLI_OPTIONS["apply_config_updates"],
    diff_config: str | None = CLI_OPTIONS["diff_config"],
    config_interactive: bool = CLI_OPTIONS["config_interactive"],
    refresh_cache: bool = CLI_OPTIONS["refresh_cache"],
    index: str | None = CLI_OPTIONS["index"],
    search: str | None = CLI_OPTIONS["search"],
    semantic_stats: bool = CLI_OPTIONS["semantic_stats"],
    remove_from_index: str | None = CLI_OPTIONS["remove_from_index"],
) -> None:
    """Run Crackerjack quality workflow with comprehensive options.

    This is the main entry point for running quality checks, tests, and
    release workflows. Run without arguments for basic quality checks,
    or use flags to customize behavior.

    Common examples:
        crackerjack run --run-tests           # Quality checks + tests
        crackerjack run --ai-fix --run-tests  # Auto-fix with AI
        crackerjack run --fast                # Quick formatting only
        crackerjack run --all patch           # Full release workflow
    """
    # Load settings
    settings = load_settings(CrackerjackSettings)

    # Print version on startup
    console.print(f"[cyan]Crackerjack[/cyan] [dim]v{__version__}[/dim]")

    # Create options object
    options = create_options(
        commit,
        interactive,
        no_config_updates,
        verbose,
        debug,
        publish,
        bump,
        benchmark,
        test_workers,
        test_timeout,
        skip_hooks,
        fast,
        comp,
        fast_iteration,
        tool,
        changed_only,
        all_files,
        create_pr,
        experimental_hooks,
        enable_pyrefly,
        enable_ty,
        start_zuban_lsp,
        stop_zuban_lsp,
        restart_zuban_lsp,
        no_zuban_lsp,
        zuban_lsp_port,
        zuban_lsp_mode,
        zuban_lsp_timeout,
        enable_lsp_hooks,
        no_git_tags,
        skip_version_check,
        dev,
        max_iterations,
        coverage_status,
        coverage_goal,
        no_coverage_ratchet,
        boost_coverage,
        disable_global_locks,
        global_lock_timeout,
        global_lock_cleanup,
        global_lock_dir,
        quick,
        thorough,
        clear_cache,
        cache_stats,
        generate_docs,
        docs_format,
        validate_docs,
        generate_changelog,
        changelog_version,
        changelog_since,
        changelog_dry_run,
        auto_version,
        version_since,
        accept_version,
        smart_commit,
        heatmap,
        heatmap_type,
        heatmap_output,
        anomaly_detection,
        anomaly_sensitivity,
        anomaly_report,
        predictive_analytics,
        prediction_periods,
        analytics_dashboard,
        advanced_optimizer,
        advanced_profile,
        advanced_report,
        mkdocs_integration,
        mkdocs_serve,
        mkdocs_theme,
        mkdocs_output,
        contextual_ai,
        ai_recommendations,
        ai_help_query,
        check_config_updates,
        apply_config_updates,
        diff_config,
        config_interactive,
        refresh_cache,
        run_tests=run_tests,
        strip_code=strip_code,
        ai_fix=ai_fix,
    )

    # Set semantic search options
    options.index = index
    options.search = search
    options.semantic_stats = semantic_stats
    options.remove_from_index = remove_from_index

    # Setup debug/verbose flags
    ai_fix, verbose = setup_debug_and_verbose_flags(
        ai_fix, ai_debug, debug, verbose, options
    )
    setup_ai_agent_env(ai_fix, ai_debug or debug)

    # Configure logger verbosity and stderr JSON output based on CLI flags
    def _configure_logger_verbosity(debug: bool) -> None:
        """Configure logger verbosity and stderr JSON output.

        Stream Configuration:
        - Default/Verbose: WARNING level, no stderr JSON (clean UX)
        - Debug: DEBUG level, enable stderr JSON (structured logs for troubleshooting)
        """
        if debug:
            os.environ["ACB_LOG_LEVEL"] = "DEBUG"
            os.environ["CRACKERJACK_DEBUG"] = "1"
            # Enable structured JSON logging to stderr for debug mode
            if "ACB_DISABLE_STRUCTURED_STDERR" in os.environ:
                del os.environ["ACB_DISABLE_STRUCTURED_STDERR"]
            os.environ["ACB_FORCE_STRUCTURED_STDERR"] = "1"
        # If not debug, keep WARNING level and disabled stderr JSON from early init

    _configure_logger_verbosity(debug=debug)

    # Process all commands
    if not _process_all_commands(locals(), options):
        return

    # Run workflow
    if interactive:
        handle_interactive_mode(options)
    else:
        handle_standard_mode(options, job_id=job_id)


def _process_all_commands(local_vars: t.Any, options: t.Any) -> bool:
    """Process all command-line commands and return True if workflow should continue."""
    if _handle_cache_commands(local_vars["clear_cache"], local_vars["cache_stats"]):
        return False

    if (
        local_vars["check_config_updates"]
        or local_vars["apply_config_updates"]
        or local_vars["diff_config"]
        or local_vars["refresh_cache"]
    ):
        handle_config_updates(options)
        return False

    if not _handle_semantic_commands(
        local_vars["index"],
        local_vars["search"],
        local_vars["semantic_stats"],
        local_vars["remove_from_index"],
        options,
    ):
        return False

    # Server commands (monitor, dashboard, watchdog, etc.) handled separately
    # MCP server commands now handled by MCPServerCLIFactory
    # TODO: Restore monitor/dashboard/watchdog handling if needed

    if not handle_coverage_status(local_vars["coverage_status"], options):
        return False

    return _handle_analysis_commands(local_vars, options)


def _handle_analysis_commands(local_vars: t.Any, options: t.Any) -> bool:
    """Handle documentation and analysis commands."""
    if not handle_documentation_commands(
        local_vars["generate_docs"], local_vars["validate_docs"], options
    ):
        return False

    if not handle_changelog_commands(
        local_vars["generate_changelog"],
        local_vars["changelog_dry_run"],
        local_vars["changelog_version"],
        local_vars["changelog_since"],
        options,
    ):
        return False

    if not handle_version_analysis(
        local_vars["auto_version"],
        local_vars["version_since"],
        local_vars["accept_version"],
        options,
    ):
        return False

    return _handle_specialized_analytics(local_vars)


def _handle_specialized_analytics(local_vars: t.Any) -> bool:
    """Handle advanced analytics commands."""
    if not handle_heatmap_generation(
        local_vars["heatmap"], local_vars["heatmap_type"], local_vars["heatmap_output"]
    ):
        return False

    if not handle_anomaly_detection(
        local_vars["anomaly_detection"],
        local_vars["anomaly_sensitivity"],
        local_vars["anomaly_report"],
    ):
        return False

    if not handle_predictive_analytics(
        local_vars["predictive_analytics"],
        local_vars["prediction_periods"],
        local_vars["analytics_dashboard"],
    ):
        return False

    return _handle_advanced_features(local_vars)


def _handle_semantic_commands(
    index: str | None,
    search: str | None,
    semantic_stats: bool,
    remove_from_index: str | None,
    options: t.Any,
) -> bool:
    """Handle semantic search commands."""
    if not _has_semantic_operations(index, search, semantic_stats, remove_from_index):
        return True

    console.print("[cyan]🔍[/cyan] Running semantic search operations...")

    try:
        _execute_semantic_operations(index, search, semantic_stats, remove_from_index)
        return False
    except Exception as e:
        console.print(f"[red]❌[/red] Semantic search error: {e}")
        return False


def _has_semantic_operations(
    index: str | None,
    search: str | None,
    semantic_stats: bool,
    remove_from_index: str | None,
) -> bool:
    """Check if any semantic operations are requested."""
    return any([index, search, semantic_stats, remove_from_index])


def _execute_semantic_operations(
    index: str | None,
    search: str | None,
    semantic_stats: bool,
    remove_from_index: str | None,
) -> None:
    """Execute semantic search operations."""
    if index:
        handle_semantic_index(index)

    if search:
        handle_semantic_search(search)

    if semantic_stats:
        handle_semantic_stats()

    if remove_from_index:
        handle_remove_from_semantic_index(remove_from_index)


def _handle_advanced_features(local_vars: t.Any) -> bool:
    """Handle advanced features like optimization and MkDocs."""
    if not handle_advanced_optimizer(
        local_vars["advanced_optimizer"],
        local_vars["advanced_profile"],
        local_vars["advanced_report"],
    ):
        return False

    if not handle_mkdocs_integration(
        local_vars["mkdocs_integration"],
        local_vars["mkdocs_serve"],
        local_vars["mkdocs_theme"],
        local_vars["mkdocs_output"],
    ):
        return False

    if not handle_contextual_ai(
        local_vars["contextual_ai"],
        local_vars["ai_recommendations"],
        local_vars["ai_help_query"],
    ):
        return False

    return True


# ============================================================================
# Standalone Commands (Domain-Specific, Preserved from Phase 6)
# ============================================================================


@app.command()
def run_tests(
    workers: int = typer.Option(
        0, "--workers", "-n", help="Test workers (0=auto-detect)"
    ),
    timeout: int = typer.Option(300, "--timeout", help="Test timeout in seconds"),
    coverage: bool = typer.Option(
        True, "--coverage/--no-coverage", help="Run with coverage tracking"
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    benchmark: bool = typer.Option(
        False, "--benchmark", help="Run performance benchmarks"
    ),
):
    """Run test suite with pytest (standalone command).

    Supports parallel execution via pytest-xdist with automatic worker detection.
    Coverage is tracked with pytest-cov and stored in htmlcov/ directory.
    """
    cmd = ["pytest"]

    # Worker configuration (pytest-xdist)
    if workers != 1:
        cmd.extend(["-n", str(workers) if workers > 0 else "auto"])

    # Coverage tracking
    if coverage:
        cmd.extend(["--cov=crackerjack", "--cov-report=html", "--cov-report=term"])

    # Timeout protection
    cmd.append(f"--timeout={timeout}")

    # Verbosity
    if verbose:
        cmd.append("-vv")

    # Benchmarks
    if benchmark:
        cmd.append("--benchmark-only")

    console.print(f"[blue]Running: {' '.join(cmd)}[/blue]")
    result = subprocess.run(cmd)
    raise typer.Exit(result.returncode)


@app.command()
def qa_health():
    """Check health of QA adapters (standalone command).

    Displays enabled/disabled adapter flags and health status.
    """
    from crackerjack.server import CrackerjackServer

    settings = load_settings(CrackerjackSettings)
    server = CrackerjackServer(settings)
    health = server.get_health_snapshot()

    qa_status = health.lifecycle_state.get("qa_adapters", {})
    enabled_flags = qa_status.get("enabled_flags", {})

    console.print("\n[bold]QA Adapter Health[/bold]")
    console.print(f"Total adapters: {qa_status.get('total', 0)}")
    console.print(f"Healthy adapters: {qa_status.get('healthy', 0)}")

    console.print("\n[bold]Enabled Adapters:[/bold]")
    for adapter_name, enabled in enabled_flags.items():
        status = "✅" if enabled else "❌"
        console.print(f"  {status} {adapter_name}")

    if qa_status.get("total", 0) == qa_status.get("healthy", 0):
        console.print("\n[green]✅ All adapters healthy[/green]")
        raise typer.Exit(0)
    else:
        console.print("\n[yellow]⚠️  Some adapters unhealthy[/yellow]")
        raise typer.Exit(1)


def main():
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
