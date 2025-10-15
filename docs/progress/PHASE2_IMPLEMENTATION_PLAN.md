# Phase 2 Implementation Plan: Layer Dependency Restructuring

**Date Started**: 2025-10-13
**Estimated Duration**: 2-3 weeks
**Status**: Planning Complete, Ready to Begin

## Executive Summary

Phase 2 focuses on removing reverse dependencies (core/managers/adapters → services) and ensuring all dependencies flow through ACB's dependency injection system. This establishes proper layered architecture where dependencies flow toward stability.

## Audit Results

### Current Dependency Analysis

**Core Layer** (`crackerjack/core/`):
- **26 direct service imports** identified
- **5 files** with service dependencies:
  - `workflow_orchestrator.py` (16 imports) 🔴 HIGH PRIORITY
  - `async_workflow_orchestrator.py` (2 imports)
  - `container.py` (2 imports)
  - `autofix_coordinator.py` (1 import)
  - `phase_coordinator.py` (5 imports)

**Manager Layer** (`crackerjack/managers/`):
- **10 direct service imports** identified
- Lower priority than core layer
- Needs investigation for specific files

**Adapter Layer** (`crackerjack/adapters/`):
- **3 direct service imports** identified
- `adapters/lsp/zuban.py` (2 imports)
- `adapters/utility/checks.py` (1 import)

### Dependency Severity Assessment

| File | Import Count | Severity | Priority |
|------|--------------|----------|----------|
| `core/workflow_orchestrator.py` | 16 | 🔴 CRITICAL | P0 |
| `core/phase_coordinator.py` | 5 | 🟡 HIGH | P1 |
| `core/container.py` | 2 | 🟢 MEDIUM | P2 |
| `core/async_workflow_orchestrator.py` | 2 | 🟢 MEDIUM | P2 |
| `adapters/lsp/zuban.py` | 2 | 🟢 MEDIUM | P3 |
| `core/autofix_coordinator.py` | 1 | 🟢 LOW | P4 |
| `adapters/utility/checks.py` | 1 | 🟢 LOW | P4 |

## Phase 2 Objectives

### 2.1 Core Layer Refactoring (Week 2)

**Objective**: Remove all direct service imports from core layer

**Approach**:
1. **Use Protocol-Based Dependency Injection**
   - Define protocols in `models/protocols.py`
   - Inject services via ACB's `depends` system
   - Core layer depends on protocols, not concrete implementations

2. **Leverage ACB Patterns**
   - Use `@depends.inject` decorator for dependency injection
   - Register services in DI container during initialization
   - Core layer receives dependencies, doesn't import them

3. **Refactoring Strategy**:
   ```python
   # Before (violates architecture)
   from crackerjack.services.git import GitService

   class WorkflowOrchestrator:
       def __init__(self):
           self.git_service = GitService()

   # After (follows ACB patterns)
   from crackerjack.models.protocols import GitServiceProtocol
   from acb.depends import depends, Inject

   class WorkflowOrchestrator:
       def __init__(self, git_service: GitServiceProtocol = Inject()):
           self.git_service = git_service
   ```

### 2.2 Manager Layer Refactoring (Week 2)

**Objective**: Remove direct service imports from managers

**Approach**:
- Same protocol-based DI approach as core layer
- Maintain existing public APIs
- Use `@depends.inject` for constructor injection

**Files to Refactor**: TBD (10 imports identified, need file-level analysis)

### 2.3 Adapter Layer Refactoring (Week 3)

**Objective**: Ensure adapters follow ACB adapter patterns

**Specific Changes**:

1. **`adapters/lsp/zuban.py`** (2 imports)
   - Remove `from crackerjack.services.lsp_client import LSPClient`
   - Use ACB adapter pattern with proper DI

2. **`adapters/utility/checks.py`** (1 import)
   - Remove `from crackerjack.services.regex_patterns import CompiledPatternCache`
   - Use ACB service layer or move to utility module

### 2.4 Success Metrics

- [ ] Zero direct imports from services in core layer
- [ ] Zero direct imports from services in manager layer
- [ ] Zero direct imports from services in adapter layer
- [ ] All dependencies flow through ACB DI system
- [ ] All tests pass with refactored dependencies
- [ ] No breaking changes to public APIs

## Implementation Phases

### Phase 2.1: Workflow Orchestrator Refactoring (Days 1-3)

**File**: `core/workflow_orchestrator.py` (16 imports)

**Service Dependencies to Remove**:
```python
# Debug & Logging
from crackerjack.services.debug import (...)
from crackerjack.services.logging import (...)

# Performance
from crackerjack.services.memory_optimizer import (...)
from crackerjack.services.monitoring.performance_benchmarks import (...)
from crackerjack.services.monitoring.performance_cache import (...)
from crackerjack.services.monitoring.performance_monitor import (...)

# Quality
from crackerjack.services.quality.quality_baseline_enhanced import (...)
from crackerjack.services.quality.quality_intelligence import (...)

# Infrastructure
from crackerjack.services.server_manager import (...)
from crackerjack.services.config_merge import (...)
from crackerjack.services.coverage_ratchet import (...)
from crackerjack.services.enhanced_filesystem import (...)
from crackerjack.services.git import (...)
from crackerjack.services.security import (...)
from crackerjack.services.log_manager import (...)
```

