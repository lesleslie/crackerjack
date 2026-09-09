---
title: Crackerjack MCP Tools Specification
generated: 2026-09-09
status: active
role: canonical
date: 2026-09-09
last_reviewed: 2026-09-09
superseded_by: null
blocks_on: []
topic: mcp-design
---

# Crackerjack MCP Tools Specification

Authoritative reference for every MCP tool the Crackerjack MCP server can
register. Source of truth: [`crackerjack/mcp/tools/`](../crackerjack/mcp/tools/)
(mirrors) and [`crackerjack/mcp/tools/profiles.py`](../crackerjack/mcp/tools/profiles.py)
(dispatch surface). Any tool not listed here is not in the wire surface.

This document was rewritten 2026-09-09 as part of the docs-audit remediation
(Category D). Earlier revisions carried phantom tools, misattributed
registrations, and an internally contradictory profile model. None of that
survives.

---

## 1. Registration model

Crackerjack uses a **three-tier profile gate** mirroring the other Bodai
components (`mahavishnu`, `session-buddy`, `akosha`, `dhara`).

| Tier | Selection env var | When |
|---|---|---|
| `MINIMAL` | `CRACKERJACK_TOOL_PROFILE=minimal` | Probes-only deployments (health checks + discovery). |
| `STANDARD` (default) | `CRACKERJACK_TOOL_PROFILE=standard` | Everyday operator surface (cradle-to-grave quality workflow). |
| `FULL` | `CRACKERJACK_TOOL_PROFILE=full` | All groups enabled (developer, CI, cross-component integrations). |

The dispatcher lives in [`mcp_common.tools.dispatch._apply_tool_profile`][mcp-common].
Crackerjack wires it from [`crackerjack/mcp/server_core.py::create_mcp_server`](../crackerjack/mcp/server_core.py)
with `crackerjack_discovery` (see §6) as the discovery override. Two
additional guarantees:

- **Mandatory groups** — `health_tools` is registered at every tier
  (load balancers and orchestrators depend on the probes being reachable).
  Declared in `CRACKERJACK_MANDATORY_GROUPS` (currently `{"health_tools"}`).
- **`discover_tools` meta-tool** — auto-registered by the W0 helper at every
  tier using `crackerjack/mcp/tools/discover_query.py::crackerjack_discovery`.

[mcp-common]: https://github.com/lesleslie/mcp-common

### 1.1 Per-profile tool counts (verified 2026-09-09)

Verified by grepping every `@mcp_app.tool()` / `@mcp.tool()` decorator under
`crackerjack/mcp/tools/` and cross-checking against
`profiles.py::PROFILE_REGISTRATIONS`. The `eventbridge_tools` row is
conditional — the `publish_to_eventbridge` tool only appears when
`settings/crackerjack.yaml::eventbridge.enabled=true` (default `false`).

| Profile | Profile-listed tools | + mandatory (health) | + `discover_tools` | **Total** |
|---|---:|---:|---:|---:|
| `MINIMAL` | 0 | 6 | 1 | **7** |
| `STANDARD` | 10 (core 1 + execution 4 + utility 4 + doc 1) | 6 | 1 | **17** |
| `FULL` (eventbridge disabled — default) | 40 | 6 | 1 | **47** |
| `FULL` (eventbridge enabled) | 41 | 6 | 1 | **48** |

### 1.2 Tools NOT in the wire surface (defined but never registered)

Two orphan groups exist in `crackerjack/mcp/tools/` but are absent from
both `REGISTRATION_MAP` and `PROFILE_REGISTRATIONS` — calling `crackerjack mcp
start` does not expose them:

| Module | Tools | Status |
|---|---|---|
| `crackerjack/mcp/tools/mahavishnu_tools.py` | `get_cross_project_git_dashboard`, `get_repository_health`, `get_cross_project_patterns`, `get_velocity_comparison` | **Orphan.** Defined but never wired. Wire-up requires adding `"mahavishnu_tools"` to `REGISTRATION_MAP` (with a corresponding register function) and assigning a tier in `PROFILE_REGISTRATIONS`. As of 2026-09-09 the module does not expose any `register_*` function. |
| `crackerjack/mcp/tools/workspace_tools.py` | `create_workspace`, `list_workspaces`, `get_workspace_info`, `remove_workspace` | **Orphan + stubs.** Defined but never wired; even when wired, `_get_manager()` raises `NotImplementedError` until the Phase 3 Oneiric workspace backend lands. |

