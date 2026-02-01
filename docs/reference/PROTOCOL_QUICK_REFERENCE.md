# Protocol Documentation Quick Reference

**Last Updated**: 2025-01-31
**Status**: 🟡 Needs Improvement (6.5/10)

---

## Executive Summary

Crackerjack has **61 protocols, 278 methods** with **world-class architecture** but **zero documentation**.

| Metric | Score | Status |
|--------|-------|--------|
| Architecture Quality | 10/10 | ✅ Excellent |
| Type Safety | 8/10 | ✅ Good |
| Documentation Coverage | 0/10 | ❌ Critical Gap |
| Developer Experience | 6/10 | ⚠️ Needs Work |

---

## Protocol Overview

### What Are Protocols?

**Protocols** (PEP 544) define interfaces without requiring inheritance:

```python
from typing import Protocol

@runtime_checkable
class ServiceProtocol(Protocol):
    """Base interface for all services."""

    def initialize(self) -> None: ...
    def cleanup(self) -> None: ...
    def health_check(self) -> bool: ...
```

**Benefits**:
- ✅ Loose coupling (no inheritance required)
- ✅ Duck typing with type safety
- ✅ Easy testing with mock implementations
- ✅ Clear interface contracts

### Protocol Hierarchy

```
ServiceProtocol (base)
├── TestManagerProtocol
├── CoverageRatchetProtocol
├── SecurityServiceProtocol
├── QAAdapterProtocol
├── [20+ service-specific protocols]
└── ...

Standalone Protocols
├── ConsoleInterface
├── OptionsProtocol
├── GitInterface
└── [30+ domain-specific protocols]
```

---

## Core Protocols

### 1. ServiceProtocol

**Purpose**: Base interface for all services in crackerjack

**Lifecycle Methods**:
```python
def initialize(self) -> None: ...
    """One-time setup. Called before any other methods."""

def cleanup(self) -> None: ...
    """Resource cleanup. Safe to call multiple times."""

def health_check(self) -> bool: ...
    """Check if service is healthy."""

def shutdown(self) -> None: ...
    """Graceful shutdown."""
```

**Usage Pattern**:
```python
def setup_service(service: ServiceProtocol) -> None:
    service.initialize()
    assert service.health_check()
    # Use service
    service.cleanup()
```

---

### 2. TestManagerProtocol

**Purpose**: Manages test execution and coverage tracking

**Key Methods**:
```python
def run_tests(self, options: OptionsProtocol) -> bool: ...
    """Run test suite. Returns True if all pass."""

def get_test_failures(self) -> list[str]: ...
    """Get list of failed test names."""

def get_coverage(self) -> dict[str, t.Any]: ...
    """Get coverage metrics."""
```

**Usage Example**:
```python
test_manager: TestManagerProtocol = TestManager(console)
success = test_manager.run_tests(options)
if not success:
    failures = test_manager.get_test_failures()
    console.print(f"Failed: {failures}")
```

---

### 3. ConsoleInterface

**Purpose**: Abstract console output (terminal, logs, etc.)

**Key Methods**:
```python
def print(self, *args: t.Any, **kwargs: t.Any) -> None: ...
    """Print output to console."""

def input(self, prompt: str = "") -> str: ...
    """Get user input."""

async def aprint(self, *args: t.Any, **kwargs: t.Any) -> None: ...
    """Async print (TYPE_CHECKING only)."""
```

**Implementations**:
- `CrackerjackConsole`: Rich console with colors
- `MockConsole`: Testing mock
- Any object with `print()` method

---

### 4. OptionsProtocol

**Purpose**: Container for CLI options and configuration

**Key Attributes**:
```python
commit: bool
test: bool
verbose: bool
run_tests: bool
ai_fix: bool
test_workers: int
# ... 50+ options
```

**Usage**:
```python
def run_checks(options: OptionsProtocol) -> None:
    if options.verbose:
        console.print("Verbose mode enabled")
    if options.test:
        test_manager.run_tests(options)
```

---

### 5. QAAdapterProtocol

**Purpose**: Base interface for QA tool adapters (ruff, mypy, etc.)

**Key Methods**:
```python
async def init(self) -> None: ...
    """Initialize adapter (load config, setup tool)."""

async def check(
    self,
    files: list[Path] | None = None,
    config: t.Any | None = None,
) -> t.Any: ...
    """Run QA checks on files."""

async def health_check(self) -> dict[str, t.Any]: ...
    """Check if tool is available and working."""
```

