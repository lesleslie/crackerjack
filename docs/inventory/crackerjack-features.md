---
title: Crackerjack Feature Inventory — the Crackerjack surface
description: "The Crackerjack lane of the fleet feature inventory: every feature and tool Crackerjack advertises, with the state of each and the evidence for that state. A feature counts as advertised when it is reachable by an operator or an agent -- an MCP tool on the registered server, a CLI subcommand, or a documented configuration block that claims to do something. Documentation alone is not advertising; a registered tool with no data feed IS advertising, and that mismatch is the defect class this document exists to surface. Every NOT WORKING row carries a command and its output, not an inference."
audience: crackerjack maintainer
created: 2026-11-20
status: active
role: canonical
topic: mcp-design
date: 2026-11-20
last_reviewed: 2026-11-20
superseded_by:
blocks_on: []
---

# Crackerjack Feature Inventory

**Lane:** the Crackerjack surface of the fleet feature inventory.
**Date:** 2026-11-20.
**Owner:** this lane only. The other components' surfaces belong to other
lanes, and the master plan index belongs to the index owner's lane. Nothing
here edits another component.

## Method

Every state in this document is **observed**, not inferred. The evidence
column holds the command that was run and what it answered.

The surface was enumerated from the live server, not from the source tree:

```bash
# The registered tool surface (53 tools on the running server)
python3 - <<'PY'
import json, urllib.request
URL = "http://127.0.0.1:8676/mcp"
... initialize, then tools/list ...
PY
```

```text
LIVE tools/list: 53 tools
```

Of those 53, **45 were called** and their answers recorded. The 8 that were
not called are the mutating ones — `crackerjack_clean`, `crackerjack_execute`,
`crackerjack_format_jinja_templates`, `crackerjack_index_file_semantic`,
`crackerjack_init`, `crackerjack_kotlin_bump_version`,
`crackerjack_remove_file_from_semantic_index`, `crackerjack_swift_bump_version`
— and they are marked *not probed* rather than being given a state they did
not earn.

The CLI surface was enumerated from `crackerjack --help` (18 top-level
subcommands) and each one was run.

## Summary

| | count |
|---|---|
| MCP tools registered on the live server | 53 |
| MCP tools probed | 45 |
| CLI subcommands run | 18 |
| **NOT WORKING** | **13** |
| SHOULD BE CONSOLIDATED | 3 |
| SHOULD BE REMOVED | 4 |
| Works, no plan covers it (undocumented dependency) | 4 |

The headline: **Crackerjack's advertised surface is larger than its working
surface.** Thirteen of the 53 registered tools do not do the thing they say
they do. Two of them are worse than broken — they report success.

## NOT WORKING

Thirteen findings. Each one carries the command and the answer.

### N1 — `crackerjack_get_embeddings` returns a hash, not an embedding

**Advertised via:** MCP tool.
**Evidence:** two different texts, two different vectors, but only **30
distinct values across 384 dimensions**, quantised to 1/255 steps:

```text
text 0: 'hello world'
   len=384  distinct values=30  -> [0.0, 0.031372549, 0.152941176, 0.180392157, 0.243137255, 0.301960784]
   first 12: [0.7255, 0.7255, 0.7255, 0.7255, 0.7255, 0.7255, 0.7255, 0.7255, 0.302, 0.302, 0.302, 0.302]
text 1: 'the mitochondria is the powerhouse of th'
   len=384  distinct values=30  -> [0.0, 0.007843137, 0.023529412, 0.043137255, 0.098039216, 0.156862745]
```

A real `all-MiniLM-L6-v2` encoding has 384 continuously varying values. These
have 30, and they are byte fractions. The source says so outright:

```text
crackerjack/services/ai/embeddings.py:75
    "ONNX session not implemented yet - using fallback embeddings",
crackerjack/services/ai/embeddings.py:99-105
    def _generate_fallback_embedding(self, text: str) -> list[float]:
        text_hash = hashlib.sha256(text.encode()).hexdigest()
        ...
            value = int(hex_pair, 16) / 255.0
```

