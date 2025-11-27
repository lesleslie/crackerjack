"""Workflow Orchestrator for ACB integration.

ACB-powered orchestration layer managing workflow lifecycle, dependency resolution,
and execution strategies. Supports dual execution modes for gradual migration.

ACB Patterns:
- MODULE_ID and MODULE_STATUS at module level
- depends.set() registration after class definition
- Structured logging with context fields
- Protocol-based interfaces
"""

from __future__ import annotations

import asyncio
import time
import typing as t
from contextlib import suppress
from importlib.metadata import version
from pathlib import Path

from acb.config import Config
from acb.console import Console
from acb.depends import Inject, depends
from acb.events import Event, EventHandlerResult

from crackerjack.agents.base import AgentContext, Issue, IssueType, Priority
from crackerjack.agents.enhanced_coordinator import EnhancedAgentCoordinator
from crackerjack.events import WorkflowEvent, WorkflowEventBus
from crackerjack.models.protocols import (
    DebugServiceProtocol,
    LoggerProtocol,
    MemoryOptimizerProtocol,
    OptionsProtocol,
    PerformanceBenchmarkProtocol,
    PerformanceCacheProtocol,
    PerformanceMonitorProtocol,
    QualityIntelligenceProtocol,
)
from crackerjack.services.logging import LoggingContext
from crackerjack.services.memory_optimizer import memory_optimized

from .phase_coordinator import PhaseCoordinator
from .session_coordinator import SessionController, SessionCoordinator
from .workflow import WorkflowPhaseExecutor


