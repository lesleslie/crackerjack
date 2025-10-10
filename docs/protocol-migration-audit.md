# Protocol Migration Audit & Implementation Plan

## Executive Summary

**Goal**: Complete migration to protocol-based dependency injection across all orchestration components.

**Current Status**: Partial migration - protocols defined but many concrete imports remain.

**Timeline**: 3-5 days

**Risk Level**: Medium (refactoring only, no functionality changes)

---

## Phase 1: Current State Analysis

### Existing Protocols (Complete - 37 protocols)

Located in `crackerjack/models/protocols.py`:

#### Infrastructure Protocols
1. `CommandRunner` - Command execution interface
2. `ConsoleInterface` - Console I/O
3. `FileSystemInterface` - Basic file operations
4. `FileSystemServiceProtocol` - Extended file operations
5. `GitInterface` - Git operations
6. `LoggerProtocol` - Structured logging
7. `ConfigManagerProtocol` - Configuration management

#### Manager Protocols
8. `HookManager` - Hook execution
9. `SecurityAwareHookManager` - Hook manager with security features
10. `TestManagerProtocol` - Test execution
11. `PublishManager` - Package publishing
12. `HookLockManagerProtocol` - Hook concurrency control

#### Service Protocols
13. `SecurityServiceProtocol` - Security validation
14. `InitializationServiceProtocol` - Project initialization
15. `ConfigurationServiceProtocol` - Config updates
16. `UnifiedConfigurationServiceProtocol` - Config merging
17. `ConfigMergeServiceProtocol` - Smart config merging
18. `CoverageRatchetProtocol` - Coverage tracking

#### Documentation Protocols
19. `DocumentationServiceProtocol` - Documentation service
20. `APIExtractorProtocol` - API extraction
21. `DocumentationGeneratorProtocol` - Doc generation
22. `DocumentationValidatorProtocol` - Doc validation

#### QA & Orchestration Protocols
23. `QAAdapterProtocol` - QA adapter interface
24. `QAOrchestratorProtocol` - QA orchestration
25. `ExecutionStrategyProtocol` - Hook execution strategies
26. `CacheStrategyProtocol` - Result caching
27. `HookOrchestratorProtocol` - Hook orchestration

#### Configuration Protocol
28. `OptionsProtocol` - CLI options (comprehensive)

### Missing Protocols (Need to Create)

Based on concrete imports analysis:

1. **PerformanceMonitorProtocol** - Performance tracking
   - Used in: `workflow_orchestrator.py`, multiple services
   - Methods: `start_monitoring()`, `stop_monitoring()`, `get_metrics()`

2. **MemoryOptimizerProtocol** - Memory optimization
   - Used in: `workflow_orchestrator.py`, `phase_coordinator.py`
   - Methods: `optimize()`, `get_stats()`, decorator support

3. **PerformanceCacheProtocol** - Performance caching
   - Used in: `workflow_orchestrator.py`, `phase_coordinator.py`
   - Methods: `get()`, `set()`, `invalidate()`

4. **QualityIntelligenceProtocol** - Quality analysis
   - Used in: `workflow_orchestrator.py`
   - Methods: `analyze()`, `get_recommendations()`

5. **QualityBaselineProtocol** - Quality baseline tracking
   - Used in: `workflow_orchestrator.py`
   - Methods: `get_baseline()`, `update_baseline()`, `compare()`

6. **ParallelExecutorProtocol** - Parallel execution
   - Used in: `phase_coordinator.py`
   - Methods: `execute_parallel()`, `get_results()`

7. **PerformanceBenchmarkProtocol** - Benchmarking service
   - Used in: `workflow_orchestrator.py`
   - Methods: `run_benchmark()`, `get_report()`

---

## Phase 2: Files Requiring Migration

### Priority 1: Core Orchestration (CRITICAL)

#### 1. `crackerjack/core/workflow_orchestrator.py`
**Concrete Imports:**
```python
from crackerjack.services.debug import (...)
from crackerjack.services.logging import (...)
from crackerjack.services.memory_optimizer import get_memory_optimizer, memory_optimized
from crackerjack.services.performance_benchmarks import PerformanceBenchmarkService
from crackerjack.services.performance_cache import get_performance_cache
from crackerjack.services.performance_monitor import (...)
from crackerjack.services.quality_baseline_enhanced import (...)
from crackerjack.services.quality_intelligence import QualityIntelligenceService
```

