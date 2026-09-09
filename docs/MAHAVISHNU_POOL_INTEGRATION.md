---
status: complete
role: canonical
date: 2026-09-09
last_reviewed: 2026-09-09
superseded_by: null
blocks_on: []
topic: mcp-design
---

# Mahavishnu Pool Integration for Crackerjack Scanning

## Status

**Design-only.** The pool-scanning integration plan in the previous
version of this document was scoped out during the 2026-08-06 AI-fix
removal. No production code currently exists in `crackerjack/` that
spawns Mahavishnu pools, distributes hooks across pool workers, or routes
quality-tool execution through `pool_execute` / `pool_route_execute`.

This document is preserved because:

1. It is still cited as the entry point for any future Phase 5
   `mahavishnu_pool_dispatcher.py` work referenced in
   `docs/superpowers/specs/2026-05-20-ai-fix-comprehensive-overhaul-design.md:243`
   and `docs/plans/2026-06-27-ty-cleanup-and-ai-fix.md:286`. Both of
   those plans describe a file (`crackerjack/integration/mahavishnu_pool_dispatcher.py`)
   that does **not exist** in the current tree.
2. Crackerjack does consume a small number of Mahavishnu MCP tools
   through the canonical FastMCP wire protocol. The tool surface
   documented below is real today; only the integration *plan* is
   design-only.

## What Is Real Today

Crackerjack is a client of Mahavishnu, not an orchestrator over it.
Today Crackerjack uses Mahavishnu for:

- **Cross-project git velocity / repository health dashboards**
  (server-side aggregation via `mahavishnu__query_local_traces`,
  `get_cross_project_git_dashboard`, etc. — see
  `crackerjack/mcp/tools/mahavishnu_tools.py`).
- **Pattern detection and anomaly correlation** when Crackerjack MCP
  exposes its own quality data via Akosha.

The pool-management surface is **not used by Crackerjack today**; it is
documented here only for future work.

______________________________________________________________________

## Mahavishnu Pool Capabilities (Ground Truth)

### Real Pool Types

Verified against `mahavishnu/pools/_registry.py` (canonical hyphen form):

| Canonical `pool_type` | Provider | Use For |
|-----------------------|----------|---------|
| `mahavishnu` | Local MahavishnuPool — direct `WorkerManager` | Low-latency local execution, debugging |
| `session-buddy` | SessionBuddyPool — delegates to a Session-Buddy instance (3 fixed workers) | Distributed execution with memory integration |
| `runpod` | RunPodPool — RunPod Flash serverless GPU | GPU/ML workloads |
| `pi` | PiPool — `npx @earendil-works/pi-coding-agent` subprocess bridge | Model-agnostic agent execution via Bifrost |
| `gpu-handler` | RunPod handler variant | GPU pool alternative |

The `pool_type` values `kubernetes`, `container`, `mahavishnu_pool`,
`session_buddy_pool`, `runpod_pool`, `pi_pool` (underscored forms in
client config) shown in earlier drafts of this document do **not**
exist. The underscored forms (`session_buddy_pool`) are accepted by
the CLI whitelist and translated to the canonical hyphen form
(`session-buddy`) before registry lookup
(`mahavishnu/pools/_registry.py:69-80`).

To discover the canonical names at runtime use
`mahavishnu/pools/_registry.py::list_pool_types()` or the CLI:
`mahavishnu pool types`.

### Real Pool MCP Tools (10 Verified)

Verified against `mahavishnu/mcp/tools/pool_tools.py` and
`mahavishnu/core/skill_mcp_validator.py` (the `KNOWN_TOOLS` whitelist
that gates `crackerjack__get_skills_for_issue`):

| MCP Tool | Purpose |
|----------|---------|
| `pool_list` | List all active pools |
| `pool_monitor` | Aggregate pool status + metrics for one or many pools |
| `pool_scale` | Scale a pool's worker count (not supported by `session-buddy`) |
| `pool_close` | Close one pool |
| `pool_close_all` | Close every active pool |
| `pool_health` | Cross-pool health snapshot |
| `pool_search_memory` | Cross-pool memory search |
| `pool_execute` | Execute a prompt on a specific pool |
| `pool_route_execute` | Auto-route a prompt to the best pool (least_loaded / round_robin / random / affinity) |
| `budget_enforce` | Declare a per-workflow budget (Phase 3 v2) — registered in `pool_tools.py` but not a pool-management primitive |

