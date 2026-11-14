---
title: Remove the Dead Module Cluster from Crackerjack
description: "Delete 128 production modules (26,659 lines) that no code path in the repo or the fleet ever loads, plus 104 test files (35,368 lines) that exist only to exercise them. The inventory was wrong the first time — 30 modules in `crackerjack/services/patterns/` are live — so this plan records the corrected set, the runtime proof behind it, and the four places where 'dead' is really 'documented but never wired'. Net: ~62,000 lines removed, zero capability that currently runs is lost, and `git_analytics.py`'s 3,275 lines get a real home instead of the bin."
audience: crackerjack maintainer
created: 2026-11-14
status: active
role: implementation
topic: architecture
date: 2026-11-14
last_reviewed: 2026-11-14
superseded_by: null
blocks_on: []
---

# Remove the Dead Module Cluster from Crackerjack

## Brief (intent-driven)

### Goal

Every production module in the repo that no code path ever loads is gone, and
the four subsystems that were built but never wired are either wired or
documented as never-wired. The repo stops carrying ~26,700 lines of production
code and ~35,400 lines of test code that exist only to exercise each other.

The inventory that produced this plan was **wrong the first time** — it called
30 live modules dead — and the correction is recorded here rather than
papered over, because the blind spot is systematic and will bite the next
inventory too.

### Constraints

1. **Nothing that currently runs may stop running.** Every deletion target is
   proven unreachable from a real entry point. The proof is a runtime import
   sweep, not a grep (see *How the dead set was established*).
2. **`crackerjack/services/patterns/` stays.** It is live — `SAFE_PATTERNS`
   is the shared 180-entry regex registry behind input validation, path
   security, the coverage ratchet, publish version bumping, and the MCP job-id
   validator.
3. **`crackerjack/mahavishnu/mcp/tools/git_analytics.py` gets a home, not a
   deletion.** It is 3,275 lines of unique content with eight MCP tools and no
   upstream equivalent. It is relocated and wired in Phase 6.
4. **The `sys.path` shim in `tests/unit/test_adapter_observability.py:29-33`
   goes away.** It inserts `<repo>/crackerjack` at `sys.path[0]`, which makes
   `import mahavishnu.*` resolve to crackerjack's copy for the rest of the
   pytest session — a live hazard for any other test in the suite.
5. **`crackerjack/tests/` is relocated, not deleted.** Those three modules are
   legitimate tests that live in the wrong directory; they ship to PyPI today
   because the wheel include is `crackerjack/**/*.py`.
6. **Pre-1.0 — direct merge to `main`, no PR.** Per
   `feedback-bodai-pre-1.0-merge-policy.md`.
7. **Do not touch `pyproject.toml` version strings** — the version bump and
   the PyPI publish are the operator's.
8. **The four "documented but never wired" features get an explicit decision,
   not a silent delete.** `safe_code_modifier`, `validation_rate_limiter`, the
   self-improvement loop, and the `SafeCodeModifier` `.bak`-sibling guarantee
   are claimed by live documentation. Deleting the code while leaving the
   documentation is a new inconsistency. See *Decisions that need a call*.
9. **Never `git add -A`.** Commit with explicit pathspecs; other sessions have
   work in this tree.

### Failure Conditions (verifier-only)

1. None of the 128 modules listed in the phase tables exist on disk.
2. `crackerjack/services/patterns/` still exists, and
   `crackerjack/services/regex_patterns.py` still exports `SAFE_PATTERNS`;
   `len(SAFE_PATTERNS) >= 180`.
3. `crackerjack/mahavishnu/mcp/tools/git_analytics.py` no longer exists at that
   path, and its eight tools are reachable from a registered MCP surface
   (either a new `crackerjack/mahavishnu-git-analytics` console script with a
   `main()` that calls `mcp.run()`, or the `crackerjack/mcp/tools/` tree).
4. `grep -rn "sys.path.insert" tests/` returns no match that inserts
   `<repo>/crackerjack`.
5. `pyproject.toml`'s wheel include no longer matches `crackerjack/tests/**`,
   and the built wheel contains no `crackerjack/tests/` file.
6. `git grep -n "crackerjack.services.patterns" -- crackerjack/` still matches
   the live registry.
7. `scripts/validate_imports.py` and `scripts/migrate_ulids.py` no longer
   import a deleted module.
8. The full test suite shows **no new failures** against the pre-removal
   baseline (20 failed / 12,606 passed / 127 skipped at `fe1bb2af`).
9. `crackerjack run -v -f` (fast hooks) passes; the release audit passes;
   `uv lock --check` passes.

---

## Context

### Where the numbers came from

An earlier sweep of this repo (the 2026-11-13 AI-fix cluster plan) reported
**192** dead modules. That number was wrong in two ways, and the correction
matters:

- 34 of them were the AI-fix cluster, which this repo already removed.
- **30 of the remaining were live.** The AST resolver collapsed
  `from . import agents` into an edge to the *package* rather than to the
  *submodule*, so the whole `crackerjack/services/patterns/` family fell out of
  the reachable set. `crackerjack/services/regex_patterns.py:1` does
  `from .patterns import (...)`, and that module has sixteen live production
  importers.

The corrected set is **128 modules / 26,659 production lines**, plus **104 test
files / 35,368 test lines**.

Two independent checks caught the same blind spot — the corrected inventory
script and a separate verification agent, working from different methods —
which is why the correction is trusted rather than merely asserted.

### How the dead set was established

Three independent layers, in increasing strength:

**1. AST reachability (the inventory).**
Roots: the two `[project.scripts]` / `[project.entry-points.bodai.apps]`
entry points, the four `crackerjack.language_adapters` entry points, every
`[tool.*]` table in `pyproject.toml`, every module path in `settings/*.yaml`,
the MCP skill catalog (`crackerjack/mcp/skills_catalog/*.md`, which the MCP
server hands to an agent that then imports the named modules), and every
`__all__` re-export in every package `__init__.py`. String-literal module
references are counted as edges, so `importlib.import_module("literal")`
maps and lazy `__getattr__` tables resolve.

**2. Cross-repo check.** The fleet's Python surface for crackerjack is tiny:
`mahavishnu` imports only `crackerjack` (and talks to it over MCP/HTTP, not
Python), `session-buddy` imports `crackerjack` and
`crackerjack.services.regex_patterns`. `akosha`, `oneiric`, and `mcp-common`
import nothing. `crackerjack.services.regex_patterns` is live, so no dead
module has an external importer.

**3. Runtime proof — the decisive layer.** Every live production module is
imported into one process and `sys.modules` is inspected:

```
production modules: 519   dead: 128   live: 391
imported OK=391 FAIL=0 of 391
DEAD MODULES LOADED BY THE UNION OF ALL LIVE IMPORTS: 0
--- per-importer attribution sweep ---
  no dead module was loaded by any live module -> the dead set is sound
```

The union of every possible import is a superset of any single runtime path.
A module that no import anywhere pulls in cannot have a runtime load path.

### The cluster table

