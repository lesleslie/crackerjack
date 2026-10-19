# plan_index_sync is git-aware; `Options.tool` is wired

Status: Active (codified in commit `1e78dfcc`, 2026-10-16).
Affects: `crackerjack/tools/plan_index_sync.py`, `crackerjack/managers/hook_manager.py`, `crackerjack/core/phase_coordinator.py`.

## Context

Two latent bugs surfaced together from a `check-local-links` failure in oneiric (`docs/plans/PLAN_INDEX.md:51` referenced an untracked `../../.claude/decisions/README.md`):

1. **`plan_index_sync` indexed untracked files.** The generator walked each store with `pathlib.rglob("*.md")` — any `.md` file under a tracked store dir got indexed, including untracked stragglers. The rendered `PLAN_INDEX.md` then linked to files that didn't exist in fresh clones, breaking `check-local-links` on CI.
2. **`crackerjack run --tool <name>` was a no-op.** `Options.tool` was declared, plumbed through `create_options`, and stored on `Options` — but the orchestrator never read it. Every hook in the phase ran regardless. The eight internal recursive callers in `adapters/python/hooks.py` (e.g. `crackerjack run --tool ruff-check`) inherited the same broken behaviour.

Both bugs share a shape: **declared end-to-end but unwired**. The original code settled the feature without wiring it.

## Decision

Adopt both fixes as one change so they share a regression boundary:

### 1. `plan_index_sync` switches from `pathlib.rglob` to `git ls-files`

`_discover_files` now restricts to git-tracked `.md` paths via `_tracked_md_names`, which wraps `git ls-files -z`. Falls back to `pathlib.rglob` when git is unavailable (test fixtures, non-git invocations) so non-repo usages still see every file.

Mirrors the existing pattern in `crackerjack/tools/local_link_checker.py:147-183` (`_list_markdown_via_git`). When a Bodai-wide pattern already exists, copy it instead of inventing.

### 2. `Options.tool` is wired through to `HookManager.set_active_tool`

`phase_coordinator.run_fast_hooks_only` and `run_comprehensive_hooks_only` push `options.tool` onto the hook manager before the run. `HookManagerImpl._filter_strategy_for_tool` builds a `dataclasses.replace(strategy, hooks=matches)` view that keeps only the hook whose name (after `-` ↔ `_` normalisation) matches. Both orchestrated and non-orchestrated paths honour the filter.

Empty strategies (unknown hook name) run zero hooks in that phase — silent signal, not a misleading full-suite run.

## Consequences

- **`plan_index_sync` regenerations across the Bodai ecosystem** now drop stale entries that referenced untracked files. The cross-repo regen (six repos) surfaced this in only one place (oneiric's `.claude/decisions/README.md`) — but the durable fix prevents future drift across all of them.
- **`--tool <name>` is now a real optimisation** rather than a decorative flag. Iterative fix-loop timing improves (no full 200-second comprehensive phase when only `ty` needs to verify).
- **Two pre-existing test failures** in `test_plan_index_sync.py` (`test_rendered_contains_all_six_canonical_stores` and `test_entry_link_targets_resolve_from_plans_dir`) reference the obsolete `docs/superpowers/{specs,plans}/` store paths from `f47d5b00 chore(crackerjack): relocate plans/specs to canonical paths`. Fixed in `fe52626b` — see that commit for the format_cases/expected_headings edits.
- **Memory rule** `feedback-crackerjack-tool-flag-scope.md` rewritten to reflect the flag now actually working (was previously aspirational).
- **Backwards compatibility**: zero. Pre-1.0; no deprecation window (`feedback-no-backwards-compat-pre-1.0`).

## Future contributors — watch for

- **`plan_index_sync` test fixtures in non-git sandboxes** must use the rglob fallback path. The `_tracked_md_names` helper returns `None` on git failure and the discovery falls back to rglob; new tests should construct fixtures via `monkeypatch.setattr(pis, "_tracked_md_names", lambda *_: None)` (see `tests/unit/test_plan_index_sync.py::test_discover_files_falls_back_to_rglob_when_git_missing`).
- **`--tool <name>` with a mis-typed hook name** completes the phase with zero results — the user sees a successful phase that ran nothing. This is intentional (the gate still passes, the user has a clear signal to check spelling) but worth flagging in onboarding if anyone interprets a fast phase that finishes in <1s as "the hook passed."
- **Hook naming convention**: the generator normalises `-` ↔ `_` (CLI ergonomics: `--tool ruff-check` matches a hook stored as `ruff_check`). New hooks should pick one and stay consistent within a single repo.
