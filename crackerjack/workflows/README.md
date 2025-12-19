> Crackerjack Docs: [Main](../../README.md) | [CLAUDE.md](../../docs/guides/CLAUDE.md) | Workflows

# Workflows

Declarative workflow orchestration combining agents, services, and executors with ACB workflow engine integration.

## Overview

The workflows package provides high-level workflow definitions and execution engines that coordinate multiple components (hooks, tests, agents) to accomplish complex tasks. Built on ACB's workflow engine, it supports automatic parallelization, event-driven coordination, and declarative workflow definitions.

## Core Components

### CrackerjackWorkflowEngine (`engine.py`)

ACB workflow engine with event bridge for backward compatibility:

**Features:**

- **Automatic Parallel Execution** - Dependency-based parallel step execution
- **Event Bridge** - Emits crackerjack-specific events for backward compatibility
- **Built-in Retry Logic** - Exponential backoff for transient failures
- **State Management** - Tracks workflow and step states
- **DI-Based Actions** - Dependency injection for action handlers
- **Timing & Metrics** - Automatic execution time tracking

**Key Capabilities:**

```python
class CrackerjackWorkflowEngine(BasicWorkflowEngine):
    async def execute(
        self, workflow: WorkflowDefinition, context: dict | None = None
    ) -> WorkflowResult:
        """Execute workflow with parallel step execution."""
```

### Workflow Definitions (`definitions.py`)

Declarative workflow structures using ACB's WorkflowDefinition:

**Available Workflows:**

1. **FAST_HOOKS_WORKFLOW** - Quick formatters and basic checks (~5s)
1. **COMPREHENSIVE_HOOKS_WORKFLOW** - Type checking, security, complexity (~30s)
1. **STANDARD_WORKFLOW** - Full quality checks with parallel phases
1. **TEST_WORKFLOW** - Test execution with coverage reporting
1. **COMMIT_WORKFLOW** - Pre-commit validation workflow
1. **PUBLISH_WORKFLOW** - PyPI publishing workflow
1. **COMPREHENSIVE_PARALLEL_WORKFLOW** - Maximum parallelization

**Workflow Selection:**

```python
def select_workflow_for_options(options: OptionsProtocol) -> WorkflowDefinition:
    """Select appropriate workflow based on CLI options."""
```

### Action Registry (`actions.py`)

Registry of workflow action handlers:

**Features:**

- **Action Registration** - Register custom action handlers
- **DI Integration** - Actions automatically get dependencies injected
- **Error Handling** - Standardized error handling for actions
- **Context Passing** - Pass state between workflow steps

**Built-in Actions:**

- `run_configuration` - Configure project settings
- `run_fast_hooks` - Execute fast quality hooks
- `run_comprehensive_hooks` - Execute comprehensive hooks
- `run_tests` - Run test suite with pytest
- `run_code_cleaning` - Code cleaning and optimization
- `run_ai_fixing` - AI-powered automatic fixing
- `run_commit` - Git commit with validation
- `run_publish` - PyPI package publishing

### Event Bridge (`event_bridge.py`)

Adapter translating ACB workflow events to crackerjack events:

**Features:**

- **Backward Compatibility** - Maintains compatibility with existing event consumers
- **Event Translation** - Maps WorkflowStep to crackerjack events
- **State Mapping** - Translates workflow states to step events
- **Progress Tracking** - Emits progress events for UI updates

### Container Builder (`container_builder.py`)

Builds DI containers for workflow execution:

**Features:**

- **Dependency Registration** - Registers all workflow dependencies
- **Service Configuration** - Configures services based on options
- **Lifecycle Management** - Manages service initialization/cleanup
- **Context Isolation** - Isolates workflow execution contexts

### AutoFixWorkflow (`auto_fix.py`)

Legacy iterative auto-fix workflow (pre-ACB integration):

**Features:**

- **Iterative Fixing** - Multiple fix iterations until success
- **Pattern Learning** - Learns from successful fixes
- **Quality Gates** - Validates fixes meet quality standards
- **Rollback Support** - Can rollback failed iterations

## Workflow Definitions

### Fast Hooks Workflow

Quick quality checks for rapid feedback (~5s):

