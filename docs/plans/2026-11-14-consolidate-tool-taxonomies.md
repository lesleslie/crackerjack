---
title: Consolidate the Tool Taxonomies in Crackerjack
description: "Crackerjack describes every quality tool three or four times over, in places that agree only by convention. This plan collapses them: one hook catalog that declares each hook once and names its command, its parser, and its structured-output re-run; one parser registry reachable from both executors; and no QA adapter layer -- the QA adapter layer's entire footprint outside its own package is one function in the hook executor plus a write-only field, and the one capability worth keeping (re-running a failing tool with a structured-output flag to recover findings) belongs to the parser taxonomy. It also fixes the hook-config sprawl the operator called out: adding a hook today means touching three to four files and hoping the names line up, and nothing checks that they do. Revised after a four-lens multi-agent review; the review found that the first draft's Phase 4 would have deleted the live language-adapter layer."
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

> **Revision note (2026-11-14).** The first draft of this plan went through a
> four-lens multi-agent review (fact-checker, design critic, adversarial red
> team, plan-conformance). The review found one **critical** defect and several
> majors. The critical one: the draft's Phase 4 said "delete
> `crackerjack/adapters/`" and called that directory "the QA adapter layer".
> It is not — the same package holds the **live language-adapter layer**,
> four PEP 621 entry points, the AI-provider registry, and a module the
> *surviving* parser registry imports. Executing the draft as written would
> have broken four registered MCP tools. Every correction is listed in
> *Review outcome* at the end.

## Brief (intent-driven)

### Goal

Crackerjack currently describes every quality tool three or four times over,
in places that only agree by convention. This plan collapses them so that each
tool is declared **once**, and the declarations are validated against each
other.

1. **One hook catalog.** A hook's identity is spread across
   `crackerjack/config/hooks.py` (the `HookDefinition` lists),
   `crackerjack/config/tool_commands.py` (the argv), the top-level flags of
   `settings/crackerjack.yaml` (`enable_pyrefly`, `enable_ty`,
   `experimental_hooks`, `skip_hooks` — there is **no `hooks:` sub-table**),
   and `settings/profiles/*.yaml`
   `checks.enabled` (a parallel vocabulary of tool names that includes names
   no hook has). Adding a hook today means touching three to four files and
   hoping the names line up; nothing checks that they do.

1. **One issue type and one parser registry.** The parser registry
   (`crackerjack/parsers/`) and the QA adapter layer
   (`crackerjack/adapters/`) both turn tool output into structured issues,
   using two different types (`models.issues.Issue` and
   `adapters/_tool_adapter_base.ToolIssue`) and two different registries. Only
   the parsers are on the live hook path.

1. **No QA adapter layer.** The QA adapter layer's entire footprint outside
   `crackerjack/adapters/**` is one function in the hook executor plus a
   write-only field. What it uniquely offers — re-running a failing tool with a
   structured-output flag to recover findings — is worth keeping, but it is a
   *parser* capability, not a reason for a second taxonomy.

### Constraints

- **Do not touch what a concurrent session owns.** The plan
  `docs/plans/2026-11-14-remove-dead-module-cluster.md` is being executed
  elsewhere. Its Phase 2 deletes `crackerjack/plugins/` and
  Phase 3 deletes the unreachable QA adapter modules — `complexity/`,
  `dependency/`, `format/mdformat.py`, `health_mixin.py`, `lint/`,
  `performance/`, `security/`, `test/`, `treesitter/`, `utility/` — which is
  **20 modules / ~3,885 lines** after `benchmark/` was already removed by
  `ab0b24dd`. (The concurrent plan's own scope line still says "23 modules,
  4,495 lines"; that count is stale and Phase 3 of *that* plan should correct
  it.) This plan assumes the phase has landed and must not duplicate its
  deletions.
- **Version bumps and PyPI publishes are the operator's.** Never edit the
  `pyproject.toml` version string.
- **Push is the operator's.**
- **One commit per phase**, each independently revertible, each ending with a
  green gate.
- Pre-1.0: **replace, do not extend.** No back-compat shims for a removed
  import path.

### Failure Conditions (verifier-only)

1. A hook that exists in the catalog cannot be resolved to a command.
1. A hook that exists in the catalog has no registered parser and is not on
   the explicit `NO_PARSER` allowlist.
1. Two catalog entries resolve to the same tool with different parsers, and
   the discrepancy is not on the explicit `DELIBERATE_DIVERGENCE` allowlist.
1. A settings key or profile YAML names a hook that is not in the catalog, and
   the mismatch is not reported at load time.
1. `HookResult.qa_result` is still written after this plan's Phase 5.
1. **The QA adapter modules are gone after this plan's Phase 5**:
   `crackerjack/adapters/_tool_adapter_base.py`,
   `crackerjack/adapters/_qa_adapter_base.py`,
   `crackerjack/adapters/factory.py`,
   `crackerjack/adapters/format/ruff.py`,
   `crackerjack/adapters/refactor/refurb.py`,
   `crackerjack/adapters/refactor/cohesion.py`,
   `crackerjack/adapters/refactor/creosote.py`,
   `crackerjack/adapters/sast/bandit.py`,
   `crackerjack/adapters/sast/semgrep.py`,
   `crackerjack/adapters/type/pyrefly.py`,
   `crackerjack/adapters/type/ty_adapter.py`.
   **`crackerjack/adapters/` itself survives.** It is the package for the
   live *language* adapter layer (`base.py`, `registry.py`, `swift/`,
   `kotlin/`, `web/`, `python/`, `_output_paths.py`), which backs four
   registered MCP tools (`crackerjack_swift_list_hooks`,
   `crackerjack_swift_bump_version`, `crackerjack_kotlin_list_hooks`,
   `crackerjack_kotlin_bump_version`) and
   `crackerjack/core/language_detector.py`. Deleting the package is out of
   scope and belongs to its own plan.
1. The MCP `qa_adapters` block still reports a `healthy` count computed from a
   `getattr(a, "healthy", True)` default.
1. The full test suite shows no new failures against the pinned baseline
   (**20 failed / 12,606 passed / 127 skipped at `fe1bb2af`** — the same
   baseline the concurrent plan pins).
1. For every hook in the catalog, the issue **count** reported by
   `crackerjack run -f` and `crackerjack run -v` is unchanged from the
   baseline captured before Phase 4, except where the execution record names
   the hook and the reason. The baseline is a checked-in fixture — one file
   per hook holding `{status, issues_count}` — not a number in a commit
   message.
1. `pyrefly` produces the same structured findings after Phase 5 as it did
   after Phase 4.
1. `import crackerjack.adapters` still succeeds, and
   `crackerjack.adapters.base`,
   `crackerjack.adapters.registry.discover_adapters`,
   `crackerjack.adapters.swift`, `crackerjack.adapters.kotlin` and
   `crackerjack.adapters.web` still import — the language-adapter layer is
   untouched by this plan.
1. `crackerjack health` still reports the adapters component as present, not
   unhealthy.

______________________________________________________________________

## Context

### The taxonomy map — `crackerjack/adapters/` holds **two** layers

This is the fact the first draft got wrong, and it is load-bearing for
everything below.

| Layer | Where | Size | Reachable from production? |
|---|---|---|---|
| **Parsers** | `crackerjack/parsers/` | 13 JSON + 27 regex parsers (40 parsers, 34 unique tool keys) | Yes — the live issue path |
| **QA adapters** | `crackerjack/adapters/{_qa_adapter_base,_tool_adapter_base,factory,health_mixin}.py` + `format/`, `refactor/`, `sast/`, `type/`, `complexity/`, `dependency/`, `lint/`, `performance/`, `security/`, `test/`, `treesitter/`, `utility/`, `benchmark/` | 18 `BaseToolAdapter` subclasses | 6 buildable by the factory; only **5 reachable via a hook** (`bandit` has no `HookDefinition`) |
| **Language adapters** | `crackerjack/adapters/{base,registry}.py` + `kotlin/`, `python/`, `swift/`, `web/` | 4 PEP 621 entry points | **Yes — four registered MCP tools** |
| **AI provider registry** | `crackerjack/adapters/ai/` | live via `cli/handlers/provider_selection.py:11` | Yes |
| **Plugin hooks** | `crackerjack/plugins/` | `CustomHookDefinition` | No — being deleted by the concurrent plan |

Production coupling points to the **QA** layer, outside
`crackerjack/adapters/**`:

| # | Site | Covered by this plan? |
|---|---|---|
| 1 | `crackerjack/executors/hook_executor.py:2315` | yes |
| 2 | `crackerjack/server.py:26` | yes |
| 3 | `crackerjack/cli/clone_cli.py:9` | yes (`pyscn` moves) |
| 4 | `crackerjack/cli/handlers/health.py:126` | **yes — Phase 5** |
| 5 | `crackerjack/cli/handlers/provider_selection.py:11` | **yes — Phase 5** |
| 6 | `crackerjack/core/language_detector.py:5` | **language layer — untouched** |
| 7 | `crackerjack/mcp/tools/language_tools.py:14-20,162-165,303,352` | **language layer — untouched** |
| 8 | `crackerjack/parsers/json_parsers.py:307` → `adapters/_output_paths.py` | **yes — Phase 5 moves it** |
| 9 | `pyproject.toml:185-188` (entry points) | **language layer — untouched** |

