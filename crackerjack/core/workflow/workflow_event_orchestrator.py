"""Event-driven workflow orchestration and logging.

Manages workflow execution via event bus and provides comprehensive logging/metrics.
"""

from __future__ import annotations

import asyncio
import time
import typing as t

from acb.console import Console
from acb.depends import Inject, depends
from acb.events import Event, EventHandlerResult

from crackerjack.events import WorkflowEvent, WorkflowEventBus
from crackerjack.models.protocols import (
    DebugServiceProtocol,
    LoggerProtocol,
    MemoryOptimizerProtocol,
    OptionsProtocol,
    PerformanceBenchmarkProtocol,
    PerformanceCacheProtocol,
    PerformanceMonitorProtocol,
)
from crackerjack.services.logging import LoggingContext
from crackerjack.services.memory_optimizer import memory_optimized

if t.TYPE_CHECKING:
    from crackerjack.core.phase_coordinator import PhaseCoordinator
    from crackerjack.core.session_coordinator import (
        SessionController,
        SessionCoordinator,
    )


class WorkflowEventOrchestrator:
    """Orchestrates workflow execution via event-driven architecture and logging."""

    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        logger: Inject[LoggerProtocol],
        performance_monitor: Inject[PerformanceMonitorProtocol],
        memory_optimizer: Inject[MemoryOptimizerProtocol],
        performance_cache: Inject[PerformanceCacheProtocol],
        debugger: Inject[DebugServiceProtocol],
        event_bus: Inject[WorkflowEventBus] | None = None,
        performance_benchmarks: Inject[PerformanceBenchmarkProtocol] | None = None,
    ) -> None:
        """Initialize event orchestrator with ACB dependency injection.

        Args:
            console: Rich console for output
            logger: Structured logging service
            performance_monitor: Performance tracking service
            memory_optimizer: Memory optimization service
            performance_cache: Performance caching service
            debugger: Debug service for workflow diagnostics
            event_bus: Optional event bus for event-driven execution
            performance_benchmarks: Optional performance benchmarking service
        """
        self.console = console
        self.logger = logger
        self._performance_monitor = performance_monitor
        self._memory_optimizer = memory_optimizer
        self._cache = performance_cache
        self.debugger = debugger
        self._event_bus = event_bus
        self._performance_benchmarks = performance_benchmarks

        # References to workflow components (set by WorkflowPipeline)
        self.session: SessionCoordinator | None = None
        self.phases: PhaseCoordinator | None = None
        self._session_controller: SessionController | None = None
        self._workflow_pipeline: t.Any = None  # Reference to parent pipeline

    def set_workflow_components(
        self,
        session: SessionCoordinator,
        phases: PhaseCoordinator,
        session_controller: SessionController,
        workflow_pipeline: t.Any,
    ) -> None:
        """Set workflow component references after initialization.

        Args:
            session: Session coordinator for workflow session management
            phases: Phase coordinator for workflow phase execution
            session_controller: Session controller for session operations
            workflow_pipeline: Parent workflow pipeline for calling non-extracted methods
        """
        self.session = session
        self.phases = phases
        self._session_controller = session_controller
        self._workflow_pipeline = workflow_pipeline

    # ========================================
    # Event-Driven Workflow Execution
    # ========================================

    def _should_debug(self) -> bool:
        """Check if debug mode is enabled via environment variable."""
        import os

        return os.environ.get("AI_AGENT_DEBUG", "0") == "1"

    @memory_optimized
    async def run_complete_workflow(self, options: OptionsProtocol) -> bool:
        """Execute complete workflow with event-driven architecture.

        Args:
            options: Workflow execution options

        Returns:
            True if workflow succeeded, False otherwise
        """
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
        """Execute the workflow either event-driven or sequentially.

        Args:
            options: Workflow execution options
            workflow_id: Unique workflow identifier
            event_context: Event context data
            start_time: Workflow start timestamp

        Returns:
            True if workflow succeeded, False otherwise
        """
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
        """Execute the workflow sequentially without event bus.

        Args:
            options: Workflow execution options
            workflow_id: Unique workflow identifier
            event_context: Event context data
            start_time: Workflow start timestamp

        Returns:
            True if workflow succeeded, False otherwise
        """
        await self._publish_event(
            WorkflowEvent.WORKFLOW_SESSION_INITIALIZING,
            event_context,
        )
        if self._session_controller:
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
        """Handle keyboard interrupt during workflow execution.

        Args:
            workflow_id: Unique workflow identifier
            event_context: Event context data

        Returns:
            False (workflow failed due to interruption)
        """
        self._performance_monitor.end_workflow(workflow_id, False)
        await self._publish_event(
            WorkflowEvent.WORKFLOW_INTERRUPTED,
            event_context,
        )
        return self._handle_user_interruption()

    async def _handle_general_exception(
        self, e: Exception, workflow_id: str, event_context: dict[str, t.Any]
    ) -> bool:
        """Handle general exceptions during workflow execution.

        Args:
            e: Exception that occurred
            workflow_id: Unique workflow identifier
            event_context: Event context data

        Returns:
            False (workflow failed due to exception)
        """
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
        if self.session:
            self.session.cleanup_resources()
        self._memory_optimizer.optimize_memory()
        await self._cache.stop()

    def _unsubscribe_all_subscriptions(self, subscriptions: list[str]) -> None:
        """Unsubscribe from all event subscriptions.

        Args:
            subscriptions: List of subscription IDs to unsubscribe
        """
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
        """Finalize the workflow execution.

        Args:
            start_time: Workflow start timestamp
            workflow_id: Unique workflow identifier
            success: Whether workflow succeeded
            completion_future: Future to set with result
            subscriptions: List of event subscriptions to clean up
            payload: Optional event payload data

        Returns:
            EventHandlerResult with success status
        """
        if completion_future.done():
            return EventHandlerResult(success=success)

        if self.session:
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
        """Publish workflow failure event.

        Args:
            event_context: Event context data
            stage: Workflow stage where failure occurred
            error: Optional exception that caused failure
        """
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
        """Handle session ready event.

        Args:
            event: Session ready event
            state_flags: Workflow state tracking flags
            workflow_id: Unique workflow identifier
            options: Workflow execution options

        Returns:
            EventHandlerResult with configuration phase status
        """
        if state_flags["configuration"]:
            return EventHandlerResult(success=True)
        state_flags["configuration"] = True

        try:
            await self._publish_event(
                WorkflowEvent.CONFIG_PHASE_STARTED,
                {"workflow_id": workflow_id},
            )
            config_success = await asyncio.to_thread(
                self.phases.run_configuration_phase,  # type: ignore[union-attr]
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
        """Handle configuration completed event.

        Args:
            event: Configuration completed event
            state_flags: Workflow state tracking flags
            workflow_id: Unique workflow identifier
            options: Workflow execution options

        Returns:
            EventHandlerResult with quality phase status
        """
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
        """Handle quality phase completed event.

        Args:
            event: Quality completed event
            state_flags: Workflow state tracking flags
            workflow_id: Unique workflow identifier
            options: Workflow execution options
            publish_requested: Whether publishing was requested

        Returns:
            EventHandlerResult with publishing phase status
        """
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
        """Handle publishing completed event.

        Args:
            event: Publishing completed event
            state_flags: Workflow state tracking flags
            workflow_id: Unique workflow identifier
            options: Workflow execution options
            commit_requested: Whether commit was requested
            publish_requested: Whether publishing was requested
            event_context: Event context data

        Returns:
            EventHandlerResult with commit phase status
        """
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
        """Handle workflow completed event.

        Args:
            event: Workflow completed event
            start_time: Workflow start timestamp
            workflow_id: Unique workflow identifier
            completion_future: Future to set with result
            subscriptions: List of event subscriptions to clean up

        Returns:
            EventHandlerResult with finalization status
        """
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
        """Handle workflow failed event.

        Args:
            event: Workflow failed event
            start_time: Workflow start timestamp
            workflow_id: Unique workflow identifier
            completion_future: Future to set with result
            subscriptions: List of event subscriptions to clean up

        Returns:
            EventHandlerResult with finalization status
        """
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
        """Execute workflow using event-driven architecture.

        Args:
            options: Workflow execution options
            workflow_id: Unique workflow identifier
            event_context: Event context data
            start_time: Workflow start timestamp

        Returns:
            True if workflow succeeded, False otherwise

        Raises:
            RuntimeError: If event bus is not configured
        """
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
            if self._session_controller:
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

    # ========================================
    # Logging and Performance Methods
    # ========================================

    def _log_workflow_startup_debug(self, options: OptionsProtocol) -> None:
        """Log workflow startup details if debug mode is enabled.

        Args:
            options: Workflow execution options
        """
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

    async def _execute_workflow_with_timing(
        self, options: OptionsProtocol, start_time: float, workflow_id: str
    ) -> bool:
        """Execute workflow phases with performance timing.

        Args:
            options: Workflow execution options
            start_time: Workflow start timestamp
            workflow_id: Unique workflow identifier

        Returns:
            True if workflow succeeded, False otherwise
        """
        # Delegate to parent pipeline for phase execution
        success = await self._workflow_pipeline._execute_workflow_phases(
            options, workflow_id
        )
        if self.session:
            self.session.finalize_session(start_time, success)

        duration = time.time() - start_time
        self._log_workflow_completion(success, duration)
        self._log_workflow_completion_debug(success, duration)
        await self._generate_performance_benchmark_report(
            workflow_id, duration, success
        )

        return success

    def _log_workflow_completion(self, success: bool, duration: float) -> None:
        """Log workflow completion status.

        Args:
            success: Whether workflow succeeded
            duration: Workflow execution duration in seconds
        """
        self.logger.info(
            "Workflow execution completed",
            success=success,
            duration_seconds=round(duration, 2),
        )

    def _log_workflow_completion_debug(self, success: bool, duration: float) -> None:
        """Log workflow completion debug information.

        Args:
            success: Whether workflow succeeded
            duration: Workflow execution duration in seconds
        """
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
        """Generate and display performance benchmark report for workflow execution.

        Args:
            workflow_id: Unique workflow identifier
            duration: Workflow execution duration in seconds
            success: Whether workflow succeeded
        """
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
        """Gather performance metrics from workflow execution.

        Args:
            workflow_id: Unique workflow identifier
            duration: Workflow execution duration in seconds
            success: Whether workflow succeeded

        Returns:
            Dictionary of performance metrics
        """
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
        """Display compact performance summary.

        Args:
            benchmark_results: Performance benchmark results
            duration: Workflow execution duration in seconds
        """
        if not benchmark_results:
            return

        self.console.print("\n[cyan]📊 Performance Benchmark Summary[/cyan]")
        self.console.print(f"Workflow Duration: [bold]{duration:.2f}s[/bold]")

        self._show_performance_improvements(benchmark_results)

    def _show_performance_improvements(self, benchmark_results: t.Any) -> None:
        """Show key performance improvements from benchmark results.

        Args:
            benchmark_results: Performance benchmark results
        """
        for result in benchmark_results.results[:3]:  # Top 3 results
            self._display_time_improvement(result)
            self._display_cache_efficiency(result)

    def _display_time_improvement(self, result: t.Any) -> None:
        """Display time improvement percentage if available.

        Args:
            result: Individual benchmark result
        """
        if result.time_improvement_percentage > 0:
            self.console.print(
                f"[green]⚡[/green] {result.test_name}:"
                f" {result.time_improvement_percentage:.1f}% faster"
            )

    def _display_cache_efficiency(self, result: t.Any) -> None:
        """Display cache hit ratio if available.

        Args:
            result: Individual benchmark result
        """
        if result.cache_hit_ratio > 0:
            self.console.print(
                f"[blue]🎯[/blue] Cache efficiency: {result.cache_hit_ratio:.0%}"
            )

    def _handle_user_interruption(self) -> bool:
        """Handle user interruption (keyboard interrupt).

        Returns:
            False (workflow failed due to interruption)
        """
        self.console.print("Interrupted by user")
        if self.session:
            self.session.fail_task("workflow", "Interrupted by user")
        self.logger.warning("Workflow interrupted by user")
        return False

    def _handle_workflow_exception(self, error: Exception) -> bool:
        """Handle workflow exception.

        Args:
            error: Exception that occurred

        Returns:
            False (workflow failed due to exception)
        """
        self.console.print(f"Error: {error}")
        if self.session:
            self.session.fail_task("workflow", f"Unexpected error: {error}")
        self.logger.exception(
            "Workflow execution failed",
            error=str(error),
            error_type=type(error).__name__,
        )
        return False

    def _show_verbose_failure_details(
        self, testing_passed: bool, comprehensive_passed: bool
    ) -> None:
        """Show verbose details about quality phase failures.

        Args:
            testing_passed: Whether testing phase passed
            comprehensive_passed: Whether comprehensive hooks passed
        """
        self.console.print(
            f"[yellow]⚠️ Quality phase results - testing_passed: {testing_passed}, comprehensive_passed: {comprehensive_passed}[/yellow]"
        )
        if not testing_passed:
            self.console.print("[yellow] → Tests reported failure[/yellow]")
        if not comprehensive_passed:
            self.console.print(
                "[yellow] → Comprehensive hooks reported failure[/yellow]"
            )

    # ========================================
    # Workflow Context and Event Publishing
    # ========================================

    def _workflow_context(
        self,
        workflow_id: str,
        options: OptionsProtocol,
    ) -> dict[str, t.Any]:
        """Build a consistent payload for workflow-level events.

        Args:
            workflow_id: Unique workflow identifier
            options: Workflow execution options

        Returns:
            Dictionary of workflow context data
        """
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
        """Publish workflow events when the bus is available.

        Args:
            event: Workflow event type to publish
            payload: Event payload data
        """
        if not getattr(self, "_event_bus", None):
            return

        try:
            await self._event_bus.publish(event, payload)  # type: ignore[union-attr]
        except Exception as exc:  # pragma: no cover - logging only
            self.logger.debug(
                "Failed to publish workflow event",
                extra={"event": event.value, "error": str(exc)},
            )

    # ========================================
    # Phase Execution Delegates
    # ========================================

    async def _execute_quality_phase(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
        """Execute quality phase via parent pipeline.

        Args:
            options: Workflow execution options
            workflow_id: Unique workflow identifier

        Returns:
            True if quality phase succeeded, False otherwise
        """
        return await self._workflow_pipeline._execute_quality_phase(
            options, workflow_id
        )

    async def _execute_publishing_workflow(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
        """Execute publishing workflow via parent pipeline.

        Args:
            options: Workflow execution options
            workflow_id: Unique workflow identifier

        Returns:
            True if publishing succeeded, False otherwise
        """
        return await self._workflow_pipeline._execute_publishing_workflow(
            options, workflow_id
        )

    async def _execute_commit_workflow(
        self, options: OptionsProtocol, workflow_id: str
    ) -> bool:
        """Execute commit workflow via parent pipeline.

        Args:
            options: Workflow execution options
            workflow_id: Unique workflow identifier

        Returns:
            True if commit succeeded, False otherwise
        """
        return await self._workflow_pipeline._execute_commit_workflow(
            options, workflow_id
        )
