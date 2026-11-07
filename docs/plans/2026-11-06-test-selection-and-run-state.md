---
title: Replace the dead pytest-snob integration with pytest-testmon, and record per-test run state in a shared commit-keyed store
description: The snob shell-out is a silent no-op (snob-lib has no cp314/cp315 wheel, the CLI is not installed, and the dependency group is empty). Swap it for pytest-testmon - pure-python, py3-none-any, requires-python >=3.10 - and make every crackerjack test run record per-test results into a crackerjack-owned SQLite store keyed by (repo, commit_sha, worktree), so "what was the test status at commit X" becomes a query instead of a full re-run.
audience: crackerjack maintainer
created: 2026-11-06
status: complete
role: implementation
topic: testing-infrastructure
date: 2026-11-06
last_reviewed: 2026-11-07
superseded_by: null
blocks_on: []
---

# Test Selection and Run-State Tracking

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make crackerjack's test phase incremental (so a full suite is not
re-run to re-establish a baseline) and make every run's per-test results
queryable by commit and worktree.

**Architecture:** Two phases, deliberately sequenced. Phase 1 replaces the
external `snob` binary with pytest-testmon's `--testmon` flag, so testmon
deselects unaffected tests at collection time instead of crackerjack
computing a test list via subprocess. Phase 2 adds a crackerjack-owned SQLite
store that records per-test results on every run, keyed by
`(repo, commit_sha, worktree)`.

**Tech Stack:** pytest-testmon >=2.2.0 (pure-python, `py3-none-any`),
pytest-json-report, SQLite via the `crackerjack/mcp/persistence.py` conventions,
`crackerjack/utils/xdg_paths.py` for XDG resolution.

**Spec:** This plan is self-contained. It implements two standing decisions:
`docs/decisions/2026-11-06-cj-xdg-namespace-and-state-paths.md` (crackerjack
owns its own XDG data) and
`crackerjack/.claude/decisions/2026-10-13-ratchet-staleness.md` (a stored
baseline must self-describe its freshness).

## Global Constraints

1. **Python floor is 3.14.** The selection path must stay pure-python. Any
   compiled dependency that ships no cp314/cp315 wheel is disqualifying —
   this is exactly what disqualified `snob-lib` (107 wheels, max tag `cp313`).
1. **testmon and branch coverage must never share a pytest run.** testmon
   raises `TestmonException` when pytest-cov runs in branch mode
   (`testmon/testmon_core.py:513-553`). Branch coverage is *on* in every
   Bodai repo — all three fleet pyproject templates carry `branch = true`
   — so the conflict is resolved by the gate, which switches coverage
   collection off for the incremental run. See correction 7.
1. **Coverage collection must stay on, via pytest-cov.** testmon's
   `_get_nocollect_reasons` returns `[]` (collection active) when the
   `cov_plugin` is present, because testmon reuses pytest-cov's coverage
   instance. Do not switch to a bare `coverage.py` invocation — that path
   disables testmon collection.
1. **Crackerjack-owned data lives under `data_dir(app="crackerjack")`.**
   `data_dir(app="session-buddy")` is reserved for files session-buddy owns.
   A path that *is* XDG-resolved must be resolved when it is used, not
   captured at import time — a module-level constant freezes one
   resolution before the test session can redirect it, and the suite then
   writes into the developer's real data directory. (See Post-implementation
   correction 6.) The three paths that never used XDG at all are recorded
   as not-yet-implemented in the decision doc's Status section.
1. **No runtime `pip install` / `uv pip install` in library code.**
1. **pytest exit code 5 ("no tests collected") is a failure**, in an
   incremental run as much as in a full one. (See Post-implementation
   correction 1: under testmon, the exit code that reaches the caller
   discriminates "everything was deselected" (0) from "pytest collected
   nothing" (5), and the empty *result set* is the signal that says the
   change affects no test.)
1. **Recording run state must never fail a test run.** The store is a side
   effect; a store error logs a warning and is swallowed.
1. Pre-1.0 — direct commit to local `main`, no PR. No push without explicit
   operator approval.

## Post-implementation corrections

Things the plan assumed, and the implementation found otherwise. Each
is recorded here because the plan is the tracked spec of record: a reader
who takes it at face value would rely on a premise that does not hold.

**Correction 1 — pytest exit code 5 means "pytest collected nothing",
which is a failure, not a pass.** Global Constraint 6 and Review Focus
item 1 are both written around pytest exiting 5 when every test is
deselected. In `--testmon` select mode testmon empties the collected
item list, so pytest computes `testscollected == 0` and *would* exit 5.
But testmon's own `pytest_sessionfinish` hook rewrites that status:

```python
def pytest_sessionfinish(self, session, exitstatus):
    if len(self.deselected_tests) and exitstatus == ExitCode.NO_TESTS_COLLECTED:
        session.exitstatus = ExitCode.OK
```

The rewrite is conditional on testmon having **actually deselected
something**. Measured on this tree:

| Case | Exit | Meaning |
|---|---|---|
| testmon deselected every test | 0 | the change affects nothing — a pass |
| pytest collected nothing at all | 5 | the test configuration is broken — a failure |

So the exit code that reaches the caller discriminates the two cases,
and it discriminates them the *other way round* from what this plan
originally assumed. Exit 5 in an incremental run means the collection
found nothing — a misconfigured test suite — and reporting that as a
green run is a fail-open. The "nothing was affected" case is detected
from the empty *result set* instead: `load_pytest_json_report` carries
an `available` flag so a report that legitimately contains no tests is
distinguishable from one that could not be read.