These tools are intentionally **not** documented in §3 below because they
are not callable through the MCP server.

---

## 2. Profile → tool group matrix

| Group | Module | MINIMAL | STANDARD | FULL |
|---|---|:---:|:---:|:---:|
| `core_tools` | `core_tools.py` | | ✓ | ✓ |
| `execution_tools` | `execution_tools.py` | | ✓ | ✓ |
| `utility_tools` | `utility_tools.py` | | ✓ | ✓ |
| `doc_tools` | `doc_tools.py` | | ✓ | ✓ |
| `eventbridge_tools` | `eventbridge_tools_wrapper.py` → `eventbridge_tools.py` | | | ✓¹ |
| `language_tools` | `language_tools.py` | | | ✓ |
| `monitoring_tools` | `monitoring_tools.py` | | | ✓ |
| `otel_tools` | `otel_tools.py` | | | ✓ |
| `progress_tools` | `progress_tools.py` | | | ✓ |
| `proactive_tools` | `proactive_tools.py` | | | ✓ |
| `pycharm_tools` | `pycharm_tools.py` | | | ✓ |
| `semantic_tools` | `semantic_tools.py` | | | ✓ |
| `health_tools` | `health_tools_wrapper.py` → `mcp_common.health.register_health_tools` | ✓ | ✓ | ✓ |
| `discover_tools` | `discover_query.py` (auto-registered by W0 helper) | ✓ | ✓ | ✓ |

¹ Conditional on `settings/crackerjack.yaml::eventbridge.enabled=true`.

---

## 3. Per-tool reference

### 3.1 `core_tools` (`core_tools.py`) — STANDARD+

| Tool | Signature | Description |
|---|---|---|
| `run_crackerjack_stage(args: str, kwargs: str) -> str` | Legacy stage runner. | **STUB.** Returns `{"error": "Workflow orchestration removed in Phase 2 (legacy runtime removal). Will be reimplemented in Phase 3 (Oneiric integration).", "success": false}`. Kept for backward compatibility; full reimplementation deferred to Phase 3. |

### 3.2 `execution_tools` (`execution_tools.py`) — STANDARD+

| Tool | Signature | Description |
|---|---|---|
| `execute_crackerjack(args: str, kwargs: str) -> str` | Args = optional sub-mode; `kwargs` = JSON `{test: bool, testing: bool, execution_timeout: int, ...}`. | Full Crackerjack quality workflow. Rate-limited via `context.rate_limiter`. Writes `workflow_checkpoints.sqlite`, `fix_attempts`, `error_patterns`, `progress_dir/job-<id>.json`. |
| `smart_error_analysis(use_cache: bool = True) -> str` | In-process `ErrorCache` frequency counter. | AI-prioritized fix suggestions from the cached error pattern DB. |
| `init_crackerjack(args: str = "", kwargs: str = "{}") -> str` | `args` = target path (default `.`); `kwargs` = `{force: bool, template: str \| None, interactive: bool}`. | First-time project setup: writes `pyproject.toml`, `.gitignore`, `CLAUDE.md`, `RULES.md`, `example.mcp.json` (per `crackerjack/services/initialization.py::_get_config_files`). |
| `suggest_agents(task_description: str = "", project_type: str = "python", current_context: str = "") -> str` | Keyword-driven recommender. | Returns structured suggestions for `TestCreationAgent`, `RefactoringAgent`, `SecurityAgent`, `PerformanceAgent`, `DocumentationAgent`, `ImportOptimizationAgent` based on task text (per `crackerjack/mcp/tools/execution_tools.py::_analyze_task_for_agents`). |

### 3.3 `utility_tools` (`utility_tools.py`) — STANDARD+

