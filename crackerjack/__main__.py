import logging
import os
import subprocess
import typing as t

import typer
from mcp_common.cli import MCPServerCLIFactory
from rich.console import Console

logger = logging.getLogger(__name__)

from crackerjack import __version__
from crackerjack.cli import (
    CLI_OPTIONS,
    BumpOption,
    create_options,
)
from crackerjack.cli.cache_handlers import _handle_cache_commands
from crackerjack.cli.handlers import check_docs, handle_config_updates, validate_docs
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

if t.TYPE_CHECKING:
    from crackerjack.cli.options import Options

mcp_settings = CrackerjackMCPSettings.load_for_crackerjack()

factory = MCPServerCLIFactory(
    server_name="crackerjack",
    settings=mcp_settings,
    start_handler=start_handler,
    stop_handler=stop_handler,
    health_probe_handler=health_probe_handler,
)

app = factory.create_app()

console = Console()


# Register MCP CLI group
from crackerjack.cli.mcp_cli import app as mcp_app
app.add_typer(mcp_app, name="mcp")


@app.callback(invoke_without_command=True)
def version_option(
    version: bool = typer.Option(False, "--version", help="Show version and exit"),
) -> None:
    if version:
        console.print(f"[cyan]Crackerjack[/cyan] [dim]v{__version__}[/dim]")
        raise typer.Exit(0)


def _detect_package_name_standalone() -> str:
    from pathlib import Path

    pkg_path = Path.cwd()

    pyproject_path = pkg_path / "pyproject.toml"
    if pyproject_path.exists():
        from contextlib import suppress

        with suppress(Exception):
            import tomllib

            with pyproject_path.open("rb") as f:
                data = tomllib.load(f)
                project_name = data.get("project", {}).get("name")
                if project_name:
                    return project_name.replace("-", "_")

    for item in pkg_path.iterdir():
        if (
            item.is_dir()
            and not item.name.startswith(".")
            and item.name not in ("tests", "docs", "build", "dist", "__pycache__")
            and (item / "__init__.py").exists()
        ):
            return item.name

    return "crackerjack"


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
    xcode_tests: bool = CLI_OPTIONS["xcode_tests"],
    xcode_project: str = CLI_OPTIONS["xcode_project"],
    xcode_scheme: str = CLI_OPTIONS["xcode_scheme"],
    xcode_configuration: str = CLI_OPTIONS["xcode_configuration"],
    xcode_destination: str = CLI_OPTIONS["xcode_destination"],
    ai_fix: bool = CLI_OPTIONS["ai_fix"],
    select_provider: bool = CLI_OPTIONS["select_provider"],
    dry_run: bool = CLI_OPTIONS["dry_run"],
    full_release: str | None = CLI_OPTIONS["full_release"],
    show_progress: bool | None = CLI_OPTIONS["show_progress"],
    advanced_monitor: bool | None = CLI_OPTIONS["advanced_monitor"],
    coverage_report: bool | None = CLI_OPTIONS["coverage_report"],
    clean_releases: bool | None = CLI_OPTIONS["clean_releases"],
    cleanup_docs: bool = CLI_OPTIONS["cleanup_docs"],
    docs_dry_run: bool = CLI_OPTIONS["docs_dry_run"],
    cleanup_configs: bool = CLI_OPTIONS["cleanup_configs"],
    configs_dry_run: bool = CLI_OPTIONS["configs_dry_run"],
    cleanup_git: bool = CLI_OPTIONS["cleanup_git"],
    update_docs: bool = CLI_OPTIONS["update_docs"],
    index: str | None = CLI_OPTIONS["index"],
    search: str | None = CLI_OPTIONS["search"],
    semantic_stats: bool = CLI_OPTIONS["semantic_stats"],
    remove_from_index: str | None = CLI_OPTIONS["remove_from_index"],
    refresh_cache: bool = CLI_OPTIONS["refresh_cache"],
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
    experimental_hooks: bool = CLI_OPTIONS["experimental_hooks"],
    enable_pyrefly: bool = CLI_OPTIONS["enable_pyrefly"],
    enable_ty: bool = CLI_OPTIONS["enable_ty"],
    start_mcp_server: bool = CLI_OPTIONS["start_mcp_server"],
    stop_mcp_server: bool = CLI_OPTIONS["stop_mcp_server"],
    restart_mcp_server: bool = CLI_OPTIONS["restart_mcp_server"],
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
    enable_hooks: list[str] | None = CLI_OPTIONS["enable_hooks"],
    enable_parallel_phases: bool = CLI_OPTIONS["enable_parallel_phases"],
    watchdog: bool = CLI_OPTIONS["watchdog"],
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
    docs_check: bool = CLI_OPTIONS["docs_check"],
    docs_validate: bool = CLI_OPTIONS["docs_validate"],
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
) -> None:
    settings = load_settings(CrackerjackSettings)
    _print_banner()

    if not dry_run:
        _cleanup_temp_files(settings)

    if select_provider:
        _handle_provider_selection()
        return

    options = _create_and_configure_options(locals())
    options = _setup_ai_options(locals(), options)
    _configure_logging(debug)

    if not _process_all_commands(locals(), options):
        return

    _execute_workflow_mode(options, job_id=job_id)


