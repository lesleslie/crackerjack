# ACB Workflow Integration - Phase 2 Implementation Plan

## Executive Summary

Phase 2 implements full WorkflowPipeline (WorkflowOrchestrator) integration with ACB workflows by creating a comprehensive DI container setup. This enables action handlers to call actual orchestrator methods instead of POC success responses.

**Goal**: Replace POC action handlers with real orchestrator integration while maintaining Phase 1's event bridge and feature flag patterns.

**Timeline**: 2-3 weeks (Week 1: DI setup, Week 2: Integration, Week 3: Testing & optimization)

**Success Criteria**: All action handlers call actual WorkflowPipeline methods, tests pass, \<5% performance overhead

## Dependency Analysis

### Complete Dependency Tree

Based on analysis of WorkflowPipeline and its dependencies:

```
WorkflowPipeline
├── Console (ACB) - no dependencies
├── Config (ACB) - requires root_path
├── PerformanceMonitorProtocol
├── MemoryOptimizerProtocol
├── PerformanceCacheProtocol
├── DebugServiceProtocol
├── LoggerProtocol
├── SessionCoordinator
│   ├── Console (shared)
│   ├── pkg_path: Path
│   └── web_job_id: str | None (optional)
├── PhaseCoordinator
│   ├── Console (shared)
│   ├── Logger
│   ├── MemoryOptimizerProtocol (shared)
│   ├── ParallelHookExecutor
│   ├── AsyncCommandExecutor
│   ├── GitOperationCache
│   ├── FileSystemCache
│   ├── pkg_path: Path (shared)
│   ├── session: SessionCoordinator (shared)
│   ├── filesystem: FileSystemInterface
│   ├── git_service: GitInterface
│   ├── hook_manager: HookManager
│   ├── test_manager: TestManagerProtocol
│   ├── publish_manager: PublishManager
│   └── config_merge_service: ConfigMergeServiceProtocol
├── QualityIntelligenceProtocol (optional)
├── PerformanceBenchmarkProtocol (optional)
└── WorkflowEventBus (fallback handled)
```

### Initialization Order Requirements

**Level 1 - Primitives (no dependencies):**

1. Console
1. Config (needs root_path from Options)
1. LoggerProtocol

**Level 2 - Core Services (depend on Level 1):**
4\. MemoryOptimizerProtocol (needs Console)
5\. PerformanceCacheProtocol (needs Console)
6\. DebugServiceProtocol (needs Console)
7\. PerformanceMonitorProtocol (needs Console)

**Level 3 - Filesystem & Git (depend on Level 1-2):**
8\. FileSystemInterface (needs Console)
9\. GitInterface (needs Console)
10\. FileSystemCache (needs Console)
11\. GitOperationCache (needs Console)

**Level 4 - Managers (depend on Level 1-3):**
12\. HookManager (needs Console, filesystem, git)
13\. TestManagerProtocol (needs Console, filesystem)
14\. PublishManager (needs Console, filesystem, git)
15\. ConfigMergeServiceProtocol (needs filesystem)

**Level 5 - Executors (depend on Level 1-4):**
16\. ParallelHookExecutor (needs Console, HookManager)
17\. AsyncCommandExecutor (needs Console)

**Level 6 - Coordinators (depend on all above):**
18\. SessionCoordinator (needs Console, pkg_path)
19\. PhaseCoordinator (needs everything from Level 1-5)

**Level 7 - Pipeline (depends on all above):**
20\. WorkflowPipeline (needs everything from Level 1-6)

## Implementation Strategy

### Week 1: DI Container Infrastructure

#### Task 1.1: Create WorkflowContainerBuilder

**File**: `crackerjack/workflows/container_builder.py`

**Purpose**: Centralized DI container setup with proper initialization order

**API Design**:

````python
from __future__ import annotations

import typing as t
from pathlib import Path

from acb.config import Config
from acb.console import Console
from acb.depends import depends

from crackerjack.models.protocols import OptionsProtocol


