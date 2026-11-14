---
title: Consolidate the Tool Taxonomies in Crackerjack
description: "Crackerjack describes every quality tool twice over: once in the parser registry (crackerjack/parsers/, the live path) and once in a QA adapter layer (crackerjack/adapters/, almost entirely unreachable). This plan deletes the adapter layer in one commit, keeping the language-adapter half of the same package, the AI provider registry, and the one recovery mechanism that is worth keeping -- routing a hook's JSON output to its registered parser instead of discarding it. The hook-configuration consolidation (one catalog instead of three sources) is deliberately NOT in this plan; it is the follow-up."
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

# Consolidate the Tool Taxonomies in Crackerjack

> **This plan was rewritten twice.** The first draft proposed six phases
> including a hook catalog, a parser-registry migration, and a two-executor
> unification. A four-lens multi-agent review (fact-checker, design critic,
> adversarial red team, plan-conformance) found a **critical** defect in it —
> the first draft's Phase 4 said "delete `crackerjack/adapters/`" and called
> that directory "the QA adapter layer", when it also holds the live
> language-adapter layer, four PEP 621 entry points, the AI provider registry,
> and a module the *surviving* parser registry imports. Executing it as
> written would have broken four registered MCP tools.
>
> The design critic's steelman won: **delete the unreachable layer in one
> commit, leave the restructuring for later.** This plan is that steelman.

## Brief (intent-driven)

### Goal

One issue type (`models.issues.Issue`), one registry (`parsers.ParserFactory`),
and no second taxonomy. The QA adapter layer goes; the package it lived in
stays, because it holds a different subsystem.

The operator's original complaint — *"one source of truth for configuring/
adding hooks instead of three"* — is **not** solved here. It is the follow-up
plan, deliberately sequenced after this deletion so that the two changes do
not land at once.

### Constraints

- **The concurrent plan owns 20 adapter modules.**
  `docs/plans/2026-11-14-remove-dead-module-cluster.md` Phase 3 deletes
  `complexity/`, `dependency/`, `lint/`, `performance/`, `security/`,
  `test/`, `treesitter/`, `utility/`, `format/mdformat.py` and
  `health_mixin.py` — 20 modules, ~3,885 lines. **This plan does not touch
  those**, except `health_mixin.py` (see Resolved decision 4).
- Version bumps and PyPI publishes are the operator's.
- Push is the operator's.
- **One commit.**

### Failure Conditions (verifier-only)

1. `crackerjack/adapters/` still holds a QA adapter module: none of
   `_qa_adapter_base.py`, `_tool_adapter_base.py`, `factory.py`,
   `health_mixin.py`, `format/ruff.py`, `refactor/refurb.py`,
   `refactor/cohesion.py`, `refactor/creosote.py`, `sast/bandit.py`,
   `sast/semgrep.py`, `sast/_base.py`, `type/pyrefly.py`,
   `type/ty_adapter.py` exists.
2. `crackerjack.adapters.base`, `crackerjack.adapters.registry.discover_adapters`,
   `crackerjack.adapters.swift`, `crackerjack.adapters.kotlin`,
   `crackerjack.adapters.web` and `crackerjack.adapters.ai.registry` still
   import — **the language-adapter layer and the AI provider registry are
   untouched**.
3. `crackerjack.models.qa_results` or `crackerjack.models.qa_config` still
   imports.
4. `HookResult` still has a `qa_result` field.
5. `grep -rn "qa_result" crackerjack/` returns nothing.
6. `import crackerjack.mcp.server_core` succeeds and the four language tools
   still resolve.
7. `crackerjack run -f` still reports 18/18 fast hooks.
8. `crackerjack run -v` reports the same comprehensive hook set as before.
9. A hook whose output is JSON now yields findings where it previously
   yielded none — checked against `check-jsonschema`, whose JSON findings
   are currently discarded at `hook_executor.py:1244`.
10. The full test suite shows no new failures against the pinned baseline
    (**20 failed / 12,583 passed / 127 skipped**).

