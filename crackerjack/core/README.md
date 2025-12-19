# Core

> Crackerjack Docs: [Main](../../README.md) | [CLAUDE.md](../../docs/guides/CLAUDE.md) | [Core](./README.md)

Core utilities, coordinators, and orchestration layer for Crackerjack's workflow management.

## Overview

The core package provides the orchestration backbone for Crackerjack's workflow execution. It implements coordinators for session management, phase execution, workflow orchestration, and service lifecycle management. Core components bridge CLI handlers and the service layer, managing execution flow, resource coordination, and error handling.

## Key Components

### Coordinators

**session_coordinator.py** - Lightweight session tracking:

- `SessionCoordinator` - Session lifecycle management
- Session metadata and task tracking via `SessionTracker`
- Cleanup handler registration and execution
- Lock file management
- Gold standard ACB integration with protocol-based DI

**phase_coordinator.py** - Execution phase coordination:

- Fast hooks phase (~5s): formatting, basic checks
- Test phase: full test suite with coverage
- Comprehensive hooks phase (~30s): type checking, security
- AI batch fixing phase: process all collected failures
- Phase dependency management and ordering

**autofix_coordinator.py** - AI agent autofix coordination:

- Agent-based issue fixing orchestration
- Batch processing of quality issues
- Confidence-based agent selection
- Fix validation and rollback support
- Integration with 12 specialized AI agents

**async_workflow_orchestrator.py** - Async workflow management:

- Asynchronous workflow execution
- Parallel phase execution support
- Event-driven workflow coordination
- Resource pooling and lifecycle management

**proactive_workflow.py** - Proactive quality monitoring:

- Predictive issue detection
- Preemptive optimization recommendations
- Trend analysis and quality forecasting
- Integration with `EnhancedProactiveAgent`

### Workflow Orchestration

**workflow_orchestrator.py** - Main workflow pipeline:

- `WorkflowPipeline` - End-to-end workflow execution
- Hook execution (fast → comprehensive)
- Test management integration
- Publishing and release coordination
- Error aggregation and reporting

