---
status: active
role: implementation
kind: plan
topic: cli-lifecycle
date: 2026-09-18
last_reviewed: 2026-09-18
superseded_by: null
blocks_on:
 - docs/superpowers/plans/2026-09-05-mcp-common-phase1.md
---

# Plan — `mcp` subcommand is the only lifecycle surface

**Working dir**: `/Users/les/Projects/crackerjack`
**Scope**: Bodai-wide across `mcp-common`, `crackerjack`, `session-buddy`,
`css-mcp`, `mailgun-mcp`.
**Outcome**: Every MCP server CLI built on `mcp_common.MCPServerCLIFactory`
exposes its lifecycle verbs (`start`, `stop`, `restart`, `status`, `health`,
`version`, `doctor`) **only** under the `mcp` subcommand. Root-level
lifecycle verbs are removed. No deprecation aliases. No legacy wrappers.

**Sequencing**: This plan executes **after** the active
`2026-09-05-mcp-common-phase1.md` plan completes. See Phase 0.

---

## 1. Outcome

A user-facing test that proves the goal:

```text
$ uv run crackerjack --help            # does NOT list start|stop|restart|status
$ uv run crackerjack mcp --help        # lists start|stop|status|restart|health
$ uv run crackerjack start             # exits "Unknown command 'start'"
$ uv run crackerjack mcp start         # starts the server (detached, PID-managed)
```

Same shape holds for `session-buddy mcp {start,stop,...}`, `css-mcp mcp {start,stop,...}`,
and `mailgun-mcp mcp {start,stop,...}`. The legacy `server` subtyper in
session-buddy is renamed to `mcp`; no other subtyper names carry lifecycle verbs.

## 2. Goals

1. `MCPServerCLIFactory` defaults `use_mcp_subcommand=True` and removes the
   parameter (single canonical layout).
2. Crackerjack exposes lifecycle verbs only at `crackerjack mcp {start,stop,status,restart,health}`.
3. Session-buddy renames `session-buddy server {start,stop,...}` → `session-buddy mcp {start,stop,...}`.
4. CSS-MCP and Mailgun-MCP get the same single-layout CLI.
5. Dead/parallel `run --start-mcp-server` / `--stop-mcp-server` / `--restart-mcp-server`
   flags are removed.
6. Documentation drift is fixed across READMEs, QUICKSTARTs, ARCHITECTURE,
   and `session_buddy/data/intent_patterns.yaml`.

## 3. Non-Goals

- No deprecation aliases (no `crackerjack start` shimming to `crackerjack mcp start`).
- No migration tooling for users with root-level commands in shell history.
- Not touching `oneiric/core/cli.py:31`'s legacy `MCPServerCLIFactory` in
  this plan — flag separately as a follow-up to delete or redirect.
- Not addressing the `crackerjack/cli/mcp_cli.py:27` URL typo
  (`"http://localhost: 8676"` → `"http://localhost:8676"`) — fix in the
  crackerjack phase opportunistically; it lives in the same module the
  plan touches.

## 4. Current Findings

Discovery surface, audit on 2026-09-18 against live tree.

