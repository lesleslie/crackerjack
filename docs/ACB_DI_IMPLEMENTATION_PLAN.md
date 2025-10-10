# ACB Dependency Injection Implementation Plan

**Status**: Phase 2 of Comprehensive Improvement Plan
**Priority**: High (targeting 1,200+ line reduction)
**Integration Score Goal**: 6/10 → 8/10

## Executive Summary

Replace crackerjack's manual dependency injection with ACB's `depends.inject` decorators to:
- Eliminate 1,200+ lines of boilerplate DI code
- Improve testability (easier mocking)
- Maintain protocol-based typing
- Preserve cache adapter functionality (critical - already working)

## Current State Analysis

### Successful ACB Integration Reference
✅ **Cache Adapter** (`crackerjack/services/acb_cache_adapter.py`):
- 472 lines of working ACB integration
- Uses `aiocache.SimpleMemoryCache` directly (same as ACB internally)
- Provides sync wrapper over async operations
- 29 passing tests demonstrating stability

**Key Pattern from Cache Adapter**:
```python
# Direct instantiation - no ACB DI used yet
def __init__(self, cache_dir: Path | None = None, enable_disk_cache: bool = True):
    self.cache_dir = cache_dir or Path.cwd() / ".crackerjack" / "cache"
    self._cache = SimpleMemoryCache(serializer=PickleSerializer(), namespace="crackerjack:")
    self._loop = asyncio.new_event_loop()
```

### Current Manual DI Pattern (WorkflowOrchestrator)

**Location**: `crackerjack/core/workflow_orchestrator.py:2025-2083`

```python
class WorkflowOrchestrator:
    def __init__(self, console: Console | None = None, pkg_path: Path | None = None, ...):
        self.console = console or Console(force_terminal=True)
        self.pkg_path = pkg_path or Path.cwd()

        # Import protocols for type hints
        from crackerjack.models.protocols import (
            ConfigMergeServiceProtocol,
            FileSystemInterface,
            GitInterface,
            HookManager,
            PublishManager,
            TestManagerProtocol,
        )

        # Manual DI container creation
        from .enhanced_container import create_enhanced_container
        self.container = create_enhanced_container(
            console=self.console,
            pkg_path=self.pkg_path,
            dry_run=self.dry_run,
            verbose=self.verbose,
        )

        # Manual service retrieval from container
        self.session = SessionCoordinator(self.console, self.pkg_path, self.web_job_id)
        self.phases = PhaseCoordinator(
            console=self.console,
            pkg_path=self.pkg_path,
            session=self.session,
            filesystem=self.container.get(FileSystemInterface),      # Manual
            git_service=self.container.get(GitInterface),            # Manual
            hook_manager=self.container.get(HookManager),            # Manual
            test_manager=self.container.get(TestManagerProtocol),    # Manual
            publish_manager=self.container.get(PublishManager),      # Manual
            config_merge_service=self.container.get(ConfigMergeServiceProtocol),  # Manual
        )

        self.pipeline = WorkflowPipeline(...)
```

**Problems**:
1. ❌ Verbose manual service retrieval (6+ `container.get()` calls)
2. ❌ Repeated parameter passing (console, pkg_path)
3. ❌ No automatic dependency resolution
4. ❌ Hard to mock for testing
5. ❌ Boilerplate repeated across multiple classes

### Current Container Implementation

**Location**: `crackerjack/core/enhanced_container.py`

```python
class EnhancedDependencyContainer:
    """Custom DI container with service lifetime management."""

    def __init__(self):
        self._services: dict[str, ServiceDescriptor] = {}
        self._singletons: dict[str, Any] = {}
        self._scopes: dict[str, ServiceScope] = {}
        self._lock = threading.Lock()

    def register(self, interface: type, implementation: type | None = None, ...):
        """Manual service registration"""
        # Complex registration logic

    def get(self, interface: type) -> Any:
        """Manual service resolution"""
        # Complex resolution logic with dependency injection
```

**Analysis**:
- 400+ lines of custom DI container code
- Duplicates ACB's `depends` functionality
- Thread-safe singleton management (ACB handles this)
- Automatic dependency resolution (ACB handles this)
- Service lifetime management (ACB handles this)

## ACB DI Architecture

### ACB's Dependency System

