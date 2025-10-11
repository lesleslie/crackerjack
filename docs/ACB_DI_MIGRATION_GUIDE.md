# ACB Dependency Injection Migration Guide

## Overview

This guide documents the migration from the custom `ACBDependencyRegistry` wrapper to pure ACB dependency injection patterns in Crackerjack.

## Core Principles

### 1. Use ACB Directly - No Wrappers

**❌ Old Pattern (Custom Registry)**
```python
from crackerjack.core.acb_di_config import ACBDependencyRegistry

ACBDependencyRegistry.register(FileSystemInterface, filesystem)
ACBDependencyRegistry.clear_all()
```

**✅ New Pattern (Pure ACB)**
```python
from acb.depends import depends

depends.set(FileSystemInterface, filesystem)
# No need for custom clear - ACB handles lifecycle
```

**Why**: ACB already provides:
- Singleton management
- Thread safety
- Type-based lookup
- No need for custom tracking

### 2. SQL Adapter in Synchronous Context

**✅ Correct Pattern**
```python
from acb.adapters import import_adapter_fast
from acb.depends import depends

# Get adapter class (not instance)
SQLAdapter = import_adapter_fast("sql", "sqlite")

# Check if already registered to avoid duplicate initialization
try:
    sql_adapter = depends.get(SQLAdapter)
except Exception:
    # First initialization
    sql_adapter = SQLAdapter()
    depends.set(SQLAdapter, sql_adapter)
```

**Why `import_adapter_fast()`?**
- Synchronous context (orchestrator `__init__`)
- Avoids async event loop conflicts
- ACB's recommended pattern for sync initialization

**Configuration Pattern**
```python
import os
from pathlib import Path

# Set environment variables BEFORE adapter initialization
default_state_dir = Path.home() / ".crackerjack" / "state"
default_state_dir.mkdir(parents=True, exist_ok=True)
default_db_path = default_state_dir / "crackerjack.db"
default_db_url = f"sqlite:///{default_db_path}"

os.environ.setdefault("SQL_DATABASE_URL", default_db_url)
os.environ.setdefault("DATABASE_URL", default_db_url)

# NOW load the adapter - it reads from environment
SQLAdapter = import_adapter_fast("sql", "sqlite")
```

### 3. Repository Dependency Pattern

**✅ Constructor Injection (Current Pattern)**
```python
class QualityBaselineRepository:
    def __init__(self, sql_adapter: Any) -> None:
        """Initialize repository with SQL adapter.

        Args:
            sql_adapter: SQL adapter instance (required - must be passed from DI)
        """
        self._sql = sql_adapter
        self._initialized = False
        self._init_lock = asyncio.Lock()
```

**Registration**
```python
from acb.adapters import import_adapter_fast
from acb.depends import depends

# Get SQL adapter from ACB
SQLAdapter = import_adapter_fast("sql", "sqlite")
sql_adapter = depends.get(SQLAdapter)

# Register repositories with SQL adapter injected
baseline_repository = QualityBaselineRepository(sql_adapter)
depends.set(QualityBaselineRepository, baseline_repository)
```

**Alternative: ACB Decorator Pattern (For Async Contexts)**
```python
from acb.depends import depends

class QualityBaselineRepository:
    def __init__(self, sql_adapter=None) -> None:
        # Lazy initialization via ACB
        self._sql = sql_adapter or depends.get(SQLAdapter)

    @depends.inject
    async def create_record(self, data: dict, sql_adapter=depends()) -> Record:
        """Method-level dependency injection."""
        # sql_adapter injected automatically if not provided
        async with sql_adapter.get_session() as session:
            # ...
```

**When to Use Each**:
- **Constructor Injection**: Synchronous initialization (like orchestrator `__init__`)
- **Decorator Pattern**: Async contexts, optional dependencies, testing flexibility

### 4. Service Registration Order

**✅ Dependency-First Order**
```python
def setup_dependencies(console: Console, pkg_path: Path) -> None:
    # 1. Core primitives (no dependencies)
    depends.set(Console, console)
    depends.set(PackagePath, PackagePath(pkg_path))

    # 2. Foundation services (minimal dependencies)
    filesystem = EnhancedFileSystemService()
    depends.set(FileSystemInterface, filesystem)

    # 3. Mid-level services (depend on foundation)
    git_service = GitService(console, pkg_path)
    depends.set(GitInterface, git_service)

    # 4. High-level services (depend on mid-level)
    config_merge = ConfigMergeService(console, filesystem, git_service)
    depends.set(ConfigMergeServiceProtocol, config_merge)

    # 5. Adapters with environment configuration
    _setup_sql_adapter()  # Configures env vars first

    # 6. Data layer (depends on adapters)
    _setup_repositories()  # Uses SQL adapter
```