**Correction 2 — an incremental run's coverage is partial, and must not
be compared to a full-suite baseline.** This plan made the incremental
path work for the first time: before it, the selection shell-out always
failed (the `snob` binary is not installed) so every run was a full-suite
run. A fully-deselected run writes `coverage.json` with
`percent_covered: 0.0`; the coverage ratchet compared that against the
full-suite baseline and reported a ~68-point regression that never
happened. The ratchet phase now skips an incremental run, with a message
saying why. The rule generalises: **any** consumer of a run's
*measurements* — coverage gates, ratchets, badges, "all tests passed"
summaries — must be gated on the run's mode, not on its exit code.

**Correction 3 — testmon requires pytest's `lfplugin`.** It is registered
by the `cacheprovider` plugin, so `-p no:cacheprovider` makes
`--testmon` die with an opaque `INTERNALERROR> KeyError: 'lf'`. Crackerjack
never passes that flag; the constraint is recorded so it stays that way.

**Correction 4 — the new code must obey the repo's own path-redaction
rule.** The store logged the absolute worktree path, and the test phase
logged the absolute store path on failure. Both name the OS account and
both land in log files on disk. Every path a message interpolates goes
through `crackerjack.utils.path_redaction` — including the traceback,
whose exception text names the path too, so the store-failure line
carries the exception *type* and no traceback.

**Correction 5 — each run's report file belongs to that run.** A shared
path let a report left behind by an earlier run — or by a run killed
before pytest wrote it — be read as the next run's result, and let two
concurrent runs read each other's. Each run writes its own
`.crackerjack/last-run-<uuid>.json`, reads back exactly that file, and
removes it once the run state is recorded. The fleet gitignore template
carries `.crackerjack/` so the file can never be committed.

**Correction 6 — a path that resolves must resolve when it is used.**
`crackerjack/cli/handlers/health.py` held the health snapshot database at
a module-level constant:

```python
DEFAULT_INTEGRATION_DB_PATH = data_dir("crackerjack") / "crackerjack_integration.db"
```

`data_dir` reads `XDG_DATA_HOME` on every call — its own docstring says
so, and says why: so a test can redirect it. A module-level constant
throws that away. The value is frozen during *collection*, before the
session-scoped fixture can set the environment, so the path is always the
developer's real one.

Measured on this tree, with the suite running from 04:16:27:

| File | Written at | Location |
|---|---|---|
| `~/.local/share/crackerjack/crackerjack_integration.db` | 04:19:08 | **the user's real data directory** |
| `<sandbox>/XDG_DATA_HOME/crackerjack/run_state.db` | during the run | the sandbox |

The run-state store was contained (it resolves through a Pydantic
`default_factory`, i.e. at instantiation). The health snapshot database
was not. The constant is replaced by `resolve_integration_db_path()`,
called at the point of use.

**Correction 7 — branch coverage is on in the fleet, so the gate has to
neutralise it rather than forbid it.** Global Constraint 3 said "branch
coverage is off in every Bodai repo today", and Task 1.6 added a guard
test that read `--cov-branch` out of the pytest `addopts` and failed if
it found it. The premise was wrong, and the guard was looking in the
wrong place:

- All three fleet pyproject templates (`pyproject-full.toml`,
  `pyproject-library.toml`, `pyproject-minimal.toml`) set
  `branch = true` under `[tool.coverage.run]`, and crackerjack's own
  pyproject has carried it since January 2026.
- The guard inspected `addopts`, which is where `--cov-branch` *would*
  appear if a project enabled branch coverage that way. The setting
  every repo actually uses is `[tool.coverage.run] branch = true`, and
  the guard never looked there.

So the conflict was live in every repo, and it was invisible to the
guard. It surfaced on 2026-11-07, when the gate's test phase died with:

```
INTERNALERROR> testmon.testmon_core.TestmonException: testmon doesn't support
INTERNALERROR> simultaneous run with pytest-cov when branch coverage is on.
INTERNALERROR> Please disable branch coverage.
```

pytest reports that as an INTERNALERROR (exit 3), which with `-n auto`
surfaces as xdist's "Unexpectedly no active workers available" — a
failed run that executed **zero** tests and looked like a timeout.

The resolution is in the gate, not in the projects:

- pytest-cov 7.1 offers `--cov-branch` to turn branch coverage *on* and
  nothing to turn it off, so a project that enables it in its coverage
  config puts testmon in branch mode and there is no flag that escapes
  it. The only remaining lever is to replace the coverage config file
  wholesale via `--cov-config`, which would silently drop every other
  coverage setting the project has.
- `--no-cov` does escape it, because pytest-cov then registers its
  plugin but never starts it, and testmon's branch check is guarded by
  `cov_plugin._started` (`testmon/testmon_core.py:522`). testmon builds
  its own `Coverage(config_file=False)` for the dependency map, so
  selection still works.

The incremental run therefore carries `--no-cov` and no coverage flag of
its own, and the full run keeps the project's own coverage configuration
— branch coverage included. Nothing measurable is lost: an incremental
run covers only the code its selected tests touch, and the coverage
ratchet already skips incremental runs (correction 2), so that number
was never a measurement.

The guard test is replaced by one that pins the resolution —
`test_the_incremental_run_disables_coverage_collection` and
`test_the_full_run_keeps_coverage_collection` in
`tests/unit/test_testmon_compatibility.py`.

## Review Focus

Five failure modes the design implies but no happy-path test exercises.
Each is pinned by a test named in the owning task.

1. **All tests deselected.** A change touching only non-Python files, or a
   `.testmondata` whose tracked sources all changed, yields an empty
   selection. A reasonable person expects "no tests affected" to be a
   *pass*.
   → `test_an_empty_selection_is_reported_plainly` in
   `tests/managers/test_incremental_coverage_semantics.py`.
   (Post-implementation correction 1: the signal is the empty *result
   set*, not the exit code — testmon rewrites the exit code 5 that an
   empty selection would produce, so a 5 reaching the caller means pytest
   collected nothing at all, which is a failure.)