| Item | Evidence | Verdict |
|---|---|---|
| Crackerjack root-level `start|stop|restart|status|health` | `crackerjack/__main__.py:96` → `crackerjack/cli/base.py:63` (factory default `use_mcp_subcommand=False`) | **Remove** |
| Crackerjack `--start-mcp-server` flag | `crackerjack/cli/facade.py:101` reads it; foreground-blocks via `start_mcp_main` | **Remove** |
| Crackerjack `--stop-mcp-server` flag | declared in `crackerjack/cli/options.py:399`, accepted by `__main__.py:218`, **no reader** in `facade.py` | **Remove (dead)** |
| Crackerjack `--restart-mcp-server` flag | declared in `crackerjack/cli/options.py:404`, accepted by `__main__.py:219`, **no reader** in `facade.py` | **Remove (dead)** |
| Crackerjack `lifecycle_handlers.py` | `crackerjack/cli/lifecycle_handlers.py:19-80` exports `start_handler`/`stop_handler`/`health_probe_handler` consumed only by `_register_lifecycle_commands` | **Delete module** after Phase 2 |
| Crackerjack `mcp_cli.py` | `crackerjack/cli/mcp_cli.py:109-638` is the rich implementation (PID file, `--force`, `--detach`, `--json`, exit codes) | **Keep — promote to canonical** |
| Session-buddy `server` subtyper | `session_buddy/cli/base.py:306-324` mounts the factory under `server` | **Rename to `mcp`** |
| Session-buddy docs reference `session-buddy server start` | `README.md:199`, `QUICKSTART.md:20,83,117,172,190,221`, `docs/FASTMCP_UNHASHABLE_BUG.md:199`, `docs/migrations/ONEIRIC_MIGRATION_PLAN.md:156`, `docs/migrations/ONEIRIC_MIGRATION_COMPLETE.md:84,135` | **Sweep** |
| CSS-MCP default | `css_mcp/cli.py:33` calls `MCPServerCLIFactory(...)` with no `use_mcp_subcommand` kwarg → defaults to `False` | **Inherit from default flip** |
| Mailgun-MCP default | `mailgun_mcp/__main__.py:125` calls `MCPServerCLIFactory.create_server_cli(...)` → classmethod forwards `use_mcp_subcommand=False` (`factory.py:97`) | **Inherit from default flip** |
| Crackerjack docs reference `crackerjack start|stop|restart` | `README.md:1348,1560,1644-1646,1801,1932,1963`, `CLAUDE.md:63,256` | **Sweep** |
| Intent patterns | `session_buddy/data/intent_patterns.yaml:198` matches `"crackerjack status"` against `crackerjack_health_check` MCP tool — string match, not exec; keep but review | **No exec impact** |

## 5. Requirements

```yaml
requirements:
  - id: REQ-001
    title: "MCPServerCLIFactory defaults to mcp subcommand layout"
  - id: REQ-002
    title: "MCPServerCLIFactory.use_mcp_subcommand parameter removed"
  - id: REQ-003
    title: "crackerjack exposes lifecycle verbs only under `mcp`"
  - id: REQ-004
    title: "crackerjack dead `run --*-mcp-server` flags removed"
  - id: REQ-005
    title: "crackerjack/cli/lifecycle_handlers.py deleted"
  - id: REQ-006
    title: "session-buddy lifecycle subtyper renamed `server` → `mcp`"
  - id: REQ-007
    title: "css-mcp and mailgun-mcp lifecycle moves to `mcp` subcommand"
  - id: REQ-008
    title: "Documentation sweep across all affected repos"
```

`audit_requirements.py` will assert each ID is referenced via
`# req: REQ-NNN` / `# Implements: REQ-NNN` / `@pytest.mark.req(["REQ-NNN"])`.

---

## 6. Implementation Phases

### Phase 0 — Coordination with `2026-09-05-mcp-common-phase1.md`

**Goal**: Land this plan **after** the active mcp-common Phase 1 plan
finishes. The two plans touch the same file (`mcp_common/cli/factory.py`)
and the same methods.

**Why sequence, not merge or override**: The active plan is mid-flight.
It has already restored `MCPServerCLIFactory.register_lifecycle_handlers`
and `create_handlers` (Task 1 landed; verified on 2026-09-18 — both
methods present at `mcp_common/cli/factory.py:338` and `:359`). It
still has remaining tasks (coverage reset, CLAUDE.md sweep,
release-audit subsystem). Inserting the default-flip + parameter-removal
in the middle of that flow would re-open a closed task and force a
re-review of the entire phase-1 chain. Sequencing is cheaper and
preserves the audit trail.

**Pre-flight check before Phase 1 of this plan**:

1. Verify `2026-09-05-mcp-common-phase1.md` is `complete` or
   `shipped` in `mahavishnu/docs/plans/PLAN_INDEX.md` (after next
   regen).
2. Confirm the active plan's Tasks 2-8 have landed on
   `mcp-common/main` (git log).
3. Re-grep for callers of the methods this plan retires:
   ```bash
   grep -rn "register_lifecycle_handlers\|create_handlers" \
     /Users/les/Projects/{crackerjack,session-buddy,css-mcp,mailgun-mcp,mahavishnu,akosha} \
     --include='*.py' | grep -v __pycache__ | grep -v '\.venv/' | grep -v worktrees/
   # Expected: zero callers outside tests (session-buddy uses create_app(), not these)
   ```