| Tool | Signature | Description |
|---|---|---|
| `clean_crackerjack(args: str = "", kwargs: str = "{}") -> str` | `args` = scope in `{temp, progress, cache, all}`; `kwargs` = `{dry_run: bool, older_than: int}`. | Delete old `crackerjack-*.log`, `.coverage.*`, `progress_dir/*.json`. **Note:** `cache` scope is currently a no-op (`pass` in `_execute_cleanup_operations`); only `temp` and `progress` perform real work. |
| `config_crackerjack(args: str = "", kwargs: str = "{}") -> str` | `args` = `list \| get <key> \| validate`. | Read-only dump of `CrackerjackSettings.model_dump()`. |
| `analyze_crackerjack(args: str = "", kwargs: str = "{}") -> str` | `args` = scope; `kwargs` = `{report_format: str}`. | **MOCKED.** Returns `{"status": "mock_success", ...}`. Real implementation pending. |
| `validate_claude_md(args: str = "", kwargs: str = "{}") -> str` | `args` may contain `--update`; `kwargs` = `{update: bool, project_path: str}`. | Validates `CLAUDE.md` against Crackerjack integration markers + essential principles. With `update=true`, may rewrite `CLAUDE.md` via `InitializationService.initialize_project_full(force=True)`. |

### 3.4 `doc_tools` (`doc_tools.py`) — STANDARD+

| Tool | Signature | Description |
|---|---|---|
| `crackerjack_doc_frontmatter_validate(pkg_path: str = ".", strict: bool = False, allow_nonstandard: bool = True, validate_links: bool = False, store: str \| None = None) -> str` | JSON-serialized validation report. | Scans all `.md` files under `pkg_path` for YAML frontmatter shape; `store="path"` persists the report. `strict=true` enforces the `status: active\|complete\|draft\|partial\|shipped` enum. |

### 3.5 `eventbridge_tools` (`eventbridge_tools_wrapper.py` → `eventbridge_tools.py`) — FULL (conditional)

Wrapper `register_crackerjack_eventbridge` honors
`settings/crackerjack.yaml::eventbridge.enabled` (default `false`). When false, the
inner registrar is a no-op and no tools from this group are exposed.

| Tool | Signature | Description |
|---|---|---|
| `publish_to_eventbridge(topic: str, payload: dict, async_callback: bool = False) -> dict` | `topic` ∈ `{test.started, test.completed, test.failed}`; only hardcoded keys are read by the dispatcher (see below) — unknown topics log a warning and are ignored. | Bodai EventBridge publisher. With `async_callback=True`, returns `{workflow_id, status: queued}` and schedules `_dispatch_topic` as a background task. |

### 3.6 `language_tools` (`language_tools.py`) — FULL

| Tool | Signature | Description |
|---|---|---|
| `swift_bump_version(project_root: str, level: Literal["major","minor","patch"] = "minor", release: bool = False) -> dict` | **Mutation. Requires `MAHAVISHNU_AUTH_ENABLED=true` and `MAHAVISHNU_JWT_SECRET`. `project_root` must be in `MAHAVISHNU_PROJECT_ROOTS` allowlist.** | Bumps Swift project version via git tags (no `Package.swift` mutation); commits, tags, pushes, optionally creates a GitHub release. Returns `{new_version, commit_sha, tag_name, release_url}`. |
| `swift_list_hooks(project_root: str) -> dict` | Read-only. | Returns Swift hook configs (`cli_command`, `autofix`, `timeout_seconds`) keyed by name. Renamed from the legacy `swift_run_hooks`: it does NOT execute hooks. |
| `detect_languages(project_root: str) -> dict[str, bool]` | Read-only. | Returns which language adapters detect the project. `python`, `swift`, `kotlin`, `web` keys. |
| `kotlin_bump_version(level: Literal["major","minor","patch"], project_root: str, dry_run: bool = False, release: bool = False) -> dict` | **Mutation. Auth + allowlist required.** | Bumps Kotlin/Gradle project version by writing `gradle.properties` (NOT `build.gradle.kts`), then commits/tags/pushes. Rolls back mutations on failure. Returns `{new_version, commit_sha, tag_name, release_url, skipped_steps}`. |
| `kotlin_list_hooks(project_root: str) -> dict[str, dict]` | Read-only. | Probes `./gradlew tasks --all`; returns hook metadata keyed by name. Hooks whose tasks are absent are filtered with a logged warning. |
| `check_web_lint(project_root: str) -> dict` | Read-only. | Activates the Web adapter; returns `{adapter: "web", enabled: bool, hooks: [{name, cli_command, timeout_seconds}]}`. Requires `package.json` at root OR `[tool.crackerjack.web] enabled = true`. |
| `format_jinja_templates(projects: list[str], dry_run: bool = True) -> dict` | **Mutation. Auth required.** | Formats Jinja templates under each project root (Tier 1: trailing newline + no trailing whitespace; Tier 2 deferred). Returns `{files, errors, mode}`. Per-project delimiter config from `[tool.crackerjack.jinja]`. |

