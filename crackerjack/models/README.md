# Models

> Crackerjack Docs: [Main](../../README.md) | [CLAUDE.md](../../docs/guides/CLAUDE.md) | [Models](./README.md)

Data models, schemas, and protocol definitions for the Crackerjack architecture.

## Overview

The models package provides the foundational data structures and protocol-based interfaces that define Crackerjack's architecture. The **protocol-based dependency injection (DI) pattern** is the most critical architectural pattern in Crackerjack, enabling loose coupling, testability, and clean separation of concerns.

## Key Components

### protocols.py - THE MOST CRITICAL FILE

**This is the heart of Crackerjack's architecture.** Always import protocols from here, never concrete classes.

**Core Service Protocols:**

- `ServiceProtocol` - Base protocol for all ACB services with lifecycle management
- `Console` (ConsoleInterface) - Rich console output interface
- `TestManagerProtocol` - Test execution and coverage management
- `HookManager` / `SecurityAwareHookManager` - Pre-commit hook orchestration
- `CoverageRatchetProtocol` - Coverage baseline tracking
- `SecurityServiceProtocol` - Security validation and secret detection

**Configuration & File System:**

- `UnifiedConfigurationServiceProtocol` - Centralized configuration access
- `FileSystemServiceProtocol` / `EnhancedFileSystemServiceProtocol` - File operations
- `GitServiceProtocol` / `GitInterface` - Git repository interactions
- `SmartFileFilterProtocol` - Intelligent file filtering

**Quality Assurance:**

- `QAAdapterProtocol` - Base protocol for all QA check adapters
- `QAOrchestratorProtocol` - QA check coordination and execution

**Hook Orchestration (Phase 3):**

- `ExecutionStrategyProtocol` - Hook execution strategies (parallel/sequential/adaptive)
- `CacheStrategyProtocol` - Result caching strategies
- `HookOrchestratorProtocol` - Hook lifecycle and dependency resolution

**Performance & Monitoring:**

- `PerformanceMonitorProtocol` - Workflow performance tracking
- `PerformanceBenchmarkProtocol` / `PerformanceBenchmarkServiceProtocol` - Benchmarking
- `MemoryOptimizerProtocol` - Memory optimization tracking
- `PerformanceCacheProtocol` - Performance result caching

**Agent System (Phase 4):**

- `AgentCoordinatorProtocol` - AI agent coordination and issue routing
- `AgentTrackerProtocol` - Agent execution metrics tracking
- `AgentDebuggerProtocol` - Agent debugging and activity logging

**Orchestration:**

- `ServiceWatchdogProtocol` - Service health monitoring and restart
- `TimeoutManagerProtocol` - Centralized timeout management
- `ParallelExecutorProtocol` / `ParallelHookExecutorProtocol` - Parallel task execution
- `AsyncCommandExecutorProtocol` - Async command execution with caching

**Publishing & Documentation:**

- `PublishManager` - Package publishing and versioning
- `DocumentationServiceProtocol` - Automated documentation generation
- `APIExtractorProtocol` / `DocumentationGeneratorProtocol` / `DocumentationValidatorProtocol` - Doc tooling

### Configuration Models

**qa_config.py** - Quality assurance configuration:

- `QACheckConfig` - Configuration for individual QA checks
- Check-specific settings (file patterns, timeouts, retries)
- Pydantic validation for type safety

**config.py** - Core configuration models:

- Project-wide configuration structures
- ACB Settings integration
- Environment-specific overrides

**config_adapter.py** - Configuration adapters:

- Bridges between different configuration formats
- Legacy config migration support

### Result Models

**qa_results.py** - Quality assurance results:

- `QAResult` - Individual check results
- `QACheckType` - Enumeration of check types
- Result aggregation structures

**results.py** - Execution results:

- `ExecutionResult` - Individual execution outcomes
- `ParallelExecutionResult` - Parallel execution aggregation
- Performance metrics and timing data

**task.py** - Task and hook models:

- `HookResult` - Pre-commit hook execution results
- `SessionTracker` - Session metadata and task tracking
- Task lifecycle management

### Specialized Models

**semantic_models.py** - Semantic analysis models:

- Code comprehension structures
- Semantic analysis results
- Intelligent refactoring support

**resource_protocols.py** - Resource management protocols:

- Resource lifecycle interfaces
- Resource cleanup coordination

## THE MOST CRITICAL PATTERN: Protocol-Based Dependency Injection

### Gold Standard Usage

