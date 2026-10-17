# ACB Workflow Phase 2 - Dependency Map

**Created**: 2025-11-05 (Week 1 Day 3)
**Purpose**: Complete dependency tree for Level 4-7 implementation

## Level 3.5: PublishManager Dependencies (New Level)

These services must be registered before Level 4 managers.

### SecurityServiceProtocol

**File**: `crackerjack/services/security.py`
**Class**: `SecurityService`
**Dependencies**: None (uses SAFE_PATTERNS from regex_patterns module)
**Registration**: Simple - `SecurityService()` with no args

### RegexPatternsProtocol

**File**: `crackerjack/services/regex_patterns.py`
**Implementation**: Module with SAFE_PATTERNS dictionary
**Dependencies**: None (static patterns and cache)
**Registration**: Need to create a service wrapper or use module directly

### GitServiceProtocol

**File**: `crackerjack/services/git.py`
**Class**: `GitService` (already registered as GitInterface in Level 3)
**Dependencies**: Console (Level 1), pkg_path
**Registration**: **Already done** - just register same instance under GitServiceProtocol

### ChangelogGeneratorProtocol

**File**: `crackerjack/services/changelog_automation.py`
**Class**: `ChangelogGenerator`
**Dependencies**: `@depends.inject` (Console, GitServiceProtocol)
**Registration**: `ChangelogGenerator()` - auto-wires dependencies

### VersionAnalyzerProtocol

**File**: `crackerjack/services/version_analyzer.py`
**Class**: `VersionAnalyzer` (needs to be found - file has BreakingChangeAnalyzer)
**Dependencies**: Console, ChangelogGenerator, GitService
**Registration**: TBD - need to find actual class

## Level 4: Managers

### HookManager (Simplest)

**File**: `crackerjack/managers/hook_manager.py`
**Class**: `HookManagerImpl`
**Dependencies**:

- pkg_path: Path
- verbose: bool = False
- quiet: bool = False
- enable_lsp_optimization: bool = False
- enable_tool_proxy: bool = True
- Retrieves Console via `depends.get_sync(Console)` internally

**Registration Strategy**:

```python
hook_manager = HookManagerImpl(
    pkg_path=self._root_path,
    verbose=getattr(self.options, "verbose", False),
    quiet=getattr(self.options, "quiet", False),
)
depends.set(HookManager, hook_manager)
```

### TestManager (Medium)

**File**: `crackerjack/managers/test_manager.py`
**Class**: `TestManager`
**Dependencies**: `@depends.inject`

- Console
- CoverageRatchetProtocol
- CoverageBadgeServiceProtocol
- LSPClient (optional)

**Registration Strategy**:

```python
# Need to register dependencies first:
# - CoverageRatchetProtocol
# - CoverageBadgeServiceProtocol
# - LSPClient

test_manager = TestManager()  # Auto-wires via @depends.inject
depends.set(TestManagerProtocol, test_manager)
```

**Missing Dependencies**:

- CoverageRatchetProtocol
- CoverageBadgeServiceProtocol
- LSPClient

### PublishManager (Complex)

**File**: `crackerjack/managers/publish_manager.py`
**Class**: `PublishManagerImpl`
**Dependencies**: `@depends.inject`

- GitServiceProtocol (Level 3.5)
- VersionAnalyzerProtocol (Level 3.5)
- ChangelogGeneratorProtocol (Level 3.5)
- FileSystemInterface (Level 3 ✅)
- SecurityServiceProtocol (Level 3.5)
- RegexPatternsProtocol (Level 3.5)
- Console (Level 1 ✅)
- pkg_path
- dry_run: bool = False

**Registration Strategy**:

```python
# All Level 3.5 dependencies must be registered first
publish_manager = PublishManagerImpl(
    pkg_path=self._root_path, dry_run=False
)  # Auto-wires via @depends.inject
depends.set(PublishManager, publish_manager)
```

## Level 4.5: TestManager Dependencies (New Level)

### CoverageRatchetProtocol

**File**: `crackerjack/services/coverage_ratchet.py`
**Class**: `CoverageRatchet`
**Dependencies**: TBD (need to check)

### CoverageBadgeServiceProtocol

**File**: `crackerjack/services/coverage_badge_service.py`
**Class**: `CoverageBadgeService`
**Dependencies**: TBD (need to check)

### LSPClient

**File**: `crackerjack/services/lsp_client.py`
**Class**: `LSPClient`
**Dependencies**: TBD (need to check)

## Level 5: Executors

### ParallelHookExecutor

**File**: TBD
**Dependencies**: TBD

### AsyncCommandExecutor

**File**: TBD
**Dependencies**: TBD

## Level 6: Coordinators

### SessionCoordinator

**File**: `crackerjack/core/session_coordinator.py`
**Dependencies**: `@depends.inject`

- Console
- pkg_path: Path
- web_job_id: str | None = None

**Registration Strategy**:

```python
session_coordinator = SessionCoordinator(pkg_path=self._root_path, web_job_id=None)
depends.set(SessionCoordinator, session_coordinator)
```

