---
status: complete
role: canonical
date: 2026-09-09
last_reviewed: 2026-09-09
superseded_by: null
blocks_on: []
topic: mcp-design
---

# Mahavishnu Pool Integration — Quick Start

## Status

This is the **current** quickstart. The previous version described a
pre-AI-fix-removal integration plan; the design was scoped out during
the **2026-08-06 AI-fix subsystem removal**, and the references to
`pool_spawn("kubernetes", ...)`, `worker_type="container"`, and the
`from mcp__mahavishnu import ...` Python idiom were all wrong or
removed. See `docs/MAHAVISHNU_POOL_INTEGRATION.md` for the full
ground-truth rewrite and `docs/audits/2026-09-09-crackerjack-docs-audit.md`
finding **F7** for the audit history.

What you should know to use Mahavishnu pools today, in three short
sections:

1. The pool types and tools that are actually wired.
1. The correct Python client idiom (JSON-RPC over HTTP).
1. The troubleshooting commands that work today.

______________________________________________________________________

## 1. Pool Types and Tools (Verified)

### Pool types (canonical hyphen form)

Source of truth: `mahavishnu/pools/_registry.py`.

| `pool_type` | What it does |
|-------------|--------------|
| `mahavishnu` | Local MahavishnuPool — direct `WorkerManager` |
| `session-buddy` | SessionBuddyPool — delegates to a Session-Buddy instance (3 fixed workers) |
| `runpod` | RunPodPool — RunPod Flash serverless GPU |
| `pi` | PiPool — `@earendil-works/pi-coding-agent` subprocess bridge |

> **`gpu-handler` is NOT a registered pool type.** `GpuHandlerPool`
> exists in `mahavishnu/pools/gpu_handler_pool.py` as a `RunPodPool`
> subclass you can instantiate directly, but it is NOT registered with
> `mahavishnu.pools._registry::register_pool_type` and does not appear
> in `list_pool_types()`. Import the class directly instead of using
> `pool_spawn` / registry dispatch.

`kubernetes`, `container`, `mahavishnu_pool`, `session_buddy_pool`,
`runpod_pool`, `pi_pool` are **not** valid pool-type values. The
underscored forms (`session_buddy_pool`, etc.) are accepted only by
the CLI whitelist, which translates them to the canonical hyphen form
before registry lookup (`mahavishnu/pools/_registry.py:69-80`).

### Pool tools (8 MCP tools, verified)

Source of truth: `mahavishnu/mcp/tools/pool_tools.py` (counted
`@mcp.tool()` decorators).

```text
pool_list           # List active pools
pool_monitor        # Status + metrics for one or many pools
pool_scale          # Scale a pool's worker count
pool_close          # Close one pool
pool_close_all      # Close every active pool
pool_health         # Cross-pool health snapshot
pool_search_memory  # Cross-pool memory search
budget_enforce      # Declare a per-workflow budget (Phase 3 v2)
```

The earlier draft claimed **9** or **10** pool tools; the live count
is **8** `@mcp.tool()` decorators in `pool_tools.py`. `pool_execute`
and `pool_route_execute` are NOT registered MCP tools — they are CLI
commands (`mahavishnu pool execute`, `mahavishnu pool route`) and
Python functions in `mahavishnu/_main_cli.py:1668`, not MCP
wire-protocol tools.

______________________________________________________________________

## 2. Calling The Mahavishnu MCP Server From Python

The correct client idiom is **JSON-RPC 2.0 over HTTP** against
`http://localhost:8680/mcp`. There is **no Python package named
`mcp__mahavishnu`**.

### Quick health check

```bash
curl -sS http://localhost:8680/health | python -m json.tool
```

### Minimal Python client (no SDK dependency)

```python
"""Minimal Mahavishnu MCP client — JSON-RPC over HTTP."""

from __future__ import annotations

import json
from typing import Any

import httpx

MAHAVISHNU_MCP_URL = "http://localhost:8680/mcp"


async def call_mcp_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
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
    text_payload = envelope["result"]["content"][0]["text"]
    return json.loads(text_payload)
```

### End-to-end smoke test

Save this as `test_mahavishnu_pool.py` and run it against a live
`mahavishnu` server.

```python
#!/usr/bin/env python3
"""Smoke-test the Mahavishnu pool surface from Python."""

from __future__ import annotations

import asyncio

from test_mahavishnu_pool import call_mcp_tool


async def main() -> None:
    print("Checking pool health...")
    health = await call_mcp_tool("pool_health", {})
    print(f"  status: {health.get('status')}")

    print("Listing active pools...")
    pools = await call_mcp_tool("pool_list", {})
    print(f"  active pools: {len(pools)}")

    print("Routing a tiny prompt to the least-loaded pool...")
    # NOTE: `pool_route_execute` is NOT an MCP tool — it is a CLI
    # command. To route via the wire protocol, use the CLI subprocess
    # (or any of the 8 registered pool_* MCP tools above).
    import subprocess

    result = subprocess.run(
        ["mahavishnu", "pool", "route",
         "--prompt", "echo hello-from-mahavishnu",
         "--selector", "least_loaded"],
        capture_output=True, text=True, check=False,
    )
    print(f"  rc={result.returncode} stdout={result.stdout[:120]}")


if __name__ == "__main__":
    asyncio.run(main())
```

