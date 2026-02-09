# AI Agent Failure Analysis - Zuban Type Errors

## Problem Summary

AI agents (ArchitectAgent primarily) are failing to fix 51 zuban/mypy type errors. All agents report "failed to fix issue" with 0 fixes applied.

---

## Error Categories (51 total)

### 1. Missing Imports (5 errors)
- `Name "async_read_file" is not defined` (agents/base.py:185)
- `Name "aiohttp" is not defined` (adapters/registry.py:371)
- `Name "logger" is not defined` (managers/test_manager.py:80, 1509)
- `Name "SessionEventEmitter" already defined` (shell/session_compat.py:56)
- `Name "ort" already defined` (services/ai/embeddings.py:17)

### 2. Wrong Type Annotations (2 errors)
- `Function "builtins.any" is not valid as a type` (core/defaults.py:261, 299)

### 3. Missing Await (8 errors)
- `Value of type "Coroutine[...]" must be used` (multiple locations)
- All are missing `await` keyword

### 4. Missing Type Annotations (3 errors)
- `Need type annotation for "definitions"` (agents/base.py:130)
- `Need type annotation for "coverage_issues"` (core/autofix_coordinator.py:379)
- `Need type annotation for "stdout_lines"` (managers/test_executor.py:543)
- `Need type annotation for "stderr_lines"` (managers/test_executor.py:634)

### 5. Attribute Errors (10 errors)
- `"AST" has no attribute "lineno"` (parsers/json_parsers.py:515, 516, 526)
- `"Self" has no attribute "lsp_client"` (managers/test_manager.py:1512)
- `"Self" has no attribute "_extract_traceback"` (services/testing/test_result_parser.py:163)
- `"Self" has no attribute "_add_fixture_parameter"` (agents/test_environment_agent.py:143)
- `"Self" has no attribute "_run_smoke_test"` (services/safe_code_modifier.py:120, 193)

### 6. Protocol/Interface Mismatches (15+ errors)
- `"Console" is missing following "ConsoleInterface" protocol member: aprint` (multiple)
- `Argument "console" to "Progress" has incompatible type "ConsoleInterface"`
- `Argument 1 to "HookExecutor" has incompatible type "Console"`

### 7. Type Incompatibilities (8+ errors)
- `Argument "file_path" to "Issue" has incompatible type "Path"; expected "str | None"`
- `Dict entry 1 has incompatible type "str": "float"; expected "str": "str | int"`

---

## Why Agents Are Failing

### Issue 1: Agent Prompts Don't Cover These Patterns

The ArchitectAgent and other agents likely don't have specific guidance for:
1. Adding missing imports
2. Fixing `builtins.any` → `typing.Any`
3. Adding `await` keywords
4. Adding type annotations

### Issue 2: Agents Try Complex Refactors

Agents might be attempting complex architectural changes when simple fixes are needed:
- `builtins.any` → `typing.Any` is a simple import/add statement
- Missing `await` is a simple keyword addition
- Missing imports are simple one-line additions

### Issue 3: Confidence Threshold Too High

Agents require `confidence ≥ 0.7` to claim success. They might be making changes but not confident enough to claim success.

---

## Recommended Improvements

### 1. Create Specialized Type-Fixing Agent

Add a new `TypeFixAgent` that specifically handles:
```python
- Missing imports: Add `from typing import Any, Dict, List`
- Wrong type hints: `any` → `Any`, `list` → `List`
- Missing await: Detect coroutines and add `await`
- Type annotations: Add `: type_here` annotations
```

### 2. Improve ArchitectAgent Prompt

Add specific guidance for common zuban patterns:

```python
## Type Error Fixing Guidelines

### Simple Fixes (DO THESE FIRST)
1. **Missing imports**: Add `from typing import Any, Dict, List, Coroutine, Awaitable`
2. **Wrong builtins**: `any` → `Any`, `list` → `List`, `dict` → `Dict`
3. **Missing await**: If line starts with `Value of type "Coroutine"`, add `await`
4. **Missing annotations**: Add `: Dict[str, Any]` or `: List[str]` as appropriate

### Import Fixing Pattern
If error says "Name X is not defined":
1. Check if X is a standard library module → Add `import X`
2. Check if X is a typo → Fix the spelling
3. Check if X is from typing → Add `from typing import X`

### Type Annotation Pattern
If error says "Need type annotation for X":
```python
# Add explicit type annotation
X: Dict[str, Any] = {}
# OR
X: List[str] = []
```

### Await Pattern
If error says "Value of type 'Coroutine' must be used":
```python
# BEFORE:
result = async_function()

# AFTER:
result = await async_function()
```

### Confidence Rules
- Simple fixes (import, await, type hint): Claim success if confidence ≥ 0.6
- Complex refactors: Only claim success if confidence ≥ 0.8
- When unsure: Apply the fix but return `success=False` with details in `fixes_applied`
```

### 3. Lower Success Threshold

Change from `confidence ≥ 0.7` to `confidence ≥ 0.5` for type errors, because:
- Type fixes are more deterministic than logic fixes
- Simple fixes (imports, await) are low-risk
- We want agents to attempt more fixes even with lower confidence

### 4. Track Partial Fixes

Even if agents can't fix ALL issues, they should:
1. Fix the easy ones (imports, await, type hints)
2. Report which fixes were applied
3. Let the next iteration handle remaining issues

---

## Implementation Priority

### HIGH PRIORITY (Do These First)

1. **Add TypeFixAgent** with specialized type error handling
2. **Update ArchitectAgent prompt** with type error patterns
3. **Lower confidence threshold** to 0.5 for type errors

### MEDIUM PRIORITY

4. **Add import statement detection** to pre-flight validation
5. **Add await keyword detection** to pre-flight validation
6. **Track cumulative fixes** across iterations

### LOW PRIORITY

7. **Fix agent coordination** to specialize by error type
8. **Add retry logic** for failed fixes
9. **Add learning from past fixes**

---

## Quick Win: Fix Simple Issues First

Let's create a script that fixes the easiest 20-30 issues:

```python
# Quick fixes to apply:
1. Add `from typing import Any, Dict, List, Coroutine, Awaitable, Optional`
   to files with builtins.any errors
2. Replace `any(` with `Any(` in type annotations
3. Replace `list[` with `List[` in type annotations
4. Replace `dict[` with `Dict[` in type annotations
5. Add missing `await` keywords before coroutines
```

This would fix ~15-20 issues immediately and reduce the burden on AI agents.