```python
FAST_HOOKS_WORKFLOW = WorkflowDefinition(
    workflow_id="crackerjack-fast-hooks",
    name="Fast Quality Checks",
    description="Quick formatters, import sorting, and basic static analysis",
    steps=[
        WorkflowStep(
            step_id="config",
            name="Configuration",
            action="run_configuration",
            retry_attempts=1,
            timeout=30.0,
        ),
        WorkflowStep(
            step_id="fast_hooks",
            name="Fast Hooks",
            action="run_fast_hooks",
            depends_on=["config"],
            retry_attempts=1,
            timeout=300.0,
        ),
    ],
    timeout=600.0,
    retry_failed_steps=True,
    continue_on_error=False,
)
```

### Standard Workflow

Full quality checks with phase-level parallelization:

```python
STANDARD_WORKFLOW = WorkflowDefinition(
    workflow_id="crackerjack-standard",
    name="Standard Quality Workflow",
    steps=[
        WorkflowStep(step_id="config", action="run_configuration"),
        # These run in parallel (both depend only on config)
        WorkflowStep(
            step_id="fast_hooks",
            action="run_fast_hooks",
            depends_on=["config"],
            parallel=True,
        ),
        WorkflowStep(
            step_id="cleaning",
            action="run_code_cleaning",
            depends_on=["config"],
            parallel=True,
        ),
        # Tests run after both complete
        WorkflowStep(
            step_id="tests",
            action="run_tests",
            depends_on=["fast_hooks", "cleaning"],
        ),
        # Comprehensive hooks run after tests
        WorkflowStep(
            step_id="comprehensive",
            action="run_comprehensive_hooks",
            depends_on=["tests"],
        ),
    ],
    timeout=1800.0,
)
```

### Test Workflow

Focused on test execution with coverage reporting:

```python
TEST_WORKFLOW = WorkflowDefinition(
    workflow_id="crackerjack-test",
    name="Test Execution",
    steps=[
        WorkflowStep(step_id="config", action="run_configuration"),
        WorkflowStep(
            step_id="tests",
            action="run_tests",
            depends_on=["config"],
            timeout=900.0,
        ),
        WorkflowStep(
            step_id="coverage_report",
            action="generate_coverage_report",
            depends_on=["tests"],
        ),
    ],
)
```

### Comprehensive Parallel Workflow

Maximum parallelization for speed:

```python
COMPREHENSIVE_PARALLEL_WORKFLOW = WorkflowDefinition(
    workflow_id="crackerjack-comprehensive-parallel",
    name="Comprehensive Parallel Workflow",
    steps=[
        WorkflowStep(step_id="config", action="run_configuration"),
        # All quality checks run in parallel
        WorkflowStep(
            step_id="fast_hooks",
            action="run_fast_hooks",
            depends_on=["config"],
            parallel=True,
        ),
        WorkflowStep(
            step_id="comprehensive",
            action="run_comprehensive_hooks",
            depends_on=["config"],
            parallel=True,
        ),
        WorkflowStep(
            step_id="tests",
            action="run_tests",
            depends_on=["config"],
            parallel=True,
        ),
        # AI fixing runs after all checks complete
        WorkflowStep(
            step_id="ai_fix",
            action="run_ai_fixing",
            depends_on=["fast_hooks", "comprehensive", "tests"],
        ),
    ],
)
```

## Usage Examples

### Basic Workflow Execution

```python
from crackerjack.workflows import CrackerjackWorkflowEngine, FAST_HOOKS_WORKFLOW
from acb.depends import depends

engine = depends.get(CrackerjackWorkflowEngine)

# Execute workflow
result = await engine.execute(
    workflow=FAST_HOOKS_WORKFLOW, context={"options": options}
)

# Check result
if result.state == WorkflowState.COMPLETED:
    print(f"✅ Workflow completed in {result.duration:.1f}s")
    print(f"Steps executed: {len(result.steps)}")
else:
    print(f"❌ Workflow failed: {result.error}")
    for step in result.steps:
        if step.state == StepState.FAILED:
            print(f"  Failed step: {step.step_id}")
```

### Custom Workflow Definition

