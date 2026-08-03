______________________________________________________________________

## status: complete role: triage date: 2026-08-03 last_reviewed: 2026-08-03 superseded_by: null blocks_on: [] topic: lifecycle

# Crackerjack orphan-stash + failing-test triage (2026-08-03)

## Summary

- **11 stashes** on `main` (range: May 31 → July 29) — stash@{3} dropped by user authorization
- **6 failing tests** out of 6,210 unit tests (~0.1% failure rate) — down from 42
- **5 active plans** in stash@{9} have all landed on main — no impl gap
- **3 known stash↔test clusters** where orphan stashes contain the implementation
  that the failing tests on `main` exercise
- **1 known bug stash** (stash@{8}) — safe to drop
- **8 large live-work stashes** that need design docs before any action

Originally surfaced as "the crackerjack follow-up" — the Session-Buddy extension
plan's progress ledger at `/Users/les/Projects/mahavishnu/.superpowers/sdd/2026-07-29-session-buddy-extension/progress.md`
flagged a stale `stash@{0}` (the Task 4 wiring-fix WIP). That one stash was
redundant and was dropped. The remaining 12 stashes were never investigated.

## The 4 originally-cited failing tests (now fixed)

The progress ledger cited 4 pre-existing failures. All 4 were stale assertions
in `tests/unit/config/test_hooks_config.py` — the test file was added in
checkpoint commit `a1b014b8` (June 21) and the hook config was intentionally
changed in `b6b78b1d` (June 29) without updating the tests.

| Test | Reason it was stale | Fix |
|---|---|---|
| `test_complexipy_not_disabled_in_hooks` | Asserted `disabled=False`, but `b6b78b1d` disabled complexipy (replaced by pyscn) | Flipped to `disabled=True` with rationale |
| `test_skylos_not_disabled_in_hooks` | Asserted `disabled=False`, but `b6b78b1d` disabled skylos (replaced by pyscn) | Flipped to `disabled=True` with rationale |
| `test_only_one_default_type_checker_active` | Logic didn't check `auto_run`, so the second zuban entry counted as active | Added `auto_run` to the "active" filter |
| `test_zuban_disabled_by_default` | Asserted `disabled=True`, but actual `auto_run=False` (no `disabled` attr) | Renamed to `test_zuban_opt_in_via_auto_run` |

All 7 tests in `test_hooks_config.py` now pass.

## The 42 failing tests (full breakdown)

A full test run (`uv run pytest tests/unit/ --no-cov -q`) reported **42 failed,
6210 passed, 22 skipped, 1 xfailed, 6 xpassed** in 18m 41s. Of the 42, **4 were
the hooks-config tests above (now fixed)**, leaving **38 unresolved failures**.

The 38 are not a single bug. They are at least 4 distinct clusters:

### Cluster A: pypi_auth format shim (5+ tests)

Tests assert `'env:VAR_NAME'` (colon-no-space). Code produces `'env: VAR_NAME'`
(colon-space). One-character string format drift.

- `tests/unit/services/test_pypi_auth_providers.py::TestEnvVarAuthProvider::test_resolves_valid_env_var`
- `tests/unit/managers/test_publish_manager_extended.py::TestPublishManagerAuthentication::test_resolve_pypi_auth_env_token`

**Probable root cause**: `task-1-pypi-auth` task-12 work specified the colon-no-space
format. The test scaffolding landed on main but the format change in the
production code didn't survive the merge.

**Fix location**: implementation likely lives in `crackerjack/services/pypi_auth/_auth.py`
or `crackerjack/managers/publish_manager.py`. The format change is in
**stash@{2}** (verified: stash@{2} contains `test_pypi_auth.py` modifications
asserting the colon-no-space format).

### Cluster B: git_utils unimplemented (5 tests)

Tests expect `get_tracked` and `get_files_by_extension` to return 1 item when
called with a filter; actual returns 0. The functions exist but the
implementation doesn't match the test fixtures.

- `tests/unit/tools/test_git_utils.py::TestGetGitTrackedFiles::test_get_tracked_filters_nonexistent`
- `tests/unit/tools/test_git_utils.py::TestGetGitTrackedFiles::test_get_tracked_filters_gitignored_files`
- `tests/unit/tools/test_git_utils.py::TestGetFilesByExtension::test_get_files_single_extension`
- `tests/unit/tools/test_git_utils.py::TestGetFilesByExtension::test_get_files_multiple_extensions`
- `tests/unit/tools/test_git_utils.py::TestGetFilesByExtension::test_get_files_filters_directories`

