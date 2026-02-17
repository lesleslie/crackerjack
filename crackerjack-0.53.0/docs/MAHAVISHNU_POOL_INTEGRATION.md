# Mahavishnu Pool Integration for Crackerjack Scanning

## Overview

Mahavishnu provides comprehensive worker pool orchestration that can dramatically accelerate Crackerjack's quality scanning workflow. By distributing slow tools (refurb, complexipy, skylos) across multiple workers, we can achieve 3-4x speedup on multi-core systems.

______________________________________________________________________

## Mahavishnu Pool Capabilities

### Available Pool Types

1. **MahavishnuPool** (Local workers)

   - Direct worker management by Mahavishnu
   - Workers run in local process context
   - Use cases: Local development, low-latency tasks, debugging
   - Worker types: TerminalAIWorker (Qwen/Claude), ContainerWorker (Docker)

1. **SessionBuddyPool** (Memory-augmented workers)

   - Workers with access to session-buddy memory
   - Ideal for tasks requiring context/knowledge retrieval
   - Use cases: Complex analysis, pattern recognition

1. **KubernetesPool** (Distributed workers)

   - Workers running in Kubernetes pods
   - Scales to hundreds of workers
   - Use cases: Large-scale scanning, CI/CD pipelines

### Pool Management Tools (9 MCP Tools)

```python
# Pool lifecycle management
pool_spawn()           # Create new pool
pool_close()           # Close specific pool
pool_close_all()       # Close all pools

# Task execution
pool_execute()         # Execute on specific pool
pool_route_execute()   # Auto-route to best pool

# Monitoring
pool_list()            # List active pools
pool_monitor()         # Get pool metrics
pool_health()          # Health status
pool_scale()           # Adjust worker count

# Advanced features
pool_search_memory()   # Search memory across pools
```

### Pool Configuration

```python
PoolConfig(
    name="quality-scanners",
    pool_type="mahavishnu",      # or "session-buddy", "kubernetes"
    min_workers=2,               # Minimum workers (always running)
    max_workers=10,              # Maximum workers (scale up as needed)
    worker_type="terminal-qwen", # or "terminal-claude", "container"
)
```

______________________________________________________________________

## Integration Architecture

### Crackerjack + Mahavishnu Integration

```
┌─────────────────────────────────────────────────────────────┐
│ Crackerjack Hook Executor                                   │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. File Scanner (git-diff/marker-based)                   │
│     └─> Detects changed files                              │
│                                                             │
│  2. Task Distributor                                        │
│     └─> Splits files into chunks                            │
│                                                             │
│  3. Mahavishnu Pool Manager (via MCP)                       │
│     ├─> pool_spawn("quality-scanners", max_workers=8)       │
│     └─> pool_execute(pool_id, task)                         │
│                                                             │
│  ┌───────────────────────────────────────────────┐         │
│  │  Mahavishnu Worker Pool                        │         │
│  ├───────────────────────────────────────────────┤         │
│  │  Worker 1: refurb (files 1-10)               │         │
│  │  Worker 2: complexipy (files 11-20)          │         │
│  │  Worker 3: skylos (files 21-30)              │         │
│  │  Worker 4: ruff (files 31-40)                │         │
│  │  Worker 5: refurb (files 41-50)              │         │
│  │  Worker 6: vulture (files 51-60)             │         │
│  │  Worker 7: semgrep (files 61-70)            │         │
│  │  Worker 8: gitleaks (all files)             │         │
│  └───────────────────────────────────────────────┘         │
│                                                             │
│  4. Result Aggregator                                       │
│     └─> Collects results, generates report                 │
└─────────────────────────────────────────────────────────────┘
```

______________________________________________________________________

## Implementation Plan

### Phase 1: Basic Pool Integration (2-3 hours)

**Goal**: Run slow tools in parallel using mahavishnu pools

#### 1.1 Create Crackerjack Pool Client

