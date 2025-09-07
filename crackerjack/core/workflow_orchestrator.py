import asyncio
import time
import typing as t
from pathlib import Path

from rich.console import Console

from crackerjack.agents.base import AgentContext, Issue, IssueType, Priority
from crackerjack.agents.coordinator import AgentCoordinator
from crackerjack.models.protocols import OptionsProtocol
from crackerjack.services.debug import get_ai_agent_debugger
from crackerjack.services.logging import (
    LoggingContext,
    get_logger,
    setup_structured_logging,
)
from crackerjack.services.memory_optimizer import get_memory_optimizer, memory_optimized
from crackerjack.services.performance_cache import get_performance_cache
from crackerjack.services.performance_monitor import (
    get_performance_monitor,
    phase_monitor,
)

from .phase_coordinator import PhaseCoordinator
from .session_coordinator import SessionCoordinator


def version() -> str:
    try:
        import importlib.metadata

        return importlib.metadata.version("crackerjack")
    except Exception:
        return "unknown"


class WorkflowPipeline:
    def __init__(
        self,
        console: Console,
        pkg_path: Path,
        session: SessionCoordinator,
        phases: PhaseCoordinator,
    ) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.session = session
        self.phases = phases
        self._mcp_state_manager: t.Any = None
        self._last_security_audit: t.Any = None  # Store security audit report

        self.logger = get_logger("crackerjack.pipeline")
        self._debugger = None

        # Performance optimization services
        self._performance_monitor = get_performance_monitor()
        self._memory_optimizer = get_memory_optimizer()
        self._cache = get_performance_cache()

    @property
    def debugger(self):
        if self._debugger is None:
            self._debugger = get_ai_agent_debugger()
        return self._debugger

    def _should_debug(self) -> bool:
        import os

        return os.environ.get("AI_AGENT_DEBUG", "0") == "1"

    @memory_optimized
    async def run_complete_workflow(self, options: OptionsProtocol) -> bool:
        workflow_id = f"workflow_{int(time.time())}"

        # Start performance monitoring
        self._performance_monitor.start_workflow(workflow_id)

        # Start cache service if not already running
        await self._cache.start()

        with LoggingContext(
            "workflow_execution",
            testing=getattr(options, "test", False),
            skip_hooks=getattr(options, "skip_hooks", False),
        ):
            start_time = time.time()
            self._initialize_workflow_session(options)

            try:
                success = await self._execute_workflow_with_timing(
                    options, start_time, workflow_id
                )

                # Finalize performance monitoring
                workflow_perf = self._performance_monitor.end_workflow(
                    workflow_id, success
                )
                self.logger.info(
                    f"Workflow performance: {workflow_perf.performance_score:.1f} score, "
                    f"{workflow_perf.total_duration_seconds:.2f}s duration"
                )

                return success

            except KeyboardInterrupt:
                self._performance_monitor.end_workflow(workflow_id, False)
                return self._handle_user_interruption()

            except Exception as e:
                self._performance_monitor.end_workflow(workflow_id, False)
                return self._handle_workflow_exception(e)

            finally:
                self.session.cleanup_resources()
                # Optimize memory after workflow completion
                self._memory_optimizer.optimize_memory()
                await self._cache.stop()

    def _initialize_workflow_session(self, options: OptionsProtocol) -> None:
        self.session.initialize_session_tracking(options)
        self.session.track_task("workflow", "Complete crackerjack workflow")

        self._log_workflow_startup_debug(options)
        self._configure_session_cleanup(options)
        self._log_workflow_startup_info(options)

    def _log_workflow_startup_debug(self, options: OptionsProtocol) -> None:
        if not self._should_debug():
            return

        self.debugger.log_workflow_phase(
            "workflow_execution",
            "started",
            details={
                "testing": getattr(options, "test", False),
                "skip_hooks": getattr(options, "skip_hooks", False),
                "ai_agent": getattr(options, "ai_agent", False),
            },
        )

    def _configure_session_cleanup(self, options: OptionsProtocol) -> None:
        if hasattr(options, "cleanup"):
            self.session.set_cleanup_config(options.cleanup)

    def _log_workflow_startup_info(self, options: OptionsProtocol) -> None:
        self.logger.info(
            "Starting complete workflow execution",
            testing=getattr(options, "test", False),
            skip_hooks=getattr(options, "skip_hooks", False),
            package_path=str(self.pkg_path),
        )

    async def _execute_workflow_with_timing(
        self, options: OptionsProtocol, start_time: float, workflow_id: str
    ) -> bool:
        success = await self._execute_workflow_phases(options, workflow_id)
        self.session.finalize_session(start_time, success)

        duration = time.time() - start_time
        self._log_workflow_completion(success, duration)
        self._log_workflow_completion_debug(success, duration)

        return success

    def _log_workflow_completion(self, success: bool, duration: float) -> None:
        self.logger.info(
            "Workflow execution completed",
            success=success,
            duration_seconds=round(duration, 2),
        )

    def _log_workflow_completion_debug(self, success: bool, duration: float) -> None:
        if not self._should_debug():
            return

        self.debugger.set_workflow_success(success)
        self.debugger.log_workflow_phase(
            "workflow_execution",
            "completed" if success else "failed",
            duration=duration,
        )

        if self.debugger.enabled:
            self.debugger.print_debug_summary()

    def _handle_user_interruption(self) -> bool:
        self.console.print("Interrupted by user")
        self.session.fail_task("workflow", "Interrupted by user")
        self.logger.warning("Workflow interrupted by user")
        return False

    def _handle_workflow_exception(self, error: Exception) -> bool:
        self.console.print(f"Error: {error}")
        self.session.fail_task("workflow", f"Unexpected error: {error}")
        self.logger.exception(
            "Workflow execution failed",
            error=str(error),
            error_type=type(error).__name__,
        )
        return False

    async def _execute_workflow_phases(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
        """Execute all workflow phases with proper security gates and performance monitoring."""
        success = True

        # Configuration phase with monitoring
        with phase_monitor(workflow_id, "configuration"):
            config_success = self.phases.run_configuration_phase(options)
            success = success and config_success

        # Execute quality phase (includes testing and comprehensive checks)
        quality_success = await self._execute_quality_phase(options, workflow_id)
        if not quality_success:
            success = False
            # For publishing workflows, enforce security gates
            if self._is_publishing_workflow(options):
                return False  # Exit early - publishing requires ALL quality checks

        # Execute publishing workflow if requested
        if not await self._execute_publishing_workflow(options, workflow_id):
            success = False
            return False

        # Execute commit workflow if requested
        if not await self._execute_commit_workflow(options, workflow_id):
            success = False

        return success

    def _is_publishing_workflow(self, options: OptionsProtocol) -> bool:
        """Check if this is a publishing workflow that requires strict security gates."""
        return bool(options.publish or options.all or options.commit)

    async def _execute_publishing_workflow(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
        """Execute publishing workflow with proper error handling and monitoring."""
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
        """Execute commit workflow with proper error handling and monitoring."""
        if not options.commit:
            return True

        with phase_monitor(workflow_id, "commit"):
            if not self.phases.run_commit_phase(options):
                return False
        return True

    async def _execute_quality_phase(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
        if hasattr(options, "fast") and options.fast:
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
        iteration = self._start_iteration_tracking(options)

        # Execute initial phases (fast hooks + optional cleaning)
        if not await self._execute_initial_phases(options, workflow_id, iteration):
            return False

        # Run main quality phases
        (
            testing_passed,
            comprehensive_passed,
        ) = await self._run_main_quality_phases_async(options, workflow_id)

        # Handle workflow completion based on agent mode
        return await self._handle_workflow_completion(
            options, iteration, testing_passed, comprehensive_passed, workflow_id
        )

    async def _execute_initial_phases(
        self, options: OptionsProtocol, workflow_id: str, iteration: int
    ) -> bool:
        """Execute fast hooks and optional code cleaning phases."""
        # Fast hooks with performance monitoring
        with phase_monitor(workflow_id, "fast_hooks") as monitor:
            if not await self._run_initial_fast_hooks_async(
                options, iteration, monitor
            ):
                return False

        # Run code cleaning if enabled
        return self._execute_optional_cleaning_phase(options)

    def _execute_optional_cleaning_phase(self, options: OptionsProtocol) -> bool:
        """Execute code cleaning phase if enabled."""
        if not getattr(options, "clean", False):
            return True

        if not self._run_code_cleaning_phase(options):
            return False

        # Run fast hooks again after cleaning for sanity check
        if not self._run_post_cleaning_fast_hooks(options):
            return False

        self._mark_code_cleaning_complete()
        return True

    async def _handle_workflow_completion(
        self,
        options: OptionsProtocol,
        iteration: int,
        testing_passed: bool,
        comprehensive_passed: bool,
        workflow_id: str = "unknown",
    ) -> bool:
        """Handle workflow completion based on agent mode."""
        if options.ai_agent:
            return await self._handle_ai_agent_workflow(
                options, iteration, testing_passed, comprehensive_passed, workflow_id
            )

        return await self._handle_standard_workflow(
            options, iteration, testing_passed, comprehensive_passed
        )

    def _start_iteration_tracking(self, options: OptionsProtocol) -> int:
        iteration = 1
        if options.ai_agent and self._should_debug():
            self.debugger.log_iteration_start(iteration)
        return iteration

    def _run_initial_fast_hooks(self, options: OptionsProtocol, iteration: int) -> bool:
        fast_hooks_passed = self._run_fast_hooks_phase(options)
        if not fast_hooks_passed:
            if options.ai_agent and self._should_debug():
                self.debugger.log_iteration_end(iteration, False)
            return False
        return True

    async def _run_main_quality_phases_async(
        self, options: OptionsProtocol, workflow_id: str
    ) -> tuple[bool, bool]:
        # Run testing and comprehensive phases in parallel where possible
        testing_task = asyncio.create_task(
            self._run_testing_phase_async(options, workflow_id)
        )
        comprehensive_task = asyncio.create_task(
            self._run_comprehensive_hooks_phase_monitored(options, workflow_id)
        )

        results = await asyncio.gather(
            testing_task, comprehensive_task, return_exceptions=True
        )

        # Handle exceptions and ensure boolean types
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

    async def _handle_ai_agent_workflow(
        self,
        options: OptionsProtocol,
        iteration: int,
        testing_passed: bool,
        comprehensive_passed: bool,
        workflow_id: str = "unknown",
    ) -> bool:
        # Handle security gates first
        if not await self._process_security_gates(options):
            return False

        # Determine if AI fixing is needed
        needs_ai_fixing = self._determine_ai_fixing_needed(
            testing_passed, comprehensive_passed, bool(options.publish or options.all)
        )

        if needs_ai_fixing:
            return await self._execute_ai_fixing_workflow(options, iteration)

        # Handle success case without AI fixing
        return self._finalize_ai_workflow_success(
            options, iteration, testing_passed, comprehensive_passed
        )

    async def _process_security_gates(self, options: OptionsProtocol) -> bool:
        """Process security gates for publishing operations."""
        publishing_requested, security_blocks = (
            self._check_security_gates_for_publishing(options)
        )

        if not (publishing_requested and security_blocks):
            return True

        # Try AI fixing for security issues, then re-check
        security_fix_result = await self._handle_security_gate_failure(
            options, allow_ai_fixing=True
        )
        return security_fix_result

    async def _execute_ai_fixing_workflow(
        self, options: OptionsProtocol, iteration: int
    ) -> bool:
        """Execute AI fixing workflow and handle debugging."""
        success = await self._run_ai_agent_fixing_phase(options)
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
        """Show security audit warning for partial success in publishing workflows."""
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
        # Check security gates for publishing operations
        publishing_requested, security_blocks = (
            self._check_security_gates_for_publishing(options)
        )

        if publishing_requested and security_blocks:
            # Standard workflow cannot bypass security gates
            return await self._handle_security_gate_failure(options)

        # Determine success based on publishing requirements
        success = self._determine_workflow_success(
            testing_passed,
            comprehensive_passed,
            publishing_requested,
        )

        # Show security audit warning for partial success in publishing workflows
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

        # Show verbose failure details if requested
        if not success and getattr(options, "verbose", False):
            self._show_verbose_failure_details(testing_passed, comprehensive_passed)

        if options.ai_agent and self._should_debug():
            self.debugger.log_iteration_end(iteration, success)
        return success

    def _run_fast_hooks_phase(self, options: OptionsProtocol) -> bool:
        self._update_mcp_status("fast", "running")

        if not self.phases.run_fast_hooks_only(options):
            self.session.fail_task("workflow", "Fast hooks failed")
            self._update_mcp_status("fast", "failed")
            return False

        self._update_mcp_status("fast", "completed")
        return True

    def _run_testing_phase(self, options: OptionsProtocol) -> bool:
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
        self._update_mcp_status("comprehensive", "running")

        success = self.phases.run_comprehensive_hooks_only(options)
        if not success:
            self.session.fail_task("comprehensive_hooks", "Comprehensive hooks failed")
            self._update_mcp_status("comprehensive", "failed")

        else:
            self._update_mcp_status("comprehensive", "completed")

        return success

    def _update_mcp_status(self, stage: str, status: str) -> None:
        if hasattr(self, "_mcp_state_manager") and self._mcp_state_manager:
            self._mcp_state_manager.update_stage_status(stage, status)

    def _run_code_cleaning_phase(self, options: OptionsProtocol) -> bool:
        """Run code cleaning phase after fast hooks but before comprehensive hooks."""
        self.console.print("\n[bold blue]🧹 Running Code Cleaning Phase...[/bold blue]")

        success = self.phases.run_cleaning_phase(options)
        if success:
            self.console.print("[green]✅ Code cleaning completed successfully[/green]")
        else:
            self.console.print("[red]❌ Code cleaning failed[/red]")
            self.session.fail_task("workflow", "Code cleaning phase failed")

        return success

    def _run_post_cleaning_fast_hooks(self, options: OptionsProtocol) -> bool:
        """Run fast hooks again after code cleaning for sanity check."""
        self.console.print(
            "\n[bold cyan]🔍 Running Post-Cleaning Fast Hooks Sanity Check...[/bold cyan]"
        )

        success = self._run_fast_hooks_phase(options)
        if success:
            self.console.print("[green]✅ Post-cleaning sanity check passed[/green]")
        else:
            self.console.print("[red]❌ Post-cleaning sanity check failed[/red]")
            self.session.fail_task("workflow", "Post-cleaning fast hooks failed")

        return success

    def _has_code_cleaning_run(self) -> bool:
        """Check if code cleaning has already run in this workflow."""
        return getattr(self, "_code_cleaning_complete", False)

    def _mark_code_cleaning_complete(self) -> None:
        """Mark code cleaning as complete for this workflow."""
        self._code_cleaning_complete = True

    def _handle_test_failures(self) -> None:
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
                file_path="tests /",
                priority=Priority.HIGH,
                stage="tests",
                auto_fixable=False,
            )
            self._mcp_state_manager.add_issue(issue)

    def _execute_standard_hooks_workflow(self, options: OptionsProtocol) -> bool:
        self._update_hooks_status_running()

        # Run fast hooks first
        fast_hooks_success = self._run_fast_hooks_phase(options)
        if not fast_hooks_success:
            self._handle_hooks_completion(False)
            return False

        # Run code cleaning after fast hooks but before comprehensive hooks
        if getattr(options, "clean", False):
            if not self._run_code_cleaning_phase(options):
                self._handle_hooks_completion(False)
                return False
            # Run fast hooks again after cleaning for sanity check
            if not self._run_post_cleaning_fast_hooks(options):
                self._handle_hooks_completion(False)
                return False
            self._mark_code_cleaning_complete()

        # Run comprehensive hooks
        comprehensive_success = self._run_comprehensive_hooks_phase(options)

        hooks_success = fast_hooks_success and comprehensive_success
        self._handle_hooks_completion(hooks_success)

        return hooks_success

    def _update_hooks_status_running(self) -> None:
        if self._has_mcp_state_manager():
            self._mcp_state_manager.update_stage_status("fast", "running")
            self._mcp_state_manager.update_stage_status("comprehensive", "running")

    def _handle_hooks_completion(self, hooks_success: bool) -> None:
        if not hooks_success:
            self.session.fail_task("workflow", "Hooks failed")
            self._update_hooks_status_failed()
        else:
            self._update_hooks_status_completed()

    def _has_mcp_state_manager(self) -> bool:
        return hasattr(self, "_mcp_state_manager") and self._mcp_state_manager

    def _update_hooks_status_failed(self) -> None:
        if self._has_mcp_state_manager():
            self._mcp_state_manager.update_stage_status("fast", "failed")
            self._mcp_state_manager.update_stage_status("comprehensive", "failed")

    def _update_hooks_status_completed(self) -> None:
        if self._has_mcp_state_manager():
            self._mcp_state_manager.update_stage_status("fast", "completed")
            self._mcp_state_manager.update_stage_status("comprehensive", "completed")

    async def _run_ai_agent_fixing_phase(self, options: OptionsProtocol) -> bool:
        self._initialize_ai_fixing_phase(options)

        try:
            # Prepare environment for AI agents
            self._prepare_ai_fixing_environment(options)

            # Setup coordinator and collect issues
            agent_coordinator, issues = await self._setup_ai_fixing_workflow()

            if not issues:
                return self._handle_no_issues_found()

            # Execute AI fixing
            return await self._execute_ai_fixes(options, agent_coordinator, issues)

        except Exception as e:
            return self._handle_fixing_phase_error(e)

    def _initialize_ai_fixing_phase(self, options: OptionsProtocol) -> None:
        """Initialize the AI fixing phase with status updates and logging."""
        self._update_mcp_status("ai_fixing", "running")
        self.logger.info("Starting AI agent fixing phase")
        self._log_debug_phase_start()

    def _prepare_ai_fixing_environment(self, options: OptionsProtocol) -> None:
        """Prepare the environment for AI agents by running optional code cleaning."""
        should_run_cleaning = (
            getattr(options, "clean", False) and not self._has_code_cleaning_run()
        )

        if not should_run_cleaning:
            return

        self.console.print(
            "\n[bold yellow]🤖 AI agents recommend running code cleaning first for better results...[/bold yellow]"
        )

        if self._run_code_cleaning_phase(options):
            # Run fast hooks sanity check after cleaning
            self._run_post_cleaning_fast_hooks(options)
            self._mark_code_cleaning_complete()

    async def _setup_ai_fixing_workflow(
        self,
    ) -> tuple[AgentCoordinator, list[t.Any]]:
        """Setup agent coordinator and collect issues to fix."""
        agent_coordinator = self._setup_agent_coordinator()
        issues = await self._collect_issues_from_failures()
        return agent_coordinator, issues

    async def _execute_ai_fixes(
        self,
        options: OptionsProtocol,
        agent_coordinator: AgentCoordinator,
        issues: list[t.Any],
    ) -> bool:
        """Execute AI fixes and process results."""
        self.logger.info(f"AI agents will attempt to fix {len(issues)} issues")
        fix_result = await agent_coordinator.handle_issues(issues)
        return await self._process_fix_results(options, fix_result)

    def _log_debug_phase_start(self) -> None:
        if self._should_debug():
            self.debugger.log_workflow_phase(
                "ai_agent_fixing",
                "started",
                details={"ai_agent": True},
            )

    def _setup_agent_coordinator(self) -> AgentCoordinator:
        from crackerjack.agents.coordinator import AgentCoordinator

        agent_context = AgentContext(
            project_path=self.pkg_path,
            session_id=getattr(self.session, "session_id", None),
        )

        agent_coordinator = AgentCoordinator(agent_context)
        agent_coordinator.initialize_agents()
        return agent_coordinator

    def _handle_no_issues_found(self) -> bool:
        self.logger.info("No issues collected for AI agent fixing")
        self._update_mcp_status("ai_fixing", "completed")
        return True

    async def _process_fix_results(
        self, options: OptionsProtocol, fix_result: t.Any
    ) -> bool:
        verification_success = await self._verify_fixes_applied(options, fix_result)
        success = fix_result.success and verification_success

        if success:
            self._handle_successful_fixes(fix_result)
        else:
            self._handle_failed_fixes(fix_result, verification_success)

        self._log_debug_phase_completion(success, fix_result)
        return success

    def _handle_successful_fixes(self, fix_result: t.Any) -> None:
        self.logger.info(
            "AI agents successfully fixed all issues and verification passed"
        )
        self._update_mcp_status("ai_fixing", "completed")
        self._log_fix_counts_if_debugging(fix_result)

    def _handle_failed_fixes(
        self, fix_result: t.Any, verification_success: bool
    ) -> None:
        if not verification_success:
            self.logger.warning(
                "AI agent fixes did not pass verification-issues still exist"
            )
        else:
            self.logger.warning(
                f"AI agents could not fix all issues: {fix_result.remaining_issues}",
            )
        self._update_mcp_status("ai_fixing", "failed")

    def _log_fix_counts_if_debugging(self, fix_result: t.Any) -> None:
        if not self._should_debug():
            return

        total_fixes = len(fix_result.fixes_applied)
        test_fixes = len(
            [f for f in fix_result.fixes_applied if "test" in f.lower()],
        )
        hook_fixes = total_fixes - test_fixes
        self.debugger.log_test_fixes(test_fixes)
        self.debugger.log_hook_fixes(hook_fixes)

    def _log_debug_phase_completion(self, success: bool, fix_result: t.Any) -> None:
        if self._should_debug():
            self.debugger.log_workflow_phase(
                "ai_agent_fixing",
                "completed" if success else "failed",
                details={
                    "confidence": fix_result.confidence,
                    "fixes_applied": len(fix_result.fixes_applied),
                    "remaining_issues": len(fix_result.remaining_issues),
                },
            )

    def _handle_fixing_phase_error(self, error: Exception) -> bool:
        self.logger.exception(f"AI agent fixing phase failed: {error}")
        self.session.fail_task("ai_fixing", f"AI agent fixing failed: {error}")
        self._update_mcp_status("ai_fixing", "failed")

        if self._should_debug():
            self.debugger.log_workflow_phase(
                "ai_agent_fixing",
                "failed",
                details={"error": str(error)},
            )

        return False

    async def _verify_fixes_applied(
        self, options: OptionsProtocol, fix_result: t.Any
    ) -> bool:
        if not fix_result.fixes_applied:
            return True

        self.logger.info("Verifying AI agent fixes by re-running quality checks")

        verification_success = True

        # Verify test fixes
        if self._should_verify_test_fixes(fix_result.fixes_applied):
            if not await self._verify_test_fixes(options):
                verification_success = False

        # Verify hook fixes
        if self._should_verify_hook_fixes(fix_result.fixes_applied):
            if not await self._verify_hook_fixes(options):
                verification_success = False

        self._log_verification_result(verification_success)
        return verification_success

    def _should_verify_test_fixes(self, fixes_applied: list[str]) -> bool:
        """Check if test fixes need verification."""
        return any("test" in fix.lower() for fix in fixes_applied)

    async def _verify_test_fixes(self, options: OptionsProtocol) -> bool:
        """Verify test fixes by re-running tests."""
        self.logger.info("Re-running tests to verify test fixes")
        test_success = self.phases.run_testing_phase(options)
        if not test_success:
            self.logger.warning("Test verification failed-test fixes did not work")
        return test_success

    def _should_verify_hook_fixes(self, fixes_applied: list[str]) -> bool:
        """Check if hook fixes need verification."""
        hook_fixes = [
            f
            for f in fixes_applied
            if "hook" not in f.lower()
            or "complexity" in f.lower()
            or "type" in f.lower()
        ]
        return bool(hook_fixes)

    async def _verify_hook_fixes(self, options: OptionsProtocol) -> bool:
        """Verify hook fixes by re-running comprehensive hooks."""
        self.logger.info("Re-running comprehensive hooks to verify hook fixes")
        hook_success = self.phases.run_comprehensive_hooks_only(options)
        if not hook_success:
            self.logger.warning("Hook verification failed-hook fixes did not work")
        return hook_success

    def _log_verification_result(self, verification_success: bool) -> None:
        """Log the final verification result."""
        if verification_success:
            self.logger.info("All AI agent fixes verified successfully")
        else:
            self.logger.error(
                "Verification failed-some fixes did not resolve the issues"
            )

    async def _collect_issues_from_failures(self) -> list[Issue]:
        issues: list[Issue] = []

        test_issues, test_count = self._collect_test_failure_issues()
        hook_issues, hook_count = self._collect_hook_failure_issues()

        issues.extend(test_issues)
        issues.extend(hook_issues)

        self._log_failure_counts_if_debugging(test_count, hook_count)

        return issues

    def _collect_test_failure_issues(self) -> tuple[list[Issue], int]:
        issues: list[Issue] = []
        test_count = 0

        if hasattr(self.phases, "test_manager") and hasattr(
            self.phases.test_manager,
            "get_test_failures",
        ):
            test_failures = self.phases.test_manager.get_test_failures()
            test_count = len(test_failures)
            for i, failure in enumerate(
                test_failures[:20],
            ):
                issue = Issue(
                    id=f"test_failure_{i}",
                    type=IssueType.TEST_FAILURE,
                    severity=Priority.HIGH,
                    message=failure.strip(),
                    stage="tests",
                )
                issues.append(issue)

        return issues, test_count

    def _collect_hook_failure_issues(self) -> tuple[list[Issue], int]:
        issues: list[Issue] = []
        hook_count = 0

        try:
            hook_results = self.phases.hook_manager.run_comprehensive_hooks()
            issues, hook_count = self._process_hook_results(hook_results)
        except Exception:
            issues, hook_count = self._fallback_to_session_tracker()

        return issues, hook_count

    def _process_hook_results(self, hook_results: t.Any) -> tuple[list[Issue], int]:
        issues: list[Issue] = []
        hook_count = 0

        for result in hook_results:
            if not self._is_hook_result_failed(result):
                continue

            hook_count += 1
            result_issues = self._extract_issues_from_hook_result(result)
            issues.extend(result_issues)

        return issues, hook_count

    def _is_hook_result_failed(self, result: t.Any) -> bool:
        return result.status in ("failed", "error", "timeout")

    def _extract_issues_from_hook_result(self, result: t.Any) -> list[Issue]:
        if result.issues_found:
            return self._create_specific_issues_from_hook_result(result)
        return [self._create_generic_issue_from_hook_result(result)]

    def _create_specific_issues_from_hook_result(self, result: t.Any) -> list[Issue]:
        issues: list[Issue] = []
        hook_context = f"{result.name}: "

        for issue_text in result.issues_found:
            parsed_issues = self._parse_issues_for_agents([hook_context + issue_text])
            issues.extend(parsed_issues)

        return issues

    def _create_generic_issue_from_hook_result(self, result: t.Any) -> Issue:
        issue_type = self._determine_hook_issue_type(result.name)
        return Issue(
            id=f"hook_failure_{result.name}",
            type=issue_type,
            severity=Priority.MEDIUM,
            message=f"Hook {result.name} failed with no specific details",
            stage="comprehensive",
        )

    def _determine_hook_issue_type(self, hook_name: str) -> IssueType:
        formatting_hooks = {
            "trailing-whitespace",
            "end-of-file-fixer",
            "ruff-format",
            "ruff-check",
        }

        if hook_name == "validate-regex-patterns":
            return IssueType.REGEX_VALIDATION

        return (
            IssueType.FORMATTING
            if hook_name in formatting_hooks
            else IssueType.TYPE_ERROR
        )

    def _fallback_to_session_tracker(self) -> tuple[list[Issue], int]:
        issues: list[Issue] = []
        hook_count = 0

        if not self.session.session_tracker:
            return issues, hook_count

        for task_id, task_data in self.session.session_tracker.tasks.items():
            if self._is_failed_hook_task(task_data, task_id):
                hook_count += 1
                hook_issues = self._process_hook_failure(task_id, task_data)
                issues.extend(hook_issues)

        return issues, hook_count

    def _is_failed_hook_task(self, task_data: t.Any, task_id: str) -> bool:
        return task_data.status == "failed" and task_id in (
            "fast_hooks",
            "comprehensive_hooks",
        )

    def _process_hook_failure(self, task_id: str, task_data: t.Any) -> list[Issue]:
        error_msg = getattr(task_data, "error_message", "Unknown error")
        specific_issues = self._parse_hook_error_details(task_id, error_msg)

        if specific_issues:
            return specific_issues

        return [self._create_generic_hook_issue(task_id, error_msg)]

    def _create_generic_hook_issue(self, task_id: str, error_msg: str) -> Issue:
        issue_type = IssueType.FORMATTING if "fast" in task_id else IssueType.TYPE_ERROR
        return Issue(
            id=f"hook_failure_{task_id}",
            type=issue_type,
            severity=Priority.MEDIUM,
            message=error_msg,
            stage=task_id.replace("_hooks", ""),
        )

    def _parse_hook_error_details(self, task_id: str, error_msg: str) -> list[Issue]:
        """Parse hook error details and create specific issues."""
        issues: list[Issue] = []

        if task_id == "comprehensive_hooks":
            issues.extend(self._parse_comprehensive_hook_errors(error_msg))
        elif task_id == "fast_hooks":
            issues.append(self._create_fast_hook_issue())

        return issues

    def _parse_comprehensive_hook_errors(self, error_msg: str) -> list[Issue]:
        """Parse comprehensive hook error messages and create specific issues."""
        issues: list[Issue] = []
        error_lower = error_msg.lower()

        # Check each error type
        complexity_issue = self._check_complexity_error(error_lower)
        if complexity_issue:
            issues.append(complexity_issue)

        type_error_issue = self._check_type_error(error_lower)
        if type_error_issue:
            issues.append(type_error_issue)

        security_issue = self._check_security_error(error_lower)
        if security_issue:
            issues.append(security_issue)

        performance_issue = self._check_performance_error(error_lower)
        if performance_issue:
            issues.append(performance_issue)

        dead_code_issue = self._check_dead_code_error(error_lower)
        if dead_code_issue:
            issues.append(dead_code_issue)

        regex_issue = self._check_regex_validation_error(error_lower)
        if regex_issue:
            issues.append(regex_issue)

        return issues

    def _check_complexity_error(self, error_lower: str) -> Issue | None:
        """Check for complexity errors and create issue if found."""
        if "complexipy" in error_lower or "c901" in error_lower:
            return Issue(
                id="complexity_violation",
                type=IssueType.COMPLEXITY,
                severity=Priority.HIGH,
                message="Code complexity violation detected",
                stage="comprehensive",
            )
        return None

    def _check_type_error(self, error_lower: str) -> Issue | None:
        """Check for type errors and create issue if found."""
        if "pyright" in error_lower:
            return Issue(
                id="pyright_type_error",
                type=IssueType.TYPE_ERROR,
                severity=Priority.HIGH,
                message="Type checking errors detected by pyright",
                stage="comprehensive",
            )
        return None

    def _check_security_error(self, error_lower: str) -> Issue | None:
        """Check for security errors and create issue if found."""
        if "bandit" in error_lower:
            return Issue(
                id="bandit_security_issue",
                type=IssueType.SECURITY,
                severity=Priority.HIGH,
                message="Security vulnerabilities detected by bandit",
                stage="comprehensive",
            )
        return None

    def _check_performance_error(self, error_lower: str) -> Issue | None:
        """Check for performance errors and create issue if found."""
        if "refurb" in error_lower:
            return Issue(
                id="refurb_quality_issue",
                type=IssueType.PERFORMANCE,
                severity=Priority.MEDIUM,
                message="Code quality issues detected by refurb",
                stage="comprehensive",
            )
        return None

    def _check_dead_code_error(self, error_lower: str) -> Issue | None:
        """Check for dead code errors and create issue if found."""
        if "vulture" in error_lower:
            return Issue(
                id="vulture_dead_code",
                type=IssueType.DEAD_CODE,
                severity=Priority.MEDIUM,
                message="Dead code detected by vulture",
                stage="comprehensive",
            )
        return None

    def _check_regex_validation_error(self, error_lower: str) -> Issue | None:
        """Check for regex validation errors and create issue if found."""
        regex_keywords = ("raw regex", "regex pattern", r"\g<", "replacement")
        if "validate-regex-patterns" in error_lower or any(
            keyword in error_lower for keyword in regex_keywords
        ):
            return Issue(
                id="regex_validation_failure",
                type=IssueType.REGEX_VALIDATION,
                severity=Priority.HIGH,
                message="Unsafe regex patterns detected by validate-regex-patterns",
                stage="fast",
            )
        return None

    def _create_fast_hook_issue(self) -> Issue:
        """Create an issue for fast hook errors."""
        return Issue(
            id="fast_hooks_formatting",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Code formatting issues detected",
            stage="fast",
        )

    def _parse_issues_for_agents(self, issue_strings: list[str]) -> list[Issue]:
        issues: list[Issue] = []

        for i, issue_str in enumerate(issue_strings):
            issue_type, priority = self._classify_issue(issue_str)

            issue = Issue(
                id=f"parsed_issue_{i}",
                type=issue_type,
                severity=priority,
                message=issue_str.strip(),
                stage="comprehensive",
            )
            issues.append(issue)

        return issues

    def _classify_issue(self, issue_str: str) -> tuple[IssueType, Priority]:
        """Classify an issue string to determine its type and priority."""
        issue_lower = issue_str.lower()

        # Check high-priority issues first
        if self._is_type_error(issue_lower):
            return IssueType.TYPE_ERROR, Priority.HIGH
        if self._is_security_issue(issue_lower):
            return IssueType.SECURITY, Priority.HIGH
        if self._is_complexity_issue(issue_lower):
            return IssueType.COMPLEXITY, Priority.HIGH
        if self._is_regex_validation_issue(issue_lower):
            return IssueType.REGEX_VALIDATION, Priority.HIGH

        # Check medium-priority issues
        if self._is_dead_code_issue(issue_lower):
            return IssueType.DEAD_CODE, Priority.MEDIUM
        if self._is_performance_issue(issue_lower):
            return IssueType.PERFORMANCE, Priority.MEDIUM
        if self._is_import_error(issue_lower):
            return IssueType.IMPORT_ERROR, Priority.MEDIUM

        # Default to formatting issue
        return IssueType.FORMATTING, Priority.MEDIUM

    def _is_type_error(self, issue_lower: str) -> bool:
        """Check if issue is related to type errors."""
        return any(
            keyword in issue_lower for keyword in ("type", "annotation", "pyright")
        )

    def _is_security_issue(self, issue_lower: str) -> bool:
        """Check if issue is related to security."""
        return any(
            keyword in issue_lower for keyword in ("security", "bandit", "hardcoded")
        )

    def _is_complexity_issue(self, issue_lower: str) -> bool:
        """Check if issue is related to code complexity."""
        return any(
            keyword in issue_lower
            for keyword in ("complexity", "complexipy", "c901", "too complex")
        )

    def _is_regex_validation_issue(self, issue_lower: str) -> bool:
        """Check if issue is related to regex validation."""
        return any(
            keyword in issue_lower
            for keyword in (
                "regex",
                "pattern",
                "validate-regex-patterns",
                r"\g<",
                "replacement",
            )
        )

    def _is_dead_code_issue(self, issue_lower: str) -> bool:
        """Check if issue is related to dead code."""
        return any(keyword in issue_lower for keyword in ("unused", "dead", "vulture"))

    def _is_performance_issue(self, issue_lower: str) -> bool:
        """Check if issue is related to performance."""
        return any(
            keyword in issue_lower for keyword in ("performance", "refurb", "furb")
        )

    def _is_import_error(self, issue_lower: str) -> bool:
        """Check if issue is related to import errors."""
        return any(keyword in issue_lower for keyword in ("import", "creosote"))

    def _log_failure_counts_if_debugging(
        self, test_count: int, hook_count: int
    ) -> None:
        if self._should_debug():
            self.debugger.log_test_failures(test_count)
            self.debugger.log_hook_failures(hook_count)

    def _check_security_gates_for_publishing(
        self, options: OptionsProtocol
    ) -> tuple[bool, bool]:
        """Check if publishing is requested and if security gates block it.

        Returns:
            tuple[bool, bool]: (publishing_requested, security_blocks_publishing)
        """
        publishing_requested = bool(options.publish or options.all or options.commit)

        if not publishing_requested:
            return False, False

        # Check security gates for publishing operations
        try:
            security_blocks_publishing = self._check_security_critical_failures()
            return publishing_requested, security_blocks_publishing
        except Exception as e:
            # Fail securely if security check fails
            self.logger.warning(f"Security check failed: {e} - blocking publishing")
            self.console.print(
                "[red]🔒 SECURITY CHECK FAILED: Unable to verify security status - publishing BLOCKED[/red]"
            )
            # Return True for security_blocks to fail securely
            return publishing_requested, True

    async def _handle_security_gate_failure(
        self, options: OptionsProtocol, allow_ai_fixing: bool = False
    ) -> bool:
        """Handle security gate failures with optional AI fixing.

        Args:
            options: Workflow options
            allow_ai_fixing: Whether AI fixing is allowed for security issues

        Returns:
            bool: True if security issues resolved, False if still blocked
        """
        self.console.print(
            "[red]🔒 SECURITY GATE: Critical security checks failed[/red]"
        )

        if allow_ai_fixing:
            self.console.print(
                "[red]Security-critical hooks (bandit, pyright, gitleaks) must pass before publishing[/red]"
            )
            self.console.print(
                "[yellow]🤖 Attempting AI-assisted security issue resolution...[/yellow]"
            )

            # Try AI fixing for security issues
            ai_fix_success = await self._run_ai_agent_fixing_phase(options)
            if ai_fix_success:
                # Re-check security after AI fixing
                try:
                    security_still_blocks = self._check_security_critical_failures()
                    if not security_still_blocks:
                        self.console.print(
                            "[green]✅ AI agents resolved security issues - publishing allowed[/green]"
                        )
                        return True
                    else:
                        self.console.print(
                            "[red]🔒 Security issues persist after AI fixing - publishing still BLOCKED[/red]"
                        )
                        return False
                except Exception as e:
                    self.logger.warning(
                        f"Security re-check failed: {e} - blocking publishing"
                    )
                    return False
            return False
        else:
            # Standard workflow cannot bypass security gates
            self.console.print(
                "[red]Security-critical hooks (bandit, pyright, gitleaks) must pass before publishing[/red]"
            )
            return False

    def _determine_ai_fixing_needed(
        self,
        testing_passed: bool,
        comprehensive_passed: bool,
        publishing_requested: bool,
    ) -> bool:
        """Determine if AI fixing is needed based on test results and publishing requirements."""
        if publishing_requested:
            # For publish/commit workflows, trigger AI fixing if either fails (since both must pass)
            return not testing_passed or not comprehensive_passed
        # For regular workflows, trigger AI fixing if either fails
        return not testing_passed or not comprehensive_passed

    def _determine_workflow_success(
        self,
        testing_passed: bool,
        comprehensive_passed: bool,
        publishing_requested: bool,
    ) -> bool:
        """Determine workflow success based on test results and workflow type."""
        if publishing_requested:
            # For publishing workflows, ALL quality checks (tests AND comprehensive hooks) must pass
            return testing_passed and comprehensive_passed
        # For regular workflows, both must pass as well
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

    def _check_security_critical_failures(self) -> bool:
        """Check if any security-critical hooks have failed.

        Returns:
            True if security-critical hooks failed and block publishing
        """
        try:
            from crackerjack.security.audit import SecurityAuditor

            auditor = SecurityAuditor()

            # Get hook results - we need to be careful not to re-run hooks
            # Instead, check the session tracker for recent failures
            fast_results = self._get_recent_fast_hook_results()
            comprehensive_results = self._get_recent_comprehensive_hook_results()

            # Generate security audit report
            audit_report = auditor.audit_hook_results(
                fast_results, comprehensive_results
            )

            # Store audit report for later use
            self._last_security_audit = audit_report

            # Block publishing if critical failures exist
            return audit_report.has_critical_failures

        except Exception as e:
            # Fail securely - if we can't determine security status, block publishing
            self.logger.warning(f"Security audit failed: {e} - failing securely")
            # Re-raise the exception so it can be caught by the calling method
            raise

    def _get_recent_fast_hook_results(self) -> list[t.Any]:
        """Get recent fast hook results from session tracker."""
        # Try to get results from session tracker
        results = self._extract_hook_results_from_session("fast_hooks")

        # If no results from session, create mock failed results for critical hooks
        if not results:
            results = self._create_mock_hook_results(["gitleaks"])

        return results

    def _extract_hook_results_from_session(self, hook_type: str) -> list[t.Any]:
        """Extract hook results from session tracker for given hook type."""
        results = []

        session_tracker = self._get_session_tracker()
        if not session_tracker:
            return results

        for task_id, task_data in session_tracker.tasks.items():
            if task_id == hook_type and hasattr(task_data, "hook_results"):
                if task_data.hook_results:
                    results.extend(task_data.hook_results)

        return results

    def _get_session_tracker(self) -> t.Any | None:
        """Get session tracker if available."""
        return (
            getattr(self.session, "session_tracker", None)
            if hasattr(self.session, "session_tracker")
            else None
        )

    def _create_mock_hook_results(self, critical_hooks: list[str]) -> list[t.Any]:
        """Create mock failed results for critical hooks to fail securely."""
        results = []

        for hook_name in critical_hooks:
            mock_result = self._create_mock_hook_result(hook_name)
            results.append(mock_result)

        return results

    def _create_mock_hook_result(self, hook_name: str) -> t.Any:
        """Create a mock result that appears to have failed for security purposes."""
        return type(
            "MockResult",
            (),
            {
                "name": hook_name,
                "status": "unknown",  # Unknown status = fail securely
                "output": "Unable to determine hook status",
            },
        )()

    def _get_recent_comprehensive_hook_results(self) -> list[t.Any]:
        """Get recent comprehensive hook results from session tracker."""
        # Try to get results from session tracker
        results = self._extract_hook_results_from_session("comprehensive_hooks")

        # If no results from session, create mock failed results for critical hooks
        if not results:
            results = self._create_mock_hook_results(["bandit", "pyright"])

        return results

    def _is_security_critical_failure(self, result: t.Any) -> bool:
        """Check if a hook result represents a security-critical failure."""

        # List of security-critical hook names (fail-safe approach)
        security_critical_hooks = {
            "bandit",  # Security vulnerability scanning
            "pyright",  # Type safety prevents security holes
            "gitleaks",  # Secret detection
        }

        hook_name = getattr(result, "name", "").lower()
        is_failed = getattr(result, "status", "unknown") in (
            "failed",
            "error",
            "timeout",
        )

        return hook_name in security_critical_hooks and is_failed

    def _show_security_audit_warning(self) -> None:
        """Show security audit warning when proceeding with partial success."""
        # Use stored audit report if available
        audit_report = getattr(self, "_last_security_audit", None)

        if audit_report:
            self.console.print(
                "[yellow]⚠️ SECURITY AUDIT: Proceeding with partial quality success[/yellow]"
            )

            # Show security status
            for warning in audit_report.security_warnings:
                if "CRITICAL" in warning:
                    # This shouldn't happen if we're showing warnings, but fail-safe
                    self.console.print(f"[red]{warning}[/red]")
                elif "HIGH" in warning:
                    self.console.print(f"[yellow]{warning}[/yellow]")
                else:
                    self.console.print(f"[blue]{warning}[/blue]")

            # Show recommendations
            if audit_report.recommendations:
                self.console.print("[bold]Security Recommendations:[/bold]")
                for rec in audit_report.recommendations[:3]:  # Show top 3
                    self.console.print(f"[dim]{rec}[/dim]")
        else:
            # Fallback if no audit report available
            self.console.print(
                "[yellow]⚠️ SECURITY AUDIT: Proceeding with partial quality success[/yellow]"
            )
            self.console.print(
                "[yellow]✅ Security-critical checks (bandit, pyright, gitleaks) have passed[/yellow]"
            )
            self.console.print(
                "[yellow]⚠️ Some non-critical quality checks failed - consider reviewing before production deployment[/yellow]"
            )

    # Performance-optimized async methods
    async def _run_initial_fast_hooks_async(
        self, options: OptionsProtocol, iteration: int, monitor: t.Any
    ) -> bool:
        """Run initial fast hooks asynchronously with monitoring."""
        monitor.record_sequential_op()  # Fast hooks run sequentially for safety
        fast_hooks_passed = self._run_fast_hooks_phase(options)
        if not fast_hooks_passed:
            if options.ai_agent and self._should_debug():
                self.debugger.log_iteration_end(iteration, False)
            return False
        return True

    async def _run_fast_hooks_phase_monitored(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
        """Run fast hooks phase with performance monitoring."""
        with phase_monitor(workflow_id, "fast_hooks") as monitor:
            monitor.record_sequential_op()
            return self._run_fast_hooks_phase(options)

    async def _run_comprehensive_hooks_phase_monitored(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
        """Run comprehensive hooks phase with performance monitoring."""
        with phase_monitor(workflow_id, "comprehensive_hooks") as monitor:
            monitor.record_sequential_op()
            return self._run_comprehensive_hooks_phase(options)

    async def _run_testing_phase_async(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
        """Run testing phase asynchronously with monitoring."""
        with phase_monitor(workflow_id, "testing") as monitor:
            monitor.record_sequential_op()
            return self._run_testing_phase(options)

    async def _execute_standard_hooks_workflow_monitored(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
        """Execute standard hooks workflow with performance monitoring."""
        with phase_monitor(workflow_id, "hooks") as monitor:
            self._update_hooks_status_running()

            # Execute fast hooks phase
            fast_hooks_success = self._execute_monitored_fast_hooks_phase(
                options, monitor
            )
            if not fast_hooks_success:
                self._handle_hooks_completion(False)
                return False

            # Execute optional cleaning phase
            if not self._execute_monitored_cleaning_phase(options):
                self._handle_hooks_completion(False)
                return False

            # Execute comprehensive hooks phase
            comprehensive_success = self._execute_monitored_comprehensive_phase(
                options, monitor
            )

            # Complete workflow
            hooks_success = fast_hooks_success and comprehensive_success
            self._handle_hooks_completion(hooks_success)
            return hooks_success

    def _execute_monitored_fast_hooks_phase(
        self, options: OptionsProtocol, monitor: t.Any
    ) -> bool:
        """Execute fast hooks phase with monitoring."""
        fast_hooks_success = self._run_fast_hooks_phase(options)
        if fast_hooks_success:
            monitor.record_sequential_op()
        return fast_hooks_success

    def _execute_monitored_cleaning_phase(self, options: OptionsProtocol) -> bool:
        """Execute optional code cleaning phase."""
        if not getattr(options, "clean", False):
            return True

        if not self._run_code_cleaning_phase(options):
            return False

        # Run fast hooks again after cleaning for sanity check
        if not self._run_post_cleaning_fast_hooks(options):
            return False

        self._mark_code_cleaning_complete()
        return True

    def _execute_monitored_comprehensive_phase(
        self, options: OptionsProtocol, monitor: t.Any
    ) -> bool:
        """Execute comprehensive hooks phase with monitoring."""
        comprehensive_success = self._run_comprehensive_hooks_phase(options)
        if comprehensive_success:
            monitor.record_sequential_op()
        return comprehensive_success


class WorkflowOrchestrator:
    def __init__(
        self,
        console: Console | None = None,
        pkg_path: Path | None = None,
        dry_run: bool = False,
        web_job_id: str | None = None,
        verbose: bool = False,
        debug: bool = False,
    ) -> None:
        self.console = console or Console(force_terminal=True)
        self.pkg_path = pkg_path or Path.cwd()
        self.dry_run = dry_run
        self.web_job_id = web_job_id
        self.verbose = verbose
        self.debug = debug

        from crackerjack.models.protocols import (
            ConfigMergeServiceProtocol,
            FileSystemInterface,
            GitInterface,
            HookManager,
            PublishManager,
            TestManagerProtocol,
        )

        # Initialize logging first so container creation respects log levels
        self._initialize_logging()

        self.logger = get_logger("crackerjack.orchestrator")

        from .enhanced_container import create_enhanced_container

        self.container = create_enhanced_container(
            console=self.console,
            pkg_path=self.pkg_path,
            dry_run=self.dry_run,
            verbose=self.verbose,
        )

        self.session = SessionCoordinator(self.console, self.pkg_path, self.web_job_id)
        self.phases = PhaseCoordinator(
            console=self.console,
            pkg_path=self.pkg_path,
            session=self.session,
            filesystem=self.container.get(FileSystemInterface),
            git_service=self.container.get(GitInterface),
            hook_manager=self.container.get(HookManager),
            test_manager=self.container.get(TestManagerProtocol),
            publish_manager=self.container.get(PublishManager),
            config_merge_service=self.container.get(ConfigMergeServiceProtocol),
        )

        self.pipeline = WorkflowPipeline(
            console=self.console,
            pkg_path=self.pkg_path,
            session=self.session,
            phases=self.phases,
        )

    def _initialize_logging(self) -> None:
        from crackerjack.services.log_manager import get_log_manager

        log_manager = get_log_manager()
        session_id = getattr(self, "web_job_id", None) or str(int(time.time()))[:8]
        debug_log_file = log_manager.create_debug_log_file(session_id)

        # Set log level based on debug flag only - verbose should not enable DEBUG logs
        log_level = "DEBUG" if self.debug else "INFO"
        setup_structured_logging(
            level=log_level, json_output=False, log_file=debug_log_file
        )

        # Use a temporary logger for the initialization message
        temp_logger = get_logger("crackerjack.orchestrator.init")
        temp_logger.debug(
            "Structured logging initialized",
            log_file=str(debug_log_file),
            log_directory=str(log_manager.log_dir),
            package_path=str(self.pkg_path),
            dry_run=self.dry_run,
        )

    def _initialize_session_tracking(self, options: OptionsProtocol) -> None:
        self.session.initialize_session_tracking(options)

    def _track_task(self, task_id: str, task_name: str) -> None:
        self.session.track_task(task_id, task_name)

    def _complete_task(self, task_id: str, details: str | None = None) -> None:
        self.session.complete_task(task_id, details)

    def _fail_task(self, task_id: str, error: str) -> None:
        self.session.fail_task(task_id, error)

    def run_cleaning_phase(self, options: OptionsProtocol) -> bool:
        return self.phases.run_cleaning_phase(options)

    def run_fast_hooks_only(self, options: OptionsProtocol) -> bool:
        return self.phases.run_fast_hooks_only(options)

    def run_comprehensive_hooks_only(self, options: OptionsProtocol) -> bool:
        return self.phases.run_comprehensive_hooks_only(options)

    def run_hooks_phase(self, options: OptionsProtocol) -> bool:
        return self.phases.run_hooks_phase(options)

    def run_testing_phase(self, options: OptionsProtocol) -> bool:
        return self.phases.run_testing_phase(options)

    def run_publishing_phase(self, options: OptionsProtocol) -> bool:
        return self.phases.run_publishing_phase(options)

    def run_commit_phase(self, options: OptionsProtocol) -> bool:
        return self.phases.run_commit_phase(options)

    def run_configuration_phase(self, options: OptionsProtocol) -> bool:
        return self.phases.run_configuration_phase(options)

    async def run_complete_workflow(self, options: OptionsProtocol) -> bool:
        return await self.pipeline.run_complete_workflow(options)

    def _cleanup_resources(self) -> None:
        self.session.cleanup_resources()

    def _register_cleanup(self, cleanup_handler: t.Callable[[], None]) -> None:
        self.session.register_cleanup(cleanup_handler)

    def _track_lock_file(self, lock_file_path: Path) -> None:
        self.session.track_lock_file(lock_file_path)

    def _get_version(self) -> str:
        try:
            return version()
        except Exception:
            return "unknown"

    async def process(self, options: OptionsProtocol) -> bool:
        self.session.start_session("process_workflow")

        try:
            result = await self.run_complete_workflow(options)
            self.session.end_session(success=result)
            return result
        except Exception:
            self.session.end_session(success=False)
            return False
