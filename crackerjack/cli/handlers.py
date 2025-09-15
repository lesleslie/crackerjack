import asyncio
import os
import sys
import typing as t
from pathlib import Path

from rich.console import Console

from .options import Options

if t.TYPE_CHECKING:
    from crackerjack.services.config_template import (
        ConfigTemplateService,
        ConfigUpdateInfo,
    )


def setup_ai_agent_env(ai_agent: bool, debug_mode: bool = False) -> None:
    if debug_mode:
        os.environ["CRACKERJACK_DEBUG"] = "1"

    if ai_agent:
        os.environ["AI_AGENT"] = "1"

        if debug_mode:
            os.environ["AI_AGENT_DEBUG"] = "1"
            os.environ["AI_AGENT_VERBOSE"] = "1"

            console = Console()
            console.print(
                "[bold cyan]🐛 AI Agent Debug Mode Configuration: [/ bold cyan]",
            )
            console.print(f" • AI Agent: {'✅ Enabled' if ai_agent else '❌ Disabled'}")
            console.print(
                f" • Debug Mode: {'✅ Enabled' if os.environ.get('AI_AGENT_DEBUG') == '1' else '❌ Disabled'}",
            )
            console.print(
                f" • Verbose Mode: {'✅ Enabled' if os.environ.get('AI_AGENT_VERBOSE') == '1' else '❌ Disabled'}",
            )
            console.print(" • Enhanced logging will be available during execution")


def handle_mcp_server(websocket_port: int | None = None) -> None:
    from crackerjack.mcp.server import main as start_mcp_main

    project_path = str(Path.cwd())

    if websocket_port:
        start_mcp_main(project_path, websocket_port)
    else:
        start_mcp_main(project_path)


def handle_monitor_mode(dev_mode: bool = False) -> None:
    from crackerjack.mcp.progress_monitor import run_progress_monitor

    console = Console()
    console.print("[bold cyan]🌟 Starting Multi-Project Progress Monitor[/ bold cyan]")
    console.print(
        "[bold yellow]🐕 With integrated Service Watchdog and WebSocket polling[/ bold yellow]",
    )

    try:
        asyncio.run(run_progress_monitor(dev_mode=dev_mode))
    except KeyboardInterrupt:
        console.print("\n[yellow]🛑 Monitor stopped[/ yellow]")


def handle_enhanced_monitor_mode(dev_mode: bool = False) -> None:
    from crackerjack.mcp.enhanced_progress_monitor import run_enhanced_progress_monitor

    console = Console()
    console.print("[bold magenta]✨ Starting Enhanced Progress Monitor[/ bold magenta]")
    console.print(
        "[bold cyan]📊 With advanced MetricCard widgets and modern web UI patterns[/ bold cyan]",
    )

    try:
        asyncio.run(run_enhanced_progress_monitor(dev_mode=dev_mode))
    except KeyboardInterrupt:
        console.print("\n[yellow]🛑 Enhanced Monitor stopped[/ yellow]")


def handle_dashboard_mode(dev_mode: bool = False) -> None:
    from crackerjack.mcp.dashboard import run_dashboard

    console = Console()
    console.print("[bold green]🎯 Starting Comprehensive Dashboard[/ bold green]")
    console.print(
        "[bold cyan]📈 With system metrics, job tracking, and performance monitoring[/ bold cyan]",
    )

    try:
        run_dashboard()
    except KeyboardInterrupt:
        console.print("\n[yellow]🛑 Dashboard stopped[/ yellow]")


def handle_unified_dashboard_mode(port: int = 8675, dev_mode: bool = False) -> None:
    from crackerjack.monitoring.websocket_server import CrackerjackMonitoringServer

    console = Console()
    console.print("[bold green]🚀 Starting Unified Monitoring Dashboard[/bold green]")
    console.print(
        f"[bold cyan]🌐 WebSocket server on port {port} with real-time streaming and web UI[/bold cyan]",
    )

    try:
        server = CrackerjackMonitoringServer()
        asyncio.run(server.start_monitoring(port))
    except KeyboardInterrupt:
        console.print("\n[yellow]🛑 Unified Dashboard stopped[/yellow]")
    except Exception as e:
        console.print(f"\n[red]❌ Unified Dashboard failed: {e}[/red]")


