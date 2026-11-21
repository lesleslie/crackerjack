---
title: Remove the Dead AI-Fix Module Cluster from Crackerjack
description: "Delete `crackerjack/fixers/` (33 files, 26,665 lines), the five orphaned `crackerjack/tools/ty_*` modules, and 70 of the 72 unreachable methods in `crackerjack/core/autofix_coordinator.py` — the residue of the AI-fix stage that was deleted from production but left its skeleton behind. The one live remnant (JSONC comment stripping) is rehomed into a new `crackerjack/tools/jsonc.py`. Net: ~52,000 lines removed, no capability that currently runs is lost."
audience: crackerjack maintainer
created: 2026-11-13
status: shipped
role: implementation
topic: architecture
date: 2026-11-13
last_reviewed: 2026-11-13
superseded_by:
blocks_on: []
---

# Remove the Dead AI-Fix Module Cluster from Crackerjack

## Brief (intent-driven)

### Goal

Every module in the AI-fix cluster that no production code path reaches is
gone from the repo, and the one piece of that cluster that *is* still live
(JSONC comment stripping) moves to a module that owns it. The repo stops
carrying ~52,000 lines of code that only its own tests exercise.

### Constraints

1. **Nothing that currently runs may stop running.** The AI-fix *stage* was
   removed from production long ago; what is left is its skeleton. This plan
   removes the skeleton. It does not remove a working feature.
2. `crackerjack/fixers/` goes entirely — no stub package, no "future
   fixers" placeholder (YAGNI per the pre-1.0 policy; the same call the
   Zuban/Skylos removal made).
3. `crackerjack/tools/ty_imports.py`, `ty_classify.py`, `ty_cleanup.py`,
   `ty_narrow.py`, and `ty_audit.py` go. `ty_ignore_syntax.py` and
   `ty_ratchet.py` **stay** — they are live hook commands.
4. `crackerjack/core/ai_fix_sinks.py` **stays** — `crackerjack/cli/replay.py`
   imports `JsonlSink` and `runs_root` from it. `crackerjack/core/ai_fix_events.py`
   **stays** — `ai_fix_sinks` imports its event types at module level.
5. The JSONC stripper is rehomed as a **new** module rather than folded into
   `crackerjack/tools/format_json.py`. `format_json.py` parses strictly with
   `json.loads`; making it comment-tolerant would change the `format-json`
   hook's semantics, which is out of scope.
6. `crackerjack/agents/` goes too. Its one live export, the `AgentContext`
   dataclass, moves to `crackerjack/models/agent_context.py` — the layer
   that already owns `FixResult` and the Protocol definitions. The package
   README states the agent runtime was removed in the 2026-08-12 refactor
   (commit 907ab860); what is left is a stub for a package whose runtime
   is gone.
7. Pre-1.0 — direct merge to `main`, no PR.
8. The working tree carries uncommitted user work (the dependency sweep, a
   `.gitignore` change, a `ty.py` deletion). Commit with explicit
   pathspecs; never `git add -A`.

### Failure Conditions (verifier-only)

01. `crackerjack/fixers/` does not exist; `uv run python -c "import crackerjack.fixers"`
    raises `ModuleNotFoundError`.
02. `crackerjack/core/autofix_coordinator.py`, `crackerjack/core/preflight.py`,
    `crackerjack/core/ai_fix_event_bus.py`, `crackerjack/services/ai_fix_progress.py`
    do not exist. `crackerjack/models/fix_plan.py` **still exists** and is
    still exported from `crackerjack.models`.
03. `crackerjack/tools/ty_imports.py`, `ty_classify.py`, `ty_cleanup.py`,
    `ty_narrow.py`, `ty_audit.py` do not exist.
04. `crackerjack/agents/` does not exist; `crackerjack/models/agent_context.py`
    does, and exports `AgentContext`; `crackerjack/models/protocols.py`
    imports it from there.
