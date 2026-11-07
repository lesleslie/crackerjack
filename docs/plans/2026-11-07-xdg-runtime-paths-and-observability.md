---
title: Move Crackerjack's remaining runtime data under the XDG base directories, surface the run-selection mode, and correct the stale snob references in Mahavishnu
description: Finishes the XDG namespace decision that the test-selection work started - the async task store, the health integration database, the AI-fix run history and the log directory all resolve outside XDG today, and three of them have legacy data stranded at the old path. Adds the aggregation that turns the already-recorded selection_mode into the answer to "how often is the incremental path taken", and corrects Mahavishnu's still-live claim that fastblocks is blocked by snob-lib on Python 3.14.
audience: crackerjack maintainer
created: 2026-11-07
status: complete
role: implementation
topic: testing-infrastructure
date: 2026-11-07
last_reviewed: 2026-11-07
superseded_by: null
blocks_on: []
---

# XDG Runtime Paths and Run-State Observability

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task.
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Every Crackerjack-owned runtime path resolves under the XDG
base directories, existing data at the old paths is migrated rather than
orphaned, and the run-state store answers "how often was the
incremental path taken" without a new metrics subsystem.

**Architecture:** One shared migration helper moves a legacy file or
directory's contents to its XDG home. Four call sites adopt it: the
async task store, the health integration database, the AI-fix run
history, and the log directory. The observability work reuses the
`selection_mode` column the store already records - no new metrics
registry, because a counter in a process that exits is weaker evidence
than a durable row.

**Tech Stack:** Python 3.14, Typer, SQLite, `pathlib`, `shutil`.

**Spec:** `docs/decisions/2026-11-06-cj-xdg-namespace-and-state-paths.md`
(the decision this implements).

## Global Constraints

1. **Python floor is 3.14.** `requires-python = ">=3.14"`, ruff
   `target-version = "py314"`.
1. **A path that resolves must resolve when it is used**, not captured
   at import time. A module-level constant freezes one resolution
   before the test session's `XDG_*` redirect can reach it, and the
   suite writes into the developer's real directory instead.
1. **A migration never destroys data.** Moving is one-way only when the
   target does not already exist; a target that exists is left alone,
   and a failed move leaves the legacy copy in place.
1. **No migration runs at import time.** Migrations happen where the
   path is opened, so importing a module never touches the filesystem.
1. **Every path a message interpolates goes through
   `crackerjack.utils.path_redaction`.**
