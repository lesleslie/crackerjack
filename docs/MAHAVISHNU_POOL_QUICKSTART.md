# Mahavishnu Pool Integration - Quick Start Guide

## Current Status

✅ **Mahavishnu MCP Server**: Connected and healthy
✅ **Pool Tools Available**: 9 tools registered
✅ **mcp-common upgraded**: 0.7.0 → 0.9.0 (includes websocket support)
⚠️ **MCP Server restart needed**: To pick up the new mcp-common version

## Next Steps

### 1. Restart Mahavishnu MCP Server

The mahavishnu MCP server needs to be restarted to load the upgraded `mcp-common` package:

```bash
# Stop the current mahavishnu server
pkill -f mahavishnu

# Restart it (use your normal startup method)
# For example:
cd /Users/les/Projects/mahavishnu
python -m mahavishnu
```

Or if you're using a specific startup script/service:
```bash
# Your normal startup command
```

### 2. Verify Pool Tools

After restart, verify the pool tools work:

```python
# Via MCP (from Claude Code or other MCP client)
from mcp__mahavishnu import pool_spawn, pool_list, pool_health

# Check health
health = await pool_health()
print(f"Status: {health['status']}")

# Spawn a test pool
pool = await pool_spawn(
    pool_type="mahavishnu",
    name="test-pool",
    min_workers=1,
    max_workers=2,
    worker_type="terminal-qwen"
)
print(f"Pool ID: {pool['pool_id']}")

# List pools
pools = await pool_list()
print(f"Active pools: {pools}")
```

### 3. Test Pool Execution

```python
# Execute a task in the pool
result = await pool_execute(
    pool_id=pool['pool_id'],
    prompt="echo 'Hello from worker!'",
    timeout=30
)
print(f"Result: {result['output']}")
```

---

## Architecture Overview

### Pool Types Available

1. **MahavishnuPool** (Local)
   - Direct worker management
   - Best for: Local development, testing
   - Workers: `terminal-qwen`, `terminal-claude`, `container`

2. **SessionBuddyPool** (Memory-augmented)
   - Workers with session-buddy memory access
   - Best for: Complex analysis, pattern recognition
   - Workers: Same as above, plus memory integration

3. **KubernetesPool** (Distributed)
   - Kubernetes pod-based workers
   - Best for: Large-scale scanning, CI/CD
   - Workers: Container-based

### Pool Management Tools

| Tool | Purpose | Example |
|------|---------|---------|
| `pool_spawn` | Create new pool | `pool_spawn("mahavishnu", "my-pool", 1, 8)` |
| `pool_execute` | Execute task on specific pool | `pool_execute(pool_id, "command")` |
| `pool_route_execute` | Auto-route to best pool | `pool_route_execute("command", "least-loaded")` |
| `pool_list` | List all active pools | `pool_list()` |
| `pool_monitor` | Get pool metrics | `pool_monitor(pool_id)` |
| `pool_health` | System health check | `pool_health()` |
| `pool_scale` | Adjust worker count | `pool_scale(pool_id, worker_count=16)` |
| `pool_close` | Close specific pool | `pool_close(pool_id)` |
| `pool_close_all` | Close all pools | `pool_close_all()` |
| `pool_search_memory` | Search memory across pools | `pool_search_memory(query)` |

---

## Crackerjack Integration Pattern

### Basic Pattern (No Pools)

```python
# Current: Sequential execution
for tool in ["refurb", "complexipy", "skylos"]:
    result = run_tool(tool, files)
    print(result)
```

### With Pools (Parallel Execution)

```python
# With mahavishna pools: Parallel execution
import asyncio

async def scan_with_pools(files):
    # Spawn pool
    pool = await pool_spawn(
        pool_type="mahavishnu",
        name="quality-scanners",
        min_workers=2,
        max_workers=8
    )

    # Split files into chunks
    chunks = split_files(files, chunk_size=10)

    # Execute tools in parallel
    tasks = []
    for tool in ["refurb", "complexipy", "skylos"]:
        for chunk in chunks:
            task = pool_execute(
                pool_id=pool['pool_id'],
                prompt=f"{tool} {' '.join(chunk)}",
                timeout=300
            )
            tasks.append(task)

    # Wait for all tasks
    results = await asyncio.gather(*tasks)

    # Close pool
    await pool_close(pool['pool_id'])

    return results
```

---

## Performance Expectations

### Without Pools (Current)
| Scenario | Time |
|----------|------|
| Full scan (all tools) | 10+ min |
| Incremental scan | 3-5 min |
| Small commit | 3-5 min |

