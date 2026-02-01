# Protocol Reference Guide

**Version**: 1.0
**Last Updated**: 2025-01-31
**Target Audience**: New developers joining crackerjack
**Prerequisites**: Python 3.13+, basic type hints knowledge

---

## Table of Contents

1. [Quick Start: What Are Protocols?](#quick-start-what-are-protocols)
2. [Why Protocol-Based Architecture?](#why-protocol-based-architecture)
3. [Protocol Hierarchy and Organization](#protocol-hierarchy-and-organization)
4. [Core Protocols Explained](#core-protocols-explained)
5. [Service Protocols](#service-protocols)
6. [Usage Patterns](#usage-patterns)
7. [Implementation Guide](#implementation-guide)
8. [Common Pitfalls and Solutions](#common-pitfalls-and-solutions)
9. [Best Practices](#best-practices)
10. [Complete Protocol Reference](#complete-protocol-reference)

---

## Quick Start: What Are Protocols?

### Definition

**Protocols** (PEP 544) are Python's way to define interfaces without requiring inheritance. They specify **what** an object can do, not **how** it's implemented.

```python
from typing import Protocol

@runtime_checkable
class ServiceProtocol(Protocol):
    """Base interface for all services."""

    def initialize(self) -> None: ...
    def cleanup(self) -> None: ...
    def health_check(self) -> bool: ...
```

### Key Characteristics

1. **Duck Typing with Type Safety**
   - "If it walks like a duck and quacks like a duck, it's a duck"
   - Protocols verify the "walking" and "quacking" at type-check time

2. **No Inheritance Required**
   - Classes implement protocols by having matching methods
   - No explicit inheritance needed: `class MyService(ServiceProtocol)`

3. **Structural Subtyping**
   - Based on structure (methods/attributes), not names
   - Two classes with same methods implement same protocol

### Basic Example

```python
from crackerjack.models.protocols import ConsoleInterface

# Any class with a print() method implements ConsoleInterface
class MyConsole:
    def print(self, *args: Any, **kwargs: Any) -> None:
        print(*args, **kwargs)

# Type checker verifies compliance
console: ConsoleInterface = MyConsole()  # ✅ Valid
console.print("Hello, protocols!")
```

---

## Why Protocol-Based Architecture?

### Benefits

#### 1. **Loose Coupling**

```python
# ❌ Tightly coupled (concrete class dependency)
from crackerjack.managers.test_manager import TestManager

def run_tests(manager: TestManager) -> None:
    manager.run_tests(options)

# ✅ Loosely coupled (protocol dependency)
from crackerjack.models.protocols import TestManagerProtocol

def run_tests(manager: TestManagerProtocol) -> None:
    manager.run_tests(options)
```

**Impact**: Can swap implementations without changing calling code

#### 2. **Easy Testing**

```python
# Create mock implementations without inheritance
class MockTestManager:
    def __init__(self) -> None:
        self.tests_run = False

    def run_tests(self, options: OptionsProtocol) -> bool:
        self.tests_run = True
        return True

    def get_test_failures(self) -> list[str]:
        return []

# Use in tests
mock = MockTestManager()
assert isinstance(mock, TestManagerProtocol)  # ✅ Runtime check passes
```

**Impact**: No complex mocking frameworks needed

#### 3. **Clear Interface Contracts**

```python
@runtime_checkable
class ServiceProtocol(t.Protocol):
    """All services must follow this lifecycle."""

    def initialize(self) -> None:
        """One-time setup. Called before any other methods."""

    def cleanup(self) -> None:
        """Release resources. Safe to call multiple times."""

    def health_check(self) -> bool:
        """Check if service is healthy."""
```

**Impact**: Clear contract, enforced by type checker

#### 4. **Better IDE Support**

```python
def process_tests(manager: TestManagerProtocol) -> None:
    # IDE shows all TestManagerProtocol methods
    manager.run_tests(options)  # ✅ Autocomplete works
    manager.get_test_failures()  # ✅ Type checker validates
```

**Impact**: Better autocomplete, fewer runtime errors

### Protocol vs. Abstract Base Class (ABC)

| Aspect | Protocol | ABC |
|--------|----------|-----|
| Inheritance | Not required | Required |
| Type checking | Structural (has methods) | Nominal (is subclass) |
| Runtime checks | `isinstance()` works | `isinstance()` works |
| Flexibility | High (any class) | Low (must inherit) |
| Use case | APIs, testing | Frameworks, enforcement |

**When to use which**:
- ✅ **Protocol**: Library APIs, dependency injection, testing
- ✅ **ABC**: Framework enforcement, class hierarchies

---

## Protocol Hierarchy and Organization

### Visual Hierarchy

```
ServiceProtocol (base lifecycle)
│
├── TestManagerProtocol
├── CoverageRatchetProtocol
├── SecurityServiceProtocol
├── InitializationServiceProtocol
├── SmartSchedulingServiceProtocol
├── UnifiedConfigurationServiceProtocol
├── ConfigIntegrityServiceProtocol
├── BoundedStatusOperationsProtocol
├── ConfigMergeServiceProtocol
├── DocumentationServiceProtocol
├── EnhancedFileSystemServiceProtocol
├── PerformanceBenchmarkServiceProtocol
├── DebugServiceProtocol
├── QualityIntelligenceProtocol
├── CoverageRatchetServiceProtocol
├── ServerManagerProtocol
├── LogManagementProtocol
├── SmartFileFilterProtocol
├── SafeFileModifierProtocol
├── HealthMetricsServiceProtocol
├── CoverageBadgeServiceProtocol
├── AgentCoordinatorProtocol
└── ServiceWatchdogProtocol

HookManager (base hooks)
│
└── SecurityAwareHookManager

QAAdapterProtocol (base adapters)
│
├── ─ ─ (18 concrete adapters)
│
└── HookOrchestratorProtocol

Standalone Protocols (no inheritance)
├── CommandRunner
├── OptionsProtocol
├── ConsoleInterface
├── FileSystemInterface
├── GitInterface
├── GitServiceProtocol
├── QAOrchestratorProtocol
├── ExecutionStrategyProtocol
├── CacheStrategyProtocol
├── HookLockManagerProtocol
├── PublishManager
├── APIExtractorProtocol
├── DocumentationGeneratorProtocol
├── DocumentationValidatorProtocol
├── DocumentationCleanupProtocol
├── LoggerProtocol
├── ConfigManagerProtocol
├── FileSystemServiceProtocol
├── PerformanceMonitorProtocol
├── MemoryOptimizerProtocol
├── PerformanceCacheProtocol
├── QualityBaselineProtocol
├── ParallelExecutorProtocol
├── ParallelHookExecutorProtocol
├── AsyncCommandExecutorProtocol
├── PerformanceBenchmarkProtocol
├── AgentTrackerProtocol
├── AgentDebuggerProtocol
├── TimeoutManagerProtocol
├── RegexPatternsProtocol
├── SecureStatusFormatterProtocol
├── VersionAnalyzerProtocol
└── ChangelogGeneratorProtocol
```

### Protocol Categories

#### 1. **Core Infrastructure** (5 protocols)
Foundational interfaces used throughout crackerjack.

- `ServiceProtocol` - Base lifecycle for all services
- `CommandRunner` - Subprocess execution
- `OptionsProtocol` - CLI options container
- `ConsoleInterface` - Console output abstraction
- `FileSystemInterface` - File operations

#### 2. **Service Extensions** (23 protocols)
Domain-specific services inheriting from `ServiceProtocol`.

**Testing & Quality**:
- `TestManagerProtocol` - Test execution
- `CoverageRatchetProtocol` - Coverage tracking
- `CoverageRatchetServiceProtocol` - Coverage enforcement

**Configuration**:
- `UnifiedConfigurationServiceProtocol` - Config management
- `ConfigIntegrityServiceProtocol` - Config validation
- `ConfigMergeServiceProtocol` - Config merging

**Security**:
- `SecurityServiceProtocol` - Security checks

**Development**:
- `InitializationServiceProtocol` - Project setup
- `SmartSchedulingServiceProtocol` - Task scheduling

**Monitoring**:
- `DebugServiceProtocol` - Debug logging
- `HealthMetricsServiceProtocol` - Health tracking
- `QualityIntelligenceProtocol` - Quality analytics

**File Operations**:
- `EnhancedFileSystemServiceProtocol` - Async file ops
- `SmartFileFilterProtocol` - File filtering
- `SafeFileModifierProtocol` - Safe file editing

**Documentation**:
- `DocumentationServiceProtocol` - Documentation generation

**Performance**:
- `PerformanceBenchmarkServiceProtocol` - Benchmarking

**Publishing**:
- `CoverageBadgeServiceProtocol` - Badge generation

**Process Management**:
- `ServerManagerProtocol` - Process management
- `ServiceWatchdogProtocol` - Service monitoring
- `LogManagementProtocol` - Structured logging

**AI Agents**:
- `AgentCoordinatorProtocol` - AI agent orchestration

**Circuit Breaker**:
- `BoundedStatusOperationsProtocol` - Circuit breaker pattern

#### 3. **Quality Assurance** (5 protocols)
QA tool orchestration and execution.

- `QAAdapterProtocol` - QA tool base (18 adapters implement this)
- `QAOrchestratorProtocol` - QA orchestration
- `ExecutionStrategyProtocol` - Execution patterns
- `CacheStrategyProtocol` - Result caching
- `HookOrchestratorProtocol` - Hook orchestration

#### 4. **Hook Management** (4 protocols)
Hook execution and locking.

- `HookManager` - Hook execution
- `SecurityAwareHookManager` - Security-focused hooks
- `HookLockManagerProtocol` - Hook locking
- `PublishManager` - Publishing operations

#### 5. **Performance & Monitoring** (8 protocols)
Performance tracking and optimization.

- `PerformanceMonitorProtocol` - Performance tracking
- `MemoryOptimizerProtocol` - Memory optimization
- `PerformanceCacheProtocol` - Result caching
- `QualityBaselineProtocol` - Quality baselines
- `ParallelExecutorProtocol` - Parallel execution
- `ParallelHookExecutorProtocol` - Parallel hooks
- `AsyncCommandExecutorProtocol` - Async commands
- `PerformanceBenchmarkProtocol` - Benchmarking

#### 6. **Documentation System** (4 protocols)
Documentation generation and validation.

- `APIExtractorProtocol` - API extraction
- `DocumentationGeneratorProtocol` - Doc generation
- `DocumentationValidatorProtocol` - Doc validation
- `DocumentationCleanupProtocol` - Doc cleanup

#### 7. **Agent System** (3 protocols)
AI agent tracking and debugging.

- `AgentTrackerProtocol` - Agent tracking
- `AgentDebuggerProtocol` - Agent debugging
- `TimeoutManagerProtocol` - Timeout management

#### 8. **Git Operations** (2 protocols)
Version control operations.

- `GitInterface` - Git operations
- `GitServiceProtocol` - Git service

#### 9. **Utility Protocols** (7 protocols)
Helper protocols for various tasks.

- `LoggerProtocol` - Logging interface
- `ConfigManagerProtocol` - Config management
- `FileSystemServiceProtocol` - File operations
- `RegexPatternsProtocol` - Safe regex
- `SecureStatusFormatterProtocol` - Secure formatting
- `VersionAnalyzerProtocol` - Version analysis
- `ChangelogGeneratorProtocol` - Changelog generation

**Total**: 61 protocols

---

## Core Protocols Explained

### 1. ServiceProtocol

**Purpose**: Base interface for all long-lived services in crackerjack.

**Lifecycle Management**:
```python
ServiceProtocol Lifecycle:
┌─────────────┐
│  Instantiated│
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ initialize()│  ← One-time setup
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Healthy   │  ← Ready to use
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   cleanup() │  ← Release resources
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Shutdown  │  ← Cannot be used again
└─────────────┘
```

**Key Methods**:

```python
@runtime_checkable
class ServiceProtocol(t.Protocol):
    def initialize(self) -> None:
        """One-time setup. Must be called before other methods."""

    def cleanup(self) -> None:
        """Release resources. Safe to call multiple times."""

    def health_check(self) -> bool:
        """Check if service is healthy."""

    def shutdown(self) -> None:
        """Graceful shutdown."""

    def metrics(self) -> dict[str, Any]:
        """Get service metrics."""

    def is_healthy(self) -> bool:
        """Alias for health_check()."""
```

**Implementation Pattern**:

```python
class MyService:
    def __init__(self, config: Config) -> None:
        self.config = config
        self._initialized = False
        self._resources: list[Any] = []

    def initialize(self) -> None:
        """One-time setup."""
        if self._initialized:
            return  # Idempotent

        # Setup resources
        self._setup_database()
        self._setup_network()

        self._initialized = True

    def cleanup(self) -> None:
        """Release all resources."""
        if not self._initialized:
            return  # Already cleaned up

        # Release resources in reverse order
        self._teardown_network()
        self._teardown_database()

        self._initialized = False

    def health_check(self) -> bool:
        """Check if service is healthy."""
        return self._initialized and self._check_resources()

    def _check_resources(self) -> bool:
        """Verify all resources are available."""
        return all(resource.is_healthy for resource in self._resources)
```

**Usage**:

```python
def use_service(service: ServiceProtocol) -> None:
    """Correct service lifecycle usage."""
    try:
        service.initialize()
        assert service.health_check()

        # Use service
        service.do_work()

    finally:
        service.cleanup()
```

**Common Implementations**:
- `TestManager` - Test execution service
- `CoverageRatchet` - Coverage tracking service
- `SecurityService` - Security checking service

---

### 2. TestManagerProtocol

**Purpose**: Manages test execution and coverage tracking.

**Key Methods**:

```python
@runtime_checkable
class TestManagerProtocol(ServiceProtocol, t.Protocol):
    def run_tests(self, options: OptionsProtocol) -> bool:
        """Run test suite. Returns True if all tests pass."""

    def get_test_failures(self) -> list[str]:
        """Get list of failed test names."""

    def validate_test_environment(self) -> bool:
        """Check if test environment is valid."""

    def get_coverage(self) -> dict[str, Any]:
        """Get coverage metrics."""
```

**Usage Example**:

```python
def run_test_suite(test_manager: TestManagerProtocol, options: OptionsProtocol) -> None:
    """Run tests and handle failures."""
    if not test_manager.validate_test_environment():
        console.print("[red]Test environment invalid[/red]")
        return

    success = test_manager.run_tests(options)

    if not success:
        failures = test_manager.get_test_failures()
        console.print(f"[red]Failed tests:[/red] {', '.join(failures)}")
    else:
        coverage = test_manager.get_coverage()
        console.print(f"[green]Coverage: {coverage['percent']}%[/green]")
```

---

### 3. ConsoleInterface

**Purpose**: Abstract console output for terminal, logs, testing, etc.

**Key Methods**:

```python
@runtime_checkable
class ConsoleInterface(t.Protocol):
    def print(self, *args: Any, **kwargs: Any) -> None:
        """Print output to console."""

    def input(self, prompt: str = "") -> str:
        """Get user input."""

    async def aprint(self, *args: Any, **kwargs: Any) -> None:
        """Async print (TYPE_CHECKING only)."""
```

**Implementations**:

1. **CrackerjackConsole** (Rich-based)
   ```python
   from rich.console import Console

   class CrackerjackConsole:
       def __init__(self) -> None:
           self.console = Console()

       def print(self, *args: Any, **kwargs: Any) -> None:
           self.console.print(*args, **kwargs)
   ```

2. **MockConsole** (Testing)
   ```python
   class MockConsole:
       def __init__(self) -> None:
           self.outputs: list[str] = []

       def print(self, *args: Any, **kwargs: Any) -> None:
           self.outputs.append(str(args))
   ```

**Usage Pattern**:

```python
def display_results(console: ConsoleInterface, results: dict[str, Any]) -> None:
    """Display results using any console implementation."""
    console.print(f"[green]Success:[/green] {results['success']}")
    console.print(f"[blue]Duration:[/blue] {results['duration']}s")

# Production
console: ConsoleInterface = CrackerjackConsole()
display_results(console, results)

# Testing
mock_console: ConsoleInterface = MockConsole()
display_results(mock_console, results)
assert len(mock_console.outputs) == 2
```

---

### 4. OptionsProtocol

**Purpose**: Container for CLI options and configuration.

**Key Attributes**:

```python
@runtime_checkable
class OptionsProtocol(t.Protocol):
    # Test options
    run_tests: bool
    test_workers: int
    test_timeout: int
    benchmark: bool

    # AI options
    ai_fix: bool
    ai_agent: bool
    ai_fix_max_iterations: int

    # Quality options
    fast: bool  # Fast hooks only
    comp: bool  # Comprehensive hooks
    skip_hooks: bool

    # Publishing options
    publish: Any | None
    bump: Any | None
    all: Any | None

    # Verbose output
    verbose: bool

    # ... 50+ total options
```

**Usage**:

```python
def execute_workflow(options: OptionsProtocol) -> None:
    """Execute workflow based on options."""
    if options.verbose:
        console.print("Verbose mode enabled")

    if options.run_tests:
        test_manager.run_tests(options)

    if options.comp:
        hook_manager.run_comprehensive_hooks()

    if options.ai_fix:
        agent_coordinator.handle_issues(failures)
```

---

### 5. FileSystemInterface

**Purpose**: Abstract file operations for testing and portability.

**Key Methods**:

```python
@runtime_checkable
class FileSystemInterface(t.Protocol):
    def read_file(self, path: str | Any) -> str:
        """Read file contents."""

    def write_file(self, path: str | Any, content: str) -> None:
        """Write content to file."""

    def exists(self, path: str | Any) -> bool:
        """Check if file exists."""

    def mkdir(self, path: str | Any, parents: bool = False) -> None:
        """Create directory."""
```

**Mock Implementation**:

```python
class MockFileSystem:
    """In-memory filesystem for testing."""

    def __init__(self) -> None:
        self.files: dict[str, str] = {}

    def read_file(self, path: str | Any) -> str:
        return self.files[str(path)]

    def write_file(self, path: str | Any, content: str) -> None:
        self.files[str(path)] = content

    def exists(self, path: str | Any) -> bool:
        return str(path) in self.files

    def mkdir(self, path: str | Any, parents: bool = False) -> None:
        # No-op for in-memory filesystem
        pass
```

**Usage**:

```python
def process_file(fs: FileSystemInterface, path: str) -> None:
    """Process file using any filesystem implementation."""
    if not fs.exists(path):
        raise FileNotFoundError(f"File not found: {path}")

    content = fs.read_file(path)
    processed = content.upper()
    fs.write_file(path, processed)

# Production
fs: FileSystemInterface = RealFileSystem()
process_file(fs, "/path/to/file.txt")

# Testing
mock_fs: FileSystemInterface = MockFileSystem()
mock_fs.write_file("/test.txt", "hello")
process_file(mock_fs, "/test.txt")
assert mock_fs.read_file("/test.txt") == "HELLO"
```

---

## Service Protocols

Service protocols extend `ServiceProtocol` with domain-specific functionality.

### TestManagerProtocol

**Purpose**: Test execution and coverage management.

**Key Methods**:
- `run_tests(options)` - Execute test suite
- `get_test_failures()` - Get failed test names
- `validate_test_environment()` - Check environment
- `get_coverage()` - Get coverage metrics

**When to Use**: Need to run tests or check coverage

**Example Implementation**: `TestManager` in `/crackerjack/managers/test_manager.py`

---

### CoverageRatchetProtocol

**Purpose**: Enforce coverage never decreases (ratchet system).

**Key Methods**:
- `get_baseline_coverage()` - Get current baseline
- `update_baseline_coverage(new_coverage)` - Update baseline
- `is_coverage_regression(current_coverage)` - Check for regression
- `get_coverage_improvement_needed()` - Get improvement needed

**When to Use**: Need to enforce coverage standards

**Example**:
```python
def check_coverage(ratchet: CoverageRatchetProtocol, current: float) -> None:
    """Check coverage against ratchet."""
    if ratchet.is_coverage_regression(current):
        baseline = ratchet.get_baseline_coverage()
        raise ValueError(f"Coverage regression! {current}% < {baseline}%")
```

---

### SecurityServiceProtocol

**Purpose**: Security checks and validation.

**Key Methods**:
- `validate_file_safety(path)` - Check if file is safe to modify
- `check_hardcoded_secrets(content)` - Find hardcoded secrets
- `is_safe_subprocess_call(cmd)` - Check subprocess safety
- `create_secure_command_env()` - Create secure subprocess environment

**When to Use**: Need security validation before operations

**Example**:
```python
def safe_edit_file(security: SecurityServiceProtocol, path: str, content: str) -> None:
    """Safely edit file with security checks."""
    if not security.validate_file_safety(path):
        raise SecurityError(f"Unsafe to edit: {path}")

    secrets = security.check_hardcoded_secrets(content)
    if secrets:
        raise SecurityError(f"Hardcoded secrets found: {secrets}")

    # Edit file
```

---

### QAAdapterProtocol

**Purpose**: Base interface for QA tool adapters (ruff, mypy, pytest, etc.).

**Key Methods**:
- `async init()` - Initialize adapter (load config, setup tool)
- `async check(files, config)` - Run QA checks
- `async validate_config(config)` - Validate configuration
- `get_default_config()` - Get default configuration
- `async health_check()` - Check tool availability

**When to Use**: Implementing a new QA tool adapter

**Example**:
```python
class MyQAAdapter:
    """Custom QA tool adapter."""

    async def init(self) -> None:
        """Initialize adapter."""
        self.config = self.get_default_config()
        await self._setup_tool()

    async def check(
        self,
        files: list[Path] | None = None,
        config: Any | None = None,
    ) -> Any:
        """Run QA checks."""
        tool_config = config or self.config
        return await self._run_tool(files, tool_config)

    async def health_check(self) -> dict[str, Any]:
        """Check if tool is available."""
        return {
            "available": await self._check_tool_installed(),
            "version": await self._get_tool_version(),
        }
```

**Common Implementations**:
- `RuffAdapter` - Ruff linting/formatting
- `MypyAdapter` - Type checking
- `PytestAdapter` - Test execution
- `BanditAdapter` - Security linting
- [18 total adapters]

---

## Usage Patterns

### Pattern 1: Protocol-Based Dependency Injection

**Concept**: Inject dependencies via protocols, not concrete classes.

**Benefits**:
- Easy testing (inject mocks)
- Loose coupling (swap implementations)
- Type safety (enforced by type checker)

**Example**:

```python
from crackerjack.models.protocols import (
    ConsoleInterface,
    TestManagerProtocol,
    FileSystemInterface,
)

class SessionCoordinator:
    """Coordinates quality check session."""

    def __init__(
        self,
        console: ConsoleInterface,
        test_manager: TestManagerProtocol,
        filesystem: FileSystemInterface,
    ) -> None:
        """Constructor injection with protocols."""
        self.console = console
        self.test_manager = test_manager
        self.filesystem = filesystem

    def run_session(self, options: OptionsProtocol) -> None:
        """Run quality check session."""
        self.console.print("Starting session...")

        if options.run_tests:
            success = self.test_manager.run_tests(options)
            if not success:
                self.console.print("Tests failed!")

# Usage
console: ConsoleInterface = CrackerjackConsole()
test_manager: TestManagerProtocol = TestManager(console)
filesystem: FileSystemInterface = FileSystemService()

coordinator = SessionCoordinator(console, test_manager, filesystem)
coordinator.run_session(options)
```

**Testing**:

```python
def test_session_coordinator() -> None:
    """Test coordinator with mocks."""
    mock_console = MockConsole()
    mock_test_manager = MockTestManager()
    mock_filesystem = MockFileSystem()

    coordinator = SessionCoordinator(
        mock_console,
        mock_test_manager,
        mock_filesystem,
    )

    coordinator.run_session(options)

    assert mock_test_manager.tests_run
    assert len(mock_console.outputs) > 0
```

---

### Pattern 2: Protocol Compliance Checking

**Concept**: Verify objects implement protocols at runtime.

**When to Use**:
- Accepting user-provided objects
- Plugin systems
- Runtime validation

**Example**:

```python
from crackerjack.models.protocols import ServiceProtocol

def register_service(service: Any) -> None:
    """Register service after validating protocol compliance."""
    if not isinstance(service, ServiceProtocol):
        raise TypeError(
            f"Service must implement ServiceProtocol, "
            f"got {type(service).__name__}"
        )

    # Safe to use ServiceProtocol methods
    service.initialize()
    assert service.health_check()

    services.append(service)
```

---

### Pattern 3: Protocol Composition

**Concept**: Combine multiple protocols for rich interfaces.

**Example**:

```python
from crackerjack.models.protocols import (
    ServiceProtocol,
    TestManagerProtocol,
    CoverageRatchetProtocol,
)

class ComprehensiveTestService:
    """Implements multiple protocols."""

    # ServiceProtocol methods
    def initialize(self) -> None: ...
    def cleanup(self) -> None: ...
    def health_check(self) -> bool: ...

    # TestManagerProtocol methods
    def run_tests(self, options: OptionsProtocol) -> bool: ...
    def get_test_failures(self) -> list[str]: ...

    # CoverageRatchetProtocol methods
    def get_baseline_coverage(self) -> float: ...
    def update_baseline_coverage(self, new_coverage: float) -> bool: ...

# Check all protocols
service = ComprehensiveTestService()

assert isinstance(service, ServiceProtocol)
assert isinstance(service, TestManagerProtocol)
assert isinstance(service, CoverageRatchetProtocol)
```

---

### Pattern 4: Mock Protocol Implementation

**Concept**: Create lightweight mocks for testing.

**Example**:

```python
class MockTestManager:
    """Mock TestManagerProtocol for testing."""

    def __init__(self) -> None:
        self.should_fail = False
        self.failures: list[str] = []
        self.tests_run = False

    # ServiceProtocol methods
    def initialize(self) -> None:
        """Initialize mock."""

    def cleanup(self) -> None:
        """Cleanup mock."""

    def health_check(self) -> bool:
        """Always healthy."""
        return True

    # TestManagerProtocol methods
    def run_tests(self, options: OptionsProtocol) -> bool:
        """Run mock tests."""
        self.tests_run = True
        return not self.should_fail

    def get_test_failures(self) -> list[str]:
        """Get mock failures."""
        return self.failures if self.should_fail else []

    def validate_test_environment(self) -> bool:
        """Always valid."""
        return True

    def get_coverage(self) -> dict[str, Any]:
        """Get mock coverage."""
        return {"percent": 85.0}
```

**Usage**:

```python
def test_workflow_with_mock() -> None:
    """Test workflow using mock test manager."""
    mock = MockTestManager()
    mock.should_fail = True
    mock.failures = ["test_example", "test_another"]

    success = mock.run_tests(options)

    assert not success
    assert mock.tests_run
    assert mock.get_test_failures() == ["test_example", "test_another"]
```

---

## Implementation Guide

### Step-by-Step: Implementing a Protocol

#### Step 1: Import the Protocol

```python
from crackerjack.models.protocols import ServiceProtocol
```

#### Step 2: Create Class with Matching Methods

```python
class MyService:
    """Custom service implementation."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self._initialized = False
        self._resources: list[Any] = []

    # ServiceProtocol methods
    def initialize(self) -> None:
        """One-time setup."""
        if self._initialized:
            return

        self._setup_resources()
        self._initialized = True

    def cleanup(self) -> None:
        """Release resources."""
        if not self._initialized:
            return

        self._teardown_resources()
        self._initialized = False

    def health_check(self) -> bool:
        """Check if healthy."""
        return self._initialized

    # ServiceProtocol additional methods
    def shutdown(self) -> None:
        """Graceful shutdown."""
        self.cleanup()

    def metrics(self) -> dict[str, Any]:
        """Get metrics."""
        return {"initialized": self._initialized}

    def is_healthy(self) -> bool:
        """Check if healthy."""
        return self.health_check()

    # Additional methods (not in protocol)
    def _setup_resources(self) -> None:
        """Setup resources."""
        pass

    def _teardown_resources(self) -> None:
        """Teardown resources."""
        pass
```

#### Step 3: Use Type Hints

```python
def use_service(service: ServiceProtocol) -> None:
    """Use service with protocol type hint."""
    service.initialize()
    assert service.health_check()

    # Type checker validates these calls
    service.cleanup()
```

#### Step 4: Runtime Verification (Optional)

```python
def verify_service(service: Any) -> ServiceProtocol:
    """Verify and return service."""
    if not isinstance(service, ServiceProtocol):
        raise TypeError(f"Not a ServiceProtocol: {type(service)}")

    return service

# Usage
my_service = MyService(config)
verified = verify_service(my_service)
verified.initialize()
```

---

## Common Pitfalls and Solutions

### Pitfall 1: Missing Required Methods

**Problem**:

```python
# WRONG: Missing cleanup() method
class BrokenService:
    def initialize(self) -> None: ...
    def health_check(self) -> bool: ...
    # cleanup() is missing!

# Type checker will catch this, but runtime isinstance() passes
service = BrokenService()
isinstance(service, ServiceProtocol)  # ✅ Returns True (WRONG!)
service.cleanup()  # ❌ AttributeError at runtime
```

**Solution**: Always implement all protocol methods

```python
# CORRECT: All methods implemented
class GoodService:
    def initialize(self) -> None: ...
    def cleanup(self) -> None: ...
    def health_check(self) -> bool: ...
```

**Verification**:

```python
def test_protocol_compliance() -> None:
    """Test that all protocol methods are implemented."""
    service = GoodService()

    # Check each method exists
    assert hasattr(service, 'initialize')
    assert hasattr(service, 'cleanup')
    assert hasattr(service, 'health_check')

    # Test callable
    assert callable(service.initialize)
    assert callable(service.cleanup)
    assert callable(service.health_check)
```

---

### Pitfall 2: Wrong Method Signatures

**Problem**:

```python
# WRONG: Wrong return type
class BadService:
    def health_check(self) -> str:  # Should return bool!
        return "healthy"

# Type checker error, but runtime isinstance() passes
service = BadService()
if isinstance(service, ServiceProtocol):
    result = service.health_check()
    # result is "healthy" (str), not True/False (bool)
```

**Solution**: Match exact protocol signature

```python
# CORRECT: Exact signature match
class GoodService:
    def health_check(self) -> bool:
        return True
```

---

### Pitfall 3: Not Calling `initialize()`

**Problem**:

```python
# WRONG: Using service without initialization
service = MyService()
result = service.do_work()  # May fail!
```

**Solution**: Always follow service lifecycle

```python
# CORRECT: Always initialize first
service = MyService()
service.initialize()
try:
    result = service.do_work()
finally:
    service.cleanup()
```

**Pattern**: Context manager for automatic lifecycle

```python
class ServiceContext:
    """Context manager for service lifecycle."""

    def __init__(self, service: ServiceProtocol) -> None:
        self.service = service

    def __enter__(self) -> ServiceProtocol:
        self.service.initialize()
        return self.service

    def __exit__(self, *args: Any) -> None:
        self.service.cleanup()

# Usage
with ServiceContext(service) as s:
    s.do_work()  # Automatically initialized/cleaned up
```

---

### Pitfall 4: Importing Concrete Classes

**Problem**:

```python
# WRONG: Importing concrete class
from crackerjack.managers.test_manager import TestManager

def run_tests(manager: TestManager) -> None:
    manager.run_tests(options)

# Tightly coupled to TestManager implementation
```

**Solution**: Import protocols

```python
# CORRECT: Importing protocol
from crackerjack.models.protocols import TestManagerProtocol

def run_tests(manager: TestManagerProtocol) -> None:
    manager.run_tests(options)

# Works with any TestManagerProtocol implementation
```

**Benefits**:
- Can swap implementations without changing calling code
- Easy testing with mocks
- Loose coupling

---

## Best Practices

### DO: Always Import Protocols

```python
# ✅ CORRECT
from crackerjack.models.protocols import ServiceProtocol
```

### DO: Use Protocols in Type Hints

```python
# ✅ CORRECT
def process(service: ServiceProtocol) -> None:
    service.initialize()
```

### DO: Verify Protocol Compliance

```python
# ✅ CORRECT
assert isinstance(obj, ServiceProtocol)
```

### DO: Follow Service Lifecycle

```python
# ✅ CORRECT
service.initialize()
try:
    service.do_work()
finally:
    service.cleanup()
```

### DO: Use Protocol-Based Dependency Injection

```python
# ✅ CORRECT
def __init__(
    self,
    console: ConsoleInterface,
    test_manager: TestManagerProtocol,
):
    self.console = console
    self.test_manager = test_manager
```

---

### DON'T: Import Concrete Classes

```python
# ❌ WRONG
from crackerjack.managers.test_manager import TestManager

# ✅ CORRECT
from crackerjack.models.protocols import TestManagerProtocol
```

### DON'T: Skip Protocol Methods

```python
# ❌ WRONG: Missing method
class BadService:
    def initialize(self) -> None: ...
    # cleanup() is missing!
```

### DON'T: Ignore Type Hints

```python
# ❌ WRONG: No type hint
def setup(service):

# ✅ CORRECT: Protocol type hint
def setup(service: ServiceProtocol):
```

### DON'T: Use Global Singletons

```python
# ❌ WRONG
console = Console()  # Global

# ✅ CORRECT
def __init__(self, console: ConsoleInterface):
    self.console = console
```

---

## Complete Protocol Reference

### Core Protocols (5)

#### ServiceProtocol
**Purpose**: Base lifecycle for all services
**Methods**: 11 (initialize, cleanup, health_check, shutdown, metrics, etc.)
**Inheritance**: Base for 23 service protocols
**Implementation Guide**: See [Core Protocols Explained](#core-protocols-explained)

#### CommandRunner
**Purpose**: Subprocess execution
**Methods**: 1 (execute_command)
**Usage**: Running external commands

#### OptionsProtocol
**Purpose**: CLI options container
**Attributes**: 50+ (commit, test, verbose, etc.)
**Usage**: Passing configuration

#### ConsoleInterface
**Purpose**: Console output abstraction
**Methods**: 3 (print, input, aprint)
**Implementations**: CrackerjackConsole, MockConsole

#### FileSystemInterface
**Purpose**: File operations
**Methods**: 4 (read_file, write_file, exists, mkdir)
**Usage**: File I/O abstraction

---

### Service Protocols (23)

#### TestManagerProtocol
**Purpose**: Test execution and coverage
**Methods**: 4 (run_tests, get_test_failures, validate_test_environment, get_coverage)
**Extends**: ServiceProtocol
**Implementation**: `TestManager` in `/crackerjack/managers/test_manager.py`

#### CoverageRatchetProtocol
**Purpose**: Coverage enforcement (ratchet system)
**Methods**: 7 (get_baseline_coverage, update_baseline_coverage, etc.)
**Extends**: ServiceProtocol

#### SecurityServiceProtocol
**Purpose**: Security checks and validation
**Methods**: 6 (validate_file_safety, check_hardcoded_secrets, etc.)
**Extends**: ServiceProtocol

#### QAAdapterProtocol
**Purpose**: Base for QA tool adapters
**Methods**: 6 (async init, async check, async validate_config, etc.)
**Extends**: None (base protocol)
**Implementations**: 18 adapters (RuffAdapter, MypyAdapter, etc.)

#### [Additional Service Protocols]
See protocol source: `/crackerjack/models/protocols.py`

---

### Quick Reference Card

```
Protocol Import Pattern:
  from crackerjack.models.protocols import [ProtocolName]

Constructor Injection:
  def __init__(self, service: ServiceProtocol) -> None:

Compliance Check:
  assert isinstance(obj, ServiceProtocol)

Lifecycle Pattern:
  service.initialize()
  try:
      service.do_work()
  finally:
      service.cleanup()
```

---

## Getting Help

### Documentation

- Architecture Compliance: See `CLAUDE.md` - "Architecture Compliance Protocol"
- Protocol Quick Reference: `/docs/reference/PROTOCOL_QUICK_REFERENCE.md`
- Protocol Review: `/docs/reference/PROTOCOL_DOCUMENTATION_REVIEW.md`

### Examples

- Protocol Implementation: `TestManager` in `/crackerjack/managers/test_manager.py`
- Protocol Usage: `SessionCoordinator` in `/crackerjack/core/session_coordinator.py`
- Protocol Testing: See `/tests/unit/` for test patterns

### Support

- Questions? Check protocol implementation examples
- Issues? Report protocol documentation gaps
- Contributions? Follow protocol documentation templates

---

**Version**: 1.0
**Status**: ✅ Complete
**Next Review**: 2025-02-28
**Maintainer**: Crackerjack Documentation Team

---

## Appendix A: Protocol Categories Summary

| Category | Count | Purpose |
|----------|-------|---------|
| Core Infrastructure | 5 | Foundational interfaces |
| Service Extensions | 23 | Domain-specific services |
| Quality Assurance | 5 | QA tool orchestration |
| Hook Management | 4 | Hook execution and locking |
| Performance & Monitoring | 8 | Performance tracking |
| Documentation System | 4 | Documentation generation |
| Agent System | 3 | AI agent tracking |
| Git Operations | 2 | Version control |
| Utility Protocols | 7 | Helper utilities |
| **Total** | **61** | **Complete protocol system** |

---

## Appendix B: Protocol Implementation Checklist

When implementing a protocol, ensure:

- [ ] All protocol methods implemented
- [ ] Method signatures match exactly
- [ ] Return types match protocol
- [ ] Type hints added to all methods
- [ ] Docstrings explain behavior
- [ ] `initialize()` is idempotent
- [ ] `cleanup()` is safe to call multiple times
- [ ] `health_check()` returns accurate status
- [ ] Runtime compliance check passes
- [ ] Type checker validates implementation

---

## Appendix C: Protocol Testing Checklist

When testing protocol implementations:

- [ ] Test all protocol methods
- [ ] Test lifecycle (initialize → use → cleanup)
- [ ] Test error conditions
- [ ] Test with mock dependencies
- [ ] Verify protocol compliance with `isinstance()`
- [ ] Test type hints with mypy/pyright
- [ ] Edge cases covered
- [ ] Integration tests pass
- [ ] Documentation examples work

---

**End of Protocol Reference Guide**
