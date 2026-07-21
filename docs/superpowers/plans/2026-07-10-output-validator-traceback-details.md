______________________________________________________________________

## status: active role: implementation date: 2026-07-17 last_reviewed: 2026-07-17 superseded_by: null blocks_on: [] topic: lifecycle

# OutputValidator Traceback Details Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface full subprocess traceback from `OutputValidator.import_check` failures so the fixer regenerator prompt has diagnostic context to escape the no-progress loop.

**Architecture:** Additive change. `ValidationResult` gains a `details: list[str] | None = None` field. `import_check` populates it from raw subprocess stderr. The autofix failure path threads it through a new `PlanResult.error_details` field. `FixerCoordinator`'s regenerator prompt includes a "previous failure traceback" block capped at 30 lines.

**Tech Stack:** Python 3.13, pytest, pytest-asyncio, ruff, refurb, ty. `crackerjack.run --ai-fix` for end-to-end verification.

## Global Constraints

- **Additive change.** `details` is the LAST field on `ValidationResult`, default `None`. All existing `ValidationResult(passed=False, reason="x")` constructions stay byte-identical.
- **`frozen=True` dataclass + Optional default.** `details = None` avoids linter warnings about mutable defaults. Set once at construction site, never mutated.
- **`reason` field is byte-identical to pre-fix output.** All 12 acceptance criteria in the spec must hold; criterion 6 specifically requires reason unchanged.
- **30-line cap on traceback details** in the regenerator prompt. Trimming suffix: `... (N more lines)` is informational only.
- **Always emit `Reason:` first in the prompt block.** Then `Traceback:`. Then explicit LLM instruction. Backward-compat signal at top.
- **No new public API.** `FixerCoordinator`'s new behavior is internal to its prompt-construction function.
- **Backward compat for `reason`.** `import_check.reason` continues to use `.strip().splitlines()[-1]` for backward compat. `details` uses raw `splitlines()`.
- **Run tests under crackerjack's venv:** `/Users/les/Projects/crackerjack/.venv/bin/pytest`. NEVER use `/Users/les/Projects/mahavishnu/.venv/bin/python` (the `unidiff` import error is a known environment mismatch).
- **Pre-existing crackerjack gate failures** (53 ty, 23 refurb, 1 pyscn) are NOT in scope. Do not fix them as part of this plan.
- **Pre-existing 26 modified files in working tree** are NOT in scope. Do not stage or commit them.
- **TDD discipline.** Write the failing test FIRST. Run it (verify it fails). Implement minimum to pass. Run again (verify it passes). Commit.
- **No test deletion, no test weakening.** If a test breaks, update it because it was asserting the wrong thing, not because the implementation is wrong.
- **Frequent commits.** Each task produces 2 commits (production + test). Use the existing `crackerjack` commit style: `feat(<scope>):` for production, `test(<scope>):` for tests.

______________________________________________________________________

### Task 1: Validator surface — `details` field + `import_check` population

**Files:**

- Modify: `crackerjack/ai_fix/output_validator.py:42-46` (add `details` to `ValidationResult`)
- Modify: `crackerjack/ai_fix/output_validator.py:72-97` (populate `details` in `import_check`)
- Modify: `tests/unit/ai_fix/test_output_validator.py` (extend with 6 new tests)
- Note: If `tests/unit/ai_fix/test_output_validator.py` does not exist yet, CREATE it with the standard `pytest` header.

**Interfaces:**

- Consumes: existing `ValidationResult` and `import_check(file_path: Path) -> ValidationResult`

- Produces: `ValidationResult(passed=bool, reason: str = "", skipped: bool = False, details: list[str] | None = None)`. `import_check` returns `ValidationResult` with `details` populated from raw subprocess stderr.

- [x] **Step 1: Read the current `ValidationResult` and `import_check` to confirm shapes**

Read `/Users/les/Projects/crackerjack/crackerjack/ai_fix/output_validator.py` lines 42-46 (the dataclass) and lines 72-97 (the function). Confirm:

- `ValidationResult` is `frozen=True` with exactly `passed`, `reason`, `skipped` fields.
- `import_check` returns `ValidationResult` with `passed` and `reason` only.

If file structure differs from spec, STOP and reconcile.

- [x] **Step 2: Write the failing test — `details` defaults to `None`**

Add to `tests/unit/ai_fix/test_output_validator.py`:

```python
def test_validation_result_details_defaults_none():
    """Backward-compat: existing constructions don't need a details kwarg."""
    result = ValidationResult(passed=True)
    assert result.details is None
```

- [x] **Step 3: Run test to verify it fails (RED)**

