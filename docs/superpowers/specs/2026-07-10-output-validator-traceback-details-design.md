# OutputValidator Traceback Details — Design

**Date**: 2026-07-11
**Status**: Draft — awaiting user review
**Author**: Claude (brainstorming session)
**Related**: triage note `docs/superpowers/triage/2026-07-10-output-validator-import-check.md`; recon-driven reframing from "validator crash" to "validator discards traceback frames"; Defect #2 commit chain `88f2b181..1d7fad27` (now on `origin/main`).

## Problem

The `crackerjack run --ai-fix` loop's fixer is stuck in no-progress loops, regenerating identical plans. The visible failure mode (from the latest run output) is:

```
OutputValidator: import_check failed for crackerjack/tools/ty_imports.py:
  AttributeError: 'NoneType' object has no attribute '__dict__'.
  Did you mean: '__dir__'?
⚠️ Output validation failed for crackerjack/tools/ty_imports.py …
✗ [FixerCoordinator] No progress — regenerated plan is identical to the failed one
  (crackerjack/tools/ty_imports.py:220)
```

The same pattern repeats for `ty_narrow.py`, `ty_classify.py`, and multiple sites in `autofix_coordinator.py`. The user's earlier 4-cluster taxonomy labeled this "Cluster 1 (validator crash)."

### What recon revealed

Three findings from the recon agent that reframe the bug:

1. **`OutputValidator` is internally consistent.** The `import_check` method, the `OutputValidator.validate` wrapper, and all three check functions (`syntax_check`, `import_check`, `ruff_sanity_check`) never touch `.__dict__` on anything. The `'NoneType' object has no attribute '__dict__'` error string is **the last line of stderr from a child Python process**, not from crackerjack's validator code.

1. **No top-level `None.__dict__` exists in any reported file.** Recon grep'd `ty_imports.py`, `ty_narrow.py`, `ty_classify.py` for `__dict__|__class__|__bases__|__mro__|__subclasses__|__name__|__module__` at module scope. The only hits are inside function bodies. `ty_imports.py:220` is `file_path: Path,` — a parameter declaration inside `def apply_import_fix(`, not an executable statement.

1. **`import_check` discards traceback frames** (`output_validator.py:95-96`):

   ```python
   err_lines = (proc.stderr or proc.stdout).strip().splitlines()
   reason = err_lines[-1] if err_lines else f"import exit {proc.returncode}"
   ```

   It takes only the **last line** of stderr as the failure reason. A multi-line Python traceback's last line is the exception type + message — the *what*, but not the *where*. The actual root-cause frame (file:line + source line) is buried several lines up and gets thrown away.

### So what is actually happening?

The validator is doing its job. The subprocess it runs (`_IMPORT_DRIVER`, lines 22-39) does `spec.loader.exec_module(module)`, which executes the **target file's top-level code**. When that code raises an `AttributeError`, the driver's `except Exception as exc:` block catches it, prints the exception type + message to stderr, prints the full traceback via `traceback.print_exc`, then `sys.exit(1)`. `import_check` sees the non-zero exit code, takes only the last line of stderr, returns `ValidationResult(passed=False, reason=<last line>)`.

The fixer sees `reason = "AttributeError: 'NoneType' object has no attribute '__dict__'"` and has no idea which file, which line, which expression raised it. So it regenerates the same plan, validation fails the same way, no-progress detector trips, loop.

**The validator is the messenger, not the bug.** The bug is the fixer's inability to learn from previous attempts because the messenger only relays the headline.

## Goal

Surface the full traceback from validator failures so the fixer's no-progress regeneration has the diagnostic context to actually produce a different plan. Specifically:

- `ValidationResult` gains a `details: list[str] | None` field carrying full traceback lines.
- `import_check` populates `details` from raw subprocess stderr (one entry per line, including frame headers and source lines).
- The autofix failure path propagates `details` through to the `FixerCoordinator` regenerator.
- The regenerator's prompt includes a "previous failure traceback" block (capped at 30 lines) so the LLM sees *where* the previous fix crashed, not just *that* it crashed.

Out of scope (separate triage if/when prioritized):

- Other failure clusters (Cluster 2 `from __future__` placement, Cluster 3 invalid Python, Cluster 4 type/lint drift).
- Other validator checks (`syntax_check`, `ruff_sanity_check`) — unchanged for this cycle; future cycle could extend them similarly.
- Fixer retry budget (current: 3, confirmed by user — unchanged).
- Fixer prompt template, model choice, or underlying agents — unchanged.

## Design Decisions

1. **Additive change to `ValidationResult`.** New field `details: list[str] | None = None` placed last. Existing constructions (`ValidationResult(passed=False, reason="x")`) continue to work without modification. Frozen dataclass + Optional default sidesteps linter warnings about mutable defaults.

1. **Raw `splitlines()`, not stripped.** `details = stderr_text.splitlines()` preserves the leading whitespace on traceback frame lines (e.g., `  File "..."`), which gives the fixer visual indentation to parse. The `reason` field continues to use `.strip().splitlines()[-1]` for backward compat.

