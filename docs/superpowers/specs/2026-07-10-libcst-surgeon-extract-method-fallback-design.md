# LibcstSurgeon Extract-Method Fallback Fix — Design

**Date**: 2026-07-10
**Status**: Draft — awaiting user review
**Author**: Claude (brainstorming session)
**Related**: triage note `docs/superpowers/triage/2026-07-10-refactoring-agent-ast-fallback.md`; WIP commit `c6c52fd2` (prior-session cleanup); upstream commit `92ea7e8a` (sandbox spec + triage capture).

## Problem

14 tests in `tests/unit/agents/test_refactoring_agent.py` fail with a uniform error signature:

```
result.success is False
result.error_message == "No changes made by extract method fallback"
```

Affected tests (all in `TestRefactoringAgentAstTransformFallback`, plus one in `TestRefactoringAgentThreeTierFallback`):

- `test_extract_method_merges_adjacent_section_starts`
- `test_extract_method_renames_colliding_helper_name`
- `test_extract_method_lifts_nested_helpers_to_module`
- `test_extract_method_lifts_nested_helpers_imports_path`
- `test_extract_method_lifts_nested_helpers_reflows_long_joined_strings`
- `test_metrics_summary_pattern_splits_metric_loops`
- `test_validation_sections_pattern_splits_guarded_validation_blocks`
- `test_registration_wrapper_pattern_lifts_to_module_helper`
- `test_report_sections_pattern_lifts_to_top_level_helpers`
- `test_class_method_extract_method_lifts_to_module_helper`
- `test_async_class_method_extract_method_lifts_to_module_helper`
- `test_execute_fix_plan_applies_ast_transform_as_full_file_replacement`
- `test_execute_fix_plan_reports_ast_transform_write_failure`
- `TestRefactoringAgentThreeTierFallback::test_three_tier_full_analysis_uses_ast_fallback`

These were already failing before this session. The prior-session triage note (`docs/superpowers/triage/2026-07-10-refactoring-agent-ast-fallback.md`) hypothesized two root causes — both of which the present brainstorming session found to be **incorrect approximations**:

| Triage hypothesis | Actual finding |
|---|---|
| `ExtractMethodPattern.match(...)` returns wrong `match_info["type"]` | `match.match_info["type"] in {"extract_method", "split_sections"}` is correct — assertions pass |
| `LibcstSurgeon.apply(...)` errors on imports | One specific test exercises import handling; the actual error is generic |

**Real root cause (discovered during brainstorming):**
- `LibcstSurgeon._apply_extract_method` has 5 dispatch branches.
- The `else` branch (plain `extract_method`) builds `transformed_lines_joined` correctly.
- The other 4 branches (`lift_nested_helpers`, `registration_wrapper`, `split_sections`, `lift_to_module`) call helper methods but **drop the return value**.
- After the dispatch, line 499 (`ast.parse(transformed_lines_joined)`) raises `NameError` for any branch that didn't run the `else` block.
- The blanket `except Exception: return None` at line 501 swallows the `NameError` (and every other unexpected failure) and reports the same uniform `"No changes made by extract method fallback"` message.
- Result: every test that takes a non-`extract_method` pattern branch fails identically, regardless of whether the helper method itself produced valid output.

Two latent bugs, one symptom:

1. **Helper return values are dropped** (4 of 5 dispatch branches).
2. **Blanket except hides diagnostics** (1 catch in `_apply_extract_method`).

## Goal

Make all 14 tests pass with a minimum-blast-radius fix. Improve diagnostic fidelity so future regressions in this code path surface a useful error rather than the generic "no changes" message.

Out of scope:

- Refactoring `ExtractMethodPattern._find_comment_sections` heuristics.
- Adding new patterns or refactoring the AST transform architecture.
- Touching other surgeons or pattern classes.
- Changing public APIs (`TransformResult`, `LibcstSurgeon.can_handle`, `LibcstSurgeon.apply`).
- Optimizing for performance.

## Design Decisions (from brainstorming)

1. **Scope = minimum** — 4-8 line code change in one file, plus 2 new regression tests. No architectural refactor.
2. **Approach = B (capture return values + typed exception logging)** — addresses both latent bugs within the minimum scope. Honest about WHY each branch failed; future regressions become diagnosable.
3. **Helper method return contracts assumed `str | None`** — this is the most common Python convention for `transform`-named methods that take source code. If any helper returns `None` for success, the change captures `""` instead, making the line-499 `ast.parse("")` failure explicit (no longer `NameError`).
4. **No new files** — single-file change keeps review small and rollback easy.
5. **Backward compatible `TransformResult` shape** — same fields, same semantics. `error_message` may contain `(KeyError): ...` etc. instead of free-form strings, but callers that pattern-match on substring still work.

