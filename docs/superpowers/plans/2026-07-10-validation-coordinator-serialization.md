# ValidationCoordinator Concurrency Serialization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Serialize concurrent calls to `ValidationCoordinator.validate_fix_for_type_change` via an instance `asyncio.Lock` so the project-wide `ty` baseline→write→recheck critical section is never concurrently executed, fixing Defect #2.

**Architecture:** Add an `asyncio.Lock` to `ValidationCoordinator.__init__` and wrap the entire `validate_fix_for_type_change` body in `async with self._ty_check_lock:`. Commit the existing untracked regression test alongside (separate commit for clean history). No public API change.

**Tech Stack:** Python 3.13, `asyncio.Lock`, pytest, pytest-asyncio, ruff, mypy, refurb, ty.

## Global Constraints

- Python 3.13 target. `asyncio.Lock`, `asyncio.timeout`, `contextlib.suppress` are all available.
- Fix is contained to `crackerjack/agents/validation_coordinator.py` (1 new attribute in `__init__` + 1 indentation block + 1 `async with` statement).
- `asyncio` is already imported at line 1 of the target file — do NOT add a redundant import.
- `ValidationCoordinator` is cached by `FixerCoordinator._get_type_change_validator()` (line 109); one instance lock correctly serializes all parallel plans in the standard call path.
- No public API change. The `validate_fix_for_type_change` signature stays `(code: str, file_path: str | None = None, original_code: str | None = None) -> tuple[bool, str]`.
- 4 callers of `validate_fix_for_type_change`: 1 production (`fixer_coordinator.py:142`), 3 existing tests (`test_validation_coordinator.py:181, 235, 253`), 1 new test (`test_validation_coordinator_concurrency.py:75`). All non-recursive.
- The new test file `tests/unit/agents/test_validation_coordinator_concurrency.py` is currently untracked. It must be committed as part of this fix (separate commit from the production change for clean history).
- Run tests under crackerjack's venv: `/Users/les/Projects/crackerjack/.venv/bin/pytest`. NEVER use `/Users/les/Projects/mahavishnu/.venv/bin/python` (the `unidiff` import error is a known environment mismatch).
- Pre-existing crackerjack gate failures (53 ty, 23 refurb, 1 pyscn) are NOT in scope. Do not fix them as part of this plan.
- `from contextlib import suppress` is already used in the file (line 6). Match that style if any new context manager is introduced.

---

### Task 1: Add serialization lock + commit regression test

**Files:**
- Modify: `crackerjack/agents/validation_coordinator.py:208-212` (add lock in `__init__`)
- Modify: `crackerjack/agents/validation_coordinator.py:343-399` (wrap body of `validate_fix_for_type_change`)
- Stage + commit (currently untracked): `tests/unit/agents/test_validation_coordinator_concurrency.py`

**Interfaces:**
- Consumes: `ValidationCoordinator(project_path: Path | None = None)` constructor signature (unchanged)
- Produces: `ValidationCoordinator` with new `self._ty_check_lock: asyncio.Lock` attribute; `validate_fix_for_type_change(...)` method body wrapped in `async with self._ty_check_lock:`

- [ ] **Step 1: Verify the test currently fails (RED)**

Run:
```bash
cd /Users/les/Projects/crackerjack && .venv/bin/pytest tests/unit/agents/test_validation_coordinator_concurrency.py -v --no-cov --timeout=60
```

Expected: **FAIL** with `AssertionError: ... assert 4 == 1` (the `recorder.max_active == 1` invariant fails because the production code has no lock).

If the test does NOT fail, something is wrong — STOP and investigate before continuing.

- [ ] **Step 2: Read the current `__init__` to confirm the field pattern**

Read `/Users/les/Projects/crackerjack/crackerjack/agents/validation_coordinator.py` lines 207-213. Confirm the existing 4-field assignment pattern:
```python
class ValidationCoordinator:
    def __init__(self, project_path: Path | None = None) -> None:
        self.syntax = SyntaxValidator()
        self.logic = LogicValidator()
        self.behavior = BehaviorValidator(project_path)
        self.quality = QualityValidator(project_path)
```

