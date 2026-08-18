# Tool profile rationale (W2a, 2026-08-18)

## Context

Adopting `mcp_common.tools.dispatch._apply_tool_profile` (mcp-common 0.18.0)
as the canonical mechanism for gating Crackerjack MCP tools based on
`CRACKERJACK_TOOL_PROFILE` (matches `MAHAVISHNU_TOOL_PROFILE` /
`AKOSHA_TOOL_PROFILE` / `DHARA_TOOL_PROFILE`).

W2a deletes the legacy `crackerjack/mcp/tools/discover_tools.py`
(236 lines: `TOOL_REGISTRY` + `DEFERRED_TOOLS` + `register_discover_tools`)
and replaces it with three modules:

- `crackerjack/mcp/tools/profiles.py` — per-tier registration lists +
  registration_map + mandatory groups.
- `crackerjack/mcp/tools/discover_query.py` — preserves the historical
  query filter via `discovery_fn=crackerjack_discovery`.
- `crackerjack/mcp/server_core.py` — wires the W0 helper via
  `await _apply_tool_profile(...)`.

See `2026-08-18-mcp-tool-profile-adoption-design` for the full plan.

## Decision rule

**Profile tiers** (MINIMAL → STANDARD → FULL):

| Tier | Groups | Rationale |
|------|--------|-----------|
| MINIMAL | `health_tools` only | Load balancers + orchestrators reach health probes at every tier. Nothing else needed for liveness/readiness checks. |
| STANDARD | `core_tools`, `execution_tools`, `utility_tools`, `doc_tools`, `health_tools` | The four "always-needed" Crackerjack runtime groups. Covers `execute_crackerjack`, `run_crackerjack_stage`, `init_crackerjack`, `clean_crackerjack`, `config_crackerjack`, `analyze_crackerjack`, `validate_claude_md`, `crackerjack_doc_frontmatter_validate`. |
| FULL | STANDARD + `eventbridge_tools`, `monitoring_tools`, `otel_tools`, `progress_tools`, `proactive_tools`, `pycharm_tools`, `semantic_tools` | All groups. Default (env-var unset). |

## Why `eventbridge_tools` and `progress_tools` are FULL not STANDARD

- **`eventbridge_tools`** registers `publish_to_eventbridge`, which only
  fires when `crackerjack.yaml::eventbridge.enabled=true`. The wrapper
  (`crackerjack/mcp/tools/eventbridge_tools_wrapper.py`) is a no-op when
  disabled, so the tool is absent from STANDARD on default configs. We
  exclude it from STANDARD to avoid surprising callers who import the
  tool name without enabling the publisher.
- **`progress_tools`** registers `get_job_progress` + `session_management`,
  which write `current_session.json` and `job-<id>.json` to disk. The
  statefulness creates local-file side effects that don't belong in a
  read-mostly STANDARD profile (operators who only need exec/utility/doc
  shouldn't see writes to their progress dir).
- **`monitoring_tools`** is FULL because the dashboard is operator-facing
  and would be wasted on agents doing routine work.
- **`otel_tools`** is FULL because OTel trace ingestion is heavy and
  only relevant for analyzer integrations.
- **`proactive_tools`** is FULL because the proactive suggestions are
  an advisor layer, not part of standard operations.
- **`pycharm_tools`** is FULL because PyCharm is an IDE-only integration;
  agents don't reach PyCharm directly.
- **`semantic_tools`** is FULL because it depends on a local
  `semantic_index.db` (TF-IDF or sentence-transformers) which is not
  part of every deployment.

## Why `validate_claude_md` is in STANDARD (write-side tool)

`validate_claude_md` lives in `utility_tools`. It writes CLAUDE.md when
called with `update=true`, but the tool is gated by an explicit user
opt-in. STANDARD includes the full `utility_tools` group because most
users want `clean_crackerjack`, `config_crackerjack`, `analyze_crackerjack`
alongside the basic execution tools — splitting utility into
read-only vs. write-only sub-groups would add tier fragmentation without
materially reducing blast radius (the write side is already gated by an
opt-in argument).

## Mandatory groups (always-on)

`CRACKERJACK_MANDATORY_GROUPS = {"health_tools"}`

Health probes are guaranteed at every tier. The W0 helper runs mandatory
groups AFTER per-profile dispatch so they remain reachable even when a
profile strips them.

## Behavioral parity: `crackerjack_discovery` vs. the deleted `register_discover_tools`

Both share the **filter** behavior (case-insensitive substring on
`name` OR `description`). They differ on the **response shape**:

- **OLD** (`discover_tools.py:189-229`): wrapped dict
  `{"status": "success", "matched": [...], "matched_count": N,
  "total_count": N, "groups": [...], "deferred": [...], "deferred_count": N, "hint": "..."}`
- **NEW** (`crackerjack_discovery`): flat `list[dict]` per the W0 helper
  default — `[{"name": ..., "description": ..., "inputSchema": ..., "group": ...}, ...]`

This is a deliberate API change. The W0 helper auto-registers the
`discover_tools` meta-tool with the new shape, matching Mahavishnu,
Akosha, and Session-Buddy. Callers should adapt to the list-of-dicts
shape (the Status 2026-08-18 note in `MEMORY_ARCHITECTURE.md`
documents this).

## Caching the historical group mapping

`tests/fixtures/_tool_groups_mapping.json` snapshots the deleted
TOOL_REGISTRY's `{tool_name: group}` mapping. `crackerjack_discovery`
reads it at module load so the `group` field still appears in responses.
This is best-effort: if the fixture is missing, the field is `None`.

## Status

Adopted 2026-08-18 in W2a. Pre-flight grep results and commit SHAs are
recorded in
`/Users/les/Projects/mahavishnu/.superpowers/sdd/2026-08-18-mcp-tool-profile-adoption/task-6-report.md`.