4. If any non-test caller exists, either delete the caller or call
   out the dependency in this Phase 0 note before proceeding.

**Exit criteria**:

```bash
cd /Users/les/Projects/mahavishnu && grep -A1 "2026-09-05-mcp-common-phase1" docs/plans/PLAN_INDEX.md
# status reads `complete` or `shipped`
cd /Users/les/Projects/mcp-common && git log --oneline -10 | head
# no in-flight phase-1 commits remaining
```

#### Integration Contract — Phase 0

- **Triggered from**: this plan's frontmatter `blocks_on:` field.
  PLAN_INDEX regeneration will reflect the dependency.
- **Returns to / updates**: the active phase-1 plan's status (once it
  ships, this plan unblocks).
- **Demonstrable by**: the two `cd` checks above return the expected
  status.
- **Rollback signal**: N/A — sequencing is non-destructive.
- **Observability added**: None.

### Phase 1 — `mcp-common`: default flip and parameter removal

**Goal**: Make the `mcp` subcommand layout the only layout.

**Tasks**:

- `mcp_common/cli/factory.py:263-288` — change `use_mcp_subcommand: bool = False`
  → `True`. Drop the conditional branching at lines 312-333; the inner branch
  becomes the only branch.
- `mcp_common/cli/factory.py:90-261` — `create_server_cli()` classmethod:
  remove the `use_mcp_subcommand` parameter and stop forwarding it (it no
  longer exists). All call sites get the default behavior.
- `mcp_common/cli/factory.py` — update module-level docstring (lines 56-88)
  and example invocations to reflect the single layout.
- Tests in `mcp-common/tests/` — drop the `use_mcp_subcommand=False` test
  variants. Assert that `create_app()` always nests the lifecycle verbs
  under `mcp`.

**Exit criteria**:

```bash
cd /Users/les/Projects/mcp-common
uv run python -c "from mcp_common import MCPServerCLIFactory; \
  app = MCPServerCLIFactory(server_name='x').create_app(); \
  print([c.name for c in app.registered_commands])"
# prints [] (root level has no lifecycle commands)
uv run python -c "from mcp_common import MCPServerCLIFactory; \
  app = MCPServerCLIFactory(server_name='x').create_app(); \
  [print(g.name) for g in app.registered_groups]"
# prints "mcp"
uv run pytest tests/ -q
# all green
```

#### Integration Contract — Phase 1

- **Triggered from**: `MCPServerCLIFactory(server_name=...).create_app()`
  in any consumer.
- **Returns to / updates**: The Typer app returned by `create_app()` now
  has zero lifecycle commands at root and exactly one registered group
  named `"mcp"` carrying `start`, `stop`, `restart`, `status`, `health`,
  `version`, `doctor`.
- **Demonstrable by**: `uv run python -c "..."` snippet above plus
  `uv run pytest mcp-common/tests/test_cli_factory.py::TestMCPServerCLIFactory::test_mcp_subcommand_is_only_layout -q`.
- **Rollback signal**: `git revert` + retag. No runtime signal needed —
  this is library code, not a service.
- **Observability added**: None — pure CLI shape change.

### Phase 2 — Crackerjack: drop root-level verbs, drop dead flags

**Goal**: Crackerjack CLI matches the new factory default.

**Tasks**:

- `crackerjack/cli/base.py:63` — drop `MCPServerCLIFactory(...)` instantiation
  of the root-level lifecycle. The new code path either:
  - (preferred) deletes `_register_lifecycle_commands` and its caller in
    `__init__`, since the `mcp` subcommand already exists at
    `crackerjack/cli/mcp_cli.py:109` and is mounted in `__main__.py:126`,
    OR
  - (fallback) keeps `_register_lifecycle_commands` but passes
    `use_mcp_subcommand=True` (which will no longer exist after Phase 1
    — the fallback only applies if Phase 1's parameter removal is
    rejected during review).
- `crackerjack/__main__.py:96-100` — remove the `start_handler=`/
  `stop_handler=`/`health_probe_handler=` kwargs from the
  `CrackerjackCLI(...)` instantiation.