If the file has been modified since the spec was written, STOP and reconcile against the spec before continuing.

- [ ] **Step 3: Add the lock to `__init__`**

Edit `crackerjack/agents/validation_coordinator.py:208-212` to add a new private attribute. After the edit, the `__init__` body becomes:

```python
def __init__(self, project_path: Path | None = None) -> None:
    self.syntax = SyntaxValidator()
    self.logic = LogicValidator()
    self.behavior = BehaviorValidator(project_path)
    self.quality = QualityValidator(project_path)
    # Serializes the project-wide ty baseline→write→recheck critical section
    # in validate_fix_for_type_change. FixerCoordinator caches a single
    # ValidationCoordinator instance and shares it across all parallel plans
    # (ParallelDispatcher runs up to min(8, cpu) concurrently), so this
    # instance lock correctly serializes every concurrent type-change
    # validation in the standard call path.
    self._ty_check_lock = asyncio.Lock()
```

- [ ] **Step 4: Read the current `validate_fix_for_type_change` body**

Read `/Users/les/Projects/crackerjack/crackerjack/agents/validation_coordinator.py` lines 343-399. The current body starts with an early-return guard for non-Python files (lines 349-350), then a file-exists guard (lines 352-354), then the working critical section (lines 356-399: baseline, write, post, diff, rollback, return).

- [ ] **Step 5: Wrap the entire method body in `async with self._ty_check_lock:`**

Edit `crackerjack/agents/validation_coordinator.py:343-399` to wrap the body. After the edit, the method becomes:

```python
async def validate_fix_for_type_change(
    self,
    code: str,
    file_path: str | None = None,
    original_code: str | None = None,
) -> tuple[bool, str]:
    if not file_path or not file_path.endswith(".py"):
        return True, "Non-Python file skipped for type-check validation"

    target = Path(file_path).resolve()
    if not target.exists():
        return True, f"File not found on disk: {file_path} — skipping"

    async with self._ty_check_lock:
        original_on_disk = target.read_text(encoding="utf-8")
        if original_code is None:
            original_code = original_on_disk

        try:
            baseline = await self._run_ty_check()
            baseline_keys = self._collect_ty_keys(baseline)

            self._atomic_write(target, code)
            try:
                post_fix = await self._run_ty_check()
                post_dicts = self._extract_issue_dicts(post_fix)
                post_keys = self._collect_ty_keys(post_fix)
            except Exception:
                self._atomic_write(target, original_on_disk)
                raise

            new_issues = self._new_issues(baseline_keys, post_dicts)
            resolved_issues = self._resolved_issues(baseline_keys, post_keys)

            rolled_back = False
            if new_issues:
                self._atomic_write(target, original_on_disk)
                rolled_back = True

            is_valid = not bool(new_issues)
            feedback = self._format_type_feedback(
                new_issues=new_issues,
                resolved_issues=resolved_issues,
                baseline_count=len(baseline_keys),
                post_count=len(post_keys),
                rolled_back=rolled_back,
            )
            return is_valid, feedback
        except FileNotFoundError as e:
            logger.debug(f"ty binary not available: {e}")
            return True, f"ty not available — type-check validation skipped: {e}"
        except (TimeoutError, OSError) as e:
            logger.debug(f"ty validation unavailable: {e}")
            return True, f"ty validation unavailable: {e}"
        finally:
            with suppress(OSError):
                if target.read_text(encoding="utf-8") != original_on_disk:
                    self._atomic_write(target, original_on_disk)
```

**Note on the early returns (lines 349-354):** they stay OUTSIDE the lock. They never reach `_run_ty_check` and don't need serialization. Putting them inside would be a trivial overhead with no correctness benefit.

- [ ] **Step 6: Run the test — verify GREEN**

