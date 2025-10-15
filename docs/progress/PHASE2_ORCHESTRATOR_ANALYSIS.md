# Phase 2: workflow_orchestrator.py Service Dependency Analysis

**Date**: 2025-10-13
**Status**: Analysis Complete - Ready for Refactoring
**Priority**: P0 (Critical Path)

## Executive Summary

The `workflow_orchestrator.py` file has **8 service import statements** importing **14 total symbols** (classes, functions, decorators). Current status shows **partial ACB migration** with some dependencies already using `depends.get()` for protocols, while others still use direct service imports.

## Service Import Inventory

### Lines 46-65: Service Imports Block

```python
# 1. Debug Services (lines 46-50)
from crackerjack.services.debug import (
    AIAgentDebugger,           # Class
    NoOpDebugger,              # Class
    get_ai_agent_debugger,     # Factory function
)

# 2. Logging Services (lines 51-54)
from crackerjack.services.logging import (
    LoggingContext,            # Context manager
    setup_structured_logging,  # Setup function
)

# 3. Memory Optimizer (line 55)
from crackerjack.services.memory_optimizer import get_memory_optimizer, memory_optimized
                                                 # Factory        # Decorator

# 4. Performance Benchmarks (line 56)
from crackerjack.services.monitoring.performance_benchmarks import PerformanceBenchmarkService  # Class

# 5. Performance Cache (line 57)
from crackerjack.services.monitoring.performance_cache import get_performance_cache  # Factory

# 6. Performance Monitor (lines 58-61)
from crackerjack.services.monitoring.performance_monitor import (
    get_performance_monitor,   # Factory function
    phase_monitor,             # Context manager decorator
)

# 7. Quality Baseline (lines 62-64)
from crackerjack.services.quality.quality_baseline_enhanced import (
    EnhancedQualityBaselineService,  # Class
)

# 8. Quality Intelligence (line 65)
from crackerjack.services.quality.quality_intelligence import QualityIntelligenceService  # Class
```

### Summary Table

| Import Source | Symbols | Type | Usage Pattern | Refactor Priority |
|---------------|---------|------|---------------|-------------------|
| `services.debug` | 3 symbols | Class + Factory | Property lazy init (line 133) | 🟡 Medium |
| `services.logging` | 2 symbols | Context + Function | Context manager (line 153) | 🟢 Low |
| `services.memory_optimizer` | 2 symbols | Factory + Decorator | Decorator usage (line 141) | 🟡 Medium |
| `services.performance_benchmarks` | 1 symbol | Class | Constructor (lines 113-115) | 🔴 High |
| `services.performance_cache` | 1 symbol | Factory | Unused (already via protocol) | 🟢 Low |
| `services.performance_monitor` | 2 symbols | Factory + Decorator | Decorator usage (lines 877+) | 🟡 Medium |
| `services.quality.quality_baseline_enhanced` | 1 symbol | Class | Constructor (line 100) | 🔴 High |
| `services.quality.quality_intelligence` | 1 symbol | Class | Constructor (line 104) | 🔴 High |

**Total**: 8 import statements, 14 imported symbols

## Current Protocol Usage (Already Migrated)

The file already uses protocols for some dependencies via `depends.get()`:

```python
# Lines 87-94 - Already using protocols! ✅
self.logger: LoggerProtocol = depends.get(LoggerProtocol)

self._performance_monitor: PerformanceMonitorProtocol = (
    depends.get(PerformanceMonitorProtocol)
)
self._memory_optimizer: MemoryOptimizerProtocol = depends.get(MemoryOptimizerProtocol)
self._cache: PerformanceCacheProtocol = depends.get(PerformanceCacheProtocol)
```

**Key Observation**: The file is **partially migrated** - it already fetches some services via protocols, but still has direct imports for classes like `EnhancedQualityBaselineService` and `PerformanceBenchmarkService`.

## Usage Analysis

### 1. Debug Services (`services.debug`)

**Usage**:
- Line 133: `self._debugger = get_ai_agent_debugger()`
  Called in `debugger` property (lazy initialization)

**Type Annotations**:
- Line 88: `self._debugger: AIAgentDebugger | NoOpDebugger | None = None`

**Refactoring Strategy**:
- Create `DebuggerProtocol` with common interface
- Register debugger instance at container initialization
- Use `Inject[DebuggerProtocol]` in constructor
- Keep lazy initialization pattern if needed

### 2. Logging Services (`services.logging`)

**Usage**:
- Line 153: `with LoggingContext(...)`
  Used as context manager in workflow execution

**Refactoring Strategy**:
- `LoggingContext` is a utility context manager - likely keep as-is
- `setup_structured_logging` may need to move to initialization layer
- Low priority - these are utilities, not state-holding services

### 3. Memory Optimizer (`services.memory_optimizer`)

**Usage**:
- Line 141: `@memory_optimized` decorator on `run_complete_workflow()`
- Line 185: `self._memory_optimizer.optimize_memory()` via protocol