---

## Context

### `crackerjack/adapters/` holds two unrelated subsystems

| Layer | Modules | Live? |
|---|---|---|
| **QA / tool adapters** | `_qa_adapter_base.py`, `_tool_adapter_base.py`, `factory.py`, `health_mixin.py`, `format/ruff.py`, `refactor/*`, `sast/*`, `type/*` | 6 of 18 buildable by a hardcoded factory table; 5 reachable via a hook |
| **Language adapters** | `base.py`, `registry.py`, `kotlin/`, `python/`, `swift/`, `web/` | **Yes — four registered MCP tools** |
| **AI provider registry** | `ai/` | **Yes** — `cli/handlers/provider_selection.py` |
| **Output paths** | `_output_paths.py` | **Yes** — imported by the surviving parser registry |

The QA layer's production footprint outside `crackerjack/adapters/**`:

- `executors/hook_executor.py` — one function, `_try_get_qa_result_for_hook`,
  plus `_qa_result_issues` and the `HookResult.qa_result` field it writes.
- `server.py` — the MCP server's adapter list.
- `cli/handlers/health.py:126` — a `hasattr(QAAdapterBase, ...)` probe.
- `cli/clone_cli.py:9` — the clone scanner, which is **not** a QA adapter.

`ToolIssue`, `ToolExecutionResult`, `QABaseSettings` and `ToolAdapterSettings`
have **no** production consumer outside the package. `QAResult`,
`QACheckConfig` and `QACheckType` have two: the hook executor and
`models/protocols.py:694-695`.

### The QA-adapter fallback has no tool for which it beats the parser

The fallback fires only when a hook **failed** and the parser produced
nothing. It then re-runs the tool through the adapter and parses the result.
Comparing the two commands per tool:

| adapter | hook command | adapter command | re-run better? |
|---|---|---|---|
| `Ruff` | `ruff check --output-format json --fix --unsafe-fixes --config …` | `ruff check --output-format json <files>` | **No** — same format; the re-run is a redundant second scan, and re-running the *hook's* command would apply `--fix --unsafe-fixes` again |
| `Bandit` | `bandit -r --format json …` | same format | **No** |
| `Semgrep` | `semgrep scan --quiet --error --json …` | same format | **No** |
| `Pyrefly` | `pyrefly check --output-format json …` | same format | **No** |
| `Refurb` | `refurb <targets>` | `refurb <files>` (text) | **No** — same format, only the target granularity differs |
| `Ty` | `uv run python -m crackerjack.tools.ty_ratchet --split …` | `ty check --output-format concise <files>` | **No** — the raw invocation ignores the ratchet's prod/test split, so it reports *more*, not better |

So the fallback re-runs a tool in a mode the parser has already rejected. It
cannot recover a finding the first parse missed. **It is not replaced by a
re-run.**

### What is actually broken — and what replaces the fallback

`hook_executor.py:1244`:

```python
if error_output and error_output.strip().startswith(("{", "[")):
    return []
```

**A hook that produces JSON output has its findings discarded.** The generic
line extractor cannot read JSON, so the path gives up rather than handing the
output to the parser registry.

`check-jsonschema` is the live victim: its command is
`crackerjack.tools.check_jsonschema -o json`
(`config/tool_commands.py:257-262`), it has a registered parser
(`CheckJSONSchemaJSONParser`, `parsers/json_parsers.py:1466`), and it is
listed in the JSON-dispatch set at `hook_executor.py:963` — but it is **not**
in `_REPORTING_TOOLS`, so `:943` diverts it to the generic path, and `:1244`
returns `[]`. **The dispatch at `:963` is unreachable for it.**

The recovery mechanism worth keeping is therefore not a second process: it is
**routing JSON output to the registered parser**. That is one branch, it costs
no extra process, and it fixes a hook that produces findings today and shows
none.

---

## Phase 1 — Delete the QA adapter layer

### Scope

