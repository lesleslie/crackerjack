---
title: Crackerjack MCP Tools Specification
generated: 2026-07-29
status: draft
source: docs/architecture/MEMORY_ARCHITECTURE.md (sections 2 and 3)
---

# Crackerjack MCP Tools Specification

This document is the **authoritative tool surface reference** for the Crackerjack MCP server.
It is derived from [`docs/architecture/MEMORY_ARCHITECTURE.md`](architecture/MEMORY_ARCHITECTURE.md)
(Sections 2 and 3) and is the contract enforced by
[`tests/unit/mcp/test_mcp_tool_drift.py`](../tests/unit/mcp/test_mcp_tool_drift.py).

For **integration contracts, drift history, and known gaps** (e.g. the
`discover_tools` meta-tool absence, `crackerjack_run` not being a single tool,
`analyze_crackerjack` being mocked, workspace tools being stubbed), see
MEMORY_ARCHITECTURE.md Section 5.

## Registration model

Crackerjack does **not** use a profile gate (unlike Mahavishnu, Session-Buddy, Akosha, Dhara).
Every register function listed below is called unconditionally from
`crackerjack/mcp/server_core.py::create_mcp_server()`.

A `register_X_tools` function is considered "in the surface" iff its name
appears in the server_core call block. Intentional deferrals are listed in
`tests/unit/mcp/test_mcp_tool_drift.py::INTENTIONAL_DEFERRED_REGISTERS`.

## 1. Always-on core tools

The 12 always-on tools form the operational core. They are imported at
`crackerjack/mcp/server_core.py:75-90` and called at lines 228-265 (plus a
separate entry-point call at line 497 for skill tools).

| Tool | Group | What it does | Writes to |
|------|-------|--------------|-----------|
| `execute_crackerjack(args, kwargs)` | `execution_tools` | Full `crackerjack run` lifecycle | `workflow_checkpoints.sqlite`, `fix_attempts`, `strategy_effectiveness`, `adapter_attempts`, `error_patterns`, `ai-fix-errors-<ts>.json`, `progress_dir/job-<id>.json` |
| `run_crackerjack_stage(args, kwargs)` | `core_tools` | One stage only (`fast | comprehensive | tests | cleaning | init`) | Same as above (single stage) |
| `init_crackerjack(args, kwargs)` | `execution_tools` | First-time setup: writes `pyproject.toml`, `CLAUDE.md`, `example.mcp.json`, `settings/local.yaml` | Project root files |
| `smart_error_analysis(use_cache=True)` | `execution_tools` | AI-prioritized fix suggestions | `ErrorCache` (in-process frequency counter, `auto_fixable` flag) |
| `analyze_errors(output, include_suggestions=True)` | `core_tools` | Post-stage error pattern extraction | `error_patterns` (frequency), `fix_results` (`auto_fixable`) — *NOTE: the `register_analyze_errors_tool` MCP entry was removed; this row documents the actual path through `execution_tools.analyze_errors_with_caching`* |
| `clean_crackerjack(args, kwargs)` | `utility_tools` | Cleanup logs, coverage files, progress dir | (deletes) `crackerjack-*.log`, `.coverage.*`, `progress_dir/*.json` |
| `config_crackerjack(args, kwargs)` | `utility_tools` | Settings introspection | None — read-only dump of `CrackerjackSettings.model_dump()` |
| `analyze_crackerjack(args, kwargs)` | `utility_tools` | Self-analysis | **MOCK**: returns `{"status": "mock_success"}` (see Contract 5.6) |
| `validate_claude_md(args, kwargs)` | `utility_tools` | `CLAUDE.md` validator; with `update=true`, may rewrite `CLAUDE.md` | `CLAUDE.md` (conditional) |
| `crackerjack_doc_frontmatter_validate(pkg_path, strict, ...)` | `doc_tools` | Frontmatter validator; optional `store` arg persists to path | `store` (if `store="path"`) |
| `publish_to_eventbridge(topic, payload, async_callback=False)` | `eventbridge_tools` | Bodai EventBridge publisher | Oneiric EventBridge (only if `enabled=true`; default `false`) |
| `get_job_progress(job_id)` / `session_management(action, checkpoint_name)` | `progress_tools` | Job progress + session state | `progress_dir/job-<id>.json`, `current_session.json`, `<checkpoint>.json` |

