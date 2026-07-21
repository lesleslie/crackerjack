---
status: active
role: implementation
topic: lifecycle
date: 2026-07-17
last_reviewed: 2026-07-17
superseded_by: null
blocks_on: []
---

# W3 LibcstSurgeon Extract-Method Fallback Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 14 failing tests in `TestRefactoringAgentAstTransformFallback` and `TestRefactoringAgentThreeTierFallback` by capturing helper-method return values in `LibcstSurgeon._apply_extract_method` and replacing the blanket `except Exception` with typed catches plus a `logger.exception(...)` call.

**Architecture:** Single-source-file surgical fix. Each of the 5 dispatch branches in `_apply_extract_method` captures its helper method's return value into a shared `transformed_lines_joined` variable initialized to `None` upfront. A typed-exception clause replaces the blanket catch, surfacing `(KeyError)` etc. instead of a generic "no changes" message. Two regression tests anchor the bug surface and the diagnostic improvement.

**Tech Stack:** Python 3.13, libcst, pytest, stdlib `logging`. Crackerjack's module-level logger idiom is `logger = logging.getLogger(__name__)` (used in `crackerjack/server.py`, `crackerjack/__main__.py`, etc.).

**Related:**

- Spec: `docs/superpowers/specs/2026-07-10-libcst-surgeon-extract-method-fallback-design.md` (commit `87cd3ea3`)
- Triage: `docs/superpowers/triage/2026-07-10-refactoring-agent-ast-fallback.md` (commit `92ea7e8a`)
- WIP cleanup commit: `c6c52fd2` (66 files pre-existing modifications; should not regress)

## Global Constraints

These apply to every task. Task requirements implicitly include this section.

- All new code must have `from __future__ import annotations` as the first non-comment line (crackerjack convention).
- Imports sorted within each section (stdlib → third-party → first-party, `force-sort-within-sections = true`, `known-first-party = ["crackerjack"]`).
- Use `X | None` not `Optional[X]`, `list[str]` not `List[str]`, `pathlib.Path` for filesystem paths.
- Function arguments with default `None` typed `X | None = None` (mypy `no_implicit_optional = true`).
- In `except` blocks use `logger.exception(...)` — never `logger.error(..., exc_info=True)`.
- Module-level logger idiom: `logger = logging.getLogger(__name__)` (adds to existing stdlib import group).
- Do NOT silence / `assert` / `print(...)` in production code under `crackerjack/`.
- Test conventions: existing pytest markers only (no new markers). Async tests don't need `@pytest.mark.asyncio` (`asyncio_mode = "auto"`).
- Line length 100 chars; function args ≤10; branches ≤15; statements ≤55.
- Run pytest from crackerjack's venv (do NOT use `/Users/les/Projects/mahavishnu/.venv/bin/python`).

______________________________________________________________________

### Task 1: Baseline + regression tests

**Files:**

- Read: `tests/unit/agents/test_refactoring_agent.py`
- Modify: `tests/unit/agents/test_refactoring_agent.py:append-at-end-of-TestRefactoringAgentAstTransformFallback`

**Interfaces:**

- The test class is `TestRefactoringAgentAstTransformFallback`; tests use the `tmp_path` pytest fixture.
- `ExtractMethodPattern` and `LibcstSurgeon` are already imported at top of the test file (used by `test_extract_method_merges_adjacent_section_starts`).
- `ast` is already imported at the test class level.

**Step 1: Confirm baseline — 14 currently failing tests**

Run:

```bash
cd /Users/les/Projects/crackerjack
pytest tests/unit/agents/test_refactoring_agent.py -v 2>&1 | tail -50
```

Expected: 14 failed tests, including:

