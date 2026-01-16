# AI Auto-Fix Workflow Analysis

## Executive Summary

The `--ai-fix` flag is **non-functional** for comprehensive hook failures. While the environment variable `AI_AGENT=1` is set, there is NO code path that checks this variable and invokes AI agents for batch fixing.

**Root Cause**: Missing integration between workflow phase coordinator and AI agent system.

## Current Architecture

### Existing Components

#### 1. AI Agent System ✅ (Implemented)
- **Location**: `/crackerjack/agents/coordinator.py`
- **Class**: `AgentCoordinator`
- **Capabilities**:
  - 12 specialized AI agents (RefactoringAgent, SecurityAgent, TestCreationAgent, etc.)
  - `handle_issues()` method for batch issue processing
  - `handle_issues_proactively()` for architectural planning
  - Confidence-based agent selection
  - Fix validation and caching

#### 2. Agent Orchestrator ✅ (Implemented)
- **Location**: `/crackerjack/intelligence/agent_orchestrator.py`
- **Class**: `AgentOrchestrator`
- **Capabilities**:
  - Multi-strategy execution (single_best, parallel, sequential, consensus)
  - Async agent invocation
  - Fallback mechanisms

#### 3. Autofix Coordinator ⚠️ (Incomplete)
- **Location**: `/crackerjack/core/autofix_coordinator.py`
- **Class**: `AutofixCoordinator`
- **Current Implementation**:
  - `_apply_fast_stage_fixes()`: Runs ruff format/check ✅
  - `_apply_comprehensive_stage_fixes()`: Only runs ruff + bandit ❌
  - **MISSING**: No AI agent invocation

### The Missing Link

**PhaseCoordinator** should invoke AI agents after comprehensive hooks fail, but doesn't:

```python
# crackerjack/core/phase_coordinator.py
def run_comprehensive_hooks_phase(self, options: OptionsProtocol) -> bool:
    """Phase 3: Comprehensive quality checks (type checking, security)."""
    # Runs comprehensive hooks
    # If success: complete_task
    # If failure: fail_task
    # MISSING: No call to AI batch fixing phase ❌
```

## Expected Workflow vs Actual

### Expected Workflow (from documentation)

```
1. Config cleanup ✅
2. Configuration updates ✅
3. Fast hooks ✅ (15/15 passed)
4. Comprehensive hooks ❌ (8/11 passed - 47 failures)
5. AI batch fixing ← MISSING! ❌
6. Retry hooks
```

### Actual Workflow

```
1. Config cleanup ✅
2. Configuration updates ✅
3. Fast hooks ✅ (15/15 passed)
4. Comprehensive hooks ❌ (8/11 passed)
5. Workflow failure ← STOPS HERE ❌
```

## Comprehensive Hook Failures (47 issues)

### zuban (20 type checking issues)
**Category**: Type checking errors
**Examples**:
- Console vs ConsoleInterface protocol mismatches
- Path | None division errors
- Missing type annotations

### complexipy (10 complexity issues)
**Category**: Cyclomatic complexity
**Location**: All in `__main__.py` (likely acceptable for main entry point)

### refurb (17 refactoring suggestions)
**Category**: Python modernization
**Examples**:
- FURB109: Replace `in` with `in (x, y, z)` (3 instances)
- FURB107: Replace `try: ... except Exception: pass` with `contextlib.suppress()` (3 instances)
- FURB117: Replace `open()` with `Path.open()` (6 instances)
- FURB103: Replace file write with `Path.write_text()` (1 instance)
- FURB188: Use `str.removesuffix()` (1 instance)

## Implementation Requirements

### Phase 1: Enable AI Agent Invocation

**File**: `crackerjack/core/autofix_coordinator.py`

**Add method**:
```python
def _apply_comprehensive_stage_fixes(self, hook_results: list[object]) -> bool:
    """Apply AI agent-based fixing for comprehensive hook failures."""
    import os

    # Check if AI agent mode is enabled
    if not os.environ.get("AI_AGENT") == "1":
        self.logger.info("AI agent fixing not enabled (AI_AGENT env var not set)")
        return False

    # Parse hook failures into Issue objects
    issues = self._parse_hook_results_to_issues(hook_results)
    if not issues:
        return True

    # Invoke AgentCoordinator
    from crackerjack.agents.coordinator import AgentCoordinator
    from crackerjack.agents.base import AgentContext

    context = AgentContext(
        root_path=self.pkg_path,
        verbose=os.environ.get("AI_AGENT_VERBOSE") == "1",
        debug=os.environ.get("AI_AGENT_DEBUG") == "1",
    )

    coordinator = AgentCoordinator(context)
    coordinator.initialize_agents()

    # Run AI batch fixing
    import asyncio

    result = asyncio.run(coordinator.handle_issues(issues))

    return result.success
```

