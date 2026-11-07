# Crackerjack's XDG namespace and its project-local state paths

Status: Active
Date: 2026-11-06

## Context

Crackerjack ships `crackerjack/utils/xdg_paths.py`, a helper for resolving
XDG Base Directory locations. It is a verbatim copy of Session-Buddy's
module — its own docstring says so:

> "XDG Base Directory resolution for **Session-Buddy owned** runtime data.
> … The data owner is always `session-buddy`, even in a repository that
> merely consumes Session-Buddy's data … Every repository carries its own
> copy of this module."

The copy kept Session-Buddy's defaults, including the app name:

```python
def data_dir(app: str = "session-buddy") -> Path:
    return _xdg_root("XDG_DATA_HOME", "~/.local/share") / app
```

So Crackerjack's user-scoped runtime data resolves into **Session-Buddy's**
XDG directory:

```
~/.local/share/session-buddy/crackerjack_integration.db   ← written by Crackerjack
~/.local/share/session-buddy/workflow_metrics.db           ← opened by Crackerjack
~/.local/share/session-buddy/correlation_insights.db       ← written by Crackerjack
```

`crackerjack_integration.db` is the sharp edge. Crackerjack's health handler
(`crackerjack/cli/handlers/health.py:20,394,424`) writes
`crackerjack_results` and `quality_metrics_history` — the same two tables
Session-Buddy creates and owns (`session_buddy/crackerjack_integration.py:263,310`).
Two components co-write one SQLite file, and the table names collide. The
collision is silent today only because both sides use `CREATE TABLE IF NOT EXISTS` with compatible columns.

Separately, `.crackerjack/` mixes three storage tiers in one gitignored
directory. In the crackerjack repo:

| Path | Size | Tier |
|---|---|---|
| `logs/` | 20 MB | **data** (history) |
| `runs/` | 5.2 MB, 665 run dirs | **data** (AI-fix event history) |
| `oneiric_cache/` | 2.1 MB | cache |
| `patterns.json` | 112 KB | learning state |
| `adapter_learning.db` | 36 KB | learning state |
| `semantic_index.db` | 32 KB | cache (regenerable) |

`runs/` and `logs/` are append-only history that grows without bound, and they
live in a gitignored directory — so `git clean -fd` destroys them. That is the
opposite of what a cache is.

## Decision rule

**1. Crackerjack's user-scoped data resolves under Crackerjack's own app
name.** Every Crackerjack-owned path uses `data_dir(app="crackerjack")`.
`data_dir(app="session-buddy")` is reserved for the genuinely
Session-Buddy-owned files that Crackerjack legitimately reads or writes, and
must be passed explicitly at those call sites.

The copied module's default argument must change to the owning repository's
app name. The module stays duplicated across repositories — the docstring
already explains why: a cross-repo import would need a publish first, and
duplicating a ~20-line dependency-free module is the accepted cost.

**2. `runs/` and `logs/` move to `$XDG_STATE_HOME/crackerjack/`.** They are
state and history, not caches. The on-disk layout under
`$XDG_STATE_HOME/crackerjack/` keeps the existing `runs/<run_id>/events.jsonl`
and `logs/` shapes so nothing downstream has to change shape.

**3. Project-local caches stay in `.crackerjack/`.** `semantic_index.db` and
`scan_markers.db` index one repository's files and are regenerable from the
source tree. They are project-local artifacts — the tier XDG does not define,
whose standard fill is a gitignored project dotfile directory (as with
`.ruff_cache/` or `.mypy_cache/`). Moving them to a user-scoped
`$XDG_CACHE_HOME` would require per-repository subdirectories and would break
the `project_path`-relative form the fixers rely on
(`crackerjack/fixers/semantic.py:177`).

## Consequences

- `crackerjack_integration.db` stops being a two-writer file. Crackerjack's
  health rows and Session-Buddy's tables separate, and the table-name
  collision disappears.
- Crackerjack's data stops appearing in Session-Buddy's XDG directory, so
  `ls ~/.local/share/session-buddy/` reflects Session-Buddy's own data.
- Run history survives `git clean -fd`.

## A correction to this record: the integration database is Session-Buddy's

This record originally said:

> Existing `~/.local/share/session-buddy/crackerjack_integration.db` content
> is Crackerjack's and moves with the rename. The migration is a file move,
> not a schema change.

**That was wrong, and acting on it would have destroyed data.** The file
holds both components' rows:

| Table | Rows | Owner |
|---|---|---|
| `crackerjack_results` | 1389 | Session-Buddy's — it writes them from the crackerjack runs it drives |
| `quality_metrics_history` (`build_status`, `lint_score`, `security_score`, `complexity_score`, `complexity_score`, `unavailable`) | 2222 | Session-Buddy's |
| `quality_metrics_history` (`health_adapters`, `health_managers`, `health_services`) | 402 | Crackerjack's health snapshots |

Moving the file would have taken Session-Buddy's 3611 rows with it. So the
file **stays where it is**, and only Crackerjack's *new* writes go to
`data_dir("crackerjack")`.

The 402 historical health rows stay in Session-Buddy's file, and no copy
is made: both of Session-Buddy's consumers filter by metric type, and
`health_*` is in neither list — `quality_scoring._parse_metrics_history`
keeps `code_coverage`, `lint_score`, `security_score` and
`complexity_score`, and `analyze_quality_trends` keeps
`test_pass_rate` and the same three. Nothing reads the rows Crackerjack
writes, in either location.

## Status

Active, and **implemented** — with two paths still outstanding, named
below.

Implemented:

- Rule 1's app-name default. `crackerjack/utils/xdg_paths.py` resolves under
  `crackerjack` rather than `session-buddy`, and the two genuinely
  Session-Buddy-owned files (`workflow_metrics.db`,
  `correlation_insights.db`) are reached with `data_dir("session-buddy")`
  passed explicitly.
- The health snapshot database resolves under
  `data_dir("crackerjack")`, and the run-state store under
  `data_dir("crackerjack") / "run_state.db"`.
- The snapshot path is resolved when it is *used*, not captured at import
  time, so the test session's `XDG_*` redirect actually contains it.
- **Rule 2.** `runs/` resolves under `$XDG_STATE_HOME/crackerjack/runs` and
  `logs/` under `$XDG_STATE_HOME/crackerjack/logs`. Run history survives
  `git clean -fd`. The on-disk shapes are unchanged:
  `runs/<run_id>/events.jsonl` and `logs/{debug,error,audit}/`.
- **The async task store** resolves under
  `data_dir("crackerjack") / "async_tasks.db"`, and the file left at
  `~/.crackerjack/state/async_tasks.db` is moved on first use.

Still outstanding:

- **Two paths still resolve outside XDG**: the prompt-evolution store
  (`~/.cache/crackerjack/prompt_evolution`) and the lock directory
  (`~/.crackerjack/locks`). Rule 1 as written — "every Crackerjack-owned
  path" — does not hold for those two yet.
- **The integration database is not migrated**, for the reason given
  above: it is Session-Buddy's file, and the rows in it are theirs.

## Not covered here

Crackerjack's semantic index still uses **hash pseudo-vectors** rather than a
real embedding model. That is a separate defect with a separate fix — it
lives in the Session-Buddy conversation-ingestion plan, because the fix
depends on the fleet-wide Oneiric embedding work (Oneiric gains an OpenAI
leg; Session-Buddy, Akosha, Mahavishnu, and Crackerjack all resolve their
vector width from it). The XDG and state-path decisions here are independent
of that work and do not wait on it.