1. **`None` for empty stderr, not `[]`.** When the subprocess exits non-zero with no captured output, `details = None`. This is the unambiguous "no structured details" signal. Consumers default with `details or []`.

1. **Wiring channel: `PlanResult.error_details`.** The autofix failure path adds a new field next to the existing `remaining_issues: list[str]` on `PlanResult`. Mirrors an existing field. Type-safe, discoverable, no shared state (avoids race risk under `ParallelDispatcher`). Implementer subagent picks this exact shape during SDD execution; if the actual return type is structurally different from `PlanResult`, the subagent chooses Option A (`result.error_details`) instead.

1. **Traceback cap at 30 lines.** A real traceback can be 100+ lines. Capping at 30 keeps the most recent frames (where the actual crash site is) and bounds the prompt budget. Trimming suffix `... (N more lines)` is informational only.

1. **`Reason:` always first in the prompt block.** Even when `details` is non-empty, the first line of the block is the same `reason` the fixer sees today. Backward-compatible signal at the top; rich signal below. Without this, an LLM might fall back to ignoring `details` and pattern-matching on `Reason:`.

1. **Explicit instruction to the LLM:** "Diagnose that frame, not the abstract error string." Without it, the LLM may overfit to the exception text rather than reading the traceback. With it, the LLM is told where to look.

1. **No new public API.** `FixerCoordinator`'s new behavior is internal to the prompt-construction function. External callers don't see anything change.

## Implementation Outline

### File 1: `crackerjack/ai_fix/output_validator.py`

**Change 1 — Add `details` to `ValidationResult`** (line 42-46):

```python
@dataclass(frozen=True)
class ValidationResult:
    passed: bool
    reason: str = ""
    skipped: bool = False
    details: list[str] | None = None
```

**Change 2 — Populate `details` in `import_check`** (lines 72-97):

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

`reason` is byte-identical to the previous output. `details` carries the full stderr.

### File 2: `crackerjack/core/autofix_coordinator.py`

**Change — Thread `details` into the failure result** (around lines 2929-2955):

The recon showed:

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