| Cluster | Modules | Lines |
|---|---|---|
| `crackerjack.services` | 41 | 9,519 |
| `crackerjack.adapters` | 23 | 4,495 |
| `crackerjack.mahavishnu` | 10 | 3,716 |
| `crackerjack.core` | 10 | 2,047 |
| `crackerjack.plugins` | 5 | 1,106 |
| `crackerjack.executors` | 2 | 1,023 |
| `crackerjack.tests` | 4 | 851 |
| `crackerjack.models` | 3 | 825 |
| `crackerjack.websocket` | 4 | 551 |
| `crackerjack.utils` | 4 | 485 |
| `crackerjack.ci_feedback` | 1 | 338 |
| `crackerjack.sop` | 5 | 334 |
| `crackerjack.data` | 3 | 262 |
| `crackerjack.security` | 1 | 210 |
| `crackerjack.py313` | 1 | 191 |
| `crackerjack.exceptions` | 4 | 185 |
| `crackerjack.tools` | 1 | 180 |
| `crackerjack.integration` | 1 | 156 |
| `crackerjack.memory` | 2 | 120 |
| `crackerjack.managers` | 1 | 41 |
| `crackerjack.contracts` | 1 | 24 |
| `crackerjack.ui` | 1 | 0 |
| **TOTAL** | **128** | **26,659** |

### The dead set is not one kind of dead

Deleting all 128 uniformly would be wrong in three places. The modules fall
into four categories.

**A. Pure dead code — a closed island, delete outright.** Most of
`crackerjack/services/` and `crackerjack/core/`. Examples:
`services/constants.py` (zero importers — the `DEFAULT_CACHE_TTL` match
against `core/defaults.py:116` is a name collision, not an import),
`services/terminal_utils.py` (0 bytes), `core/self_heal/` (four modules that
only reference each other), `sop/` (five modules, mutually referencing).

**B. Stale duplicates — a live twin already exists, delete the orphan.**

| Dead module | Lines | Live twin |
|---|---|---|
| `services/predictive_analytics.py` | 476 | `services/ai/predictive_analytics.py` (used by `cli/handlers/analytics.py:432`) |
| `services/intelligent_commit.py` | 307 | `services/ai/intelligent_commit.py` (same `CommitMessageGenerator` class, different constructor signature) |
| `services/smart_file_filter_v2.py` | 107 | `services/file_filter.py` (`SmartFileFilter`, used by `hook_manager.py:241`, `hook_executor.py:447`) |
| `services/metrics.py` | 259 | `crackerjack/monitoring.py` (`MetricsCollector`) |
| `services/pool_*.py` | 851 | `services/swarm_client.py` (`MahavishnuSwarmClient`) |
| `adapters/type/ty.py` | 257 | already removed in `73bf3eda` — a second copy of `ty_adapter.py`, same `MODULE_ID` |

This is a recurring pattern: a re-implementation landed under a new path and
the old file was never deleted.

**C. Documented but never wired — needs a decision, not a silent delete.**
Four places where live documentation claims a capability that no code path
provides:

| Feature | Implementation | What the docs claim |
|---|---|---|
| `.bak` sibling guarantee before any ruff rewrite | `services/safe_code_modifier.py` (447) | `docs/plans/2026-08-06-crackerjack-ruff-fix-policy.md:544` requires *every* unsafe-fix invocation to route through it. `adapters/format/ruff.py:147-159` and `config/tool_commands.py:481-492` invoke ruff directly — **the guarantee is not in effect today.** |
| Core security component | `services/validation_rate_limiter.py` (221) | `SECURITY.md:84` and `docs/reference/SECURITY.md:97` list it under *Core Security Components*; `:268-277` gives a `get_validation_rate_limiter()` integration snippet. **No production module calls it.** |
| Self-improvement loop | `services/self_patcher.py` (268), `improvement_generator.py` (128), `improvement_overseer.py` (72), `constitution.py` (47) | `docs/architecture/MEMORY_ARCHITECTURE.md:301,686,796,1377` describes `PhaseCoordinator → FailureRecorder → … → ImprovementGenerator → ImprovementOverseer → SelfPatcher`, then admits the overseer is *"currently unused"* and the generator's `improvement_job_id` has *"no consumer"*. `phase_coordinator.py` contains zero matches for `improvement\|overseer\|self_patch`. |
| `MemoryOptimizerProtocol` injection | `services/memory_optimizer.py` (420) | `core/phase_coordinator.py:77` accepts `memory_optimizer: MemoryOptimizerProtocol \| None = None` and `:170` stores it — but `memory_optimizer=` is **never passed** at any construction site repo-wide. |

Deleting these leaves documentation claiming a feature that does not exist.
Deleting the *documentation* leaves a feature nobody asked for. Both are
decisions; the plan records them rather than choosing silently.

**D. Unique content with no home — relocate, don't delete.**
`crackerjack/mahavishnu/mcp/tools/git_analytics.py` (3,275 lines) exposes
eight MCP tools (`get_portfolio_velocity_dashboard`, `analyze_merge_patterns`,
`get_best_practices_propagation`, `get_repository_comparison`,
`get_cross_project_conflicts`, `get_active_branches_analysis`,
`get_repository_health_dashboard`, `get_workflow_recommendations`) on a
`FastMCP("crackerjack-mahavishnu-git-analytics")` server. A fleet-wide grep
finds **zero** occurrences of those tool names outside this one file. It has
no `mcp.run()`, no `__main__` block, no console script, and no MCP
registration — so the server object is unreachable even as a standalone
process, while six live documents describe it as live. It is also the *only*
consumer of `crackerjack/integration/mahavishnu_integration.py` and
`crackerjack/memory/git_metrics_collector.py`.

### Decisions that need a call

These are the only genuinely open questions. Everything else in this plan is
mechanical.

