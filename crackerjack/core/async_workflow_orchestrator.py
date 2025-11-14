import asyncio
import time
import typing as t
from pathlib import Path

from acb.depends import Inject, depends
from acb.logger import Logger
from rich.console import Console

from crackerjack.agents.base import FixResult, Issue, IssueType, Priority
from crackerjack.models.protocols import OptionsProtocol

from .phase_coordinator import PhaseCoordinator
from .session_coordinator import SessionCoordinator
from .timeout_manager import TimeoutStrategy, get_timeout_manager


class AsyncWorkflowPipeline:
    @depends.inject
    def __init__(
        self,
        logger: Inject[Logger],
        console: Inject[Console],
        pkg_path: Path,
        session: SessionCoordinator,
        phases: PhaseCoordinator,
    ) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.session = session
        self.phases = phases
        self.logger = logger
        self.timeout_manager = get_timeout_manager()
        self._active_tasks: list[asyncio.Task[t.Any]] = []
        self.resource_context: t.Any | None = None

    async def run_complete_workflow_async(self, options: OptionsProtocol) -> bool:
        start_time = time.time()
        self.session.initialize_session_tracking(options)
        self.session.track_task("workflow", "Complete async crackerjack workflow")

        try:
            async with self.timeout_manager.timeout_context(
                "complete_workflow", strategy=TimeoutStrategy.GRACEFUL_DEGRADATION
            ):
                if hasattr(options, "ai_agent") and options.ai_agent:
                    success = await self._execute_ai_agent_workflow_async(options)
                else:
                    success = await self._execute_workflow_phases_async(options)
                self.session.finalize_session(start_time, success)
                return success
        except KeyboardInterrupt:
            self.console.print("Interrupted by user")
            self.session.fail_task("workflow", "Interrupted by user")
            return False
        except Exception as e:
            self.console.print(f"Error: {e}")
            self.session.fail_task("workflow", f"Unexpected error: {e}")
            return False
        finally:
            self.session.cleanup_resources()

    async def _execute_workflow_phases_async(self, options: OptionsProtocol) -> bool:
        success = True

        self.phases.run_configuration_phase(options)  # type: ignore[arg-type]

        if not await self._execute_cleaning_phase_async(options):
            success = False

            self.session.fail_task("workflow", "Cleaning phase failed")
            return False

        if not await self._execute_quality_phase_async(options):
            success = False

            return False

        if not self.phases.run_publishing_phase(options):  # type: ignore[arg-type]
            success = False
            self.session.fail_task("workflow", "Publishing failed")
            return False

        if not self.phases.run_commit_phase(options):  # type: ignore[arg-type]
            success = False

        return success

    async def _cleanup_active_tasks(self) -> None:
        if not self._active_tasks:
            return

        self.logger.info(f"Cleaning up {len(self._active_tasks)} active tasks")

        for task in self._active_tasks:
            if not task.done():
                task.cancel()

        if self._active_tasks:
            try:
                await asyncio.wait_for(
                    asyncio.gather(*self._active_tasks, return_exceptions=True),
                    timeout=30.0,
                )
            except TimeoutError:
                self.logger.warning("Timeout waiting for task cleanup")

        self._active_tasks.clear()

    async def _execute_cleaning_phase_async(self, options: OptionsProtocol) -> bool:
        if not options.clean:
            return True

        result = await self.timeout_manager.with_timeout(
            "file_operations",
            asyncio.to_thread(self.phases.run_cleaning_phase, options),  # type: ignore[arg-type]
            strategy=TimeoutStrategy.RETRY_WITH_BACKOFF,
        )
        return bool(result)  # type: ignore[return-value]

    async def _execute_quality_phase_async(self, options: OptionsProtocol) -> bool:
        if hasattr(options, "fast") and options.fast:
            return await self._run_fast_hooks_async(options)
        if hasattr(options, "comp") and options.comp:
            return await self._run_comprehensive_hooks_async(options)
        print(f"DEBUG: options.test = {options.test}")
        if options.test:
            return await self._execute_test_workflow_async(options)
        return await self._execute_standard_hooks_workflow_async(options)

    async def _execute_test_workflow_async(self, options: OptionsProtocol) -> bool:
        overall_success = True

        if not await self._run_fast_hooks_async(options):
            overall_success = False
            self.session.fail_task("workflow", "Fast hooks failed")
            return False

        try:
            test_task, hooks_task = self._create_parallel_tasks(options)
            done, pending = await self._execute_parallel_tasks(test_task, hooks_task)

            await self._cleanup_pending_tasks(pending)

            test_success, hooks_success = await self._process_task_results(
                done, test_task, hooks_task
            )

            return self._validate_workflow_results(
                test_success, hooks_success, overall_success
            )

        except Exception as e:
            self.logger.error(f"Test workflow execution error: {e}")
            self.session.fail_task("workflow", f"Test workflow error: {e}")
            return False

    def _create_parallel_tasks(
        self, options: OptionsProtocol
    ) -> tuple[asyncio.Task[bool], asyncio.Task[bool]]:
        test_task = asyncio.create_task(
            self.timeout_manager.with_timeout(
                "test_execution",
                self._run_testing_phase_async(options),
                strategy=TimeoutStrategy.GRACEFUL_DEGRADATION,
            )
        )
        hooks_task = asyncio.create_task(
            self.timeout_manager.with_timeout(
                "comprehensive_hooks",
                self._run_comprehensive_hooks_async(options),
                strategy=TimeoutStrategy.GRACEFUL_DEGRADATION,
            )
        )
        return test_task, hooks_task

    async def _execute_parallel_tasks(
        self, test_task: asyncio.Task[bool], hooks_task: asyncio.Task[bool]
    ) -> tuple[set[asyncio.Task[bool]], set[asyncio.Task[bool]]]:
        combined_timeout = (
            self.timeout_manager.get_timeout("test_execution")
            + self.timeout_manager.get_timeout("comprehensive_hooks")
            + 60
        )

        done, pending = await asyncio.wait(
            [test_task, hooks_task],
            timeout=combined_timeout,
            return_when=asyncio.ALL_COMPLETED,
        )

        return done, pending

    async def _cleanup_pending_tasks(self, pending: set[asyncio.Task[t.Any]]) -> None:
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _process_task_results(
        self,
        done: set[asyncio.Task[bool]],
        test_task: asyncio.Task[bool],
        hooks_task: asyncio.Task[bool],
    ) -> tuple[bool, bool]:
        test_success = hooks_success = False

        for task in done:
            try:
                result = await task
                if task == test_task:
                    test_success = result
                elif task == hooks_task:
                    hooks_success = result
            except Exception as e:
                self.logger.error(f"Task execution error: {e}")
                if task == test_task:
                    test_success = False
                elif task == hooks_task:
                    hooks_success = False

        return test_success, hooks_success

    def _validate_workflow_results(
        self, test_success: bool, hooks_success: bool, overall_success: bool
    ) -> bool:
        if not test_success:
            overall_success = False
            self.session.fail_task("workflow", "Testing failed")
            return False

        if not hooks_success:
            overall_success = False
            self.session.fail_task("workflow", "Comprehensive hooks failed")
            return False

        return overall_success

    async def _execute_standard_hooks_workflow_async(
        self,
        options: OptionsProtocol,
    ) -> bool:
        hooks_success = await self._run_hooks_phase_async(options)
        if not hooks_success:
            self.session.fail_task("workflow", "Hooks failed")
            return False
        return True

    async def _create_managed_task(
        self,
        coro: t.Coroutine[t.Any, t.Any, t.Any],
        timeout: float = 300.0,
        task_name: str = "workflow_task",
    ) -> asyncio.Task[t.Any]:
        task = asyncio.create_task(coro, name=task_name)

        if self.resource_context:
            self.resource_context.managed_task(task, timeout)

        self._active_tasks.append(task)
        return task

    async def _run_fast_hooks_async(self, options: OptionsProtocol) -> bool:
        result = await self.timeout_manager.with_timeout(
            "fast_hooks",
            asyncio.to_thread(self.phases.run_fast_hooks_only, options),  # type: ignore[arg-type]
            strategy=TimeoutStrategy.RETRY_WITH_BACKOFF,
        )
        return bool(result)  # type: ignore[return-value]

    async def _run_comprehensive_hooks_async(self, options: OptionsProtocol) -> bool:
        result = await self.timeout_manager.with_timeout(
            "comprehensive_hooks",
            asyncio.to_thread(self.phases.run_comprehensive_hooks_only, options),  # type: ignore[arg-type]
            strategy=TimeoutStrategy.GRACEFUL_DEGRADATION,
        )
        return bool(result)  # type: ignore[return-value]

    async def _run_hooks_phase_async(self, options: OptionsProtocol) -> bool:
        result = await self.timeout_manager.with_timeout(
            "comprehensive_hooks",
            asyncio.to_thread(self.phases.run_hooks_phase, options),  # type: ignore[arg-type]
            strategy=TimeoutStrategy.GRACEFUL_DEGRADATION,
        )
        return bool(result)  # type: ignore[return-value]

    async def _run_testing_phase_async(self, options: OptionsProtocol) -> bool:
        result = await self.timeout_manager.with_timeout(
            "test_execution",
            asyncio.to_thread(self.phases.run_testing_phase, options),  # type: ignore[arg-type]
            strategy=TimeoutStrategy.GRACEFUL_DEGRADATION,
        )
        return bool(result)  # type: ignore[return-value]

    async def _execute_ai_agent_workflow_async(
        self, options: OptionsProtocol, max_iterations: int = 10
    ) -> bool:
        self.console.print(
            f"🤖 Starting AI Agent workflow (max {max_iterations} iterations)"
        )

        self.phases.run_configuration_phase(options)  # type: ignore[arg-type]

        if not await self._execute_cleaning_phase_async(options):
            self.session.fail_task("workflow", "Cleaning phase failed")
            return False

        iteration_success = await self._run_iterative_quality_improvement(
            options, max_iterations
        )
        if not iteration_success:
            return False

        return await self._run_final_workflow_phases(options)

    async def _run_iterative_quality_improvement(
        self, options: OptionsProtocol, max_iterations: int
    ) -> bool:
        for iteration in range(1, max_iterations + 1):
            self.console.print(f"\n🔄 Iteration {iteration}/{max_iterations}")

            try:
                iteration_result = await self.timeout_manager.with_timeout(
                    "workflow_iteration",
                    self._execute_single_iteration(options, iteration),
                    strategy=TimeoutStrategy.GRACEFUL_DEGRADATION,
                )

                if iteration_result == "success":
                    self.console.print("✅ All quality checks passed !")
                    return True
                elif iteration_result == "failed":
                    return False

            except Exception as e:
                self.logger.error(f"Iteration {iteration} failed with error: {e}")
                self.console.print(f"⚠️ Iteration {iteration} failed: {e}")

                if iteration == max_iterations:
                    return False

        self.console.print(
            f"❌ Failed to achieve code quality after {max_iterations} iterations"
        )
        self.session.fail_task("workflow", f"Failed after {max_iterations} iterations")
        return False

    async def _execute_single_iteration(
        self, options: OptionsProtocol, iteration: int
    ) -> str:
        fast_hooks_success = await self._run_fast_hooks_with_retry_async(options)

        test_issues = await self._collect_test_issues_async(options)
        hook_issues = await self._collect_comprehensive_hook_issues_async(options)

        if fast_hooks_success and not test_issues and not hook_issues:
            return "success"

        if test_issues or hook_issues:
            fix_success = await self._apply_ai_fixes_async(
                options, test_issues, hook_issues, iteration
            )
            if not fix_success:
                self.console.print(f"❌ AI fixing failed in iteration {iteration}")
                self.session.fail_task(
                    "workflow", f"AI fixing failed in iteration {iteration}"
                )
                return "failed"

        return "continue"

    def _parse_issues_for_agents(
        self, test_issues: list[str], hook_issues: list[str]
    ) -> list[Issue]:
        structured_issues = []

        for issue in hook_issues:
            parsed_issue = self._parse_single_hook_issue(issue)
            structured_issues.append(parsed_issue)

        for issue in test_issues:
            parsed_issue = self._parse_single_test_issue(issue)
            structured_issues.append(parsed_issue)

        return structured_issues

    def _parse_single_hook_issue(self, issue: str) -> Issue:
        from crackerjack.agents.base import IssueType, Priority

        if "refurb: " in issue and "[FURB" in issue:
            return self._parse_refurb_issue(issue)

        hook_type_mapping = {
            "pyright: ": (IssueType.TYPE_ERROR, Priority.HIGH, "pyright"),
            "Type error": (IssueType.TYPE_ERROR, Priority.HIGH, "pyright"),
            "bandit: ": (IssueType.SECURITY, Priority.HIGH, "bandit"),
            "vulture: ": (IssueType.DEAD_CODE, Priority.MEDIUM, "vulture"),
            "complexipy: ": (IssueType.COMPLEXITY, Priority.MEDIUM, "complexipy"),
        }

        for keyword, (issue_type, priority, stage) in hook_type_mapping.items():
            if keyword in issue:
                return self._create_generic_issue(issue, issue_type, priority, stage)

        return self._create_generic_issue(
            issue, IssueType.FORMATTING, Priority.MEDIUM, "hook"
        )

    def _parse_refurb_issue(self, issue: str) -> Issue:
        import re
        import uuid

        from crackerjack.agents.base import Issue, IssueType, Priority

        match = re.search(
            r"refurb: \s *(.+?): (\d +): (\d +)\s +\[(\w +)\]: \s *(.+)", issue
        )
        if match:
            file_path, line_num, _, error_code, message = match.groups()
            return Issue(
                id=str(uuid.uuid4()),
                type=IssueType.FORMATTING,
                severity=Priority.MEDIUM,
                message=f"[{error_code}] {message}",
                file_path=file_path,
                line_number=int(line_num),
                details=[issue],
                stage="refurb",
            )

        return self._create_generic_issue(
            issue, IssueType.FORMATTING, Priority.MEDIUM, "refurb"
        )

    def _parse_single_test_issue(self, issue: str) -> Issue:
        import uuid

        from crackerjack.agents.base import Issue, IssueType, Priority

        if "FAILED" in issue or "ERROR" in issue:
            severity = Priority.HIGH
        else:
            severity = Priority.MEDIUM

        return Issue(
            id=str(uuid.uuid4()),
            type=IssueType.TEST_FAILURE,
            severity=severity,
            message=issue,
            details=[issue],
            stage="test",
        )

    def _create_generic_issue(
        self, issue: str, issue_type: IssueType, priority: Priority, stage: str
    ) -> Issue:
        import uuid

        from crackerjack.agents.base import Issue

        return Issue(
            id=str(uuid.uuid4()),
            type=issue_type,
            severity=priority,
            message=issue,
            details=[issue],
            stage=stage,
        )

    async def _run_final_workflow_phases(self, options: OptionsProtocol) -> bool:
        if not self.phases.run_publishing_phase(options):  # type: ignore[arg-type]
            self.session.fail_task("workflow", "Publishing failed")
            return False

        if not self.phases.run_commit_phase(options):  # type: ignore[arg-type]
            self.session.fail_task("workflow", "Commit failed")
            return False

        return True

    async def _run_fast_hooks_with_retry_async(self, options: OptionsProtocol) -> bool:
        return await asyncio.to_thread(self.phases.run_fast_hooks_only, options)  # type: ignore[arg-type]

    async def _collect_test_issues_async(self, options: OptionsProtocol) -> list[str]:
        if not options.test:
            return []

        try:
            success = await self.timeout_manager.with_timeout(
                "test_execution",
                self._run_testing_phase_async(options),
                strategy=TimeoutStrategy.GRACEFUL_DEGRADATION,
            )
            if success:
                return []
            else:
                test_failures = self.phases.test_manager.get_test_failures()
                if test_failures:
                    return [f"Test failure: {failure}" for failure in test_failures]
                else:
                    return ["Test failures detected-see logs for details"]
        except Exception as e:
            return [f"Test execution error: {e}"]

    async def _collect_comprehensive_hook_issues_async(
        self, options: OptionsProtocol
    ) -> list[str]:
        try:
            hook_results = await self.timeout_manager.with_timeout(
                "comprehensive_hooks",
                asyncio.to_thread(self.phases.hook_manager.run_comprehensive_hooks),  # type: ignore[arg-type]
                strategy=TimeoutStrategy.GRACEFUL_DEGRADATION,
            )

            all_issues = []
            for result in hook_results:
                if (
                    result.status in ("failed", "error", "timeout")
                    and result.issues_found
                ):
                    hook_context = f"{result.name}: "
                    for issue in result.issues_found:
                        all_issues.append(hook_context + issue)

            return all_issues

        except Exception as e:
            return [f"Comprehensive hooks error: {e}"]

    async def _apply_ai_fixes_async(
        self,
        options: OptionsProtocol,
        test_issues: list[str],
        hook_issues: list[str],
        iteration: int,
    ) -> bool:
        all_issues = test_issues + hook_issues
        if not all_issues:
            return True

        self.console.print(
            f"🔧 Applying AI fixes for {len(all_issues)} issues in iteration {iteration}"
        )

        try:
            result = await self.timeout_manager.with_timeout(
                "ai_agent_processing",
                self._execute_ai_fix_workflow(test_issues, hook_issues, iteration),
                strategy=TimeoutStrategy.GRACEFUL_DEGRADATION,
            )
            return bool(result)
        except Exception as e:
            return self._handle_ai_fix_error(e)

    async def _execute_ai_fix_workflow(
        self, test_issues: list[str], hook_issues: list[str], iteration: int
    ) -> bool:
        structured_issues = self._parse_issues_for_agents(test_issues, hook_issues)

        if not structured_issues:
            self.console.print("⚠️ No actionable issues found for AI agents")
            return True

        coordinator = self._create_agent_coordinator()

        fix_result = await self.timeout_manager.with_timeout(
            "ai_agent_processing",
            coordinator.handle_issues(structured_issues),
            strategy=TimeoutStrategy.GRACEFUL_DEGRADATION,
        )

        self._report_fix_results(fix_result, iteration)
        return bool(fix_result.success if fix_result else False)

    def _create_agent_coordinator(self) -> t.Any:
        from crackerjack.agents.base import AgentContext
        from crackerjack.agents.enhanced_coordinator import create_enhanced_coordinator

        context = AgentContext(project_path=self.pkg_path)
        # Use enhanced coordinator with Claude Code agent integration
        return create_enhanced_coordinator(context=context, enable_external_agents=True)

    def _report_fix_results(self, fix_result: FixResult, iteration: int) -> None:
        if fix_result.success:
            self._report_successful_fixes(fix_result, iteration)
        else:
            self._report_failed_fixes(fix_result, iteration)

    def _report_successful_fixes(self, fix_result: FixResult, iteration: int) -> None:
        self.console.print(f"✅ AI fixes applied successfully in iteration {iteration}")
        if fix_result.fixes_applied:
            self.console.print(f" Applied {len(fix_result.fixes_applied)} fixes")

    def _report_failed_fixes(self, fix_result: FixResult, iteration: int) -> None:
        self.console.print(f"⚠️ Some AI fixes failed in iteration {iteration}")
        if fix_result.remaining_issues:
            for error in fix_result.remaining_issues[:3]:
                self.console.print(f" Error: {error}")

    def _handle_ai_fix_error(self, error: Exception) -> bool:
        self.logger.error(f"AI fixing failed: {error}")
        self.console.print(f"❌ AI agent system error: {error}")
        return False


