# Protocol Reference Guide

**Version:** 1.0
**Last Updated:** 2025-10-14
**Status:** Complete - Phase 2-4 Refactoring

## Table of Contents

1. [Overview](#overview)
2. [What Are Protocols?](#what-are-protocols)
3. [Why Protocol-Based DI?](#why-protocol-based-di)
4. [Protocol Categories](#protocol-categories)
5. [Core Infrastructure Protocols](#core-infrastructure-protocols)
6. [Service Layer Protocols](#service-layer-protocols)
7. [Manager Layer Protocols](#manager-layer-protocols)
8. [Orchestration Layer Protocols](#orchestration-layer-protocols)
9. [Agent System Protocols](#agent-system-protocols)
10. [Adapter Protocols](#adapter-protocols)
11. [How to Use Protocols](#how-to-use-protocols)
12. [How to Create New Protocols](#how-to-create-new-protocols)
13. [Common Patterns](#common-patterns)
14. [Troubleshooting](#troubleshooting)

---

## Overview

This guide documents all protocol definitions in Crackerjack's architecture. Protocols are the foundation of our ACB-based dependency injection system, providing clear contracts for service interactions without tight coupling to concrete implementations.

**Location:** All protocols are defined in `crackerjack/models/protocols.py` (1571 lines)

**Current Status:**
- **70+ protocols** defined across all architectural layers
- **100% runtime-checkable** with `@runtime_checkable` decorator
- **Zero circular dependencies** achieved through protocol-based imports

---

## What Are Protocols?

Protocols in Python (PEP 544) define structural subtyping - they specify "what an object can do" rather than "what an object is."

```python
import typing as t
from typing import Protocol

@t.runtime_checkable
class LoggerProtocol(Protocol):
    """Protocol defining logger interface."""

    def info(self, message: str) -> None: ...
    def error(self, message: str) -> None: ...
    def debug(self, message: str) -> None: ...
```

**Key Benefits:**
- **Duck typing with type safety:** If it walks like a duck and quacks like a duck, it's a duck
- **No inheritance required:** Any class implementing the methods satisfies the protocol
- **Runtime checking:** `@runtime_checkable` enables `isinstance()` checks
- **Clear contracts:** Explicit method signatures document expected behavior

---

## Why Protocol-Based DI?

### Before Protocols (The Problem)

```python
# ❌ Creates circular dependency
from ..managers.test_manager import TestManager
from ..services.filesystem import FilesystemService

class SessionCoordinator:
    def __init__(self, test_manager: TestManager, fs: FilesystemService):
        self.test_manager = test_manager
        self.fs = fs
```

**Issues:**
- Tight coupling to concrete implementations
- Import cycles when modules need each other
- Difficult to test (need real implementations)
- Hard to swap implementations

### After Protocols (The Solution)

```python
# ✅ Protocol-based dependency injection
from acb.depends import depends, Inject
from ..models.protocols import TestManagerProtocol, FilesystemProtocol

class SessionCoordinator:
    @depends.inject
    def __init__(
        self,
        test_manager: Inject[TestManagerProtocol],
        filesystem: Inject[FilesystemProtocol],
    ):
        self.test_manager = test_manager
        self.filesystem = filesystem
```

**Benefits:**
- Loose coupling through protocols
- Zero circular dependencies
- Easy testing with mock implementations
- Implementation can be swapped without changing consumers

---

## Protocol Categories

Crackerjack protocols are organized into logical categories:

| Category | Count | Purpose | Example Protocols |
|----------|-------|---------|-------------------|
| **Core Infrastructure** | 15+ | Console, logging, caching | `Console`, `LoggerProtocol`, `CacheProtocol` |
| **Service Layer** | 20+ | Business logic services | `FilesystemProtocol`, `GitProtocol`, `SecurityProtocol` |
| **Manager Layer** | 10+ | High-level coordination | `TestManagerProtocol`, `HookManagerProtocol` |
| **Orchestration** | 8+ | Workflow coordination | `SessionCoordinatorProtocol`, `PhaseCoordinatorProtocol` |
| **Agent System** | 5+ | AI agent interfaces | `AgentCoordinatorProtocol`, `AgentTrackerProtocol` |
| **Adapters** | 10+ | Tool integrations | `QAAdapterProtocol`, `FormatAdapterProtocol` |

---

## Core Infrastructure Protocols

### Console (Rich Console)

**Location:** `crackerjack/models/protocols.py`

```python
@t.runtime_checkable
class Console(Protocol):
    """Protocol for Rich console output."""

    def print(
        self,
        *objects: t.Any,
        sep: str = " ",
        end: str = "\n",
        style: str | None = None,
        justify: str | None = None,
        overflow: str | None = None,
        no_wrap: bool | None = None,
        emoji: bool | None = None,
        markup: bool | None = None,
        highlight: bool | None = None,
        width: int | None = None,
        height: int | None = None,
        crop: bool = True,
        soft_wrap: bool = False,
        new_line_start: bool = False,
    ) -> None: ...

    def status(
        self,
        status: str,
        *,
        spinner: str = "dots",
        spinner_style: str = "status.spinner",
        speed: float = 1.0,
        refresh_per_second: float = 12.5,
    ) -> t.Any: ...
```

**Usage:**
```python
from acb.depends import depends, Inject
from crackerjack.models.protocols import Console

@depends.inject
def display_status(console: Inject[Console] = None):
    console.print("[green]Build successful![/green]")
    with console.status("Running tests..."):
        run_tests()
```

### LoggerProtocol

```python
@t.runtime_checkable
class LoggerProtocol(Protocol):
    """Protocol for structured logging."""

    def info(self, message: str, **kwargs: t.Any) -> None: ...
    def warning(self, message: str, **kwargs: t.Any) -> None: ...
    def error(self, message: str, **kwargs: t.Any) -> None: ...
    def debug(self, message: str, **kwargs: t.Any) -> None: ...
    def exception(self, message: str, **kwargs: t.Any) -> None: ...
```

**Usage:**
```python
@depends.inject
def process_files(logger: Inject[LoggerProtocol] = None):
    logger.info("Starting file processing", file_count=42)
    try:
        # Process files
        pass
    except Exception as e:
        logger.exception("File processing failed", error=str(e))
```

### CacheProtocol

```python
@t.runtime_checkable
class CacheProtocol(Protocol):
    """Protocol for caching operations."""

    async def get(self, key: str) -> t.Any: ...
    async def set(self, key: str, value: t.Any, ttl: int | None = None) -> None: ...
    async def delete(self, key: str) -> None: ...
    async def clear(self) -> None: ...
    async def exists(self, key: str) -> bool: ...
```

---

## Service Layer Protocols

### FilesystemProtocol

```python
@t.runtime_checkable
class FilesystemProtocol(ServiceProtocol, Protocol):
    """Protocol for filesystem operations."""

    def read_file(self, path: Path) -> str: ...
    def write_file(self, path: Path, content: str) -> None: ...
    def file_exists(self, path: Path) -> bool: ...
    def list_files(
        self,
        directory: Path,
        pattern: str | None = None,
        recursive: bool = False
    ) -> list[Path]: ...
    def create_directory(self, path: Path) -> None: ...
    def delete_file(self, path: Path) -> None: ...
    def get_file_hash(self, path: Path) -> str: ...
```

**Usage:**
```python
@depends.inject
def process_config(filesystem: Inject[FilesystemProtocol] = None):
    if filesystem.file_exists(Path("config.yaml")):
        content = filesystem.read_file(Path("config.yaml"))
        # Process configuration
```

### GitProtocol

```python
@t.runtime_checkable
class GitProtocol(ServiceProtocol, Protocol):
    """Protocol for git operations."""

    def get_staged_files(self) -> list[Path]: ...
    def get_modified_files(self) -> list[Path]: ...
    def get_current_branch(self) -> str: ...
    def commit(self, message: str, files: list[Path] | None = None) -> None: ...
    def create_branch(self, branch_name: str) -> None: ...
    def get_commit_message(self, commit_hash: str) -> str: ...
    def is_git_repo(self, path: Path | None = None) -> bool: ...
```

### SecurityProtocol

```python
@t.runtime_checkable
class SecurityProtocol(ServiceProtocol, Protocol):
    """Protocol for security operations."""

    def scan_for_secrets(self, files: list[Path]) -> list[dict[str, t.Any]]: ...
    def validate_permissions(self, path: Path) -> bool: ...
    def sanitize_output(self, content: str) -> str: ...
    def check_path_traversal(self, path: Path) -> bool: ...
```

---

## Manager Layer Protocols

### TestManagerProtocol

```python
@t.runtime_checkable
class TestManagerProtocol(ServiceProtocol, Protocol):
    """Protocol for test execution management."""

    async def run_tests(
        self,
        test_paths: list[Path] | None = None,
        workers: int | None = None,
        verbose: bool = False,
    ) -> dict[str, t.Any]: ...

    def collect_tests(self, paths: list[Path]) -> list[str]: ...
    def get_test_status(self) -> dict[str, t.Any]: ...
    async def cleanup(self) -> None: ...
```

**Usage:**
```python
@depends.inject
async def run_quality_checks(test_manager: Inject[TestManagerProtocol] = None):
    result = await test_manager.run_tests(
        test_paths=[Path("tests/")],
        workers=4,
        verbose=True
    )
    return result["passed"]
```

### HookManagerProtocol

```python
@t.runtime_checkable
class HookManagerProtocol(ServiceProtocol, Protocol):
    """Protocol for hook execution management."""

    async def run_hooks(
        self,
        strategy: str = "fast",
        files: list[Path] | None = None,
    ) -> dict[str, t.Any]: ...

    def get_hook_status(self, hook_name: str) -> dict[str, t.Any]: ...
    async def cleanup(self) -> None: ...
```

---

## Orchestration Layer Protocols

### SessionCoordinatorProtocol

```python
@t.runtime_checkable
class SessionCoordinatorProtocol(ServiceProtocol, Protocol):
    """Protocol for session lifecycle coordination."""

    async def initialize_session(self) -> None: ...
    async def run_quality_workflow(self) -> dict[str, t.Any]: ...
    async def finalize_session(self) -> None: ...
    def get_session_metrics(self) -> dict[str, t.Any]: ...
```

### PhaseCoordinatorProtocol

```python
@t.runtime_checkable
class PhaseCoordinatorProtocol(ServiceProtocol, Protocol):
    """Protocol for multi-phase workflow coordination."""

    async def run_phase(
        self,
        phase_name: str,
        config: dict[str, t.Any] | None = None,
    ) -> dict[str, t.Any]: ...

    def get_phase_status(self) -> dict[str, t.Any]: ...
    async def rollback_phase(self, phase_name: str) -> None: ...
```

---

## Agent System Protocols

**Status:** Defined in Phase 4, implementation pending future phase

### AgentCoordinatorProtocol

```python
@t.runtime_checkable
class AgentCoordinatorProtocol(ServiceProtocol, Protocol):
    """Protocol for agent coordination and issue handling."""

    def initialize_agents(self) -> None: ...

    async def handle_issues(
        self,
        issues: list[t.Any]
    ) -> t.Any: ...

    async def handle_issues_proactively(
        self,
        issues: list[t.Any]
    ) -> t.Any: ...

    def get_agent_capabilities(self) -> dict[str, dict[str, t.Any]]: ...
    def set_proactive_mode(self, enabled: bool) -> None: ...
```

### AgentTrackerProtocol

```python
@t.runtime_checkable
class AgentTrackerProtocol(Protocol):
    """Protocol for tracking agent execution and metrics."""

    def register_agents(self, agent_types: list[str]) -> None: ...
    def set_coordinator_status(self, status: str) -> None: ...

    def track_agent_processing(
        self,
        agent_name: str,
        issue: t.Any,
        confidence: float
    ) -> None: ...

    def track_agent_complete(
        self,
        agent_name: str,
        result: t.Any
    ) -> None: ...

    def get_agent_stats(self) -> dict[str, t.Any]: ...
```

**Note:** Agent system protocols were defined in Phase 4 for future migration. Current agent system uses `AgentContext` pattern (legacy but functional).

---

## Adapter Protocols

### QAAdapterProtocol

```python
@t.runtime_checkable
class QAAdapterProtocol(Protocol):
    """Protocol for quality assurance adapters."""

    @property
    def adapter_name(self) -> str: ...

    @property
    def module_id(self) -> uuid.UUID: ...

    async def check(
        self,
        files: list[Path] | None = None,
        config: dict | None = None,
    ) -> t.Any: ...  # Returns QAResult

    async def init(self) -> None: ...
    async def cleanup(self) -> None: ...
```

---

## How to Use Protocols

### Basic Usage Pattern

```python
# Step 1: Import protocol and DI decorators
from acb.depends import depends, Inject
from crackerjack.models.protocols import Console, FilesystemProtocol

# Step 2: Use @depends.inject decorator
@depends.inject
def my_function(
    console: Inject[Console] = None,
    filesystem: Inject[FilesystemProtocol] = None,
) -> None:
    """Dependencies are automatically injected."""
    console.print("[green]Processing files...[/green]")
    files = filesystem.list_files(Path("."))
```

### Class Constructor Pattern

```python
from acb.depends import depends, Inject
from crackerjack.models.protocols import (
    Console,
    TestManagerProtocol,
    GitProtocol,
)

class MyCoordinator:
    """Example coordinator following gold standard pattern."""

    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        test_manager: Inject[TestManagerProtocol],
        git: Inject[GitProtocol],
        pkg_path: Path,  # Non-DI parameter
    ) -> None:
        """All service dependencies injected via protocols."""
        self.console = console
        self.test_manager = test_manager
        self.git = git
        self.pkg_path = pkg_path
```

### Async Lifecycle Pattern

```python
class MyService:
    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        cache: Inject[CacheProtocol],
    ) -> None:
        self.console = console
        self.cache = cache

    async def init(self) -> None:
        """Async initialization."""
        await self.cache.clear()
        self.console.print("[green]Service initialized[/green]")

    async def cleanup(self) -> None:
        """Async cleanup."""
        await self.cache.clear()
        self.console.print("[yellow]Service cleaned up[/yellow]")
```

---

## How to Create New Protocols

### Step 1: Define the Protocol

```python
# In crackerjack/models/protocols.py

import typing as t
from typing import Protocol

@t.runtime_checkable
class MyNewServiceProtocol(ServiceProtocol, Protocol):
    """Protocol for my new service.

    This protocol defines the interface for...
    """

    def process_data(self, data: dict[str, t.Any]) -> dict[str, t.Any]:
        """Process data and return results.

        Args:
            data: Input data dictionary

        Returns:
            Processed results dictionary
        """
        ...

    async def async_operation(self) -> None:
        """Async operation example."""
        ...
```

**Best Practices:**
- Always use `@t.runtime_checkable` decorator
- Inherit from `ServiceProtocol` if it's a service
- Use `...` (ellipsis) for method bodies
- Include comprehensive docstrings
- Use `t.Any` to avoid import cycles (add comment for actual type)

### Step 2: Implement the Protocol

```python
# In crackerjack/services/my_new_service.py

from acb.depends import depends, Inject
from crackerjack.models.protocols import (
    MyNewServiceProtocol,
    Console,
    LoggerProtocol,
)

class MyNewService(MyNewServiceProtocol):
    """Concrete implementation of MyNewServiceProtocol."""

    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        logger: Inject[LoggerProtocol],
    ) -> None:
        self.console = console
        self.logger = logger

    def process_data(self, data: dict[str, t.Any]) -> dict[str, t.Any]:
        """Implementation of process_data."""
        self.logger.info("Processing data", data_keys=list(data.keys()))
        # Implementation here
        return processed_data

    async def async_operation(self) -> None:
        """Implementation of async_operation."""
        await asyncio.sleep(0.1)
```

### Step 3: Register with ACB Container

```python
# At module level in my_new_service.py

from acb.depends import depends
from contextlib import suppress

# Register with ACB container
with suppress(Exception):
    depends.set(MyNewService, protocol=MyNewServiceProtocol)
```

### Step 4: Use the Protocol

```python
# In any other module

from acb.depends import depends, Inject
from crackerjack.models.protocols import MyNewServiceProtocol

@depends.inject
def use_my_service(service: Inject[MyNewServiceProtocol] = None):
    result = service.process_data({"key": "value"})
    await service.async_operation()
```

---

## Common Patterns

### Pattern 1: Service with Dependencies

```python
@t.runtime_checkable
class MyServiceProtocol(ServiceProtocol, Protocol):
    """Service that depends on other services."""

    def do_something(self) -> None: ...

class MyService(MyServiceProtocol):
    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        filesystem: Inject[FilesystemProtocol],
    ) -> None:
        self.console = console
        self.filesystem = filesystem

    def do_something(self) -> None:
        self.console.print("[green]Doing something...[/green]")
        files = self.filesystem.list_files(Path("."))
```

### Pattern 2: Optional Dependencies

```python
@depends.inject
def my_function(
    console: Inject[Console] = None,  # Injected by ACB
    optional_param: str | None = None,  # Regular parameter
) -> None:
    """Function with mix of DI and regular parameters."""
    console.print(f"Optional: {optional_param}")
```

### Pattern 3: Protocol Composition

```python
@t.runtime_checkable
class AdvancedServiceProtocol(ServiceProtocol, Protocol):
    """Protocol inheriting from ServiceProtocol."""

    # ServiceProtocol provides:
    # - async def init(self) -> None
    # - async def cleanup(self) -> None

    # Add specific methods:
    def advanced_operation(self) -> None: ...
```

---

## Troubleshooting

### Issue: Protocol Not Found

**Error:** `AttributeError: module 'crackerjack.models.protocols' has no attribute 'MyProtocol'`

**Solution:**
1. Check spelling in import statement
2. Verify protocol exists in `crackerjack/models/protocols.py`
3. Ensure no circular imports

### Issue: DI Not Injecting

**Error:** Function receives `None` instead of service instance

**Common Causes:**
```python
# ❌ Missing @depends.inject decorator
def my_function(console: Inject[Console] = None):
    pass

# ✅ Correct
@depends.inject
def my_function(console: Inject[Console] = None):
    pass
```

### Issue: Import Circular Dependency

**Error:** `ImportError: cannot import name 'MyProtocol' from partially initialized module`

**Solution:** Always import protocols, never concrete classes:
```python
# ❌ Wrong - Creates circular dependency
from ..services.my_service import MyService

# ✅ Correct - Import protocol instead
from ..models.protocols import MyServiceProtocol
```

### Issue: Type Checker Complains

**Error:** Mypy/Pyright shows "object has no attribute X"

**Solution:** Ensure protocol methods are defined with correct signatures:
```python
@t.runtime_checkable
class MyProtocol(Protocol):
    # ❌ Wrong - no type hints
    def my_method(self, data): ...

    # ✅ Correct - full type hints
    def my_method(self, data: dict[str, t.Any]) -> str: ...
```

---

## Summary

**Key Takeaways:**

1. **All protocols in one place:** `crackerjack/models/protocols.py` (1571 lines)
2. **70+ protocols** cover all architectural layers
3. **Always use `@depends.inject`** decorator for DI
4. **Import protocols, not classes** to avoid circular dependencies
5. **Follow gold standards:** CLI handlers (90%) and SessionCoordinator (perfect DI)

**Best Practices:**

✅ **DO:**
- Import protocols from `models/protocols.py`
- Use `@depends.inject` decorator
- Follow `Inject[Protocol]` pattern
- Include docstrings in protocol definitions
- Use `@t.runtime_checkable` on all protocols

❌ **DON'T:**
- Import concrete classes for DI
- Add manual fallbacks like `console or Console()`
- Skip `@depends.inject` decorator
- Use `if TYPE_CHECKING:` lazy imports
- Create factory functions that bypass DI

**For More Information:**
- [ACB-MIGRATION-GUIDE.md](ACB-MIGRATION-GUIDE.md) - Success patterns from Phase 2-4
- [CLAUDE.md](../CLAUDE.md) - Architecture overview and code standards
- [README.md](../README.md) - Comprehensive project documentation
