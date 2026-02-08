# AI-Fix Shadowing Damage - New Failure Pattern Discovered

**Date**: 2026-02-07
**Status**: 🔴 **CRITICAL** - New damage pattern bypasses syntax validation

---

## Executive Summary

**AI agents have evolved a new damage pattern** that bypasses our syntax validation:

### What Works ✅

1. **Syntax validation successfully prevents syntax errors**
   - Pre-apply validation in `AgentContext.write_file_content()` works perfectly
   - Example: Caught unclosed parenthesis in `code_transformer.py:351`
   - **No syntax errors reached disk**

2. **Safety validation layers are functioning**
   - Pre-apply: Invalid syntax rejected before writing
   - Post-apply: All modified files compile successfully
   - Rollback: Automatic git checkout if validation fails

### What's Broken 🔴

**AI agents now create semantic errors via shadowing:**

1. **Broken stub functions** that call non-existent methods
2. **Duplicate function definitions** where stub shadows real function
3. **Files compile** but contain massive amounts of dead broken code
4. **26 files damaged** with up to 13 duplicate definitions each

---

## The New Damage Pattern

### Example: `crackerjack/services/async_file_io.py`

```python
# Lines 81-82: BROKEN STUB (AI-generated)
async def async_read_file(file_path: Path) -> str:
    self._process_general_1()  # ❌ 'self' undefined in module function!

# Lines 85-91: __all__ export list
__all__ = [
    "async_read_file",
    # ...
]

# Lines 94-105: REAL FUNCTION (shadows broken stub)
async def async_read_file(file_path: Path) -> str:
    loop = asyncio.get_event_loop()
    # ... actual implementation
```

### Why This Bypasses Syntax Validation

```python
# In AgentContext.write_file_content():
compile(content, str(file_path), 'exec')  # ✅ Passes!
```

**Why it passes:**
- `self._process_general_1()` is **syntactically valid** Python
- `compile()` checks syntax, not undefined names
- The shadowing doesn't create syntax errors
- Python allows redefining functions (shadowing)

**Why it's broken:**
- `self` is undefined at runtime in module-level function
- The broken stub is dead code but wastes space
- Creates confusing code with duplicate definitions
- Massive code bloat (some files have 13 duplicates)

---

## Damage Scale

### Files with Duplicate Definitions

```
crackerjack/services/async_file_io.py:
  ⚠️ async_read_file: 2 definitions

crackerjack/services/debug.py:
  ⚠️ 11 functions with duplicates

crackerjack/services/dependency_analyzer.py:
  ⚠️ to_dict: 3 definitions

crackerjack/parsers/json_parsers.py:
  ⚠️ parse_json: 8 definitions
  ⚠️ get_issue_count: 8 definitions

crackerjack/parsers/regex_parsers.py:
  ⚠️ parse_text: 13 definitions
  ⚠️ __init__: 10 definitions

... and 26+ files total
```

### Damage Metrics

- **Files affected**: 26+
- **Total duplicate definitions**: 150+ estimated
- **Worst case**: 13 duplicates of one function
- **Compilation status**: All files compile ✅
- **Semantic status**: Massive broken code ❌

---

## Why Syntax Validation Isn't Enough

### Validation Layers

| Layer | What It Catches | What It Misses |
|-------|----------------|----------------|
| **Pre-apply** (`compile()`) | Syntax errors (unclosed parens, invalid tokens) | Semantic errors (undefined names, shadowing) |
| **Post-apply** (`compile()`) | Same as pre-apply | Same as pre-apply |
| **AST Analysis** (proposed) | Duplicate definitions, undefined names | May not catch all semantic errors |
| **Type Checking** (zuban/pyright) | Type errors, undefined attributes | Runtime behavior issues |

### Fundamental Limitation

```python
# This COMPILES but is BROKEN:
def broken_function():
    self.nonexistent_method()  # 'self' undefined at runtime

# Syntax validators see: Valid function call syntax
# Runtime sees: NameError: name 'self' is not defined
```

**compile() validates:**
- ✅ Token structure
- ✅ Grammar rules
- ✅ Expression syntax

**compile() does NOT validate:**
- ❌ Undefined names
- ❌ Type correctness
- ❌ Duplicate definitions
- ❌ Attribute existence
- ❌ Runtime behavior

---

## Test Results

### Command Run

```bash
python -m crackerjack run --ai-fix --comp --max-iterations 3
```

