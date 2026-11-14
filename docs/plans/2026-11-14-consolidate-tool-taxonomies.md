---
title: Consolidate the Tool Taxonomies in Crackerjack
description: "Crackerjack describes every quality tool three or four times over, in places that agree only by convention. This plan collapses them: one hook catalog that declares each hook once and names its command, its parser, and its fallback parser; one parser registry reachable from both executors; and no adapter layer — the adapter layer's entire footprint outside `crackerjack/adapters/**` is one function in the hook executor plus a write-only field, and the one capability worth keeping (re-running a failing tool with a structured-output flag to recover findings) belongs to the parser taxonomy. It also fixes the hook-config sprawl the operator called out: adding a hook today means touching three to four files and hoping the names line up, and nothing checks that they do."
audience: crackerjack maintainer
created: 2026-11-14
status: draft
role: implementation
topic: architecture
date: 2026-11-14
last_reviewed: 2026-11-14
superseded_by: null
blocks_on: []
---

# Consolidate the Tool Taxonomies in Crackerjack

## Brief (intent-driven)

### Goal

Crackerjack currently describes every quality tool three or four times over, in
places that only agree by convention. This plan collapses them so that each tool
is declared **once**, and the declarations are validated against each other.

The three collapses, in the order they are addressed here:

1. **One hook catalog.** Today a hook's identity is spread across
   `crackerjack/config/hooks.py` (the `HookDefinition` lists),
   `crackerjack/config/tool_commands.py` (the argv), the `hooks:` block of
   `settings/crackerjack.yaml` (enable flags and timeouts), and the
   `checks.enabled` list of `settings/profiles/*.yaml` (a parallel vocabulary of
   tool names that includes names no hook has, such as `mypy` and `safety`).
   A fifth source — the plugin system — is being deleted by a separate plan.
   Adding a hook today means touching three to four files and hoping the names
   line up; nothing checks that they do.

2. **One issue type and one parser registry.** The parser registry
   (`crackerjack/parsers/`) and the adapter layer (`crackerjack/adapters/`)
   both turn tool output into structured issues, using two different types
   (`models.issues.Issue` and `adapters/_tool_adapter_base.ToolIssue`) and two
   different registries. Only the parsers are on the live hook path.

3. **No adapter layer.** The adapter layer's entire footprint outside
   `crackerjack/adapters/**` is one function in the hook executor plus a
   write-only field. What it uniquely offers — re-running a failing tool with a
   structured-output flag to recover findings — is worth keeping, but it is a
   *parser* capability, not a reason for a second taxonomy.

### Constraints

- **Do not touch what a concurrent session owns.** The plan
  `docs/plans/2026-11-14-remove-dead-module-cluster.md` is being executed
  elsewhere. Its Phase 2 deletes `crackerjack/plugins/` and
  `crackerjack/websocket/`; its Phase 3 deletes 23 unreachable adapter modules
  under `crackerjack/adapters/` (`benchmark/`, `complexity/`, `dependency/`,
  `format/mdformat.py`, `health_mixin.py`, `lint/`, `performance/`, `security/`,
  `test/`, `treesitter/`, `utility/`). This plan assumes both have landed and
  must not duplicate their deletions.
- **Version bumps and PyPI publishes are the operator's.** Never edit the
  `pyproject.toml` version string.
- **Push is the operator's.**
- **One commit per phase**, each independently revertible, each ending with a
  green gate.
- Pre-1.0: **replace, do not extend.** No back-compat shims for a removed
  import path.

### Failure Conditions (verifier-only)

1. A hook that exists in the catalog cannot be resolved to a command.
2. A hook that exists in the catalog has no registered parser and no
   documented reason why not.
3. Two catalog entries resolve to the same tool with different parsers, and the
   discrepancy is not deliberate.
4. `settings/crackerjack.yaml` or a profile YAML names a hook that is not in
   the catalog, and the mismatch is not reported at load time.