class AsyncWorkflowOrchestrator:
    @depends.inject
    def __init__(
        self,
        logger: Inject[Logger],
        console: Inject[Console],
        pkg_path: Path | None = None,
        dry_run: bool = False,
        web_job_id: str | None = None,
        verbose: bool = False,
        debug: bool = False,
        changed_only: bool = False,
    ) -> None:
        # Initialize console and pkg_path first
        self.console = console
        self.pkg_path = pkg_path or Path.cwd()
        self.dry_run = dry_run
        self.web_job_id = web_job_id
        self.verbose = verbose
        self.debug = debug
        self.changed_only = changed_only

        # Configure ACB dependency injection using native patterns
        from acb.depends import depends

        # Register core dependencies directly with ACB
        depends.set(Path, self.pkg_path)

        # Import protocols for retrieving dependencies via ACB
        from crackerjack.models.protocols import (
            ConfigMergeServiceProtocol,
            FileSystemInterface,
            GitInterface,
            HookManager,
            PublishManager,
            TestManagerProtocol,
        )

        # Setup services with ACB DI (reuse from WorkflowOrchestrator)
        from .workflow_orchestrator import WorkflowOrchestrator

        # Use a temporary orchestrator instance just for service setup
        temp_orch = WorkflowOrchestrator.__new__(WorkflowOrchestrator)
        temp_orch.console = self.console
        temp_orch.pkg_path = self.pkg_path
        temp_orch.verbose = self.verbose
        temp_orch._setup_acb_services()

        self._initialize_logging()

        self.logger = logger

        # Create coordinators - dependencies retrieved via ACB's depends.get_sync()
        self.session = SessionCoordinator(self.console, self.pkg_path, self.web_job_id)
        self.phases = PhaseCoordinator(
            console=self.console,
            pkg_path=self.pkg_path,
            session=self.session,
            filesystem=depends.get_sync(FileSystemInterface),
            git_service=depends.get_sync(GitInterface),
            hook_manager=depends.get_sync(HookManager),
            test_manager=depends.get_sync(TestManagerProtocol),
            publish_manager=depends.get_sync(PublishManager),
            config_merge_service=depends.get_sync(ConfigMergeServiceProtocol),
        )

        self.async_pipeline = AsyncWorkflowPipeline(
            pkg_path=self.pkg_path,
            session=self.session,
            phases=self.phases,
        )

    def _initialize_logging(self) -> None:
        from crackerjack.services.log_manager import get_log_manager

        log_manager = get_log_manager()
        session_id = getattr(self, "web_job_id", None) or str(int(time.time()))[:8]
        debug_log_file = log_manager.create_debug_log_file(session_id)

        log_level = "DEBUG" if self.debug else "INFO"
        self.logger.set_level(log_level)
        self.logger.add_file_handler(debug_log_file)

    async def run_complete_workflow_async(self, options: OptionsProtocol) -> bool:
        return await self.async_pipeline.run_complete_workflow_async(options)

    def run_complete_workflow(self, options: OptionsProtocol) -> bool:
        return asyncio.run(self.run_complete_workflow_async(options))

    def run_cleaning_phase(self, options: OptionsProtocol) -> bool:
        result = self.phases.run_cleaning_phase(options)  # type: ignore[arg-type]
        return bool(result)

    def run_fast_hooks_only(self, options: OptionsProtocol) -> bool:
        result = self.phases.run_fast_hooks_only(options)  # type: ignore[arg-type]
        return bool(result)

    def run_comprehensive_hooks_only(self, options: OptionsProtocol) -> bool:
        result = self.phases.run_comprehensive_hooks_only(options)  # type: ignore[arg-type]
        return bool(result)

    def run_hooks_phase(self, options: OptionsProtocol) -> bool:
        result = self.phases.run_hooks_phase(options)  # type: ignore[arg-type]
        return bool(result)

    def run_testing_phase(self, options: OptionsProtocol) -> bool:
        result = self.phases.run_testing_phase(options)  # type: ignore[arg-type]
        return bool(result)

    def run_publishing_phase(self, options: OptionsProtocol) -> bool:
        result = self.phases.run_publishing_phase(options)  # type: ignore[arg-type]
        return bool(result)

    def run_commit_phase(self, options: OptionsProtocol) -> bool:
        result = self.phases.run_commit_phase(options)  # type: ignore[arg-type]
        return bool(result)

    def run_configuration_phase(self, options: OptionsProtocol) -> bool:
        result = self.phases.run_configuration_phase(options)  # type: ignore[arg-type]
        return bool(result)

    def _cleanup_resources(self) -> None:
        self.session.cleanup_resources()

    def _register_cleanup(self, cleanup_handler: t.Callable[[], None]) -> None:
        self.session.register_cleanup(cleanup_handler)

    def _track_lock_file(self, lock_file_path: Path) -> None:
        self.session.track_lock_file(lock_file_path)