- `crackerjack/__main__.py:217-219` — remove `start_mcp_server`,
  `stop_mcp_server`, `restart_mcp_server` parameters and their
  corresponding entries in `_create_and_configure_options`.
- `crackerjack/cli/options.py:87-89` — remove the three `*_mcp_server`
  dataclass fields.
- `crackerjack/cli/options.py:394-408` — remove the three
  `*_mcp_server` Typer Option entries.
- `crackerjack/cli/facade.py:93-122` — remove `_should_handle_special_modes`
  branch for `start_mcp_server`, `_handle_special_modes`, and
  `_start_mcp_server`.
- `crackerjack/cli/lifecycle_handlers.py` — delete the entire module
  (no remaining callers after this phase).
- `crackerjack/cli/mcp_cli.py:27` — fix URL typo
  `"http://localhost: 8676"` → `"http://localhost:8676"`. Re-export the
  `health` command to match factory names (`probe`, `json_output` already
  match — no API change).
- Tests in `crackerjack/tests/` — remove or rewrite any test that:
  - Asserts `crackerjack start` is registered.
  - Patches `lifecycle_handlers.start_handler` etc.
  - Invokes `CliRunner(app, ["start"])` / `["stop"]` / `["restart"]` /
    `["status"]`.
- Add positive test: `CliRunner(app, ["mcp", "--help"])` lists
  `start`, `stop`, `status`, `restart`, `health`. `CliRunner(app, ["start"])`
  exits non-zero with `"Unknown command"`.

**Exit criteria**:

```bash
cd /Users/les/Projects/crackerjack
uv run python -m crackerjack --help 2>&1 | grep -E '^\s+(start|stop|restart|status|health)\s'
# empty (no root-level lifecycle verbs)
uv run python -m crackerjack mcp --help 2>&1 | grep -E '^\s+(start|stop|status|restart|health)\s'
# lists all five
uv run python -m crackerjack start
# exits with "No such command 'start'"
uv run pytest tests/ -q -k "cli or mcp_cli or lifecycle"
# all green
```

#### Integration Contract — Phase 2

- **Triggered from**: `python -m crackerjack {--help,start,stop,...}` and
  the Typer dispatch in `CrackerjackCLI` / `crackerjack/__main__.py`.
- **Returns to / updates**: CLI surface. PID file at
  `/tmp/crackerjack-mcp.pid` (managed by `mcp_cli.py`) continues to be
  the canonical state.
- **Demonstrable by**: `uv run python -m crackerjack --help | grep
  -E '^\s+(start|stop|restart|status)\s'` returns empty.
- **Rollback signal**: `crackerjack --help` showing any of
  `start|stop|restart|status` at root indicates Phase 2 incomplete.
- **Observability added**: None.

### Phase 3 — Session-buddy: rename `server` → `mcp`

**Goal**: Session-buddy lifecycle moves from `session-buddy server {start,...}`
to `session-buddy mcp {start,...}`.

**Tasks**:

- `session_buddy/cli/base.py:306-324` — change
  `self.add_typer(lifecycle_app, name="server")` → `name="mcp"`. Update
  the docstring on `_mount_lifecycle_subtyper`.
- `session_buddy/cli/base.py:307-314` — update the comment about why
  `mcp` was avoided (OneiricCLIBase-provided `health` collision).
  Verify by inspection that no other OneiricCLIBase subclass in this
  repo defines a `health` command at root; if it does, pick a different
  name and document why.
- Tests in `session_buddy/tests/` — replace `cli_runner.invoke(app,
  ["server", "start"])` with `["mcp", "start"]` everywhere.
  `session_buddy/tests/cli/test_base.py:54` patches the handlers; update
  if any test still expects `server` in the registered names.
- `session_buddy/cli/__init__.py` (if present and re-exporting) — confirm
  nothing hardcodes the name `server`.

**Exit criteria**:

```bash
cd /Users/les/Projects/session-buddy
uv run python -m session_buddy --help 2>&1 | grep -E '^\s+server\s'
# empty (no `server` subtyper)
uv run python -m session_buddy mcp --help 2>&1 | grep -E '^\s+(start|stop|status|restart|health)\s'
# lists all five
uv run pytest tests/cli tests/unit/test_cli.py tests/unit/test_cli_with_modes.py -q
# all green
```