5. `HookResult.qa_result` is still written after this plan's Phase 4.
6. `crackerjack/adapters/` still exists after this plan's Phase 4.
7. The MCP server's `qa_adapters` health block still reports a `healthy` count
   that is computed from a `getattr(a, "healthy", True)` default.
8. The full test suite gains a failure that is not present on the base commit.

---

## Context

### The three taxonomies, measured

| Taxonomy | Where | Size | Reachable from production? |
|---|---|---|---|
| **Parsers** | `crackerjack/parsers/` | 13 JSON + 28 regex parsers | Yes — the live issue path |
| **Adapters** | `crackerjack/adapters/` | 20 `BaseToolAdapter` subclasses | 6 of 20 (the factory's fixed table) |
| **Plugin hooks** | `crackerjack/plugins/` | `CustomHookDefinition` | No — no production caller (being deleted) |

Verified facts about the adapter layer:

- **`ToolIssue`, `ToolExecutionResult`, `QABaseSettings`, and
  `ToolAdapterSettings` have no production consumer outside
  `crackerjack/adapters/**` at all.**
- **`QAResult`, `QACheckConfig`, and `QACheckType` have exactly one external
  consumer**: `HookExecutor._try_get_qa_result_for_hook`
  (`crackerjack/executors/hook_executor.py:2297-2395`) and its two helpers
  (`_qa_result_issues:848`, `_handle_no_issues_for_failed_hook:875`). The
  executor does not import any of them — the value flows through as `t.Any`.
- **`HookResult.qa_result` (`crackerjack/models/task.py:56`) is written once and
  never read.** `grep` for `.qa_result` across the whole repository, production
  and tests, returns zero hits.
- **`Issue` (`crackerjack/models/issues.py:39`) is the live issue type.** The
  only three production sites that read its attributes are
  `hook_executor.py:1037/1039` and `async_hook_executor.py:856/894/896`.
- **`models/issues.py:76` `CrackerjackRunResult` is never referenced.**
- **`crackerjack/models/__init__.py:27-29` re-exports `QAResult`,
  `QAResultStatus`, `QACheckType`, `QACheckConfig`, and `QAAdapterProtocol`;
  nothing imports any of them via `from crackerjack.models import ...`.**
- **`crackerjack/core/phase_coordinator.py:1149-1151` constructs a
  `ParserFactory()` and discards it** — a no-op with no effect.

### The three hook-config sources, measured

| # | Source | Holds | Linked by |
|---|---|---|---|
| 1 | `crackerjack/config/hooks.py` | `FAST_HOOKS`, `COMPREHENSIVE_HOOKS` — 22 `HookDefinition` objects | — |
| 2 | `crackerjack/config/tool_commands.py` | the argv for each hook name | hook name string |
| 3 | `settings/crackerjack.yaml` `hooks:` | `enable_pyrefly`, `enable_ty`, `enable_ty_ignore_syntax`, `experimental_hooks`, `skip_hooks`; `adapter_timeouts.<name>_timeout` | hook name string |
| 4 | `settings/profiles/*.yaml` `checks.enabled` | `ruff`, `pytest`, `coverage`, `bandit`, `safety`, `mypy`, `complexipy` | tool name string — **a different vocabulary** |
| 5 | `crackerjack/plugins/` | `CustomHookDefinition` | hook name string — **being deleted by the concurrent plan** |

The linkage is by bare string in every case. Nothing verifies that a name in
source 3 or 4 exists in source 1, that a hook in source 1 has a command in
source 2, or that a hook in source 1 has a parser.

Two concrete consequences of that:

- **`stage` is documentary metadata for built-in hooks and a behavioural
  switch for plugin hooks.** `HookDefinition`'s own docstring says so:
  *"The bifurcation exists because the two registration paths share this
  dataclass but derive execution semantics differently."* For a built-in hook,
  which list it lives in decides whether it runs; the `stage` field is a
  convention nothing enforces, so drift between the two is a silent
  inconsistency.
- **`settings/profiles/comprehensive.yaml` lists `mypy` and `safety`.** Neither
  is a hook — the type checker is `ty`/`pyrefly`, and the dependency scanner is
  `osv-scanner`. The profile vocabulary and the hook vocabulary have already
  diverged.

### The tool-name coverage matrix

Registered parsers cover every live hook **except `pyrefly`**:

```
hooks WITH a registered parser : bandit, betterleaks, check-jsonschema,
    cohesion, creosote, linkcheckmd, lychee, pymetrica, pyscn, refurb, ruff,
    ruff-check, ruff-format, semgrep, ty
hooks WITHOUT a registered parser: pyrefly
```

`pyrefly` is the inversion: it has an adapter in the factory's table but no
parser, so the **async** executor falls back to generic line extraction while
the **sync** executor gets structured issues from the adapter. This is the only
tool where the adapter path is the better of the two — and it was the better
one only because the adapter path was broken until 2026-11-14.

### The QA-adapter fallback, and why it is worth keeping

`_try_get_qa_result_for_hook` runs when a hook **failed** and the text
parsers produced **nothing**. It re-runs the tool — the same tool the hook just
ran — with the adapter's own settings, and uses the structured issues it finds
in place of the generic `"hook exited with code N but reported no parseable
issues"` message.

That is a real capability and a real bug fix (`9e76f4de`, bounded in
`d4c98598`). But it is implemented as an entire second taxonomy — a second
issue type, a second command builder, a second settings hierarchy, a second
result type — to deliver what a parser could deliver: *run the tool with
`--outputjson`, hand the output to the registered JSON parser.*

The adapter's re-run also carries a cost the parser path does not: it runs the
tool over the whole package again, with the hook's timeout as its budget
(added in `d4c98598` after the unbounded version made the test suite hang for
minutes).

### The MCP server's adapters are decorative too

`crackerjack/server.py` initializes six QA adapters
(`Ruff`, `Bandit`, `Semgrep`, `Pyrefly`, `Ty`, `Refurb`) and keeps them in
`self.adapters`. What it then does with them:

- `stop()` (`:134`) calls `adapter.cleanup()` **if the adapter has one**. No
  adapter in the tree defines `cleanup` — the loop never executes.
- The health snapshot (`:156-159`) reports
  `sum(1 for a in self.adapters if getattr(a, "healthy", True))` as the
  healthy count. **No adapter defines `healthy`**, so the default `True`
  applies to every adapter and the healthy count always equals the total. The
  `crackerjack qa-health` command prints "Healthy adapters: N" where N is
  always "Total adapters: N".

The observable MCP contribution of the adapter layer is therefore: *the count of
adapters that initialized without raising*, reported twice.

### What this plan does not touch

- `crackerjack/services/patterns/` — a third pattern registry
  (`SAFE_PATTERNS`), used by `individual_hook_executor.py`, which the
  concurrent plan deletes. The `pyright` output patterns there are read by
  that module; they are left alone until it goes.
- `settings/profiles/*.yaml`'s *quality gate* and *tooling* sections — only the
  `checks.enabled` name list is in scope.
- The `crackerjack.adapters.ai.unified` `FallbackChainCodeFixer`, which the
  factory reaches by a special case at `factory.py:135-138` and which is not a
  QA tool adapter.

---

## Phase 1 — One hook catalog

### Scope

Introduce a single `HookSpec` record per hook in one place, and make every
other source a *reference* to it rather than a parallel declaration.

**New: `crackerjack/config/hook_catalog.py`.** One `HOOK_CATALOG: tuple[HookSpec,
...]`, one entry per hook. `HookSpec` carries what `HookDefinition` carries
today, plus the two links that are currently implicit:

```python
@dataclass(frozen=True)
class HookSpec:
    name: str
    stage: HookStage
    timeout: int
    parser: str | None            # ParserFactory key
    fallback_parser: str | None   # parser for the structured-output re-run
    command_factory: Callable[[], list[str]] | None
    security_level: SecurityLevel
    accepts_file_paths: bool
    auto_run: bool
    enabled_by_default: bool
    opt_in_setting: str | None     # settings flag name, if opt-in
    description: str | None
```

The catalog is the **only** place a hook is declared. `HookConfigLoader`
resolves `stage` into the fast and comprehensive strategies from the catalog
rather than from two separate lists, which removes the "which list decides
whether it runs" question and makes `stage` load-bearing for built-ins the way
it already is for plugins.

**`crackerjack/config/tool_commands.py`** keeps the argv builders — they carry
version-probing logic that does not belong in a data file — but the catalog
references them by name instead of the executor reaching into a dict by hook
name. A hook with no command builder and no explicit command is a catalog
error.

**`settings/crackerjack.yaml`** keeps its `hooks:` block, but every key in it
must name a hook in the catalog. `enable_pyrefly` becomes
`pyrefly: {enabled: false}` — keyed by hook name, with the flag names derived
from the catalog rather than hand-written.

**`settings/profiles/*.yaml`** `checks.enabled` becomes a list of **hook names**,
validated against the catalog at load time. `mypy` and `safety` are not hooks;
they are replaced with the hooks that actually do that work (`ty`,
`osv-scanner`), or dropped if the profile does not gate on them.

**`HookDefinition`** survives as the resolved, per-run value — a `HookSpec`
plus the settings overrides applied — so the executors do not change shape.

### Integration Contract

- **Triggered from**: `HookConfigLoader.load_strategy()`, called by
  `HookManagerImpl` (`crackerjack/managers/hook_manager.py:390,457,546`) and
  `AsyncHookManager` (`crackerjack/managers/async_hook_manager.py:73`), and by
  `crackerjack/core/phase_coordinator.py:544`.
- **Returns to / updates**: `settings/crackerjack.yaml` `hooks:`;
  `settings/profiles/{quick,standard,comprehensive}.yaml` `checks.enabled`.
- **Demonstrable by**: `crackerjack run -f` still reports 18/18 fast hooks;
  `crackerjack run -v` still reports the same comprehensive set; a typo in a
  profile's `checks.enabled` is reported at load time rather than ignored.
- **Rollback signal**: the fast or comprehensive hook set changes membership.
- **Observability added**: a startup log line listing the resolved hook set
  with each hook's parser, so "which parser does this hook use?" is answerable
  from the run log.

### Resolved decisions

1. **The catalog is Python, not YAML.** `tool_commands.py` carries version
   probing (`preferred_binary_command_with_min_version`) that a data file
   cannot express, and a YAML catalog would reintroduce the string-keyed
   coupling the phase is meant to remove.
2. **Keep `HookDefinition` as the resolved value.** The executors take
   `HookDefinition`; changing that is a separate, larger change. The catalog
   produces them.
3. **The catalog names parsers, and the parser registry stays where it is.**
   The catalog is the *index*; `ParserFactory` remains the implementation of
   parsing.
4. **`checks.enabled` in the profile YAMLs becomes hook names.** `mypy` and
   `safety` are not hooks; they are replaced with `ty` and `osv-scanner`.
   The profile's quality-gate sections are untouched.
5. **The plugin path is not resurrected.** The concurrent plan deletes it; this
   plan does not add a plugin-shaped escape hatch to the catalog.

### Risks

1. **A hook with no parser.** `pymetrica` and `cohesion` have registered regex
   parsers but the *sync* executor only reaches a parser for the tools in
   `_REPORTING_TOOLS`, so the catalog would record a parser the sync path
   never calls. Mitigation: the catalog records the parser, and Phase 2 makes
   the sync executor consult the catalog instead of its private frozenset —
   which is where that frozenset dies.
2. **Timeout override names.** `adapter_timeouts` uses
   `<hook_name>_timeout` and `<hook_name-with-dashes>_timeout`. The catalog
   keeps both spellings working by deriving them from `HookSpec.name`.
3. **Opt-in hooks.** `pyrefly`, `ty`, and `ty-ignore-syntax` are added to the
   catalog only when their settings flag is on. The catalog holds them
   unconditionally with an `opt_in_setting`; the loader filters.

### Estimated scope

1 new module, 2 rewritten modules, 2 settings files, 4 profile files,
1 consistency test, ~600 lines net.

---

## Phase 2 — One parser path in both executors

### Scope

Make the **sync** executor reach the parser registry the way the **async**
executor already does, and retire the hand-maintained
`HookExecutor._REPORTING_TOOLS` frozenset.

Today:

- `async_hook_executor.py:883-889` dispatches by hook name to
  `ParserFactory().parse_with_validation(...)`.
- `hook_executor.py:953-980` uses a private frozenset of 10 tool names to
  decide whether to use a parser at all, and falls back to generic line
  extraction for everything else — so `cohesion` and `pymetrica` have
  registered parsers that the sync path never calls.

After this phase both executors ask the same question the same way: *does this
hook have a registered parser?* If yes, use it. If no, fall back to the generic
line extractor.

The special cases that are genuinely special stay special, but they move to
named functions rather than a membership test in a frozenset: `_parse_refurb_issues`,
`_parse_gitleaks_issues`, `_parse_creosote_issues`, `_parse_osv_scanner_issues`,
`_parse_lychee_issues`, `_parse_ty_ratchet_issues`, `_parse_tc_refs_issues`.

### Integration Contract

- **Triggered from**: `HookExecutor._extract_issues_from_process_output`.
- **Returns to / updates**: `HookExecutor._REPORTING_TOOLS` is deleted.
- **Demonstrable by**: a `cohesion` hook that fails produces the same issue
  text through the sync executor as through the async one.
- **Rollback signal**: the issue count for any hook changes by more than the
  difference between generic line extraction and the registered parser.
- **Observability added**: none needed.

### Resolved decisions

1. **Do not delete the per-tool parsers.** `_parse_creosote_issues` and
   `_parse_pyscn_issues` carry version-specific knowledge that the generic
   parsers do not. They become named functions reached by name, not members of
   a set.
2. **`pyrefly` gets a parser in this phase or Phase 5.** Until it has one, it
   keeps the generic extractor in the async path. See *Follow-ups*.

### Risks

1. **The generic extractor and a registered parser disagree.** Where a
   registered parser exists but the generic extractor also matched lines, the
   issue count changes. Mitigation: the full suite is the check, and the
   per-hook parsers are preferred deliberately.

### Estimated scope

2 modules, ~200 lines net, 1 test file.

---

## Phase 3 — A parser-based structured-output fallback

### Scope

Replace the adapter-based QA fallback with a parser-based one, keeping the
capability that `9e76f4de` and `d4c98598` established.

New behaviour, in the sync executor, when a hook **failed** and the registered
parser produced **nothing**:

1. Look up the hook's `fallback_parser` in the catalog.
2. If there is one, re-run the hook's command with the structured-output flag
   that parser understands, bounded by the hook's timeout.
3. Feed the output to that parser and use the resulting issues in place of
   `"hook exited with code N but reported no parseable issues"`.

This is what the adapter path does today, expressed in the parser taxonomy.
The adapter's `build_command`, `execute_tool`, `ToolExecutionResult`,
`ToolIssue`, and `ToolAdapterSettings` are not needed for it.

The fallback stays gated exactly as it is now: only on failure, only when the
parser produced nothing, and with the hook's timeout as the budget.

### Integration Contract

- **Triggered from**: `HookExecutor.execute_single_hook` →
  `_handle_no_issues_for_failed_hook`.
- **Returns to / updates**: `_try_get_qa_result_for_hook` and
  `_qa_result_issues` are deleted.
- **Demonstrable by**: a `ruff-check` hook that fails with unparseable output
  still yields the structured ruff findings instead of the generic message.
- **Rollback signal**: the generic `"hook exited with code N but reported no
  parseable issues"` message appears where structured findings appeared
  before.
- **Observability added**: the fallback logs which parser it used at debug
  level, as the adapter path does today.

### Resolved decisions

1. **Keep the "failed and nothing parsed" gate.** The adapter re-runs the
   tool over the whole package; doing that when the parser already produced
   issues is a second full scan for a result that would be discarded.
2. **Keep the hook's timeout as the budget.** The adapter's own default was
   300 s, which outlived the hook that triggered it.

### Risks

1. **A fallback parser that cannot read the tool's output.** The catalog
   records which parser handles which format, so the pairing is explicit
   rather than inferred.
2. **Double-scanning.** The fallback re-runs the tool. It is bounded by the
   hook's timeout and gated on the parser having produced nothing.

### Estimated scope

1 module, ~150 lines net, 4 tests.

---

## Phase 4 — Delete the adapter layer

### Scope

With Phases 1-3 in place, the adapter layer has no remaining consumer. Delete
it.

**`crackerjack/adapters/`** — the QA adapter layer: the base classes
(`_tool_adapter_base.py`, `_qa_adapter_base.py`), the factory, and the six
surviving tool adapters (`format/ruff.py`, `refactor/refurb.py`,
`sast/bandit.py`, `sast/semgrep.py`, `type/pyrefly.py`, `type/ty_adapter.py`).

The `sast/pyscn.py` adapter moves out first — it is **not** a QA adapter; it
is the clone scanner, and the clone CLI now calls it (see *Resolved decisions*).
Its home is `crackerjack/clone/`, next to `grouper.py` and `classifier.py`,
which are the other clone-domain modules.

**`crackerjack/models/qa_results.py`** — `QAResult`, `QAResultStatus`,
`QACheckType`. **`crackerjack/models/qa_config.py`** — `QACheckConfig`,
`QABaseSettings`. **`crackerjack/models/task.py:56`** — `HookResult.qa_result`.

**`crackerjack/models/__init__.py:27-29`** — the dead re-exports.

**`crackerjack/core/phase_coordinator.py:1149-1151`** — the discarded
`ParserFactory()`.

**`crackerjack/server.py`** — the MCP server's adapter initialization. The
`qa_adapters` health block is replaced with something honest: the count of
catalog hooks whose tool binary is actually resolvable, which is what an
operator asking "is my toolchain wired up?" wants to know. The `healthy`
figure that always equalled the total goes away rather than being
reimplemented.

**`crackerjack/models/protocols.py`** — `AdapterFactoryProtocol`,
`AdapterProtocol`, and the `QAAdapterProtocol` re-export.

**`crackerjack/adapters/registry.py`** — `AdapterRegistry` and
`get_adapter_registry`, already test-only, if the concurrent plan has not
already taken them.

**`docs/reference/ADAPTER_UUID_REGISTRY.md`** — updated or removed.

### Integration Contract

- **Triggered from**: the MCP server, the hook executor, the CLI.
- **Returns to / updates**: `crackerjack/server.py`, `crackerjack/models/`,
  `crackerjack/models/protocols.py`, the generated API docs.
- **Demonstrable by**: `import crackerjack.adapters` raises
  `ModuleNotFoundError`; `crackerjack run -f` still reports 18/18; the MCP
  server still starts and still serves its tools; `crackerjack qa-health`
  reports the toolchain's real state.
- **Rollback signal**: any import of `crackerjack.adapters` fails at startup.
- **Observability added**: the `qa_adapters` health block reports resolvable
  tools rather than adapter objects.

### Resolved decisions

1. **The clone scanner moves to `crackerjack/clone/`, not into
   `crackerjack/parsers/`.** It is a feature, not a QA check: it produces
   clone groups for the refactoring engine, not issues for a hook report.
   Its `PyscnCloneScanError` moves with it.
2. **The `QAResult` triple goes.** `Issue` plus `HookResult.issues_found` is
   enough for the hook path, and the MCP server never read `QAResult`.
3. **The `healthy` count is not reimplemented as a constant.** The MCP health
   block reports whether each hook's tool binary resolves.
4. **`PyscnAdapter` is not deleted** even though the factory cannot build it.
   The clone CLI calls it directly, and the concurrent plan's Phase 3 does not
   include `sast/`.

### Risks

1. **An external consumer imports `crackerjack.adapters`.** It is a public
   package path. Pre-1.0, replace not extend; the CHANGELOG states the
   removal.
2. **The `docs/reference/ADAPTER_UUID_REGISTRY.md` UUIDs become wrong.** It
   is updated in the same commit.
3. **`scripts/create_test_templates.py`** names adapter classes in template
   text. Those rows are removed.

### Estimated scope

~20 modules, ~4,000 lines, 1 model file, 1 server file, ~28 test files.

---

## Phase 5 — Follow-ups (not blocking)

1. **A `pyrefly` parser.** `pyrefly` is the only live hook with no registered
   parser, and the only tool where the adapter path was the better of the two
   paths. With the adapter layer gone, `pyrefly` needs a
   `PyreflyJSONParser` in `crackerjack/parsers/` so both executors produce
   the same structured findings. Tracked as a follow-up; it is not a phase
   blocker.
2. **`refactor/cohesion.py` and `refactor/creosote.py`.** Neither is in the
   concurrent plan's Phase 3 scope, and neither is reachable from the factory.
   `cohesion` has a registered regex parser that the sync executor never
   calls (fixed in Phase 2) and `creosote` has both a regex parser and a
   dedicated text parser. Both adapters are dead once the factory is gone;
   decide whether they are deleted here or in the concurrent plan.
3. **The `services/patterns/` registry.** `SAFE_PATTERNS` is a third pattern
   registry. `individual_hook_executor.py` reads it and the concurrent plan
   deletes that module; the `pyright` output patterns and the rest of
   `services/patterns/` then need a decision of their own.
4. **`settings/profiles/`'s quality-gate sections.** Out of scope here; only
   the `checks.enabled` name list was touched.

---

## Risks

1. **The concurrent plan and this plan both touch `crackerjack/adapters/`.**
   Mitigation: this plan's Phase 4 runs *after* the concurrent plan's Phase 3
   lands, and Phase 4's scope is only what Phase 3 left behind. If the
   concurrent plan has not started when this plan's Phase 1 begins, the two
   must not run in the same worktree.
2. **The adapter layer is a public package path.** Removing it is a breaking
   change. Pre-1.0 and operator-owned publishing: the CHANGELOG carries the
   removal and the version bump is the operator's.
3. **`HookResult.qa_result` is write-only today, but a downstream consumer
   may read it.** It is typed `t.Any | None`, so no in-repo consumer can be
   found by the type checker. The CHANGELOG calls this out.
4. **The profile YAML rename (`mypy` → `ty`, `safety` → `osv-scanner`) changes
   what a profile gates on.** The `checks.enabled` list is read by
   `ProfileLoader`, whose consumers must be checked before the rename.

---

## References

- `docs/plans/2026-11-14-remove-dead-module-cluster.md` — the concurrent plan.
  Its Phase 2 deletes the plugin system (the fifth hook-config source) and its
  Phase 3 deletes 23 unreachable adapters. **Its Phase 3 risk #3 refers to
  `_tool_has_qa_adapter` at `hook_executor.py:2334+`, which was deleted on
  2026-11-14 in `9e76f4de`** — that risk note is stale.
- `docs/decisions/` — the repo's decision records.
- `crackerjack/parsers/factory.py` — the parser registry that survives.
- `crackerjack/config/hooks.py` — the hook definitions this plan replaces.
- `crackerjack/config/tool_commands.py` — the command builders that survive.
- `crackerjack/adapters/factory.py` — the three-table factory this plan
  retires.
- Commits: `9e76f4de` (adapter lookup fixed), `d4c98598` (adapter bounded by
  the hook), `ab0b24dd` (benchmark adapter deleted).

---

## Execution record

_(To be filled in as the phases execute.)_