def _print_banner() -> None:
    console.print(f"[cyan]Crackerjack[/cyan] [dim]v{__version__}[/dim]")


def _cleanup_temp_files(settings: CrackerjackSettings) -> None:
    try:
        from crackerjack.utils.temp_file_cleanup import cleanup_temp_files

        cleaned = cleanup_temp_files()
        if cleaned > 0 and settings.execution.verbose:
            console.print(
                f"[dim]Cleaned up {cleaned} temporary file(s) from previous runs[/dim]"
            )
    except Exception as e:
        logger.warning(f"Failed to cleanup temporary files: {e}")


def _handle_provider_selection() -> None:
    import asyncio

    from crackerjack.cli.handlers.provider_selection import handle_select_provider

    asyncio.run(handle_select_provider())


def _create_and_configure_options(local_vars: dict[str, t.Any]) -> "Options":
    options = create_options(
        commit=local_vars["commit"],
        interactive=local_vars["interactive"],
        no_config_updates=local_vars["no_config_updates"],
        verbose=local_vars["verbose"],
        debug=local_vars["debug"],
        publish=local_vars["publish"],
        bump=local_vars["bump"],
        benchmark=local_vars["benchmark"],
        test_workers=local_vars["test_workers"],
        test_timeout=local_vars["test_timeout"],
        skip_hooks=local_vars["skip_hooks"],
        fast=local_vars["fast"],
        comp=local_vars["comp"],
        fast_iteration=local_vars["fast_iteration"],
        tool=local_vars["tool"],
        changed_only=local_vars["changed_only"],
        all_files=local_vars["all_files"],
        create_pr=local_vars["create_pr"],
        experimental_hooks=local_vars["experimental_hooks"],
        enable_pyrefly=local_vars["enable_pyrefly"],
        enable_ty=local_vars["enable_ty"],
        start_zuban_lsp=local_vars["start_zuban_lsp"],
        stop_zuban_lsp=local_vars["stop_zuban_lsp"],
        restart_zuban_lsp=local_vars["restart_zuban_lsp"],
        no_zuban_lsp=local_vars["no_zuban_lsp"],
        zuban_lsp_port=local_vars["zuban_lsp_port"],
        zuban_lsp_mode=local_vars["zuban_lsp_mode"],
        zuban_lsp_timeout=local_vars["zuban_lsp_timeout"],
        enable_lsp_hooks=local_vars["enable_lsp_hooks"],
        enable_hooks=local_vars["enable_hooks"],
        enable_parallel_phases=local_vars["enable_parallel_phases"],
        no_git_tags=local_vars["no_git_tags"],
        skip_version_check=local_vars["skip_version_check"],
        dev=local_vars["dev"],
        max_iterations=local_vars["max_iterations"],
        coverage_status=local_vars["coverage_status"],
        coverage_goal=local_vars["coverage_goal"],
        no_coverage_ratchet=local_vars["no_coverage_ratchet"],
        boost_coverage=local_vars["boost_coverage"],
        disable_global_locks=local_vars["disable_global_locks"],
        global_lock_timeout=local_vars["global_lock_timeout"],
        global_lock_cleanup=local_vars["global_lock_cleanup"],
        global_lock_dir=local_vars["global_lock_dir"],
        quick=local_vars["quick"],
        thorough=local_vars["thorough"],
        clear_cache=local_vars["clear_cache"],
        cleanup_docs=local_vars["cleanup_docs"],
        docs_dry_run=local_vars["docs_dry_run"],
        cleanup_configs=local_vars["cleanup_configs"],
        configs_dry_run=local_vars["configs_dry_run"],
        cleanup_git=local_vars["cleanup_git"],
        update_docs=local_vars["update_docs"],
        cache_stats=local_vars["cache_stats"],
        generate_docs=local_vars["generate_docs"],
        docs_format=local_vars["docs_format"],
        validate_docs=local_vars["validate_docs"],
        docs_check=local_vars["docs_check"],
        docs_validate=local_vars["docs_validate"],
        generate_changelog=local_vars["generate_changelog"],
        changelog_version=local_vars["changelog_version"],
        changelog_since=local_vars["changelog_since"],
        changelog_dry_run=local_vars["changelog_dry_run"],
        auto_version=local_vars["auto_version"],
        version_since=local_vars["version_since"],
        accept_version=local_vars["accept_version"],
        smart_commit=local_vars["smart_commit"],
        heatmap=local_vars["heatmap"],
        heatmap_type=local_vars["heatmap_type"],
        heatmap_output=local_vars["heatmap_output"],
        anomaly_detection=local_vars["anomaly_detection"],
        anomaly_sensitivity=local_vars["anomaly_sensitivity"],
        anomaly_report=local_vars["anomaly_report"],
        predictive_analytics=local_vars["predictive_analytics"],
        prediction_periods=local_vars["prediction_periods"],
        analytics_dashboard=local_vars["analytics_dashboard"],
        advanced_optimizer=local_vars["advanced_optimizer"],
        advanced_profile=local_vars["advanced_profile"],
        advanced_report=local_vars["advanced_report"],
        mkdocs_integration=local_vars["mkdocs_integration"],
        mkdocs_serve=local_vars["mkdocs_serve"],
        mkdocs_theme=local_vars["mkdocs_theme"],
        mkdocs_output=local_vars["mkdocs_output"],
        contextual_ai=local_vars["contextual_ai"],
        ai_recommendations=local_vars["ai_recommendations"],
        ai_help_query=local_vars["ai_help_query"],
        check_config_updates=local_vars["check_config_updates"],
        apply_config_updates=local_vars["apply_config_updates"],
        diff_config=local_vars["diff_config"],
        config_interactive=local_vars["config_interactive"],
        refresh_cache=local_vars["refresh_cache"],
        strip_code=local_vars["strip_code"],
        run_tests=local_vars["run_tests"],
        xcode_tests=local_vars["xcode_tests"],
        xcode_project=local_vars["xcode_project"],
        xcode_scheme=local_vars["xcode_scheme"],
        xcode_configuration=local_vars["xcode_configuration"],
        xcode_destination=local_vars["xcode_destination"],
        ai_fix=local_vars["ai_fix"],
        dry_run=local_vars["dry_run"],
        full_release=local_vars["full_release"],
        show_progress=local_vars["show_progress"],
        advanced_monitor=local_vars["advanced_monitor"],
        coverage_report=local_vars["coverage_report"],
        clean_releases=local_vars["clean_releases"],
    )

    options.index = local_vars["index"]
    options.search = local_vars["search"]
    options.semantic_stats = local_vars["semantic_stats"]
    options.remove_from_index = local_vars["remove_from_index"]

    return options


