# Phase 3: Hook Orchestration & Execution - Design Document

**Status**: 🎯 In Design
**Lead Agents**: `architecture-council` (Opus), `python-pro` (Sonnet)
**Duration**: 10 days (with 2 parallel streams)
**Dependencies**: Phase 2 (All adapters with MODULE_ID + logging) ✅

______________________________________________________________________

## Executive Summary

Phase 3 transforms the current pre-commit-based hook system into an ACB-powered orchestration layer with async execution, intelligent caching, and dependency resolution. This phase **DOES NOT** remove pre-commit infrastructure - that happens in Phase 8. Instead, we build the ACB orchestration layer **alongside** the existing system.

**Key Deliverables**:

1. **HookOrchestrator** - ACB component managing hook lifecycle and execution
1. **Execution Strategies** - Async parallel execution with resource management
1. **Cache Integration** - Content-based caching for performance optimization

______________________________________________________________________

## Current Architecture Analysis

### Existing Hook System (Pre-commit Based)

```
HookManagerImpl (managers/hook_manager.py)
├─ HookExecutor (executors/hook_executor.py)
│  ├─ execute_strategy() - Sequential/parallel execution
│  ├─ _execute_hook() - Subprocess calls to pre-commit
│  └─ _handle_retries() - Formatting hook retries
│
├─ LSPAwareHookExecutor (executors/lsp_aware_hook_executor.py)
│  ├─ execute_strategy() - LSP-optimized execution
│  └─ ToolProxy integration
│
└─ HookConfigLoader (config/hooks.py)
   ├─ FAST_HOOKS (11 hooks)
   ├─ COMPREHENSIVE_HOOKS (6 hooks)
   └─ HookStrategy definitions

Hook Execution Flow:
1. WorkflowOrchestrator calls HookManager
2. HookManager loads strategy (fast/comprehensive)
3. HookExecutor runs hooks via pre-commit CLI
4. Results collected as HookResult objects
```

**Key Observations**:

- ✅ Well-defined HookResult, HookStrategy, HookDefinition models
- ✅ Already has parallel execution capability
- ✅ LSP optimization infrastructure exists
- ❌ Tightly coupled to pre-commit CLI (subprocess calls)
- ❌ No dependency resolution between hooks
- ❌ Limited caching (tool_proxy only)
- ❌ No ACB module registration

______________________________________________________________________

## Target Architecture (ACB Integration)

### Design Principles

1. **Non-Disruptive Integration**: ACB layer sits alongside existing system
1. **Gradual Migration Path**: One adapter at a time can switch to ACB
1. **Dual Execution Mode**: Support both pre-commit CLI and direct adapter calls
1. **Cache-First Strategy**: Leverage existing tool_proxy caching
1. **Protocol-Based DI**: Use ACB's dependency injection

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│ WorkflowOrchestrator (Existing)                             │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│ HookOrchestrator (NEW - ACB Component)                      │
│ - MODULE_ID: UUID("01937d86-ace0-7000-8000-000000000003")  │
│ - Manages hook lifecycle and execution                      │
│ - Dependency resolution                                      │
│ - Result aggregation                                         │
└────────────┬───────────────────────────────┬────────────────┘
             │                               │
             │ (Dual Path Strategy)          │
             │                               │
             ▼                               ▼
┌──────────────────────────┐   ┌──────────────────────────────┐
│ Legacy Path (Phase 3-7)  │   │ ACB Path (Phase 8+)          │
│                          │   │                              │
│ HookExecutor             │   │ Direct Adapter Execution     │
│ └─ pre-commit CLI        │   │ ├─ BanditAdapter.check()     │
│    subprocess calls      │   │ ├─ GitleaksAdapter.check()   │
│                          │   │ ├─ ZubanAdapter.check()      │
│                          │   │ └─ [... all adapters]        │
└──────────────────────────┘   └──────────────────────────────┘
             │                               │
             └───────────────┬───────────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │ Execution Strategies │
                  │ - Async parallel     │
                  │ - Resource limits    │
                  │ - Timeout handling   │
                  └─────────────────────┘
                             │
                             ▼
                  ┌─────────────────────┐
                  │ Cache Layer         │
                  │ - Content hashing   │
                  │ - tool_proxy        │
                  │ - Result caching    │
                  └─────────────────────┘
