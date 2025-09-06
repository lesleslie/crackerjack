import asyncio
import os
import sys
from pathlib import Path

from rich.console import Console

from .options import Options


def setup_ai_agent_env(ai_agent: bool, debug_mode: bool = False) -> None:
    # Only set debug environment variable if debug mode is explicitly enabled
    if debug_mode:
        os.environ["CRACKERJACK_DEBUG"] = "1"

    if ai_agent:
        os.environ["AI_AGENT"] = "1"
        # Only enable AI agent debug if debug mode is explicitly requested
        if debug_mode:
            os.environ["AI_AGENT_DEBUG"] = "1"
            os.environ["AI_AGENT_VERBOSE"] = "1"

            # Show debug configuration when debug mode is enabled
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

    # Configure global lock manager from CLI options
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
            orchestrator = AsyncWorkflowOrchestrator(
                console=console,
                pkg_path=pkg_path,
                dry_run=getattr(options, "dry_run", False),
                web_job_id=job_id,
                verbose=options.verbose,
                debug=getattr(options, "debug", False),
            )
            success = asyncio.run(orchestrator.run_complete_workflow_async(options))
        else:
            orchestrator = WorkflowOrchestrator(
                console=console,
                pkg_path=pkg_path,
                dry_run=getattr(options, "dry_run", False),
                web_job_id=job_id,
                verbose=options.verbose,
                debug=getattr(options, "debug", False),
            )
            success = asyncio.run(orchestrator.run_complete_workflow(options))

        if not success:
            raise SystemExit(1)


def handle_orchestrated_mode(options: Options, job_id: str | None = None) -> None:
    from rich.console import Console

    console = Console()
    console.print("[bold bright_blue]🚀 ORCHESTRATED MODE ENABLED[/ bold bright_blue]")

    # Configure global lock manager from CLI options
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