### Phase 2: Hook Result Parsing

**Add method to AutofixCoordinator**:
```python
def _parse_hook_results_to_issues(self, hook_results: list[object]) -> list[Issue]:
    """Parse hook results into Issue objects for AI agents."""
    from crackerjack.agents.base import Issue, IssueType, Priority

    issues = []
    for result in hook_results:
        if not self._validate_hook_result(result):
            continue

        if getattr(result, "status", "") != "Failed":
            continue

        hook_name = getattr(result, "name", "")
        raw_output = getattr(result, "raw_output", "")

        # Map hook names to issue types
        issue_type = self._map_hook_to_issue_type(hook_name)
        severity = Priority.HIGH if hook_name in ["zuban", "bandit"] else Priority.MEDIUM

        # Parse individual issues from raw_output
        parsed_issues = self._parse_raw_output_to_issues(
            hook_name, raw_output, issue_type, severity
        )
        issues.extend(parsed_issues)

    return issues
```

### Phase 3: Update PhaseCoordinator

**File**: `crackerjack/core/phase_coordinator.py`

**Modify** `run_comprehensive_hooks_phase()`:
```python
def run_comprehensive_hooks_phase(self, options: OptionsProtocol) -> bool:
    """Phase 3: Comprehensive quality checks (type checking, security)."""
    # ... existing comprehensive hooks code ...

    if not success:
        self.task_tracker.fail_task("comprehensive_hooks")

        # NEW: Try AI batch fixing if enabled
        if options.ai_fix:  # Check ai_fix flag from options
            self.console.print("\n[bold yellow]🤖 Attempting AI batch fixing...[/bold yellow]\n")

            autofix_result = self.autofix_coordinator.apply_comprehensive_stage_fixes(
                hook_results
            )

            if autofix_result:
                self.console.print("[green]✅ AI batch fixing completed, retrying hooks...[/green]")
                # Retry comprehensive hooks after AI fixes
                return self._run_comprehensive_hooks(options)

        return False

    self.task_tracker.complete_task("comprehensive_hooks")
    return True
```

## Testing Strategy

### Unit Tests
1. Test `_parse_hook_results_to_issues()` with various hook outputs
2. Test AI agent invocation with mock issues
3. Test environment variable checking

### Integration Tests
1. Test full workflow with `--ai-fix` flag
2. Verify AI agents are called for comprehensive failures
3. Verify fixes are applied and hooks re-run

### Manual Testing
```bash
# Test AI auto-fixing
python -m crackerjack run --ai-fix -v

# Expected behavior:
# 1. Fast hooks run and pass
# 2. Comprehensive hooks run and fail
# 3. AI agents are invoked to fix failures
# 4. Comprehensive hooks are retried
# 5. Workflow succeeds if fixes were successful
```

## Current Workarounds

### Manual AI Agent Invocation
```python
import asyncio
from crackerjack.agents.coordinator import AgentCoordinator
from crackerjack.agents.base import AgentContext, Issue, IssueType, Priority

# Create context
context = AgentContext(root_path=Path.cwd())
coordinator = AgentCoordinator(context)
coordinator.initialize_agents()

# Create issues from hook failures
issues = [
    Issue(
        id="1",
        type=IssueType.TYPE_ERROR,
        severity=Priority.HIGH,
        message="Console vs ConsoleInterface type mismatch",
        file_path="crackerjack/core/phase_coordinator.py",
        line_number=178,
    ),
    # ... more issues ...
]

# Run AI fixing
result = asyncio.run(coordinator.handle_issues(issues))
```

## Priority Assessment

**Severity**: High
**Impact**: Major feature gap - documented feature doesn't work
**Risk**: Low - AI agents exist and work, just need integration

## Recommendations

1. **Immediate**: Implement AI agent invocation in `AutofixCoordinator`
2. **Short-term**: Add comprehensive hook result parsing
3. **Medium-term**: Implement retry logic after AI fixes
4. **Long-term**: Add AI fix success/failure reporting and metrics

## Related Files

- `/crackerjack/agents/coordinator.py` - AI agent coordination
- `/crackerjack/intelligence/agent_orchestrator.py` - Agent orchestration
- `/crackerjack/core/autofix_coordinator.py` - Auto-fix coordination (needs update)
- `/crackerjack/core/phase_coordinator.py` - Workflow orchestration (needs update)
- `/crackerjack/cli/handlers/main_handlers.py` - Environment variable setup (working)
