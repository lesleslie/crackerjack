# CLAUDE Code Patterns & Standards

Crackerjack-specific code standards, conventions, and patterns.

> **For architecture overview**, see [CLAUDE_ARCHITECTURE.md](./CLAUDE_ARCHITECTURE.md)
> **For quick commands**, see [CLAUDE_QUICKSTART.md](./CLAUDE_QUICKSTART.md)
> **For working protocols**, see [CLAUDE_PROTOCOLS.md](./CLAUDE_PROTOCOLS.md)

## Core Code Standards

### Quality Rules

- **Complexity ≤15** per function (enforced by mccabe)
- **No hardcoded paths** (use `tempfile` module)
- **No shell=True** in subprocess (security risk)
- **Type annotations required** (Python 3.13+ with `|` unions)
- **Protocol-based DI** (import from `models/protocols.py`)
- **Self-documenting code** (no docstrings, descriptive names)

### Python Version

- **Python 3.13+**: Modern type hints, protocols, pathlib
- Key features used:
  - `|` union syntax (PEP 604)
  - Protocol types (PEP 544)
  - `@runtime_checkable` for runtime protocol checks
  - Type aliases (PEP 695)

### Code Style Philosophy

**DRY/YAGNI/KISS**: Every line is a liability. Optimize for readability.

- **Don't Repeat Yourself**: Extract common patterns
- **You Aren't Gonna Need It**: Avoid speculative flexibility
- **Keep It Simple, Stupid**: Prefer simple over clever

**Readability Counts**: Code should be self-documenting with:

- Clear variable names
- Descriptive function names
- Minimal comments (only for "why", not "what")
- Single responsibility per function

## Anti-Patterns to Avoid

### ❌ NEVER DO These

```python
# ❌ Global singletons (except logger)
console = Console()  # At module level

# ❌ Factory functions without dependency injection
self.tracker = get_agent_tracker()
self.timeout_manager = get_timeout_manager()

# ❌ Direct class imports from crackerjack modules
from crackerjack.managers.test_manager import TestManager
from rich.console import Console as RichConsole

# ❌ Module-level dependency injection
depends.set(MyClass)  # Bypasses constructor injection

# ❌ Hardcoded paths
path = "/tmp/crackerjack"  # Use tempfile or pathlib

# ❌ Shell=True in subprocess
subprocess.run(cmd, shell=True)  # Security risk

# ❌ Placeholders
API_KEY = "YOUR_API_KEY"  # Use environment variables
```

### ✅ ALWAYS DO These

```python
# ✅ Import protocols from models/protocols.py
from crackerjack.models.protocols import Console, TestManagerProtocol


# ✅ Constructor injection
def __init__(
    self,
    console: Console,
    test_manager: TestManagerProtocol,
) -> None:
    self.console = console
    self.test_manager = test_manager


# ✅ Module-level logger
logger = logging.getLogger(__name__)


# ✅ Protocol-based types
def process(
    data: dict[str, Any] | None,
    config: CrackerjackConfig | None,
) -> Result: ...


# ✅ Tempfile for temporary files
import tempfile

with tempfile.NamedTemporaryFile(mode="w") as f:
    ...

# ✅ Environment variables for secrets
import os

api_key = os.getenv("API_KEY")
assert api_key, "API_KEY must be set"
```

## Refactoring Pattern

**Breaking Complex Methods:**

```python
# ❌ BAD: Too complex
def complex_method(self, data: dict) -> bool:
    if not self._validate_input(data):
        return self._handle_invalid_input()
    processed = self._process_data(data)
    return self._save_results(processed)


# ✅ GOOD: Broken into helpers
def process_data(self, data: dict) -> bool:
    if not self._validate_input(data):
        return self._handle_invalid_input()
    processed = self._process_data(data)
    return self._save_results(processed)


def complex_method(self, data: dict) -> bool:
    if not self._validate_input(data):
        return self._handle_invalid_input()
    processed = self.process_data(data)
    return self._save_results(processed)
```