ACB provides a lightweight, powerful DI system through `acb.depends`:

```python
from acb.depends import depends

# PATTERN 1: Direct registration
depends.set(MyService)  # Register service class
depends.set(MyService, instance)  # Register instance

# PATTERN 2: Automatic retrieval
service = depends.get(MyService)  # Get or create instance

# PATTERN 3: Decorator injection
from acb.depends import depends

@depends.inject
class MyClass:
    service: MyServiceProtocol = depends()  # Auto-injected

    def method(self):
        # Use self.service automatically
```

### ACB DI Features

1. **Automatic Singleton Management**: Services are singletons by default
2. **Type-Based Resolution**: Uses type annotations for dependency lookup
3. **Lazy Initialization**: Services created on first access
4. **Thread-Safe**: Built-in locking for concurrent access
5. **Protocol Support**: Works seamlessly with Python protocols (our current pattern)

## Implementation Strategy

### Phase 1: ACB DI Configuration (Day 1)

**Goal**: Configure ACB's DI system with crackerjack services

**Tasks**:
1. Create `crackerjack/core/acb_di_config.py` for centralized DI setup
2. Register all service protocols with ACB's depends system
3. Maintain protocol-based typing (coordinate with architecture-council)
4. Test basic DI functionality

**Implementation**:

```python
# crackerjack/core/acb_di_config.py
"""ACB Dependency Injection Configuration for Crackerjack.

Centralizes all service registrations with ACB's depends system.
"""
from pathlib import Path
from acb.depends import depends
from rich.console import Console

from crackerjack.models.protocols import (
    FileSystemInterface,
    GitInterface,
    HookManager,
    TestManagerProtocol,
    PublishManager,
    ConfigMergeServiceProtocol,
    ConfigurationServiceProtocol,
    SecurityServiceProtocol,
    CoverageRatchetProtocol,
)


def configure_acb_dependencies(
    console: Console,
    pkg_path: Path,
    dry_run: bool = False,
    verbose: bool = False,
) -> None:
    """Configure ACB dependency injection for all crackerjack services.

    Args:
        console: Rich console for output
        pkg_path: Package path for services
        dry_run: Dry run mode flag
        verbose: Verbose output flag
    """
    # Register core dependencies
    depends.set(Console, console)
    depends.set(Path, pkg_path)  # Register as Path type for pkg_path

    # Register filesystem service
    from crackerjack.services.filesystem import FileSystemService
    filesystem = FileSystemService(console, pkg_path)
    depends.set(FileSystemInterface, filesystem)

    # Register git service
    from crackerjack.services.git import GitService
    git_service = GitService(console, pkg_path)
    depends.set(GitInterface, git_service)

    # Register hook manager
    from crackerjack.managers.hook_manager import HookManagerImpl
    hook_manager = HookManagerImpl(console, pkg_path)
    depends.set(HookManager, hook_manager)

    # Register test manager
    from crackerjack.managers.test_manager import TestManager
    test_manager = TestManager(console, pkg_path)
    depends.set(TestManagerProtocol, test_manager)

    # Register publish manager
    from crackerjack.managers.publish_manager import PublishManagerImpl
    publish_manager = PublishManagerImpl(console, pkg_path, git_service)
    depends.set(PublishManager, publish_manager)

    # Register config merge service
    from crackerjack.services.config_merge import ConfigMergeService
    config_merge = ConfigMergeService(console, pkg_path, filesystem)
    depends.set(ConfigMergeServiceProtocol, config_merge)

    # Register security service
    from crackerjack.services.security import SecurityService
    security = SecurityService(console, pkg_path)
    depends.set(SecurityServiceProtocol, security)

    # Register coverage ratchet
    from crackerjack.services.coverage_ratchet import CoverageRatchetService
    coverage_ratchet = CoverageRatchetService(console, pkg_path)
    depends.set(CoverageRatchetProtocol, coverage_ratchet)

    # Register cache adapter (already using ACB internally)
    from crackerjack.services.acb_cache_adapter import ACBCrackerjackCache
    cache = ACBCrackerjackCache()
    depends.set(ACBCrackerjackCache, cache)


def clear_acb_dependencies() -> None:
    """Clear all ACB dependency registrations.

    Useful for testing to ensure clean state between tests.
    """
    # ACB doesn't provide a clear_all() method, so we'll need to track
    # registered types and clear them individually if needed
    pass
```