### With Pools (8 Workers)
| Scenario | Time | Speedup |
|----------|------|---------|
| Full scan (all tools) | 3-4 min | 2.5-3x |
| Incremental scan | 30-60s | 3-6x |
| Small commit | 10-20s | 10-20x |

### With Incremental + Pools (Recommended)
| Scenario | Time | Total Speedup |
|----------|------|---------------|
| Small commit (5-10 files) | 10-20s | 30-60x |
| Medium commit (10-50 files) | 20-40s | 15-30x |
| Large commit (50+ files) | 2-3 min | 3-5x |

---

## Configuration Example

```yaml
# .crackerjack.yaml

pool_scanning:
  # Enable Mahavishnu pool integration
  enabled: true

  # Pool configuration
  pool:
    name: "crackerjack-quality-scanners"
    pool_type: "mahavishnu"
    min_workers: 2
    max_workers: 8
    worker_type: "terminal-qwen"
    auto_scale: true

  # Tools to run in pools
  pooled_tools:
    - refurb
    - complexipy
    - skylos
    - semgrep
    - gitleaks

  # Incremental scanning (combine with pools)
  incremental:
    enabled: true
    use_git_diff: true
    fallback_to_full: true
    full_scan_interval_days: 7

  # Auto-scaling
  autoscaling:
    enabled: true
    scale_up_threshold: 10     # Pending tasks
    scale_down_threshold: 300   # Idle seconds
    max_workers: 16
```

---

## Troubleshooting

### Issue: "No module named 'mahavishnu.mcp.pools'"
**Cause**: Mahavishnu MCP server started before mcp-common was upgraded
**Fix**: Restart mahavishnu MCP server
```bash
pkill -f mahavishnu
# Restart with your normal startup command
```

### Issue: "No module named 'mcp_common.websocket'"
**Cause**: Old version of mcp-common (< 0.9.0)
**Fix**: Upgrade mcp-common
```bash
pip install --upgrade mcp-common==0.9.0
```

### Issue: Pool spawn fails with timeout
**Cause**: Workers taking too long to initialize
**Fix**: Increase timeout or check worker availability
```python
pool = await pool_spawn(
    ...,
    timeout=60  # Increase from default 30
)
```

---

## Quick Test Script

Save this as `test_pools.py`:

```python
#!/usr/bin/env python3
"""Test mahavishnu pool integration."""

import asyncio
from mcp__mahavishnu import (
    pool_health,
    pool_spawn,
    pool_execute,
    pool_list,
    pool_close,
)

async def main():
    print("🔍 Checking mahavishnu health...")
    health = await pool_health()
    print(f"Status: {health['status']}")
    print(f"Active pools: {health['pools_active']}")

    print("\n🚀 Spawning test pool...")
    pool = await pool_spawn(
        pool_type="mahavishnu",
        name="test-pool",
        min_workers=1,
        max_workers=2,
        worker_type="terminal-qwen"
    )
    print(f"✅ Pool spawned: {pool['pool_id']}")

    print("\n📋 Listing pools...")
    pools = await pool_list()
    print(f"Active pools: {len(pools)}")
    for p in pools:
        print(f"  - {p['name']} ({p['pool_id']})")

    print("\n🧪 Executing test command...")
    result = await pool_execute(
        pool_id=pool['pool_id'],
        prompt="echo 'Hello from Mahavishnu pool!'",
        timeout=30
    )
    print(f"Output: {result.get('output', 'No output')}")

    print("\n🧹 Closing pool...")
    await pool_close(pool['pool_id'])
    print("✅ Pool closed")

    print("\n✅ All tests passed!")

if __name__ == "__main__":
    asyncio.run(main())
```

Run with:
```bash
python test_pools.py
```

---

## Next Steps After Restart

1. **✅ Verify pool tools work**: Run the test script above
2. **✅ Spawn a test pool**: Confirm pool creation works
3. **✅ Execute test command**: Verify workers can run commands
4. **📋 Implement Crackerjack integration**:
   - Create `crackerjack/services/pool_client.py`
   - Add pool-based hooks
   - Update configuration
5. **📊 Benchmark performance**: Measure speedup with real workloads
6. **🚀 Production rollout**: Enable for all workflows

---

**Status**: Ready for testing after mahavishnu restart
**Last Updated**: 2026-02-13
**Dependencies**: mahavishnu MCP server, mcp-common >= 0.9.0
