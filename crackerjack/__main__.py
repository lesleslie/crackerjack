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
        _handle_monitoring_commands(monitor, enhanced_monitor, dashboard, watchdog, dev)
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
    clean: bool = CLI_OPTIONS["clean"],
    test: bool = CLI_OPTIONS["test"],
    benchmark: bool = CLI_OPTIONS["benchmark"],
    test_workers: int = CLI_OPTIONS["test_workers"],
    test_timeout: int = CLI_OPTIONS["test_timeout"],
    skip_hooks: bool = CLI_OPTIONS["skip_hooks"],
    fast: bool = CLI_OPTIONS["fast"],
    comp: bool = CLI_OPTIONS["comp"],
    create_pr: bool = CLI_OPTIONS["create_pr"],
    ai_agent: bool = CLI_OPTIONS["ai_agent"],
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
) -> None:
    options = create_options(
        commit,
        interactive,
        no_config_updates,
        update_precommit,
        verbose,
        debug,
        publish,
        all,
        bump,
        clean,
        test,
        benchmark,
        test_workers,
        test_timeout,
        skip_hooks,
        fast,
        comp,
        create_pr,
        ai_agent,
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
    )

    if ai_debug:
        ai_agent = True
        verbose = True
        # Update the options object to reflect the verbose setting
        options.verbose = True

    # If debug flag is set, enable verbose mode as well
    if debug:
        verbose = True
        options.verbose = True

    setup_ai_agent_env(ai_agent, ai_debug or debug)

    if _handle_server_commands(
        monitor,
        enhanced_monitor,
        dashboard,
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

    if interactive:
        handle_interactive_mode(options)
    else:
        handle_standard_mode(options, async_mode, job_id, orchestrated)


def cli() -> None:
    app()


if __name__ == "__main__":
    app()