**workflow/** - Specialized workflow components:

- `workflow_ai_coordinator.py` - AI agent workflow integration
- `workflow_event_orchestrator.py` - Event-driven workflow coordination
- `workflow_issue_parser.py` - Quality issue parsing and categorization
- `workflow_phase_executor.py` - Individual phase execution logic
- `workflow_security_gates.py` - Security validation gates

### Service Management

**service_watchdog.py** - Service health monitoring:

- Monitors long-running services (MCP server, WebSocket server)
- Automatic restart on failure
- Health check coordination
- Service status reporting
- **⚠️ Needs DI integration** (currently uses factory functions)

**timeout_manager.py** - Centralized timeout management:

- Per-operation timeout configuration
- Timeout strategy selection (fixed, adaptive, exponential backoff)
- Timeout enforcement and tracking
- Performance metrics for timeout tuning

**resource_manager.py** - Resource lifecycle coordination:

- Resource registration and tracking
- Cleanup coordination across components
- Memory optimization support
- Resource leak detection

### Performance & Monitoring

**performance.py** - Performance tracking utilities:

- Execution timing decorators
- Performance metric collection
- Benchmark helpers
- Performance regression detection

**performance_monitor.py** - Workflow performance monitoring:

- Per-workflow performance tracking
- Phase-level performance metrics
- Performance trend analysis
- Benchmark comparison and reporting

### Lifecycle Management

**file_lifecycle.py** - File operation lifecycle:

- Atomic file operations
- Backup and rollback support
- Safe file modification
- File lock coordination

**websocket_lifecycle.py** - WebSocket connection lifecycle:

- WebSocket connection management
- Reconnection logic
- Event subscription handling
- Connection health monitoring

### Dependency Injection Containers

**container.py** - Base DI container:

- Service registration
- Dependency resolution
- Singleton management
- Factory function support

**enhanced_container.py** - Enhanced DI container:

- Advanced dependency injection features
- Circular dependency detection
- Lazy initialization support
- Scope management (singleton, transient, scoped)

## Usage Examples

### Session Coordination (Gold Standard)

```python
from acb.depends import depends, Inject
from crackerjack.core.session_coordinator import SessionCoordinator
from crackerjack.models.protocols import Console


@depends.inject
def run_workflow(
    session: Inject[SessionCoordinator] = None,
    console: Inject[Console] = None,
) -> None:
    """Run workflow with session tracking."""
    session.start_session("quality_checks")

    try:
        # Execute workflow phases
        console.print("[bold]Running quality checks...[/bold]")
        # ... workflow logic ...
        session.end_session(success=True)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        session.end_session(success=False)
        raise
```

### Phase Coordination

```python
from crackerjack.core.phase_coordinator import PhaseCoordinator


@depends.inject
async def execute_quality_pipeline(
    phase_coord: Inject[PhaseCoordinator] = None,
) -> bool:
    """Execute quality assurance pipeline."""
    # Phase 1: Fast hooks
    fast_results = await phase_coord.execute_fast_phase()

    # Phase 2: Tests
    test_results = await phase_coord.execute_test_phase()

    # Phase 3: Comprehensive hooks
    comp_results = await phase_coord.execute_comprehensive_phase()

    # Phase 4: AI batch fixing (if enabled)
    if phase_coord.ai_fix_enabled:
        fix_results = await phase_coord.execute_ai_fix_phase(
            fast_results + comp_results + test_results
        )

    return all([fast_results, test_results, comp_results])
```

### Workflow Orchestration

```python
from crackerjack.core.workflow_orchestrator import WorkflowPipeline
from crackerjack.models.protocols import OptionsProtocol

@depends.inject
async def run_full_workflow(
    workflow: Inject[WorkflowPipeline] = None,
    options: OptionsProtocol,
) -> bool:
    """Execute complete workflow pipeline."""
    result = await workflow.execute(options)

    if result.success:
        console.print("[green]✓ Workflow completed successfully[/green]")
    else:
        console.print("[red]✗ Workflow failed[/red]")
        for error in result.errors:
            console.print(f"  - {error}")

    return result.success
```

### Performance Monitoring

```python
from crackerjack.core.performance_monitor import PerformanceMonitor


@depends.inject
def monitored_operation(
    perf_monitor: Inject[PerformanceMonitor] = None,
) -> None:
    """Operation with performance monitoring."""
    workflow_id = "quality_checks_2025"

    perf_monitor.start_workflow(workflow_id)
    perf_monitor.start_phase(workflow_id, "fast_hooks")

    try:
        # Execute operation
        run_fast_hooks()
        perf_monitor.end_phase(workflow_id, "fast_hooks", success=True)
    except Exception:
        perf_monitor.end_phase(workflow_id, "fast_hooks", success=False)
        raise
    finally:
        perf_data = perf_monitor.end_workflow(workflow_id)
        print(f"Workflow duration: {perf_data.duration}s")
```

### Timeout Management

```python
from crackerjack.core.timeout_manager import TimeoutManager


@depends.inject
def execute_with_timeout(
    timeout_mgr: Inject[TimeoutManager] = None,
) -> bool:
    """Execute operation with managed timeout."""
    try:
        result = timeout_mgr.apply_timeout(
            operation="hook_execution",
            func=run_expensive_hook,
            hook_name="bandit",
        )
        return result
    except TimeoutError:
        print("Operation timed out")
        return False
```

## Architecture Patterns

### Coordinator Pattern

Coordinators orchestrate multiple services to accomplish complex workflows:

```python
class MyCoordinator:
    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        hook_manager: Inject[HookManager],
        test_manager: Inject[TestManagerProtocol],
    ) -> None:
        """Coordinator with protocol-based dependencies."""
        self.console = console
        self.hook_manager = hook_manager
        self.test_manager = test_manager

    async def coordinate_workflow(self) -> bool:
        """Coordinate multi-service workflow."""
        # Fast hooks
        hook_results = await self.hook_manager.run_fast_hooks()

        # Tests if hooks pass
        if all(r.success for r in hook_results):
            test_results = await self.test_manager.run_tests()
            return test_results

        return False
```

### Lifecycle Management

Resources are managed through registration and cleanup:

```python
from crackerjack.core.resource_manager import ResourceManager


@depends.inject
def manage_resources(
    resource_mgr: Inject[ResourceManager] = None,
) -> None:
    """Manage resource lifecycle."""
    # Register resources
    lock_file = acquire_lock()
    resource_mgr.register_resource(lock_file)

    try:
        # Use resource
        perform_operation(lock_file)
    finally:
        # Cleanup happens automatically
        resource_mgr.cleanup_resource(lock_file)
```

## Configuration

Core components integrate with ACB Settings:

```yaml
# settings/crackerjack.yaml
max_parallel_hooks: 8
workflow_timeout: 600
enable_performance_monitoring: true
session_tracking: true
```

```python
from crackerjack.config import CrackerjackSettings

settings = CrackerjackSettings.load()
max_parallel = settings.max_parallel_hooks
timeout = settings.workflow_timeout
```

## Best Practices

1. **Use Protocol-Based DI**: Always inject dependencies via protocols
1. **Coordinate, Don't Implement**: Coordinators orchestrate, services implement
1. **Track Performance**: Use `PerformanceMonitor` for execution metrics
1. **Manage Lifecycle**: Register resources for automatic cleanup
1. **Handle Timeouts**: Use `TimeoutManager` for consistent timeout handling
1. **Log Structured Data**: Use structured logging with context
1. **Fail Gracefully**: Coordinators should handle errors and report clearly

## Compliance Status

Based on Phase 2-4 refactoring audit:

- **Coordinators (70% compliant)**:

  - ✅ `SessionCoordinator` - Gold standard ACB integration
  - ✅ Phase coordinators use proper DI
  - ⚠️ Async coordinators need protocol standardization

- **Orchestration (70% compliant)**:

  - ✅ `WorkflowOrchestrator` - DI containers, lifecycle management
  - ⚠️ `ServiceWatchdog` - Needs DI integration (factory functions, manual fallbacks)

## Related Documentation

- [CLAUDE.md](../../docs/guides/CLAUDE.md) - Architecture overview and patterns
- [Models](../models/README.md) - Protocol definitions
- [Managers](../managers/README.md) - Service implementations
- [Orchestration](../orchestration/README.md) - Execution strategies
- [Agents](../agents/README.md) - AI agent system

## Future Enhancements

- Complete DI migration for `ServiceWatchdog`
- Enhanced async workflow coordination
- Advanced performance profiling
- Real-time workflow dashboards
- Distributed workflow execution support
