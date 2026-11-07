---
status: wired
role: lifecycle
topic: testing-infrastructure
date: 2026-11-07
last_reviewed: 2026-11-07
superseded_by: null
blocks_on: []
---

# XDG Runtime Paths

## Summary

Every Crackerjack-owned runtime path resolves under the XDG base
directories, and the data already at the old paths is migrated rather
than stranded. The async task store moves into
`$XDG_DATA_HOME/crackerjack`, and the AI-fix run history and the log
directory into `$XDG_STATE_HOME/crackerjack`. This finishes the
namespace decision that the test-selection work started.

## Why

- **The test suite wrote into the developer's real home directory.**
  `AsyncTaskSettings.storage_path` resolved to
  `~/.crackerjack/state/async_tasks.db` - outside every XDG base
  directory - so every suite run wrote to it. Measured: the file's
  mtime moved during a run, from 04:36 to 04:46.
- **`git clean -fd` destroyed the run history and the logs.** Both lived
  in the project's gitignored `.crackerjack/` directory. Run history is
  append-only and grows without bound; a clean taking it away is the
  opposite of what a cache is.
- **The logs were in the wrong tier.** `LogManager`'s XDG fallback put
  them under `$XDG_CACHE_HOME`, the tier for regenerable data. Logs are
  not regenerable.
- **A path that resolves must resolve when it is used.** A
  module-level constant froze one resolution at import, before the test
  session's `XDG_*` redirect could reach it - so the suite wrote into
  the real directory regardless.

## What is delivered

- **`crackerjack/utils/legacy_paths.py`** — `migrate_legacy_file` and
  `migrate_legacy_dir`. A move never overwrites an existing target, a
  failed move leaves the legacy copy in place, and a symlink is not
  followed.
- **`crackerjack/utils/xdg_paths.py`** — the `state_dir` tier, used by
  the run history and the logs.
- **`crackerjack/core/ai_fix_sinks.py`** — `runs_root()` is the single
  resolver for the run history: the sink that writes, the restore that
  reads, the orphan detector that scans and the replay command that
  reports where it looked all agree.
- **`crackerjack/services/log_manager.py`** — the log directory
  resolves under `$XDG_STATE_HOME/crackerjack/logs`, with the
  project-local directory kept as a fallback.
- **`crackerjack/config/settings.py`** — the async task store resolves
  under `$XDG_DATA_HOME/crackerjack/async_tasks.db`.
- **`crackerjack/mcp/server_core.py`** — the MCP server moves the legacy
  task store at startup.

## Transitions

| From | To | Date | Trigger | Evidence |
|------|----|------|---------|----------|
| (none) | `draft` | 2026-11-07 | Entry created | plan `docs/plans/2026-11-07-xdg-runtime-paths-and-observability.md` |
| `draft` | `built` | 2026-11-07 | The moves and the migration helper landed | commits `1f5d4274`, `759342c0`, `cd784784`, `88a6606c` |
| `built` | `wired` | 2026-11-07 | The paths resolve under XDG and the legacy data is migrated on first use | `tests/unit/utils/test_legacy_paths.py`, `tests/unit/mcp/test_async_task_store_migration.py`, `tests/unit/core/test_runs_root.py`, `tests/unit/services/test_log_manager_paths.py` |

Not yet `adopted`: that needs observability showing the paths in regular
use, and a migration counter would have to exist first.

## Links

- **Plan:** `docs/plans/2026-11-07-xdg-runtime-paths-and-observability.md`
- **Canonical doc:** `docs/decisions/2026-11-06-cj-xdg-namespace-and-state-paths.md`
- **Related entries:** `docs/feature-tracking/2026-11-06-test-selection-and-run-state.md`
- **Issue / discussion:** none

## Rollback signal

- **The async task store:** set `async_task.storage_path` back to
  `~/.crackerjack/state/async_tasks.db` in `settings/local.yaml`. The
  legacy file was *moved*, not copied, so a rollback needs the file back
  from the new location.
- **The run history:** `crackerjack replay --base-dir <project>` still
  reads a project-local run directory, and an explicit `base_dir` keeps
  writing there.
- **The logs:** point `XDG_STATE_HOME` at a read-only path and the
  manager falls back to the project-local directory.
- **Everything:** `git revert` of the commits above.

## Observability

- **Log:** a `logger.info` per successful migration (file or directory
  name, no absolute path) and a `logger.warning` per failure.
- **Query:** the resolved paths are visible through `crackerjack
  run-state show`, which prints the worktree, and through the
  `storage_path=` line the MCP server prints at startup.
- **Gap:** no counter for how many migrations have run, or how often a
  migration failed. That is what has to exist before this feature can be
  called `adopted`.