```bash
python test_mahavishnu_pool.py
```

This is the modern replacement for the older `from mcp__mahavishnu
import pool_spawn, pool_list, pool_health` snippet. The earlier form
was a fiction; the Python import path `mcp__mahavishnu` is the
FastMCP-tool-namespace token used inside an MCP-capable Claude
session, not a Python import.

______________________________________________________________________

## 3. Troubleshooting

### "Connection refused on http://localhost:8680"

The Mahavishnu MCP server is not running. Use the user's normal
launcher (launchd plist / `mahavishnu mcp start` / uv-managed
process — do **not** hardcode an absolute `python` path).

```bash
# Confirm Mahavishnu is reachable
curl -sS http://localhost:8680/health | python -m json.tool

# Check pool health once it is
mahavishnu pool health
```

The earlier draft's `cd /Users/les/Projects/mahavishnu && python -m mahavishnu`
works but breaks if the venv is moved (see memory
`mahavishnu-launcher-venv-discovery.md`); prefer the launcher.

### "Pool spawn fails with timeout"

Workers can take time to spin up, especially on first start
(embedding model warm-up, tmux session creation). Pass a longer
timeout to the spawn call.

```python
# NOTE: `pool_route_execute` is NOT an MCP tool — it is a CLI command.
# Use `subprocess.run(...)` (see the smoke-test above for the pattern)
# or pick a real MCP tool from the 8 listed above (e.g. `pool_list`).
result = subprocess.run(
    ["mahavishnu", "pool", "route",
     "--prompt", prompt, "--selector", "least_loaded", "--timeout", "60"],
    capture_output=True, text=True, check=False,
)
```

If `pool_scale` returns `NotImplementedError` (`{"status": "failed",
"error": "Pool does not support scaling (e.g., SessionBuddyPool is
fixed at 3 workers)"}`), the pool type is the constraint, not your
call — pick `mahavishnu` if you need to scale.

### "Unknown pool type 'kubernetes'"

The pool type string is wrong. Use one of the four canonical registered
names (`mahavishnu`, `session-buddy`, `runpod`, `pi`). The error
comes from `mahavishnu/pools/_registry.py::get_pool_factory` via the
manager dispatch. `gpu-handler` is NOT a registered pool type (see
the callout above — `GpuHandlerPool` exists but requires direct
instantiation, not registry dispatch).

### "No module named 'mahavishnu.mcp.pools'"

This error was real for the **2026-07-17** version of mcp-common. It
is not a current symptom — mcp-common has since shipped the relevant
modules. If you still see this, your mcp-common install is older than
the version Mahavishnu expects; reinstall with `uv sync` against the
current `mahavishnu/pyproject.toml` rather than guessing.

### "Mahavishnu tool count in docs does not match the live server"

Run:

```bash
python -c "from mahavishnu.core.skill_mcp_validator import KNOWN_TOOLS; print(sorted(t for t in KNOWN_TOOLS if 'pool' in t))"
```

If that returns more pool tools than this doc lists, the doc is
stale. Update the table at the top of section 1 to match — the live
`KNOWN_TOOLS` whitelist is the source of truth, not this doc.

______________________________________________________________________

## 4. Quick Reference — What Crackerjack Actually Uses

For cross-project observability and pattern queries, the **crackerjack
MCP server** (port 8676) has the wired-in tools. Use these instead
of the Mahavishnu pool surface:

```text
mcp__crackerjack__get_cross_project_git_dashboard
mcp__crackerjack__get_repository_health
mcp__crackerjack__clone_detect_ecosystem
mcp__crackerjack__get_cross_project_patterns
mcp__mahavishnu__get_health         # system-level, not pool-specific
mcp__mahavishnu__list_repos
mcp__mahavishnu__search_otel_traces
```

For a live inventory at any time:

```python
from mcp.client.streamable_http import streamablehttp_client

async with streamablehttp_client("http://localhost:8680/mcp") as (read, write, _):
    async with ClientSession(read, write) as session:
        await session.initialize()
        tools = await session.list_tools()
        print([t.name for t in tools.tools if "pool" in t.name])
```

______________________________________________________________________

## Related Docs

- `docs/MAHAVISHNU_POOL_INTEGRATION.md` — full ground-truth rewrite,
  pool types, worker backends, out-of-scope notes.
- `mahavishnu/CLAUDE.md` — Mahavishnu orchestration overview, port
  table, MCP tool profile tiers.
- `bodai/docs/memory/TOOL_ALIAS_INVENTORY.md` — canonical
  cross-component MCP-tool whitelist.
- `docs/audits/2026-09-09-crackerjack-docs-audit.md` — finding **F7**
  for the history this quickstart corrects.