#### Integration Contract — Phase 3

- **Triggered from**: `python -m session-buddy {--help,server,mcp,...}`.
- **Returns to / updates**: CLI surface. No change to PID file
  management (factory default settings unchanged).
- **Demonstrable by**: `uv run python -m session-buddy --help | grep -E
  '^\s+server\s'` returns empty; `uv run python -m session-buddy mcp
  start --detach` produces a PID file.
- **Rollback signal**: `session-buddy --help` listing a top-level
  `server` group means the rename was skipped.
- **Observability added**: None.

### Phase 4 — CSS-MCP and Mailgun-MCP: inherit new default

**Goal**: These servers get the `mcp` subcommand layout with no local
code change beyond tests.

**Tasks**:

- `css_mcp/cli.py:24-42` — no source change required (Phase 1 already
  flipped the default). Verify `create_app()` produces a Typer with
  the `mcp` subtyper.
- `css_mcp/tests/` — update any `CliRunner` invocations that target
  `start`/`stop`/`restart`/`status` at root to use `mcp start` etc.
- `mailgun_mcp/__main__.py:125-132` — no source change required.
  Verify `create_app()` produces the `mcp` subtyper.
- `mailgun_mcp/tests/` — same test-invocation sweep as css-mcp.

**Exit criteria**:

```bash
cd /Users/les/Projects/css-mcp
uv run python -m css_mcp --help 2>&1 | grep -E '^\s+(start|stop|restart|status)\s'
# empty
uv run python -m css_mcp mcp --help 2>&1 | grep -E '^\s+(start|stop|status|restart|health)\s'
# lists all five
cd /Users/les/Projects/mailgun-mcp
uv run python -m mailgun_mcp --help 2>&1 | grep -E '^\s+(start|stop|restart|status)\s'
# empty
uv run python -m mailgun_mcp mcp --help 2>&1 | grep -E '^\s+(start|stop|status|restart|health)\s'
# lists all five
```

#### Integration Contract — Phase 4

- **Triggered from**: `python -m css_mcp ...` and
  `python -m mailgun_mcp ...`.
- **Returns to / updates**: CLI surface in both repos.
- **Demonstrable by**: `--help` greps above.
- **Rollback signal**: N/A — pure default inheritance.
- **Observability added**: None.

### Phase 5 — Documentation sweep

**Goal**: No doc, intent pattern, or config file advertises the removed
root-level verbs.

**Tasks**:

**Crackerjack** (`/Users/les/Projects/crackerjack/`):

- `README.md:1348,1560,1644-1646,1801,1932,1963` — replace every
  `python -m crackerjack start|stop|restart|status|health` reference
  with `python -m crackerjack mcp {start|stop|restart|status|health}`.
- `CLAUDE.md:63,256` — same replacement.
- `examples/` — sweep any shell script or docstring referencing
  root-level verbs.

**Session-buddy** (`/Users/les/Projects/session-buddy/`):

- `README.md:199` — `session-buddy server start` →
  `session-buddy mcp start`.
- `QUICKSTART.md:20,83,117,172,190,221` — same.
- `ARCHITECTURE.md:156,184,765,782` — same. Note: `ARCHITECTURE.md:184`
  uses `--mcp` as a flag (`session-buddy start --mode=standard --mcp`).
  Inspect: this `--mcp` is a separate concern (mode selector). Keep
  only if it's a flag, not a command position.
- `docs/FASTMCP_UNHASHABLE_BUG.md:199`,
  `docs/migrations/ONEIRIC_MIGRATION_PLAN.md:156`,
  `docs/migrations/ONEIRIC_MIGRATION_COMPLETE.md:84,135` — same.
- `session_buddy/data/intent_patterns.yaml:198` — `"crackerjack status"`
  pattern: this is natural-language intent matching for the
  `crackerjack_health_check` MCP tool, not a CLI exec pattern. **Keep**
  but add a sibling pattern for `"crackerjack mcp status"` if not
  already matched.
- `AGENTS.md:13` — `uv run session-buddy start` →
  `uv run session-buddy mcp start`.