05. `crackerjack/tools/ty_ignore_syntax.py` and `crackerjack/tools/ty_ratchet.py`
    still exist and are still registered as hook commands in
    `crackerjack/config/tool_commands.py`.
06. `crackerjack/core/ai_fix_sinks.py` still exists and still exports
    `JsonlSink` and `runs_root`; `crackerjack/cli/replay.py` still imports them.
07. `crackerjack/tools/jsonc.py` exists and exports the two strip functions.
08. `git grep -n "autofix_coordinator\|AutofixCoordinator" -- crackerjack/ scripts/`
    returns zero matches.
09. `git grep -n "crackerjack.fixers\|from .fixers\|from ..fixers" -- crackerjack/ scripts/`
    returns zero matches.
10. `scripts/validate_imports.py` no longer lists `crackerjack.core.autofix_coordinator`
    and still exits 0.
11. `pytest tests/` collects and runs without an import error; the pass/fail
    set is **identical** to the pre-change baseline (no new failures).
12. `crackerjack run -f` on the repo exits 0.

## Context

### The AI-fix stage was removed; its skeleton was not

`crackerjack/agents/` now contains only `base.py`, `helpers/`, and `README.md`
— the SubAgent implementations are gone. `crackerjack/fixers/__init__.py`
still describes itself as the extraction target for that removal:

> *"Framework-free deterministic fixers extracted from crackerjack.agents…
> see `docs/plans/2026-08-06-ai-fix-removal-extraction.md` for the plan."*

That plan does not exist in `docs/plans/` or `docs/plans/.archive/`. The
extraction target was built, never adopted, and left with **zero production
importers**.

### Dead module inventory (verified 2026-11-13)

Reachability was computed with an AST scan, not grep: a module referenced only
by other dead modules is dead.

| Module | Lines | Production importers | Verdict |
|---|---|---|---|
| `crackerjack/fixers/` (33 files) | 26,665 | none outside the package | **DEAD** |
| `crackerjack/core/autofix_coordinator.py` | 1,803 | 2 (both trivial — see below) | **96% DEAD** |
| `crackerjack/core/preflight.py` | 389 | `autofix_coordinator` only | **DEAD** |
| `crackerjack/services/ai_fix_progress.py` | 145 | `autofix_coordinator` only | **DEAD** |
| `crackerjack/models/fix_plan.py` | 78 | `autofix_coordinator` + `fixers/` + **`crackerjack/models/__init__.py`** | **KEEP** — public API (see below) |
| `crackerjack/core/ai_fix_event_bus.py` | 54 | `ai_fix_sinks.build_default_bus` + `preflight` | **DEAD** (cascade) |
| `crackerjack/tools/ty_audit.py` | 363 | none | **DEAD** |
| `crackerjack/tools/ty_classify.py` | 161 | none | **DEAD** |
| `crackerjack/tools/ty_cleanup.py` | 440 | `autofix_coordinator` only | **DEAD** |
| `crackerjack/tools/ty_imports.py` | 354 | none | **DEAD** |
| `crackerjack/tools/ty_narrow.py` | 281 | none | **DEAD** |

**Total production: 30,735 lines** (of which `models/fix_plan.py` is
reclassified as KEEP below).

### `crackerjack/models/fix_plan.py` stays

The dead-`fixers/` sweep would suggest deleting it, but
`crackerjack/models/__init__.py` re-exports `ChangeSpec`, `FixPlan`,
`create_change_spec`, and `create_fix_plan` in its `__all__`. That makes
them part of the published `crackerjack.models` surface.

The module is also generic rather than AI-fix-specific — a `FixPlan` is
"a validated set of changes to one file" with a risk level, which any
consumer could use — and it has its own test file
(`tests/models/test_fix_plan.py`). Its only *production* consumers were
the dead fixers, but a public export is not the same as dead code.

**Decision: keep `fix_plan.py` and leave `crackerjack/models/__init__.py`
untouched.** Removing four names from a published package's `__all__` is an
API break, and 78 lines is not worth it.

