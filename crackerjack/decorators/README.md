> Crackerjack Docs: [Main](../../README.md) | [Crackerjack Package](../README.md) | [Decorators](./README.md)

# Decorators

Cross-cutting decorators and helper wrappers for error handling, retry logic, validation, and performance optimization. All decorators support both sync and async functions automatically.

## Available Decorators

### Error Handling

**`handle_errors`** - Centralized error handling with transformation and fallback support

```python
from crackerjack.decorators import handle_errors
from crackerjack.errors import FileError


@handle_errors(
    error_types=[FileNotFoundError, PermissionError],
    transform_to=FileError,
    fallback={},
)
def load_config(path: str) -> dict:
    with open(path) as f:
        return json.load(f)
```

**`log_errors`** - Log errors with context before re-raising

```python
import logging
from crackerjack.decorators import log_errors

logger = logging.getLogger(__name__)


@log_errors(logger=logger, level="error", include_traceback=True)
async def critical_operation() -> bool:
    return await perform_operation()
```

**`graceful_degradation`** - Gracefully degrade on errors with optional warnings

```python
from crackerjack.decorators import graceful_degradation


@graceful_degradation(fallback_value=[], warn=True)
def get_optional_features() -> list[str]:
    # Returns [] on error with warning
    return fetch_features()
```

### Retry and Timeout

**`retry`** - Retry decorator with exponential backoff

```python
from crackerjack.decorators import retry


@retry(max_attempts=3, exceptions=[ConnectionError], backoff=0.5)
async def fetch_data() -> dict:
    return await api_client.get()
```

**`with_timeout`** - Timeout enforcement for long-running operations

```python
from crackerjack.decorators import with_timeout


@with_timeout(seconds=30, error_message="Operation timed out")
def heavy_computation() -> int:
    return compute_result()
```

### Validation

**`validate_args`** - Validate function arguments using callables and type checks

```python
from crackerjack.decorators import validate_args


@validate_args(
    validators={"path": lambda p: Path(p).exists(), "count": lambda n: n > 0},
    type_check=True,
)
def process_files(path: str, count: int) -> bool:
    return True
```

### Pattern Detection

**`cache_errors`** - Detect and cache error patterns for AI-powered analysis

```python
from crackerjack.decorators import cache_errors
from pathlib import Path


@cache_errors(error_type="lint", auto_analyze=True)
async def run_linter(files: list[Path]) -> bool:
    # Errors automatically cached and analyzed
    return await linter.run(files)
```

## Best Practices

### Complexity Guidelines

Keep decorator implementation complexity ≤15 per function using helper methods:

```python
def _create_async_wrapper(func, config):
    """Helper to create async wrapper - reduces complexity."""

    @wraps(func)
    async def wrapper(*args, **kwargs):
        return await func(*args, **kwargs)

    return wrapper
```

### Sync and Async Support

All decorators automatically detect function type using `is_async_function`:

```python
from crackerjack.decorators.helpers import is_async_function


def decorator(func):
    if is_async_function(func):
        return _create_async_wrapper(func)
    return _create_sync_wrapper(func)
```

### Error Context

Use `get_function_context` for rich error reporting:

```python
from crackerjack.decorators.helpers import get_function_context

context = get_function_context(func)
# Returns: {
#     "function_name": "my_function",
#     "module": "mymodule",
#     "qualname": "MyClass.my_function",
#     "is_async": True
# }
```

### Combining Decorators

Stack decorators from innermost to outermost:

```python
@log_errors()
@retry(max_attempts=3)
@with_timeout(seconds=30)
@handle_errors(fallback={})
async def fetch_and_process() -> dict:
    return await process()
```

## Implementation Modules

- **`error_handling.py`** - Core error decorators (retry, handle_errors, timeout, etc.)
- **`patterns.py`** - Pattern detection decorators (cache_errors)
- **`utils.py`** - Shared utilities for decorator implementation

## Related

- [Exceptions](../exceptions/README.md) - Custom exception types and error handling
- [MCP Cache](../mcp/README.md) - Error pattern caching for AI analysis
- [Architecture: ACB Patterns](../../docs/guides/CLAUDE.md#critical-architectural-pattern-protocol-based-di) - Dependency injection patterns