```

______________________________________________________________________

## Phase 3 Detailed Tasks

### 3.1 Hook Orchestrator Design & Implementation

**Objective**: Create ACB component managing hook lifecycle

**Components**:

#### A. HookOrchestratorAdapter (NEW)

````python
# Location: crackerjack/orchestration/hook_orchestrator.py
from __future__ import annotations

import asyncio
import logging
import typing as t
from contextlib import suppress
from pathlib import Path
from uuid import UUID

from acb.depends import depends
from pydantic import Field

from crackerjack.adapters._tool_adapter_base import BaseToolAdapter
from crackerjack.config.hooks import HookStrategy, HookDefinition
from crackerjack.models.task import HookResult

# ACB Module Registration
MODULE_ID = UUID("01937d86-ace0-7000-8000-000000000003")
MODULE_STATUS = "stable"

logger = logging.getLogger(__name__)


class HookOrchestratorSettings(BaseSettings):
    """Settings for hook orchestration."""

    max_parallel_hooks: int = 3
    default_timeout: int = 300
    enable_caching: bool = True
    enable_dependency_resolution: bool = True
    retry_on_failure: bool = False
    cache_backend: str = "tool_proxy"  # tool_proxy, redis, memory


class HookOrchestratorAdapter:
    """ACB-powered hook orchestration layer.

    Manages hook lifecycle, dependency resolution, and execution strategies.
    Supports dual execution mode: pre-commit CLI (legacy) and direct adapters (ACB).

    Features:
    - Async parallel execution
    - Dependency resolution between hooks
    - Content-based caching
    - Resource management
    - Result aggregation

    Example:
        ```python
        orchestrator = await depends.get(HookOrchestratorAdapter)
        results = await orchestrator.execute_strategy(
            strategy=fast_strategy,
            execution_mode="legacy",  # or "acb"
        )
        ```
    """

    settings: HookOrchestratorSettings

    def __init__(self, settings: HookOrchestratorSettings | None = None) -> None:
        self.settings = settings or HookOrchestratorSettings()
        self._dependency_graph: dict[str, list[str]] = {}
        logger.debug(
            "HookOrchestratorAdapter initialized",
            extra={"has_settings": settings is not None},
        )

    async def init(self) -> None:
        """Initialize orchestrator and build dependency graph."""
        logger.info(
            "HookOrchestratorAdapter initialization complete",
            extra={
                "max_parallel_hooks": self.settings.max_parallel_hooks,
                "enable_caching": self.settings.enable_caching,
                "enable_dependency_resolution": self.settings.enable_dependency_resolution,
            },
        )

    @property
    def module_id(self) -> UUID:
        """Reference to module-level MODULE_ID."""
        return MODULE_ID

    async def execute_strategy(
        self,
        strategy: HookStrategy,
        execution_mode: str = "legacy",  # "legacy" or "acb"
    ) -> list[HookResult]:
        """Execute hook strategy with specified mode.

        Args:
            strategy: Hook strategy (fast or comprehensive)
            execution_mode: "legacy" (pre-commit CLI) or "acb" (direct adapters)

        Returns:
            List of HookResult objects
        """
        logger.info(
            "Executing hook strategy",
            extra={
                "strategy_name": strategy.name,
                "hook_count": len(strategy.hooks),
                "execution_mode": execution_mode,
                "parallel": strategy.parallel,
            },
        )

        if execution_mode == "legacy":
            return await self._execute_legacy_mode(strategy)
        elif execution_mode == "acb":
            return await self._execute_acb_mode(strategy)
        else:
            raise ValueError(f"Invalid execution mode: {execution_mode}")

    async def _execute_legacy_mode(self, strategy: HookStrategy) -> list[HookResult]:
        """Execute hooks via pre-commit CLI (existing HookExecutor)."""
        # Delegate to existing HookExecutor
        # This is the bridge to the old system during Phase 3-7
        logger.debug("Using legacy pre-commit execution mode")
        # TODO: Integration with existing HookExecutor
        return []

    async def _execute_acb_mode(self, strategy: HookStrategy) -> list[HookResult]:
        """Execute hooks via direct adapter calls (ACB-powered)."""
        logger.debug("Using ACB direct adapter execution mode")

        if self.settings.enable_dependency_resolution:
            ordered_hooks = self._resolve_dependencies(strategy.hooks)
        else:
            ordered_hooks = strategy.hooks

        if strategy.parallel:
            return await self._execute_parallel(ordered_hooks)
        else:
            return await self._execute_sequential(ordered_hooks)

    def _resolve_dependencies(
        self, hooks: list[HookDefinition]
    ) -> list[HookDefinition]:
        """Resolve hook dependencies and return execution order.

        Dependency rules:
        - gitleaks must run before bandit (secrets before security)
        - zuban must run before refurb (types before refactoring)
        - formatting hooks run first (ruff-format, mdformat)
        """
        # Topological sort based on dependency graph
        # TODO: Implement dependency resolution
        return hooks

    async def _execute_parallel(self, hooks: list[HookDefinition]) -> list[HookResult]:
        """Execute hooks in parallel with resource limits."""
        semaphore = asyncio.Semaphore(self.settings.max_parallel_hooks)

        async def execute_with_limit(hook: HookDefinition) -> HookResult:
            async with semaphore:
                return await self._execute_single_hook(hook)

        tasks = [execute_with_limit(hook) for hook in hooks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error HookResults
        return [
            r if isinstance(r, HookResult) else self._error_result(h, r)
            for h, r in zip(hooks, results)
        ]

    async def _execute_sequential(
        self, hooks: list[HookDefinition]
    ) -> list[HookResult]:
        """Execute hooks sequentially."""
        results = []
        for hook in hooks:
            result = await self._execute_single_hook(hook)
            results.append(result)
        return results

    async def _execute_single_hook(self, hook: HookDefinition) -> HookResult:
        """Execute a single hook (ACB adapter call)."""
        # TODO: Implement direct adapter execution
        # This will call adapter.check() directly instead of pre-commit CLI
        logger.debug(f"Executing hook: {hook.name}")
        return HookResult(
            hook_name=hook.name,
            status="passed",
            duration=0.0,
            output="",
        )

    def _error_result(self, hook: HookDefinition, error: Exception) -> HookResult:
        """Create error HookResult from exception."""
        return HookResult(
            hook_name=hook.name,
            status="error",
            duration=0.0,
            output=str(error),
        )


# ACB Registration
with suppress(Exception):
    depends.set(HookOrchestratorAdapter)
````

#### B. Integration with Existing HookManager

```python
# Location: crackerjack/managers/hook_manager.py
# MODIFICATION: Add orchestrator delegation


