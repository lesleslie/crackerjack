# AI-fix no-op circuit breaker — design

**Date:** 2026-07-11
**Status:** Approved (hard skip after 2 identical plans chosen)
**Scope:** 1 modified file, 1 new test file
**Cluster:** 4 (no-op fix detection — 1 pure entry in ty_imports.py showing 3 identical no-op plans)

## Problem

The AI-fix loop's per-issue retry path retries plans up to 3 times. When the planner produces a plan that the LLM cannot execute (no-op: file content unchanged), the loop wastes all 3 attempts retrying the same plan.

Latest AI-fix log evidence (`crackerjack/logs/ai-fix-errors-20260711-025727.json`):

```
crackerjack/tools/ty_imports.py: Failed after 3 attempts:
  Attempt 1: no-op fix: file content unchanged
  Attempt 2: no-op fix: file content unchanged
  Attempt 3: no-op fix: file content unchanged
```

Two other files show the same pattern post-timeout (`autofix_coordinator.py`, `ty_narrow.py`), where attempt 1 times out and attempts 2-3 produce no-ops — same wasted pattern.

`TightenedFixerDispatcher.dispatch_with_bytes_check` (in `crackerjack/ai_fix/tightened_dispatcher.py:19-37`) correctly detects no-op fixes and returns a `FixResult` with `success=False, remaining_issues=["no-op fix: file content unchanged"]`. The validation works as designed. The fix is in the loop that retries the same broken plan.

## Goals

1. Stop the retry loop early when 2 consecutive plan signatures match — the third attempt has zero chance of producing a different outcome.
1. Surface the "stuck" condition with a distinct reason so the AI-fix log distinguishes "no-op" from "stuck: planner producing identical plans".
1. Keep existing single-attempt success behavior unchanged (don't break the happy path).

## Non-goals

- Don't diagnose WHY the planner produces identical plans (separate investigation; out of scope).
- Don't add randomness or plan mutations to break determinism.
- Don't change the per-issue timeout, the regen timeout, or the global retry budget.
- Don't replace `TightenedFixerDispatcher` — it stays as-is.

## Architecture

### Component 1: `_plan_signature` static method (new on `AutofixCoordinator`)

A stable, content-derived hash of a `FixPlan` that:

- Includes `issue_type`, `file_path`, and the sorted tuple of change tuples `(line_range, old_code, new_code, reason)`.
- Excludes unstable fields like `rationale` (free-form) or timestamps.
- Uses Python's built-in `hashlib.sha256` over the JSON-serialized stable representation — guarantees deterministic across processes.

```python
import hashlib
import json

@staticmethod
def _plan_signature(plan: FixPlan) -> str:
    """Stable content hash for a FixPlan (excludes free-form rationale)."""
    stable = {
        "issue_type": plan.issue_type,
        "file_path": str(plan.file_path),
        "changes": sorted(
            (
                tuple(c.line_range),
                c.old_code,
                c.new_code,
                c.reason,
            )
            for c in plan.changes
        ),
    }
    raw = json.dumps(stable, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]
```

Place this method adjacent to `_get_regen_timeout` (cluster-3 fix landed at lines 1654-1662), to keep related planning helpers together.

### Component 2: Wire circuit breaker into the retry loop

In `crackerjack/core/autofix_coordinator.py:4329` (the `for attempt in range(3):` loop), add:

1. Before the loop: `_previous_signature: str | None = None`.
1. After `success, plan_results, feedback = await asyncio.wait_for(...)` returns successfully (no timeout/OSError):
   - If `not success` AND `any("no-op fix:" in ri for ri in (result.remaining_issues or []) for result in plan_results if result)`:
     - Compute `_current_signature = self._plan_signature(plan)`.
     - If `_current_signature == _previous_signature`, **break out of the loop** with a new failure reason `"stuck: planner producing identical plans"`.
     - Else: `_previous_signature = _current_signature`.
1. If `_previous_signature is None` (no no-op ever seen), the loop continues normally.

The break-out path:

- Returns a `FixResult(success=False, reason="stuck: planner producing identical plans", ...)` (via the existing `_fail_plan` helper if available, or inline construction).
- Logs at WARNING level so the AI-fix error log shows a distinct pattern.
- Preserves `accumulated_feedback` for downstream consumers.

**Note**: in the current code, all 3 attempts use the SAME `plan` variable (the regen happens in a different code path at line 4473-4484). So `_current_signature` will always equal `_previous_signature` after the first no-op. The break fires after attempt 2 (second no-op in a row), saving the third attempt — matches the user's "hard skip after 2 identical plans" choice.

If a future change makes the retry loop regenerate plans (per the 2026-07-07 design doc PR 6 FixRouter), this same circuit breaker correctly skips when regeneration produces the same hash as the original.

### Component 3: Tests

New file: `tests/unit/core/test_autofix_no_op_circuit_breaker.py`

Tests:

1. **`test_plan_signature_is_stable_for_identical_plans`** — two `FixPlan` instances with the same content produce the same signature.
1. **`test_plan_signature_differs_for_distinct_plans`** — different `file_path`, `issue_type`, or `changes` produce different signatures.
1. **`test_plan_signature_ignores_rationale`** — two plans differing only in `rationale` produce the same signature (rationale is free-form).
1. **`test_circuit_breaker_skips_after_two_no_op_results`** — call the retry loop with a stub that always produces a no-op result; verify only 2 attempts are made (not 3) and the returned reason is `"stuck: planner producing identical plans"`.
1. **`test_circuit_breaker_does_not_trigger_for_different_failures`** — first attempt no-op, second attempt timeout (different signature won't match, but the test is for non-no-op failures); verify the loop continues.

For test 4: use `unittest.mock.AsyncMock` to stub `_execute_plan_with_validation` to return `(False, [<FixResult with no-op remaining_issues>], "no-op")`. Test verifies: loop returns after 2 calls, final FixResult has the "stuck" reason.

For test 5: verify that the loop doesn't break on the FIRST no-op — only after 2 consecutive.

## Error handling

- No new error paths. The circuit breaker is an early-exit on an existing loop.
- If `_plan_signature` raises (malformed `FixPlan`), the exception propagates — same behavior as today (no defensive coding).

## Testing strategy

- 5 unit tests above.
- Run the existing `tests/unit/core/test_autofix_coordinator.py` to confirm no regression.
- Manual verification: run `crackerjack run --ai-fix --dry-run` on a known case where the planner produces no-op plans; confirm the loop exits after 2 attempts instead of 3.

## Success criteria

- `_plan_signature` exists, returns deterministic 16-char hex string.
- The retry loop at line 4329 breaks early when 2 consecutive no-op results occur.
- The break-out emits a `FixResult` with reason `"stuck: planner producing identical plans"`.
- 5 new tests pass.
- No regression in existing `test_autofix_coordinator.py` tests.
- AI-fix error log: cluster-4 entries drop to 0 (was 1).

## Rollback signal

If the circuit breaker falsely skips a legitimate retry (e.g., a transient no-op that would have succeeded on attempt 3), we'd see new "stuck" errors in the AI-fix log. Rollback: `git revert` the circuit-breaker commit. The `_plan_signature` helper is independently useful and can stay.

## Open questions

None.
