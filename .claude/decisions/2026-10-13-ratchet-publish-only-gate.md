---
name: ratchet-publish-only-gate
description: "The coverage ratchet phase is opt-in via --coverage-ratchet and auto-enabled on --publish. It does not run on default cj run, on -f, on -c, or on bare fast/comprehensive-hooks verification. The previous default-on behavior was a silent phase that no one verified."
status: active
role: canonical
date: 2026-10-13
last_reviewed: 2026-10-13
topic: workflow-architecture
---

## Context

`crackerjack/runtime/oneiric_workflow.py:_should_run_coverage_ratchet` previously gated
the ratchet phase only on `not no_coverage_ratchet`. The phase fired on every workflow
run — `crackerjack run -v`, `crackerjack run -f`, `crackerjack run -c`, and the
default run alike. This is wrong on two counts:

1. The ratchet is a release-time concern. Its consumers are
   `crackerjack/checks/release_audit.py:388-469` (CLAUDE.md coverage claim
   verification), `crackerjack/managers/publish_manager.py:706-725` (publish
   pipeline), and `crackerjack/documentation/dual_output_generator.py:237`
   (progressive-enhancement narrative). It is not consulted by any dev-loop
   phase.
2. The ratchet depends on `coverage.json` from a prior `tests` phase. On `-f`
   (fast hooks only), no tests run, so the ratchet either silently no-ops
   or errors on missing data — both are bad. On `-c` (comp hooks only), the
   same data-dependency problem applies.

A 2026-10-12 session surfaced the ratchet "unexpectedly starting" on
`crackerjack run -f` and asked whether the ratchet should be publish-only. The
answer is yes, with the same opt-in-with-auto-on-publish shape as
`documentation_cleanup` and `plan_index_sync`.

## Decision rule

The coverage ratchet is **publish-time-only by default**. It runs in the
workflow when:

- the user passes `--coverage-ratchet` explicitly, OR
- the user passes `--publish` AND
  `settings.documentation.auto_coverage_ratchet_on_publish` is true (the default).

The previous `--no-coverage-ratchet` flag is removed entirely. There is now
one way to disable auto-enable on publish: set
`settings.documentation.auto_coverage_ratchet_on_publish: false` in
`settings/local.yaml`. There is no per-run escape hatch because the
release-audit pipeline reads `.coverage-ratchet.json` and a stale or missing
file at publish time is a hard fail — letting users skip the ratchet
mid-release is a footgun, not a feature.

## Implementation

1. `crackerjack/cli/options.py`: replaced the `no_coverage_ratchet: bool = False`
   field on the `Options` dataclass and in the `CLI_OPTIONS` dict with
   `coverage_ratchet: bool = False`. The flag is `--coverage-ratchet` (a single
   opt-in flag, not a `--coverage-ratchet/--no-coverage-ratchet` toggle pair
   — the `--no-X` form is gone).
2. `crackerjack/__main__.py`: updated the `run()` parameter binding to use
   `coverage_ratchet` instead of `no_coverage_ratchet`.
3. `crackerjack/cli/handlers/main_handlers.py`: added a third auto-enable
   branch in the existing `if options.publish and (...)` block, mirroring
   `cleanup_docs` and `plan_index_sync`. Sets `options.coverage_ratchet = True`
   when publish is requested and the user has not opted in manually.
4. `crackerjack/config/settings.py`: added
   `auto_coverage_ratchet_on_publish: bool = True` to `DocumentationSettings`.
   (The `DocumentationSettings` placement is intentional and matches the
   plan_index_sync precedent; refactoring the settings taxonomy is a separate
   cleanup tracked elsewhere.)
5. `crackerjack/runtime/oneiric_workflow.py`: rewrote
   `_should_run_coverage_ratchet(options)` from
   `return not getattr(options, "no_coverage_ratchet", False)` to
   `return bool(getattr(options, "coverage_ratchet", False))`. The auto-enable
   already happened in `main_handlers.py` before the workflow runs.