Test code that exists only to cover the above:

| Test | Lines |
|---|---|
| `tests/fixers/` (21 files) | 17,941 |
| `tests/tools/test_ty_audit.py` | 1,076 |
| `tests/tools/test_ty_cleanup.py` | 1,010 |
| `tests/tools/test_ty_narrow.py` | 497 |
| `tests/tools/test_ty_classify.py` | 171 |
| `tests/tools/test_ty_imports.py` | 274 |
| `tests/integration/test_tier_architecture_e2e.py` | 319 |
| `tests/test_autofix_coordinator.py` | 159 |

**Total tests: 21,447 lines.**

### `crackerjack/agents/` is a husk holding one dataclass

The package README says it plainly:

> *"The full AI-fix agent runtime was removed in the 2026-08-12 refactor
> (commit 907ab860) and replaced by the external Workflow tool loop at
> `.claude/workflows/ai-fix-loop.js`."*

What remains on disk:

```
crackerjack/agents/README.md                                     17 lines
crackerjack/agents/base.py                                        31 lines  (the only .py)
crackerjack/agents/helpers/refactoring/dead_code_detector.py.backup      309 lines
crackerjack/agents/helpers/refactoring/dead_code_detector.py.backup.json   1 line
```

`base.py` is a typed stub exporting one dataclass, `AgentContext`, plus a
re-export of `FixResult` that **nobody imports from here** (`protocols.py`
takes `FixResult` from `crackerjack.models.issues` directly).

`AgentContext` is used in exactly two places:

- `crackerjack/models/protocols.py:16` — a `TYPE_CHECKING` import, then
  six method signatures in `AgentDelegatorProtocol` (lines 944-976). **Live.**
- `crackerjack/core/autofix_coordinator.py:47` — also `TYPE_CHECKING`.
  **Dies with the coordinator.**

So the plan moves `AgentContext` to `crackerjack/models/agent_context.py`
and deletes the whole `agents/` package, including the two stale `.backup`
files and the README.

### The ty tools are not uniformly dead

| Module | How it is invoked | Verdict |
|---|---|---|
| `ty_ignore_syntax.py` | `crackerjack/config/tool_commands.py:221` (hook) | **LIVE** |
| `ty_ratchet.py` | `crackerjack/config/tool_commands.py:230` (hook) | **LIVE** |
| `ty_cleanup.py` | `autofix_coordinator.py:488` (`uv run python -m …`) | DEAD (caller dead) |
| `ty_imports.py` | none | DEAD |
| `ty_classify.py` | none | DEAD |
| `ty_narrow.py` | none | DEAD |
| `ty_audit.py` | none | DEAD |

**Capability note:** the "tier 1 mechanical" type-error auto-fix
(`ty_cleanup` → `ty_imports` → `ty_narrow`, classified by `ty_classify`)
has *no live entry point*. The live ty surface is `ty_ratchet` (reports
ty errors) and `ty_ignore_syntax` (validates `# ty: ignore` directives).
Deleting these removes a capability that already does not run — it does not
remove one that works.

### The live remnant in `autofix_coordinator.py`

Transitive reachability from the two external call sites leaves **3 of 72
methods** alive:

- `_strip_jsonc_comments_from_failed_json_files` — called from
  `crackerjack/core/phase_coordinator.py:482`
- `_strip_jsonc_comments` — called by the above
- `_get_uv_environment_paths` — **NOT actually live** (see below)

`_get_uv_environment_paths` was a false positive in the first scan: the
call site at `crackerjack/executors/hook_executor.py:2200` is
`self._get_uv_environment_paths()` on the **HookExecutor**, which has its
own near-identical copy at line 2204. The `autofix_coordinator` copy is a
duplicate whose only difference is an extra `shutil.rmtree()` of the cache
root. It is dead.

