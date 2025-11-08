# AI Agent Integration Design for ACB Workflows

## Overview

This document defines how AI agents (`EnhancedAgentCoordinator` and associated agents) integrate with ACB workflow execution for automated error fixing.

## Current AI Agent Architecture

```python
# Current: EnhancedAgentCoordinator in crackerjack/agents/enhanced_coordinator.py
class EnhancedAgentCoordinator:
    """Coordinates AI agents for automated fixing."""

    def process_issues(
        self,
        issues: list[Issue],
        context: AgentContext,
        max_iterations: int = 3,
    ) -> tuple[list[Fix], list[Issue]]:
        """Process issues and generate fixes."""
```

**Key Components:**

- **12 Specialized Agents**: RefactoringAgent, SecurityAgent, TestCreationAgent, etc.
- **AgentContext**: Dataclass with project path, console, settings
- **Issue Model**: Type (error/warning), priority, file location, description
- **Fix Model**: File changes, confidence score, rationale

## Integration Strategy: Post-Workflow AI Fixing

### Phase 1-2: Post-Workflow Approach (RECOMMENDED)

**Concept**: AI agents run AFTER workflow completes, analyzing failures.

**Advantages:**

- ✅ Minimal integration complexity
- ✅ Preserves existing agent logic
- ✅ Clear separation of concerns
- ✅ Easy to test independently

**Implementation:**

```python
# In workflow_orchestrator.py or new ai_workflow_adapter.py


async def run_workflow_with_ai_fixing(
    engine: CrackerjackWorkflowEngine,
    workflow: WorkflowDefinition,
    options: OptionsProtocol,
) -> tuple[WorkflowResult, list[Fix]]:
    """Execute workflow and apply AI fixing if enabled and needed."""

    # Execute workflow
    result = await engine.execute(workflow, context={"options": options})

    # Check if AI fixing needed
    if not options.ai_agent:
        return (result, [])

    if result.state == WorkflowState.COMPLETED:
        return (result, [])  # No fixes needed

    # Extract issues from failed steps
    issues = extract_issues_from_workflow_result(result)

    # Run AI coordinator
    coordinator = EnhancedAgentCoordinator(...)
    agent_context = create_agent_context(options, result)
    fixes, remaining_issues = coordinator.process_issues(
        issues, agent_context, max_iterations=3
    )

    # Apply fixes if any
    if fixes:
        await apply_fixes_and_rerun(engine, workflow, fixes, options)

    return (result, fixes)


def extract_issues_from_workflow_result(result: WorkflowResult) -> list[Issue]:
    """Convert failed step results to Issue objects."""
    issues = []

    for step_result in result.steps:
        if step_result.state == StepState.FAILED:
            issue = Issue(
                type=IssueType.ERROR,
                priority=Priority.HIGH,
                file=step_result.metadata.get("file", "unknown"),
                line=step_result.metadata.get("line"),
                description=step_result.error or "Step failed",
                category=step_result.step_id,  # e.g., "zuban", "bandit"
            )
            issues.append(issue)

    return issues
```

**Workflow:**

```
1. Execute ACB workflow
   ↓
2. Workflow completes with failures
   ↓
3. If --ai-fix flag set:
   ↓
4. Extract issues from failed steps
   ↓
5. Run EnhancedAgentCoordinator.process_issues()
   ↓
6. Apply fixes
   ↓
7. Re-run workflow
   ↓
8. Repeat up to max_iterations (default: 3)
```

### Phase 3: Integrated AI Step (OPTIONAL, FUTURE)

**Concept**: AI fixing as a workflow step with conditional execution.

**Workflow Definition:**

```python
STANDARD_WORKFLOW_WITH_AI = WorkflowDefinition(
    workflow_id="standard-with-ai",
    steps=[
        WorkflowStep(step_id="config", action="run_config"),
        WorkflowStep(step_id="fast", action="run_fast", depends_on=["config"]),
        WorkflowStep(step_id="comp", action="run_comp", depends_on=["fast"]),
        # AI fixing step runs even if previous steps failed
        WorkflowStep(
            step_id="ai_fix",
            action="run_ai_coordinator",
            depends_on=["comp"],
            skip_on_failure=False,  # Run even if comp failed
            retry_attempts=3,  # Auto-retry with fixes
        ),
    ],
)
```

