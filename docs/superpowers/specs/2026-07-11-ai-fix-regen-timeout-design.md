# AI-fix plan-regeneration timeout — design

**Date:** 2026-07-11
**Status:** Approved (clarifying question on env var name + default answered: separate env var, default 90s)
**Scope:** 1 production file, 1 test file
**Cluster:** 3 (plan timeouts — 14 of 20 failures in latest AI-fix error log)

## Problem

The `--ai-fix` loop's plan-regeneration step has a hardcoded 30-second timeout:

```python
# crackerjack/core/autofix_coordinator.py:4475-4478
new_plans = await asyncio.wait_for(
    analysis_coordinator.analyze_issues([enhanced_issue]),
    timeout=30,
)
```

When the LLM round-trip for `analyze_issues` exceeds 30s (cold start, model slowness, network blip), the regen step silently falls back to the previous (failed) plan, which then re-triggers the per-issue timeout, then retries, then times out again — cascading into the dominant error signature in the AI-fix log: `"Timed out after 90s; Timed out after 90s; Timed out after 90s"`.

The 90s outer-loop figure is the operator's tuned `per_issue_timeout` (env: `CRACKERJACK_AI_FIX_PER_ISSUE_TIMEOUT`). The 30s inner-regen figure is invisible to operators. **The fix parameterizes the inner timeout with a new env var so the two layers can be tuned independently.**

The pattern is already in place for `per_issue_timeout` (lines 1644-1652). We mirror it.

## Goals

1. Make the regen timeout operator-tunable without code changes.
2. Pick a default that matches the operator's mental model (the 90s observed in error logs).
3. Add a regression test that catches accidental reintroduction of the hardcoded literal.

## Non-goals

- Changing `per_issue_timeout` (already operator-tunable, currently tuned to 90s in practice).
- Changing `analyze_issues` itself (LLM call duration is out of scope for this cluster).
- Touching the other timeout layers (validation_coordinator.py, resource_manager.py — different code paths).

## Architecture

### Change 1: `AutofixCoordinator._get_regen_timeout()` (new static method)

Pattern mirrors the existing `_get_per_issue_timeout()` exactly:

```python
@staticmethod
def _get_regen_timeout() -> int:
    raw = os.environ.get("CRACKERJACK_AI_FIX_REGEN_TIMEOUT")
    if raw is None:
        return 90
    try:
        return int(raw)
    except ValueError:
        return 90
```

Place it adjacent to `_get_per_issue_timeout` (after line 1652) to keep related config getters together.

### Change 2: Wire it into the regen call

```python
# Before (line 4475-4478):
new_plans = await asyncio.wait_for(
    analysis_coordinator.analyze_issues([enhanced_issue]),
    timeout=30,
)

# After:
new_plans = await asyncio.wait_for(
    analysis_coordinator.analyze_issues([enhanced_issue]),
    timeout=self._get_regen_timeout(),
)
```

Static method → call without `self._get_regen_timeout()` works because `@staticmethod`. Use `self._get_regen_timeout()` for consistency with the per-issue call site (line 4344 uses `per_issue_timeout = self._get_per_issue_timeout()` then passes the local — we can do the same here, or call inline). The cleanest version:

```python
regen_timeout = self._get_regen_timeout()
new_plans = await asyncio.wait_for(
    analysis_coordinator.analyze_issues([enhanced_issue]),
    timeout=regen_timeout,
)
```

This matches the local-variable pattern at line 4290 (`per_issue_timeout = self._get_per_issue_timeout()`).

### Change 3: Unit test

New file: `tests/unit/core/test_autofix_coordinator_regen_timeout.py`

Tests:

1. **Default returns 90**: with no env var set, `_get_regen_timeout()` returns 90.
2. **Env var override**: with `CRACKERJACK_AI_FIX_REGEN_TIMEOUT=180`, returns 180.
3. **Malformed env value**: with `CRACKERJACK_AI_FIX_REGEN_TIMEOUT=not-a-number`, returns 90 (falls back to default).
4. **Negative value**: with `CRACKERJACK_AI_FIX_REGEN_TIMEOUT=-5`, returns the value as-is (no special handling — same as `per_issue_timeout`).

Test pattern: `monkeypatch.setenv("CRACKERJACK_AI_FIX_REGEN_TIMEOUT", "180")` then call the static method directly.

Use `pytest.mark.unit` marker (project convention from `pyproject.toml`).

## Error handling

- No new error paths. The `asyncio.wait_for` already raises `TimeoutError`, which the existing `except TimeoutError` block at line 4484 catches and handles (falls back to old plan). Behavior is unchanged on timeout.

## Testing strategy

- **Unit tests** (above): 4 tests, all green on first run.
- **Manual verification**: Run `crackerjack run --ai-fix --dry-run` and confirm the AI-fix loop doesn't cascade timeouts on the canonical cluster-1 file (`crackerjack/tools/ty_imports.py`).
- **No end-to-end test** required — this is a config-parameterization change, not a behavior change. The cluster-3 fix's value is "fewer spurious timeouts in production runs," which shows up in the AI-fix error log distribution.

## Success criteria

- `_get_regen_timeout()` exists and is callable.
- `_get_regen_timeout()` returns 90 when env var unset.
- `_get_regen_timeout()` honors `CRACKERJACK_AI_FIX_REGEN_TIMEOUT` when set.
- `_get_regen_timeout()` falls back to 90 when env var is malformed.
- The hardcoded `timeout=30` literal at line 4477 is gone (a future test should grep for it).
- 4 unit tests pass.
- No regression in existing tests.

## Rollback signal

If the bump causes downstream callers (e.g., `IterativeFixAgent`) to take noticeably longer on retries, the timeout can be lowered via env var without code change. The default of 90s is conservative; operators can dial down to 30s, 45s, 60s without touching code.

## Open questions

None.