Earlier drafts of this document claimed **9** pool tools; the current
ground-truth count is **10**. The earlier drafts also showed example
parameters (`pool_id`, `pool_type="mahavishnu"`, `worker_type="container"`)
that are inconsistent with the live signatures in `pool_tools.py`.

### Tool Signatures (Verified)

```python
# mahavishnu/mcp/tools/pool_tools.py
async def pool_list() -> list[dict[str, Any]]
async def pool_monitor(pool_ids: list[str] | None = None) -> dict[str, dict[str, Any]]
async def pool_scale(pool_id: str, target_workers: int) -> dict[str, Any]
async def pool_close(pool_id: str) -> dict[str, Any]
async def pool_close_all() -> dict[str, Any]
async def pool_health() -> dict[str, Any]
async def pool_search_memory(query: str, limit: int = 100) -> list[dict[str, Any]]
async def budget_enforce(workflow_id: str, budget_tokens: int | None = None,
                         budget_turns: int | None = None,
                         budget_wallclock_seconds: float | None = None,
                         declared_by: str | None = None) -> dict[str, Any]
```

`pool_execute` and `pool_route_execute` are referenced in
`mahavishnu/pools/manager.py:518-519` and listed as registered in
`bodai/docs/memory/TOOL_ALIAS_INVENTORY.md` (the canonical
cross-component truth). Their full signatures live in the Mahavishnu
worker dispatch path, not `pool_tools.py`.

______________________________________________________________________

## Client Idiom — How To Call Mahavishnu From Python

There is **no Python package named `mcp__mahavishnu`**. The earlier
draft's `from mcp__mahavishnu import pool_spawn, ...` is wrong. The
correct client idiom is the MCP wire protocol over
`http://localhost:8680/mcp` (Streamable HTTP transport).

### Using `httpx.AsyncClient` (no SDK dependency)

```python
from __future__ import annotations

import json
from typing import Any

import httpx

MAHAVISHNU_MCP_URL = "http://localhost:8680/mcp"


async def call_mcp_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Call a Mahavishnu MCP tool over the canonical Streamable HTTP transport."""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {"name": tool_name, "arguments": arguments},
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(MAHAVISHNU_MCP_URL, json=payload)
        response.raise_for_status()
        envelope = response.json()
    if "error" in envelope:
        raise RuntimeError(f"MCP error from {tool_name}: {envelope['error']}")
    # FastMCP returns the result wrapped in result.content[0].text (JSON string).
    text_payload = envelope["result"]["content"][0]["text"]
    return json.loads(text_payload)


async def example_route_execute(prompt: str) -> dict[str, Any]:
    """Auto-route a prompt to the least-loaded pool."""
    return await call_mcp_tool(
        "pool_route_execute",
        {"prompt": prompt, "pool_selector": "least_loaded"},
    )
```

### Using the official MCP Python client

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


async def example_pool_health() -> dict[str, Any]:
    async with streamablehttp_client("http://localhost:8680/mcp") as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("pool_health", {})
            return result  # structured result; first text block carries JSON
