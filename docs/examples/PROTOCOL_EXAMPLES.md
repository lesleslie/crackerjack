# Protocol Usage Examples

**Version**: 1.0
**Last Updated**: 2025-01-31
**Target Audience**: Developers implementing protocol-based code

---

## Table of Contents

1. [Simple Protocol Implementation](#simple-protocol-implementation)
2. [Protocol Composition](#protocol-composition)
3. [Dependency Injection Patterns](#dependency-injection-patterns)
4. [Testing with Protocol Mocks](#testing-with-protocol-mocks)
5. [Common Patterns](#common-patterns)
6. [Anti-Patterns to Avoid](#anti-patterns-to-avoid)

---

## Simple Protocol Implementation

### Example 1: Basic ServiceProtocol Implementation

```python
from pathlib import Path
from crackerjack.models.protocols import ServiceProtocol, ConsoleInterface


class DataProcessingService:
    """Service that processes data files.

    This service demonstrates the basic ServiceProtocol lifecycle:
    1. Initialize resources (database connections, file handles)
    2. Process data
    3. Clean up resources
    """

    def __init__(self, console: ConsoleInterface, data_dir: Path) -> None:
        """Initialize service with dependencies.

        Args:
            console: Console interface for output.
            data_dir: Directory containing data files.
        """
        self.console = console
        self.data_dir = data_dir
        self._initialized = False
        self._db_connection = None
        self._file_handles = []

    def initialize(self) -> None:
        """Initialize service resources.

        This method is idempotent - can be called multiple times safely.
        """
        if self._initialized:
            return  # Already initialized

        self.console.print("[cyan]Initializing DataProcessingService...[/cyan]")

        # Setup database connection
        self._db_connection = self._connect_database()

        # Open file handles
        self._file_handles = self._open_file_handles()

        self._initialized = True
        self.console.print("[green]DataProcessingService initialized[/green]")

    def cleanup(self) -> None:
        """Clean up all resources.

        Safe to call multiple times. Releases resources in reverse order.
        """
        if not self._initialized:
            return  # Already cleaned up

        self.console.print("[cyan]Cleaning up DataProcessingService...[/cyan]")

        # Close file handles (in reverse order)
        for handle in reversed(self._file_handles):
            handle.close()
        self._file_handles = []

        # Close database connection
        if self._db_connection:
            self._db_connection.close()
            self._db_connection = None

        self._initialized = False
        self.console.print("[green]DataProcessingService cleaned up[/green]")

    def health_check(self) -> bool:
        """Check if service is healthy.

        Returns:
            True if initialized and all resources are available.
        """
        if not self._initialized:
            return False

        # Check database connection
        if not self._db_connection or not self._db_connection.is_open():
            return False

        # Check file handles
        if not all(handle.closed == False for handle in self._file_handles):
            return False

        return True

    # Additional ServiceProtocol methods
    def shutdown(self) -> None:
        """Graceful shutdown."""
        self.cleanup()

    def metrics(self) -> dict[str, t.Any]:
        """Get service metrics."""
        return {
            "initialized": self._initialized,
            "open_files": len(self._file_handles),
            "db_connected": self._db_connection is not None,
        }

    def is_healthy(self) -> bool:
        """Alias for health_check()."""
        return self.health_check()

    # Service-specific methods
    def process_file(self, file_path: Path) -> dict[str, t.Any]:
        """Process a data file.

        Args:
            file_path: Path to file to process.

        Returns:
            Processing results.

        Raises:
            RuntimeError: If service not initialized.
        """
        if not self._initialized:
            raise RuntimeError("Service not initialized. Call initialize() first.")

        # Process file
        results = {"file": str(file_path), "records_processed": 0}
        # ... processing logic ...

        return results

    def _connect_database(self) -> t.Any:
        """Connect to database (private helper)."""
        # Implementation here
        pass

    def _open_file_handles(self) -> list[t.Any]:
        """Open file handles (private helper)."""
        # Implementation here
        pass
```

### Usage Example

```python
from crackerjack.models.protocols import ServiceProtocol
from rich.console import Console

def use_service() -> None:
    """Demonstrate proper service lifecycle usage."""
    # Create service
    console = Console()
    service = DataProcessingService(console, Path("/data"))

    # Use service with proper lifecycle
    try:
        service.initialize()
        assert service.health_check(), "Service should be healthy"

        # Use service
        results = service.process_file(Path("/data/file.csv"))
        print(f"Processed: {results}")

    finally:
        service.cleanup()

# Correct usage pattern with context manager
class ServiceContext:
    """Context manager for automatic service lifecycle."""

    def __init__(self, service: ServiceProtocol) -> None:
        self.service = service

    def __enter__(self) -> ServiceProtocol:
        self.service.initialize()
        return self.service

    def __exit__(self, *args: t.Any) -> None:
        self.service.cleanup()

# Usage
def use_service_with_context() -> None:
    """Use service with context manager."""
    console = Console()
    service = DataProcessingService(console, Path("/data"))

    with ServiceContext(service) as s:
        results = s.process_file(Path("/data/file.csv"))
        print(f"Processed: {results}")
    # Automatically cleaned up
```

---

## Protocol Composition

### Example 2: Implementing Multiple Protocols

```python
from crackerjack.models.protocols import (
    ServiceProtocol,
    TestManagerProtocol,
    CoverageRatchetProtocol,
    OptionsProtocol,
)


class ComprehensiveTestService:
    """Implements both TestManagerProtocol and CoverageRatchetProtocol.

    This demonstrates protocol composition - a single class can implement
    multiple protocols by providing all required methods.
    """

    def __init__(self, console: ConsoleInterface) -> None:
        self.console = console
        self._initialized = False
        self._baseline_coverage = 0.0

    # ServiceProtocol methods
    def initialize(self) -> None:
        """Initialize service."""
        if not self._initialized:
            self._load_baseline()
            self._initialized = True

    def cleanup(self) -> None:
        """Clean up service."""
        if self._initialized:
            self._save_baseline()
            self._initialized = False

    def health_check(self) -> bool:
        """Check health."""
        return self._initialized

    # TestManagerProtocol methods
    def run_tests(self, options: OptionsProtocol) -> bool:
        """Run test suite.

        Args:
            options: Test options.

        Returns:
            True if all tests pass.
        """
        self.console.print("[cyan]Running tests...[/cyan]")
        # ... test execution logic ...
        return True  # or False if tests fail

    def get_test_failures(self) -> list[str]:
        """Get failed test names."""
        return []  # Return list of failed tests

    def validate_test_environment(self) -> bool:
        """Validate test environment."""
        return True  # or False if invalid

    def get_coverage(self) -> dict[str, t.Any]:
        """Get coverage metrics."""
        return {"percent": 85.0, "covered_lines": 850, "total_lines": 1000}

    # CoverageRatchetProtocol methods
    def get_baseline_coverage(self) -> float:
        """Get baseline coverage."""
        return self._baseline_coverage

    def update_baseline_coverage(self, new_coverage: float) -> bool:
        """Update baseline (only if higher)."""
        if new_coverage > self._baseline_coverage:
            self._baseline_coverage = new_coverage
            return True
        return False

    def is_coverage_regression(self, current_coverage: float) -> bool:
        """Check for coverage regression."""
        return current_coverage < self._baseline_coverage

    def get_coverage_improvement_needed(self) -> float:
        """Get coverage needed to reach baseline."""
        return max(0, self._baseline_coverage - self.get_coverage()["percent"])

    def get_status_report(self) -> dict[str, t.Any]:
        """Get ratchet status."""
        current = self.get_coverage()["percent"]
        return {
            "baseline": self._baseline_coverage,
            "current": current,
            "regression": self.is_coverage_regression(current),
        }

    def get_coverage_report(self) -> str | None:
        """Get detailed coverage report."""
        return f"Coverage: {self.get_coverage()['percent']}%"

    def check_and_update_coverage(self) -> dict[str, t.Any]:
        """Check and update coverage if improved."""
        coverage = self.get_coverage()["percent"]
        updated = self.update_baseline_coverage(coverage)
        return {
            "coverage": coverage,
            "baseline": self._baseline_coverage,
            "updated": updated,
        }

    # Private helpers
    def _load_baseline(self) -> None:
        """Load baseline from storage."""
        # Implementation here
        pass

    def _save_baseline(self) -> None:
        """Save baseline to storage."""
        # Implementation here
        pass
```

### Verifying Protocol Compliance

```python
from crackerjack.models.protocols import (
    ServiceProtocol,
    TestManagerProtocol,
    CoverageRatchetProtocol,
)

def verify_protocols() -> None:
    """Verify that service implements all expected protocols."""
    service = ComprehensiveTestService(console)

    # Check all protocols
    assert isinstance(service, ServiceProtocol)
    assert isinstance(service, TestManagerProtocol)
    assert isinstance(service, CoverageRatchetProtocol)

    print("✅ Service implements all expected protocols")

    # Use service
    service.initialize()
    try:
        # Use as TestManagerProtocol
        success = service.run_tests(options)
        failures = service.get_test_failures()

        # Use as CoverageRatchetProtocol
        baseline = service.get_baseline_coverage()
        is_regression = service.is_coverage_regression(80.0)

    finally:
        service.cleanup()
```

---

## Dependency Injection Patterns

### Example 3: Constructor Injection

```python
from crackerjack.models.protocols import (
    ConsoleInterface,
    TestManagerProtocol,
    FileSystemInterface,
    GitInterface,
)


class SessionCoordinator:
    """Coordinates a quality check session.

    This class demonstrates proper dependency injection using protocols.
    All dependencies are injected via the constructor, making the class
    easy to test and maintain.
    """

    def __init__(
        self,
        console: ConsoleInterface,
        test_manager: TestManagerProtocol,
        filesystem: FileSystemInterface,
        git: GitInterface,
    ) -> None:
        """Initialize coordinator with dependencies.

        Args:
            console: Console interface for output.
            test_manager: Test manager for running tests.
            filesystem: File system interface for file operations.
            git: Git interface for version control operations.
        """
        self.console = console
        self.test_manager = test_manager
        self.filesystem = filesystem
        self.git = git

    def run_session(self, options: OptionsProtocol) -> bool:
        """Run complete quality check session.

        Args:
            options: Session options.

        Returns:
            True if session succeeded, False otherwise.
        """
        self.console.print("[cyan]Starting quality check session...[/cyan]")

        # Run tests
        if options.run_tests:
            success = self.test_manager.run_tests(options)
            if not success:
                failures = self.test_manager.get_test_failures()
                self.console.print(f"[red]Tests failed:[/red] {failures}")
                return False

        # Check git status
        if self.git.is_git_repo():
            changed_files = self.git.get_changed_files()
            self.console.print(f"Changed files: {len(changed_files)}")

        return True
```

### Using with Real Implementations

```python
from rich.console import Console
from crackerjack.services.test_manager import TestManager
from crackerjack.services.git_service import GitService
from crackerjack.services.file_system import FileSystemService

def create_real_coordinator() -> SessionCoordinator:
    """Create coordinator with real implementations."""
    console = Console()
    test_manager = TestManager(console)
    filesystem = FileSystemService()
    git = GitService()

    return SessionCoordinator(console, test_manager, filesystem, git)

# Usage
coordinator = create_real_coordinator()
success = coordinator.run_session(options)
```

### Using with Mock Implementations (Testing)

```python
class MockTestManager:
    """Mock TestManagerProtocol for testing."""

    def __init__(self) -> None:
        self.tests_run = False
        self.should_fail = False

    def run_tests(self, options: OptionsProtocol) -> bool:
        self.tests_run = True
        return not self.should_fail

    def get_test_failures(self) -> list[str]:
        return ["test1", "test2"] if self.should_fail else []

    # ... other TestManagerProtocol methods ...


class MockFileSystem:
    """Mock FileSystemInterface for testing."""

    def __init__(self) -> None:
        self.files = {}

    def write_file(self, path: str | Path, content: str) -> None:
        self.files[str(path)] = content

    def read_file(self, path: str | Path) -> str:
        return self.files.get(str(path), "")

    def exists(self, path: str | Path) -> bool:
        return str(path) in self.files

    def mkdir(self, path: str | Path, parents: bool = False) -> None:
        self.files[str(path)] = ""  # Create directory marker


class MockGit:
    """Mock GitInterface for testing."""

    def __init__(self) -> None:
        self.is_repo = True
        self.changed_files = []

    def is_git_repo(self) -> bool:
        return self.is_repo

    def get_changed_files(self) -> list[str]:
        return self.changed_files

    # ... other GitInterface methods ...


def test_session_coordinator() -> None:
    """Test SessionCoordinator with mocks."""
    # Create mocks
    console = Console()
    test_manager = MockTestManager()
    filesystem = MockFileSystem()
    git = MockGit()

    # Create coordinator with mocks
    coordinator = SessionCoordinator(console, test_manager, filesystem, git)

    # Test successful session
    options = OptionsProtocol()
    options.run_tests = True

    success = coordinator.run_session(options)
    assert success, "Session should succeed"
    assert test_manager.tests_run, "Tests should be run"

    # Test failed session
    test_manager.should_fail = True
    success = coordinator.run_session(options)
    assert not success, "Session should fail when tests fail"
```

### Optional Dependencies Pattern

```python
from typing import t


class SessionCoordinatorWithOptionalDeps:
    """Coordinator with optional dependencies.

    Demonstrates handling optional protocol-based dependencies.
    """

    def __init__(
        self,
        console: ConsoleInterface,
        test_manager: TestManagerProtocol,
        filesystem: FileSystemInterface | None = None,
        git: GitInterface | None = None,
    ) -> None:
        """Initialize with required and optional dependencies.

        Args:
            console: Required console interface.
            test_manager: Required test manager.
            filesystem: Optional file system interface.
            git: Optional git interface.
        """
        self.console = console
        self.test_manager = test_manager
        self.filesystem = filesystem
        self.git = git

    def run_session(self, options: OptionsProtocol) -> bool:
        """Run session with optional features."""
        # Required: always run tests
        success = self.test_manager.run_tests(options)
        if not success:
            return False

        # Optional: use git if available
        if self.git and self.git.is_git_repo():
            changed_files = self.git.get_changed_files()
            self.console.print(f"Changed files: {len(changed_files)}")
        else:
            self.console.print("[yellow]Git not available[/yellow]")

        # Optional: use filesystem if available
        if self.filesystem:
            report_path = Path("/tmp/report.txt")
            self.filesystem.write_file(report_path, "Session completed")

        return True
```

---

## Testing with Protocol Mocks

### Example 4: Creating Lightweight Mocks

```python
from crackerjack.models.protocols import ServiceProtocol, ConsoleInterface


class SimpleServiceMock:
    """Minimal ServiceProtocol mock for testing.

    This mock provides just enough functionality for testing
    without requiring a full implementation.
    """

    def __init__(self) -> None:
        self.initialize_count = 0
        self.cleanup_count = 0
        self._healthy = True

    def initialize(self) -> None:
        self.initialize_count += 1
        self._healthy = True

    def cleanup(self) -> None:
        self.cleanup_count += 1
        self._healthy = False

    def health_check(self) -> bool:
        return self._healthy

    # Minimal implementations of other ServiceProtocol methods
    def shutdown(self) -> None:
        self.cleanup()

    def metrics(self) -> dict[str, t.Any]:
        return {"initialize_count": self.initialize_count}

    def is_healthy(self) -> bool:
        return self._healthy

    def register_resource(self, resource: t.Any) -> None:
        pass

    def cleanup_resource(self, resource: t.Any) -> None:
        pass

    def record_error(self, error: Exception) -> None:
        pass

    def increment_requests(self) -> None:
        pass

    def get_custom_metric(self, name: str) -> t.Any:
        return None

    def set_custom_metric(self, name: str, value: t.Any) -> None:
        pass


class ConsoleMock:
    """Mock ConsoleInterface for testing."""

    def __init__(self) -> None:
        self.outputs = []
        self.inputs = []

    def print(self, *args: t.Any, **kwargs: t.Any) -> None:
        self.outputs.append(str(args))

    def input(self, prompt: str = "") -> str:
        self.inputs.append(prompt)
        return "test_input"


def test_service_lifecycle() -> None:
    """Test service lifecycle with mock."""
    service = SimpleServiceMock()

    # Test initialization
    assert not service.health_check()
    service.initialize()
    assert service.health_check()
    assert service.initialize_count == 1

    # Test cleanup
    service.cleanup()
    assert not service.health_check()
    assert service.cleanup_count == 1

    # Test idempotence
    service.initialize()
    service.initialize()
    assert service.initialize_count == 2  # Still counts calls
    assert service.health_check()


def test_console_mock() -> None:
    """Test console mock."""
    console = ConsoleMock()

    console.print("Hello", "World")
    assert len(console.outputs) == 1
    assert "Hello" in console.outputs[0]

    result = console.input("Enter value: ")
    assert result == "test_input"
    assert len(console.inputs) == 1
    assert console.inputs[0] == "Enter value: "
```

### Using pytest Fixture with Protocol Mocks

```python
import pytest
from crackerjack.models.protocols import ServiceProtocol


@pytest.fixture
def mock_service() -> SimpleServiceMock:
    """Pytest fixture providing mock service."""
    service = SimpleServiceMock()
    service.initialize()
    yield service
    service.cleanup()


@pytest.fixture
def mock_console() -> ConsoleMock:
    """Pytest fixture providing mock console."""
    return ConsoleMock()


def test_with_fixtures(mock_service: ServiceProtocol, mock_console: ConsoleMock) -> None:
    """Test using pytest fixtures."""
    # Service is already initialized
    assert mock_service.health_check()

    # Use console
    mock_console.print("Test message")
    assert len(mock_console.outputs) == 1

    # Cleanup happens automatically
```

---

## Common Patterns

### Pattern 1: Service Lifecycle Context Manager

```python
from contextlib import contextmanager
from crackerjack.models.protocols import ServiceProtocol


@contextmanager
def managed_service(service: ServiceProtocol):
    """Context manager for automatic service lifecycle.

    Args:
        service: Service to manage.

    Yields:
        Initialized service.

    Example:
        with managed_service(service) as s:
            s.do_work()
        # Automatically cleaned up
    """
    service.initialize()
    try:
        yield service
    finally:
        service.cleanup()


# Usage
def use_context_manager() -> None:
    """Use service with context manager."""
    service = DataProcessingService(console, Path("/data"))

    with managed_service(service) as s:
        results = s.process_file(Path("/data/file.csv"))
        print(f"Results: {results}")

    # Service automatically cleaned up
```

### Pattern 2: Adapter Pattern

```python
from crackerjack.models.protocols import QAAdapterProtocol, HookDefinition


class ToolAdapter:
    """Base adapter class for QA tools.

    Implements the common adapter pattern used by all QA tools.
    """

    def __init__(self, name: str, settings: t.Any | None = None) -> None:
        self.name = name
        self.settings = settings

    # QAAdapterProtocol implementation
    async def init(self) -> None:
        """Initialize adapter."""
        if self.settings:
            self._load_config()

    async def check(
        self,
        files: list[Path] | None = None,
        config: t.Any | None = None,
    ) -> t.Any:
        """Run QA check."""
        # Default implementation
        tool_config = config or self.settings
        return await self._run_tool(files, tool_config)

    async def validate_config(self, config: t.Any) -> bool:
        """Validate configuration."""
        return config is not None

    def get_default_config(self) -> t.Any:
        """Get default configuration."""
        return {"enabled": True}

    async def health_check(self) -> dict[str, t.Any]:
        """Check tool health."""
        return {"available": True, "version": "1.0.0"}

    @property
    def adapter_name(self) -> str:
        """Get adapter name."""
        return self.name

    @property
    def module_id(self) -> t.Any:
        """Get module identifier."""
        return self.name

    # Abstract methods (must be implemented by subclasses)
    async def _run_tool(self, files: list[Path] | None, config: t.Any) -> t.Any:
        """Run the tool (must be implemented by subclass)."""
        raise NotImplementedError

    def _load_config(self) -> None:
        """Load configuration (optional implementation)."""
        pass


class RuffAdapter(ToolAdapter):
    """Adapter for Ruff linter/formatter."""

    def __init__(self, settings: t.Any | None = None) -> None:
        super().__init__("ruff", settings)

    async def _run_tool(self, files: list[Path] | None, config: t.Any) -> t.Any:
        """Run ruff on files."""
        cmd = ["ruff", "check"]
        if files:
            cmd.extend([str(f) for f in files])

        # Run command and return results
        # ... implementation here ...
        return {"success": True, "issues": []}


class MypyAdapter(ToolAdapter):
    """Adapter for MyPy type checker."""

    def __init__(self, settings: t.Any | None = None) -> None:
        super().__init__("mypy", settings)

    async def _run_tool(self, files: list[Path] | None, config: t.Any) -> t.Any:
        """Run mypy on files."""
        cmd = ["mypy"]
        if files:
            cmd.extend([str(f) for f in files])

        # Run command and return results
        # ... implementation here ...
        return {"success": True, "errors": []}
```

### Pattern 3: Manager Pattern

```python
from crackerjack.models.protocols import (
    HookManager,
    OptionsProtocol,
    ConsoleInterface,
)


class HookManagerImpl:
    """Implementation of HookManager protocol.

    Manages quality check hooks with configuration and execution.
    """

    def __init__(
        self,
        console: ConsoleInterface,
        config_path: Path | None = None,
    ) -> None:
        """Initialize hook manager.

        Args:
            console: Console interface for output.
            config_path: Path to hook configuration file.
        """
        self.console = console
        self.config_path = config_path
        self._hooks: list[t.Any] = []
        self._progress_callback = None
        self._progress_start_callback = None

    # HookManager protocol methods
    def run_fast_hooks(self) -> list[t.Any]:
        """Run fast hooks (~5 seconds)."""
        self.console.print("[cyan]Running fast hooks...[/cyan]")
        results = []

        for hook in self._get_fast_hooks():
            result = self._run_hook(hook)
            results.append(result)

            if self._progress_callback:
                self._progress_callback(len(results), len(self._get_fast_hooks()))

        return results

    def run_comprehensive_hooks(self) -> list[t.Any]:
        """Run comprehensive hooks (~30 seconds)."""
        self.console.print("[cyan]Running comprehensive hooks...[/cyan]")
        results = []

        for hook in self._get_comprehensive_hooks():
            result = self._run_hook(hook)
            results.append(result)

        return results

    def install_hooks(self) -> bool:
        """Install hooks for project."""
        self.console.print("[cyan]Installing hooks...[/cyan]")
        # ... installation logic ...
        return True

    def set_config_path(self, path: str | t.Any) -> None:
        """Set hook configuration path."""
        self.config_path = Path(path)

    def get_hook_summary(
        self,
        results: t.Any,
        elapsed_time: float | None = None,
    ) -> t.Any:
        """Get hook execution summary."""
        return HookSummary(results, elapsed_time)

    # Private helpers
    def _get_fast_hooks(self) -> list[t.Any]:
        """Get fast hook list."""
        return [h for h in self._hooks if h.category == "fast"]

    def _get_comprehensive_hooks(self) -> list[t.Any]:
        """Get comprehensive hook list."""
        return [h for h in self._hooks if h.category == "comprehensive"]

    def _run_hook(self, hook: t.Any) -> t.Any:
        """Run single hook."""
        # ... hook execution logic ...
        return HookResult(hook.name, success=True)
```

### Pattern 4: Agent Pattern

```python
from crackerjack.models.protocols import AgentCoordinatorProtocol, ServiceProtocol


class AgentCoordinatorImpl:
    """Coordinates AI agents for issue resolution.

    Implements AgentCoordinatorProtocol to manage AI-based fixing.
    """

    def __init__(
        self,
        console: ConsoleInterface,
        debug_service: ServiceProtocol,
    ) -> None:
        """Initialize coordinator.

        Args:
            console: Console interface.
            debug_service: Debug service for logging.
        """
        self.console = console
        self.debug_service = debug_service
        self._agents: dict[str, t.Any] = {}
        self._proactive_mode = False

    # AgentCoordinatorProtocol methods
    def initialize_agents(self) -> None:
        """Initialize all agents."""
        self.console.print("[cyan]Initializing agents...[/cyan]")
        self._agents = {
            "refactoring": RefactoringAgent(),
            "security": SecurityAgent(),
            "formatting": FormattingAgent(),
        }

    async def handle_issues(self, issues: list[t.Any]) -> t.Any:
        """Handle issues with AI agents."""
        results = []

        for issue in issues:
            agent = self._select_agent(issue)
            if agent:
                result = await agent.fix(issue)
                results.append(result)

        return AgentResult(results)

    async def handle_issues_proactively(self, issues: list[t.Any]) -> t.Any:
        """Handle issues proactively (prevention mode)."""
        if not self._proactive_mode:
            return AgentResult([])

        return await self.handle_issues(issues)

    def get_agent_capabilities(self) -> dict[str, dict[str, t.Any]]:
        """Get agent capabilities."""
        return {
            name: {"confidence": agent.confidence, "category": agent.category}
            for name, agent in self._agents.items()
        }

    def set_proactive_mode(self, enabled: bool) -> None:
        """Enable/disable proactive mode."""
        self._proactive_mode = enabled

    # Private helpers
    def _select_agent(self, issue: t.Any) -> t.Any | None:
        """Select appropriate agent for issue."""
        issue_type = issue.get("type", "")
        return self._agents.get(issue_type)
```

---

## Anti-Patterns to Avoid

### ❌ Anti-Pattern 1: Direct Class Imports

```python
# WRONG: Importing concrete class
from crackerjack.managers.test_manager import TestManager

def run_tests(manager: TestManager) -> None:
    manager.run_tests(options)

# Problems:
# - Tightly coupled to TestManager implementation
# - Hard to test (cannot use mocks easily)
# - Cannot swap implementations


# CORRECT: Importing protocol
from crackerjack.models.protocols import TestManagerProtocol

def run_tests(manager: TestManagerProtocol) -> None:
    manager.run_tests(options)

# Benefits:
# - Loose coupling (any TestManagerProtocol implementation works)
# - Easy to test (can inject mocks)
# - Can swap implementations without changing code
```

### ❌ Anti-Pattern 2: Global Singletons

```python
# WRONG: Global singleton
console = Console()  # Global!

def print_message(msg: str) -> None:
    console.print(msg)

# Problems:
# - Hard to test (cannot inject mock console)
# - Hidden dependencies
# - Thread safety issues


# CORRECT: Protocol-based dependency injection
def print_message(msg: str, console: ConsoleInterface) -> None:
    console.print(msg)

# Or with class
class MessagePrinter:
    def __init__(self, console: ConsoleInterface) -> None:
        self.console = console

    def print(self, msg: str) -> None:
        self.console.print(msg)
```

### ❌ Anti-Pattern 3: Factory Functions Without DI

```python
# WRONG: Factory function creating concrete class
def get_test_manager() -> TestManager:
    return TestManager()

def run_tests() -> None:
    manager = get_test_manager()  # Hidden dependency
    manager.run_tests(options)

# Problems:
# - Hidden dependency on TestManager
# - Hard to test
# - Tight coupling


# CORRECT: Constructor injection or service locator
class ServiceContainer:
    """Container for service instances."""

    def __init__(self) -> None:
        self._test_manager: TestManagerProtocol | None = None

    def get_test_manager(self) -> TestManagerProtocol:
        if self._test_manager is None:
            # Create with injected dependencies
            console = Console()
            self._test_manager = TestManager(console)
        return self._test_manager


# Or even better: inject everything via constructor
def run_tests(test_manager: TestManagerProtocol) -> None:
    test_manager.run_tests(options)
```

### ❌ Anti-Pattern 4: Breaking Protocol Contract

```python
# WRONG: Changing method signature
class BrokenTestManager:
    def run_tests(self, options: OptionsProtocol, extra_param: str) -> bool:
        # Extra parameter breaks protocol contract!
        return True

# Problems:
# - Type checker will complain
# - Protocol contract violated
# - Calling code will break


# CORRECT: Match exact protocol signature
class GoodTestManager:
    def run_tests(self, options: OptionsProtocol) -> bool:
        # Exact protocol signature
        return True
```

### ❌ Anti-Pattern 5: Not Following Lifecycle

```python
# WRONG: Using service without initialization
service = MyService()
result = service.do_work()  # May fail!

# Problems:
# - Service not initialized
# - Resources not set up
# - Unpredictable behavior


# CORRECT: Always follow lifecycle
service = MyService()
service.initialize()
try:
    result = service.do_work()
finally:
    service.cleanup()
```

---

**End of Protocol Usage Examples**

**Version**: 1.0
**Status**: ✅ Complete
**Last Updated**: 2025-01-31
**Maintainer**: Crackerjack Documentation Team

---

## Additional Resources

- **Protocol Reference Guide**: `/docs/reference/PROTOCOL_REFERENCE_GUIDE.md`
- **Architecture Documentation**: `CLAUDE.md` - "Architecture Compliance Protocol"
- **Protocol Quick Reference**: `/docs/reference/PROTOCOL_QUICK_REFERENCE.md`
- **Implementation Examples**: See `/crackerjack/managers/` and `/crackerjack/services/`