**Refactoring Steps**:
1. Define protocols for all 16 service dependencies
2. Update `workflow_orchestrator.py` constructor to accept protocol types
3. Use `@depends.inject` for automatic dependency injection
4. Register concrete services in container initialization
5. Test orchestrator with injected dependencies

### Phase 2.2: Phase Coordinator Refactoring (Days 4-5)

**File**: `core/phase_coordinator.py` (5 imports)

**Service Dependencies**:
- `memory_optimizer`
- `parallel_executor`
- `performance_cache`

**Refactoring Steps**:
1. Define protocols for 5 dependencies
2. Update constructor with protocol types
3. Use dependency injection
4. Test phase coordination

### Phase 2.3: Remaining Core Files (Days 6-7)

**Files**:
- `core/container.py` (2 imports)
- `core/async_workflow_orchestrator.py` (2 imports)
- `core/autofix_coordinator.py` (1 import)

**Approach**: Same protocol-based DI refactoring

### Phase 2.4: Manager Layer (Days 8-10)

**To Be Determined**: Need file-level analysis of 10 imports

### Phase 2.5: Adapter Layer (Days 11-12)

**Files**:
- `adapters/lsp/zuban.py`
- `adapters/utility/checks.py`

### Phase 2.6: Testing & Validation (Days 13-14)

**Test Suite**:
- Unit tests for each refactored file
- Integration tests for workflow orchestration
- Performance regression tests
- Full `python -m crackerjack` test

## Technical Patterns

### Pattern 1: Protocol Definition

```python
# crackerjack/models/protocols.py
from typing import Protocol

class GitServiceProtocol(Protocol):
    """Protocol for Git operations."""

    def get_current_branch(self) -> str: ...
    def commit(self, message: str) -> bool: ...
    # ... other methods
```

### Pattern 2: Constructor Injection

```python
# Using Inject() - ACB automatically provides dependency
from acb.depends import Inject

class WorkflowOrchestrator:
    def __init__(
        self,
        git_service: GitServiceProtocol = Inject(),
        filesystem: FileSystemProtocol = Inject(),
    ):
        self.git_service = git_service
        self.filesystem = filesystem
```

### Pattern 3: Service Registration

```python
# In container.py or initialization code
from acb.depends import depends
from crackerjack.services.git import GitService
from crackerjack.models.protocols import GitServiceProtocol

# Register concrete implementation for protocol
depends.set(GitServiceProtocol, GitService())
```

### Pattern 4: Method Injection (Alternative)

```python
# Using @depends.inject decorator
from acb.depends import depends

class WorkflowOrchestrator:
    @depends.inject
    def execute(
        self,
        git_service: GitServiceProtocol,
        filesystem: FileSystemProtocol,
    ):
        # Dependencies automatically injected
        git_service.commit("message")
```

## Risk Mitigation

### Risk 1: Breaking Public APIs
**Mitigation**: Maintain backward compatibility with wrapper methods

### Risk 2: Circular Dependencies
**Mitigation**: Use protocol-based interfaces to break cycles

### Risk 3: Performance Overhead
**Mitigation**: Profile before/after, optimize hot paths

### Risk 4: Test Failures
**Mitigation**: Comprehensive test coverage before refactoring

## Rollout Strategy

### Stage 1: Single File Proof-of-Concept
- Refactor `autofix_coordinator.py` (1 import only)
- Validate pattern works
- Document learnings

### Stage 2: High-Priority Core Files
- `workflow_orchestrator.py`
- `phase_coordinator.py`

### Stage 3: Remaining Core Files
- `container.py`
- `async_workflow_orchestrator.py`

### Stage 4: Manager & Adapter Layers
- Manager layer refactoring
- Adapter layer refactoring

### Stage 5: Full Validation
- Complete test suite
- Performance benchmarks
- Production readiness check

## Success Criteria

### Technical Criteria
- ✅ Zero `from crackerjack.services` imports in core layer
- ✅ Zero `from crackerjack.services` imports in manager layer
- ✅ Zero `from crackerjack.services` imports in adapter layer
- ✅ All tests passing
- ✅ No performance regressions

### Architectural Criteria
- ✅ Dependencies flow through ACB DI system
- ✅ Protocols defined for all service interfaces
- ✅ Core layer depends on protocols, not implementations
- ✅ Proper layering: Application → Services → Core

### Quality Criteria
- ✅ Code coverage maintained or improved
- ✅ Complexity scores unchanged or improved
- ✅ No new pylint/mypy errors
- ✅ Documentation updated

## Next Steps

1. **Review and Approve** this implementation plan
2. **Create Protocol Definitions** for top 5 services
3. **Start with Proof-of-Concept**: Refactor `autofix_coordinator.py`
4. **Proceed to High-Priority Files**: `workflow_orchestrator.py`
5. **Iterate and Validate** throughout process

## Documentation

- This plan: `docs/progress/PHASE2_IMPLEMENTATION_PLAN.md`
- Daily progress: `docs/progress/PHASE2_DAILY_LOG.md` (TBD)
- Completion report: `docs/progress/PHASE2_COMPLETION_REPORT.md` (TBD)

---

**Plan Status**: ✅ Ready for Implementation
**Approval Required**: Yes
**Estimated Completion**: 2-3 weeks from start date