**Why it matters:** the tool returns `"success": true` and a 384-dimensional
vector, indistinguishable in shape from a real embedding. A caller computes a
cosine similarity over a SHA-256 digest and gets a number with no meaning in
it. This is the fleet's embedding surface, and the fleet settled a canonical
width of 1024 elsewhere — Crackerjack's stub is not that, and is not
measuring that.

**Owning plan:** none in this repository. `grep -rliE "embedding" docs/plans/`
returns only the AI-fix plans and a completed testing-infrastructure plan,
none of which own the embedding service. **Plan-coverage gap.**

### N2 — `crackerjack_analyze` returns a mock and says so only in a field

**Advertised via:** MCP tool.
**Evidence:**

```text
crackerjack_analyze
{"success": true, "command": "analyze_crackerjack", "scope": "all",
 "report_format": "summary", "dry_run": true, "timestamp": ...,
 "analysis": {"scope": "all", "report_format": "summary",
              "status": "mock_success",
              "summary": "Project analysis complete (mock)."}}
```

The payload reports `"success": true`. The mock is visible only in
`analysis.status`, a field a caller is unlikely to check — the outer
`success` is the one that gates.

### N3 — `crackerjack_run_stage` is a permanent stub

**Advertised via:** MCP tool.
**Evidence:**

```text
crackerjack_run_stage
{"error": "Workflow orchestration removed in Phase 2 (legacy runtime removal). Will be reimplemented in Phase 3 (Oneiric integration).", "success": false}
```

The tool's own description says the same thing. It is registered, advertised
in `tools/list`, and cannot run anything.

### N4 — the state manager is not available, and three tools depend on it

**Advertised via:** MCP tools.
**Evidence:**

```text
crackerjack_get_stage_status
{"error": "State manager not available", "success": false}

crackerjack_session_management
{"error": "State manager not available"}

crackerjack_get_next_action
{"recommended_action": "initialize", "reason": "No state manager available"}
```

`get_next_action` is the worst of the three: it returns a *recommendation*
derived from the absence of the state it is supposed to reason about. A caller
gets a confident "run initialize first" and no indication that the tool has
nothing to inspect.

**Owning plan:** none. `grep -rliE "state manager" docs/plans/` returns
nothing. **Plan-coverage gap.**

### N5 — `crackerjack_result_store` dies on a closed event loop

**Advertised via:** MCP tool.
**Evidence:**

```text
crackerjack_result_store
Error calling tool 'crackerjack_result_store': Event loop is closed
```

The async task store cannot be read at all.

### N6 — `crackerjack_validate_claude_md` fails on its own response

**Advertised via:** MCP tool.
**Evidence:**

```text
crackerjack_validate_claude_md
{"error": "CLAUDE.md validation failed: Object of type PosixPath is not JSON serializable", "success": false}
```

The validator's failure is a serialisation bug in the tool's own error path,
not a validation verdict. Whatever the file's real state, the tool cannot
report it.

### N7 and N8 — `crackerjack_get_symbol_info` and `crackerjack_find_usages` are unimplemented

**Advertised via:** MCP tools.
**Evidence:**

```text
crackerjack_get_symbol_info
{"success": false, "error": "PyCharm MCP server not connected. Symbol info requires IDE connection.", "symbol": "main", "hint": "Ensure PyCharm is running with MCP server enabled."}

crackerjack_find_usages
{"success": false, "error": "PyCharm MCP server not connected. Find usages requires IDE connection.", "symbol": "main"}
```

The error blames the IDE. But the tool descriptions say the truth:

> The actual symbol lookup is not implemented yet, so a connected IDE still
> returns a `not_implemented` status rather than symbol data.

> The actual usage search is not implemented yet, so a connected IDE still
> returns a `not_implemented` status rather than usage locations.

So these do not become useful when PyCharm is running. They are stubs with
a misleading error message.

### N9 — `crackerjack_get_ide_diagnostics` reports "no problems" when no IDE was consulted