**Mailgun-MCP** (search the repo for `mailgun-mcp start|stop|restart|status`
in `.md`/`.sh`/`.plist`/`.yaml`/`.json`; sweep any matches to `mailgun-mcp mcp ...`).

**CSS-MCP** (same sweep).

**Exit criteria**:

```bash
grep -rn -E '(crackerjack|session-buddy|css-mcp|mailgun-mcp) (start|stop|restart|status|health)\b' \
  /Users/les/Projects/{crackerjack,session-buddy,css-mcp,mailgun-mcp} \
  --include='*.md' --include='*.sh' --include='*.yaml' --include='*.yml' \
  --include='*.json' --include='*.toml' --include='*.txt' \
  --include='*.plist' 2>/dev/null | grep -v 'docs/archive/' | grep -v 'node_modules/' | grep -v '\.venv/'
# expected: empty, or only matches where `mcp` precedes the verb (e.g. `mcp start`)
```

#### Integration Contract — Phase 5

- **Triggered from**: doc/PR review, CI lint of cross-repo
  documentation patterns.
- **Returns to / updates**: Markdown, shell, and YAML files in five
  repos. Each reference becomes `mcp {verb}`.
- **Demonstrable by**: the grep above.
- **Rollback signal**: N/A.
- **Observability added**: None.

### Phase 6 — Cross-repo coordination: order of merge

**Goal**: Land Phases 2-4 in parallel across the four consumer repos
once Phase 0 unblocks. Phase 5 (doc sweep) can ride with the same PRs
to minimize churn.

**Tasks**:

- Wait for Phase 0 exit criteria (active phase-1 plan completes).
- Land mcp-common Phase 1 as a single PR. Tag a release
  (`X.Y.Z`) per the `crackerjack-version-bumping-manual` memory rule
  (user does the bump; flag in the plan).
- Land Phases 2-4 in parallel — each repo can adopt the new release
  independently.
- Land Phase 5 last (or in the same PRs as 2-4 to minimize churn).

**Exit criteria**:

- `mcp-common` PyPI version X.Y.Z published; crackerjack/session-buddy/
  css-mcp/mailgun-mcp each bump their `mcp-common` dep to `>=X.Y.Z`.
- All five repos green on their respective CI.

#### Integration Contract — Phase 6

- **Triggered from**: `crackerjack run -p minor` on `mcp-common` per
  the user's manual-bump convention; subsequent bumps in the four
  consumers.
- **Returns to / updates**: PyPI releases, lockfile pins, README
  changelogs.
- **Demonstrable by**: `uv pip show mcp-common` in each consumer's
  venv reports `>=X.Y.Z`.
- **Rollback signal**: PyPI yank (last resort); otherwise revert +
  retag.
- **Observability added**: None.

---

## 7. Required Code Changes

```
mcp-common/
  mcp_common/cli/factory.py                    [REQ-001, REQ-002]
  mcp_common/cli/factory.py (tests)            [REQ-001, REQ-002]

crackerjack/
  crackerjack/__main__.py                      [REQ-003, REQ-004]
  crackerjack/cli/base.py                      [REQ-003]
  crackerjack/cli/options.py                   [REQ-004]
  crackerjack/cli/facade.py                    [REQ-004]
  crackerjack/cli/lifecycle_handlers.py        [REQ-005]  (delete)
  crackerjack/cli/mcp_cli.py                   [REQ-003]  (typo fix)
  crackerjack/tests/                           [REQ-003, REQ-004, REQ-005]

session-buddy/
  session_buddy/cli/base.py                    [REQ-006]
  session_buddy/tests/                         [REQ-006]

css-mcp/
  css_mcp/tests/                               [REQ-007]

mailgun-mcp/
  mailgun_mcp/tests/                           [REQ-007]

crackerjack/docs/
  README.md, CLAUDE.md, examples/              [REQ-008]

session-buddy/docs/
  README.md, QUICKSTART.md, ARCHITECTURE.md,
  AGENTS.md, docs/migrations/, docs/FASTMCP_UNHASHABLE_BUG.md   [REQ-008]

mailgun-mcp/, css-mcp/  (md/yaml/sh/plist)     [REQ-008]
```

## 8. Validation Matrix