```python
# ✅ CORRECT - Always import protocols from models/protocols.py
from acb.depends import depends, Inject
from crackerjack.models.protocols import (
    Console,
    TestManagerProtocol,
    SecurityServiceProtocol,
)


@depends.inject
def setup_environment(
    console: Inject[Console] = None,
    test_manager: Inject[TestManagerProtocol] = None,
    security: Inject[SecurityServiceProtocol] = None,
) -> None:
    """All functions use @depends.inject with protocol-based dependencies."""
    console.print("[green]Environment configured[/green]")
    test_manager.validate_test_environment()
    security.validate_file_safety("/path/to/file")


class MyCoordinator:
    @depends.inject
    def __init__(
        self,
        console: Inject[Console],
        test_manager: Inject[TestManagerProtocol],
    ) -> None:
        """Perfect DI integration with protocol-based dependencies."""
        self.console = console
        self.test_manager = test_manager
```

### Anti-Patterns to Avoid

```python
# ❌ WRONG - Direct class imports (BREAKS ARCHITECTURE)
from crackerjack.managers.test_manager import TestManager
from rich.console import Console as RichConsole

# ❌ WRONG - Manual fallbacks bypass DI
self.console = console or Console()
self.cache = cache or CrackerjackCache()

# ❌ WRONG - Factory functions bypass DI
self.tracker = get_agent_tracker()
self.timeout_manager = get_timeout_manager()

# ❌ WRONG - Direct service instantiation
self.logger = logging.getLogger(__name__)
```

## Why Protocol-Based DI?

1. **Loose Coupling**: Depend on interfaces, not implementations
1. **Testability**: Easy to mock with protocol implementations
1. **Flexibility**: Swap implementations without changing dependents
1. **Type Safety**: Runtime type checking via `@runtime_checkable`
1. **Clear Contracts**: Protocol defines exact interface requirements
1. **ACB Integration**: Seamless integration with ACB dependency injection

## Usage Examples

### Using Protocols for Type Hints

```python
from crackerjack.models.protocols import Console, FileSystemServiceProtocol


def process_files(
    console: Console,
    fs: FileSystemServiceProtocol,
    paths: list[Path],
) -> bool:
    """Process files with protocol-based dependencies."""
    for path in paths:
        if fs.exists(path):
            content = fs.read_file(path)
            console.print(f"Processing {path}")
    return True
```

### Creating Protocol Implementations

```python
import typing as t
from crackerjack.models.protocols import ServiceProtocol


@t.runtime_checkable
class MyServiceProtocol(ServiceProtocol, t.Protocol):
    """Custom service protocol extending base ServiceProtocol."""

    def custom_operation(self, data: str) -> bool:
        """Custom operation for this service."""
        ...


class MyService:
    """Concrete implementation of MyServiceProtocol."""

    def initialize(self) -> None:
        """Initialize service."""
        pass

    def cleanup(self) -> None:
        """Cleanup resources."""
        pass

    def health_check(self) -> bool:
        """Health check."""
        return True

    # ... implement all ServiceProtocol methods ...

    def custom_operation(self, data: str) -> bool:
        """Implementation of custom operation."""
        return True
```

### Dependency Injection Integration

```python
from acb.depends import depends
from crackerjack.models.protocols import Console, TestManagerProtocol

# Register concrete implementation
depends.set(Console, MyConsoleImplementation())
depends.set(TestManagerProtocol, MyTestManager())


# Inject in functions/classes
@depends.inject
def my_function(
    console: Console = depends(),
    test_manager: TestManagerProtocol = depends(),
) -> None:
    """Function with automatic dependency injection."""
    console.print("Running tests...")
    test_manager.run_tests(options)
```

## Configuration

Models use **Pydantic** for validation and type safety:

```python
from pydantic import BaseModel, Field


class MyConfig(BaseModel):
    """Example configuration model."""

    timeout: int = Field(default=300, gt=0, description="Timeout in seconds")
    enabled: bool = Field(default=True, description="Enable feature")
    patterns: list[str] = Field(default_factory=list, description="File patterns")
```

## Best Practices

1. **ALWAYS Import Protocols**: Never import concrete classes for dependencies
1. **Use @runtime_checkable**: Mark all protocols with `@runtime_checkable`
1. **Extend ServiceProtocol**: Base all service protocols on `ServiceProtocol`
1. **Use Inject[T]**: Use `Inject[ProtocolType]` type hints for DI parameters
1. **Validate with Pydantic**: Use Pydantic models for configuration validation
1. **Document Protocols**: Add comprehensive docstrings to protocol methods
1. **Type Annotate Everything**: Use Python 3.13+ type hints (`|` unions)

## Related Documentation

- [CLAUDE.md](../../docs/guides/CLAUDE.md) - Architecture patterns and DI guidelines
- [Managers](../managers/README.md) - Protocol implementations
- [Services](../services/README.md) - Service layer implementations
- [Core](../core/README.md) - Coordinators and orchestration
- [COVERAGE_POLICY.md](../../docs/reference/COVERAGE_POLICY.md) - Testing requirements

## Future Enhancements

- Phase 5: Additional agent system protocols
- Enhanced validation protocols for AI agent fixes
- Extended performance monitoring protocols
- Advanced caching strategy protocols