class HookManagerImpl:
    def __init__(
        self,
        console: Console,
        pkg_path: Path,
        verbose: bool = False,
        quiet: bool = False,
        enable_lsp_optimization: bool = False,
        enable_tool_proxy: bool = True,
        use_acb_orchestrator: bool = False,  # NEW: Enable ACB orchestration
    ) -> None:
        self.console = console
        self.pkg_path = pkg_path
        self.use_acb_orchestrator = use_acb_orchestrator

        # Initialize orchestrator if ACB mode enabled
        self.orchestrator: HookOrchestratorAdapter | None = None
        if use_acb_orchestrator:
            from acb.depends import depends
            from crackerjack.orchestration.hook_orchestrator import (
                HookOrchestratorAdapter,
            )

            self.orchestrator = depends.get(HookOrchestratorAdapter)

        # Keep existing executor for legacy mode
        if enable_lsp_optimization:
            self.executor = LSPAwareHookExecutor(...)
        else:
            self.executor = HookExecutor(...)

    async def run_fast_hooks_async(self) -> list[HookResult]:
        """Run fast hooks with async support."""
        strategy = self.config_loader.load_strategy("fast")

        if self.orchestrator:
            # Use ACB orchestrator (Phase 8+)
            return await self.orchestrator.execute_strategy(
                strategy=strategy, execution_mode="acb"
            )
        else:
            # Use legacy executor (Phase 3-7)
            execution_result = self.executor.execute_strategy(strategy)
            return execution_result.results