def _setup_ai_options(local_vars: dict[str, t.Any], options: "Options") -> "Options":
    ai_fix, verbose = setup_debug_and_verbose_flags(
        local_vars["ai_fix"],
        local_vars["ai_debug"],
        local_vars["debug"],
        local_vars["verbose"],
        options,
    )
    setup_ai_agent_env(ai_fix, local_vars["ai_debug"] or local_vars["debug"])
    return options


def _configure_logging(debug: bool) -> None:
    if debug:
        os.environ["ACB_LOG_LEVEL"] = "DEBUG"
        os.environ["CRACKERJACK_DEBUG"] = "1"

        if "ACB_DISABLE_STRUCTURED_STDERR" in os.environ:
            del os.environ["ACB_DISABLE_STRUCTURED_STDERR"]
        os.environ["ACB_FORCE_STRUCTURED_STDERR"] = "1"


def _execute_workflow_mode(options: "Options", job_id: str | None = None) -> None:
    if options.interactive:
        handle_interactive_mode(options)
    else:
        handle_standard_mode(options, job_id=job_id)


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

    # TODO: Restore monitor/dashboard/watchdog handling if needed

    if not handle_coverage_status(local_vars["coverage_status"], options):
        return False

    return _handle_analysis_commands(local_vars, options)