Production coupling points to the **language** layer: 8 sites, none of which
this plan may break. `crackerjack/adapters/registry.py` must be **split**, not
deleted: the legacy `AdapterRegistry` class and `get_adapter_registry()` are
test-only, but `discover_adapters()` in the same module is live — it is called
from `crackerjack/mcp/tools/language_tools.py:259` and reads the
`crackerjack.language_adapters` entry-point group. Its failure mode is a
**silent** empty adapter set (`registry.py:100-122` catches every exception
and logs a warning), so breaking it would not crash — it would just make four
MCP tools report nothing.

### Verified facts about the QA adapter layer

- **`ToolIssue`, `ToolExecutionResult`, `QABaseSettings`, and
  `ToolAdapterSettings` have no production consumer outside
  `crackerjack/adapters/**` at all.**
- **`QAResult`, `QACheckConfig`, and `QACheckType` have exactly two external
  consumers**: `HookExecutor._try_get_qa_result_for_hook`
  (`crackerjack/executors/hook_executor.py:2297-2395`) and its two helpers
  (`_qa_result_issues:848`, `_handle_no_issues_for_failed_hook:875`), plus
  the protocol signature at `crackerjack/models/protocols.py:694-695`. The
  executor *does* import `QACheckConfig` and `QACheckType`
  (`hook_executor.py:2316-2317`); only `QAResult` flows through as `t.Any`.
- **`HookResult.qa_result` (`crackerjack/models/task.py:56`) is written once
  and never read.** `grep` for `.qa_result` across the whole repository,
  production and tests, returns zero hits.
- **`Issue` (`crackerjack/models/issues.py:39`) is the live issue type.** At
  least six production sites read its attributes: `hook_executor.py:1037/1039`,
  `async_hook_executor.py:856/894/896`,
  `services/pattern_cache.py:105,122-125`,
  `services/quality/pattern_cache.py:122-125` (that module is live — imported
  by `services/pattern_detector.py:13`), and `services/prompt_evolution.py:65-68`.
- **`models/issues.py:76` `CrackerjackRunResult` is never referenced in this
  repo — but its docstring says an external ai-fix-loop driver depends on the
  schema.** It is out-of-repo load-bearing; it lives in the same file Phase 5
  touches and its `schema_version` must not move.
- **`crackerjack/models/__init__.py:27-29` re-exports `QAResult`,
  `QAResultStatus`, `QACheckType`, `QACheckConfig`, and `QAAdapterProtocol`;
  nothing imports any of them via `from crackerjack.models import ...`.** The
  `__all__` entries at `:60-64` must be removed with the imports.
- **`crackerjack/core/phase_coordinator.py:1149-1151` constructs a
  `ParserFactory()` and discards it** — a no-op with no effect.

### The MCP server's adapters are decorative — and the report is a false green

`crackerjack/server.py` is **not** the MCP server. `crackerjack/mcp/server_core.py`
never imports `crackerjack.adapters` for QA. `CrackerjackServer` has exactly
one importer in the repo — the `crackerjack qa-health` command at
`crackerjack/__main__.py:814` — and that command constructs the server and
calls `get_health_snapshot()` **without awaiting `start()`**. So
`_init_qa_adapters()` never runs, `self.adapters` is `[]`, and the health block
reads `total=0, healthy=0`. The command prints "Total adapters: 0 / Healthy
adapters: 0", then "✅ All adapters healthy", and exits 0.

Two defects follow: the `cleanup()` loop (`:134`) tests
`hasattr(adapter, "cleanup")` and **no adapter defines `cleanup`**, so it never
executes; and the healthy count (`:156-159`) computes
`getattr(a, "healthy", True)` and **no adapter defines `healthy`**, so the
default `True` applies to every adapter and the count always equals the total
— had any adapter ever been constructed.

### The hook-config sources, measured

| # | Source | Holds | Linked by |
|---|---|---|---|
| 1 | `crackerjack/config/hooks.py` | `FAST_HOOKS` (18) + `COMPREHENSIVE_HOOKS` (14) = **32** `HookDefinition` objects, plus 3 opt-in-generated | — |
| 2 | `crackerjack/config/tool_commands.py` | the argv for each hook name | hook name string |
| 3 | `settings/crackerjack.yaml` **top level** (there is no `hooks:` sub-table) | `enable_pyrefly: false`, `enable_ty: true`, `experimental_hooks: false`, `skip_hooks: false`; and `adapter_timeouts` (also top level). `enable_ty_ignore_syntax` exists **only** as a schema default (`config/settings.py:30`) — it is not in the YAML | hook name string |
| 4 | `settings/profiles/*.yaml` `checks.enabled` | `ruff`, `pytest`, `coverage`, `bandit`, `safety`, `mypy`, `complexipy` | tool name string — **a different vocabulary** |
| 5 | `crackerjack/plugins/` | `CustomHookDefinition` | hook name string — **being deleted by the concurrent plan** |

The linkage is by bare string in every case. Nothing verifies that a name in
source 3 or 4 exists in source 1, that a hook in source 1 has a command in
source 2, or that a hook in source 1 has a parser.

Two concrete consequences:

- **`stage` is documentary metadata for built-in hooks and a behavioural
  switch for plugin hooks.** `HookDefinition`'s own docstring says so:
  *"The bifurcation exists because the two registration paths share this
  dataclass but derive execution semantics differently."* For a built-in
  hook, which list it lives in decides whether it runs; the `stage` field is
  a convention nothing enforces, so drift between the two is a silent
  inconsistency.
- **`settings/profiles/comprehensive.yaml` lists `mypy` and `safety`.** Neither
  is a hook — the type checker is `ty`/`pyrefly`, the dependency scanner is
  `osv-scanner`. **Only 1 of its 7 names (`complexipy`) is a hook at all**;
  `ruff` is two hooks (`ruff-check`, `ruff-format`), and `pytest`, `coverage`
  and `bandit` are not hooks. See Phase 1, which drops this work.

### A fifth registry, and a live bug in the settings knobs

**`crackerjack/models/tool_config.py` is a per-tool structured-output
registry** — `ToolConfig(name, supports_json, json_flag, output_format, fallback_to_regex, required_json_fields)` and a 16-entry `TOOL_CONFIGS`
(`:39-149`). It is exactly where the structured-output flag lives, and it is
already a third source of truth:

- `get_json_flag` (`tool_config.py:161-163`) has **zero non-test consumers**.
- `supports_json` is read in exactly one production place —
  `crackerjack/parsers/factory.py:99`.
- `TOOL_CONFIGS["complexipy"].json_flag` is `"--output-json"`
  (`tool_config.py:101`), but the real argv is
  `--output-format json --output /tmp/complexipy_results_{pid}.json`
  (`tool_commands.py:366-369`). The registry and the command table have
  already diverged.
- `TOOL_CONFIGS` has no entry for `pyrefly`, `ty`, `ty-ignore-syntax`,
  `cohesion`, `creosote`, or `pymetrica`.

**Decision: `TOOL_CONFIGS` is out of scope for this plan.** Phase 1 does
*not* fold `supports_json` / `json_flag` / `required_json_fields` into
`HookSpec`; the catalog records the structured-output flag where it is
actually used — in `StructuredRerun.argv_template` — and `TOOL_CONFIGS` stays
as it is.

**This plan therefore does not deliver "one source of truth" for
structured-output flags — it delivers it for hooks.** `StructuredRerun`'s
argv template, `tool_commands.py`'s argv, and `TOOL_CONFIGS`' `json_flag` are
three places a flag is written down, and the third already disagrees with the
second for `complexipy`. That triple-bookkeeping is a future-drift hazard and
is recorded as a Phase 6 follow-up, not resolved here.

**Why out of scope:** `TOOL_CONFIGS` is a *tool* registry (16 tools, some with
no hook) and this phase's subject is a *hook* registry. Merging them would
make the catalog carry entries for tools that are not hooks — the same
category error the profile vocabulary already made. The follow-up is the right
home for it.

**The operator-facing hook flags in `settings/crackerjack.yaml` are inert.**
The YAML puts `enable_pyrefly`, `enable_ty`, `skip_hooks` and
`experimental_hooks` at the **top level**, but `config/hooks.py:454,468,482`
reads `settings.hooks.<key>`. Because the root model allows extras, the flat
values land in `__pydantic_extra__` and **never reach `settings.hooks`** —
verified at runtime: a YAML with `enable_pyrefly: true` still yields
`settings.hooks.enable_pyrefly == False`. The operator's `enable_pyrefly`
switch does nothing.

Worse, the two consumers of the same knob read **different places**:
`config/hooks.py` reads `settings.hooks.enable_ty` while
`crackerjack/server.py:79-86` reads the flat `settings.enable_ty`. That is
precisely the drift this plan exists to remove, and it is live today.

