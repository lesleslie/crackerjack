# Phase 2: phase_coordinator.py Service Dependency Analysis

**Date**: 2025-10-13
**Status**: Analysis Complete - Ready for Refactoring
**Priority**: P1 (High Priority - Core Layer)

## Executive Summary

The `phase_coordinator.py` file has **3 service import statements** importing **7 factory functions**. These are used to instantiate services directly in the constructor. All services have corresponding protocols, making this a straightforward refactoring following the proven workflow_orchestrator.py pattern.

## Service Import Inventory

### Lines 14-25: Service Imports Block

```python
# 1. Memory Optimizer (lines 14-17)
from crackerjack.services.memory_optimizer import (
    create_lazy_service,        # Factory function
    get_memory_optimizer,        # Factory function
)

# 2. Parallel Executor (lines 18-21)
from crackerjack.services.parallel_executor import (
    get_async_executor,          # Factory function
    get_parallel_executor,       # Factory function
)

# 3. Performance Cache (lines 22-25)
from crackerjack.services.monitoring.performance_cache import (
    get_filesystem_cache,        # Factory function
    get_git_cache,               # Factory function
)
```

### Summary Table

| Import Source | Symbols | Type | Usage Pattern | Refactor Priority |
|---------------|---------|------|---------------|-------------------|
| `services.memory_optimizer` | 2 symbols | Factory functions | Direct instantiation (line 85, 91-94) | 🔴 High |
| `services.parallel_executor` | 2 symbols | Factory functions | Direct instantiation (lines 86-87) | 🔴 High |
| `services.monitoring.performance_cache` | 2 symbols | Factory functions | Direct instantiation (lines 88-89) | 🔴 High |

**Total**: 3 import statements, 7 imported symbols (all factory functions)

## Current Protocol Usage

The file already uses protocols extensively via `depends()` for manager-level dependencies:

```python
# Lines 53-58 - Already using protocols! ✅
filesystem: FileSystemInterface = depends(),
git_service: GitInterface = depends(),
hook_manager: HookManager = depends(),
test_manager: TestManagerProtocol = depends(),
publish_manager: PublishManager = depends(),
config_merge_service: ConfigMergeServiceProtocol = depends(),
```

**Key Observation**: The file is **partially migrated** - manager dependencies use protocols, but service dependencies still use factory functions.

## Usage Analysis

### 1. Memory Optimizer (`services.memory_optimizer`)

**Usage**:
- Line 85: `self._memory_optimizer: MemoryOptimizerProtocol = get_memory_optimizer()`
  Direct instantiation via factory function
- Lines 91-94: `self._lazy_autofix = create_lazy_service(...)`
  Creates lazy-loaded AutofixCoordinator

**Type Annotations**:
- Line 85: `self._memory_optimizer: MemoryOptimizerProtocol`

**Refactoring Strategy**:
- Remove `get_memory_optimizer` import (service already registered in container)
- Use `Inject[MemoryOptimizerProtocol]` in constructor
- For `create_lazy_service`: Keep import OR move to protocol-based lazy loading

### 2. Parallel Executor (`services.parallel_executor`)

**Usage**:
- Line 86: `self._parallel_executor: ParallelHookExecutor = get_parallel_executor()`
- Line 87: `self._async_executor: AsyncCommandExecutor = get_async_executor()`
  Both direct instantiation via factory functions

**Type Annotations**:
- Line 86: `self._parallel_executor: ParallelHookExecutor`
- Line 87: `self._async_executor: AsyncCommandExecutor`

**Refactoring Strategy**: 🔴 HIGH PRIORITY
- Check if protocols exist for ParallelHookExecutor and AsyncCommandExecutor
- If protocols exist, use `Inject[Protocol]` pattern
- If not, create protocols or register concrete types
- Remove factory function imports

### 3. Performance Cache (`services.monitoring.performance_cache`)

**Usage**:
- Line 88: `self._git_cache: PerformanceCacheProtocol = get_git_cache()`
- Line 89: `self._filesystem_cache: PerformanceCacheProtocol = get_filesystem_cache()`
  Both direct instantiation via factory functions

**Type Annotations**:
- Lines 88-89: `self._git_cache: PerformanceCacheProtocol`
- Lines 88-89: `self._filesystem_cache: PerformanceCacheProtocol`

**Refactoring Strategy**: 🔴 HIGH PRIORITY
- Both use `PerformanceCacheProtocol` - good!
- Register git_cache and filesystem_cache separately in container
- Use `Inject[PerformanceCacheProtocol]` with qualifier/name parameter
- OR create separate protocols (GitCacheProtocol, FileSystemCacheProtocol)
- Remove factory function imports

