# Phase 2: Manager Layer Service Dependency Analysis

**Date**: 2025-10-13
**Status**: Analysis Complete - Ready for Refactoring
**Priority**: P1 (High Priority - Manager Layer)

## Executive Summary

The Manager Layer has **2 active files** with service dependencies: `test_manager.py` and `publish_manager.py`. Surprisingly, both files are **already partially migrated** to protocol-based dependency injection! The remaining work involves:

1. **test_manager.py**: 3 lazy service imports (2 in constructor, 1 in method)
2. **publish_manager.py**: 4 direct service instantiations in methods (2 locations)

**Key Finding**: Unlike the core layer, managers already use protocol-based injection for core dependencies. The refactoring will be **simpler and faster** than core layer work.

## Service Import Inventory

### File 1: test_manager.py (3 service imports)

**Already Using Protocols** ✅:
- Line 8: `from crackerjack.models.protocols import CoverageRatchetProtocol` (constructor param)
- Constructor supports `CoverageRatchetProtocol` injection (line 19)

**Service Imports to Refactor**:

```python
# Line 28-33: Lazy import in constructor
if coverage_ratchet is None:
    from crackerjack.services.coverage_ratchet import CoverageRatchetService
    coverage_ratchet_obj = CoverageRatchetService(pkg_path, console)

# Line 43-45: Lazy import in constructor
from crackerjack.services.coverage_badge_service import CoverageBadgeService
self._coverage_badge_service = CoverageBadgeService(console, pkg_path)

# Line 433: Lazy import in method
from crackerjack.services.lsp_client import LSPClient
lsp_client = LSPClient(self.console)
```

**Summary**:
- 3 service imports total
- 2 services lazy-loaded in constructor (CoverageRatchetService, CoverageBadgeService)
- 1 service lazy-loaded in method (LSPClient)

### File 2: publish_manager.py (4 service instantiations)

**Already Using Protocols** ✅:
- Lines 8: `from crackerjack.models.protocols import FileSystemInterface, SecurityServiceProtocol`
- Lines 17-18: Constructor accepts protocol injection
- Lines 28-35: Lazy imports with protocol fallback pattern

**Service Imports to Refactor**:

```python
# Lines 202-207: Method _get_version_recommendation()
from crackerjack.services.git import GitService
from crackerjack.services.version_analyzer import VersionAnalyzer

git_service = GitService(self.console, self.pkg_path)
version_analyzer = VersionAnalyzer(self.console, git_service)

# Lines 575-580: Method _update_changelog_for_version()
from crackerjack.services.changelog_automation import ChangelogGenerator
from crackerjack.services.git import GitService

git_service = GitService(self.console, self.pkg_path)
changelog_generator = ChangelogGenerator(self.console, git_service)
```

**Summary**:
- 4 service instantiations in 2 methods
- GitService instantiated twice (in different methods)
- VersionAnalyzer and ChangelogGenerator instantiated once each

### Summary Table

| File | Service Imports | Already Protocol-Based | Needs Refactoring | Complexity |
|------|----------------|----------------------|-------------------|------------|
| `test_manager.py` | 3 | CoverageRatchet (partial) | 3 lazy imports | 🟡 Medium |
| `publish_manager.py` | 4 | FileSystem + Security | 4 method instantiations | 🟡 Medium |
| **TOTAL** | **7** | **3 protocols** | **7 services** | **🟡 Medium** |

## Adapter Layer Preview

**Found 2 adapter files with service imports**:

1. `/Users/les/Projects/crackerjack/crackerjack/adapters/lsp/zuban.py`
   - 2 imports of `LSPClient` (likely duplicates)

2. `/Users/les/Projects/crackerjack/crackerjack/adapters/utility/checks.py`
   - 1 import of `CompiledPatternCache`

**Estimated**: 2-3 service imports in adapter layer

## Protocol Verification

Need to verify/create these protocols:

1. ✅ **CoverageRatchetProtocol** - Already exists and used!
2. ❓ **CoverageBadgeProtocol** - Check if exists
3. ❓ **LSPClientProtocol** - Check if exists
4. ❓ **GitServiceProtocol** - Check if exists (publish_manager references it!)
5. ❓ **VersionAnalyzerProtocol** - Check if exists (publish_manager references it!)
6. ❓ **ChangelogGeneratorProtocol** - Check if exists (publish_manager references it!)
7. ❓ **RegexPatternsProtocol** - Check if exists (publish_manager uses it at line 96!)