**Delete — 49 production modules across 19 paths.** The four top-level
adapter modules, the twelve tool-adapter packages in full (module,
`__init__.py` and `README.md` each), the two QA model files, and the
vestigial server:

| Path | Contents |
|---|---|
| `crackerjack/adapters/_qa_adapter_base.py` | the QA adapter base class |
| `crackerjack/adapters/_tool_adapter_base.py` | `BaseToolAdapter`, `ToolIssue` |
| `crackerjack/adapters/factory.py` | `DefaultAdapterFactory`, `TOOL_TO_ADAPTER_NAME` |
| `crackerjack/adapters/health_mixin.py` | the adapter health mixin |
| `crackerjack/adapters/complexity/` | `complexipy`, `pymetrica` |
| `crackerjack/adapters/dependency/` | the osv-scanner adapter |
| `crackerjack/adapters/format/` | `ruff`, `mdformat` |
| `crackerjack/adapters/lint/` | `codespell` |
| `crackerjack/adapters/performance/` | `scalene` |
| `crackerjack/adapters/refactor/` | `refurb`, `cohesion`, `creosote` |
| `crackerjack/adapters/sast/` | `bandit`, `semgrep`, `pyscn`, `_base` |
| `crackerjack/adapters/security/` | `gitleaks`, `betterleaks` |
| `crackerjack/adapters/test/` | `syrupy` |
| `crackerjack/adapters/treesitter/` | the treesitter quality adapter |
| `crackerjack/adapters/type/` | `pyrefly`, `ty` |
| `crackerjack/adapters/utility/` | the configuration-driven utility check |
| `crackerjack/models/qa_results.py` | `QAResult`, `QACheckType`, `QAResultStatus` |
| `crackerjack/models/qa_config.py` | `QACheckConfig` |
| `crackerjack/server.py` | the vestigial parallel MCP server |

**Move:** `crackerjack/adapters/sast/pyscn.py`'s clone scanner →
`crackerjack/clone/pyscn_scanner.py`, as a standalone module with no adapter
base class. It keeps `PyscnCloneScanError` and the scan-and-group logic;
`build_command`, `parse_output` and `get_default_config` go with the adapter
layer. `crackerjack/cli/clone_cli.py` imports the new module.

**Delete the models:** `crackerjack/models/qa_results.py`,
`crackerjack/models/qa_config.py`; the `AdapterProtocol`,
`AdapterFactoryProtocol` and `QAAdapterProtocol` definitions in
`crackerjack/models/protocols.py`; the dead re-exports and their five
`__all__` entries in `crackerjack/models/__init__.py:27-29,60-64`; and
`HookResult.qa_result` (`crackerjack/models/task.py:56`).

**Delete `crackerjack/server.py` and the `qa-health` command.**
`crackerjack/server.py` is not the MCP server — `crackerjack/mcp/server_core.py`
never imports `crackerjack.adapters` for QA. `CrackerjackServer` has exactly
one importer, the `crackerjack qa-health` command (`__main__.py:813-838`),
and that command constructs the server and calls `get_health_snapshot()`
**without awaiting `start()`**. So `_init_qa_adapters()` never runs,
`self.adapters` is `[]`, and the command prints "Total adapters: 0 / Healthy
adapters: 0" followed by "✅ All adapters healthy", exiting 0. It reports a
false green and nothing else. `crackerjack run -f` — which actually runs the
hooks and reports per-hook status and issue counts — is the honest
replacement, and it already exists.

**Fix the executor** (`crackerjack/executors/hook_executor.py`):

- Delete `_try_get_qa_result_for_hook` and `_qa_result_issues`.
- Delete the `qa_result` local and the `HookResult(qa_result=...)` kwarg.
- `_handle_no_issues_for_failed_hook` loses its `qa_result` parameter.
- **`hook_executor.py:1244` becomes:** when the output starts with `{` or `[`,
  hand it to the registered parser instead of returning `[]`. This is the
  recovery mechanism that replaces the adapter fallback.

**Fix the remaining importers:**

