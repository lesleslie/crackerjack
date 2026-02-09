# AI-Fix Workflow Audit

## Executive Summary

**Current Behavior**: AI-fix stops after only 2 iterations with 5% reduction (104 → 99 issues), claiming "convergence limit reached" despite `max_iterations=10`.

**Problem**: The convergence detection is too aggressive - it stops after only 2 iterations when the agent IS making progress (5 issues fixed).

---

## Configuration Analysis

### Current Settings

**Max Iterations**:
- Default: `5` (from `settings.py`)
- CLI override: `10` (from `--max-iterations 10`)
- Environment variable: `CRACKERJACK_AI_FIX_MAX_ITERATIONS`

**Convergence Threshold**:
- Default: `3` (stops if no progress for 3 consecutive iterations)
- Environment variable: `CRACKERJACK_AI_FIX_CONVERGENCE_THRESHOLD`

### Code Locations

`/Users/les/Projects/crackerjack/crackerjack/core/autofix_coordinator.py`:

```python
# Line 1169-1173
def _get_max_iterations(self) -> int:
    if self._max_iterations is not None:
        return self._max_iterations
    return int(os.environ.get("CRACKERJACK_AI_FIX_MAX_ITERATIONS", "5"))

# Line 1175-1176
def _get_convergence_threshold(self) -> int:
    return int(os.environ.get("CRACKERJACK_AI_FIX_CONVERGENCE_THRESHOLD", "3"))
```

---

## Convergence Detection Logic

### The Problem

Looking at `_check_iteration_completion()` and `_should_stop_on_convergence()`:

```python
def _should_stop_on_convergence(
    self,
    current_count: int,
    previous_count: float,
    no_progress_count: int,
) -> bool:
    convergence_threshold = self._get_convergence_threshold()

    if current_count >= previous_count:  # ← PROBLEM: This counts as "no progress"
        if no_progress_count + 1 >= convergence_threshold:
            return True
    return False
```

**The Issue**:
- If `current_count >= previous_count` (issues stayed same or increased), it's counted as "no progress"
- After 3 consecutive iterations with no reduction, workflow stops
- But the agent IS making progress (104 → 99 = 5 issues fixed)!

**What's Happening**:
- Iteration 0: 104 issues (initial)
- Iteration 1: ? issues (agent runs, might have reduced issues)
- Iteration 2: 99 issues (agent reports "remaining issues: 1" multiple times)
- Workflow stops because `no_progress_count` reached threshold

### Expected Behavior

If agents fix 5 out of 104 issues (5% reduction), that IS progress! The workflow should:
1. Continue until reaching `max_iterations` (10)
2. OR until convergence threshold (3 iterations with ZERO reduction)

---

## Agent Fix Criteria Analysis

### Agent Scoring System

From the agent logs, I see:

```
ArchitectAgent failed to fix issue
Remaining issues: 1
```

**The Problem**: Agents are reporting "failed to fix issue" even when they ARE fixing issues. This suggests:
1. Agents are too conservative in claiming success
2. Each agent only handles 1 issue at a time
3. If 1 agent fails, it counts as "no progress" for the entire iteration

### FixResult Confidence Threshold

Looking at the agent coordinator:

```python
# Agents return FixResult with:
fix_result.success  # Boolean
fix_result.confidence  # Float (0.0-1.0)
fix_result.fixes_applied  # List[str]
fix_result.remaining_issues  # List[Issue]
```

**Current Behavior**:
- Agents only claim `success=True` if they fix ALL issues
- Partial fixes (5/104 issues) count as "failed"
- This triggers the convergence counter

**What Should Happen**:
- Partial fixes (5 issues fixed) should count as PROGRESS
- Only ZERO issues fixed should increment `no_progress_count`
- Workflow should continue for all 10 iterations unless truly stuck

---

## Recommended Changes

### 1. Fix Convergence Detection (HIGH PRIORITY)

**File**: `crackerjack/core/autofix_coordinator.py`

**Current Logic** (WRONG):
```python
if current_count >= previous_count:  # No reduction or got worse
    no_progress_count += 1
```