**Complexity Management:**

- Target: ≤15 cyclomatic complexity per function
- Tools: `python -m crackerjack run --comprehensive`
- Strategy: Extract helper methods for repeated logic
- Pattern: Single responsibility per function

## Dependency Injection Patterns

### legacy Framework Usage

**CLI Handlers Only:**

```python
from legacy.depends import depends, Inject
from crackerjack.models.protocols import Console


@depends.inject
def setup_environment(console: Inject[Console] = None, verbose: bool = False) -> None:
    """Protocol-based injection with decorator."""
    if console is None:
        from rich.console import Console

        console = Console()
    console.print("[green]Environment ready[/green]")
```

**Key Points:**

- Use only in CLI handlers
- Use `Inject[Protocol]` for type hints
- Provide `None` defaults for optional dependencies
- NOT for managers, services, or other layers

### Protocol-Based Constructor Injection

**Standard Pattern (All Other Layers):**

```python
from crackerjack.models.protocols import Console, TestManagerProtocol, CacheProtocol


class SessionCoordinator:
    def __init__(
        self,
        console: Console,
        test_manager: TestManagerProtocol,
        cache: CacheProtocol,
    ) -> None:
        """Constructor injection with protocol-based dependencies."""
        self.console = console
        self.test_manager = test_manager
        self.cache = cache
```

**Key Principles:**

- All dependencies via `__init__`
- Protocol types for interface contracts
- Runtime type checking with `@runtime_checkable`
- No factory functions or singletons (except logger)

## Error Handling Patterns

### Retry Logic

```python
from crackerjack.decorators import retry, TimeoutConfig


@retry(max_attempts=3, backoff_factor=2, exceptions=(TimeoutError, ConnectionError))
async def fetch_data(url: str) -> bytes:
    """Retry with exponential backoff."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response.raise_for_status()
            return await response.read()
```

### Timeout Management

```python
from crackerjack.core.timeout_manager import TimeoutManager, TimeoutConfig

# With timeout context
timeout_manager = TimeoutManager(default_timeout=60)

with timeout_manager.timeout("operation"):
    result = await long_running_operation()

# Handle timeout
if not result:
    raise TimeoutError("Operation timed out")
```

### Error Suppression

**For Expected Failures:**

```python
from crackerjack.decorators.error_handling import suppress_expected_error


@suppress_expected_error
def check_git_ignore() -> bool:
    """Don't log if .gitignore not found (expected in some contexts)."""
    try:
        Path(".gitignore").read_text()
    except FileNotFoundError:
        return False
    return True
```

## Testing Patterns

### Synchronous Tests (Preferred)

```python
# ✅ GOOD: Simple synchronous config tests
def test_batch_configuration(self, batched_saver):
    assert batched_saver.max_batch_size == expected_size


# ❌ BAD: Async tests that can hang
@pytest.mark.asyncio
async def test_batch_processing(self, batched_saver):
    await batched_saver.start()  # Can hang indefinitely
```

### Fixture Patterns

```python
import pytest
from crackerjack.services.config import CrackerjackSettings


@pytest.fixture
def settings() -> CrackerjackSettings:
    """Provide settings for tests."""
    return CrackerjackSettings.load()


@pytest.fixture
def temp_project(settings: CrackerjackSettings, tmp_path):
    """Create temporary project directory."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir(exist_ok=True)
    return project_dir, settings
```

## Regex Safety

### ❌ DANGEROUS Raw Regex

```python
# NEVER write raw regex patterns like these
import re

text = re.sub(r"(\w+) - (\w+)", r"\g<1>-\g<2>", text)
text = re.sub(r"pypi-AgEIcHlwaS5vcmcCJGE4M2Y3ZjI", r"\g<token>", text)
```

**Risks:**

- Catastrophic backtracking (ReDoS)
- Incorrect matches (false positives/negatives)
- Hard to maintain and debug

### ✅ SAFE Centralized Patterns