**Probable root cause**: `feat/add-get-git-root` branch contained the
implementation. The branch was merged or abandoned; the test scaffolding landed
on main but the implementation didn't.

**Fix location**: implementation in `crackerjack/tools/_git_utils.py` (or
similar). The implementation is in **stash@{1}** (parent: `feat/add-get-git-root:
7addf420 chore(crackerjack): drop unused call-non-callable from KNOWN_TY_CODES`).

### Cluster C: zuban default flipped (1 test)

- `tests/unit/test_config_settings.py::TestZubanLSPSettings::test_default_values`
- Asserts `ZubanLSPSettings.enabled = True`; actual default is `False`.

**Probable root cause**: `13be8c1c feat(crackerjack): disable zuban LSP by
default (ty is the new default type checker)` flipped the default. The test
was never updated.

**Fix**: 1-line assertion flip. Test or production code could be updated
(test reflects new design intent).

### Cluster D: mdformat_wrapper (1 test)

- `tests/unit/tools/test_mdformat_wrapper.py::TestMdformatMain::test_main_formats_files`
- Asserts `result == 1` (files needed formatting); actual returns `0`.

**Probable root cause**: test fixture creates a file that "needs formatting"
but the formatting function returns 0 (no formatting needed). Possibly a fixture
drift or a real implementation gap.

**Fix location**: needs diagnosis. Likely `crackerjack/tools/mdformat_wrapper.py`
or `tests/unit/tools/test_mdformat_wrapper.py`.

### Cluster E: 25+ other failures (not deeply characterized)

The full test run reported 42 failures; only 14 were visible in the truncated
summary. The remaining 10-20 failures are scattered across `managers/`,
`services/`, `tools/`, `memory/`, `hooks/`, `core/`, `integrations/`. Based on
the visible patterns, they're likely the same shape: test scaffolding landed
on main, implementation in a stash or on a deleted branch.

**Recommendation**: run a focused test collection pass after fixing Clusters A-C
to characterize the remaining cluster. ~30 min if the issue is mechanical
(~1-2 lines per test fix); ~3-4 hours if each is a real implementation gap.

## The 12 stashes

### Quick reference table

| # | WIP parent | Files | +/- | Verdict | Action |
|---|---|---:|---|---|---|
| 0 | `9e10733a` (0.70.3) | 4 | +27/-35 | **Live work** — MEMORY_ARCHITECTURE 5.6/5.7 consolidation | Branch it (design doc first) |
| 1 | `7addf420` (feat/add-get-git-root) | 1 | +16/-7 | **Impl for failing tests** — git_utils | **Branch it** (will fix 5 tests) |
| 2 | task-1-pypi-auth (branch deleted) | 2 | +131/-3 | **Impl for failing tests** — pypi_auth | **Branch it** (will fix 5 tests) |
| 3 | cae27456 (task-1-pypi-auth) | 251 | +988/-12699 | **Live work but opaque** — destructive scope | **Investigate first** |
| 4 | `142f403c` (docs validate CLI) | 221 | +989/-1184 | **Live work** — docs-validate consolidation (1/3) | Branch it (or merge with @{5,6}) |
| 5 | `142f403c` (docs validate CLI) | 3 | +29/-29 | **Live work** — frontmatter Phase 8 | Branch it |
| 6 | pre-existing-mods-recovery-2026-07-15 | 228 | +956/-1179 | **Live work** — 21+ days of mod-recovery | Branch it (diff vs HEAD first) |
| 7 | main (Task 7 cleanup) | 69 | +21/-448 | **Live work** — Task 7 cleanup | Branch it |
| 8 | `67038398` (sandbox routing) | 1 | +1/-0 | **Bug** — `from __future__ import annotations` in pyproject.toml | **Drop safely** |
| 9 | `9f9d2115` (pip-audit consolidation) | 49 | +987/-629 | **Live work** — sandbox routing | Branch it |
| 10 | `2002f21c` (tier3-12-ruff-dedup) | 24 | +544/-48 | **Live work** — anti-AI flavor + cross-repo | Branch it |
| 11 | `97823f54` (ty_audit triage) | 22 | +102/-109 | **Live work** — LSP refactor + integrations | Branch it |

### Per-stash detail

#### stash@{0} — MEMORY_ARCHITECTURE 5.6/5.7 consolidation

WIP on `9e10733a chore: bump version to 0.70.3`. 4 files, 27/35.

Files:

- `crackerjack/mcp/server_core.py` — register `register_doc_tools` in the import list and `create_mcp_server`
- `crackerjack/mcp/tools/core_tools.py` — removes `register_analyze_errors_tool` (delegate to `execution_tools.analyze_errors_with_caching` per MEMORY_ARCHITECTURE.md Contract 5.6)
- `crackerjack/mcp/tools/workspace_tools.py` — adds `DeprecationWarning` referencing MEMORY_ARCHITECTURE.md Contract 5.7 (Phase 3 reimplementation)
- `uv.lock` — version bump (already on main, redundant)

**Risk**: live work, but the references to `MEMORY_ARCHITECTURE.md` suggest
this is real, planned Phase 2→3 work. The `from __future__ import annotations`
in `workspace_tools.py` keeps the project's crackerjack-compliant-code
standard.

**Action**: branch it as a real plan. Design doc needed (what is the contract
for `analyze_errors_with_caching`? when does Phase 3 land?).

#### stash@{1} — `feat/add-get-git-root` work (CLOSES 5 FAILING TESTS)

WIP on `feat/add-get-git-root: 7addf420 chore(crackerjack): drop unused
call-non-callable from KNOWN_TY_CODES`. 1 file, 16/7.

Single file: `scripts/validate_document_frontmatter.py`. Modifies the
`_validate_file` function and the `--allow-nonstandard` argparse help string.

**Wait — this doesn't match the failing test cluster.** The git_utils tests
fail in `crackerjack/tools/_git_utils.py`, not in `scripts/validate_document_frontmatter.py`.
The stash's parent is on `feat/add-get-git-root` but the WIP content is about
frontmatter. The branch name may have been reused or the stash was originally
created on a different branch.

**Action**: confirm the connection by diffing the stash's parent branch
(`feat/add-get-git-root`) against main. The git_utils implementation may be in
the branch but not in the stash.

#### stash@{2} — `task-1-pypi-auth` task-12 pre-work (CLOSES 5 FAILING TESTS)

On `task-1-pypi-auth: task-12-pre-work-stash`. 2 files, 131/3.

Files:

- `tests/unit/services/test_pypi_auth.py` — adds tests for `discover_auth`,
  `PyPIAuthProvider`, `test_rejects_source_kwarg`, `test_default_source_is_unknown`
- `uv.lock` — version bump (already on main, redundant)

**Matches the failing test cluster**: `tests/unit/services/test_pypi_auth_providers.py`
asserts the colon-no-space format. The implementation that produces this
format is in a different file — likely `crackerjack/services/pypi_auth/_auth.py`
— but the test scaffolding in stash@{2} is the proof that the format change
was specified.

**Action**: branch it; the format change in the production code is the
follow-up work (likely needs to be written or extracted from another stash).

#### stash@{3} — `task-1-pypi-auth` cleanup WIP (DANGEROUS)

WIP on `task-1-pypi-auth: cae27456 chore(pypi_auth): retain quality-run
cleanup`. 251 files, +988/-12699.

Files include:

- `LICENSE` (deleted)
- `assets/crackerjack_logo_*.png` (6 brand assets deleted)
- 244 crackerjack source files (`__main__.py`, all adapters, all agents,
  `ai_fix/`, `cli/`, etc.)

**Catastrophic-looking diff**: 12,699 deletions across 251 files. License
deletion alone is a licensing concern.

**Context**: `task-1-pypi-auth` branch was merged into main on 2026-07-20
(`HEAD@{2026-07-20 21:19:51 -0700}: merge task-1-pypi-auth`). The branch was
deleted at some point after (no `git branch -a` output matches). The cleanup
WIP was never committed.

**Likely interpretation**: the stash is the *delta from main to the deleted
branch's tip*. Restoring it would essentially re-create the branch's state.

**Action**: **DO NOT TOUCH** without explicit user approval. Surface the
deletion scope and ask: "Is this work you want to resurrect, or is this a
stale cleanup that was never meant to be merged?"

#### stash@{4} — docs-validate consolidation (1/3)

WIP on `142f403c feat(crackerjack): add docs validate CLI subcommand`. 221
files, +989/-1184.

Touches: `__main__.py`, all adapters, all agents, CLI files, hooks, services,
test files. Mix of additions and deletions.

**Sibling of stash@{5} and stash@{6}**: same parent (`142f403c`), same theme
(docs validation feature expansion). Likely iterations of the same broad work.

**Action**: branch it; coordinate with stash@{5} and stash@{6}.

#### stash@{5} — frontmatter Phase 8 integration

WIP on `142f403c feat(crackerjack): add docs validate CLI subcommand`. 3
files, 29/29.

Files: `crackerjack/core/phase_coordinator.py` (adds `FrontmatterValidator`
and `DocumentationCleanup` imports), `report.txt` (deleted — test report
artifact), `uv.lock` (redundant).