## 2. Skill / coverage tools

| Tool | Group | Side effects |
|------|-------|--------------|
| `list_skills(skill_type="all")` | `skill_tools` | None (read from `_skill_registries`) |
| `get_skill_info(skill_id, skill_type="agent")` | `skill_tools` | None |
| `search_skills(query, search_in="all")` | `skill_tools` | None |
| `get_skills_for_issue(issue_type)` | `skill_tools` | None |
| `get_skill_statistics()` | `skill_tools` | None — aggregate counts |
| `execute_skill(skill_id, issue_type, issue_data, timeout=None)` | `skill_tools` | Delegates to skill `execute` (may write `fix_attempts`) |
| `find_best_skill(issue_type)` | `skill_tools` | None — returns highest-confidence match |
| `skill_coverage_report(...)` | `skills/coverage.py` | Calls `mcp__session-buddy__distilled_skill_health` — see Contract 5.4 |

Skill tools are initialized via `initialize_skills` at server startup,
which calls `register_all_skills` → `register_agent_skills`. The registries
(`AgentSkillRegistry`, `MCPSkillRegistry`, `HybridSkillRegistry`) live
in-process; no persistence across restarts.

## 3. Semantic / git-semantic tools

| Tool | Group | Side effects |
|------|-------|--------------|
| `index_file_semantic(file_path, config_json="")` | `semantic_tools` | `crackerjack/.crackerjack/semantic_index.db` (embeddings + file_tracking rows) |
| `remove_file_from_semantic_index(file_path, config_json="")` | `semantic_tools` | Deletes rows from same DB |
| `search_semantic(query, max_results, min_similarity, file_types, config_json)` | `semantic_tools` | None |
| `get_semantic_stats(config_json="")` | `semantic_tools` | None |
| `get_embeddings(texts, config_json="")` | `semantic_tools` | None |
| `calculate_similarity_semantic(embedding1, embedding2, config_json)` | `semantic_tools` | None |
| `index_git_history(days_back, repository_path="")` | `git_semantic_tools` | embeddings + file_tracking (one row per git event) |
| `search_git_history(query, limit, days_back, repository_path="")` | `git_semantic_tools` | None |
| `find_workflow_patterns(pattern_description, days_back, min_frequency, repository_path="")` | `git_semantic_tools` | None |
| `recommend_git_practices(focus_area, days_back, repository_path="")` | `git_semantic_tools` | None |

## 4. Self-improvement / monitoring tools

| Tool | Group | Side effects |
|------|-------|--------------|
| `agent_performance_analysis()` | `intelligence_tool_registry` | None — read-only rollup |
| `execute_smart_task(...)` | `intelligence_tool_registry` | Writes `fix_attempts` (via `_record_fix_attempt`) |
| `get_comprehensive_status()` | `monitoring_tools` | None |
| `get_filtered_status(components="jobs")` | `monitoring_tools` | None |
| `get_server_stats()` | `monitoring_tools` | None |
| `get_stage_status()` | `monitoring_tools` | None |
| `get_next_action()` | `monitoring_tools` | None |
| `query_local_traces(task_class, time_range_minutes, system_id, limit)` | `otel_tools` | None — proxies to Akosha MCP over HTTP |
| `get_cross_project_git_dashboard(...)` | `mahavishnu_tools` | None — calls Mahavishnu aggregator |
| `get_repository_health(...)` | `mahavishnu_tools` | None |
| `get_velocity_comparison(...)` | `mahavishnu_tools` | None |
| `get_cross_project_patterns(...)` | `mahavishnu_tools` | None |

## 5. Code search / IDE integration

| Tool | Group | Notes |
|------|-------|-------|
| `search_code(pattern, file_pattern=None)` | `pycharm_tools` | Returns `"MCP server not connected"` if PyCharm MCP down |
| `get_ide_diagnostics(file_path, errors_only=False)` | `pycharm_tools` | Same |
| `get_symbol_info(symbol_name, include_usages=False)` | `pycharm_tools` | **STUB**: returns `status: not_implemented` (Contract 5.9) |
| `find_usages(symbol_name, file_path=None, limit=50)` | `pycharm_tools` | **STUB** (Contract 5.9) |
| `pycharm_health()` | `pycharm_tools` | Returns `status: healthy | degraded` |