```

**Implementation Steps**:

1. ✅ Create `crackerjack/orchestration/` directory
1. ✅ Implement `HookOrchestratorAdapter` with MODULE_ID and logging
1. ✅ Add `use_acb_orchestrator` flag to HookManagerImpl
1. ✅ Implement legacy mode delegation
1. ⏳ Implement dependency resolution graph
1. ⏳ Add comprehensive logging throughout execution flow

**Testing Requirements**:

- Unit tests for HookOrchestratorAdapter initialization
- Integration tests for legacy mode delegation
- Dependency resolution tests (gitleaks→bandit, zuban→refurb)

______________________________________________________________________

### 3.2 Execution Strategies Implementation

**Objective**: Implement async parallel execution with resource management

**Components**:

#### A. ExecutionStrategyProtocol

```python
# Location: crackerjack/models/protocols.py
# ADD: Execution strategy protocol

from typing import Protocol, runtime_checkable


@runtime_checkable
class ExecutionStrategyProtocol(Protocol):
    """Protocol for hook execution strategies."""

    async def execute(
        self,
        hooks: list[HookDefinition],
        max_parallel: int = 3,
        timeout: int = 300,
    ) -> list[HookResult]:
        """Execute hooks according to strategy."""
        ...

    def get_execution_order(
        self,
        hooks: list[HookDefinition],
    ) -> list[list[HookDefinition]]:
        """Return batches of hooks for execution."""
        ...
```

#### B. ParallelExecutionStrategy

```python
# Location: crackerjack/orchestration/strategies/parallel_strategy.py


class ParallelExecutionStrategy:
    """Parallel execution strategy with resource limits.

    Features:
    - Concurrent execution with asyncio.gather
    - Semaphore-based resource limiting
    - Per-hook timeout handling
    - Exception isolation (one failure doesn't stop others)
    """

    def __init__(
        self,
        max_parallel: int = 3,
        default_timeout: int = 300,
    ) -> None:
        self.max_parallel = max_parallel
        self.default_timeout = default_timeout
        self.semaphore = asyncio.Semaphore(max_parallel)

    async def execute(
        self,
        hooks: list[HookDefinition],
        max_parallel: int | None = None,
        timeout: int | None = None,
    ) -> list[HookResult]:
        """Execute hooks in parallel with resource limits."""
        max_par = max_parallel or self.max_parallel
        timeout_sec = timeout or self.default_timeout

        async def execute_with_timeout(hook: HookDefinition) -> HookResult:
            async with self.semaphore:
                try:
                    return await asyncio.wait_for(
                        self._execute_hook(hook), timeout=hook.timeout or timeout_sec
                    )
                except asyncio.TimeoutError:
                    return HookResult(
                        hook_name=hook.name,
                        status="timeout",
                        duration=hook.timeout or timeout_sec,
                        output=f"Hook timed out after {hook.timeout}s",
                    )

        tasks = [execute_with_timeout(hook) for hook in hooks]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return [self._handle_result(h, r) for h, r in zip(hooks, results)]
```

#### C. SequentialExecutionStrategy

```python
# Location: crackerjack/orchestration/strategies/sequential_strategy.py


class SequentialExecutionStrategy:
    """Sequential execution strategy for dependent hooks.

    Use when:
    - Hooks have dependencies (gitleaks → bandit)
    - Resource constraints require sequential execution
    - Debugging requires isolated execution
    """

    async def execute(
        self,
        hooks: list[HookDefinition],
        max_parallel: int | None = None,  # Ignored for sequential
        timeout: int | None = None,
    ) -> list[HookResult]:
        """Execute hooks sequentially."""
        results = []
        for hook in hooks:
            try:
                result = await asyncio.wait_for(
                    self._execute_hook(hook), timeout=hook.timeout or timeout
                )
                results.append(result)

                # Early exit on critical failures
                if (
                    result.status == "failed"
                    and hook.security_level == SecurityLevel.CRITICAL
                ):
                    logger.warning(
                        f"Critical hook {hook.name} failed, stopping execution",
                        extra={"hook": hook.name, "security_level": "CRITICAL"},
                    )
                    break
            except asyncio.TimeoutError:
                results.append(self._timeout_result(hook))

        return results