## Protocol Verification

Need to verify/create these protocols:

1. ✅ `MemoryOptimizerProtocol` - Already exists (used in workflow_orchestrator)
2. ❓ `ParallelHookExecutorProtocol` - Check if exists
3. ❓ `AsyncCommandExecutorProtocol` - Check if exists
4. ✅ `PerformanceCacheProtocol` - Already exists (used in workflow_orchestrator)

**Note**: For git_cache and filesystem_cache, we need a strategy to differentiate them since they share the same protocol.

## Refactoring Priority Breakdown

### 🔴 High Priority (All Services)

All 3 service imports are HIGH priority because they all:
1. Use factory functions for direct instantiation
2. Should be registered in container initialization
3. Follow the same pattern as workflow_orchestrator refactoring

**Pattern**: All three directly instantiate services via factory functions, violating separation of concerns.

## Recommended Refactoring Sequence

### Phase 2.2: Phase Coordinator Refactoring (Days 1-2)

**Goal**: Remove factory function imports and use dependency injection

#### Step 1: Protocol Verification (30 minutes)
```python
# Check models/protocols.py for:
# - ParallelHookExecutorProtocol
# - AsyncCommandExecutorProtocol
# - Strategy for git_cache vs filesystem_cache
```

#### Step 2: Service Registration (1 hour)

**Option A: Separate Cache Protocols** (Recommended)
```python
# In crackerjack/models/protocols.py
@runtime_checkable
class GitCacheProtocol(Protocol):
    """Protocol for git-specific caching operations."""
    ...

@runtime_checkable
class FileSystemCacheProtocol(Protocol):
    """Protocol for filesystem-specific caching operations."""
    ...
```

**Option B: Named Cache Registration** (Alternative)
```python
# In crackerjack/config/__init__.py
def register_services():
    # ... existing registrations ...

    # Register parallel execution services
    from crackerjack.services.parallel_executor import (
        get_async_executor,
        get_parallel_executor,
    )

    parallel_executor = get_parallel_executor()
    depends.set(ParallelHookExecutorProtocol, parallel_executor)

    async_executor = get_async_executor()
    depends.set(AsyncCommandExecutorProtocol, async_executor)

    # Register cache services
    from crackerjack.services.monitoring.performance_cache import (
        get_filesystem_cache,
        get_git_cache,
    )

    git_cache = get_git_cache()
    depends.set(GitCacheProtocol, git_cache)

    filesystem_cache = get_filesystem_cache()
    depends.set(FileSystemCacheProtocol, filesystem_cache)
```

#### Step 3: Update PhaseCoordinator Constructor (1 hour)

**Before**:
```python
class PhaseCoordinator:
    @depends.inject
    def __init__(
        self,
        console: Console = depends(),
        pkg_path: Path = depends(),
        session: SessionCoordinator = depends(),
        filesystem: FileSystemInterface = depends(),
        git_service: GitInterface = depends(),
        hook_manager: HookManager = depends(),
        test_manager: TestManagerProtocol = depends(),
        publish_manager: PublishManager = depends(),
        config_merge_service: ConfigMergeServiceProtocol = depends(),
    ) -> None:
        # ... other init ...

        self._memory_optimizer: MemoryOptimizerProtocol = get_memory_optimizer()
        self._parallel_executor: ParallelHookExecutor = get_parallel_executor()
        self._async_executor: AsyncCommandExecutor = get_async_executor()
        self._git_cache: PerformanceCacheProtocol = get_git_cache()
        self._filesystem_cache: PerformanceCacheProtocol = get_filesystem_cache()

        self._lazy_autofix = create_lazy_service(
            lambda: AutofixCoordinator(console=console, pkg_path=pkg_path),
            "autofix_coordinator",
        )
```

**After**:
```python
class PhaseCoordinator:
    @depends.inject
    def __init__(
        self,
        memory_optimizer: Inject[MemoryOptimizerProtocol],
        parallel_executor: Inject[ParallelHookExecutorProtocol],
        async_executor: Inject[AsyncCommandExecutorProtocol],
        git_cache: Inject[GitCacheProtocol],
        filesystem_cache: Inject[FileSystemCacheProtocol],
        console: Console = depends(),
        pkg_path: Path = depends(),
        session: SessionCoordinator = depends(),
        filesystem: FileSystemInterface = depends(),
        git_service: GitInterface = depends(),
        hook_manager: HookManager = depends(),
        test_manager: TestManagerProtocol = depends(),
        publish_manager: PublishManager = depends(),
        config_merge_service: ConfigMergeServiceProtocol = depends(),
    ) -> None:
        # ... other init ...

        # Services injected via ACB DI
        self._memory_optimizer = memory_optimizer
        self._parallel_executor = parallel_executor
        self._async_executor = async_executor
        self._git_cache = git_cache
        self._filesystem_cache = filesystem_cache

        # Lazy service: Keep create_lazy_service OR refactor to protocol
        self._lazy_autofix = create_lazy_service(
            lambda: AutofixCoordinator(console=console, pkg_path=pkg_path),
            "autofix_coordinator",
        )
```