class WorkflowPipeline:
    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        config: Inject[Config],
        performance_monitor: Inject[PerformanceMonitorProtocol],
        memory_optimizer: Inject[MemoryOptimizerProtocol],
        performance_cache: Inject[PerformanceCacheProtocol],
        debugger: Inject[DebugServiceProtocol],
        logger: Inject[LoggerProtocol],
        session: Inject[SessionCoordinator],
        phases: Inject[PhaseCoordinator],
        phase_executor: Inject[WorkflowPhaseExecutor],
        quality_intelligence: Inject[QualityIntelligenceProtocol] | None = None,
        performance_benchmarks: Inject[PerformanceBenchmarkProtocol] | None = None,
    ) -> None:
        self.console = console
        self.config = config
        self.pkg_path = config.root_path
        self.session = session
        self.phases = phases
        self._mcp_state_manager: t.Any = None
        self._last_security_audit: t.Any = None

        # Services injected via ACB DI
        self._debugger = debugger
        self._performance_monitor = performance_monitor
        self._memory_optimizer = memory_optimizer
        self._cache = performance_cache
        self._quality_intelligence = quality_intelligence
        self._performance_benchmarks = performance_benchmarks
        self.logger = logger

        # Event bus with graceful fallback
        try:
            self._event_bus: WorkflowEventBus | None = depends.get_sync(
                WorkflowEventBus
            )
        except Exception as e:
            print(f"WARNING: WorkflowEventBus not available: {type(e).__name__}: {e}")
            self._event_bus = None

        # Phase executor for workflow execution
        self._phase_executor = phase_executor
        self._phase_executor.configure(session, phases, self._event_bus)
        self._phase_executor._mcp_state_manager = self._mcp_state_manager

        self._session_controller = SessionController(self)

    @property
    def debugger(self) -> DebugServiceProtocol:
        """Get debug service (already injected via DI)."""
        return self._debugger

    def _should_debug(self) -> bool:
        import os

        return os.environ.get("AI_AGENT_DEBUG", "0") == "1"

    @memory_optimized
    async def run_complete_workflow(self, options: OptionsProtocol) -> bool:
        workflow_id = f"workflow_{int(time.time())}"
        event_context = self._workflow_context(workflow_id, options)
        start_time = time.time()

        self._performance_monitor.start_workflow(workflow_id)
        await self._cache.start()
        await self._publish_event(WorkflowEvent.WORKFLOW_STARTED, event_context)

        success = False
        try:
            with LoggingContext(
                "workflow_execution",
                testing=getattr(options, "test", False),
                skip_hooks=getattr(options, "skip_hooks", False),
            ):
                success = await self._execute_workflow(
                    options, workflow_id, event_context, start_time
                )
            return success
        except KeyboardInterrupt:
            return await self._handle_keyboard_interrupt(workflow_id, event_context)
        except Exception as e:
            return await self._handle_general_exception(e, workflow_id, event_context)
        finally:
            await self._cleanup_workflow_resources()

    async def _execute_workflow(
        self,
        options: OptionsProtocol,
        workflow_id: str,
        event_context: dict[str, t.Any],
        start_time: float,
    ) -> bool:
        """Execute the workflow either event-driven or sequentially."""
        if self._event_bus:
            return await self._run_event_driven_workflow(
                options, workflow_id, event_context, start_time
            )
        return await self._run_sequential_workflow(
            options, workflow_id, event_context, start_time
        )

    async def _run_sequential_workflow(
        self,
        options: OptionsProtocol,
        workflow_id: str,
        event_context: dict[str, t.Any],
        start_time: float,
    ) -> bool:
        """Execute the workflow sequentially."""
        await self._publish_event(
            WorkflowEvent.WORKFLOW_SESSION_INITIALIZING,
            event_context,
        )
        self._session_controller.initialize(options)
        await self._publish_event(
            WorkflowEvent.WORKFLOW_SESSION_READY,
            event_context,
        )
        success = await self._execute_workflow_with_timing(
            options, start_time, workflow_id
        )
        final_event = (
            WorkflowEvent.WORKFLOW_COMPLETED
            if success
            else WorkflowEvent.WORKFLOW_FAILED
        )
        await self._publish_event(
            final_event,
            event_context | {"success": success},
        )
        self._performance_monitor.end_workflow(workflow_id, success)
        return success

    async def _handle_keyboard_interrupt(
        self, workflow_id: str, event_context: dict[str, t.Any]
    ) -> bool:
        """Handle keyboard interrupt during workflow execution."""
        self._performance_monitor.end_workflow(workflow_id, False)
        await self._publish_event(
            WorkflowEvent.WORKFLOW_INTERRUPTED,
            event_context,
        )
        return self._handle_user_interruption()

    async def _handle_general_exception(
        self, e: Exception, workflow_id: str, event_context: dict[str, t.Any]
    ) -> bool:
        """Handle general exceptions during workflow execution."""
        self._performance_monitor.end_workflow(workflow_id, False)
        await self._publish_event(
            WorkflowEvent.WORKFLOW_FAILED,
            event_context
            | {
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )
        return self._handle_workflow_exception(e)

    async def _cleanup_workflow_resources(self) -> None:
        """Clean up workflow resources in the finally block."""
        self.session.cleanup_resources()
        self._memory_optimizer.optimize_memory()
        await self._cache.stop()

    def _unsubscribe_all_subscriptions(self, subscriptions: list[str]) -> None:
        """Unsubscribe from all event subscriptions."""
        for subscription_id in subscriptions.copy():
            if self._event_bus:
                self._event_bus.unsubscribe(subscription_id)
            subscriptions.remove(subscription_id)

    async def _finalize_workflow(
        self,
        start_time: float,
        workflow_id: str,
        success: bool,
        completion_future: asyncio.Future[bool],
        subscriptions: list[str],
        payload: dict[str, t.Any] | None = None,
    ) -> EventHandlerResult:
        """Finalize the workflow execution."""
        if completion_future.done():
            return EventHandlerResult(success=success)

        self.session.finalize_session(start_time, success)
        duration = time.time() - start_time
        self._log_workflow_completion(success, duration)
        self._log_workflow_completion_debug(success, duration)

        workflow_perf = self._performance_monitor.end_workflow(workflow_id, success)
        self.logger.info(
            f"Workflow performance: {workflow_perf.performance_score: .1f} score, "
            f"{workflow_perf.total_duration_seconds: .2f}s duration"
        )

        await self._generate_performance_benchmark_report(
            workflow_id, duration, success
        )

        self._unsubscribe_all_subscriptions(subscriptions)
        completion_future.set_result(success)

        return EventHandlerResult(success=success)

    async def _publish_workflow_failure(
        self,
        event_context: dict[str, t.Any],
        stage: str,
        error: Exception | None = None,
    ) -> None:
        """Publish workflow failure event."""
        payload: dict[str, t.Any] = event_context | {"stage": stage}
        if error is not None:
            payload["error"] = str(error)
            payload["error_type"] = type(error).__name__

        await self._publish_event(WorkflowEvent.WORKFLOW_FAILED, payload)

    async def _handle_session_ready(
        self,
        event: Event,
        state_flags: dict[str, bool],
        workflow_id: str,
        options: OptionsProtocol,
    ) -> EventHandlerResult:
        """Handle session ready event."""
        if state_flags["configuration"]:
            return EventHandlerResult(success=True)
        state_flags["configuration"] = True

        try:
            await self._publish_event(
                WorkflowEvent.CONFIG_PHASE_STARTED,
                {"workflow_id": workflow_id},
            )
            config_success = await asyncio.to_thread(
                self.phases.run_configuration_phase,
                options,
            )
            await self._publish_event(
                WorkflowEvent.CONFIG_PHASE_COMPLETED,
                {
                    "workflow_id": workflow_id,
                    "success": config_success,
                },
            )
            if not config_success:
                await self._publish_workflow_failure(
                    {"workflow_id": workflow_id}, "configuration"
                )
            return EventHandlerResult(success=config_success)
        except Exception as exc:  # pragma: no cover - defensive
            await self._publish_workflow_failure(
                {"workflow_id": workflow_id}, "configuration", exc
            )
            return EventHandlerResult(success=False, error_message=str(exc))

    async def _handle_config_completed(
        self,
        event: Event,
        state_flags: dict[str, bool],
        workflow_id: str,
        options: OptionsProtocol,
    ) -> EventHandlerResult:
        """Handle configuration completed event."""
        if not event.payload.get("success", False):
            return EventHandlerResult(success=False)
        if state_flags["quality"]:
            return EventHandlerResult(success=True)
        state_flags["quality"] = True

        try:
            await self._publish_event(
                WorkflowEvent.QUALITY_PHASE_STARTED,
                {"workflow_id": workflow_id},
            )
            quality_success = await self._execute_quality_phase(options, workflow_id)
            await self._publish_event(
                WorkflowEvent.QUALITY_PHASE_COMPLETED,
                {
                    "workflow_id": workflow_id,
                    "success": quality_success,
                },
            )
            if not quality_success:
                await self._publish_workflow_failure(
                    {"workflow_id": workflow_id}, "quality"
                )
            return EventHandlerResult(success=quality_success)
        except Exception as exc:  # pragma: no cover - defensive
            await self._publish_workflow_failure(
                {"workflow_id": workflow_id}, "quality", exc
            )
            return EventHandlerResult(success=False, error_message=str(exc))

    async def _handle_quality_completed(
        self,
        event: Event,
        state_flags: dict[str, bool],
        workflow_id: str,
        options: OptionsProtocol,
        publish_requested: bool,
    ) -> EventHandlerResult:
        """Handle quality phase completed event."""
        if not event.payload.get("success", False):
            return EventHandlerResult(success=False)
        if state_flags["publishing"]:
            return EventHandlerResult(success=True)
        state_flags["publishing"] = True

        try:
            if publish_requested:
                await self._publish_event(
                    WorkflowEvent.PUBLISH_PHASE_STARTED,
                    {"workflow_id": workflow_id},
                )
                publishing_success = await self._execute_publishing_workflow(
                    options, workflow_id
                )
                await self._publish_event(
                    WorkflowEvent.PUBLISH_PHASE_COMPLETED,
                    {
                        "workflow_id": workflow_id,
                        "success": publishing_success,
                    },
                )
                if not publishing_success:
                    await self._publish_workflow_failure(
                        {"workflow_id": workflow_id}, "publishing"
                    )
                    return EventHandlerResult(success=False)
            else:
                await self._publish_event(
                    WorkflowEvent.PUBLISH_PHASE_COMPLETED,
                    {
                        "workflow_id": workflow_id,
                        "success": True,
                        "skipped": True,
                    },
                )
            return EventHandlerResult(success=True)
        except Exception as exc:  # pragma: no cover - defensive
            await self._publish_workflow_failure(
                {"workflow_id": workflow_id}, "publishing", exc
            )
            return EventHandlerResult(success=False, error_message=str(exc))

    async def _handle_publish_completed(
        self,
        event: Event,
        state_flags: dict[str, bool],
        workflow_id: str,
        options: OptionsProtocol,
        commit_requested: bool,
        publish_requested: bool,
        event_context: dict[str, t.Any],
    ) -> EventHandlerResult:
        """Handle publishing completed event."""
        if publish_requested and not event.payload.get("success", False):
            return EventHandlerResult(success=False)
        if state_flags["commit"]:
            return EventHandlerResult(success=True)
        state_flags["commit"] = True

        try:
            if commit_requested:
                await self._publish_event(
                    WorkflowEvent.COMMIT_PHASE_STARTED,
                    {"workflow_id": workflow_id},
                )
                commit_success = await self._execute_commit_workflow(
                    options, workflow_id
                )
                await self._publish_event(
                    WorkflowEvent.COMMIT_PHASE_COMPLETED,
                    {
                        "workflow_id": workflow_id,
                        "success": commit_success,
                    },
                )
                if not commit_success:
                    await self._publish_workflow_failure(
                        {"workflow_id": workflow_id}, "commit"
                    )
                    return EventHandlerResult(success=False)
            else:
                await self._publish_event(
                    WorkflowEvent.COMMIT_PHASE_COMPLETED,
                    {
                        "workflow_id": workflow_id,
                        "success": True,
                        "skipped": True,
                    },
                )

            await self._publish_event(
                WorkflowEvent.WORKFLOW_COMPLETED,
                event_context | {"success": True},
            )
            return EventHandlerResult(success=True)
        except Exception as exc:  # pragma: no cover - defensive
            await self._publish_workflow_failure(
                {"workflow_id": workflow_id}, "commit", exc
            )
            return EventHandlerResult(success=False, error_message=str(exc))

    async def _handle_workflow_completed(
        self,
        event: Event,
        start_time: float,
        workflow_id: str,
        completion_future: asyncio.Future[bool],
        subscriptions: list[str],
    ) -> EventHandlerResult:
        """Handle workflow completed event."""
        return await self._finalize_workflow(
            start_time,
            workflow_id,
            True,
            completion_future,
            subscriptions,
            event.payload,
        )

    async def _handle_workflow_failed(
        self,
        event: Event,
        start_time: float,
        workflow_id: str,
        completion_future: asyncio.Future[bool],
        subscriptions: list[str],
    ) -> EventHandlerResult:
        """Handle workflow failed event."""
        return await self._finalize_workflow(
            start_time,
            workflow_id,
            False,
            completion_future,
            subscriptions,
            event.payload,
        )

    async def _run_event_driven_workflow(
        self,
        options: OptionsProtocol,
        workflow_id: str,
        event_context: dict[str, t.Any],
        start_time: float,
    ) -> bool:
        if not self._event_bus:
            raise RuntimeError("Workflow event bus is not configured.")

        loop = asyncio.get_running_loop()
        completion_future: asyncio.Future[bool] = loop.create_future()
        subscriptions: list[str] = []

        publish_requested = bool(
            getattr(options, "publish", False) or getattr(options, "all", False)
        )
        commit_requested = bool(getattr(options, "commit", False))

        state_flags = {
            "configuration": False,
            "quality": False,
            "publishing": False,
            "commit": False,
        }

        # Subscribe to events
        async def on_session_ready(event: Event) -> EventHandlerResult:
            return await self._handle_session_ready(
                event, state_flags, workflow_id, options
            )

        async def on_config_completed(event: Event) -> EventHandlerResult:
            return await self._handle_config_completed(
                event, state_flags, workflow_id, options
            )

        async def on_quality_completed(event: Event) -> EventHandlerResult:
            return await self._handle_quality_completed(
                event, state_flags, workflow_id, options, publish_requested
            )

        async def on_publish_completed(event: Event) -> EventHandlerResult:
            return await self._handle_publish_completed(
                event,
                state_flags,
                workflow_id,
                options,
                commit_requested,
                publish_requested,
                event_context,
            )

        async def on_workflow_completed(event: Event) -> EventHandlerResult:
            return await self._handle_workflow_completed(
                event, start_time, workflow_id, completion_future, subscriptions
            )

        async def on_workflow_failed(event: Event) -> EventHandlerResult:
            return await self._handle_workflow_failed(
                event, start_time, workflow_id, completion_future, subscriptions
            )

        subscriptions.extend(
            (
                self._event_bus.subscribe(
                    WorkflowEvent.WORKFLOW_SESSION_READY,
                    on_session_ready,
                ),
                self._event_bus.subscribe(
                    WorkflowEvent.CONFIG_PHASE_COMPLETED,
                    on_config_completed,
                ),
                self._event_bus.subscribe(
                    WorkflowEvent.QUALITY_PHASE_COMPLETED,
                    on_quality_completed,
                ),
                self._event_bus.subscribe(
                    WorkflowEvent.PUBLISH_PHASE_COMPLETED,
                    on_publish_completed,
                ),
                self._event_bus.subscribe(
                    WorkflowEvent.WORKFLOW_COMPLETED,
                    on_workflow_completed,
                ),
                self._event_bus.subscribe(
                    WorkflowEvent.WORKFLOW_FAILED,
                    on_workflow_failed,
                ),
            )
        )

        try:
            await self._publish_event(
                WorkflowEvent.WORKFLOW_SESSION_INITIALIZING,
                event_context,
            )
            self._session_controller.initialize(options)
            await self._publish_event(
                WorkflowEvent.WORKFLOW_SESSION_READY,
                event_context,
            )
        except Exception as exc:  # pragma: no cover - defensive
            await self._publish_workflow_failure(
                event_context, "session_initialization", exc
            )
            await self._finalize_workflow(
                start_time, workflow_id, False, completion_future, subscriptions
            )
            return False

        return await completion_future

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
        success = await self._phase_executor._execute_workflow_phases(
            options, workflow_id
        )
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
                f"[green]⚡[/green] {result.test_name}:"
                f" {result.time_improvement_percentage:.1f}% faster"
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

    def _run_initial_fast_hooks(self, options: OptionsProtocol, iteration: int) -> bool:
        fast_hooks_passed = self._phase_executor._run_fast_hooks_phase(options)
        if not fast_hooks_passed:
            if options.ai_agent and self._should_debug():
                self.debugger.log_iteration_end(iteration, False)
            return False
        return True

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

    def _execute_standard_hooks_workflow(self, options: OptionsProtocol) -> bool:
        self._phase_executor._update_hooks_status_running()

        if not self._execute_fast_hooks_workflow(options):
            self._phase_executor._handle_hooks_completion(False)
            return False

        if not self._execute_cleaning_workflow_if_needed(options):
            self._phase_executor._handle_hooks_completion(False)
            return False

        comprehensive_success = self._phase_executor._run_comprehensive_hooks_phase(
            options
        )
        self._phase_executor._handle_hooks_completion(comprehensive_success)

        return comprehensive_success

    def _execute_fast_hooks_workflow(self, options: OptionsProtocol) -> bool:
        """Execute fast hooks phase."""
        return self._phase_executor._run_fast_hooks_phase(options)

    def _execute_cleaning_workflow_if_needed(self, options: OptionsProtocol) -> bool:
        """Execute cleaning workflow if requested."""
        if not getattr(options, "clean", False):
            return True

        if not self._phase_executor._run_code_cleaning_phase(options):
            return False

        if not self._phase_executor._run_post_cleaning_fast_hooks(options):
            return False

        self._phase_executor._mark_code_cleaning_complete()
        return True

    def _is_publishing_workflow(self, options: OptionsProtocol) -> bool:
        """Check if this is a publishing workflow."""
        return bool(
            getattr(options, "publish", False) or getattr(options, "all", False)
        )

    def _update_mcp_status(self, phase: str, status: str) -> None:
        """Update MCP (Model Context Protocol) status."""
        # Check if _mcp_state_manager exists and is not None
        mcp_state_manager = getattr(self, "_mcp_state_manager", None)
        if mcp_state_manager:
            try:
                mcp_state_manager.update_status(phase, status)
            except (AttributeError, TypeError, RuntimeError) as e:
                # If MCP is not available or fails, continue without error
                self.logger.debug(f"MCP status update failed: {e}")

    async def _execute_quality_phase(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
        """Execute the quality phase of the workflow."""
        try:
            # Check if this is a publishing workflow
            is_publishing = self._is_publishing_workflow(options)

            # Run fast hooks phase first
            fast_success = self.phases.run_fast_hooks_only(options)
            if not fast_success and is_publishing:
                return False  # For publishing workflows, fast hook failures should stop execution

            # Run comprehensive hooks phase
            comprehensive_success = self.phases.run_comprehensive_hooks_only(options)
            if not comprehensive_success and is_publishing:
                return False  # For publishing workflows, comprehensive hook failures should stop execution

            # Both fast and comprehensive hooks must pass for success
            quality_success = fast_success and comprehensive_success

            # Run testing phase if requested
            if getattr(options, "test", False):
                testing_success = self.phases.run_testing_phase(options)
                if not testing_success and is_publishing:
                    return False  # For publishing workflows, test failures should stop execution
                # For non-publishing workflows, testing failures should factor into overall success too
                quality_success = quality_success and testing_success

            return quality_success
        except Exception as e:
            self.logger.error(f"Quality phase execution failed: {e}")
            return False

    async def _execute_publishing_workflow(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
        """Execute the publishing workflow phase."""
        try:
            # Run publishing phase
            publishing_success = self.phases.run_publishing_phase(options)
            return publishing_success
        except Exception as e:
            self.logger.error(f"Publishing workflow execution failed: {e}")
            return False

    async def _execute_commit_workflow(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
        """Execute the commit workflow phase."""
        try:
            # Run commit phase
            commit_success = self.phases.run_commit_phase(options)
            return commit_success
        except Exception as e:
            self.logger.error(f"Commit workflow execution failed: {e}")
            return False

    def _has_code_cleaning_run(self) -> bool:
        """Check if code cleaning has already run in this session."""
        # Check session metadata or a dedicated flag
        if (
            self.session.session_tracker
            and "code_cleaning_completed" in self.session.session_tracker.metadata
        ):
            return bool(
                self.session.session_tracker.metadata["code_cleaning_completed"]
            )
        return False

    def _mark_code_cleaning_complete(self) -> None:
        """Mark that code cleaning has been completed."""
        if self.session.session_tracker:
            self.session.session_tracker.metadata["code_cleaning_completed"] = True

    def _run_code_cleaning_phase(self, options: OptionsProtocol) -> bool:
        """Execute code cleaning phase - wrapper for ACB workflow compatibility."""
        result: bool = self.phases.run_cleaning_phase(options)  # type: ignore[arg-type,assignment]
        return result

    def _run_post_cleaning_fast_hooks(self, options: OptionsProtocol) -> bool:
        """Run fast hooks after code cleaning phase."""
        result: bool = self.phases.run_fast_hooks_only(options)  # type: ignore[arg-type,assignment]
        return result

    def _run_fast_hooks_phase(self, options: OptionsProtocol) -> bool:
        """Execute fast hooks phase - wrapper for ACB workflow compatibility."""
        result: bool = self.phases.run_fast_hooks_only(options)  # type: ignore[arg-type,assignment]
        return result

    def _run_comprehensive_hooks_phase(self, options: OptionsProtocol) -> bool:
        """Execute comprehensive hooks phase - wrapper for ACB workflow compatibility."""
        result: bool = self.phases.run_comprehensive_hooks_only(options)  # type: ignore[arg-type,assignment]
        return result

    def _run_testing_phase(self, options: OptionsProtocol) -> bool:
        """Execute testing phase - wrapper for ACB workflow compatibility."""
        result: bool = self.phases.run_testing_phase(options)  # type: ignore[arg-type,assignment]
        return result

    def _configure_session_cleanup(self, options: OptionsProtocol) -> None:
        """Configure session cleanup handlers."""
        # Add any necessary session cleanup configuration here
        self.session.register_cleanup(self._cleanup_workflow_resources)
        if hasattr(self, "_mcp_state_manager") and self._mcp_state_manager:
            self.session.register_cleanup(self._mcp_state_manager.cleanup)

    def _initialize_zuban_lsp(self, options: OptionsProtocol) -> None:
        """Initialize Zuban LSP server if needed."""
        # Placeholder implementation - actual LSP initialization would go here
        pass

    def _configure_hook_manager_lsp(self, options: OptionsProtocol) -> None:
        """Configure hook manager LSP settings."""
        # Placeholder implementation - actual hook manager LSP configuration would go here
        pass

    def _register_lsp_cleanup_handler(self, options: OptionsProtocol) -> None:
        """Register LSP cleanup handler."""
        # Placeholder implementation - actual LSP cleanup handler would go here
        pass

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
        # Always log this important phase start for AI consumption
        self.logger.info(
            "AI agent fixing phase started",
            ai_agent_fixing=True,
            event_type="ai_fix_init",
        )
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
    ) -> tuple[EnhancedAgentCoordinator, list[t.Any]]:
        agent_coordinator = self._setup_agent_coordinator()
        issues = await self._collect_issues_from_failures()
        return agent_coordinator, issues

    async def _execute_ai_fixes(
        self,
        options: OptionsProtocol,
        agent_coordinator: EnhancedAgentCoordinator,
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
            # Log structured data to stderr for AI consumption
            self.logger.info(
                "AI agent fixing phase started",
                ai_agent_fixing=True,
                event_type="ai_fix_start",
            )

    def _setup_agent_coordinator(self) -> EnhancedAgentCoordinator:
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

    def _workflow_context(
        self,
        workflow_id: str,
        options: OptionsProtocol,
    ) -> dict[str, t.Any]:
        """Build a consistent payload for workflow-level events."""
        return {
            "workflow_id": workflow_id,
            "test_mode": getattr(options, "test", False),
            "skip_hooks": getattr(options, "skip_hooks", False),
            "publish": getattr(options, "publish", False),
            "all": getattr(options, "all", False),
            "commit": getattr(options, "commit", False),
            "ai_agent": getattr(options, "ai_agent", False),
        }

    async def _publish_event(
        self, event: WorkflowEvent, payload: dict[str, t.Any]
    ) -> None:
        """Publish workflow events when the bus is available."""
        if not getattr(self, "_event_bus", None):
            return

        try:
            await self._event_bus.publish(event, payload)  # type: ignore[union-attr]
        except Exception as exc:  # pragma: no cover - logging only
            self.logger.debug(
                "Failed to publish workflow event",
                extra={"event": event.value, "error": str(exc)},
            )


class WorkflowOrchestrator:
    def __init__(
        self,
        pkg_path: Path | None = None,
        dry_run: bool = False,
        web_job_id: str | None = None,
        verbose: bool = False,
        debug: bool = False,
        changed_only: bool = False,
    ) -> None:
        # Initialize console and pkg_path first
        from acb.console import Console

        self.console = depends.get_sync(Console)
        self.pkg_path = pkg_path or Path.cwd()
        self.dry_run = dry_run
        self.web_job_id = web_job_id
        self.verbose = verbose
        self.debug = debug
        self.changed_only = changed_only

        # Import protocols for retrieving dependencies via ACB
        from crackerjack.models.protocols import (
            ConfigMergeServiceProtocol,
            FileSystemInterface,
            GitInterface,
            HookManager,
            PublishManager,
            TestManagerProtocol,
        )

        # Setup services with ACB DI
        self._setup_acb_services()

        self._initialize_logging()

        self.logger = depends.get_sync(LoggerProtocol)

        # Create coordinators - dependencies retrieved via ACB's depends.get_sync()
        self.session = SessionCoordinator(self.console, self.pkg_path, self.web_job_id)

        # Register SessionCoordinator in DI for WorkflowPipeline injection
        depends.set(SessionCoordinator, self.session)

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

        # Register PhaseCoordinator in DI for WorkflowPipeline injection
        depends.set(PhaseCoordinator, self.phases)

        # WorkflowPipeline uses @depends.inject, so all parameters are auto-injected
        self.pipeline = WorkflowPipeline()

    def _setup_acb_services(self) -> None:
        """Setup all services using ACB dependency injection."""
        self._register_filesystem_and_git_services()
        self._register_manager_services()
        self._register_core_services()
        self._register_quality_services()
        self._register_monitoring_services()
        self._setup_event_system()

    def _register_filesystem_and_git_services(self) -> None:
        """Register filesystem and git services."""
        from acb.depends import depends

        from crackerjack.models.protocols import (
            FileSystemInterface,
            GitInterface,
            GitServiceProtocol,
        )
        from crackerjack.services.enhanced_filesystem import EnhancedFileSystemService
        from crackerjack.services.git import GitService

        filesystem = EnhancedFileSystemService()
        depends.set(FileSystemInterface, filesystem)

        git_service = GitService(self.pkg_path)
        depends.set(GitInterface, git_service)
        depends.set(GitServiceProtocol, git_service)

    def _register_manager_services(self) -> None:
        """Register hook, test, and publish managers."""
        from acb.depends import depends

        from crackerjack.managers.hook_manager import HookManagerImpl
        from crackerjack.managers.publish_manager import PublishManagerImpl
        from crackerjack.managers.test_manager import TestManager
        from crackerjack.models.protocols import (
            HookManager,
            PublishManager,
            TestManagerProtocol,
        )

        hook_manager = HookManagerImpl(
            self.pkg_path,
            verbose=self.verbose,
            debug=self.debug,
            use_incremental=self.changed_only,
        )
        depends.set(HookManager, hook_manager)

        test_manager = TestManager()
        depends.set(TestManagerProtocol, test_manager)

        publish_manager = PublishManagerImpl()
        depends.set(PublishManager, publish_manager)

    def _register_core_services(self) -> None:
        """Register core configuration and security services."""
        from acb.depends import depends

        from crackerjack.executors.hook_lock_manager import HookLockManager
        from crackerjack.models.protocols import (
            ConfigIntegrityServiceProtocol,
            ConfigMergeServiceProtocol,
            EnhancedFileSystemServiceProtocol,
            HookLockManagerProtocol,
            SecurityServiceProtocol,
            SmartSchedulingServiceProtocol,
            UnifiedConfigurationServiceProtocol,
        )
        from crackerjack.services.cache import CrackerjackCache
        from crackerjack.services.config_integrity import ConfigIntegrityService
        from crackerjack.services.config_merge import ConfigMergeService
        from crackerjack.services.enhanced_filesystem import EnhancedFileSystemService
        from crackerjack.services.security import SecurityService
        from crackerjack.services.smart_scheduling import SmartSchedulingService
        from crackerjack.services.unified_config import UnifiedConfigurationService

        depends.set(
            UnifiedConfigurationServiceProtocol,
            UnifiedConfigurationService(pkg_path=self.pkg_path),
        )
        depends.set(
            ConfigIntegrityServiceProtocol,
            ConfigIntegrityService(project_path=self.pkg_path),
        )
        depends.set(ConfigMergeServiceProtocol, ConfigMergeService())
        depends.set(
            SmartSchedulingServiceProtocol,
            SmartSchedulingService(project_path=self.pkg_path),
        )
        depends.set(EnhancedFileSystemServiceProtocol, EnhancedFileSystemService())
        depends.set(SecurityServiceProtocol, SecurityService())
        depends.set(HookLockManagerProtocol, HookLockManager())
        depends.set(CrackerjackCache, CrackerjackCache())

    def _register_quality_services(self) -> None:
        """Register coverage, version analysis, and code quality services."""
        from acb.depends import depends

        from crackerjack.models.protocols import (
            ChangelogGeneratorProtocol,
            CoverageBadgeServiceProtocol,
            CoverageRatchetProtocol,
            GitInterface,
            RegexPatternsProtocol,
            VersionAnalyzerProtocol,
        )
        from crackerjack.services.changelog_automation import ChangelogGenerator
        from crackerjack.services.coverage_badge_service import CoverageBadgeService
        from crackerjack.services.coverage_ratchet import CoverageRatchetService
        from crackerjack.services.regex_patterns import RegexPatternsService
        from crackerjack.services.version_analyzer import VersionAnalyzer

        coverage_ratchet = CoverageRatchetService(self.pkg_path)
        depends.set(CoverageRatchetProtocol, coverage_ratchet)

        coverage_badge = CoverageBadgeService(project_root=self.pkg_path)
        depends.set(CoverageBadgeServiceProtocol, coverage_badge)

        git_service = depends.get_sync(GitInterface)
        version_analyzer = VersionAnalyzer(git_service=git_service)
        depends.set(VersionAnalyzerProtocol, version_analyzer)

        changelog_generator = ChangelogGenerator()
        depends.set(ChangelogGeneratorProtocol, changelog_generator)

        regex_patterns = RegexPatternsService()
        depends.set(RegexPatternsProtocol, regex_patterns)

    def _register_monitoring_services(self) -> None:
        """Register performance monitoring and benchmarking services."""
        from acb.depends import depends
        from acb.logger import Logger

        from crackerjack.models.protocols import PerformanceBenchmarkProtocol
        from crackerjack.services.monitoring.performance_benchmarks import (
            PerformanceBenchmarkService,
        )

        performance_benchmarks = PerformanceBenchmarkService(
            console=self.console,
            logger=depends.get_sync(Logger),
            pkg_path=self.pkg_path,
        )
        depends.set(PerformanceBenchmarkProtocol, performance_benchmarks)

    def _setup_event_system(self) -> None:
        """Setup event bus and telemetry."""
        from acb.depends import depends

        from crackerjack.events import (
            WorkflowEventBus,
            WorkflowEventTelemetry,
            register_default_subscribers,
        )

        default_state_dir = Path.home() / ".crackerjack" / "state"
        default_state_dir.mkdir(parents=True, exist_ok=True)

        event_bus = WorkflowEventBus()
        telemetry_state_file = default_state_dir / "workflow_events.json"
        telemetry = WorkflowEventTelemetry(state_file=telemetry_state_file)
        register_default_subscribers(event_bus, telemetry)

        depends.set(WorkflowEventBus, event_bus)
        depends.set(WorkflowEventTelemetry, telemetry)

    def _initialize_logging(self) -> None:
        from crackerjack.services.log_manager import get_log_manager
        from crackerjack.services.logging import setup_structured_logging

        log_manager = get_log_manager()
        session_id = getattr(self, "web_job_id", None) or str(int(time.time()))[:8]
        debug_log_file = log_manager.create_debug_log_file(session_id)

        log_level = "DEBUG" if self.debug else "INFO"
        setup_structured_logging(
            level=log_level, json_output=False, log_file=debug_log_file
        )

        temp_logger = depends.get_sync(LoggerProtocol)
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
        result: bool = self.phases.run_cleaning_phase(options)  # type: ignore[arg-type,assignment]
        return result

    def run_fast_hooks_only(self, options: OptionsProtocol) -> bool:
        result: bool = self.phases.run_fast_hooks_only(options)  # type: ignore[arg-type,assignment]
        return result

    def run_comprehensive_hooks_only(self, options: OptionsProtocol) -> bool:
        result: bool = self.phases.run_comprehensive_hooks_only(options)  # type: ignore[arg-type,assignment]
        return result

    def run_hooks_phase(self, options: OptionsProtocol) -> bool:
        result: bool = self.phases.run_hooks_phase(options)  # type: ignore[arg-type,assignment]
        return result

    def run_testing_phase(self, options: OptionsProtocol) -> bool:
        result: bool = self.phases.run_testing_phase(options)  # type: ignore[arg-type,assignment]
        return result

    def run_publishing_phase(self, options: OptionsProtocol) -> bool:
        result: bool = self.phases.run_publishing_phase(options)  # type: ignore[arg-type,assignment]
        return result

    def run_commit_phase(self, options: OptionsProtocol) -> bool:
        result: bool = self.phases.run_commit_phase(options)  # type: ignore[arg-type,assignment]
        return result

    def run_configuration_phase(self, options: OptionsProtocol) -> bool:
        result: bool = self.phases.run_configuration_phase(options)  # type: ignore[arg-type,assignment]
        return result

    async def run_complete_workflow(self, options: OptionsProtocol) -> bool:
        result: bool = await self.pipeline.run_complete_workflow(options)
        # Ensure we properly clean up any pending tasks before finishing
        await self._cleanup_pending_tasks()
        return result

    async def _cleanup_pending_tasks(self) -> None:
        """Clean up any remaining asyncio tasks before event loop closes."""
        # First call the pipeline cleanup methods if they exist
        await self._cleanup_pipeline_executors()

        # Then handle general asyncio task cleanup
        await self._cleanup_remaining_tasks()

    async def _cleanup_pipeline_executors(self) -> None:
        """Clean up specific pipeline executors."""
        with suppress(Exception):
            # Try to call specific async cleanup methods on executors/pipeline if they exist
            if hasattr(self, "pipeline") and hasattr(self.pipeline, "phases"):
                await self._cleanup_executor_if_exists(
                    self.pipeline.phases, "_parallel_executor"
                )
                await self._cleanup_executor_if_exists(
                    self.pipeline.phases, "_async_executor"
                )

    async def _cleanup_executor_if_exists(
        self, phases_obj: t.Any, executor_attr: str
    ) -> None:
        """Clean up an executor if it exists and has the required cleanup method."""
        if hasattr(phases_obj, executor_attr):
            executor = getattr(phases_obj, executor_attr)
            if hasattr(executor, "async_cleanup"):
                await executor.async_cleanup()

    async def _cleanup_remaining_tasks(self) -> None:
        """Clean up any remaining asyncio tasks."""
        with suppress(RuntimeError):
            loop = asyncio.get_running_loop()
            # Get all pending tasks
            pending_tasks = [
                task for task in asyncio.all_tasks(loop) if not task.done()
            ]
            await self._cancel_pending_tasks(pending_tasks)

    async def _cancel_pending_tasks(self, pending_tasks: list) -> None:
        """Cancel pending tasks with proper error handling."""
        for task in pending_tasks:
            if not task.done():
                try:
                    task.cancel()
                    # Wait a short time for cancellation to complete
                    await asyncio.wait_for(task, timeout=0.1)
                except (TimeoutError, asyncio.CancelledError):
                    # Task was cancelled or couldn't finish in time, continue
                    pass
                except RuntimeError as e:
                    # Catch the specific error when event loop is closed during task cancellation
                    if "Event loop is closed" in str(e):
                        # Event loop was closed while trying to cancel tasks, just return
                        return
                    else:
                        # Re-raise other RuntimeErrors
                        raise

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
            return version("crackerjack")
        except Exception:
            return "unknown"

    async def process(self, options: OptionsProtocol) -> bool:
        self.session.start_session("process_workflow")

        try:
            result = await self.run_complete_workflow(options)
            return self._finalize_session_with_result(result)
        except Exception:
            return self._finalize_session_on_exception()

    def _finalize_session_with_result(self, result: bool) -> bool:
        """Finalize session with the workflow result."""
        self.session.end_session(success=result)
        return result

    def _finalize_session_on_exception(self) -> bool:
        """Finalize session when an exception occurs."""
        self.session.end_session(success=False)
        return False
