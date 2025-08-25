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
        # Start iteration tracking for AI agent mode
        iteration = 1
        if options.ai_agent and self._should_debug():
            self.debugger.log_iteration_start(iteration)

        # Collect ALL failures before determining success
        fast_hooks_passed = self._run_fast_hooks_phase(options)
        if not fast_hooks_passed:
            if options.ai_agent and self._should_debug():
                self.debugger.log_iteration_end(iteration, False)
            return False  # Fast hooks must pass before proceeding

        # Run tests and comprehensive hooks regardless of individual failures
        # to collect ALL issues for AI agent analysis
        testing_passed = self._run_testing_phase(options)
        comprehensive_passed = self._run_comprehensive_hooks_phase(options)

        # AI agent mode: Collect failures and let agents fix them
        if options.ai_agent:
            if not testing_passed or not comprehensive_passed:
                success = await self._run_ai_agent_fixing_phase(options)
                if self._should_debug():
                    self.debugger.log_iteration_end(iteration, success)
                return success
            if self._should_debug():
                self.debugger.log_iteration_end(iteration, True)
            return True  # All phases passed, no fixes needed

        # Non-AI agent mode: All phases must pass
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
            self.session.fail_task("workflow", "Comprehensive hooks failed")
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

        if self._should_debug():
            self.debugger.log_workflow_phase(
                "ai_agent_fixing",
                "started",
                details={"ai_agent": True},
            )

        try:
            # Create AI agent context
            agent_context = AgentContext(
                project_path=self.pkg_path,
                session_id=getattr(self.session, "session_id", None),
            )

            # Initialize agent coordinator
            agent_coordinator = AgentCoordinator(agent_context)
            agent_coordinator.initialize_agents()

            # Collect issues from failures
            issues = await self._collect_issues_from_failures()

            if not issues:
                self.logger.info("No issues collected for AI agent fixing")
                self._update_mcp_status("ai_fixing", "completed")
                return True

            self.logger.info(f"AI agents will attempt to fix {len(issues)} issues")

            # Let agents handle the issues
            fix_result = await agent_coordinator.handle_issues(issues)

            success = fix_result.success
            if success:
                self.logger.info("AI agents successfully fixed all issues")
                self._update_mcp_status("ai_fixing", "completed")

                # Log fix counts for debugging
                if self._should_debug():
                    total_fixes = len(fix_result.fixes_applied)
                    # Estimate test vs hook fixes based on original issue types
                    test_fixes = len(
                        [f for f in fix_result.fixes_applied if "test" in f.lower()],
                    )
                    hook_fixes = total_fixes - test_fixes
                    self.debugger.log_test_fixes(test_fixes)
                    self.debugger.log_hook_fixes(hook_fixes)
            else:
                self.logger.warning(
                    f"AI agents could not fix all issues: {fix_result.remaining_issues}",
                )
                self._update_mcp_status("ai_fixing", "failed")

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

            return success

        except Exception as e:
            self.logger.exception(f"AI agent fixing phase failed: {e}")
            self.session.fail_task("ai_fixing", f"AI agent fixing failed: {e}")
            self._update_mcp_status("ai_fixing", "failed")

            if self._should_debug():
                self.debugger.log_workflow_phase(
                    "ai_agent_fixing",
                    "failed",
                    details={"error": str(e)},
                )

            return False

    async def _collect_issues_from_failures(self) -> list[Issue]:
        """Collect issues from test and comprehensive hook failures."""
        issues: list[Issue] = []
        test_count = 0
        hook_count = 0

        # Collect test failures
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

        # Collect hook failures from session
        if hasattr(self.session, "_failed_tasks"):
            for task_id, error_msg in self.session._failed_tasks.items():
                if task_id in ["fast_hooks", "comprehensive_hooks"]:
                    hook_count += 1
                    issue_type = (
                        IssueType.FORMATTING
                        if "fast" in task_id
                        else IssueType.TYPE_ERROR
                    )
                    issue = Issue(
                        id=f"hook_failure_{task_id}",
                        type=issue_type,
                        severity=Priority.MEDIUM,
                        message=error_msg,
                        stage=task_id.replace("_hooks", ""),
                    )
                    issues.append(issue)

        # Log failure counts for debugging
        if self._should_debug():
            self.debugger.log_test_failures(test_count)
            self.debugger.log_hook_failures(hook_count)

        return issues


class WorkflowOrchestrator:
    def __init__(
        self,
        console: Console | None = None,
        pkg_path: Path | None = None,
        dry_run: bool = False,
        web_job_id: str | None = None,
    ) -> None:
        self.console = console or Console(force_terminal=True)
        self.pkg_path = pkg_path or Path.cwd()
        self.dry_run = dry_run
        self.web_job_id = web_job_id

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