1. **Branch coverage enabled.** testmon raises `TestmonException` in
   branch mode and the whole test phase dies with an opaque error.
   Expected: the incremental run neutralises it, so the phase still runs.
   → Task 1.6, `test_the_incremental_run_disables_coverage_collection`
   and `test_the_full_run_keeps_coverage_collection`.
1. **First run after install.** `.testmondata` does not exist yet, so testmon
   must run the *full* suite and write the data file. A reasonable person
   expects a complete first run, not an empty one.
   → Task 1.6, `test_first_run_without_testmondata_runs_full_suite`.
1. **Two worktrees, one repo.** `.testmondata` is per-checkout. A change made
   in worktree A must not cause worktree B to skip tests it never touched.
   Expected: each checkout keeps its own dependency data, and the shared
   store distinguishes runs by worktree path.
   → Task 2.2, `test_runs_from_different_worktrees_are_distinct`.
1. **Stale store rows.** The store accumulates rows across commits. A query
   for "status at commit X" must not return rows from commit Y. Expected:
   commit SHA is part of the key, and a query for a commit with no recorded
   run returns an explicit "no recorded run" rather than an empty result
   that looks like success.
   → Task 2.2, `test_get_run_returns_none_for_unknown_commit`.

______________________________________________________________________

# Phase 1 — Replace the snob shell-out with pytest-testmon

## Context

`crackerjack/managers/test_command_builder.py:58` (`_get_incremental_tests`)
shells out to `["snob"]` (`:93-99`) feeding it the output of
`git diff --name-only HEAD~10`, then passes the resulting paths to pytest.
This path is a **silent no-op today**: the `snob` CLI is not on PATH
(`which snob` → not found), the `FileNotFoundError` handler returns `None`,
and `None` means "run the full suite".

The dependency was already removed: `crackerjack/pyproject.toml:187-194`
declares `snob = []`, an **empty** group whose comment block still advertises
`"pytest-snob + its Rust extension snob-lib"` and
`"Install via: uv sync --group snob"`. That instruction installs nothing.
`uv.lock` has no `pytest-snob` / `snob-lib` / `snob` entry, and neither the
crackerjack venv nor this machine has the `snob` binary.

`crackerjack/test_selection.py` is a 420-line pytest-testmon integration that
is **imported by nothing** in `crackerjack/crackerjack/`. It also contains a
stub (`_parse_testmon_data` at `:173-180` always returns `{}`) and a runtime
`pip install` (`install_testmon` at `:406`). It is superseded by this phase.

## Design

Stop computing the test list in crackerjack. Pass `--testmon` to pytest and
let testmon deselect at collection time using its own `.testmondata`
dependency map.

This is strictly better than the snob shape:

- no external binary to install or keep in sync
- no `git diff HEAD~10` heuristic — testmon tracks file *content* changes
- testmon reuses pytest-cov's coverage instance, so the dependency map costs
  no additional tracing
- `.testmondata` also accumulates per-test average durations
  (`testmon/db.py:142-192`), a second reusable baseline artifact

The separate `snob_tests` DAG phase exists only to shell out to `snob` and
run the resulting subset. With testmon, the `tests` phase is already
incremental, so the phase is removed.

## Integration Contract

**Integration Contract:**

- **Triggered from:** every crackerjack invocation that runs the `tests`
  phase, with incremental selection enabled (the default).
- **Returns to / updates:** `test_manager.run_tests()` returns `True` when
  pytest exits 0. Unchanged otherwise.
  (Superseded by Post-implementation correction 1: this contract originally
  said the phase returns `True` when pytest exits 5 under incremental
  selection. Exit 5 means pytest collected nothing — a broken test
  configuration — and reporting it as success turned a misconfigured suite
  into a green run. "Nothing was affected" is now detected from the empty
  result set, not the exit code.)
- **Demonstrable by:** with a `.testmondata` present and a change to one
  module, `crackerjack run -t` reports the deselected count and runs only
  the affected tests.
- **Rollback signal:** pytest reports "no tests ran" (exit 5) during a
  *full* invocation of a non-empty suite — the deselection logic is
  over-eager.
- **Observability added:** a `logger.info` recording selected/deselected
  counts and the `.testmondata` path in use.

## Tasks

### Task 1.1 — Declare pytest-testmon; delete the stale `snob` group

**Files:**

- Modify: `crackerjack/pyproject.toml:78-82` (`[project].dependencies`)
- Modify: `crackerjack/pyproject.toml:187-194` (delete the `snob` group)
- Test: `tests/unit/test_pyproject_dependencies.py` (create)

**Interfaces:**

- Consumes: nothing.

- Produces: `[project].dependencies` contains an entry starting with
  `"pytest-testmon>=2.2.0"`; `[dependency-groups]` has no `snob` key.

- [ ] **Step 1: Write the failing tests**

```python
def test_pytest_testmon_is_a_main_dependency():
    data = tomllib.loads(Path("pyproject.toml").read_text())
    assert any(
        d.startswith("pytest-testmon>=2.2.0") for d in data["project"]["dependencies"]
    )


def test_no_snob_dependency_group():
    data = tomllib.loads(Path("pyproject.toml").read_text())
    assert "snob" not in data["dependency-groups"]
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/unit/test_pyproject_dependencies.py -v`
Expected: FAIL — `pytest-testmon` absent, `snob` group present.

- [ ] **Step 3: Implement**

Add `"pytest-testmon>=2.2.0",` to `[project].dependencies` between
`"pytest-cov>=7.1.0",` and `"pytest-timeout>=2.4.0",`. Delete the
`# snob group:` comment block through `snob = []` (lines 187-194).

- [ ] **Step 4: Run to verify they pass**

Run: `pytest tests/unit/test_pyproject_dependencies.py -v`
Expected: PASS.

- [ ] **Step 5: Refresh the lockfile**