### Phase 2: Migrate WorkflowOrchestrator (Day 2)

**Goal**: Replace largest manual DI with ACB patterns

**Before** (59 lines of boilerplate):
```python
class WorkflowOrchestrator:
    def __init__(self, console: Console | None = None, pkg_path: Path | None = None, ...):
        self.console = console or Console(force_terminal=True)
        self.pkg_path = pkg_path or Path.cwd()

        from .enhanced_container import create_enhanced_container
        self.container = create_enhanced_container(...)

        self.session = SessionCoordinator(...)
        self.phases = PhaseCoordinator(
            console=self.console,
            pkg_path=self.pkg_path,
            session=self.session,
            filesystem=self.container.get(FileSystemInterface),
            git_service=self.container.get(GitInterface),
            hook_manager=self.container.get(HookManager),
            test_manager=self.container.get(TestManagerProtocol),
            publish_manager=self.container.get(PublishManager),
            config_merge_service=self.container.get(ConfigMergeServiceProtocol),
        )
        self.pipeline = WorkflowPipeline(...)
```

**After** (15 lines - 74% reduction):
```python
from acb.depends import depends

class WorkflowOrchestrator:
    def __init__(
        self,
        console: Console | None = None,
        pkg_path: Path | None = None,
        dry_run: bool = False,
        web_job_id: str | None = None,
        verbose: bool = False,
        debug: bool = False,
    ):
        # Configure ACB DI
        from .acb_di_config import configure_acb_dependencies
        configure_acb_dependencies(
            console=console or Console(force_terminal=True),
            pkg_path=pkg_path or Path.cwd(),
            dry_run=dry_run,
            verbose=verbose,
        )

        # Get services via ACB DI
        self.console = depends.get(Console)
        self.pkg_path = depends.get(Path)

        # Coordinators with automatic DI
        self.session = SessionCoordinator(
            console=self.console,
            pkg_path=self.pkg_path,
            web_job_id=web_job_id
        )

        self.phases = PhaseCoordinator(
            console=self.console,
            pkg_path=self.pkg_path,
            session=self.session,
            # All other dependencies auto-injected via depends.inject decorator
        )

        self.pipeline = WorkflowPipeline(
            console=self.console,
            pkg_path=self.pkg_path,
            session=self.session,
            phases=self.phases,
        )
```

**PhaseCoordinator Migration**:
```python
from acb.depends import depends

@depends.inject
class PhaseCoordinator:
    # Auto-injected dependencies
    filesystem: FileSystemInterface = depends()
    git_service: GitInterface = depends()
    hook_manager: HookManager = depends()
    test_manager: TestManagerProtocol = depends()
    publish_manager: PublishManager = depends()
    config_merge_service: ConfigMergeServiceProtocol = depends()

    def __init__(
        self,
        console: Console,
        pkg_path: Path,
        session: SessionCoordinator,
    ):
        self.console = console
        self.pkg_path = pkg_path
        self.session = session
        # All protocol dependencies already injected by ACB
```

### Phase 3: Migrate Other Coordinators (Day 3)

**Priority Order**:
1. SessionCoordinator
2. WorkflowPipeline
3. HookManagerImpl
4. TestManager
5. PublishManagerImpl

**Pattern for Each**:
```python
from acb.depends import depends

@depends.inject
class ServiceName:
    # Declare injected dependencies
    dependency: ProtocolType = depends()

    def __init__(self, explicit_params: ...):
        # Only explicit constructor parameters
        # Dependencies auto-injected
```

### Phase 4: Update Tests (Day 4)

**Test Migration Pattern**:

**Before**:
```python
def test_service():
    console = Console()
    pkg_path = Path.cwd()

    # Manual mocking
    mock_filesystem = Mock(spec=FileSystemInterface)
    mock_git = Mock(spec=GitInterface)

    # Manual injection
    service = MyService(
        console=console,
        pkg_path=pkg_path,
        filesystem=mock_filesystem,
        git_service=mock_git,
    )

    # Test...
```