def handle_watchdog_mode() -> None:
    from crackerjack.mcp.service_watchdog import main as start_watchdog

    console = Console()
    try:
        asyncio.run(start_watchdog())
    except KeyboardInterrupt:
        console.print("\n[yellow]🛑 Watchdog stopped[/ yellow]")


def handle_start_websocket_server(port: int = 8675) -> None:
    from crackerjack.mcp.websocket.server import handle_websocket_server_command

    handle_websocket_server_command(start=True, port=port)


def handle_stop_websocket_server() -> None:
    from crackerjack.mcp.websocket.server import handle_websocket_server_command

    handle_websocket_server_command(stop=True)


def handle_restart_websocket_server(port: int = 8675) -> None:
    from crackerjack.mcp.websocket.server import handle_websocket_server_command

    handle_websocket_server_command(restart=True, port=port)


def handle_stop_mcp_server() -> None:
    from crackerjack.services.server_manager import list_server_status, stop_all_servers

    console = Console()
    console.print("[bold red]🛑 Stopping MCP Servers[/ bold red]")

    list_server_status(console)

    if stop_all_servers(console):
        console.print("\n[bold green]✅ All servers stopped successfully[/ bold green]")
    else:
        console.print("\n[bold red]❌ Some servers failed to stop[/ bold red]")
        raise SystemExit(1)


def handle_restart_mcp_server(websocket_port: int | None = None) -> None:
    from crackerjack.services.server_manager import restart_mcp_server

    console = Console()
    if restart_mcp_server(websocket_port, console):
        console.print("\n[bold green]✅ MCP server restart completed[/ bold green]")
    else:
        console.print("\n[bold red]❌ MCP server restart failed[/ bold red]")
        raise SystemExit(1)


def handle_start_zuban_lsp(port: int = 8677, mode: str = "tcp") -> None:
    """Start Zuban LSP server."""
    from crackerjack.services.zuban_lsp_service import create_zuban_lsp_service

    console = Console()
    console.print("[bold cyan]🚀 Starting Zuban LSP Server[/bold cyan]")

    async def _start() -> None:
        lsp_service = await create_zuban_lsp_service(
            port=port, mode=mode, console=console
        )
        if await lsp_service.start():
            console.print(
                f"[bold green]✅ Zuban LSP server started on port {port} ({mode} mode)[/bold green]"
            )
        else:
            console.print("[bold red]❌ Failed to start Zuban LSP server[/bold red]")
            raise SystemExit(1)

    try:
        asyncio.run(_start())
    except KeyboardInterrupt:
        console.print("\n[yellow]🛑 Zuban LSP startup interrupted[/yellow]")


def handle_stop_zuban_lsp() -> None:
    """Stop Zuban LSP server."""
    from crackerjack.services.server_manager import stop_zuban_lsp

    console = Console()
    console.print("[bold red]🛑 Stopping Zuban LSP Server[/bold red]")

    if stop_zuban_lsp(console):
        console.print(
            "\n[bold green]✅ Zuban LSP server stopped successfully[/bold green]"
        )
    else:
        console.print("\n[bold red]❌ Failed to stop Zuban LSP server[/bold red]")
        raise SystemExit(1)


def handle_restart_zuban_lsp(port: int = 8677, mode: str = "tcp") -> None:
    """Restart Zuban LSP server."""
    from crackerjack.services.server_manager import restart_zuban_lsp

    console = Console()
    if restart_zuban_lsp(console):
        console.print(
            "\n[bold green]✅ Zuban LSP server restart completed[/bold green]"
        )
    else:
        console.print("\n[bold red]❌ Zuban LSP server restart failed[/bold red]")
        raise SystemExit(1)


def handle_interactive_mode(options: Options) -> None:
    from crackerjack.cli.utils import get_package_version

    from .interactive import launch_interactive_cli

    pkg_version = get_package_version()
    launch_interactive_cli(pkg_version, options)