**Key Points**:
- Register dependencies before dependents
- Configure environment before adapters
- Group related registrations in helper functions

### 5. Custom Type Wrappers

**Problem**: Multiple services need `Path` instances with different meanings
**Solution**: Type wrappers for disambiguation

```python
class PackagePath(Path):
    """Type wrapper for package path to enable dependency injection."""
    pass

# Registration
pkg_path_typed = PackagePath(pkg_path)
depends.set(PackagePath, pkg_path_typed)

# Usage
from acb.depends import depends
pkg_path = depends.get(PackagePath)  # Unambiguous
```

**Why**: ACB uses type-based lookup. Generic types like `Path` would conflict.

### 6. Protocol-Based Interfaces

**✅ Always Import Protocols**
```python
# ❌ WRONG - Don't import concrete classes
from crackerjack.managers.test_manager import TestManager

# ✅ CORRECT - Import protocols
from crackerjack.models.protocols import TestManagerProtocol

# Register concrete implementation under protocol interface
test_manager = TestManager(console, pkg_path)
depends.set(TestManagerProtocol, test_manager)

# Retrieve via protocol
test_manager = depends.get(TestManagerProtocol)
```

**Benefits**:
- Loose coupling
- Easy mocking in tests
- Interface-driven design
- Swap implementations without changing consumers

## Migration Checklist

### Phase 1: Create New Setup Module
- [x] Create `acb_di_setup.py` with pure ACB patterns
- [x] Implement `setup_dependencies()` function
- [x] Add helper functions: `_setup_sql_adapter()`, `_setup_repositories()`
- [x] Add convenience accessors: `get_console()`, `get_pkg_path()`

### Phase 2: Update Orchestrator
- [ ] Update import: `from .acb_di_setup import setup_dependencies`
- [ ] Change call: `setup_dependencies(console, pkg_path, dry_run, verbose)`
- [ ] Verify all `depends.get()` calls work correctly
- [ ] Test orchestrator initialization

### Phase 3: Update Tests
- [ ] Find tests importing `acb_di_config`
- [ ] Update to import `acb_di_setup`
- [ ] Change `configure_acb_dependencies()` to `setup_dependencies()`
- [ ] Update `reset_dependencies()` calls if any

### Phase 4: Remove Old Code
- [ ] Delete `crackerjack/core/acb_di_config.py`
- [ ] Remove any remaining references
- [ ] Run full test suite
- [ ] Verify no import errors

## Testing Patterns

### Test Setup
```python
import pytest
from pathlib import Path
from rich.console import Console
from acb.depends import depends

from crackerjack.core.acb_di_setup import setup_dependencies

@pytest.fixture
def setup_di(tmp_path):
    """Setup ACB dependencies for testing."""
    console = Console()
    setup_dependencies(console, tmp_path)
    yield
    # ACB handles cleanup automatically

def test_with_dependencies(setup_di):
    """Test that uses registered dependencies."""
    from crackerjack.models.protocols import FileSystemInterface

    filesystem = depends.get(FileSystemInterface)
    assert filesystem is not None
```

### Mocking Dependencies
```python
import pytest
from unittest.mock import Mock
from acb.depends import depends

@pytest.fixture
def mock_filesystem():
    """Mock filesystem for testing."""
    mock_fs = Mock(spec=FileSystemInterface)
    depends.set(FileSystemInterface, mock_fs)
    yield mock_fs
    # No explicit cleanup needed

def test_with_mock(mock_filesystem):
    """Test using mocked dependency."""
    service = MyService()  # Uses depends.get(FileSystemInterface) internally
    service.do_something()
    mock_filesystem.read_file.assert_called_once()
```

## Common Patterns

### Pattern 1: Adapter with Settings
```python
from acb.adapters import import_adapter_fast
from acb.config import Settings
import os

# Configure environment BEFORE loading adapter
os.environ["CACHE_BACKEND"] = "redis"
os.environ["CACHE_URL"] = "redis://localhost:6379/0"

# Load adapter - reads environment automatically
CacheAdapter = import_adapter_fast("cache", "redis")
cache = CacheAdapter()
depends.set(CacheAdapter, cache)
```

