import typing as t

import typer
from rich.console import Console

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
    handle_dashboard_mode,
    handle_enhanced_monitor_mode,
    handle_mcp_server,
    handle_monitor_mode,
    handle_restart_mcp_server,
    handle_restart_websocket_server,
    handle_start_websocket_server,
    handle_stop_mcp_server,
    handle_stop_websocket_server,
    handle_watchdog_mode,
)

console = Console(force_terminal=True)
app = typer.Typer(
    help="Crackerjack: Your Python project setup and style enforcement tool.",
)


def _handle_monitoring_commands(
    monitor: bool,
    enhanced_monitor: bool,
    dashboard: bool,
    unified_dashboard: bool,
    unified_dashboard_port: int | None,
    watchdog: bool,
    dev: bool,
) -> bool:
    if monitor:
        handle_monitor_mode(dev_mode=dev)
        return True
    if enhanced_monitor:
        handle_enhanced_monitor_mode(dev_mode=dev)
        return True
    if dashboard:
        handle_dashboard_mode(dev_mode=dev)
        return True
    if unified_dashboard:
        from .cli.handlers import handle_unified_dashboard_mode

        port = unified_dashboard_port or 8675
        handle_unified_dashboard_mode(port=port, dev_mode=dev)
        return True
    if watchdog:
        handle_watchdog_mode()
        return True
    return False


def _handle_websocket_commands(
    start_websocket_server: bool,
    stop_websocket_server: bool,
    restart_websocket_server: bool,
    websocket_port: int | None,
) -> bool:
    if start_websocket_server:
        port = websocket_port or 8675
        handle_start_websocket_server(port)
        return True
    if stop_websocket_server:
        handle_stop_websocket_server()
        return True
    if restart_websocket_server:
        port = websocket_port or 8675
        handle_restart_websocket_server(port)
        return True
    return False


def _handle_mcp_commands(
    start_mcp_server: bool,
    stop_mcp_server: bool,
    restart_mcp_server: bool,
    websocket_port: int | None,
) -> bool:
    if start_mcp_server:
        handle_mcp_server(websocket_port)
        return True
    if stop_mcp_server:
        handle_stop_mcp_server()
        return True
    if restart_mcp_server:
        handle_restart_mcp_server(websocket_port)
        return True
    return False


def _handle_server_commands(
    monitor: bool,
    enhanced_monitor: bool,
    dashboard: bool,
    unified_dashboard: bool,
    unified_dashboard_port: int | None,
    watchdog: bool,
    start_websocket_server: bool,
    stop_websocket_server: bool,
    restart_websocket_server: bool,
    start_mcp_server: bool,
    stop_mcp_server: bool,
    restart_mcp_server: bool,
    websocket_port: int | None,
    dev: bool,
) -> bool:
    return (
        _handle_monitoring_commands(
            monitor,
            enhanced_monitor,
            dashboard,
            unified_dashboard,
            unified_dashboard_port,
            watchdog,
            dev,
        )
        or _handle_websocket_commands(
            start_websocket_server,
            stop_websocket_server,
            restart_websocket_server,
            websocket_port,
        )
        or _handle_mcp_commands(
            start_mcp_server,
            stop_mcp_server,
            restart_mcp_server,
            websocket_port,
        )
    )


def _generate_documentation(doc_service: t.Any, console: t.Any) -> bool:
    """Generate API documentation.

    Returns True if successful, False if failed.
    """
    console.print("📖 [bold blue]Generating API documentation...[/bold blue]")
    success = doc_service.generate_full_api_documentation()
    if success:
        console.print(
            "✅ [bold green]Documentation generated successfully![/bold green]"
        )
        return True
    else:
        console.print("❌ [bold red]Documentation generation failed![/bold red]")
        return False


