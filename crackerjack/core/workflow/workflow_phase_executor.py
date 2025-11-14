"""Phase execution orchestration for workflow pipeline.

Executes individual workflow phases (config, quality, tests, hooks, publishing, commit).
Handles LSP configuration and integration with Zuban type checking server.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import typing as t
from contextlib import suppress
from pathlib import Path

from acb.console import Console
from acb.depends import Inject, depends

from crackerjack.agents.base import AgentContext
from crackerjack.events import WorkflowEvent, WorkflowEventBus
from crackerjack.models.protocols import (
    DebugServiceProtocol,
    LoggerProtocol,
    OptionsProtocol,
    QualityIntelligenceProtocol,
)
from crackerjack.services.monitoring.performance_monitor import phase_monitor


class WorkflowPhaseExecutor:
    """Executes individual workflow phases and manages LSP configuration.

    This class handles:
    - Phase execution (config, quality, testing, hooks, publishing, commit)
    - LSP server lifecycle (initialization, configuration, cleanup)
    - AI-assisted fixing workflows
    - Phase monitoring and status tracking
    """

    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        logger: Inject[LoggerProtocol],
        pkg_path: Path,
        debugger: Inject[DebugServiceProtocol],
        quality_intelligence: Inject[QualityIntelligenceProtocol] | None = None,
    ) -> None:
        """Initialize phase executor.

        Args:
            console: Console for user output
            logger: Structured logger
            pkg_path: Project root path
            debugger: Debug service for workflow tracking
            quality_intelligence: Optional quality intelligence service
        """
        self.console = console
        self.logger = logger
        self.pkg_path = pkg_path
        self.debugger = debugger
        self._quality_intelligence = quality_intelligence
        self._mcp_state_manager: t.Any = None
        self._last_security_audit: t.Any = None
        self._code_cleaning_complete = False

        # These will be injected by orchestrator
        self.session: t.Any = None
        self.phases: t.Any = None
        self._event_bus: WorkflowEventBus | None = None

    def configure(
        self, session: t.Any, phases: t.Any, event_bus: WorkflowEventBus | None = None
    ) -> None:
        """Configure executor with required dependencies.

        Args:
            session: Session coordinator
            phases: Phase coordinator
            event_bus: Optional event bus for workflow events
        """
        self.session = session
        self.phases = phases
        self._event_bus = event_bus

    # =============================================================================
    # LSP CONFIGURATION METHODS (8 methods)
    # =============================================================================

    def _configure_session_cleanup(self, options: OptionsProtocol) -> None:
        """Configure session cleanup behavior."""
        if hasattr(options, "cleanup"):
            self.session.set_cleanup_config(options.cleanup)

    def _initialize_zuban_lsp(self, options: OptionsProtocol) -> None:
        """Initialize Zuban LSP server if not disabled."""
        if self._should_skip_zuban_lsp(options):
            return

        if self._is_zuban_lsp_already_running():
            return

        self._start_zuban_lsp_server(options)

    def _should_skip_zuban_lsp(self, options: OptionsProtocol) -> bool:
        """Check if Zuban LSP server should be skipped."""
        if getattr(options, "no_zuban_lsp", False):
            self.logger.debug("Zuban LSP server disabled by --no-zuban-lsp flag")
            return True

        config = getattr(options, "zuban_lsp", None)
        if config and not config.enabled:
            self.logger.debug("Zuban LSP server disabled in configuration")
            return True

        if config and not config.auto_start:
            self.logger.debug("Zuban LSP server auto-start disabled in configuration")
            return True

        return False

    def _is_zuban_lsp_already_running(self) -> bool:
        """Check if LSP server is already running to avoid duplicates."""
        from crackerjack.services.server_manager import find_zuban_lsp_processes

        existing_processes = find_zuban_lsp_processes()
        if existing_processes:
            self.logger.debug(
                f"Zuban LSP server already running (PID: {existing_processes[0]['pid']})"
            )
            return True
        return False

    def _start_zuban_lsp_server(self, options: OptionsProtocol) -> None:
        """Start the Zuban LSP server in background."""
        try:
            config = getattr(options, "zuban_lsp", None)
            zuban_lsp_port, zuban_lsp_mode = self._get_zuban_lsp_config(options, config)

            cmd = [
                sys.executable,
                "-m",
                "crackerjack",
                "--start-zuban-lsp",
                "--zuban-lsp-port",
                str(zuban_lsp_port),
                "--zuban-lsp-mode",
                zuban_lsp_mode,
            ]

            subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )

            self.logger.info(
                f"Auto-started Zuban LSP server on port {zuban_lsp_port} ({zuban_lsp_mode} mode)"
            )

        except Exception as e:
            self.logger.warning(f"Failed to auto-start Zuban LSP server: {e}")

    def _get_zuban_lsp_config(
        self, options: OptionsProtocol, config: t.Any
    ) -> tuple[int, str]:
        """Get Zuban LSP configuration values."""
        if config:
            return config.port, config.mode
        return (
            getattr(options, "zuban_lsp_port", 8677),
            getattr(options, "zuban_lsp_mode", "stdio"),
        )

    def _configure_hook_manager_lsp(self, options: OptionsProtocol) -> None:
        """Configure hook manager with LSP optimization settings."""
        # Check if LSP hooks are enabled
        enable_lsp_hooks = getattr(options, "enable_lsp_hooks", False)

        # Configure the hook manager
        hook_manager = self.phases.hook_manager
        if hasattr(hook_manager, "configure_lsp_optimization"):
            hook_manager.configure_lsp_optimization(enable_lsp_hooks)

            if enable_lsp_hooks and not getattr(options, "no_zuban_lsp", False):
                self.console.print(
                    "🔍 LSP-optimized hook execution enabled for faster type checking",
                    style="blue",
                )

    def _register_lsp_cleanup_handler(self, options: OptionsProtocol) -> None:
        """Register cleanup handler to stop LSP server when workflow completes."""
        # Get configuration to check if we should handle LSP cleanup
        config = getattr(options, "zuban_lsp", None)
        if config and not config.enabled:
            return

        if getattr(options, "no_zuban_lsp", False):
            return

        def cleanup_lsp_server() -> None:
            """Cleanup function to gracefully stop LSP server if it was auto-started."""
            try:
                from crackerjack.services.server_manager import (
                    find_zuban_lsp_processes,
                    stop_process,
                )

                lsp_processes = find_zuban_lsp_processes()
                if lsp_processes:
                    for proc in lsp_processes:
                        self.logger.debug(
                            f"Stopping auto-started Zuban LSP server (PID: {proc['pid']})"
                        )
                        stop_process(proc["pid"])

            except Exception as e:
                self.logger.debug(f"Error during LSP cleanup: {e}")

        # Register the cleanup handler with the session
        self.session.register_cleanup(cleanup_lsp_server)

    # =============================================================================
    # PHASE EXECUTION METHODS (~51 methods)
    # =============================================================================

    async def _execute_workflow_phases(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
        """Execute all workflow phases in order.

        Args:
            options: Workflow options
            workflow_id: Unique workflow identifier

        Returns:
            True if all phases succeeded, False otherwise
        """
        # Execute configuration phase
        config_success, success = await self._execute_config_phase(options, workflow_id)

        # Execute quality phase
        (
            quality_success,
            quality_phase_status,
        ) = await self._execute_quality_phase_with_events(options, workflow_id)
        success = success and quality_phase_status

        # If quality phase failed and we're in publishing mode, stop here
        if not quality_success and self._is_publishing_workflow(options):
            return False

        # Execute publishing workflow if requested
        (
            publish_requested,
            publishing_success,
        ) = await self._execute_publishing_if_requested(options, workflow_id)
        if not publishing_success:
            success = False

        # Execute commit workflow independently if requested
        commit_requested, commit_success = await self._execute_commit_if_requested(
            options, workflow_id
        )
        if not commit_success:
            success = False

        # Only fail the overall workflow if publishing was explicitly requested and failed
        if self._should_fail_on_publish_failure(publishing_success, options):
            self.console.print(
                "[red]❌ Publishing failed - overall workflow marked as failed[/red]"
            )
            return False

        return success

    async def _execute_config_phase(
        self, options: OptionsProtocol, workflow_id: str
    ) -> tuple[bool, bool]:
        """Execute the configuration phase and return success status and overall status."""
        await self._publish_event(
            WorkflowEvent.CONFIG_PHASE_STARTED,
            {"workflow_id": workflow_id},
        )

        with phase_monitor(workflow_id, "configuration"):
            config_success = self.phases.run_configuration_phase(options)
            success = config_success

        await self._publish_event(
            WorkflowEvent.CONFIG_PHASE_COMPLETED,
            {"workflow_id": workflow_id, "success": config_success},
        )

        return config_success, success

    async def _execute_quality_phase_with_events(
        self, options: OptionsProtocol, workflow_id: str
    ) -> tuple[bool, bool]:
        """Execute the quality phase with events and return success and combined status."""
        await self._publish_event(
            WorkflowEvent.QUALITY_PHASE_STARTED,
            {"workflow_id": workflow_id},
        )
        quality_success = await self._execute_quality_phase(options, workflow_id)
        success = quality_success

        await self._publish_event(
            WorkflowEvent.QUALITY_PHASE_COMPLETED,
            {"workflow_id": workflow_id, "success": quality_success},
        )

        return quality_success, success

    async def _execute_quality_phase(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
        """Execute the quality phase based on options."""
        # Use quality intelligence to make informed decisions about quality phase
        if self._quality_intelligence:
            quality_decision = await self._make_quality_intelligence_decision(options)
            self.console.print(
                f"[dim]🧠 Quality Intelligence: {quality_decision}[/dim]"
            )

        if hasattr(options, "fast") and options.fast:
            return await self._run_fast_hooks_phase_monitored(options, workflow_id)
        if hasattr(options, "fast_iteration") and options.fast_iteration:
            return await self._run_fast_hooks_phase_monitored(options, workflow_id)
        if hasattr(options, "comp") and options.comp:
            return await self._run_comprehensive_hooks_phase_monitored(
                options, workflow_id
            )
        if getattr(options, "test", False):
            return await self._execute_test_workflow(options, workflow_id)
        return await self._execute_standard_hooks_workflow_monitored(
            options, workflow_id
        )

    async def _execute_test_workflow(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
        """Execute test workflow with optional AI fixing."""
        iteration = self._start_iteration_tracking(options)

        if not await self._execute_initial_phases(options, workflow_id, iteration):
            return False

        (
            testing_passed,
            comprehensive_passed,
        ) = await self._run_main_quality_phases_async(options, workflow_id)

        return await self._handle_ai_workflow_completion(
            options, iteration, testing_passed, comprehensive_passed, workflow_id
        )

    async def _execute_initial_phases(
        self, options: OptionsProtocol, workflow_id: str, iteration: int
    ) -> bool:
        """Execute initial fast hooks phase."""
        with phase_monitor(workflow_id, "fast_hooks") as monitor:
            if not await self._run_initial_fast_hooks_async(
                options, iteration, monitor
            ):
                return False

        return self._execute_optional_cleaning_phase(options)

    def _execute_optional_cleaning_phase(self, options: OptionsProtocol) -> bool:
        """Execute code cleaning phase if requested."""
        if not getattr(options, "clean", False):
            return True

        if not self._run_code_cleaning_phase(options):
            return False

        if not self._run_post_cleaning_fast_hooks(options):
            return False

        self._mark_code_cleaning_complete()
        return True

    async def _execute_publishing_if_requested(
        self, options: OptionsProtocol, workflow_id: str
    ) -> tuple[bool, bool]:
        """Execute publishing phase if requested."""
        publish_requested = bool(
            getattr(options, "publish", False) or getattr(options, "all", False)
        )

        if publish_requested:
            await self._publish_event(
                WorkflowEvent.PUBLISH_PHASE_STARTED,
                {"workflow_id": workflow_id},
            )

        publishing_success = await self._execute_publishing_workflow(
            options, workflow_id
        )

        if publish_requested:
            await self._publish_event(
                WorkflowEvent.PUBLISH_PHASE_COMPLETED,
                {
                    "workflow_id": workflow_id,
                    "success": publishing_success,
                },
            )

        return publish_requested, publishing_success

    async def _execute_commit_if_requested(
        self, options: OptionsProtocol, workflow_id: str
    ) -> tuple[bool, bool]:
        """Execute commit phase if requested."""
        commit_requested = bool(getattr(options, "commit", False))

        if commit_requested:
            await self._publish_event(
                WorkflowEvent.COMMIT_PHASE_STARTED,
                {"workflow_id": workflow_id},
            )

        commit_success = await self._execute_commit_workflow(options, workflow_id)

        if commit_requested:
            await self._publish_event(
                WorkflowEvent.COMMIT_PHASE_COMPLETED,
                {
                    "workflow_id": workflow_id,
                    "success": commit_success,
                },
            )

        return commit_requested, commit_success

    async def _execute_publishing_workflow(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
        """Execute publishing workflow."""
        if not options.publish and not options.all:
            return True

        with phase_monitor(workflow_id, "publishing"):
            if not self.phases.run_publishing_phase(options):
                self.session.fail_task("workflow", "Publishing failed")
                return False
        return True

    async def _execute_commit_workflow(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
        """Execute commit workflow."""
        if not options.commit:
            return True

        with phase_monitor(workflow_id, "commit"):
            if not self.phases.run_commit_phase(options):
                return False
        return True

    def _is_publishing_workflow(self, options: OptionsProtocol) -> bool:
        """Check if this is a publishing workflow."""
        return bool(
            getattr(options, "publish", False) or getattr(options, "all", False)
        )

    def _should_fail_on_publish_failure(
        self, publishing_success: bool, options: OptionsProtocol
    ) -> bool:
        """Check if the overall workflow should fail due to publishing failure."""
        return not publishing_success and (
            getattr(options, "publish", False) or getattr(options, "all", False)
        )

    # Phase execution helpers

    def _start_iteration_tracking(self, options: OptionsProtocol) -> int:
        """Start tracking iteration for AI workflows."""
        iteration = 1
        if options.ai_agent and self._should_debug():
            self.debugger.log_iteration_start(iteration)
        return iteration

    async def _run_main_quality_phases_async(
        self, options: OptionsProtocol, workflow_id: str
    ) -> tuple[bool, bool]:
        """Run testing and comprehensive hooks phases in parallel."""
        testing_task = asyncio.create_task(
            self._run_testing_phase_async(options, workflow_id)
        )
        comprehensive_task = asyncio.create_task(
            self._run_comprehensive_hooks_phase_monitored(options, workflow_id)
        )

        results = await asyncio.gather(
            testing_task, comprehensive_task, return_exceptions=True
        )

        testing_result, comprehensive_result = results

        if isinstance(testing_result, Exception):
            self.logger.error(f"Testing phase failed with exception: {testing_result}")
            testing_passed = False
        else:
            testing_passed = bool(testing_result)

        if isinstance(comprehensive_result, Exception):
            self.logger.error(
                f"Comprehensive hooks failed with exception: {comprehensive_result}"
            )
            comprehensive_passed = False
        else:
            comprehensive_passed = bool(comprehensive_result)

        return testing_passed, comprehensive_passed

    async def _handle_ai_workflow_completion(
        self,
        options: OptionsProtocol,
        iteration: int,
        testing_passed: bool,
        comprehensive_passed: bool,
        workflow_id: str = "unknown",
    ) -> bool:
        """Handle workflow completion with optional AI fixing."""
        if options.ai_agent:
            return await self._handle_ai_agent_workflow(
                options, iteration, testing_passed, comprehensive_passed, workflow_id
            )

        return await self._handle_standard_workflow(
            options, iteration, testing_passed, comprehensive_passed
        )

    async def _handle_ai_agent_workflow(
        self,
        options: OptionsProtocol,
        iteration: int,
        testing_passed: bool,
        comprehensive_passed: bool,
        workflow_id: str = "unknown",
    ) -> bool:
        """Handle workflow with AI agent enabled."""
        # Import security gates methods from workflow_security_gates
        from .workflow_security_gates import WorkflowSecurityGates

        security_gates = WorkflowSecurityGates(
            console=self.console,
            logger=self.logger,
            session=self.session,
            debugger=self.debugger,
        )
        security_gates.configure(self.phases, self._execute_ai_fixing_workflow)

        if not await security_gates.process_security_gates(options):
            return False

        needs_ai_fixing = self._determine_ai_fixing_needed(
            testing_passed, comprehensive_passed, bool(options.publish or options.all)
        )

        if needs_ai_fixing:
            return await self._execute_ai_fixing_workflow(options, iteration)

        return self._finalize_ai_workflow_success(
            options, iteration, testing_passed, comprehensive_passed
        )

    async def _execute_ai_fixing_workflow(
        self, options: OptionsProtocol, iteration: int
    ) -> bool:
        """Execute AI fixing workflow."""
        # Import AI coordinator methods from workflow_ai_coordinator
        from .workflow_ai_coordinator import WorkflowAICoordinator

        ai_coordinator = WorkflowAICoordinator(
            console=self.console,
            logger=self.logger,
            pkg_path=self.pkg_path,
            debugger=self.debugger,
        )
        ai_coordinator.configure(self.session, self.phases, self._mcp_state_manager)

        success = await ai_coordinator.run_ai_agent_fixing_phase(options)
        if self._should_debug():
            self.debugger.log_iteration_end(iteration, success)
        return success

    def _finalize_ai_workflow_success(
        self,
        options: OptionsProtocol,
        iteration: int,
        testing_passed: bool,
        comprehensive_passed: bool,
    ) -> bool:
        """Finalize AI workflow when no fixing is needed."""
        publishing_requested = bool(options.publish or options.all)

        final_success = self._determine_workflow_success(
            testing_passed, comprehensive_passed, publishing_requested
        )

        self._show_partial_success_warning_if_needed(
            publishing_requested, final_success, testing_passed, comprehensive_passed
        )

        if self._should_debug():
            self.debugger.log_iteration_end(iteration, final_success)

        return final_success

    def _show_partial_success_warning_if_needed(
        self,
        publishing_requested: bool,
        final_success: bool,
        testing_passed: bool,
        comprehensive_passed: bool,
    ) -> None:
        """Show warning if workflow succeeded with partial quality."""
        should_show_warning = (
            publishing_requested
            and final_success
            and not (testing_passed and comprehensive_passed)
        )

        if should_show_warning:
            self._show_security_audit_warning()

    async def _handle_standard_workflow(
        self,
        options: OptionsProtocol,
        iteration: int,
        testing_passed: bool,
        comprehensive_passed: bool,
    ) -> bool:
        """Handle standard workflow without AI agent."""
        # Import security gates methods
        from .workflow_security_gates import WorkflowSecurityGates

        security_gates = WorkflowSecurityGates(
            console=self.console,
            logger=self.logger,
            session=self.session,
            debugger=self.debugger,
        )
        security_gates.configure(self.phases, None)

        (
            publishing_requested,
            security_blocks,
        ) = await security_gates.check_security_gates_for_publishing(options)

        if publishing_requested and security_blocks:
            return await security_gates.handle_security_gate_failure(options)

        success = self._determine_workflow_success(
            testing_passed,
            comprehensive_passed,
            publishing_requested,
        )

        if (
            publishing_requested
            and success
            and not (testing_passed and comprehensive_passed)
        ):
            self._show_security_audit_warning()
        elif publishing_requested and not success:
            self.console.print(
                "[red]❌ Quality checks failed - cannot proceed to publishing[/red]"
            )

        if not success and getattr(options, "verbose", False):
            self._show_verbose_failure_details(testing_passed, comprehensive_passed)

        if options.ai_agent and self._should_debug():
            self.debugger.log_iteration_end(iteration, success)
        return success

    def _determine_workflow_success(
        self,
        testing_passed: bool,
        comprehensive_passed: bool,
        publishing_requested: bool,
    ) -> bool:
        """Determine overall workflow success."""
        if publishing_requested:
            return testing_passed and comprehensive_passed

        return testing_passed and comprehensive_passed

    def _show_verbose_failure_details(
        self, testing_passed: bool, comprehensive_passed: bool
    ) -> None:
        """Show detailed failure information in verbose mode."""
        self.console.print(
            f"[yellow]⚠️ Quality phase results - testing_passed: {testing_passed}, comprehensive_passed: {comprehensive_passed}[/yellow]"
        )
        if not testing_passed:
            self.console.print("[yellow] → Tests reported failure[/yellow]")
        if not comprehensive_passed:
            self.console.print(
                "[yellow] → Comprehensive hooks reported failure[/yellow]"
            )

    def _determine_ai_fixing_needed(
        self,
        testing_passed: bool,
        comprehensive_passed: bool,
        publishing_requested: bool,
    ) -> bool:
        """Determine if AI fixing is needed."""
        if publishing_requested:
            return not testing_passed or not comprehensive_passed

        return not testing_passed or not comprehensive_passed

    def _show_security_audit_warning(self) -> None:
        """Show security audit warning."""
        audit_report = getattr(self, "_last_security_audit", None)

        if audit_report:
            self.console.print(
                "[yellow]⚠️ SECURITY AUDIT: Proceeding with partial quality success[/yellow]"
            )

            for warning in audit_report.security_warnings:
                if "CRITICAL" in warning:
                    self.console.print(f"[red]{warning}[/red]")
                elif "HIGH" in warning:
                    self.console.print(f"[yellow]{warning}[/yellow]")
                else:
                    self.console.print(f"[blue]{warning}[/blue]")

            if audit_report.recommendations:
                self.console.print("[bold]Security Recommendations: [/bold]")
                for rec in audit_report.recommendations[:3]:
                    self.console.print(f"[dim]{rec}[/dim]")
        else:
            self.console.print(
                "[yellow]⚠️ SECURITY AUDIT: Proceeding with partial quality success[/yellow]"
            )
            self.console.print(
                "[yellow]✅ Security-critical checks (bandit, pyright, gitleaks) have passed[/yellow]"
            )
            self.console.print(
                "[yellow]⚠️ Some non-critical quality checks failed - consider reviewing before production deployment[/yellow]"
            )

    # Individual phase execution methods

    def _run_fast_hooks_phase(self, options: OptionsProtocol) -> bool:
        """Execute fast hooks phase."""
        self._update_mcp_status("fast", "running")

        if not self.phases.run_fast_hooks_only(options):
            self.session.fail_task("workflow", "Fast hooks failed")
            self._update_mcp_status("fast", "failed")
            return False

        self._update_mcp_status("fast", "completed")
        return True

    def _run_testing_phase(self, options: OptionsProtocol) -> bool:
        """Execute testing phase."""
        self._update_mcp_status("tests", "running")

        success = self.phases.run_testing_phase(options)
        if not success:
            self.session.fail_task("workflow", "Testing failed")
            self._handle_test_failures()
            self._update_mcp_status("tests", "failed")

        else:
            self._update_mcp_status("tests", "completed")

        return success

    def _run_comprehensive_hooks_phase(self, options: OptionsProtocol) -> bool:
        """Execute comprehensive hooks phase."""
        self._update_mcp_status("comprehensive", "running")

        success = self.phases.run_comprehensive_hooks_only(options)
        if not success:
            self.session.fail_task("comprehensive_hooks", "Comprehensive hooks failed")
            self._update_mcp_status("comprehensive", "failed")

        else:
            self._update_mcp_status("comprehensive", "completed")

        return success

    def _run_code_cleaning_phase(self, options: OptionsProtocol) -> bool:
        """Execute code cleaning phase."""
        self.console.print("\n[bold blue]🧹 Running Code Cleaning Phase...[/bold blue]")

        success = self.phases.run_cleaning_phase(options)
        if success:
            self.console.print("[green]✅ Code cleaning completed successfully[/green]")
        else:
            self.console.print("[red]❌ Code cleaning failed[/red]")
            self.session.fail_task("workflow", "Code cleaning phase failed")

        return success

    def _run_post_cleaning_fast_hooks(self, options: OptionsProtocol) -> bool:
        """Run fast hooks after code cleaning as sanity check."""
        self.console.print(
            "\n[bold cyan]🔍 Running Post-Cleaning Fast Hooks Sanity Check...[/bold cyan]"
        )
        # Allow a single re-run after cleaning by resetting the session guard
        with suppress(Exception):
            # Access PhaseCoordinator instance to reset its duplicate guard
            setattr(self.phases, "_fast_hooks_started", False)
        success = self._run_fast_hooks_phase(options)
        if success:
            self.console.print("[green]✅ Post-cleaning sanity check passed[/green]")
        else:
            self.console.print("[red]❌ Post-cleaning sanity check failed[/red]")
            self.session.fail_task("workflow", "Post-cleaning fast hooks failed")

        return success

    # Async phase execution with monitoring

    async def _run_initial_fast_hooks_async(
        self, options: OptionsProtocol, iteration: int, monitor: t.Any
    ) -> bool:
        """Run initial fast hooks asynchronously."""
        monitor.record_sequential_op()
        fast_hooks_passed = self._run_fast_hooks_phase(options)
        if not fast_hooks_passed:
            if options.ai_agent and self._should_debug():
                self.debugger.log_iteration_end(iteration, False)
            return False
        return True

    async def _run_fast_hooks_phase_monitored(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
        """Run fast hooks phase with monitoring."""
        iteration = self._start_iteration_tracking(options)

        with phase_monitor(workflow_id, "fast_hooks") as monitor:
            monitor.record_sequential_op()
            # Run blocking sync method in thread to avoid blocking event loop
            fast_hooks_success = await asyncio.to_thread(
                self._run_fast_hooks_phase, options
            )

            # Delegate to AI workflow completion handler if AI agent enabled
            if options.ai_agent:
                return await self._handle_ai_workflow_completion(
                    options, iteration, fast_hooks_success, True, workflow_id
                )

            return fast_hooks_success

    async def _run_comprehensive_hooks_phase_monitored(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
        """Run comprehensive hooks phase with monitoring."""
        iteration = self._start_iteration_tracking(options)

        with phase_monitor(workflow_id, "comprehensive_hooks") as monitor:
            monitor.record_sequential_op()
            # Run blocking sync method in thread to avoid blocking event loop
            comprehensive_success = await asyncio.to_thread(
                self._run_comprehensive_hooks_phase, options
            )

            # Delegate to AI workflow completion handler if AI agent enabled
            if options.ai_agent:
                return await self._handle_ai_workflow_completion(
                    options, iteration, True, comprehensive_success, workflow_id
                )

            return comprehensive_success

    async def _run_testing_phase_async(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
        """Run testing phase asynchronously with optional coverage improvement."""
        with phase_monitor(workflow_id, "testing") as monitor:
            monitor.record_sequential_op()
            test_result = self._run_testing_phase(options)

            # Execute coverage improvement if boost_coverage is enabled and tests passed
            if test_result and getattr(options, "boost_coverage", False):
                await self._execute_coverage_improvement(options)

            return test_result

    async def _execute_coverage_improvement(self, options: OptionsProtocol) -> None:
        """Execute coverage improvement when boost_coverage is enabled."""
        try:
            from crackerjack.orchestration.coverage_improvement import (
                create_coverage_improvement_orchestrator,
            )

            coverage_orchestrator = await create_coverage_improvement_orchestrator(
                self.pkg_path
            )

            should_improve = await coverage_orchestrator.should_improve_coverage()
            if not should_improve:
                self.console.print(
                    "[dim]📈 Coverage at 100% - no improvement needed[/dim]"
                )
                return

            # Create agent context for coverage improvement
            agent_context = AgentContext(
                project_path=self.pkg_path,
            )

            result = await coverage_orchestrator.execute_coverage_improvement(
                agent_context
            )

            if result["status"] == "completed":
                # Coverage orchestrator already printed success message
                pass
            elif result["status"] == "skipped":
                self.console.print(
                    f"[dim]📈 Coverage improvement skipped: {result.get('reason', 'Unknown')}[/dim]"
                )
            else:
                # Coverage orchestrator already printed failure message
                pass

        except Exception as e:
            # Coverage orchestrator handles error display, only log for internal tracking
            self.logger.warning(f"Coverage improvement error: {e}")

    async def _execute_standard_hooks_workflow_monitored(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
        """Execute standard hooks workflow with monitoring."""
        iteration = self._start_iteration_tracking(options)

        with phase_monitor(workflow_id, "hooks") as monitor:
            self._update_hooks_status_running()

            # Run blocking sync method in thread to avoid blocking event loop
            fast_hooks_success = await asyncio.to_thread(
                self._execute_monitored_fast_hooks_phase, options, monitor
            )
            if not fast_hooks_success:
                self._handle_hooks_completion(False)
                # If AI agent is enabled and hooks failed, delegate to AI workflow completion
                if options.ai_agent:
                    return await self._handle_ai_workflow_completion(
                        options, iteration, fast_hooks_success, False, workflow_id
                    )
                return False

            # Run blocking sync method in thread to avoid blocking event loop
            cleaning_success = await asyncio.to_thread(
                self._execute_monitored_cleaning_phase, options
            )
            if not cleaning_success:
                self._handle_hooks_completion(False)
                return False

            # Run blocking sync method in thread to avoid blocking event loop
            comprehensive_success = await asyncio.to_thread(
                self._execute_monitored_comprehensive_phase, options, monitor
            )

            hooks_success = fast_hooks_success and comprehensive_success
            self._handle_hooks_completion(hooks_success)

            # Delegate to AI workflow completion handler to check if AI fixing is needed
            return await self._handle_ai_workflow_completion(
                options,
                iteration,
                fast_hooks_success,
                comprehensive_success,
                workflow_id,
            )

    def _execute_monitored_fast_hooks_phase(
        self, options: OptionsProtocol, monitor: t.Any
    ) -> bool:
        """Execute fast hooks with monitoring."""
        fast_hooks_success = self._run_fast_hooks_phase(options)
        if fast_hooks_success:
            monitor.record_sequential_op()
        return fast_hooks_success

    def _execute_monitored_cleaning_phase(self, options: OptionsProtocol) -> bool:
        """Execute cleaning phase with monitoring."""
        if not getattr(options, "clean", False):
            return True

        if not self._run_code_cleaning_phase(options):
            return False

        if not self._run_post_cleaning_fast_hooks(options):
            return False

        self._mark_code_cleaning_complete()
        return True

    def _execute_monitored_comprehensive_phase(
        self, options: OptionsProtocol, monitor: t.Any
    ) -> bool:
        """Execute comprehensive hooks with monitoring."""
        comprehensive_success = self._run_comprehensive_hooks_phase(options)
        if comprehensive_success:
            monitor.record_sequential_op()
        return comprehensive_success

    # Quality intelligence methods

    async def _make_quality_intelligence_decision(
        self, options: OptionsProtocol
    ) -> str:
        """Use quality intelligence to make informed decisions about workflow execution."""
        try:
            if not self._quality_intelligence:
                return "Quality intelligence not available"

            anomalies = await self._quality_intelligence.detect_anomalies_async()
            patterns = await self._quality_intelligence.identify_patterns_async()

            recommendations = self._build_quality_recommendations(anomalies, patterns)
            return "; ".join(recommendations)

        except Exception as e:
            return f"Quality intelligence analysis failed: {str(e)[:50]}..."

    def _build_quality_recommendations(
        self, anomalies: t.Any, patterns: t.Any
    ) -> list[str]:
        """Build quality recommendations based on anomalies and patterns."""
        recommendations = []

        if anomalies:
            recommendations.extend(self._analyze_anomalies(anomalies))

        if patterns:
            recommendations.extend(self._analyze_patterns(patterns))

        if not recommendations:
            recommendations.append("baseline quality analysis active")

        return recommendations

    def _analyze_anomalies(self, anomalies: t.Any) -> list[str]:
        """Analyze anomalies and return recommendations."""
        high_severity_anomalies = [
            a for a in anomalies if a.severity.name in ("CRITICAL", "HIGH")
        ]

        if high_severity_anomalies:
            return ["comprehensive analysis recommended due to quality anomalies"]
        return ["standard quality checks sufficient"]

    def _analyze_patterns(self, patterns: t.Any) -> list[str]:
        """Analyze patterns and return recommendations."""
        improving_patterns = [
            p for p in patterns if p.trend_direction.name == "IMPROVING"
        ]

        if improving_patterns:
            return ["quality trending upward"]
        return ["quality monitoring active"]

    # Helper methods

    def _update_mcp_status(self, stage: str, status: str) -> None:
        """Update MCP state manager status."""
        if hasattr(self, "_mcp_state_manager") and self._mcp_state_manager:
            self._mcp_state_manager.update_stage_status(stage, status)

    def _update_hooks_status_running(self) -> None:
        """Update hooks status to running."""
        if self._has_mcp_state_manager():
            self._mcp_state_manager.update_stage_status("fast", "running")
            self._mcp_state_manager.update_stage_status("comprehensive", "running")

    def _handle_hooks_completion(self, hooks_success: bool) -> None:
        """Handle hooks completion status."""
        if not hooks_success:
            self.session.fail_task("workflow", "Hooks failed")
            self._update_hooks_status_failed()
        else:
            self._update_hooks_status_completed()

    def _has_mcp_state_manager(self) -> bool:
        """Check if MCP state manager is available."""
        return hasattr(self, "_mcp_state_manager") and self._mcp_state_manager

    def _update_hooks_status_failed(self) -> None:
        """Update hooks status to failed."""
        if self._has_mcp_state_manager():
            self._mcp_state_manager.update_stage_status("fast", "failed")
            self._mcp_state_manager.update_stage_status("comprehensive", "failed")

    def _update_hooks_status_completed(self) -> None:
        """Update hooks status to completed."""
        if self._has_mcp_state_manager():
            self._mcp_state_manager.update_stage_status("fast", "completed")
            self._mcp_state_manager.update_stage_status("comprehensive", "completed")

    def _has_code_cleaning_run(self) -> bool:
        """Check if code cleaning has been run."""
        return getattr(self, "_code_cleaning_complete", False)

    def _mark_code_cleaning_complete(self) -> None:
        """Mark code cleaning as complete."""
        self._code_cleaning_complete = True

    def _handle_test_failures(self) -> None:
        """Handle test failures by logging to MCP state."""
        if not (hasattr(self, "_mcp_state_manager") and self._mcp_state_manager):
            return

        test_manager = self.phases.test_manager
        if not hasattr(test_manager, "get_test_failures"):
            return

        failures = test_manager.get_test_failures()

        if self._should_debug():
            self.debugger.log_test_failures(len(failures))

        from crackerjack.mcp.state import Issue, Priority

        for i, failure in enumerate(failures[:10]):
            issue = Issue(
                id=f"test_failure_{i}",
                type="test_failure",
                message=failure.strip(),
                file_path="tests/",
                priority=Priority.HIGH,
                stage="tests",
                auto_fixable=False,
            )
            self._mcp_state_manager.add_issue(issue)

    def _should_debug(self) -> bool:
        """Check if debug mode is enabled."""
        import os

        return os.environ.get("AI_AGENT_DEBUG", "0") == "1"

    async def _publish_event(
        self, event: WorkflowEvent, data: dict[str, t.Any]
    ) -> None:
        """Publish workflow event if event bus is available."""
        if self._event_bus:
            await self._event_bus.publish_async(event, data)
