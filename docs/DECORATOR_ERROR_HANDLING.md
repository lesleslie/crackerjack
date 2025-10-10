# Decorator-Based Error Handling

Crackerjack provides a comprehensive set of composable decorators for error handling, retry logic, timeout enforcement, and graceful degradation. All decorators support both synchronous and asynchronous functions and integrate seamlessly with Crackerjack's error infrastructure.

## Quick Start

```python
from crackerjack.decorators import retry, with_timeout, handle_errors

@retry(max_attempts=3)
@with_timeout(seconds=30)
async def fetch_data(url: str) -> dict:
    # Automatically retries on failure, times out after 30s
    return await client.get(url)
```

## Available Decorators

### @retry

Automatically retry operations with exponential backoff.

**Signature:**
```python
@retry(
    max_attempts: int = 3,
    backoff: float = 2.0,
    max_delay: float = 60.0,
    exceptions: tuple[type[Exception], ...] | None = None,
    on_retry: Callable[[Exception, int], None] | None = None,
    console: Console | None = None,
)
```

**Parameters:**
- `max_attempts`: Maximum retry attempts (default: 3)
- `backoff`: Exponential backoff multiplier (default: 2.0)
- `max_delay`: Maximum delay between retries in seconds (default: 60.0)
- `exceptions`: Specific exception types to retry (None = all exceptions)
- `on_retry`: Optional callback on each retry
- `console`: Optional Rich Console for output

**Example:**
```python
from crackerjack.errors import NetworkError

@retry(max_attempts=5, backoff=2.0, exceptions=[NetworkError])
async def fetch_package_info(package: str) -> dict:
    # Retries up to 5 times on NetworkError
    # Delays: 2s, 4s, 8s, 16s
    return await pypi_client.get(package)
```

**Behavior:**
- Uses exponential backoff: `delay = min(backoff ** attempt, max_delay)`
- Shows progress via Rich console
- Re-raises exception after final attempt
- Works with both sync and async functions

### @with_timeout

Enforce execution timeout with automatic cancellation.

**Signature:**
```python
@with_timeout(
    seconds: float,
    error_message: str | None = None,
)
```

**Parameters:**
- `seconds`: Timeout duration
- `error_message`: Optional custom error message

**Example:**
```python
@with_timeout(seconds=30, error_message="Database query timed out")
async def slow_query() -> list:
    return await db.execute_complex_query()
```

**Raises:**
- `CrackerjackTimeoutError` on timeout

**Notes:**
- Async functions use `asyncio.wait_for` for clean cancellation
- Sync functions use `signal.alarm` (Unix only)
- Provides recovery suggestions in error

### @handle_errors

Centralized error handling with transformation and fallback.

**Signature:**
```python
@handle_errors(
    error_types: list[type[Exception]] | None = None,
    fallback: Any = None,
    transform_to: type[CrackerjackError] | None = None,
    console: Console | None = None,
    suppress: bool = False,
)
```

**Parameters:**
- `error_types`: Exception types to handle (None = all)
- `fallback`: Fallback value or callable
- `transform_to`: Transform to CrackerjackError subclass
- `console`: Optional Rich Console
- `suppress`: Suppress errors (no re-raise)

**Example:**
```python
from crackerjack.errors import FileError

@handle_errors(
    error_types=[OSError, PermissionError],
    transform_to=FileError,
    fallback={}
)
def load_config(path: Path) -> dict:
    # OS errors transformed to FileError
    # Returns {} on error
    with path.open() as f:
        return json.load(f)
```

**Example with callable fallback:**
```python
@handle_errors(fallback=lambda: {"default": True})
def get_settings() -> dict:
    # Returns {"default": True} on error
    return load_settings()
```

### @log_errors

Log errors with context before re-raising.

**Signature:**
```python
@log_errors(
    logger: Any | None = None,
    level: str = "error",
    include_traceback: bool = True,
    console: Console | None = None,
)
```

**Parameters:**
- `logger`: Logger instance (uses console if None)
- `level`: Log level (error, warning, info, debug)
- `include_traceback`: Include full traceback
- `console`: Optional Rich Console

**Example:**
```python
import logging
logger = logging.getLogger(__name__)

@log_errors(logger=logger, level="error", include_traceback=True)
async def critical_operation() -> bool:
    # Errors logged with full context before re-raising
    return await perform_operation()
```

**Logged Context:**
- Function name and module
- Error type and message
- Full exception chain
- Custom extra fields