The failure path adds `error_details` to whatever result type is returned here. **Implementer subagent must confirm the exact return type during execution** (the recon didn't show the full return site). If it's `PlanResult` from `fix_runner.py`, add `PlanResult.error_details: list[str] | None = None`. If it's a parallel type, add the field there instead. Recommendation in this spec is `PlanResult.error_details` mirroring the existing `PlanResult.remaining_issues: list[str]`.

### File 3: `crackerjack/agents/fixer_coordinator.py`

**Change — Format details into the regenerator prompt:**

The implementer subagent must locate the prompt-construction function (the recon didn't pinpoint it; likely named `_build_*_prompt`, `_format_*_prompt`, or inline at the regenerator call site). Add the formatting helper:

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

The prompt-construction function appends this block when the previous failure has non-None `error_details`:

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

### File 4: `crackerjack/ai_fix/fix_runner.py`

**Change — Add `error_details` to `PlanResult`:**

The dataclass gains a new field:

```python
@dataclass(frozen=True)
class PlanResult:
    plan_idx: int
    success: bool
    remaining_issues: list[str] = field(default_factory=list)
    error_details: list[str] | None = None  # NEW
```

Implementer subagent confirms during execution that this is the actual type returned at the autofix failure site. If the type differs structurally (parallel result type instead of `PlanResult`), the subagent adds `error_details` to that type instead — same field shape, same semantics.

## Acceptance Criteria

The cycle is "done" when all 12 criteria below are true:

| # | Criterion |
|---|---|
| 1 | `ValidationResult(passed=True)` still works with no `details` kwarg (default `None`). |
| 2 | `ValidationResult(passed=False, reason="x", details=["line1", "line2"])` constructs correctly. |
| 3 | `import_check` on a file with a top-level `AttributeError` returns `details` containing the full traceback lines (≥3 lines: `Traceback...`, `File ...`, `AttributeError: ...`). |
| 4 | `import_check` on a file with a passing import returns `details=None`. |
| 5 | `import_check` on a file where the subprocess exits non-zero with empty stderr returns `details=None`. |
| 6 | `import_check.reason` is byte-identical to its pre-fix output for every existing test case. |
| 7 | `OutputValidator.validate()` passes `details` through without modification. |
| 8 | `autofix_coordinator` failure path propagates `validation_result.details` into the result returned to the fixer. |
| 9 | `FixerCoordinator` no-progress regenerator prompt includes the previous failure's `details` formatted as a traceback block. |
| 10 | Cap on traceback lines (30) is enforced; longer tracebacks are trimmed with the `... (N more lines)` suffix. |
| 11 | Ruff + refurb + ty clean on all changed files. |
| 12 | Pre-existing 4-cluster failure counts elsewhere in the codebase (53 ty, 23 refurb, 1 pyscn) do NOT move. |

## Test Plan

### Unit tests (extend existing + add new)

| Test | File | Asserts |
|---|---|---|
| `test_validation_result_details_defaults_none` | `tests/unit/ai_fix/test_output_validator.py` | Criterion 1 |
| `test_validation_result_details_explicit_list` | same | Criterion 2 |
| `test_import_check_captures_full_traceback_for_top_level_none_dict` | `tests/unit/ai_fix/test_output_validator_cluster1.py` (NEW) | Criterion 3 (the Cluster 1 regression) |
| `test_import_check_details_none_on_success` | same | Criterion 4 |
| `test_import_check_details_none_on_empty_stderr` | same | Criterion 5 |
| `test_import_check_reason_unchanged` | same | Criterion 6 (parametrize over existing test scenarios) |
| `test_output_validator_validate_passes_details_through` | same | Criterion 7 |
| `test_autofix_coordinator_propagates_error_details` | `tests/unit/core/test_autofix_coordinator.py` | Criterion 8 (mocked validator) |
| `test_fixer_coordinator_prompt_includes_traceback_block` | `tests/unit/agents/test_fixer_coordinator.py` | Criterion 9 (mocked prompt builder, capture constructed prompt) |
| `test_format_previous_failure_caps_at_30_lines` | same | Criterion 10 |

### The Cluster 1 regression test (most important)

```python
def test_import_check_captures_full_traceback_for_top_level_none_dict():
    """Regression for Cluster 1: validator previously reported only the last
    line of stderr, hiding the actual crash frame. With details populated,
    the fixer can see which line raised AttributeError on None.__dict__."""
    with tempfile.TemporaryDirectory() as td:
        bad_file = Path(td) / "crash.py"
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

### Existing tests that must continue to pass

- `tests/unit/agents/test_validation_coordinator.py` (uses `ValidationCoordinator`, not `ValidationResult`; unaffected)
- `tests/unit/agents/test_fixer_coordinator.py` (may need updates if it asserts exact prompt text — see Section 7.2)
- `tests/core/autofix_coordinator*` (likely uses the autofix_coordinator; may need updates if it asserts exact return shapes)

**Hard rule: no test deletion, no test weakening.** If a test fails, it must be updated because the test was asserting the wrong thing, not because the test was correct and the implementation is wrong.

### Out-of-scope verification (NOT in this cycle)

- Cluster 2: `from __future__` placement in fixer output
- Cluster 3: Fixer regenerates invalid Python
- Cluster 4: Type/lint drift after fix
- 164 pre-existing modified files in working tree
- Pre-existing crackerjack gate failures elsewhere (53 ty, 23 refurb, 1 pyscn)

The implementer subagent must explicitly verify these counts did not move at the end of the cycle (sanity check that we didn't accidentally regress something).

## Risk and Rollback

### Risk register

| # | Risk | Likelihood | Severity | Mitigation |
|---|---|---|---|---|
| 1 | Backward-compat break from new last field | Low | Medium | Field is `details: list[str] \| None = None` placed last. Spot-check during impl: search the codebase for `ValidationResult(` and confirm none pass >2 positional args. |
| 2 | Fixer overfits to traceback frame instead of root cause | Medium | Medium | Section 5's explicit instruction ("Diagnose that frame, not the abstract error string") pushes toward root-cause thinking. |
| 3 | Prompt budget bloat (~1500 tokens for 30-line traceback) | Low | Low | 30-line cap is conservative; can drop to 15 in follow-up if needed. |
| 4 | Concurrency race under ParallelDispatcher | Negligible | — | Recommendation is `PlanResult.error_details`, no shared state. |
| 5 | Test brittleness — existing tests assert exact prompt text | Medium | Low | Hard rule: no test deletion, no weakening. Tests that break must be updated because they asserted the wrong thing. |
| 6 | Path leak in traceback frames | Low | Low | CLI tool, logs are local. No new logging of details beyond what already existed for `reason`. |
| 7 | Subtle frozen-dataclass + Optional mutation bug | Negligible | Low | Frozen dataclass is the right call. |
| 8 | Traceback frame may include crackerjack-internal paths | Low | Low | Subprocess runs the target file; first frame should almost always be the target file. |

### Rollback

- **Single `git revert` of the implementation commit(s)** returns to the current state. If we ship as 2 commits (production + test, mirroring Defect #2's pattern), revert both.
- **Working state at `1d7fad27` (end of Defect #2 cycle, pre-Cluster-1)** is recoverable from git.
- **No data migration concerns.** `ValidationResult.details` is a new field with `None` default. Pre-fix `ValidationResult` instances have no `details` attribute; per the recon, no existing consumer reads `.details`. If a downstream caller is added between this spec landing and the impl running, that caller needs a fallback (`details or []`).

## Open Questions

None. The design is settled by:

- The bug shape (validator discards traceback frames).
- The user's confirmed retry budget (3).
- The user's chosen fix shape (Option 3, rich result + fixer wiring).
- The recon results (no top-level `None.__dict__` in reported files — the actual root cause is hidden behind the discarded frames).
