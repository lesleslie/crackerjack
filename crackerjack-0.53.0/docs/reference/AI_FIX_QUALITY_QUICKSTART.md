# AI Fix Quality System - Quick Start Guide

## Overview

The new multi-agent quality system enforces **read-first, validate-early** principles to dramatically improve AI fix success rates from 2.7% to expected 40-60%.

## Core Principles

### 1. Read First

Agents **MUST** read full file context before generating any fix:

```python
# ✅ CORRECT
content = await self._read_file_context(issue.file_path)
fix = self._generate_fix(issue, content)

# ❌ WRONG - generates fix without context
fix = self._generate_fix(issue)  # No file content!
```

### 2. Validate Early

Validate BEFORE applying changes:

```python
# Check diff size
if not self._validate_diff_size(old_code, new_code):
    return FixResult(success=False, ...)

# Check syntax
is_valid, errors = await self._validate_syntax(new_code)
if not is_valid:
    return FixResult(success=False, ...)
```

### 3. Use Validation Coordinator

For comprehensive validation with parallel execution:

```python
from crackerjack.agents import ValidationCoordinator

coordinator = ValidationCoordinator()
is_valid, feedback = await coordinator.validate_fix(
    code=generated_code,
    file_path=file_path,
    run_tests=True  # Optional: run tests
)
```

## Quick Reference

### FileContextReader

**Purpose**: Thread-safe file reading with caching

```python
reader = FileContextReader()
content = await reader.read_file("path/to/file.py")
reader.clear_cache()  # When needed
```

### SyntaxValidator

**Purpose**: Fast AST-based syntax validation

```python
validator = SyntaxValidator()
result = await validator.validate(code)
if result.valid:
    print("Syntax OK")
else:
    print(f"Errors: {result.errors}")
```

### LogicValidator

**Purpose**: Check for logical errors (duplicates, imports, incomplete blocks)

```python
from crackerjack.agents import LogicValidator

validator = LogicValidator()
result = await validator.validate(code)
# Checks: duplicates, import placement, anti-patterns
```

### ValidationCoordinator

**Purpose**: Run all validators in parallel with permissive logic

```python
from crackerjack.agents import ValidationCoordinator

coordinator = ValidationCoordinator()

# Permissive: passes if ANY validator passes
is_valid, feedback = await coordinator.validate_fix(
    code=generated_code,
    file_path="/path/to/file.py"
)

if is_valid:
    print("Fix validated!")
else:
    print(f"Fix rejected:\n{feedback}")
```

### FixPlan

**Purpose**: Structured change specification with risk assessment

```python
from crackerjack.models import ChangeSpec, FixPlan

change = ChangeSpec(
    line_range=(1, 10),
    old_code="old code",
    new_code="new code",
    reason="Refactor for clarity"
)

plan = FixPlan(
    file_path="/path/to/file.py",
    issue_type="COMPLEXITY",
    changes=[change],
    rationale="Reduce cyclomatic complexity",
    risk_level="medium",  # low/medium/high
    validated_by="RefactoringAgent"
)

# Check if acceptable
if plan.is_acceptable_risk("medium"):
    print("Risk level acceptable")
```

## Common Patterns

### Pattern 1: Safe Agent Fix

```python
async def analyze_and_fix(self, issue: Issue) -> FixResult:
    # 1. Read context (MANDATORY)
    file_content = await self._read_file_context(issue.file_path)

    # 2. Generate fix
    new_code = self._generate_fix(issue, file_content)

    # 3. Validate diff size
    if not self._validate_diff_size(file_content, new_code):
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["Diff too large"],
            ...
        )

    # 4. Validate syntax
    is_valid, errors = await self._validate_syntax(new_code)
    if not is_valid:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=errors,
            ...
        )

    # 5. Apply with context write (has syntax validation)
    success = self.context.write_file_content(issue.file_path, new_code)

    return FixResult(success=success, ...)
```

### Pattern 2: Parallel Validation

```python
async def validate_with_parallel(self, code: str, file_path: str) -> bool:
    coordinator = ValidationCoordinator()

    # Runs Syntax, Logic, Behavior validators in parallel
    is_valid, feedback = await coordinator.validate_fix(
        code=code,
        file_path=file_path,
        run_tests=False  # Fast mode
    )

    return is_valid
```

### Pattern 3: Risk Assessment

```python
plan = FixPlan(...)

# Check risk level
if plan.is_high_risk():
    print("High risk change - requires review")

# Check if risk is acceptable
if plan.is_acceptable_risk(max_risk="medium"):
    print("Risk acceptable - can apply")

# Estimate change size
diff_size = plan.estimate_diff_size()
if diff_size > 50:
    print(f"Warning: Large change ({diff_size} lines)")
```

## Troubleshooting

### Issue: "ModuleNotFoundError: No module named 'crackerjack.agents.file_context'"

**Solution**: Make sure you've updated imports:

```python
# In crackerjack/agents/__init__.py
from .file_context import FileContextReader
from .syntax_validator import SyntaxValidator
# etc.
```

### Issue: Tests failing

**Solution**: Run tests individually:

```bash
python -m pytest tests/agents/test_file_context.py -v
python -m pytest tests/agents/test_syntax_validator.py -v
python -m pytest tests/models/test_fix_plan.py -v
```

### Issue: Validation too slow

**Solution**: Adjust parallel execution:

```python
# Fewer validators for faster validation
is_valid, feedback = await coordinator.validate_fix(
    code=code,
    run_tests=False  # Skip tests (slow)
)
```

## Best Practices

### ✅ DO

- Always read full file context before generating fixes
- Validate syntax with AST before applying changes
- Check diff size limits (max 50 lines)
- Use parallel validation for speed (2-3x faster)
- Return detailed FixResult with specific errors
- Log validation failures for debugging

### ❌ DON'T

- Generate fixes without reading file context
- Apply changes without syntax validation
- Make changes larger than 50 lines without splitting
- Run validators sequentially (use parallel)
- Ignore validation errors (always report them)

## Performance Tips

1. **Use Caching**: FileContextReader caches reads automatically
1. **Parallel Validation**: ValidationCoordinator runs 3 validators at once
1. **Early Returns**: Fail fast on diff size violations
1. **Lazy Test Running**: Only run tests on final validation, not intermediate

## Migration Guide

### Updating Existing Agents

**Before**:

```python
class MyAgent(SubAgent):
    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        new_code = self._generate_fix(issue)
        self.context.write_file_content(issue.file_path, new_code)
        return FixResult(success=True, ...)
```

**After** (with quality system):

```python
from crackerjack.agents import ProactiveAgent

class MyAgent(ProactiveAgent):
    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        # 1. Read context
        content = await self._read_file_context(issue.file_path)

        # 2. Generate fix
        new_code = self._generate_fix(issue, content)

        # 3. Validate
        if not self._validate_diff_size(content, new_code):
            return FixResult(success=False, ...)

        is_valid, errors = await self._validate_syntax(new_code)
        if not is_valid:
            return FixResult(success=False, ...)

        # 4. Apply
        self.context.write_file_content(issue.file_path, new_code)
        return FixResult(success=True, ...)
```

## Support

For issues or questions:

1. Check test files for usage examples
1. Review MVP_AI_FIX_QUALITY_SUMMARY.md for architecture details
1. Run specific test to debug: `pytest tests/agents/test_file_context.py::TestFileContextReader::test_read_file_basic -v`