**Advertised via:** MCP tool. **This is a false pass, and it is the most
dangerous row in this document.**

**Evidence** — two tools, same server, same moment, disagreeing:

```text
crackerjack_get_ide_diagnostics
{"success": true, "issues": [], "count": 0, "file_path": "crackerjack/tools/mdformat_wrapper.py"}

pycharm_health
{"success": true, "mcp_available": false, "circuit_breaker_open": false, "failure_count": 0, "cache_size": 3, "status": "healthy"}
```

The IDE is not connected (`mcp_available: false`). The diagnostics tool
nonetheless reports success and zero issues. The mechanism is in
`crackerjack/services/pycharm_mcp_integration.py:123-145`: the call goes
through `_execute_with_circuit_breaker`, which swallows the connection
failure and returns an empty list, and `crackerjack/mcp/tools/pycharm_tools.py:134`
renders that empty list as `{"success": true, "count": 0}`.

A caller checking diagnostics concludes the file is clean. Nothing was
checked. Note also that `pycharm_health` reports `"status": "healthy"` while
`mcp_available` is `false` — the health field contradicts the availability
field in the same payload.

### N10 — the semantic index is empty, and two tools depend on it

**Advertised via:** MCP tools.
**Evidence:**

```text
crackerjack_get_semantic_stats
{"success": true, "total_files": 0, "total_chunks": 0, "index_size_mb": 0.0, "average_chunks_per_file": 0.0, "embedding_model": "sentence-transformers/all-MiniLM-L6-v2", "embedding_dimension": 384, "last_updated": "2026-11-20T14:54:52.100149"}

crackerjack_search_semantic
{"success": true, "query": "quality gate hook", "results_count": 0, "max_results": 10, "min_similarity": 0.7, "results": [], "status": "degraded", "hint": "Semantic index is empty. Run the reindex procedure documented in crackerjack/docs/operations/reindex.md"}
```

`get_semantic_stats` is honest — it correctly reports an empty index.
`search_semantic` is honest too: it returns `status: "degraded"` and points at
a reindex procedure that exists (`docs/operations/reindex.md` is present).

The defect is the **feed**, not the tools: the advertised capability —
"search the codebase by meaning" — returns nothing because the index has
never been populated. An agent that reads only `success: true` and
`results: []` sees an empty codebase, not an unbuilt index.

**Owning plan:** none. `grep -rliE "semantic index|reindex" docs/plans/`
returns only AI-fix plans that use the word incidentally. **Plan-coverage
gap.**

### N11 — four language tools refuse every call in the default environment

**Advertised via:** MCP tools.
**Evidence:**

```text
crackerjack_detect_languages      -> Error: MAHAVISHNU_PROJECT_ROOTS unset. Configure with colon-separated absolute paths to allow.
crackerjack_swift_list_hooks      -> Error: MAHAVISHNU_PROJECT_ROOTS unset. Configure with colon-separated absolute paths to allow.
crackerjack_kotlin_list_hooks     -> Error: MAHAVISHNU_PROJECT_ROOTS unset. Configure with colon-separated absolute paths to allow.
crackerjack_check_web_lint        -> Error: MAHAVISHNU_PROJECT_ROOTS unset. Configure with colon-separated absolute paths to allow.
```

All four fail identically. The message names the fix, so this is a
configuration gap rather than a code defect — but the tools are registered
and advertised, and in the environment as it ships they cannot be called at
all.

### N12 — the monitoring tools report that the MCP server is not running

**Advertised via:** MCP tools.
**Evidence:**

```text
crackerjack_get_filtered_status
{"timestamp": ..., "services": {"mcp_server": {"running": [], "processes": []}}, "_security": {...}}

crackerjack_get_comprehensive_status
{"services": {"mcp_server": {"running": [], "processes": []}}, "jobs": {"active_count": 0, ...}, ...}
```

Both report that no MCP server is running. The MCP server is running: it is
serving these very calls, and `get_liveness` reports
`{"status": "ok", "uptime_seconds": 363471.21}`.

