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

        self.logger = get_logger("crackerjack.pipeline")
        self._debugger = None

    @property
    def debugger(self):
        if self._debugger is None:
            self._debugger = get_ai_agent_debugger()
        return self._debugger

    def _should_debug(self) -> bool:
        import os

        return os.environ.get("AI_AGENT_DEBUG", "0") == "1"

    async def run_complete_workflow(self, options: OptionsProtocol) -> bool:
        with LoggingContext(
            "workflow_execution",
            testing=getattr(options, "testing", False),
            skip_hooks=getattr(options, "skip_hooks", False),
        ):
            start_time = time.time()
            self.session.initialize_session_tracking(options)
            self.session.track_task("workflow", "Complete crackerjack workflow")

            if self._should_debug():
                self.debugger.log_workflow_phase(
                    "workflow_execution",
                    "started",
                    details={
                        "testing": getattr(options, "testing", False),
                        "skip_hooks": getattr(options, "skip_hooks", False),
                        "ai_agent": getattr(options, "ai_agent", False),
                    },
                )

            if hasattr(options, "cleanup"):
                self.session.set_cleanup_config(options.cleanup)

            self.logger.info(
                "Starting complete workflow execution",
                testing=getattr(options, "testing", False),
                skip_hooks=getattr(options, "skip_hooks", False),
                package_path=str(self.pkg_path),
            )

            try:
                success = await self._execute_workflow_phases(options)
                self.session.finalize_session(start_time, success)

                duration = time.time() - start_time
                self.logger.info(
                    "Workflow execution completed",
                    success=success,
                    duration_seconds=round(duration, 2),
                )

                if self._should_debug():
                    # Set final workflow success status
                    self.debugger.set_workflow_success(success)

                    self.debugger.log_workflow_phase(
                        "workflow_execution",
                        "completed" if success else "failed",
                        duration=duration,
                    )
                    if self.debugger.enabled:
                        self.debugger.print_debug_summary()

                return success

            except KeyboardInterrupt:
                self.console.print("Interrupted by user")
                self.session.fail_task("workflow", "Interrupted by user")
                self.logger.warning("Workflow interrupted by user")
                return False

            except Exception as e:
                self.console.print(f"Error: {e}")
                self.session.fail_task("workflow", f"Unexpected error: {e}")
                self.logger.exception(
                    "Workflow execution failed",
                    error=str(e),
                    error_type=type(e).__name__,
                )
                return False

            finally:
                self.session.cleanup_resources()

    async def _execute_workflow_phases(self, options: OptionsProtocol) -> bool:
        success = True
        self.phases.run_configuration_phase(options)
        if not self.phases.run_cleaning_phase(options):
            success = False
            self.session.fail_task("workflow", "Cleaning phase failed")
            return False
        if not await self._execute_quality_phase(options):
            success = False
            return False
        if not self.phases.run_publishing_phase(options):
            success = False
            self.session.fail_task("workflow", "Publishing failed")
            return False
        if not self.phases.run_commit_phase(options):
            success = False

        return success

    async def _execute_quality_phase(self, options: OptionsProtocol) -> bool:
        if hasattr(options, "fast") and options.fast:
            return self._run_fast_hooks_phase(options)
        if hasattr(options, "comp") and options.comp:
            return self._run_comprehensive_hooks_phase(options)
        if options.test:
            return await self._execute_test_workflow(options)
        return self._execute_standard_hooks_workflow(options)

    async def _execute_test_workflow(self, options: OptionsProtocol) -> bool:
        iteration = self._start_iteration_tracking(options)

        if not self._run_initial_fast_hooks(options, iteration):
            return False

        testing_passed, comprehensive_passed = self._run_main_quality_phases(options)

        if options.ai_agent:
            return await self._handle_ai_agent_workflow(
                options, iteration, testing_passed, comprehensive_passed
            )

        return self._handle_standard_workflow(
            options, iteration, testing_passed, comprehensive_passed
        )

    def _start_iteration_tracking(self, options: OptionsProtocol) -> int:
        """Start iteration tracking for AI agent mode."""
        iteration = 1
        if options.ai_agent and self._should_debug():
            self.debugger.log_iteration_start(iteration)
        return iteration

    def _run_initial_fast_hooks(self, options: OptionsProtocol, iteration: int) -> bool:
        """Run initial fast hooks phase and handle failure."""
        fast_hooks_passed = self._run_fast_hooks_phase(options)
        if not fast_hooks_passed:
            if options.ai_agent and self._should_debug():
                self.debugger.log_iteration_end(iteration, False)
            return False  # Fast hooks must pass before proceeding
        return True

    def _run_main_quality_phases(self, options: OptionsProtocol) -> tuple[bool, bool]:
        """Run tests and comprehensive hooks to collect ALL issues."""
        testing_passed = self._run_testing_phase(options)
        comprehensive_passed = self._run_comprehensive_hooks_phase(options)
        return testing_passed, comprehensive_passed

    async def _handle_ai_agent_workflow(
        self,
        options: OptionsProtocol,
        iteration: int,
        testing_passed: bool,
        comprehensive_passed: bool,
    ) -> bool:
        """Handle AI agent workflow with failure collection and fixing."""
        if not testing_passed or not comprehensive_passed:
            success = await self._run_ai_agent_fixing_phase(options)
            if self._should_debug():
                self.debugger.log_iteration_end(iteration, success)
            return success

        if self._should_debug():
            self.debugger.log_iteration_end(iteration, True)
        return True  # All phases passed, no fixes needed

    def _handle_standard_workflow(
        self,
        options: OptionsProtocol,
        iteration: int,
        testing_passed: bool,
        comprehensive_passed: bool,
    ) -> bool:
        """Handle standard workflow where all phases must pass."""
        success = testing_passed and comprehensive_passed
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
            # In AI agent mode, continue to collect more failures
            # In non-AI mode, this will be handled by caller
        else:
            self._update_mcp_status("tests", "completed")

        return success

    def _run_comprehensive_hooks_phase(self, options: OptionsProtocol) -> bool:
        self._update_mcp_status("comprehensive", "running")

        success = self.phases.run_comprehensive_hooks_only(options)
        if not success:
            self.session.fail_task("comprehensive_hooks", "Comprehensive hooks failed")
            self._update_mcp_status("comprehensive", "failed")
            # In AI agent mode, continue to collect more failures
            # In non-AI mode, this will be handled by caller
        else:
            self._update_mcp_status("comprehensive", "completed")

        return success

    def _update_mcp_status(self, stage: str, status: str) -> None:
        if hasattr(self, "_mcp_state_manager") and self._mcp_state_manager:
            self._mcp_state_manager.update_stage_status(stage, status)

        self.session.update_stage(stage, status)

    def _handle_test_failures(self) -> None:
        if not (hasattr(self, "_mcp_state_manager") and self._mcp_state_manager):
            return

        test_manager = self.phases.test_manager
        if not hasattr(test_manager, "get_test_failures"):
            return

        failures = test_manager.get_test_failures()

        # Log test failure count for debugging
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

    def _execute_standard_hooks_workflow(self, options: OptionsProtocol) -> bool:
        """Execute standard hooks workflow with proper state management."""
        self._update_hooks_status_running()

        hooks_success = self.phases.run_hooks_phase(options)
        self._handle_hooks_completion(hooks_success)

        return hooks_success

    def _update_hooks_status_running(self) -> None:
        """Update MCP state to running for hook phases."""
        if self._has_mcp_state_manager():
            self._mcp_state_manager.update_stage_status("fast", "running")
            self._mcp_state_manager.update_stage_status("comprehensive", "running")

    def _handle_hooks_completion(self, hooks_success: bool) -> None:
        """Handle hooks completion with appropriate status updates."""
        if not hooks_success:
            self.session.fail_task("workflow", "Hooks failed")
            self._update_hooks_status_failed()
        else:
            self._update_hooks_status_completed()

    def _has_mcp_state_manager(self) -> bool:
        """Check if MCP state manager is available."""
        return hasattr(self, "_mcp_state_manager") and self._mcp_state_manager

    def _update_hooks_status_failed(self) -> None:
        """Update MCP state to failed for hook phases."""
        if self._has_mcp_state_manager():
            self._mcp_state_manager.update_stage_status("fast", "failed")
            self._mcp_state_manager.update_stage_status("comprehensive", "failed")

    def _update_hooks_status_completed(self) -> None:
        """Update MCP state to completed for hook phases."""
        if self._has_mcp_state_manager():
            self._mcp_state_manager.update_stage_status("fast", "completed")
            self._mcp_state_manager.update_stage_status("comprehensive", "completed")

    async def _run_ai_agent_fixing_phase(self, options: OptionsProtocol) -> bool:
        """Run AI agent fixing phase to analyze and fix collected failures."""
        self._update_mcp_status("ai_fixing", "running")
        self.logger.info("Starting AI agent fixing phase")
        self._log_debug_phase_start()

        try:
            agent_coordinator = self._setup_agent_coordinator()
            issues = await self._collect_issues_from_failures()

            if not issues:
                return self._handle_no_issues_found()

            self.logger.info(f"AI agents will attempt to fix {len(issues)} issues")
            fix_result = await agent_coordinator.handle_issues(issues)

            return await self._process_fix_results(options, fix_result)

        except Exception as e:
            return self._handle_fixing_phase_error(e)

    def _log_debug_phase_start(self) -> None:
        """Log debug information for phase start."""
        if self._should_debug():
            self.debugger.log_workflow_phase(
                "ai_agent_fixing",
                "started",
                details={"ai_agent": True},
            )

    def _setup_agent_coordinator(self) -> AgentCoordinator:
        """Set up agent coordinator with proper context."""
        from crackerjack.agents.coordinator import AgentCoordinator

        agent_context = AgentContext(
            project_path=self.pkg_path,
            session_id=getattr(self.session, "session_id", None),
        )

        agent_coordinator = AgentCoordinator(agent_context)
        agent_coordinator.initialize_agents()
        return agent_coordinator

    def _handle_no_issues_found(self) -> bool:
        """Handle case when no issues are collected."""
        self.logger.info("No issues collected for AI agent fixing")
        self._update_mcp_status("ai_fixing", "completed")
        return True

    async def _process_fix_results(
        self, options: OptionsProtocol, fix_result: t.Any
    ) -> bool:
        """Process fix results and verify success."""
        verification_success = await self._verify_fixes_applied(options, fix_result)
        success = fix_result.success and verification_success

        if success:
            self._handle_successful_fixes(fix_result)
        else:
            self._handle_failed_fixes(fix_result, verification_success)

        self._log_debug_phase_completion(success, fix_result)
        return success

    def _handle_successful_fixes(self, fix_result: t.Any) -> None:
        """Handle successful fix results."""
        self.logger.info(
            "AI agents successfully fixed all issues and verification passed"
        )
        self._update_mcp_status("ai_fixing", "completed")
        self._log_fix_counts_if_debugging(fix_result)

    def _handle_failed_fixes(
        self, fix_result: t.Any, verification_success: bool
    ) -> None:
        """Handle failed fix results."""
        if not verification_success:
            self.logger.warning(
                "AI agent fixes did not pass verification - issues still exist"
            )
        else:
            self.logger.warning(
                f"AI agents could not fix all issues: {fix_result.remaining_issues}",
            )
        self._update_mcp_status("ai_fixing", "failed")

    def _log_fix_counts_if_debugging(self, fix_result: t.Any) -> None:
        """Log fix counts for debugging if debug mode is enabled."""
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
        """Log debug information for phase completion."""
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
        """Handle errors during the fixing phase."""
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
        """Verify that AI agent fixes actually resolved the issues by re-running checks."""
        if not fix_result.fixes_applied:
            return True  # No fixes were applied, nothing to verify

        self.logger.info("Verifying AI agent fixes by re-running quality checks")

        # Re-run the phases that previously failed to verify fixes
        verification_success = True

        # Check if we need to re-run tests
        if any("test" in fix.lower() for fix in fix_result.fixes_applied):
            self.logger.info("Re-running tests to verify test fixes")
            test_success = self.phases.run_testing_phase(options)
            if not test_success:
                self.logger.warning(
                    "Test verification failed - test fixes did not work"
                )
                verification_success = False

        # Check if we need to re-run comprehensive hooks
        hook_fixes = [
            f
            for f in fix_result.fixes_applied
            if "hook" not in f.lower()
            or "complexity" in f.lower()
            or "type" in f.lower()
        ]
        if hook_fixes:
            self.logger.info("Re-running comprehensive hooks to verify hook fixes")
            hook_success = self.phases.run_comprehensive_hooks_only(options)
            if not hook_success:
                self.logger.warning(
                    "Hook verification failed - hook fixes did not work"
                )
                verification_success = False

        if verification_success:
            self.logger.info("All AI agent fixes verified successfully")
        else:
            self.logger.error(
                "Verification failed - some fixes did not resolve the issues"
            )

        return verification_success

    async def _collect_issues_from_failures(self) -> list[Issue]:
        """Collect issues from test and comprehensive hook failures."""
        issues: list[Issue] = []

        test_issues, test_count = self._collect_test_failure_issues()
        hook_issues, hook_count = self._collect_hook_failure_issues()

        issues.extend(test_issues)
        issues.extend(hook_issues)

        self._log_failure_counts_if_debugging(test_count, hook_count)

        return issues

    def _collect_test_failure_issues(self) -> tuple[list[Issue], int]:
        """Collect test failure issues and return count."""
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
            ):  # Limit to prevent overload
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
        """Collect hook failure issues and return count."""
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
        """Check if a task is a failed hook task."""
        return task_data.status == "failed" and task_id in (
            "fast_hooks",
            "comprehensive_hooks",
        )

    def _process_hook_failure(self, task_id: str, task_data: t.Any) -> list[Issue]:
        """Process a single hook failure and return corresponding issues."""
        error_msg = getattr(task_data, "error_message", "Unknown error")
        specific_issues = self._parse_hook_error_details(task_id, error_msg)

        if specific_issues:
            return specific_issues

        return [self._create_generic_hook_issue(task_id, error_msg)]

    def _create_generic_hook_issue(self, task_id: str, error_msg: str) -> Issue:
        """Create a generic issue for unspecific hook failures."""
        issue_type = IssueType.FORMATTING if "fast" in task_id else IssueType.TYPE_ERROR
        return Issue(
            id=f"hook_failure_{task_id}",
            type=issue_type,
            severity=Priority.MEDIUM,
            message=error_msg,
            stage=task_id.replace("_hooks", ""),
        )

    def _parse_hook_error_details(self, task_id: str, error_msg: str) -> list[Issue]:
        """Parse specific hook failure details to create targeted issues."""
        issues: list[Issue] = []

        # For comprehensive hooks, parse specific tool failures
        if task_id == "comprehensive_hooks":
            # Check for complexipy failures (complexity violations)
            if "complexipy" in error_msg.lower():
                issues.append(
                    Issue(
                        id="complexipy_violation",
                        type=IssueType.COMPLEXITY,
                        severity=Priority.HIGH,
                        message="Code complexity violation detected by complexipy",
                        stage="comprehensive",
                    )
                )

            # Check for pyright failures (type errors)
            if "pyright" in error_msg.lower():
                issues.append(
                    Issue(
                        id="pyright_type_error",
                        type=IssueType.TYPE_ERROR,
                        severity=Priority.HIGH,
                        message="Type checking errors detected by pyright",
                        stage="comprehensive",
                    )
                )

            # Check for bandit failures (security issues)
            if "bandit" in error_msg.lower():
                issues.append(
                    Issue(
                        id="bandit_security_issue",
                        type=IssueType.SECURITY,
                        severity=Priority.HIGH,
                        message="Security vulnerabilities detected by bandit",
                        stage="comprehensive",
                    )
                )

            # Check for refurb failures (code quality issues)
            if "refurb" in error_msg.lower():
                issues.append(
                    Issue(
                        id="refurb_quality_issue",
                        type=IssueType.PERFORMANCE,  # Use PERFORMANCE as closest match for refurb issues
                        severity=Priority.MEDIUM,
                        message="Code quality issues detected by refurb",
                        stage="comprehensive",
                    )
                )

            # Check for vulture failures (dead code)
            if "vulture" in error_msg.lower():
                issues.append(
                    Issue(
                        id="vulture_dead_code",
                        type=IssueType.DEAD_CODE,
                        severity=Priority.MEDIUM,
                        message="Dead code detected by vulture",
                        stage="comprehensive",
                    )
                )

        elif task_id == "fast_hooks":
            # Fast hooks are typically formatting issues
            issues.append(
                Issue(
                    id="fast_hooks_formatting",
                    type=IssueType.FORMATTING,
                    severity=Priority.LOW,
                    message="Code formatting issues detected",
                    stage="fast",
                )
            )

        return issues

    def _log_failure_counts_if_debugging(
        self, test_count: int, hook_count: int
    ) -> None:
        """Log failure counts if debugging is enabled."""
        if self._should_debug():
            self.debugger.log_test_failures(test_count)
            self.debugger.log_hook_failures(hook_count)


