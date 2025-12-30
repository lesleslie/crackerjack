import logging
import os
import typing as t
from pathlib import Path

from rich.console import Console

from .options import Options

console = Console()
logger = logging.getLogger(__name__)

if t.TYPE_CHECKING:
    from crackerjack.services.quality.config_template import (
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
    elif debug_mode:  # Handle debug mode without AI agent
        os.environ["AI_AGENT_DEBUG"] = "1"
        os.environ["AI_AGENT_VERBOSE"] = "1"
        console.print(
            "[bold cyan]🐛 AI Debug Mode Configuration: [/ bold cyan]",
        )
        console.print(
            f" • Debug Mode: {'✅ Enabled' if os.environ.get('AI_AGENT_DEBUG') == '1' else '❌ Disabled'}",
        )
        console.print(
            f" • Verbose Mode: {'✅ Enabled' if os.environ.get('AI_AGENT_VERBOSE') == '1' else '❌ Disabled'}",
        )
        console.print(" • Structured logging enabled for debugging")

    # Set up structured logging if debug or ai_agent is enabled
    if ai_agent or debug_mode:
        from crackerjack.services.logging import setup_structured_logging

        setup_structured_logging(level="DEBUG", json_output=True)


def handle_mcp_server() -> None:
    from crackerjack.mcp.server import main as start_mcp_main

    project_path = str(Path.cwd())
    start_mcp_main(project_path)


def handle_watchdog_mode() -> None:
    from crackerjack.mcp.service_watchdog import main as start_watchdog

    try:
        asyncio.run(start_watchdog())
    except KeyboardInterrupt:
        console.print("\n[yellow]🛑 Watchdog stopped[/ yellow]")


def handle_stop_mcp_server() -> None:
    from crackerjack.services.server_manager import (
        list_server_status,
        stop_all_servers,
    )

    console.print("[bold red]🛑 Stopping MCP Servers[/ bold red]")

    list_server_status(console)

    if stop_all_servers(console):
        console.print("\n[bold green]✅ All servers stopped successfully[/ bold green]")
    else:
        console.print("\n[bold red]❌ Some servers failed to stop[/ bold red]")
        raise SystemExit(1)


def handle_restart_mcp_server() -> None:
    from crackerjack.services.server_manager import restart_mcp_server

    if restart_mcp_server(console):
        console.print("\n[bold green]✅ MCP server restart completed[/ bold green]")
    else:
        console.print("\n[bold red]❌ MCP server restart failed[/ bold red]")
        raise SystemExit(1)


def handle_start_zuban_lsp(port: int = 8677, mode: str = "tcp") -> None:
    """Start Zuban LSP server."""
    from crackerjack.services.zuban_lsp_service import (
        create_zuban_lsp_service,
    )

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

    if restart_zuban_lsp(console):
        console.print(
            "\n[bold green]✅ Zuban LSP server restart completed[/bold green]"
        )
    else:
        console.print("\n[bold red]❌ Zuban LSP server restart failed[/bold red]")
        raise SystemExit(1)


def handle_interactive_mode(options: Options) -> None:
    from crackerjack.cli.version import get_package_version

    from .interactive import launch_interactive_cli

    pkg_version = get_package_version()
    launch_interactive_cli(pkg_version, options)


def handle_standard_mode(
    options: Options,
    job_id: str | None = None,
) -> None:
    """Execute standard quality workflow.

    TODO(Phase 3): Workflow orchestration infrastructure removed in Phase 2.
    Will be reimplemented with Oneiric integration.
    """
    raise NotImplementedError(
        "Workflow orchestration removed in Phase 2 (ACB removal). "
        "Will be reimplemented in Phase 3 (Oneiric integration)."
    )


def handle_config_updates(options: Options) -> None:
    """Handle configuration update commands."""
    from crackerjack.services.quality.config_template import ConfigTemplateService

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
    config_service: "ConfigTemplateService", pkg_path: Path
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
) -> None:
    """Handle showing configuration diff."""
    console.print(f"[bold cyan]📊 Showing diff for {config_type}...[/bold cyan]")
    diff_preview = config_service._generate_diff_preview(config_type, pkg_path)
    console.print(f"\nChanges for {config_type}:")
    console.print(diff_preview)


def _handle_refresh_cache(
    config_service: "ConfigTemplateService", pkg_path: Path
) -> None:
    """Handle refreshing cache."""
    console.print("[bold cyan]🧹 Refreshing cache...[/bold cyan]")
    config_service._invalidate_cache(pkg_path)
    console.print("[green]✅ Cache refreshed[/green]")


def _display_available_updates(updates: dict[str, "ConfigUpdateInfo"]) -> None:
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
) -> int:
    """Apply configuration updates in batch and return success count."""
    success_count = 0
    for config_type in configs:
        if config_service.apply_update(config_type, pkg_path, interactive=interactive):
            success_count += 1
    return success_count


def _report_update_results(success_count: int, total_count: int) -> None:
    """Report the results of configuration updates."""
    if success_count == total_count:
        console.print(
            f"[green]✅ Successfully updated {success_count} configurations[/green]"
        )
    else:
        console.print(
            f"[yellow]⚠️ Updated {success_count}/{total_count} configurations[/yellow]"
        )
