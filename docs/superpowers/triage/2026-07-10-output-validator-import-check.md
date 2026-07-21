______________________________________________________________________

## status: active role: implementation date: 2026-07-17 last_reviewed: 2026-07-17 superseded_by: null blocks_on: [] topic: lifecycle

# Triage Note — OutputValidator.import_check None crash (Cluster 1)

**Date**: 2026-07-10
**Status**: 1 root cause identified via console log; recon in progress to confirm exact code path. <!-- legacy status — see YAML frontmatter -->
**Severity**: High — every fixer attempt that touches a file validated by `import_check` is currently guaranteed to fail regardless of fix correctness. The "no-progress" / "no-op" detectors downstream cannot distinguish "fixer is wrong" from "validator is broken."
**Scope**: Likely 1-2 files. Possibly ≤30 lines of production code + 1 regression test.

## Symptom (verbatim from latest `crackerjack run -v --ai-fix` output)

```
OutputValidator: import_check failed for crackerjack/tools/ty_imports.py:
  AttributeError: 'NoneType' object has no attribute '__dict__'.
  Did you mean: '__dir__'?
⚠️ Output validation failed for crackerjack/tools/ty_imports.py …
✗ [FixerCoordinator] No progress — regenerated plan is identical to the failed one
  (crackerjack/tools/ty_imports.py:220)
```

Same pattern repeats for `crackerjack/tools/ty_narrow.py`, `crackerjack/tools/ty_classify.py`, `crackerjack/core/autofix_coordinator.py` (multiple sites).

## Why this is Cluster 1 (not the other failure clusters)

The user's earlier 4-cluster diagnosis of the broken AI-fix loop included 3 model-quality clusters (`from __future__` placement, invalid Python generation, type/lint drift). **Cluster 1 is the only one with a clear crackerjack-side bug** — the others might be AI quality or context-window issues, but Cluster 1 is `AttributeError: 'NoneType' object has no attribute '__dict__'` which is unambiguously a code path where something returned `None` and the caller tried to read its `.__dict__`.

## Pattern (from the log)

The error originates from `OutputValidator.import_check` (crackerjack-side validator). Either:

1. `import_check` itself returns `None` somewhere and a downstream caller does `result.__dict__[...]`, or
1. `import_check` calls a helper that returns `None`, and `import_check` then tries to read `.__dict__` on it.

Both shapes produce the same error string; the recon agent is locating the exact line.

## Fix shape (high confidence, subject to recon)

Two candidate shapes:

**Shape A — Add a None guard + return early.** If `import_check` calls a helper that returns `None`, guard the call:

```python
result = self._import_helper(...)
if result is None:
    return ValidationResult.skipped("import_check helper returned None")
```

This is the minimal, safe fix.

**Shape B — Fix the helper that returns None.** If the helper has a bug where it returns `None` instead of a `dict`/object, fix the helper to always return a structured result.

The right answer depends on which helper is the source of the None — recon will tell us.

## Why "skip" instead of "fail"?

`OutputValidator` is a gate, not a fix. If `import_check` can't run (helper missing, file unparsable, environment issue), the right behavior is to **report the validator couldn't run** and let the broader gate decide. Crashing the validator means **every fixer attempt against files using that validator fails** — exactly what we're seeing.

## Production code surface (pending recon)

- `OutputValidator` class — likely `crackerjack/agents/output_validator.py` or similar.
- `OutputValidator.import_check` method — the failing entry point.
- Helper(s) called by `import_check` — one of these returns `None`.

## Out of scope (will be triaged separately if/when prioritized)

- Cluster 2: `from __future__` placement bug in fixer output
- Cluster 3: Fixer regenerates invalid Python
- Cluster 4: Type/lint drift after fix
- 164 pre-existing modified files in working tree from earlier auto-formatting
- Pre-existing crackerjack gate failures (53 ty, 23 refurb, 1 pyscn) elsewhere

## Recommended next steps

1. **Recon** (in progress): find `OutputValidator`, find `import_check`, identify the line that returns `None`. Already dispatched.
1. **Brainstorming** — present 2-3 design alternatives (Shape A vs Shape B vs "skip + log" vs other).
1. **Spec** at `docs/superpowers/specs/2026-07-10-output-validator-import-check-design.md`.
1. **Plan + SDD execution** — likely 1 task: implement fix + regression test.
1. **Push** to `origin/main`.

## Effort estimate

XS — likely 1-2 files, ≤30 lines of production code, 1 regression test. The hard part is identifying which line is the source of the None; once that's known, the fix is mechanical.