Run: `uv lock` then `rg -n "pytest-testmon" uv.lock`
Expected: the lockfile lists `pytest-testmon` and no `snob-lib`.

- [ ] **Step 6: Commit**

```bash
git add crackerjack/pyproject.toml tests/unit/test_pyproject_dependencies.py uv.lock
git commit --only crackerjack/pyproject.toml tests/unit/test_pyproject_dependencies.py uv.lock -m "build(deps): replace the snob dependency group with pytest-testmon"
```

### Task 1.2 — Replace the snob subprocess with `--testmon`

**Files:**

- Modify: `crackerjack/managers/test_command_builder.py:58-129`
  (`_get_incremental_tests` — delete)
- Modify: `crackerjack/managers/test_command_builder.py:131-159`
  (`build_command`)
- Test: `tests/managers/test_test_command_builder.py` (create)

**Interfaces:**

- Consumes: `options.incremental_tests: bool` (existing,
  `crackerjack/cli/options.py:149`).

- Produces: `TestCommandBuilder.build_command(options) -> list[str]` appends
  `"--testmon"` when `getattr(options, "incremental_tests", True)` is truthy.
  `_get_incremental_tests` no longer exists.

- [ ] **Step 1: Write the failing tests**

```python
def test_build_command_includes_testmon_when_incremental():
    cmd = TestCommandBuilder().build_command(SimpleNamespace(incremental_tests=True))
    assert "--testmon" in cmd


def test_build_command_omits_testmon_when_full():
    cmd = TestCommandBuilder().build_command(SimpleNamespace(incremental_tests=False))
    assert "--testmon" not in cmd
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/managers/test_test_command_builder.py -v`
Expected: FAIL — `--testmon` not in the command.

- [ ] **Step 3: Implement**

Delete `_get_incremental_tests`. In `build_command`, immediately after
`cmd = ["uv", "run", "python", "-m", "pytest"]`, append `"--testmon"` when
`getattr(options, "incremental_tests", True)`. Remove the
`if incremental_tests is not None:` branch and its empty-list
`["pytest", "--collect-only", "--co-quiet"]` return, and the trailing
`if incremental_tests is None: self._add_test_path(cmd)`.

- [ ] **Step 4: Run to verify they pass**

Run: `pytest tests/managers/test_test_command_builder.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crackerjack/managers/test_command_builder.py tests/managers/test_test_command_builder.py
git commit --only crackerjack/managers/test_command_builder.py tests/managers/test_test_command_builder.py -m "feat(tests): select affected tests via pytest-testmon instead of the snob CLI"
```

### Task 1.3 — Treat pytest exit code 5 as a failure

> **Superseded by Post-implementation correction 1.** This task originally
> read "Treat pytest exit code 5 as success", on the premise that testmon
> surfaces exit 5 when it deselects every test. It does the opposite: it
> rewrites that exit code to 0, and lets 5 through only when pytest
> collected *nothing*. The task text is kept for the record, with the
> corrected behaviour below.

**Files:**

- Modify: `crackerjack/managers/test_manager.py:280-301`
  (`_run_pytest_if_needed`)
- Test: `tests/managers/test_test_manager_exit_codes.py` (create)

**Interfaces:**

- Consumes: `subprocess.CompletedProcess.returncode`;
  `options.incremental_tests`.

- Produces: `_run_pytest_if_needed` returns `False` for `returncode == 5`
  in every mode; the "change affects no test" case is signalled by an
  empty *result set*, not by the exit code.

- [ ] **Step 1: Write the failing tests**

```python
def test_exit_code_five_is_failure_when_incremental():
    # _execute_test_workflow patched to return CompletedProcess(returncode=5)
    assert (
        manager._run_pytest_if_needed(
            True, SimpleNamespace(incremental_tests=True), 0.0
        )
        is False
    )


def test_exit_code_five_is_failure_when_not_incremental():
    assert (
        manager._run_pytest_if_needed(
            True, SimpleNamespace(incremental_tests=False), 0.0
        )
        is False
    )
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/managers/test_test_manager_exit_codes.py -v`
Expected: FAIL — the incremental case currently falls into the success
branch.

- [ ] **Step 3: Implement**

In `_run_pytest_if_needed`, an exit code of 5 falls through to
`_handle_test_failure` in both modes. The "nothing was affected" case is
detected from the observed test count:

```python
if result.returncode == 0 and incremental and observed_tests == 0:
    logger.info("No tests affected by recent changes; skipping test execution")
    return True
```

- [ ] **Step 4: Run to verify they pass**

Run: `pytest tests/managers/test_test_manager_exit_codes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crackerjack/managers/test_manager.py tests/managers/test_test_manager_exit_codes.py
git commit --only crackerjack/managers/test_manager.py tests/managers/test_test_manager_exit_codes.py -m "fix(tests): treat pytest exit code 5 as a failure, in incremental runs too"
```

### Task 1.4 — Remove the `snob_tests` phase and the dead `no_snob` checks

**Files:**

- Modify: `crackerjack/runtime/oneiric_workflow.py:291-295` (phase
  registration), `:372-373` (step append)
- Modify: `crackerjack/core/phase_coordinator.py:529-625`
  (`run_snob_tests_phase`, `_get_snob_affected_tests` — delete)
- Modify: `crackerjack/core/phase_coordinator.py:530`,
  `crackerjack/runtime/oneiric_workflow.py:372` (the `no_snob` `getattr`
  checks — delete)
- Modify: `tests/core/test_plan_index_sync_phase.py:62` (fixture
  key `"no_snob": False`)

**Interfaces:**

- Consumes: nothing.

- Produces: `"snob_tests"` never appears in the workflow step list;
  `PhaseCoordinator.run_snob_tests_phase` and
  `PhaseCoordinator._get_snob_affected_tests` no longer exist.

- [ ] **Step 1: Write the failing test**