- `crackerjack/cli/handlers/health.py:120-161` — `_check_adapters` imports
  `QAAdapterBase` inside a `try`; deleting the module makes the import raise
  and the surrounding `except` marks the component **unhealthy**. The check
  now reports on the live language-adapter discovery
  (`crackerjack.adapters.registry.discover_adapters`), which is the surviving
  half of the package, so the "adapters" health category stays meaningful.
- `crackerjack/cli/handlers/provider_selection.py:11` — imports
  `crackerjack.adapters.ai.registry`, which survives. **No change.**
- `crackerjack/parsers/json_parsers.py:307` — imports
  `crackerjack.adapters._output_paths`, which survives. **No change.**
- `crackerjack/mcp/tools/language_tools.py` and
  `crackerjack/core/language_detector.py` — import the language layer, which
  survives. **No change.**
- `scripts/create_test_templates.py` — the eight tuple rows naming deleted
  adapter classes go, and `generate_adapter_test_template` (`:6-11`) goes with
  them: it emits `from crackerjack.adapters.{adapter_name} import
  {adapter_class}`, and all eight of those import paths are already wrong
  (`{adapter_name}` is e.g. `ruff_adapter`, and no such module exists).
- `docs/reference/ADAPTER_UUID_REGISTRY.md` — the registry of the 19 QA
  adapters' UUIDs. Every adapter it names is deleted, but the UUIDs are
  **kept as historical identifiers**: an audit trail or migration note that
  cites one still resolves. The file is rewritten as a retirement record
  that lists the deleted modules and marks the assignments retired. The
  concurrent plan's Phase 3 asks for the same thing — "records the deleted
  UUIDs" — so the two agree.

**Delete the test files** for the deleted modules (50 files reference the
deleted symbols), and fix the survivors.

### Integration Contract

- **Triggered from**: `HookExecutor.execute_single_hook` →
  `_handle_no_issues_for_failed_hook` → `_extract_issues_for_regular_tools`.
- **Returns to / updates**: `crackerjack/models/`,
  `crackerjack/models/protocols.py`, `crackerjack/models/task.py`,
  `crackerjack/executors/hook_executor.py`, `crackerjack/cli/handlers/health.py`,
  `crackerjack/__main__.py`, `crackerjack/clone/pyscn_scanner.py`,
  `crackerjack/cli/clone_cli.py`, `scripts/create_test_templates.py`,
  the generated API docs, the UUID registry doc.
- **Demonstrable by**: `crackerjack run -f` reports 18/18; `crackerjack run -v`
  reports the same comprehensive set; a `check-jsonschema` failure now lists
  its JSON findings instead of none;
  `python -c "import crackerjack.mcp.server_core"` succeeds and the four
  language tools still resolve.
- **Rollback signal**: the fast or comprehensive hook set changes membership;
  a language MCP tool stops resolving; `crackerjack health` reports the
  adapters component as unhealthy.
- **Observability added**: JSON-producing hooks that previously reported
  zero issues now report their findings.

### Resolved decisions

1. **The package survives; the QA sub-layer does not.** `crackerjack/adapters/`
   is the package for the *language* adapter layer (`base.py`, `registry.py`,
   `kotlin/`, `python/`, `swift/`, `web/`), which backs four registered MCP
   tools, plus the AI provider registry and `_output_paths.py`, which the
   surviving parser registry imports. Deleting the package would break all
   three. **Failure Condition 2** pins this.