**Action Handler:**

```python
async def run_ai_coordinator_action(
    context: dict[str, Any],
    step_id: str,
    **params,
) -> Any:
    """AI coordination action handler."""
    options = context["options"]
    previous_steps = context.get("previous_steps", [])

    # Check if AI fixing needed
    if not options.ai_agent:
        return None  # Skip

    # Get failures from previous steps
    failed_steps = [s for s in previous_steps if s.state == StepState.FAILED]
    if not failed_steps:
        return None  # No fixes needed

    # Extract issues
    issues = [extract_issue_from_step(s) for s in failed_steps]

    # Run coordinator
    coordinator = EnhancedAgentCoordinator(...)
    agent_context = create_agent_context(options, context)
    fixes, remaining = coordinator.process_issues(issues, agent_context)

    # Apply fixes
    if fixes:
        apply_fixes(fixes)
        # Re-run failed steps (workflow engine handles this via retry)
        return {"fixes_applied": len(fixes), "remaining_issues": len(remaining)}

    return None
```

## Implementation Details

### Issue Extraction

**Map step failures to Issue objects:**

```python
def extract_issue_from_step_result(step_result: StepResult) -> Issue:
    """Convert step failure to Issue."""

    # Parse error message for file/line info
    error_text = step_result.error or ""

    # Example: "crackerjack/core/workflow.py:123: E501 line too long"
    match = re.match(r"(.+?):(\d+):\s*(.+)", error_text)

    if match:
        file, line, message = match.groups()
        return Issue(
            type=IssueType.ERROR,
            priority=Priority.HIGH,
            file=file,
            line=int(line),
            description=message,
            category=step_result.step_id,
        )

    # Fallback: Generic issue
    return Issue(
        type=IssueType.ERROR,
        priority=Priority.MEDIUM,
        file="unknown",
        description=error_text,
        category=step_result.step_id,
    )
```

### Agent Context Creation

**Create AgentContext from workflow context:**

```python
def create_agent_context(
    options: OptionsProtocol,
    workflow_result: WorkflowResult | None = None,
) -> AgentContext:
    """Create AgentContext for AI coordinator."""

    from crackerjack.agents.base import AgentContext
    from acb.depends import depends
    from acb.console import Console

    console = depends.get(Console)

    return AgentContext(
        project_root=Path.cwd(),
        console=console,
        debug_mode=getattr(options, "ai_debug", False),
        max_iterations=getattr(options, "max_ai_iterations", 3),
        confidence_threshold=0.7,
        metadata={
            "workflow_id": workflow_result.workflow_id if workflow_result else None,
            "workflow_state": workflow_result.state.value if workflow_result else None,
        },
    )
```

### Fix Application

**Apply fixes and trigger re-run:**

```python
async def apply_fixes_and_rerun(
    engine: CrackerjackWorkflowEngine,
    workflow: WorkflowDefinition,
    fixes: list[Fix],
    options: OptionsProtocol,
    max_retries: int = 3,
) -> WorkflowResult:
    """Apply fixes and re-run workflow."""

    for attempt in range(max_retries):
        # Apply fixes
        for fix in fixes:
            apply_single_fix(fix)

        # Re-run workflow
        result = await engine.execute(workflow, context={"options": options})

        # Success?
        if result.state == WorkflowState.COMPLETED:
            return result

        # More fixes needed?
        new_issues = extract_issues_from_workflow_result(result)
        if not new_issues:
            break  # No more issues, but workflow still failed

        # Get more fixes
        coordinator = EnhancedAgentCoordinator(...)
        context = create_agent_context(options, result)
        fixes, _ = coordinator.process_issues(new_issues, context)

        if not fixes:
            break  # No more fixes available

    return result


def apply_single_fix(fix: Fix) -> None:
    """Apply a single fix to the codebase."""
    if fix.file_changes:
        for file_path, new_content in fix.file_changes.items():
            Path(file_path).write_text(new_content)
```

## Integration Points