```python
def test_snob_tests_step_not_in_workflow_steps():
    steps = build_workflow_steps(options_with_fast_hooks_enabled())
    assert "snob_tests" not in steps
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/core/test_workflow_orchestrator.py -v`
Expected: FAIL — `"snob_tests"` is present.

- [ ] **Step 3: Implement**

Delete the `snob_tests` entries from the phase-task registry in
`oneiric_workflow.py` and the `steps.append("snob_tests")` block. Delete
`run_snob_tests_phase` and `_get_snob_affected_tests` from
`phase_coordinator.py`. Remove the `"no_snob"` key from the test fixture.

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/core/ tests/runtime/ -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crackerjack/runtime/oneiric_workflow.py crackerjack/core/phase_coordinator.py tests/core/test_plan_index_sync_phase.py
git commit --only crackerjack/runtime/oneiric_workflow.py crackerjack/core/phase_coordinator.py tests/core/test_plan_index_sync_phase.py -m "refactor(workflow): drop the snob_tests phase now that selection happens inside pytest"
```

### Task 1.5 — Delete the orphaned `crackerjack/test_selection.py`

**Files:**

- Delete: `crackerjack/test_selection.py`
- Delete: `tests/test_test_selection.py`

**Interfaces:**

- Consumes: nothing.

- Produces: no `crackerjack.test_selection` module exists.

- [ ] **Step 1: Confirm the module is orphaned**

Run: `rg -n "test_selection" crackerjack/ --type py`
Expected: matches only inside `crackerjack/test_selection.py` and
`tests/test_test_selection.py`.

- [ ] **Step 2: Delete both files**

- [ ] **Step 3: Run the suite to confirm nothing broke**

Run: `pytest crackerjack/tests -q --timeout=600`
Expected: PASS — no import or collection errors.

- [ ] **Step 4: Commit**

```bash
git add crackerjack/test_selection.py tests/test_test_selection.py
git commit --only crackerjack/test_selection.py tests/test_test_selection.py -m "refactor(tests): remove the orphaned test_selection module"
```

### Task 1.6 — Guard the testmon invariants

**Files:**

- Create: `tests/unit/test_testmon_compatibility.py`

**Interfaces:**

- Consumes: `crackerjack/pyproject.toml`
  `[tool.pytest.ini_options].addopts`.

- Produces: a test that fails if `--cov-branch` is enabled anywhere, and a
  test that fails if `pytest-testmon` is not installed.

- [ ] **Step 1: Write the tests**

```python
def test_no_branch_coverage_with_testmon():
    addopts = tomllib.loads(Path("pyproject.toml").read_text())["tool"]["pytest"][
        "ini_options"
    ]["addopts"]
    flat = " ".join(addopts) if isinstance(addopts, list) else addopts
    assert "--cov-branch" not in flat


def test_testmon_is_installed():
    assert importlib.metadata.version("pytest-testmon")


def test_first_run_without_testmondata_runs_full_suite(tmp_path):
    # Build a tiny suite in tmp_path with a source module and two tests;
    # run pytest --testmon with cwd=tmp_path and assert both tests ran.
    ...
```

- [ ] **Step 2: Run to verify the guard passes and the install check fails**

Run: `pytest tests/unit/test_testmon_compatibility.py -v`
Expected: the branch-coverage guard PASSES; `test_testmon_is_installed` FAILS
until the dependency is installed.

- [ ] **Step 3: Install the dependency**

Run: `uv sync`
Expected: `pytest-testmon` installs cleanly on Python 3.14 (pure-python wheel).

- [ ] **Step 4: Run to verify all pass**

Run: `pytest tests/unit/test_testmon_compatibility.py -v`
Expected: PASS.

- [ ] **Step 5: Verify testmon runs under pytest-cov**

Run: `uv run pytest --testmon -q --timeout=600`
Expected: PASS with no `TestmonException`, and a `.testmondata` file
appears in the repo root.

- [ ] **Step 6: Commit**

```bash
git add tests/unit/test_testmon_compatibility.py
git commit --only tests/unit/test_testmon_compatibility.py -m "test(selection): guard the testmon branch-coverage and first-run invariants"
```

______________________________________________________________________

# Phase 2 — Shared, commit-keyed test-run state

## Context

Phase 1 makes the *run* cheaper. It does not answer "what was the test
status of this repo at this commit?" — that still requires a run. Phase 2
makes the answer a query.

**What already exists (verified against the live system):**

- `session_buddy/crackerjack_integration.py:279-291` defines a `test_results`
  table with the right columns: `test_name`, `status`, `duration`,
  `file_path`, `line_number`, `error_message`, `timestamp`, FK to
  `crackerjack_results(id)`.
- The live `~/.local/share/session-buddy/crackerjack_integration.db` holds
  **1357** rows in `crackerjack_results`, **2572** in
  `quality_metrics_history`, and **0** in `test_results`.
- **Root cause of the zero:** `session_buddy/utils/crackerjack/output_parser.py:109-139`
  extracts per-test rows with a regex
  `(\w+\.py)::\s*(\w+)\s*(PASSED|FAILED|SKIPPED|ERROR|XFAIL|XPASS)\s*(?:\[(\d+%)\])?\s*(?:\((.+)\))?`.
  `\w+` cannot cross `/` or `::`, so `tests/unit/test_x.py::TestClass::test_m[param]`
  does not match; and the pattern expects a coverage/timing group that
  pytest's default reporter does not print. All 400 rows with non-empty
  `parsed_data` contain `"test_results": []`.
- **Root cause of the fake rows:** the `crackerjack_results` contents are
  almost entirely synthetic. **0** rows have a command containing "run";
  547 have `working_directory = "."`; 64 use paths like
  `/nonexistent/path/to/project`. Session-buddy's own test suite is writing
  fixtures into the live production database.
- **Root cause of the worktree gap:** the store only captures runs that
  session-buddy itself launched. A developer running `crackerjack run`
  directly in a worktree — the normal path, and the merge-gate path —
  records nothing.
- **Root cause of the "at commit X" gap:** the schema has no commit SHA.
  `working_directory` is the only locality key.

## Design

1. **Crackerjack writes the results itself**, on every run, regardless of who
   invoked it. Crackerjack owns its data: `data_dir(app="crackerjack")`, per
   `docs/decisions/2026-11-06-cj-xdg-namespace-and-state-paths.md`.
1. **The store gains `commit_sha` and `worktree`**, so a run is addressable by
   `(repo, commit_sha, worktree)`.
1. **Per-test results come from pytest's JSON report**, not from a regex over
   terminal output. The regex is the bug that produced 0 rows.
1. **Session-buddy stops being written by crackerjack** (the XDG collision),
   and reads crackerjack's store instead.

**New module:** `crackerjack/services/testing/run_state_store.py`

```python
class RunStateStore:
    def __init__(self, db_path: Path) -> None: ...
    def record_run(
        self,
        *,
        repo: str,
        commit_sha: str,
        worktree: str,
        branch: str | None,
        started_at: datetime,
        finished_at: datetime,
        exit_code: int,
        selection_mode: str,
        tests: list[dict[str, Any]],
    ) -> str: ...
    def get_run(
        self, repo: str, commit_sha: str, worktree: str | None = None
    ) -> dict[str, Any] | None: ...
    def get_test_results(self, run_id: str) -> list[dict[str, Any]]: ...