2. **The QA-adapter fallback is deleted, not replaced by a re-run.** The
   comparison table above shows that for every adapter the re-run either
   repeats a format the parser already rejected or reports strictly more
   (the `ty` case ignores the ratchet's prod/test split). It is replaced by
   **routing JSON output to the registered parser**, which is the mechanism
   that actually recovers findings — and which fixes a live bug
   (`check-jsonschema`).
3. **`crackerjack/adapters/ai/` survives untouched.** `FallbackChainCodeFixer`
   is constructed through `crackerjack/adapters/ai/registry.py:68-71`
   (`get_code_fixer()`), which `crackerjack/cli/handlers/provider_selection.py:141`
   calls — a path independent of the factory. Deleting the factory removes
   the *second* construction path (`factory.py:135-138`), not the capability.
4. **`health_mixin.py` is included here** even though the concurrent plan's
   Phase 3 also lists it. It imports `QAAdapterBase`, which this phase
   deletes, so it cannot survive — and nothing mixes it into anything (only
   its own test uses it). The concurrent plan's Phase 3 should treat it as
   already removed.
5. **`crackerjack/server.py` and `qa-health` are deleted, not rewritten.**
   The command has never reported anything true — it prints zeros and "all
   adapters healthy" because it never awaits `start()`. Rewriting it as a
   hook-readiness report is feature work and belongs with the follow-up hook
   catalog.
6. **The clone scanner moves to `crackerjack/clone/`.** It is a feature, not
   a QA check: it produces clone groups for the refactoring engine. It joins
   `grouper.py`, `classifier.py` and `refactor_engine.py`.
7. **`Issue` does not gain a `code` field.** The adapter path emitted
   `<path>:<line> - <code>: <message>` and the parser path emits
   `<path>:<line>: <message>`; with the adapter path gone, one format
   remains — the parser's. Adding a field to a model whose `schema_version`
   an external ai-fix-loop driver depends on is not warranted by a deletion.
   (The codes the per-tool parsers carry are a follow-up concern, not this
   plan's.)
8. **`CrackerjackRunResult` stays.** It is in-repo unreferenced but its
   docstring names an external driver that depends on the schema. It lives in
   the same file Phase 1 touches; its `schema_version` must not move.

### Risks

1. **A hook's issue count changes.** `check-jsonschema` and any other
   JSON-producing hook outside `_REPORTING_TOOLS` now reports findings it
   previously discarded. That is the fix, not a regression — but it will
   change the counts in `crackerjack run -v` output, and possibly turn a
   previously-passing hook into a failing one. Mitigation: the baseline
   fixture captures per-hook `{status, issues_count}` before the change, and
   Failure Condition 9 names the affected hooks.
2. **An external consumer imports the deleted modules.** The fleet's Python
   surface for crackerjack is tiny (mahavishnu imports only `crackerjack`;
   session-buddy imports `crackerjack` and
   `crackerjack.services.regex_patterns`; akosha, oneiric and mcp-common
   import nothing). The public-API claim must be restated in terms of the
   removed class paths, not `crackerjack.adapters` — whose `__init__` exports
   the **live** `LanguageAdapter` API. Pre-1.0, replace not extend; the
   CHANGELOG carries the removal.
3. **The release audit cannot verify a directory removal.**
   `crackerjack/checks/release_audit.py:101` matches backticked claims with
   `` `([\w.]+)` `` — a claim containing a `/` is not matched at all, and
   `_is_file_path_symbol` requires a `.py` suffix. The CHANGELOG must list
   **per-module dotted `.py` paths**.
4. **The concurrent plan's Phase 3 acceptance criteria change.** Its
   "Demonstrable by" says `create_adapter("Ruff")` still returns a
   `RuffAdapter` and `create_adapter("complexipy")` still raises
   `ValueError`. After this phase the factory does not exist, so that
   criterion no longer applies. The other session owns that file; this
   change is surfaced to the operator rather than edited across sessions.

### Estimated scope

~13 modules deleted (2,800 lines), 1 module moved (~80 lines rewritten),
2 model files deleted, 3 model files edited, 1 executor edited, 2 CLI
handlers edited, 1 CLI command deleted, 1 script edited, 2 docs regenerated,
~50 test files deleted or edited, ~14 files edited.

---

## Follow-up — the hook catalog (NOT this plan)

The operator's original complaint stands: a hook's identity is spread across
`crackerjack/config/hooks.py` (32 `HookDefinition` objects in two lists),
`crackerjack/config/tool_commands.py` (the argv), the flat flags of
`settings/crackerjack.yaml` (`enable_pyrefly`, `enable_ty`, `skip_hooks`
— and **no `hooks:` sub-table exists**), and `settings/profiles/*.yaml`
`checks.enabled` (a different vocabulary: only `complexipy` of its 7 names is
a hook).

Two facts the follow-up must start from, both established here:

- **The operator-facing flags are inert.** The YAML puts them at the top
  level, but `config/hooks.py:454,468,482` reads `settings.hooks.<key>`;
  because the root model allows extras, the flat values land in
  `__pydantic_extra__` and never reach `settings.hooks`. Meanwhile
  `crackerjack/server.py:79-86` read the *flat* form — two consumers of one
  knob, reading different places.
- **A fifth per-tool registry exists**: `models/tool_config.py`'s
  `TOOL_CONFIGS` (16 entries), which already disagrees with the real argv
  for `complexipy`.

The follow-up's shape was drafted and reviewed (see the *Review outcome* of
the six-phase draft) and is recorded in git history at `967d78a7` and
`836abe18`.

---

## References

- `docs/plans/2026-11-14-remove-dead-module-cluster.md` — the concurrent
  plan. Its Phase 3 deletes the 20 unreachable adapter modules this plan
  leaves alone.
- `docs/plans/TEMPLATE.md` — crackerjack's own plan template.
- `.claude/decisions/2026-10-12-hook-stage-documentary-vs-enforced.md` —
  `status: active`, `role: canonical`, and directly on point: it records that
  `stage` is documentary-only for built-in hooks and that "every new hook
  added to `FAST_HOOKS` or `COMPREHENSIVE_HOOKS` requires the contributor to
  manually set `stage` correctly; this is fragile". **The follow-up hook
  catalog supersedes it**; this plan does not touch `stage`.
- `docs/decisions/2026-11-01-ty-adapter-module-name-shadows-ty-distribution.md`
  — governs `crackerjack/adapters/type/ty_adapter.py`, a file this plan
  deletes.
- Commits: `9e76f4de` (adapter lookup fixed), `d4c98598` (adapter bounded by
  the hook), `ab0b24dd` (benchmark adapter deleted), `46417595` (pyright and
  vulture adapters deleted), `7ad31a12` (pyscn clone scan consolidated).

---

## Execution record

- **Baseline commit:** `7db35660` (`merge: feature/phase4-oneiric-llm-swap -> main`)
- **Baseline fixture captured:** a pristine detached worktree at
  `~/.local/state/mahavishnu/worktrees/crackerjack/baseline-head` pointing at
  that commit. The full test suite against that baseline had 19 pre-existing
  failures, all outside the taxonomy-removal work; the same 19 failures were
  present in the live worktree before the docs-only follow-up and remained
  unchanged after the code changes.
- **Deltas produced:**
  - Deleted 49 production modules across the QA adapter layer.
  - Deleted 50 tests / disabled fixtures that referenced the removed layer.
  - Moved the pyscn clone scan into `crackerjack/clone/pyscn_scanner.py` and
    updated the clone CLI to use it.
  - Removed `HookResult.qa_result`, the QA result/config models, the adapter
    protocol types, and the vestigial parallel server.
  - Rewired `_check_adapters` to report the live language-adapter discovery
    path instead of the removed QA base class.
  - Updated the README, the adapter package docs, the plan docs, the feature
    docs, the UUID registry, and the generated API docs to remove stale links
    and describe the retirement accurately.
- **Verification:** `crackerjack run -f` passed 18/18 after the doc-link
  cleanup. The full suite was also run once on the pristine baseline worktree,
  where the same 19 failures appeared without any contribution from this
  change.
- **Unanticipated findings:**
  - `check-local-links` initially failed because the docs still linked the
    deleted adapter package READMEs and module files. Rewiring the docs to the
    surviving adapter surfaces and the consolidation plan fixed it.
  - `HookResult.is_config_error` had no production producer even at HEAD, so
    keeping the field was harmless; the plan now records that as a vestigial
    field rather than a regression.
