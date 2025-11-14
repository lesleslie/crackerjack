"""AI agent coordination and fix verification for workflows.

Coordinates AI agent fixing workflow, manages fix execution, and verifies
that fixes resolve issues. Extracted from WorkflowOrchestrator to improve
modularity and testability.

This module handles:
- AI agent workflow lifecycle management
- AI fixing phase execution
- Fix result processing and verification
- Integration with EnhancedAgentCoordinator
- Re-verification of fixes (tests and hooks)
- Code cleaning preparation for AI fixing
"""

from __future__ import annotations

import typing as t
from contextlib import suppress
from pathlib import Path

from acb.console import Console
from acb.depends import Inject, depends

from crackerjack.agents.base import AgentContext, Issue
from crackerjack.agents.enhanced_coordinator import EnhancedAgentCoordinator
from crackerjack.models.protocols import (
    DebugServiceProtocol,
    LoggerProtocol,
)

if t.TYPE_CHECKING:
    from crackerjack.core.phase_coordinator import PhaseCoordinator
    from crackerjack.core.session_coordinator import SessionCoordinator
    from crackerjack.models.protocols import OptionsProtocol

    from .workflow_issue_parser import WorkflowIssueParser
    from .workflow_security_gates import WorkflowSecurityGates


class WorkflowAICoordinator:
    """Coordinates AI agent fixing and verifies fixes.

    This coordinator manages the AI agent workflow lifecycle:
    1. Determines if AI fixing is needed
    2. Prepares environment (code cleaning if needed)
    3. Collects issues from failures via WorkflowIssueParser
    4. Creates and configures EnhancedAgentCoordinator
    5. Executes AI fixes
    6. Verifies fixes by re-running quality checks
    7. Reports results and updates workflow state

    Uses protocol-based dependency injection following ACB patterns.
    Delegates issue parsing to WorkflowIssueParser and security
    validation to WorkflowSecurityGates.
    """

    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        logger: Inject[LoggerProtocol],
        debugger: Inject[DebugServiceProtocol],
        session: SessionCoordinator,
        phases: PhaseCoordinator,
        pkg_path: Path,
        issue_parser: WorkflowIssueParser,
        security_gates: WorkflowSecurityGates,
        mcp_state_manager: t.Any | None = None,
    ) -> None:
        """Initialize AI coordinator with injected dependencies.

        Args:
            console: Console for output
            logger: Logger for diagnostic messages
            debugger: Debug service for detailed diagnostics
            session: Session coordinator for workflow state
            phases: Phase coordinator for running quality checks
            pkg_path: Project root path
            issue_parser: Parser for collecting and classifying issues
            security_gates: Security gate validator
            mcp_state_manager: Optional MCP state manager
        """
        self.console = console
        self.logger = logger
        self.debugger = debugger
        self.session = session
        self.phases = phases
        self.pkg_path = pkg_path
        self.issue_parser = issue_parser
        self.security_gates = security_gates
        self._mcp_state_manager = mcp_state_manager

        # State tracking
        self._code_cleaning_complete = False

    # ===================================================================
    # Main AI Workflow Coordination
    # ===================================================================

    async def handle_ai_workflow_completion(
        self,
        options: OptionsProtocol,
        iteration: int,
        testing_passed: bool,
        comprehensive_passed: bool,
        workflow_id: str = "unknown",
    ) -> bool:
        """Handle workflow completion with optional AI fixing.

        Args:
            options: Configuration options
            iteration: Current workflow iteration
            testing_passed: Whether tests passed
            comprehensive_passed: Whether comprehensive hooks passed
            workflow_id: Workflow identifier

        Returns:
            True if workflow completed successfully
        """
        if options.ai_agent:
            return await self.handle_ai_agent_workflow(
                options, iteration, testing_passed, comprehensive_passed, workflow_id
            )

        return await self._handle_standard_workflow(
            options, iteration, testing_passed, comprehensive_passed
        )

    async def handle_ai_agent_workflow(
        self,
        options: OptionsProtocol,
        iteration: int,
        testing_passed: bool,
        comprehensive_passed: bool,
        workflow_id: str = "unknown",
    ) -> bool:
        """Handle AI agent-enabled workflow with fixing capability.

        Args:
            options: Configuration options
            iteration: Current workflow iteration
            testing_passed: Whether tests passed
            comprehensive_passed: Whether comprehensive hooks passed
            workflow_id: Workflow identifier

        Returns:
            True if workflow completed successfully with AI assistance
        """
        if not await self._process_security_gates(options):
            return False

        needs_ai_fixing = self.determine_ai_fixing_needed(
            testing_passed, comprehensive_passed, bool(options.publish or options.all)
        )

        if needs_ai_fixing:
            return await self._execute_ai_fixing_workflow(options, iteration)

        return self.finalize_ai_workflow_success(
            options, iteration, testing_passed, comprehensive_passed
        )

    async def _handle_standard_workflow(
        self,
        options: OptionsProtocol,
        iteration: int,
        testing_passed: bool,
        comprehensive_passed: bool,
    ) -> bool:
        """Handle standard workflow without AI fixing.

        Args:
            options: Configuration options
            iteration: Current workflow iteration
            testing_passed: Whether tests passed
            comprehensive_passed: Whether comprehensive hooks passed

        Returns:
            True if workflow completed successfully
        """
        publishing_requested = bool(options.publish or options.all)

        final_success = self.determine_workflow_success(
            testing_passed, comprehensive_passed, publishing_requested
        )

        if self._should_debug():
            self.debugger.log_iteration_end(iteration, final_success)

        return final_success

    async def _process_security_gates(self, options: OptionsProtocol) -> bool:
        """Process security gates for publishing workflows.

        Delegates to WorkflowSecurityGates for validation.

        Args:
            options: Configuration options

        Returns:
            True if security gates passed or AI fixed issues
        """
        publishing_requested, security_blocks = (
            self.security_gates.check_security_gates_for_publishing(options)
        )

        if not (publishing_requested and security_blocks):
            return True

        security_fix_result = await self._handle_security_gate_failure(
            options, allow_ai_fixing=True
        )
        return security_fix_result

    async def _handle_security_gate_failure(
        self, options: OptionsProtocol, allow_ai_fixing: bool = False
    ) -> bool:
        """Handle security gate failure with optional AI fixing.

        Args:
            options: Configuration options
            allow_ai_fixing: Whether to attempt AI-assisted fixing

        Returns:
            True if security issues were resolved
        """
        self.security_gates.display_security_gate_failure_message()

        if allow_ai_fixing:
            return await self._attempt_ai_assisted_security_fix(options)
        return self._handle_manual_security_fix()

    async def _attempt_ai_assisted_security_fix(self, options: OptionsProtocol) -> bool:
        """Attempt to fix security issues using AI assistance.

        Args:
            options: Configuration options

        Returns:
            True if security issues were resolved, False otherwise
        """
        self.security_gates.display_ai_fixing_messages()

        ai_fix_success = await self.run_ai_agent_fixing_phase(options)
        if ai_fix_success:
            return self.security_gates.verify_security_fix_success()

        return False

    def _handle_manual_security_fix(self) -> bool:
        """Handle security fix when AI assistance is not allowed.

        Returns:
            Always False since manual intervention is required
        """
        return self.security_gates.handle_manual_security_fix()

    async def _execute_ai_fixing_workflow(
        self, options: OptionsProtocol, iteration: int
    ) -> bool:
        """Execute the AI fixing workflow.

        Args:
            options: Configuration options
            iteration: Current workflow iteration

        Returns:
            True if AI fixing succeeded
        """
        success = await self.run_ai_agent_fixing_phase(options)
        if self._should_debug():
            self.debugger.log_iteration_end(iteration, success)
        return success

    def finalize_ai_workflow_success(
        self,
        options: OptionsProtocol,
        iteration: int,
        testing_passed: bool,
        comprehensive_passed: bool,
    ) -> bool:
        """Finalize successful AI workflow completion.

        Args:
            options: Configuration options
            iteration: Current workflow iteration
            testing_passed: Whether tests passed
            comprehensive_passed: Whether comprehensive hooks passed

        Returns:
            True if workflow is successful
        """
        publishing_requested = bool(options.publish or options.all)

        final_success = self.determine_workflow_success(
            testing_passed, comprehensive_passed, publishing_requested
        )

        self.security_gates.show_partial_success_warning_if_needed(
            publishing_requested, final_success, testing_passed, comprehensive_passed
        )

        if self._should_debug():
            self.debugger.log_iteration_end(iteration, final_success)

        return final_success

    def determine_ai_fixing_needed(
        self,
        testing_passed: bool,
        comprehensive_passed: bool,
        publishing_requested: bool,
    ) -> bool:
        """Determine if AI fixing is needed based on quality results.

        Args:
            testing_passed: Whether tests passed
            comprehensive_passed: Whether comprehensive hooks passed
            publishing_requested: Whether publishing was requested

        Returns:
            True if AI fixing should be attempted
        """
        if publishing_requested:
            return not testing_passed or not comprehensive_passed

        return not testing_passed or not comprehensive_passed

    def determine_workflow_success(
        self,
        testing_passed: bool,
        comprehensive_passed: bool,
        publishing_requested: bool,
    ) -> bool:
        """Determine overall workflow success.

        Args:
            testing_passed: Whether tests passed
            comprehensive_passed: Whether comprehensive hooks passed
            publishing_requested: Whether publishing was requested

        Returns:
            True if workflow is successful
        """
        if publishing_requested:
            return testing_passed and comprehensive_passed

        return testing_passed and comprehensive_passed

    # ===================================================================
    # AI Fixing Phase Execution
    # ===================================================================

    async def run_ai_agent_fixing_phase(self, options: OptionsProtocol) -> bool:
        """Run the AI agent fixing phase.

        Main entry point for AI-assisted issue resolution. Coordinates:
        1. Environment preparation (code cleaning if needed)
        2. Issue collection from test/hook failures
        3. Agent coordinator setup
        4. Fix execution
        5. Fix verification

        Args:
            options: Configuration options

        Returns:
            True if fixes were successfully applied and verified
        """
        self._initialize_ai_fixing_phase(options)

        try:
            self._prepare_ai_fixing_environment(options)

            agent_coordinator, issues = await self._setup_ai_fixing_workflow()

            if not issues:
                return self._handle_no_issues_found()

            return await self._execute_ai_fixes(options, agent_coordinator, issues)

        except Exception as e:
            return self._handle_fixing_phase_error(e)

    def _initialize_ai_fixing_phase(self, options: OptionsProtocol) -> None:
        """Initialize the AI fixing phase with logging and status updates.

        Args:
            options: Configuration options
        """
        self._update_mcp_status("ai_fixing", "running")
        self.logger.info("Starting AI agent fixing phase")
        # Always log this important phase start for AI consumption
        self.logger.info(
            "AI agent fixing phase started",
            ai_agent_fixing=True,
            event_type="ai_fix_init",
        )
        self._log_debug_phase_start()

    def _prepare_ai_fixing_environment(self, options: OptionsProtocol) -> None:
        """Prepare environment for AI fixing by running code cleaning if needed.

        Args:
            options: Configuration options
        """
        should_run_cleaning = (
            getattr(options, "clean", False) and not self.has_code_cleaning_run()
        )

        if not should_run_cleaning:
            return

        self.console.print(
            "\n[bold yellow]🤖 AI agents recommend running code cleaning first for better results...[/bold yellow]"
        )

        if self._run_code_cleaning_phase(options):
            self._run_post_cleaning_fast_hooks(options)
            self.mark_code_cleaning_complete()

    async def _setup_ai_fixing_workflow(
        self,
    ) -> tuple[EnhancedAgentCoordinator, list[Issue]]:
        """Setup agent coordinator and collect issues.

        Returns:
            Tuple of (agent coordinator, list of issues)
        """
        agent_coordinator = self._setup_agent_coordinator()
        issues = await self._collect_issues_from_failures()
        return agent_coordinator, issues

    async def _execute_ai_fixes(
        self,
        options: OptionsProtocol,
        agent_coordinator: EnhancedAgentCoordinator,
        issues: list[Issue],
    ) -> bool:
        """Execute AI fixes using the agent coordinator.

        Args:
            options: Configuration options
            agent_coordinator: Initialized agent coordinator
            issues: List of issues to fix

        Returns:
            True if fixes were successfully applied and verified
        """
        self.logger.info(f"AI agents will attempt to fix {len(issues)} issues")
        fix_result = await agent_coordinator.handle_issues(issues)
        return await self._process_fix_results(options, fix_result)

    def _log_debug_phase_start(self) -> None:
        """Log debug information at AI fixing phase start."""
        if self._should_debug():
            self.debugger.log_workflow_phase(
                "ai_agent_fixing",
                "started",
                details={"ai_agent": True},
            )
            # Log structured data to stderr for AI consumption
            self.logger.info(
                "AI agent fixing phase started",
                ai_agent_fixing=True,
                event_type="ai_fix_start",
            )

    def _setup_agent_coordinator(self) -> EnhancedAgentCoordinator:
        """Create and initialize the enhanced agent coordinator.

        Returns:
            Initialized EnhancedAgentCoordinator
        """
        from crackerjack.agents.enhanced_coordinator import create_enhanced_coordinator

        agent_context = AgentContext(
            project_path=self.pkg_path,
            session_id=getattr(self.session, "session_id", None),
        )

        # Use enhanced coordinator with Claude Code agent integration
        agent_coordinator = create_enhanced_coordinator(
            context=agent_context, enable_external_agents=True
        )
        agent_coordinator.initialize_agents()
        return agent_coordinator

    def _handle_no_issues_found(self) -> bool:
        """Handle case where no issues were found to fix.

        Returns:
            True (success since there are no issues)
        """
        self.logger.info("No issues collected for AI agent fixing")
        self._update_mcp_status("ai_fixing", "completed")
        return True

    async def _process_fix_results(
        self, options: OptionsProtocol, fix_result: t.Any
    ) -> bool:
        """Process the results from AI fixing.

        Args:
            options: Configuration options
            fix_result: Result object from agent coordinator

        Returns:
            True if fixes were successful and verified
        """
        verification_success = await self._verify_fixes_applied(options, fix_result)
        success = fix_result.success and verification_success

        if success:
            self._handle_successful_fixes(fix_result)
        else:
            self._handle_failed_fixes(fix_result, verification_success)

        self._log_debug_phase_completion(success, fix_result)
        return success

    def _handle_successful_fixes(self, fix_result: t.Any) -> None:
        """Handle successful fix results.

        Args:
            fix_result: Result object from agent coordinator
        """
        self.logger.info(
            "AI agents successfully fixed all issues and verification passed"
        )
        self._update_mcp_status("ai_fixing", "completed")
        self._log_fix_counts_if_debugging(fix_result)

    def _handle_failed_fixes(
        self, fix_result: t.Any, verification_success: bool
    ) -> None:
        """Handle failed fix results.

        Args:
            fix_result: Result object from agent coordinator
            verification_success: Whether verification passed
        """
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
        """Log fix counts for debugging purposes.

        Args:
            fix_result: Result object from agent coordinator
        """
        if not self._should_debug():
            return

        total_fixes = len(fix_result.fixes_applied)
        test_fixes = len(
            [f for f in fix_result.fixes_applied if "test" in f.lower()],
        )
        hook_fixes = total_fixes - test_fixes
        self.debugger.log_test_fixes(test_fixes)
        self.debugger.log_hook_fixes(hook_fixes)

        # Log structured data to stderr for AI consumption
        self.logger.info(
            "AI fixes applied",
            ai_agent_fixing=True,
            event_type="ai_fix_counts",
            total_fixes=total_fixes,
            test_fixes=test_fixes,
            hook_fixes=hook_fixes,
        )

    def _log_debug_phase_completion(self, success: bool, fix_result: t.Any) -> None:
        """Log debug information at AI fixing phase completion.

        Args:
            success: Whether the phase succeeded
            fix_result: Result object from agent coordinator
        """
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
            # Log structured data to stderr for AI consumption
            self.logger.info(
                f"AI agent fixing phase {'completed' if success else 'failed'}",
                ai_agent_fixing=True,
                event_type="ai_fix_completion",
                success=success,
                confidence=fix_result.confidence,
                fixes_applied=len(fix_result.fixes_applied),
                remaining_issues=len(fix_result.remaining_issues),
            )

    def _handle_fixing_phase_error(self, error: Exception) -> bool:
        """Handle errors during AI fixing phase.

        Args:
            error: Exception that occurred

        Returns:
            False (failure)
        """
        self.logger.exception(f"AI agent fixing phase failed: {error}")
        self.session.fail_task("ai_fixing", f"AI agent fixing failed: {error}")
        self._update_mcp_status("ai_fixing", "failed")

        if self._should_debug():
            self.debugger.log_workflow_phase(
                "ai_agent_fixing",
                "failed",
                details={"error": str(error)},
            )
            # Log structured data to stderr for AI consumption
            self.logger.error(
                "AI agent fixing phase failed",
                ai_agent_fixing=True,
                event_type="ai_fix_error",
                error=str(error),
                error_type=type(error).__name__,
            )

        return False

    # ===================================================================
    # Fix Verification
    # ===================================================================

    async def _verify_fixes_applied(
        self, options: OptionsProtocol, fix_result: t.Any
    ) -> bool:
        """Verify that AI fixes actually resolved issues by re-running checks.

        Args:
            options: Configuration options
            fix_result: Result object from agent coordinator

        Returns:
            True if verification passed
        """
        if not fix_result.fixes_applied:
            return True

        self.logger.info("Verifying AI agent fixes by re-running quality checks")

        verification_success = True

        if self._should_verify_test_fixes(fix_result.fixes_applied):
            if not await self._verify_test_fixes(options):
                verification_success = False

        if self._should_verify_hook_fixes(fix_result.fixes_applied):
            if not await self._verify_hook_fixes(options):
                verification_success = False

        self._log_verification_result(verification_success)
        return verification_success

    def _should_verify_test_fixes(self, fixes_applied: list[str]) -> bool:
        """Check if test fixes need verification.

        Args:
            fixes_applied: List of fixes that were applied

        Returns:
            True if any test-related fixes were applied
        """
        return any("test" in fix.lower() for fix in fixes_applied)

    async def _verify_test_fixes(self, options: OptionsProtocol) -> bool:
        """Verify test fixes by re-running tests.

        Args:
            options: Configuration options

        Returns:
            True if tests now pass
        """
        self.logger.info("Re-running tests to verify test fixes")
        test_success = self.phases.run_testing_phase(options)
        if not test_success:
            self.logger.warning("Test verification failed-test fixes did not work")
        return test_success

    def _should_verify_hook_fixes(self, fixes_applied: list[str]) -> bool:
        """Check if hook fixes need verification.

        Args:
            fixes_applied: List of fixes that were applied

        Returns:
            True if any hook-related fixes were applied
        """
        hook_fixes = [fix for fix in fixes_applied if self._is_hook_related_fix(fix)]
        return bool(hook_fixes)

    def _is_hook_related_fix(self, fix: str) -> bool:
        """Check if a fix is related to hooks and should trigger hook verification.

        Args:
            fix: Description of the fix

        Returns:
            True if the fix is hook-related
        """
        fix_lower = fix.lower()
        return (
            "hook" not in fix_lower or "complexity" in fix_lower or "type" in fix_lower
        )

    async def _verify_hook_fixes(self, options: OptionsProtocol) -> bool:
        """Verify hook fixes by re-running comprehensive hooks.

        Args:
            options: Configuration options

        Returns:
            True if hooks now pass
        """
        self.logger.info("Re-running comprehensive hooks to verify hook fixes")
        hook_success = self.phases.run_comprehensive_hooks_only(options)
        if not hook_success:
            self.logger.warning("Hook verification failed-hook fixes did not work")
        return hook_success

    def _log_verification_result(self, verification_success: bool) -> None:
        """Log the result of fix verification.

        Args:
            verification_success: Whether verification passed
        """
        if verification_success:
            self.logger.info("All AI agent fixes verified successfully")
        else:
            self.logger.error(
                "Verification failed-some fixes did not resolve the issues"
            )

    # ===================================================================
    # Issue Collection (Delegates to WorkflowIssueParser)
    # ===================================================================

    async def _collect_issues_from_failures(self) -> list[Issue]:
        """Collect issues from test and hook failures.

        Delegates to WorkflowIssueParser for issue collection and classification.

        Returns:
            List of collected issues
        """
        issues: list[Issue] = []

        test_issues, test_count = self.issue_parser.collect_test_failure_issues(
            self.phases
        )
        hook_issues, hook_count = self.issue_parser.collect_hook_failure_issues(
            self.phases, self.session
        )

        issues.extend(test_issues)
        issues.extend(hook_issues)

        self.issue_parser.log_failure_counts_if_debugging(
            test_count, hook_count, self._should_debug()
        )

        return issues

    # ===================================================================
    # Helper Methods
    # ===================================================================

    def _should_debug(self) -> bool:
        """Check if debug mode is enabled.

        Returns:
            True if AI_AGENT_DEBUG environment variable is set
        """
        import os

        return os.environ.get("AI_AGENT_DEBUG", "0") == "1"

    def _update_mcp_status(self, stage: str, status: str) -> None:
        """Update MCP state manager status if available.

        Args:
            stage: Stage name
            status: Status value
        """
        if hasattr(self, "_mcp_state_manager") and self._mcp_state_manager:
            self._mcp_state_manager.update_stage_status(stage, status)

    def has_code_cleaning_run(self) -> bool:
        """Check if code cleaning has already run.

        Returns:
            True if code cleaning has completed
        """
        return self._code_cleaning_complete

    def mark_code_cleaning_complete(self) -> None:
        """Mark code cleaning as complete."""
        self._code_cleaning_complete = True

    def _run_code_cleaning_phase(self, options: OptionsProtocol) -> bool:
        """Run the code cleaning phase.

        Args:
            options: Configuration options

        Returns:
            True if cleaning succeeded
        """
        self.console.print("\n[bold blue]🧹 Running Code Cleaning Phase...[/bold blue]")

        success = self.phases.run_cleaning_phase(options)
        if success:
            self.console.print("[green]✅ Code cleaning completed successfully[/green]")
        else:
            self.console.print("[red]❌ Code cleaning failed[/red]")
            self.session.fail_task("workflow", "Code cleaning phase failed")

        return success

    def _run_post_cleaning_fast_hooks(self, options: OptionsProtocol) -> bool:
        """Run fast hooks after code cleaning as sanity check.

        Args:
            options: Configuration options

        Returns:
            True if fast hooks passed
        """
        self.console.print(
            "\n[bold cyan]🔍 Running Post-Cleaning Fast Hooks Sanity Check...[/bold cyan]"
        )
        # Allow a single re-run after cleaning by resetting the session guard
        with suppress(Exception):
            # Access PhaseCoordinator instance to reset its duplicate guard
            setattr(self.phases, "_fast_hooks_started", False)

        success = self.phases.run_fast_hooks_phase(options)
        if success:
            self.console.print("[green]✅ Post-cleaning sanity check passed[/green]")
        else:
            self.console.print("[red]❌ Post-cleaning sanity check failed[/red]")
            self.session.fail_task("workflow", "Post-cleaning fast hooks failed")

        return success
