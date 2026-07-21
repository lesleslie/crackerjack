______________________________________________________________________

## status: active role: implementation date: 2026-07-17 last_reviewed: 2026-07-17 superseded_by: null blocks_on: [] topic: lifecycle

# AI-fix no-op circuit breaker — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop the AI-fix per-issue retry loop early when the planner produces identical no-op plans back-to-back, saving the wasted 3rd attempt.

**Architecture:** Add a `_plan_signature(plan)` static helper that returns a stable SHA-256-based 16-char hex hash of `FixPlan` content (issue_type + file_path + sorted changes). Track the previous signature across the 3-attempt retry loop; when 2 consecutive attempts produce no-op results with matching signatures, `break` the loop and emit a `FixResult` with reason `"stuck: planner producing identical plans"`.

**Tech Stack:** Python 3.13, `hashlib` (stdlib), `pytest` (auto asyncio mode), `unittest.mock.AsyncMock`.

## Global Constraints

- **Project conventions** (from `crackerjack/CLAUDE.md`):
  - `from __future__ import annotations` as the first non-comment line of every source file.
  - Imports sorted within each section (stdlib → third-party → first-party, with `force-sort-within-sections = true`).
  - Modern syntax: `X | None`, `list[str]`, `pathlib.Path`.
  - Function arguments with default `None` typed as `X | None = None`.
