# Python Improvements Summary: Logging & Progress Bar Implementation

**Date**: 2025-11-26
**Quick Reference**: Essential Python patterns for the implementation

______________________________________________________________________

## Top 5 Python Anti-Patterns Found

### 1. ❌ Direct `print()` Statements (CRITICAL)

**Problem**: `dependency_guard.py` uses `print()` instead of proper logging

```python
# BAD - Lines 28-30, 61-62, 86
print("WARNING: Logger dependency was registered as empty tuple")
print("INFO: Registering LoggerProtocol with fresh logger instance")
```

**Solution**: Use stderr with debug check

```python
# GOOD
def _log_dependency_issue(message: str, *, level: str = "WARNING") -> None:
    if os.environ.get("CRACKERJACK_DEBUG") != "1":
        return
    print(f"[CRACKERJACK:{level}] {message}", file=sys.stderr)
```

______________________________________________________________________

### 2. ❌ Environment Variable Deletion is Unsafe

**Problem**: Proposed solution uses `del os.environ[key]` (can raise KeyError)

```python
# BAD
if "ACB_DISABLE_STRUCTURED_STDERR" in os.environ:
    del os.environ["ACB_DISABLE_STRUCTURED_STDERR"]
```

**Solution**: Use `.pop()` for safe deletion

```python
# GOOD
os.environ.pop("ACB_DISABLE_STRUCTURED_STDERR", None)  # Safe, no KeyError
```

______________________________________________________________________

### 3. ❌ No Thread Safety for Global State

**Problem**: Multiple threads mutating `os.environ` = race conditions

```python
# BAD - Not thread-safe
os.environ["ACB_LOG_LEVEL"] = "WARNING"
os.environ["CRACKERJACK_DEBUG"] = "1"
```

**Solution**: Use thread-local storage for internal state

```python
# GOOD
import threading

_logger_state = threading.local()


def get_debug_mode() -> bool:
    return getattr(_logger_state, "debug", False)


def set_debug_mode(enabled: bool) -> None:
    _logger_state.debug = enabled
```

______________________________________________________________________

### 4. ❌ DRY Violation: Repeated Logger Creation

**Problem**: Same 3-line pattern repeated 5+ times

```python
# BAD - Repeated everywhere
from acb.logger import Logger as ACBLogger

fresh_logger = ACBLogger()
depends.set(Logger, fresh_logger)
```

**Solution**: Factory function

```python
# GOOD
def _create_and_register_logger() -> Logger:
    from acb.logger import Logger as ACBLogger

    fresh_logger = ACBLogger()
    depends.set(Logger, fresh_logger)
    return fresh_logger


# Use everywhere
fresh_logger = _create_and_register_logger()
```

______________________________________________________________________

### 5. ❌ Fragile String Matching for CLI Args

**Problem**: `"--debug" not in sys.argv` doesn't handle `-d` or `--debug=true`

```python
# BAD
if "--debug" not in sys.argv:
    os.environ["ACB_LOG_LEVEL"] = "WARNING"
```

**Solution**: Proper argparse-compatible detection

```python
# GOOD
_EARLY_DEBUG_FLAG = any(
    arg in ("--debug", "-d") or arg.startswith("--debug=") for arg in sys.argv[1:]
)
```

______________________________________________________________________

## Essential Python Patterns to Use

### Pattern 1: Context Manager for Environment Lifecycle

```python
@contextmanager
def logger_verbosity(*, debug: bool = False) -> Iterator[None]:
    """Temporary logger configuration with automatic restoration."""
    original_state = {
        "ACB_LOG_LEVEL": os.environ.get("ACB_LOG_LEVEL"),
        "CRACKERJACK_DEBUG": os.environ.get("CRACKERJACK_DEBUG"),
    }

    try:
        # Apply new config
        if debug:
            os.environ["ACB_LOG_LEVEL"] = "DEBUG"
            os.environ["CRACKERJACK_DEBUG"] = "1"
        yield
    finally:
        # Restore original state
        for key, value in original_state.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
```

**Use Case**: Testing isolation (each test restores environment)

______________________________________________________________________

### Pattern 2: Protocol-Based Dependency Injection

```python
# ALWAYS import protocols, never concrete classes
from crackerjack.models.protocols import LoggerProtocol


@depends.inject
def configure_logger(logger: Inject[LoggerProtocol] = None) -> None:
    """Perfect ACB integration."""
    logger.info("Configured successfully")
```

______________________________________________________________________

### Pattern 3: Type Hints with Literal for Constants

```python
from typing import Literal, Final

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR"]


def configure_logger(*, level: LogLevel = "WARNING") -> None:
    """Type-safe log level configuration."""
    os.environ["ACB_LOG_LEVEL"] = level


# Constants should be Final
_EARLY_DEBUG_FLAG: Final[bool] = "--debug" in sys.argv
```

______________________________________________________________________

### Pattern 4: Safe Environment Variable Operations

