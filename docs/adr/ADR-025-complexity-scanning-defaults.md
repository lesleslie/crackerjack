---
status: active
role: canonical
topic: architecture
date: 2026-07-17
last_reviewed: 2026-07-17
superseded_by: null
blocks_on: []
---

# ADR-025: Complexity Scanning Defaults

## Status

**Accepted** — 2026-06-28

## Context

crackerjack runs **three independent complexity scanners** as part of the comprehensive
stage: `complexipy`, `pyscn`, and ruff's `mccabe` lint. Until 2026-06-27 these had drifted
apart:

| Tool | Where configured | Threshold before | Threshold now |
|------|------------------|------------------|---------------|
| ruff mccabe | `pyproject.toml:164` (`[tool.ruff.lint.mccabe].max-complexity`) | 25 | 25 |
| complexipy | `pyproject.toml:409` (`[tool.complexipy].max_complexity`) **and** `crackerjack/config/tool_commands.py:236` (CLI flag `--max-complexity-allowed`) | 15 | 25 |
| pyscn | `crackerjack/config/tool_commands.py:282` (CLI flag `--max-complexity`) | 15 | 15 |

Mccabe and complexipy now agree on 25. pyscn remains at 15 — that's deliberate (see
Decision).

A separate but related issue surfaced: `crackerjack/executors/individual_hook_executor.py:490`
hardcoded `issues_count = 1 if status == "failed" else 0`, which made every failed hook
report "1 issue" regardless of how many real violations existed. complexipy alone has
**125 functions over complexity 15**; without the threshold raise the run summary was
both wrong and misleading. Fixed by reading `progress.errors_found` (the parser's real
count) instead.

## Decision

**Adopt 25 as the unified cyclomatic-complexity ceiling across all three scanners.**
15 remains the pyscn floor because pyscn reports clone duplication and is used as the
**strict** backend in CI.

The thresholds were calibrated against the following industry references:

| Reference | Default | Recommended | Notes |
|-----------|---------|-------------|-------|
| mccabe (Python original) | 10 | 15 | Pylint era default |
| ruff mccabe | 10 | 15-20 | Most projects override to 15 |
| SonarQube | 15 | 15 | Cognitive complexity, separate from cyclomatic |
| pylint `max-branches` | 12 | 12-15 | Very strict |
| radon CC | 20 (grade C→D boundary) | 20 | Most-used Python tool, grade-C ceiling |
| lizard | 15 | 15-20 | Multi-language |
| SonarCloud default per-file-method | — | 20 | Industry typical |

crackerjack's **25** sits at the high end of "industry typical" for cyclomatic
complexity but is defensible because:

1. crackerjack's own agents (ArchitectAgent, PlanningAgent) are AST/transform
   engines that *legitimately* run hot in some helpers (e.g.
   `LibcstSurgeon::_apply_extract_method` is complexity 29 by necessity).
1. The complexity scanners live in the **comprehensive stage** (≈10 min total
   budget), not in pre-commit. False positives on borderline functions waste
   developer attention; the strict ceiling is enforced by `pyscn` at 15 in CI
   for the most common patterns (clone detection).
1. The crackerjack-runner reports `cognitive` complexity (complexipy measures
   this, not raw cyclomatic) — cognitive numbers run higher than cyclomatic for
   the same code, so a 25 cognitive ceiling ≈ 18-20 cyclomatic.

## Industry Defaults Reference

For projects that prefer stricter:

| Profile | Ruff mccabe | Complexipy | pyscn | Use case |
|---------|-------------|------------|-------|----------|
| Strict (legacy Python / pylint-style) | 10 | 10 | 10 | Pre-2018 code, libraries with high correctness stakes |
| Standard (SonarQube default) | 15 | 15 | 15 | Most Python projects |
| **crackerjack default** | **25** | **25** | **15** | AST/transform-heavy codebases |
| Relaxed (legacy refactors in-progress) | 30 | 30 | 20 | Migration projects |

crackerjack's setting is in the "Standard" tier for pyscn and "above-Standard"
for ruff/complexipy. This is a *deliberate* trade-off: catch the egregious
stuff (cognitive > 25 → almost certainly needs extraction) without drowning
the signal in borderline functions that the AI autofix already handles.

## Consequences

**Positive**

- The three scanners no longer disagree. Before this change, a function could
  pass mccabe (≤25) but fail complexipy (≤15) — confusing for contributors.
- The hook result's `issues_count` now reflects reality. Sift investigations,
  Akosha signals, and the crackerjack dashboard all consume this field.
- The crackerjack-quality-scanners pool can quote a single number for SLA
  tracking.

**Negative**

- Functions with cognitive complexity 16-25 are *allowed* in the comprehensive
  stage. Refurb's `FURB101` (extract-method) and `FURB102` (early-return)
  remain the structural nudge for those.
- A future "strict mode" feature flag would need to drop these to 15 across
  the board — that's the only meaningful override.

**Out of scope**

- `crackerjack/agents/helpers/ast_transform/` files have very high cognitive
  numbers and were deliberately excluded from `pymetrica` (2026-06-27 fix).
  These files also exceed the new threshold but are not blockable; they
  represent irreducible AST traversal cost.
- The cognitive-vs-cyclomatic confusion: complexipy reports cognitive, ruff
  reports cyclomatic. Same number means different things. A future ADR may
  recommend picking one. For now, we treat complexipy as authoritative.

## Verification

Run any of these to confirm the post-fix state:

```bash
# 1. Confirm the thresholds match
grep -n "max-complexity" pyproject.toml
grep -n "max-complexity-allowed" crackerjack/config/tool_commands.py
grep -n '"--max-complexity"' crackerjack/config/tool_commands.py

# 2. Confirm the count bug fix
grep -n "issues_count" crackerjack/executors/individual_hook_executor.py

# 3. Live run (should report real issue count, not always "1")
uv run crackerjack run -v -c 2>&1 | grep -E "(complexipy|Issues found)"
```

## Related

- Phase S fix (commit `a468b30b`): consolidation of hook lists; first time the
  three scanners were brought into agreement.
- ADR-024 (if it exists) — the `auto_run` field rename.
- The `pymetrica_timeout` raise (2026-06-27): also relaxed, for similar
  reason — crackerjack is AST-heavy and the strict-default timeout was
  unrealistic for the codebase.