### 3.7 `monitoring_tools` (`monitoring_tools.py`) — FULL

All tools in this group require the in-process `state_manager` (initialized
by the legacy runtime; absent on fresh `crackerjack.mcp` invocations and
return the documented error JSON).

| Tool | Signature | Description |
|---|---|---|
| `get_stage_status() -> str` | Returns `{stages: {fast, comprehensive, tests, cleaning}, session: {total_iterations, current_iteration, session_active}, timestamp}`. | Stage-by-stage completion state from the legacy runtime state manager. |
| `get_next_action() -> str` | Returns `{recommended_action: run_stage \| complete \| initialize, parameters, reason}`. | Recommends the next stage based on current `state_manager` view. |
| `get_server_stats() -> str` | Returns server info + rate-limit config + resource usage. | Read-only snapshot of MCP server runtime state. |
| `get_comprehensive_status() -> str` | Runs through `bounded_status_operation` with auth + security validation. | Comprehensive services + jobs + server stats snapshot. Requires `StatusAuthenticator` setup. |
| `list_slash_commands() -> str` | Returns `{available_commands, command_details, total_commands}`. | Enumerates the three Crackerjack slash commands (`run`, `status`, `init`) with usage hints. **NB:** Not registered via `utility_tools` (audit Lens 2 correction; actual location: `monitoring_tools.py:_register_command_help_tool`). |
| `get_filtered_status(components: str = "all") -> str` | `components` ∈ `{services, jobs, resources, all}` (comma-separated). | Filtered slice of the comprehensive status payload. |

### 3.8 `otel_tools` (`otel_tools.py`) — FULL

| Tool | Signature | Description |
|---|---|---|
| `query_local_traces(task_class: str, time_range_minutes: int = 60, system_id: str \| None = None, limit: int = 100) -> list[dict]` | Proxies to `mcp__akosha__query_local_traces` over HTTP at `$AKOSHA_MCP_ENDPOINT` (default `http://localhost:8682`). | Read-only proxy. Errors are swallowed and `[]` is returned. |

### 3.9 `progress_tools` (`progress_tools.py`) — FULL

| Tool | Signature | Description |
|---|---|---|
| `get_job_progress(job_id: str) -> str` | `job_id` validated against `crackerjack.services.regex_patterns.is_valid_job_id`. | Reads `progress_dir/job-<id>.json` and returns the JSON-serialized payload. |
| `session_management(action: str, checkpoint_name: str \| None = None) -> str` | `action` ∈ `{start, checkpoint, complete, reset}`. | Drives the legacy `state_manager` session lifecycle; writes `current_session.json` and `<checkpoint>.json`. |

### 3.10 `proactive_tools` (`proactive_tools.py`) — FULL

| Tool | Signature | Description |
|---|---|---|
| `plan_development(args: str, kwargs: str) -> str` | `args` = feature context; `kwargs` = `{feature: str, complexity: "low"\|"medium"\|"high"}`. | Architectural planning recommendation. Returns `crackerjack-architect`, `refactoring-specialist`, `security-auditor` suggestions with rationale. |
| `validate_architecture(args: str, kwargs: str) -> str` | `args` or `kwargs.file_path` = target file. | Runs the four-check compliance suite (complexity_compliance, clean_code_patterns, security_patterns, type_annotations). |
| `suggest_patterns(args: str, kwargs: str) -> str` | `args` = problem context (keyword-driven). | Recommends extract_method, common_base_class, list_comprehension, secure_temp_files, etc. based on context keywords (`complex`, `duplicate`, `performance`, `security`). |