```python
from acb.workflows import WorkflowDefinition, WorkflowStep

custom_workflow = WorkflowDefinition(
    workflow_id="my-custom-workflow",
    name="Custom Quality Workflow",
    description="My project-specific quality checks",
    steps=[
        WorkflowStep(
            step_id="config",
            name="Configuration",
            action="run_configuration",
        ),
        WorkflowStep(
            step_id="custom_check",
            name="Custom Quality Check",
            action="run_custom_check",
            depends_on=["config"],
            timeout=120.0,
            retry_attempts=1,
        ),
        WorkflowStep(
            step_id="tests",
            name="Run Tests",
            action="run_tests",
            depends_on=["custom_check"],
        ),
    ],
    timeout=600.0,
    retry_failed_steps=True,
)

# Execute custom workflow
result = await engine.execute(custom_workflow, context={})
```

### Registering Custom Actions

```python
from crackerjack.workflows import ACTION_REGISTRY


@ACTION_REGISTRY.register("run_custom_check")
async def run_custom_check(context: dict) -> dict:
    """Custom quality check action."""
    options = context.get("options")

    # Perform custom checks
    results = await perform_custom_checks(options.pkg_path)

    return {
        "success": results.passed,
        "issues": results.issues,
        "duration": results.duration,
    }
```

### Workflow with Event Handling

```python
from crackerjack.workflows import CrackerjackWorkflowEngine
from crackerjack.workflows.event_bridge import EventBridgeAdapter

engine = CrackerjackWorkflowEngine()


# Register event handlers
@engine.event_bridge.on_step_started
async def handle_step_started(step_id: str, context: dict):
    print(f"Starting step: {step_id}")


@engine.event_bridge.on_step_completed
async def handle_step_completed(step_id: str, result: dict):
    print(f"Completed step: {step_id} - {result.get('success')}")


# Execute workflow with event handling
result = await engine.execute(STANDARD_WORKFLOW)
```

### Workflow Selection Based on Options

```python
from crackerjack.workflows import select_workflow_for_options

# Select appropriate workflow based on CLI options
workflow = select_workflow_for_options(options)

# Execute selected workflow
result = await engine.execute(workflow, context={"options": options})
```

### Parallel Step Execution

```python
from acb.workflows import WorkflowDefinition, WorkflowStep

# Define workflow with parallel steps
parallel_workflow = WorkflowDefinition(
    workflow_id="parallel-checks",
    name="Parallel Quality Checks",
    steps=[
        WorkflowStep(step_id="config", action="run_configuration"),
        # These three steps run in parallel
        WorkflowStep(
            step_id="linting",
            action="run_linting",
            depends_on=["config"],
            parallel=True,
        ),
        WorkflowStep(
            step_id="type_check",
            action="run_type_checking",
            depends_on=["config"],
            parallel=True,
        ),
        WorkflowStep(
            step_id="security",
            action="run_security_scan",
            depends_on=["config"],
            parallel=True,
        ),
        # This runs after all parallel steps complete
        WorkflowStep(
            step_id="report",
            action="generate_report",
            depends_on=["linting", "type_check", "security"],
        ),
    ],
)
```

## WorkflowResult Structure

```python
@dataclass
class WorkflowResult:
    state: WorkflowState  # COMPLETED, FAILED, CANCELLED
    steps: list[StepResult]  # Results from each step
    duration: float  # Total execution time (seconds)
    error: str | None  # Error message if failed
    context: dict  # Final execution context

    @property
    def success(self) -> bool:
        """Whether workflow completed successfully."""
        return self.state == WorkflowState.COMPLETED

    @property
    def failed_steps(self) -> list[StepResult]:
        """List of failed steps."""
        return [s for s in self.steps if s.state == StepState.FAILED]
```

## Workflow States

```python
class WorkflowState(Enum):
    PENDING = "pending"  # Not yet started
    RUNNING = "running"  # Currently executing
    COMPLETED = "completed"  # Successfully completed
    FAILED = "failed"  # Failed with errors
    CANCELLED = "cancelled"  # Cancelled by user
```

## Step States

```python
class StepState(Enum):
    PENDING = "pending"  # Waiting for dependencies
    RUNNING = "running"  # Currently executing
    COMPLETED = "completed"  # Successfully completed
    FAILED = "failed"  # Failed with error
    SKIPPED = "skipped"  # Skipped due to conditions
```

