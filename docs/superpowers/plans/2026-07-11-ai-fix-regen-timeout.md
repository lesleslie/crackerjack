______________________________________________________________________

## status: active role: implementation date: 2026-07-17 last_reviewed: 2026-07-17 superseded_by: null blocks_on: [] topic: lifecycle

# AI-fix plan-regeneration timeout — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the AI-fix plan-regeneration step's timeout operator-tunable via a new env var, defaulting to 90 seconds.

**Architecture:** Add a new static method `_get_regen_timeout()` on `AutofixCoordinator` mirroring the existing `_get_per_issue_timeout()` pattern. Replace the hardcoded `timeout=30` literal at the regen call site with a call to this method. Add 4 unit tests to the existing `test_ai_fix_env_vars.py` file.

**Tech Stack:** Python 3.13, pytest (auto asyncio mode per `pyproject.toml`), `pytest.MonkeyPatch.setenv` / `delenv`.

## Global Constraints

- **Project conventions** (from `crackerjack/CLAUDE.md`):
  - `from __future__ import annotations` as the first non-comment line of every source file.
  - Imports sorted within each section (stdlib → third-party → first-party, with `force-sort-within-sections = true`).
  - Modern syntax: `X | None`, `list[str]`, `pathlib.Path`.
  - Function arguments with default `None` typed as `X | None = None`.
  - Use the Oneiric logger, not stdlib `logging` (production code only — tests use stdlib `logging` per project convention).
- **Test conventions**:
  - Use the project pytest markers: `unit` (don't invent new ones).
  - Async tests don't need `@pytest.mark.asyncio` — `asyncio_mode = "auto"`.
  - Tests in `tests/unit/core/` namespace have relaxed typing but `from __future__ import annotations` still applies.
- **Ruff line length**: 88 chars (per `pyproject.toml [tool.ruff] line-length`).
- **Hard limits**: max-args 10, max-branches 15, max-returns 6, max-statements 55 (per `pyproject.toml [tool.ruff.lint.pylint]`).
- **Env var pattern**: all `_get_xxx()` static methods on `AutofixCoordinator` follow the exact pattern: `os.environ.get(...)` → if None return default → try `int(raw)` → except `ValueError` return default. Mirror this exactly.

______________________________________________________________________

### Task 1: Add `_get_regen_timeout` static method + wire it + add 4 tests

**Files:**

- Modify: `crackerjack/core/autofix_coordinator.py:1652-1653` (add new method after `_get_per_issue_timeout`)
- Modify: `crackerjack/core/autofix_coordinator.py:4473-4484` (replace hardcoded `timeout=30` with call to new method)
- Modify: `tests/unit/core/test_ai_fix_env_vars.py` (append 4 new test functions before the existing module-end)

**Interfaces:**

- Consumes: `os.environ.get("CRACKERJACK_AI_FIX_REGEN_TIMEOUT")` — string or None

- Consumes: `_get_per_issue_timeout()` pattern at lines 1644-1652 — mirror this exactly

- Produces: `AutofixCoordinator._get_regen_timeout() -> int` — default 90, env-overridable, falls back to 90 on `ValueError`

- [x] **Step 1: Write the failing tests**

Append to `tests/unit/core/test_ai_fix_env_vars.py` (after the existing `test_get_ai_fix_sandbox_timeout_s_default` function at line 42, before EOF):

```python


def test_get_regen_timeout_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CRACKERJACK_AI_FIX_REGEN_TIMEOUT", raising=False)
    assert AutofixCoordinator._get_regen_timeout() == 90


def test_get_regen_timeout_env_var_override(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CRACKERJACK_AI_FIX_REGEN_TIMEOUT", "180")
    assert AutofixCoordinator._get_regen_timeout() == 180


def test_get_regen_timeout_malformed_falls_back_to_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CRACKERJACK_AI_FIX_REGEN_TIMEOUT", "not-a-number")
    assert AutofixCoordinator._get_regen_timeout() == 90


def test_get_regen_timeout_negative_value_passes_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CRACKERJACK_AI_FIX_REGEN_TIMEOUT", "-5")
    assert AutofixCoordinator._get_regen_timeout() == -5
```

Note: 4 tests total. The first test asserts the default is 90 (matches spec). The second asserts env var override. The third asserts malformed value falls back to default (matches `_get_per_issue_timeout` behavior at line 1651). The fourth asserts negative value passes through unfiltered (matches `_get_per_issue_timeout` behavior at line 1650 — no special handling).

- [x] **Step 2: Run the tests to verify they fail**

Run: `uv run pytest tests/unit/core/test_ai_fix_env_vars.py -v -k "regen_timeout"`
Expected: 4 FAILED tests with `AttributeError: type object 'AutofixCoordinator' has no attribute '_get_regen_timeout'`

- [x] **Step 3: Add the `_get_regen_timeout` static method**

In `crackerjack/core/autofix_coordinator.py`, insert after line 1652 (the `_get_per_issue_timeout` method ends with `return 300` followed by blank line at 1653):

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

The blank line between the existing `_get_per_issue_timeout` block and the new method preserves the PEP 8 two-blank-lines-between-methods convention for class methods.

- [x] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/core/test_ai_fix_env_vars.py -v -k "regen_timeout"`
Expected: 4 PASSED tests

- [x] **Step 5: Wire the new method into the regen call site**

In `crackerjack/core/autofix_coordinator.py`, replace lines 4473-4478:

Before:

```python
        enhanced_issue = self._enhance_issue_with_feedback(source_issue, feedback)
        try:
            new_plans = await asyncio.wait_for(
                analysis_coordinator.analyze_issues([enhanced_issue]),
                timeout=30,
            )
```

After:

```python
        enhanced_issue = self._enhance_issue_with_feedback(source_issue, feedback)
        regen_timeout = self._get_regen_timeout()
        try:
            new_plans = await asyncio.wait_for(
                analysis_coordinator.analyze_issues([enhanced_issue]),
                timeout=regen_timeout,
            )
```

The local-variable pattern (`regen_timeout = self._get_regen_timeout()`) matches the existing `per_issue_timeout = self._get_per_issue_timeout()` pattern at line 4290.

- [x] **Step 6: Verify ruff clean on the changed file**

Run: `uv run ruff check crackerjack/core/autofix_coordinator.py`
Expected: All checks passed!

If any violations appear, fix them in-place before committing. The most likely violations are: line-length (>88 chars after edit), import-order if a new import is needed (none expected — `os` is already imported at module top).

- [x] **Step 7: Run the full test suite for the changed module to confirm no regressions**

Run: `uv run pytest tests/unit/core/test_ai_fix_env_vars.py tests/unit/core/test_autofix_coordinator.py -v`
Expected: All previously-passing tests still pass; the 4 new tests pass.

- [x] **Step 8: Commit**

```bash
git add crackerjack/core/autofix_coordinator.py tests/unit/core/test_ai_fix_env_vars.py
git commit -m "feat(ai-fix): make plan-regen timeout operator-tunable (cluster 3)"
```

Commit message body should reference the spec (`docs/superpowers/specs/2026-07-11-ai-fix-regen-timeout-design.md` at commit `2f222044`) and note that the previous hardcoded `timeout=30` was the root cause of the dominant timeout cascade in the AI-fix error log.