def handle_standard_mode(
    options: Options,
    async_mode: bool,
    job_id: str | None = None,
    orchestrated: bool = False,
) -> None:
    from rich.console import Console

    console = Console()

    from crackerjack.executors.hook_lock_manager import hook_lock_manager

    hook_lock_manager.configure_from_options(options)

    if orchestrated:
        handle_orchestrated_mode(options, job_id)
    else:
        from crackerjack.core.async_workflow_orchestrator import (
            AsyncWorkflowOrchestrator,
        )
        from crackerjack.core.workflow_orchestrator import WorkflowOrchestrator

        pkg_path = Path.cwd()

        if async_mode:
            async_orchestrator = AsyncWorkflowOrchestrator(
                console=console,
                pkg_path=pkg_path,
                dry_run=getattr(options, "dry_run", False),
                web_job_id=job_id,
                verbose=options.verbose,
                debug=getattr(options, "debug", False),
            )
            success = asyncio.run(
                async_orchestrator.run_complete_workflow_async(options)
            )
        else:
            sync_orchestrator = WorkflowOrchestrator(
                console=console,
                pkg_path=pkg_path,
                dry_run=getattr(options, "dry_run", False),
                web_job_id=job_id,
                verbose=options.verbose,
                debug=getattr(options, "debug", False),
            )
            success = sync_orchestrator.run_complete_workflow_sync(options)

        if not success:
            raise SystemExit(1)


def handle_orchestrated_mode(options: Options, job_id: str | None = None) -> None:
    from rich.console import Console

    console = Console()
    console.print("[bold bright_blue]🚀 ORCHESTRATED MODE ENABLED[/ bold bright_blue]")

    from crackerjack.executors.hook_lock_manager import hook_lock_manager

    hook_lock_manager.configure_from_options(options)

    try:
        from crackerjack.core.session_coordinator import SessionCoordinator
        from crackerjack.orchestration.advanced_orchestrator import (
            AdvancedWorkflowOrchestrator,
        )
        from crackerjack.orchestration.execution_strategies import (
            AICoordinationMode,
            ExecutionStrategy,
            OrchestrationConfig,
            ProgressLevel,
        )
    except ImportError as e:
        console.print(f"[red]Orchestrated mode not available: {e}[/ red]")
        console.print("[yellow]Falling back to standard mode[/ yellow]")
        handle_standard_mode(options, False, job_id)
        return

    try:
        strategy = ExecutionStrategy(options.orchestration_strategy)
    except ValueError:
        console.print(
            f"[red]Invalid orchestration strategy: {options.orchestration_strategy}[/ red]",
        )
        strategy = ExecutionStrategy.ADAPTIVE

    try:
        progress = ProgressLevel(options.orchestration_progress)
    except ValueError:
        console.print(
            f"[red]Invalid progress level: {options.orchestration_progress}[/ red]",
        )
        progress = ProgressLevel.GRANULAR

    try:
        ai_mode = AICoordinationMode(options.orchestration_ai_mode)
    except ValueError:
        console.print(f"[red]Invalid AI mode: {options.orchestration_ai_mode}[/ red]")
        ai_mode = AICoordinationMode.SINGLE_AGENT

    config = OrchestrationConfig(
        execution_strategy=strategy,
        progress_level=progress,
        ai_coordination_mode=ai_mode,
    )

    console.print(f"[cyan]Execution Strategy: [/ cyan] {strategy.value}")
    console.print(f"[cyan]Progress Level: [/ cyan] {progress.value}")
    console.print(f"[cyan]AI Coordination: [/ cyan] {ai_mode.value}")

    pkg_path = Path.cwd()
    session = SessionCoordinator(console, pkg_path, web_job_id=job_id)
    orchestrator = AdvancedWorkflowOrchestrator(console, pkg_path, session, config)

    try:
        success = asyncio.run(orchestrator.execute_orchestrated_workflow(options))
        if success:
            console.print(
                "\n[bold green]🎉 ORCHESTRATED WORKFLOW COMPLETED SUCCESSFULLY ![/ bold green]",
            )
        else:
            console.print("\n[bold red]❌ ORCHESTRATED WORKFLOW FAILED[/ bold red]")
            sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]🛑 Orchestrated workflow interrupted[/ yellow]")
        sys.exit(130)
    except Exception as e:
        console.print(f"\n[red]💥 Orchestrated workflow error: {e}[/ red]")
        sys.exit(1)