## 6. Workspace tools (intentionally stubbed)

Per Contract 5.7, the workspace manager backend was removed in Phase 2;
the four tools below are stubbed pending Phase 3 (Oneiric integration).
**Do not call `register_workspace_tools` from `server_core.py`** — the
deferral is enforced by `INTENTIONAL_DEFERRED_REGISTERS` in
`tests/unit/mcp/test_mcp_tool_drift.py`.

| Tool | Group | Notes |
|------|-------|-------|
| `create_workspace(...)` | `workspace_tools` | `_get_manager` raises `NotImplementedError` |
| `list_workspaces(...)` | `workspace_tools` | Same |
| `get_workspace_info(...)` | `workspace_tools` | Same |
| `remove_workspace(...)` | `workspace_tools` | Same |

## 7. Tool groups by access pattern

| Group | Latency profile | Called by |
|-------|-----------------|-----------|
| **Hot** (`execute_crackerjack`, `run_crackerjack_stage`) | Every Mahavishnu worker dispatch | `dispatch_to_pool` |
| **Monitoring** (`get_comprehensive_status`, `get_filtered_status`, `get_server_stats`) | Operator dashboards | `mcp__mahavishnu__ecosystem_status`, manual dashboards |
| **Code intelligence** (`search_code`, `search_semantic`, `search_git_history`, `find_workflow_patterns`) | IDE + semantic | Crackerjack internal + cross-component |
| **Skill / self-improvement** (`list_skills`, `find_best_skill`, `skill_coverage_report`, `agent_performance_analysis`) | Mahavishnu self-improvement loop | `mcp__crackerjack__get_skill_statistics`, `mcp__crackerjack__agent_performance_analysis` |
| **Admin / utility** (`analyze_crackerjack`, `clean_crackerjack`, `config_crackerjack`, `validate_claude_md`) | Operator one-offs | Manual invocation |

## 8. Tool groups by persistence side-effect

| Group | Reads | Writes | Notes |
|-------|-------|--------|-------|
| Hot execution | `CrackerjackSettings`, `LifecycleManager`, `GitMetricsCollector` | `workflow_checkpoints.sqlite`, `fix_attempts`, `error_patterns`, `progress_dir/job-<id>.json` | Side-effect heavy |
| Self-improvement | `learning_system`, `orchestrator` | `fix_attempts` | Fire-and-forget improvement generation (Contract 5.8) |
| Semantic search | `crackerjack/.crackerjack/semantic_index.db` | Same DB (embeddings + file_tracking) | Indexed once, queried many |
| Git semantic | `git log` over window | embeddings DB (one row per event) | Build vs query split |
| Skill discovery | `_skill_registries` (in-process) | Same (init-time) | No cross-restart persistence |
| Monitoring | `progress_dir/*.json`, `state_manager` | None | Read-only |

## 9. Tools that proxy to other components

| Tool | Proxies to | Protocol |
|------|------------|----------|
| `query_local_traces` | `mcp__akosha__query_local_traces` | HTTP (Mahavishnu MCP cross-server) |
| `skill_coverage_report` | `mcp__session-buddy__distilled_skill_health` | HTTP (see Contract 5.4) |
| `get_cross_project_*` / `get_repository_health` | Mahavishnu aggregator | HTTP |
| `search_code` / `get_ide_diagnostics` | PyCharm MCP | HTTP (returns "not connected" on failure) |
| `publish_to_eventbridge` | Oneiric EventBridge | In-process when `enabled=true`; no-op otherwise |

## 10. Registration map (function → tool group)

This table is the **single source of truth** for which `register_X_tools`
function registers which tool group. It is checked mechanically by
`test_docs_match_registered_tools`.