**Correct Logic**:
```python
if current_count >= previous_count:  # No reduction or got worse
    # Only count as "no progress" if ZERO issues were fixed
    fixes_applied_this_iteration = len(fix_result.fixes_applied) if 'fix_result' in locals() else 0
    if fixes_applied_this_iteration == 0:
        no_progress_count += 1
    else:
        no_progress_count = 0  # Reset - we made progress!
```

### 2. Increase Default Max Iterations

**Current**: `max_iterations=5` (default) or `10` (CLI)
**Recommended**: `max_iterations=10` (default), `20` (CLI)

**Reasoning**:
- With 104 issues, 10 iterations might not be enough
- Agents are working but slowly
- More iterations = more opportunities to fix issues

### 3. Adjust Confidence Threshold

**Current**: Agents claim `success=True` only if confidence ≥0.7 AND all issues fixed
**Recommended**:
- Lower success threshold to count partial fixes as progress
- Track cumulative fixes across all agents in an iteration
- Reset `no_progress_count` if ANY agent makes progress

### 4. Add Progress Metrics

**Add tracking for**:
- Total fixes applied across all iterations
- Cumulative reduction percentage
- Agent success rate (how many agents fixed their assigned issues)

---

## Iteration Behavior Analysis

### What Actually Happened (From Logs)

```
Iteration 0: 104 issues collected
Iteration 1: Agents attempted fixes
Iteration 2: 99 issues remaining (5 fixed)
Workflow stopped: "Convergence limit reached"
```

### Root Cause

The `_update_progress_count()` method increments `no_progress_count` whenever `current_count >= previous_count`:

```python
def _update_progress_count(
    self,
    current_count: int,
    previous_count: float,
    no_progress_count: int,
) -> int:
    if current_count >= previous_count:
        return no_progress_count + 1  # ← PROBLEM
    return 0
```

But this doesn't account for:
1. Issues that WERE fixed (104 → 99 = 5 fixed!)
2. Multiple agents working in parallel
3. Partial progress across the iteration

---

## Recommended Immediate Actions

### Quick Fix (5 minutes)

Change the convergence logic to reset `no_progress_count` when ANY progress is made:

```python
def _update_progress_count(
    self,
    current_count: int,
    previous_count: float,
    no_progress_count: int,
    fixes_applied: int = 0,  # ← NEW PARAMETER
) -> int:
    if fixes_applied > 0:
        return 0  # Reset - we made progress!
    if current_count >= previous_count:
        return no_progress_count + 1
    return 0
```

### Test the Fix

1. Run comprehensive hooks + AI-fix
2. Observe if it continues beyond 2 iterations
3. Check if more issues get fixed

### Expected Result

- Should run for 10 iterations (not just 2)
- Should fix more than 5 issues
- Should only stop if truly stuck (3 iterations with ZERO progress)

---

## Configuration Recommendations

### Increase Iteration Limits

**Add to `settings/crackerjack.yaml`**:

```yaml
# AI Fix Settings
ai_fix:
  max_iterations: 20  # Increased from 10
  convergence_threshold: 5  # Increased from 3 (more patient)
  min_improvement_threshold: 1  # Must fix at least 1 issue per iteration
```

### Environment Variables

**For immediate testing**:
```bash
export CRACKERJACK_AI_FIX_MAX_ITERATIONS=20
export CRACKERJACK_AI_FIX_CONVERGENCE_THRESHOLD=5
python -m crackerjack run --comp --ai-fix
```

---

## Summary

| Issue | Current Behavior | Recommended Fix | Priority |
|-------|-----------------|-----------------|----------|
| **Convergence too aggressive** | Stops after 2 iterations | Only stop if ZERO progress for 5 iterations | HIGH |
| **Partial fixes not counted** | 5 issues fixed = "no progress" | Count ANY fix as progress | HIGH |
| **Max iterations too low** | 10 iterations default | Increase to 20 | MEDIUM |
| **No progress metric unclear** | `current >= previous` | Track `fixes_applied` explicitly | HIGH |

---

## Next Steps

1. **Fix convergence detection logic** (HIGH PRIORITY)
2. **Test with increased iterations** (MEDIUM PRIORITY)
3. **Add better progress tracking** (LOW PRIORITY)
4. **Monitor agent effectiveness** (ONGOING)

---

**Status**: 🔴 AI-fix workflow stopping too early - needs immediate attention
**Impact**: 99 issues remaining that could be auto-fixed if workflow continued