## Implementation Outline

### File 1: `crackerjack/agents/helpers/ast_transform/surgeons/libcst_surgeon.py`

**Change 1 — Capture helper return values (lines 439-457):**

The dispatch must initialize `transformed_lines_joined = None` *before* the `if/elif` chain so the two pre-existing early-returns inside the `extract_method` branch (which skip assignment) cannot leave the variable undefined when control reaches line 499.

```python
transformed_lines_joined: str | None = None

if match_info.get("type") == "lift_nested_helpers":
    transformed_lines_joined = self._lift_nested_helpers_to_module(
        code, func_node, helper_name,
    )
elif match_info.get("registration_wrapper"):
    transformed_lines_joined = self._lift_registration_wrapper_to_module(
        code, func_node,
    )
elif match_info.get("type") == "split_sections":
    transformed_lines_joined = self._apply_split_sections(
        code, func_node, match_info,
    )
elif match_info.get("lift_to_module"):
    transformed_lines_joined = self._lift_method_to_module(
        code, func_node, helper_name,
    )
elif match_info.get("type") == "extract_method":
    # existing else-block body, retained verbatim.
    # NOTE: this branch contains two `return None` early-exits
    # (block boundary validation, empty dedented_block). When those
    # fire, `transformed_lines_joined` stays None and we surface a
    # typed "non-extractable" error below instead of the old blanket
    # `No changes made` swallow.
    ...
    transformed_lines_joined = ...
else:
    return TransformResult(
        success=False,
        error_message=f"Unknown pattern type: {pattern_type}",
    )

if transformed_lines_joined is None:
    return TransformResult(
        success=False,
        error_message=f"{pattern_info_type}: helper produced no transformed code",
    )

ast.parse(transformed_lines_joined)
return transformed_lines_joined  # type: ignore[return-value]
```

(`extract_method` is now explicit rather than the implicit `else` — same behavior, better diagnostic contract.)

**Change 2 — Replace blanket except (line 501) with typed catches + logging:**

```python
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

This uses the crackerjack `logger.exception(...)` convention (per `CLAUDE.md`) and surfaces actionable signal instead of the generic "no changes" message.

**Change 3 — Add module-level logger import if not already present** (verify at top of file).

### File 2: `tests/unit/agents/test_refactoring_agent.py`

Two new tests added to `TestRefactoringAgentAstTransformFallback`:

- `test_apply_extract_method_dispatches_split_sections` — Construct `match.match_info["type"] = "split_sections"` with a known-good async AST fixture. Assert `result.success is True`. This is the *minimum regression coverage* for the dropped-return-value bug.

- `test_apply_extract_method_reports_keyerror_with_pattern_context` — Construct `match_info` that triggers `KeyError` (e.g., omit a required key). Assert `result.success is False` and `error_message` contains `(KeyError)`. This is the *minimum regression coverage* for the diagnostic-improvement change.

Both tests will use the same fixture pattern as the existing `test_extract_method_merges_adjacent_section_starts` to keep the surface area small.

## Acceptance Criteria

- All 14 currently-failing tests pass.
- All 2 new regression tests pass.
- No previously-passing test in the file regresses.
- `_apply_extract_method` produces a useful `error_message` (containing the exception type) when its helper methods raise an unexpected exception, instead of the uniform `"No changes made by extract method fallback"` text.
- The change is contained to `libcst_surgeon.py` and `test_refactoring_agent.py`.

## Test Plan

1. Run the full `pytest tests/unit/agents/test_refactoring_agent.py -v` suite before and after the change. Expected: 14 fewer failures + 2 new passes.
2. Run `pytest tests/unit/agents/` to confirm no other module regresses.
3. Run `mypy crackerjack/agents/helpers/ast_transform/surgeons/libcst_surgeon.py` and `ruff check` against the changed file.

The FixSandbox e2e smoke check is **out of scope for this fix** and is tracked separately under Phase 4.

## Risk and Rollback

**Risk:**
- If any of the 4 helper methods (`_lift_nested_helpers_to_module`, `_lift_registration_wrapper_to_module`, `_apply_split_sections`, `_lift_method_to_module`) returns `None` on a successful transform, our fix would mis-classify those as failures. The change adds an explicit `is None` check with a clear error message, so such a case would surface as `"<pattern>: helper returned None"` instead of crashing or silently producing no output.
- If callers downstream of `apply()` parse `error_message` for specific substrings (e.g., `"No changes made by extract method fallback"`), the new typed messages break them. Mitigation: `crackerjack grep` for that exact substring before merging.

**Rollback:** Single `git revert` of the implementation commit returns the system to the current state. WIP commit `c6c52fd2` is independent and unaffected.