### N13 — the CLI `status` command reports a false negative

**Advertised via:** CLI subcommand.
**Evidence:**

```text
$ crackerjack status
Server not running
```

while, at the same moment:

```text
$ curl -s http://127.0.0.1:8676/health
{"service": "crackerjack", "version": "0.95.0", "status": "healthy", ...}
```

The cause is in `crackerjack/cli/mcp_cli.py:276,281,403`: the check is for a
PID file, and this server was started by the shared `mcp_common` launcher,
which does not write one. `crackerjack status` reports on a launcher it does
not own.

## Advertised but absent

Two things the documentation advertises that do not exist.

### A1 — `crackerjack skills audit`

The top-level CLI help says:

> skills — Skill-distillation operational tools. Refresh runs
> `distill_skills_now` and is intended for cron use; **`audit` skills** is
> for interactive/CI use.

There is no `audit` subcommand:

```text
$ crackerjack skills audit
╭─ Error ─────────────────────────────────────────╮
│ No such command 'audit'.                        │
╰─────────────────────────────────────────────────╯
```

`crackerjack skills --help` lists exactly one subcommand: `refresh`.

### A2 — `crackerjack audit orphans`

The command's own help says:

> audit — Orphan-detection audit. Wraps the project's `scripts/audit_orphans.py`.
> Reports recently-added Python symbols with zero callers ('built but not wired').

Crackerjack has no such script:

```text
$ crackerjack audit orphans
audit_orphans.py not found under ~/Projects/crackerjack
Expected: /Users/les/Projects/crackerjack/scripts/audit_orphans.py
See: https://github.com/lesleslie/mahavishnu for the canonical script.
```

The script exists in mahavishnu (`mahavishnu/scripts/audit_orphans.py`) and
not here. The command looks only in the local repository, so in Crackerjack it
can never succeed.

## The MCP tool surface

53 tools. *State* is what the tool answered when called.