class WorkflowOrchestrator:
    def __init__(
        self,
        console: Console | None = None,
        pkg_path: Path | None = None,
        dry_run: bool = False,
        web_job_id: str | None = None,
        verbose: bool = False,
    ) -> None:
        self.console = console or Console(force_terminal=True)
        self.pkg_path = pkg_path or Path.cwd()
        self.dry_run = dry_run
        self.web_job_id = web_job_id
        self.verbose = verbose

        from crackerjack.models.protocols import (
            FileSystemInterface,
            GitInterface,
            HookManager,
            PublishManager,
            TestManagerProtocol,
        )

        from .container import create_container

        self.container = create_container(
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
        )

        self.pipeline = WorkflowPipeline(
            console=self.console,
            pkg_path=self.pkg_path,
            session=self.session,
            phases=self.phases,
        )

        self.logger = get_logger("crackerjack.orchestrator")

        self._initialize_logging()

    def _initialize_logging(self) -> None:
        from crackerjack.services.log_manager import get_log_manager

        log_manager = get_log_manager()
        session_id = getattr(self, "web_job_id", None) or str(int(time.time()))[:8]
        debug_log_file = log_manager.create_debug_log_file(session_id)

        setup_structured_logging(log_file=debug_log_file)

        self.logger.info(
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