```

**Schema** (crackerjack-owned, `~/.local/share/crackerjack/run_state.db`):

```sql
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    repo TEXT NOT NULL,
    commit_sha TEXT NOT NULL,
    worktree TEXT NOT NULL,
    branch TEXT,
    started_at TIMESTAMP NOT NULL,
    finished_at TIMESTAMP,
    exit_code INTEGER,
    selection_mode TEXT NOT NULL,
    total INTEGER, passed INTEGER, failed INTEGER,
    skipped INTEGER, errors INTEGER, duration REAL
);
CREATE TABLE IF NOT EXISTS test_results (
    run_id TEXT NOT NULL,
    node_id TEXT NOT NULL,
    status TEXT NOT NULL,
    duration REAL,
    file_path TEXT,
    error_message TEXT,
    PRIMARY KEY (run_id, node_id),
    FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);
```

## Integration Contract

**Integration Contract:**

- **Triggered from:** every crackerjack `tests` phase completion, full or
  incremental.
- **Returns to / updates:** nothing in the return path — recording is a side
  effect that never fails a run.
- **Demonstrable by:** run `crackerjack run -t` in a worktree, then
  `crackerjack run-state show --commit <sha>` prints the per-test status for
  that commit without re-running any test.
- **Rollback signal:** the store file grows without bound, or a query for one
  commit returns rows whose `commit_sha` differs from the requested one.
- **Observability added:** a `logger.info` per recorded run carrying the run
  id, commit, and test counts; a `logger.warning` if recording fails.

## Tasks

### Task 2.1 — Capture structured results with pytest-json-report

**Files:**

- Modify: `crackerjack/pyproject.toml` (`[project].dependencies`) — add
  `"pytest-json-report>=1.5.0",`
- Modify: `crackerjack/managers/test_command_builder.py` — add the report
  flags
- Test: `tests/managers/test_test_command_builder.py` (extend)

**Interfaces:**

- Consumes: `options.incremental_tests` (existing).

- Produces: `build_command()` includes `"--json-report"` and a
  `"--json-report-file=<path>"` argument.
  `TestCommandBuilder.get_json_report_path() -> Path` returns
  `<project root>/.crackerjack/last-run.json`.

- [ ] **Step 1: Write the failing test**

```python
def test_build_command_includes_json_report():
    cmd = TestCommandBuilder().build_command(SimpleNamespace(incremental_tests=True))
    assert "--json-report" in cmd
    assert any(a.startswith("--json-report-file=") for a in cmd)
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/managers/test_test_command_builder.py -v`
Expected: FAIL — no JSON report flags.

- [ ] **Step 3: Implement**

Add the dependency, add `--json-report` and
`f"--json-report-file={self.get_json_report_path()}"` to the command, and add
`get_json_report_path()`.

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/managers/test_test_command_builder.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crackerjack/pyproject.toml crackerjack/managers/test_command_builder.py tests/managers/test_test_command_builder.py uv.lock
git commit --only crackerjack/pyproject.toml crackerjack/managers/test_command_builder.py tests/managers/test_test_command_builder.py uv.lock -m "feat(tests): capture structured pytest results with pytest-json-report"
```

### Task 2.2 — Create the run-state store

**Files:**

- Create: `crackerjack/services/testing/run_state_store.py`
- Test: `tests/services/test_run_state_store.py` (create)

**Interfaces:**

- Consumes: `db_path: Path`.

- Produces: the `RunStateStore` class and the four methods listed in the
  Design section. `record_run` returns the new run id. `get_run` returns
  `None` when no run matches — never an empty dict.

- [ ] **Step 1: Write the failing tests**

```python
def test_record_run_then_get_run_roundtrips(tmp_path):
    store = RunStateStore(tmp_path / "run_state.db")
    run_id = store.record_run(
        repo="crackerjack",
        commit_sha="abc123",
        worktree="/w",
        branch="main",
        started_at=now,
        finished_at=now,
        exit_code=0,
        selection_mode="full",
        tests=[
            {
                "node_id": "tests/test_a.py::t1",
                "status": "passed",
                "duration": 0.1,
                "file_path": "tests/test_a.py",
            }
        ],
    )
    run = store.get_run(repo="crackerjack", commit_sha="abc123")
    assert run["id"] == run_id
    assert run["total"] == 1
    assert store.get_test_results(run_id)[0]["node_id"] == "tests/test_a.py::t1"


def test_runs_from_different_worktrees_are_distinct(tmp_path): ...
def test_get_run_returns_none_for_unknown_commit(tmp_path): ...
```

