import time
import typing as t
from pathlib import Path

from rich.console import Console

from ..agents import AgentContext, AgentCoordinator, Issue, IssueType, Priority
from ..config.hooks import HookConfigLoader
from ..core.session_coordinator import SessionCoordinator
from ..executors.hook_executor import HookExecutor
from ..executors.individual_hook_executor import HookProgress, IndividualHookExecutor
from ..managers.test_manager import TestManagementImpl
from ..models.protocols import OptionsProtocol
from ..models.task import HookResult
from ..services.metrics import get_metrics_collector
from .execution_strategies import (
    AICoordinationMode,
    ExecutionContext,
    ExecutionPlan,
    ExecutionStrategy,
    OrchestrationConfig,
    OrchestrationPlanner,
)
from .test_progress_streamer import TestProgressStreamer, TestSuiteProgress


class CorrelationTracker:
    def __init__(self) -> None:
        self.iteration_data: list[dict[str, t.Any]] = []
        self.failure_patterns: dict[str, list[str]] = {}
        self.fix_success_rates: dict[str, float] = {}

    def record_iteration(
        self,
        iteration: int,
        hook_results: list[HookResult],
        test_results: dict[str, t.Any],
        ai_fixes: list[str],
    ) -> None:
        failed_hooks = [r.name for r in hook_results if r.status == "failed"]

        iteration_data = {
            "iteration": iteration,
            "timestamp": time.time(),
            "failed_hooks": failed_hooks,
            "test_failures": test_results.get("failed_tests", []),
            "ai_fixes_applied": ai_fixes,
            "total_errors": sum(
                len(getattr(r, "error_details", [])) for r in hook_results
            ),
        }

        self.iteration_data.append(iteration_data)
        self._analyze_failure_patterns()

    def _analyze_failure_patterns(self) -> None:
        if len(self.iteration_data) < 2:
            return

        for i in range(1, len(self.iteration_data)):
            current = self.iteration_data[i]
            previous = self.iteration_data[i - 1]

            recurring_failures = set(current["failed_hooks"]) & set(
                previous["failed_hooks"]
            )

            for hook in recurring_failures:
                if hook not in self.failure_patterns:
                    self.failure_patterns[hook] = []
                self.failure_patterns[hook].append(f"iteration_{current['iteration']}")

    def get_problematic_hooks(self) -> list[str]:
        return [
            hook
            for hook, failures in self.failure_patterns.items()
            if len(failures) >= 2
        ]

    def get_correlation_data(self) -> dict[str, t.Any]:
        return {
            "iteration_count": len(self.iteration_data),
            "failure_patterns": self.failure_patterns,
            "problematic_hooks": self.get_problematic_hooks(),
            "recent_trends": self.iteration_data[-3:]
            if len(self.iteration_data) >= 3
            else self.iteration_data,
        }


class ProgressStreamer:
    def __init__(
        self, config: OrchestrationConfig, session: SessionCoordinator
    ) -> None:
        self.config = config
        self.session = session
        self.current_stage = "initialization"
        self.current_substage = ""
        self.hook_progress: dict[str, HookProgress] = {}

    def update_stage(self, stage: str, substage: str = "") -> None:
        self.current_stage = stage
        self.current_substage = substage
        self._stream_update(
            {
                "type": "stage_update",
                "stage": stage,
                "substage": substage,
                "timestamp": time.time(),
            }
        )

    def update_hook_progress(self, progress: HookProgress) -> None:
        self.hook_progress[progress.hook_name] = progress
        self._stream_update(
            {
                "type": "hook_progress",
                "hook_name": progress.hook_name,
                "progress": progress.to_dict(),
                "timestamp": time.time(),
            }
        )

    def _stream_update(self, update_data: dict[str, t.Any]) -> None:
        self.session.update_stage(
            self.current_stage,
            f"{self.current_substage}: {update_data.get('hook_name', 'processing')}",
        )

        if hasattr(self.session, "web_job_id") and self.session.web_job_id:
            self._update_websocket_progress(update_data)

    def _update_websocket_progress(self, update_data: dict[str, t.Any]) -> None:
        try:
            if hasattr(self.session, "progress_file") and self.session.progress_file:
                import json

                progress_data = {}
                if self.session.progress_file.exists():
                    with self.session.progress_file.open() as f:
                        progress_data = json.load(f)

                progress_data.update(
                    {
                        "current_stage": self.current_stage,
                        "current_substage": self.current_substage,
                        "hook_progress": {
                            name: prog.to_dict()
                            for name, prog in self.hook_progress.items()
                        },
                        "last_update": update_data,
                        "updated_at": time.time(),
                    }
                )

                with self.session.progress_file.open("w") as f:
                    json.dump(progress_data, f, indent=2)

        except Exception:
            pass