**Migration Strategy:**
- Create missing protocols first
- Replace concrete imports with protocol imports
- Update type annotations in `__init__()` and methods
- Update DI container to inject protocol instances

#### 2. `crackerjack/core/phase_coordinator.py`
**Concrete Imports:**
```python
from crackerjack.services.memory_optimizer import (...)
from crackerjack.services.parallel_executor import (...)
from crackerjack.services.performance_cache import get_filesystem_cache, get_git_cache
```

**Migration Strategy:**
- Use new protocols from Phase 1
- Replace concrete imports
- Update method signatures

#### 3. `crackerjack/core/autofix_coordinator.py`
**Concrete Imports:**
```python
from crackerjack.services.logging import get_logger
```

**Migration Strategy:**
- Use `LoggerProtocol` (already exists)
- Replace concrete import

#### 4. `crackerjack/core/enhanced_container.py`
**Concrete Imports:**
```python
from crackerjack.services.logging import get_logger
```

**Migration Strategy:**
- Use `LoggerProtocol`
- Update DI container initialization

### Priority 2: Coordinators

#### Files to Migrate:
- `crackerjack/coordinators/*.py` (if any exist)

### Priority 3: Managers

#### Files to Audit:
- `crackerjack/managers/hook_manager.py`
- `crackerjack/managers/test_manager.py`
- `crackerjack/managers/publish_manager.py`

**Note**: These likely already implement protocols, just need verification.

### Priority 4: Services (Selective)

Only migrate services that are directly used in orchestration:
- `crackerjack/services/debug.py`
- `crackerjack/services/logging.py`
- `crackerjack/services/memory_optimizer.py`
- `crackerjack/services/performance_*.py`
- `crackerjack/services/quality_*.py`

---

## Phase 3: Implementation Steps

### Step 1: Create Missing Protocols (Day 1)

Add to `crackerjack/models/protocols.py`:

```python
@t.runtime_checkable
class PerformanceMonitorProtocol(t.Protocol):
    """Protocol for performance monitoring."""

    def start_monitoring(self, operation: str) -> None: ...
    def stop_monitoring(self, operation: str) -> dict[str, t.Any]: ...
    def get_metrics(self) -> dict[str, t.Any]: ...
    def reset_metrics(self) -> None: ...

@t.runtime_checkable
class MemoryOptimizerProtocol(t.Protocol):
    """Protocol for memory optimization."""

    def optimize(self) -> None: ...
    def get_stats(self) -> dict[str, t.Any]: ...
    def get_memory_usage(self) -> int: ...

@t.runtime_checkable
class PerformanceCacheProtocol(t.Protocol):
    """Protocol for performance caching."""

    def get(self, key: str) -> t.Any | None: ...
    def set(self, key: str, value: t.Any, ttl: int = 3600) -> None: ...
    def invalidate(self, key: str) -> bool: ...
    def clear_all(self) -> None: ...

@t.runtime_checkable
class QualityIntelligenceProtocol(t.Protocol):
    """Protocol for quality intelligence analysis."""

    def analyze(self, metrics: dict[str, t.Any]) -> dict[str, t.Any]: ...
    def get_recommendations(self) -> list[dict[str, t.Any]]: ...
    def predict_quality_trend(self) -> dict[str, t.Any]: ...

@t.runtime_checkable
class QualityBaselineProtocol(t.Protocol):
    """Protocol for quality baseline tracking."""

    def get_baseline(self) -> dict[str, t.Any]: ...
    def update_baseline(self, metrics: dict[str, t.Any]) -> bool: ...
    def compare(self, current: dict[str, t.Any]) -> dict[str, t.Any]: ...

@t.runtime_checkable
class ParallelExecutorProtocol(t.Protocol):
    """Protocol for parallel task execution."""

    async def execute_parallel(
        self,
        tasks: list[t.Any],
        max_workers: int = 3
    ) -> list[t.Any]: ...

    def get_results(self) -> list[t.Any]: ...

@t.runtime_checkable
class PerformanceBenchmarkProtocol(t.Protocol):
    """Protocol for performance benchmarking."""

    def run_benchmark(self, operation: str) -> dict[str, t.Any]: ...
    def get_report(self) -> dict[str, t.Any]: ...
    def compare_benchmarks(
        self,
        baseline: dict[str, t.Any],
        current: dict[str, t.Any]
    ) -> dict[str, t.Any]: ...
```