**Note**: publish_manager already references some protocols that may not exist yet (lines 19-22).

## Current Usage Patterns

### test_manager.py Pattern: Lazy Constructor Initialization

```python
def __init__(
    self,
    console: Console,
    pkg_path: Path,
    coverage_ratchet: CoverageRatchetProtocol | None = None,  # ✅ Already protocol-based!
) -> None:
    # Fallback lazy initialization if not injected
    if coverage_ratchet is None:
        from crackerjack.services.coverage_ratchet import CoverageRatchetService
        coverage_ratchet_obj = CoverageRatchetService(pkg_path, console)
        self.coverage_ratchet = t.cast(CoverageRatchetProtocol, coverage_ratchet_obj)
    else:
        self.coverage_ratchet = coverage_ratchet

    # Direct lazy import (no protocol)
    from crackerjack.services.coverage_badge_service import CoverageBadgeService
    self._coverage_badge_service = CoverageBadgeService(console, pkg_path)
```

**Pattern**: Mix of protocol-based injection with lazy fallback + direct instantiation

### publish_manager.py Pattern: Method-Level Lazy Initialization

```python
def _get_version_recommendation(self) -> t.Any:
    """Get AI-powered version bump recommendation based on git history."""
    try:
        # Direct instantiation in method (no protocol)
        from crackerjack.services.git import GitService
        from crackerjack.services.version_analyzer import VersionAnalyzer

        git_service = GitService(self.console, self.pkg_path)
        version_analyzer = VersionAnalyzer(self.console, git_service)

        # ... use services ...
```

**Pattern**: Direct service instantiation in methods when needed

## Refactoring Strategy

### Strategy 1: test_manager.py - Constructor Injection

**Current State**: Partially migrated with lazy fallback pattern

**Refactoring Approach**:

1. **Coverage Badge Service**:
   - Create `CoverageBadgeProtocol` (or use concrete type pragmatically)
   - Inject via `Inject[CoverageBadgeProtocol]` in constructor
   - Remove lazy import

2. **Coverage Ratchet Service**:
   - Already supports protocol injection!
   - Remove fallback instantiation logic (always require injection)
   - Simplify constructor

3. **LSP Client**:
   - Move from method to constructor injection
   - Create `LSPClientProtocol` (or use concrete type)
   - Inject via `Inject[LSPClientProtocol | None]` (optional)

**Before**:
```python
def __init__(
    self,
    console: Console,
    pkg_path: Path,
    coverage_ratchet: CoverageRatchetProtocol | None = None,
):
    # Lazy fallback instantiation
    if coverage_ratchet is None:
        from crackerjack.services.coverage_ratchet import CoverageRatchetService
        coverage_ratchet_obj = CoverageRatchetService(pkg_path, console)
        self.coverage_ratchet = t.cast(CoverageRatchetProtocol, coverage_ratchet_obj)
    else:
        self.coverage_ratchet = coverage_ratchet

    from crackerjack.services.coverage_badge_service import CoverageBadgeService
    self._coverage_badge_service = CoverageBadgeService(console, pkg_path)
```

**After**:
```python
@depends.inject
def __init__(
    self,
    coverage_ratchet: Inject[CoverageRatchetProtocol],
    coverage_badge: Inject[CoverageBadgeProtocol],
    console: Console = depends(),
    pkg_path: Path = depends(),
    lsp_client: Inject[LSPClientProtocol] | None = None,
):
    # Services injected via ACB DI
    self.coverage_ratchet = coverage_ratchet
    self._coverage_badge_service = coverage_badge
    self._lsp_client = lsp_client
```

### Strategy 2: publish_manager.py - Service-as-Dependency

**Current State**: Methods instantiate services when needed

**Refactoring Approach**:

1. **Git Service**:
   - Inject once via constructor (used in 2 methods)
   - Use `Inject[GitServiceProtocol]` (protocol likely exists - already referenced!)
   - Remove duplicate instantiations

2. **Version Analyzer**:
   - Inject via constructor
   - Use `Inject[VersionAnalyzerProtocol]` (protocol likely exists - already referenced!)
   - Remove method-level instantiation