```python
# crackerjack/services/pool_client.py

import asyncio
from pathlib import Path
from typing import Any

class CrackerjackPoolClient:
    """Client for Mahavishnu pool execution."""

    def __init__(self, mcp_server_url: str = "http://localhost:8680"):
        self.mcp_url = mcp_server_url
        self.pool_id: str | None = None

    async def spawn_scanner_pool(
        self,
        min_workers: int = 2,
        max_workers: int = 8
    ) -> str:
        """Spawn a worker pool for quality scanning.

        Args:
            min_workers: Minimum workers to spawn
            max_workers: Maximum workers for scaling

        Returns:
            Pool ID for subsequent operations
        """
        # Call mahavishnu MCP tool: pool_spawn
        result = await self._call_mcp_tool(
            "pool_spawn",
            pool_type="mahavishnu",
            name="crackerjack-quality-scanners",
            min_workers=min_workers,
            max_workers=max_workers,
            worker_type="terminal-qwen"
        )

        if result.get("status") == "created":
            self.pool_id = result["pool_id"]
            return self.pool_id
        else:
            raise RuntimeError(f"Failed to spawn pool: {result}")

    async def execute_tool_scan(
        self,
        tool_name: str,
        files: list[Path],
        timeout: int = 300
    ) -> dict[str, Any]:
        """Execute a quality tool on specific files.

        Args:
            tool_name: Tool to run (refurb, complexipy, skylos, etc.)
            files: Files to scan
            timeout: Timeout in seconds

        Returns:
            Tool execution result
        """
        if not self.pool_id:
            raise RuntimeError("Pool not spawned. Call spawn_scanner_pool() first.")

        # Build command for tool
        cmd = self._build_tool_command(tool_name, files)

        # Execute via mahavishnu pool
        result = await self._call_mcp_tool(
            "pool_execute",
            pool_id=self.pool_id,
            prompt=f"Execute: {' '.join(map(str, cmd))}",
            timeout=timeout
        )

        return result

    def _build_tool_command(self, tool_name: str, files: list[Path]) -> list[str]:
        """Build command line for tool execution."""
        commands = {
            "refurb": ["refurb", *map(str, files)],
            "complexipy": ["complexipy", *map(str, files), "--path", "."],
            "skylos": ["skylos", *map(str, files)],
            "vulture": ["vulture", *map(str, files)],
            "ruff": ["ruff", "check", *map(str, files)],
        }
        return commands.get(tool_name, [])

    async def _call_mcp_tool(self, tool_name: str, **kwargs) -> dict[str, Any]:
        """Call Mahavishnu MCP tool."""
        # Implementation uses MCP client to call tools
        # This is simplified - actual implementation would use mcp-client
        pass
```

#### 1.2 Update Hook Executor

```python
# crackerjack/hooks/pool_based_hooks.py

from crackerjack.services.pool_client import CrackerjackPoolClient

async def run_refurb_with_pool(options) -> HookResult:
    """Run refurb on changed files using mahavishnu pool."""
    # Get changed files
    scanner = IncrementalScanner(options.pkg_path)
    files = scanner.get_files_to_scan("refurb")

    if not files:
        return HookResult(success=True, stdout="No changes to scan")

    # Spawn pool if needed
    client = CrackerjackPoolClient()
    if not client.pool_id:
        await client.spawn_scanner_pool(max_workers=8)

    # Execute scan in pool
    result = await client.execute_tool_scan("refurb", files)

    return HookResult(
        success=result.get("status") == "completed",
        stdout=result.get("output", ""),
        stderr=result.get("error", ""),
        exit_code=result.get("exit_code", 0)
    )
```

### Phase 2: Pool Optimization (2-3 hours)

**Goal**: Optimize pool usage and implement smart routing

#### 2.1 Tool-to-Worker Routing

```python
# crackerjack/services/pool_router.py

class PoolRouter:
    """Route tools to optimal workers."""

    TOOL_WORKER_MAP = {
        # Heavy CPU tools → dedicated workers
        "refurb": "heavy-cpu-worker",
        "complexipy": "heavy-cpu-worker",
        "skylos": "fast-worker",  # Rust-based, already fast

        # Light tools → shared workers
        "ruff": "fast-worker",
        "vulture": "fast-worker",
        "mypy": "fast-worker",

        # Security tools → dedicated workers (isolation)
        "gitleaks": "security-worker",
        "semgrep": "security-worker",
    }

    async def route_to_best_pool(
        self,
        tool_name: str,
        files: list[Path]
    ) -> str:
        """Route tool to best pool using pool_route_execute."""
        worker_type = self.TOOL_WORKER_MAP.get(tool_name, "fast-worker")

        result = await self._call_mcp_tool(
            "pool_route_execute",
            tool_name=tool_name,
            worker_type=worker_type,
            files=files
        )

        return result["pool_id"]
```

#### 2.2 Auto-scaling Based on Load

```python
# crackerjack/services/pool_scaler.py

class PoolScaler:
    """Auto-scale pool workers based on load."""

    async def monitor_and_scale(self, pool_id: str):
        """Monitor pool metrics and scale as needed."""
        while True:
            # Get pool metrics
            metrics = await self._call_mcp_tool("pool_monitor", pool_id=pool_id)

            # Scale up if backlog > 10 tasks
            if metrics["pending_tasks"] > 10:
                await self._call_mcp_tool(
                    "pool_scale",
                    pool_id=pool_id,
                    worker_count=metrics["max_workers"] + 2
                )

            # Scale down if idle > 5 minutes
            elif metrics["idle_time"] > 300:
                await self._call_mcp_tool(
                    "pool_scale",
                    pool_id=pool_id,
                    worker_count=max(2, metrics["min_workers"])
                )

            await asyncio.sleep(30)
```

### Phase 3: Memory Integration (2-3 hours)

**Goal**: Use session-buddy memory for smarter scanning

```python
# crackerjack/services/memory_aware_scanner.py

class MemoryAwareScanner:
    """Scanner that learns from past results."""

    async def scan_with_memory(
        self,
        tool_name: str,
        files: list[Path]
    ) -> dict[str, Any]:
        """Scan files using memory to skip known-good files."""

        # Search memory for past results
        memory_results = await self._call_mcp_tool(
            "pool_search_memory",
            pool_id=self.pool_id,
            query={
                "tool": tool_name,
                "files": [str(f) for f in files]
            }
        )

        # Filter out files that passed recently
        known_good = [
            f for f, result in memory_results.items()
            if result["status"] == "passed" and
            result["timestamp"] > time.time() - 86400  # 24 hours
        ]

        files_to_scan = [f for f in files if f not in known_good]

        if not files_to_scan:
            return {"status": "skipped", "reason": "All files known good"}

        # Execute scan on remaining files
        return await self.execute_tool_scan(tool_name, files_to_scan)
```