### @graceful_degradation

Gracefully handle failures with fallback values.

**Signature:**
```python
@graceful_degradation(
    fallback_value: Any = None,
    warn: bool = True,
    console: Console | None = None,
)
```

**Parameters:**
- `fallback_value`: Value to return on error (can be callable)
- `warn`: Show warning on fallback (default: True)
- `console`: Optional Rich Console

**Example:**
```python
@graceful_degradation(fallback_value=[], warn=True)
def load_optional_plugins(plugin_dir: Path) -> list[str]:
    # Returns [] on error with warning
    # App continues running
    return [p.name for p in plugin_dir.glob("*.py")]
```

**Use Cases:**
- Optional features
- Non-critical operations
- Degraded functionality acceptable

### @validate_args

Validate function arguments before execution.

**Signature:**
```python
@validate_args(
    validators: dict[str, Callable | list[Callable]] | None = None,
    type_check: bool = True,
    allow_none: set[str] | None = None,
)
```

**Parameters:**
- `validators`: Dict of parameter name -> validator function(s)
- `type_check`: Enable type checking from annotations
- `allow_none`: Parameters that can be None

**Example:**
```python
@validate_args(
    validators={
        "email": [
            lambda e: "@" in e,
            lambda e: len(e) > 5,
        ],
        "age": lambda a: 0 < a < 150,
    },
    type_check=True,
)
def register_user(email: str, age: int) -> bool:
    # Email must contain @ and be > 5 chars
    # Age must be 0 < age < 150
    # Types validated automatically
    return True
```

**Raises:**
- `ValidationError` with detailed context

**Features:**
- Multiple validators per parameter
- Automatic type checking from annotations
- Detailed error messages

### @cache_errors

Detect and cache error patterns for analysis.

**Signature:**
```python
@cache_errors(
    cache_dir: Path | None = None,
    error_type: str | None = None,
    auto_analyze: bool = True,
)
```

**Parameters:**
- `cache_dir`: Cache directory (default: ~/.cache/crackerjack-mcp)
- `error_type`: Override error type classification
- `auto_analyze`: Auto-analyze errors for patterns

**Example:**
```python
@cache_errors(error_type="lint", auto_analyze=True)
async def run_linter(files: list[Path]) -> dict:
    # Error patterns cached for auto-fix suggestions
    result = subprocess.run(["ruff", "check", *files])
    return {"success": result.returncode == 0}
```

**Integration:**
- Uses Crackerjack's `ErrorCache`
- Tracks error frequency
- Enables AI auto-fix suggestions

## Decorator Composition

Decorators can be stacked for complex error handling:

```python
@with_timeout(seconds=60)
@retry(max_attempts=3, backoff=2.0)
@log_errors(logger=my_logger)
@handle_errors(fallback={"success": False})
async def robust_operation() -> dict:
    # 1. Timeout after 60s
    # 2. Retry up to 3 times
    # 3. Log all errors
    # 4. Fallback to {"success": False}
    return await perform_operation()
```

**Order Matters:**
- Decorators execute from bottom to top
- Outermost decorator gets first chance to handle
- Inner decorators execute on success of outer

**Recommended Stacks:**

**For network operations:**
```python
@with_timeout(seconds=30)
@retry(max_attempts=5, exceptions=[NetworkError])
@log_errors()
```

**For critical operations:**
```python
@log_errors()
@validate_args(validators={...})
@handle_errors(transform_to=ExecutionError)
```

**For optional features:**
```python
@graceful_degradation(fallback_value=[])
@with_timeout(seconds=5)
```

## Integration with ErrorHandlingMixin

Decorators complement the existing `ErrorHandlingMixin`:

```python
from crackerjack.mixins.error_handling import ErrorHandlingMixin
from crackerjack.decorators import retry, log_errors

class QualityManager(ErrorHandlingMixin):
    def __init__(self):
        super().__init__()
        # Has self.console and self.logger from mixin

    @retry(max_attempts=3)
    @log_errors()
    async def run_hooks(self) -> bool:
        # Uses decorators for retry/logging
        # Can still use mixin methods:
        # self.handle_subprocess_error(...)
        # self.handle_file_operation_error(...)
        pass
```

**When to Use Each:**

**Use Decorators:**
- Function-level error handling
- Retry logic
- Timeout enforcement
- Argument validation
- Composable error handling

**Use Mixin:**
- Class-level error handling utilities
- Common error logging patterns
- Tool validation
- Shared error handling across methods