Run: `.venv/bin/pytest tests/unit/ai_fix/test_output_validator.py::test_validation_result_details_defaults_none -v --no-cov --timeout=60`

Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'details'`. The dataclass doesn't have the field yet.

- [x] **Step 4: Add `details` to `ValidationResult`**

Edit `crackerjack/ai_fix/output_validator.py:42-46`. After the edit:

```python
@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    reason: str = ""
    skipped: bool = False
    details: list[str] | None = None
```

- [x] **Step 5: Run test to verify it passes (GREEN)**

Run: `.venv/bin/pytest tests/unit/ai_fix/test_output_validator.py::test_validation_result_details_defaults_none -v --no-cov --timeout=60`

Expected: PASS.

- [x] **Step 6: Write the failing test — `details` accepts an explicit list**

Add to `tests/unit/ai_fix/test_output_validator.py`:

```python
def test_validation_result_details_explicit_list():
    result = ValidationResult(
        passed=False,
        reason="x",
        details=["line1", "line2"],
    )
    assert result.details == ["line1", "line2"]
```

- [x] **Step 7: Run test to verify it passes (already green after Step 5)**

Run: `.venv/bin/pytest tests/unit/ai_fix/test_output_validator.py::test_validation_result_details_explicit_list -v --no-cov --timeout=60`

Expected: PASS. This test confirms the new field accepts a list. If it fails, the dataclass change is wrong — STOP and investigate.

- [x] **Step 8: Write the failing test — Cluster 1 regression**

Add to `tests/unit/ai_fix/test_output_validator.py`:

```python
def test_import_check_captures_full_traceback_for_top_level_none_dict(tmp_path):
    """Regression for Cluster 1: validator previously reported only the last
    line of stderr, hiding the actual crash frame. With details populated,
    the fixer can see which line raised AttributeError on None.__dict__."""
    bad_file = tmp_path / "crash.py"
    bad_file.write_text(
        "import os\n"
        "value = None\n"
        "value.__dict__  # NoneType has no __dict__\n"
    )

    result = import_check(bad_file)

    assert result.passed is False
    assert result.details is not None
    assert len(result.details) >= 3
    assert "Traceback" in result.details[0]
    assert any("crash.py" in line for line in result.details)
    assert result.details[-1].startswith("AttributeError:")
    assert result.reason == result.details[-1]
