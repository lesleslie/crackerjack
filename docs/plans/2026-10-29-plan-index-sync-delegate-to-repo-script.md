---
status: active
role: implementation
topic: documentation-tooling
date: 2026-10-29
last_reviewed: 2026-10-29
superseded_by: null
blocks_on: []
---

# Plan Index Sync Should Delegate to the Repository's Own Renderer

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `crackerjack.tools.plan_index_sync` produce the same index the repository's own audit expects, by deferring to the repository's renderer instead of rendering with a stale in-tool fork.

**Architecture:** Every Bodai repository ships its own `scripts/regenerate_plan_index.py` — the authoritative renderer, with auto-discovered stores and the repo's own index format. `crackerjack/tools/plan_index_sync.py` is a *fork* of that script that lost auto-discovery in the copy: it walks a hardcoded five-store tuple. The fork's own docstring still says "Walk the six stores" while `DEFAULT_STORES` has five entries. This plan replaces the fork with delegation, and repairs the bundled fallback so a repository without its own script still gets a correct index.

**Tech Stack:** Python 3.14, subprocess, pytest.

**Spec:** none — this is a defect fix. Evidence and reproduction are in the Background section.

## Background

`scripts/audit_plan_index.py` in mahavishnu delegates store discovery to the
repository's `scripts/regenerate_plan_index.py`, "so the audit and the renderer
never disagree about what counts as a store." But `crackerjack.tools.plan_index_sync`
— the tool that actually regenerates `PLAN_INDEX.md` during the
`plan-index-sync` phase — uses its own hardcoded store list. The two
therefore disagree, permanently, in both directions:

- **Audit vs. tool:** mahavishnu's audit reported **82** frontmatter'd files
  missing from `PLAN_INDEX.md`, all in `docs/decisions/` and `docs/audits/` —
  two stores the tool's fixed list never walks. After regenerating with the
  repository's script, the audit reports `OK: 168 paths consistent`.
- **Tool vs. repository:** the fork also renders a plainer format than the
  repository's script. The repository's version emits frontmatter, a Status
  Legend, an Authority Matrix, Review Entry Points, per-store descriptive
  headings, and a "By Kind" grouping; the fork emits a bare store table.
  Regenerating with the fork rewrites a 394-insertion index back to the
  plainer form.

The tool's fork has also drifted from the repository copies themselves:
mahavishnu's `scripts/regenerate_plan_index.py` has 26 top-level functions
and accepts `--repo-root`; crackerjack's own copy has 16 and does not.

**Interim mitigations already in place (2026-10-29):** mahavishnu regenerates
with `scripts/regenerate_plan_index.py`, and sets
`documentation.auto_plan_index_sync_on_publish: false` in
`settings/crackerjack.yaml` so the publish path cannot clobber the index.
Both should be reverted once this plan ships.

## Global Constraints

- The repository's renderer wins. A repository that ships
  `scripts/regenerate_plan_index.py` decides its own index format and store
  set; the tool must not second-guess it.
- Never write a *degraded* index. If the tool cannot produce a correct index,
  it must fail loudly with an actionable message, not silently emit a
  plainer one.
- Preserve relative-link rendering — `check-local-links` depends on it.
- No change to the audit script's expectations.
- Pre-1.0: replace, do not extend. Do not add a deprecation window for the
  fork's behavior.

## Review Focus

1. **A repository with no `scripts/regenerate_plan_index.py`** — the bundled
   fallback must still render a complete index, with auto-discovered stores.
   Covered by Task 2.
2. **A repository whose script exits non-zero** — the tool must propagate that
   exit code and must not write a partial or empty index over a good one.
   Covered by Task 1.
3. **A repository whose script lacks `--repo-root`** (crackerjack's own copy
   does) — the delegation must not depend on that flag; it must run with the
   repository root as the working directory. Covered by Task 1.
4. **A repository whose script writes nothing** — the tool must detect the
   unchanged output and report it, rather than reporting success.
   Covered by Task 1.

---

### Task 1: Delegate to the repository's renderer

**Files:**
- Modify: `crackerjack/tools/plan_index_sync.py` (`main()`, ~line 410)

**Interfaces:**
- Consumes: `<repo_root>/scripts/regenerate_plan_index.py` — a script exposing
  `main(argv) -> int` and accepting `--out PATH`. `--repo-root` is **optional**
  and must not be passed (older copies lack it); the working directory is set
  to the repository root instead.