| tool | advertised via | state | evidence | owning plan | disposition |
|---|---|---|---|---|---|
| `crackerjack_get_embeddings` | MCP tool | **NOT WORKING** | 30 distinct values in 384 dims; `embeddings.py:75` "ONNX session not implemented yet" | *none* | consolidate into the fleet embedding service |
| `crackerjack_analyze` | MCP tool | **NOT WORKING** | `"status": "mock_success"`, `"summary": "… (mock)."` | *none* | consolidate into `crackerjack run` |
| `crackerjack_run_stage` | MCP tool | **NOT WORKING** | `"error": "Workflow orchestration removed in Phase 2…"` | *none* (Oneiric migration plan is the nearest) | remove until Phase 3 |
| `crackerjack_get_stage_status` | MCP tool | **NOT WORKING** | `{"error": "State manager not available"}` | *none* | remove or wire the state manager |
| `crackerjack_session_management` | MCP tool | **NOT WORKING** | `{"error": "State manager not available"}` | *none* | remove or wire the state manager |
| `crackerjack_get_next_action` | MCP tool | **NOT WORKING** | `"reason": "No state manager available"` | *none* | remove or wire the state manager |
| `crackerjack_result_store` | MCP tool | **NOT WORKING** | `Error: Event loop is closed` | *none* | fix the store |
| `crackerjack_validate_claude_md` | MCP tool | **NOT WORKING** | `PosixPath is not JSON serializable` | *none* | fix the error path |
| `crackerjack_get_symbol_info` | MCP tool | **NOT WORKING** | "not implemented yet" per its own description | `specs/2026-09-07-crackerjack-multi-language-design.md` | remove |
| `crackerjack_find_usages` | MCP tool | **NOT WORKING** | "not implemented yet" per its own description | `specs/2026-09-07-crackerjack-multi-language-design.md` | remove |
| `crackerjack_get_ide_diagnostics` | MCP tool | **NOT WORKING (false pass)** | `{"success": true, "count": 0}` while `pycharm_health` says `mcp_available: false` | `specs/2026-09-07-crackerjack-multi-language-design.md` | fix: report the unreachable IDE |
| `crackerjack_search_semantic` | MCP tool | **NOT WORKING (empty feed)** | `"results_count": 0, "status": "degraded"` | *none* | populate the index |
| `crackerjack_detect_languages` | MCP tool | **NOT WORKING** | `MAHAVISHNU_PROJECT_ROOTS unset` | *none* | document the requirement, or default it |
| `crackerjack_swift_list_hooks` | MCP tool | **NOT WORKING** | `MAHAVISHNU_PROJECT_ROOTS unset` | *none* | as above |
| `crackerjack_kotlin_list_hooks` | MCP tool | **NOT WORKING** | `MAHAVISHNU_PROJECT_ROOTS unset` | *none* | as above |
| `crackerjack_check_web_lint` | MCP tool | **NOT WORKING** | `MAHAVISHNU_PROJECT_ROOTS unset` | *none* | as above |
| `crackerjack_get_filtered_status` | MCP tool | **NOT WORKING (false negative)** | `mcp_server: {"running": []}` while the server serves the call | `plans/2026-11-14-remove-dead-module-cluster.md` | fix: read the live process |
| `crackerjack_get_comprehensive_status` | MCP tool | **NOT WORKING (false negative)** | same `mcp_server: {"running": []}` | `plans/2026-11-14-remove-dead-module-cluster.md` | fix: read the live process |
| `crackerjack_analyze_errors` | MCP tool | WORKS (empty feed) | `"patterns_found": 0` — the cache holds no patterns | *none* | undocumented dependency |
| `crackerjack_get_semantic_stats` | MCP tool | WORKS | reports `total_files: 0` truthfully | *none* | undocumented dependency |
| `crackerjack_calculate_similarity_semantic` | MCP tool | WORKS (over N1) | `similarity_score: 1.0` for identical inputs | *none* | — |
| `crackerjack_search_code` | MCP tool | WORKS | returns matches from the local fallback | *none* | undocumented dependency |
| `crackerjack_config` | MCP tool | WORKS | returns the effective configuration | `plans/2026-10-10-crackerjack-oneiric-loader-migration.md` | — |
| `crackerjack_doc_frontmatter_validate` | MCP tool | WORKS | `{"success": true, "files_scanned": 64, "errors": []}` | *none* | undocumented dependency |
| `crackerjack_validate_architecture` | MCP tool | WORKS (no substance) | every check returns `"requires_analysis"` | *none* | undocumented dependency |
| `crackerjack_get_server_stats` | MCP tool | WORKS | returns server stats; `rate_limiting.enabled: false` | *none* | undocumented dependency |
| `crackerjack_list_agents` | MCP tool | WORKS | returns the published agents | *none* | undocumented dependency |
| `crackerjack_get_agent` | MCP tool | WORKS | returns signed metadata and body | *none* | undocumented dependency |
| `crackerjack_list_skills` | MCP tool | WORKS | returns the published skills | *none* | undocumented dependency |
| `crackerjack_get_skill` | MCP tool | WORKS | returns signed metadata and body | *none* | undocumented dependency |
| `crackerjack_suggest_agents` | MCP tool | WORKS | returns `TestCreationAgent` with a reason | *none* | undocumented dependency |
| `crackerjack_suggest_patterns` | MCP tool | WORKS | returns matching pattern families | *none* | undocumented dependency |
| `crackerjack_plan_development` | MCP tool | WORKS | returns agents and a strategy | *none* | undocumented dependency |
| `crackerjack_list_slash_commands` | MCP tool | WORKS | lists the three slash commands | *none* | undocumented dependency |
| `crackerjack_get_job_progress` | MCP tool | WORKS | `{"error": "Job … not found"}` for a bogus id | *none* | undocumented dependency |
| `crackerjack_validate_claude_md` | MCP tool | **NOT WORKING** | see N6 | *none* | fix the error path |
| `get_health` | MCP tool | WORKS | `{"status": "healthy", "degraded_feeds": []}` | *none* | undocumented dependency |
| `get_liveness` | MCP tool | WORKS | `{"status": "ok", "uptime_seconds": 363471.21}` | *none* | undocumented dependency |
| `get_readiness` | MCP tool | WORKS | `{"ready": true, "failed_required": []}` | *none* | undocumented dependency |
| `health_check_all` | MCP tool | WORKS | session-buddy and mahavishnu both healthy | *none* | undocumented dependency |
| `health_check_service` | MCP tool | WORKS | mahavishnu healthy, 90 ms | *none* | undocumented dependency |
| `wait_for_dependency` | MCP tool | WORKS | `{"success": true, "elapsed_seconds": 0.155}` | *none* | undocumented dependency |
| `wait_for_all_dependencies` | MCP tool | WORKS | `{"success": true, "total_wait_seconds": 0.854}` | *none* | undocumented dependency |
| `query_local_traces` | MCP tool | WORKS | returns the fleet trace store | *none* | undocumented dependency |
| `discover_tools` | MCP tool | WORKS | returns the registry with descriptions | *none* | undocumented dependency |
| `crackerjack_clean` | MCP tool | not probed | mutating | — | — |
| `crackerjack_execute` | MCP tool | not probed | mutating; the implementation path is real (`execute_crackerjack_workflow`) | — | — |
| `crackerjack_format_jinja_templates` | MCP tool | not probed | mutating | — | — |
| `crackerjack_index_file_semantic` | MCP tool | not probed | mutating | — | — |
| `crackerjack_init` | MCP tool | not probed | mutating | — | — |
| `crackerjack_kotlin_bump_version` | MCP tool | not probed | mutating | — | — |
| `crackerjack_remove_file_from_semantic_index` | MCP tool | not probed | mutating | — | — |
| `crackerjack_swift_bump_version` | MCP tool | not probed | mutating | — | — |