### 3.11 `pycharm_tools` (`pycharm_tools.py`) — FULL

Proxies through `crackerjack.services.pycharm_mcp_integration.PyCharmMCPAdapter`.
All tools return a structured error if PyCharm is not connected.

| Tool | Signature | Description |
|---|---|---|
| `search_code(pattern: str, file_pattern: str \| None = None) -> str` | Regex search via PyCharm MCP. | Returns matches with file path, line, column, match text, context. |
| `get_ide_diagnostics(file_path: str, errors_only: bool = False) -> str` | `errors_only` filters out warnings/info. | Surfaces PyCharm inspections as `{file_path, line_number, column_number, message, code, severity, suggestion, source: "pycharm"}` records. |
| `get_symbol_info(symbol_name: str, include_usages: bool = False) -> str` | **STUB.** | Returns `status: "not_implemented"` with reason "PyCharm MCP server not connected. Symbol info requires IDE connection." Real implementation pending the PyCharm MCP extension. |
| `find_usages(symbol_name: str, file_path: str \| None = None, limit: int = 50) -> str` | **STUB.** | Same not-implemented reason as `get_symbol_info`. |
| `pycharm_health() -> str` | Circuit-breaker aware. | Returns `{mcp_available, circuit_breaker_open, failure_count, cache_size, status: healthy \| degraded}`. |

### 3.12 `semantic_tools` (`semantic_tools.py`) — FULL

| Tool | Signature | Description |
|---|---|---|
| `index_file_semantic(file_path: str, config_json: str = "") -> str` | `config_json` overrides defaults (`embedding_model`, `chunk_size`, `chunk_overlap`, `max_search_results`, `similarity_threshold`, `embedding_dimension`). | Chunks and embeds a file into `.crackerjack/semantic_index.db`. |
| `remove_file_from_semantic_index(file_path: str, config_json: str = "") -> str` | Same config semantics. | Removes all chunks for a file from the index. |
| `search_semantic(query: str, max_results: int = 10, min_similarity: float = 0.7, file_types: str = "", config_json: str = "") -> str` | `file_types` = comma-separated suffix list. | Cosine-similarity search; returns `{file_path, content, similarity_score, start_line, end_line, file_type, chunk_id}` records. |
| `get_semantic_stats(config_json: str = "") -> str` | Returns `{total_files, total_chunks, index_size_mb, average_chunks_per_file, embedding_model, embedding_dimension, last_updated}`. | Read-only index introspection. |
| `get_embeddings(texts: str, config_json: str = "") -> str` | `texts` = JSON array of strings. | Returns raw embedding vectors from the configured model (default `sentence-transformers/all-MiniLM-L6-v2`, dim 384). |
| `calculate_similarity_semantic(embedding1: str, embedding2: str, config_json: str = "") -> str` | Embeddings are JSON arrays of floats. | Returns `{similarity_score, embedding1_dimension, embedding2_dimension}`. |

---

## 4. `discover_tools` meta-tool (always-on)

Auto-registered at every profile tier by the W0 helper, using
`crackerjack_discovery` from `crackerjack/mcp/tools/discover_query.py`. The
override preserves the historical query-filter behavior from the deleted
`crackerjack/mcp/tools/discover_tools.py:189-229` module.

| Signature | Behavior |
|---|---|
| `discover_tools(query: str \| None = None) -> list[dict]` | When `query` is `None`, returns all registered tools with `{name, description, inputSchema, group}`. When `query` is a string, performs case-insensitive substring match against `name` OR `description` and returns the filtered subset. |

The `group` field is sourced from `tests/fixtures/_tool_groups_mapping.json`
(a snapshot of the historical tool-name → group mapping). If the fixture
is missing, the field silently degrades to `None`.

---

## 5. `health_tools` probes (always-on via `CRACKERJACK_MANDATORY_GROUPS`)