So the real live surface is **2 methods, ~60 lines**: strip JSONC comments
from `.json` files that the `format-json`/`check-json` hooks rejected, so
the phase can retry them.

Separately, the class's **public API has zero callers** —
`apply_autofix_for_hooks`, `apply_fast_stage_fixes`,
`apply_comprehensive_stage_fixes`, `run_fix_command`, `should_skip_autofix`,
`validate_fix_command`, `validate_hook_result` are all unreferenced outside
the class.

`crackerjack/core/phase_coordinator.py:181` assigns
`self._lazy_autofix = create_lazy_service(lambda: AutofixCoordinator(...), …)`
and **never reads it** — a dead field.

### Where the JSONC stripper goes

New module `crackerjack/tools/jsonc.py`, exporting:

```python
def strip_jsonc_comments(content: str) -> tuple[str, bool]:
    """Return (stripped_content, had_comments)."""

def strip_jsonc_comments_from_failed_json_files(root: Path) -> bool:
    """Strip JSONC comments from every tracked .json file. Returns success."""
```

`crackerjack/tools/` already holds the sibling JSON operations
(`check_json.py`, `format_json.py`), both of which import
`get_files_by_extension` from `._git_utils` — the same helper the current
implementation uses.

### The `ai_fix_sinks` cluster must be split, not deleted

```
crackerjack/cli/replay.py ──imports JsonlSink, runs_root──> crackerjack/core/ai_fix_sinks.py
                                                                       │ module-level
                                                                       ▼
                                                            crackerjack/core/ai_fix_events.py   [KEEP]
```

`ai_fix_sinks.build_default_bus()` lazily imports `ai_fix_event_bus`, and
its only caller is the dead `autofix_coordinator`. So `ai_fix_event_bus.py`
can go — but only after `build_default_bus` (and `LoggingSink`,
`MetricsSink`, `migrate_legacy_runs`, whose only callers it was) are
removed from `ai_fix_sinks.py`.

### Prior art

`docs/plans/2026-10-11-remove-zuban-skylos-lsp-from-crackerjack.md` — the
house format for a removal plan in this repo, and the precedent for
deleting a whole adapter package with no stub left behind.

## Approach

Five phases, ordered so the test suite breaks loudly the moment something
with an unaccounted-for dependent is touched.

### Phase 1 — Rehome the live JSONC remnant

**Files:**

- `crackerjack/tools/jsonc.py` — **new**. `strip_jsonc_comments()` and
  `strip_jsonc_comments_from_failed_json_files()`, moved verbatim from
  `AutofixCoordinator._strip_jsonc_comments` /
  `_strip_jsonc_comments_from_failed_json_files`. `redact_path` comes from
  `crackerjack/utils/path_redaction.py`; `get_files_by_extension` from
  `crackerjack/tools/_git_utils.py`.
- `crackerjack/core/phase_coordinator.py` — drop the
  `from crackerjack.core.autofix_coordinator import AutofixCoordinator`
  at line 24 and the local import at line 457; call the new module from
  `_prepare_jsonc_files_before_retry`.
- `crackerjack/tools/jsonc_test.py` → `tests/tools/test_jsonc.py` — **new**
  test for the moved behaviour (the strip round-trips, comments removed,
  already-valid JSON untouched).

**Integration Contract:**

- Triggered from: this plan (manual edit)
- Returns to / updates: `crackerjack/tools/jsonc.py` (new),
  `crackerjack/core/phase_coordinator.py`
- Demonstrable by: `pytest tests/tools/test_jsonc.py` passes;
  `uv run python -c "from crackerjack.tools.jsonc import strip_jsonc_comments; print(strip_jsonc_comments('{\"a\":1} // hi')[0])"`
  prints `{"a":1}`
- Rollback signal: `pytest tests/unit/core/test_workflow_pipeline_eventbridge_wiring.py`
  fails, or the `format-json`/`check-json` fast hook regresses
- Observability added: none — the JSONC stripper keeps its existing
  `logger.info` / `logger.warning` lines