def _handle_analysis_commands(local_vars: t.Any, options: t.Any) -> bool:

    if local_vars["docs_check"]:
        from crackerjack.core.console import CrackerjackConsole

        console_impl = CrackerjackConsole()
        exit_code = check_docs(console_impl)
        raise typer.Exit(exit_code)

    if local_vars["docs_validate"]:
        from crackerjack.core.console import CrackerjackConsole

        console_impl = CrackerjackConsole()
        exit_code = validate_docs(console_impl)
        raise typer.Exit(exit_code)

    if not handle_documentation_commands(
        local_vars["generate_docs"],
        local_vars["validate_docs"],
        options,
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
        local_vars["heatmap"],
        local_vars["heatmap_type"],
        local_vars["heatmap_output"],
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
) -> None:
    if index:
        handle_semantic_index(index)

    if search:
        handle_semantic_search(search)

    if semantic_stats:
        handle_semantic_stats()

    if remove_from_index:
        handle_remove_from_semantic_index(remove_from_index)


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

    return handle_contextual_ai(
        local_vars["contextual_ai"],
        local_vars["ai_recommendations"],
        local_vars["ai_help_query"],
    )


@app.command()
def run_tests(
    workers: int = typer.Option(
        0,
        "--workers",
        "-n",
        help="Test workers (0=auto-detect)",
    ),
    timeout: int = typer.Option(300, "--timeout", help="Test timeout in seconds"),
    coverage: bool = typer.Option(
        True,
        "--coverage/--no-coverage",
        help="Run with coverage tracking",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Verbose output"),
    benchmark: bool = typer.Option(
        False,
        "--benchmark",
        help="Run performance benchmarks",
    ),
) -> t.Never:
    cmd = ["pytest"]

    if workers != 1:
        cmd.extend(["-n", str(workers) if workers > 0 else "auto"])

    if coverage:
        package_name = _detect_package_name_standalone()
        cmd.extend([f"--cov={package_name}", "--cov-report=html", "--cov-report=term"])

    cmd.append(f"--timeout={timeout}")

    if verbose:
        cmd.append("-vv")

    if benchmark:
        cmd.append("--benchmark-only")

    console.print(f"[blue]Running: {' '.join(cmd)}[/blue]")
    result = subprocess.run(cmd, check=False)
    raise typer.Exit(result.returncode)


@app.command("health")
def health_command(
    component: str | None = typer.Option(
        None,
        "--component",
        "-c",
        help="Specific component to check (adapters, managers, services, all)",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output results as JSON",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Show detailed health information",
    ),
    quiet: bool = typer.Option(
        False,
        "--quiet",
        "-q",
        help="Only show exit code (no output)",
    ),
) -> t.Never:
    from pathlib import Path

    from crackerjack.cli.handlers.health import handle_health_check

    pkg_path = Path.cwd()
    exit_code = handle_health_check(
        component=component,
        json_output=json_output,
        verbose=verbose,
        quiet=quiet,
        pkg_path=pkg_path,
    )
    raise typer.Exit(exit_code)


@app.command()
def qa_health() -> t.Never:
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
        console.print(f" {status} {adapter_name}")

    if qa_status.get("total", 0) == qa_status.get("healthy", 0):
        console.print("\n[green]✅ All adapters healthy[/green]")
        raise typer.Exit(0)
    console.print("\n[yellow]⚠️ Some adapters unhealthy[/yellow]")
    raise typer.Exit(1)


@app.command()
def shell() -> None:
    from crackerjack.config import CrackerjackSettings, load_settings
    from crackerjack.shell import CrackerjackShell

    settings = load_settings(CrackerjackSettings)

    shell_instance = CrackerjackShell(settings)
    shell_instance.start()


def main() -> None:
    app()


if __name__ == "__main__":
    main()


cli = app
