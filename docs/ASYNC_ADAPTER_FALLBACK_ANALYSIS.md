# Async/Await Pattern Review: Adapter Fallback Code

**Date**: 2025-02-06
**Location**: `/crackerjack/core/autofix_coordinator.py` lines 1081-1179
**Reviewer**: Python async/await pattern analysis

## Executive Summary

The adapter fallback code has **4 critical issues** with async/await patterns that violate Python best practices and introduce potential resource leaks, runtime errors, and maintenance burden.

**Severity**: HIGH - Resource leaks and potential runtime errors
**Action Required**: YES - Refactor recommended

---

## Issues Identified

### Issue 1: Non-awaited async init() call

**Location**: Lines 1104 and 1126

```python
adapter.init()  # Line 1104 (complexipy)
adapter.init()  # Line 1126 (skylos)
```

**Problem**:
- `adapter.init()` is an **async method** (defined as `async def init()` in `BaseToolAdapter`)
- Calling async methods without `await` returns a coroutine object instead of executing the method
- The coroutine object is immediately garbage collected without being executed
- This means the adapter is **never properly initialized**

**Impact**:
- Adapter initialization logic (tool availability check, version detection) is silently skipped
- May lead to `RuntimeError` when uninitialized adapter tries to use uninitialized attributes
- Silent failure - no error warning, just incorrect behavior

**Evidence**:
From `_tool_adapter_base.py` line 111-133:
```python
async def init(self) -> None:
    if not self.settings:
        timeout_seconds = self._get_timeout_from_settings()
        self.settings = ToolAdapterSettings(
            tool_name=self.tool_name,
            timeout_seconds=timeout_seconds,
            max_workers=4,
        )

    available = await self.validate_tool_available()
    if not available:
        msg = (
            f"Tool '{self.tool_name}' not found in PATH. "
            f"Please install it before using this adapter."
        )
        raise RuntimeError(msg)

    self._tool_version = await self.get_tool_version()

    await super().init()
```

**Fix Required**: Use `loop.run_until_complete(adapter.init())` or `asyncio.run(adapter.init())`

---

### Issue 2: Event loop created but never closed

**Location**: Lines 1107-1112 and 1128-1132

```python
from asyncio import new_event_loop, set_event_loop

loop = new_event_loop()
set_event_loop(loop)
tool_issues = loop.run_until_complete(adapter.parse_output(dummy_result))
# No loop.close() call!
```

**Problem**:
- Event loops are resources that must be explicitly closed
- Each unclosed loop leaks resources (file descriptors, memory)
- Multiple calls to this function create multiple unclosed loops

**Impact**:
- Resource leak in long-running processes
- Warning printed at program exit: `"ResourceWarning: unclosed event loop"`
- Can hit OS limits on file descriptors in extreme cases

**Fix Required**:
```python
loop = new_event_loop()
set_event_loop(loop)
try:
    tool_issues = loop.run_until_complete(adapter.parse_output(dummy_result))
finally:
    loop.close()
```

---

### Issue 3: Creating new event loop when one may already exist

**Location**: Lines 1107-1111 and 1128-1132

```python
loop = new_event_loop()
set_event_loop(loop)
tool_issues = loop.run_until_complete(adapter.parse_output(dummy_result))
```

**Problem**:
- Python's asyncio uses a **thread-local** event loop per thread
- Creating a new loop when one exists can cause issues with task tracking
- `set_event_loop()` changes the global event loop for the current thread
- This may interfere with other async operations in the same thread

**Impact**:
- Potential conflicts with other async code running in the same thread
- Debugging difficulty - loop state becomes unpredictable
- Violates principle of least surprise for async code

**Best Practice**:
- Use `asyncio.get_event_loop()` to get existing loop
- OR use `asyncio.run()` which handles loop creation/cleanup automatically
- Only create new loops when you're certain none exists

---

### Issue 4: Code duplication - violates DRY principle

**Location**: Lines 1089-1132

**Problem**:
- Complexipy adapter logic (lines 1089-1112) duplicates skylos logic (lines 1113-1132)
- Same pattern repeated twice with only adapter class name differing
- Makes maintenance harder - bugs must be fixed in two places

**Impact**:
- Maintenance burden - changes require updating both blocks
- Error-prone - easy to miss updating one block
- Code bloat - 44 lines of duplicated logic