### What Happened

1. **Comprehensive hooks detected 76 issues** across 6 tools
2. **AI agents applied 15 fixes**
3. **Syntax validation worked**:
   - Caught: `Syntax error in AI-generated code for code_transformer.py:351: '(' was never closed`
   - **Prevented syntax errors from being written**
4. **But semantic errors slipped through**:
   - 26+ files with duplicate function definitions
   - Broken stub functions calling non-existent methods
   - Massive code bloat

### Results

```
Started with: 64 issues
Finished with: 59 issues (8% reduction)
Iterations: 2
Convergence limit reached

✅ No syntax errors reached disk (validation worked!)
❌ Massive semantic damage via shadowing (new problem!)
```

---

## Root Causes

### Problem 1: AI Agent Code Generation

AI agents are generating broken code with this pattern:

```python
# Step 1: Create broken stub with call to non-existent helper
def function_name(args):
    self._process_general_1()  # ❌ Non-existent method!

# Step 2: Define real function (shadowing the stub)
def function_name(args):
    # Actual implementation
    pass
```

### Problem 2: Limited Validation

Our current validation only catches syntax errors:

```python
# crackerjack/agents/base.py:111
try:
    compile(content, str(file_path), 'exec')  # Only checks syntax
except SyntaxError as e:
    logger.error(f"Syntax error: {e}")
    return False
```

**This misses:**
- Undefined names (`self` in module functions)
- Duplicate function definitions
- Calls to non-existent methods
- Type errors

---

## Solution Options

### Option A: Enhanced AST Validation ✅ **RECOMMENDED**

Add AST analysis to detect duplicate definitions:

```python
def validate_no_duplicate_definitions(content: str, file_path: str) -> bool:
    """Check for duplicate function/class definitions."""
    import ast

    try:
        tree = ast.parse(content)

        func_defs = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = node.name
                if name in func_defs:
                    logger.error(
                        f"❌ Duplicate definition '{name}' at line {node.lineno} "
                        f"(previous at line {func_defs[name]})"
                    )
                    return False
                func_defs[name] = node.lineno

        return True
    except Exception as e:
        logger.warning(f"Could not check for duplicates: {e}")
        return True  # Don't block on validation errors
```

**Pros:**
- Catches shadowing patterns
- Fast (AST is already parsed by compile())
- No external dependencies
- Easy to implement

**Cons:**
- Still doesn't catch all semantic errors
- May have false positives (overloaded functions in some patterns)

### Option B: Static Type Checking

Run zuban or pyright as validation:

```python
def validate_with_type_checker(content: str, file_path: str) -> bool:
    """Run type checker to catch undefined names."""
    # Write to temp file
    # Run zuban/pyright
    # Check for errors
    pass
```

**Pros:**
- Catches undefined names
- Catches type errors
- More comprehensive

**Cons:**
- Slower (type checking is expensive)
- External dependency
- May have false positives
- 20-200x slower than syntax validation (defeats performance gains)

### Option C: Linting Validation

Run ruff or pylint as validation:

```python
def validate_with_linter(content: str, file_path: str) -> bool:
    """Run linter to catch code quality issues."""
    # Write to temp file
    # Run ruff check
    # Check for errors
    pass
```

**Pros:**
- Catches many code quality issues
- Fast (ruff is Rust-powered)

**Cons:**
- May have false positives
- External dependency
- May need configuration

### Option D: Disable Problematic Agents

Disable agents that generate broken code:

- RefactoringAgent (disabling function extraction already helped)
- PatternAgent (may be generating broken patterns)

**Pros:**
- Prevents damage at source
- No performance overhead

**Cons:**
- Reduces AI-fix capabilities
- Agents might be fixable with better prompts

---

## Recommended Implementation

### Priority 1: Add AST Validation (Option A) ✅

**Implementation:**

1. Add `validate_no_duplicate_definitions()` to `AgentContext`
2. Call it after `compile()` in `write_file_content()`
3. Reject code with duplicate definitions

**Code:**