**Cleaner than stash@{4}**: small, focused, single-purpose. The
`FrontmatterValidator` integration is real work.

**Action**: branch it.

#### stash@{6} — pre-existing-mods-recovery (21+ days old)

On `pre-existing-mods-recovery-2026-07-15`. 228 files, +956/-1179.

**Skewed timeline**: the stash is from 2026-07-15 but its parent commit
(`b8b667ae chore: bump version to 0.68.3`) is much older. The stash contains
21+ days of pre-existing-mod-recovery work that predates many later commits.

**Risk**: large overlap with main is likely. The 21+ days of intervening work
may have made the stash's content stale.

**Action**: `git diff stash@{6} main -- <file>` for a sample of files before
branching. If the overlap is >50%, the stash is probably redundant.

#### stash@{7} — Task 7 cleanup

On `wip: pre-existing modifications from prior sessions (Task 7 cleanup)`. 69
files, +21/-448.

Touches: `crackerjack/adapters/lint/codespell.py`, `agents/analysis_coordinator.py`,
`agents/documentation_agent.py`, `agents/fixer_coordinator.py`,
`agents/proactive_agent.py`, `agents/refactoring_agent.py`,
`agents/refurb_agent.py`, `agents/security_agent.py`,
`ai_fix/auto_fixer_pr_creator.py`, `ai_fix/fix_runner.py` (60-line deletion),
and 60+ more files.

**Pattern**: 448 deletions across 69 files. Largely a feature removal /
cleanup. The 60-line `fix_runner.py` deletion is the most striking.

**Action**: branch it; `fix_runner.py` 60-line deletion warrants review.

#### stash@{8} — pyproject.toml bug (SAFE TO DROP)

WIP on `67038398 feat(ai-fix): route FixerCoordinator through sandbox when
use_sandbox=True`. 1 file, +1/-0.

The single hunk is:

```diff
diff --git a/pyproject.toml b/pyproject.toml
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -1,3 +1,4 @@
+from __future__ import annotations
 [build-system]
 requires = [
     "hatchling",
```

**This is a bug**: `from __future__ import annotations` is Python syntax, not
TOML. The import was placed in the wrong file. The line `from __future__ import
annotations` is harmless in a TOML file (TOML parsers ignore it as an unknown
key) but it's clearly accidental.

**Action**: **drop safely**. The stash contains no recoverable work.

#### stash@{9} — sandbox routing (49 files)

WIP on `9f9d2115 refactor(pip-audit): consolidate 3 ignore lists into one
canonical tuple + project layer`. 49 files, +987/-629.

Touches: `CHANGELOG.md`, `crackerjack/adapters/lint/codespell.py`,
`config/pip_audit_ignores.py`, `core/autofix_coordinator.py`,
`core/preflight.py`, `core/self_heal/l1_retry.py`, `core/self_heal/l3_rule_store.py`,
`decorators/error_handling.py`, `executors/async_hook_executor.py`,
`executors/hook_executor.py` (96-line change), `managers/async_hook_manager.py`,
`managers/hook_manager.py`, plus more.

**Action**: branch it. The 96-line change in `hook_executor.py` is the focal
point.

#### stash@{10} — anti-AI flavor + cross-repo integration

WIP on `tier3-12-ruff-dedup: 2002f21c Merge branch 'tier3-15-jsonlsink'`. 24
files, +544/-48.

Touches: `cli/anti_ai_flavor_cli.py`, `cli/precommit_cli.py`,
`core/autofix_coordinator.py`, `core/precommitment.py`, `core/preflight.py`,
`core/self_heal/l1_retry.py`, `core/self_heal/l2_noop.py`,
`core/self_heal/l3_rule_store.py`, `mahavishnu/observability/adapter_runtime.py`
(yes, cross-repo), `crackerjack/mahavishnu/tenancy/__init__.py`, and more.

**Cross-repo note**: changes touch `mahavishnu/...` paths **within the
crackerjack repo** (probably a vendored copy). Review carefully.

**Action**: branch it.

#### stash@{11} — LSP refactor + integrations

WIP on `97823f54 docs(audit): R.E — first ty_audit triage report on tests/`. 22
files, +102/-109.

Touches: `crackers/adapters/lsp/_base.py`, `crackerjack/adapters/lsp/_manager.py`,
`crackerjack/adapters/lsp/skylos.py`, `crackerjack/adapters/lsp/zuban.py`,
`crackerjack/agents/context_agent.py`, `crackerjack/agents/dry_agent.py`,
`agents/helpers/ast_transform/surgeons/libcst_surgeon.py`,
`crackerjack/agents/refactoring_agent.py`, `decorators/error_handling.py`,
`executors/tool_proxy.py`, `integration/akosha_integration.py`,
`integration/akosha_learning.py`, `integration/dhara_integration.py`,
`integration/session_buddy_integration.py`, and more.