## The CLI surface

18 top-level subcommands.

| command | advertised via | state | evidence | owning plan | disposition |
|---|---|---|---|---|---|
| `crackerjack status` | CLI | **NOT WORKING (false negative)** | "Server not running" while the server answers on :8676 | *none* | fix the PID-file check |
| `crackerjack audit orphans` | CLI | **NOT WORKING** | `audit_orphans.py not found under ~/Projects/crackerjack` | *none* | vendor the script or resolve it across the ecosystem |
| `crackerjack skills audit` | CLI | **NOT WORKING (advertised, absent)** | "No such command 'audit'" | *none* | add it or stop advertising it |
| `crackerjack version` | CLI | WORKS | `crackerjack: 0.96.0` | — | — |
| `crackerjack doctor` | CLI | WORKS | `adapters: healthy - total=1 healthy=1 degraded=0 unhealthy=0` | — | — |
| `crackerjack health` | CLI | WORKS | `{'status': 'healthy', 'exit_code': 0, 'component': 'crackerjack', 'version': '0.96.0'}` | — | — |
| `crackerjack run` | CLI | WORKS | the real quality gate; `crackerjack run -v -f` is the merge gate | — | — |
| `crackerjack run-tests` | CLI | WORKS | — | `plans/2026-11-06-test-selection-and-run-state.md` | — |
| `crackerjack run-state` | CLI | WORKS | `show` / `diff` subcommands | `plans/2026-11-06-test-selection-and-run-state.md` | — |
| `crackerjack coverage-ratchet` | CLI | WORKS | `status` → "Coverage ratchet not initialized" (a truthful verdict) | `plans/2026-11-07-pyscn-intel-marker-and-json-schema.md` | — |
| `crackerjack hypothesis-lock` | CLI | WORKS | subcommand group renders | `specs/2026-07-08-fix-sandbox-integration-design.md` | — |
| `crackerjack skills refresh` | CLI | WORKS | the one real subcommand | `plans/2026-10-28-oneiric-action-kit-adoption.md` | — |
| `crackerjack mcp` | CLI | WORKS | start/stop/status for the MCP server | — | — |
| `crackerjack docs` | CLI | WORKS | documentation management | — | — |
| `crackerjack gitignore` | CLI | WORKS | — | `plans/2026-09-07-bodai-shared-gitignore-snippet.md` | — |
| `crackerjack shell` | CLI | WORKS | — | — | — |
| `crackerjack start` / `stop` / `restart` | CLI | WORKS | server lifecycle | — | — |
| `crackerjack audit` | CLI | WORKS (the group) | renders; its `orphans` subcommand does not | *none* | see A2 |

