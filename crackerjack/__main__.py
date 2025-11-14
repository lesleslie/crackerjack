import typing as t
import warnings

import typer
from acb.console import Console
from acb.depends import Inject, depends

# Suppress asyncio subprocess cleanup warnings when event loop closes
# This is a known Python issue - the subprocesses are properly cleaned up,
# but the warning appears when the event loop closes with pending subprocess handlers
warnings.filterwarnings(
    "ignore",
    message=".*loop.*closed.*",
    category=RuntimeWarning,
)

if t.TYPE_CHECKING:
    pass


from .cli import (
    CLI_OPTIONS,
    BumpOption,
    create_options,
    handle_interactive_mode,
    handle_standard_mode,
    setup_ai_agent_env,
)
from .cli.cache_handlers import _handle_cache_commands
from .cli.handlers import (
    handle_config_updates,
)
from .cli.handlers.advanced import (
    handle_advanced_optimizer,
)
from .cli.handlers.ai_features import handle_contextual_ai
from .cli.handlers.analytics import (
    handle_anomaly_detection,
    handle_heatmap_generation,
    handle_predictive_analytics,
)
from .cli.handlers.changelog import (
    handle_changelog_commands,
    handle_version_analysis,
    setup_debug_and_verbose_flags,
)
from .cli.handlers.coverage import (
    handle_coverage_status,
)
from .cli.handlers.documentation import (
    handle_documentation_commands,
    handle_mkdocs_integration,
)
from .cli.handlers.monitoring import handle_server_commands
from .cli.semantic_handlers import (
    handle_remove_from_semantic_index,
    handle_semantic_index,
    handle_semantic_search,
    handle_semantic_stats,
)

console = Console()
app = typer.Typer(
    help="Crackerjack: Your Python project setup and style enforcement tool.",
)


@app.command()
def main(
    commit: bool = CLI_OPTIONS["commit"],
    interactive: bool = CLI_OPTIONS["interactive"],
    no_config_updates: bool = CLI_OPTIONS["no_config_updates"],
    update_precommit: bool = CLI_OPTIONS["update_precommit"],
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
    async_mode: bool = CLI_OPTIONS["async_mode"],
    experimental_hooks: bool = CLI_OPTIONS["experimental_hooks"],
    enable_pyrefly: bool = CLI_OPTIONS["enable_pyrefly"],
    enable_ty: bool = CLI_OPTIONS["enable_ty"],
    no_git_tags: bool = CLI_OPTIONS["no_git_tags"],
    skip_version_check: bool = CLI_OPTIONS["skip_version_check"],
    start_websocket_server: bool = CLI_OPTIONS["start_websocket_server"],
    stop_websocket_server: bool = CLI_OPTIONS["stop_websocket_server"],
    restart_websocket_server: bool = CLI_OPTIONS["restart_websocket_server"],
    websocket_port: int | None = CLI_OPTIONS["websocket_port"],
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
    orchestrated: bool = CLI_OPTIONS["orchestrated"],
    orchestration_strategy: str = CLI_OPTIONS["orchestration_strategy"],
    orchestration_progress: str = CLI_OPTIONS["orchestration_progress"],
    orchestration_ai_mode: str = CLI_OPTIONS["orchestration_ai_mode"],
    dev: bool = CLI_OPTIONS["dev"],
    dashboard: bool = CLI_OPTIONS["dashboard"],
    unified_dashboard: bool = CLI_OPTIONS["unified_dashboard"],
    unified_dashboard_port: int | None = CLI_OPTIONS["unified_dashboard_port"],
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
    use_acb_workflows: bool = CLI_OPTIONS["use_acb_workflows"],
    use_legacy_orchestrator: bool = CLI_OPTIONS["use_legacy_orchestrator"],
    index: str | None = CLI_OPTIONS["index"],
    search: str | None = CLI_OPTIONS["search"],
    semantic_stats: bool = CLI_OPTIONS["semantic_stats"],
    remove_from_index: str | None = CLI_OPTIONS["remove_from_index"],
) -> None:
    from acb.depends import depends

    from crackerjack.config import register_services
    from crackerjack.config.loader import load_settings
    from crackerjack.config.settings import CrackerjackSettings

    settings = load_settings(CrackerjackSettings)
    depends.set(CrackerjackSettings, settings)

    register_services()

    options = create_options(
        commit,
        interactive,
        no_config_updates,
        update_precommit,
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
        async_mode,
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
        orchestrated,
        orchestration_strategy,
        orchestration_progress,
        orchestration_ai_mode,
        dev,
        dashboard,
        unified_dashboard,
        unified_dashboard_port,
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
        use_acb_workflows,
        use_legacy_orchestrator,
        run_tests=run_tests,
    )

    options.index = index
    options.search = search
    options.semantic_stats = semantic_stats
    options.remove_from_index = remove_from_index

    ai_fix, verbose = setup_debug_and_verbose_flags(
        ai_fix, ai_debug, debug, verbose, options
    )
    setup_ai_agent_env(ai_fix, ai_debug or debug)

    if not _process_all_commands(locals(), options):
        return

    if interactive:
        handle_interactive_mode(options)
    else:
        handle_standard_mode(options, async_mode, job_id, orchestrated)


def _process_all_commands(local_vars: t.Any, options: t.Any) -> bool:
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

    if handle_server_commands(
        local_vars["monitor"],
        local_vars["enhanced_monitor"],
        local_vars["dashboard"],
        local_vars["unified_dashboard"],
        local_vars["unified_dashboard_port"],
        local_vars["watchdog"],
        local_vars["start_websocket_server"],
        local_vars["stop_websocket_server"],
        local_vars["restart_websocket_server"],
        local_vars["start_mcp_server"],
        local_vars["stop_mcp_server"],
        local_vars["restart_mcp_server"],
        local_vars["websocket_port"],
        local_vars["start_zuban_lsp"],
        local_vars["stop_zuban_lsp"],
        local_vars["restart_zuban_lsp"],
        local_vars["zuban_lsp_port"],
        local_vars["zuban_lsp_mode"],
        local_vars["dev"],
    ):
        return False

    if not handle_coverage_status(local_vars["coverage_status"], options):
        return False

    return _handle_analysis_commands(local_vars, options)


def _handle_analysis_commands(local_vars: t.Any, options: t.Any) -> bool:
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


@depends.inject  # type: ignore[misc]
def _handle_semantic_commands(
    index: str | None,
    search: str | None,
    semantic_stats: bool,
    remove_from_index: str | None,
    options: t.Any,
    console: Inject[Console],
) -> bool:
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
    return any([index, search, semantic_stats, remove_from_index])


def _execute_semantic_operations(
    index: str | None,
    search: str | None,
    semantic_stats: bool,
    remove_from_index: str | None,
) -> list[str]:
    if index:
        handle_semantic_index(index)

    if search:
        handle_semantic_search(search)

    if semantic_stats:
        handle_semantic_stats()

    if remove_from_index:
        handle_remove_from_semantic_index(remove_from_index)

    return []


def _handle_advanced_features(local_vars: t.Any) -> bool:
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


def cli() -> None:
    app()


if __name__ == "__main__":
    app()