```

The `streamablehttp_client` import is the same one the (not-yet-built)
`crackerjack/integration/mahavishnu_pool_dispatcher.py` would use —
see `docs/plans/2026-06-27-ty-cleanup-and-ai-fix.md:286`.

______________________________________________________________________

## Worker Backends Mahavishnu Currently Exposes

Worker backends are **separate** from pool types. Mahavishnu currently
ships:

| Worker Type | Status |
|-------------|--------|
| `terminal-claude` | Production — default |
| `terminal-qwen` | Production — alternate terminal adapter |
| Apple Container (`apple_container`) | Production on Apple silicon |
| E2B sandbox (`e2b_sandbox`) | Production cloud sandbox |
| Cloud worker (`cloud_worker`) | Production — MiniMax M3 default |

The earlier draft's `worker_type="container"` is **not** a valid
Mahavishnu worker type; Docker/OrbStack workers were removed in
2026-07 per `mahavishnu/CLAUDE.md` (Docker/OrbStack removed 2026-07).

For a full list, see `mahavishnu/mcp/tools/terminal_tools.py` and the
worker-type enumeration in `mahavishnu/terminal/adapters/`.

______________________________________________________________________

## Performance Notes

The earlier draft cited a **"3-4× speedup"** from distributing slow
quality tools across pool workers. That figure is unsourced and was
never benchmarked. No measured throughput numbers exist for the
proposed `mahavishnu_pool_dispatcher.py` because the dispatcher
itself was removed from scope in 2026-08.

Crackerjack's existing incremental scanning (no pool) is documented in
`docs/INTEGRAL_SCANNING_OPTIONS.md` and `crackerjack/config/settings.py`
(`pool_router`, `pooled_tools`, `local_tools` blocks). The
"15-30× faster" / "30-60× faster" numbers in earlier drafts were
extrapolations, not measurements — treat them as targets, not facts.

______________________________________________________________________

## Out Of Scope — What Was Removed And Why

The following items from earlier versions of this document were
scoped out during the **2026-08-06 AI-fix subsystem removal** (see
`docs/audits/2026-09-09-crackerjack-docs-audit.md` Cross-lens finding
**Orphan**):

| Removed item | Source | Status |
|--------------|--------|--------|
| `crackerjack/integration/mahavishnu_pool_dispatcher.py` (236 lines, routes via `mcp__mahavishnu__pool_route_execute`) | `docs/plans/2026-06-27-ty-cleanup-and-ai-fix.md:286`, `docs/superpowers/specs/2026-05-20-ai-fix-comprehensive-overhaul-design.md:243` | File does not exist. Phase 4 implementation was dropped when the AI-fix pipeline was removed. |
| `pool_scanning:` Crackerjack config block | `crackerjack/config/settings.py` `pooled_tools`, `local_tools`, `autoscaling`, `memory` | These config keys still exist for forward compatibility but no production code reads them. |
| `crackerjack/services/pool_client.py`, `crackerjack/hooks/pool_based_hooks.py`, `crackerjack/services/pool_router.py`, `crackerjack/services/pool_scaler.py`, `crackerjack/services/memory_aware_scanner.py` | Earlier drafts of this document | None of these modules exist. |

Any future reimplementation belongs in a **new Phase 5 plan**, not in
this document. The 2026-05-20 spec and 2026-06-27 plan are
**historical** (see their `status:` frontmatter — they predate the
2026-08-06 removal and are not the source of truth).

______________________________________________________________________

## What Crackerjack Should Actually Use

For cross-project observability and pattern queries today, use the
**crackerjack-side** tools, not the Mahavishnu pool surface:

```text
# Cross-project git velocity (real, wired, in tree today)
mcp__crackerjack__get_cross_project_git_dashboard
mcp__crackerjack__get_repository_health

# Pattern detection (real, wired, in tree today)
mcp__crackerjack__clone_detect_ecosystem
mcp__crackerjack__get_cross_project_patterns

# Mahavishnu health + workflow (real, exposed by mahavishnu server)
mcp__mahavishnu__get_health
mcp__mahavishnu__list_repos
```

For the full inventory, run `crackerjack__discover_tools(query="...")`
on the live MCP server.

______________________________________________________________________

## Verification Commands

To check the canonical state at any time:

```bash
# Pool type whitelist (canonical hyphen form)
python -c "from mahavishnu.pools._registry import list_pool_types; print(list_pool_types())"

# Registered pool tools
python -c "from mahavishnu.core.skill_mcp_validator import KNOWN_TOOLS; print(sorted(t for t in KNOWN_TOOLS if 'pool' in t))"

# Live MCP health
curl -sS http://localhost:8680/health | python -m json.tool
```

If any of the above returns a value the doc contradicts, the doc is
stale — the live system is the source of truth.

______________________________________________________________________

## Related Docs

- `docs/INTEGRAL_SCANNING_OPTIONS.md` — Incremental scanning
  approaches (no pool dependency).
- `crackerjack/config/settings.py` — `pool_router`, `pooled_tools`,
  `local_tools` config blocks (forward-compat only).
- `mahavishnu/CLAUDE.md` — Mahavishnu orchestration overview, port
  table, MCP tool profile tiers.
- `docs/plans/` — Historical Phase 1-4 plans (not the source of truth
  post-2026-08).