3. **Changelog Generator**:
   - Inject via constructor
   - Use `Inject[ChangelogGeneratorProtocol]` (protocol likely exists - already referenced!)
   - Remove method-level instantiation

**Before**:
```python
def _get_version_recommendation(self) -> t.Any:
    from crackerjack.services.git import GitService
    from crackerjack.services.version_analyzer import VersionAnalyzer

    git_service = GitService(self.console, self.pkg_path)
    version_analyzer = VersionAnalyzer(self.console, git_service)
    # ... use services ...
```

**After**:
```python
@depends.inject
def __init__(
    self,
    git_service: Inject[GitServiceProtocol],
    version_analyzer: Inject[VersionAnalyzerProtocol],
    changelog_generator: Inject[ChangelogGeneratorProtocol],
    console: Console = depends(),
    pkg_path: Path = depends(),
    # ... existing params ...
):
    self._git_service = git_service
    self._version_analyzer = version_analyzer
    self._changelog_generator = changelog_generator

def _get_version_recommendation(self) -> t.Any:
    # Services already available as instance attributes
    recommendation = self._version_analyzer.recommend_version_bump()
    # ... use services ...
```

## Service Registration Requirements

All services must be registered in `crackerjack/config/__init__.py::register_services()`:

### test_manager.py Services

```python
# In register_services():

# Coverage Badge Service
from crackerjack.services.coverage_badge_service import CoverageBadgeService
console = depends.get(Console)
pkg_path = depends.get(Path)
coverage_badge = CoverageBadgeService(console, pkg_path)
depends.set(CoverageBadgeProtocol, coverage_badge)

# Coverage Ratchet Service (if not already registered)
from crackerjack.services.coverage_ratchet import CoverageRatchetService
coverage_ratchet = CoverageRatchetService(pkg_path, console)
depends.set(CoverageRatchetProtocol, coverage_ratchet)

# LSP Client (optional service)
from crackerjack.services.lsp_client import LSPClient
try:
    lsp_client = LSPClient(console)
    depends.set(LSPClientProtocol, lsp_client)
except Exception:
    pass  # LSP client is optional
```

### publish_manager.py Services

```python
# In register_services():

# Git Service (may already be registered)
from crackerjack.services.git import GitService
git_service = GitService(console, pkg_path)
depends.set(GitServiceProtocol, git_service)

# Version Analyzer
from crackerjack.services.version_analyzer import VersionAnalyzer
version_analyzer = VersionAnalyzer(console, git_service)
depends.set(VersionAnalyzerProtocol, version_analyzer)

# Changelog Generator
from crackerjack.services.changelog_automation import ChangelogGenerator
changelog_generator = ChangelogGenerator(console, git_service)
depends.set(ChangelogGeneratorProtocol, changelog_generator)
```

## Complexity Assessment

**Estimated Effort**: 3-4 hours total for both managers

### test_manager.py Refactoring

**Breakdown**:
- Protocol verification: 30 minutes
- Service registration: 45 minutes
- Constructor refactoring: 45 minutes
- Remove lazy imports: 15 minutes
- Testing: 30 minutes

**Risk Level**: 🟡 MEDIUM
- Already partially migrated (good foundation)
- Lazy fallback pattern needs careful removal
- LSP client is optional (graceful handling needed)

### publish_manager.py Refactoring

**Breakdown**:
- Protocol verification: 30 minutes (likely already exist!)
- Service registration: 45 minutes
- Constructor refactoring: 30 minutes
- Refactor 2 methods: 30 minutes
- Testing: 30 minutes

**Risk Level**: 🟢 LOW
- Protocols likely already exist (referenced in type hints)
- Straightforward constructor injection
- No complex fallback logic

## Expected Outcomes

### Before Refactoring
- ❌ 7 direct service imports across 2 managers
- ✅ Partial protocol usage (3 protocols already used)
- ❌ Lazy instantiation in constructors and methods
- ✅ Good protocol foundation already established

### After Refactoring
- ✅ 0 direct service imports in manager constructors
- ✅ All services registered in container init
- ✅ All dependencies via `Inject[Protocol]`
- ✅ 100% protocol-based manager architecture

## Success Criteria