### Pattern 2: Service with Multiple Dependencies
```python
from acb.depends import depends

class MyService:
    def __init__(self):
        # Retrieve all dependencies via ACB
        self.console = depends.get(Console)
        self.filesystem = depends.get(FileSystemInterface)
        self.git = depends.get(GitInterface)
        self.cache = depends.get(CacheAdapter)

    def process(self):
        # Use dependencies
        self.console.print("Processing...")
        content = self.filesystem.read_file("config.yaml")
        # ...

# Register
service = MyService()
depends.set(MyService, service)
```

### Pattern 3: Conditional Registration
```python
from acb.depends import depends

def setup_optional_service(enabled: bool):
    """Register service only if enabled."""
    if not enabled:
        return

    service = OptionalService()
    depends.set(OptionalService, service)

# Usage - safe to call depends.get() even if not registered
try:
    optional = depends.get(OptionalService)
except Exception:
    optional = None  # Service not enabled
```

## Benefits of Pure ACB Patterns

1. **Simplicity**: No custom wrappers - just ACB
2. **Correctness**: Following ACB's intended patterns
3. **Maintainability**: Standard patterns easier to understand
4. **Testing**: Built-in support for mocking and cleanup
5. **Performance**: ACB's optimized singleton management
6. **Type Safety**: Better IDE support and static analysis

## Anti-Patterns to Avoid

### ❌ Don't Create Custom Registries
```python
# BAD - Custom wrapper defeats ACB's purpose
class MyRegistry:
    def register(self, interface, instance):
        depends.set(interface, instance)
        self.track_registration()  # Unnecessary
```

### ❌ Don't Manually Track Registrations
```python
# BAD - ACB already handles this
_registered_types: set[type] = set()
depends.set(MyService, service)
_registered_types.add(MyService)  # Unnecessary
```

### ❌ Don't Use Async Adapters in Sync Context
```python
# BAD - Will cause event loop conflicts
from acb.adapters import import_adapter
SQLAdapter = import_adapter("sql")  # Returns async adapter class

# GOOD - Use fast variant for sync contexts
from acb.adapters import import_adapter_fast
SQLAdapter = import_adapter_fast("sql", "sqlite")
```

### ❌ Don't Register Without Type Hint
```python
# BAD - Generic Path type conflicts
depends.set(Path, my_path)

# GOOD - Use type wrapper
class PackagePath(Path):
    pass
depends.set(PackagePath, PackagePath(my_path))
```

## Troubleshooting

### Issue: "Dependency not found"
**Cause**: Service not registered or registered after it's needed
**Solution**: Check registration order in `setup_dependencies()`

### Issue: "Event loop conflicts" with SQL adapter
**Cause**: Using `import_adapter()` instead of `import_adapter_fast()`
**Solution**: Use `import_adapter_fast("sql", "sqlite")` in sync contexts

### Issue: Multiple instances created
**Cause**: Not checking if already registered
**Solution**: Use try/except pattern
```python
try:
    service = depends.get(MyService)
except Exception:
    service = MyService()
    depends.set(MyService, service)
```

### Issue: Can't mock in tests
**Cause**: Using concrete imports instead of protocols
**Solution**: Import and register via protocols
```python
# Use protocols for loose coupling
from crackerjack.models.protocols import FileSystemInterface
depends.set(FileSystemInterface, mock_filesystem)
```

## References

- **ACB Documentation**: [ACB Depends System](https://github.com/acb-framework)
- **Crackerjack Settings**: `crackerjack/config.py` (ACB Settings integration)
- **Repository Pattern**: `crackerjack/data/repository.py`
- **Protocol Definitions**: `crackerjack/models/protocols.py`

## Questions & Answers

**Q: When should I use `import_adapter()` vs `import_adapter_fast()`?**
A: Use `import_adapter_fast()` in synchronous contexts (like `__init__` methods). Use `import_adapter()` in async contexts where you can `await` initialization.

**Q: Can I register the same type multiple times?**
A: Yes - later registrations override previous ones. This is useful for testing (register mock, test, register real).

**Q: How do I know if a dependency is registered?**
A: Try to get it:
```python
try:
    service = depends.get(MyService)
except Exception:
    # Not registered
```

**Q: Should repositories use constructor injection or `@depends.inject`?**
A: Use constructor injection for synchronous initialization (current pattern). Use `@depends.inject` for async methods or optional dependencies.

**Q: How do I clear dependencies between tests?**
A: ACB handles cleanup automatically. For tests, create fresh instances:
```python
@pytest.fixture
def fresh_setup():
    setup_dependencies(Console(), Path.cwd())
    yield
    # ACB handles cleanup
```
