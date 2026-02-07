# Phase 2 Optimization: Eliminate Redundant Tool Execution

## Current State (Inefficient)

```
Tool Execution #1 (Fast Hooks)
  ↓
HookExecutor → HookResult → [DISCARDED]

Tool Execution #2 (QA Adapters)
  ↓
QA Adapter → QAResult.parsed_issues → AI-fix
```

**Problem**: Same tool runs twice, wasting time and resources.

## Proposed State (Optimized)

```
Tool Execution #1 (Fast Hooks)
  ↓
HookExecutor → HookResult + QAResult → Cached
                              ↓
                              Reused by AI-fix (no second execution)
```

## Implementation Strategy

### Option A: QAResult Caching (Recommended)

**Approach**: Modify HookExecutor to return QAResult alongside HookResult.

**Files to Modify**:
1. `crackerjack/executors/hook_executor.py` - Return QAResult from execution
2. `crackerjack/core/autofix_coordinator.py` - Use cached QAResult
3. `crackerjack/models/protocols.py` - Add QAResult to hook result protocols

**Benefits**:
- ✅ Tools run once (50% faster workflow)
- ✅ QA adapters already populate QAResult
- ✅ Minimal code changes
- ✅ Backward compatible (can still fall back to raw parsing)

**Example**:
```python
# In HookExecutor
def execute_hook(self, hook: Hook) -> HookResult:
    """Execute hook and return both HookResult and QAResult."""
    result = hook.run()

    # Try to get QAResult from adapter (if available)
    qa_result = None
    if self._tool_has_qa_adapter(hook.name):
        adapter = self._adapter_factory.create_adapter(hook.name)
        qa_result = adapter.check(config=...)

    return HookResult(
        name=hook.name,
        status=result.status,
        exit_code=result.exit_code,
        duration=result.duration,
        qa_result=qa_result,  # ← NEW: Attach QAResult
    )
```

```python
# In AutofixCoordinator
def _parse_hook_results_to_issues_with_qa(
    self, hook_results: Sequence[object]
) -> list[Issue]:
    """Parse hook results using cached QAResult."""
    issues = []

    for result in hook_results:
        # ✅ Use cached QAResult from HookResult
        if hasattr(result, 'qa_result') and result.qa_result:
            qa_result = result.qa_result
            if qa_result.parsed_issues:
                issues.extend(
                    self._convert_parsed_issues_to_issues(
                        result.name, qa_result.parsed_issues
                    )
                )
                continue

        # ❌ Fallback: Run QA adapter (legacy)
        # ... existing _run_qa_adapters_for_hooks logic

    return issues
```

### Option B: Direct Integration (More Invasive)

**Approach**: QA adapters become the primary hook interface.

**Files to Modify**:
1. All hook implementations
2. HookExecutor
3. Hook registration system

**Benefits**:
- ✅ Cleanest architecture (single path)
- ✅ Maximum performance

**Drawbacks**:
- ❌ Major refactoring (high risk)
- ❌ Breaks existing hook implementations
- ❌ Longer development time

## Migration Path

### Phase 1: QAResult Caching (Quick Win)

**Timeline**: 1-2 days

**Steps**:
1. Add `qa_result` field to HookResult model
2. Modify HookExecutor to populate QAResult during execution
3. Update AutofixCoordinator to use cached QAResult
4. Add tests for caching behavior
5. Measure performance improvement

**Expected Impact**:
- **Performance**: 40-50% faster comprehensive hooks
- **Reliability**: Same tool run = same results (no race conditions)
- **Maintainability**: Simpler workflow (no duplicate execution)

### Phase 2: Adapter-First Architecture (Long-term)

**Timeline**: 1-2 weeks

**Steps**:
1. Design unified hook/adapter interface
2. Refactor hooks to use QA adapters
3. Remove legacy ParserFactory
4. Update all documentation

**Expected Impact**:
- **Performance**: Additional 10-20% improvement
- **Maintainability**: Single code path
- **Consistency**: All tools use same interface

## Performance Estimates

### Current Workflow

```
Fast Hooks: ~5s
  ↓
Tests: ~30s (auto-detect workers)
  ↓
QA Adapters (run #2): ~30s
  ↓
AI-fix: ~60s
---
Total: ~125s
```

### After Phase 1 Optimization

```
Fast Hooks + QA Adapters (cached): ~35s
  ↓
Tests: ~30s
  ↓
AI-fix: ~60s
---
Total: ~125s → ~95s (24% faster)
```

### After Phase 2 Optimization

```
Integrated Hooks: ~35s
  ↓
Tests: ~30s
  ↓
AI-fix: ~60s
---
Total: ~95s → ~85s (32% faster overall)
```

## Risk Assessment

### Phase 1: Low Risk

**Risks**:
- QAResult caching adds complexity to HookExecutor
- Need to handle tools without QA adapters

**Mitigations**:
- Fallback to raw parsing if QAResult unavailable
- Comprehensive tests for caching logic
- Gradual rollout (feature flag)

### Phase 2: Medium Risk

**Risks**:
- Major refactoring of hook system
- Potential breakage of existing hooks
- Longer development time

**Mitigations**:
- Incremental migration
- Extensive testing
- Backward compatibility layer

## Success Criteria

### Phase 1

- [ ] HookExecutor returns QAResult for 23 tools with adapters
- [ ] AutofixCoordinator uses cached QAResult (no re-execution)
- [ ] Performance improvement ≥20% on comprehensive hooks
- [ ] All existing tests pass
- [ ] New tests for caching behavior
- [ ] Zero data loss (same issue counts)

### Phase 2

- [ ] All hooks use QA adapters
- [ ] ParserFactory removed from workflow
- [ ] Additional 10% performance improvement
- [ ] Documentation updated
- [ ] Migration guide for custom hooks

## Recommendations

### Immediate (Next Sprint)

✅ **Implement Phase 1**: QAResult caching

**Why**:
- High ROI (20-30% performance gain)
- Low risk (minimal code changes)
- Quick win (1-2 days)
- Foundation for Phase 2

### Future (Next Quarter)

⏸️ **Plan Phase 2**: Adapter-first architecture

**Why**:
- Requires more design and planning
- Can be done incrementally
- Not blocking current improvements

## Related Documentation

- `docs/features/QA_RESULT_INTEGRATION.md` - Current architecture
- `docs/AI_FIX_EXPECTED_BEHAVIOR.md` - AI-fix workflow
- `crackerjack/executors/hook_executor.py` - Current hook execution
- `crackerjack/core/autofix_coordinator.py` - Current AI-fix coordination
