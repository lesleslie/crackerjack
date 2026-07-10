# Triage Note — ValidationCoordinator concurrency (Defect #2)

**Date**: 2026-07-10
**Test file**: `tests/unit/agents/test_validation_coordinator_concurrency.py` (untracked, ready-to-merge once production code is fixed)
**Status**: 1 test failing. Pre-existing. Not caused by W3 (commits 92ea7e8a..545d5c93) or Phase 4 (87ea8dac..5bd14598).
**Scope**: small, single-class fix with explicit test coverage. May be 5-10 lines of production code.

## Failing test (1)

```
tests/unit/agents/test_validation_coordinator_concurrency.py::test_type_change_validation_serialized_under_concurrency

AssertionError: Project-wide ty validation must be serialized. Observed max_active=4:
concurrent validations overlapped their baseline→write→recheck windows, which lets one
plan's disk write pollute another plan's baseline diff (defect #2).
assert 4 == 1
```

## Pattern

`ValidationCoordinator.validate_fix_for_type_change` (line 343) executes a 4-step
project-global critical section:

1. Capture a project-wide `ty` baseline
2. Write the candidate file to disk
3. Re-run project-wide `ty`
4. Diff post vs baseline; any *new* signature is a regression → roll the file back

`FixerCoordinator._get_type_change_validator()` (`fixer_coordinator.py:109-111`)
caches a single `ValidationCoordinator` instance and shares it across all parallel
plans (`ParallelDispatcher` runs up to `min(8, cpu)` plans concurrently). Without
serialization, plan A's baseline→post window overlaps plan B's disk write, so B's
freshly-written error shows up as "new" in A's diff — A is blamed for B's regression
and spuriously rolled back.

The test patches `_run_ty_check` to record concurrency via a `_ConcurrencyRecorder`
and asserts `recorder.max_active == 1` across 4 concurrent validations.

## Root cause

`ValidationCoordinator.__init__` does not allocate an `asyncio.Lock`. The
`validate_fix_for_type_change` body runs to completion without any cross-coroutine
serialization, so concurrent calls from `asyncio.gather` interleave freely.

The test docstring is explicit about the fix:

> *"The fix serializes the critical section with a shared lock so at most one
> type-change validation runs at a time."*

## Production code surface

- `crackerjack/agents/validation_coordinator.py:343` — `validate_fix_for_type_change` (the public entry)
- `crackerjack/agents/validation_coordinator.py:407` — `_run_ty_check` (called twice per validation: baseline + post)
- `crackerjack/agents/validation_coordinator.py:415` — `_collect_ty_keys` (key extraction)
- `crackerjack/agents/validation_coordinator.py:424` — `_extract_issue_dicts` (dict conversion)
- `crackerjack/agents/fixer_coordinator.py:109-111` — `_get_type_change_validator` (the cached singleton)

## Fix shape (high confidence)

Two-line production change + one-line test infrastructure (in `__init__`):

1. **Add a lock in `__init__`:**
   ```python
   self._ty_check_lock = asyncio.Lock()
   ```

2. **Wrap the validate_fix_for_type_change body** so the lock is held across both
   `_run_ty_check` invocations (baseline + post) and the intervening disk write.
   ```python
   async def validate_fix_for_type_change(self, ...):
       async with self._ty_check_lock:
           # existing body
   ```

Because `FixerCoordinator` caches the coordinator instance and shares it across
parallel plans, **a single instance-level lock correctly serializes all
concurrent validations project-wide**. No changes needed in `fixer_coordinator.py`.

## Why deferred (not part of Phase 4)

- W3 (libcst_surgeon) was a different root cause and explicitly accepted the
  14th test as deferred.
- Phase 4's recon flagged this test as "ready-to-merge" but did not run pytest.
  The test was actually failing because production code lacks the lock.
- Phase 4 scope was: 2 bug fixes, sandbox e2e, working tree cleanup. Defect #2
  would have been a 3rd bug fix without prior brainstorming/spec/plan.
- The user explicitly chose "Push + open follow-up for Defect #2" to handle
  this as a separate cycle with proper SDD.

## Recommended next steps

1. **Brainstorming session** — present 2-3 design alternatives (e.g., instance
   lock vs class lock, lock scope: full body vs just ty-check calls, whether
   to also lock the disk write step).
2. **Spec doc** at `docs/superpowers/specs/2026-07-10-validation-coordinator-serialization-design.md`.
3. **Plan + SDD execution** — likely 2 tasks: (a) implement fix + run test,
   (b) final review.
4. **Push** to `origin/main`.

## Effort estimate

XS — single class, ~5 lines of production code, 1 test that already exists.
The hard part is the design choice around lock scope; the implementation is
mechanical once the design is approved.