### Phase 2 — Delete `crackerjack/fixers/` and the orphaned ty tools

**Delete (production, 3,155 lines):**

- `crackerjack/fixers/` — all 33 files and the directory
- `crackerjack/tools/ty_audit.py`, `ty_classify.py`, `ty_cleanup.py`,
  `ty_imports.py`, `ty_narrow.py`

**Move:**

- `crackerjack/agents/base.py` → `crackerjack/models/agent_context.py` —
  the `AgentContext` dataclass only (the unused `FixResult` re-export is
  dropped). `crackerjack/models/protocols.py:16` imports it from the new
  path. Delete `crackerjack/agents/` entirely afterwards, including
  `README.md` and the two stale `.backup` files under `helpers/refactoring/`.

**Delete (tests, 20,628 lines):**

- `tests/fixers/` — all 21 files and the directory
- `tests/tools/test_ty_audit.py`, `test_ty_classify.py`, `test_ty_cleanup.py`,
  `test_ty_imports.py`, `test_ty_narrow.py`
- `tests/integration/test_tier_architecture_e2e.py`

**Edit:**

- `crackerjack/models/protocols.py` — line 16 becomes
  `from crackerjack.models.agent_context import AgentContext`
- `crackerjack/config/tool_commands.py` — **no change** (`ty_ignore_syntax`
  and `ty_ratchet` entries stay; the deleted tools were never listed there)
- `tests/tools/test_ty_ratchet.py` — drop the `ty_audit` reference if the
  file imports it (verified during execution)

**Integration Contract:**

- Triggered from: Phase 1 complete
- Returns to / updates: deletes `crackerjack/fixers/`, `tests/fixers/`,
  `crackerjack/agents/`, and the five orphaned ty tools + their tests; adds
  `crackerjack/models/agent_context.py`; edits
  `crackerjack/models/protocols.py`
- Demonstrable by: `uv run python -c "import crackerjack.fixers"` raises
  `ModuleNotFoundError`; `git grep -n "crackerjack.fixers\|ty_imports\|ty_classify\|ty_cleanup\|ty_narrow\|ty_audit" -- crackerjack/ tests/ scripts/`
  returns zero matches (CHANGELOG history excluded);
  `uv run python -c "import crackerjack.tools.ty_ignore_syntax, crackerjack.tools.ty_ratchet"`
  succeeds; `uv run python -c "from crackerjack.models.agent_context import AgentContext"`
  succeeds and `uv run python -c "import crackerjack.agents"` raises
  `ModuleNotFoundError`
- Rollback signal: `pytest tests/` reports a collection error naming a
  deleted module
- Observability added: none — pure deletion

### Phase 3 — Delete `autofix_coordinator.py` and its exclusive support modules

**Delete (production, 2,391 lines):**

- `crackerjack/core/autofix_coordinator.py` (1,803)
- `crackerjack/core/preflight.py` (389)
- `crackerjack/services/ai_fix_progress.py` (145)
- `crackerjack/core/ai_fix_event_bus.py` (54)

**Keep:** `crackerjack/models/fix_plan.py` — public API of
`crackerjack.models` (see Context).

**Delete (test):**

- `tests/test_autofix_coordinator.py` (159)

**Edit:**

- `crackerjack/core/phase_coordinator.py` — drop the `_lazy_autofix` lazy
  service (lines 181-186) and the `AutofixCoordinator` import (line 24)
- `crackerjack/core/ai_fix_sinks.py` — drop `build_default_bus`,
  `LoggingSink`, `MetricsSink`, and `migrate_legacy_runs` (each reachable
  only from the deleted coordinator)
- `scripts/validate_imports.py` — drop `"crackerjack.core.autofix_coordinator"`
  from `CRITICAL_MODULES` (line 23)

**Integration Contract:**