Registered via `crackerjack/mcp/tools/health_tools_wrapper.py::register_crackerjack_health`,
which calls `mcp_common.health.register_health_tools` with the Crackerjack
service name + version + dependency allowlist. The wrapper hardcodes two
non-required dependencies (`session_buddy` at `:8678`, `mahavishnu` at
`:8680`); readiness probes report degraded when they are unreachable.

| Tool | Signature | Purpose |
|---|---|---|
| `get_liveness() -> dict` | Liveness probe (no I/O). | Standard liveness signal for orchestrators. |
| `get_readiness() -> dict` | Probes both `session_buddy` and `mahavishnu`. | Readiness signal — degraded when any dependency is unreachable. |
| `health_check_service(service_name_arg: str, host: str = "localhost", port: int = 8080, timeout: int = 5, use_tls: bool = False, health_path: str = "/health") -> dict` | Single-service HTTP `GET` to `health_path`. | Reachability probe for any registered dependency. |
| `health_check_all() -> dict` | Iterates every dependency in `_HEALTH_DEPENDENCIES`. | Bulk reachability snapshot. |
| `wait_for_dependency(dep_service_name: str, host: str = "localhost", port: int = 8080, timeout: int = 30, required: bool = True, use_tls: bool = False, health_path: str = "/health") -> dict` | Exponential-backoff loop. | Blocks until the target is healthy or the timeout elapses. |
| `wait_for_all_dependencies() -> dict` | Same backoff semantics across the allowlist. | Blocks until every registered dependency is healthy or the timeout elapses. |

---

## 6. Tools that proxy to other components

| Tool | Upstream | Protocol | Failure mode |
|---|---|---|---|
| `publish_to_eventbridge` | Oneiric EventBridge | In-process when `eventbridge.enabled=true` | Returns `{status: "no_publisher", warning: ...}` if enabled but not wired; silent no-op when disabled. |
| `query_local_traces` | `mcp__akosha__query_local_traces` | HTTP POST to `AKOSHA_MCP_ENDPOINT/mcp` (JSON-RPC 2.0) | Swallowed errors → `[]` returned. |
| `search_code`, `get_ide_diagnostics`, `pycharm_health` | PyCharm MCP | HTTP via `PyCharmMCPAdapter` (timeout 30s) | Structured error JSON when PyCharm MCP unreachable; circuit-breaker trips after repeated failures. |
| `get_symbol_info`, `find_usages` | PyCharm MCP (planned) | HTTP via `PyCharmMCPAdapter` | Returns `status: "not_implemented"`; pending PyCharm MCP extension. |
| `get_cross_project_*`, `get_repository_health`, `get_velocity_comparison` (orphan) | Mahavishnu aggregator (planned) | In-process via `crackerjack.integration.mahavishnu_integration` | **Not reachable** — `mahavishnu_tools` is not wired into any profile. |

---

## 7. Tool groups by access pattern

| Group | Latency profile | Typical caller |
|---|---|---|
| **Hot execution** (`execute_crackerjack`, `run_crackerjack_stage`) | Up to 600s with rate-limit 12 req/s + burst 35 | Mahavishnu worker dispatch, CI |
| **Language mutation** (`swift_bump_version`, `kotlin_bump_version`, `format_jinja_templates`) | 1-30s per project, blocked on auth + allowlist | Manual operator + CI release pipeline |
| **Language introspection** (`swift_list_hooks`, `kotlin_list_hooks`, `detect_languages`, `check_web_lint`) | <1s | Editor / IDE integration |
| **Monitoring** (`get_comprehensive_status`, `get_filtered_status`, `get_server_stats`, `get_stage_status`, `get_next_action`, `list_slash_commands`) | <100ms | Operator dashboards |
| **OTel** (`query_local_traces`) | Network-bound, 30s default timeout | Mahavishnu observability layer |
| **Code intelligence** (`search_code`, `get_ide_diagnostics`, `pycharm_health`) | Network-bound, 30s timeout | PyCharm IDE |
| **Semantic search** (`index_file_semantic`, `search_semantic`, `get_semantic_stats`, `get_embeddings`, `calculate_similarity_semantic`, `remove_file_from_semantic_index`) | Index build is O(file size); search is vector-cosine | RAG pipelines, `mahavishnu/ingesters/content_ingester.py:611` |
| **Admin / utility** (`clean_crackerjack`, `config_crackerjack`, `analyze_crackerjack`, `validate_claude_md`, `crackerjack_doc_frontmatter_validate`) | <1s | Operator one-offs |
| **Proactive** (`plan_development`, `validate_architecture`, `suggest_patterns`) | <10ms (in-process rule dispatch) | Claude / agent workflows |
| **Progress** (`get_job_progress`, `session_management`) | <50ms (JSON file I/O) | Workflow dashboards |