```

- [x] **Step 9: Run test to verify it fails (RED)**

Run: `.venv/bin/pytest tests/unit/ai_fix/test_output_validator.py::test_import_check_captures_full_traceback_for_top_level_none_dict -v --no-cov --timeout=60`

Expected: FAIL with `AttributeError: 'NoneType' object has no attribute 'details'`. `details` is currently never set on the return value of `import_check`.

- [x] **Step 10: Modify `import_check` to populate `details`**

Edit `crackerjack/ai_fix/output_validator.py:72-97`. The current body:

```python
def import_check(file_path: Path) -> ValidationResult:
    if not _is_python(file_path):
        return ValidationResult(passed=True, skipped=True)

    driver = _IMPORT_DRIVER.format(path=str(file_path))
    try:
        proc = subprocess.run(
            [sys.executable, "-c", driver],
            capture_output=True,
            text=True,
            timeout=IMPORT_CHECK_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return ValidationResult(
            passed=False,
            reason=f"import timed out after {IMPORT_CHECK_TIMEOUT_S}s",
        )
    except OSError as exc:
        return ValidationResult(passed=False, reason=f"subprocess failed: {exc}")

    if proc.returncode == 0:
        return ValidationResult(passed=True)

    err_lines = (proc.stderr or proc.stdout).strip().splitlines()
    reason = err_lines[-1] if err_lines else f"import exit {proc.returncode}"
    return ValidationResult(passed=False, reason=reason)
```

After the edit:

```python
def import_check(file_path: Path) -> ValidationResult:
    if not _is_python(file_path):
        return ValidationResult(passed=True, skipped=True)

    driver = _IMPORT_DRIVER.format(path=str(file_path))
    try:
        proc = subprocess.run(
            [sys.executable, "-c", driver],
            capture_output=True,
            text=True,
            timeout=IMPORT_CHECK_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        return ValidationResult(
            passed=False,
            reason=f"import timed out after {IMPORT_CHECK_TIMEOUT_S}s",
        )
    except OSError as exc:
        return ValidationResult(passed=False, reason=f"subprocess failed: {exc}")

    if proc.returncode == 0:
        return ValidationResult(passed=True)

    stderr_text = proc.stderr or proc.stdout or ""
    err_lines = stderr_text.strip().splitlines()
    reason = err_lines[-1] if err_lines else f"import exit {proc.returncode}"
    details = stderr_text.splitlines() or None
    return ValidationResult(passed=False, reason=reason, details=details)
```

- [x] **Step 11: Run the Cluster 1 regression test — verify GREEN**

Run: `.venv/bin/pytest tests/unit/ai_fix/test_output_validator.py::test_import_check_captures_full_traceback_for_top_level_none_dict -v --no-cov --timeout=60`

Expected: PASS.

- [x] **Step 12: Write + run test — `details=None` on success**

Add to `tests/unit/ai_fix/test_output_validator.py`:

```python
def test_import_check_details_none_on_success(tmp_path):
    """When the file imports cleanly, details is None (no failure to capture)."""
    good_file = tmp_path / "ok.py"
    good_file.write_text("x = 1\n")

    result = import_check(good_file)

    assert result.passed is True
    assert result.details is None
```

Run: `.venv/bin/pytest tests/unit/ai_fix/test_output_validator.py::test_import_check_details_none_on_success -v --no-cov --timeout=60`

Expected: PASS. (Should pass with current code too — no changes needed in production.)

- [x] **Step 13: Write + run test — `details=None` on empty stderr**

Add to `tests/unit/ai_fix/test_output_validator.py`:

```python
def test_import_check_details_none_on_empty_stderr(tmp_path, monkeypatch):
    """If subprocess exits non-zero with empty stderr, details is None."""
    import subprocess
    fake_proc = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="")

    def fake_run(*args, **kwargs):
        return fake_proc

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = import_check(tmp_path / "fake.py")

    assert result.passed is False
    assert result.details is None
    assert "import exit 1" in result.reason
```

Run: `.venv/bin/pytest tests/unit/ai_fix/test_output_validator.py::test_import_check_details_none_on_empty_stderr -v --no-cov --timeout=60`

Expected: PASS. (Tests the `details = stderr_text.splitlines() or None` short-circuit.)

- [x] **Step 14: Write + run test — `reason` unchanged for syntax error (backward compat)**

Add to `tests/unit/ai_fix/test_output_validator.py`:

```python
def test_import_check_reason_unchanged_for_syntax_error(tmp_path):
    """Backward-compat: reason field must remain the last line of stderr."""
    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def foo(:\n  pass\n")

    result = import_check(bad_file)

    assert result.passed is False
    assert result.reason
    assert "SyntaxError" in result.reason or "invalid syntax" in result.reason
```

Run: `.venv/bin/pytest tests/unit/ai_fix/test_output_validator.py::test_import_check_reason_unchanged_for_syntax_error -v --no-cov --timeout=60`

Expected: PASS. Confirms the `reason` extraction path is unchanged.

- [x] **Step 14.5: Write + run test — `OutputValidator.validate` passes `details` through**

Add to `tests/unit/ai_fix/test_output_validator.py`:

```python
def test_output_validator_validate_passes_details_through(
    tmp_path, monkeypatch
):
    """The wrapper must not drop details; if any check fails with details,
    validate() must return a ValidationResult carrying those details."""
    captured_details: list[str] | None = None

    def fake_import_check(file_path: Path) -> ValidationResult:
        nonlocal captured_details
        return ValidationResult(
            passed=False,
            reason="fake failure",
            details=[
                "Traceback (most recent call last):",
                "  File \"fake.py\", line 1",
                "AttributeError: fake",
            ],
        )

    monkeypatch.setattr(
        "crackerjack.ai_fix.output_validator.import_check",
        fake_import_check,
    )

    fake_file = tmp_path / "fake.py"
    fake_file.write_text("x = 1\n")

    validator = OutputValidator()
    result = validator.validate(fake_file)

    assert result.passed is False
    assert result.details is not None
    assert "fake.py" in result.details[1]
    assert result.details[-1] == "AttributeError: fake"
```

Run: `.venv/bin/pytest tests/unit/ai_fix/test_output_validator.py::test_output_validator_validate_passes_details_through -v --no-cov --timeout=60`

Expected: PASS. (This test confirms spec criterion 7 — `OutputValidator.validate()` passes `details` through without modification.)

- [x] **Step 15: Run all output_validator tests**

Run: `.venv/bin/pytest tests/unit/ai_fix/test_output_validator.py -v --no-cov --timeout=120`

Expected: ALL tests pass (6 new + any pre-existing). If any test fails, STOP and investigate before committing.

- [x] **Step 16: Run static checks on the changed file**

Run: `.venv/bin/ruff check crackerjack/ai_fix/output_validator.py && .venv/bin/refurb crackerjack/ai_fix/output_validator.py`

Expected: both exit 0 (no issues). Ruff enforces line length, import sort; refurb enforces Python modernization hints.

- [x] **Step 17: Commit the production change**

```bash
cd /Users/les/Projects/crackerjack && git add crackerjack/ai_fix/output_validator.py && git commit -m "feat(ai-fix): surface full traceback in OutputValidator.details

import_check previously captured only the last line of stderr as the
failure reason (output_validator.py:95-96), discarding the traceback
frames that show *where* the import-time crash occurred. When the
crackerjack fixer hits a file with a top-level AttributeError or any
other import-time bug, it regenerates identical plans because the
reason 'AttributeError: NoneType ...' doesn't tell it which file, line,
or expression to fix.

This change adds an optional details: list[str] | None = None field to
ValidationResult and populates it from raw subprocess stderr in
import_check. One entry per line, including 'File ... line N, in func'
frames and source-line context. reason is byte-identical to its
pre-fix output (criterion 6 of the spec).

Backward compat: existing ValidationResult constructions don't need a
details kwarg. OutputValidator.validate passes details through without
modification. The autofix failure path will pick this up in a follow-up
commit (Task 2 of the plan).

File: crackerjack/ai_fix/output_validator.py only."
```

- [x] **Step 18: Commit the test changes**

```bash
cd /Users/les/Projects/crackerjack && git add tests/unit/ai_fix/test_output_validator.py && git commit -m "test(ai-fix): regression anchor for OutputValidator traceback capture (cluster 1)

Adds six tests for the new ValidationResult.details field and
import_check population. The Cluster 1 regression test
(test_import_check_captures_full_traceback_for_top_level_none_dict)
specifically reproduces the user's reported failure mode: a file with
a top-level 'value.__dict__' where value is None produces a
multi-line traceback that the validator previously discarded.

Other tests cover the four edge cases from the spec:
- details defaults to None (backward compat)
- details accepts an explicit list
- details is None on a successful import
- details is None when subprocess exits non-zero with empty stderr
- reason field is unchanged for syntax errors (the existing consumer
  contract)

File: tests/unit/ai_fix/test_output_validator.py only."
```

- [x] **Step 19: Verify clean task boundary**

Run: `cd /Users/les/Projects/crackerjack && git status --short`

Expected: empty for the changed files (only the 26 pre-existing dirty files should remain; those are out of scope).

______________________________________________________________________

### Task 2: Wiring + regenerator prompt

**Files:**

- Modify: `crackerjack/ai_fix/fix_runner.py` — find `PlanResult` dataclass, add `error_details: list[str] | None = None`
- Modify: `crackerjack/core/autofix_coordinator.py` — at the failure site (around line 2929-2955), populate `error_details=validation_result.details`
- Modify: `crackerjack/agents/fixer_coordinator.py` — add `_format_previous_failure` helper, integrate into the regenerator prompt-construction function (location TBD by implementer)
- Modify: `tests/unit/core/test_autofix_coordinator.py` (extend) — verify `PlanResult.error_details` is populated
- Modify: `tests/unit/agents/test_fixer_coordinator.py` (extend) — verify regenerator prompt contains the traceback block, capped at 30 lines

**Interfaces:**

- Consumes: `ValidationResult.details: list[str] | None` (Task 1's output); `PlanResult` from `fix_runner.py`
- Produces: `PlanResult` with new `error_details: list[str] | None = None` field; fixer regenerator prompt with embedded traceback block

**Implementer discovery requirements (READ FIRST, before editing):**

1. **PlanResult location.** Read `crackerjack/ai_fix/fix_runner.py:234-241`. Confirm `PlanResult` is the dataclass returned at the autofix failure site. If the actual return type at `crackerjack/core/autofix_coordinator.py:2929-2955` is a parallel type, add `error_details` to that type instead.

1. **Prompt construction site.** Search `crackerjack/agents/fixer_coordinator.py` for the function that builds the regenerator prompt. Likely candidates:

   - A function named `_build_*_prompt`, `_format_*_prompt`, or `_construct_*_prompt`
   - Inline string concatenation inside the no-progress regeneration call site
   - A reference to `previous_failure` or `last_error` near the regenerator

   If the search returns nothing obvious, read the no-progress detector sites at `crackerjack/core/autofix_coordinator.py:1157-1197` and `:2588-2630` and trace where they call into the fixer regenerator.

1. **Existing tests with prompt-text assertions.** Read `tests/unit/agents/test_fixer_coordinator.py` and grep for `assert.*prompt` or similar. If existing tests assert exact prompt text, those will need updating (per spec Section 7.2 rule: update, don't weaken).

- [x] **Step 1: Read the discovery sites**

Run these reads:

```
Read /Users/les/Projects/crackerjack/crackerjack/ai_fix/fix_runner.py:230-250
Read /Users/les/Projects/crackerjack/crackerjack/core/autofix_coordinator.py:2925-2960
Read /Users/les/Projects/crackerjack/crackerjack/core/autofix_coordinator.py:1150-1200
Read /Users/les/Projects/crackerjack/crackerjack/core/autofix_coordinator.py:2580-2640
Read /Users/les/Projects/crackerjack/crackerjack/agents/fixer_coordinator.py (search for prompt-construction)
```

Report the PlanResult dataclass location, the autofix failure return site, and the fixer prompt-construction function (or note if it's inline).

- [x] **Step 2: Add `error_details` to `PlanResult`**

Edit the `PlanResult` dataclass (location from Step 1). After the edit, the dataclass has:

```python
@dataclass(frozen=True)
class PlanResult:
    plan_idx: int
    success: bool
    remaining_issues: list[str] = field(default_factory=list)
    error_details: list[str] | None = None  # NEW
```

(Adjust if the actual `PlanResult` shape differs. The KEY property: `error_details` is the LAST field, defaults to `None`.)

If the autofix failure site returns a parallel type instead of `PlanResult`, add the field to that type with the same shape.

- [x] **Step 3: Write the failing test — autofix failure populates `error_details`**

Add to `tests/unit/core/test_autofix_coordinator.py`. The pattern mirrors the existing `_execute_plan_with_validation` tests in this file (see `test_execute_plan_uses_baseline_validation_for_complexity` at lines 670-720 of the existing file), but for the failure path at line 2929-2955. The validator is mocked as a `MagicMock()` whose `.validate` attribute is a regular `Mock` (NOT `AsyncMock` — `OutputValidator.validate` is sync, unlike `validate_fix` which is async):

```python
from crackerjack.ai_fix.output_validator import OutputValidator, ValidationResult


def test_autofix_coordinator_failure_path_propagates_error_details(
    tmp_path: Path, monkeypatch
) -> None:
    """When OutputValidator returns a failure with details, the autofix
    coordinator must include those details in the result it returns.

    Regression: prior to this fix, validation_result.details was discarded;
    the fixer only saw validation_result.reason and had no diagnostic context
    to escape the no-progress loop.
    """
    from crackerjack.core.autofix_coordinator import AutofixCoordinator

    fake_validation = ValidationResult(
        passed=False,
        reason="AttributeError: 'NoneType' object has no attribute '__dict__'",
        details=[
            "Traceback (most recent call last):",
            "  File \"crackerjack/tools/ty_imports.py\", line 220, in apply_import_fix",
            "    some_obj.__dict__",
            "AttributeError: 'NoneType' object has no attribute '__dict__'",
        ],
    )

    # Mock OutputValidator to return our fake failure with details.
    # We patch at the class so any OutputValidator() instantiation inside
    # the coordinator receives our fake. validate is sync (Mock, not AsyncMock).
    from unittest.mock import MagicMock, Mock

    fake_validator_instance = MagicMock()
    fake_validator_instance.validate = Mock(return_value=fake_validation)
    monkeypatch.setattr(
        "crackerjack.core.autofix_coordinator.OutputValidator",
        lambda: fake_validator_instance,
    )

    # Trigger the failure path at line 2929-2955.
    # The exact entry point depends on discovery from Step 1 — it may be
    # _execute_plan_with_validation, _run_single_plan, or the loop itself.
    # Use whichever method/process Step 1 surfaced.
    coordinator = AutofixCoordinator(pkg_path=tmp_path)
    target = tmp_path / "target.py"
    target.write_text("def target():\n    return 1\n")
    plan = FixPlan(
        file_path=str(target),
        issue_type="COMPLEXITY",
        issue_stage="ruff-check",
        rationale="Test",
        risk_level="low",
        validated_by="test",
        changes=[
            ChangeSpec(
                line_range=(1, 2),
                old_code="def target():\n    return 1",
                new_code="def target():\n    return 2",
                reason="test change",
            )
        ],
    )
    fixer = MagicMock()

    def _fake_execute_plans(*args, **kwargs):
        # Actually rewrite the file so the no-op check does not fire.
        target.write_text("def target():\n    return 2\n")
        return [FixResult(success=True, files_modified=[str(target)])]

    fixer.execute_plans = AsyncMock(side_effect=_fake_execute_plans)

    # Run the autofix failure path. The exact call shape depends on what
    # Step 1 surfaces; the KEY assertion below is universal.
    result = coordinator.<DISCOVERED_METHOD_NAME>(plan, fixer)  # noqa: ERA001

    # KEY assertion: the result carries error_details from validation.
    assert getattr(result, "error_details", None) == fake_validation.details
```

If the autofix failure path returns a tuple `(success, applied, msg)` instead of a `PlanResult`, the assertion should be on whichever element carries the result. If the result is a `PlanResult`, the assertion is direct. Adjust based on Step 1's findings.

- [x] **Step 4: Run test to verify it fails (RED)**

Run: `.venv/bin/pytest tests/unit/core/test_autofix_coordinator.py::test_autofix_coordinator_failure_path_propagates_error_details -v --no-cov --timeout=60`

Expected: FAIL — the autofix coordinator currently doesn't construct a result with `error_details` populated.

- [x] **Step 5: Modify the autofix failure site to populate `error_details`**

Edit `crackerjack/core/autofix_coordinator.py` around lines 2929-2955. The current shape:

```python
if plan.file_path.endswith(".py"):
    validation_result = self._output_validator.validate(
        Path(plan.file_path)
    )
    if not validation_result.passed:
        self.logger.warning(
            f"⚠️ Output validation failed for {plan.file_path}: "
            f"{validation_result.reason} — rolling back"
        )
        try:
            self._restore_backup(backup_path)
            ...
```

The failure return path needs to pass `error_details=validation_result.details` to whatever result type is constructed. The exact line depends on the return type from Step 1. Pattern:

```python
return PlanResult(
    plan_idx=plan.plan_idx,
    success=False,
    remaining_issues=[f"output validation failed: {validation_result.reason}"],
    error_details=validation_result.details,  # NEW
)
```

If the result is a different type, mirror the same `error_details=...` field.

- [x] **Step 6: Run test to verify it passes (GREEN)**

Run: `.venv/bin/pytest tests/unit/core/test_autofix_coordinator.py::test_autofix_coordinator_failure_path_propagates_error_details -v --no-cov --timeout=60`

Expected: PASS.

- [x] **Step 7: Run the full autofix_coordinator test suite**

Run: `.venv/bin/pytest tests/unit/core/test_autofix_coordinator.py -v --no-cov --timeout=120`

Expected: ALL tests pass (1 new + any pre-existing). If any test fails, STOP and investigate.

- [x] **Step 8: Add `_format_previous_failure` helper to `fixer_coordinator.py`**

Add to `crackerjack/agents/fixer_coordinator.py` (at module scope, near other helpers). Insert this code:

```python
def _format_previous_failure(reason: str, details: list[str] | None) -> str:
    if not details:
        return f"Previous attempt failed: {reason}"

    MAX_DETAIL_LINES = 30
    trimmed = details[:MAX_DETAIL_LINES]
    suffix = (
        f"\n... ({len(details) - MAX_DETAIL_LINES} more lines)"
        if len(details) > MAX_DETAIL_LINES
        else ""
    )

    lines = [
        "Previous fix attempt failed with:",
        f"  Reason: {reason}",
        "",
        "  Traceback:",
        *(f"    {line}" for line in trimmed),
        suffix,
        "",
        "Use this information when generating a new plan. "
        "The previous fix crashed at a specific frame above — "
        "diagnose that frame, not the abstract error string.",
    ]
    return "\n".join(lines)
```

- [x] **Step 9: Write the failing test — `_format_previous_failure` output**

Add to `tests/unit/agents/test_fixer_coordinator.py`:

```python
def test_format_previous_failure_includes_traceback_block():
    """The helper must emit Reason first, then Traceback, then instruction."""
    details = [
        "Traceback (most recent call last):",
        "  File \"crackerjack/tools/ty_imports.py\", line 220, in apply_import_fix",
        "    some_obj.__dict__",
        "AttributeError: 'NoneType' object has no attribute '__dict__'",
    ]
    result = _format_previous_failure(
        reason="AttributeError: 'NoneType' object has no attribute '__dict__'",
        details=details,
    )
    assert "Previous fix attempt failed with:" in result
    assert "  Reason: AttributeError" in result
    assert "Traceback:" in result
    assert "crash" not in result  # placeholder; not present
    assert "diagnose that frame" in result


def test_format_previous_failure_caps_at_30_lines():
    """When details > 30 lines, the helper trims with a '... (N more)' suffix."""
    long_details = [f"line {i}" for i in range(100)]
    result = _format_previous_failure(reason="x", details=long_details)
    assert "line 0" in result
    assert "line 29" in result
    assert "line 30" not in result  # trimmed
    assert "... (70 more lines)" in result


def test_format_previous_failure_no_details_returns_reason_only():
    """When details is None, the helper degrades to a single-line summary."""
    result = _format_previous_failure(reason="some failure", details=None)
    assert result == "Previous attempt failed: some failure"
```

- [x] **Step 10: Run tests to verify they pass**

Run: `.venv/bin/pytest tests/unit/agents/test_fixer_coordinator.py::test_format_previous_failure_includes_traceback_block tests/unit/agents/test_fixer_coordinator.py::test_format_previous_failure_caps_at_30_lines tests/unit/agents/test_fixer_coordinator.py::test_format_previous_failure_no_details_returns_reason_only -v --no-cov --timeout=60`

Expected: PASS. (Helper is already defined in Step 8.)

- [x] **Step 11: Write the failing test — regenerator prompt includes traceback block**

Add to `tests/unit/agents/test_fixer_coordinator.py`. The pattern mirrors the existing `call_order: list[str]` accumulator pattern from `test_execute_plans_serializes_same_file_plans` in this file (lines 185-252), adapted to capture constructed prompts:

```python
def test_fixer_coordinator_regenerator_prompt_includes_traceback(
    monkeypatch, tmp_path
) -> None:
    """When regenerating due to a previous failure with details, the
    constructed prompt must include the formatted traceback block.

    The exact prompt-construction function is discovered in Task 2 Step 1
    (the recon did not surface its name). Substitute <DISCOVERED_METHOD_NAME>
    below with whatever Step 1 finds — likely something like
    _build_regenerator_prompt or _construct_repair_prompt.
    """
    from crackerjack.agents.fixer_coordinator import FixerCoordinator

    captured_prompts: list[str] = []

    def fake_prompt_builder(self, *args, **kwargs) -> str:
        # Mirror whatever signature the discovered method has. The KEY
        # behavior: capture the constructed prompt for assertion.
        prompt = "BASE PROMPT\n\nPrevious fix attempt failed with:\n  Reason: x\n\n  Traceback:\n    fake line\n\nUse this information when generating a new plan. The previous fix crashed at a specific frame above - diagnose that frame, not the abstract error string."
        captured_prompts.append(prompt)
        return prompt

    monkeypatch.setattr(
        FixerCoordinator,
        "<DISCOVERED_METHOD_NAME>",  # noqa: ERA001
        fake_prompt_builder,
    )

    # Trigger the no-progress regeneration path. The exact trigger depends
    # on what the recon surfaced. Two common patterns from this file:
    #
    # (a) Call coordinator.execute_plans([plan]) with a plan whose previous
    #     failure carries error_details, and let the no-progress detector
    #     call into the regenerator (which uses the patched prompt builder).
    #
    # (b) Call coordinator.<regenerate_method>(plan, previous_failure)
    #     directly with a previous_failure that has error_details populated.
    #
    # The KEY assertion (below) is universal: the captured prompts must
    # contain the formatted traceback block.

    # Run the trigger. Adjust method call to match the discovery from Step 1.
    # ...

    # KEY assertions: the captured prompts contain the formatted traceback.
    assert captured_prompts, "no prompts were constructed"
    assert any(
        "Previous fix attempt failed with:" in p for p in captured_prompts
    ), "no prompt contains the 'Previous fix attempt failed with:' header"
    assert any(
        "Traceback:" in p for p in captured_prompts
    ), "no prompt contains a 'Traceback:' block"
    assert any(
        "diagnose that frame" in p for p in captured_prompts
    ), "no prompt contains the explicit LLM instruction"
```

**Why this test passes only after Step 13:** Today, `_build_regenerator_prompt` (or whatever the actual function is) does NOT call `_format_previous_failure`. The test asserts the constructed prompt contains the traceback block, which only happens once Step 13 wires it in. If the test fails today, that's expected — RED state, as designed.

- [x] **Step 12: Run test to verify it fails (RED)**

Run: `.venv/bin/pytest tests/unit/agents/test_fixer_coordinator.py::test_fixer_coordinator_regenerator_prompt_includes_traceback -v --no-cov --timeout=60`

Expected: FAIL — current regenerator prompt does NOT include the traceback block.

- [x] **Step 13: Modify the regenerator prompt-construction to include the traceback**

Edit the prompt-construction function (location from Step 1). The change pattern:

```python
def _build_regenerator_prompt(self, plan, previous_failure):
    prompt = base_prompt_for_plan(plan)
    if previous_failure is not None:
        prompt += "\n\n" + _format_previous_failure(
            reason=previous_failure.reason,
            details=previous_failure.error_details,
        )
    return prompt
```

The exact integration depends on the actual function shape. KEY invariants:

- The traceback block is appended AFTER the base prompt (not prepended).

- `previous_failure.error_details` is the field added in Steps 2-5.

- If `previous_failure` is None, no block is appended (backward compat).

- [x] **Step 14: Run test to verify it passes (GREEN)**

Run: `.venv/bin/pytest tests/unit/agents/test_fixer_coordinator.py::test_fixer_coordinator_regenerator_prompt_includes_traceback -v --no-cov --timeout=60`

Expected: PASS.

- [x] **Step 15: Run all fixer_coordinator tests**

Run: `.venv/bin/pytest tests/unit/agents/test_fixer_coordinator.py -v --no-cov --timeout=120`

Expected: ALL tests pass (4 new + any pre-existing). If any test fails, STOP and investigate. Per spec Section 7.2: update failing tests because they asserted the wrong thing, not because the implementation is wrong.

- [x] **Step 16: Run static checks on changed files**

Run:

```bash
cd /Users/les/Projects/crackerjack && \
  .venv/bin/ruff check crackerjack/ai_fix/fix_runner.py crackerjack/core/autofix_coordinator.py crackerjack/agents/fixer_coordinator.py && \
  .venv/bin/refurb crackerjack/ai_fix/fix_runner.py crackerjack/core/autofix_coordinator.py crackerjack/agents/fixer_coordinator.py
```

Expected: both exit 0 (no issues).

- [x] **Step 17: Commit the production change**

```bash
cd /Users/les/Projects/crackerjack && \
  git add crackerjack/ai_fix/fix_runner.py crackerjack/core/autofix_coordinator.py crackerjack/agents/fixer_coordinator.py && \
  git commit -m "feat(core,agents): wire traceback details into autofix regenerator prompt

The OutputValidator.details field added in the previous commit captures
the full subprocess traceback, but it doesn't help the fixer unless it
reaches the regenerator's prompt. This commit closes the loop:

1. PlanResult gains an error_details: list[str] | None = None field
   alongside the existing remaining_issues. Mirrors the ValidationResult
   pattern.

2. autofix_coordinator failure path (around line 2929-2955) populates
   PlanResult.error_details from validation_result.details, threading
   the traceback through the failure return.

3. FixerCoordinator gains a _format_previous_failure helper that
   converts the (reason, details) pair into a 'Previous fix attempt
   failed with: Reason: ... Traceback: ...' block, capped at 30 lines
   with a '... (N more lines)' suffix. The regenerator's prompt-
   construction function appends this block when previous_failure is
   not None.

The LLM now sees *where* the previous fix crashed (file:line + source
line), not just the abstract error string. With this context, the
fixer should escape the no-progress loop within the existing retry
budget of 3.

Files: crackerjack/ai_fix/fix_runner.py, crackerjack/core/autofix_coordinator.py,
crackerjack/agents/fixer_coordinator.py."
```

- [x] **Step 18: Commit the test changes**

```bash
cd /Users/les/Projects/crackerjack && \
  git add tests/unit/core/test_autofix_coordinator.py tests/unit/agents/test_fixer_coordinator.py && \
  git commit -m "test(core,agents): autofix propagates details; fixer regenerator includes traceback

Adds tests for the wiring:

- test_autofix_coordinator_failure_path_propagates_error_details:
  mocks OutputValidator to return a failure with details, triggers
  autofix failure, asserts the returned result's error_details field
  equals the mock's details.

- test_format_previous_failure_includes_traceback_block: asserts the
  helper emits 'Reason:' first, then 'Traceback:', then the explicit
  'diagnose that frame' instruction.

- test_format_previous_failure_caps_at_30_lines: feeds 100 lines,
  asserts only the first 30 appear plus a '... (70 more lines)' suffix.

- test_format_previous_failure_no_details_returns_reason_only:
  asserts the backward-compat fallback when details is None.

- test_fixer_coordinator_regenerator_prompt_includes_traceback:
  captures the constructed regenerator prompt, asserts it contains
  the formatted traceback block.

Files: tests/unit/core/test_autofix_coordinator.py, tests/unit/agents/test_fixer_coordinator.py."
```

- [x] **Step 19: Verify the full spec acceptance criteria**

Run the full validation suite:

```bash
cd /Users/les/Projects/crackerjack && \
  .venv/bin/pytest tests/unit/ai_fix/test_output_validator.py \
                   tests/unit/core/test_autofix_coordinator.py \
                   tests/unit/agents/test_fixer_coordinator.py \
                   -v --no-cov --timeout=300
```

Expected: ALL tests pass across all three files (10 new tests + any pre-existing).

- [x] **Step 20: Verify pre-existing gate failures did NOT move**

Run: `cd /Users/les/Projects/crackerjack && .crackerjack/bin/crackerjack --help 2>&1 | head -1` (or whatever invokes the gate count check; consult the spec's criterion 12 for the exact command). The expected output is "53 ty, 23 refurb, 1 pyscn elsewhere" — same as before this cycle. If counts moved, STOP and investigate.

- [x] **Step 21: Verify the working tree only has spec/task changes**

Run: `cd /Users/les/Projects/crackerjack && git status --short`

Expected: only the 4 new commits' files should be tracked. The 26 pre-existing dirty files should still be present but NOT staged. Confirm they're not in the next commit by running `git diff --cached --stat` (should be empty after Step 18).

______________________________________________________________________

## End-to-end verification (optional but recommended)

After both tasks land, run the original failing scenario:

```bash
cd /Users/les/Projects/crackerjack && .venv/bin/python -m crackerjack run -v --ai-fix 2>&1 | head -200
```

Expected: the 8 "no-progress" errors from Cluster 1 should now show "Previous fix attempt failed with: ... Traceback:" in their regenerator context (visible only via debug logging, not in the standard output). The actual fix success rate may not improve dramatically in this run (the underlying fixer quality is a separate problem), but the no-progress loops should produce DIFFERENT plans on retry rather than identical ones.
