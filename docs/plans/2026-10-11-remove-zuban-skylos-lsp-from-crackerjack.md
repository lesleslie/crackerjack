---
title: Remove Zuban + Skylos LSP Adapters from Crackerjack
description: Delete the now-unused zuban and skylos rust-tool adapters and the entire `crackerjack/adapters/lsp/` package. Skylos was already removed from `pyproject.toml`; zuban is no longer used. Both files, their base classes, the LSP client, the hook manager, the settings fields, the hook entries, the CLI command builders, the tool-proxy factories, and ~30+ test files all need cleanup.
audience: crackerjack maintainer
created: 2026-10-11
status: active
role: implementation
topic: architecture
date: 2026-10-11
last_reviewed: 2026-10-11
superseded_by: null
blocks_on: []
---

# Remove Zuban + Skylos LSP Adapters from Crackerjack

## Brief (intent-driven)

### Goal

`crackerjack/adapters/lsp/` directory and every reference to zuban/skylos in crackerjack source, settings, tests, and docs are gone. `ty` remains the default type checker; nothing in the user-facing quality gate regresses.

### Constraints

1. Skylos is already absent from `pyproject.toml` (the user removed it on 2026-10-11). This plan must finish the work: every other skylos reference must also go.
2. Zuban is no longer deployed; remove the `zuban>=0.10.0` runtime dep too.
3. `ty` (the active type checker) must remain functional. The default hook chain must not lose any non-zuban/skylos check.
4. The `crackerjack/adapters/lsp/` package becomes empty after removal — delete the entire directory, including `_base.py` (`RustToolAdapter` Protocol + `BaseRustToolAdapter` ABC), `_client.py` (`ZubanLSPClient`), `_manager.py` (`RustToolHookManager`), and `__init__.py`. Do NOT keep a stub for "future rust adapters" (YAGNI per pre-1.0 policy).
5. Pre-1.0 — direct merge to `main`, no PR, per `feedback-bodai-pre-1.0-merge-policy.md`.
6. The fleet-wide `BodaiAdapter` Protocol work is in flight in another session (mahavishnu, plan pending). This plan must not collide with that work — when in doubt, this plan lands first and the protocol work can re-introduce structured adapter bases later if needed.

### Failure Conditions (verifier-only)

1. `crackerjack/adapters/lsp/` directory does not exist after the change.
2. `git grep -nE "zuban|skylos" -- ':!*.bak' ':!*.archive' ':!CHANGELOG.md'` returns zero matches in `crackerjack/` source (CHANGELOG historical entries excluded; same for archive and bak files).
3. `uv run python -c "import crackerjack.adapters.lsp"` raises `ModuleNotFoundError`.
4. `crackerjack/adapters/lsp/_base.py`, `_client.py`, `_manager.py`, `__init__.py`, `skylos.py`, `zuban.py` are all deleted.
5. `crackerjack/config/settings.py` has no `enable_zuban`, `zuban_lsp*`, `zuban_timeout`, `skylos_timeout` fields; no `ZubanLSPSettings` class.
6. `crackerjack/config/hooks.py` has no zuban or skylos `Hook` entries; no `enable_zuban` gating logic.
7. `crackerjack/config/tool_commands.py` has no `_build_skylos_command` and no `_preferred_binary_command("zuban", ...)` call.
8. `crackerjack/executors/tool_proxy.py` has no `_create_zuban_adapter` or `_create_skylos_adapter` methods.
9. `pyproject.toml` no longer declares `zuban>=0.10.0`.
10. `settings/crackerjack.yaml` and `.crackerjack.example.yaml` have no `zuban_*` or `skylos_*` keys.
11. `pytest tests/` exits 0 (after test cleanup).
12. `crackerjack run` exits 0 on `crackerjack/` itself (the canonical self-test).

## Context

### Current state of the LSP module (verified 2026-10-11)