- [ ] **Step 2: Run to verify they fail**

Run: `pytest tests/services/test_run_state_store.py -v`
Expected: FAIL — module does not exist.

- [ ] **Step 3: Implement**

Follow the conventions in `crackerjack/mcp/persistence.py`: SQLite, `PRAGMA journal_mode=WAL`, `PRAGMA synchronous=NORMAL`, and all DB access through
`loop.run_in_executor` for the async callers.

- [ ] **Step 4: Run to verify they pass**

Run: `pytest tests/services/test_run_state_store.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crackerjack/services/testing/run_state_store.py tests/services/test_run_state_store.py
git commit --only crackerjack/services/testing/run_state_store.py tests/services/test_run_state_store.py -m "feat(state): add the commit-keyed run-state store"
```

### Task 2.3 — Wire the store into the tests phase

**Files:**

- Modify: `crackerjack/managers/test_manager.py` (`_run_pytest_if_needed`)
- Modify: `crackerjack/config/settings.py` — add `RunStateSettings` with
  `storage_path: Path = data_dir("crackerjack") / "run_state.db"`
- Test: `tests/managers/test_test_manager_exit_codes.py` (extend)

**Interfaces:**

- Consumes: `RunStateStore.record_run(...)` (Task 2.2);
  `TestCommandBuilder.get_json_report_path()` (Task 2.1).

- Produces: after every pytest run, one `runs` row and N `test_results` rows
  exist.

- [ ] **Step 1: Write the failing test**

```python
def test_test_phase_records_run_state(tmp_path, monkeypatch):
    # point settings.run_state.storage_path at tmp_path; run the phase;
    # assert the store has one runs row and the expected test_results rows.
    ...
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/managers/test_test_manager_exit_codes.py -v`
Expected: FAIL — nothing is recorded.

- [ ] **Step 3: Implement**

After `_execute_test_workflow` returns, parse the JSON report, resolve
`commit_sha` via `git rev-parse HEAD` and `branch` via
`git rev-parse --abbrev-ref HEAD`, and call `record_run`. Wrap the whole
recording block in `try/except Exception` that logs a warning and does not
re-raise.

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/managers/test_test_manager_exit_codes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crackerjack/managers/test_manager.py crackerjack/config/settings.py tests/managers/test_test_manager_exit_codes.py
git commit --only crackerjack/managers/test_manager.py crackerjack/config/settings.py tests/managers/test_test_manager_exit_codes.py -m "feat(state): record per-test run state on every test phase"
```

### Task 2.4 — Add the `run-state` CLI surface

**Files:**

- Modify: `crackerjack/cli/options.py`
- Modify: `crackerjack/cli/handlers/` (new `run_state.py`)
- Modify: `crackerjack/__main__.py` (command registration)
- Test: `tests/cli/test_run_state_cli.py` (create)

**Interfaces:**

- Consumes: `RunStateStore.get_run` / `get_test_results` (Task 2.2).

- Produces: `crackerjack run-state show [--repo NAME] [--commit SHA] [--worktree PATH]` prints a per-test table; `crackerjack run-state diff --base SHA` prints the tests whose status changed relative to the base
  commit. `show` prints an explicit "no recorded run for <sha>" when the
  commit has no row.

- [ ] **Step 1: Write the failing test**

```python
def test_run_state_show_reports_no_recorded_run(tmp_path, capsys):
    # assert the output contains "no recorded run"
    ...
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/cli/test_run_state_cli.py -v`
Expected: FAIL — the command does not exist.

- [ ] **Step 3: Implement**

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/cli/test_run_state_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crackerjack/cli/options.py crackerjack/cli/handlers/ crackerjack/__main__.py tests/cli/test_run_state_cli.py
git commit --only crackerjack/cli/options.py crackerjack/cli/handlers/ crackerjack/__main__.py tests/cli/test_run_state_cli.py -m "feat(cli): add the run-state show and diff commands"
```

### Task 2.5 — Resolve the XDG collision

**Files:**

- Modify: `crackerjack/cli/handlers/health.py:189-204` (the `data_dir()`
  default)
- Modify: `crackerjack/utils/xdg_paths.py` (default app name)
- Test: `tests/cli/handlers/test_health.py` (create or extend)

**Interfaces:**

- Consumes: `crackerjack.utils.xdg_paths.data_dir`.

- Produces: crackerjack's health snapshot database resolves under
  `~/.local/share/crackerjack/`, never under `~/.local/share/session-buddy/`.

- [ ] **Step 1: Write the failing test**

```python
def test_health_snapshot_db_is_crackjack_owned():
    assert "session-buddy" not in str(resolve_health_db_path())
    assert "crackerjack" in str(resolve_health_db_path())
```

- [ ] **Step 2: Run to verify it fails**

Run: `pytest tests/cli/handlers/test_health.py -v`
Expected: FAIL — the path still resolves under `session-buddy`.

- [ ] **Step 3: Implement**

Change the default app name in `xdg_paths.data_dir` to `"crackerjack"` and
pass `app="crackerjack"` explicitly at the health-handler call site. Follow
the decision doc's rule that `data_dir(app="session-buddy")` is only for
files session-buddy owns.

- [ ] **Step 4: Run to verify it passes**

Run: `pytest tests/cli/handlers/test_health.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crackerjack/cli/handlers/health.py crackerjack/utils/xdg_paths.py tests/cli/handlers/test_health.py
git commit --only crackerjack/cli/handlers/health.py crackerjack/utils/xdg_paths.py tests/cli/handlers/test_health.py -m "fix(xdg): resolve crackerjack's integration database under its own app name"
```

