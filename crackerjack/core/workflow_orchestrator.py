import asyncio
import time
import typing as t
from pathlib import Path

from rich.console import Console

from crackerjack.agents.base import AgentContext, Issue, IssueType, Priority
from crackerjack.agents.coordinator import AgentCoordinator
from crackerjack.models.protocols import OptionsProtocol
from crackerjack.services.debug import (
    AIAgentDebugger,
    NoOpDebugger,
    get_ai_agent_debugger,
)
from crackerjack.services.logging import (
    LoggingContext,
    get_logger,
    setup_structured_logging,
)
from crackerjack.services.memory_optimizer import get_memory_optimizer, memory_optimized
from crackerjack.services.performance_benchmarks import PerformanceBenchmarkService
from crackerjack.services.performance_cache import get_performance_cache
from crackerjack.services.performance_monitor import (
    get_performance_monitor,
    phase_monitor,
)
from crackerjack.services.quality_baseline_enhanced import (
    EnhancedQualityBaselineService,
)
from crackerjack.services.quality_intelligence import QualityIntelligenceService

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
        self._last_security_audit: t.Any = None

        self.logger = get_logger("crackerjack.pipeline")
        self._debugger: AIAgentDebugger | NoOpDebugger | None = None

        self._performance_monitor = get_performance_monitor()
        self._memory_optimizer = get_memory_optimizer()
        self._cache = get_performance_cache()

        # Initialize quality intelligence for advanced decision making
        self._quality_intelligence: QualityIntelligenceService | None
        try:
            quality_baseline = EnhancedQualityBaselineService()
            self._quality_intelligence = QualityIntelligenceService(quality_baseline)
        except Exception:
            # Fallback gracefully if quality intelligence is not available
            self._quality_intelligence = None

        # Initialize performance benchmarking for workflow analysis
        self._performance_benchmarks: PerformanceBenchmarkService | None
        try:
            self._performance_benchmarks = PerformanceBenchmarkService(
                console, pkg_path
            )
        except Exception:
            # Fallback gracefully if benchmarking is not available
            self._performance_benchmarks = None

    @property
    def debugger(self) -> AIAgentDebugger | NoOpDebugger:
        if self._debugger is None:
            self._debugger = get_ai_agent_debugger()
        return self._debugger

    def _should_debug(self) -> bool:
        import os

        return os.environ.get("AI_AGENT_DEBUG", "0") == "1"

    @memory_optimized
    async def run_complete_workflow(self, options: OptionsProtocol) -> bool:
        workflow_id = f"workflow_{int(time.time())}"

        self._performance_monitor.start_workflow(workflow_id)

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

                workflow_perf = self._performance_monitor.end_workflow(
                    workflow_id, success
                )
                self.logger.info(
                    f"Workflow performance: {workflow_perf.performance_score: .1f} score, "
                    f"{workflow_perf.total_duration_seconds: .2f}s duration"
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

                self._memory_optimizer.optimize_memory()
                await self._cache.stop()

    def _initialize_workflow_session(self, options: OptionsProtocol) -> None:
        self.session.initialize_session_tracking(options)
        self.session.track_task("workflow", "Complete crackerjack workflow")

        self._log_workflow_startup_debug(options)
        self._configure_session_cleanup(options)
        self._initialize_zuban_lsp(options)
        self._configure_hook_manager_lsp(options)
        self._register_lsp_cleanup_handler(options)
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
            import subprocess
            import sys

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

    def _log_zuban_lsp_status(self) -> None:
        """Display current Zuban LSP server status during workflow startup."""
        from crackerjack.services.server_manager import find_zuban_lsp_processes

        try:
            lsp_processes = find_zuban_lsp_processes()

            if lsp_processes:
                proc = lsp_processes[0]  # Show first running process
                self.logger.info(
                    f"🔍 Zuban LSP server running (PID: {proc['pid']}, "
                    f"CPU: {proc['cpu']}%, Memory: {proc['mem']}%)"
                )
            else:
                self.logger.info("🔍 Zuban LSP server not running")

        except Exception as e:
            self.logger.debug(f"Failed to check Zuban LSP status: {e}")

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

    def _log_workflow_startup_info(self, options: OptionsProtocol) -> None:
        self.logger.info(
            "Starting complete workflow execution",
            testing=getattr(options, "test", False),
            skip_hooks=getattr(options, "skip_hooks", False),
            package_path=str(self.pkg_path),
        )

        # Display Zuban LSP server status
        self._log_zuban_lsp_status()

    async def _execute_workflow_with_timing(
        self, options: OptionsProtocol, start_time: float, workflow_id: str
    ) -> bool:
        success = await self._execute_workflow_phases(options, workflow_id)
        self.session.finalize_session(start_time, success)

        duration = time.time() - start_time
        self._log_workflow_completion(success, duration)
        self._log_workflow_completion_debug(success, duration)
        await self._generate_performance_benchmark_report(
            workflow_id, duration, success
        )

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

    async def _generate_performance_benchmark_report(
        self, workflow_id: str, duration: float, success: bool
    ) -> None:
        """Generate and display performance benchmark report for workflow execution."""
        if not self._performance_benchmarks:
            return

        try:
            self._gather_performance_metrics(workflow_id, duration, success)
            benchmark_results = await self._performance_benchmarks.run_benchmark_suite()
            self._display_benchmark_results(benchmark_results, duration)

        except Exception as e:
            self.console.print(
                f"[dim]⚠️ Performance benchmark failed: {str(e)[:50]}...[/dim]"
            )

        if self.debugger.enabled:
            self.debugger.print_debug_summary()

    def _gather_performance_metrics(
        self, workflow_id: str, duration: float, success: bool
    ) -> dict[str, t.Any]:
        """Gather performance metrics from workflow execution."""
        return {
            "workflow_id": workflow_id,
            "total_duration": duration,
            "success": success,
            "cache_metrics": self._cache.get_stats() if self._cache else {},
            "memory_metrics": self._memory_optimizer.get_stats()
            if hasattr(self._memory_optimizer, "get_stats")
            else {},
        }

    def _display_benchmark_results(
        self, benchmark_results: t.Any, duration: float
    ) -> None:
        """Display compact performance summary."""
        if not benchmark_results:
            return

        self.console.print("\n[cyan]📊 Performance Benchmark Summary[/cyan]")
        self.console.print(f"Workflow Duration: [bold]{duration:.2f}s[/bold]")

        self._show_performance_improvements(benchmark_results)

    def _show_performance_improvements(self, benchmark_results: t.Any) -> None:
        """Show key performance improvements from benchmark results."""
        for result in benchmark_results.results[:3]:  # Top 3 results
            self._display_time_improvement(result)
            self._display_cache_efficiency(result)

    def _display_time_improvement(self, result: t.Any) -> None:
        """Display time improvement percentage if available."""
        if result.time_improvement_percentage > 0:
            self.console.print(
                f"[green]⚡[/green] {result.test_name}: {result.time_improvement_percentage:.1f}% faster"
            )

    def _display_cache_efficiency(self, result: t.Any) -> None:
        """Display cache hit ratio if available."""
        if result.cache_hit_ratio > 0:
            self.console.print(
                f"[blue]🎯[/blue] Cache efficiency: {result.cache_hit_ratio:.0%}"
            )

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
        success = True

        with phase_monitor(workflow_id, "configuration"):
            config_success = self.phases.run_configuration_phase(options)
            success = success and config_success

        quality_success = await self._execute_quality_phase(options, workflow_id)
        success = success and quality_success

        # If quality phase failed and we're in publishing mode, stop here
        if not quality_success and self._is_publishing_workflow(options):
            return False

        # Execute publishing workflow if requested
        publishing_success = await self._execute_publishing_workflow(
            options, workflow_id
        )
        if not publishing_success:
            success = False

        # Execute commit workflow independently if requested
        # Note: Commit workflow runs regardless of publish success to ensure
        # version bump changes are always committed when requested
        commit_success = await self._execute_commit_workflow(options, workflow_id)
        if not commit_success:
            success = False

        # Only fail the overall workflow if publishing was explicitly requested and failed
        if not publishing_success and (options.publish or options.all):
            self.console.print(
                "[red]❌ Publishing failed - overall workflow marked as failed[/red]"
            )
            return False

        return success

    def _handle_quality_phase_result(
        self, success: bool, quality_success: bool, options: OptionsProtocol
    ) -> bool:
        """Handle the result of the quality phase execution."""
        if not quality_success:
            if self._is_publishing_workflow(options):
                # For publishing workflows, quality failures should stop execution
                return False
            # For non-publishing workflows, we continue but mark as failed
            return False
        return success

    def _handle_workflow_completion(
        self, success: bool, publishing_success: bool, options: OptionsProtocol
    ) -> bool:
        """Handle workflow completion and determine final success status."""
        # Only fail the overall workflow if publishing was explicitly requested and failed
        if not publishing_success and (options.publish or options.all):
            self.console.print(
                "[red]❌ Publishing failed - overall workflow marked as failed[/red]"
            )
            return False
        return success

    def _is_publishing_workflow(self, options: OptionsProtocol) -> bool:
        return bool(options.publish or options.all)

    async def _execute_publishing_workflow(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
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
        if not options.commit:
            return True

        with phase_monitor(workflow_id, "commit"):
            if not self.phases.run_commit_phase(options):
                return False
        return True

    async def _execute_quality_phase(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
        # Use quality intelligence to make informed decisions about quality phase
        if self._quality_intelligence:
            quality_decision = await self._make_quality_intelligence_decision(options)
            self.console.print(
                f"[dim]🧠 Quality Intelligence: {quality_decision}[/dim]"
            )

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

    async def _make_quality_intelligence_decision(
        self, options: OptionsProtocol
    ) -> str:
        """Use quality intelligence to make informed decisions about workflow execution."""
        try:
            if not self._quality_intelligence:
                return "Quality intelligence not available"

            anomalies = self._quality_intelligence.detect_anomalies()
            patterns = self._quality_intelligence.identify_patterns()

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

    async def _execute_test_workflow(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
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
        with phase_monitor(workflow_id, "fast_hooks") as monitor:
            if not await self._run_initial_fast_hooks_async(
                options, iteration, monitor
            ):
                return False

        return self._execute_optional_cleaning_phase(options)

    def _execute_optional_cleaning_phase(self, options: OptionsProtocol) -> bool:
        if not getattr(options, "clean", False):
            return True

        if not self._run_code_cleaning_phase(options):
            return False

        if not self._run_post_cleaning_fast_hooks(options):
            return False

        self._mark_code_cleaning_complete()
        return True

    async def _handle_ai_workflow_completion(
        self,
        options: OptionsProtocol,
        iteration: int,
        testing_passed: bool,
        comprehensive_passed: bool,
        workflow_id: str = "unknown",
    ) -> bool:
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

    async def _handle_ai_agent_workflow(
        self,
        options: OptionsProtocol,
        iteration: int,
        testing_passed: bool,
        comprehensive_passed: bool,
        workflow_id: str = "unknown",
    ) -> bool:
        if not await self._process_security_gates(options):
            return False

        needs_ai_fixing = self._determine_ai_fixing_needed(
            testing_passed, comprehensive_passed, bool(options.publish or options.all)
        )

        if needs_ai_fixing:
            return await self._execute_ai_fixing_workflow(options, iteration)

        return self._finalize_ai_workflow_success(
            options, iteration, testing_passed, comprehensive_passed
        )

    async def _process_security_gates(self, options: OptionsProtocol) -> bool:
        publishing_requested, security_blocks = (
            self._check_security_gates_for_publishing(options)
        )

        if not (publishing_requested and security_blocks):
            return True

        security_fix_result = await self._handle_security_gate_failure(
            options, allow_ai_fixing=True
        )
        return security_fix_result

    async def _execute_ai_fixing_workflow(
        self, options: OptionsProtocol, iteration: int
    ) -> bool:
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
        publishing_requested, security_blocks = (
            self._check_security_gates_for_publishing(options)
        )

        if publishing_requested and security_blocks:
            return await self._handle_security_gate_failure(options)

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
        self.console.print("\n[bold blue]🧹 Running Code Cleaning Phase...[/bold blue]")

        success = self.phases.run_cleaning_phase(options)
        if success:
            self.console.print("[green]✅ Code cleaning completed successfully[/green]")
        else:
            self.console.print("[red]❌ Code cleaning failed[/red]")
            self.session.fail_task("workflow", "Code cleaning phase failed")

        return success

    def _run_post_cleaning_fast_hooks(self, options: OptionsProtocol) -> bool:
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
        return getattr(self, "_code_cleaning_complete", False)

    def _mark_code_cleaning_complete(self) -> None:
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

        if not self._execute_fast_hooks_workflow(options):
            self._handle_hooks_completion(False)
            return False

        if not self._execute_cleaning_workflow_if_needed(options):
            self._handle_hooks_completion(False)
            return False

        comprehensive_success = self._run_comprehensive_hooks_phase(options)
        self._handle_hooks_completion(comprehensive_success)

        return comprehensive_success

    def _execute_fast_hooks_workflow(self, options: OptionsProtocol) -> bool:
        """Execute fast hooks phase."""
        return self._run_fast_hooks_phase(options)

    def _execute_cleaning_workflow_if_needed(self, options: OptionsProtocol) -> bool:
        """Execute cleaning workflow if requested."""
        if not getattr(options, "clean", False):
            return True

        if not self._run_code_cleaning_phase(options):
            return False

        if not self._run_post_cleaning_fast_hooks(options):
            return False

        self._mark_code_cleaning_complete()
        return True

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
            self._prepare_ai_fixing_environment(options)

            agent_coordinator, issues = await self._setup_ai_fixing_workflow()

            if not issues:
                return self._handle_no_issues_found()

            return await self._execute_ai_fixes(options, agent_coordinator, issues)

        except Exception as e:
            return self._handle_fixing_phase_error(e)

    def _initialize_ai_fixing_phase(self, options: OptionsProtocol) -> None:
        self._update_mcp_status("ai_fixing", "running")
        self.logger.info("Starting AI agent fixing phase")
        self._log_debug_phase_start()

    def _prepare_ai_fixing_environment(self, options: OptionsProtocol) -> None:
        should_run_cleaning = (
            getattr(options, "clean", False) and not self._has_code_cleaning_run()
        )

        if not should_run_cleaning:
            return

        self.console.print(
            "\n[bold yellow]🤖 AI agents recommend running code cleaning first for better results...[/bold yellow]"
        )

        if self._run_code_cleaning_phase(options):
            self._run_post_cleaning_fast_hooks(options)
            self._mark_code_cleaning_complete()

    async def _setup_ai_fixing_workflow(
        self,
    ) -> tuple[AgentCoordinator, list[t.Any]]:
        agent_coordinator = self._setup_agent_coordinator()
        issues = await self._collect_issues_from_failures()
        return agent_coordinator, issues

    async def _execute_ai_fixes(
        self,
        options: OptionsProtocol,
        agent_coordinator: AgentCoordinator,
        issues: list[t.Any],
    ) -> bool:
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

        if self._should_verify_test_fixes(fix_result.fixes_applied):
            if not await self._verify_test_fixes(options):
                verification_success = False

        if self._should_verify_hook_fixes(fix_result.fixes_applied):
            if not await self._verify_hook_fixes(options):
                verification_success = False

        self._log_verification_result(verification_success)
        return verification_success

    def _should_verify_test_fixes(self, fixes_applied: list[str]) -> bool:
        return any("test" in fix.lower() for fix in fixes_applied)

    async def _verify_test_fixes(self, options: OptionsProtocol) -> bool:
        self.logger.info("Re-running tests to verify test fixes")
        test_success = self.phases.run_testing_phase(options)
        if not test_success:
            self.logger.warning("Test verification failed-test fixes did not work")
        return test_success

    def _should_verify_hook_fixes(self, fixes_applied: list[str]) -> bool:
        hook_fixes = [fix for fix in fixes_applied if self._is_hook_related_fix(fix)]
        return bool(hook_fixes)

    def _is_hook_related_fix(self, fix: str) -> bool:
        """Check if a fix is related to hooks and should trigger hook verification."""
        fix_lower = fix.lower()
        return (
            "hook" not in fix_lower or "complexity" in fix_lower or "type" in fix_lower
        )

    async def _verify_hook_fixes(self, options: OptionsProtocol) -> bool:
        self.logger.info("Re-running comprehensive hooks to verify hook fixes")
        hook_success = self.phases.run_comprehensive_hooks_only(options)
        if not hook_success:
            self.logger.warning("Hook verification failed-hook fixes did not work")
        return hook_success

    def _log_verification_result(self, verification_success: bool) -> None:
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
        issues: list[Issue] = []

        if task_id == "comprehensive_hooks":
            issues.extend(self._parse_comprehensive_hook_errors(error_msg))
        elif task_id == "fast_hooks":
            issues.append(self._create_fast_hook_issue())

        return issues

    def _parse_comprehensive_hook_errors(self, error_msg: str) -> list[Issue]:
        error_lower = error_msg.lower()
        error_checkers = self._get_comprehensive_error_checkers()

        issues = []
        for check_func in error_checkers:
            issue = check_func(error_lower)
            if issue:
                issues.append(issue)

        return issues

    def _get_comprehensive_error_checkers(
        self,
    ) -> list[t.Callable[[str], Issue | None]]:
        """Get list of error checking functions for comprehensive hooks."""
        return [
            self._check_complexity_error,
            self._check_type_error,
            self._check_security_error,
            self._check_performance_error,
            self._check_dead_code_error,
            self._check_regex_validation_error,
        ]

    def _check_complexity_error(self, error_lower: str) -> Issue | None:
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
        issue_lower = issue_str.lower()

        # Check high priority issues first
        high_priority_result = self._check_high_priority_issues(issue_lower)
        if high_priority_result:
            return high_priority_result

        # Check medium priority issues
        medium_priority_result = self._check_medium_priority_issues(issue_lower)
        if medium_priority_result:
            return medium_priority_result

        # Default to formatting issue
        return IssueType.FORMATTING, Priority.MEDIUM

    def _check_high_priority_issues(
        self, issue_lower: str
    ) -> tuple[IssueType, Priority] | None:
        """Check for high priority issue types.

        Args:
            issue_lower: Lowercase issue string

        Returns:
            Tuple of issue type and priority if found, None otherwise
        """
        high_priority_checks = [
            (self._is_type_error, IssueType.TYPE_ERROR),
            (self._is_security_issue, IssueType.SECURITY),
            (self._is_complexity_issue, IssueType.COMPLEXITY),
            (self._is_regex_validation_issue, IssueType.REGEX_VALIDATION),
        ]

        for check_func, issue_type in high_priority_checks:
            if check_func(issue_lower):
                return issue_type, Priority.HIGH

        return None

    def _check_medium_priority_issues(
        self, issue_lower: str
    ) -> tuple[IssueType, Priority] | None:
        """Check for medium priority issue types.

        Args:
            issue_lower: Lowercase issue string

        Returns:
            Tuple of issue type and priority if found, None otherwise
        """
        medium_priority_checks = [
            (self._is_dead_code_issue, IssueType.DEAD_CODE),
            (self._is_performance_issue, IssueType.PERFORMANCE),
            (self._is_import_error, IssueType.IMPORT_ERROR),
        ]

        for check_func, issue_type in medium_priority_checks:
            if check_func(issue_lower):
                return issue_type, Priority.MEDIUM

        return None

    def _is_type_error(self, issue_lower: str) -> bool:
        return any(
            keyword in issue_lower for keyword in ("type", "annotation", "pyright")
        )

    def _is_security_issue(self, issue_lower: str) -> bool:
        return any(
            keyword in issue_lower for keyword in ("security", "bandit", "hardcoded")
        )

    def _is_complexity_issue(self, issue_lower: str) -> bool:
        return any(
            keyword in issue_lower
            for keyword in ("complexity", "complexipy", "c901", "too complex")
        )

    def _is_regex_validation_issue(self, issue_lower: str) -> bool:
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
        return any(keyword in issue_lower for keyword in ("unused", "dead", "vulture"))

    def _is_performance_issue(self, issue_lower: str) -> bool:
        return any(
            keyword in issue_lower for keyword in ("performance", "refurb", "furb")
        )

    def _is_import_error(self, issue_lower: str) -> bool:
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
        publishing_requested = bool(options.publish or options.all)

        if not publishing_requested:
            return False, False

        try:
            security_blocks_publishing = self._check_security_critical_failures()
            return publishing_requested, security_blocks_publishing
        except Exception as e:
            self.logger.warning(f"Security check failed: {e} - blocking publishing")
            self.console.print(
                "[red]🔒 SECURITY CHECK FAILED: Unable to verify security status - publishing BLOCKED[/red]"
            )

            return publishing_requested, True

    async def _handle_security_gate_failure(
        self, options: OptionsProtocol, allow_ai_fixing: bool = False
    ) -> bool:
        self._display_security_gate_failure_message()

        if allow_ai_fixing:
            return await self._attempt_ai_assisted_security_fix(options)
        return self._handle_manual_security_fix()

    def _display_security_gate_failure_message(self) -> None:
        """Display initial security gate failure message."""
        self.console.print(
            "[red]🔒 SECURITY GATE: Critical security checks failed[/red]"
        )

    async def _attempt_ai_assisted_security_fix(self, options: OptionsProtocol) -> bool:
        """Attempt to fix security issues using AI assistance.

        Args:
            options: Configuration options

        Returns:
            True if security issues were resolved, False otherwise
        """
        self._display_ai_fixing_messages()

        ai_fix_success = await self._run_ai_agent_fixing_phase(options)
        if ai_fix_success:
            return self._verify_security_fix_success()

        return False

    def _display_ai_fixing_messages(self) -> None:
        """Display messages about AI-assisted security fixing."""
        self.console.print(
            "[red]Security-critical hooks (bandit, pyright, gitleaks) must pass before publishing[/red]"
        )
        self.console.print(
            "[yellow]🤖 Attempting AI-assisted security issue resolution...[/yellow]"
        )

    def _verify_security_fix_success(self) -> bool:
        """Verify that AI fixes resolved the security issues.

        Returns:
            True if security issues were resolved, False otherwise
        """
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
            self.logger.warning(f"Security re-check failed: {e} - blocking publishing")
            return False

    def _handle_manual_security_fix(self) -> bool:
        """Handle security fix when AI assistance is not allowed.

        Returns:
            Always False since manual intervention is required
        """
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
        if publishing_requested:
            return not testing_passed or not comprehensive_passed

        return not testing_passed or not comprehensive_passed

    def _determine_workflow_success(
        self,
        testing_passed: bool,
        comprehensive_passed: bool,
        publishing_requested: bool,
    ) -> bool:
        if publishing_requested:
            return testing_passed and comprehensive_passed

        return testing_passed and comprehensive_passed

    def _show_verbose_failure_details(
        self, testing_passed: bool, comprehensive_passed: bool
    ) -> None:
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
        try:
            from crackerjack.security.audit import SecurityAuditor

            auditor = SecurityAuditor()

            fast_results = self._get_recent_fast_hook_results()
            comprehensive_results = self._get_recent_comprehensive_hook_results()

            audit_report = auditor.audit_hook_results(
                fast_results, comprehensive_results
            )

            self._last_security_audit = audit_report

            return audit_report.has_critical_failures

        except Exception as e:
            self.logger.warning(f"Security audit failed: {e} - failing securely")

            raise

    def _get_recent_fast_hook_results(self) -> list[t.Any]:
        results = self._extract_hook_results_from_session("fast_hooks")

        if not results:
            results = self._create_mock_hook_results(["gitleaks"])

        return results

    def _extract_hook_results_from_session(self, hook_type: str) -> list[t.Any]:
        results: list[t.Any] = []

        session_tracker = self._get_session_tracker()
        if not session_tracker:
            return results

        for task_id, task_data in session_tracker.tasks.items():
            if task_id == hook_type and hasattr(task_data, "hook_results"):
                if task_data.hook_results:
                    results.extend(task_data.hook_results)

        return results

    def _get_session_tracker(self) -> t.Any | None:
        return (
            getattr(self.session, "session_tracker", None)
            if hasattr(self.session, "session_tracker")
            else None
        )

    def _create_mock_hook_results(self, critical_hooks: list[str]) -> list[t.Any]:
        results: list[t.Any] = []

        for hook_name in critical_hooks:
            mock_result = self._create_mock_hook_result(hook_name)
            results.append(mock_result)

        return results

    def _create_mock_hook_result(self, hook_name: str) -> t.Any:
        return type(
            "MockResult",
            (),
            {
                "name": hook_name,
                "status": "unknown",
                "output": "Unable to determine hook status",
            },
        )()

    def _get_recent_comprehensive_hook_results(self) -> list[t.Any]:
        results = self._extract_hook_results_from_session("comprehensive_hooks")

        if not results:
            results = self._create_mock_hook_results(["bandit", "pyright"])

        return results

    def _is_security_critical_failure(self, result: t.Any) -> bool:
        security_critical_hooks = {
            "bandit",
            "pyright",
            "gitleaks",
        }

        hook_name = getattr(result, "name", "").lower()
        is_failed = getattr(result, "status", "unknown") in (
            "failed",
            "error",
            "timeout",
        )

        return hook_name in security_critical_hooks and is_failed

    def _show_security_audit_warning(self) -> None:
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

    async def _run_initial_fast_hooks_async(
        self, options: OptionsProtocol, iteration: int, monitor: t.Any
    ) -> bool:
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
        with phase_monitor(workflow_id, "fast_hooks") as monitor:
            monitor.record_sequential_op()
            return self._run_fast_hooks_phase(options)

    async def _run_comprehensive_hooks_phase_monitored(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
        with phase_monitor(workflow_id, "comprehensive_hooks") as monitor:
            monitor.record_sequential_op()
            return self._run_comprehensive_hooks_phase(options)

    async def _run_testing_phase_async(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
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
                self.pkg_path, console=self.console
            )

            should_improve = await coverage_orchestrator.should_improve_coverage()
            if not should_improve:
                self.console.print(
                    "[dim]📈 Coverage at 100% - no improvement needed[/dim]"
                )
                return

            # Create agent context for coverage improvement
            from crackerjack.agents.base import AgentContext
            from crackerjack.services.filesystem import FileSystemService

            FileSystemService()
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
        with phase_monitor(workflow_id, "hooks") as monitor:
            self._update_hooks_status_running()

            fast_hooks_success = self._execute_monitored_fast_hooks_phase(
                options, monitor
            )
            if not fast_hooks_success:
                self._handle_hooks_completion(False)
                return False

            if not self._execute_monitored_cleaning_phase(options):
                self._handle_hooks_completion(False)
                return False

            comprehensive_success = self._execute_monitored_comprehensive_phase(
                options, monitor
            )

            hooks_success = fast_hooks_success and comprehensive_success
            self._handle_hooks_completion(hooks_success)
            return hooks_success

    def _execute_monitored_fast_hooks_phase(
        self, options: OptionsProtocol, monitor: t.Any
    ) -> bool:
        fast_hooks_success = self._run_fast_hooks_phase(options)
        if fast_hooks_success:
            monitor.record_sequential_op()
        return fast_hooks_success

    def _execute_monitored_cleaning_phase(self, options: OptionsProtocol) -> bool:
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

        log_level = "DEBUG" if self.debug else "INFO"
        setup_structured_logging(
            level=log_level, json_output=False, log_file=debug_log_file
        )

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
        result: bool = await self.pipeline.run_complete_workflow(options)
        return result

    def run_complete_workflow_sync(self, options: OptionsProtocol) -> bool:
        """Sync wrapper for run_complete_workflow."""
        return asyncio.run(self.run_complete_workflow(options))

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