```
crackerjack/adapters/lsp/
  __init__.py    26 lines — re-exports SkylosAdapter, ZubanAdapter, ZubanLSPClient,
                          BaseRustToolAdapter, Issue, RustToolAdapter, ToolResult,
                          RustToolHookManager, TypeIssue, DeadCodeIssue
  _base.py      ~150 lines — RustToolAdapter (Protocol) + BaseRustToolAdapter (ABC)
                          + Issue + ToolResult + ExecutionContext
  _client.py    ~200 lines — ZubanLSPClient (zuban-specific, NOT shared with skylos)
  _manager.py   ~200 lines — RustToolHookManager (orphan if both adapters go)
  skylos.py     ~300 lines — SkylosAdapter (11443 bytes, concrete)
  zuban.py      ~350 lines — ZubanAdapter (14806 bytes, concrete)
```

`ZubanLSPClient` is imported only by `crackerjack/adapters/lsp/__init__.py` and `crackerjack/adapters/lsp/zuban.py` (verified by grep). Skylos has its own internal client surface, not via `ZubanLSPClient`.

`RustToolHookManager` is imported by `tests/adapters/lsp/test_lsp_manager.py` only — no production usage in the lsp module or elsewhere. Orphan if both adapters go.

`_create_zuban_adapter()` and `_create_skylos_adapter()` in `crackerjack/executors/tool_proxy.py:298-322` are defined but `grep` shows zero callers — they were scaffolding for a future health-check flow that never shipped.

### Settings surface (verified)

`crackerjack/config/settings.py`:
- Line 27: `enable_zuban: bool = False`
- Line 232: `zuban_lsp_timeout: float = 120.0`
- Line 233: `skylos_timeout: int = 900`
- Line 236: `zuban_timeout: int = 60`
- Line 418: `"skylos": "fast-worker"` (worker-pool mapping)
- Line 437: `"skylos",` (in some list)
- Line 512: `zuban_lsp: ZubanLSPSettings = ZubanLSPSettings()`

`crackerjack/config/hooks.py`:
- Line 273: comment "Primary type checker (replaced zuban). Active by default"
- Line 293: `name="zuban"` Hook entry
- Line 300: "Legacy type checker (opt-in via enable_zuban flag)"
- Line 347: `name="skylos"` Hook entry
- Line 469: `if getattr(settings.hooks, "enable_zuban", False):`
- Line 472-474: dynamically constructs a zuban hook from `enable_zuban`
- Line 493: comment "Primary ty type checking (default-on, replaced zuban)"

`crackerjack/config/tool_commands.py`:
- Line 65-72: `_build_skylos_command(package_name: str) -> list[str]`
- Line 151-153: `"skylos": _build_skylos_command(...)` and `"zuban": _preferred_binary_command("zuban", ...)`

`pyproject.toml`:
- Line 81: `"zuban>=0.10.0"` (in `[project].dependencies` or similar — verify exact section)
- Line 134: comment "pyrefly and ty are alternatives to zuban; install one to try them"
- Line 439-454: `zuban_lsp_*` and `zuban_timeout` settings (test defaults — verify section)

`settings/crackerjack.yaml`:
- Line 197-201: `zuban_enabled`, `zuban_auto_start`, `zuban_port`, `zuban_mode`, `zuban_timeout`
- Line 246-249: `zuban_lsp_timeout`, `skylos_timeout`, `zuban_timeout`

`.crackerjack.example.yaml`:
- Line 44: `- skylos` in some list

### Test surface (verified by grep, ~30+ files)

