# Error Handling Standard

**Date**: 2025-02-08
**Status**: Active Standard
**Applies to**: All Python code in crackerjack

______________________________________________________________________

## Overview

This document defines the standard error handling pattern for the crackerjack codebase. Consistent error handling ensures:

1. **Debuggability**: Full context for troubleshooting
1. **Observability**: Persistent logs for headless execution
1. **Reliability**: No silent failures or lost errors
1. **Maintainability**: Predictable error handling patterns

______________________________________________________________________

## Standard Pattern

### 1. Logging Errors with Context

**✅ CORRECT**:

```python
except Exception as e:
    logger.exception(
        f"Failed to {action} for {resource}: {error_context}",
        extra={
            "file_path": str(file_path),
            "function": function_name,
            "line_number": line_number,
        }
    )
    # Handle or re-raise as appropriate
```

**❌ INCORRECT**:

```python
except Exception as e:
    console.print(f"Error: {e}")  # Not logged, lost in headless mode
```

**❌ INCORRECT**:

```python
except Exception:
    pass  # Silent failure - worst practice
```

### 2. Always Include Stack Traces

**✅ CORRECT** (with stack trace):

```python
except Exception as e:
    logger.exception(f"Failed to process {file_path}")
```

**✅ CORRECT** (explicit stack trace):

```python
except Exception as e:
    logger.error(
        f"Failed to process {file_path}: {e}",
        exc_info=True
    )
```

**❌ INCORRECT** (no stack trace):

```python
except Exception as e:
    logger.error(f"Failed to process {file_path}: {e}")
```

### 3. Provide Actionable Context

**✅ CORRECT** (specific context):

```python
except Exception as e:
    logger.exception(
        f"Failed to load configuration from {config_path}",
        extra={"config_path": str(config_path)}
    )
```

**❌ INCORRECT** (generic):

```python
except Exception as e:
    logger.error(f"Error: {e}")
```

### 4. Re-Raise or Handle Appropriately

**✅ CORRECT** (re-raise with context):

```python
except Exception as e:
    logger.exception(f"Failed to {action}")
    raise  # Re-raise for caller to handle
```

**✅ CORRECT** (return error result):

```python
except Exception as e:
    logger.exception(f"Failed to {action}")
    return ErrorResult(error=str(e))
```

**✅ CORRECT** (convert to domain error):

```python
except ValueError as e:
    logger.exception(f"Invalid {resource} format")
    raise ValidationError(f"Invalid {resource}: {e}") from e
```

______________________________________________________________________

## Error Handling Decision Tree

```
Exception occurs
    │
    ├─→ Can you recover from it?
    │   ├─→ YES → Log with exception, return error/fallback value
    │   └─→ NO  → Continue below
    │
    ├─→ Should caller handle it?
    │   ├─→ YES → Log with exception, re-raise (possibly with context)
    │   └─→ NO  → Continue below
    │
    └─→ Is it a critical failure?
        ├─→ YES → Log with exception, raise/exit appropriately
        └─→ NO  → Log warning, continue with degraded functionality
```

______________________________________________________________________

## Common Patterns

### Pattern 1: File Operations

```python
try:
    content = file_path.read_text()
except (OSError, UnicodeDecodeError) as e:
    logger.exception(
        f"Failed to read file: {file_path}",
        extra={"file_path": str(file_path), "error_type": type(e).__name__}
    )
    raise FileNotFoundError(f"Cannot read {file_path}: {e}") from e
```

### Pattern 2: External Process Execution

```python
try:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=30,
    )
except subprocess.TimeoutExpired as e:
    logger.error(
        f"Command timed out: {' '.join(command)}",
        extra={"command": command, "timeout": 30}
    )
    raise
except Exception as e:
    logger.exception(
        f"Failed to execute command: {' '.join(command)}",
        extra={"command": command}
    )
    raise
```

### Pattern 3: Data Parsing/Validation

```python
try:
    data = json.loads(json_content)
except json.JSONDecodeError as e:
    logger.warning(
        f"Invalid JSON in {file_path}: {e}",
        extra={"file_path": str(file_path), "json_error": str(e)}
    )
    return {}  # Return safe default
```

