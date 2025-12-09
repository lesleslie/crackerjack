"""Main CLI handlers that were originally in the monolithic handlers.py file.

This module contains the core handler functions that coordinate the main CLI
workflows and need to be separated from monitoring-specific handlers.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from acb.console import Console
from acb.depends import Inject, depends

from ..options import Options


@depends.inject  # type: ignore[misc]
def setup_ai_agent_env(
    ai_agent: bool, debug_mode: bool = False, console: Inject[Console] = None
) -> None:
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


@depends.inject  # type: ignore[misc]
def handle_interactive_mode(options: Options, console: Inject[Console] = None) -> None:
    from crackerjack.cli.version import get_package_version

    from ..interactive import launch_interactive_cli

    pkg_version = get_package_version()
    launch_interactive_cli(pkg_version, options)


@depends.inject  # type: ignore[misc]
def handle_standard_mode(
    options: Options,
    async_mode: bool,
    job_id: str | None = None,
    orchestrated: bool = False,
    console: Inject[Console] = None,
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

    # Default path: Legacy orchestrator (Phase 4.0 status)
    if not orchestrated:
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
                changed_only=getattr(options, "changed_only", False),
            )
            success = asyncio.run(
                async_orchestrator.run_complete_workflow_async(options)
            )
        else:
            sync_orchestrator = WorkflowOrchestrator(
                pkg_path=pkg_path,
                dry_run=getattr(options, "dry_run", False),
                web_job_id=job_id,
                verbose=options.verbose,
                debug=getattr(options, "debug", False),
                changed_only=getattr(options, "changed_only", False),
            )
            success = sync_orchestrator.run_complete_workflow_sync(options)

        if not success:
            raise SystemExit(1)


@depends.inject  # type: ignore[misc]
def handle_acb_workflow_mode(
    options: Options,
    job_id: str | None = None,
    console: Inject[Console] = None,
) -> None:
    """Execute workflow using ACB workflow engine (Phase 3 Production).

    This handler routes execution to the CrackerjackWorkflowEngine using
    the WorkflowContainerBuilder to set up the full DI container with all
    28 services across 7 levels. Action handlers use WorkflowPipeline from
    the container for production-quality workflow execution.

    Args:
        options: CLI options with use_acb_workflows=True
        job_id: Optional WebSocket job ID for progress tracking
        console: Rich console for output
    """

    from acb.depends import depends

    from crackerjack.events.workflow_bus import WorkflowEventBus
    from crackerjack.workflows import (
        CrackerjackWorkflowEngine,
        EventBridgeAdapter,
        WorkflowContainerBuilder,
        register_actions,
        select_workflow_for_options,
    )

    console.print("[bold cyan]🚀 Crackerjack Workflow Engine (ACB-Powered)[/bold cyan]")

    try:
        # Phase 4: ACB workflows are now the default!
        console.print(
            "[dim]Building DI container (28 services across 7 levels)...[/dim]"
        )
        builder = WorkflowContainerBuilder(options, console=console)
        builder.build()

        # Validate all services are available
        health = builder.health_check()
        if not health["all_available"]:
            missing = ", ".join(health["missing"])
            console.print(f"[yellow]⚠️  Missing services: {missing}[/yellow]")
            console.print(
                "[yellow]Container health check failed, continuing with available services[/yellow]"
            )

        console.print("[dim]✓ DI container ready with WorkflowPipeline[/dim]")

        # Register ACB Logger explicitly (needed for BasicWorkflowEngine)
        from acb.logger import Logger

        try:
            logger = depends.get_sync(Logger)
        except Exception:
            # ACB Logger not available, this shouldn't happen but handle gracefully
            import logging

            logger = logging.getLogger("crackerjack")
            depends.set(Logger, logger)

        # Register WorkflowEventBus with DI container
        event_bus = WorkflowEventBus()
        depends.set(WorkflowEventBus, event_bus)

        # Register EventBridgeAdapter BEFORE creating engine (engine needs it for DI!)
        event_bridge = EventBridgeAdapter()
        depends.set(EventBridgeAdapter, event_bridge)

        # Initialize engine (EventBridgeAdapter will be injected)
        engine = CrackerjackWorkflowEngine()

        # Register action handlers with engine
        register_actions(engine)

        # Select workflow based on options (fast/comp/test/standard)
        workflow = select_workflow_for_options(options)

        console.print(f"[dim]Selected workflow: {workflow.name}[/dim]")

        # Show orchestration status
        from crackerjack.config import CrackerjackSettings

        settings = depends.get_sync(CrackerjackSettings)
        if settings.enable_orchestration:
            mode_info = f" ({settings.orchestration_mode} mode)"
            console.print(
                f"[dim]Orchestration: [cyan]⚡ enabled[/cyan]{mode_info} - async hooks with caching[/dim]"
            )

        # Phase 4.1: Retrieve WorkflowPipeline from DI container (synchronous context)
        # and pass it explicitly in workflow context to avoid async DI scope issues
        from crackerjack.core.workflow_orchestrator import WorkflowPipeline

        pipeline = depends.get_sync(WorkflowPipeline)

        # Phase 4.2: All dependencies now use Inject[] instead of deprecated depends()
        # This ensures they are properly resolved when retrieved from DI container

        # Execute workflow with options and pipeline in context
        result = asyncio.run(
            engine.execute(
                workflow,
                context={
                    "options": options,
                    "pipeline": pipeline,  # Pass pipeline with all dependencies properly resolved
                },
            )
        )

        # Check result and exit with appropriate code
        from acb.workflows import WorkflowState

        if result.state != WorkflowState.COMPLETED:
            console.print(f"[red]Workflow failed: {result.error}[/red]")
            raise SystemExit(1)

        console.print("[bold green]✓ Workflow completed successfully[/bold green]")

    except Exception as e:
        import traceback

        console.print(f"[red]ACB workflow execution failed: {e}[/red]")
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        console.print("[yellow]Falling back to legacy orchestrator[/yellow]")
        # Enable legacy orchestrator flag and retry
        options.use_legacy_orchestrator = True
        options.use_acb_workflows = False
        handle_standard_mode(options, False, job_id, False, console)


@depends.inject  # type: ignore[misc]
def handle_orchestrated_mode(
    options: Options, job_id: str | None = None, console: Inject[Console] = None
) -> None:
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


@depends.inject  # type: ignore[misc]
def handle_config_updates(options: Options, console: Inject[Console] = None) -> None:
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


@depends.inject  # type: ignore[misc]
def _handle_check_updates(
    config_service: ConfigTemplateService, pkg_path: Path, console: Inject[Console]
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


@depends.inject  # type: ignore[misc]
def _handle_apply_updates(
    config_service: ConfigTemplateService,
    pkg_path: Path,
    interactive: bool,
    console: Inject[Console],
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


@depends.inject  # type: ignore[misc]
def _handle_diff_config(
    config_service: ConfigTemplateService,
    pkg_path: Path,
    config_type: str,
    console: Inject[Console],
) -> None:
    """Handle showing configuration diff."""
    console.print(f"[bold cyan]📊 Showing diff for {config_type}...[/bold cyan]")
    diff_preview = config_service._generate_diff_preview(config_type, pkg_path)
    console.print(f"\nChanges for {config_type}:")
    console.print(diff_preview)


@depends.inject  # type: ignore[misc]
def _handle_refresh_cache(
    config_service: ConfigTemplateService, pkg_path: Path, console: Inject[Console]
) -> None:
    """Handle refreshing cache."""
    console.print("[bold cyan]🧹 Refreshing cache...[/bold cyan]")
    config_service._invalidate_cache(pkg_path)
    console.print("[green]✅ Cache refreshed[/green]")


@depends.inject  # type: ignore[misc]
def _display_available_updates(
    updates: dict[str, ConfigUpdateInfo], console: Inject[Console]
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


@depends.inject  # type: ignore[misc]
def _apply_config_updates_batch(
    config_service: ConfigTemplateService,
    configs: list[str],
    pkg_path: Path,
    interactive: bool,
    console: Inject[Console],
) -> int:
    """Apply configuration updates in batch and return success count."""
    success_count = 0
    for config_type in configs:
        if config_service.apply_update(config_type, pkg_path, interactive=interactive):
            success_count += 1
    return success_count


@depends.inject  # type: ignore[misc]
def _report_update_results(
    success_count: int, total_count: int, console: Inject[Console]
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