#### Step 4: Remove Factory Function Imports (15 minutes)

**Delete**:
```python
# DELETE these lines:
from crackerjack.services.memory_optimizer import get_memory_optimizer
from crackerjack.services.parallel_executor import (
    get_async_executor,
    get_parallel_executor,
)
from crackerjack.services.monitoring.performance_cache import (
    get_filesystem_cache,
    get_git_cache,
)
```

**Keep** (if needed):
```python
# KEEP for lazy service creation (if not refactored):
from crackerjack.services.memory_optimizer import create_lazy_service
```

#### Step 5: Update Imports (15 minutes)

**Add**:
```python
from acb.depends import Inject, depends
from crackerjack.models.protocols import (
    AsyncCommandExecutorProtocol,
    FileSystemCacheProtocol,
    GitCacheProtocol,
    MemoryOptimizerProtocol,
    ParallelHookExecutorProtocol,
)
```

## Expected Outcomes

### Before Refactoring
- ❌ 3 direct service imports
- ❌ 7 factory function imports
- ❌ Direct service instantiation in coordinator
- ✅ Partial protocol usage (managers only)

### After Refactoring
- ✅ 0 direct service imports (except possibly create_lazy_service)
- ✅ All services registered in container init
- ✅ All dependencies via `Inject[Protocol]`
- ✅ 100% protocol-based architecture

## Complexity Assessment

**Estimated Effort**: 2-3 hours

**Breakdown**:
- Protocol verification/creation: 30 minutes (EASY - may need cache protocols)
- Service registration: 1 hour (EASY - follow workflow_orchestrator pattern)
- Constructor refactoring: 1 hour (EASY - straightforward injection)
- Testing: 30 minutes (MEDIUM - verify all phases work)

**Risk Level**: 🟢 LOW
- Simple factory function replacements
- Clear protocol interfaces
- Proven pattern from workflow_orchestrator
- Good test coverage expected

## Success Criteria

- [ ] Zero factory function imports in phase_coordinator.py
- [ ] All services registered in container initialization
- [ ] All service dependencies use `Inject[Protocol]` pattern
- [ ] PhaseCoordinator imports successfully
- [ ] All phase methods execute correctly
- [ ] No performance regressions

## Special Considerations

### 1. Lazy Service Creation

The `create_lazy_service` pattern for AutofixCoordinator:
```python
self._lazy_autofix = create_lazy_service(
    lambda: AutofixCoordinator(console=console, pkg_path=pkg_path),
    "autofix_coordinator",
)
```

**Options**:
1. **Keep as-is**: Import `create_lazy_service` and use it (simplest)
2. **Refactor to DI**: Register AutofixCoordinator in container with lazy initialization
3. **Protocol-based lazy**: Create LazyServiceProtocol pattern

**Recommendation**: Keep as-is for now (separate optimization task)

### 2. Cache Service Differentiation

Two caches share same protocol but serve different purposes:
- `git_cache`: Git operations caching
- `filesystem_cache`: Filesystem operations caching

**Options**:
1. **Separate Protocols** (Recommended): Create GitCacheProtocol and FileSystemCacheProtocol
2. **Named Registration**: Use DI container naming/qualifiers (if ACB supports)
3. **Single Protocol**: Keep PerformanceCacheProtocol, differentiate by constructor parameter names

**Recommendation**: Create separate protocols for type safety and clarity

## Next Steps

1. ✅ Complete this analysis document
2. ⏳ Check models/protocols.py for executor protocols
3. ⏳ Create cache protocols (GitCacheProtocol, FileSystemCacheProtocol)
4. ⏳ Register services in config/__init__.py
5. ⏳ Refactor PhaseCoordinator constructor
6. ⏳ Remove factory function imports
7. ⏳ Test all phase operations

---

**Analysis Status**: ✅ Complete
**Next Action**: Verify/create protocols for parallel executors and caches
**Estimated Start**: Ready to begin Phase 2.2