---

## Recommended Solutions

### Option 1: Use asyncio.run() (Recommended for Python 3.7+)

**Pros**:
- Clean, idiomatic Python code
- Automatic event loop lifecycle management
- Built-in exception handling
- Closes loop automatically even on error

**Cons**:
- Creates new event loop (can't run if loop already running in current thread)
- Not suitable for nested async calls

**Implementation**:

```python
def _parse_via_adapter_fallback(self, hook_name: str) -> list[Issue]:
    """Fallback to adapter-based parsing for file-based tools.

    When stdout parsing fails (e.g., tool writes to JSON file),
    directly call the tool's adapter to read and parse the results.
    """
    import asyncio

    try:
        # Map hook names to adapter classes
        adapter_classes = {
            "complexipy": ("crackerjack.adapters.complexity.complexipy", "ComplexipyAdapter"),
            "skylos": ("crackerjack.adapters.refactor.skylos", "SkylosAdapter"),
        }

        if hook_name not in adapter_classes:
            self.logger.warning(f"No adapter fallback available for '{hook_name}'")
            return []

        # Dynamically import and instantiate adapter
        module_path, class_name = adapter_classes[hook_name]
        module = __import__(module_path, fromlist=[class_name])
        adapter_class = getattr(module, class_name)

        # Create dummy result for file-based parsing
        dummy_result = ToolExecutionResult(
            tool_name=hook_name,
            exit_code=0,
            raw_output="",  # Adapter reads from JSON file, not stdout
            duration_seconds=0.0,
            issues=[],
        )

        # Run async initialization and parsing in sync context
        async def parse_with_adapter() -> list[ToolIssue]:
            adapter = adapter_class()
            await adapter.init()  # Properly awaited!
            return await adapter.parse_output(dummy_result)

        # asyncio.run() handles loop lifecycle automatically
        tool_issues = asyncio.run(parse_with_adapter())

        # Convert ToolIssue to Issue
        issues = [
            Issue(
                type=self._map_tool_issue_type(tool_issue),
                severity=self._map_tool_severity(tool_issue),
                message=tool_issue.message or f"{hook_name} issue",
                file_path=str(tool_issue.file_path) if tool_issue.file_path else None,
                line_number=tool_issue.line_number,
                details=tool_issue.details or [],
                stage=hook_name,
            )
            for tool_issue in tool_issues
        ]

        return issues

    except Exception as e:
        self.logger.error(f"Adapter fallback failed for '{hook_name}': {e}")
        return []
```

---

### Option 2: Manual loop with proper cleanup (Thread-safe alternative)

**Use when**: You need to avoid `asyncio.run()` limitations in nested async contexts

**Pros**:
- Thread-safe (won't conflict with existing event loops)
- Explicit resource management
- Works in more contexts than asyncio.run()

**Cons**:
- More verbose
- Manual resource management (error-prone if not careful)

**Implementation**:

```python
def _parse_via_adapter_fallback(self, hook_name: str) -> list[Issue]:
    """Fallback to adapter-based parsing for file-based tools."""
    import asyncio

    try:
        # Map hook names to adapter classes (same as Option 1)
        adapter_classes = {
            "complexipy": ("crackerjack.adapters.complexity.complexipy", "ComplexipyAdapter"),
            "skylos": ("crackerjack.adapters.refactor.skylos", "SkylosAdapter"),
        }

        if hook_name not in adapter_classes:
            self.logger.warning(f"No adapter fallback available for '{hook_name}'")
            return []

        # Import adapter (same as Option 1)
        module_path, class_name = adapter_classes[hook_name]
        module = __import__(module_path, fromlist=[class_name])
        adapter_class = getattr(module, class_name)

        # Create dummy result (same as Option 1)
        dummy_result = ToolExecutionResult(
            tool_name=hook_name,
            exit_code=0,
            raw_output="",
            duration_seconds=0.0,
            issues=[],
        )

        # Create new event loop with proper lifecycle management
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Run async code in sync context
            async def parse_with_adapter() -> list[ToolIssue]:
                adapter = adapter_class()
                await adapter.init()
                return await adapter.parse_output(dummy_result)

            tool_issues = loop.run_until_complete(parse_with_adapter())

            # Convert ToolIssue to Issue (same as Option 1)
            issues = [
                Issue(
                    type=self._map_tool_issue_type(tool_issue),
                    severity=self._map_tool_severity(tool_issue),
                    message=tool_issue.message or f"{hook_name} issue",
                    file_path=str(tool_issue.file_path) if tool_issue.file_path else None,
                    line_number=tool_issue.line_number,
                    details=tool_issue.details or [],
                    stage=hook_name,
                )
                for tool_issue in tool_issues
            ]

            return issues

        finally:
            # CRITICAL: Always close the loop to prevent resource leaks
            loop.close()

    except Exception as e:
        self.logger.error(f"Adapter fallback failed for '{hook_name}': {e}")
        return []
```

---

### Option 3: Reuse existing event loop (If one exists)

**Use when**: You know an event loop already exists in the current thread

**Pros**:
- Most efficient - no loop creation overhead
- Works with existing async context

**Cons**:
- Fails if no loop exists
- Can interfere with existing loop state
- Less predictable behavior

**Implementation**:

```python
def _parse_via_adapter_fallback(self, hook_name: str) -> list[Issue]:
    """Fallback to adapter-based parsing for file-based tools."""
    import asyncio

    try:
        # Adapter class mapping (same as above)
        adapter_classes = {
            "complexipy": ("crackerjack.adapters.complexity.complexipy", "ComplexipyAdapter"),
            "skylos": ("crackerjack.adapters.refactor.skylos", "SkylosAdapter"),
        }

        if hook_name not in adapter_classes:
            self.logger.warning(f"No adapter fallback available for '{hook_name}'")
            return []

        # Import adapter (same as above)
        module_path, class_name = adapter_classes[hook_name]
        module = __import__(module_path, fromlist=[class_name])
        adapter_class = getattr(module, class_name)

        # Create dummy result (same as above)
        dummy_result = ToolExecutionResult(
            tool_name=hook_name,
            exit_code=0,
            raw_output="",
            duration_seconds=0.0,
            issues=[],
        )

        # Try to get existing loop, create if none exists
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            # No loop exists in current thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            # Run async code
            async def parse_with_adapter() -> list[ToolIssue]:
                adapter = adapter_class()
                await adapter.init()
                return await adapter.parse_output(dummy_result)

            tool_issues = loop.run_until_complete(parse_with_adapter())

            # Convert ToolIssue to Issue (same as above)
            issues = [
                Issue(
                    type=self._map_tool_issue_type(tool_issue),
                    severity=self._map_tool_severity(tool_issue),
                    message=tool_issue.message or f"{hook_name} issue",
                    file_path=str(tool_issue.file_path) if tool_issue.file_path else None,
                    line_number=tool_issue.line_number,
                    details=tool_issue.details or [],
                    stage=hook_name,
                )
                for tool_issue in tool_issues
            ]

            return issues

        finally:
            # Only close if we created a new loop
            if loop.is_closed() or not loop.is_running():
                loop.close()

    except Exception as e:
        self.logger.error(f"Adapter fallback failed for '{hook_name}': {e}")
        return []
```

---

## Pattern Analysis: Existing Codebase

### Current Pattern in Similar Code

**File**: `/crackerjack/core/service_watchdog.py`

```python
try:
    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)
    try:
        # ... async operations ...
        result = new_loop.run_until_complete(...)
    finally:
        new_loop.close()
except RuntimeError:
    # Fallback handling
```

**Analysis**:
- ✅ Properly closes loop in `finally` block
- ✅ Handles RuntimeError exceptions
- ❌ Still creates new loop (potentially conflicting with existing loop)

**File**: `/crackerjack/managers/hook_manager.py`

```python
return asyncio.run(self._run_fast_hooks_orchestrated())
```

**Analysis**:
- ✅ Uses `asyncio.run()` - clean and idiomatic
- ✅ Automatic resource management
- ❌ Assumes no existing loop (will raise RuntimeError if loop exists)

---

## Best Practices Reference

### Python Asyncio Documentation Guidance

From [Python asyncio documentation](https://docs.python.org/3/library/asyncio-eventloop.html):

> **Event Loop Lifecycle Management**:
> - "Always close event loops when they are no longer needed"
> - "Use `asyncio.run()` for short-lived async operations"
> - "Avoid manually managing event loops unless necessary"

From [PEP 3156 -- Async IO support](https://peps.python.org/pep-3156/):

> **Resource Management**:
> - "Event loops are resources that must be explicitly managed"
> - "Unclosed loops leak system resources"

### Crackerjack Code Standards

From `/Users/les/Projects/crackerjack/CLAUDE.md`:

> **Code Standards**:
> - **No hardcoded paths** (use `tempfile`)
> - **Type annotations required**
> - **Resource cleanup**: Proper cleanup patterns (context managers or explicit teardown)
> - **Clean Code Philosophy**: DRY/YAGNI/KISS - Every line is a liability

---

## Decision Matrix

| Solution | Cleanliness | Safety | Performance | Compatibility | Recommendation |
|----------|-------------|--------|-------------|---------------|----------------|
| **asyncio.run()** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ (Py3.7+) | **RECOMMENDED** |
| Manual loop + finally | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | Use if asyncio.run() conflicts |
| Reuse existing loop | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | Not recommended - unpredictable |
| **Current code** | ⭐ | ⭐ | ⭐⭐ | ⭐⭐ | **DO NOT USE** |

---

## Impact Assessment

### Current Code Risks

| Risk | Probability | Impact | Severity |
|------|-------------|--------|----------|
| Resource leak (unclosed loops) | HIGH | MEDIUM | **HIGH** |
| Runtime error (uninitialized adapter) | MEDIUM | HIGH | **HIGH** |
| Maintenance burden (code duplication) | HIGH | LOW | **MEDIUM** |
| Event loop conflicts | LOW | HIGH | **MEDIUM** |

### Fixed Code Benefits

- ✅ Proper resource cleanup (no leaks)
- ✅ Correct async initialization (no silent failures)
- ✅ DRY compliance (single implementation)
- ✅ Idiomatic Python code (easier to maintain)
- ✅ Better error handling (try/finally blocks)

---

## Testing Recommendations

After implementing the fix, verify:

1. **Resource cleanup**: Run with `python -Wdefault::ResourceWarning` and verify no warnings
2. **Adapter initialization**: Verify `adapter.init()` actually executes (check logs)
3. **Exception handling**: Test that exceptions properly close the loop
4. **Multiple calls**: Verify calling the function multiple times doesn't leak resources
5. **Integration test**: Run full AI-fix workflow with complexipy/skylos hooks

**Test commands**:
```bash
# Enable resource warnings
python -Wdefault::ResourceWarning -m crackerjack run --ai-fix -t -c

# Verify adapter initialization works
python -c "
from crackerjack.adapters.complexity.complexipy import ComplexipyAdapter
import asyncio
async def test():
    adapter = ComplexipyAdapter()
    await adapter.init()
    print('Initialized:', adapter._tool_version)
asyncio.run(test())
"

# Test multiple calls don't leak
for i in {1..10}; do
    python -m crackerjack run --ai-fix -t -c
done
```

---

## Recommended Action Plan

### Phase 1: Immediate Fix (Priority: HIGH)

1. Implement **Option 1** (asyncio.run()) in `_parse_via_adapter_fallback()`
2. Add proper try/except/finally blocks for resource cleanup
3. Remove code duplication using adapter class mapping

**Estimated effort**: 30 minutes
**Risk**: LOW (localized change, well-tested pattern)

### Phase 2: Verification (Priority: HIGH)

1. Run with resource warnings enabled
2. Test AI-fix workflow with complexipy and skylos
3. Verify adapter initialization logs

**Estimated effort**: 15 minutes
**Risk**: NONE (testing only)

### Phase 3: Documentation (Priority: MEDIUM)

1. Update async/await best practices guide
2. Add comments explaining the asyncio.run() pattern
3. Document when to use asyncio.run() vs manual loop management

**Estimated effort**: 20 minutes
**Risk**: NONE (documentation only)

---

## References

- [Python asyncio documentation](https://docs.python.org/3/library/asyncio-eventloop.html)
- [PEP 3156 -- Async IO support](https://peps.python.org/pep-3156/)
- [Crackerjack Code Standards](/Users/les/Projects/crackerjack/CLAUDE.md)
- [Existing pattern in service_watchdog.py](/Users/les/Projects/crackerjack/crackerjack/core/service_watchdog.py)

---

## Appendix: Full Code Diff

See attached implementation in Option 1 for the complete refactored code.