**Lifecycle**:
```python
async def use_adapter(adapter: QAAdapterProtocol):
    await adapter.init()
    result = await adapter.check(files=[Path("test.py")])
    return result
```

**Implementations**:
- `RuffAdapter`: Ruff linting/formatting
- `MypyAdapter`: Type checking
- `PytestAdapter`: Test execution
- [18 total adapters]

---

## Usage Patterns

### Pattern 1: Protocol-Based Dependency Injection

```python
from crackerjack.models.protocols import (
    ConsoleInterface,
    TestManagerProtocol,
)

def create_coordinator(
    console: ConsoleInterface,
    test_manager: TestManagerProtocol,
) -> SessionCoordinator:
    """Create coordinator with protocol-based DI."""
    return SessionCoordinator(
        console=console,
        test_manager=test_manager,
    )

# Usage
console: ConsoleInterface = CrackerjackConsole()
test_manager: TestManagerProtocol = TestManager(console)
coordinator = create_coordinator(console, test_manager)
```

**Benefits**:
- ✅ Easy testing (pass mocks)
- ✅ Loose coupling
- ✅ Type safety

---

### Pattern 2: Protocol Compliance Checking

```python
from crackerjack.models.protocols import ServiceProtocol

def verify_service(service: t.Any) -> None:
    """Verify object implements ServiceProtocol."""
    if isinstance(service, ServiceProtocol):
        service.initialize()
        assert service.health_check()
        print("✅ Service implements ServiceProtocol")
    else:
        raise TypeError("Not a valid service")

# Usage
service = MyService()
verify_service(service)  # Raises if invalid
```

---

### Pattern 3: Protocol Composition

```python
# Multiple protocol inheritance
class MyService:
    def initialize(self) -> None: ...
    def cleanup(self) -> None: ...
    def health_check(self) -> bool: ...

    def run_tests(self, options: OptionsProtocol) -> bool: ...
    def get_test_failures(self) -> list[str]: ...

# Check both protocols
from crackerjack.models.protocols import (
    ServiceProtocol,
    TestManagerProtocol,
)

assert isinstance(service, ServiceProtocol)
assert isinstance(service, TestManagerProtocol)
```

---

### Pattern 4: Mock Protocol Implementation

```python
class MockTestManager:
    """Mock TestManagerProtocol for testing."""

    def __init__(self):
        self.should_fail = False

    def run_tests(self, options: OptionsProtocol) -> bool:
        return not self.should_fail

    def get_test_failures(self) -> list[str]:
        return ["mock_test_1"] if self.should_fail else []

    # Implement other TestManagerProtocol methods...

# Usage
mock = MockTestManager()
assert isinstance(mock, TestManagerProtocol)
mock.should_fail = True
assert not mock.run_tests(options)
```

---

## Implementation Guide

### How to Implement a Protocol

**Step 1**: Import the protocol
```python
from crackerjack.models.protocols import ServiceProtocol
```

**Step 2**: Create a class with matching methods
```python
class MyService:
    def __init__(self, config: Config):
        self.config = config
        self._initialized = False

    def initialize(self) -> None:
        """One-time setup."""
        if self._initialized:
            return
        # Setup code here
        self._initialized = True

    def cleanup(self) -> None:
        """Resource cleanup."""
        if not self._initialized:
            return
        # Teardown code here
        self._initialized = False

    def health_check(self) -> bool:
        """Check if service is healthy."""
        return self._initialized

    # ... implement other required methods
```

**Step 3**: Use type hints to verify compliance
```python
def use_service(service: ServiceProtocol) -> None:
    service.initialize()
    assert service.health_check()

my_service = MyService(config)
use_service(my_service)  # Type checker verifies compliance
```

**Step 4**: Add runtime check (optional but recommended)
```python
if isinstance(my_service, ServiceProtocol):
    use_service(my_service)
else:
    raise TypeError("MyService doesn't implement ServiceProtocol")
```

---

## Testing Protocol Implementations

### Unit Testing Pattern

```python
import pytest
from crackerjack.models.protocols import ServiceProtocol

def test_service_implementation():
    """Test that MyService implements ServiceProtocol."""
    service = MyService(config=Config())

    # Check protocol compliance
    assert isinstance(service, ServiceProtocol)

    # Test lifecycle
    service.initialize()
    assert service.health_check() is True

    service.cleanup()
    # Post-cleanup state

def test_service_with_mock():
    """Test using protocol mock."""
    mock_service = MockService()
    result = use_service(mock_service)
    assert result == expected
```

