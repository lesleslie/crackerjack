# Workflow Orchestrator Refactoring Plan

## Problem

The `_setup_acb_services` method in `/Users/les/Projects/crackerjack/crackerjack/core/workflow_orchestrator.py` has a complexity of 32, exceeding the project's maximum of 15.

## Current State Analysis

**Method**: `WorkflowOrchestrator._setup_acb_services()`

- **Lines**: 142 lines (lines 2642-2783)
- **Complexity**: 32
- **Issues**:
  - Single monolithic method handling all ACB service registration
  - Multiple import blocks throughout the method
  - Mixed concerns: filesystem, git, hooks, testing, publishing, security, monitoring, events
  - No logical grouping of related services

## Refactoring Strategy

### 1. Extract Helper Methods by Service Category

Break down `_setup_acb_services` into focused helper methods:

```python
def _setup_acb_services(self) -> None:
    """Setup all services using ACB dependency injection."""
    self._register_core_services()
    self._register_filesystem_and_git_services()
    self._register_manager_services()
    self._register_quality_services()
    self._register_publishing_services()
    self._register_monitoring_services()
    self._setup_event_system()
```

### 2. Service Registration Groups

#### Core Services (lines 2666-2716)

- **Method**: `_register_core_services()`
- **Services**: UnifiedConfiguration, ConfigIntegrity, ConfigMerge, SmartScheduling, Security, HookLockManager
- **Complexity**: ~5

#### Filesystem & Git Services (lines 2667-2672, 2671-2672, 2719)

- **Method**: `_register_filesystem_and_git_services()`
- **Services**: EnhancedFileSystem, GitService
- **Complexity**: ~3

#### Manager Services (lines 2674-2678, 2729-2731)

- **Method**: `_register_manager_services()`
- **Services**: HookManager, TestManager
- **Complexity**: ~4

#### Quality Services (lines 2721-2753)

- **Method**: `_register_quality_services()`
- **Services**: CoverageRatchet, CoverageBadge, VersionAnalyzer, ChangelogGenerator, RegexPatterns
- **Complexity**: ~6

#### Publishing Services (lines 2754-2756)

- **Method**: `_register_publishing_services()`
- **Services**: PublishManager
- **Complexity**: ~3

#### Monitoring Services (lines 2770-2779)

- **Method**: `_register_monitoring_services()`
- **Services**: PerformanceBenchmark
- **Complexity**: ~4

#### Event System (lines 2784-2803)

- **Method**: `_setup_event_system()` (already extracted)
- **Complexity**: ~5

## Implementation Plan

### Step 1: Move imports to top of file

- Consolidate duplicate imports
- Remove inline imports where possible
- Keep only dynamic imports for optional dependencies

### Step 2: Extract service registration methods

- Create one helper method per service category
- Each method handles related service instantiation and registration
- Maintain clear separation of concerns

### Step 3: Validate refactoring

- Run complexity check: `ruff check --select C901`
- Ensure all services still register correctly
- Verify no behavioral changes

## Expected Complexity Reduction

| Method | Current | Target |
|--------|---------|--------|
| `_setup_acb_services` | 32 | ≤10 |
| `_register_core_services` | - | ≤5 |
| `_register_filesystem_and_git_services` | - | ≤3 |
| `_register_manager_services` | - | ≤4 |
| `_register_quality_services` | - | ≤6 |
| `_register_publishing_services` | - | ≤3 |
| `_register_monitoring_services` | - | ≤4 |

**Total complexity**: 10 (main) + 25 (helpers) = 35 distributed
**Maximum per method**: 6

## Benefits

1. **Readability**: Each method has a clear, focused purpose
1. **Maintainability**: Easy to add/remove services in specific categories
1. **Testability**: Each registration group can be tested independently
1. **Complexity**: All methods stay well below ≤15 threshold
1. **Documentation**: Method names self-document the service groups

## Preservation Requirements

1. **Functionality**: No changes to service behavior or registration
1. **Dependencies**: All ACB DI patterns remain intact
1. **Order**: Maintain service registration order (dependencies matter)
1. **Async**: Keep async/await patterns unchanged
1. **Error Handling**: Preserve existing error handling behavior

## Next Steps

1. Review and approve plan
1. Implement refactoring
1. Run `python -m crackerjack run` to validate
1. Verify complexity reduction with ruff