- Triggered from: Phase 2 complete
- Returns to / updates: deletes the five modules above; edits
  `crackerjack/core/phase_coordinator.py`, `crackerjack/core/ai_fix_sinks.py`,
  `scripts/validate_imports.py`
- Demonstrable by: `git grep -n "autofix_coordinator\|AutofixCoordinator" -- crackerjack/ scripts/`
  returns zero matches; `uv run python scripts/validate_imports.py` exits 0;
  `uv run python -c "from crackerjack.core.ai_fix_sinks import JsonlSink, runs_root"`
  succeeds
- Rollback signal: `pytest tests/unit/core/test_workflow_pipeline_eventbridge_wiring.py`
  or `pytest tests/cli/` fails; `crackerjack replay --help` errors
- Observability added: none

### Phase 4 — Docs and references

**Files:**

- `CHANGELOG.md` — add an `### Removed` entry under `[Unreleased]`
- `docs/followups/triage/2026-07-10-output-validator-import-check.md` — the
  triage note names `ty_narrow.py`, `ty_classify.py`, and
  `autofix_coordinator.py` as files where a fixed bug "repeats". Those files
  no longer exist; annotate the note rather than rewriting its history.
- `docs/plans/2026-08-06-ai-fix-*.md` and other archived AI-fix plans —
  leave historical entries intact (same rule the Zuban/Skylos plan used)
- `crackerjack/fixers/` references inside `crackerjack/memory/git_metrics_collector.py`
  and `crackerjack/integration/git_metrics_integration.py` docstrings — these
  point at `autofix_coordinator.py` as "the dead-code note"; repoint them at
  this plan
- `crackerjack/agents/README.md` — deleted with the package; its content is
  superseded by this plan's Context section

**Integration Contract:**

- Triggered from: Phase 3 complete
- Returns to / updates: `CHANGELOG.md`,
  `docs/followups/triage/2026-07-10-output-validator-import-check.md`
- Demonstrable by: `git grep -n "autofix_coordinator" -- docs/` returns
  matches only in historical/annotated contexts; the CHANGELOG has a
  `### Removed` entry naming the deleted packages
- Rollback signal: the release audit fails on an unverified `### Removed`
  symbol claim — keep the entry prose-only, with no backticked
  fully-qualified symbol names, so the audit does not try to verify them
- Observability added: none

### Phase 5 — Final validation

**Commands:**

- `pytest tests/` — must not introduce a new failure against the recorded
  baseline (20 pre-existing failures; see Risks)
- `uv run python scripts/validate_imports.py` — exit 0
- `.venv/bin/python -m crackerjack run -f` — exit 0 on the repo
- `git grep -n "crackerjack.fixers\|autofix_coordinator\|AutofixCoordinator\|ty_imports\|ty_classify\|ty_cleanup\|ty_narrow\|ty_audit" -- crackerjack/ tests/ scripts/`
  — zero matches

**Integration Contract:**

- Triggered from: Phase 4 complete
- Returns to / updates: nothing — validation only
- Demonstrable by: all four commands above pass
- Rollback signal: any new test failure versus the baseline set
- Observability added: none

## Resolved decisions

1. **Delete rather than stub.** `crackerjack/fixers/` gets no placeholder
   package. Same precedent as the Zuban/Skylos removal.
2. **New `crackerjack/tools/jsonc.py` rather than extending
   `format_json.py`.** `format_json.py` uses strict `json.loads`; making it
   comment-tolerant would change the `format-json` hook's behaviour, which
   this plan does not authorise.
3. **Keep `ai_fix_sinks.py` and `ai_fix_events.py`.** `cli/replay.py` is a
   live CLI surface. The dead *functions* inside `ai_fix_sinks.py` are
   pruned instead.
4. **Keep `ty_ignore_syntax.py` and `ty_ratchet.py`.** Both are registered
   hook commands.
5. **Delete the orphaned modules' own tests.** A test that exercises a
   module that does not exist is not a safety net.