______________________________________________________________________

## Performance Estimates

### Without Pools (Current)

| Scenario | Time | Bottleneck |
|----------|------|------------|
| Full scan (all tools) | 10+ min | Sequential execution |
| Incremental scan | 3-5 min | Still sequential per tool |
| Publish workflow | 10+ min | Full scan, sequential |

### With Mahavishnu Pools (8 workers)

| Scenario | Time | Speedup | Bottleneck |
|----------|------|---------|------------|
| Full scan (all tools) | 3-4 min | 2.5-3x | Tool execution time |
| Incremental scan | 30-60s | 3-6x | File I/O |
| Publish workflow | 3-4 min | 2.5-3x | Tool execution time |

### With Incremental + Pools (Recommended)

| Scenario | Time | Total Speedup |
|----------|------|---------------|
| Small commit (5-10 files) | 10-20s | 30-60x faster |
| Medium commit (10-50 files) | 20-40s | 15-30x faster |
| Large commit (50+ files) | 2-3 min | 3-5x faster |
| Publish workflow (full scan) | 3-4 min | 2.5-3x faster |

______________________________________________________________________

## Configuration

### Crackerjack Configuration

```yaml
# .crackerjack.yaml

pool_scanning:
  # Enable Mahavishnu pool integration
  enabled: true

  # Mahavishnu MCP server URL
  mcp_server_url: "http://localhost:8680"

  # Pool configuration
  pool:
    name: "crackerjack-quality-scanners"
    pool_type: "mahavishnu"
    min_workers: 2
    max_workers: 8
    worker_type: "terminal-qwen"

  # Tools to run in pools
  pooled_tools:
    - refurb
    - complexipy
    - skylos
    - semgrep
    - gitleaks

  # Tools to run locally (fast tools)
  local_tools:
    - ruff
    - vulture
    - codespell
    - check-jsonschema

  # Auto-scaling configuration
  autoscaling:
    enabled: true
    scale_up_threshold: 10    # Pending tasks
    scale_down_threshold: 300  # Idle seconds
    max_workers: 16

  # Memory integration
  memory:
    enabled: true
    cache_duration: 86400  # 24 hours
```

______________________________________________________________________

## Benefits

### 1. Dramatic Speed Improvements

- Small commits: 10+ min → 10-20s (**30-60x faster**)
- Medium commits: 10+ min → 20-40s (**15-30x faster**)
- Publish workflows: 10+ min → 3-4 min (**2.5-3x faster**)

### 2. Better Resource Utilization

- Parallel tool execution across all CPU cores
- Smart routing based on tool characteristics
- Auto-scaling based on actual load

### 3. Improved Developer Experience

- Faster feedback on commits
- Less waiting for quality gates
- Can run comprehensive checks more frequently

### 4. Scalability

- KubernetesPool can scale to hundreds of workers
- Suitable for large monorepos
- CI/CD pipeline integration

### 5. Fault Isolation

- Worker crashes don't affect other tools
- Automatic retry and recovery
- Detailed error tracking

______________________________________________________________________

## Comparison: Incremental vs Pools vs Combined

| Approach | Implementation Time | Speedup | Complexity | Best For |
|----------|-------------------|---------|------------|----------|
| **Incremental only** | 2-3 hours | 10-20x | Low | Small teams, simple workflows |
| **Pools only** | 2-3 hours | 2.5-3x | Medium | Large codebases, CI/CD |
| **Combined** | 4-6 hours | 30-60x | High | **All scenarios (recommended)** |

______________________________________________________________________

## Open Questions

1. **Mahavishnu Availability**: Is mahavishnu running in all environments? (local, CI, docker)
1. **Pool Lifecycle**: When to spawn/close pools? (per-session, per-scan, persistent daemon?)
1. **Worker Type**: Which worker type is best? (qwen, claude, container?)
1. **Memory Integration**: How to handle cache invalidation across branches?
1. **Error Handling**: What to do if pool crashes mid-scan?
1. **Cost**: Are there resource costs we should monitor?

______________________________________________________________________

## Next Steps

1. **✅ Document Ready**: This integration plan is ready for implementation
1. **🔄 Wait for Mahavishnu**: User restarting mahavishnu MCP server
1. **📋 Consultant Review**: Get feedback on approach and priorities
1. **🚀 Start with Phase 1**: Basic pool integration once mahavishnu is available
1. **📊 Measure & Tune**: Benchmark performance and optimize

______________________________________________________________________

**Prepared by**: Claude Sonnet 4.5
**Date**: 2026-02-13
**Related Docs**:

- `docs/INTEGRAL_SCANNING_OPTIONS.md` - Incremental scanning approaches
- `docs/plans/` - Implementation plans