- Produces: `plan_index_sync.main()` returns the delegated script's exit code.
  When the repository script is absent, control falls through to the bundled
  renderer unchanged.

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_plan_index_sync.py` (create if absent): a test that
builds a temporary repository containing a `scripts/regenerate_plan_index.py`
that writes a known sentinel string to its `--out` path, then calls
`plan_index_sync.main(["--repo-root", str(tmp_path)])` and asserts the output
file contains the sentinel.

- [ ] **Step 2: Run it to verify it fails**

Run: `./.venv/bin/pytest tests/unit/test_plan_index_sync.py -v`

Expected: FAIL — the current implementation ignores the repository's script
and renders its own index.

- [ ] **Step 3: Implement delegation**

In `main()`, before the `use_shared_regenerator` branch and before the legacy
render path, locate `repo_root / "scripts" / "regenerate_plan_index.py"`. If
it exists, invoke it as a subprocess:

- `sys.executable` as the interpreter
- `cwd` set to `repo_root`
- arguments: the script path, `--out`, and the resolved output path
- **do not** pass `--repo-root` (not every copy accepts it)
- capture stdout/stderr and forward them to the tool's own stdout/stderr

Return the subprocess's exit code directly. Do not fall through to the
bundled renderer when the subprocess fails — a failed delegation must surface
as a failure, not silently produce a different index.

- [ ] **Step 4: Verify the output was actually written**

After a successful subprocess return, assert the output file exists and that
its modification time or content changed relative to before the call. If the
repository's script exited 0 without writing, raise an error naming the
script path. A silent no-write is the failure mode most likely to go
unnoticed.

- [ ] **Step 5: Run the test to verify it passes**

Run: `./.venv/bin/pytest tests/unit/test_plan_index_sync.py -v`

Expected: PASS.

- [ ] **Step 6: Add the exit-code propagation test**

Add a test whose repository script exits with code 3 and writes nothing.
Assert `main()` returns 3 and that a pre-existing output file is left
**unchanged** — a failed delegation must not truncate a good index.

- [ ] **Step 7: Run the full plan-index test set**

Run: `./.venv/bin/pytest tests/unit/test_plan_index_sync.py tests/ -k "plan_index" -v`

Expected: all PASS.

- [ ] **Step 8: Commit**

```bash
git add crackerjack/tools/plan_index_sync.py tests/unit/test_plan_index_sync.py
git commit --only crackerjack/tools/plan_index_sync.py tests/unit/test_plan_index_sync.py -m "fix(plan-index): delegate to the repository's own renderer when present"
```

#### Integration Contract

- **Triggered from**: The `plan-index-sync` phase (`crackerjack/core/phase_coordinator.py:845`) and the `plan-index-sync` tool command.
- **Returns to / updates**: `<repo_root>/docs/plans/PLAN_INDEX.md` — now written by the repository's own script, which owns the format and store set.
- **Demonstrable by**: `./.venv/bin/pytest tests/unit/test_plan_index_sync.py -v` passes; and in mahavishnu, `python scripts/audit_plan_index.py` reports `OK: 168 paths consistent` after a tool-driven regeneration.
- **Rollback signal**: A repository with no `scripts/regenerate_plan_index.py` produces a missing or empty index after the phase runs.
- **Observability added**: The tool's log records whether it delegated or used the bundled renderer, and the delegated script's exit code.

---

### Task 2: Repair the bundled fallback renderer

**Files:**
- Modify: `crackerjack/tools/plan_index_sync.py` (`DEFAULT_STORES`, ~line 108; `render_plan_index()`, ~line 393)

**Interfaces:**
- Consumes: the auto-discovery algorithm (`discover_stores`, `discover_files`,
  `MIN_STORE_DOCS`) as implemented in **mahavishnu's**
  `scripts/regenerate_plan_index.py` — see the Fleet scope note below for why
  the source is not this repository's own copy.
- Produces: a bundled renderer that discovers stores dynamically, so a repository without its own script still gets a complete index.

> **Fleet scope note.** Auto-discovery is *not* the fleet baseline. All six
> Bodai repositories ship a `scripts/regenerate_plan_index.py`, but only
> mahavishnu's has evolved past the 16-function fixed-store-list version
> (mahavishnu's has 26 top-level functions and `discover_stores`; oneiric,
> crackerjack, session-buddy, akosha, and mcp-common each have the 16-function
> version with no `discover_stores`). So this repository's own
> `scripts/regenerate_plan_index.py` cannot supply the algorithm — port it
> from mahavishnu's, and treat the remaining five repositories' copies as a
> separate propagation task.

- [ ] **Step 1: Write the failing test**

Add a test that creates a temporary repository containing a
`docs/decisions/` directory with two frontmatter'd markdown files, and asserts
that the bundled renderer includes both in its output. Under the current
fixed five-store list, `docs/decisions/` is not walked and both are absent.

- [ ] **Step 2: Run it to verify it fails**

Run: `./.venv/bin/pytest tests/unit/test_plan_index_sync.py -v`

Expected: FAIL — the bundled renderer omits `docs/decisions/`.

- [ ] **Step 3: Replace the fixed store list with auto-discovery**

Replace the `DEFAULT_STORES` tuple with a call to a `discover_stores()`
function that walks the repository root and nominates any directory holding
at least two frontmatter'd markdown files, excluding system directories.
Port the algorithm from **mahavishnu's** `scripts/regenerate_plan_index.py`
— do not re-derive it, and do not copy it from this repository's own
16-function script, which predates auto-discovery.

Keep the existing exclusion rules and the git-tracked-files restriction
(`git ls-files`) intact: the reason for that restriction is that untracked
files in a tracked store get indexed, then their rendered link fails
`check-local-links` on fresh clones.

- [ ] **Step 4: Run the test to verify it passes**

Run: `./.venv/bin/pytest tests/unit/test_plan_index_sync.py -v`

Expected: PASS.

- [ ] **Step 5: Fix the stale docstring**

The `render_plan_index()` docstring reads "Walk the six stores" while
`DEFAULT_STORES` has five entries. Update it to describe auto-discovery
rather than a count.

- [ ] **Step 6: Commit**

```bash
git add crackerjack/tools/plan_index_sync.py tests/unit/test_plan_index_sync.py
git commit --only crackerjack/tools/plan_index_sync.py tests/unit/test_plan_index_sync.py -m "fix(plan-index): discover documentation stores dynamically in the bundled renderer"
```

#### Integration Contract

- **Triggered from**: The `plan-index-sync` phase, for repositories that ship no renderer of their own.
- **Returns to / updates**: `<repo_root>/docs/plans/PLAN_INDEX.md`, now covering every auto-discovered documentation store.
- **Demonstrable by**: The Task 2 Step 1 test passes; `scripts/audit_plan_index.py` in a repository with `docs/decisions/` reports no missing paths.
- **Rollback signal**: The bundled renderer's output omits a store that the repository's audit expects, or the rendered index loses its relative links.
- **Observability added**: The number of discovered stores is logged, so a sudden drop from N to 5 is visible.

---

### Task 3: Retire the interim guards in mahavishnu

**Files:**
- Modify: `settings/crackerjack.yaml` (remove the `documentation:` block)
- Modify: `docs/plans/PLAN_INDEX.md` (regenerate)
- Cross-repo: `~/Projects/mahavishnu/scripts/audit_plan_index.py` (no change needed — it already delegates to the repository script)

**Interfaces:**
- Consumes: the delegated renderer from Task 1.
- Produces: mahavishnu's index regenerable by the tool, with the interim
  guard removed.

- [ ] **Step 1: Remove the interim guard**

Delete the `documentation:` block from `settings/crackerjack.yaml`, including
its explanatory comment. The file may then be empty of crackerjack-specific
settings — if so, delete the file rather than leaving an empty one.

- [ ] **Step 2: Re-enable the publish path**

Confirm the default (`auto_plan_index_sync_on_publish: true`) now produces a
correct index in mahavishnu:

Run in `~/Projects/mahavishnu`: `python -m crackerjack.tools.plan_index_sync --repo-root . --out docs/plans/PLAN_INDEX.md`

Expected: the index regenerates with the repository's format and the
`docs/decisions/` and `docs/audits/` rows intact.

- [ ] **Step 3: Verify the audit**

Run: `python scripts/audit_plan_index.py`

Expected: `OK: 168 paths consistent across PLAN_INDEX.md and filesystem`.

- [ ] **Step 4: Commit in mahavishnu**

```bash
git add settings/crackerjack.yaml docs/plans/PLAN_INDEX.md
git commit --only settings/crackerjack.yaml docs/plans/PLAN_INDEX.md -m "docs(plans): re-enable the tool's plan index sync now that it delegates"
```

#### Integration Contract

- **Triggered from**: Manual execution of this plan.
- **Returns to / updates**: `settings/crackerjack.yaml`, `docs/plans/PLAN_INDEX.md`.
- **Demonstrable by**: `python scripts/audit_plan_index.py` reports `OK`, and a tool-driven regeneration leaves the index unchanged.
- **Rollback signal**: The audit reports missing paths after a tool-driven regeneration — re-add the `documentation:` guard.
- **Observability added**: none; this task removes a workaround.

---

## Parking

| Field | Value |
|---|---|
| Status | Approved (`status: active`), not started |
| Reason | Cross-repo change to a tool used by every Bodai repository; needs its own review and gate |
| Resume trigger | Any session where the plan-index drift is revisited, or where `plan_index_sync` is next modified |
| Interim guard | mahavishnu disables `auto_plan_index_sync_on_publish` and regenerates via `scripts/regenerate_plan_index.py` |
| Related | mahavishnu `docs/plans/2026-10-29-oneiric-resolver-plans.md` (pointer), `docs/plans/PLAN_INDEX.md` |