6. **One commit per phase**, each with an explicit pathspec, so the history
   shows the removal in reviewable steps and the pre-existing uncommitted
   user work stays untouched.

## Risks

1. **The test suite already has 20 pre-existing failures** (verified
   2026-11-13: they fail in isolation, not just under test ordering). The
   baseline must be recorded before Phase 1 and compared after Phase 5 — the
   removal must not *add* to it. A further 9 failures are order-dependent
   (they pass in isolation and fail only in a full-suite run); those are
   excluded from the comparison.
2. **`crackerjack/agents/` may still reference the fixers.** Verified zero
   production importers on 2026-11-13, but the agents package is small
   enough that Phase 2's grep check must confirm it.
3. **The dependency sweep in the working tree is unrelated to this plan.**
   Its own 40-package change is committed separately, so the two changes do
   not become one unreviewable diff.
4. **`pyproject.toml` may declare packages only `fixers/` needed.** Phase 2
   must check for now-unused runtime dependencies (e.g. `libcst`,
   `redbaron`) and drop them.

## References

- `docs/plans/2026-10-11-remove-zuban-skylos-lsp-from-crackerjack.md` — house format and precedent
- `docs/followups/triage/2026-07-10-output-validator-import-check.md` — prior triage naming these files
- `crackerjack/fixers/__init__.py` — the extraction-target docstring
- `crackerjack/core/autofix_coordinator.py:1066`, `:1530` — "AI-fix subsystem removed (Tasks 25-27)" notes
- `crackerjack/core/phase_coordinator.py:181`, `:456-486` — the dead lazy service and the live JSONC call
- `crackerjack/executors/hook_executor.py:2204` — the duplicate `_get_uv_environment_paths`
- `crackerjack/cli/replay.py:22` — the live `ai_fix_sinks` importer

## Estimated scope

| | Files | Lines |
|---|---|---|
| Production deleted | 46 | 31,016 |
| Tests deleted | 29 | 21,447 |
| Production added | 2 (`tools/jsonc.py`, `models/agent_context.py`) | ~95 |
| Production edited | 5 | ~30 |
| **Net** | **−73 files** | **−52,338 lines** |

### Follow-up (not in this plan)

A repo-wide AST inventory (2026-11-13) found **192 dead modules / 55,534
dead production lines** across 109 dead clusters — 34.3% of the 560 modules
under `crackerjack/`. This plan covers the AI-fix cluster. The remainder
(including the orphaned `crackerjack/mahavishnu/` MCP tree at 3,716 lines,
the QA-adapter tier at 4,495 lines, and the `services.patterns.*` families)
is a separate plan. The inventory scripts are re-runnable from
`/tmp/cj_dead_inventory.py`.

## Execution record (2026-11-13/14)

Executed in five phases, one commit each. Two findings turned up during
execution that the plan did not anticipate:

1. **`crackerjack/intelligence/` was left behind by the August 2026
   AI-fix removal.** `docs/plans/2026-08-11-darnlink-replaces-check-local- links.md` records that the package "was deleted in commit 907ab860",
   but its README survived. It described an intelligence layer whose code
   was gone. Deleted.

2. **The API documentation generator wrote to the wrong tree.**
   `DocumentationServiceImpl` treats `pkg_path` as the *package*
   directory; the CLI passed the *repository root*. Three symptoms
   followed: the docs went to an untracked `<repo>/docs/generated/api/`
   instead of the tracked, wheel-shipped
   `crackerjack/docs/generated/api/`; the `<repo>/**/*.py` scan pulled
   361 test classes into the API reference; and
   `update_documentation_index()` overwrote the canonical
   `docs/index.md` (on a case-insensitive filesystem `docs/INDEX.md` and
   `docs/index.md` are the same file). The tracked cross-references had
   **68 stale class references** as a result. Fixed at the call site and
   regenerated — now 351 classes, zero stale.

Net result: **−73 files, −52,338 lines** of production and test code, plus
the two fixes above.