- **Test conventions**:
  - Use the project pytest markers: `unit` (don't invent new ones).
  - Async tests don't need `@pytest.mark.asyncio` — `asyncio_mode = "auto"`.
- **Ruff line length**: 88 chars.
- **Hard limits**: max-args 10, max-branches 15, max-returns 6, max-statements 55.

______________________________________________________________________

### Task 1: Add `_plan_signature` helper + wire circuit breaker into retry loop + 5 tests

**Files:**

- Modify: `crackerjack/core/autofix_coordinator.py` — add `_plan_signature` static method adjacent to existing `_get_regen_timeout` (around line 1654); add circuit-breaker state + check inside the retry loop at line 4329.
- Create: `tests/unit/core/test_autofix_no_op_circuit_breaker.py` — 5 unit tests.

**Interfaces:**

- Produces: `AutofixCoordinator._plan_signature(plan: FixPlan) -> str` — returns deterministic 16-char hex SHA-256 prefix.

- [x] **Step 1: Write the failing test file**

Create `tests/unit/core/test_autofix_no_op_circuit_breaker.py` with the following contents:

```python
"""Test the _plan_signature helper and no-op circuit breaker."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from crackerjack.ai_fix.tightened_dispatcher import NO_OP_REMAINING_ISSUE
from crackerjack.core.autofix_coordinator import AutofixCoordinator
from crackerjack.models.fix_plan import ChangeSpec, FixPlan


def _make_plan(
    issue_type: str = "refactor_for_clarity",
    file_path: str = "crackerjack/foo.py",
    changes: tuple[ChangeSpec, ...] = (),
    rationale: str = "default rationale",
) -> FixPlan:
    return FixPlan(
        issue_type=issue_type,
        file_path=file_path,
        changes=list(changes),
        rationale=rationale,
        risk_level="low",
        validated_by="test",
        issue_message="test",
        issue_stage="test",
        issue_details=[],
    )


def test_plan_signature_is_stable_for_identical_plans() -> None:
    p1 = _make_plan()
    p2 = _make_plan()
    assert AutofixCoordinator._plan_signature(p1) == AutofixCoordinator._plan_signature(p2)


def test_plan_signature_differs_for_distinct_file_paths() -> None:
    p1 = _make_plan(file_path="crackerjack/a.py")
    p2 = _make_plan(file_path="crackerjack/b.py")
    assert AutofixCoordinator._plan_signature(p1) != AutofixCoordinator._plan_signature(p2)


def test_plan_signature_ignores_rationale() -> None:
    p1 = _make_plan(rationale="first")
    p2 = _make_plan(rationale="second")
    assert AutofixCoordinator._plan_signature(p1) == AutofixCoordinator._plan_signature(p2)


def test_plan_signature_differs_for_distinct_changes() -> None:
    p1 = _make_plan(
        changes=(
            ChangeSpec(
                line_range=(1, 1),
                old_code="x = 1",
                new_code="x = 2",
                reason="test",
            ),
        )
    )
    p2 = _make_plan(
        changes=(
            ChangeSpec(
                line_range=(1, 1),
                old_code="x = 1",
                new_code="x = 999",
                reason="test",
            ),
        )
    )
    assert AutofixCoordinator._plan_signature(p1) != AutofixCoordinator._plan_signature(p2)


@pytest.mark.asyncio
async def test_circuit_breaker_skips_after_two_no_op_results() -> None:
    """After 2 consecutive no-op attempts, the loop should break with 'stuck' reason."""
    from crackerjack.agents.base import FixResult

    coord = AutofixCoordinator(project_path=".", max_iterations=3)

    # Stub _execute_plan_with_validation to always return no-op
    no_op_result = FixResult(
        success=False,
        confidence=0.0,
        fixes_applied=[],
        remaining_issues=[NO_OP_REMAINING_ISSUE],
        recommendations=[],
        files_modified=[],
        issue_specific_confidence=None,
    )
    coord._execute_plan_with_validation = AsyncMock(  # type: ignore[method-assign]
        return_value=(False, [no_op_result], "no-op")
    )
    coord._is_global_budget_exhausted = lambda: False  # type: ignore[method-assign]
    coord._fail_plan = MagicMock(  # type: ignore[method-assign]
        return_value=("stuck: planner producing identical plans", [no_op_result])
    )
    coord._global_attempt_count = 0
    coord.logger = MagicMock()  # type: ignore[assignment]

    plan = _make_plan()
    fc = MagicMock()
    vc = MagicMock()
    bar = MagicMock()

    # Call the inner loop body — note: this test assumes the loop is exposed
    # OR we call it via a small public seam. Adjust based on actual structure:
    # see Step 5 for the wiring details.
```

- [x] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/core/test_autofix_no_op_circuit_breaker.py -v --no-cov`
Expected: tests 1-4 fail with `AttributeError: type object 'AutofixCoordinator' has no attribute '_plan_signature'`. Test 5 also fails (method doesn't exist yet).

- [x] **Step 3: Add the `_plan_signature` static method**

In `crackerjack/core/autofix_coordinator.py`, insert after `_get_regen_timeout` (around line 1662). Add the import at the top of the file if not already present:

```python
import hashlib
import json
```

Then insert the method:

```python

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

Verify `FixPlan` and `ChangeSpec` are importable from `crackerjack.models.fix_plan` (existing module). If not, fix the import.

- [x] **Step 4: Run the unit tests for the helper to verify they pass**

Run: `uv run pytest tests/unit/core/test_autofix_no_op_circuit_breaker.py -v --no-cov -k "plan_signature"`
Expected: 4 PASSED tests (tests 1-4 — the signature tests).

- [x] **Step 5: Wire the circuit breaker into the retry loop**

In `crackerjack/core/autofix_coordinator.py`, find the retry loop at line 4329 (`for attempt in range(3):`). Read the loop body carefully (lines 4329-4400 approximately) to understand the current structure before editing.

The wiring changes:

**Before the loop** (insert one line above `for attempt in range(3):`):

```python
        _previous_plan_signature: str | None = None
```

**Inside the loop**, after the `success, plan_results, feedback = await asyncio.wait_for(...)` call completes successfully (no TimeoutError, no OSError), add this check:

```python
                # No-op circuit breaker: if 2 consecutive attempts produce the same
                # plan signature with no-op outcomes, stop — the third attempt can't differ.
                if not success and any(
                    "no-op fix:" in (ri or "")
                    for result in plan_results or []
                    for ri in (result.remaining_issues or [])
                ):
                    _current_signature = self._plan_signature(plan)
                    if _current_signature == _previous_plan_signature:
                        feedback = "stuck: planner producing identical plans"
                        self.logger.warning(
                            f"\033[93m⛔ [FixerCoordinator] {feedback} "
                            f"({plan_loc}); breaking retry loop\033[0m"
                        )
                        return self._fail_plan(
                            "Stuck Plan",
                            feedback,
                            feedback,
                            plan.file_path,
                            accumulated_feedback,
                            bar,
                        )
                    _previous_plan_signature = _current_signature
                elif success:
                    _previous_plan_signature = None
```

The exact placement depends on the loop body's structure. Read it first, then insert at the right indentation. The `self._fail_plan` helper exists (verify with `grep -n "_fail_plan" crackerjack/core/autofix_coordinator.py`); use it if available, otherwise construct the failure inline.

- [x] **Step 6: Run all 5 tests to verify they pass**

Run: `uv run pytest tests/unit/core/test_autofix_no_op_circuit_breaker.py -v --no-cov`
Expected: 5 PASSED tests.

If test 5 (the async circuit breaker test) fails because the loop isn't exposed, adjust the test to call the loop body via the public method or extract the loop into a small helper that the test can stub directly. Update the test to match the actual structure.

- [x] **Step 7: Verify no regression in existing autofix coordinator tests**

Run: `uv run pytest tests/unit/core/test_autofix_coordinator.py -v --no-cov`
Expected: all pre-existing tests still pass.

- [x] **Step 8: Verify ruff clean on the changed file**

Run: `uv run ruff check crackerjack/core/autofix_coordinator.py tests/unit/core/test_autofix_no_op_circuit_breaker.py`
Expected: All checks passed!

If violations appear, fix them in-place before committing. Most likely: line-length (88 chars max), import order.

- [x] **Step 9: Commit**

```bash
git add crackerjack/core/autofix_coordinator.py tests/unit/core/test_autofix_no_op_circuit_breaker.py
git commit -m "feat(ai-fix): add no-op circuit breaker to skip identical retry plans (cluster 4)"
```

Commit message body should reference the spec (`docs/superpowers/specs/2026-07-11-ai-fix-no-op-circuit-breaker-design.md` committed `6ee55480`) and note that the circuit breaker fires when 2 consecutive attempts produce no-op results with matching plan signatures.