**After**:
```python
from acb.depends import depends

def test_service():
    # Setup ACB DI with mocks
    mock_filesystem = Mock(spec=FileSystemInterface)
    mock_git = Mock(spec=GitInterface)

    depends.set(FileSystemInterface, mock_filesystem)
    depends.set(GitInterface, mock_git)

    # Service gets mocks automatically
    service = MyService(
        console=Console(),
        pkg_path=Path.cwd(),
    )

    # Test...

    # Cleanup (in fixture)
    depends.clear()
```

**Pytest Fixture**:
```python
@pytest.fixture(autouse=True)
def reset_acb_dependencies():
    """Reset ACB dependencies between tests."""
    yield
    # Clear all registered dependencies
    # (ACB doesn't have clear() - will need custom tracking)
```

### Phase 5: Remove Old Container (Day 5)

**Files to Remove**:
- `crackerjack/core/enhanced_container.py` (400+ lines)
- Any other custom DI container code

**Verification**:
1. All tests pass (29 cache + 26 decorator + others)
2. No references to `enhanced_container` remain
3. ACB DI integration score: 8/10

## Success Metrics

### Quantitative Goals
- ✅ Remove 1,200+ lines of manual DI boilerplate
- ✅ Pass all 29 cache adapter tests (no regression)
- ✅ Pass all 26 decorator tests
- ✅ ACB integration score: 6/10 → 8/10

### Qualitative Goals
- ✅ Improved testability (easier mocking)
- ✅ Cleaner, more maintainable code
- ✅ Protocol-based typing maintained
- ✅ No breaking changes to public API

## Risk Management

### Critical Risks

**Risk 1: Cache Adapter Regression**
- **Impact**: HIGH - Cache is critical for performance
- **Mitigation**:
  - Run cache tests after every change
  - Keep cache adapter unchanged (already working)
  - Test cache integration with new DI

**Risk 2: Protocol Typing Conflicts**
- **Impact**: MEDIUM - Architecture-council doing concurrent work
- **Mitigation**:
  - Coordinate on protocol definitions
  - Use same protocol imports
  - Share protocol migration plan

**Risk 3: Test Migration Complexity**
- **Impact**: MEDIUM - Many tests use manual DI
- **Mitigation**:
  - Migrate tests incrementally
  - Create reusable test fixtures
  - Document ACB DI testing patterns

### Rollback Plan

If critical issues arise:
1. Revert to manual DI (git revert)
2. Keep ACB cache adapter (it works)
3. Document lessons learned
4. Retry with revised approach

## Timeline

| Day | Tasks | Deliverables |
|-----|-------|--------------|
| 1 | ACB DI Configuration | `acb_di_config.py`, service registration |
| 2 | WorkflowOrchestrator migration | Updated orchestrator, passing tests |
| 3 | Other coordinators migration | All coordinators using ACB DI |
| 4 | Test migration | Updated test suite, new fixtures |
| 5 | Container removal, verification | Clean codebase, all tests passing |

## Integration Points

### With Other Threads

**Main Thread (Template Extraction)**:
- **Overlap**: Minimal (different files)
- **Coordination**: Share protocol definitions

**Architecture-Council (Protocol Migration)**:
- **Overlap**: HIGH (both use protocols)
- **Coordination**: Daily sync on protocol changes
- **Shared Goal**: Maintain protocol-based typing

**Cache Adapter**:
- **Status**: Already working with ACB
- **Action**: Preserve, use as reference
- **Tests**: 29 tests must continue passing

## Post-Implementation

### Documentation Updates
1. Update README with ACB DI patterns
2. Document ACB DI testing approach
3. Add examples for common DI scenarios

### Code Quality
- Run crackerjack: `python -m crackerjack`
- Expected improvements:
  - Reduced complexity (simpler constructors)
  - Better test coverage (easier mocking)
  - Cleaner architecture (no custom container)

## References

- **ACB Framework Expertise**: See system prompt for ACB patterns
- **Cache Adapter**: `/Users/les/Projects/crackerjack/crackerjack/services/acb_cache_adapter.py`
- **Protocol Definitions**: `/Users/les/Projects/crackerjack/crackerjack/models/protocols.py`
- **Current Container**: `/Users/les/Projects/crackerjack/crackerjack/core/enhanced_container.py`

---

**Next Steps**: Begin Phase 1 - ACB DI Configuration
