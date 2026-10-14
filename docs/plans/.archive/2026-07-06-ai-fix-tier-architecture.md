---
status: shipped
role: implementation
topic: lifecycle
date: 2026-07-17
last_reviewed: 2026-07-17
superseded_by: null
blocks_on: []
---

# AI-Fix Tier Architecture

**Status:** shipped, historical <!-- legacy status — see YAML frontmatter -->
**Date:** 2026-07-06
**Owner:** crackerjack team

**Note:** Promoted 2026-07-15 after drift-sync verified all items shipped in versions 0.68.0-0.68.3.

## Problem

`crackerjack ai-fix` currently auto-fixes ~30% of ty errors. The remaining 70%
break down into three buckets with very different cost/benefit profiles:

- **Mechanically-fixable** — pattern matches a deterministic rewrite.
  Current tooling covers 2 codes (`unused-type-ignore-comment`,
  `redundant-cast`).
- **Reasoning-required** — needs narrowing, isinstance checks, signature
  design. Routed to `TypeErrorSpecialistAgent` (one-shot LLM).
- **Design-required** — method override signatures, abstract-method bodies,
  ambiguous design choices. Human review queue.

Real measurement on `tests/` after this PR: **88 errors in tier 1** (today),
**654 in tier 3** (needs new infrastructure), **8 in tier 4** (human).

## Goal

Push auto-fix coverage from ~30% to ~85-90% by:

1. **Expanding tier 1** with deterministic narrowers and import resolvers.
1. **Adding tier 3** — spawn full Claude/Qwen CLI sessions with the actual
   Read/Edit/Bash toolset for the long tail of narrowing/typing work.
1. **Capturing every tier-3 success as a Session-Buddy skill** so the
   100th occurrence of the same shape replays mechanically (zero LLM cost).

## Tier definitions

| Tier | Mechanism | Latency | Cost | Example fix |
|---|---|---|---|---|
| 1 | Mechanical (regex/AST) | \<1ms / fix | $0 | `import time` (ty_imports) |
| 2 | One-shot LLM | ~2s / fix | ~$0.01 | `if x is None: return` |
| 3 | Iterative CLI session | ~30-60s / fix | ~$0.50 | complex union narrowing |
| 4 | Human review | n/a | n/a | signature drift, abstract bodies |

## Implementation status

### Shipped (this PR)

- **`crackerjack/tools/ty_imports.py`** — resolves `unresolved-reference` for
  stdlib modules and top-level stdlib sub-names (e.g. `Path` → `pathlib`).
  Inserts into the file's import block, idempotent.
- **`crackerjack/tools/ty_classify.py`** — pre-fix tier classification.
  Single source of truth for the `code → tier` mapping. Produces a
  report that can drive the dashboard's "coverage today" widget.
- **Tests** — 20 + 13 unit tests, mirroring `ty_cleanup.py`'s pattern.

### Stubbed / next

- **`crackerjack/tools/ty_narrow.py`** — None-narrowing helper for
  `unsupported-operator` and `not-subscriptable` shapes where a
  one-line guard (`assert x is not None` or `if x is None: return`)
  resolves the error. Estimated 30-50% of cat 1 / 4 / 5 in the
  survey.

- **`crackerjack/agents/iterative_fix_agent.py`** — tier-3 dispatch
  agent. Architecture:

  ```python
  class IterativeFixAgent(SubAgent):
      """Tier-3 ai-fix: spawn full CLI sessions via worker pool."""

      async def fix_file(self, file_path, errors):
          sig = signature(errors)
          if skill := self.skill_store.find(sig):
              return await self.apply_skill(file_path, skill)  # fast replay
          result = await self.pool.dispatch(
              prompt=build_prompt(file_path, errors),
              tools=["Read", "Edit", "Bash", "Grep"],
              timeout=600,
              selector="least_loaded",
          )
          if result.success and await self.validate_ty(file_path):
              await self.skill_store.distill(sig, result.diff)
          return result
  ```

  Wiring lives in `crackerjack/agents/fixer_coordinator.py`:
  add `self._iterative_agent = IterativeFixAgent(...)` and route
  to it from `_route_fix` after tier 1+2.

