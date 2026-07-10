# Triage Note — refactoring_agent.py AST fallback tests

**Date**: 2026-07-10
**Test file**: `tests/unit/agents/test_refactoring_agent.py`
**Status**: 14 tests failing. Pre-existing (unrelated to the FixSandbox SDD).
**Scope**: likely needs its own brainstorming + plan before code changes.

## Failing tests (14)

All in `TestRefactoringAgentAstTransformFallback` (lines 677-1782) except:
`TestRefactoringAgentThreeTierFallback::test_three_tier_full_analysis_uses_ast_fallback`.

```
TestRefactoringAgentAstTransformFallback::test_registration_wrapper_pattern_lifts_to_module_helper
TestRefactoringAgentAstTransformFallback::test_report_sections_pattern_lifts_to_top_level_helpers
TestRefactoringAgentAstTransformFallback::test_extract_method_renames_colliding_helper_name
TestRefactoringAgentAstTransformFallback::test_extract_method_lifts_nested_helpers_to_module
TestRefactoringAgentAstTransformFallback::test_extract_method_lifts_nested_helpers_imports_path
TestRefactoringAgentAstTransformFallback::test_extract_method_lifts_nested_helpers_reflows_long_joined_strings
TestRefactoringAgentAstTransformFallback::test_metrics_summary_pattern_splits_metric_loops
TestRefactoringAgentAstTransformFallback::test_validation_sections_pattern_splits_guarded_validation_blocks
TestRefactoringAgentAstTransformFallback::test_extract_method_merges_adjacent_section_starts
TestRefactoringAgentAstTransformFallback::test_class_method_extract_method_lifts_to_module_helper
TestRefactoringAgentAstTransformFallback::test_async_class_method_extract_method_lifts_to_module_helper
TestRefactoringAgentAstTransformFallback::test_execute_fix_plan_applies_ast_transform_as_full_file_replacement
TestRefactoringAgentAstTransformFallback::test_execute_fix_plan_reports_ast_transform_write_failure
TestRefactoringAgentThreeTierFallback::test_three_tier_full_analysis_uses_ast_fallback
```

## Pattern

All failures share this `TransformResult` shape:

```
result.success is False
result.error_message == "No changes made by extract method fallback"
```

So `ExtractMethodPattern.match(...)` either returns `None` or returns a
match whose `type` is not one of the expected values
(`{"extract_method", "split_sections"}`).

## Likely root cause

`ExtractMethodPattern._find_comment_sections(...)` finds comment-delimited
sections inside a function body. The pattern then matches against
those sections. Tests with `assert len(sections) >= 2` apparently do
pass that gate; the issue is downstream — `pattern.match(...)` either
returns `None` or returns a match whose `match_info["type"]` is one of
the failing values not in the `{"extract_method", "split_sections"}`
allowlist.

Speculative causes (verify before patching):

1. The pattern's heuristic for "this section is just a comment
   annotation" may have shifted; new code might include more
   inline-tokens that push sections past a line-count threshold.
2. `LibcstSurgeon.apply(...)` may be erroring on imports — the test
   `test_extract_method_lifts_nested_helpers_imports_path` suggests
   there's a known path that imports get mishandled.

## What doesn't fix it

Patching individual tests to widen the assertion surface (e.g.
`assert result.success is False or result.success is True`) — that
defeats the test. The tests are the spec; the code is what's broken.

## Recommended next steps (separate session)

1. Read `crackerjack/agents/refactoring_agent.py` — find
   `ExtractMethodPattern` and `LibcstSurgeon`. Likely 600-900 LOC of
   AST/cst logic.
2. Pick ONE failing test (recommend
   `test_extract_method_merges_adjacent_section_starts` as the
   simplest input) and bisect: instrument
   `ExtractMethodPattern.match(...)` with debug print of `match_info`
   on each case.
3. Decide whether the bug is in pattern detection or surgeon
   application. Likely **detection** — the "lifts" tests all show
   `success=False`, never a partial transform.
4. Likely fix is small (10-30 LOC) once the root cause is clear.
   Reach for plan-then-execute because the test surface is large.

## Why deferred

Out of session scope: W1 (CLI wiring) and W2 (IndentationError repair)
were straightforward and completed in this session. W3 needs dedicated
focus (could be 30-90 min) and a fresh context to avoid chasing
incidental findings.