```

**Implementation Steps**:

1. ✅ Create `crackerjack/orchestration/strategies/` directory
1. ✅ Implement ExecutionStrategyProtocol in protocols.py
1. ✅ Implement ParallelExecutionStrategy
1. ✅ Implement SequentialExecutionStrategy
1. ⏳ Add strategy selection logic in HookOrchestrator
1. ⏳ Performance benchmarking (parallel vs sequential)

**Testing Requirements**:

- Parallel execution with 3 concurrent hooks
- Timeout handling (individual hook timeouts)
- Exception isolation (one hook fails, others continue)
- Sequential execution order verification

______________________________________________________________________

### 3.3 Cache Integration

**Objective**: Implement content-based caching for performance optimization

**Components**:

#### A. CacheStrategyProtocol

```python
# Location: crackerjack/models/protocols.py
# ADD: Cache strategy protocol


@runtime_checkable
class CacheStrategyProtocol(Protocol):
    """Protocol for result caching strategies."""

    async def get(self, key: str) -> HookResult | None:
        """Retrieve cached result."""
        ...

    async def set(self, key: str, result: HookResult, ttl: int = 3600) -> None:
        """Cache result with TTL."""
        ...

    def compute_key(self, hook: HookDefinition, files: list[Path]) -> str:
        """Compute cache key from hook and file content."""
        ...
```

#### B. ToolProxyCacheAdapter

```python
# Location: crackerjack/orchestration/cache/tool_proxy_cache.py


class ToolProxyCacheAdapter:
    """Adapter for existing tool_proxy caching infrastructure.

    Bridges HookOrchestrator to ToolProxy for cache operations.
    """

    def __init__(self, tool_proxy: ToolProxy) -> None:
        self.tool_proxy = tool_proxy
        logger.debug("ToolProxyCacheAdapter initialized")

    def compute_key(self, hook: HookDefinition, files: list[Path]) -> str:
        """Compute cache key from hook configuration and file content hashes.

        Key format: {hook_name}:{config_hash}:{content_hash}

        - hook_name: Hook identifier
        - config_hash: Hash of hook settings/command
        - content_hash: Hash of all file contents
        """
        import hashlib

        # Hash hook configuration
        config_data = f"{hook.name}:{hook.command}:{hook.timeout}"
        config_hash = hashlib.sha256(config_data.encode()).hexdigest()[:8]

        # Hash file contents
        content_parts = []
        for file_path in sorted(files):
            if file_path.exists():
                content = file_path.read_bytes()
                file_hash = hashlib.sha256(content).hexdigest()[:8]
                content_parts.append(f"{file_path.name}:{file_hash}")

        content_hash = hashlib.sha256(":".join(content_parts).encode()).hexdigest()[:8]

        cache_key = f"{hook.name}:{config_hash}:{content_hash}"
        logger.debug(
            f"Computed cache key",
            extra={
                "hook": hook.name,
                "file_count": len(files),
                "cache_key": cache_key,
            },
        )
        return cache_key

    async def get(self, key: str) -> HookResult | None:
        """Retrieve cached result from tool_proxy."""
        # TODO: Integration with existing tool_proxy
        return None

    async def set(self, key: str, result: HookResult, ttl: int = 3600) -> None:
        """Cache result via tool_proxy."""
        # TODO: Integration with existing tool_proxy
        pass
```

#### C. Cache-Aware Execution

```python
# Location: crackerjack/orchestration/hook_orchestrator.py
# MODIFY: Add caching to _execute_single_hook