def handle_config_updates(options: Options) -> None:
    """Handle configuration update commands."""
    from crackerjack.services.config_template import ConfigTemplateService

    console = Console()
    pkg_path = Path.cwd()
    config_service = ConfigTemplateService(console, pkg_path)

    if options.check_config_updates:
        _handle_check_updates(config_service, pkg_path, console)
    elif options.apply_config_updates:
        _handle_apply_updates(
            config_service, pkg_path, options.config_interactive, console
        )
    elif options.diff_config:
        _handle_diff_config(config_service, pkg_path, options.diff_config, console)
    elif options.refresh_cache:
        _handle_refresh_cache(config_service, pkg_path, console)


def _handle_check_updates(
    config_service: "ConfigTemplateService", pkg_path: Path, console: Console
) -> None:
    """Handle checking for configuration updates."""
    console.print("[bold cyan]🔍 Checking for configuration updates...[/bold cyan]")
    updates = config_service.check_updates(pkg_path)

    if not updates:
        console.print("[green]✅ No configuration templates available[/green]")
        return

    has_updates = any(update.needs_update for update in updates.values())
    if not has_updates:
        console.print("[green]✅ All configurations are up to date[/green]")
        return

    _display_available_updates(updates, console)
    console.print("\nUse --apply-config-updates to apply these updates")


def _handle_apply_updates(
    config_service: "ConfigTemplateService",
    pkg_path: Path,
    interactive: bool,
    console: Console,
) -> None:
    """Handle applying configuration updates."""
    console.print("[bold cyan]🔧 Applying configuration updates...[/bold cyan]")
    updates = config_service.check_updates(pkg_path)

    if not updates:
        console.print("[yellow]⚠️ No configuration templates available[/yellow]")
        return

    configs_to_update = _get_configs_needing_update(updates)
    if not configs_to_update:
        console.print("[green]✅ All configurations are already up to date[/green]")
        return

    success_count = _apply_config_updates_batch(
        config_service, configs_to_update, pkg_path, interactive, console
    )
    _report_update_results(success_count, len(configs_to_update), console)


def _handle_diff_config(
    config_service: "ConfigTemplateService",
    pkg_path: Path,
    config_type: str,
    console: Console,
) -> None:
    """Handle showing configuration diff."""
    console.print(f"[bold cyan]📊 Showing diff for {config_type}...[/bold cyan]")
    diff_preview = config_service._generate_diff_preview(config_type, pkg_path)
    console.print(f"\nChanges for {config_type}:")
    console.print(diff_preview)


def _handle_refresh_cache(
    config_service: "ConfigTemplateService", pkg_path: Path, console: Console
) -> None:
    """Handle refreshing pre-commit cache."""
    console.print("[bold cyan]🧹 Refreshing pre-commit cache...[/bold cyan]")
    config_service._invalidate_precommit_cache(pkg_path)
    console.print("[green]✅ Pre-commit cache refreshed[/green]")


def _display_available_updates(
    updates: dict[str, "ConfigUpdateInfo"], console: Console
) -> None:
    """Display available configuration updates."""
    console.print("[yellow]📋 Available updates:[/yellow]")
    for config_type, update_info in updates.items():
        if update_info.needs_update:
            console.print(
                f"  • {config_type}: {update_info.current_version} → {update_info.latest_version}"
            )


def _get_configs_needing_update(updates: dict[str, "ConfigUpdateInfo"]) -> list[str]:
    """Get list of configurations that need updates."""
    return [
        config_type
        for config_type, update_info in updates.items()
        if update_info.needs_update
    ]


def _apply_config_updates_batch(
    config_service: "ConfigTemplateService",
    configs: list[str],
    pkg_path: Path,
    interactive: bool,
    console: Console,
) -> int:
    """Apply configuration updates in batch and return success count."""
    success_count = 0
    for config_type in configs:
        if config_service.apply_update(config_type, pkg_path, interactive=interactive):
            success_count += 1
    return success_count


def _report_update_results(
    success_count: int, total_count: int, console: Console
) -> None:
    """Report the results of configuration updates."""
    if success_count == total_count:
        console.print(
            f"[green]✅ Successfully updated {success_count} configurations[/green]"
        )
    else:
        console.print(
            f"[yellow]⚠️ Updated {success_count}/{total_count} configurations[/yellow]"
        )