def _validate_documentation_files(doc_service: t.Any, console: t.Any) -> None:
    """Validate existing documentation files."""
    from pathlib import Path

    console.print("🔍 [bold blue]Validating documentation...[/bold blue]")
    doc_paths = [Path("docs"), Path("README.md"), Path("CHANGELOG.md")]
    existing_docs = [p for p in doc_paths if p.exists()]

    if existing_docs:
        issues = doc_service.validate_documentation(existing_docs)
        if issues:
            console.print(f"⚠️ Found {len(issues)} documentation issues:")
            for issue in issues:
                file_path = issue.get("path", issue.get("file", "unknown"))
                console.print(f"  - {file_path}: {issue['message']}")
        else:
            console.print(
                "✅ [bold green]Documentation validation passed![/bold green]"
            )
    else:
        console.print("⚠️ No documentation files found to validate.")


def _handle_documentation_commands(
    generate_docs: bool, validate_docs: bool, console: Console, options: t.Any
) -> bool:
    """Handle documentation generation and validation commands.

    Returns True if documentation commands were handled and execution should continue,
    False if execution should return early.
    """
    if not (generate_docs or validate_docs):
        return True

    from pathlib import Path

    from crackerjack.services.documentation_service import DocumentationServiceImpl

    pkg_path = Path("crackerjack")
    doc_service = DocumentationServiceImpl(pkg_path=pkg_path, console=console)

    if generate_docs:
        if not _generate_documentation(doc_service, console):
            return False

    if validate_docs:
        _validate_documentation_files(doc_service, console)

    # Check if we should continue with other operations
    return any(
        [
            options.run_tests,
            options.strip_code,
            options.all,
            options.publish,
            options.comp,
        ]
    )


def _handle_changelog_commands(
    generate_changelog: bool,
    changelog_dry_run: bool,
    changelog_version: str | None,
    changelog_since: str | None,
    console: Console,
    options: t.Any,
) -> bool:
    """Handle changelog generation commands.

    Returns True if changelog commands were handled and execution should continue,
    False if execution should return early.
    """
    if not (generate_changelog or changelog_dry_run):
        return True

    from pathlib import Path

    from crackerjack.services.changelog_automation import ChangelogGenerator
    from crackerjack.services.git import GitService

    pkg_path = Path(".")
    git_service = GitService(console, pkg_path)
    changelog_generator = ChangelogGenerator(console, git_service)
    changelog_path = pkg_path / "CHANGELOG.md"

    if changelog_dry_run:
        console.print("🔍 [bold blue]Previewing changelog generation...[/bold blue]")
        entries = changelog_generator.generate_changelog_entries(changelog_since)
        if entries:
            changelog_generator._display_changelog_preview(entries)
            console.print("✅ [bold green]Changelog preview completed![/bold green]")
        else:
            console.print("⚠️ No new changelog entries to generate.")
    elif generate_changelog:
        console.print("📝 [bold blue]Generating changelog...[/bold blue]")
        version = changelog_version or "Unreleased"
        success = changelog_generator.generate_changelog_from_commits(
            changelog_path=changelog_path,
            version=version,
            since_version=changelog_since,
        )
        if success:
            console.print(
                f"✅ [bold green]Changelog updated for version {version}![/bold green]"
            )
        else:
            console.print("❌ [bold red]Changelog generation failed![/bold red]")
            return False

    # Check if we should continue with other operations
    return any(
        [
            options.run_tests,
            options.strip_code,
            options.all,
            options.publish,
            options.comp,
        ]
    )


def _handle_version_analysis(
    auto_version: bool,
    version_since: str | None,
    accept_version: bool,
    console: Console,
    options: t.Any,
) -> bool:
    """Handle automatic version analysis and recommendations.

    Returns True if version analysis was handled and execution should continue,
    False if execution should return early.
    """
    if not auto_version:
        return True

    from pathlib import Path

    from rich.prompt import Confirm

    from crackerjack.services.git import GitService
    from crackerjack.services.version_analyzer import VersionAnalyzer

    pkg_path = Path(".")
    git_service = GitService(console, pkg_path)
    version_analyzer = VersionAnalyzer(console, git_service)

    try:
        import asyncio

        recommendation = asyncio.run(
            version_analyzer.recommend_version_bump(version_since)
        )
        version_analyzer.display_recommendation(recommendation)

        if accept_version or Confirm.ask(
            f"\nAccept recommendation ({recommendation.bump_type.value})",
            default=True,
        ):
            console.print(
                f"[green]✅ Version bump accepted: {recommendation.current_version} → {recommendation.recommended_version}[/green]"
            )
            # Note: Actual version bumping would integrate with existing publish/bump logic
        else:
            console.print("[yellow]❌ Version bump declined[/yellow]")

    except Exception as e:
        console.print(f"[red]❌ Version analysis failed: {e}[/red]")

    # Check if we should continue with other operations
    return any(
        [
            options.run_tests,
            options.strip_code,
            options.all,
            options.publish,
            options.comp,
        ]
    )