---

## 8. Tool groups by persistence side-effect

| Group | Reads | Writes |
|---|---|---|
| Hot execution | `CrackerjackSettings`, `LifecycleManager`, `GitMetricsCollector` | `workflow_checkpoints.sqlite`, `fix_attempts`, `error_patterns`, `progress_dir/job-<id>.json` |
| Language mutation | `gradle.properties`, git refs, `MAHAVISHNU_PROJECT_ROOTS` allowlist | `gradle.properties`, git commits/tags, optionally `gh release` |
| Monitoring | `progress_dir/*.json`, in-process `state_manager` | None |
| Semantic search | `.crackerjack/semantic_index.db` | Same DB (embeddings + chunks) |
| Progress | `progress_dir/job-<id>.json`, `current_session.json` | Same files |
| Admin / utility | `CrackerjackSettings`, `CLAUDE.md` | `CLAUDE.md` (conditional via `update=true`) |

---

## 9. Registration map (function → tool group)

The mechanical single source of truth, mirroring `REGISTRATION_MAP` in
`crackerjack/mcp/tools/profiles.py`.

| Register function | Tool group | Module |
|---|---|---|
| `register_core_tools` | `core_tools` (`run_crackerjack_stage`) | `crackerjack/mcp/tools/core_tools.py` |
| `register_doc_tools` | `doc_tools` (`crackerjack_doc_frontmatter_validate`) | `crackerjack/mcp/tools/doc_tools.py` |
| `register_crackerjack_eventbridge` (wrapper) → `register_eventbridge_tools` | `eventbridge_tools` (`publish_to_eventbridge`, conditional) | `crackerjack/mcp/tools/eventbridge_tools_wrapper.py` → `crackerjack/mcp/tools/eventbridge_tools.py` |
| `register_execution_tools` | `execution_tools` (`execute_crackerjack`, `smart_error_analysis`, `init_crackerjack`, `suggest_agents`) | `crackerjack/mcp/tools/execution_tools.py` |
| `register_language_tools` | `language_tools` (`swift_bump_version`, `swift_list_hooks`, `detect_languages`, `kotlin_bump_version`, `kotlin_list_hooks`, `check_web_lint`, `format_jinja_templates`) | `crackerjack/mcp/tools/language_tools.py` |
| `register_monitoring_tools` | `monitoring_tools` (`get_stage_status`, `get_next_action`, `get_server_stats`, `get_comprehensive_status`, `list_slash_commands`, `get_filtered_status`) | `crackerjack/mcp/tools/monitoring_tools.py` |
| `register_otel_tools` | `otel_tools` (`query_local_traces`) | `crackerjack/mcp/tools/otel_tools.py` |
| `register_proactive_tools` | `proactive_tools` (`plan_development`, `validate_architecture`, `suggest_patterns`) | `crackerjack/mcp/tools/proactive_tools.py` |
| `register_progress_tools` | `progress_tools` (`get_job_progress`, `session_management`) | `crackerjack/mcp/tools/progress_tools.py` |
| `register_pycharm_tools` | `pycharm_tools` (`search_code`, `get_ide_diagnostics`, `get_symbol_info`, `find_usages`, `pycharm_health`) | `crackerjack/mcp/tools/pycharm_tools.py` |
| `register_semantic_tools` | `semantic_tools` (`index_file_semantic`, `search_semantic`, `get_semantic_stats`, `remove_file_from_semantic_index`, `get_embeddings`, `calculate_similarity_semantic`) | `crackerjack/mcp/tools/semantic_tools.py` |
| `register_utility_tools` | `utility_tools` (`clean_crackerjack`, `config_crackerjack`, `analyze_crackerjack`, `validate_claude_md`) | `crackerjack/mcp/tools/utility_tools.py` |
| `register_crackerjack_health` (wrapper) → `mcp_common.health.register_health_tools` | `health_tools` (`get_liveness`, `get_readiness`, `health_check_service`, `health_check_all`, `wait_for_dependency`, `wait_for_all_dependencies`) | `crackerjack/mcp/tools/health_tools_wrapper.py` → `mcp_common` |
| `_apply_tool_profile` (W0 helper) | `discover_tools` (meta-tool, always-on) | `crackerjack/mcp/server_core.py` (uses `crackerjack/mcp/tools/discover_query.py`) |
| `register_all_tool_groups` | Bulk registrar passed as `register_all_fn=` to `_apply_tool_profile`; iterates every group in `REGISTRATION_MAP` | `crackerjack/mcp/tools/profiles.py` |