**Current State**: ✅ Already using `MemoryOptimizerProtocol` via `depends.get()`

**Refactoring Strategy**:
- Remove `get_memory_optimizer` import (unused)
- Keep `memory_optimized` decorator import OR move to protocol-based approach
- Consider if decorator can be applied via DI

### 4. Performance Benchmarks (`services.performance_benchmarks`)

**Usage**:
- Lines 113-115: Direct instantiation in constructor
  ```python
  self._performance_benchmarks = PerformanceBenchmarkService(
      console, pkg_path
  )
  ```
- Line 117: Manual registration with DI
  `depends.set(PerformanceBenchmarkProtocol, self._performance_benchmarks)`

**Type Annotation**:
- Line 111: `self._performance_benchmarks: PerformanceBenchmarkProtocol | None`

**Refactoring Strategy**: 🔴 HIGH PRIORITY
- Remove direct import of `PerformanceBenchmarkService`
- Register service in container initialization (not in orchestrator)
- Use `Inject[PerformanceBenchmarkProtocol]` in constructor
- Remove manual `depends.set()` call from orchestrator

### 5. Performance Cache (`services.performance_cache`)

**Usage**:
- Line 94: `self._cache: PerformanceCacheProtocol = depends.get(PerformanceCacheProtocol)`
- Line 148: `await self._cache.start()`
- Line 186: `await self._cache.stop()`

**Current State**: ✅ Already using `PerformanceCacheProtocol` via `depends.get()`

**Refactoring Strategy**:
- Remove `get_performance_cache` import (already via protocol)
- No changes needed - this is already correct!

### 6. Performance Monitor (`services.performance_monitor`)

**Usage**:
- Line 92-93: `self._performance_monitor: PerformanceMonitorProtocol = depends.get(PerformanceMonitorProtocol)`
- Line 146: `self._performance_monitor.start_workflow(workflow_id)`
- Lines 877, 994, 1006, 1109, 2340: `with phase_monitor(workflow_id, "phase_name")`

**Current State**:
- ✅ Service accessed via `PerformanceMonitorProtocol`
- ❌ `phase_monitor` decorator still imported directly

**Refactoring Strategy**:
- Remove `get_performance_monitor` import (already via protocol)
- Keep `phase_monitor` decorator OR refactor to protocol method
- Consider: `self._performance_monitor.phase("phase_name")` context manager

### 7. Quality Baseline (`services.quality.quality_baseline_enhanced`)

**Usage**:
- Line 100: Direct instantiation
  `quality_baseline = EnhancedQualityBaselineService()`
- Line 101: Manual registration
  `depends.set(QualityBaselineProtocol, quality_baseline)`

**Type Annotation**:
- Via protocol: `QualityBaselineProtocol`

**Refactoring Strategy**: 🔴 HIGH PRIORITY
- Remove direct import
- Register service in container initialization
- Remove manual `depends.set()` from orchestrator
- Service should be available via DI when orchestrator initializes

### 8. Quality Intelligence (`services.quality.quality_intelligence`)

**Usage**:
- Line 104: Direct instantiation
  `self._quality_intelligence = QualityIntelligenceService(quality_baseline)`
- Line 105: Manual registration
  `depends.set(QualityIntelligenceProtocol, self._quality_intelligence)`

**Type Annotation**:
- Line 97: `self._quality_intelligence: QualityIntelligenceProtocol | None`

**Refactoring Strategy**: 🔴 HIGH PRIORITY
- Remove direct import
- Register service in container initialization with proper dependencies
- Use `Inject[QualityIntelligenceProtocol]` in constructor
- Remove manual `depends.set()` from orchestrator

## Refactoring Priority Breakdown

### 🔴 High Priority (Must Fix)
1. **Performance Benchmarks** - Direct instantiation + manual registration
2. **Quality Baseline** - Direct instantiation + manual registration
3. **Quality Intelligence** - Direct instantiation + manual registration

**Pattern**: All three manually instantiate and register services. This violates separation of concerns - orchestrator should NOT be responsible for service lifecycle.

### 🟡 Medium Priority (Should Fix)
4. **Debug Services** - Factory function usage in lazy property
5. **Memory Optimizer** - Decorator import (service already via protocol)
6. **Performance Monitor** - Decorator import (service already via protocol)

**Pattern**: These use factory functions or decorators that could be simplified via DI.

### 🟢 Low Priority (Consider)
7. **Logging Services** - Utility context managers and setup functions
8. **Performance Cache** - Already correct via protocol ✅

**Pattern**: Utilities that may not need refactoring or are already correct.

## Recommended Refactoring Sequence

### Phase 2.1: Service Registration Cleanup (Days 1-2)
**Goal**: Move service instantiation out of orchestrator into container initialization