def _setup_debug_and_verbose_flags(
    ai_debug: bool, debug: bool, verbose: bool, options: t.Any
) -> tuple[bool, bool]:
    """Configure debug and verbose flags and update options.

    Returns tuple of (ai_fix, verbose) flags.
    """
    ai_fix = False

    if ai_debug:
        ai_fix = True
        verbose = True
        options.verbose = True

    if debug:
        verbose = True
        options.verbose = True

    return ai_fix, verbose


@app.command()
def main(
    commit: bool = CLI_OPTIONS["commit"],
    interactive: bool = CLI_OPTIONS["interactive"],
    no_config_updates: bool = CLI_OPTIONS["no_config_updates"],
    update_precommit: bool = CLI_OPTIONS["update_precommit"],
    verbose: bool = CLI_OPTIONS["verbose"],
    debug: bool = CLI_OPTIONS["debug"],
    publish: BumpOption | None = CLI_OPTIONS["publish"],
    all: BumpOption | None = CLI_OPTIONS["all"],
    bump: BumpOption | None = CLI_OPTIONS["bump"],
    strip_code: bool = CLI_OPTIONS["strip_code"],
    run_tests: bool = CLI_OPTIONS["run_tests"],
    benchmark: bool = CLI_OPTIONS["benchmark"],
    test_workers: int = CLI_OPTIONS["test_workers"],
    test_timeout: int = CLI_OPTIONS["test_timeout"],
    skip_hooks: bool = CLI_OPTIONS["skip_hooks"],
    fast: bool = CLI_OPTIONS["fast"],
    comp: bool = CLI_OPTIONS["comp"],
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
) -> None:
    """Main CLI entry point with complexity <= 15."""
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
        create_pr,
        async_mode,
        experimental_hooks,
        enable_pyrefly,
        enable_ty,
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
    )

    # Setup debug and verbose flags
    ai_fix, verbose = _setup_debug_and_verbose_flags(ai_debug, debug, verbose, options)
    setup_ai_agent_env(ai_fix, ai_debug or debug)

    # Handle cache management commands early (they exit after execution)
    if _handle_cache_commands(clear_cache, cache_stats, console):
        return

    # Handle server commands (monitoring, websocket, MCP)
    if _handle_server_commands(
        monitor,
        enhanced_monitor,
        dashboard,
        unified_dashboard,
        unified_dashboard_port,
        watchdog,
        start_websocket_server,
        stop_websocket_server,
        restart_websocket_server,
        start_mcp_server,
        stop_mcp_server,
        restart_mcp_server,
        websocket_port,
        dev,
    ):
        return

    # Handle documentation commands
    if not _handle_documentation_commands(
        generate_docs, validate_docs, console, options
    ):
        return

    # Handle changelog commands
    if not _handle_changelog_commands(
        generate_changelog,
        changelog_dry_run,
        changelog_version,
        changelog_since,
        console,
        options,
    ):
        return

    # Handle version analysis
    if not _handle_version_analysis(
        auto_version, version_since, accept_version, console, options
    ):
        return

    # Execute main workflow (interactive or standard mode)
    if interactive:
        handle_interactive_mode(options)
    else:
        handle_standard_mode(options, async_mode, job_id, orchestrated)


def cli() -> None:
    app()


if __name__ == "__main__":
    app()