```python
# ALWAYS use validated patterns from registry
from crackerjack.services.regex_patterns import SAFE_PATTERNS

# Token masking (word boundaries prevent false matches)
text = SAFE_PATTERNS["mask_pypi_token"].apply(text)

# Command formatting with validated replacements
text = SAFE_PATTERNS["fix_python_command"].apply(text)

# Test name normalization with iterative application
text = SAFE_PATTERNS["normalize_pytest_names"].apply(text)
```

**Pattern Categories:**

- **Command & Flag Formatting**: Fix spacing, hyphenated names
- **Security Token Masking**: PyPI tokens, GitHub PATs, generic keys
- **Version Management**: Update `pyproject.toml`, coverage requirements
- **Code Quality**: Subprocess security, unsafe replacements
- **Test Optimization**: Assert normalization, job ID validation

**Safety Features:**

- Thread-safe compiled pattern cache
- Input size limits (10MB max)
- Iterative application limits (10 iterations max)
- Comprehensive test cases for each pattern

## Async Patterns

### Async/Await Guidelines

```python
# ✅ GOOD: Explicit async/await
async def process_item(item: dict) -> Result:
    await validate(item)
    processed = await transform(item)
    await save(processed)


# ❌ BAD: Mixing sync/async implicitly
async def process_item(item: dict) -> Result:
    result = validate(item)  # Missing await!
    processed = transform(result)
    save(processed)
```

### Async Context Managers

```python
# ✅ GOOD: Proper async context managers
class AsyncConnection:
    async def __aenter__(self):
        self.conn = await create_connection()
        return self.conn

    async def __aexit__(self, exc_type, exc, tb):
        await self.conn.close()
```

## File I/O Patterns

### Path Handling

```python
# ✅ GOOD: Pathlib for cross-platform paths
from pathlib import Path

config_path = Path("settings") / "config.yaml"
data_dir = Path.home() / ".crackerjack" / "cache"

# ❌ BAD: os.path for platform-specific paths
import os

config_path = os.path.join("settings", "config.yaml")  # Windows issues
```

### Temporary Files

```python
# ✅ GOOD: Automatic cleanup with context managers
import tempfile

with tempfile.NamedTemporaryFile(mode="w", suffix=".json") as f:
    f.write(json_data)
    # Automatically deleted after with block

# ✅ GOOD: Explicit cleanup
temp_file = tempfile.NamedTemporaryFile(mode="w")
try:
    temp_file.write(data)
finally:
    temp_file.close()
    temp_file.unlink()  # Manual cleanup
```

## Performance Patterns

### Caching Strategy

```python
from crackerjack.orchestration.cache.tool_proxy_cache import ToolProxyCache

# Content-based caching with file hash verification
cache = ToolProxyCache(max_size=1000, ttl=3600)

result = cache.get(key, compute_fn, content_hash)
```

**Cache Benefits:**

- 70% cache hit rate in typical workflows
- Content-aware invalidation (only re-run when files actually change)
- Configurable TTL (default 3600s = 1 hour)
- LRU eviction for automatic cleanup

### Parallel Execution

```python
# Dependency-aware parallel execution
async def run_hooks(hooks: list[QATool]) -> dict[str, QAResult]:
    """Run independent hooks in parallel."""
    # Build dependency graph
    # Schedule independent hooks concurrently
    # Wait for all completions
```

**Concurrency Safety:**

- Semaphore control prevents resource exhaustion
- Memory-based limits (2GB per worker minimum)
- Graceful degradation on timeout

## Security Patterns

### Subprocess Safety

```python
# ✅ GOOD: Split command into list (no shell=True)
subprocess.run(["ruff", "check", "."], capture_output=True)

# ❌ BAD: Shell=True allows injection
subprocess.run("ruff check .", shell=True)  # DANGEROUS
```

### Secrets Management

```python
# ✅ GOOD: Environment variables
import os

api_key = os.getenv("PYPI_API_KEY")
if not api_key:
    raise ValueError("PYPI_API_KEY must be set")

# ✅ GOOD: Keyring for secure storage
import keyring

api_key = keyring.get_password("https://upload.pypi.org/legacy/", "__token__")
```