| Check | Command | Pass criterion |
|---|---|---|
| Factory default | `python -c "from mcp_common import MCPServerCLIFactory; print([g.name for g in MCPServerCLIFactory(server_name='x').create_app().registered_groups])"` | `['mcp']` |
| Crackerjack root | `python -m crackerjack --help` | no `start|stop|restart|status` at root |
| Crackerjack sub | `python -m crackerjack mcp --help` | lists `start, stop, status, restart, health` |
| Crackerjack fail | `python -m crackerjack start` | exits non-zero with "No such command" |
| Session-buddy root | `python -m session-buddy --help` | no `server` subtyper |
| Session-buddy sub | `python -m session-buddy mcp --help` | lists `start, stop, status, restart, health` |
| CSS-MCP root | `python -m css_mcp --help` | no `start|stop|restart|status` at root |
| CSS-MCP sub | `python -m css_mcp mcp --help` | lists the five |
| Mailgun-MCP root | `python -m mailgun_mcp --help` | no `start|stop|restart|status` at root |
| Mailgun-MCP sub | `python -m mailgun_mcp mcp --help` | lists the five |
| Doc sweep | `grep -rn -E '(crackerjack\|session-buddy\|css-mcp\|mailgun-mcp) (start\|stop\|restart\|status)\b' ...` (excluding `mcp ` prefix and `docs/archive/`) | empty |
| Quality gate | `uv run crackerjack` (per repo) | all green |

## 9. Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| External shell scripts or launchd plists call `crackerjack start` etc. | Medium | Document in CHANGELOG; grep `/Users/les/Projects/mahavishnu/ops/` and `~/.claude/` for callers before merge; if found, update them in the same PR |
| Session-buddy users have muscle memory for `server` subcommand | Medium | Same — CHANGELOG note; the rename is mechanical (`server` → `mcp`); no behavior change |
| Mailgun-MCP launchd plist uses `--mode=...` flag that overlaps with the verb | Low | Phase 4 verification checks `mailgun-mcp mcp --help` for `--mode` flag; if missing, document as a separate concern |
| Oneiric legacy `MCPServerCLIFactory` (oneiric/core/cli.py:31) still in use | Unknown — outside this plan | Flag separately; out of scope |
| `--start-mcp-server` flag had a third-party caller | Low | Grep crackerjack `dist/` for wheel usage; CHANGELOG |
| `intent_patterns.yaml` matcher breaks if `"crackerjack status"` query is no longer valid | Low | Phase 5 keeps the pattern; add `"crackerjack mcp status"` as a sibling |

## 10. Decision Rule

This plan is "done enough" when:

1. `mcp-common` PyPI X.Y.Z released with `use_mcp_subcommand` parameter
   removed (or default flipped if review keeps the parameter).
2. Crackerjack, session-buddy, css-mcp, and mailgun-mcp each show
   `[no root-level lifecycle verbs]` and `[mcp subcommand lists all five]`
   on `uv run <component> --help` and `uv run <component> mcp --help`.
3. `--start-mcp-server`, `--stop-mcp-server`, `--restart-mcp-server`
   flags in `crackerjack run` are gone — `crackerjack --help` and
   `crackerjack run --help` no longer mention them.
4. Validation matrix above is green across all five repos.
5. Documentation grep returns empty (excluding `docs/archive/`).

Scope pressure cuts at: Phase 5 (documentation). If a doc reference is
in `docs/archive/`, leave it. Otherwise fix in this plan.

---

## References

- `mcp-common/mcp_common/cli/factory.py:90-336` — factory contract this
  plan retires the parameter on.
- `crackerjack/cli/base.py:26-83` — crackerjack's `MCPServerCLIFactory`
  consumer.
- `crackerjack/__main__.py:96-219` — top-level wiring and dead flags.
- `session_buddy/cli/base.py:306-324` — subtyper name to rename.
- `mahavishnu/CLAUDE.md` "Process Discipline" — wiring-contract policy
  this plan honors with Integration Contract blocks per phase.
- Memory `crackerjack-version-bumping-manual.md` — Phase 6 follows the
  manual-bump + user-initiated publish convention.
- Memory `crackerjack-cli-run-subcommand.md` — `crackerjack run` is the
  workflow entry point, distinct from lifecycle commands.