class WorkflowContainerBuilder:
    """Builds and initializes DI container for ACB workflows.

    Handles dependency registration in correct order, validates all services
    are available, and provides health checks for debugging.

    Example:
        ```python
        builder = WorkflowContainerBuilder(options)
        builder.build()  # Register all services

        # Services now available via depends.get_sync()
        pipeline = depends.get_sync(WorkflowPipeline)
        ```
    """

    def __init__(
        self,
        options: OptionsProtocol,
        console: Console | None = None,
        root_path: Path | None = None,
    ) -> None:
        """Initialize builder with options and optional overrides.

        Args:
            options: CLI options containing configuration
            console: Optional console override (for testing)
            root_path: Optional root path override (for testing)
        """
        self.options = options
        self._console = console
        self._root_path = root_path or Path.cwd()
        self._registered: set[str] = set()

    def build(self) -> None:
        """Build container by registering all services in dependency order."""
        self._register_level1_primitives()
        self._register_level2_core_services()
        self._register_level3_filesystem_git()
        self._register_level4_managers()
        self._register_level5_executors()
        self._register_level6_coordinators()
        self._register_level7_pipeline()

    def health_check(self) -> dict[str, bool]:
        """Check which services are registered and available.

        Returns:
            dict mapping service names to availability status
        """
        # Implementation checks each service with depends.get_sync()
        pass

    def _register_level1_primitives(self) -> None:
        """Register Console, Config, Logger."""
        pass

    def _register_level2_core_services(self) -> None:
        """Register MemoryOptimizer, PerformanceCache, etc."""
        pass

    # ... more levels
````

**Key Features**:

- Lazy initialization (only register when build() called)
- Health check for debugging
- Test-friendly (inject Console, root_path)
- Clear separation of registration levels
- Tracks what's been registered

#### Task 1.2: Service Registration Implementations

For each level, implement actual service creation and registration:

**Level 1 Example**:

```python
def _register_level1_primitives(self) -> None:
    """Register Console, Config, Logger."""
    # Console
    if not self._console:
        self._console = Console()
    depends.set(Console, self._console)
    self._registered.add("Console")

    # Config
    config = Config(root_path=self._root_path)
    depends.set(Config, config)
    self._registered.add("Config")

    # Logger
    from crackerjack.services.logging import get_logger

    logger = get_logger(__name__)
    depends.set(LoggerProtocol, logger)
    self._registered.add("LoggerProtocol")
```

**Level 2 Example**:

```python
def _register_level2_core_services(self) -> None:
    """Register MemoryOptimizer, PerformanceCache, etc."""
    from crackerjack.services.memory_optimizer import MemoryOptimizer
    from crackerjack.services.performance_cache import PerformanceCache
    from crackerjack.services.debug_service import DebugService
    from crackerjack.services.monitoring.performance_monitor import PerformanceMonitor

    # Get already-registered Console
    console = depends.get_sync(Console)

    # Memory Optimizer
    memory_optimizer = MemoryOptimizer(console=console)
    depends.set(MemoryOptimizerProtocol, memory_optimizer)
    self._registered.add("MemoryOptimizerProtocol")

    # Performance Cache
    perf_cache = PerformanceCache(console=console)
    depends.set(PerformanceCacheProtocol, perf_cache)
    self._registered.add("PerformanceCacheProtocol")

    # ... continue for other services
```

**Pattern**: Each level gets services from previous levels using `depends.get_sync()`

#### Task 1.3: Health Check Implementation

```python
def health_check(self) -> dict[str, t.Any]:
    """Check which services are registered and available.

    Returns:
        dict with:
            - registered: set of service names
            - available: dict mapping service to availability
            - missing: list of expected but missing services
    """
    from crackerjack.models import protocols

    # All expected protocols
    expected = [
        ("Console", Console),
        ("Config", Config),
        ("LoggerProtocol", protocols.LoggerProtocol),
        ("MemoryOptimizerProtocol", protocols.MemoryOptimizerProtocol),
        ("PerformanceCacheProtocol", protocols.PerformanceCacheProtocol),
        ("DebugServiceProtocol", protocols.DebugServiceProtocol),
        ("PerformanceMonitorProtocol", protocols.PerformanceMonitorProtocol),
        # ... all other services
    ]

    available = {}
    for name, protocol_type in expected:
        try:
            service = depends.get_sync(protocol_type)
            available[name] = service is not None
        except Exception as e:
            available[name] = False

    missing = [name for name, avail in available.items() if not avail]

    return {
        "registered": self._registered,
        "available": available,
        "missing": missing,
        "all_available": len(missing) == 0,
    }
```

### Week 2: Action Handler Integration

#### Task 2.1: Update run_fast_hooks Action

**Current (POC)**:

```python
@depends.inject
async def run_fast_hooks(
    context: dict[str, t.Any],
    step_id: str,
    orchestrator: Inject[WorkflowOrchestrator] | None = None,
    phase_coordinator: Inject[PhaseCoordinator] | None = None,
    **params: t.Any,
) -> dict[str, t.Any]:
    """Execute fast hooks phase."""
    options: OptionsProtocol = context.get("options")  # type: ignore[assignment]
    if not options:
        msg = "Missing 'options' in workflow context"
        raise ValueError(msg)

    # Phase 1 POC: Simple success response
    print("✓ ACB Workflow: Fast hooks phase completed (POC mode)")

    return {
        "phase": "fast_hooks",
        "success": True,
        "message": "Fast hooks completed successfully",
    }
```

**Target (Phase 2)**:

```python
@depends.inject
async def run_fast_hooks(
    context: dict[str, t.Any],
    step_id: str,
    **params: t.Any,
) -> dict[str, t.Any]:
    """Execute fast hooks phase.

    Fast hooks include:
    - Formatters (ruff, mdformat)
    - Import sorting (ruff)
    - Basic static analysis
    """
    options: OptionsProtocol = context.get("options")  # type: ignore[assignment]
    if not options:
        msg = "Missing 'options' in workflow context"
        raise ValueError(msg)

    # Get WorkflowPipeline from DI container (registered by WorkflowContainerBuilder)
    try:
        pipeline = depends.get_sync(WorkflowPipeline)
    except Exception as e:
        msg = f"WorkflowPipeline not available via DI: {e}"
        raise RuntimeError(msg) from e

    # Execute fast hooks using pipeline's method
    # Note: WorkflowPipeline methods are synchronous, use asyncio.to_thread
    success = await asyncio.to_thread(
        pipeline.phases._execute_monitored_fast_hooks_phase,
        options,
    )

    if not success:
        msg = "Fast hooks execution failed"
        raise RuntimeError(msg)

    return {
        "phase": "fast_hooks",
        "success": True,
        "message": "Fast hooks completed successfully",
    }
```

**Key Changes**:

1. Remove `orchestrator` and `phase_coordinator` parameters (not injected by ACB engine)
1. Use `depends.get_sync()` to get WorkflowPipeline
1. Call actual pipeline method via `asyncio.to_thread()`
1. Proper error handling and reporting

#### Task 2.2: Update Other Action Handlers

Apply same pattern to:

- `run_code_cleaning()` → `pipeline.phases._execute_monitored_cleaning_phase()`
- `run_comprehensive_hooks()` → `pipeline.phases._execute_monitored_comprehensive_phase()`
- `run_test_workflow()` → `pipeline._execute_test_workflow()`
- `run_configuration()` → May stay as POC (no automated config updates)

#### Task 2.3: Update CLI Handler

**Current**:

```python
@depends.inject
def handle_acb_workflow_mode(
    options: Options,
    job_id: str | None = None,
    console: Inject[Console] = None,
) -> None:
    """Execute workflow using ACB workflow engine (Phase 1 POC)."""
    # ... existing event bus registration ...

    # Phase 1 POC: Skip WorkflowOrchestrator registration
    # Phase 2 will implement proper DI setup for all dependencies
```

**Target**:

```python
@depends.inject
def handle_acb_workflow_mode(
    options: Options,
    job_id: str | None = None,
    console: Inject[Console] = None,
) -> None:
    """Execute workflow using ACB workflow engine with full integration."""
    import asyncio
    from acb.depends import depends
    from crackerjack.events.workflow_bus import WorkflowEventBus
    from crackerjack.workflows import (
        CrackerjackWorkflowEngine,
        EventBridgeAdapter,
        WorkflowContainerBuilder,
        register_actions,
        select_workflow_for_options,
    )

    console.print("[bold cyan]🚀 ACB Workflow Mode[/bold cyan]")

    try:
        # Build DI container with all services
        builder = WorkflowContainerBuilder(options, console=console)
        builder.build()

        # Health check to verify all services available
        health = builder.health_check()
        if not health["all_available"]:
            console.print(f"[red]Missing services: {health['missing']}[/red]")
            raise RuntimeError("DI container setup incomplete")

        # Event bus and bridge (already in Phase 1)
        event_bus = WorkflowEventBus()
        depends.set(WorkflowEventBus, event_bus)

        event_bridge = EventBridgeAdapter()
        depends.set(EventBridgeAdapter, event_bridge)

        # Initialize engine and register action handlers
        engine = CrackerjackWorkflowEngine()
        register_actions(engine)

        # Select workflow based on options
        workflow = select_workflow_for_options(options)

        console.print(f"[dim]Selected workflow: {workflow.name}[/dim]")

        # Execute workflow
        result = asyncio.run(engine.execute(workflow, context={"options": options}))

        # Check result
        from acb.workflows import WorkflowState

        if result.state != WorkflowState.COMPLETED:
            console.print(f"[red]Workflow failed: {result.error}[/red]")
            raise SystemExit(1)

        console.print("[bold green]✓ Workflow completed successfully[/bold green]")

    except Exception as e:
        console.print(f"[red]ACB workflow execution failed: {e}[/red]")
        console.print("[yellow]Falling back to legacy orchestrator[/yellow]")
        options.use_acb_workflows = False
        handle_standard_mode(options, False, job_id, False, console)
```