- **Skill store** — Session-Buddy's `distill_skills_now` is the right
  primitive. Signature = hash of `(error_codes ∪ normalized_messages)`
  so the same PATTERN reuses the same skill, regardless of file path
  or specific identifier. Initial `evidence_threshold=3` to avoid
  capturing one-off fixes as patterns.

## Tier-3 dispatch: Mahavishnu + Session-Buddy integration

The tier-3 agent's `WorkerPool` should be:

- **Mahavishnu pool** (preferred) — `pool_route_execute` already
  dispatches to workers with full Read/Edit/Bash toolset. Use
  `pool_selector="least_loaded"`.
- **Session-Buddy pool** (alternative) — delegates to a remote
  Session-Buddy instance with 3 workers each. Useful for
  cross-server scaling.
- **Local subprocess** (fallback when neither is available) —
  `subprocess.run(["claude", "--print", ...])` still gives a full
  toolset, just no orchestration.

The `SkillStore` should be:

- **Session-Buddy** (preferred) — `distill_skills_now` + `find_skill`.
- **In-memory dict** (fallback) — `dict[signature, dict]` keyed by
  signature. Works for one ai-fix run; no cross-run persistence.

Both fallbacks are protocol-based (`WorkerPool` and `SkillStore`),
so swapping implementations is a constructor change, not a code change.

## Validation

- Tier 1 + 2 fixes are validated by the existing
  `FixerCoordinator._validate_type_change` (project-wide `ty check`
  post-edit).
- Tier 3 fixes MUST be validated by the same path — the iterative
  agent loops "edit → ty check" internally; the coordinator's
  post-fix validation is a final safety net.

## Cost model

Assuming ~3,300 total ty errors project-wide and the breakdown from
this PR's classifier output:

| Tier | Count | Per-fix cost | Total |
|---|---|---|---|
| 1 | ~400 (12%) | $0 | $0 |
| 2 | ~440 (13%) | $0.01 | $4.40 |
| 3 | ~2,440 (74%) | $0.50 | $1,220 |
| 4 | ~20 (1%) | n/a | n/a |

Initial run: ~$1,225. After skill distillation compounds (3-4 weeks
of normal development), most tier-3 work is replayed at tier-1 cost:
**steady-state run ~$50-200** instead of $1,200+.

## Why this matters

The Mahavishnu/Session-Buddy ecosystem already has the right primitives:

- **Mahavishnu** dispatches full CLI sessions (`worker_type="terminal-claude"`).
- **Session-Buddy** captures and replays successful patterns
  (`distill_skills_now`, `search_distilled_skills`).
- **Crackerjack** orchestrates quality gates.

What's been missing is the wiring — there's no agent that
opportunistically *uses* Mahavishnu/Session-Buddy for the long tail
of mechanical type fixes. This plan adds that wiring without
disrupting the existing `TypeErrorSpecialistAgent` path.

## Acceptance criteria

1. **Coverage today:** classifier reports tier 1 ≥ 12% (currently 12%).
1. **Coverage with tier 3:** classifier reports tier 1+2+3 ≥ 95%.
1. **Skill capture:** every tier-3 success appears in
   `Session-Buddy.search_distilled_skills` within 24h.
1. **Steady-state cost:** second-run cost (with skills replayed) is
   ≤20% of first-run cost.
1. **No regressions:** existing `crackerjack run` continues to pass
   the full test suite.

## Open questions

- Do we ship tier 3 in a follow-up PR, or include it here?
- Is the `signature()` hash robust enough to avoid capturing
  bad patterns as skills? (Initial `evidence_threshold=3` mitigates
  but doesn't eliminate.)
- Should the iterative agent be allowed to *modify function
  signatures* (cat 8 in the survey), or always defer to human?