### Task 2.6 — Sync the plan index

**Files:**

- Modify: `crackerjack/docs/plans/PLAN_INDEX.md`

**Interfaces:**

- Consumes: nothing.

- Produces: the plan index lists this plan.

- [ ] **Step 1: Run the plan-index sync phase**

Run: `crackerjack run --plan-index-sync` (or the equivalent the
`plan_index_sync` phase invokes)
Expected: `PLAN_INDEX.md` lists `2026-11-06-test-selection-and-run-state`.

- [ ] **Step 2: Verify**

Run: `rg -n "test-selection-and-run-state" crackerjack/docs/plans/PLAN_INDEX.md`
Expected: one match.

- [ ] **Step 3: Commit**

```bash
git add crackerjack/docs/plans/PLAN_INDEX.md
git commit --only crackerjack/docs/plans/PLAN_INDEX.md -m "docs(plans): index the test-selection and run-state plan"
```

______________________________________________________________________

# Out of Scope

1. **OTel per-test spans.** `opentelemetry-instrumentation-pytest` does not
   exist on PyPI (404 on the JSON API) and is absent from the
   opentelemetry-python-contrib tree; the two third-party options are
   `pytest-opentelemetry` (chrisguidry, v1.1.0, ~38 stars) and `pytest-otel`
   (older, weaker). Crackerjack has no `opentelemetry` dependency today, so
   pytest emits no spans. OTel spans answer *"why is this test slow, and
   which application spans did it touch"* — a different question from *"what
   was the status at commit X"*.
   `mahavishnu/mahavishnu/ingesters/otel_ingester.py` (DuckDB via Akosha
   HotStore, or PostgreSQL + pgvector, with embeddings for semantic search)
   is a **search** substrate, not a keyed status table — embedding every test
   span to answer "is commit abc123 green" would be the wrong trade.
   Revisit as a Phase 3 if flaky-test diagnosis becomes the priority.
1. **`pytest-split` / `pytest-shard`.** Worth a follow-up: testmon's
   `.testmondata` already accumulates `avg_durations` per test, which is the
   same artifact `pytest-split` needs for duration-balanced shards — the two
   compose. Sharding is a CI concern, not a local-worktree one.
1. **`diff-cover`.** Independent and cheap:
   `diff-cover coverage.xml --compare-branch=origin/main --fail-under=X`
   answers patch coverage against a base branch with no separate baseline
   run. Separate small change.
1. **Rolling this out to mahavishnu, session-buddy, and mcp-common.** This
   plan is crackerjack-first by decision. The store's schema and the
   `run-state` CLI are the reusable artifacts.
1. **The stale snob references in mahavishnu** —
   `BODAI_UPGRADE_WATCH.md:51` and
   `docs/adr/016-phase-4-streaming-tar-evolution.md:46,129,138` describe a
   fastblocks blocker that no longer exists: fastblocks has zero snob
   references in `pyproject.toml`, `uv.lock`, source, or docs. Separate
   documentation cleanup.

# Follow-up plan — session-buddy (different repository)

This plan is crackerjack-only. Two session-buddy defects are *adjacent* to it
and must not block it, but they are the reason the shared store has never
worked. They belong in a separate plan in the session-buddy repo,
`docs/plans/2026-11-06-crackerjack-run-state-reader.md`:

1. **Fix the `pytest_result` regex** in
   `session_buddy/utils/crackerjack/output_parser.py:109-139`. The current
   pattern cannot match `tests/unit/test_x.py::TestClass::test_method[param]`
   and expects coverage/timing groups pytest's default reporter does not
   print. The replacement should consume pytest's JSON report instead of
   scraping terminal output — the same source Phase 2 uses.
1. **Stop the test suite writing into the live database.** Fixtures are
   creating rows in `~/.local/share/session-buddy/crackerjack_integration.db`
   with `working_directory` values like `/nonexistent/path/to/project`. The
   integration's `db_path` must be overridable and the fixtures must point
   at `tmp_path`.
1. **Read crackerjack's new store.** Add a reader for
   `~/.local/share/crackerjack/run_state.db` so session-buddy's
   `crackerjack_history` and `analyze_crackerjack_test_patterns` tools report
   real per-test history instead of counting `"success"` occurrences in
   conversation prose.

# Verification

| Check | Command | Expected |
|---|---|---|
| testmon is a main dependency | `rg -n "pytest-testmon" crackerjack/pyproject.toml` | one match in `[project].dependencies` |
| no snob group remains | `rg -n "snob" crackerjack/pyproject.toml` | only the comment explaining the replacement |
| no snob execution code remains | `rg -n "snob" crackerjack/crackerjack/` | only the creosote known-plugin exclusion and the docstring documenting it |
| creosote sees no unused dependency | `creosote --venv .venv -p crackerjack --include-deferred` | "No unused dependencies found!" |
| branch coverage stays off | `rg -n "cov-branch" crackerjack/pyproject.toml` | no matches |
| testmon runs under pytest-cov | `uv run pytest --testmon -q --timeout=600` | PASS, no `TestmonException` |
| exit code 5 is a pass | `pytest tests/managers/test_test_manager_exit_codes.py -v` | PASS |
| run state is recorded | `sqlite3 ~/.local/share/crackerjack/run_state.db "select count(*) from runs;"` | > 0 after a run |
| per-test rows exist | `sqlite3 ~/.local/share/crackerjack/run_state.db "select count(*) from test_results;"` | > 0 after a run |
| XDG collision resolved | `ls ~/.local/share/crackerjack/ ~/.local/share/session-buddy/` | the integration db is under the former only |
| full suite green | `uv run pytest -q --timeout=600` | PASS |

# Status

Active. Phase 1 is self-contained and unblocks incremental selection today.
Phase 2 is the part that removes the need to re-run a suite to re-establish a
baseline.