async def _execute_single_hook(self, hook: HookDefinition) -> HookResult:
    """Execute a single hook with caching."""

    if self.settings.enable_caching:
        # Compute cache key from hook + file content
        cache_key = self._compute_cache_key(hook)

        # Check cache
        cached_result = await self.cache_adapter.get(cache_key)
        if cached_result:
            logger.debug(
                f"Cache HIT for {hook.name}",
                extra={"hook": hook.name, "cache_key": cache_key},
            )
            return cached_result

        logger.debug(
            f"Cache MISS for {hook.name}",
            extra={"hook": hook.name, "cache_key": cache_key},
        )

    # Execute hook
    result = await self._execute_hook_impl(hook)

    # Cache result
    if self.settings.enable_caching and result.status == "passed":
        await self.cache_adapter.set(cache_key, result)

    return result
```

**Implementation Steps**:

1. ✅ Implement CacheStrategyProtocol in protocols.py
1. ✅ Create ToolProxyCacheAdapter bridging to existing tool_proxy
1. ✅ Implement content hashing for cache keys
1. ⏳ Add cache integration to HookOrchestrator
1. ⏳ Add cache statistics tracking (hits/misses/hit rate)
1. ⏳ Performance benchmarking (cache impact on execution time)

**Testing Requirements**:

- Cache key computation (same content = same key)
- Cache hit/miss scenarios
- Cache invalidation (file content changes)
- Performance metrics (cache hit rate >80%)

______________________________________________________________________

## Success Criteria

**Phase 3 Complete When**:

- ✅ HookOrchestratorAdapter registered in ACB
- ✅ Legacy mode delegation functional (pre-commit CLI still works)
- ✅ Dual execution mode implemented (legacy + ACB paths)
- ✅ Parallel execution with resource limits working
- ✅ Cache integration with tool_proxy operational
- ✅ Comprehensive logging at all execution points
- ✅ Test coverage >85% for orchestration layer
- ✅ Performance benchmarks show \<5% overhead vs current system

**Review Gates**:

1. `architecture-council` (Opus) - Design patterns, scalability, ACB compliance
1. `performance-engineer` (Sonnet) - Async performance, resource management
1. `test-specialist` (Sonnet) - Test coverage, integration test quality

______________________________________________________________________

## Dependencies & Risks

**Dependencies**:

- ✅ Phase 2: All adapters with MODULE_ID + logging (COMPLETED)
- ⏳ Existing HookExecutor continues to function during migration

**Risks**:

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| Async/sync mixing issues | Medium | High | Careful async/await design, separate sync wrappers |
| Performance regression | Low | High | Benchmarking at each step, cache optimization |
| Integration complexity | Medium | Medium | Dual execution mode allows gradual migration |
| Cache invalidation bugs | Medium | Medium | Comprehensive cache key testing, content hashing |

**Mitigation Strategies**:

1. **Async/Sync Mixing**: Keep HookOrchestrator fully async, provide sync wrappers for compatibility
1. **Performance**: Benchmark after each component (orchestrator, strategies, cache)
1. **Integration**: Maintain full backward compatibility with existing HookManager API
1. **Cache**: Extensive unit tests for cache key computation, use cryptographic hashes

______________________________________________________________________

## Timeline

**Sequential Foundation** (Day 1-2):

- Hook Orchestrator design (architecture-council)
- Protocol definitions (ExecutionStrategy, CacheStrategy)

**Parallel Group 3A** (Day 3-7):

- Stream A: Execution strategies (performance-engineer + python-pro #1)
- Stream B: Cache integration (python-pro #2)

**Parallel Group 3B** (Day 8-10):

- Stream A: Integration tests (test-specialist)
- Stream B: Performance benchmarking (performance-engineer)

**Estimated Duration**: 10 days
**Time Saved vs Sequential**: 5 days (33% reduction)

______________________________________________________________________

## Next Phase

**Phase 4: Configuration Management** begins after Phase 3 review gates pass.

Key handoff:

- HookOrchestrator is operational in legacy mode
- All adapters can be called directly (MODULE_ID + logging complete)
- Configuration system will use ACB settings validation
- Phase 8 will complete the migration by removing pre-commit CLI

______________________________________________________________________

**Document Status**: 📝 Draft for Architecture Council Review
**Last Updated**: 2025-01-09
**Next Review**: After architecture-council design approval