### 9.1 Not in the registration map

| Tool group | Tools | Why excluded |
|---|---|---|
| `mahavishnu_tools` | `get_cross_project_git_dashboard`, `get_repository_health`, `get_cross_project_patterns`, `get_velocity_comparison` | Not present in `REGISTRATION_MAP`. Wire-up deferred pending an integration test that asserts non-empty results (per `.claude/decisions/mcp-backend-wiring-discipline.md`). |
| `workspace_tools` | `create_workspace`, `list_workspaces`, `get_workspace_info`, `remove_workspace` | Not present in `REGISTRATION_MAP`. The internal `_get_manager()` raises `NotImplementedError` because the Oneiric workspace backend (`crackerjack.mahavishnu.workspace`) was removed in Phase 2; Phase 3 is the planned reimplementation target. |

---

## 10. Cross-references

- **Registration source code** — `crackerjack/mcp/tools/profiles.py` (`PROFILE_REGISTRATIONS`, `REGISTRATION_MAP`, `CRACKERJACK_MANDATORY_GROUPS`, `register_all_tool_groups`).
- **Server wiring** — `crackerjack/mcp/server_core.py::create_mcp_server` (lines 196-248, `_apply_tool_profile` invocation).
- **Discovery override** — `crackerjack/mcp/tools/discover_query.py::crackerjack_discovery` (substitutes the W0 helper's default discovery with a case-insensitive substring filter on `name`/`description`).
- **Phase 4 web-adapter hooks** — `crackerjack/adapters/web/hooks.py` (`web.stylelint`, `web.eslint`, `web.tsc`, `web.html_validate`); surfaced via `language_tools.check_web_lint` + `language_tools.format_jinja_templates`.
- **Sibling specs** — `akosha/docs/architecture/MEMORY_ARCHITECTURE.md`, `mahavishnu/docs/MCP_TOOLS_SPECIFICATION.md`, `session-buddy/docs/MCP_TOOLS_SPECIFICATION.md`, `dhara/docs/MCP_TOOLS_SPECIFICATION.md` (when present).
- **Drift regression tests** — `tests/unit/mcp/test_mcp_tool_drift.py` (mechanical enforcement of registration drift).
- **Wiring policy** — `.claude/decisions/mcp-backend-wiring-discipline.md` (every tool must have `feed.entities_count`, `feed.last_updated_timestamp`, `feed.errors_total`, `cycles_total` and a passing `tests/integration/test_<tool>_e2e.py`).

---

## 11. Status legend

- **Registered** — active in the wire surface at the indicated tier(s).
- **Stub** — function defined but returns a canned "not implemented" / "Phase X reimplementation" payload (`run_crackerjack_stage`, `analyze_crackerjack`, `get_symbol_info`, `find_usages`).
- **Conditional** — only registered when a config setting enables the group (`publish_to_eventbridge` requires `eventbridge.enabled=true`).
- **Orphan** — defined in `crackerjack/mcp/tools/` but not wired into `REGISTRATION_MAP` (not in the wire surface). See §9.1.