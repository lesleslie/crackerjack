# Decorator-Based Error Handling Implementation Plan

## Overview

Create a composable decorator system for error handling that complements the existing `ErrorHandlingMixin` and integrates seamlessly with Crackerjack's error architecture.

## Design Goals

1. **Composability**: Stack multiple decorators for complex error handling scenarios
2. **Type Safety**: Full type hints for IDE support and static analysis
3. **Async Support**: Native async/await support for both sync and async functions
4. **Rich Integration**: Beautiful console output using existing Rich patterns
5. **Logging Integration**: Seamless integration with Crackerjack's logging infrastructure
6. **Backward Compatibility**: Works alongside existing ErrorHandlingMixin

## Architecture

### Core Decorators

1. **@retry** - Retry logic with exponential backoff
   - Configurable max attempts, backoff factor, max delay
   - Support for specific exception types
   - Async-aware retry logic
   - Rich progress indication

2. **@handle_errors** - Centralized error handling
   - Type-specific error handling
   - Fallback values/functions
   - Error transformation (wrap in CrackerjackError)
   - Console + logging integration

3. **@with_timeout** - Timeout enforcement
   - Support for both sync and async functions
   - Raise TimeoutError from errors.py
   - Graceful cancellation for async

4. **@log_errors** - Error logging decorator
   - Automatic error context capture
   - Integration with Crackerjack's logger
   - Configurable log levels

5. **@graceful_degradation** - Fallback behavior
   - Return fallback values on error
   - Optional warning messages
   - Error suppression with logging

### Advanced Decorators

6. **@validate_args** - Argument validation
   - Type checking
   - Value range validation
   - Custom validators

7. **@cache_errors** - Error pattern caching
   - Integration with ErrorCache
   - Pattern detection and storage
   - Auto-fix suggestions

8. **@circuit_breaker** - Circuit breaker pattern
   - Prevent cascading failures
   - Configurable failure threshold
   - Auto-recovery after timeout

## Implementation Structure

```
crackerjack/decorators/
├── __init__.py              # Public API exports
├── error_handling.py        # Core error handling decorators
├── retry.py                 # Retry logic implementation
├── timeout.py               # Timeout handling
├── validation.py            # Argument validation
├── patterns.py              # Error pattern detection
└── utils.py                 # Shared utilities
```

## Integration Points

1. **errors.py**: Use existing exception classes
2. **ErrorHandlingMixin**: Complement, don't replace
3. **Rich Console**: Reuse formatting patterns
4. **Logging**: Integrate with existing loggers
5. **ErrorCache**: Pattern detection and caching

## Usage Examples

### Basic Retry
```python
@retry(max_attempts=3, backoff=2.0, exceptions=[NetworkError])
async def fetch_data(url: str) -> dict:
    ...
```

### Stacked Decorators
```python
@with_timeout(seconds=30)
@retry(max_attempts=3)
@log_errors(logger=my_logger)
async def risky_operation() -> bool:
    ...
```

### Error Handling with Fallback
```python
@handle_errors(
    error_types=[FileError, PermissionError],
    fallback=lambda: {}
)
def load_config(path: Path) -> dict:
    ...
```

### Graceful Degradation
```python
@graceful_degradation(fallback_value=[], warn=True)
def get_optional_data() -> list[str]:
    ...
```

## Testing Strategy

1. **Unit Tests**: Each decorator tested independently
2. **Integration Tests**: Decorator composition scenarios
3. **Async Tests**: Verify async/await behavior
4. **Error Cases**: Verify error handling and transformation
5. **Performance Tests**: Overhead measurement

## Documentation

- Comprehensive docstrings with examples
- Type hints for all parameters
- Usage examples in tests
- Integration guide in docs/

## Success Criteria

- [ ] All decorators implemented with type hints
- [ ] Async support for all decorators
- [ ] Rich console integration
- [ ] Comprehensive test coverage
- [ ] Documentation complete
- [ ] Integration with existing ErrorHandlingMixin verified
- [ ] No breaking changes to existing code