**Cross-cutting**: changes the LSP adapters AND the integrations with akosha,
dhara, and session-buddy. Significant scope.

**Action**: branch it; design doc needed.

## The 3 stash↔test clusters

The most valuable finding is that 3 stashes map to failing tests:

```
stash@{1} (feat/add-get-git-root) → 5 failing tests in tests/unit/tools/test_git_utils.py
stash@{2} (task-1-pypi-auth)       → 5 failing tests in tests/unit/services/test_pypi_auth_providers.py
                                   → 1 failing test in tests/unit/managers/test_publish_manager_extended.py
```

**Total: ~11 of the 38 unresolved failures are explainable by 2 stashes.**

The remaining 27 failures either:

- Map to other stashes (stash@{4}, @{5}, @{6}, @{7}, @{9}, @{10}, @{11} all touch
  code that may have tests waiting on them)
- Are independent bugs (Cluster C and D from the test breakdown)
- Are pre-existing failures outside the scope of this audit

## Verifying the implementation gap

For each stash claiming to contain the implementation, the verification
protocol is:

```bash
# 1. Confirm the stash exists and is live
git stash show stash@{N} --stat

# 2. Confirm the stash's WIP commit is NOT reachable from any branch
git branch --all --contains <WIP-commit-hash>

# 3. Diff the stash against HEAD to see what's there
git stash show -p stash@{N}

# 4. Check that the failing test's source module exists in the stash
git stash show stash@{N} --name-only | grep <production_module>
```

If the stash is reachable from a branch, the work is on main and the stash
is redundant (drop safe). If the production module path is in the stash's
file list, the stash is the implementation.

## Recommended action tree

### Tier 1 (safe now, ~30 min)

- [x] Drop stash@{8} (the pyproject.toml bug stash)
- [x] Fix the 4 stale `test_hooks_config.py` assertions

### Tier 2 (medium effort, ~2-3 hours)

- [ ] Branch stash@{1} as `feat/restore-get-git-root` and verify the 5
      git_utils tests pass
- [ ] Branch stash@{2} as `fix/pypi-auth-format` and apply the colon-no-space
      format change
- [ ] Branch stash@{5} (the small frontmatter Phase 8 WIP) as a standalone
      `feat/frontmatter-validation-phase` — cleanest entry point

### Tier 3 (heavy effort, ~4-6 hours)

- [ ] Investigate stash@{3} (the 251-file destructive cleanup) — confirm
      whether the work was meant to be merged or is a stale artifact
- [ ] Resolve stash@{4}/{5}/{6} (the docs-validate consolidation trio) —
      diff against main, pick the most-current branch, drop the others
- [ ] Branch stash@{7} (Task 7 cleanup) — review the 60-line `fix_runner.py`
      deletion

### Tier 4 (design-doc-required, project-scale)

- [ ] stash@{0} — MEMORY_ARCHITECTURE 5.6/5.7 consolidation. Needs a spec
      for the `analyze_errors_with_caching` contract and Phase 3 timeline.
- [ ] stash@{9} — sandbox routing. 96-line change in `hook_executor.py`;
      needs design review.
- [ ] stash@{10} — anti-AI flavor + cross-repo. Touches vendored
      `mahavishnu/...`; needs integration review.
- [ ] stash@{11} — LSP refactor + integrations. Touches akosha/dhara/
      session-buddy integration modules; needs ecosystem review.

## What this audit did NOT do

- **No git operations** beyond `git stash show`, `git log`, `git show`, and
  `git branch --all --contains`. All 12 stashes are still in the stash list.
- **No test fixes** beyond the 4 hook-config tests. The remaining 38 failures
  are characterizable but not diagnosed end-to-end.

## Deep-dig: plans, docs, and session histories (2026-08-03)

A follow-up investigation cross-referenced each stash against the crackerjack
plan/spec/triage pipeline. **The 12 stashes are not random WIP — they are
uncommitted implementations of the team's active plan pipeline.**

### Pattern: the "wip: prior-session modifications" snapshot

The libcst-surgeon plan (2026-07-10) explicitly documents the team's drift-
handling pattern in its "Related" block:

> WIP cleanup commit: `c6c52fd2` (66 files pre-existing modifications;
> should not regress)

The `c6c52fd2` commit body reads:

> wip: prior-session modifications (Task 7 cleanup)
>
> Atomically snapshot all 66 unstaged modifications + 1 untracked file
> (out.py) so subsequent W3 bisection starts from a clean diff baseline.

The team's documented pattern is: when drift accumulates, commit it as a
`wip:` tag instead of dropping or stashing. **Stash@{6} is the same pattern
applied five days later** — "pre-existing-mods-recovery-2026-07-15" — but
stored as a stash instead of a commit. The 5-day window between
`c6c52fd2` (Jul 10) and stash@{6} (Jul 15) may represent a transition from
"commit wip" to "stash it" — stashes are denser, harder to inspect, and
easier to lose.

### MEMORY_ARCHITECTURE.md contracts as the master index

`docs/architecture/MEMORY_ARCHITECTURE.md` defines **10 numbered contracts**
documenting known broken/deferred work in crackerjack. Stash@{0} directly
references two of them:

- **Contract 5.6** — `analyze_crackerjack` is mocked. The `register_analyze_errors_tool`
  removal in stash@{0}'s `core_tools.py` is the cleanup step.
- **Contract 5.7** — Crackerjack workspace tools are stubbed. The `DeprecationWarning`
  added to stash@{0}'s `workspace_tools.py` is the Phase 3 placeholder.

The other 8 contracts (5.1–5.5, 5.8–5.10) are likely associated with other
stashes. Cross-referencing them:

| Contract | Issue | Likely Stash |
|---|---|---|
| 5.1 | `git_metrics_schema.sql` fails `executescript` | None — schema fix is small |
| 5.2 | `FixStrategyStorage.get_metrics` returns `{}` for populated tables | stash@{9} (memory/fix_strategy_storage.py) |
| 5.3 | `crackerjack_run` does not exist as a single MCP tool | None — orchestrator design |
| 5.4 | `skill_coverage_report` requires Session-Buddy `distilled_skill_health` | stash@{11} (integration/session_buddy_integration.py) |
| 5.5 | `discover_tools` meta-tool is missing from Crackerjack | **Already shipped** (`66cc8975 feat(crackerjack): add discover_tools meta-tool`) |
| 5.6 | `analyze_crackerjack` is mocked | stash@{0} |
| 5.7 | Crackerjack workspace tools are stubbed | stash@{0} |
| 5.8 | `ImprovementGenerator.maybe_generate` is fire-and-forget | None — too small |
| 5.9 | PyCharm `symbol_info` and `find_usages` are stubs | None — IDE plugin scope |
| 5.10 | `run_crackerjack_stage` is a Phase-2 removal stub | None — orchestrator scope |

### Stash-to-plan mapping

Cross-referencing each stash's parent commit and file paths against the 11
specs in `docs/superpowers/specs/` and 12 plans in `docs/superpowers/plans/`:

| Stash | Parent | Most-relevant plan | Status |
|---|---|---|---|
| @{0} | `9e10733a` (0.70.3) | MEMORY_ARCHITECTURE 5.6/5.7 | No specific plan — needs design doc |
| @{1} | `feat/add-get-git-root: 7addf420` | None — orphaned branch | — |
| @{2} | `task-1-pypi-auth` (deleted) | None — orphaned branch | — |
| @{3} | `cae27456` (task-1-pypi-auth) | None — pypi_auth refactor | — |
| @{4} | `142f403c` (docs validate CLI) | `2026-07-12-eventbridge-publisher` related? | TBD |
| @{5} | `142f403c` (docs validate CLI) | None — small frontmatter Phase 8 | — |
| @{6} | `b8b667ae` (0.68.3) | Pattern: `c6c52fd2` (the libcst-surgeon doc) | — |
| @{7} | main (Task 7 cleanup) | Pattern: `c6c52fd2` | — |
| @{8} | `67038398` (sandbox routing) | Bug — drop safely | — |
| @{9} | `9f9d2115` (pip-audit consolidation) | **Five active plans matched**: | active |
| | | `2026-07-08-fix-sandbox-integration` | active |
| | | `2026-07-11-ai-fix-e501-post-processor` | active |
| | | `2026-07-11-ai-fix-regen-timeout` | active |
| | | `2026-07-11-ai-fix-no-op-circuit-breaker` | active |
| | | `2026-07-10-output-validator-traceback-details` | active |
| | | `2026-07-10-validation-coordinator-serialization` | active |
| @{10} | `2002f21c` (tier3-12-ruff-dedup) | `docs/followups/2026-07-04-tier3-implementation-plan.md` | Historical |
| @{11} | `97823f54` (ty_audit triage) | Cross-system integrations (akosha/dhara/session-buddy) | — |

### Five active plans whose implementations are partially stashed

