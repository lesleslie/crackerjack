---
status: adopted
role: lifecycle
topic: testing-infrastructure
date: 2026-11-06
last_reviewed: 2026-11-07
superseded_by: null
blocks_on: []
---

# Test Selection and Run-State Tracking

## Summary

Crackerjack selects the tests a change actually affects, and records what
every test run observed into a crackerjack-owned SQLite store keyed by
`(repo, commit_sha, worktree)`. The selection half replaces a `snob`
shell-out that had been a silent no-op; the recording half turns "what
was the test status at commit X" into a query instead of a full re-run.
It is wired into the `tests` phase and queryable through
`crackerjack run-state show` / `crackerjack run-state diff`.

## Why

- **The snob shell-out never ran.** `snob-lib` has no cp314/cp315 wheel,
  the `snob` CLI was not installed, and the `[dependency-groups].snob`
  group was empty — so the "incremental test selection" the gate
  advertised was a no-op that cost a subprocess per run and selected
  nothing. Measured: 1179 tests / 37.34 s for a full run.
- **Every suite run re-established a baseline by hand.** The whole point
  of running the suite was to compare against the previous run, and that
  comparison lived in whatever terminal scrollback the operator happened
  to have.
- **pytest-testmon selects for real.** Pure-python (`py3-none-any`),
  `requires-python >= 3.10`, tracks file *content* changes rather than a
  `git diff HEAD~10` heuristic, reuses pytest-cov's coverage instance so
  the dependency map costs no extra tracing, and accumulates per-test
  average durations as a second reusable baseline. Measured: 1179 tests
  / 37.34 s full → **12 tests / 3.64 s** on a one-module change → **0
  tests / 0.32 s** when nothing changed.

## What is delivered

- **`pytest-testmon>=2.2.0`** in `[project].dependencies`; the `snob`
  dependency group is deleted.
- **`crackerjack/managers/test_command_builder.py`** — appends `--testmon`
  to the pytest command when incremental selection is on, and points
  `--json-report-file` at a per-run
  `.crackerjack/last-run-<uuid>.json`.
- **`crackerjack/services/testing/run_state_store.py`** — the SQLite
  store (`runs` + `test_results`, WAL, FK cascade) at
  `~/.local/share/crackerjack/run_state.db`, keyed by
  `(repo, commit_sha, worktree)`.
- **`crackerjack/managers/test_manager.py`** — records the run's
  per-test results after every `tests` phase, full or incremental.
  Recording is a side effect and never fails a run.
- **`crackerjack/cli/run_state_cli.py`** — `crackerjack run-state show`
  and `crackerjack run-state diff`, registered on the CLI.
- **`crackerjack/core/phase_coordinator.py`** — the coverage ratchet
  skips an incremental run, whose coverage covers only the affected
  tests and cannot be compared to the full-suite baseline.
- **`.testmondata*` and `.crackerjack/`** in `.gitignore` and in
  `templates/GITIGNORE_BODAI.md`.

## Transitions

| From | To | Date | Trigger | Evidence |
|------|----|------|---------|----------|
| (none) | `draft` | 2026-11-06 | Entry created | plan `docs/plans/2026-11-06-test-selection-and-run-state.md` |
| `draft` | `built` | 2026-11-06 | Store, CLI and testmon wiring landed | commit `ee99b10e` |
| `built` | `wired` | 2026-11-07 | `tests` phase records run state; `crackerjack run-state show` / `diff` read it back | plan tasks 2.3 and 2.4; `run-state diff` reported status changes, disappeared tests (`absent`) and new tests against a recorded baseline |
| `wired` | `adopted` | 2026-11-07 | The selection mode became observable: every run records how it was selected, and `crackerjack run-state stats` aggregates it | commit `7888546f`; `run-state stats` reports the incremental and full counts, and the incremental count is the ratchet-skip count |

## Links

- **Plan:** `docs/plans/2026-11-06-test-selection-and-run-state.md`
- **Canonical doc:** none yet — the decision record for the store's
  location is `docs/decisions/2026-11-06-cj-xdg-namespace-and-state-paths.md`
- **Related entries:** none
- **Upstream context:** `docs/decisions/2026-11-06-cj-xdg-namespace-and-state-paths.md`
  — that record's rule 2 (`runs/` and `logs/` to `$XDG_STATE_HOME`) and
  three legacy non-XDG paths are **not** implemented by this feature.

## Rollback signal

- **Selection:** uninstall `pytest-testmon` and the `--testmon` flag
  stops being appended; the `tests` phase runs the full suite. The
  dependency is a direct one, so removing it from
  `[project].dependencies` and re-syncing is enough.
- **Recording:** set `run_state.storage_path` to a path the process
  cannot write, or make the store's directory read-only — the failure is
  logged as a warning and the run continues. Recording never fails a
  test run, so the feature can be disabled without a code change by
  pointing the setting at an unwritable path.
- **Both:** `git revert` of the merge commit `c2b1f9a5` removes the
  whole feature; the `snob` group was already a no-op, so nothing
  observable is lost.

## Observability

- **Store:** `~/.local/share/crackerjack/run_state.db` — one row per
  run in `runs`, one per test in `test_results`.
- **Log:** a `logger.info` per recorded run carrying the run id, repo,
  commit and test counts; a `logger.warning` if recording fails.
- **Query:** `crackerjack run-state show --commit <sha>` and
  `crackerjack run-state diff --base <sha> --commit <sha>`.
- **Selection mode:** `crackerjack run-state stats` — the runs counted
  by selection mode. The coverage ratchet skips exactly when a run was
  incremental, so the incremental count is also the number of times the
  ratchet was skipped. `run-state show` reports the mode of one run.
- **Deliberately not a Prometheus counter.** A counter in a process that
  exits is weaker evidence than a durable row: it cannot be queried
  after the fact, and it would have needed a second counter for the
  ratchet skip that could only drift from the first.