## Configuration

Workflow configuration through ACB Settings:

```yaml
# settings/crackerjack.yaml

# Workflow engine
workflow_engine_enabled: true
max_concurrent_steps: 5        # Max parallel workflow steps
workflow_timeout: 1800         # Global workflow timeout (seconds)

# Workflow selection
default_workflow: "standard"   # fast_hooks, standard, comprehensive
auto_select_workflow: true     # Auto-select based on options

# Step configuration
step_retry_enabled: true
step_retry_attempts: 1
step_retry_delay: 5            # Seconds between retries
step_timeout: 300              # Default step timeout

# Event bridge
event_bridge_enabled: true
emit_progress_events: true
progress_update_interval: 1.0  # Seconds

# Parallelization
enable_parallel_execution: true
parallel_fast_and_cleaning: true
parallel_all_checks: false     # Experimental: all checks in parallel
```

## Integration Examples

### With Agent System

```python
from crackerjack.workflows import CrackerjackWorkflowEngine
from crackerjack.intelligence import get_agent_orchestrator

engine = CrackerjackWorkflowEngine()
agent_orchestrator = get_agent_orchestrator()


# Register AI fixing action
@ACTION_REGISTRY.register("run_ai_fixing")
async def run_ai_fixing(context: dict) -> dict:
    errors = context.get("errors", [])
    fixed_count = 0

    for error in errors:
        result = await agent_orchestrator.fix_error(error)
        if result.success:
            fixed_count += 1

    return {"fixed_count": fixed_count, "total_errors": len(errors)}
```

### With Hook Executors

```python
from crackerjack.executors import CachedHookExecutor


@ACTION_REGISTRY.register("run_fast_hooks")
async def run_fast_hooks(context: dict) -> dict:
    options = context["options"]
    executor = CachedHookExecutor(console=console, pkg_path=options.pkg_path)

    result = executor.execute_strategy("fast_hooks")

    return {
        "success": result.success,
        "duration": result.total_duration,
        "cache_hit_rate": result.cache_hit_rate,
    }
```

## Best Practices

1. **Use Declarative Definitions** - Define workflows declaratively for clarity
1. **Enable Parallelization** - Mark independent steps as parallel for speed
1. **Set Appropriate Timeouts** - Configure realistic timeouts for each step
1. **Handle Failures Gracefully** - Use retry logic for transient failures
1. **Minimize Dependencies** - Only declare necessary dependencies for max parallelism
1. **Use Event Bridge** - Leverage event system for progress tracking
1. **Context Passing** - Use context to share state between steps
1. **Workflow Selection** - Auto-select workflows based on CLI options
1. **Monitor Performance** - Track workflow execution metrics
1. **Test Custom Actions** - Thoroughly test custom action handlers

## Performance Considerations

### Execution Time Comparison

```
Sequential execution (no parallelization):
  Standard workflow: ~120s
  Comprehensive workflow: ~180s

Parallel execution (phase-level):
  Standard workflow: ~60s (2x faster)
  Comprehensive workflow: ~90s (2x faster)

Maximum parallelization:
  Standard workflow: ~40s (3x faster)
  Comprehensive workflow: ~60s (3x faster)
```

### Resource Usage

```
Base workflow engine: ~50MB
Event bridge overhead: ~5MB
Per workflow instance: ~10MB
Per concurrent step: ~20-50MB (depends on step type)
```

## Related

- [Executors](../executors/README.md) - Hook execution engines
- [Intelligence](../intelligence/README.md) - Agent orchestration
- [Hooks](../hooks/README.md) - Hook system integration
- [CLAUDE.md](../../docs/guides/CLAUDE.md) - Workflow architecture overview

## Future Enhancements

- [ ] DAG visualization for workflow dependencies
- [ ] Workflow composition (combine multiple workflows)
- [ ] Conditional step execution based on context
- [ ] Dynamic workflow generation from project analysis
- [ ] Workflow templates for common patterns
- [ ] Distributed workflow execution across machines
- [ ] Real-time workflow monitoring dashboard
- [ ] Workflow versioning and rollback