## SHOULD BE CONSOLIDATED

Three things that are the same capability wearing two hats.

1. **`crackerjack_analyze` (MCP) and `crackerjack run` (CLI)** — the MCP tool
   returns a mock; the CLI does the real work. One of them should go.
2. **`crackerjack_get_embeddings` (MCP) and the fleet embedding service** —
   Crackerjack keeps its own SHA-256 stub while the fleet settles a
   canonical width and provider chain elsewhere. The stub should be replaced
   by the fleet service, not maintained alongside it.
3. **`crackerjack_search_code` and `crackerjack_search_semantic`** — both
   advertised as "search the codebase", one by regex and one by meaning. The
   semantic one has an empty index, so today there is exactly one working
   search. Either populate the index or say plainly that there is one.

## SHOULD BE REMOVED

Four things that advertise a capability they do not have, and that no plan
will deliver.

1. **`crackerjack_get_symbol_info`** — "the actual symbol lookup is not
   implemented yet". Registering it invites calls that can only fail.
2. **`crackerjack_find_usages`** — "the actual usage search is not
   implemented yet". Same.
3. **`crackerjack_run_stage`** — a stub that says the runtime was removed in
   Phase 2 and will return in Phase 3. It has been in that state across
   every profile since.
4. **`crackerjack skills audit`** — documented in the CLI help, absent from
   the CLI.

## Works, and no plan covers it

Four capabilities that work, that an agent or an operator will depend on, and
that no plan in the index owns. These are the class the inventory calls an
*undocumented dependency*: they will break the day the code they sit on is
refactored, because nothing is tracking them.

- **`crackerjack_doc_frontmatter_validate`** — the frontmatter schema check.
  Crackerjack's own `CLAUDE.md` and the fleet's document contract depend on
  it. No plan owns it.
- **`crackerjack_get_semantic_stats`** — the only honest reporter of the
  semantic index's state. No plan owns the index.
- **`crackerjack_search_code`** — the only working code search today. No plan
  owns the local fallback.
- **`crackerjack_analyze_errors`** — the error-pattern surface. No plan owns
  the error cache.

## Cross-reference summary

Les asked for three classes of finding. This lane's tally:

| class | count | what it means here |
|---|---|---|
| **plan-execution finding** | 4 | advertised, broken, and a plan exists that should have prevented it — the PyCharm symbol/usage tools under `specs/2026-09-07-crackerjack-multi-language-design.md`, and the two monitoring tools under `plans/2026-11-14-remove-dead-module-cluster.md` |
| **plan-coverage gap** | 9 | advertised, broken, and **no plan covers it** — the embedding stub, the state-manager trio, the empty semantic index, the four `MAHAVISHNU_PROJECT_ROOTS` tools, and the result store. This is the more serious class. |
| **undocumented dependency** | 4 | works, and nothing tracks it — see the section above |

The plan-coverage gaps outnumber the plan-execution findings by more than
two to one. The pattern is consistent: the things with plans are the things
that were being worked on; the things nobody planned are the ones that
quietly stopped working.

## Related

- The fleet inventory's scope and lane split: Bodai memory `m#10119`.
- The master plan index is a separate lane and is not regenerated here.
- `docs/plans/2026-11-14-consolidate-tool-taxonomies.md` — "Consolidate the
  Tool Taxonomies in Crackerjack" — is the nearest existing plan to several
  of the consolidation findings above.
- `docs/plans/2026-11-13-remove-dead-ai-fix-module-cluster.md` and
  `docs/plans/2026-11-14-remove-dead-module-cluster.md` — the two plans that
  should have caught the dead tool surface.