1. **The `crackerjack/mahavishnu/` namespace.** The tree is not a vendored
   copy of upstream `mahavishnu/` — it is a **fork with drifted APIs**. Three
   of its four substantive modules were written in parallel with upstream
   specs #8/#9/#10 on 2026-06-27 and upstream has since evolved past them
   (`SettingsPersister`/`activate()` vs upstream's
   `SettingsActivationPersister`/`record_activation()`; `TenantContextPack` as
   a Pydantic model with `CONTEXT_FILES` vs upstream's frozen dataclass with
   `compute_content_hash()`; `ProgressSnapshot` with a Typer `watch` CLI vs
   upstream's async `record_progress_snapshot`/`list_progress_snapshots`).
   Options: (a) re-fork the three from upstream's current APIs and rewrite
   their tests; (b) delete them together with their three test files and the
   `sys.path` shim. Either way **the `crackerjack/mahavishnu/` namespace
   should not survive** — parking crackerjack-local code under a foreign
   package name, and shadowing the real `mahavishnu` package via `sys.path`,
   is a hazard regardless of which option is chosen.
2. **`git_analytics.py`'s home.** (a) A console script
   `crackerjack-mahavishnu-git-analytics = "…:main"` with a `main()` that
   calls `mcp.run()`, registered in `.mcp.json` and a launchd plist —
   preserves the documented "standalone server" contract. (b) Relocate to
   `crackerjack/mcp/tools/git_analytics.py` and wire its eight tools into
   `crackerjack/mcp/tools/profiles.py` — makes them reachable on the existing
   crackerjack MCP wire (port 8676) with no new process to supervise. Note
   that upstream's own plan lists registering this tool as an explicit
   **Non-Goal** (`docs/plans/2026-10-31-mcp-substrate-rewire.md:58`), so
   upstream will not take it over.
3. **The four documented-but-unwired features (category C).** Wire them, or
   correct the documentation to say they are not wired. This plan's default
   is *correct the documentation* — four of them are large, and "wire the
   self-improvement loop" is a feature project, not a cleanup.
4. **`crackerjack.exceptions` and `crackerjack.contracts` are published public
   API.** `crackerjack.exceptions` ships a README documenting
   `ToolExecutionError` / `ConfigIntegrityError` as the public exception
   hierarchy, and `CONTRIBUTING.md:222-228` tells contributors to
   `from crackerjack.exceptions import CheckError, ConfigurationError` —
   **neither name exists** (`__init__.py:1-4` exports only
   `PluginTrustError` and `ToolExecutionError`), so the contributing guide is
   already stale. `crackerjack/contracts.py` is a 24-line back-compat
   re-export shim over `mcp_common`. No known consumer imports either
   (fleet-wide import surface is two modules), and pre-1.0 policy is replace
   not extend — so deletion is defensible, but it is a **published-API
   change**, which makes it a MINOR bump, and the stale `CONTRIBUTING.md`
   snippet must be fixed in the same commit.

### What else the sweep turned up

Three live-code defects surfaced during the verification. They are **not**
part of this plan's deletions; they are recorded here so the work is not
lost.

1. **`hook_executor.py:2283` passes a tool name to a factory that wants an
   adapter name.** `adapter_factory.create_adapter(hook.name)` where
   `hook.name` is `"ruff"`, `"complexipy"`, `"gitleaks"`… but
   `adapters/factory.py:140-147` keys its table by `"Ruff"`, `"Bandit"`,
   `"Semgrep"`, `"Refurb"`, `"Pyrefly"`, `"Ty"`. Verified at runtime:
   `create_adapter('ruff')` → `ValueError: Unknown adapter: ruff`;
   `create_adapter('Ruff')` → `RuffAdapter`. The `ValueError` is swallowed by
   the `except Exception` at `hook_executor.py:2327-2332`, so
   `_try_get_qa_result_for_hook` returns `None` for **every** tool, and the
   QA-result integration in the hook executor never runs. The server side
   (`crackerjack/server.py:61-95`) uses the correct names and does work.
2. **A `MODULE_ID` UUID collision.** The dead
   `adapters/benchmark/adapter.py:31` and the **live**
   `adapters/ai/unified.py:16` both declare
   `UUID("a1b2c3d4-e5f6-7890-abcd-ef1234567890")`. Harmless today because
   the benchmark adapter is dead; a landmine if it is ever wired, since the
   two would emit identical `check_id` values into a `QAResult`.
3. **Six live documents describe the git-analytics MCP server as running**
   (`docs/MCP_TOOLS_SPECIFICATION.md:61-62,252,313`,
   `docs/architecture/MEMORY_ARCHITECTURE.md:222,1006-1007,1202,1397`,
   `docs/features/SYMBIOTIC_ECOSYSTEM_INTEGRATION.md:14-15`,
   `docs/task-breakdown.md:7`, and
   `crackerjack/memory/git_metrics_collector.py:9-19`). It has no launcher.
   `MEMORY_ARCHITECTURE.md:54` also documents
   `crackerjack/memory/git_metrics_storage.py`, a module that no longer exists.

---

## Phase 1 — Stop shipping tests inside the package

### Scope

`crackerjack/tests/` holds four modules (851 lines) of legitimate tests in the
wrong directory:

| Module | Lines | Path |
|---|---|---|
| `crackerjack.tests.checks` | 0 | `crackerjack/tests/checks/__init__.py` |
| `crackerjack.tests.checks.test_gitignore_conformance` | 200 | `crackerjack/tests/checks/test_gitignore_conformance.py` |
| `crackerjack.tests.checks.test_release_audit` | 489 | `crackerjack/tests/checks/test_release_audit.py` |
| `crackerjack.tests.test_runtime_facts` | 162 | `crackerjack/tests/test_runtime_facts.py` |

They are excluded from every automated path (`pyproject.toml:560-562` sets
`testpaths = ["tests"]`; the repo has no `.github/workflows/` directory; no
script invokes them) but they **ship to PyPI**, because
`pyproject.toml:230-235` includes `crackerjack/**/*.py`. The built
`dist/crackerjack-0.93.0-py3-none-any.whl` contains all five files.

They are not dead code — they are misfiled. `test_release_audit.py:20-36`
resolves fixtures from a sibling `mcp-common` checkout and skips when absent,
so in a wheel install it silently skips.

### Integration Contract

- **Triggered from**: the wheel build (`hatchling`).
- **Returns to / updates**: `pyproject.toml` `[tool.hatch.build.targets.wheel].include`;
  the repo's `tests/` tree.
- **Demonstrable by**: the built wheel contains no `crackerjack/tests/` file;
  `pytest tests/checks/test_release_audit.py -q` passes; the full suite count
  is unchanged.
- **Rollback signal**: the release audit's collect-only step stops finding the
  relocated tests.
- **Observability added**: none needed — this is a file move.

### Resolved decisions

1. **Relocate, do not delete.** The three test modules are correct tests in
   the wrong directory. Move them to `tests/checks/` and `tests/unit/`, fix
   their relative-path assumptions (`test_runtime_facts.py:23-28` computes
   `Path(__file__).resolve().parents[1] / "core" / "runtime_facts.py"` — the
   depth changes when it moves), and add `crackerjack/tests/**` to the wheel's
   exclude list so a stale copy can never ship again.
2. **`tests/checks/test_release_audit.py` already exists** (1,294 lines, 95
   tests) and would collide with the relocated copy. The two are
   complementary, not redundant: the repo-level file unit-tests the audit's
   internals against synthetic `tmp_path` trees, while the in-package one
   runs the audit end-to-end against **fixtures from the sibling `mcp-common`
   checkout** and skips when that checkout is absent. The relocated file
   needs a distinct name — `tests/checks/test_release_audit_e2e.py` — not a
   merge, because the fixture-based coverage does not exist anywhere else.
3. **Keep the `mcp-common` fixture skip.** `test_release_audit.py` skipping
   when the sibling checkout is absent is correct behaviour for a
   repo-local test.
4. **`tests/checks/test_gitignore_conformance.py` and
   `tests/unit/test_runtime_facts.py` are free** — no collision.

### Risks

1. **`test_release_audit.py` depends on a sibling repo.** It resolves
   `mcp-common` fixtures relative to the repo root. After the move the
   relative depth changes. Mitigation: re-read the fixture resolver before
   moving and adjust the depth explicitly, not by trial and error.
2. **A second copy could reappear.** Mitigation: the wheel exclude list, plus
   a note in `crackerjack/tests/`'s replacement location.

### Estimated scope

3 files moved, 1 `pyproject.toml` edit, ~851 lines relocated.

---

## Phase 2 — Delete the plugin system and the websocket server

### Scope

Two self-contained subsystems with no runtime caller.

**`crackerjack/plugins/` — 5 modules, 1,106 lines.**
`PluginManager` is instantiated only in tests; `PluginManager.initialize()` is
never called from production. `PluginDiscovery.discover_in_project()` scans
`<project>/plugins`, `<project>/.cache/crackerjack/plugins`, and
`<project>/tools/crackerjack` — not crackerjack's own package — and loads
files with `importlib.util.spec_from_file_location`. There is no CLI
subcommand, no MCP tool, no settings entry, and no entry point.

Its only non-test consumer, `examples/custom_hook_plugin.py:5-11`, imports
`CustomHookDefinition` and `HookStage` from `crackerjack.plugins` — which
does not export them. Verified: `ImportError: cannot import name
'CustomHookDefinition' from 'crackerjack.plugins'`. The one showcase of the
system cannot even import.

**`crackerjack/websocket/` — 4 modules, 551 lines.**
`CrackerjackWebSocketServer` is never instantiated in production. No CLI
subcommand starts it, no MCP tool starts it, and the only crackerjack launchd
plist on the machine (`~/Library/LaunchAgents/com.mcp.crackerjack.plist`)
runs `python -m crackerjack.mcp.server_core`, which loads zero
`crackerjack.websocket.*` modules. `mcp_websocket_port: 8696`
(`settings/crackerjack.yaml:194`) is a write-only field — defined in four
places, read by none. The MCP server's WebSocket transport comes from
`mcp_common` via `crackerjack/contracts.py:6`, not from this package.

### Integration Contract

- **Triggered from**: the CLI, the MCP server, `python -m crackerjack`.
- **Returns to / updates**: `pyproject.toml` lint excludes
  (`crackerjack/websocket/**` at `:349`, `crackerjack/plugins/**` at `:381`,
  `"crackerjack/plugins/*"` at `:642`).
- **Demonstrable by**: `import crackerjack.plugins` and
  `import crackerjack.websocket` raise `ModuleNotFoundError`; the MCP server
  still starts and still serves its tools; `examples/custom_hook_plugin.py`
  is gone.
- **Rollback signal**: any import of `crackerjack.plugins` or
  `crackerjack.websocket` fails at startup.
- **Observability added**: none needed.

### Resolved decisions

1. **Delete `examples/custom_hook_plugin.py` with the plugin system.** It
   raises `ImportError` today and is referenced by nothing.
2. **Do not keep `crackerjack/contracts.py` "for the websocket server".** The
   server is dead; `contracts.py` is a separate target in Phase 4.
3. **Leave `mcp_websocket_port` alone.** It is a settings field, not a module.
   Removing it is a settings-schema change and out of scope here; it is
   recorded as a follow-up.

### Risks

1. **A plugin shipped in a user's project directory.** `discover_in_project()`
   scans the *user's* project for plugin files. Since nothing calls the
   loader, that path is unreachable today — but if a user has a
   `plugins/` directory in their repo expecting crackerjack to pick it up,
   this removal makes that expectation permanently false. Mitigation: the
   CHANGELOG entry states the plugin system was never enabled.
2. **`docs/CLI_REFERENCE.md:160` and `:199` describe a "WebSocket Server" on
   port 8675.** That is the MCP server's transport, supplied by
   `mcp_common`, and the port does not even match the setting (8696). The
   doc is already stale; Phase 7 corrects it.

### Estimated scope

10 modules, 1,657 lines, 1 example, 3 lint-exclude edits.

---

## Phase 3 — Delete the unused QA adapters

### Scope

23 modules, 4,495 lines under `crackerjack/adapters/`: `benchmark/` (3),
`complexity/` (3), `dependency/` (2), `format/mdformat.py`, `health_mixin.py`,
`lint/` (2), `performance/` (2), `security/` (3), `test/` (2),
`treesitter/` (2), `utility/` (2).

There are exactly three adapter registration mechanisms in this codebase, and
none reaches this cluster:

1. **QA / tool adapters** — a hardcoded six-entry dict at
   `adapters/factory.py:140-147` (`Ruff`, `Bandit`, `Semgrep`, `Refurb`,
   `Pyrefly`, `Ty`), resolved via `__import__(f"crackerjack.adapters.{module_path}")`
   at `:153-157`, plus `Claude AI` / `FallbackChain` at `:102-105`. Zero from
   this cluster.
2. **Language adapters** — PEP 621 entry points
   (`[project.entry-points."crackerjack.language_adapters"]`, four entries),
   read by `adapters/registry.py:82,85-125`. Zero from this cluster.
3. **The legacy `AdapterRegistry`** (`adapters/registry.py:20-61`) — its
   `register()` has zero production callers; its own docstring says it is
   *"Only consumed by tests/adapters/test_adapter_registry.py"*.

**There is no directory scan.** `pkgutil` / `iter_modules` / `walk_packages`
appear nowhere in `crackerjack/`. `__init_subclass__` auto-registration does
not exist in `crackerjack/adapters/`. The plugin loader only ever loads
user-supplied files, never `crackerjack/adapters/**`.

### Integration Contract

- **Triggered from**: `adapters/factory.py`, `adapters/registry.py`, the MCP
  server, `cli/handlers/health.py`.
- **Returns to / updates**: `docs/reference/ADAPTER_UUID_REGISTRY.md`
  (records the deleted modules' UUIDs), the per-package READMEs under
  `crackerjack/adapters/*/README.md`.
- **Demonstrable by**: `create_adapter("Ruff")` still returns a `RuffAdapter`;
  `create_adapter("complexipy")` still raises `ValueError: Unknown adapter:
  complexipy`; the MCP server still starts and its `language_tools` still
  resolve the four language adapters.
- **Rollback signal**: `adapters/factory.py:140-147` no longer resolves.
- **Observability added**: none needed.

### Resolved decisions

1. **Delete the whole set, including the package `__init__.py` files.**
   `adapters/lint/__init__.py` is 1 line, `adapters/utility/__init__.py` is
   1 line — pure namespace markers for deleted packages.
2. **Do not delete the underlying tools.** `codespell`, `mdformat`,
   `gitleaks`, `betterleaks`, `complexipy`, `pymetrica`, `osv-scanner`, and
   `pyscn` all still run as hooks via `config/tool_commands.py`. This phase
   removes the *adapter classes*, not the tool behaviour. If the intent is to
   restore QA-result integration for these tools, the wiring bug in
   `hook_executor.py:2283` (see *What else the sweep turned up*) is the thing
   to fix — and it is a separate piece of work.
3. **`adapters/dependency/__init__.py` exports `OsvScannerAdapter` and
   `PipAuditAdapter` at package level**, so an external PyPI consumer could
   import them. No known consumer does. Pre-1.0, replace not extend.

### Risks

1. **`docs/reference/ADAPTER_UUID_REGISTRY.md` records the deleted UUIDs.**
   Nothing reads it, but it would become wrong. Phase 7 updates it.
2. **`scripts/create_test_templates.py:104-113` names these adapters in
   template text** (`"mdformat_adapter"`, `"gitleaks_adapter"`,
   `"codespell_adapter"`, `"complexipy_adapter"`). Those are strings written
   into generated test files, not imports — but the generated tests would
   then import deleted modules. Phase 4 removes those template entries.
3. **The deleted adapters were never wired, but the wiring *intent* is
   visible in `_tool_has_qa_adapter`** (`hook_executor.py:2334+`), which lists
   `complexipy`, `codespell`, `mdformat`, `gitleaks` among 26 tool names. That
   set stays; it is a name set, not a class reference, and the path it guards
   is already dead for every tool (see the `hook_executor.py:2283` finding).

### Estimated scope

23 modules, 4,495 lines, 28 test-file references, 1 script edit.

---

## Phase 4 — Delete the mechanical dead core

### Scope

The remaining low-risk clusters, all of which are closed islands or files
with no importer:

| Cluster | Modules | Lines | Notes |
|---|---|---|---|
| `crackerjack.core` | 10 | 2,047 | `defaults`, `file_lifecycle`, `language_detector`, `performance`, `proactive_workflow`, `self_heal` + 3, `service_watchdog`. `core/__init__.py` is 0 bytes — no `__all__` re-exports to preserve. |
| `crackerjack.sop` | 5 | 334 | five modules that only reference each other |
| `crackerjack.data` | 3 | 262 | `data.models` ← `data.repository`, and `data.repository` has no importer |
| `crackerjack.models` | 3 | 825 | `config_adapter`, `pydantic_models`, `resource_protocols` — none in `crackerjack/models/__init__.py`'s 39-name `__all__`; `pydantic_models.py` has zero references repo-wide |
| `crackerjack.utils` | 4 | 485 | `console_utils`, `error_handling`, `python_fixups`, `retry_utils` |
| `crackerjack.executors` | 2 | 1,023 | `individual_hook_executor` (746), `tool_proxy` (277) |
| `crackerjack.managers` | 1 | 41 | `managers.constants` — zero importers |
| `crackerjack.contracts` | 1 | 24 | back-compat re-export shim over `mcp_common`; only importer is the dead `websocket/server.py` |
| `crackerjack.ui` | 1 | 0 | 0-byte `__init__.py` plus a README; ships to PyPI as an empty package |
| `crackerjack.security` | 1 | 210 | `security.audit` |
| `crackerjack.ci_feedback` | 1 | 338 | |
| `crackerjack.py313` | 1 | 191 | **not** a version-gated shim — no `sys.version_info` check anywhere references it |
| `crackerjack.tools` | 1 | 180 | `validate_input_validator_patterns` — a pytest-shaped module (`main`, `test_sql_injection_patterns`) masquerading as a tool; not registered in `tool_commands.py` |
| `crackerjack.exceptions` | 4 | 185 | published public API — see the decisions below |
| `crackerjack.integration` | 1 | 156 | `mahavishnu_integration` — the only consumer is the dead `git_analytics.py` |
| `crackerjack.memory` | 2 | 120 | `memory/__init__.py` is 0 bytes |

### Integration Contract

- **Triggered from**: the CLI, the MCP server, `python -m crackerjack`.
- **Returns to / updates**: `crackerjack/models/protocols.py` (four
  protocols lose their only implementation), `crackerjack/integration/__init__.py`
  (its docstring already records the `mahavishnu_integration` removal),
  `CONTRIBUTING.md` (stale exception names).
- **Demonstrable by**: `import crackerjack.contracts` and
  `import crackerjack.exceptions` raise `ModuleNotFoundError`;
  `crackerjack.models.protocols` still imports; the CLI still runs.
- **Rollback signal**: an `ImportError` at CLI or MCP startup.
- **Observability added**: none needed.

### Resolved decisions

1. **`crackerjack.exceptions` and `crackerjack.contracts` are deleted, and the
   stale docs are fixed in the same commit.** `CONTRIBUTING.md:222-228` tells
   contributors to import `CheckError` and `ConfigurationError` from
   `crackerjack.exceptions`; neither name exists in
   `crackerjack/exceptions/__init__.py:1-4`, which exports only
   `PluginTrustError` and `ToolExecutionError`. The contributing guide is
   already broken and is corrected here. `crackerjack/exceptions/README.md`
   goes with the package.
2. **The four orphaned protocols in `crackerjack/models/protocols.py` are
   removed or marked.** `DebuggerProtocol:713`, `MemoryOptimizerProtocol:739`,
   `QualityIntelligenceProtocol:903`, and
   `UnifiedConfigurationServiceProtocol:394` become unimplemented once their
   only implementations are deleted. A protocol with no implementation is
   dead API surface; remove them unless a live module still references them.
3. **Do not delete `crackerjack/core/performance_monitor.py`.** It is live
   (`core/async_workflow_orchestrator.py:6`). Only `core/performance.py`
   (263 lines) is a target, and the two are different modules with confusingly
   similar names.
4. **`crackerjack/memory/__init__.py` stays as a 0-byte marker** if any
   live module imports the package. If not, the package goes with
   `git_metrics_collector.py` — but `git_analytics.py` needs it, and that
   file's fate is Phase 6. **Defer the `crackerjack.memory` pair to Phase 6.**
5. **`crackerjack/tools/validate_input_validator_patterns.py` is deleted, and
   its two test files with it** (`tests/test_validate_input_validator_patterns.py`,
   `tests/tools/test_validate_input_validator_patterns.py`).

### Risks

1. **`crackerjack/integration/__init__.py` is live** (it exports the learning
   adapters). Only `mahavishnu_integration.py` inside it is a target — do not
   delete the package `__init__.py`.
2. **`crackerjack/ui/` ships to PyPI as an empty package today.** Deleting it
   is a small win but removes a documented namespace (`crackerjack/ui/README.md`
   says *"User interface components and templates"*). It has no code, so there
   is nothing to lose.
3. **`docs/specs/2026-05-20-ai-fix-comprehensive-overhaul-design.md:218` and
   `docs/plans/2026-06-02-ai-fix-display-loop-bugs.md:42` reference
   `crackerjack/ui/ai_fix_dashboard.py`.** That file does not exist — the
   references are already stale. Phase 7 removes them.

### Estimated scope

38 modules, 8,340 lines, ~40 test files.

---

## Phase 5 — Delete the dead service modules

### Scope

41 modules, 9,519 lines under `crackerjack/services/`. They group into
closed islands, and one of them — `services/patterns/` — is **live** and
stays.

**Do not delete:** `crackerjack/services/patterns/` (33 modules, 2,787 lines)
and its two siblings `patterns/core.py` and `patterns/operations.py`. The
package's `__init__.py:1-15` eagerly imports every submodule and `:22-33`
unions their `PATTERNS` dicts into `SAFE_PATTERNS` — 180 validated patterns
that back input validation, path security, the coverage ratchet, publish
version bumping, the MCP job-id validator, and the AI templates.
`crackerjack/services/regex_patterns.py:1` is the bridge, and it has sixteen
live production importers.

**Delete — pure dead islands:**

| Island | Modules | Lines |
|---|---|---|
| self-improvement loop *(category C — see decisions)* | `self_patcher`, `improvement_generator`, `improvement_overseer`, `constitution` | 515 |
| pool orchestration *(stale duplicate of `swarm_client.py`)* | `pool_client`, `pool_orchestrator`, `pool_router`, `pool_scaler` | 851 |
| version / tool-update | `tool_version_service`, `version_checker`, `smart_scheduling` | 452 |
| quality intelligence | `quality.quality_intelligence`, `quality.quality_baseline_enhanced`, `quality.pattern_cache`, `quality.anti_ai_flavor_adapter` | 605 |
| debug / dedup | `debug`, `message_deduplicator` | 935 |
| incremental / tool filter | `tool_filter`, `incremental_executor`, `profiler`, `incremental_scanner` | 839 |
| safe code modifier *(category C)* | `safe_code_modifier`, `async_file_io` | 557 |
| stale duplicates | `predictive_analytics`, `smart_file_filter_v2`, `metrics`, `intelligent_commit` | 1,149 |
| standalone orphans | `refurb_fixer` (1,286), `regex_utils` (406), `memory_optimizer` (420), `prompt_evolution` (279), `command_execution_service` (219), `memory_aware_scanner` (216), `validation_rate_limiter` (221), `marker_tracker` (146), `config_integrity` (137), `unified_config` (105), `file_chunker` (101), `constants` (50), `import_resolution` (30), `terminal_utils` (0) | 3,626 |

### Integration Contract

- **Triggered from**: `crackerjack/api.py`, `code_cleaner.py`, the MCP
  server, `publish_manager.py`, the coverage ratchet.
- **Returns to / updates**: `scripts/validate_imports.py:20` and
  `scripts/migrate_ulids.py:10`; `SECURITY.md` and
  `docs/reference/SECURITY.md` (the `validation_rate_limiter` claim);
  `docs/architecture/MEMORY_ARCHITECTURE.md` (the self-improvement loop and
  the `git_metrics_storage.py` reference to a module that no longer exists);
  `docs/plans/2026-08-06-crackerjack-ruff-fix-policy.md` and its spec (the
  `SafeCodeModifier` routing requirement).
- **Demonstrable by**: `from crackerjack.services.regex_patterns import
  SAFE_PATTERNS` still works and still holds ≥180 patterns;
  `import crackerjack.services.refurb_fixer` raises `ModuleNotFoundError`;
  `scripts/validate_imports.py` exits 0.
- **Rollback signal**: an `ImportError` at CLI or MCP startup, or
  `SAFE_PATTERNS` coming back short.
- **Observability added**: none needed.

### Resolved decisions

1. **The four category-C features are deleted and their documentation is
   corrected.** Default: correct the docs, because wiring the self-improvement
   loop is a feature project and not a cleanup.
   - `safe_code_modifier` → the ruff-fix-policy plan's `.bak`-sibling
     requirement is marked as never-implemented, not silently dropped.
   - `validation_rate_limiter` → removed from the *Core Security Components*
     list in `SECURITY.md` and `docs/reference/SECURITY.md`, with the
     integration snippet removed.
   - the self-improvement loop → `MEMORY_ARCHITECTURE.md`'s Phase-3 chain
     diagram is marked as the unwired design it was.
   - `memory_optimizer` → `core/phase_coordinator.py:77` keeps the parameter
     (the protocol is live in `models/protocols.py`), but the module behind it
     goes and the parameter's docstring is corrected to say no implementation
     is wired.
2. **`services/constants.py` goes.** Its `DEFAULT_CACHE_TTL` match against
   `core/defaults.py:116` is a name collision, not an import — verified:
   `from .constants import` has no hits outside `crackerjack/cli/constants.py`.
3. **`services/terminal_utils.py` is a 0-byte file** — the cheapest deletion
   in the set.
4. **`services/quality/anti_ai_flavor_adapter.py` goes, but
   `services/quality/anti_ai_flavor.py` stays.** The base module is live via
   `cli/anti_ai_flavor_cli.py:6`; the adapter wrapper
   `run_anti_ai_flavor_check()` has no caller.
5. **Two script repairs are part of this phase**, not a follow-up:
   `scripts/validate_imports.py:20` drops
   `"crackerjack.services.memory_optimizer"` from `CRITICAL_MODULES` (the
   script `importlib.import_module`s every entry, so a stale entry fails the
   script), and `scripts/migrate_ulids.py:10` switches from
   `crackerjack.services.metrics` to `crackerjack.monitoring`.

### Risks

1. **`services/metrics.py` vs `crackerjack/monitoring.py`.** Both define a
   `MetricsCollector`. `scripts/migrate_ulids.py` imports the dead one and
   `documentation/dual_output_generator.py:248` documents the live one. A
   blind search-and-replace picks the wrong file. Mitigation: edit the import
   by exact path.
2. **`services/predictive_analytics.py` vs `services/ai/predictive_analytics.py`.**
   Same class name, different behaviour; `cli/handlers/analytics.py:432`
   imports the `ai.` one. Same mitigation.
3. **`services/intelligent_commit.py` vs `services/ai/intelligent_commit.py`.**
   Both define `CommitMessageGenerator`; the `ai.` version has a different
   constructor signature (`git_service` first, `console` optional). The root
   one is the older relative-import copy. Do not swap one for the other.
4. **`services/quality/pattern_cache.py` vs `services/pattern_cache.py`.**
   The former is a stale twin; the latter is live via
   `services/pattern_detector.py:13`.
5. **Coverage moves.** Deleting 9,519 lines of production code and ~26,000
   lines of test code changes the coverage denominator. The `--cov-fail-under`
   mirror must be recomputed — see Phase 7.

### Estimated scope

41 modules, 9,519 lines, ~45 test files, 2 script edits, 5 doc edits.

---

## Phase 6 — Resolve the `crackerjack/mahavishnu/` fork

### Scope

10 modules, 3,716 lines under a namespace that is a **lie**: it suggests
"the mahavishnu package, vendored", but the package is neither upstream's nor
importable as upstream's.

| Module | Lines | Verdict |
|---|---|---|
| `crackerjack.mahavishnu` | 3 | empty stub — delete |
| `crackerjack.mahavishnu.mcp` | 3 | empty stub — delete |
| `crackerjack.mahavishnu.mcp.tools` | 3 | empty stub — delete |
| `crackerjack.mahavishnu.mcp.tools.git_analytics` | 3,275 | **unique content** — relocate and wire |
| `crackerjack.mahavishnu.observability` | 0 | 0-byte stub — delete |
| `crackerjack.mahavishnu.observability.adapter_runtime` | 127 | fork of upstream spec #8 — re-fork or delete with its test |
| `crackerjack.mahavishnu.tenancy` | 25 | self-referential re-export only — delete |
| `crackerjack.mahavishnu.tenancy.context_packs` | 123 | fork of upstream spec #9 — re-fork or delete with its test |
| `crackerjack.mahavishnu.workflows` | 0 | 0-byte stub — delete |
| `crackerjack.mahavishnu.workflows.progress` | 157 | fork of upstream spec #10 — re-fork or delete with its test |

The three forks were written in parallel with upstream specs #8/#9/#10 on
2026-06-27 (crackerjack `29db53fb` / `5cbc7bb4` / `7df846ac`; upstream
`5ee2d718` / `13fb51e8` / `0de0f6e8`) and have diverged since. Upstream has
since evolved past them; the crackerjack copies have not been touched since
2026-10-30.

### Integration Contract

- **Triggered from**: nothing in production. The three forks are reachable
  only from their own tests.
- **Returns to / updates**: `tests/unit/test_adapter_observability.py`
  (the `sys.path` shim), `tests/unit/test_progress_snapshots.py`,
  `tests/unit/mahavishnu/tenancy/test_tenant_context_packs.py`;
  `docs/MCP_TOOLS_SPECIFICATION.md`, `docs/architecture/MEMORY_ARCHITECTURE.md`,
  `docs/features/SYMBIOTIC_ECOSYSTEM_INTEGRATION.md`, `docs/task-breakdown.md`.
- **Demonstrable by**: the eight git-analytics tools answer on a registered
  MCP surface; `grep -rn "sys.path.insert" tests/` shows no `<repo>/crackerjack`
  insertion; `import mahavishnu` in the test session resolves to the real
  upstream package.
- **Rollback signal**: the relocated tools stop answering, or the test
  session's `mahavishnu` resolution changes.
- **Observability added**: the relocated server's own MCP tool list.

### Resolved decisions

1. **The `crackerjack/mahavishnu/` namespace does not survive in any form.**
   It parks crackerjack-local code under a foreign package name, and the
   `sys.path` shim shadows the real `mahavishnu` package for the rest of the
   pytest session. Both are hazards independent of which fork option is
   chosen.
2. **The three forks are deleted with their tests**, rather than re-forked.
   Re-forking means rewriting three test files against upstream's current
   dataclass/`record_activation`/`record_progress_snapshot` APIs — feature
   work with a clear owner, not cleanup. The crackerjack forks have had no
   production caller since they were written.
   - `tests/unit/test_adapter_observability.py` (19 tests) goes, and with it
     the `sys.path` shim.
   - `tests/unit/test_progress_snapshots.py` (289 lines) goes.
   - `tests/unit/mahavishnu/tenancy/test_tenant_context_packs.py` (205 lines)
     goes, and `tests/unit/mahavishnu/` with it.
3. **`git_analytics.py` is relocated to `crackerjack/mcp/tools/git_analytics.py`
   and its eight tools are wired into `crackerjack/mcp/tools/profiles.py`.**
   This is option (b) from *Decisions that need a call*: it makes the tools
   reachable on the existing crackerjack MCP wire (port 8676) with no new
   process to supervise, no plist, and no `mcp.run()` launcher to write. It
   also matches how every other crackerjack MCP tool is registered. Option
   (a) — a separate console script and launchd plist — adds a supervised
   process for eight tools that the existing server can serve.
4. **The two dependencies `git_analytics.py` needs move with it**:
   `crackerjack/integration/mahavishnu_integration.py` (156 lines) and
   `crackerjack/memory/git_metrics_collector.py` (120 lines) are its only
   consumers' only consumers. Since `git_analytics.py` becomes live, both
   become live, and they leave the dead set.
5. **The six stale documents are corrected** to describe the tools where they
   now live, and `MEMORY_ARCHITECTURE.md:54`'s reference to
   `crackerjack/memory/git_metrics_storage.py` — a module that no longer
   exists — is corrected.

### Risks

1. **`git_analytics.py` is 3,275 lines with an unfamiliar surface.** Moving
   it means it starts importing, for the first time, modules it was written
   against but never loaded (`crackerjack.integration.mahavishnu_integration`,
   `crackerjack.memory.git_metrics_collector`). Those modules have never been
   imported in a running process — they may not import cleanly, may have
   import-time side effects, or may reference the live `crackerjack.monitoring`
   and `services/file_filter` twins. **Mitigation: import the relocated
   module in isolation and exercise the eight tools before registering it.**
   This is the highest-risk step in the plan.
2. **`FastMCP` tool registration conflicts.** If any of the eight tool names
   collides with an existing crackerjack MCP tool name, registration fails
   at server start. Mitigation: check `crackerjack/mcp/tools/profiles.py` for
   the eight names before wiring.
3. **The `sys.path` shim's removal changes what `import mahavishnu` means
   for the rest of the suite.** If any other test depends on the shim's
   shadowing, it will now import the real upstream package — which is not
   installed in crackerjack's venv, so it will raise `ModuleNotFoundError`.
   Mitigation: `grep -rn "sys.path.insert" tests/` before touching the shim,
   and run the full suite after.
4. **`pyproject.toml:427`'s lint per-file-ignore for
   `crackerjack/mahavishnu/**`** goes away with the tree.
5. **The `FastMCP("crackerjack-mahavishnu-git-analytics")` server object
   becomes unused.** The relocated module should use the shared crackerjack
   server's registration pattern, not carry its own `FastMCP` instance —
   a module wired to its own FastMCP instance is unreachable even when every
   registration table has it.

### Estimated scope

10 modules, 3,716 lines, 3 test files (~513 lines), 1 module relocated
(3,275 lines), 4 doc edits, 1 lint-exclude edit, 1 MCP registration.

---

## Phase 7 — Documentation, changelog, ratchet, validation

### Scope

Everything the deletions leave behind.

1. **Live documents that name deleted modules.** 52 dead modules are named in
   live (non-`.archive/`) documentation across 23 files. Two of those are
   generated and need no manual edit (`crackerjack/docs/generated/api/API_REFERENCE.md`
   and `SERVICES.md`, 34 modules each — regenerate them). The rest:

   | File | Dead modules named |
   |---|---|
   | `docs/audits/2026-09-09-crackerjack-docs-audit.md` | 3 |
   | `docs/implementation/PHASE5_SERVICE_CONSOLIDATION_AUDIT.md` | 3 |
   | `docs/features/SYMBIOTIC_ECOSYSTEM_INTEGRATION.md` | 3 |
   | `crackerjack/adapters/{complexity,lint,security,utility,format}/README.md` | 2, 2, 2, 2, 1 |
   | `docs/performance/PHASE_2.2_COMPLETION_REPORT.md` | 2 |
   | `docs/task-breakdown.md` | 2 |
   | `CHANGELOG.md` | 1 |
   | `CONTRIBUTING.md` | 1 |
   | `crackerjack/exceptions/README.md` | 1 |
   | `SECURITY.md`, `docs/reference/SECURITY.md` | 1 each |
   | `crackerjack/core/README.md` | 1 |
   | `docs/plans/2026-08-06-crackerjack-ruff-fix-policy.md` | 1 |
   | `docs/ERROR_HANDLING_MIGRATION_GUIDE.md` | 1 |
   | `docs/MCP_TOOLS_SPECIFICATION.md` | 1 |
   | `docs/architecture/MEMORY_ARCHITECTURE.md` | 1 |
   | `docs/features/MAHAVISHNU_INTEGRATION.md` | 1 |
   | `docs/symbiotic-ecosystem-quick-start.md` | 1 |
   | `docs/plans/2026-10-28-oneiric-action-kit-adoption.md` | 1 |

   Archived documents under `docs/.archive/` are a historical record and are
   **not** rewritten — four modules are named only there.

2. **The CHANGELOG entry.** One `### Removed` entry per deleted module
   family. The release audit parses `### Removed` bullets and verifies each
   claim against disk; a dotted path ending in `.py`
   (`crackerjack.services.patterns.core.py`) is treated as a *file-path*
   claim and the audit checks that the file is gone — a stronger check than a
   prose bullet, which the backtick regex `([\w.]+)` cannot even match when
   the path contains a `/`. Use dotted `.py` paths.

3. **The coverage ratchet.** Deleting 26,659 production lines and ~35,000
   test lines moves the coverage denominator.
   `crackerjack/services/coverage_ratchet.py` has two mirror sites —
   `--cov-fail-under` in `[tool.pytest.ini_options].addopts` and
   `fail_under` in `[tool.coverage.report]` — and both must carry the same
   number (the 2026-11-13 commit `270c752c` fixed the case where only one
   was updated). Re-measure, then write both via
   `CoverageRatchetService.mirror_to_pyproject(coverage)`.

4. **The plan index.** `crackerjack.tools.plan_index_sync --repo-root . --out
   docs/plans/PLAN_INDEX.md` — and the *phase* variant of the tool, not
   `scripts/regenerate_plan_index.py`, which produces a different format.

### Integration Contract

- **Triggered from**: the release audit and the publish flow.
- **Returns to / updates**: `CHANGELOG.md`, `docs/`, `pyproject.toml`.
- **Demonstrable by**: the release audit passes; `crackerjack run -v -f`
  passes; the generated API docs no longer name a deleted module;
  `git grep -n "<deleted module>" -- docs/ ':!docs/.archive'` returns nothing
  for live docs.
- **Rollback signal**: the release audit reports a `Removed` claim whose file
  still exists, or the coverage floor disagrees between the two mirror sites.
- **Observability added**: none needed.

### Resolved decisions

1. **Archived docs are left alone.** `docs/.archive/` is a historical record;
   rewriting it falsifies the record.
2. **The generated API docs are regenerated, not hand-edited.**
3. **`pyproject.toml`'s version string is not touched.** The bump and the
   publish are the operator's.

### Risks

1. **Coverage could move in either direction.** Removing well-covered code
   lowers the percentage; removing uncovered code raises it. The ratchet only
   advances on improvement, so a drop needs `lower_baseline()` — and the
   2026-11-13 fix means both floor fields are written together.
2. **The generated API docs produce a large diff.** Expected; it is the point.

### Estimated scope

23 doc files, 1 CHANGELOG entry, 1 ratchet update, 1 plan-index regeneration.

---

## Risks

1. **The inventory tool has a systematic blind spot for relative-package
   submodule imports** (`from . import X`, `from .sibling import Y`). It hit
   30 modules / 2,787 lines in `services/` alone, and the previous plan's
   follow-up section (`docs/plans/2026-11-13-remove-dead-ai-fix-module-cluster.md:491-496`)
   lists *"the `services.patterns.*` families"* among the dead modules — the
   same blind spot. **Mitigation: the corrected resolver is in
   `/tmp/cj_dead_inventory_v2.py`, and the runtime import sweep (Phase 7
   verification) is the authority, not the AST.** If the inventory is reused,
   the fix travels with it.
2. **`git_analytics.py` has never been imported in a running process.**
   Relocating it turns on 3,275 lines of code whose own dependencies
   (`mahavishnu_integration`, `git_metrics_collector`) have likewise never
   run. Highest-risk step; mitigated by an isolated import-and-exercise check
   before registration.
3. **The `sys.path` shim's removal changes `import mahavishnu` for the whole
   test session.** The real upstream package is not installed in crackerjack's
   venv, so any test that was relying on the shim's shadowing will now fail
   with `ModuleNotFoundError`.
4. **Four stale-duplicate pairs share class names** (`predictive_analytics`,
   `intelligent_commit`, `metrics`, `pattern_cache`). A search-and-replace
   across the tree will pick the wrong file. Mitigation: edit by exact path.
5. **Shared test files need surgical edits, not deletion.** 39 test files
   import both dead and live modules — `tests/test_services_coverage.py` (7
   dead imports), `tests/test_qa_adapters_protocol_compliance.py` (5),
   `tests/test_qa_tool_adapters.py` (4), `tests/unit/test_coverage_targets.py`
   (3), `tests/conftest_reset.py` (2), `tests/test_shared_contracts.py` (2),
   `tests/adapters/test_benchmark_adapter.py` (2). 65 test files import only
   dead modules and are deleted whole.
6. **Published-API surface.** `crackerjack.exceptions` and
   `crackerjack.contracts` are importable by downstream consumers. No known
   consumer imports either (the fleet's Python surface is two modules), and
   pre-1.0 policy is replace not extend — but this is a MINOR-level change
   and the stale `CONTRIBUTING.md` snippet must be fixed in the same commit.
7. **The wheel shrinks by ~26,700 lines of production code and ~851 lines of
   test code.** That is the point, but it is a visible packaging change for
   anyone pinning a wheel hash.

---

## References

- Memory `feedback-no-backwards-compat-pre-1.0.md` — replace not extend; no
  deprecation windows
- Memory `bodai-pre-1.0-merge-policy.md` — direct merge to main pre-1.0
- Memory `feedback-bodai-push-is-user-controlled.md` — never push without
  explicit approval
- Memory `feedback-git-commit-only-pathspec-with-staged-changes.md` — commit
  with `--only` when the index holds other work
- Memory `feedback-no-claude-code-coauthor-attribution.md` — no
  `Co-Authored-By` trailer; author is `les@wedgwoodwebworks.com`
- Memory `feedback-keep-plan-files-tracked.md` — this file stays tracked
- `docs/plans/2026-11-13-remove-dead-ai-fix-module-cluster.md` — the
  predecessor plan; its follow-up section named `services.patterns.*` as a
  removal target, which this plan corrects
- `docs/plans/2026-10-11-remove-zuban-skylos-lsp-from-crackerjack.md` — the
  house format for a removal plan
- `docs/decisions/2026-11-01-ty-adapter-module-name-shadows-ty-distribution.md`
  — the same stale-duplicate pattern, in the adapter layer
- `docs/plans/2026-10-31-mcp-substrate-rewire.md:58` — upstream lists
  registering the git-analytics tool as an explicit Non-Goal
- `docs/plans/2026-08-06-crackerjack-ruff-fix-policy.md:544` and
  `docs/specs/2026-08-06-crackerjack-ruff-fix-policy-design.md:120,201` —
  the `SafeCodeModifier` routing requirement that is not in effect
- `crackerjack/checks/release_audit.py` — parses `### Added` / `### Removed`;
  a dotted `.py` path is verified against disk
- `crackerjack/services/coverage_ratchet.py` — `mirror_to_pyproject()` writes
  both coverage-floor mirror sites

---

## Execution record

_(To be filled in as the phases execute.)_
