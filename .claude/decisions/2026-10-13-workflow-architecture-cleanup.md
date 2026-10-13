# Workflow architecture cleanup

## Context

Four long-standing quality issues in `crackerjack/runtime/oneiric_workflow.py`
were flagged in the crackerjack workflow review cycle. Each had drifted into
"the code works, but the shape is wrong" territory — one was actively
misleading (release phases running on every invocation), three were dead or
hand-rolled code that obscured the actual phase DAG.

## Decision rule

Address all four in a single cleanup branch with one commit per observation,
so the regression surface stays reviewable.

### Observation 1 — gate `publishing` and `commit` on CLI flags

**Before**: `steps.extend(("publishing", "commit"))` ran unconditionally at
the tail of `_build_workflow_steps`. Plain `crackerjack run` and
`crackerjack run -f` (fast hooks) silently included the publish/commit
phases in their DAG.

**After**: append `publishing` only when `options.publish` is truthy (any
non-None value covers `major`/`minor`/`patch`/`testpypi`/`pypi` strings),
and `commit` only when `options.commit` is truthy. The release-side phases
are now opt-in.

### Observation 2 — collapse dead `enable_parallel` branch

**Before**: lines 354-364 contained an `if enable_parallel: ... else: ...`
where both arms executed `steps.extend(("tests", "comprehensive_hooks"))`.
Pure dead code; the actual parallel-mode wiring lived in
`_build_nodes_with_dependencies`.

**After**: single `steps.extend(("tests", "comprehensive_hooks"))` with a
comment pointing at the downstream wiring. The if/elif/elif is gone.

### Observation 3 — explicit `PHASE_DEPENDENCIES` for DAG construction

**Before**: `_build_nodes_with_dependencies` and the helper
`_handle_parallel_step` hand-rolled predecessor edges by threading a
`parallel_predecessor` state variable through the loop. The
phase-definition dict in `_register_tasks` carried only the runner; the
edges lived in a side helper with no documented contract.

**After**: a module-level `PHASE_DEPENDENCIES: dict[str, tuple[str, ...]]`
constant is the canonical source of truth for non-default predecessor
edges. Phases listed there get explicit deps; phases not listed fall
back to the default predecessor chain (depend on the immediately
preceding step). The tests + comprehensive_hooks parallel branch is
encoded by leaving the tuple empty as the signal that the parallel
logic should compute the shared predecessor. `_handle_parallel_step` is
deleted — its three-branch logic is folded into the main loop as a
4-line case alongside the explicit-deps branch and the default chain.
Each branch is documented at its call site.

### Observation 4 — drop dead `config_cleanup` gate

**Before**: `_should_run_config_cleanup` had returned `False` with a
6-month-old `TODO: Revert this temporary fix after config_cleanup
debugging` comment since the config_cleanup debugging stalled. The
escape hatch was either going to be reverted (the phase re-enabled) or
removed. The debugging never resumed, so the gate was dead code that
misled readers into thinking the phase was on a temporary off-ramp.

**After**: the function and its call site in `_build_workflow_steps` are
deleted. The `config_cleanup` task factory stays registered — the
underlying `PhaseCoordinator.run_config_cleanup_phase` method still
exists — so a future re-introduction can re-add a real gate without
resurrecting the TODO'd stub. If the feature actually needs to ship,
file a follow-up note rather than reviving the dead function.

## Status

Shipped on branch `fix/observations-1-4` as four commits + one
companion test commit:

- `adf0b602` — gate publishing/commit on CLI flags
- `9940fb89` — collapse dead enable_parallel branch
- `ff0a3006` — make phase DAG dependencies explicit
- `2b08e45e` — remove dead config_cleanup gate
- `a0205cdc` — set publish/commit defaults on `MockOptions`

Test coverage:

- `tests/unit/test_parallel_workflow.py` — 9/9 pass
- `tests/core/test_workflow_orchestrator.py` — 11/11 pass
- `tests/core/test_plan_index_sync_phase.py` — pass except one
  pre-existing hardcoded-path test
  (`test_plan_index_sync_removed_from_fast_hooks_in_source`) that points
  at `~/.local/state/mahavishnu/worktrees/crackerjack/` rather than the
  current worktree (`crackerjack-d/`). This failure is unrelated to the
  cleanup — the hardcoded path predates the branch and is a separate
  bug to file in a follow-up.
- `tests/cli/handlers/test_main_handlers.py` — 25/25 pass
- `crackerjack run -f` — 17/17 fast hooks pass

## Follow-ups

- File a follow-up for the hardcoded `REPO_ROOT` path in
  `tests/core/test_plan_index_sync_phase.py` so the test works from
  any worktree name.
- If config_cleanup ever needs to ship for real, re-introduce the gate
  in `_build_workflow_steps` based on a documented option (not the
  deleted TODO stub).