### Step 2: Migrate workflow_orchestrator.py (Day 2)

**Before:**
```python
from crackerjack.services.performance_monitor import (
    PerformanceMonitor,
    get_performance_monitor,
)

class WorkflowOrchestrator:
    def __init__(self, ..., performance_monitor: PerformanceMonitor):
        self.performance_monitor = performance_monitor
```

**After:**
```python
from crackerjack.models.protocols import PerformanceMonitorProtocol

class WorkflowOrchestrator:
    def __init__(self, ..., performance_monitor: PerformanceMonitorProtocol):
        self.performance_monitor = performance_monitor
```

### Step 3: Migrate phase_coordinator.py (Day 2)

**Before:**
```python
from crackerjack.services.parallel_executor import ParallelExecutor

class PhaseCoordinator:
    def __init__(self, ..., executor: ParallelExecutor):
        self.executor = executor
```

**After:**
```python
from crackerjack.models.protocols import ParallelExecutorProtocol

class PhaseCoordinator:
    def __init__(self, ..., executor: ParallelExecutorProtocol):
        self.executor = executor
```

### Step 4: Migrate autofix_coordinator.py (Day 3)

Replace `get_logger` usage with `LoggerProtocol`.

### Step 5: Update DI Container (Day 3)

Update `enhanced_container.py` to inject protocol instances:

```python
from crackerjack.models.protocols import (
    PerformanceMonitorProtocol,
    MemoryOptimizerProtocol,
    # ... etc
)

# Ensure concrete implementations are registered to satisfy protocols
container.register(PerformanceMonitorProtocol, performance_monitor_instance)
```

### Step 6: Test & Validate (Day 4-5)

1. Run all tests: `python -m crackerjack --run-tests`
2. Verify type checking: `python -m crackerjack --comp`
3. Check for circular imports
4. Validate ACB cache adapter still works
5. Run full quality workflow

---

## Phase 4: Validation Checklist

### Type Checking
- [ ] Pyright/mypy passes with no errors
- [ ] No `Any` types introduced (except where unavoidable)
- [ ] All protocol methods have proper signatures

### Testing
- [ ] All 29 cache tests pass
- [ ] All 26 decorator tests pass
- [ ] Integration tests pass
- [ ] No functionality regressions

### Architecture
- [ ] Zero concrete imports in orchestration layer
- [ ] All DI uses protocol types
- [ ] No circular import issues
- [ ] Clean separation of concerns

### Documentation
- [ ] Protocol docstrings updated
- [ ] Migration guide documented
- [ ] CLAUDE.md updated with new pattern

---

## Success Metrics

**Before Migration:**
- ❌ ~15 concrete class imports in orchestration
- ❌ Mixed protocol/concrete usage
- ❌ Tight coupling to implementations

**After Migration:**
- ✅ Zero concrete class imports in orchestration
- ✅ 100% protocol-based DI
- ✅ Loose coupling, testable architecture

---

## Risk Mitigation

### Low Risk Areas
- Creating new protocols (no breaking changes)
- Replacing imports (type-only change)
- Updating type annotations

### Medium Risk Areas
- DI container updates (test thoroughly)
- Service initialization order
- Protocol method signature mismatches

### Mitigation Strategies
1. **Incremental migration**: One file at a time
2. **Test after each change**: Ensure tests pass
3. **Git commits**: Commit after each successful file migration
4. **Rollback plan**: Keep concrete implementations working during migration

---

## Timeline

**Day 1**: Create missing protocols, validate signatures
**Day 2**: Migrate workflow_orchestrator.py and phase_coordinator.py
**Day 3**: Migrate autofix_coordinator.py, enhanced_container.py
**Day 4**: Full test suite validation
**Day 5**: Documentation updates, final verification

---

## Deliverables

1. ✅ 7 new protocols added to `protocols.py`
2. ✅ 4 core orchestration files migrated
3. ✅ Updated DI container configuration
4. ✅ All tests passing
5. ✅ Documentation updated
6. ✅ Migration completion report

---

## Notes

- **DO NOT** modify existing protocol definitions unless absolutely necessary
- **DO NOT** change functionality - this is pure refactoring
- **MAINTAIN** all existing error handling patterns
- **PRESERVE** ACB cache adapter integration (already working)
- **TEST** after every single file migration