```python
# Setting (idempotent)
os.environ.setdefault("ACB_LOG_LEVEL", "WARNING")

# Getting (with default)
debug_enabled = os.environ.get("CRACKERJACK_DEBUG", "0") == "1"

# Deleting (safe, no KeyError)
os.environ.pop("ACB_DISABLE_STRUCTURED_STDERR", None)

# Checking existence
if "CRACKERJACK_DEBUG" in os.environ:
    # ...
```

______________________________________________________________________

### Pattern 5: Modern Python 3.13 Features

```python
# Use | unions (not Union)
def configure(value: str | None = None) -> bool | None:
    pass


# Use match statements (not if/elif chains)
match logger_instance:
    case tuple() if len(logger_instance) == 0:
        return _create_and_register_logger()
    case str():
        return _create_and_register_logger()
    case _:
        return logger_instance

# Use frozenset for immutable collections
_CLI_ARGS: Final[frozenset[str]] = frozenset(sys.argv[1:])
_EARLY_DEBUG_FLAG: Final[bool] = bool(_CLI_ARGS & {"--debug", "-d"})
```

______________________________________________________________________

## Quick Implementation Checklist

### Before Implementing

- [ ] Replace all `print()` with `_log_dependency_issue()` in `dependency_guard.py`
- [ ] Change all `del os.environ[key]` to `os.environ.pop(key, None)`
- [ ] Add factory function `_create_and_register_logger()`
- [ ] Improve early debug detection to handle `-d` and `--debug=value`
- [ ] Add full type hints to all new functions

### New Files to Create

- [ ] `crackerjack/utils/logger_config.py` - Thread-safe logger configuration
- [ ] `crackerjack/utils/logger_state.py` - Thread-local storage for logger state
- [ ] `tests/utils/test_logger_config.py` - Comprehensive test suite

### Files to Modify

- [ ] `crackerjack/__main__.py` - Early debug detection + post-parse config
- [ ] `crackerjack/utils/dependency_guard.py` - Replace print() with proper logging
- [ ] `crackerjack/executors/progress_hook_executor.py` - Change `transient=False` to `transient=True`

### Testing Requirements

- [ ] Test with `python -m crackerjack` (default, clean output)
- [ ] Test with `python -m crackerjack --verbose` (no low-level logs)
- [ ] Test with `python -m crackerjack --debug` (full logging + stderr JSON)
- [ ] Test with `python -m crackerjack -d` (short form debug flag)
- [ ] Test progress bar behavior across all flag combinations
- [ ] Verify thread safety with concurrent test execution

______________________________________________________________________

## Code Review Checklist

### Python Best Practices

- [ ] All functions have type hints
- [ ] No direct `print()` statements (use logging or stderr)
- [ ] Environment variables use `.pop()` for deletion
- [ ] Thread-local storage for mutable state
- [ ] Context managers for resource lifecycle
- [ ] Factory functions for repeated patterns (DRY)

### Crackerjack Standards

- [ ] Import protocols from `models/protocols.py`
- [ ] Use `@depends.inject` decorator
- [ ] Use `Inject[Protocol]` for dependencies
- [ ] Python 3.13+ syntax (`|` unions, match statements)
- [ ] Complexity ≤15 per function
- [ ] Comprehensive docstrings with Examples

### Testing Standards

- [ ] Fixtures for environment isolation
- [ ] Mock external dependencies
- [ ] Test both success and error paths
- [ ] Clear test names (`test_<behavior>_<condition>`)
- [ ] Pytest conventions (class-based organization)

______________________________________________________________________

## Performance Optimizations

### High Impact

```python
# Use frozenset for O(1) membership testing
_CLI_ARGS = frozenset(sys.argv[1:])
if "--debug" in _CLI_ARGS:  # O(1) vs O(n)
    pass
```

### Medium Impact

```python
# Use match statements (single type check)
match instance:
    case tuple() if len(instance) == 0:
        # handle
    case str():
        # handle
```

### Low Impact

```python
# Use lazy imports (only if needed)
def _create_logger() -> Logger:
    from acb.logger import Logger as ACBLogger  # Lazy

    return ACBLogger()
```

______________________________________________________________________

## Common Pitfalls to Avoid

1. ❌ Don't use `del os.environ[key]` → Use `.pop(key, None)`
1. ❌ Don't use `print()` in library code → Use logging or stderr
1. ❌ Don't mutate global state without thread safety → Use thread-local storage
1. ❌ Don't repeat patterns → Extract to factory functions
1. ❌ Don't skip type hints → Add to all new functions
1. ❌ Don't hardcode values → Use constants with `Final` annotation
1. ❌ Don't use `Union[X, None]` → Use `X | None` (Python 3.13+)
1. ❌ Don't use bare `except:` → Catch specific exceptions

______________________________________________________________________

## One-Line Summary

**Replace `print()` with logging, use `.pop()` for env vars, add thread-local storage, extract factory functions, and improve early debug detection.**

______________________________________________________________________

For full analysis and examples, see: `/docs/python-review-logging-progress-implementation.md`
