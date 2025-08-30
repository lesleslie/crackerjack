# AI Agent Workflow Rules

## Core AI Agent Iteration Protocol

**CRITICAL**: The AI agent must follow this exact workflow order to ensure fixes are applied between iterations.

### Iteration Sequence (MANDATORY)

Each iteration follows this strict sequence:

1. **Fast Hooks Phase** (Formatting & Quick Fixes)

   - Run: `trailing-whitespace`, `end-of-file-fixer`, `ruff-format`, `ruff-check`, `gitleaks`
   - **Retry Logic**: If any fast hooks fail, retry once (formatting fixes often cascade)
   - **Proceed Only When**: Fast hooks pass OR have been retried once

1. **Test Collection Phase** (Don't Stop on First Failure)

   - Run complete test suite: `uv run pytest`
   - **Collect ALL test failures** - don't stop on first failure
   - **Return**: List of all test issues found

1. **Comprehensive Hooks Phase** (Don't Stop on First Failure)

   - Run: `pyright`, `bandit`, `vulture`, `refurb`, `creosote`, `complexipy`
   - **Collect ALL hook issues** - don't stop on first failure
   - **Return**: List of all quality issues found

1. **AI Fixing Phase** (CRITICAL STEP)

   - **Process ALL collected issues in batch** (tests + hooks)
   - **Apply fixes to source code** using AI agent analysis
   - **ONLY AFTER fixes are applied**, proceed to next iteration

1. **Validation Phase** (Next Iteration)

   - Next iteration validates that fixes from previous iteration worked
   - If all checks pass, workflow completes successfully
   - If issues remain, repeat cycle (max 10 iterations)

### Implementation Architecture

```python
# AsyncWorkflowOrchestrator._execute_ai_agent_workflow_async()
for iteration in range(1, max_iterations + 1):
    # Step 1: Fast hooks with retry
    fast_hooks_success = await self._run_fast_hooks_with_retry_async(options)

    # Step 2: Collect ALL test issues (don't stop on first)
    test_issues = await self._collect_test_issues_async(options)

    # Step 3: Collect ALL hook issues (don't stop on first)
    hook_issues = await self._collect_comprehensive_hook_issues_async(options)

    # Exit if everything passes
    if fast_hooks_success and not test_issues and not hook_issues:
        break

    # Step 4: Apply AI fixes for ALL collected issues
    fix_success = await self._apply_ai_fixes_async(
        options, test_issues, hook_issues, iteration
    )
    if not fix_success:
        return False  # Fail the workflow
```

## Critical Design Principles

### 1. No Early Exit During Collection

- **WRONG**: Stop on first test failure or first hook failure
- **CORRECT**: Collect ALL failures before moving to fixing phase

### 2. Batch Fixing Approach

- **WRONG**: Fix one issue, then re-run checks, then fix next issue
- **CORRECT**: Collect all issues, then apply all fixes in one batch

### 3. Iteration Boundaries

- **WRONG**: Apply fixes in the middle of an iteration
- **CORRECT**: Apply fixes ONLY at the end of iteration, validate in next iteration

### 4. Progress Validation

- **WRONG**: Assume fixes worked without validation
- **CORRECT**: Next iteration validates that previous fixes were successful

## MCP Server Integration

### Orchestrator Selection

- **Standard Orchestrator**: Use for MCP server compatibility
- **Advanced Orchestrator**: Internal iteration loop conflicts with MCP progress reporting
- **Forced Selection**: MCP server forces standard orchestrator in `execution_tools.py:274-292`

### WebSocket Progress Reporting

- **Real-time Updates**: Each phase reports progress via WebSocket
- **Job Tracking**: Progress available at `ws://localhost:8675/ws/progress/{job_id}`
- **Iteration Tracking**: Clear iteration boundaries for progress monitoring

## Error Patterns to Avoid

### 1. Missing AI Fixing Stage

```python
# WRONG: Just run checks in loop without applying fixes
for iteration in range(max_iterations):
    if run_checks():
        break  # No fixes applied!
```

### 2. Early Exit on First Failure

```python
# WRONG: Stop collecting issues on first failure
if test_fails:
    return False  # Missing other issues!
```

### 3. Iteration Logic Without Fixes

```python
# WRONG: Iterate without applying fixes between iterations
for i in range(10):
    run_same_checks()  # Same failures every iteration
```

## Validation Commands

Test the AI agent workflow:

```bash
# Standard AI agent workflow
python -m crackerjack --ai-agent -t

# MCP server workflow (uses AI agent logic)
python -m crackerjack --start-mcp-server
# Then use /crackerjack:run in Claude

# Debug AI agent workflow
python -m crackerjack --ai-debug -t
```

## Success Criteria

The AI agent workflow is working correctly when:

1. **Progress Through Iterations**: Each iteration shows different results as fixes are applied
1. **Issue Reduction**: Number of issues decreases between iterations
1. **Eventual Success**: Workflow completes with all checks passing
1. **No Infinite Loops**: Workflow terminates within 10 iterations
1. **Real-time Progress**: WebSocket shows meaningful progress updates

## Failure Indicators

The AI agent workflow is broken when:

1. **Same Issues Every Iteration**: No fixes being applied between iterations
1. **Stuck on Single Issue**: Same failure repeats across all iterations
1. **No Progress Updates**: WebSocket shows no meaningful progress
1. **Quick Cycling**: 10 iterations complete very quickly without fixes
1. **Missing Phases**: Skipping test or comprehensive hook phases