**Security Best Practices:**

- Never commit tokens to version control
- Use `.env` files (add to `.gitignore`)
- Prefer keyring over environment variables
- Rotate tokens regularly
- Use project-scoped tokens when possible

## Naming Conventions

### Module Names

```
# ✅ GOOD: Descriptive, lowercase
from crackerjack.services import file_system, git_operations

# ❌ BAD: Abbreviations, unclear
from crackerjack.services import fs, gitops  # What is fs?
```

### Variable Names

```
# ✅ GOOD: Descriptive
user_authentication_token = "..."
max_retry_attempts = 3
connection_pool_size = 10

# ❌ BAD: Cryptic, abbreviated
uat = "..."
n1 = "..."
x = ...  # Single letter except loop counters
```

### Function Names

```python
# ✅ GOOD: Verb or verb_noun
def validate_input(data: dict) -> bool: ...


def calculate_crc32(data: bytes) -> int: ...


# ❌ BAD: Vague, unclear
def process(data: dict) -> bool: ...


def do_it(x: int) -> int: ...
```

## Documentation Patterns

### Docstring Conventions

**Crackerjack Standard**: No docstrings (self-documenting code)

```python
# ✅ GOOD: Clear names, no docstring needed
def calculate_coverage(passed: int, total: int) -> float:
    """Return test coverage percentage."""
    return (passed / total) * 100


# ❌ AVOIDED: Unnecessary docstrings
def calculate_coverage(passed: int, total: int) -> float:
    """Calculate the percentage of tests that passed.

    Args:
        passed: Number of tests that passed
        total: Total number of tests

    Returns:
        float: Coverage percentage
    """
```

### Comment Guidelines

- **Explain "why" not "what"**: Code should be self-documenting
- **Keep comments current**: Outdated comments worse than none
- **No commented-out code**: Delete don't comment, use git history
- **No TODO/FIXME in code**: Use issue tracker

## Common Mistakes to Avoid

### 1. Ignoring Quality Gates

```python
# ❌ WRONG: Committing without quality checks
git commit -m "WIP"

# ✅ CORRECT: Always run quality first
python -m crackerjack run
git commit -m "Add feature after quality gates pass"
```

### 2. Bypassing Protocol-Based Design

```python
# ❌ WRONG: Direct imports for convenience
from crackerjack.managers.hook_manager import HookManager

# ✅ CORRECT: Use protocol imports
from crackerjack.models.protocols import HookManagerProtocol
```

### 3. Adding Unused Code

```python
# ❌ WRONG: Speculative flexibility
def process_data(
    data: dict,
    future_feature_flag: bool = None,  # YAGNI violation
) -> Result: ...


# ✅ CORRECT: Only what's needed now
def process_data(data: dict) -> Result: ...
```

## Code Review Checklist

Before committing or requesting review, verify:

- [ ] All imports use protocols (no direct class imports)
- [ ] Constructor injection used (no factory functions)
- [ ] Complexity ≤15 for all new functions
- [ ] Type annotations present
- [ ] No hardcoded paths or placeholders
- [ ] Tests added for new functionality
- [ ] Quality gates pass (`python -m crackerjack run --run-tests -c`)
- [ ] No shell=True in subprocess calls
- [ ] Environment variables used for secrets
- [ ] Documentation updated (if applicable)

## Quality Checklist

Before claiming work is complete:

- [ ] Code follows all patterns in this document
- [ ] All tests pass (no skips except documented ones)
- [ ] Coverage not decreased (ratchet system)
- [ ] No complexity warnings
- [ ] No security vulnerabilities detected
- [ ] Dependencies updated in `pyproject.toml`
- [ ] Peer review obtained (if required)
- [ ] Documentation is clear and accurate

`★ Insight ─────────────────────────────────────`
**Quality > Speed**: These patterns prevent technical debt accumulation. Following them from the start is faster than fixing issues later.
`─────────────────────────────────────────────────`