**Pure deletion (no edits needed):**
- `tests/unit/adapters/test_zuban_adapter.py`
- `tests/unit/adapters/test_skylos_adapter.py`
- `tests/adapters/test_zuban_adapter.py`
- `tests/adapters/test_skylos.py`
- `tests/adapters/lsp/test_lsp_skylos.py`
- `tests/adapters/lsp/test_zuban.py`
- `tests/adapters/lsp/test_lsp_manager.py`
- `tests/test_skylos_adapter.py`
- `tests/test_lsp_aware_hook_executor.py` (verify it's zuban/skylos-only)

**Edit to remove zuban/skylos references (names, mocks, sys.modules keys):**
- `tests/executors/test_tool_proxy.py` (heavy `crackerjack.adapters.lsp.{zuban,skylos,_base}` mocking at lines 752, 766, 767, 807, 808, 820, 844, 845)
- `tests/test_integration_new_hooks.py`
- `tests/test_qa_tool_adapters.py`
- `tests/test_profiler_integration.py`
- `tests/test_profiler.py`
- `tests/test_fast_iteration_mode.py`
- `tests/test_server.py`
- `tests/test_service_watchdog.py`
- `tests/test_tool_filter.py`
- `tests/unit/test_comprehensive_type_hooks.py`
- `tests/unit/test_config_settings.py`
- `tests/unit/parsers/test_regex_parsers_property.py`
- `tests/unit/parsers/test_json_parsers.py`
- `tests/unit/tools/test_git_utils.py`
- `tests/unit/core/test_autofix_coordinator.py`
- `tests/unit/parsers/test_regex_parsers.py`
- `tests/unit/config/test_hooks.py`
- `tests/unit/config/test_hooks_config.py`
- `tests/unit/adapters/test_factory.py`
- `tests/unit/utils/test_issue_detection.py`
- `tests/unit/exceptions/test_tool_execution_error.py`
- `tests/unit/services/test_lsp_client.py`
- `tests/core/test_session_controller.py`
- `tests/parsers/test_regex_parsers.py`
- `tests/config/test_tool_commands.py`
- `tests/integration/test_phase8_direct_invocation.py`
- `tests/models/test_pydantic_models.py`
- `tests/models/test_config_adapter.py`
- `tests/models/test_fix_plan.py`
- `tests/models/test_config.py`
- `tests/adapters/test_creosote.py`
- `tests/adapters/test_factory.py`
- `tests/adapters/test_tool_adapter_base.py`
- `tests/adapters/test_type_adapters.py`
- `tests/exceptions/test_tool_execution_error.py`
- `tests/fixers/test_dead_code.py`

(Some of the "edit" list may turn out to be zero edits after a final grep — that's fine; the test files just continue to pass.)

### Type-checker tool classification

`_tool_adapter_base.py:566`:
```python
if any(
    x in tool_lower
    for x in ("type", "pyright", "mypy", "zuban", "pyrefly", "ty")
):
    return QACheckType.TYPE
```

The "zuban" string in this set must come out (zuban is gone) but the rest stay (pyright, mypy, pyrefly, ty are independent type checkers).

## Approach

Six phases, ordered lowest-level-first so the test suite breaks loudly the moment we touch something that has unaccounted-for dependents. Each phase ends with `pytest tests/ -x` to surface the next round of broken tests before moving on.

### Phase 1 — Drop the runtime dep + settings fields

**Files:**
- `pyproject.toml` — remove `"zuban>=0.10.0"` from the deps section; update the comment on line 134
- `crackerjack/config/settings.py` — drop `enable_zuban`, `zuban_lsp_timeout`, `skylos_timeout`, `zuban_timeout`, the `ZubanLSPSettings` class, and the `"skylos": "fast-worker"` mapping
- `settings/crackerjack.yaml` — drop the `zuban_*` and `skylos_*` keys
- `.crackerjack.example.yaml` — drop the `- skylos` entry

**Integration Contract:**
- Triggered from: this plan (manual edit, no external trigger)
- Returns to / updates: `pyproject.toml`, `crackerjack/config/settings.py`, `settings/crackerjack.yaml`, `.crackerjack.example.yaml`
- Demonstrable by: `git grep -nE "zuban|skylos" -- pyproject.toml crackerjack/config/settings.py settings/ .crackerjack.example.yaml` returns zero matches (excluding the `zuban_timeout` line and any "zuban" mention inside `ZubanLSPSettings` that survived the deletion)
- Rollback signal: `pytest tests/unit/test_config_settings.py` fails on a missing field name OR `crackerjack run` errors at config load
- Observability added: none — pure deletion

### Phase 2 — Drop the hook + CLI command surface

**Files:**
- `crackerjack/config/hooks.py` — drop the zuban `Hook` entry (line 293) and the skylos `Hook` entry (line 347); drop the `if getattr(settings.hooks, "enable_zuban", False):` block (lines 469-477); drop the "replaced zuban" comments where they reference zuban specifically (keep the "ty is the default" intent)
- `crackerjack/config/tool_commands.py` — drop `_build_skylos_command` and the `"skylos"` / `"zuban"` entries in the command map

**Integration Contract:**
- Triggered from: Phase 1 complete
- Returns to / updates: `crackerjack/config/hooks.py`, `crackerjack/config/tool_commands.py`
- Demonstrable by: `git grep -nE "zuban|skylos" -- crackerjack/config/hooks.py crackerjack/config/tool_commands.py` returns zero matches; `crackerjack hooks --list` shows the remaining hooks intact; `crackerjack run --help` still parses
- Rollback signal: `pytest tests/unit/config/test_hooks.py tests/unit/config/test_hooks_config.py tests/config/test_tool_commands.py` fails
- Observability added: none — pure deletion

### Phase 3 — Drop the tool-proxy factories and the LSP package

**Files:**
- `crackerjack/executors/tool_proxy.py` — drop `_create_zuban_adapter()` (lines 299-310) and `_create_skylos_adapter()` (lines 312-323) and any caller references (verified zero callers in the prior assessment, but re-grep to be safe)
- `crackerjack/adapters/lsp/` — delete the entire directory: `zuban.py`, `skylos.py`, `_client.py`, `_manager.py`, `_base.py`, `__init__.py`, and the directory itself
- `crackerjack/executors/hook_executor.py` — verify no `LSKYLOS_LSP` / `LSP_AWARE_HOOK` references survive the package deletion (the prior assessment flagged this file but didn't read it; confirm during execution)

**Integration Contract:**
- Triggered from: Phase 2 complete
- Returns to / updates: `crackerjack/executors/tool_proxy.py`, deletes `crackerjack/adapters/lsp/` entirely
- Demonstrable by: `crackerjack/adapters/lsp/` does not exist; `uv run python -c "import crackerjack.adapters.lsp"` raises `ModuleNotFoundError`; `git grep -nE "adapters\.lsp" -- crackerjack/` returns zero matches
- Rollback signal: any test fails to import a class that lived in the lsp package
- Observability added: none — pure deletion

### Phase 4 — Test cleanup

**Delete:**
- All 8-9 dedicated test files listed in "Test surface / Pure deletion" above
- `tests/test_lsp_aware_hook_executor.py` if confirmed zuban/skylos-only (otherwise just edit)

**Edit to remove references:**
- All 30+ files in "Test surface / Edit" list
- Specifically: in `tests/executors/test_tool_proxy.py`, remove the `patch.dict("sys.modules", {"crackerjack.adapters.lsp.zuban": ...})` and the `monkeypatch.setitem(_sys.modules, ...)` calls
- In `_tool_adapter_base.py:566`, remove `"zuban"` from the type-checker name set (keep `"type", "pyright", "mypy", "pyrefly", "ty"`)

**Integration Contract:**
- Triggered from: Phase 3 complete
- Returns to / updates: `tests/**`, `crackerjack/adapters/_tool_adapter_base.py`
- Demonstrable by: `pytest tests/` exits 0; `git grep -nE "zuban|skylos" -- tests/` returns zero matches
- Rollback signal: any test failure after the edits
- Observability added: none

### Phase 5 — Docs cleanup

**Files:**
- `README.md` — remove zuban/skylos from any "supported tools" or "type checkers" lists
- `CHANGELOG.md` — leave historical entries intact; add a new entry under the unreleased section noting "Removed: zuban and skylos LSP adapters; `crackerjack/adapters/lsp/` package deleted"
- Any other top-level docs that mention zuban/skylos as currently-supported tools (audit via `git grep -l zuban -- docs/`)

**Integration Contract:**
- Triggered from: Phase 4 complete
- Returns to / updates: `README.md`, `CHANGELOG.md`, possibly other top-level docs
- Demonstrable by: `git grep -nE "zuban|skylos" -- README.md CHANGELOG.md` returns only historical/changelog references (acceptable); `docs/` returns no currently-active references
- Rollback signal: docs audit fails (e.g. README still claims zuban is supported)
- Observability added: none

### Phase 6 — Final validation

- `uv sync` then `pytest tests/` → exits 0
- `crackerjack run` on `crackerjack/` itself → exits 0
- `crackerjack mcp start` then `curl localhost:8676/health` → 200
- `git grep -nE "zuban|skylos" -- ':!*.bak' ':!*.archive' ':!CHANGELOG.md' ':!*.git' ':!node_modules'` → only matches in CHANGELOG.md (historical) and any `uv.lock` (dep lockfile will get regenerated by `uv sync`)

**Integration Contract:**
- Triggered from: Phase 5 complete
- Returns to / updates: nothing (validation only)
- Demonstrable by: all of the above checks pass
- Rollback signal: any check fails
- Observability added: none

## Resolved decisions

1. **Delete the whole `crackerjack/adapters/lsp/` directory**, not just the concrete adapters. `RustToolAdapter` Protocol and `BaseRustToolAdapter` ABC have zero remaining concrete subclasses after this — keeping them violates YAGNI per `feedback-no-backwards-compat-pre-1.0.md`. The fleet-wide `BodaiAdapter` Protocol work (in flight in another session) can re-introduce structured bases later if the ecosystem needs them.
2. **Delete `ZubanLSPClient`** — verified zuban-specific, no other consumer.
3. **Delete `RustToolHookManager`** — verified only consumed by its own test file (`tests/adapters/lsp/test_lsp_manager.py`).
4. **Drop `zuban>=0.10.0` from `pyproject.toml`** even though skylos is already gone — zuban must also leave the dep list.
5. **Don't gate the deletion on the fleet-wide `BodaiAdapter` Protocol work.** The protocol work may want to re-introduce a `BaseRustToolAdapter` for future rust adapters, but we don't ship a stub now. The protocol can add it later with its own reasoning.
6. **Don't bother with backwards-compat shims.** Pre-1.0, replace not extend. Any external caller importing `crackerjack.adapters.lsp.*` gets a `ModuleNotFoundError` and fixes their import. (None expected — this is a oneiric-coupled internal package.)
7. **Edit `_tool_adapter_base.py:566` to remove `"zuban"` from the type-checker name set.** Keep `"type", "pyright", "mypy", "pyrefly", "ty"` since those are independent tools.

## Risks

1. **Hidden test breakage.** The grep found 30+ test files that reference zuban/skylos by name. The `tests/executors/test_tool_proxy.py` mocking is the riskiest — it does deep `sys.modules` patching. Mitigation: do the test cleanup in Phase 4 with `pytest tests/ -x` between edits to surface failures incrementally.
2. **`crackerjack/executors/hook_executor.py` LSP-aware code path.** The prior assessment flagged `LSKYLOS_LSP` markers in this file but didn't read it. If the LSP-aware hook executor couples to the lsp package, deletion breaks it. Mitigation: read the file in Phase 3 BEFORE deleting the lsp directory. If there's coupling, port or remove the LSP-aware path (decision deferred to execution).
3. **Settings-layer validation.** `crackerjack/config/settings.py:512` declares `zuban_lsp: ZubanLSPSettings = ZubanLSPSettings()`. The `ZubanLSPSettings` class itself must come out. Verify no other settings field references the type (grep `ZubanLSPSettings`).
4. **`hooks` config schema drift.** `crackerjack/config/hooks.py:469` reads `settings.hooks.enable_zuban`. If user YAML files in the wild have `hooks.enable_zuban: true`, the schema will silently drop it (settings is `extra="allow"`? — verify). Add a one-line "RemovedInVersionX" warning if we want to be friendly, but pre-1.0 policy says no.
5. **CHANGELOG bloat.** The existing CHANGELOG has many historical zuban/skylos entries. We do not rewrite history. Add a single new "Removed" line in the unreleased section.
6. **The fleet-wide `BodaiAdapter` Protocol session is in flight.** If that work depends on `BaseRustToolAdapter` or any other class from `crackerjack/adapters/lsp/`, this plan conflicts. Mitigation: check with the other session before Phase 3. If they're not ready, defer Phase 3 until they are. (The other session is `BodaiAdapter` Protocol; rust adapters are orthogonal, but verify.)
7. **`crackerjack run` regression on fleet repos.** If any fleet repo's `settings/crackerjack.yaml` has a `zuban_*` or `skylos_*` key, deleting the settings field will trigger `extra="allow"` storage (silent drop, not error). Not a blocker for this plan, but worth a follow-up note to fleet owners via CHANGELOG.

## References

- Memory `feedback-no-backwards-compat-pre-1.0.md` — replace not extend; no deprecation windows
- Memory `bodai-pre-1.0-merge-policy.md` — direct merge to main pre-1.0; no PRs
- Memory `feedback-bodai-push-is-user-controlled.md` — never `git push` for bodai without explicit approval
- Memory `feedback-keep-plan-files-tracked.md` — `git add docs/plans/*.md` first
- Memory `feedback-mcp-common-version-bump-is-user.md` — never bump version in any Bodai `pyproject.toml` (don't trigger this when removing `zuban>=0.10.0`)
- Memory `feedback-rename-brief-must-enumerate-all-string-literals.md` — verify every literal `zuban`/`skylos` is removed; the grep covers this
- Memory `feedback-cli-flag-consumer-wiring.md` — `enable_zuban` flag → grep every instantiation site before removing
- Memory `docs-audit-removed-but-referenced.md` — every Bodai deletion PR should grep docs for removed symbols
- `docs/decisions/wire-up-contract.md` — Integration Contract pattern (Triggered from / Returns to / Demonstrable by / Rollback signal / Observability added)
- Plan template: `docs/plans/TEMPLATE.md` (if present, else this format follows the 2026-09-07-bodai-shared-gitignore-snippet plan)
- Companion plan: `docs/plans/2026-10-10-crackerjack-oneiric-loader-migration.md` — orthogonal but both touch the settings/loader layer; do not conflict, but coordinate if both run in parallel

## Estimated scope

| Phase | Effort |
|---|---|
| 1. Settings + dep cleanup | 20 min |
| 2. Hooks + CLI commands | 30 min |
| 3. Tool proxy + lsp package deletion | 45 min (incl. `hook_executor.py` verification) |
| 4. Test cleanup | 2-3 hr (30+ files, incremental) |
| 5. Docs cleanup | 20 min |
| 6. Final validation | 15 min |
| **Total** | ~4-5 hr |

Ship target: end of week (per the user's note "we'll take care of that in a separate session").

## Coordination notes

- The fleet-wide `BodaiAdapter` Protocol work is in another session. Before Phase 3, ping the protocol session to confirm no dependency on `crackerjack/adapters/lsp/`. If there is, defer Phase 3 until the protocol lands.
- This plan is `status: active` but execution is deferred to a separate session per the user's instruction.
- `feedback-keep-plan-files-tracked.md`: remember to `git add docs/plans/2026-10-11-remove-zuban-skylos-lsp-from-crackerjack.md docs/plans/PLAN_INDEX.md` before any commit.