### Week 3: Testing & Optimization

#### Task 3.1: Integration Tests

**File**: `tests/workflows/test_acb_integration.py`

```python
"""Integration tests for ACB workflow Phase 2."""

import pytest
from pathlib import Path
from acb.console import Console
from acb.depends import depends

from crackerjack.workflows.container_builder import WorkflowContainerBuilder
from crackerjack.core.workflow_orchestrator import WorkflowPipeline
from crackerjack.models.protocols import OptionsProtocol


@pytest.fixture
def test_options():
    """Create test options."""
    from crackerjack.cli.options import Options

    return Options(
        fast=True,
        skip_hooks=True,
        project_root=Path.cwd(),
    )


@pytest.fixture
def clean_container():
    """Clean DI container before each test."""
    # Reset depends container
    # Implementation depends on ACB's container API
    yield
    # Cleanup after test


class TestWorkflowContainerBuilder:
    """Test DI container builder."""

    def test_build_registers_all_services(self, test_options, clean_container):
        """Verify all services are registered."""
        builder = WorkflowContainerBuilder(test_options)
        builder.build()

        health = builder.health_check()
        assert health["all_available"], f"Missing: {health['missing']}"

    def test_services_are_accessible(self, test_options, clean_container):
        """Verify services can be retrieved."""
        builder = WorkflowContainerBuilder(test_options)
        builder.build()

        # Should be able to get WorkflowPipeline
        pipeline = depends.get_sync(WorkflowPipeline)
        assert pipeline is not None

        # Should have console
        assert pipeline.console is not None

    def test_initialization_order_is_correct(self, test_options, clean_container):
        """Verify services initialize in correct order."""
        builder = WorkflowContainerBuilder(test_options)

        # Track registration order
        registered_order = []
        original_set = depends.set

        def tracking_set(type_obj, instance):
            registered_order.append(type_obj.__name__)
            return original_set(type_obj, instance)

        depends.set = tracking_set
        try:
            builder.build()
        finally:
            depends.set = original_set

        # Verify Console comes before services that depend on it
        console_idx = registered_order.index("Console")
        memory_idx = registered_order.index("MemoryOptimizerProtocol")
        assert console_idx < memory_idx


class TestACBWorkflowIntegration:
    """Test end-to-end ACB workflow execution."""

    @pytest.mark.asyncio
    async def test_fast_hooks_workflow_executes(self, test_options, clean_container):
        """Test fast hooks workflow with real orchestrator."""
        from crackerjack.workflows import (
            CrackerjackWorkflowEngine,
            FAST_HOOKS_WORKFLOW,
            register_actions,
        )

        # Setup container
        builder = WorkflowContainerBuilder(test_options)
        builder.build()

        # Setup engine
        engine = CrackerjackWorkflowEngine()
        register_actions(engine)

        # Execute workflow
        result = await engine.execute(
            FAST_HOOKS_WORKFLOW, context={"options": test_options}
        )

        # Verify success
        from acb.workflows import WorkflowState

        assert result.state == WorkflowState.COMPLETED

    def test_cli_handler_with_acb_workflows(self, test_options, clean_container):
        """Test CLI handler with ACB workflow flag."""
        from crackerjack.cli.handlers import handle_acb_workflow_mode

        # Should not raise
        handle_acb_workflow_mode(test_options, job_id=None)
```

#### Task 3.2: Performance Benchmarking

**File**: `tests/workflows/test_acb_performance.py`

```python
"""Performance tests comparing ACB vs legacy orchestrator."""

import pytest
import time
from pathlib import Path


class TestACBPerformance:
    """Benchmark ACB workflow performance."""

    @pytest.mark.benchmark
    def test_fast_hooks_acb_vs_legacy(self, benchmark, test_options):
        """Compare fast hooks execution time."""

        # Baseline: Legacy orchestrator
        def run_legacy():
            from crackerjack.cli.handlers import handle_standard_mode

            handle_standard_mode(test_options, orchestrated=False, job_id=None)

        legacy_time = benchmark(run_legacy)

        # ACB workflow
        test_options.use_acb_workflows = True

        def run_acb():
            from crackerjack.cli.handlers import handle_acb_workflow_mode

            handle_acb_workflow_mode(test_options, job_id=None)

        acb_time = benchmark(run_acb)

        # Verify <5% overhead
        overhead = (acb_time - legacy_time) / legacy_time
        assert overhead < 0.05, f"ACB overhead {overhead:.1%} exceeds 5% target"
```

