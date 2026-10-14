# ACB Workflow Migration Plan

## Executive Summary

Crackerjack currently uses a custom `WorkflowOrchestrator` implementation. This plan outlines migrating to ACB's `WorkflowService` and `BasicWorkflowEngine` to leverage:

- **Automatic parallel execution** where dependencies allow
- **Built-in retry logic** with exponential backoff
- **State persistence** and recovery
- **Event integration** for workflow tracking
- **Declarative workflow definitions** (step-based composition)
- **Dependency resolution** engine

## Current Architecture

### Current Workflow Components

```
crackerjack/core/
├── workflow_orchestrator.py   # Main orchestration (2800+ lines)
├── phase_coordinator.py        # Phase execution (fast, comp, cleaning, etc.)
├── session_coordinator.py      # Session management
└── async_workflow_orchestrator.py  # Async variant
```

### Current Execution Flow

```
python -m crackerjack
  ↓
WorkflowOrchestrator.run_complete_workflow()
  ↓
_run_event_driven_workflow()
  ↓
Event-driven phases:
  1. CONFIG_PHASE_COMPLETED → Quality Phase
  2. QUALITY_PHASE_COMPLETED → Publish Phase (if requested)
  3. PUBLISH_PHASE_COMPLETED → Commit Phase (if requested)
  4. WORKFLOW_COMPLETED
```

### Current Phase Structure

**Quality Phase** (the main workflow):

```
_execute_quality_phase()
  ├── options.fast → _run_fast_hooks_phase_monitored()
  ├── options.comp → _run_comprehensive_hooks_phase_monitored()
  ├── options.test → _execute_test_workflow()
  └── default → _execute_standard_hooks_workflow_monitored()
      ├── Fast hooks
      ├── Cleaning (if --clean)
      └── Comprehensive hooks
```

### What We Do Well (Keep)

✅ Event-driven workflow coordination
✅ ACB dependency injection throughout
✅ Protocol-based interfaces
✅ Session management and tracking
✅ Performance monitoring integration
✅ Rich terminal output with panels

### What ACB Workflows Would Improve

❌ Manual step orchestration (hard-coded sequences)
❌ Limited parallelization (only within hook execution)
❌ Custom retry logic per phase
❌ No declarative workflow definitions
❌ Manual state management
❌ Complex conditional branching logic

## ACB Workflow System Benefits

### Key Features

1. **Step-Based Composition**

   - Declarative `WorkflowDefinition` with `WorkflowStep[]`
   - Each step has `action`, `params`, `depends_on`
   - Clean separation of workflow structure from execution

1. **Automatic Parallel Execution**

   - `BasicWorkflowEngine` analyzes `depends_on` relationships
   - Executes independent steps concurrently
   - Respects `max_concurrent_steps` semaphore
   - Example: Fast hooks could run in parallel with configuration

1. **Built-in Retry Logic**

   - Per-step `retry_attempts` and `retry_delay`
   - Exponential backoff support
   - `skip_on_failure` flag for non-critical steps

1. **State Management**

   - `WorkflowResult` and `StepResult` tracking
   - Automatic timing and duration calculation
   - State persistence (when enabled)

1. **Event Integration**

   - Works with existing `acb.events.Event` system
   - Can emit workflow/step events for monitoring

## Migration Strategy

### Phase 1: Proof of Concept (1-2 days)

**Goal**: Demonstrate ACB workflows can execute a simplified crackerjack workflow

**Tasks**:

1. Create example workflow definition for fast hooks only
1. Implement action handlers as async functions
1. Register handlers with `BasicWorkflowEngine`
1. Execute and compare output with current implementation

**Example Code**:

```python
from acb.workflows import BasicWorkflowEngine, WorkflowDefinition, WorkflowStep

# Define workflow
fast_workflow = WorkflowDefinition(
    workflow_id="crackerjack-fast",
    name="Fast Quality Checks",
    steps=[
        WorkflowStep(
            step_id="config",
            name="Configuration Phase",
            action="run_configuration_phase",
            params={},
        ),
        WorkflowStep(
            step_id="fast_hooks",
            name="Fast Hooks",
            action="run_fast_hooks_phase",
            params={},
            depends_on=["config"],
        ),
    ],
)

# Create engine and register actions
engine = BasicWorkflowEngine(max_concurrent_steps=3)
engine.register_action("run_configuration_phase", config_handler)
engine.register_action("run_fast_hooks_phase", fast_hooks_handler)

# Execute
result = await engine.execute(fast_workflow, context={"options": options})
```

### Phase 2: Core Migration (3-5 days)

**Goal**: Migrate standard workflow to ACB workflows

**Tasks**:

1. Create `CrackerjackWorkflowEngine` extending `BasicWorkflowEngine`
1. Define workflow for default execution path:
   - Configuration → Fast Hooks → Cleaning → Comprehensive Hooks
1. Implement action handlers wrapping existing phase methods
1. Add conditional step execution based on options flags
1. Integrate with existing event bus

**New File Structure**:

```
crackerjack/workflows/
├── __init__.py
├── engine.py              # CrackerjackWorkflowEngine
├── definitions.py         # Workflow definitions
├── actions.py            # Action handlers
└── adapters.py           # Legacy phase adapters
```

**Workflow Definition Example**:

```python
STANDARD_WORKFLOW = WorkflowDefinition(
    workflow_id="crackerjack-standard",
    name="Standard Quality Workflow",
    steps=[
        WorkflowStep(
            step_id="config",
            name="Configuration",
            action="run_configuration",
            retry_attempts=1,  # Config rarely needs retry
        ),
        WorkflowStep(
            step_id="fast_hooks",
            name="Fast Hooks",
            action="run_fast_hooks",
            depends_on=["config"],
            retry_attempts=2,  # Retry on transient failures
        ),
        WorkflowStep(
            step_id="cleaning",
            name="Code Cleaning",
            action="run_code_cleaning",
            depends_on=["fast_hooks"],
            skip_on_failure=True,  # Optional step
        ),
        WorkflowStep(
            step_id="comprehensive",
            name="Comprehensive Hooks",
            action="run_comprehensive_hooks",
            depends_on=["cleaning"],
            retry_attempts=2,
        ),
        # Publishing and commit steps added conditionally
    ],
)
```

### Phase 3: Advanced Features (2-3 days)

**Goal**: Leverage advanced ACB workflow capabilities

**Tasks**:

1. Implement parallel hook execution within phases
   - Individual hooks as workflow steps with dependencies
   - Example: gitleaks, bandit, skylos can run in parallel
1. Add dynamic workflow composition based on options
1. Implement workflow caching/persistence
1. Add workflow metrics and reporting

**Parallel Hooks Example**:

```python
COMPREHENSIVE_HOOKS_WORKFLOW = WorkflowDefinition(
    workflow_id="comprehensive-hooks",
    name="Comprehensive Quality Checks",
    steps=[
        WorkflowStep(
            step_id="zuban",
            name="Type Checking (Zuban)",
            action="run_hook",
            params={"hook_name": "zuban"},
            parallel=True,  # Can run in parallel
        ),
        WorkflowStep(
            step_id="bandit",
            name="Security Check (Bandit)",
            action="run_hook",
            params={"hook_name": "bandit"},
            parallel=True,  # Can run in parallel
        ),
        WorkflowStep(
            step_id="gitleaks",
            name="Secret Scanning (Gitleaks)",
            action="run_hook",
            params={"hook_name": "gitleaks"},
            parallel=True,  # Can run in parallel
        ),
        # All three run concurrently!
    ],
)
```

### Phase 4: Testing & Validation (2-3 days)

**Goal**: Ensure migration maintains all functionality

**Tasks**:

1. Comprehensive integration testing
1. Performance benchmarking (expect improvements!)
1. Backward compatibility verification
1. Documentation updates

## Benefits Analysis

### Performance Improvements

**Current**: Sequential execution

```
Config (5s) → Fast Hooks (40s) → Cleaning (10s) → Comp Hooks (60s)
Total: 115 seconds
```