### Pattern 4: Async Operations

```python
try:
    result = await async_function()
except Exception as e:
    logger.exception(
        f"Async operation failed: {function_name}",
        extra={"function": function_name, "args": str(args)}
    )
    raise  # Re-raise for caller to handle
```

______________________________________________________________________

## Category-Specific Guidelines

### 1. Managers (crackerjack/managers/)

**Pattern**: Log with exception, return status or re-raise

```python
except Exception as e:
    logger.exception(f"Manager {manager_name} failed to {action}")
    return False  # or raise, depending on severity
```

### 2. Coordinators (crackerjack/core/)

**Pattern**: Use `logger.exception()` for full context

```python
except Exception as e:
    self.logger.exception(
        f"Coordinator {coord_name} error in {stage}",
        extra={"stage": stage, "context": context}
    )
```

### 3. Adapters (crackerjack/adapters/)

**Pattern**: Convert errors to domain-specific exceptions

```python
except Exception as e:
    logger.exception(f"Adapter {adapter_name} failure")
    raise AdapterError(f"Adapter {adapter_name} failed: {e}") from e
```

### 4. Services (crackerjack/services/)

**Pattern**: Log with service-specific context

```python
except Exception as e:
    logger.exception(
        f"Service {service_name} error",
        extra={"service": service_name, "operation": operation}
    )
```

______________________________________________________________________

## Anti-Patterns to Avoid

### ❌ Anti-Pattern 1: Silent Exception Swallowing

```python
try:
    risky_operation()
except Exception:
    pass  # ERROR: Silent failure, no way to debug
```

### ❌ Anti-Pattern 2: Console-Only Logging

```python
try:
    risky_operation()
except Exception as e:
    console.print(f"Error: {e}")  # ERROR: Lost in headless mode, no log
```

### ❌ Anti-Pattern 3: Overly Broad Exception Handling

```python
try:
    risky_operation()
except:  # ERROR: Bare except, catches everything including KeyboardInterrupt
    pass
```

### ❌ Anti-Pattern 4: Logging Without Context

```python
try:
    risky_operation()
except Exception as e:
    logger.error(f"Error: {e}")  # ERROR: No context, hard to debug
```

### ❌ Anti-Pattern 5: Losing Original Exception

```python
try:
    risky_operation()
except ValueError as e:
    raise RuntimeError("Something failed")  # ERROR: Lost 'e' context
```

**CORRECT**:

```python
try:
    risky_operation()
except ValueError as e:
    raise RuntimeError("Something failed") from e  # Preserves stack trace
```

______________________________________________________________________

## Implementation Checklist

When adding error handling to new code:

- [ ] Uses `logger.exception()` or `logger.error(..., exc_info=True)`
- [ ] Includes meaningful context (what, where, why)
- [ ] Logs at appropriate level (error for failures, warning for recoverable issues)
- [ ] Either re-raises or returns appropriate error value
- [ ] Never silently catches exceptions
- [ ] Preserves original exception with `from e` when re-raising

______________________________________________________________________

## Migration Plan

### Phase 1: Audit (COMPLETED)

- [x] Identify all error handling patterns
- [x] Document inconsistencies
- [x] Create standard

### Phase 2: Apply to Core Files (IN PROGRESS)

Priority order:

1. Coordinators (crackerjack/core/)
1. Managers (crackerjack/managers/)
1. Adapters (crackerjack/adapters/)
1. Services (crackerjack/services/)

### Phase 3: Validation

- [ ] Run test suite to ensure no behavioral changes
- [ ] Verify all errors are logged with context
- [ ] Check for no silent exception swallowing

______________________________________________________________________

## Related Documents

- `CLAUDE.md` - Code standards and quality decision framework
- `PHASE_3_PLAN.md` - Phase 3 implementation plan
- Python logging best practices: https://docs.python.org/3/howto/logging.html

______________________________________________________________________

**Last Updated**: 2025-02-08
**Owner**: Architecture Team
**Status**: Active Standard