#### Task 3.3: Error Handling & Edge Cases

Test error scenarios:

- Missing services in container
- Service initialization failures
- Workflow step failures
- Graceful fallback to legacy orchestrator

## Migration Checklist

### Phase 2 Completion Criteria

- [ ] WorkflowContainerBuilder implemented and tested
- [ ] All 20+ services registered in correct order
- [ ] Health check validates all services available
- [ ] All action handlers use real orchestrator methods
- [ ] Integration tests pass (>90% coverage)
- [ ] Performance benchmarks meet \<5% overhead target
- [ ] Error handling covers edge cases
- [ ] Documentation updated

### Production Readiness Gates

- [ ] All tests passing in CI/CD
- [ ] Performance benchmarks documented
- [ ] Error scenarios tested
- [ ] Monitoring/alerting configured
- [ ] Team training completed
- [ ] Runbook created for debugging
- [ ] Gradual rollout plan approved

## Risk Mitigation

### Technical Risks

| Risk | Mitigation |
|------|-----------|
| Service initialization order issues | Health check catches missing dependencies early |
| Performance regression | Continuous benchmarking in CI/CD |
| Memory leaks in long-running workflows | Memory profiling tests |
| Deadlocks in parallel execution | Timeout enforcement, circuit breakers |

### Rollback Strategy

1. **Instant Rollback**: Disable `use_acb_workflows` flag
1. **Graceful Degradation**: Automatic fallback to legacy orchestrator on errors
1. **Monitoring**: Alert on >5% performance degradation or error rate increase
1. **Feature Flag**: Gradual rollout (10% → 50% → 100% traffic)

## Success Metrics

### Phase 2 Success (Go/No-Go for Phase 3)

- [ ] All action handlers integrated (no POC code remaining)
- [ ] DI container manages all dependencies successfully
- [ ] Performance within 5% of legacy orchestrator
- [ ] Zero critical bugs in testing
- [ ] >95% test coverage for workflow integration

### Long-term Success (6 months post-deployment)

- [ ] ACB workflows handle 100% of production traffic
- [ ] Legacy orchestrator removed from codebase
- [ ] Developer productivity improved (faster iterations)
- [ ] Maintenance burden reduced (declarative > imperative)
- [ ] Parallel execution reduces total runtime by >20%

## Timeline & Milestones

### Week 1: DI Container Infrastructure

- Day 1-2: WorkflowContainerBuilder skeleton + Level 1-2 registration
- Day 3-4: Level 3-5 registration + health check
- Day 5: Level 6-7 registration + testing

### Week 2: Action Handler Integration

- Day 1-2: Update run_fast_hooks + run_code_cleaning
- Day 3-4: Update run_comprehensive_hooks + run_test_workflow
- Day 5: Update CLI handler + integration testing

### Week 3: Testing & Optimization

- Day 1-2: Integration test suite
- Day 3: Performance benchmarking
- Day 4: Error handling & edge cases
- Day 5: Documentation + team review

## References

### Implementation Files

**Phase 2 New Files**:

- `crackerjack/workflows/container_builder.py` - DI container setup
- `tests/workflows/test_acb_integration.py` - Integration tests
- `tests/workflows/test_acb_performance.py` - Performance benchmarks

**Phase 2 Modified Files**:

- `crackerjack/workflows/actions.py` - Update all action handlers
- `crackerjack/cli/handlers.py` - Add container builder to handle_acb_workflow_mode

**Phase 1 Files (Reference)**:

- `crackerjack/workflows/engine.py` - Workflow engine (no changes)
- `crackerjack/workflows/event_bridge.py` - Event bridge (no changes)
- `crackerjack/workflows/definitions.py` - Workflow definitions (no changes)

### Related Documentation

- Phase 1 POC: `docs/ACB-WORKFLOW-INTEGRATION.md`
- Crackerjack Architecture: `CLAUDE.md`
- ACB Framework: `/Users/les/Projects/acb/README.md`

______________________________________________________________________

**Document Version**: 1.0
**Last Updated**: 2025-11-05
**Author**: ACB Workflow Integration Team
**Status**: Phase 2 Planning - Ready for Implementation
