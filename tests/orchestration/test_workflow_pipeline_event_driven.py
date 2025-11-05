from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest
from rich.console import Console

from acb.events import EventHandlerResult

from crackerjack.core.workflow_orchestrator import WorkflowPipeline
from crackerjack.events import WorkflowEvent, WorkflowEventBus


async def _noop_async(*_: Any, **__: Any) -> None:
    return None


def _build_pipeline(
    *,
    config_result: bool = True,
    quality_result: bool = True,
    publish_result: bool = True,
    commit_result: bool = True,
) -> WorkflowPipeline:
    pipeline = WorkflowPipeline.__new__(WorkflowPipeline)

    # Minimal surface for pipeline dependencies
    class DummySession:
        def initialize_session_tracking(self, options: Any) -> None:
            self._initialized = True

        def track_task(self, *_: Any, **__: Any) -> None:
            pass

        def finalize_session(self, *_: Any, **__: Any) -> None:
            pass

        def cleanup_resources(self) -> None:
            pass

        def register_cleanup(self, *_: Any, **__: Any) -> None:
            pass

        def set_cleanup_config(self, *_: Any, **__: Any) -> None:
            pass

        def fail_task(self, *_: Any, **__: Any) -> None:
            pass

    class DummyPhases:
        def run_configuration_phase(self, options: Any) -> bool:
            return config_result

    pipeline.console = Console(force_terminal=False)
    pipeline.pkg_path = SimpleNamespace()
    pipeline.session = DummySession()
    pipeline.phases = DummyPhases()
    pipeline._memory_optimizer = SimpleNamespace(optimize_memory=lambda: None)
    pipeline._cache = SimpleNamespace(start=_noop_async, stop=_noop_async)
    pipeline._performance_monitor = SimpleNamespace(
        start_workflow=lambda workflow_id: None,
        end_workflow=lambda workflow_id, success: SimpleNamespace(
            performance_score=100.0,
            total_duration_seconds=0.1,
        ),
    )
    pipeline._generate_performance_benchmark_report = _noop_async
    pipeline._event_bus = WorkflowEventBus()
    pipeline._quality_intelligence = None
    pipeline._performance_benchmarks = None
    # Minimal logger stub
    pipeline.logger = SimpleNamespace(
        info=lambda *_args, **_kwargs: None,
        debug=lambda *_args, **_kwargs: None,
        warning=lambda *_args, **_kwargs: None,
        exception=lambda *_args, **_kwargs: None,
    )

    pipeline._log_workflow_startup_debug = lambda *_: None
    pipeline._configure_session_cleanup = lambda *_: None
    pipeline._initialize_zuban_lsp = lambda *_: None
    pipeline._configure_hook_manager_lsp = lambda *_: None
    pipeline._register_lsp_cleanup_handler = lambda *_: None
    pipeline._log_workflow_startup_info = lambda *_: None
    pipeline._should_debug = lambda: False

    def fake_initialize(self: WorkflowPipeline, opts: Any) -> None:
        self.session.initialize_session_tracking(opts)

    async def fake_quality(self: WorkflowPipeline, *_: Any) -> bool:
        return quality_result

    async def fake_publish(self: WorkflowPipeline, *_: Any) -> bool:
        return publish_result

    async def fake_commit(self: WorkflowPipeline, *_: Any) -> bool:
        return commit_result

    pipeline._initialize_workflow_session = fake_initialize.__get__(pipeline)
    # Session controller shim for current event-driven workflow
    pipeline._session_controller = SimpleNamespace(
        initialize=pipeline._initialize_workflow_session
    )
    pipeline._execute_quality_phase = fake_quality.__get__(pipeline)
    pipeline._execute_publishing_workflow = fake_publish.__get__(pipeline)
    pipeline._execute_commit_workflow = fake_commit.__get__(pipeline)

    return pipeline


@pytest.mark.asyncio
async def test_event_driven_workflow_success() -> None:
    pipeline = _build_pipeline()
    events: list[str] = []

    async def capture(event) -> EventHandlerResult:
        events.append(event.metadata.event_type)
        return EventHandlerResult(success=True)

    pipeline._event_bus.subscribe(None, capture)

    options = SimpleNamespace(
        test=False,
        skip_hooks=False,
        publish=False,
        all=False,
        commit=False,
    )

    result = await pipeline.run_complete_workflow(options)

    assert result is True
    assert WorkflowEvent.WORKFLOW_COMPLETED.value in events
    assert WorkflowEvent.WORKFLOW_FAILED.value not in events


@pytest.mark.asyncio
async def test_event_driven_workflow_configuration_failure() -> None:
    pipeline = _build_pipeline(config_result=False)
    failure_events: list[str] = []

    async def capture_failure(event) -> EventHandlerResult:
        failure_events.append(event.metadata.event_type)
        return EventHandlerResult(success=True)

    pipeline._event_bus.subscribe(None, capture_failure)

    options = SimpleNamespace(
        test=False,
        skip_hooks=False,
        publish=False,
        all=False,
        commit=False,
    )

    result = await pipeline.run_complete_workflow(options)

    assert result is False
    assert WorkflowEvent.WORKFLOW_FAILED.value in failure_events