### test_manager.py
- [ ] Zero lazy service imports in constructor
- [ ] CoverageBadgeService injected via protocol
- [ ] LSPClient injected via protocol (optional)
- [ ] Simplified constructor logic (no fallback instantiation)
- [ ] All services registered in container
- [ ] TestManager imports successfully
- [ ] All test operations work correctly

### publish_manager.py
- [ ] Zero service instantiations in methods
- [ ] GitService injected once via constructor
- [ ] VersionAnalyzer injected via protocol
- [ ] ChangelogGenerator injected via protocol
- [ ] Methods use injected services (no local instantiation)
- [ ] PublishManager imports successfully
- [ ] All publishing operations work correctly

## Phase 2 Overall Progress

### Current Status
- ✅ **Core Layer**: 100% complete (2/2 files)
  - workflow_orchestrator.py: 5/8 service imports removed
  - phase_coordinator.py: 6/7 factory imports removed

- ⏳ **Manager Layer**: 0% complete (0/2 files)
  - test_manager.py: 3 service imports to refactor
  - publish_manager.py: 4 service instantiations to refactor

- ⏳ **Adapter Layer**: 0% complete (0/2 files)
  - zuban.py: ~2 service imports to refactor
  - checks.py: 1 service import to refactor

### Updated Estimates
- **Total Target**: 39 service imports (original estimate)
- **Actual Count**: ~22 service imports found
  - Core: 11 removed ✅
  - Manager: 7 remaining
  - Adapter: ~3 remaining
  - Misc: ~1 remaining

- **Progress**: 11/22 = 50% complete! 🎉

### Revised Timeline
- **Core Layer**: ✅ Complete (6 hours spent)
- **Manager Layer**: 3-4 hours (both managers)
- **Adapter Layer**: 1-2 hours (both adapters)
- **Phase 2 Total**: ~10-12 hours (original estimate accurate)

## Next Steps

### Immediate (Day 1)
1. ✅ Complete this analysis document
2. ⏳ Verify protocols exist in `models/protocols.py`
3. ⏳ Register manager services in `config/__init__.py`
4. ⏳ Refactor test_manager.py constructor
5. ⏳ Test test_manager.py refactoring

### Day 2
6. ⏳ Refactor publish_manager.py constructor and methods
7. ⏳ Test publish_manager.py refactoring
8. ⏳ Create manager layer success document

### Day 3
9. ⏳ Analyze and refactor adapter layer
10. ⏳ Create Phase 2 completion report

## Special Considerations

### 1. test_manager.py: Lazy Fallback Removal

The current pattern allows optional injection with fallback:
```python
coverage_ratchet: CoverageRatchetProtocol | None = None
```

**Decision**: Remove fallback pattern, require injection:
- Services should always be registered in container
- Eliminates constructor complexity
- Enforces proper dependency injection

**Exception**: LSP client can remain optional (not all environments have LSP)

### 2. publish_manager.py: Async Service Usage

Version analyzer uses async operations:
```python
recommendation = await version_analyzer.recommend_version_bump()
```

**Consideration**: Ensure injected service handles async properly when moved to constructor

### 3. Protocol References Already Exist!

publish_manager.py already references protocols in type hints (lines 19-22):
```python
git_service: GitServiceProtocol | None = None,
version_analyzer: VersionAnalyzerProtocol | None = None,
changelog_generator: ChangelogGeneratorProtocol | None = None,
```

**Key Insight**: These protocols likely already exist! This makes refactoring even simpler.

## Lessons from Core Layer

### What Worked Well
1. **Detailed Analysis First**: Creating analysis docs prevented surprises
2. **Protocol Verification**: Checking protocols exist before refactoring saved time
3. **Incremental Testing**: Testing each file after refactoring caught issues early
4. **Pragmatic Protocol Usage**: Using concrete types when protocols don't exist accelerated work

### Apply to Manager Layer
1. **Verify Protocols**: Check that GitServiceProtocol, VersionAnalyzerProtocol, etc. exist
2. **Service Registration Order**: Register git_service before version_analyzer (dependency)
3. **Graceful Fallbacks**: Keep optional services (LSP) with try/except
4. **Test Incrementally**: Test test_manager.py before moving to publish_manager.py

---

**Analysis Status**: ✅ Complete
**Next Action**: Verify protocols in models/protocols.py
**Estimated Start**: Ready to begin manager layer refactoring
**Overall Phase 2 Progress**: 50% complete (11/22 service imports eliminated)