### PhaseCoordinator

**File**: `crackerjack/core/phase_coordinator.py`
**Dependencies**: `@depends.inject`

- Console
- Logger
- MemoryOptimizerProtocol (Level 2 ✅)
- ParallelHookExecutor (Level 5)
- AsyncCommandExecutor (Level 5)
- GitOperationCache (Level 3 ✅)
- FileSystemCache (Level 3 ✅)
- pkg_path: Path
- session: SessionCoordinator (Level 6)
- filesystem: FileSystemInterface (Level 3 ✅)
- git_service: GitInterface (Level 3 ✅)
- hook_manager: HookManager (Level 4)
- test_manager: TestManagerProtocol (Level 4)
- publish_manager: PublishManager (Level 4)
- config_merge_service: ConfigMergeServiceProtocol

**Registration Strategy**:

```python
# Requires Session from Level 6 + all Level 1-5 services
phase_coordinator = PhaseCoordinator(
    pkg_path=self._root_path
    # Other params auto-injected via @depends.inject
)
depends.set(PhaseCoordinator, phase_coordinator)
```

## Level 7: Pipeline

### WorkflowPipeline

**File**: `crackerjack/core/workflow_orchestrator.py`
**Dependencies**: `@depends.inject`

- Console (Level 1 ✅)
- Config (Level 1 ✅)
- PerformanceMonitorProtocol (Level 2 ✅)
- MemoryOptimizerProtocol (Level 2 ✅)
- PerformanceCacheProtocol (Level 2 ✅)
- DebugServiceProtocol (Level 2 ✅)
- LoggerProtocol (Level 1 ✅)
- SessionCoordinator (Level 6)
- PhaseCoordinator (Level 6)
- QualityIntelligenceProtocol (optional)
- PerformanceBenchmarkProtocol (optional)

**Registration Strategy**:

```python
# Final service - depends on everything
workflow_pipeline = WorkflowPipeline()  # Auto-wires all dependencies
depends.set(WorkflowPipeline, workflow_pipeline)
```

## Implementation Order (Revised)

### Week 1 Day 3: Level 3.5 (PublishManager Dependencies)

1. ✅ SecurityService (no dependencies)
1. ✅ RegexPatterns (static - might need wrapper)
1. ✅ GitService as GitServiceProtocol (reuse Level 3 instance)
1. ✅ ChangelogGenerator (@depends.inject)
1. ⚠️ VersionAnalyzer (need to find class)

### Week 1 Day 4: Level 4 (Managers Part 1)

1. ✅ HookManager (simple - pkg_path + options)
1. ⏳ Start Level 4.5 (TestManager dependencies)

### Week 1 Day 5: Level 4.5 + Level 4 Part 2

1. ✅ CoverageRatchet
1. ✅ CoverageBadgeService
1. ✅ LSPClient
1. ✅ TestManager (now dependencies available)
1. ✅ PublishManager (all Level 3.5 dependencies registered)

### Week 2 Day 1-2: Level 5 (Executors)

1. ParallelHookExecutor
1. AsyncCommandExecutor

### Week 2 Day 3: Level 6 (Coordinators)

1. SessionCoordinator (simple)
1. PhaseCoordinator (complex - needs all Levels 1-5)

### Week 2 Day 4: Level 7 (Pipeline)

1. WorkflowPipeline (depends on all previous levels)

### Week 2 Day 5: Integration

1. Update action handlers to use WorkflowPipeline
1. End-to-end testing
1. Performance validation

## Missing Service Discoveries

### Critical Gaps to Investigate

1. **VersionAnalyzer**: File exists but need to find actual class

   - Check if there's a VersionAnalyzer class in version_analyzer.py
   - May need to create wrapper for BreakingChangeAnalyzer

1. **ConfigMergeServiceProtocol**: Referenced by PhaseCoordinator

   - Find implementation file
   - Understand dependencies

1. **QualityIntelligenceProtocol**: Optional for WorkflowPipeline

   - Find implementation
   - Decide if needed for Phase 2

1. **PerformanceBenchmarkProtocol**: Optional for WorkflowPipeline

   - Find implementation
   - Decide if needed for Phase 2

## Registration Pattern Summary

### Services with No Dependencies

```python
service = ServiceClass()
depends.set(ProtocolType, service)
```

### Services with @depends.inject

```python
service = ServiceClass()  # Dependencies auto-injected!
depends.set(ProtocolType, service)
```

### Services with Explicit Parameters

```python
service = ServiceClass(
    param1=value1, param2=value2
)  # May still use @depends.inject for some params
depends.set(ProtocolType, service)
```

### Reusing Registered Services

```python
# GitService registered as both GitInterface and GitServiceProtocol
git_service = depends.get_sync(GitInterface)
depends.set(GitServiceProtocol, git_service)
```

______________________________________________________________________

**Document Version**: 1.0
**Next Update**: After VersionAnalyzer and missing services discovered
**Status**: Active Reference for Phase 2 Implementation