Run:
```bash
cd /Users/les/Projects/crackerjack && .venv/bin/pytest tests/unit/agents/test_validation_coordinator_concurrency.py -v --no-cov --timeout=60
```

Expected: **PASS** with `1 passed`. The test patches `_run_ty_check` to record concurrency; with the lock held across both calls, `recorder.max_active == 1` is now true.

- [ ] **Step 7: Run the existing validation/fixer suite — verify no regressions**

Run:
```bash
cd /Users/les/Projects/crackerjack && .venv/bin/pytest tests/unit/agents/test_validation_coordinator.py tests/unit/agents/test_fixer_coordinator_sandbox.py -v --no-cov --timeout=120
```

Expected: all tests pass. If any test fails, STOP and investigate before continuing — the production code change is small but the existing tests have non-trivial coverage.

- [ ] **Step 8: Run static checks on the changed file**

Run:
```bash
cd /Users/les/Projects/crackerjack && .venv/bin/ruff check crackerjack/agents/validation_coordinator.py && .venv/bin/refurb crackerjack/agents/validation_coordinator.py
```

Expected: both exit 0 (no issues). Ruff enforces import sort, line length, complexity; refurb enforces Python modernization hints. If either flags an issue, fix it before committing.

- [ ] **Step 9: Commit the production code change**

```bash
cd /Users/les/Projects/crackerjack && git add crackerjack/agents/validation_coordinator.py && git commit -m "fix(agents): serialize ValidationCoordinator.validate_fix_for_type_change

Project-wide ty baseline→write→recheck is a critical section shared
across all parallel plans via FixerCoordinator's cached coordinator
(ParallelDispatcher runs up to min(8, cpu) plans concurrently).
Without serialization, plan A's baseline→post window overlaps plan B's
disk write, so B's freshly-written error shows up as 'new' in A's
diff and A is spuriously rolled back for B's regression (defect #2).

Fix: add an instance asyncio.Lock in ValidationCoordinator.__init__
and wrap the working body of validate_fix_for_type_change in
\`async with self._ty_check_lock:\`. The early-return guards (non-Python
files, missing files) stay outside the lock since they never reach
_run_ty_check and don't need serialization.

The lock is bound to the event loop where the coordinator was created;
one instance lock correctly serializes all parallel plans because
FixerCoordinator._get_type_change_validator caches a single coordinator
instance. Throughput trade-off accepted: all type-change validations
now serialize. Acceptable per the bug's correctness requirements.

Test: tests/unit/agents/test_validation_coordinator_concurrency.py
goes from RED to GREEN (asserts recorder.max_active == 1 across 4
concurrent validations). Existing tests in
tests/unit/agents/test_validation_coordinator.py and
test_fixer_coordinator_sandbox.py continue to pass.

Files: crackerjack/agents/validation_coordinator.py only.
"
```

- [ ] **Step 10: Commit the untracked regression test file**

```bash
cd /Users/les/Projects/crackerjack && git add tests/unit/agents/test_validation_coordinator_concurrency.py && git commit -m "test(agents): regression anchor for ValidationCoordinator concurrency (defect #2)

Adds the untracked regression test that was written before the
production fix landed. The test patches _run_ty_check with a
_ConcurrencyRecorder to track active count, then runs 4 concurrent
validate_fix_for_type_change calls via asyncio.gather and asserts
recorder.max_active == 1.

This test was failing in main (defect #2) because the production
code lacked the shared lock. With the lock now in place (see
previous commit), the test passes. It serves as a permanent
regression anchor so future refactors of the validation
critical section cannot silently re-introduce the bug.

The test docstring documents the bug shape: plan A's
baseline→post window overlapping plan B's disk write causes
B's freshly-written ty error to surface as 'new' in A's diff,
leading to spurious rollbacks of A.
"
```

- [ ] **Step 11: Verify the working tree is clean (no leftover modifications)**

Run:
```bash
cd /Users/les/Projects/crackerjack && git status --short
```

Expected: empty output. If any modified or untracked files appear, STOP and investigate before continuing.