| Register function | Tool group | Module |
|-------------------|------------|--------|
| `register_core_tools` | `core_tools` (`run_crackerjack_stage`, `analyze_errors`) | `crackerjack/mcp/tools/core_tools.py` |
| `register_doc_tools` | `doc_tools` (`crackerjack_doc_frontmatter_validate`) | `crackerjack/mcp/tools/doc_tools.py` |
| `register_eventbridge_tools` | `eventbridge_tools` (`publish_to_eventbridge`) | `crackerjack/mcp/tools/eventbridge_tools.py` |
| `register_execution_tools` | `execution_tools` (`execute_crackerjack`, `init_crackerjack`, `smart_error_analysis`) | `crackerjack/mcp/tools/execution_tools.py` |
| `register_git_semantic_tools` | `git_semantic_tools` (`index_git_history`, `search_git_history`, `find_workflow_patterns`, `recommend_git_practices`) | `crackerjack/mcp/tools/git_semantic_tools.py` |
| `register_health_tools` | health tools (`get_liveness`, `get_readiness`, etc.) | `mcp_common.health.register_health_tools` |
| `register_intelligence_tools` | `intelligence_tool_registry` (`execute_smart_task`, `agent_performance_analysis`, etc.) | `crackerjack/mcp/tools/intelligence_tools.py` |
| `register_monitoring_tools` | `monitoring_tools` (`get_comprehensive_status`, `get_filtered_status`, `get_server_stats`, `get_stage_status`, `get_next_action`) | `crackerjack/mcp/tools/monitoring_tools.py` |
| `register_otel_tools` | `otel_tools` (`query_local_traces`) | `crackerjack/mcp/tools/otel_tools.py` |
| `register_proactive_tools` | proactive tools (auto-suggestion cluster) | `crackerjack/mcp/tools/proactive_tools.py` |
| `register_progress_tools` | `progress_tools` (`get_job_progress`, `session_management`) | `crackerjack/mcp/tools/progress_tools.py` |
| `register_pycharm_tools` | `pycharm_tools` (`search_code`, `get_ide_diagnostics`, `pycharm_health`, stubs) | `crackerjack/mcp/tools/pycharm_tools.py` |
| `register_semantic_tools` | `semantic_tools` (`index_file_semantic`, `remove_file_from_semantic_index`, `search_semantic`, `get_semantic_stats`, `get_embeddings`, `calculate_similarity_semantic`) | `crackerjack/mcp/tools/semantic_tools.py` |
| `register_skill_tools` | `skill_tools` (`list_skills`, `get_skill_info`, `search_skills`, `get_skills_for_issue`, `get_skill_statistics`, `execute_skill`, `find_best_skill`) | `crackerjack/mcp/tools/skill_tools.py` |
| `register_utility_tools` | `utility_tools` (`clean_crackerjack`, `config_crackerjack`, `analyze_crackerjack`, `validate_claude_md`, `list_slash_commands`) | `crackerjack/mcp/tools/utility_tools.py` |
| `register_workspace_tools` | `workspace_tools` (stubbed — Phase 3 deferred, NOT called from `server_core.py`) | `crackerjack/mcp/tools/workspace_tools.py` |
| `register_mahavishnu_tools` | `mahavishnu_tools` (`get_cross_project_git_dashboard`, `get_repository_health`, `get_velocity_comparison`, `get_cross_project_patterns`) | `crackerjack/mcp/tools/mahavishnu_tools.py` |
| `register_discover_tools` | `discover_tools` (`discover_tools` meta-tool — surfaces the full registry + deferred set; resolves Contract 5.5) | `crackerjack/mcp/tools/discover_tools.py` |

## 11. Cross-references

- **Integration contracts** (mocked tools, stubs, drift vectors): `MEMORY_ARCHITECTURE.md` Section 5
- **Storage layer details**: `MEMORY_ARCHITECTURE.md` Section 1
- **Drift regression tests**: `tests/unit/mcp/test_mcp_tool_drift.py`
- **Tool alias inventory** (which slash commands consume which tools): `bodai/docs/memory/TOOL_ALIAS_INVENTORY.md`
- **Sibling specs**: `akosha/docs/architecture/MEMORY_ARCHITECTURE.md`, `mahavishnu/docs/architecture/MEMORY_ARCHITECTURE.md`, `session-buddy/docs/architecture/MEMORY_ARCHITECTURE.md`, `dhara/docs/architecture/MEMORY_ARCHITECTURE.md`

---

**Status legend**

- ✅ **Always-on** — registered unconditionally in `server_core.py`
- ⏸ **Stubbed** — function defined but raises `NotImplementedError` (workspace tools)
- 🚧 **Mocked** — returns canned response, real implementation pending (analyze_crackerjack)
- 🔌 **Proxies** — delegates to another MCP server or component (query_local_traces, search_code)
