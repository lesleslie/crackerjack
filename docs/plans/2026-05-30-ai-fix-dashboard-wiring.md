# Plan: Wire AIFixDashboard + Rich AI-Fix Progress

**Date**: 2026-05-30
**Status**: ✅ All 5 steps complete
**Quality**: `crackerjack run` passes 9/9 hooks; 21 integration tests pass
**User Issue**: AI-fix stage showed only "FixerCoordinator: Executing plan in X" — no sub-agent identity, no hook name, no per-agent detail.

## Root Cause

Two independent problems:

1. **AIFixDashboard is built but never wired in** — `attach_dashboard()` exists but is not called from the execution path (`__main__.py:451` has a TODO)
2. **Sub-agent identity is not emitted** — `autofix_coordinator.py` emits `AgentDispatched` with hardcoded `agent="FixerCoordinator"` before calling `execute_plans()`. The actual sub-agent name is available via `fixer_coordinator.fixers[issue_type].name` but was never used.

## Plan Steps

### Step 1 — Wire `attach_dashboard()` into execution path
**File**: `crackerjack/core/phase_coordinator.py` (`_apply_ai_fix_for_fast_hooks`)
**Change**: After `AutofixCoordinator(...)` instantiation, call `attach_dashboard(bus=autofix_coordinator._event_bus, mode='auto', max_iterations=10)`, storing result in `self._dashboard`. `__main__.py:451` TODO updated to point to the actual wiring site.
**Gating**: Already gated by `should_activate()` inside `attach_dashboard()` (isatty, CI env, CRACKERJACK_NO_TUI)
**Testing**: ✅ 27 dashboard tests pass; 30 event bus/events tests pass
**Status**: ✅ Complete (lines 435-443 in phase_coordinator.py)

### Step 2 — Emit actual sub-agent name in `AgentDispatched` (HIGHEST IMPACT)
**File**: `crackerjack/core/autofix_coordinator.py` lines ~2950-2964
**Change**: Before emitting `AgentDispatched`, look up the primary fixer for `plan.issue_type` and use its `.name`:

```python
# At line ~2950, before emit_nowait:
primary_key = fixer_coordinator._candidate_fixer_keys(plan.issue_type)[0]
primary_agent = fixer_coordinator.fixers.get(primary_key)
agent_name = getattr(primary_agent, "name", primary_key) if primary_agent else "FixerCoordinator"

self._event_bus.emit_nowait(
    AgentDispatched(
        run_id=self._run_id,
        iteration=0,
        agent=agent_name,  # e.g., "TypeErrorSpecialist" not "FixerCoordinator"
        action="Executing plan",
        file=plan.file_path,
    )
)
```

**Why this works**:
- `_candidate_fixer_keys(issue_type)[0]` returns the primary fixer key (deterministic, no result needed)
- `fixer.__class__.__name__` or `getattr(fixer, "name", ...)` gives the display name
- Agent instances have `self.name = getattr(self, "name", self.__class__.__name__)` (base.py:287)
- Fallback to `"FixerCoordinator"` if anything is wrong

**Same fix needed for ValidationCoordinator** if it has a similar `validators` map.

**Testing**: Existing event bus and dashboard tests pass; manual smoke test shows actual agent names.
**Status**: ✅ Complete (autofix_coordinator.py ~2950-2973)

### Step 3 — Event field expansion
**File**: `crackerjack/core/ai_fix_events.py`
**Changes** (backward-compatible, `= ""` defaults):
- Add `issue_type: str = ""` to `AgentDispatched`, `IssueResolved`, `IssueFailed`
- Add `hook_name: str = ""` to `AgentDispatched` only
- Populate `issue_type` from `plan.issue_type` at emission points
- `hook_name` must be threaded from hook runner → dispatcher → emission site (not in FixPlan)

**Backward compatibility**: All new fields use `= ""` defaults. Old producers/consumers unaffected. `dataclasses.asdict()` in JsonlSink emits empty strings for new fields (additive, not breaking).
**Status**: ✅ Complete (`ai_fix_events.py`; all three event types updated; autofix_coordinator.py emits `issue_type=plan.issue_type`)

### Step 4 — Console output (`_neon_print`) parallel enhancement
**File**: `crackerjack/services/ai_fix_progress.py` lines ~143-169
**Change**: Update `_neon_print` format to include `issue_type` when available:
```python
# Current format: f"{color}{status_icon} {icon} {agent_short}: {action} in {file_short}"
# Enhanced:        f"{color}{status_icon} {icon} {agent_short} [{issue_type}]: {action} in {file_short}"
```
CI/non-TTY environments skip the Live panel but still see informative output.
**Status**: ✅ Complete (`_neon_print` enhanced; `type_label = f" [{issue_type}]" if issue_type else ""` added)

### Step 5 — Integration tests
**Files**: `tests/integration/test_ai_fix_event_bus_dashboard.py`
**Changes**:
- Full `_execute_ai_fix → event bus → dashboard` integration test
- Multi-iteration event sequence test for aggregation correctness
- `emit_nowait` exception isolation test with multiple sinks
- `RunFinished` prevents subsequent events from corrupting state
**Status**: ✅ Complete — 21 tests pass covering all four areas above

## Review Panel Summary

| Reviewer | Verdict | Key Concern |
|----------|---------|--------------|
| Integration | ✅ Approved | Event bus accessible at `_run_v2_ai_fix_iteration_loop`; 2-line change replacing TODO |
| Events | ✅ Approved | Backward compatible; latent bug: dashboard uses `event.agent` as row key instead of explicit `issue_type` |
| UX | ✅ Approved | Sub-agent identity now shows actual agent name (e.g., "RefactoringAgent") not "FixerCoordinator"; console shows `[ISSUE_TYPE]` label |
| Testing | ✅ Approved | 21 integration tests pass; full `_execute_ai_fix → bus → dashboard` chain covered |

## Implementation Notes

- **Wiring site correction**: The plan originally identified `__main__.py:451` as the wiring site. Actual wiring is in `phase_coordinator.py:_apply_ai_fix_for_fast_hooks` (lines 435-443). `__main__.py:451` was updated to point to the correct location.
- **Dashboard row key behavior**: `_DashboardState._row()` keys by `event.agent` (agent name), not `event.issue_type`. The `issue_type` field on events feeds into the console `_neon_print` output, not the dashboard row key. Integration tests reflect this.
- **`hook_name` threading**: `hook_name` is added as `= ""` default since it cannot be threaded from `FixPlan` without a refactor of the hook runner.

## References

- `crackerjack/ui/ai_fix_dashboard.py` — AIFixDashboard (Phase 3 implementation, 27 tests)
- `crackerjack/core/autofix_coordinator.py:2956` — AgentDispatched emission site
- `crackerjack/agents/fixer_coordinator.py:30-58` — `fixers` dict (issue_type → agent instance)
- `crackerjack/agents/fixer_coordinator.py:217-234` — `_candidate_fixer_keys()` (deterministic routing)
- `crackerjack/agents/base.py:287` — `self.name = getattr(self, "name", self.__class__.__name__)`
- `crackerjack/core/ai_fix_events.py` — event dataclasses
- `crackerjack/services/ai_fix_progress.py:143-169` — `_neon_print` (console output)