1. **Move to `crackerjack/config/__init__.py` or new `crackerjack/core/container.py`**:
   ```python
   # Register performance services
   performance_benchmarks = PerformanceBenchmarkService(console, pkg_path)
   depends.set(PerformanceBenchmarkProtocol, performance_benchmarks)

   # Register quality services
   quality_baseline = EnhancedQualityBaselineService()
   depends.set(QualityBaselineProtocol, quality_baseline)

   quality_intelligence = QualityIntelligenceService(quality_baseline)
   depends.set(QualityIntelligenceProtocol, quality_intelligence)
   ```

2. **Update `WorkflowPipeline.__init__()` to use `Inject[]`**:
   ```python
   @depends.inject
   def __init__(
       self,
       console: Console = depends(),
       pkg_path: Path = depends(),
       session: SessionCoordinator = depends(),
       phases: PhaseCoordinator = depends(),
       logger: Inject[Logger],
       performance_monitor: Inject[PerformanceMonitorProtocol],
       memory_optimizer: Inject[MemoryOptimizerProtocol],
       cache: Inject[PerformanceCacheProtocol],
       performance_benchmarks: Inject[PerformanceBenchmarkProtocol],
       quality_intelligence: Inject[QualityIntelligenceProtocol],
   ) -> None:
       self.console = console
       self.pkg_path = pkg_path
       self.session = session
       self.phases = phases
       self.logger = logger
       self._performance_monitor = performance_monitor
       self._memory_optimizer = memory_optimizer
       self._cache = cache
       self._performance_benchmarks = performance_benchmarks
       self._quality_intelligence = quality_intelligence
   ```

3. **Remove direct imports**:
   ```python
   # DELETE these lines:
   from crackerjack.services.performance_benchmarks import PerformanceBenchmarkService
   from crackerjack.services.quality.quality_baseline_enhanced import (
       EnhancedQualityBaselineService,
   )
   from crackerjack.services.quality.quality_intelligence import QualityIntelligenceService
   ```

4. **Remove manual registration code** (lines 98-120)

### Phase 2.2: Factory Functions & Decorators (Days 3-4)
**Goal**: Eliminate factory function imports where services are available via protocols

1. **Debug Services**:
   - Register debugger at container init
   - Inject via `debugger: Inject[DebuggerProtocol]`
   - Remove `get_ai_agent_debugger()` call

2. **Decorator Pattern**:
   - Keep `@memory_optimized` decorator (it's a utility)
   - Refactor `phase_monitor` to use protocol method:
     `self._performance_monitor.phase_context("phase_name")`

3. **Remove unused imports**:
   ```python
   # DELETE:
   from crackerjack.services.memory_optimizer import get_memory_optimizer
   from crackerjack.services.performance_cache import get_performance_cache
   from crackerjack.services.monitoring.performance_monitor import get_performance_monitor
   ```

### Phase 2.3: Protocol Verification (Day 5)
**Goal**: Ensure all protocols are defined and complete

1. Verify `DebuggerProtocol` exists in `models/protocols.py`
2. Add any missing methods to existing protocols
3. Ensure all service protocols are runtime-checkable

## Expected Outcomes

### Before Refactoring
- ❌ 8 direct service imports
- ❌ Manual service instantiation in orchestrator
- ❌ Manual DI registration in orchestrator
- ✅ Partial protocol usage (50% migrated)

### After Refactoring
- ✅ 0 direct service imports
- ✅ All services registered in container init
- ✅ All dependencies via `Inject[Protocol]`
- ✅ 100% protocol-based architecture
- ✅ Orchestrator focuses on orchestration, not service lifecycle

## Complexity Assessment

**Estimated Effort**: 4-5 days

**Breakdown**:
- Service registration refactoring: 2 days (HIGH complexity - requires careful dependency ordering)
- Decorator/factory cleanup: 1 day (MEDIUM complexity)
- Protocol verification: 1 day (LOW complexity)
- Testing and validation: 1 day (HIGH importance)

**Risk Level**: 🟡 MEDIUM
- Many interconnected services
- Manual registration suggests complex initialization order
- Quality services depend on each other
- High test coverage required

## Success Criteria

- [ ] Zero imports from `crackerjack.services` in workflow_orchestrator.py
- [ ] All services registered in container initialization
- [ ] All dependencies use `Inject[Protocol]` pattern
- [ ] No manual `depends.set()` calls in orchestrator
- [ ] All tests passing
- [ ] No performance regressions
- [ ] WorkflowPipeline constructor < 15 complexity (currently likely >15)

## Next Steps

1. ✅ Complete this analysis document
2. ⏳ Review protocols in `models/protocols.py` for completeness
3. ⏳ Create service registration module (container.py or update config/__init__.py)
4. ⏳ Refactor WorkflowPipeline constructor
5. ⏳ Remove service imports
6. ⏳ Test all workflow scenarios

---

**Analysis Status**: ✅ Complete
**Next Action**: Review existing protocols and plan service registration strategy
**Estimated Start**: Ready to begin Phase 2.1