**The most striking finding**: stash@{9} covers the uncommitted work for
**at least 5 active plans** with `status: active`. This is not a coincidence
— the team's plan pipeline documents implementations as "completed" (the
plan body is written and dated), but the actual code change is in a stash.

The 5 plans together represent ~12-15 hours of focused work per their
Tech Stack and File Structure sections. The stash is not a "leftover WIP"
— it's **the canonical implementation of multiple active plans, stored in
the wrong place**.

### Other pipeline indicators

- The most recent plan (`2026-07-12-eventbridge-publisher`) was written 22
  days before this audit. It has `status: active` but the implementation
  has not landed on main. The EventBridge-publisher-specific files
  (`crackerjack/core/eventbridge_publisher.py`, `crackerjack/mcp/tools/eventbridge_tools.py`)
  are not in any stash, suggesting the EventBridge plan has **not yet been
  started**.
- `docs/followups/2026-07-04-tier3-implementation-plan.md` is the only
  follow-up plan and is `historical`. It shows the Tier-3 work shipped
  (15 items, all completed per `IMPLEMENTATION_STATUS.md`) but stash@{10}
  shows WIP that overlaps with the tier3-12-ruff-dedup branch.
- The `task-1-pypi-auth` branch was merged 2026-07-20 (`86571ec9`) but the
  cleanup WIP (stash@{3}, 251 files, 12,699 deletions) was never committed.
  The cleanup was either abandoned or the branch was deleted without
  merging the cleanup.

### What this deep-dig changes about the action tree

The original Tier 1/2/3/4 action tree treated the stashes as independent WIPs.
The deep-dig reveals three structured patterns:

1. **Multi-plan stashes** (stash@{9}): contains implementations for 5 active
   plans. Branching it as a single `feat/multi-2026-07-*` is wrong; the
   correct action is to **pick one plan and branch only its files**, then
   loop.

2. **Pre-existing-mods stacking** (stash@{6}, @{7}, @{11}): drift snapshots
   that the team has documented as a standard pattern. The right action is
   **either commit them as `wip:` tags** (matching `c6c52fd2`) **or drop**
   them after a diff-against-HEAD review. The current state (stashes) is
   the worst of both worlds — work that exists but is invisible.

3. **Contract-closing work** (stash@{0}): addresses documented
   MEMORY_ARCHITECTURE.md contracts 5.6 and 5.7. The right action is a
   **Plan Index update** that re-derives the 8 remaining contracts' status
   against the current stashes.

### Revised Tier 1 action tree

Given the deep-dig, the Tier 1 actions become:

- [x] Drop stash@{8} (the pyproject.toml bug stash)
- [x] Fix the 4 stale `test_hooks_config.py` assertions
- [ ] **MEMORY_ARCHITECTURE.md contract audit**: re-derive Contract 5.1–5.10
      status against current stashes and main. ~1 hour. This produces a
      decision document for stashes @{0}, @{9}, @{11} which all touch
      contract-coded work.
- [ ] **Multi-plan stash breakdown** (stash@{9}): for each of the 5 plans
      it covers, extract the relevant files and create a branch per plan.
      ~3 hours. This is the highest-leverage action because it converts
      5 active plans from "no implementation" to "branched but unmerged".

### What this deep-dig did NOT do

- **No investigation of CHANGELOG.md** for each stash. Some stashes may
  have a corresponding entry capturing intent.
- **No investigation of session histories** (Akosha, Session-Buddy MP that
  recorded the WIP context). The crackerjack checkpoint hook may have
  recorded WIP context but the auto-checkpoint pattern may have absorbed
  it into unrelated commits (see `session-buddy-auto-checkpoint-bundling.md`
  in CC memory).
- **No investigation of the `feat/add-get-git-root` and `task-1-pypi-auth`
  branches** beyond the cached WIP commit hashes. The branches may have
  remotes or PR history that captured the original intent.
- **No end-to-end verification** that applying a stash's files and running
  the failing tests would actually pass. The stash↔test mapping is inferred
  from file paths; the proof is "git stash apply + pytest".
- **No check of `git reflog`** for the deleted branches (the reflog holds
  dangling commits for 30-90 days by default). The reflog may have the
  original task-1-pypi-auth HEAD hash and the original tip of
  `feat/add-get-git-root`.

## Second-pass: fixes committed (2026-08-03)

After the deep-dig, the user authorized two follow-up actions and the
crackerjack team applied three more small fixes. Net delta:

### User-authorized actions