### 1. CLI Handler Integration

```python
# In crackerjack/cli/handlers.py


@depends.inject
async def handle_standard_mode_with_acb(
    options: Options,
    console: Inject[Console],
) -> None:
    """Handle standard mode using ACB workflows."""

    # Create workflow engine
    engine = CrackerjackWorkflowEngine()

    # Select workflow
    workflow = select_workflow_for_options(options)

    # Execute with AI fixing
    result, fixes = await run_workflow_with_ai_fixing(engine, workflow, options)

    # Report results
    if fixes:
        console.print(f"[green]✅ Applied {len(fixes)} AI fixes[/green]")

    if result.state != WorkflowState.COMPLETED:
        raise SystemExit(1)
```

### 2. Event Integration

**Emit events for AI fixing:**

```python
# Emit AI fixing events
await event_bus.publish(
    WorkflowEvent.AI_FIXING_STARTED,
    {"workflow_id": result.workflow_id, "issue_count": len(issues)},
)

# ... run AI coordinator ...

await event_bus.publish(
    WorkflowEvent.AI_FIXING_COMPLETED,
    {
        "workflow_id": result.workflow_id,
        "fixes_applied": len(fixes),
        "remaining_issues": len(remaining_issues),
    },
)
```

## Testing Strategy

### Unit Tests

```python
def test_extract_issue_from_step_result():
    """Test issue extraction from step failure."""
    step_result = StepResult(
        step_id="zuban",
        state=StepState.FAILED,
        error="crackerjack/core/workflow.py:123: E501 line too long",
    )

    issue = extract_issue_from_step_result(step_result)

    assert issue.file == "crackerjack/core/workflow.py"
    assert issue.line == 123
    assert "E501" in issue.description


def test_create_agent_context():
    """Test AgentContext creation from options."""
    options = Options(ai_debug=True, max_ai_iterations=5)

    context = create_agent_context(options)

    assert context.debug_mode is True
    assert context.max_iterations == 5
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_workflow_with_ai_fixing():
    """Test complete workflow with AI fixing."""
    # Create workflow that will fail
    workflow = WorkflowDefinition(
        steps=[
            WorkflowStep(step_id="fail", action="failing_action"),
        ]
    )

    # Execute with AI fixing
    options = Options(ai_agent=True)
    result, fixes = await run_workflow_with_ai_fixing(engine, workflow, options)

    # Verify fixes were attempted
    assert len(fixes) > 0
```

## Success Criteria

**Phase 1-2:**

- ✅ AI agents work with `--ai-fix` flag
- ✅ Issues extracted correctly from failed steps
- ✅ Fixes applied and workflow re-runs
- ✅ Event emissions for AI fixing
- ✅ Test coverage ≥ existing

**Phase 3 (Optional):**

- ✅ AI fixing as workflow step
- ✅ Conditional execution (skip if no failures)
- ✅ Retry logic with fixes

## Migration Checklist

- [x] Design post-workflow AI integration approach
- [ ] Implement `extract_issues_from_workflow_result()`
- [ ] Implement `create_agent_context()`
- [ ] Implement `apply_fixes_and_rerun()`
- [ ] Implement `run_workflow_with_ai_fixing()`
- [ ] Add AI fixing events to event bus
- [ ] Update CLI handlers to use AI integration
- [ ] Add unit tests for issue extraction
- [ ] Add integration tests for AI workflow
- [ ] Document AI integration in CLAUDE.md

## Open Questions

1. **Should AI fixing be automatic or require confirmation?**
   → Start with automatic (existing behavior), add `--ai-confirm` flag later

1. **How many retry iterations?**
   → Default to 3 (existing), configurable via `--max-ai-iterations`

1. **What if AI fixes introduce new errors?**
   → Track fix success rate, abort after 3 failed fix attempts

1. **Should we persist fix history?**
   → Phase 3 feature, not MVP

## References

- Current AI Agent Coordinator: `crackerjack/agents/enhanced_coordinator.py`
- Issue/Fix Models: `crackerjack/agents/base.py`
- Existing AI integration: `crackerjack/core/workflow_orchestrator.py` (lines 1400-1500)
