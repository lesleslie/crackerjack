# ValidationCoordinator Concurrency Serialization — Design

**Date**: 2026-07-10
**Status**: Draft — awaiting user review
**Author**: Claude (brainstorming session)
**Related**: triage note `docs/superpowers/triage/2026-07-10-validation-coordinator-concurrency.md`; untracked regression test `tests/unit/agents/test_validation_coordinator_concurrency.py`; Phase 4 commit chain `87ea8dac..5bd14598` (now on `origin/main`).

## Problem

`tests/unit/agents/test_validation_coordinator_concurrency.py::test_type_change_validation_serialized_under_concurrency` fails:

```
AssertionError: Project-wide ty validation must be serialized. Observed max_active=4:
concurrent validations overlapped their baseline→write→recheck windows, which lets one
plan's disk write pollute another plan's baseline diff (defect #2).
assert 4 == 1
```

`ValidationCoordinator.validate_fix_for_type_change` executes a 4-step project-global critical section:

1. Capture a project-wide `ty` baseline
1. Write the candidate file to disk
1. Re-run project-wide `ty`
1. Diff post vs baseline; any *new* signature is a regression → roll the file back

`FixerCoordinator._get_type_change_validator()` (`crackerjack/agents/fixer_coordinator.py:109-111`) caches a single `ValidationCoordinator` instance and shares it across all parallel plans (`ParallelDispatcher` runs up to `min(8, cpu)` plans concurrently). Without serialization, plan A's baseline→post window overlaps plan B's disk write, so B's freshly-written error shows up as "new" in A's diff — A is blamed for B's regression and spuriously rolled back.

## Goal

Make the existing test pass by serializing concurrent calls to `validate_fix_for_type_change` on a shared `ValidationCoordinator` instance. Improve call-site observability so future concurrency regressions surface in code, not only in production `--ai-fix` runs.

Out of scope:

- Per-file or per-glob locking (over-engineering; the natural critical section is project-wide).
- Refactoring `ParallelDispatcher` or `FixerCoordinator` dispatching.
- Throughput optimizations (batched validation, async type-check pools, etc.).
- Touching any other class or module.

## Design Decisions (from brainstorming)

1. **Lock scope = full method body.** Locking only the two `_run_ty_check` calls would let plan A's disk write interleave with plan B's baseline, which is the actual bug, not just its observable symptom. The test passes either way; the *correct* fix locks the full critical section.

1. **Lock placement = instance attribute, not class-level.** `asyncio.Lock` is bound to the event loop where it was created. Instance lock = one lock per coordinator = one event loop. Class-level would be coarser and would couple unrelated coordinators. `FixerCoordinator`'s single-coordinator cache means instance lock already serializes all parallel plans in the standard call path.

1. **Lock granularity = single lock, not per-file or per-workflow.** Per-file locks would let 4 validations on 4 different files run concurrently — and the test exercises exactly that pattern (`mod_0.py` through `mod_3.py`). The natural critical section is project-wide validation, not per-file.

1. **Throughput trade-off accepted.** All type-change validations now serialize through one lock. Under real `--ai-fix` workloads, type-changing plans are rare (most are import shuffles, doc fixes) and the lock is held sub-second. The throughput cost is real but small. Optimization is out of scope.

1. **No new public API.** `validate_fix_for_type_change` signature unchanged. `asyncio.Lock` allocated in `__init__` is a private detail.

## Implementation Outline

### File 1: `crackerjack/agents/validation_coordinator.py`

**Change 1 — Allocate the lock in `__init__`:**

Locate the existing `__init__` method (currently no `asyncio.Lock` allocation). Add one new attribute:

```python
self._ty_check_lock = asyncio.Lock()
```

**Change 2 — Wrap the method body:**

In `validate_fix_for_type_change` (line 343), wrap the entire method body in `async with self._ty_check_lock:`. Indent the existing body one level. No logic changes — the lock acquisition and release are the only additions.

Before:

```python
async def validate_fix_for_type_change(
    self, code: str, file_path: str, original_code: str, ...
) -> tuple[bool, str]:
    # existing body
    ...
    return is_valid, feedback
```

After:

```python
async def validate_fix_for_type_change(
    self, code: str, file_path: str, original_code: str, ...
) -> tuple[bool, str]:
    async with self._ty_check_lock:
        # existing body, unchanged
        ...
    return is_valid, feedback
```

**Change 3 — Verify `asyncio` is imported.** It is already imported in this file (used elsewhere in the validation logic). No new import needed.

### File 2: `tests/unit/agents/test_validation_coordinator_concurrency.py`

**No production-code change required.** The test is already written and ready-to-merge. It will go from RED to GREEN once the production lock lands.

The test uses `coordinator._run_ty_check = fake_run_ty_check` (instance attribute assignment) and a `_ConcurrencyRecorder` to track active count. The lock is acquired in the production method BEFORE the patched `_run_ty_check` is called, so the recorder's `enter()` will serialize naturally.

## Acceptance Criteria

- `tests/unit/agents/test_validation_coordinator_concurrency.py::test_type_change_validation_serialized_under_concurrency` passes.
- All previously-passing tests in `tests/unit/agents/test_validation_coordinator.py` and `tests/unit/agents/test_fixer_coordinator*.py` continue to pass.
- No new public API; no signature changes.
- The fix is contained to `validation_coordinator.py` (one new attribute + one indentation block + a `with` statement).
- The `_ConcurrencyRecorder.max_active == 1` invariant is now enforceable by CI.

## Test Plan

1. Run the previously-failing test: `pytest tests/unit/agents/test_validation_coordinator_concurrency.py -v --no-cov --timeout=60`
1. Run the full validation/fixer suite to confirm no regressions: `pytest tests/unit/agents/test_validation_coordinator.py tests/unit/agents/test_fixer_coordinator*.py -v --no-cov --timeout=120`
1. Run `mypy crackerjack/agents/validation_coordinator.py` and `ruff check` against the changed file.
1. Run `refurb crackerjack/agents/validation_coordinator.py` to confirm no new modernization issues.
1. Optional: re-run the full crackerjack run gate, expecting no change in pre-existing failure counts (53 ty, 23 refurb, 1 pyscn elsewhere in the codebase).

## Risk and Rollback

**Risk:**

- If the existing `__init__` signature has callers that pass a custom `asyncio.Lock` for testing, adding `self._ty_check_lock = asyncio.Lock()` unconditionally could conflict. Mitigation: read `__init__` to confirm before implementation.
- If `validate_fix_for_type_change` is currently called recursively or re-entrantly by something, an instance lock would deadlock. Mitigation: grep for `validate_fix_for_type_change` callers in the codebase to confirm no recursive paths.
- Throughput under heavy `--ai-fix` load with many type-changing plans is reduced. Acceptable per design decision 4; not a blocker.

**Rollback:** Single `git revert` of the implementation commit returns to the current state. The untracked test file (`test_validation_coordinator_concurrency.py`) remains untracked and uncommitted — no revert needed for it.

## Open Questions

None. The design is settled by the test's own contract.