6. `crackerjack/core/phase_coordinator.py:run_coverage_ratchet_phase`:
   removed the belt-and-suspenders `if no_coverage_ratchet: return True`
   short-circuit. The phase is gated at the workflow level; double-gating in
   the runner is redundant and would be a stale code path after the flag
   rename.
7. `crackerjack/interactive.py:444`: updated the rich-UI builder's ratchet
   phase gate from `enabled=not no_coverage_ratchet` to
   `enabled=getattr(options, "coverage_ratchet", False)`.
8. Test files updated: `tests/core/test_plan_index_sync_phase.py` and
   `tests/test_cli/test_global_lock_options.py` both had `no_coverage_ratchet`
   in their default-options fixtures; switched to `coverage_ratchet=False`.

## Prerequisite fix (separate commit, same branch)

The dirty `crackerjack/managers/test_manager.py` in main had a missing
`from crackerjack.services.testing.coverage_manager import CoverageManager`
import. The clean worktree at `aac2aff7` (the HEAD I branched from) has the
same bug, so `crackerjack run -f` from the worktree surfaced the
`NameError: CoverageManager is not defined`. Without the import fix, the
merge gate (`crackerjack run -v`) cannot pass.

The fix is one line: add the missing import to the
`crackerjack.services.testing.*` import block, sorted alphabetically before
`test_result_parser`. The dirty-tree version of the file (still uncommitted
in main) has the same fix; this PR re-applies it on the worktree branch so
the merge can proceed.

## Verification

| Check | Result |
|---|---|
| `_should_run_coverage_ratchet(SimpleNamespace(coverage_ratchet=True))` | `True` |
| `_should_run_coverage_ratchet(SimpleNamespace(coverage_ratchet=False))` | `False` |
| `_should_run_coverage_ratchet(SimpleNamespace())` (no field) | `False` |
| `_should_run_coverage_ratchet(SimpleNamespace(no_coverage_ratchet=True))` (dead-flag case) | `False` (the field is dead and ignored) |
| `crackerjack run -f` | 17/17 fast hooks passed in 39.03s; ratchet phase did NOT start |
| `pytest tests/core/test_workflow_orchestrator.py tests/core/test_plan_index_sync_phase.py tests/test_cli/test_global_lock_options.py tests/cli/handlers/test_main_handlers.py` | 93 passed in 56.85s |

The dead-flag test case (4) is important: it confirms that even if a stale
caller passes `no_coverage_ratchet=True`, the ratchet correctly defaults to
off. The old field is genuinely dead, not just hidden by a getter.

## Follow-ups filed as part of this work

- Consider whether `--coverage-ratchet` should also auto-fire on
  `--full-release` (currently it only auto-fires on `--publish`). The
  full-release workflow is `--strip-code -t -p <ver> --commit`, which
  includes `-p <ver>` — so `publish` is always set in practice, and
  full-release will pick up the auto-enable. If that ever changes, the
  one-line follow-up is `or getattr(options, "full_release", None) is not
  None` in the `main_handlers.py` auto-enable block.
- The `phase_coordinator.py:run_coverage_ratchet_phase` is now a
  data-dependent phase that assumes `coverage.json` exists. A
  defensive `if not coverage.json.exists(): return True` in the runner
  is worth adding once the publish-only gate is exercised in CI. The
  current behavior is "let it fail" which is fine while the ratchet
  only runs after `tests` in the publish workflow, but the ratchet
  becoming a manual `--coverage-ratchet` invocation breaks the
  invariant. Track separately.

## Status

Active. The gate is enforced by the gate function in
`crackerjack/runtime/oneiric_workflow.py` and the auto-enable in
`crackerjack/cli/handlers/main_handlers.py`. Fast hooks verify the new
behavior end-to-end (ratchet no longer fires on `-f`).