## Best Practices

### 1. Choose the Right Decorator

```python
# Network operations - retry
@retry(max_attempts=3, exceptions=[NetworkError])
async def fetch_data(): ...

# Long operations - timeout
@with_timeout(seconds=30)
async def slow_query(): ...

# Optional features - graceful degradation
@graceful_degradation(fallback_value=[])
def load_plugins(): ...

# Critical operations - validation + error handling
@validate_args(validators={...})
@handle_errors(transform_to=ExecutionError)
def critical_operation(): ...
```

### 2. Use Specific Exception Types

```python
# Good - specific exceptions
@retry(exceptions=[NetworkError, TimeoutError])

# Bad - too broad
@retry(exceptions=[Exception])
```

### 3. Provide Meaningful Fallbacks

```python
# Good - useful fallback
@handle_errors(fallback=lambda: {"status": "error", "data": []})

# Bad - None isn't useful
@handle_errors(fallback=None)
```

### 4. Log Before Suppressing

```python
# Good - log then suppress
@log_errors()
@graceful_degradation(fallback_value=[])
def optional_feature(): ...

# Bad - silent failures
@graceful_degradation(fallback_value=[], warn=False)
def optional_feature(): ...
```

### 5. Validate Early

```python
# Good - validate at entry
@validate_args(validators={"email": lambda e: "@" in e})
def register_user(email: str): ...

# Bad - validation deep in function
def register_user(email: str):
    # ... many lines later ...
    if "@" not in email:
        raise ValueError()
```

## Performance Considerations

### Decorator Overhead

- **Minimal**: ~1-5μs per function call
- **Retry**: Adds delay on retries (expected)
- **Timeout**: Uses native asyncio/signal (fast)
- **Validation**: Depends on validator complexity

### Optimization Tips

```python
# Cache expensive validators
email_validator = compile_email_regex()

@validate_args(validators={"email": email_validator.match})
def register_user(email: str): ...

# Use specific exceptions for retry
@retry(exceptions=[NetworkError])  # Fast
# vs
@retry(exceptions=[Exception])  # Catches everything
```

## Testing with Decorators

### Mocking Decorated Functions

```python
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_with_decorators():
    @retry(max_attempts=2)
    async def flaky_operation():
        # Test implementation
        pass

    # Decorators work normally in tests
    result = await flaky_operation()
```

### Testing Decorator Behavior

```python
def test_retry_logic():
    call_count = 0

    @retry(max_attempts=3, backoff=0.01)  # Fast for testing
    def failing_operation():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise NetworkError("Temporary")
        return "success"

    result = failing_operation()
    assert result == "success"
    assert call_count == 3
```

## Migration Guide

### From ErrorHandlingMixin Methods

**Before:**
```python
class Manager(ErrorHandlingMixin):
    def process_file(self, path: Path) -> bool:
        try:
            result = do_something(path)
        except Exception as e:
            return self.handle_file_operation_error(
                e, path, "process", critical=True
            )
```

**After:**
```python
class Manager:
    @handle_errors(
        error_types=[OSError, PermissionError],
        transform_to=FileError,
    )
    @log_errors()
    def process_file(self, path: Path) -> bool:
        return do_something(path)
```

### Benefits

- ✅ Less boilerplate
- ✅ Composable error handling
- ✅ Type-safe with annotations
- ✅ Consistent error handling
- ✅ Better testability

## Troubleshooting

### Issue: Decorators Not Working

**Check:**
1. Import from correct module
2. Decorator order (bottom to top)
3. Async/sync function compatibility

### Issue: Validation Always Fails

**Check:**
1. Validator function signature (`param -> bool`)
2. Type annotations match actual types
3. `allow_none` configuration

### Issue: Timeout Not Working (Sync)

**Platform:** Sync timeout uses `signal.alarm` (Unix only)

**Solution:** Use async functions or multiprocessing for cross-platform timeout

## Examples

See `examples/decorator_usage.py` for comprehensive real-world examples.

## API Reference

All decorators support:
- ✅ Synchronous functions
- ✅ Asynchronous functions
- ✅ Type hints
- ✅ Composition with other decorators
- ✅ Rich console integration
- ✅ Logging integration

For detailed API documentation, see source docstrings in:
- `crackerjack/decorators/retry.py`
- `crackerjack/decorators/timeout.py`
- `crackerjack/decorators/error_handling.py`
- `crackerjack/decorators/validation.py`
- `crackerjack/decorators/patterns.py`