---

## Common Pitfalls

### ❌ Pitfall 1: Missing Required Methods

```python
# WRONG: Missing cleanup() method
class BrokenService:
    def initialize(self) -> None: ...
    def health_check(self) -> bool: ...
    # cleanup() is missing!

# Type checker will catch this, but runtime won't
service = BrokenService()
isinstance(service, ServiceProtocol)  # Returns True (wrong!)
service.cleanup()  # AttributeError at runtime
```

**Fix**: Always implement all protocol methods
```python
# CORRECT: All methods implemented
class GoodService:
    def initialize(self) -> None: ...
    def cleanup(self) -> None: ...
    def health_check(self) -> bool: ...
```

---

### ❌ Pitfall 2: Wrong Method Signatures

```python
# WRONG: Wrong return type
class BadService:
    def health_check(self) -> str:  # Should return bool!
        return "healthy"

# Type checker error, but runtime passes isinstance()
service = BadService()
if isinstance(service, ServiceProtocol):
    result = service.health_check()
    # result is "healthy" (str), not True/False (bool)
```

**Fix**: Match exact protocol signature
```python
# CORRECT: Exact signature match
class GoodService:
    def health_check(self) -> bool:
        return True
```

---

### ❌ Pitfall 3: Not Calling `initialize()`

```python
# WRONG: Using service without initialization
service = MyService()
result = service.do_work()  # May fail!

# CORRECT: Always initialize first
service = MyService()
service.initialize()
result = service.do_work()  # Works!
```

**Fix**: Always follow service lifecycle
```python
service = MyService()
service.initialize()
try:
    result = service.do_work()
finally:
    service.cleanup()
```

---

## Protocol Best Practices

### ✅ DO

1. **Always import protocols from `models.protocols`**
   ```python
   from crackerjack.models.protocols import ServiceProtocol
   ```

2. **Use protocols in type hints**
   ```python
   def process(service: ServiceProtocol) -> None:
       service.initialize()
   ```

3. **Verify protocol compliance at runtime**
   ```python
   assert isinstance(obj, ServiceProtocol)
   ```

4. **Follow service lifecycle**
   ```python
   service.initialize()
   try:
       service.do_work()
   finally:
       service.cleanup()
   ```

5. **Use protocol-based dependency injection**
   ```python
   def __init__(
       self,
       console: ConsoleInterface,
       test_manager: TestManagerProtocol,
   ):
       self.console = console
       self.test_manager = test_manager
   ```

---

### ❌ DON'T

1. **Don't import concrete classes**
   ```python
   # WRONG
   from crackerjack.managers.test_manager import TestManager

   # CORRECT
   from crackerjack.models.protocols import TestManagerProtocol
   ```

2. **Don't skip protocol methods**
   ```python
   # WRONG: Missing method
   class BadService:
       def initialize(self) -> None: ...
       # cleanup() is missing!
   ```

3. **Don't ignore type hints**
   ```python
   # WRONG: No type hint
   def setup(service):  # What type is service?

   # CORRECT: Protocol type hint
   def setup(service: ServiceProtocol):
   ```

4. **Don't use global singletons**
   ```python
   # WRONG
   console = Console()  # Global

   # CORRECT
   def __init__(self, console: ConsoleInterface):
       self.console = console
   ```

---

## Protocol Reference

### Complete Protocol List (61 total)

#### Core Protocols (5)
- `ServiceProtocol` - Base for all services
- `CommandRunner` - Subprocess execution
- `OptionsProtocol` - CLI options container
- `ConsoleInterface` - Console output abstraction
- `FileSystemInterface` - File operations

#### Service Protocols (20)
- `TestManagerProtocol` - Test execution
- `CoverageRatchetProtocol` - Coverage tracking
- `SecurityServiceProtocol` - Security checks
- `InitializationServiceProtocol` - Project setup
- `SmartSchedulingServiceProtocol` - Task scheduling
- `UnifiedConfigurationServiceProtocol` - Config management
- `ConfigIntegrityServiceProtocol` - Config validation
- `BoundedStatusOperationsProtocol` - Circuit breaker
- `ConfigMergeServiceProtocol` - Config merging
- `DocumentationServiceProtocol` - Documentation generation
- `EnhancedFileSystemServiceProtocol` - Async file ops
- `PerformanceBenchmarkServiceProtocol` - Benchmarking
- `DebugServiceProtocol` - Debug logging
- `QualityIntelligenceProtocol` - Quality analytics
- `CoverageRatchetServiceProtocol` - Coverage enforcement
- `ServerManagerProtocol` - Process management
- `LogManagementProtocol` - Structured logging
- `SmartFileFilterProtocol` - File filtering
- `SafeFileModifierProtocol` - Safe file editing
- `HealthMetricsServiceProtocol` - Health tracking
- `CoverageBadgeServiceProtocol` - Badge generation
- `AgentCoordinatorProtocol` - AI agent orchestration
- `ServiceWatchdogProtocol` - Service monitoring

