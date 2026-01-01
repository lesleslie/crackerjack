# Adapter Protocol Type Error Fixes

**Mission**: Fix remaining adapter/protocol mismatches in zuban errors
**Target**: 20-30 errors fixed from 67 total

## Error Analysis

### 1. Type Annotation Missing (complexipy.py:276)

**Error**: `Need type annotation for "issues" (hint: "issues: List[<type>] = ...")`
**File**: `crackerjack/adapters/complexity/complexipy.py:276`
**Fix**: Add explicit type annotation

```python
# Current (line 276)
issues = []

# Fixed
issues: list[ToolIssue] = []
```

### 2. Pydantic Field Validator Type Errors (checks.py:85, 111)

**Error**: `Value of type variable "_V2BeforeAfterOrPlainValidatorType" of function cannot be "Callable[[UtilityCheckSettings, str | None, dict[str, Any]], str | None]"`
**File**: `crackerjack/adapters/utility/checks.py:85, 111`
**Cause**: Pydantic v2 `field_validator` signature mismatch - second parameter should be `ValidationInfo` not `dict`
**Fix**:

```python
# Current (incorrect for Pydantic v2)
@field_validator("pattern")
def validate_pattern(cls, v: str | None, values: dict[str, t.Any]) -> str | None:
    if v is not None:
        try:
            CompiledPatternCache.get_compiled_pattern(v)
        except ValueError as e:
            raise ValueError(f"Invalid regex pattern: {e}")
    return v

# Fixed (Pydantic v2 compatible)
from pydantic import ValidationInfo

@field_validator("pattern")
@classmethod
def validate_pattern(cls, v: str | None, info: ValidationInfo) -> str | None:
    """Validate regex pattern using safe compilation."""
    if v is not None:
        try:
            CompiledPatternCache.get_compiled_pattern(v)
        except ValueError as e:
            raise ValueError(f"Invalid regex pattern: {e}")
    return v
```

### 3. Missing Required Arguments (checks.py:171)

**Error**: `Missing named argument "parser_type", "max_size_bytes", "lock_command"`
**File**: `crackerjack/adapters/utility/checks.py:171`
**Cause**: Direct instantiation of `UtilityCheckSettings` without required fields
**Fix**: Need to examine line 171 and provide all required fields or use `model_validate`

### 4. Import Name Conflict (dependency/__init__.py:22)

**Error**: `Name "PipAuditAdapter" already defined (possibly by an import)`
**File**: `crackerjack/adapters/dependency/__init__.py:22`
**Cause**: Type ignore comment doesn't cover "no-redef" error code
**Fix**: Update type ignore comment

```python
# Current
PipAuditAdapter = None  # type: ignore[assignment,misc]

# Fixed
PipAuditAdapter = None  # type: ignore[assignment,misc,no-redef]
```

### 5. QA Orchestrator Coroutine Mismatch (qa_orchestrator.py:197)

**Error**: `Argument 1 to "create_task" has incompatible type "Awaitable[QAResult]"; expected "Coroutine[Any, Any, QAResult]"`
**File**: `crackerjack/services/quality/qa_orchestrator.py:197`
**Cause**: Async method not returning actual coroutine
**Fix**: Ensure `check()` methods return proper coroutines

## Fix Strategy

### Priority 1: Quick Wins (5 errors)

1. **complexipy.py:276** - Add type annotation to `issues` variable
1. **dependency/__init__.py:22** - Update type ignore comment
1. **checks.py validators** - Fix Pydantic v2 validator signatures (2 errors)

### Priority 2: Medium Complexity (3+ errors)

1. **checks.py:171** - Fix missing required arguments
1. **qa_orchestrator.py:197** - Fix coroutine type issue

## Implementation Steps

1. Fix complexipy type annotation
1. Fix dependency/__init__ type ignore
1. Fix checks.py validators (Pydantic v2 compatibility)
1. Fix checks.py:171 instantiation
1. Fix qa_orchestrator coroutine issue
1. Run zuban to verify fixes
1. Run crackerjack quality checks

## Expected Outcome

- **Errors Fixed**: 7-10 adapter/protocol errors
- **Zuban Performance**: Faster type checking (20-200x)
- **Architecture Compliance**: Protocol-based DI maintained
- **Test Coverage**: No regression in coverage baseline

## Verification Commands

```bash
# Verify zuban fixes
uv run zuban check crackerjack/adapters/

# Full quality check
python -m crackerjack run

# Run tests
python -m crackerjack run --run-tests
```

## Files to Modify

1. `crackerjack/adapters/complexity/complexipy.py` (1 line)
1. `crackerjack/adapters/dependency/__init__.py` (1 line)
1. `crackerjack/adapters/utility/checks.py` (3 locations)
1. `crackerjack/services/quality/qa_orchestrator.py` (1 location)

**Total Estimated Changes**: 10-15 lines across 4 files