Two more knobs the plan must classify rather than assume:
`experimental_hooks` is plumbed through the CLI, the MCP server and the models
but **read by no gate** (a dead knob), while `skip_hooks` *is* consumed
(`core/phase_coordinator.py:322,360,518`).

### The tool-name coverage matrix

Derived at runtime from the registry and the resolved strategies (29 live
hooks: 18 fast + 11 comprehensive):

```
LIVE hook with NO registered parser (2):  tc-refs, no-conflict-markers
Registered parser with NO live hook (7): bandit, complexipy, complexity,
                                          gitleaks, mypy, pytest, ruff
```

**`pyrefly` is not a live hook.** It is opt-in
(`settings.hooks.enable_pyrefly`, default `False`), so it is off in every
default run. It is an *inversion* only when an operator turns it on: it then
has an adapter in the factory's table and no parser, so the **async** executor
falls back to generic line extraction while the **sync** executor gets
structured issues from the adapter.

Two consequences for this plan:

- The **live** parser gaps are `tc-refs` and `no-conflict-markers`, not
  `pyrefly`. `tc-refs` has a dedicated executor parser
  (`_parse_tc_refs_issues`) that returns `[]` for a zero count on purpose;
  `no-conflict-markers` has nothing.
- **`bandit` is not a hook.** It has a command builder, a `ToolConfig`, an
  `AdapterTimeouts` entry and a registered parser, but no `HookDefinition` —
  so the Bandit adapter's fallback can never fire. This is how a tool
  acquired a parser and an adapter while never being a hook.

### The structured-output fallback, and why the plan must not re-run the hook's command

The QA-adapter fallback runs when a hook **failed** and the text parsers
produced **nothing**. It re-runs the tool and uses the structured issues it
finds in place of the generic `"hook exited with code N but reported no parseable issues"` message. That is a real capability and a real bug fix
(`9e76f4de`, bounded in `d4c98598`).

**The fallback's value comes from building a *different* argv than the hook
runs.** Two facts make "re-run the hook's command" the wrong design:

1. **The hook's command already carries the structured-output flag** for four
   of the six wired tools:

   | hook | hook command | already structured? |
   |---|---|---|
   | `ruff-check` | `ruff check --output-format json --fix --config <inline> <targets>` | yes |
   | `bandit` | `bandit -r --format json <targets>` | yes |
   | `semgrep` | `semgrep scan --quiet --error --json <targets>` | yes |
   | `pyrefly` | `pyrefly check --output-format json --summary none <targets>` | yes |
   | `refurb` | `refurb <targets>` | **no** — `supports_json=False` |
   | `ty` | `uv run python -m crackerjack.tools.ty_ratchet --split …` | **no** — and it is crackerjack's ratchet wrapper, not `ty` itself |

   Re-running such a command reproduces byte-identical output to the run that
   just failed to parse. **The fallback would be a no-op.**

1. **`ruff-check`'s hook command carries `--fix`.** Re-running it would apply
   `--fix` a **second** time, inside a *reporting* path, after the hook
   already fixed the working tree. The adapter deliberately did **not** do
   this: `ruff.py:119-139` builds `["ruff", "check"]` and
   `_add_check_mode_options` (`:142-170`) adds `--fix` only when
   `settings.fix_enabled` is true (`RuffSettings.fix_enabled` defaults
   `False`).

   The two commands also differ in **file scope**: the hook targets
   *directories* (`_build_targets()` → `tool_commands.py:52-64`) while the
   adapter targets *every individual `.py` file* under the package
   (`_tool_adapter_base.py:273-300`).

So the replacement needs the adapter's `build_command`, and the plan needs a
record that can express it. That record is `StructuredRerun` (below) — five
fields, not a 4,000-line package.

### The two issue shapes are **not** the same

The adapter path emits `<path>:<line> - <code>: <message>`
(`hook_executor.py:848`), which carries the tool's error code. The parser path
emits `<path>:<line>: <message>` (`hook_executor.py:1030`), which does not —
`crackerjack.models.issues.Issue` has no `code` field; it has `type`,
`severity`, `message`, `id`, `file_path`, `line_number`, `details`, `stage`.

The first draft of this plan asserted the two were the same shape. They are
not, and Phase 4 has to pick one.

### `_REPORTING_TOOLS` carries **two** behaviours, not one

`hook_executor.py:102-115` defines the frozenset, and it is used at five
sites of which only one is parser dispatch:

- `:943` — parser dispatch (the plan's Phase 3 targets this).
- `:824` — `status_flipping_tools = self._REPORTING_TOOLS - {"ty"}` → flips a
  hook to `"failed"` when issues are found. **A different rule**, coupled to
  the parser semantics: `tc-refs` returns `[]` for a zero count precisely so
  a clean repo does not flip.
- `:800`, `:829`, `:934` — debug printing.

Deleting the frozenset without relocating the flip rule changes status
semantics. `ty` would gain status-flipping; `ruff-check`, `cohesion` and
`pymetrica` would gain it; and the async executor has no equivalent set at
all.

### What this plan does not touch

- **`crackerjack/services/patterns/` — live, and permanently out of scope.**
  `SAFE_PATTERNS` (`services/patterns/__init__.py:38`) is read by 15+ production
  modules beyond `individual_hook_executor.py`: `services/regex_patterns.py`,
  `services/regex_utils.py`, `services/patterns/operations.py` (60 sites),
  `services/api_extractor.py`, `services/coverage_badge_service.py`,
  `services/documentation_service.py`, `services/input_validator.py`,
  `services/security.py`, `services/secure_status_formatter.py`,
  `crackerjack/api.py`, `crackerjack/code_cleaner.py`,
  `documentation/ai_templates.py`. It backs input validation, path security,
  the coverage ratchet, publish version bumping and the MCP job-id validator.
  The concurrent plan's own failure condition requires `SAFE_PATTERNS` to
  survive with `len >= 180`. The `pyright` output patterns in
  `services/patterns/tool_output/pyright.py` are one of twelve sub-registries
  and are read by `individual_hook_executor.py`, which the concurrent plan
  deletes — that removes one reader of many, not the registry.
- **`settings/profiles/*.yaml`** — see Phase 1's resolved decision.
- **`crackerjack/adapters/ai/`** — not a QA adapter layer, and it keeps its
  construction path (`adapters/ai/registry.py:68-71` →
  `cli/handlers/provider_selection.py:141`), independent of the factory.
  Phase 5 deletes the factory's special case and nothing else.
- The **language adapter layer** — `base.py`, `registry.py`'s
  `discover_adapters()`, `kotlin/`, `python/`, `swift/`, `web/`, and
  the `pyproject.toml` entry points that load them.

______________________________________________________________________

## Phase 1 — One hook catalog

### Scope

Introduce a single `HookSpec` record per hook in one place, and make every
other source a *reference* to it rather than a parallel declaration.

**New: `crackerjack/config/hook_catalog.py`.** One `HOOK_CATALOG`, one entry
per hook. The catalog is the **only** place a hook is declared.
`HookConfigLoader` resolves `stage` into the fast and comprehensive strategies
from the catalog rather than from two separate lists, which removes the "which
list decides whether it runs" question and makes `stage` load-bearing for
built-ins the way it already is for plugins.

```python
@dataclass(frozen=True)
class CommandContext:
    """What a command builder needs from the run.

    A builder cannot be zero-argument: crackerjack's argv depends on the
    detected package name, the run's root, and — for some tools — a version
    probe and a report path.
    """

    package_name: str
    pkg_path: Path


@dataclass(frozen=True)
class StructuredRerun:
    """How to re-run a tool with structured output, for the fallback path.

    The adapter's `build_command` was the thing that constructed the
    *alternative* argv -- a parser key cannot express "re-run `ruff` with
    `--output-format json`, over these files, without `--fix`". This record
    is the whole of what that machinery was worth.
    """

    tool: str
    argv_template: tuple[str, ...]
    parser: str  # ParserFactory key
    env: Mapping[str, str] = field(default_factory=dict)
    file_scope: str = "package"  # "package" | "targets"


@dataclass(frozen=True)
class HookSpec:
    name: str
    tool: str  # "ruff" for both ruff-check and ruff-format
    stage: HookStage
    timeout: int
    parser: str | None  # ParserFactory key
    command_factory: Callable[[CommandContext], list[str]] | None
    structured_rerun: StructuredRerun | None
    status_flip_on_issues: bool  # the _REPORTING_TOOLS - {"ty"} rule
    security_level: SecurityLevel
    accepts_file_paths: bool
    enabled: bool
    opt_in_setting: str | None  # settings flag name, if opt-in
    is_formatting: bool  # consumed by hook_executor.py:809-813
    scans_own_target: bool  # refurb only: suppress file-target splicing
    retry_on_failure: bool
    run_schedule: str | None
    allow_unsafe_fixes: bool
    description: str | None
```

`scans_own_target` is load-bearing and was missing from the first draft:
`refurb` forwards everything after `--` to Mypy, so a catalog-driven
`build_command` that appends `crackerjack/` after the separator makes refurb
fail with "unrecognized argument" (`hooks.py:98-111`).

**`crackerjack/config/tool_commands.py`** keeps the argv construction — it
carries version-probing logic that does not belong in a data file — but the
catalog references `get_tool_command(name, …)` **whole**, not its parts.
There are no per-tool builder functions: the argv is one flat 38-entry dict
(`tool_commands.py:209-432`), and `get_tool_command` (`:462-504`) applies
post-processing the dict cannot carry — the `--unsafe-fixes` injection
(`:481-492`), the `ty --verbose` append (`:494-495`), and
`build_refurb_mypy_args` (`:499-502`, which reads the repo's own
`[tool.refurb].mypy_args`).

The table also registers tools with **no hook** — `bandit` (`:290`) and
`plan-index-sync` (`:210`). A hook with no command is a catalog error; a
command with no hook is a fact the catalog should be able to express.

**`settings/crackerjack.yaml`** keeps its top-level flags, but every hook name
in it must name a hook in the catalog. `enable_pyrefly` becomes
`pyrefly: {enabled: false}` — keyed by hook name, with the flag names derived
from the catalog rather than hand-written. The flat top-level keys are
**removed in the same commit**, so there is never a moment with two sources of
truth.

**`HookDefinition`** survives as the resolved, per-run value — a `HookSpec`
plus the settings overrides applied — so the executors do not change shape.

### Integration Contract

- **Triggered from**: `HookConfigLoader.load_strategy()`, called by
  `HookManagerImpl` (`crackerjack/managers/hook_manager.py:390,457,546`) and
  `AsyncHookManager` (`crackerjack/managers/async_hook_manager.py:73`), and by
  `crackerjack/core/phase_coordinator.py:544`.
- **Returns to / updates**: `settings/crackerjack.yaml`;
  `crackerjack/config/hooks.py`; `crackerjack/config/tool_commands.py`.
- **Demonstrable by**: `crackerjack run -f` still reports 18/18 fast hooks;
  `crackerjack run -v` still reports the same comprehensive set; a typo in a
  settings hook name is reported at load time rather than ignored.
- **Rollback signal**: the fast or comprehensive hook set changes membership.
- **Observability added**: a startup log line listing the resolved hook set
  with each hook's parser, so "which parser does this hook use?" is
  answerable from the run log.

### Resolved decisions

1. **The catalog is Python, not YAML.** `tool_commands.py` carries version
   probing (`preferred_binary_command_with_min_version`) that a data file
   cannot express, and a YAML catalog would reintroduce the string-keyed
   coupling the phase is meant to remove. Python also lets the catalog
   resolve its references **at import time**, so a bad parser key is an
   import error, not a runtime `KeyError`.

1. **Keep `HookDefinition` as the resolved value.** The executors take
   `HookDefinition`; changing that is a separate, larger change. The catalog
   produces them.

1. **The catalog names parsers, and the parser registry stays where it is.**
   The catalog is the *index*; `ParserFactory` remains the implementation of
   parsing. Phase 2 makes the registry complete enough for the catalog to be
   honest.

1. **`settings/profiles/` is out of scope, and its deletion is a separate
   commit (Phase 6, item 1).** `ProfileLoader` has no production importer:
   `load_profile`, `get_profile_loader` and `list_profiles` are reached only
   from `crackerjack/cli/profile_handlers.py`, which reads
   `ProfileConfig.checks` — an unvalidated `dict[str, Any]` — to *print* a
   list. No runtime path consults `checks.enabled`, so the vocabulary is not a
   gate and renaming it would change nothing observable. Two of the entries
   are not hooks and have no hook equivalent (`pytest` and `coverage` are
   quality-gate inputs), and the same stale vocabulary appears in
   `checks.disabled` (quick.yaml:15-21, standard.yaml:17-21). Deleting dead
   configuration is real work, but it is not this plan's work: it has its own
   commit and its own risk surface. **This plan does not touch the profile
   files, and does not claim the vocabulary is validated.**

1. **The catalog is not the cost; the settings load is.** Measured on `main`
   at `22fb3e06`: `import crackerjack.config.hooks` takes **7.0 s** (the
   module-level `settings_instance = load_settings(CrackerjackSettings)` in
   `crackerjack/config/__init__.py`, plus the Oneiric import chain);
   `HookConfigLoader.load_strategy("fast")` takes 0.11 s cold and 0.077 s
   warm; `load_strategy("comprehensive")` takes 0.27 s. `load_settings` is not
   cached, and the comprehensive path calls it **twice** — once in
   `_build_opt_in_type_hooks` and once in `_update_hook_timeouts_from_settings`.
   Building ~33 frozen `HookSpec`s at import is tens of microseconds and is
   invisible against those numbers. `load_strategy` is not a hot path: it is
   called about nine times across `hook_manager.py` and `async_hook_manager.py`,
   always at run setup and never per hook.

   Two changes are therefore in scope for Phase 1, and both make the catalog
   *cheaper* than what it replaces:
   a. **Resolve settings once per `load_strategy` call** and derive both
   strategies from that single resolution. This halves the comprehensive
   path.
   b. **Stop mutating module-level singletons.** `FAST_STRATEGY.hooks` *is*
   the `FAST_HOOKS` list, and `COMPREHENSIVE_STRATEGY.hooks` shares
   `HookDefinition` objects with the list `load_strategy("comprehensive")`
   returns; `_update_hook_timeouts_from_settings` mutates them in place, so
   a timeout override leaks into every later call in the same process. The
   catalog builds fresh `HookDefinition`s per call from frozen specs, which
   fixes this for free.

5. **This supersedes `.claude/decisions/2026-10-12-hook-stage-documentary-vs-enforced.md`.**
   That record is `status: active`, `role: canonical`, and governs exactly this
   change: *"HookDefinition.stage is documentary-only for built-in entries…
   Every new hook added to FAST_HOOKS or COMPREHENSIVE_HOOKS requires the
   contributor to manually set stage correctly; this is fragile."* Its two
   acceptable fix shapes (a runtime `__post_init__` check with a `_builtin`
   marker, or a test pin) both assume the two lists survive. The catalog
   removes the lists, so `stage` becomes load-bearing by construction and
   neither shape applies. **Phase 1 updates that record to `status:
   superseded` in the same commit**, with `superseded_by` pointing at this
   plan.
6. **`ty` and `ty-ignore-syntax` exist twice today and the catalog holds
   them once.** `COMPREHENSIVE_HOOKS` contains static *placeholders* for both
   with `auto_run=False` (`hooks.py:288-315`), and `_build_opt_in_type_hooks()`
   appends *runnable* entries with the **same names** and `auto_run=True`
   (`hooks.py:444-499`); `_build_comprehensive_hooks()` filters the static ones
   out with `h.auto_run and not h.disabled`. The catalog holds one entry per
   name, with `opt_in_setting`; the loader emits it only when the flag is on,
   only for the comprehensive stage, and the failure mode of a settings-load
   error is "no opt-in hooks", not a per-flag fallback.

1. **`auto_run`, `enabled_by_default`, `opt_in_setting` and `disabled` collapse
   to `enabled` plus `opt_in_setting`.** The four-field version had already
   drifted at 32 entries (`gitleaks` is `auto_run=True, disabled=True`).

### Risks

1. **A hook with no parser.** The registry covers every live hook except
   `pyrefly` (Phase 2 fixes that) and `tc-refs` (Phase 2 adds it). The
   catalog's `parser` field must not be a lie, so Phase 2 lands before the
   catalog is trusted.
1. **Timeout override names.** `adapter_timeouts` uses
   `<hook_name>_timeout` and `<hook_name-with-dashes>_timeout`. The catalog
   keeps both spellings working by deriving them from `HookSpec.name`.
1. **Opt-in hooks are comprehensive-only.** `pyrefly`, `ty` and
   `ty-ignore-syntax` are `stage=HookStage.COMPREHENSIVE`; the fast strategy
   never gets them. The catalog filter must be stage-aware.
1. **The 7-second import.** The catalog must not add to
   `import crackerjack.config.hooks` — in particular it must not import
   `tool_commands` at module scope beyond what `hooks.py` already does.

### Estimated scope

1 new module, 2 rewritten modules, 1 settings file, 1 consistency test,
~600 lines net. (`TOOL_CONFIGS` is out of scope — see the Context section.)

______________________________________________________________________

## Phase 2 — Move the executor's per-tool parsers into the registry

### Scope

`crackerjack/executors/hook_executor.py` carries nine tool-specific parsers:
seven private methods reached by name (`_parse_refurb_issues`,
`_parse_gitleaks_issues`, `_parse_creosote_issues`, `_parse_osv_scanner_issues`,
`_parse_lychee_issues`, `_parse_ty_ratchet_issues`, `_parse_tc_refs_issues`),
the module-level `parse_ty_ratchet_issues`, and two text fallbacks inside
`_extract_issues_via_json_parser` (`_parse_pyscn_issues`,
`_parse_complexipy_issues`).

The parser registry already holds an entry for nine of the ten
`_REPORTING_TOOLS` — `RefurbRegexParser`, `PyscnJSONParser`,
`GitleaksJSONParser`, `CreosoteRegexParser`, `OsvScannerJSONParser`,
`LycheeJSONParser`, `ComplexipyJSONParser` / `ComplexityRegexParser`,
`TyRegexParser` — and the live path never calls them, because the executor
shadows them with local functions. `tc-refs` has no entry at all.

Move each parser into `crackerjack/parsers/` as a registry entry and delete the
executor's private copies, so the executor has **zero** tool-specific knowledge
and `HookSpec.parser` names the only parser for every hook.

| executor-local parser | registry entry | work needed |
|---|---|---|
| `_parse_refurb_issues` | `RefurbRegexParser` | move; the `[FURB123]` code needs `Issue.code` — **added in this phase** (see below) |
| `_parse_gitleaks_issues` | `GitleaksJSONParser` | move; the registry parser supersedes a keyword filter |
| `_parse_lychee_issues` | `LycheeJSONParser` (+ regex) | move |
| `_parse_osv_scanner_issues` | `OsvScannerJSONParser` | move; **must learn** `crackerjack/config/pip_audit_ignores.py:IGNORED_VULNERABILITY_IDS` |
| `_parse_creosote_issues` | `CreosoteRegexParser` | move the bullet-per-category semantics into the registry entry |
| `_parse_pyscn_issues` | `PyscnJSONParser` | move; the registry parser must also read the *text* `check` failure form |
| `_parse_complexipy_issues` | `ComplexipyJSONParser` / `ComplexityRegexParser` | move; the first draft of this plan omitted this one entirely |
| `parse_ty_ratchet_issues` | `TyRegexParser` (registered, never called) | **not as-is** — the ratchet logic is crackerjack's own tool's output format, not `ty`'s. Becomes `TyRatchetParser`, registered under `ty-ratchet` |
| `_parse_tc_refs_issues` | **none** | **new** `TcRefsParser`, registered under `tc-refs` |
| — | **none** | **new** `NoConflictMarkersParser`, registered under `no-conflict-markers` |
| — | **none** | **new** `PyreflyJSONParser`, registered under `pyrefly` (opt-in hook) |

**The two live parser gaps are `tc-refs` and `no-conflict-markers`.**
`tc-refs` has a dedicated executor parser (`_parse_tc_refs_issues`) that
returns `[]` for a zero count *on purpose*, so a clean repo does not flip to
failed — that semantics must move with it into a `TcRefsParser`.
`no-conflict-markers` has nothing at all.

**`Issue` gains `code: str | None = None` in this phase.** The codes the
moved parsers carry (`[FURB123]`, ruff's `F401`, semgrep's rule ids) are
information the Fast Hook Results table shows today. The field is optional
with a `None` default, so no existing construction site or caller changes;
the executor's formatter emits `<path>:<line> - <code>: <message>` when
`code` is set and `<path>:<line>: <message>` when it is not. The field is
added **without** touching `CrackerjackRunResult` and **without** bumping
the `schema_version` an external ai-fix-loop driver depends on.

**`pyrefly` is a prerequisite only for operators who enable it.** It is
opt-in and off by default (`settings.hooks.enable_pyrefly == False`), so it
is not a live hook — but when it *is* enabled it is the one tool for which
the adapter path is the better of the two, because it has an adapter and no
parser. `PyreflyJSONParser` lands here so that turning the knob on does not
depend on the adapter layer's existence.

### Integration Contract

- **Triggered from**: `HookExecutor._extract_issues_for_reporting_tools`,
  `AsyncHookExecutor._parse_factory_issues`.
- **Returns to / updates**: `crackerjack/parsers/json_parsers.py`,
  `crackerjack/parsers/regex_parsers.py`,
  `crackerjack/executors/hook_executor.py`.
- **Demonstrable by**: `grep -n "_parse_" crackerjack/executors/hook_executor.py`
  returns no per-tool parser; every catalog hook resolves to a registered
  parser; `pyrefly` produces structured findings.
- **Rollback signal**: a hook's issue count changes.
- **Observability added**: none needed.

### Resolved decisions

1. **`ty` becomes a crackerjack parser, not a `ty` parser.** The ratchet's
   prod/test split and `Found N diagnostics` suppression are crackerjack's own
   output format. `TyRegexParser` parses raw `ty` output
   (`path:line:col: severity[code]: message`) and would find nothing in the
   ratchet's output.
1. **`OsvScannerJSONParser` learns the ignore list.** The registry parser
   does not currently honour `IGNORED_VULNERABILITY_IDS`; the executor's local
   parser does.
1. **`GitleaksJSONParser` replaces `_parse_gitleaks_issues`**, which is a
   keyword filter and strictly less accurate. This is a quality improvement,
   not a port.

### Risks

1. **The per-tool parsers encode version-specific knowledge** (creosote's
   modern-vs-legacy bullet forms, pyscn's JSON-vs-text split). Moving them
   must preserve that, not flatten it.
1. **`Issue` has no `code` field**, so `[FURB123]` and similar codes are lost
   in the move unless Phase 4 adds the field. The plan sequences Phase 4
   accordingly.

### Estimated scope

2 parser modules, 1 executor module, ~10 new or updated parser classes,
1 test file.

______________________________________________________________________

## Phase 3 — One parser path in both executors

### Scope

Make the **sync** executor reach the parser registry the way the **async**
executor already does, and retire the hand-maintained
`HookExecutor._REPORTING_TOOLS` frozenset.

By this phase the per-tool parsers live in `crackerjack/parsers/` and are
reached through the registry, so the special cases are no longer a membership
test in a frozenset *and* no longer private methods — they are registry
entries, which is the only place a tool's output format should live.

**The status-flip rule moves with them.** `_update_status_for_reporting_tools`
flips a hook to `"failed"` when issues are found, for `_REPORTING_TOOLS - {"ty"}`. That rule is coupled to the parser semantics: `tc-refs` returns `[]`
for a zero count precisely so a clean repo does not flip. It becomes
`HookSpec.status_flip_on_issues`, next to the parser it governs.

**Three hooks have a registered parser the sync path never calls**:
`cohesion`, `pymetrica`, and — the one the first draft of this plan missed —
`check-jsonschema`, which is inside the JSON dispatch set
(`hook_executor.py:963`) but is *not* in `_REPORTING_TOOLS`, so `:943`
diverts it to the generic extractor.

**The scope is narrower than "every hook with a parser".** The sync executor's
other 22 hooks go through `_extract_issues_for_regular_tools`, which returns
`[]` for passing hooks, special-cases `ruff-check` JSON, **returns `[]`
outright when the output starts with `{` or `[`** (`:1244`), and otherwise uses
the `extract_issue_lines` heuristic. Routing all of them through
`ParserFactory` changes counting semantics (per-file vs per-line) for ~15
hooks whose registry parsers have never run on the live path. That migration
is **separate and opt-in**, with a per-hook before/after count — it is not
this phase.

### Integration Contract

- **Triggered from**: `HookExecutor._extract_issues_from_process_output`.
- **Returns to / updates**: `HookExecutor._REPORTING_TOOLS` is deleted;
  `HookSpec.status_flip_on_issues` replaces it.
- **Demonstrable by**: a `cohesion` hook that fails produces the same issue
  text through the sync executor as through the async one; `ty` does **not**
  gain status-flipping.
- **Rollback signal**: **any hook's PASSED/FAILED status changes**, not just
  its issue count.
- **Observability added**: none needed.

### Resolved decisions

1. **Do not delete the per-tool parsers** — Phase 2 moved them.
1. **The remaining ~15 heuristic hooks keep their heuristic** in this phase.
   Migrating them is a separate, opt-in change with its own baseline.
1. **`tc-refs` needs an explicit `NO_PARSER` exemption** if Phase 2's
   `TcRefsParser` does not land, because Failure Condition #2 would otherwise
   fire on it. Phase 2 lands it, so no exemption is needed — but the
   allowlist must exist as data, not as prose.

### Risks

1. **The generic extractor and a registered parser disagree.** Where a
   registered parser exists but the generic extractor also matched lines, the
   issue count changes. The full suite and the Phase 4 baseline fixture are
   the check.

### Estimated scope

2 modules, ~200 lines net, 1 test file.

______________________________________________________________________

## Phase 4 — A parser-based structured-output fallback

### Scope

Replace the adapter-based QA fallback with one expressed in the parser
taxonomy, keeping the capability that `9e76f4de` and `d4c98598` established.

New behaviour, in the sync executor, when a hook **failed** and the registered
parser produced **nothing**:

1. Look up the hook's `HookSpec.structured_rerun`.
1. If there is one, build the **adapter-shaped** argv — tool plus structured
   output flag, explicit file list, **no `--fix`** — bounded by the hook's
   timeout.
1. Feed the output to the rerun's parser and use the resulting issues in
   place of `"hook exited with code N but reported no parseable issues"`.

**The timeout never lives in the command** — it reaches the subprocess through
the executor: `hook_executor.py:540-548` (`subprocess.run(command, …, timeout=hook.timeout)`) for `hook.timeout <= 120`, and `:564-616`
(`Popen` + `communicate(timeout=hook.timeout)`) above that. The fallback must
pick one of those two paths explicitly; "bounded by the hook's timeout" is
not free.

**The re-run must NOT be the hook's own command.** For `ruff-check`,
`bandit`, `semgrep` and `pyrefly` the hook's command already carries the
structured-output flag, so re-running it reproduces byte-identical output to
the run that just failed to parse — a no-op. For `ruff-check` it would also
re-apply `--fix` **and `--unsafe-fixes`** inside a reporting path, mutating
the working tree a second time. `tool_commands.py:481-492` injects
`--unsafe-fixes` whenever `settings.ruff_unsafe_fixes` is true, and
`HookSettings.ruff_unsafe_fixes` defaults to **True**
(`config/settings.py:32`) — so the hook's default argv is
`ruff check --output-format json --fix --unsafe-fixes --config …`. The
adapter deliberately did **not** do this: `ruff.py:119-139` builds
`["ruff", "check"]` and `_add_check_mode_options` (`:142-170`) adds `--fix`
only when `settings.fix_enabled` is true (`RuffSettings.fix_enabled`
defaults `False`).

**The fallback does not exist for every tool.** Of the six adapters the
factory can build, only **`ruff`, `semgrep` and `pyrefly`** have both a JSON
output mode and a registered JSON parser:

| adapter | reachable via a hook? | hook command | structured? | fallback |
|---|---|---|---|---|
| `Ruff` | yes (`ruff-check`, `ruff-format`) | `ruff check --output-format json --fix --unsafe-fixes --config …` | yes, **but mutating** | **yes — the adapter-shaped, fix-free argv** |
| `Semgrep` | yes | `semgrep scan --quiet --error --json …` | yes | **no** — the hook's own output is already structured |
| `Pyrefly` | **opt-in only** | `pyrefly check --output-format json --summary none …` | yes | **no** — already structured |
| `Ty` | yes | `uv run python -m crackerjack.tools.ty_ratchet --split …` | **no** — crackerjack's ratchet wrapper, not `ty` | **no** |
| `Refurb` | yes | `refurb <targets>` | **no** — `supports_json=False` | **no** |
| `Bandit` | **no — `bandit` has no `HookDefinition`** | `bandit -r --format json …` | yes | **no — unreachable** |

So in practice **exactly one tool keeps a structured re-run: `ruff`**, and
only because its hook command is mutating and its output must be re-read
without the fix. **For the other five the fallback is skipped and the generic
message stands.** The catalog records this as `structured_rerun=None`.

Note `ty`'s ratchet has its own `--json` switch
(`crackerjack/tools/ty_ratchet.py:224-226`) that **no parser consumes**, and
`TyRegexParser` expects raw `ty` output
(`path:line:col: severity[code]: message`), so feeding it the ratchet's
output yields nothing.

**The issue format must be decided here.** The adapter path emits
`<path>:<line> - <code>: <message>`; the parser path emits
`<path>:<line>: <message>`, because `Issue` has no `code` field. Either
`Issue` gains `code: str | None` and the executor's formatter includes it, or
the rerun's codes are dropped. The choice changes what operators see in the
Fast Hook Results table and in `crackerjack run --json`.

### Integration Contract

- **Triggered from**: `HookExecutor.execute_single_hook` →
  `_handle_no_issues_for_failed_hook`.
- **Returns to / updates**: `_try_get_qa_result_for_hook` and
  `_qa_result_issues` are deleted.
- **Demonstrable by**: a `ruff-check` hook that fails with unparsable output
  still yields the structured ruff findings instead of the generic message —
  and the working tree is **not** modified a second time.
- **Rollback signal**: the generic `"hook exited with code N but reported no parseable issues"` message appears where structured findings appeared
  before; or a hook's working tree changes during a reporting path.
- **Observability added**: the fallback logs which rerun it used at debug
  level, as the adapter path does today.

### Resolved decisions

1. **Keep the "failed and nothing parsed" gate.** The rerun scans the package;
   doing that when the parser already produced issues is a second full scan
   for a result that would be discarded.
1. **Keep the hook's timeout as the budget.** The adapter's own default was
   300 s, which outlived the hook that triggered it.
1. **Do not re-run the tool when the hook's own output was already
   structured.** The re-run exists for the case where the hook's *text* output
   yielded nothing. The `StructuredRerun` record is only populated for tools
   whose hook command is not already structured.
1. **`Issue` gains `code: str | None = None`, and the executor's formatter
   includes it when present.** The adapter path emitted
   `<path>:<line> - <code>: <message>` and the parser path emits
   `<path>:<line>: <message>`; dropping the code loses information the Fast
   Hook Results table shows today. The field is optional with a `None`
   default, so every existing construction site and every `Issue(...)` caller
   is unaffected. The formatter emits `<path>:<line> - <code>: <message>` when
   `code` is set and `<path>:<line>: <message>` when it is not. This is an
   additive schema change to a model whose `schema_version` is pinned by an
   external ai-fix-loop driver (`models/issues.py:76`), so the field is added
   **without** touching `CrackerjackRunResult` and **without** bumping that
   version. The field is added in **Phase 2**, not Phase 4, so the
   `[FURB123]`-style codes that Phase 2 moves into the registry do not lose
   information on the way.

### Risks

1. **A rerun parser that cannot read the tool's output.** The catalog records
   which parser handles which format, so the pairing is explicit rather than
   inferred.
1. **Double-scanning.** The rerun is bounded by the hook's timeout and gated
   on the parser having produced nothing.
1. **Working-tree mutation.** `ruff-check`'s hook command carries `--fix`.
   The rerun's argv must be built without it. A test asserts the working
   tree is unchanged by the fallback path.

### Estimated scope

1 module, ~150 lines net, 4 tests.

______________________________________________________________________

## Phase 5 — Delete the QA adapter layer

### Scope

With Phases 1-4 in place, the **QA** adapter layer has no remaining consumer.
Delete it — **by file list, not by package**.

**`crackerjack/adapters/` — the QA sub-layer only:**

| File | Note |
|---|---|
| `_tool_adapter_base.py` | `BaseToolAdapter`, `ToolIssue`, `ToolExecutionResult`, `ToolAdapterSettings` |
| `_qa_adapter_base.py` | `QAAdapterBase`, `QABaseSettings` |
| `factory.py` | `DefaultAdapterFactory`, `TOOL_TO_ADAPTER_NAME` |
| `health_mixin.py` | already deleted by the concurrent plan's Phase 3 |
| `format/ruff.py` | |
| `refactor/refurb.py` | |
| `refactor/cohesion.py` | **decided here, not deferred** — see below |
| `refactor/creosote.py` | **decided here, not deferred** — see below |
| `sast/bandit.py`, `sast/semgrep.py`, `sast/_base.py` | `_base.py` holds `SASTAdapterProtocol` |
| `type/pyrefly.py`, `type/ty_adapter.py` | |

**`crackerjack/adapters/registry.py` — split, do not delete.** The legacy
`AdapterRegistry` class and `get_adapter_registry()` are test-only and go.
`discover_adapters()` in the same module is **live** — it is the
entry-point-backed language-adapter discovery that
`crackerjack/mcp/tools/language_tools.py:259` calls — and it stays.

**`crackerjack/adapters/sast/pyscn.py` moves out first.** It *is* a
`BaseToolAdapter` subclass (`sast/pyscn.py:61`) and inherits the QA `check()`
path — but it is not used as one: it is the clone scanner, and the clone CLI
calls it directly (see *Resolved decisions*). Its home is `crackerjack/clone/`, next to `grouper.py`
and `classifier.py`, which are the other clone-domain modules. Its
`PyscnCloneScanError` moves with it.

**Three cross-layer imports move before the QA base classes go:**

| Importer | Imports | Move to |
|---|---|---|
| `crackerjack/parsers/json_parsers.py:307` | `crackerjack.adapters._output_paths.AdapterOutputPaths` | `crackerjack/config/` — the parser layer must not depend on the adapters package |
| `crackerjack/cli/handlers/health.py:126` | `crackerjack.adapters._qa_adapter_base.QAAdapterBase` | deleted — the health check becomes a catalog-hook readiness check |
| `crackerjack/cli/handlers/provider_selection.py:11` | `crackerjack.adapters.ai.registry` | `crackerjack/adapters/ai/` stays (it is not a QA adapter layer); its own fate needs a decision |

**`crackerjack/adapters/ai/` survives untouched.** It is not a QA adapter
layer. `FallbackChainCodeFixer` is constructed through
`crackerjack/adapters/ai/registry.py:68-71` (`get_code_fixer()`), which
`crackerjack/cli/handlers/provider_selection.py:141` calls — a path
independent of the factory. Deleting the factory removes the *second*
construction path (`factory.py:135-138`), not the capability. Nothing in
`adapters/ai/` is deleted, moved, or modified by this phase.

*(The first draft of this plan claimed the opposite — that `adapters/ai/`
"loses its only construction path" — and left the decision open. The
plan-conformance reviewer traced `get_code_fixer()` and found the independent
path; the claim was wrong and the decision is now resolved.)*

**`refactor/cohesion.py` and `refactor/creosote.py` are decided here, not in
a follow-up.** Neither is in the concurrent plan's Phase 3 scope, neither is
reachable from the factory, and leaving the decision open across two
concurrently-executing plans is how a package ends up half-deleted. **This
plan deletes them.** `cohesion` has a registered regex parser
(`CohesionRegexParser`) that the sync executor never calls — fixed in Phase 3 —
and `creosote` has both `CreosoteRegexParser` and the dedicated text parser,
both moved in Phase 2. The concurrent plan's Phase 3 scope is unchanged.

**`crackerjack/models/qa_results.py`** — `QAResult`, `QAResultStatus`,
`QACheckType`. **`crackerjack/models/qa_config.py`** — `QACheckConfig`,
`QABaseSettings`. **`crackerjack/models/task.py:56`** —
`HookResult.qa_result`.

**`crackerjack/models/issues.py:76` `CrackerjackRunResult` stays.** It is
in-repo unreferenced but its docstring states an external ai-fix-loop driver
depends on the schema and that `schema_version` must be bumped when the shape
changes. It lives in the same file Phase 5 touches; the plan does not modify
its shape.

**`crackerjack/models/__init__.py`** — the dead re-exports at `:27-29` **and
their five `__all__` entries at `:60-64`**. Removing only the imports makes
`from crackerjack.models import *` raise `AttributeError`.

**`crackerjack/core/phase_coordinator.py:1149-1151`** — the discarded
`ParserFactory()`.

**`crackerjack/models/protocols.py`** — `AdapterFactoryProtocol`,
`AdapterProtocol`, and the `QAAdapterProtocol` re-export.

**`crackerjack/server.py` — the MCP health replacement.** `crackerjack/server.py`
is *not* the MCP server: `crackerjack/mcp/server_core.py` never imports
`crackerjack.adapters` for QA. `CrackerjackServer` has exactly one importer in
the repo — the `crackerjack qa-health` command at
`crackerjack/__main__.py:814` — and that command constructs the server and
calls `get_health_snapshot()` **without awaiting `start()`**, so
`_init_qa_adapters()` never runs, `self.adapters` is `[]`, and the health block
reports `total=0, healthy=0`. The command prints "Total adapters: 0 / Healthy
adapters: 0", then "✅ All adapters healthy", and exits 0. The `cleanup()` loop
never executes and the `getattr(a, "healthy", True)` default never sees an
adapter. **The adapter list buys an operator a false green plus a list of
settings echoes.**

The `qa_adapters` block is replaced with a **per-hook readiness table**, not a
count:

```text
"qa_adapters": {
    "total": len(catalog_hooks),
    "ready": <count of hooks whose command resolves>,
    "hooks": {
        "<hook name>": {
            "command_kind": "binary" | "python_module" | "uv_module",
            "resolvable": True,
            "parser": "<registry key>" | None,
        },
        ...
    },
    "enabled_flags": <unchanged>,
},
```

"Resolvable" is computed from the *command's shape*, not from its first
token. Crackerjack's commands come in three forms: a literal binary
(`osv-scanner`, `lychee`, `creosote`), `python -m <module>`
(`crackerjack.tools.*`, `ruff`, `bandit`, `refurb`, `semgrep`), and
`uv run python -m <module>` (`ty`). A first-token `shutil.which` reports every
`python -m` hook as unresolvable, which turns the block into a **false red** —
worse than the false green it replaces. For the `python -m` form,
"resolvable" means the module is importable, which is a crackerjack property
rather than a toolchain one, and the block says which of the two it is
reporting.

**`crackerjack/cli/handlers/health.py:120-161`** — `_check_adapters` imports
`QAAdapterBase` inside a `try`; deleting `_qa_adapter_base.py` makes the
import raise, and the surrounding `except` marks the component **unhealthy**.
A false negative on the operator's dashboard, caused by removing a module
nothing uses. The `_check_adapters` function is replaced with the same
readiness check.

**`pyproject.toml`** — the four `crackerjack.language_adapters` entry points
stay (the language layer survives); the ruff
`[tool.ruff.lint.per-file-ignores]` block for `"crackerjack/adapters/**"`
stays (the path survives).

**`scripts/run_coverage_audit.sh:93`** — `pytest --cov=crackerjack/adapters ...`
stays (the path survives).

**`scripts/create_test_templates.py`** — the eight tuple rows naming deleted
adapter classes are removed, and the generator function
`generate_adapter_test_template` (`:6-11`) is deleted with them: it emits
`from crackerjack.adapters.{adapter_name} import {adapter_class}` into
generated files, and all eight of those import paths are *already* wrong
(`{adapter_name}` is e.g. `ruff_adapter`, and no such module exists).

**`docs/reference/ADAPTER_UUID_REGISTRY.md`** — **regenerated from the source,
not edited.** It is already stale: it lists four UUIDs for adapters that no
longer exist and omits seven that do, and its `pyrefly` and `ty` UUIDs are
swapped relative to the source.

### Integration Contract

- **Triggered from**: the MCP server, the hook executor, the CLI.
- **Returns to / updates**: `crackerjack/models/`,
  `crackerjack/models/protocols.py`, `crackerjack/server.py`,
  `crackerjack/cli/handlers/health.py`, `crackerjack/parsers/json_parsers.py`,
  `crackerjack/cli/clone_cli.py`, `crackerjack/clone/`,
  `crackerjack/config/`, the generated API docs, the coverage script, the
  test-template script, the UUID registry doc.
- **Demonstrable by**: `import crackerjack.adapters.format.ruff` raises
  `ModuleNotFoundError`; `import crackerjack.adapters` still succeeds;
  `crackerjack run -f` still reports 18/18; `crackerjack health` reports the
  adapters component as present; `crackerjack qa-health` reports the
  readiness table; the MCP server still starts and still serves its four
  language tools.
- **Rollback signal**: any import of `crackerjack.adapters` fails at startup,
  or the MCP server's language tools stop resolving.
- **Observability added**: the `qa_adapters` health block reports per-hook
  readiness instead of a vacuous count.

### Resolved decisions

1. **The clone scanner moves to `crackerjack/clone/`, not into
   `crackerjack/parsers/`.** It is a feature, not a QA check: it produces
   clone groups for the refactoring engine, not issues for a hook report.
   Its `PyscnCloneScanError` moves with it.
1. **The `QAResult` triple goes.** `Issue` plus `HookResult.issues_found` is
   enough for the hook path, and the MCP server never read `QAResult`.
1. **The `healthy` count is not reimplemented as a constant.** The MCP health
   block reports whether each hook's command resolves, per hook.
1. **`PyscnAdapter` is not deleted** even though the factory cannot build it.
   The clone CLI calls it directly, and the concurrent plan's Phase 3 does not
   include `sast/`.
1. **The package survives.** Only the QA sub-layer goes.

### Risks

1. **An external consumer imports the deleted modules.** `crackerjack.adapters`
   is not the published public name — `crackerjack/adapters/__init__.py`
   exports the **live** `LanguageAdapter` API — so the public-API claim must be
   restated in terms of the actual removed names
   (`crackerjack.adapters.format.ruff.RuffAdapter`,
   `crackerjack.adapters.sast.bandit.BanditAdapter`, …). The fleet's Python
   surface for crackerjack is tiny (mahavishnu imports only `crackerjack`;
   session-buddy imports `crackerjack` and
   `crackerjack.services.regex_patterns`; akosha, oneiric and mcp-common
   import nothing). Pre-1.0, replace not extend; the CHANGELOG carries the
   removal.
1. **`HookResult.qa_result` may have a downstream reader.** It is typed
   `t.Any | None`, so neither grep-for-`.qa_result` nor the type checker can
   establish its absence. **Blocking check before Phase 5: grep the fleet's
   `HookResult` consumers — session-buddy, akosha, mahavishnu — for
   `qa_result`. If any reads it, the field stays and only its type is
   narrowed.**
1. **`docs/reference/ADAPTER_UUID_REGISTRY.md` is regenerated, not edited** —
   it is already stale and its type-adapter UUIDs are swapped.
1. **Live documentation names `crackerjack.adapters`.** At minimum:
   `docs/api/reference.md`, `docs/CLI_REFERENCE.md`,
   `docs/architecture/MEMORY_ARCHITECTURE.md`,
   `docs/development/SYMBOL_DISPLAY_{CRITICAL_FIX,IMPLEMENTATION}.md`,
   `docs/ERROR_HANDLING_{STANDARD,MIGRATION_GUIDE}.md`,
   `docs/feature-tracking/2026-11-07-pyscn-intel-marker-and-version-resolution.md`,
   `docs/decisions/2026-11-01-ty-adapter-module-name-shadows-ty-distribution.md`,
   and ~20 `CHANGELOG.md` hits.
1. **The release audit cannot verify a directory removal.**
   `crackerjack/checks/release_audit.py:101` matches backticked claims with
   `` `([\w.]+)` `` — a claim containing a `/` is not matched at all, and
   `_is_file_path_symbol` requires a `.py` suffix. The CHANGELOG must list
   **per-module dotted `.py` paths**, not the directory.

### Estimated scope

~14 modules, ~3,500 lines, 1 model file, 1 server file, 2 CLI handlers,
1 parser module, ~48 test files, 2 scripts, 9 doc files.

______________________________________________________________________

## Phase 6 — Follow-ups (not blocking)

1. **`settings/profiles/`** — delete it and `crackerjack/config/profile_loader.py`
   as dead configuration, or wire `ProfileLoader` into a live consumer. Phase 1
   leaves the files untouched; this is the follow-up that resolves them.
1. **`crackerjack/adapters/ai/`** — decide whether it gets its own entry point
   or is deleted. Phase 5 must resolve it either way; this follow-up is for
   the broader question of whether the AI-provider registry belongs under
   `crackerjack/adapters/` at all.
1. **The `services/patterns/` registry** — live and out of scope permanently.
   Once `individual_hook_executor.py` is gone by the concurrent plan, the
   `pyright` output patterns have no reader (the repo no longer runs pyright
   at all), but the registry as a whole backs input validation, path
   security, the coverage ratchet and publish version bumping. Any cleanup
   there is its own plan.

______________________________________________________________________

## Risks

1. **The concurrent plan and this plan both touch `crackerjack/adapters/`.**
   This is a **spatial** hazard, not only a sequencing one: two plans, one
   package, and one of them owns the live half. Mitigation: this plan's
   Phase 5 must not begin until `git log` shows the concurrent plan's Phase 3
   merged. Conversely, the concurrent plan's Phase 3 must not begin until this
   plan's Phase 5 has either completed or been amended to exclude
   `crackerjack/adapters/registry.py`'s `discover_adapters` and the four
   `crackerjack.language_adapters` entry points. **The two plans must not run
   in the same worktree.**
1. **The public API claim is misstated.** `crackerjack.adapters` is not the
   published public name — its `__init__` exports the live `LanguageAdapter`
   API. The claim must be restated in terms of the removed class paths.
1. **`HookResult.qa_result` is typed `t.Any | None`.** Its absence of
   in-repo readers is not establishable by grep or by the type checker. See
   Phase 5's Risk 2 for the blocking fleet-wide check.
1. **`CrackerjackRunResult` has an out-of-repo contract.** Its docstring names
   an external ai-fix-loop driver. It lives in the file Phase 5 touches; its
   `schema_version` must not move.
1. **The profile YAML work is deferred, not merely risky.**
   `ProfileLoader` has no production importer and `checks` is an unvalidated
   `dict[str, Any]`, so nothing in production reads `checks.enabled`. The
   rename would change a file no runtime path consults — which is a reason to
   either delete the file or wire it, not to treat the rename as a risk.
1. **No baseline is pinned for issue counts.** Every "Demonstrable by" is
   structural ("still reports 18/18", "still raises `ModuleNotFoundError`").
   Failure Condition #9 requires a checked-in per-hook fixture.

______________________________________________________________________

## References

- `docs/plans/2026-11-14-remove-dead-module-cluster.md` — the concurrent plan.
  Its Phase 2 deletes the plugin system (the fifth hook-config source) and its
  Phase 3 deletes 23 unreachable QA adapters. **Its Phase 3 risk #3 refers to
  `_tool_has_qa_adapter` at `hook_executor.py:2334+`, which was deleted on
  2026-11-14 in `9e76f4de`** — that risk note is stale. Its Phase 3
  "Demonstrable by" requires that "the MCP server still starts and its
  `language_tools` still resolve the four language adapters", which this
  plan's Phase 5 must not break.
- `crackerjack/parsers/factory.py` — the parser registry that survives.
- `crackerjack/config/hooks.py` — the hook definitions this plan replaces.
- `crackerjack/config/tool_commands.py` — the command builders that survive.
- `crackerjack/adapters/factory.py` — the three-table factory this plan
  retires.
- `crackerjack/adapters/registry.py` — the file that must be **split**, not
  deleted.
- Commits: `9e76f4de` (adapter lookup fixed), `d4c98598` (adapter bounded by
  the hook), `ab0b24dd` (benchmark adapter deleted).

______________________________________________________________________

## Review outcome

A four-lens multi-agent review (fact-checker, design critic, adversarial red
team, plan-conformance) ran against the first draft of this plan. Findings
carried into this revision:

**Critical — corrected.** The first draft's Phase 4 said "delete
`crackerjack/adapters/`" and called it "the QA adapter layer". It holds the
live language-adapter layer, four PEP 621 entry points, the AI-provider
registry, and `_output_paths.py` — which the *surviving* parser registry
imports. Executing it would have broken four registered MCP tools and
`core/language_detector.py`. Phase 5 is now a file list; the package survives;
Failure Condition #6 is rewritten; `registry.py` is split rather than deleted.

**Major — corrected.** (1) The first draft's Phase 3 would have re-run the
hook's own command, which for `ruff-check` carries `--fix` — a second
working-tree mutation inside a reporting path — and for four of six tools is
already structured, making the fallback a no-op. (2) The first draft claimed
the adapter and parser issue shapes were the same; `Issue` has no `code`
field. (3) The first draft deleted `_REPORTING_TOOLS` without noticing it also
carries the status-flip rule. (4) The settings inventory was wrong:
`settings/crackerjack.yaml` has no `hooks:` sub-table. (5) The profile
vocabulary was miscounted — only 1 of 7 names is a hook — and `ProfileLoader`
has no production importer, so the "report typos at load time" claim was
undemonstrable. (6) `pyrefly` was deferred to a non-blocking follow-up even
though deleting the adapter layer without its parser ships a regression; it is
now a Phase 2 prerequisite. (7) `models/__init__.py`'s `__all__` entries,
`adapters/*/__init__.py`, `sast/_base.py`, `cli/handlers/health.py`,
`pyproject.toml` and `scripts/run_coverage_audit.sh` were all unaccounted
for. (8) `services/patterns/` was described as pending a decision when it is
live and permanently out of scope.

**Corrected numbers.** `22 HookDefinition` → **32** (18 fast + 14
comprehensive, plus 3 opt-in-generated). `settings/profiles` "2 of 6 names
are not hooks" → **6 of 7**.

**Second round — corrections carried in.** (1) The first draft's
parser-coverage matrix was wrong: `pyrefly` is **not a live hook** (it is
opt-in and off by default), so the live parser gaps are **`tc-refs`** and
**`no-conflict-markers`**; seven registered parsers have no live hook
(`bandit`, `complexipy`, `complexity`, `gitleaks`, `mypy`, `pytest`,
`ruff`). (2) `bandit` is **not a hook** either — it has a command, a config,
a parser and an adapter but no `HookDefinition` — so only **five** of the six
factory-buildable adapters are reachable through the hook path. (3) The
executor *does* import `QACheckConfig` and `QACheckType`; only `QAResult`
flows as `t.Any`, and `models/protocols.py:694-695` is a **second** external
consumer of the types. (4) `Issue` attributes are read at **six** production
sites, not three. (5) A **fifth registry** —
`crackerjack/models/tool_config.py`'s `TOOL_CONFIGS` — was never inventoried;
it already disagrees with the real argv for `complexipy`. (6) The operator's
`enable_pyrefly` / `enable_ty` YAML flags are **inert** — the YAML is flat,
the code reads `settings.hooks.*`, and `server.py` reads the flat form — so
the two consumers of the same knob disagree. That is a live bug this plan
now names. (7) `ruff-check`'s hook command carries `--fix --unsafe-fixes`
(`ruff_unsafe_fixes` defaults to `True`), so re-running it is a second
*unsafe-fix* mutation. (8) The timeout never lives in the command; it reaches
the subprocess through the executor, and the fallback must pick a path.
(9) `scans_own_target` is load-bearing for `refurb` and was missing from the
first draft's `HookSpec`. (10) `tool_commands.py` has no per-tool builder
functions — one flat dict plus `get_tool_command` post-processing. (11) The
concurrent plan's Phase 3 scope count is stale (20 modules / ~3,885 lines,
not 23 / 4,495).

**Open.** The Phase 5 `crackerjack/adapters/ai/` decision, the
`settings/profiles/` decision, the `TOOL_CONFIGS` disposition, and the
`HookResult.qa_result` fleet-wide grep are named as blocking checks in the
phases that need them.

______________________________________________________________________

## Execution record

_(Filled in as the phases execute, in the house style of the executed sibling
`docs/plans/2026-11-13-remove-dead-ai-fix-module-cluster.md`. Each phase
records the commit SHA, the baseline fixture captured before it, the
issue-count deltas per hook, and any decision taken that the plan left open;
the closing entry names the findings that turned up during execution that the
plan did not anticipate.)_

```
## Execution record (YYYY-MM-DD/YYYY-MM-DD)

Executed in N phases, one commit each. Findings that turned up during
execution that the plan did not anticipate:

1. **<finding>** — <what it changed>. Net result: **<+/- files, +/- lines>** …

Per phase:

| Phase | Commit | Baseline | Issue-count deltas | Decisions taken |
|---|---|---|---|---|
| 1 | <sha> | <fixture path> | <deltas> | <decisions> |
```