1. **No `assert` in production code**; no `print()` in library code.
1. Pre-1.0 — direct commit to local `main`, no PR. **No push without
   explicit operator approval** (this plan's Task 8 is that approval).

## Review Focus

Five failure modes the design implies but no happy-path test exercises.

1. **The target already exists.** A migration must not overwrite a live
   database with a stale legacy copy.
1. **The move fails** (permissions, a locked file, a full disk). The
   legacy copy must survive and the run must continue.
1. **The legacy path is a symlink**, or points outside the expected
   tree. Following it blindly can move something the user did not mean.
1. **Two projects share one state directory.** The run history is
   user-scoped after the move; a run id from one project must not be
   restored as if it belonged to another.
1. **The selection mode is unknown.** A run recorded before the column
   existed, or by a caller that passes a mode the CLI does not know,
   must not crash the aggregate query.

---

## Task 1 — A shared legacy-path migration helper

**Files:**
- Create: `crackerjack/utils/legacy_paths.py`
- Test: `tests/unit/utils/test_legacy_paths.py`

**Interfaces:**
- Produces: `migrate_legacy_file(legacy: Path, target: Path) -> bool` and
  `migrate_legacy_dir(legacy: Path, target: Path) -> bool`. Both return
  `True` when something moved.

- [ ] **Step 1: Write the failing tests**

```python
def test_moves_a_legacy_file_when_the_target_is_absent(tmp_path):
    legacy = tmp_path / "old" / "db.sqlite"
    legacy.parent.mkdir(parents=True)
    legacy.write_bytes(b"payload")
    target = tmp_path / "new" / "db.sqlite"

    assert migrate_legacy_file(legacy, target) is True
    assert target.read_bytes() == b"payload"
    assert not legacy.exists()


def test_leaves_an_existing_target_alone(tmp_path):
    legacy = tmp_path / "old.sqlite"
    legacy.write_bytes(b"legacy")
    target = tmp_path / "new.sqlite"
    target.write_bytes(b"live")

    assert migrate_legacy_file(legacy, target) is False
    assert target.read_bytes() == b"live"
    assert legacy.exists()


def test_moves_directory_contents_and_merges(tmp_path):
    legacy = tmp_path / "old"
    (legacy / "run-a").mkdir(parents=True)
    (legacy / "run-a" / "events.jsonl").write_text("{}\n")
    target = tmp_path / "new"
    (target / "run-b").mkdir(parents=True)

    assert migrate_legacy_dir(legacy, target) is True
    assert (target / "run-a" / "events.jsonl").exists()
    assert (target / "run-b").is_dir()
```

Also: a move that fails returns `False` and leaves the legacy copy
intact; a legacy path that is a symlink is not followed.

- [ ] **Step 2: Run them to verify they fail**

Run: `pytest tests/unit/utils/test_legacy_paths.py -v`
Expected: FAIL — `crackerjack.utils.legacy_paths` does not exist.

- [ ] **Step 3: Implement**

`migrate_legacy_file`: return `False` when the legacy path is absent,
is not a regular file, is a symlink, or the target exists. Otherwise
create the target's parent and `shutil.move` it, returning `True` on
success and `False` on `OSError` (logged with the redacted paths).

`migrate_legacy_dir`: return `False` when the legacy path is absent or
is not a directory. Create the target, move each child that does not
already exist there, and remove the legacy directory if it is left
empty.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/unit/utils/test_legacy_paths.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add crackerjack/utils/legacy_paths.py tests/unit/utils/test_legacy_paths.py
git commit --only crackerjack/utils/legacy_paths.py tests/unit/utils/test_legacy_paths.py -m "feat(paths): add a shared legacy-to-XDG migration helper"
```

**Integration Contract:**
- **Triggered from:** wherever a runtime path is opened (Task 2-4).
- **Returns to / updates:** nothing; a migration is a side effect that
  never fails the caller.
- **Demonstrable by:** `pytest tests/unit/utils/test_legacy_paths.py`.
- **Rollback signal:** the helper is additive; removing the call sites
  leaves the migrated files where they are.
- **Observability added:** a `logger.info` per successful move (run id
  and file names, no absolute paths) and a `logger.warning` per failure.

---

## Task 2 — The async task store and the health integration database

**Files:**
- Modify: `crackerjack/config/settings.py:466-474` (`AsyncTaskSettings`)
- Modify: `crackerjack/mcp/server_core.py:166-183` (store construction)
- Modify: `crackerjack/cli/handlers/health.py:20` (integration DB path)
- Test: `tests/unit/utils/test_legacy_paths.py`, `tests/mcp/…` (new)

**Interfaces:**
- Consumes: `migrate_legacy_file` from Task 1.
- Produces: `AsyncTaskSettings.storage_path` defaults to
  `data_dir("crackerjack") / "async_tasks.db"`.

- [ ] **Step 1: Write the failing tests**

```python
def test_async_task_store_defaults_into_the_xdg_data_dir():
    settings = AsyncTaskSettings()
    assert settings.storage_path.parent.name == "crackerjack"
    assert settings.storage_path.name == "async_tasks.db"


def test_the_legacy_async_task_store_is_migrated(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
    legacy = Path.home() / ".crackerjack" / "state" / "async_tasks.db"
    # ... create the legacy file, construct the store, assert the data moved
```

- [ ] **Step 2: Run them to verify they fail**

Expected: FAIL — the default is still `~/.crackerjack/state/`.

- [ ] **Step 3: Implement**

Change the default to `data_dir("crackerjack") / "async_tasks.db"`. In
`server_core.py`, before constructing the store, call
`migrate_legacy_file(Path.home() / ".crackerjack" / "state" /
"async_tasks.db", settings.async_task.storage_path)`.

In `health.py`, the integration database resolves under
`data_dir("crackerjack")`; migrate the legacy
`data_dir("session-buddy") / "crackerjack_integration.db"` into it on
first use — 1.5 MB of quality history is currently stranded there.

- [ ] **Step 4: Run the tests to verify they pass**

- [ ] **Step 5: Commit**

```bash
git commit --only crackerjack/config/settings.py crackerjack/mcp/server_core.py crackerjack/cli/handlers/health.py tests/... -m "fix(xdg): move the async task store and migrate the legacy integration database"
```

**Integration Contract:**
- **Triggered from:** MCP server startup (async tasks); every health
  check (integration database).
- **Returns to / updates:** nothing.
- **Demonstrable by:** the legacy files are gone and the new ones hold
  the same rows.
- **Rollback signal:** the legacy file is moved, not copied; set the
  settings path back to the legacy location to keep using it.
- **Observability added:** a `logger.info` per migration.

---

## Task 3 — The AI-fix run history moves to `$XDG_STATE_HOME`

**Files:**
- Modify: `crackerjack/core/ai_fix_sinks.py:110,131-137,149-157,253-275`
- Modify: `crackerjack/core/autofix_coordinator.py:123`
- Modify: `crackerjack/cli/replay.py:96-108`
- Test: `tests/unit/core/test_pr0_crash_recovery.py`,
  `tests/unit/cli/test_pr0_replay.py`

**Interfaces:**
- Consumes: `migrate_legacy_dir` from Task 1.
- Produces: `runs_root(base_dir: Path | None) -> Path` in
  `crackerjack/core/ai_fix_sinks.py`.

- [ ] **Step 1: Write the failing tests**

```python
def test_runs_resolve_under_the_xdg_state_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    sink = JsonlSink()
    sink._open("run-1")
    assert (tmp_path / "crackerjack" / "runs" / "run-1" / "events.jsonl").exists()


def test_an_explicit_base_dir_still_works(tmp_path):
    sink = JsonlSink(base_dir=tmp_path)
    sink._open("run-1")
    assert (tmp_path / ".crackerjack" / "runs" / "run-1" / "events.jsonl").exists()
```

- [ ] **Step 2: Run them to verify they fail**

- [ ] **Step 3: Implement**

```python
def runs_root(base_dir: Path | None = None) -> Path:
    if base_dir is not None:
        return base_dir / ".crackerjack" / "runs"
    return state_dir("crackerjack") / "runs"
```

Use it in `JsonlSink._open`, `JsonlSink.restore_run`,
`detect_orphan_sidecars`, and `cli/replay.py`'s "Checked:" message.
Change `autofix_coordinator.py:123` from `build_default_bus(self.pkg_path)`
to `build_default_bus()` so production resolves under XDG. Migrate
`<project>/.crackerjack/runs/` into the state directory on first use.

- [ ] **Step 4: Run the tests to verify they pass**

- [ ] **Step 5: Commit**

```bash
git commit --only crackerjack/core/ai_fix_sinks.py crackerjack/core/autofix_coordinator.py crackerjack/cli/replay.py tests/... -m "feat(xdg): move the AI-fix run history under XDG_STATE_HOME"
```

**Integration Contract:**
- **Triggered from:** every AI-fix event bus construction; `crackerjack
  replay`.
- **Returns to / updates:** nothing.
- **Demonstrable by:** `crackerjack replay <run_id>` finds a run that
  `git clean -fd` can no longer destroy.
- **Rollback signal:** `crackerjack replay --base-dir <project>` still
  reads a project-local run directory.
- **Observability added:** a `logger.info` per migrated run directory.

---

## Task 4 — The log directory moves to `$XDG_STATE_HOME`

**Files:**
- Modify: `crackerjack/services/log_manager.py:26-51`
- Test: `tests/unit/services/test_log_manager.py` (new or existing)

**Interfaces:**
- Consumes: `migrate_legacy_dir` from Task 1.
- Produces: `LogManager.log_dir` resolves to
  `$XDG_STATE_HOME/crackerjack/logs`.

- [ ] **Step 1: Write the failing tests**

```python
def test_log_directory_resolves_under_the_xdg_state_home(monkeypatch, tmp_path):
    monkeypatch.setenv("XDG_STATE_HOME", str(tmp_path))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    manager = LogManager()
    assert manager.log_dir == tmp_path / "crackerjack" / "logs"
```

- [ ] **Step 2: Run them to verify they fail**

Expected: FAIL — the project-local `.crackerjack/logs` wins today, and
the XDG fallback is under *cache*, not *state*.

- [ ] **Step 3: Implement**

Put `$XDG_STATE_HOME/crackerjack/logs` first in the candidate chain and
keep the project-local path as a fallback for a checkout that cannot
write to the state directory. Migrate the project-local `logs/`
contents on first use.

- [ ] **Step 4: Run the tests to verify they pass**

- [ ] **Step 5: Commit**

```bash
git commit --only crackerjack/services/log_manager.py tests/... -m "feat(xdg): move the log directory under XDG_STATE_HOME"
```

**Integration Contract:**
- **Triggered from:** `LogManager.__init__`, which every logging setup
  constructs.
- **Returns to / updates:** nothing.
- **Demonstrable by:** the log files appear under
  `$XDG_STATE_HOME/crackerjack/logs/{debug,error,audit}`.
- **Rollback signal:** `XDG_STATE_HOME` pointed at a read-only path
  falls back to the project-local directory.
- **Observability added:** a `logger.info` per migrated log directory.

---

## Task 5 — The selection mode becomes answerable

**Files:**
- Modify: `crackerjack/services/testing/run_state_store.py` (aggregate
  query)
- Modify: `crackerjack/cli/run_state_cli.py` (`show` prints the mode;
  new `stats` command)
- Test: `tests/services/test_run_state_store.py`,
  `tests/cli/test_run_state_cli.py`

**Interfaces:**
- Produces: `RunStateStore.summarize(repo: str | None = None) -> dict[str, object]`
  returning `{"runs": int, "incremental": int, "full": int, "failed": int,
  "passed": int}`.
- Produces: `crackerjack run-state stats`.

- [ ] **Step 1: Write the failing tests**

```python
def test_summarize_counts_runs_by_selection_mode(store):
    # two incremental runs, one full run
    assert store.summarize()["incremental"] == 2
    assert store.summarize()["full"] == 1
```

and a CLI test that `run-state stats` prints the counts, and that
`run-state show` prints the selection mode of the run.

- [ ] **Step 2: Run them to verify they fail**

- [ ] **Step 3: Implement**

`summarize` is one `GROUP BY` over `runs`. `show` adds the mode to its
summary line. `stats` prints the counts. The ratchet-skip count needs
no separate record: the ratchet skips exactly when the run was
incremental, so `selection_mode = 'incremental'` *is* the skip count.

- [ ] **Step 4: Run the tests to verify they pass**

- [ ] **Step 5: Commit**

```bash
git commit --only crackerjack/services/testing/run_state_store.py crackerjack/cli/run_state_cli.py tests/... -m "feat(state): surface the run selection mode and aggregate it"
```

**Integration Contract:**
- **Triggered from:** `crackerjack run-state show` and
  `crackerjack run-state stats`.
- **Returns to / updates:** nothing.
- **Demonstrable by:** `crackerjack run-state stats` answers "how often
  was the incremental path taken" without a metrics subsystem.
- **Rollback signal:** the command is additive.
- **Observability added:** the store's existing `selection_mode` column
  becomes queryable.

---

## Task 6 — The records say what is true

**Files:**
- Modify: `docs/decisions/2026-11-06-cj-xdg-namespace-and-state-paths.md`
- Modify: `docs/feature-tracking/2026-11-06-test-selection-and-run-state.md`
- Modify: `docs/plans/PLAN_INDEX.md` (regenerated)

- [ ] **Step 1: Write the failing test**

The decision record has no test. The plan index does: regenerate it and
require the plan's row to be present with the expected status.

- [ ] **Step 2: Run it to verify it fails**

- [ ] **Step 3: Implement**

Update the decision record's Status section: rule 1 and rule 2 are now
implemented, the data migrations are done, and the remaining legacy
paths are named. Move the feature-tracking entry from `wired` to
`adopted`, with the observability that now exists and the transitions
table updated.

- [ ] **Step 4: Run it to verify it passes**

- [ ] **Step 5: Commit**

---

## Task 7 — Mahavishnu's stale snob references

**Files (in `/Users/les/Projects/mahavishnu`):**
- Modify: `BODAI_UPGRADE_WATCH.md:51`
- Modify: `docs/adr/016-phase-4-streaming-tar-evolution.md:46,129,138`

**Interfaces:**
- Consumes: nothing from this repo.

- [ ] **Step 1: Establish the facts**

`git log --all -S snob-lib` in the fastblocks checkout: `bd82e6b`
(2026-09-28) removed `pytest-snob` and `snob-lib` from the lock, and
fastblocks now declares `requires-python = ">=3.14"`. The blocker
recorded on 2026-08-23 no longer exists.

- [ ] **Step 2: Correct the records**

`BODAI_UPGRADE_WATCH.md` is a live status list: replace the bullet with
the resolution. The ADR is a point-in-time decision record: add a
resolution note rather than rewriting the history it captured.

- [ ] **Step 3: Commit**

Commit only those two files. **Do not run the quality gate over that
tree** - another session is actively working in it, and the gate scans
the whole tree and autofixes Python files that are not this change's.

---

## Task 8 — Push

**Files:** none.

- [ ] **Step 1: Confirm the gate passes on this branch**

Run: `crackerjack run -v -f`
Expected: 18/18 hooks, 0 issues.

- [ ] **Step 2: Confirm the full suite**

Run: `pytest -q`
Expected: the same failure count as the base commit, all pre-existing.

- [ ] **Step 3: Squash-merge into local `main`**

In a temporary worktree, so `git merge --squash` never stages into
another checkout's index.

- [ ] **Step 4: Push**

Run: `git push origin main`
The operator's approval is this plan's Task 8.