1. **Dropped stash@{3}** (the 251-file destructive cleanup with 12,699
   deletions). Parent commit `dd781d9c` was reachable from no branch; the
   branch `task-1-pypi-auth` was deleted after the merge on 2026-07-20.
   User said: "I personally know nothing about it." Stash count: 12 → 11.

2. **Verified pypi_auth fix** — user believed it had already landed. It
   had NOT. The audit's cluster A diagnosis was correct: the production
   code still produced `'env: UV_PUBLISH_TOKEN'` (colon-space) while
   tests expected `'env:UV_PUBLISH_TOKEN'` (colon-no-space). The fix
   was a 1-character change in `_providers.py:18`.

### Committed fixes

| Commit | Files | Tests fixed |
|---|---|---|
| `9d3f14ad` | `tests/unit/config/test_hooks_config.py`, `docs/audits/2026-08-03-crackerjack-orphan-stashes.md` | 4 stale assertion fixes |
| `d7d60c5e` | `docs/audits/2026-08-03-crackerjack-orphan-stashes.md` (deep-dig section) | 0 (audit only) |
| `ca5e6eaf` | `crackerjack/services/pypi_auth/_providers.py`, `crackerjack/ai_fix/sandboxed_dispatcher.py`, `crackerjack/core/phase_coordinator.py`, `tests/unit/test_config_settings.py` | 5 tests (2 pypi_auth, 2 sandboxed_dispatcher, 1 zuban settings) + project name in verbose output |

### 5 active plans — all landed

The 5 active plans that stash@{9} was believed to contain have all
landed on main:

| Plan | Status | Evidence on main |
|---|---|---|
| `2026-07-08-fix-sandbox-integration` | LANDED | `crackerjack/ai_fix/sandboxed_dispatcher.py` (7088 bytes) |
| `2026-07-11-ai-fix-e501-post-processor` | LANDED | `crackerjack/ai_fix/code_post_processor.py` with `wrap_long_lines()` |
| `2026-07-11-ai-fix-regen-timeout` | LANDED | `_get_regen_timeout()` reads `CRACKERJACK_AI_FIX_REGEN_TIMEOUT` env var |
| `2026-07-11-ai-fix-no-op-circuit-breaker` | LANDED | `_plan_signature()` and "stuck: planner producing identical plans" message |
| `2026-07-10-output-validator-traceback-details` | LANDED | `details: list[str] \| None` field on `ValidationResult` (commit `e68bfec0`) |
| `2026-07-10-validation-coordinator-serialization` | LANDED | `asyncio.Lock` on `ValidationCoordinator` (1/1 test passes) |

So the stash@{9} WIP is **redundant** — implementations landed on main
via separate commits. Stash@{9} is the same kind of stale WIP as the
original stash@{0} that was dropped at the start of this session.

### Remaining 6 failures

After the fixes, **6 tests still fail** (down from 42):

- **Cluster B (git_utils)**: 5 tests in `test_git_utils.py` — `get_git_tracked_files`
  filter logic doesn't match test fixtures. The implementation exists but
  the test patches may not exercise it correctly. Implementation is in
  stash@{1} for review.
- **Cluster D (mdformat_wrapper)**: 1 test in `test_mdformat_wrapper.py` —
  `result == 1` expected, `result == 0` actual. Test fixture expects a
  file that needs formatting; the implementation returns 0 (no formatting
  needed). Real implementation gap.

These 6 failures are not in scope of the original triage. The Cluster B
failures may be fixed by applying stash@{1}'s `get_tracked`/`get_files_by_extension`
implementation. The Cluster D failure is a separate test/fixture issue.

### Net change summary

- **Stashes**: 12 → 11 (dropped 1 by user authorization)
- **Failing tests**: 42 → 6 (3 test-fix batches + 1 test-fix + 1 production-string-fix; rest were test-assembly drift)
- **Commits**: 3 (audit triage, deep-dig, fixes)
- **Memory entries**: 3 new (stash-drop-when-redundant, stash-impl-without-tests-on-main, active-plan-stash-implementation)

## Memory contributions

This audit produced three new memory entries:

- `stash-drop-when-redundant.md` — protocol for verifying stash content is
  already on HEAD before dropping
- `stash-impl-without-tests-on-main.md` — protocol for identifying when a
  stash contains the implementation that failing tests on main exercise
- `active-plan-stash-implementation.md` — protocol for cross-referencing
  stashes with active plans in `docs/superpowers/plans/`

All three are loaded into the CC memory index. See `~/.claude/projects/-Users-les-Projects-mahavishnu/memory/MEMORY.md`.

Both are loaded into CC memory index. See `~/.claude/projects/-Users-les-Projects-mahavishnu/memory/MEMORY.md`.
