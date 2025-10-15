# Dependency Injection Patterns Guide

**Version:** 1.0
**Last Updated:** 2025-10-14
**Status:** Complete - Based on Phase 2-4 Refactoring

## Table of Contents

1. [Overview](#overview)
2. [Core Concepts](#core-concepts)
3. [Gold Standard Patterns](#gold-standard-patterns)
4. [Anti-Patterns to Avoid](#anti-patterns-to-avoid)
5. [Pattern Catalog](#pattern-catalog)
6. [Layer-Specific Patterns](#layer-specific-patterns)
7. [Testing with DI](#testing-with-di)
8. [Migration Checklist](#migration-checklist)
9. [Troubleshooting](#troubleshooting)
10. [FAQ](#faq)

---

## Overview

This guide presents battle-tested dependency injection patterns from Crackerjack's Phase 2-4 refactoring. These patterns are based on real code that achieved 75% overall DI compliance across all architectural layers.

**What You'll Learn:**
- How to use ACB's DI system correctly
- Gold standard patterns from 90%+ compliant layers
- Common anti-patterns and how to avoid them
- Layer-specific best practices
- Testing strategies with DI

**Prerequisites:**
- Understanding of Python protocols (PEP 544)
- Basic familiarity with dependency injection concepts
- Knowledge of async/await patterns

---

## Core Concepts

### What is Dependency Injection?

Dependency Injection (DI) is a design pattern where objects receive their dependencies from external sources rather than creating them internally.

```python
# ❌ Without DI - Tight coupling
class MyService:
    def __init__(self):
        self.console = Console()  # Creates own dependency
        self.filesystem = FilesystemService()  # Tight coupling

# ✅ With DI - Loose coupling
class MyService:
    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        filesystem: Inject[FilesystemProtocol],
    ):
        self.console = console  # Injected dependency
        self.filesystem = filesystem  # Protocol-based
```

### Why ACB for DI?

**ACB (Asynchronous Component Base)** provides:

1. **Module-level registration** - Services registered once, used everywhere
2. **Protocol-based contracts** - Loose coupling through interfaces
3. **Async-first design** - Native support for async initialization
4. **Zero configuration** - Works out of the box
5. **Runtime type checking** - Catch errors early with `@runtime_checkable`

### The Three Pillars

1. **`@depends.inject` Decorator** - Marks functions/methods for DI
2. **`Inject[Protocol]` Type Hint** - Specifies what to inject
3. **Protocol Definitions** - Define contracts in `models/protocols.py`

---

## Gold Standard Patterns

### Pattern 1: CLI Handler (90% Compliance)

**Source:** `crackerjack/cli/handlers.py`

```python
from acb.depends import depends, Inject
from crackerjack.models.protocols import Console

@depends.inject
def setup_ai_agent_env(
    ai_agent: bool,
    debug_mode: bool = False,
    console: Inject[Console] = None,
) -> None:
    """Gold standard CLI handler pattern.

    Key Features:
    - @depends.inject decorator
    - Inject[Console] type hint
    - Mix of DI and regular parameters
    - No manual fallbacks
    """
    if ai_agent:
        console.print("[green]AI agents enabled[/green]")
        if debug_mode:
            console.print("[yellow]Debug mode active[/yellow]")
```

**Why This Is Gold Standard:**
- ✅ Clean separation of concerns
- ✅ Easy to test (mock console)
- ✅ No tight coupling
- ✅ Clear parameter roles

### Pattern 2: SessionCoordinator (Perfect DI)

**Source:** `crackerjack/core/session_coordinator.py`

```python
from acb.depends import depends, Inject
from pathlib import Path
from crackerjack.models.protocols import (
    Console,
    TestManagerProtocol,
    GitProtocol,
)

class SessionCoordinator:
    """Gold standard orchestration pattern.

    This is the model all new coordinators should follow.
    """

    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        test_manager: Inject[TestManagerProtocol],
        git: Inject[GitProtocol],
        pkg_path: Path,
        web_job_id: str | None = None,
    ) -> None:
        """All service dependencies injected via protocols.

        Args:
            console: Rich console for output
            test_manager: Test execution coordinator
            git: Git operations service
            pkg_path: Package path (non-DI parameter)
            web_job_id: Optional web job ID (non-DI parameter)
        """
        # Store DI dependencies
        self.console = console
        self.test_manager = test_manager
        self.git = git

        # Store non-DI parameters
        self.pkg_path = pkg_path
        self.web_job_id = web_job_id

    async def run_quality_workflow(self) -> dict[str, t.Any]:
        """Execute quality workflow using injected services."""
        self.console.print("[bold]Starting quality workflow...[/bold]")

        # Use injected test manager
        test_results = await self.test_manager.run_tests()

        # Use injected git service
        staged_files = self.git.get_staged_files()

        return {
            "test_results": test_results,
            "staged_files": len(staged_files),
        }
```

**Why This Is Perfect:**
- ✅ All services via DI
- ✅ Protocol-based dependencies
- ✅ Mix of DI and regular parameters
- ✅ Clear documentation
- ✅ Async support
- ✅ Zero manual fallbacks

### Pattern 3: Service with Lifecycle

**Based on Phase 3 refactored services**

```python
from acb.depends import depends, Inject
from crackerjack.models.protocols import (
    Console,
    FilesystemProtocol,
    LoggerProtocol,
)

class MyService:
    """Service following Phase 3 standards.

    Key Features:
    - Constructor injection
    - Async lifecycle methods
    - Protocol-based dependencies
    """

    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        filesystem: Inject[FilesystemProtocol],
        logger: Inject[LoggerProtocol],
    ) -> None:
        """Initialize service with DI dependencies."""
        self.console = console
        self.filesystem = filesystem
        self.logger = logger
        self._initialized = False

    async def init(self) -> None:
        """Async initialization.

        Use this for:
        - Opening connections
        - Loading configuration
        - Initializing async resources
        """
        if self._initialized:
            return

        self.logger.info("Initializing service")
        # Async setup here
        self._initialized = True

    async def cleanup(self) -> None:
        """Async cleanup.

        Use this for:
        - Closing connections
        - Releasing resources
        - Final logging
        """
        if not self._initialized:
            return

        self.logger.info("Cleaning up service")
        # Async cleanup here
        self._initialized = False

    def do_work(self) -> None:
        """Business logic using injected services."""
        self.console.print("[green]Processing...[/green]")
        files = self.filesystem.list_files(Path("."))
        self.logger.info("Processed files", file_count=len(files))
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Manual Fallbacks

❌ **Wrong - Bypasses DI container:**

```python
class MyService:
    def __init__(self, console: Console | None = None):
        # This defeats DI - creates dependency if not provided
        self.console = console or Console()
```

✅ **Correct - Trust the DI container:**

```python
class MyService:
    @depends.inject
    def __init__(self, console: Inject[Console]):
        # DI container always provides console
        self.console = console
```

**Why It's Bad:**
- Bypasses dependency injection
- Makes testing harder
- Can create wrong implementations
- Hides dependencies from DI system

### Anti-Pattern 2: Factory Functions

❌ **Wrong - Factory bypasses DI:**

```python
def get_agent_tracker() -> AgentTracker:
    """Factory function creating instance."""
    return AgentTracker()

class AgentCoordinator:
    def __init__(self):
        # Bypasses DI container
        self.tracker = get_agent_tracker()
```

✅ **Correct - Inject via protocol:**

```python
class AgentCoordinator:
    @depends.inject
    def __init__(self, tracker: Inject[AgentTrackerProtocol]):
        self.tracker = tracker
```

**Why It's Bad:**
- Hidden dependencies
- Difficult to test
- Can't swap implementations
- Breaks DI chain

### Anti-Pattern 3: Direct Service Instantiation

❌ **Wrong - Creates service directly:**

```python
class MyCoordinator:
    def __init__(self):
        # Direct instantiation
        self.logger = logging.getLogger(__name__)
        self.console = Console()
```

✅ **Correct - Inject services:**

```python
class MyCoordinator:
    @depends.inject
    def __init__(
        self,
        logger: Inject[LoggerProtocol],
        console: Inject[Console],
    ):
        self.logger = logger
        self.console = console
```

**Why It's Bad:**
- Tight coupling to concrete implementations
- Can't mock for testing
- Ignores DI system configuration

### Anti-Pattern 4: Importing Concrete Classes

❌ **Wrong - Imports concrete class:**

```python
from ..managers.test_manager import TestManager
from rich.console import Console

class MyCoordinator:
    @depends.inject
    def __init__(
        self,
        test_manager: Inject[TestManager],  # Concrete class
        console: Inject[Console],  # This one is OK (Console is a protocol)
    ):
        pass
```

✅ **Correct - Import protocols:**

```python
from ..models.protocols import TestManagerProtocol, Console

class MyCoordinator:
    @depends.inject
    def __init__(
        self,
        test_manager: Inject[TestManagerProtocol],  # Protocol
        console: Inject[Console],  # Protocol
    ):
        pass
```

**Why It's Bad:**
- Creates circular dependencies
- Couples to implementation
- Breaks protocol-based architecture

### Anti-Pattern 5: Lazy Imports

❌ **Wrong - Lazy TYPE_CHECKING imports:**

```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..managers.test_manager import TestManager

class MyCoordinator:
    def __init__(self, test_manager: "TestManager"):
        pass
```

✅ **Correct - Direct protocol imports:**

```python
from ..models.protocols import TestManagerProtocol

class MyCoordinator:
    @depends.inject
    def __init__(self, test_manager: Inject[TestManagerProtocol]):
        pass
```

**Why It's Bad:**
- Masks import issues
- Runtime type checking doesn't work
- Maintenance burden
- **Phase 2 eliminated ALL lazy imports (100% success)**

---

## Pattern Catalog

### Pattern: Function-Level Injection

**Use When:** Writing standalone functions, CLI handlers

```python
@depends.inject
def process_files(
    files: list[Path],
    console: Inject[Console] = None,
    filesystem: Inject[FilesystemProtocol] = None,
) -> dict[str, t.Any]:
    """Process files with DI services.

    Args:
        files: Files to process (regular parameter)
        console: Injected console service
        filesystem: Injected filesystem service

    Returns:
        Processing results
    """
    console.print(f"[green]Processing {len(files)} files...[/green]")

    results = []
    for file_path in files:
        if filesystem.file_exists(file_path):
            content = filesystem.read_file(file_path)
            results.append({"path": file_path, "size": len(content)})

    return {"processed": len(results), "results": results}
```

### Pattern: Class-Level Injection

**Use When:** Creating services, coordinators, managers

```python
class DataProcessor:
    """Service for data processing."""

    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        logger: Inject[LoggerProtocol],
        cache: Inject[CacheProtocol],
    ) -> None:
        """Initialize with injected dependencies."""
        self.console = console
        self.logger = logger
        self.cache = cache

    async def process(self, data: dict) -> dict:
        """Process data using injected services."""
        self.logger.info("Processing data", keys=list(data.keys()))

        # Check cache
        cached = await self.cache.get(str(data))
        if cached:
            return cached

        # Process and cache
        result = self._do_processing(data)
        await self.cache.set(str(data), result)
        return result
```

### Pattern: Optional Dependencies

**Use When:** Dependency is truly optional (rare!)

```python
@depends.inject
def optional_logging(
    data: dict,
    logger: Inject[LoggerProtocol] | None = None,  # Optional DI
) -> None:
    """Function with optional DI dependency."""
    if logger:
        logger.info("Processing", data_keys=list(data.keys()))
    # Process without logging if logger not available
```

**Caution:** Most services should be required, not optional.

### Pattern: Multiple Protocol Inheritance

**Use When:** Creating protocols with shared behavior

```python
@t.runtime_checkable
class AdvancedServiceProtocol(ServiceProtocol, CachableProtocol, Protocol):
    """Protocol combining multiple base protocols.

    Inherits:
    - ServiceProtocol: init(), cleanup()
    - CachableProtocol: cache operations
    """

    def advanced_operation(self) -> dict: ...
```

### Pattern: Context Manager with DI

**Use When:** Need automatic cleanup

```python
class ResourceManager:
    """Resource manager with automatic cleanup."""

    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        logger: Inject[LoggerProtocol],
    ) -> None:
        self.console = console
        self.logger = logger
        self._resource = None

    async def __aenter__(self):
        """Async context manager entry."""
        self.logger.info("Acquiring resource")
        self._resource = await self._acquire_resource()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._resource:
            await self._release_resource()
            self.logger.info("Released resource")

# Usage:
async def use_resource():
    async with ResourceManager() as manager:
        await manager.do_work()
    # Automatic cleanup on exit
```

---

## Layer-Specific Patterns

### CLI Handlers (90% Compliance)

**Pattern: Decorated Handler Functions**

```python
from acb.depends import depends, Inject
from crackerjack.models.protocols import Console

@depends.inject
def handle_command(
    arg1: str,
    arg2: int,
    console: Inject[Console] = None,
    verbose: bool = False,
) -> None:
    """CLI handler with mixed parameters.

    Args:
        arg1, arg2: Command arguments (regular params)
        console: Injected console (DI param)
        verbose: Flag (regular param)
    """
    console.print(f"[green]Handling {arg1} with {arg2}[/green]")
```

### Services (95% Compliance)

**Pattern: Service with Lifecycle**

```python
class MyService:
    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        filesystem: Inject[FilesystemProtocol],
    ) -> None:
        self.console = console
        self.filesystem = filesystem
        self._ready = False

    async def init(self) -> None:
        """Async initialization."""
        self.console.print("[yellow]Initializing service...[/yellow]")
        # Setup here
        self._ready = True

    async def cleanup(self) -> None:
        """Async cleanup."""
        self.console.print("[yellow]Cleaning up service...[/yellow]")
        # Cleanup here
        self._ready = False
```

### Managers (80% Compliance)

**Pattern: Manager Coordination**

```python
class ResourceManager:
    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        filesystem: Inject[FilesystemProtocol],
        git: Inject[GitProtocol],
    ) -> None:
        """Manager coordinating multiple services."""
        self.console = console
        self.filesystem = filesystem
        self.git = git

    async def coordinate(self) -> dict:
        """Coordinate multiple services."""
        files = self.filesystem.list_files(Path("."))
        staged = self.git.get_staged_files()

        return {
            "total_files": len(files),
            "staged_files": len(staged),
        }
```

### Orchestration (70% Compliance)

**Pattern: Coordinator with Phase Management**

```python
class WorkflowCoordinator:
    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        test_manager: Inject[TestManagerProtocol],
        hook_manager: Inject[HookManagerProtocol],
    ) -> None:
        """Workflow coordinator."""
        self.console = console
        self.test_manager = test_manager
        self.hook_manager = hook_manager

    async def run_workflow(self) -> dict:
        """Execute multi-phase workflow."""
        # Phase 1: Run tests
        self.console.print("[bold]Phase 1: Tests[/bold]")
        test_results = await self.test_manager.run_tests()

        # Phase 2: Run hooks
        self.console.print("[bold]Phase 2: Hooks[/bold]")
        hook_results = await self.hook_manager.run_hooks()

        return {
            "tests": test_results,
            "hooks": hook_results,
        }
```

---

## Testing with DI

### Pattern: Mock Injection

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from acb.depends import depends

@pytest.fixture
def mock_console():
    """Mock console for testing."""
    console = MagicMock()
    console.print = MagicMock()
    return console

@pytest.fixture
def mock_filesystem():
    """Mock filesystem for testing."""
    fs = MagicMock()
    fs.list_files = MagicMock(return_value=[Path("file1.py")])
    fs.read_file = MagicMock(return_value="content")
    return fs

def test_my_service(mock_console, mock_filesystem):
    """Test service with mocked dependencies."""
    # Setup DI mocks
    depends.set(mock_console, protocol=Console)
    depends.set(mock_filesystem, protocol=FilesystemProtocol)

    # Create service (DI injects mocks)
    service = MyService()

    # Execute
    service.do_work()

    # Verify
    mock_console.print.assert_called()
    mock_filesystem.list_files.assert_called_once()
```

### Pattern: Pytest Fixture Injection

```python
@pytest.fixture
@depends.inject
def test_service(
    console: Inject[Console],
    filesystem: Inject[FilesystemProtocol],
) -> MyService:
    """Fixture providing service with real DI."""
    service = MyService()
    return service

def test_with_fixture(test_service):
    """Test using fixture with DI."""
    result = test_service.do_work()
    assert result is not None
```

---

## Migration Checklist

### Before Migration
- [ ] Read this guide completely
- [ ] Review gold standard examples
- [ ] Understand protocol definitions
- [ ] Identify all dependencies in target code

### During Migration
- [ ] Add `@depends.inject` decorator
- [ ] Change imports to protocols
- [ ] Remove manual fallbacks
- [ ] Remove factory functions
- [ ] Add type hints with `Inject[Protocol]`
- [ ] Test with real dependencies
- [ ] Test with mocked dependencies

### After Migration
- [ ] Run type checker (zuban)
- [ ] Run full test suite
- [ ] Check for import cycles
- [ ] Verify DI working correctly
- [ ] Update documentation
- [ ] Review with team

### Quality Checks
- [ ] No `console or Console()` patterns
- [ ] No `get_*()` factory functions
- [ ] No concrete class imports
- [ ] No `if TYPE_CHECKING:` blocks
- [ ] All services use `@depends.inject`
- [ ] All dependencies via `Inject[Protocol]`

---

## Troubleshooting

### Issue: DI Not Working

**Symptom:** Function receives `None` instead of service

**Debug Steps:**
1. Check `@depends.inject` decorator present
2. Verify `Inject[Protocol]` type hint
3. Check protocol registered with ACB
4. Look for typos in protocol name

**Solution:**
```python
# ❌ Missing decorator
def my_function(console: Inject[Console] = None):
    pass

# ✅ With decorator
@depends.inject
def my_function(console: Inject[Console] = None):
    pass
```

### Issue: Import Circular Dependency

**Symptom:** `ImportError: cannot import name 'X' from partially initialized module`

**Solution:** Import protocols, not concrete classes
```python
# ❌ Circular dependency
from ..services.my_service import MyService

# ✅ Protocol import
from ..models.protocols import MyServiceProtocol
```

### Issue: Wrong Implementation Injected

**Symptom:** DI injects unexpected implementation

**Debug Steps:**
1. Check `depends.set()` calls
2. Verify protocol registration
3. Look for multiple registrations

**Solution:**
```python
# Ensure correct registration
with suppress(Exception):
    depends.set(MyService, protocol=MyServiceProtocol)
```

### Issue: Type Checker Errors

**Symptom:** Mypy/Pyright complains about protocol methods

**Solution:** Ensure protocol has complete type hints
```python
# ❌ Incomplete
@t.runtime_checkable
class MyProtocol(Protocol):
    def method(self, data): ...

# ✅ Complete
@t.runtime_checkable
class MyProtocol(Protocol):
    def method(self, data: dict[str, t.Any]) -> str: ...
```

---

## FAQ

### Q: When should I use DI vs direct instantiation?

**A:** Use DI for:
- Services that depend on other services
- Code that needs testing with mocks
- Components shared across modules
- Anything with I/O or side effects

Use direct instantiation for:
- Plain data classes
- Pure functions with no dependencies
- Value objects

### Q: Can I mix DI and regular parameters?

**A:** Yes! This is the pattern used in CLI handlers:
```python
@depends.inject
def handler(
    arg1: str,  # Regular parameter
    arg2: int,  # Regular parameter
    console: Inject[Console] = None,  # DI parameter
    verbose: bool = False,  # Regular parameter
):
    pass
```

### Q: How do I test code with DI?

**A:** Two approaches:

1. **Mock injection** (recommended):
```python
def test_my_function(mock_console):
    depends.set(mock_console, protocol=Console)
    result = my_function()
    mock_console.print.assert_called()
```

2. **Real dependencies** (integration tests):
```python
def test_my_function():
    result = my_function()  # Uses real DI services
    assert result is not None
```

### Q: What if I need multiple implementations of a protocol?

**A:** Use named registrations:
```python
# Register different implementations
depends.set(FastCache(), protocol=CacheProtocol, name="fast")
depends.set(PersistentCache(), protocol=CacheProtocol, name="persistent")

# Inject specific implementation
@depends.inject
def my_function(cache: Inject[CacheProtocol, "fast"]):
    pass
```

### Q: Should every class use DI?

**A:** No! Use DI for services, managers, coordinators. Don't use for:
- Data classes (`@dataclass`)
- Models with no dependencies
- Pure value objects
- Simple utility classes

### Q: How do I handle circular dependencies?

**A:** Use protocols instead of concrete classes:
```python
# ❌ Creates cycle
from ..services.a import ServiceA
from ..services.b import ServiceB

# ✅ No cycle
from ..models.protocols import ServiceAProtocol, ServiceBProtocol
```

---

## Summary

**Key Takeaways:**

1. **Always use `@depends.inject`** for DI functions/classes
2. **Import protocols, never concrete classes** to avoid cycles
3. **No manual fallbacks** - trust the DI container
4. **Follow gold standards** - CLI handlers (90%), SessionCoordinator (perfect)
5. **Test with mocks** for unit tests, real services for integration

**Compliance Scores:**
- CLI Handlers: 90% (gold standard)
- Services: 95% (excellent)
- Managers: 80% (good)
- Orchestration: 70% (mixed)
- Coordinators: 70% (mixed)
- Agent System: 40% (legacy pattern)

**For More Information:**
- [PROTOCOL_REFERENCE_GUIDE.md](PROTOCOL_REFERENCE_GUIDE.md) - Complete protocol documentation
- [ACB-MIGRATION-GUIDE.md](ACB-MIGRATION-GUIDE.md) - Migration patterns and success stories
- [CLAUDE.md](../CLAUDE.md) - Architecture overview and code standards