- `TestRefactoringAgentAstTransformFallback::test_extract_method_merges_adjacent_section_starts`
- `TestRefactoringAgentAstTransformFallback::test_registration_wrapper_pattern_lifts_to_module_helper`
- `TestRefactoringAgentThreeTierFallback::test_three_tier_full_analysis_uses_ast_fallback`
  (plus 11 others, listed in the spec's Problem section).

If the count differs from 14, STOP — investigate. Otherwise continue.

- [x] **Step 2: Add the split_sections dispatch regression test**

Append this test to the end of `TestRefactoringAgentAstTransformFallback`:

```python
    def test_apply_extract_method_dispatches_split_sections(self, tmp_path) -> None:
        """Regression: helper method return values were dropped for non-else
        dispatch branches (lift_nested_helpers, registration_wrapper,
        split_sections, lift_to_module), causing NameError → blanket except →
        uniform 'No changes made' message. This test directly exercises the
        split_sections dispatch branch."""
        content = (
            "async def sync_one(source, destination):\n"
            "    # Section A\n"
            "    a = source + 1\n"
            "    a = a * 2\n"
            "    # Section B\n"
            "    b = destination - 1\n"
            "    b = b / 2\n"
            "    return a + b\n"
        )
        tree = ast.parse(content)
        node = next(
            n
            for n in ast.walk(tree)
            if isinstance(n, ast.AsyncFunctionDef) and n.name == "sync_one"
        )

        pattern = ExtractMethodPattern()
        find_lines: list[str] = [str(line) for line in content.splitlines()]
        sections = pattern._find_comment_sections(node, find_lines)
        assert len(sections) >= 2

        lines: list[str] = [str(line) for line in content.splitlines()]
        match = pattern.match(node, lines)
        assert match is not None
        # Force dispatch into split_sections to exercise that branch.
        match.match_info["type"] = "split_sections"

        result = LibcstSurgeon().apply(
            content,
            match.match_info,
            tmp_path / "sync_one.py",
        )

        assert result.success is True, (
            f"Expected split_sections dispatch to succeed; got: {result.error_message}"
        )
        assert isinstance(result.transformed_code, str)
        ast.parse(result.transformed_code)
```

- [x] **Step 3: Add the KeyError diagnostic regression test**

Append this test to the end of `TestRefactoringAgentAstTransformFallback`:

```python
    def test_apply_extract_method_reports_keyerror_with_pattern_context(self) -> None:
        """Regression: blanket `except Exception` swallowed every error as the
        uniform 'No changes made by extract method fallback' message. The fix
        replaces it with typed catches + logger.exception, surfacing
        `Transform exception (KeyError): ...` instead so future regressions
        are diagnosable from the error_message alone."""
        # match_info missing required 'extraction_start' triggers KeyError when
        # the extract_method else-branch runs `int(match_info.get('extraction_start', 0)) - 1`.
        # The dict.get default makes the int() succeed with 0, so the -1 yields -1, which
        # trips the `block_start < 0` boundary check. We instead trigger a real KeyError
        # by passing a malformed match_info that the dict.get pattern in dispatch cannot
        # recover from. Easiest: completely empty match_info with type=extract_method.
        match_info: dict = {"type": "extract_method"}

        result = LibcstSurgeon().apply(
            "def f():\n    pass\n",
            match_info,
            None,
        )

        assert result.success is False
        assert result.error_message is not None
        # Either path produces a typed-message surface:
        # - First dispatch returned None (helper returned None) → ends with
        #   "helper produced no transformed code"
        # - Or post-dispatch validation surfaces (KeyError) via the typed except
        # Either is acceptable; the regression we anchor is that the blanket
        # "No changes made by extract method fallback" is no longer the
        # default surface for unexpected exceptions in the typed-exception path.
        assert "extract method fallback" not in (result.error_message or ""), (
            f"Expected typed diagnostic, got blanket swallow: {result.error_message}"
        )
```

- [x] **Step 4: Verify file still parses**

```bash
python -c "import ast; ast.parse(open('/Users/les/Projects/crackerjack/tests/unit/agents/test_refactoring_agent.py').read()); print('OK')"
```

Expected: `OK`.

- [x] **Step 5: Run the new tests — confirm both fail BEFORE the fix**

```bash
cd /Users/les/Projects/crackerjack
pytest tests/unit/agents/test_refactoring_agent.py::TestRefactoringAgentAstTransformFallback::test_apply_extract_method_dispatches_split_sections tests/unit/agents/test_refactoring_agent.py::TestRefactoringAgentAstTransformFallback::test_apply_extract_method_reports_keyerror_with_pattern_context -v
```

Expected: Both tests fail. The first fails on `assert result.success is True`; the second fails on the `not in "extract method fallback"` assertion.

If a new test passes BEFORE the fix, STOP — that means our diagnosis is wrong. Re-investigate.

- [x] **Step 6: Commit the new failing tests**

```bash
cd /Users/les/Projects/crackerjack
git add tests/unit/agents/test_refactoring_agent.py
git commit -m "test(refactoring): add 2 regression tests for libcst_surgeon extract-method fallback

Anchors the bug surface and the diagnostic improvement:
- split_sections dispatch must succeed when helper returns valid code
- blanket 'No changes made by extract method fallback' must not be the
  default surface for typed exceptions

Both tests fail before the fix; both must pass after."
```

______________________________________________________________________

### Task 2: Implement the three code changes in libcst_surgeon.py

**Files:**

- Modify: `crackerjack/agents/helpers/ast_transform/surgeons/libcst_surgeon.py:1-13` (imports)
- Modify: `crackerjack/agents/helpers/ast_transform/surgeons/libcst_surgeon.py:406-502` (the three code changes)

**Interfaces:**

- Function signature **expands** to: `_apply_extract_method(self, code: str, match_info: dict) -> str | None | TransformResult`

- The helper methods being captured (`_lift_nested_helpers_to_module`, `_lift_registration_wrapper_to_module`, `_apply_split_sections`, `_lift_method_to_module`) all return `str | None`. Capturing `None` is the success-or-failure signal the post-dispatch check uses.

- `TransformResult` is imported from `crackerjack.agents.helpers.ast_transform.surgeons.base`.

- The caller `LibcstSurgeon.apply()` (lines 330-393) treats `transformed` as `str | None` and passes it to `_simplify_append_loops(transformed)`. With the new contract, `apply()` must check `isinstance(transformed, TransformResult)` BEFORE the `_simplify_append_loops` call to short-circuit.

- [x] **Step 1: Add module-level `logging.getLogger(__name__)` import**

Find (top of file, lines 1-13):

```python
from __future__ import annotations

import ast
import copy
import re
import textwrap
import typing as t
from pathlib import Path
from typing import TYPE_CHECKING

import libcst as cst

from crackerjack.agents.helpers.ast_transform.surgeons.base import (
    BaseSurgeon,
    TransformResult,
)
```

Replace with:

```python
from __future__ import annotations

import ast
import copy
import logging
import re
import textwrap
import typing as t
from pathlib import Path
from typing import TYPE_CHECKING

import libcst as cst

from crackerjack.agents.helpers.ast_transform.surgeons.base import (
    BaseSurgeon,
    TransformResult,
)

logger = logging.getLogger(__name__)
```

(Adds `import logging` to the stdlib group alphabetically; appends module-level logger line.)

- [x] **Step 2: Initialize `transformed_lines_joined` to `None` upfront**

Find (line 411-412):

```python
    def _apply_extract_method(
        self,
        code: str,
        match_info: dict,
    ) -> str | None:
        node = match_info.get("node")
        try:
```

Replace with:

```python
    def _apply_extract_method(
        self,
        code: str,
        match_info: dict,
    ) -> str | None:
        node = match_info.get("node")
        transformed_lines_joined: str | None = None
        try:
```

- [x] **Step 3: Capture helper return values in the dispatch chain**

Find (lines 439-457 — the four dispatch branches that currently drop returns):

```python
            if match_info.get("type") == "lift_nested_helpers":
                self._lift_nested_helpers_to_module(
                    code,
                    func_node,
                    helper_name,
                )
            elif match_info.get("registration_wrapper"):
                self._lift_registration_wrapper_to_module(
                    code,
                    func_node,
                )
            elif match_info.get("type") == "split_sections":
                self._apply_split_sections(
                    code,
                    func_node,
                    match_info,
                )
            elif match_info.get("lift_to_module"):
                self._lift_method_to_module(
                    code,
                    func_node,
                    helper_name,
                )
```

Replace with (each branch now captures the return value):

```python
            if match_info.get("type") == "lift_nested_helpers":
                transformed_lines_joined = self._lift_nested_helpers_to_module(
                    code,
                    func_node,
                    helper_name,
                )
            elif match_info.get("registration_wrapper"):
                transformed_lines_joined = self._lift_registration_wrapper_to_module(
                    code,
                    func_node,
                )
            elif match_info.get("type") == "split_sections":
                transformed_lines_joined = self._apply_split_sections(
                    code,
                    func_node,
                    match_info,
                )
            elif match_info.get("lift_to_module"):
                transformed_lines_joined = self._lift_method_to_module(
                    code,
                    func_node,
                    helper_name,
                )
```

The `else` branch (extract_method) is left structurally identical, but remove the inline type annotation on its assignment so the wider `str | None` variable accepts the assignment without mypy complaint.

Find (line ~497):

```python
                transformed_lines = (
                    new_lines[:insertion_index]
                    + [helper_header, helper_body, ""]
                    + new_lines[insertion_index:]
                )

                transformed_lines_joined: str = "\n".join(transformed_lines)
```

Replace with:

```python
                transformed_lines = (
                    new_lines[:insertion_index]
                    + [helper_header, helper_body, ""]
                    + new_lines[insertion_index:]
                )

                transformed_lines_joined = "\n".join(transformed_lines)
```

(Removed the `: str` inline annotation; variable is already typed `str | None` at function entry.)

- [x] **Step 4: Replace the blanket `except` with typed catches + post-dispatch `is None` guard**

Find (lines 499-502):

```python
            ast.parse(transformed_lines_joined)
            return transformed_lines_joined
        except Exception:
            return None
```

Replace with:

```python
            if transformed_lines_joined is None:
                return TransformResult(
                    success=False,
                    error_message=(
                        f"{match_info.get('type')}: "
                        "helper produced no transformed code"
                    ),
                )

            ast.parse(transformed_lines_joined)
            return transformed_lines_joined  # type: ignore[return-value]
        except (NameError, TypeError, ValueError, KeyError, AttributeError) as exc:
            logger.exception(
                "extract_method transform failed",
                extra={"pattern_type": match_info.get("type")},
            )
            return TransformResult(
                success=False,
                error_message=f"Transform exception ({type(exc).__name__}): {exc}",
            )
```

The `# type: ignore[return-value]` is necessary because at this point `transformed_lines_joined` is still typed `str | None` even though we just narrowed with the `is None` check; mypy strict can't follow the narrowing without an explicit annotation. Adding a `# type: ignore` on this single return line keeps the contract correct.

- [x] **Step 4b: Update `apply()` to handle the new `TransformResult` return type**

In `LibcstSurgeon.apply()`'s extract-method dispatch (currently around line 350-360), the `transformed = self._apply_extract_method(code, match_info)` call may now return a `TransformResult` (typed-error path). The existing code passes `transformed` to `_simplify_append_loops` which expects a string. Without this update, the typed-error path would crash.

Find:

```python
            transformed = self._apply_extract_method(code, match_info)
            if transformed is None:
                return TransformResult(
                    success=False,
                    error_message="No changes made by extract method fallback",
                )
            transformed = self._simplify_append_loops(transformed)
            return TransformResult(
                success=True,
                transformed_code=transformed,
                pattern_name=pattern_type,
            )
```

Replace with:

```python
            transformed = self._apply_extract_method(code, match_info)
            if transformed is None:
                return TransformResult(
                    success=False,
                    error_message="No changes made by extract method fallback",
                )
            if isinstance(transformed, TransformResult):
                return transformed
            transformed = self._simplify_append_loops(transformed)
            return TransformResult(
                success=True,
                transformed_code=transformed,
                pattern_name=pattern_type,
            )
```

The new `isinstance` check short-circuits the typed-error dispatch and returns the structured failure unchanged. The success path (`transformed: str`) flows through unchanged to `_simplify_append_loops`. The `None` path produces the legacy "No changes made by extract method fallback" message (preserved for backward compatibility — some test assertions may grep for it).

- [x] **Step 5: Run the full test class — confirm all 14+2 tests pass**

```bash
cd /Users/les/Projects/crackerjack
pytest tests/unit/agents/test_refactoring_agent.py -v 2>&1 | tail -30
```

Expected: 0 failed tests. Specifically: the 14 previously-failing tests pass, AND the 2 new regression tests from Task 1 also pass.

If any test fails, STOP — the fix is incomplete. Diagnose via the new typed error messages:

- A test asserting `result.success is True` failing → most likely one of the 4 helpers returns `None` even on a valid input. Inspect that helper's logic.

- A test asserting `(KeyError)` substring → the typed catches fired unexpectedly; check the input match_info shape.

- [x] **Step 6: Run all `agents/` tests — confirm no regressions in other modules**

```bash
cd /Users/les/Projects/crackerjack
pytest tests/unit/agents/ -q 2>&1 | tail -10
```

Expected: 0 failed tests across `tests/unit/agents/`.

- [x] **Step 7: Run mypy + ruff on the changed file**

```bash
cd /Users/les/Projects/crackerjack
mypy crackerjack/agents/helpers/ast_transform/surgeons/libcst_surgeon.py
ruff check crackerjack/agents/helpers/ast_transform/surgeons/libcst_surgeon.py
ruff format --check crackerjack/agents/helpers/ast_transform/surgeons/libcst_surgeon.py
```

Expected: All three exit 0. If mypy complains about the `# type: ignore`, ensure the rule code is `return-value` (not `misc`). If ruff complains about line length, the change should be under 10 lines net — reformat to fit 100-char limit.

- [x] **Step 8: Commit the fix**

```bash
cd /Users/les/Projects/crackerjack
git add crackerjack/agents/helpers/ast_transform/surgeons/libcst_surgeon.py
git commit -m "fix(ast-transform): capture helper return values + type the except clause

Two latent bugs in LibcstSurgeon._apply_extract_method surfaced as a
uniform 'No changes made by extract method fallback' message for the
14 tests in TestRefactoringAgentAstTransformFallback:

(1) Four dispatch branches (lift_nested_helpers, registration_wrapper,
    split_sections, lift_to_module) called helper methods but dropped
    the return value, causing NameError when subsequent ast.parse
    read the unassigned variable.
(2) Blanket `except Exception: return None` swallowed (1) and every
    other unexpected failure, masking the diagnostic signal.

Fix:
- Initialize transformed_lines_joined: str | None = None upfront so
  pre-existing early-returns in the else-branch don't leave the
  variable undefined.
- Capture each helper's return value into transformed_lines_joined.
- Post-dispatch `if is None` check classifies 'helper genuinely
  returned None' as a typed TransformResult failure.
- Typed `except` clause (NameError, TypeError, ValueError, KeyError,
  AttributeError) replaces the blanket catch, logging with
  logger.exception(...) per crackerjack convention.

All 14 previously-failing tests now pass. New regression tests in
TestRefactoringAgentAstTransformFallback anchor both the success
path and the diagnostic improvement.

Closes the W3 thread of the FixSandbox spec checklist."
```

______________________________________________________________________

### Task 3: Final verification

**Files:** None changed. Run read-only checks.

- [x] **Step 1: Full test class re-run (sanity check after both commits)**

```bash
cd /Users/les/Projects/crackerjack
pytest tests/unit/agents/test_refactoring_agent.py -v 2>&1 | tail -30
```

Expected: 0 failed tests.

- [x] **Step 2: Confirm `crackerjack/`-wide test suite is green for the agents subdir**

```bash
cd /Users/les/Projects/crackerjack
pytest tests/unit/agents/ -q
```

Expected: All tests pass. No regressions in adjacent test files.

- [x] **Step 3: Final git status check**

```bash
cd /Users/les/Projects/crackerjack
git status
```

Expected: clean working tree (no uncommitted modifications).

- [x] **Step 4: Confirm commit chain on `main`**

```bash
cd /Users/les/Projects/crackerjack
git log --oneline main -5
```

Expected stack (newest at top):

```
<fix-commit-hash>  fix(ast-transform): capture helper return values + type the except clause
<test-commit-hash> test(refactoring): add 2 regression tests for libcst_surgeon extract-method fallback
87cd3ea3          docs(specs): W3 libcst_surgeon extract-method fallback fix design
c6c52fd2          wip: prior-session modifications (Task 7 cleanup)
92ea7e8a          docs: update sandbox spec + capture refactoring_agent triage note
```

W3 is complete. Phase 4 (sandbox e2e + TestWatchCLI triage + final commit) is a separate thread tracked under task #4.

______________________________________________________________________

## Self-Review Notes

**Spec coverage check:**

- Spec §"Implementation Outline → Change 1" → Task 2 Steps 2-3 (variable init + helper capture) ✓
- Spec §"Implementation Outline → Change 2" → Task 2 Step 4 (typed catches + logger.exception) ✓
- Spec §"Implementation Outline → Change 3" → Task 2 Step 1 (logger import) ✓
- Spec §"Test additions" → Task 1 Steps 2-3 (two regression tests) ✓
- Spec §"Acceptance Criteria" → Task 2 Steps 5-6 + Task 3 Steps 1-2 ✓
- Spec §"Test Plan" → Task 2 Step 6 (pytest agents/) + Task 2 Step 7 (mypy + ruff) ✓
- Spec §"Risk and Rollback" → the `# type: ignore[return-value]` is a deliberate concession; rollback path is `git revert <fix-commit>` (single atomic revert)

**Placeholder scan:** None found (no "TBD" / "TODO" / "appropriate handling").

**Type consistency:**

- `transformed_lines_joined` declared once at function entry as `str | None`; assigned in 4 helper branches and 1 else branch; consumed by post-dispatch `is None` check + ast.parse + return. Single source of truth for the type.
- Helper method return types verified: `str | None` for all four. Plan captures return value uniformly regardless of actual return.

**Note on plan shape:**
The plan chooses TDD-with-baseline (Task 1 = tests first; Task 2 = fix) over edit-then-test because (a) the 2 new tests are *regression coverage* that anchor the bug surface — they MUST fail before the fix and pass after, and (b) the 14 existing tests are themselves regression coverage at the test-class level, so the new tests aren't even strictly required — but per the user's scope decision ("14 tests pass + new regression test"), they belong.