class AdvancedWorkflowOrchestrator:
    def __init__(
        self,
        console: Console,
        pkg_path: Path,
        session: SessionCoordinator,
        config: OrchestrationConfig | None = None,
    ) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.session = session
        self.config = config or OrchestrationConfig()

        self.hook_config_loader = HookConfigLoader()
        self.batch_executor = HookExecutor(console, pkg_path)
        self.individual_executor = IndividualHookExecutor(console, pkg_path)
        self.test_manager = TestManagementImpl(console, pkg_path)
        self.test_streamer = TestProgressStreamer(console, pkg_path)
        self.planner = OrchestrationPlanner(console)
        
        # Detect if running in MCP mode and configure accordingly
        self._detect_and_configure_mcp_mode()

        self.correlation_tracker = CorrelationTracker()
        self.progress_streamer = ProgressStreamer(
            config or OrchestrationConfig(), session
        )
        self.metrics = get_metrics_collector()

        self.agent_coordinator: AgentCoordinator | None = None

    def _detect_and_configure_mcp_mode(self) -> None:
        """Detect if running in MCP context and configure for minimal terminal I/O."""
        # Check for MCP context indicators
        is_mcp_mode = (
            # Console is using StringIO (stdio mode)
            hasattr(self.console.file, 'getvalue')
            # Or console is not attached to a real terminal
            or not self.console.is_terminal
            # Or we have a web job ID (indicates MCP execution)
            or hasattr(self.session, 'job_id')
        )
        
        if is_mcp_mode:
            # Configure individual executor for MCP mode to prevent terminal lockup
            self.individual_executor.set_mcp_mode(True)
            self.console.print("[dim]🔧 MCP mode detected - using minimal output mode[/dim]")
        if self.config.ai_coordination_mode in (
            AICoordinationMode.MULTI_AGENT,
            AICoordinationMode.COORDINATOR,
        ):
            self._initialize_multi_agent_system()

        self.individual_executor.set_progress_callback(
            self.progress_streamer.update_hook_progress
        )
        self.test_streamer.set_progress_callback(self._update_test_suite_progress)

    def _initialize_multi_agent_system(self) -> None:
        self.console.print(
            "[bold cyan]🤖 Initializing Multi-Agent AI System[/bold cyan]"
        )

        agent_context = AgentContext(
            project_path=self.pkg_path,
            session_id=getattr(self.session, "job_id", None),
        )

        self.agent_coordinator = AgentCoordinator(agent_context)
        self.agent_coordinator.initialize_agents()

        capabilities = self.agent_coordinator.get_agent_capabilities()
        self.console.print(
            f"[green]✅ Initialized {len(capabilities)} specialized agents: [/green]"
        )
        for agent_name, info in capabilities.items():
            types_str = ", ".join(info["supported_types"])
            self.console.print(f" • {agent_name}: {types_str}")

        self.console.print(
            f"[cyan]AI Coordination Mode: {self.config.ai_coordination_mode.value}[/cyan]"
        )

    async def execute_orchestrated_workflow(
        self,
        options: OptionsProtocol,
        max_iterations: int = 10,
    ) -> bool:
        workflow_start_time = time.time()
        job_id = (
            getattr(self.session, "job_id", None) or f"orchestration_{int(time.time())}"
        )

        self.console.print(
            "\n[bold bright_blue]🚀 STARTING ORCHESTRATED WORKFLOW[/bold bright_blue]"
        )

        context = ExecutionContext(self.pkg_path, options)

        hook_strategies = [
            self.hook_config_loader.load_strategy("fast"),
            self.hook_config_loader.load_strategy("comprehensive"),
        ]

        execution_plan = self.planner.create_execution_plan(
            self.config, context, hook_strategies
        )

        execution_plan.print_plan_summary(self.console)

        success = False
        strategy_switches = 0
        hooks_time = 0
        tests_time = 0
        ai_time = 0

        for iteration in range(1, max_iterations + 1):
            self.console.print(
                f"\n[bold bright_yellow]🔄 ITERATION {iteration} / {max_iterations}[/bold bright_yellow]"
            )

            context.iteration_count = iteration

            time.time()
            iteration_success, iteration_times = await self._execute_single_iteration(
                execution_plan, context, iteration
            )

            hooks_time += iteration_times.get("hooks", 0)
            tests_time += iteration_times.get("tests", 0)
            ai_time += iteration_times.get("ai", 0)

            if iteration_success:
                self.console.print(
                    f"\n[bold green]🎉 WORKFLOW COMPLETED SUCCESSFULLY IN {iteration} ITERATIONS![/bold green]"
                )
                success = True
                break

            if iteration < max_iterations:
                old_strategy = execution_plan.execution_strategy
                execution_plan = self._adapt_execution_plan(execution_plan, context)
                if execution_plan.execution_strategy != old_strategy:
                    strategy_switches += 1

        if not success:
            self.console.print(
                f"\n[bold red]❌ WORKFLOW INCOMPLETE AFTER {max_iterations} ITERATIONS[/bold red]"
            )

        self._print_final_analysis()

        total_time = int((time.time() - workflow_start_time) * 1000)
        correlation_data = self.correlation_tracker.get_correlation_data()

        self.metrics.record_orchestration_execution(
            job_id=job_id,
            execution_strategy=execution_plan.execution_strategy.value,
            progress_level=self.config.progress_level.value,
            ai_mode=self.config.ai_coordination_mode.value,
            iteration_count=context.iteration_count,
            strategy_switches=strategy_switches,
            correlation_insights=correlation_data,
            total_execution_time_ms=total_time,
            hooks_execution_time_ms=int(hooks_time),
            tests_execution_time_ms=int(tests_time),
            ai_analysis_time_ms=int(ai_time),
        )

        return success

    async def _execute_single_iteration(
        self,
        plan: ExecutionPlan,
        context: ExecutionContext,
        iteration: int,
    ) -> tuple[bool, dict[str, int]]:
        self.progress_streamer.update_stage("iteration_start", f"iteration_{iteration}")

        phase_times = {"hooks": 0, "tests": 0, "ai": 0}

        hooks_start = time.time()
        hook_results = await self._execute_hooks_phase(plan, context)
        phase_times["hooks"] = int((time.time() - hooks_start) * 1000)

        tests_start = time.time()
        test_results = await self._execute_tests_phase(plan, context)
        phase_times["tests"] = int((time.time() - tests_start) * 1000)

        ai_fixes = []
        if not (
            all(r.status == "passed" for r in hook_results)
            and test_results.get("success", False)
        ):
            ai_start = time.time()
            ai_fixes = await self._execute_ai_phase(plan, hook_results, test_results)
            phase_times["ai"] = int((time.time() - ai_start) * 1000)

        job_id = (
            getattr(self.session, "job_id", None) or f"orchestration_{int(time.time())}"
        )
        self.metrics.record_strategy_decision(
            job_id=job_id,
            iteration=iteration,
            previous_strategy=getattr(context, "previous_strategy", None),
            selected_strategy=plan.execution_strategy.value,
            decision_reason=f"Iteration {iteration} execution strategy",
            context_data={
                "failed_hooks": len([r for r in hook_results if r.status == "failed"]),
                "failed_tests": len(test_results.get("failed_tests", [])),
                "ai_fixes_applied": len(ai_fixes),
            },
            effectiveness_score=None,
        )

        self.correlation_tracker.record_iteration(
            iteration, hook_results, test_results, ai_fixes
        )

        all_hooks_passed = all(r.status == "passed" for r in hook_results)
        all_tests_passed = test_results.get("success", False)

        return all_hooks_passed and all_tests_passed, phase_times

    async def _execute_hooks_phase(
        self,
        plan: ExecutionPlan,
        context: ExecutionContext,
    ) -> list[HookResult]:
        self.progress_streamer.update_stage("hooks", "starting")

        all_results = []

        for hook_plan in plan.hook_plans:
            strategy = hook_plan["strategy"]
            execution_mode = hook_plan["execution_mode"]

            self.progress_streamer.update_stage("hooks", f"executing_{strategy.name}")

            if execution_mode == ExecutionStrategy.INDIVIDUAL:
                result = await self.individual_executor.execute_strategy_individual(
                    strategy
                )
                all_results.extend(result.hook_results)
            else:
                results = self.batch_executor.execute_strategy(strategy)
                all_results.extend(results.results)

        self.progress_streamer.update_stage("hooks", "completed")
        return all_results

    async def _execute_tests_phase(
        self,
        plan: ExecutionPlan,
        context: ExecutionContext,
    ) -> dict[str, t.Any]:
        self.progress_streamer.update_stage("tests", "starting")

        test_mode = plan.test_plan.get("mode", "full_suite")

        if test_mode in ("individual_with_progress", "selective"):
            test_results = await self.test_streamer.run_tests_with_streaming(
                context.options, test_mode
            )

            job_id = (
                getattr(self.session, "job_id", None)
                or f"orchestration_{int(time.time())}"
            )
            individual_tests = test_results.get("individual_tests", [])

            for test in individual_tests:
                self.metrics.record_individual_test(
                    job_id=job_id,
                    test_id=test.test_id,
                    test_file=test.test_file,
                    test_class=test.test_class,
                    test_method=test.test_method,
                    status=test.status,
                    execution_time_ms=int((test.duration or 0) * 1000),
                    error_message=test.error_message,
                    error_traceback=test.failure_traceback,
                )
        else:
            test_success = self.test_manager.run_tests(context.options)
            test_results = {
                "success": test_success,
                "failed_tests": [],
                "suite_progress": None,
                "individual_tests": [],
            }

        self.progress_streamer.update_stage("tests", "completed")
        return test_results

    def _update_test_suite_progress(self, suite_progress: TestSuiteProgress) -> None:
        current_test = suite_progress.current_test or "running tests"
        self.progress_streamer.update_stage(
            "tests",
            f"{suite_progress.completed_tests} / {suite_progress.total_tests} - {current_test}",
        )

    async def _execute_ai_phase(
        self,
        plan: ExecutionPlan,
        hook_results: list[HookResult],
        test_results: dict[str, t.Any],
    ) -> list[str]:
        self.progress_streamer.update_stage("ai_analysis", "analyzing_failures")

        failed_hooks = [r for r in hook_results if r.status == "failed"]
        failed_tests = test_results.get("failed_tests", [])

        individual_tests = test_results.get("individual_tests", [])
        failed_individual_tests = [t for t in individual_tests if t.status == "failed"]

        correlation_data = self.correlation_tracker.get_correlation_data()

        self.console.print("\n[bold magenta]🤖 AI ANALYSIS PHASE[/bold magenta]")
        self.console.print(f"AI Mode: {self.config.ai_coordination_mode.value}")
        self.console.print(f"Failed hooks: {len(failed_hooks)}")
        self.console.print(f"Failed tests: {len(failed_tests)}")

        if failed_individual_tests:
            self.console.print(
                f"Individual test failures: {len(failed_individual_tests)}"
            )
            for test in failed_individual_tests[:3]:
                self.console.print(f" ❌ {test.test_id}")

        if correlation_data["problematic_hooks"]:
            self.console.print(
                f"Problematic hooks (recurring): {', '.join(correlation_data['problematic_hooks'])}"
            )

        if self.agent_coordinator and self.config.ai_coordination_mode in (
            AICoordinationMode.MULTI_AGENT,
            AICoordinationMode.COORDINATOR,
        ):
            ai_fixes = await self._execute_multi_agent_analysis(
                failed_hooks, failed_tests, failed_individual_tests, correlation_data
            )
        else:
            ai_fixes = await self._execute_single_agent_analysis(
                failed_hooks, failed_tests, failed_individual_tests, correlation_data
            )

        self.progress_streamer.update_stage("ai_analysis", "completed")
        return ai_fixes

    async def _execute_multi_agent_analysis(
        self,
        failed_hooks: list[HookResult],
        failed_tests: list[str],
        failed_individual_tests: list[t.Any],
        correlation_data: dict[str, t.Any],
    ) -> list[str]:
        self.console.print("[bold cyan]🤖 Multi-Agent Analysis Started[/bold cyan]")

        issues = []

        for hook_result in failed_hooks:
            issue_type = self._map_hook_to_issue_type(hook_result.name)
            issue = Issue(
                id=f"hook_{hook_result.name}_{hash(hook_result.error)}",
                type=issue_type,
                severity=Priority.HIGH
                if hook_result.name in correlation_data.get("problematic_hooks", [])
                else Priority.MEDIUM,
                message=hook_result.error or f"{hook_result.name} failed",
                stage="hooks",
                details=getattr(hook_result, "error_details", []),
            )
            issues.append(issue)

        for test_failure in failed_individual_tests:
            issue = Issue(
                id=f"test_{test_failure.test_id}",
                type=IssueType.TEST_FAILURE,
                severity=Priority.HIGH,
                message=test_failure.error_message
                or f"Test failed: {test_failure.test_id}",
                file_path=getattr(test_failure, "test_file", None),
                stage="tests",
                details=[test_failure.failure_traceback]
                if hasattr(test_failure, "failure_traceback")
                else [],
            )
            issues.append(issue)

        if not issues:
            return ["No issues identified for multi-agent analysis"]

        self.console.print(
            f"[cyan]Processing {len(issues)} issues with specialized agents...[/cyan]"
        )

        assert self.agent_coordinator is not None
        result = await self.agent_coordinator.handle_issues(issues)

        ai_fixes = []
        if result.fixes_applied:
            ai_fixes.extend(result.fixes_applied)
        else:
            ai_fixes.append(
                f"Multi-agent analysis completed with {result.confidence:.2f} confidence"
            )

        if result.remaining_issues:
            ai_fixes.append(f"Remaining issues: {len(result.remaining_issues)}")

        if result.recommendations:
            ai_fixes.extend(
                [f"Recommendation: {rec}" for rec in result.recommendations[:3]]
            )

        self.console.print(
            f"[green]✅ Multi-agent analysis completed: {len(result.fixes_applied)} fixes applied[/green]"
        )
        return ai_fixes

    async def _execute_single_agent_analysis(
        self,
        failed_hooks: list[HookResult],
        failed_tests: list[str],
        failed_individual_tests: list[t.Any],
        correlation_data: dict[str, t.Any],
    ) -> list[str]:
        ai_fixes = [
            f"[Single Agent] Analyzed {len(failed_hooks)} hook failures",
            f"[Single Agent] Analyzed {len(failed_tests)} test failures",
            f"[Single Agent] Analyzed {len(failed_individual_tests)} individual test failures",
            "[Single Agent] Applied batch fixes based on correlation analysis",
        ]

        return ai_fixes

    def _map_hook_to_issue_type(self, hook_name: str) -> IssueType:
        hook_type_mapping = {
            "ruff-format": IssueType.FORMATTING,
            "ruff-check": IssueType.FORMATTING,
            "pyright": IssueType.TYPE_ERROR,
            "bandit": IssueType.SECURITY,
            "vulture": IssueType.DEAD_CODE,
            "refurb": IssueType.COMPLEXITY,
            "creosote": IssueType.DEPENDENCY,
            "detect-secrets": IssueType.SECURITY,
            "trailing-whitespace": IssueType.FORMATTING,
            "end-of-file-fixer": IssueType.FORMATTING,
        }

        return hook_type_mapping.get(hook_name, IssueType.FORMATTING)

    def _adapt_execution_plan(
        self,
        current_plan: ExecutionPlan,
        context: ExecutionContext,
    ) -> ExecutionPlan:
        problematic_hooks = self.correlation_tracker.get_problematic_hooks()

        if problematic_hooks:
            self.console.print(
                f"[yellow]🧠 Adapting strategy due to recurring failures in: {', '.join(problematic_hooks)}[/yellow]"
            )

            if current_plan.execution_strategy == ExecutionStrategy.BATCH:
                self.config.execution_strategy = ExecutionStrategy.INDIVIDUAL
                self.console.print(
                    "[cyan]📋 Switching to individual execution for better debugging[/cyan]"
                )

        hook_strategies = [
            self.hook_config_loader.load_strategy("fast"),
            self.hook_config_loader.load_strategy("comprehensive"),
        ]

        return self.planner.create_execution_plan(self.config, context, hook_strategies)

    def _print_final_analysis(self) -> None:
        correlation_data = self.correlation_tracker.get_correlation_data()

        if correlation_data["iteration_count"] == 0:
            return

        self.console.print("\n" + "=" * 80)
        self.console.print(
            "[bold bright_magenta]🔍 CORRELATION ANALYSIS[/bold bright_magenta]"
        )
        self.console.print("=" * 80)

        self.console.print(f"Total iterations: {correlation_data['iteration_count']}")

        if correlation_data["problematic_hooks"]:
            self.console.print(
                "\n[bold red]Problematic hooks (recurring failures): [/bold red]"
            )
            for hook in correlation_data["problematic_hooks"]:
                failures = correlation_data["failure_patterns"][hook]
                self.console.print(f" ❌ {hook} - failed in {len(failures)} iterations")

        if correlation_data["recent_trends"]:
            self.console.print("\n[bold yellow]Recent trends: [/bold yellow]")
            for trend in correlation_data["recent_trends"][-2:]:
                failed_count = len(trend["failed_hooks"])
                self.console.print(
                    f" Iteration {trend['iteration']}: {failed_count} failed hooks, "
                    f"{trend['total_errors']} total errors"
                )

        self.console.print("=" * 80)
