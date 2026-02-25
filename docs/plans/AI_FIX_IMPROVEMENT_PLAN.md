# AI-Fix Improvement Plan

## Current State

**Success Rate:** 9.6% (27/281)
**Main Failure Modes:**
- 254 Max Retries Error - fix attempted but failed validation
- "Plan has no changes to apply" - couldn't generate fix
- "Could not extract FURB code" - parsing failure

## Error Distribution (117 zuban errors)

| Error Type | Count | Auto-fix Strategy |
|------------|-------|-------------------|
| attr-defined | 28 | Type narrowing or `# type: ignore[attr-defined]` |
| arg-type | 26 | Cast (`str()`) or type annotation |
| name-defined | 10 | Add missing import |
| index | 10 | Add type annotation to collection |
| call-arg | 9 | Fix signature or add ignore |
| operator | 6 | Type annotation |
| misc | 6 | Case-by-case |
| assignment | 6 | Type annotation |

## Improvement Strategies

### 1. Smarter Error Classification

Create error classifiers that determine fix strategy:

```python
class ErrorClassifier:
    """Classify errors by fix strategy."""

    SAFE_AUTO_FIX = {  # Can always auto-fix
        "name-defined": "add_import",
        "var-annotated": "add_annotation",
    }

    CONDITIONAL_FIX = {  # Need context analysis
        "attr-defined": "type_narrow_or_ignore",
        "arg-type": "cast_or_ignore",
    }

    MANUAL_REVIEW = {  # Too risky to auto-fix
        "operator": "manual",
        "return-value": "manual",
    }
```

### 2. Pattern-Based Quick Fixers

Create specialized fixers for common patterns:

#### Path → str Converter
```python
def fix_path_arg_type(issue: Issue, code: str) -> ChangeSpec | None:
    """Fix 'Path' vs 'str' argument type errors."""
    if "Path" in issue.message and "str" in issue.message:
        # Find Path variable and wrap with str()
        pattern = r'\b(file_path|path)\b(?!\s*\))'
        new_code = re.sub(pattern, r'str(\1)', code)
        if new_code != code:
            return ChangeSpec(...)
    return None
```

#### Type Narrowing for attr-defined
```python
def fix_attr_defined_with_narrowing(issue: Issue, code: str) -> ChangeSpec | None:
    """Fix 'object has no attribute' with type narrowing."""
    # If accessing attribute on 'object' type
    if '"object" has no attribute' in issue.message:
        # Add isinstance check or type: ignore
        attr = extract_attribute_from_message(issue.message)
        new_code = f"if hasattr(obj, '{attr}'):\n    {code}"
        return ChangeSpec(...)
    return None
```

### 3. Complexity Reduction for Pyscn

For complexity issues, apply refactoring patterns:

```python
class ComplexityReducer:
    """Reduce function complexity through refactoring."""

    def reduce_complexity(self, func_node: ast.FunctionDef) -> list[ChangeSpec]:
        changes = []

        # 1. Extract guard clauses
        changes.extend(self._extract_guard_clauses(func_node))

        # 2. Decompose conditionals
        changes.extend(self._decompose_conditionals(func_node))

        # 3. Extract helper methods
        changes.extend(self._extract_helpers(func_node))

        return changes
```

### 4. Better Retry Logic

Don't just retry - analyze failure and adapt:

```python
class AdaptiveRetryStrategy:
    """Adapt fix strategy based on failure analysis."""

    def get_next_strategy(self, failure_reason: str) -> str:
        if "validation failed" in failure_reason:
            return "more_conservative_fix"
        elif "syntax error" in failure_reason:
            return "simpler_pattern"
        elif "new errors introduced" in failure_reason:
            return "minimal_change"
        return "type_ignore_fallback"
```

### 5. Feedback Loop Integration

Use prompt_evolution more effectively:

```python
# In autofix_coordinator.py
def record_fix_outcome(self, issue: Issue, fix: ChangeSpec, success: bool):
    if success:
        self._prompt_evolution.record_successful_fix(
            issue=issue,
            before_code=fix.old_code,
            after_code=fix.new_code,
        )
    else:
        self._prompt_evolution.record_failed_fix(
            issue=issue,
            attempted_fix=str(fix),
            failure_reason="Validation failed",
        )
```

### 6. Multi-Pass Fixing

Fix simpler issues first, then complex:

```python
FIX_ORDER = [
    # Pass 1: Safe fixes (no risk)
    ["name-defined", "var-annotated"],

    # Pass 2: Low-risk fixes
    ["call-arg", "arg-type"],

    # Pass 3: Medium-risk fixes
    ["attr-defined", "union-attr"],

    # Pass 4: Complex fixes
    ["operator", "assignment", "index"],
]
```

### 7. Pre-flight Validation

Before applying fix, validate it won't break:

```python
def validate_fix_safety(change: ChangeSpec, file_path: Path) -> bool:
    """Check if fix is safe to apply."""
    # 1. Syntax check
    try:
        ast.parse(change.new_code)
    except SyntaxError:
        return False

    # 2. Type check (optional, slow)
    # run_zuban_on_snippet(change.new_code)

    # 3. Semantic check - does it still do the same thing?
    # Compare AST structure

    return True
```

## Implementation Priority

1. **High Impact, Low Effort:**
   - Path → str converter for arg-type errors
   - Better error code extraction
   - Multi-pass fixing order

2. **High Impact, Medium Effort:**
   - Adaptive retry strategy
   - Pre-flight validation
   - Better prompt_evolution integration

3. **Medium Impact, High Effort:**
   - Complexity reduction for pyscn
   - Type narrowing for attr-defined
   - Semantic validation

## Success Metrics

- **Target:** 50% AI-fix success rate (currently 9.6%)
- **Stretch:** 75% success rate
- **Key metric:** Issues fixed per run without manual intervention