**With ACB Workflows**: Parallel where possible

```
Config (5s) → [Fast Hooks (40s) || Cleaning (10s)] → Comp Hooks (60s)
                                                      ├─ zuban (20s) ┐
                                                      ├─ bandit (15s)├─ parallel
                                                      └─ gitleaks (10s)┘
Total: ~75 seconds (35% faster!)
```

### Code Quality Improvements

1. **Declarative > Imperative**

   - Workflow structure is data, not code
   - Easier to understand, test, and modify
   - Can be serialized, versioned, visualized

1. **Better Error Handling**

   - Built-in retry logic
   - Per-step timeout management
   - Clearer failure attribution

1. **Reduced Complexity**

   - Remove custom orchestration logic (~500 lines)
   - Dependency resolution handled by engine
   - State management automatic

1. **Better Testing**

   - Mock individual action handlers
   - Test workflow definitions without execution
   - Easier to test failure scenarios

## Implementation Checklist

### Phase 1: POC

- [ ] Create `crackerjack/workflows/` package
- [ ] Implement basic workflow definition
- [ ] Create sample action handlers
- [ ] Execute and validate output
- [ ] Document findings

### Phase 2: Core Migration

- [ ] Design `CrackerjackWorkflowEngine` class
- [ ] Create workflow definitions for all execution modes
- [ ] Implement action handlers wrapping existing phases
- [ ] Integrate with event bus
- [ ] Update CLI handlers to use workflows
- [ ] Maintain backward compatibility

### Phase 3: Advanced Features

- [ ] Implement hook-level parallelization
- [ ] Add dynamic workflow composition
- [ ] Implement workflow persistence
- [ ] Add metrics and monitoring

### Phase 4: Testing & Docs

- [ ] Write integration tests
- [ ] Benchmark performance
- [ ] Update CLAUDE.md
- [ ] Update README.md
- [ ] Create migration guide

## Risk Mitigation

### Risks

1. **Breaking Changes**: Migration could introduce bugs

   - Mitigation: Feature flag to toggle ACB workflows vs legacy
   - Mitigation: Comprehensive integration testing

1. **Performance Regression**: Unknown overhead from ACB workflows

   - Mitigation: Benchmark early in POC phase
   - Mitigation: Profile with performance monitoring

1. **Complexity Increase**: Learning curve for ACB workflows

   - Mitigation: Excellent ACB documentation
   - Mitigation: Start with simple POC

1. **Event System Compatibility**: Integration challenges

   - Mitigation: ACB workflows already support events
   - Mitigation: Can emit custom events alongside built-in ones

### Success Criteria

✅ All existing functionality preserved
✅ Performance improvement (target: 20-30%)
✅ Code complexity reduction (target: 20% fewer lines)
✅ All tests passing
✅ Clean integration with existing event bus
✅ Improved error messages and debugging

## Timeline Estimate

- **Phase 1 (POC)**: 1-2 days
- **Phase 2 (Core)**: 3-5 days
- **Phase 3 (Advanced)**: 2-3 days
- **Phase 4 (Testing)**: 2-3 days

**Total**: 8-13 days

## Next Steps

1. **Review and approve this plan**
1. **Create feature branch**: `feature/acb-workflow-migration`
1. **Start Phase 1 POC**: Implement fast hooks workflow
1. **Daily progress updates**: Track progress and blockers
1. **Decision point after POC**: Continue or adjust approach

## Open Questions

1. Should we maintain dual orchestrators during migration (legacy + ACB)?
1. Do we want workflow definitions in YAML/JSON for external configuration?
1. Should hook-level parallelization be opt-in or default?
1. How do we handle AI agent coordination with ACB workflows?
1. Should we implement workflow caching for repeated executions?

## References

- ACB Workflows Package: `/Users/les/Projects/acb/acb/workflows/`
- Current Orchestrator: `crackerjack/core/workflow_orchestrator.py`
- BasicWorkflowEngine: `/Users/les/Projects/acb/acb/workflows/engine.py`
- Event System: `crackerjack/events/workflow_bus.py`