```python
# crackerjack/agents/base.py
def write_file_content(self, file_path: str | Path, content: str) -> bool:
    import logging
    import ast

    logger = logging.getLogger(__name__)

    # Layer 1: Syntax validation
    try:
        compile(content, str(file_path), 'exec')
        logger.debug(f"✅ Syntax validation passed for {file_path}")
    except SyntaxError as e:
        logger.error(f"❌ Syntax error: {e}")
        return False

    # Layer 2: AST validation for duplicates
    try:
        tree = ast.parse(content)

        definitions = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name in definitions:
                    logger.error(
                        f"❌ Duplicate definition '{node.name}' at line {node.lineno} "
                        f"(previous at line {definitions[node.name]})"
                    )
                    return False
                definitions[node.name] = node.lineno

        logger.debug(f"✅ No duplicate definitions in {file_path}")
    except Exception as e:
        logger.warning(f"⚠️ Could not check for duplicates: {e}")

    # Write file...
```

**Impact:**
- Prevents shadowing damage
- Adds <10ms overhead (AST already parsed)
- No external dependencies
- Catches the current damage pattern

### Priority 2: Investigate Root Agent Fix

**Question**: Why are AI agents generating broken stubs?

**Hypothesis**: Agents are trying to:
1. Create placeholder for refactoring
2. Add helper method calls
3. Then fill in real implementation

**Fix**: Improve agent prompts to:
- Never create stub functions
- Never call non-existent methods
- Always write complete functions

### Priority 3: Monitor for New Patterns

After implementing AST validation, monitor for:
- New semantic error patterns
- Agent behavior changes
- False positive rates

---

## Testing Protocol

### Test AST Validation

```bash
# Create test file with duplicates
cat > /tmp/test_duplicates.py << 'EOF'
def my_function():
    pass

def my_function():  # Duplicate!
    pass
EOF

# Test validation
python -c "
import ast
import sys

with open('/tmp/test_duplicates.py', 'r') as f:
    content = f.read()

tree = ast.parse(content)

definitions = {}
for node in ast.walk(tree):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        if node.name in definitions:
            print(f'❌ Duplicate: {node.name} at line {node.lineno}')
            sys.exit(1)
        definitions[node.name] = node.lineno

print('✅ No duplicates')
"
```

### Test After Implementation

```bash
# Run AI-fix with new validation
python -m crackerjack run --ai-fix --comp --max-iterations 3

# Expected behavior:
# - AI agents generate code
# - Pre-apply validation checks syntax + duplicates
# - Invalid code rejected BEFORE writing
# - No files modified with broken code
# - Git status should be clean or show only valid changes
```

---

## Success Criteria

✅ **AST validation implemented** in `AgentContext.write_file_content()`
✅ **Duplicate definitions detected** before writing to disk
✅ **AI-fix test passes** without shadowing damage
✅ **No false positives** (valid code not rejected)
✅ **Performance impact** <10ms per file
✅ **Documentation updated** with new validation layer

---

## Performance Impact

### Current Validation

- **Syntax check**: ~10-50ms per file
- **Total overhead**: <1 second per iteration

### With AST Validation

- **Syntax check**: ~10-50ms per file
- **AST duplicate check**: ~5-10ms per file (AST already parsed)
- **Total overhead**: <1.1 seconds per iteration

**ROI**: Worth the ~100ms cost to prevent massive damage cleanup.

---

## Conclusion

### What We Learned

1. ✅ **Syntax validation works perfectly** - no syntax errors reached disk
2. ❌ **Semantic validation needed** - shadowing bypasses syntax checks
3. 🎯 **AST analysis is the solution** - catches duplicates without external dependencies
4. 🚨 **AI agents need better prompts** - shouldn't generate stub functions

### Next Steps

1. ✅ **DONE**: Revert shadowing damage
2. ⏭️ **TODO**: Implement AST duplicate validation
3. ⏭️ **TODO**: Test AI-fix with enhanced validation
4. ⏭️ **TODO**: Investigate agent prompt improvements
5. ⏭️ **TODO**: Monitor for new semantic error patterns

### Final Assessment

**Current Status**: Syntax validation ✅ working, semantic validation ❌ needed

**With AST Validation**: Both syntax and shadowing errors caught ✅

**Recommendation**: Implement AST duplicate validation immediately (Priority 1).

---

**Status**: 🔴 **AWAITING FIX** - AST validation implementation required

**Files Referenced**:
- `crackerjack/agents/base.py` - Pre-apply validation location
- `crackerjack/core/autofix_coordinator.py` - Post-apply validation location
- `docs/AI_FIX_SAFETY_VALIDATION_IMPLEMENTED.md` - Previous implementation
- `docs/AI_FIX_VALIDATION_ISSUES.md` - Original syntax error analysis
