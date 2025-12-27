"""Main CLI handlers that were originally in the monolithic handlers.py file.


logger = logging.getLogger(__name__)

This module contains the core handler functions that coordinate the main CLI
workflows and need to be separated from monitoring-specific handlers.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from rich.console import Console
from acb.depends import Inject, depends

from ..options import Options
def setup_ai_agent_env(
    ai_agent: bool, debug_mode: bool = False) -> None:
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
def handle_interactive_mode(options: Options) -> None:
    from crackerjack.cli.version import get_package_version

    from ..interactive import launch_interactive_cli

    pkg_version = get_package_version()
    launch_interactive_cli(pkg_version, options)
def handle_standard_mode(
    options: Options,
    async_mode: bool,
    job_id: str | None = None,
    orchestrated: bool = False,
) -> None:
    # Run the async configure method in an isolated event loop

    from crackerjack.executors.hook_lock_manager import hook_lock_manager

    # Call the synchronous method directly
    hook_lock_manager.configure_from_options(options)

    # Phase 4.2 COMPLETE: ACB workflows are now the default
    # Use --use-legacy-orchestrator to opt out and use the old orchestration system
    if not getattr(options, "use_legacy_orchestrator", False):
        # Default path: ACB workflow engine (Phase 4.2 complete)
        # Only skip if user explicitly opted out with --use-legacy-orchestrator
        handle_acb_workflow_mode(options, job_id, console)
        return

    # Legacy orchestrator path (only if use_legacy_orchestrator=True)
    if orchestrated:
        handle_orchestrated_mode(options, job_id)

    # TODO(Phase 3): Replace with Oneiric workflow execution
    if not orchestrated:
        raise NotImplementedError(
            "Legacy workflow orchestration removed in Phase 2 (ACB removal). "
            "Will be reimplemented in Phase 3 (Oneiric integration)."
        )
def handle_acb_workflow_mode(
    options: Options,
    job_id: str | None = None,
) -> None:
    """Execute workflow using ACB workflow engine (Phase 3 Production).

    TODO(Phase 3): This function is disabled pending Oneiric integration.
    ACB workflow infrastructure was removed in Phase 2.
    """
    raise NotImplementedError(
        "ACB workflow engine removed in Phase 2 (ACB removal). "
        "Will be reimplemented in Phase 3 (Oneiric integration)."
    )
def handle_orchestrated_mode(
    options: Options, job_id: str | None = None) -> None:
    console.print("[bold bright_blue]🚀 ORCHESTRATED MODE ENABLED[/ bold bright_blue]")

    # Run the async configure method in an isolated event loop

    from crackerjack.executors.hook_lock_manager import hook_lock_manager

    # Call the synchronous method directly
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
    config_service: ConfigTemplateService, pkg_path: Path
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
    config_service: ConfigTemplateService,
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
    config_service: ConfigTemplateService,
    pkg_path: Path,
    config_type: str,
) -> None:
    """Handle showing configuration diff."""
    console.print(f"[bold cyan]📊 Showing diff for {config_type}...[/bold cyan]")
    diff_preview = config_service._generate_diff_preview(config_type, pkg_path)
    console.print(f"\nChanges for {config_type}:")
    console.print(diff_preview)
def _handle_refresh_cache(
    config_service: ConfigTemplateService, pkg_path: Path
) -> None:
    """Handle refreshing cache."""
    console.print("[bold cyan]🧹 Refreshing cache...[/bold cyan]")
    config_service._invalidate_cache(pkg_path)
    console.print("[green]✅ Cache refreshed[/green]")
def _display_available_updates(
    updates: dict[str, ConfigUpdateInfo]
) -> None:
    """Display available configuration updates."""
    console.print("[yellow]📋 Available updates:[/yellow]")
    for config_type, update_info in updates.items():
        if update_info.needs_update:
            console.print(
                f"  • {config_type}: {update_info.current_version} → {update_info.latest_version}"
            )


def _get_configs_needing_update(updates: dict[str, ConfigUpdateInfo]) -> list[str]:
    """Get list of configurations that need updates."""
    return [
        config_type
        for config_type, update_info in updates.items()
        if update_info.needs_update
    ]
def _apply_config_updates_batch(
    config_service: ConfigTemplateService,
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
def _report_update_results(
    success_count: int, total_count: int
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