#### QA Protocols (5)
- `QAAdapterProtocol` - QA tool base
- `QAOrchestratorProtocol` - QA orchestration
- `ExecutionStrategyProtocol` - Execution patterns
- `CacheStrategyProtocol` - Result caching
- `HookOrchestratorProtocol` - Hook orchestration

#### Hook Protocols (3)
- `HookManager` - Hook execution
- `SecurityAwareHookManager` - Security-focused hooks
- `HookLockManagerProtocol` - Hook locking
- `PublishManager` - Publishing operations

#### Performance Protocols (8)
- `PerformanceMonitorProtocol` - Performance tracking
- `MemoryOptimizerProtocol` - Memory optimization
- `PerformanceCacheProtocol` - Result caching
- `QualityBaselineProtocol` - Quality baselines
- `ParallelExecutorProtocol` - Parallel execution
- `ParallelHookExecutorProtocol` - Parallel hooks
- `AsyncCommandExecutorProtocol` - Async commands
- `PerformanceBenchmarkProtocol` - Benchmarking

#### Documentation Protocols (4)
- `APIExtractorProtocol` - API extraction
- `DocumentationGeneratorProtocol` - Doc generation
- `DocumentationValidatorProtocol` - Doc validation
- `DocumentationCleanupProtocol` - Doc cleanup

#### Agent Protocols (3)
- `AgentTrackerProtocol` - Agent tracking
- `AgentDebuggerProtocol` - Agent debugging
- `TimeoutManagerProtocol` - Timeout management

#### Git Protocols (2)
- `GitInterface` - Git operations
- `GitServiceProtocol` - Git service

#### Utility Protocols (6)
- `LoggerProtocol` - Logging interface
- `ConfigManagerProtocol` - Config management
- `FileSystemServiceProtocol` - File operations
- `RegexPatternsProtocol` - Safe regex
- `SecureStatusFormatterProtocol` - Secure formatting
- `VersionAnalyzerProtocol` - Version analysis
- `ChangelogGeneratorProtocol` - Changelog generation

---

## Getting Help

### Documentation

- Full Protocol Review: `/docs/reference/PROTOCOL_DOCUMENTATION_REVIEW.md`
- Architecture Compliance: See `CLAUDE.md` - "Architecture Compliance Protocol"
- Protocol Examples: See implementation in `/crackerjack/managers/` and `/crackerjack/services/`

### Examples

- Protocol Implementation: `TestManager` in `/crackerjack/managers/test_manager.py`
- Protocol Usage: `SessionCoordinator` in `/crackerjack/core/session_coordinator.py`
- Protocol Testing: See `/tests/unit/` for test patterns

### Support

- Questions? Check protocol implementation examples
- Issues? Report protocol documentation gaps
- Contributions? Follow protocol documentation templates

---

## Next Steps

### Immediate Actions

1. **Read Full Review**: Check `PROTOCOL_DOCUMENTATION_REVIEW.md` for detailed analysis
2. **Study Examples**: Review `TestManager` and `SessionCoordinator` implementations
3. **Follow Patterns**: Use "Usage Patterns" section above for common scenarios

### For Protocol Authors

1. **Add Docstrings**: Follow templates in `PROTOCOL_DOCUMENTATION_REVIEW.md` Appendix B
2. **Document Contracts**: Specify preconditions, postconditions, errors
3. **Provide Examples**: Show typical usage patterns
4. **Testing Guide**: Document how to test protocol implementations

### For Protocol Users

1. **Use Protocol Imports**: Always import from `crackerjack.models.protocols`
2. **Type Hints**: Use protocols in function signatures
3. **Runtime Checks**: Verify with `isinstance()` when needed
4. **Lifecycle**: Follow `initialize()` → use → `cleanup()` pattern

---

**Version**: 1.0
**Status**: 🟡 Needs Improvement
**Target**: 🟢 Excellent (9+/10) by Q2 2025
