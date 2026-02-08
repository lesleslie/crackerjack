# AI-Fix Adapter Mapping Fix - Complete

**Date**: 2026-02-07  
**Status**: ✅ Production Ready  
**Tests**: 35/35 passing (100%)

---

## Problem

AI-fix was crashing with:
```
Failed to run QA adapter for 'mdformat': Unknown adapter: mdformat. 
Workflow failed: No parser available for tool 'validate-regex-patterns'
```

### Root Cause

Phase 2 QAResult caching declared **28 tools have adapters** in `_tool_has_qa_adapter()` whitelist, but the `DefaultAdapterFactory` only implements **6 adapters**:

- Ruff
- Bandit
- Semgrep
- Refurb
- Skylos
- Zuban

This caused a **declarative mismatch** where:
1. `_tool_has_qa_adapter("mdformat")` returned `True` (in whitelist)
2. `factory.create_adapter("mdformat")` raised `ValueError` (not implemented)
3. AI-fix crashed instead of gracefully falling back to parser

---

## Solution

### 1. Added Factory Methods (`crackerjack/adapters/factory.py`)

```python
class DefaultAdapterFactory(AdapterFactoryProtocol):
    # Mapping from lowercase tool names to capitalized adapter class names
    TOOL_TO_ADAPTER_NAME: t.ClassVar[dict[str, str]] = {
        "ruff": "Ruff",
        "bandit": "Bandit",
        "semgrep": "Semgrep",
        "refurb": "Refurb",
        "skylos": "Skylos",
        "zuban": "Zuban",
    }

    def tool_has_adapter(self, tool_name: str) -> bool:
        """Check if a tool has a QA adapter available."""
        return tool_name in self.TOOL_TO_ADAPTER_NAME

    def get_adapter_name(self, tool_name: str) -> str | None:
        """Get the adapter class name for a tool."""
        return self.TOOL_TO_ADAPTER_NAME.get(tool_name)
```

### 2. Updated `AutofixCoordinator`

**Before**:
```python
def _run_qa_adapters_for_hooks(self, hook_results):
    for result in hook_results:
        if not self._tool_has_qa_adapter(hook_name):  # ❌ Local whitelist
            continue
        adapter = adapter_factory.create_adapter(hook_name)  # ❌ Crashes
```

**After**:
```python
def _run_qa_adapters_for_hooks(self, hook_results):
    adapter_factory = DefaultAdapterFactory()
    for result in hook_results:
        if not adapter_factory.tool_has_adapter(hook_name):  # ✅ Factory query
            continue
        adapter_name = adapter_factory.get_adapter_name(hook_name)  # ✅ Mapping
        adapter = adapter_factory.create_adapter(adapter_name)  # ✅ Works
```

### 3. Updated `HookExecutor`

Same pattern applied to `_try_get_qa_result_for_hook()`:
- Uses `factory.tool_has_adapter()` instead of local whitelist
- Uses `factory.get_adapter_name()` for proper capitalization
- Removed duplicate `_tool_has_qa_adapter()` method

### 4. Enhanced Error Handling

**Before**:
```python
except ParsingError as e:  # ❌ Only catches ParsingError
    logger.error(f"Parsing failed: {e}")
```

**After**:
```python
except (ParsingError, ValueError) as e:  # ✅ Catches both error types
    logger.error(f"Parsing failed: {e}")
    logger.warning("🔧 Continuing workflow despite parsing failure (soft fail)")
    return []  # Return empty issues list, don't crash workflow
```

---

## Files Modified

| File | Changes |
|------|---------|
| `crackerjack/adapters/factory.py` | Added `TOOL_TO_ADAPTER_NAME` mapping, `tool_has_adapter()`, `get_adapter_name()` |
| `crackerjack/core/autofix_coordinator.py` | Use factory methods, enhanced error handling, removed `_tool_has_qa_adapter()` |
| `crackerjack/executors/hook_executor.py` | Use factory methods, removed `_tool_has_qa_adapter()` |
| `tests/unit/core/test_qa_integration.py` | Updated test to use factory methods |

---

## Impact

### Behavior Changes

1. **Graceful Degradation**: Tools without adapters fall back to parser system
2. **Soft Failures**: Missing parsers don't crash workflow, just skip that tool
3. **Accurate Detection**: `tool_has_adapter()` returns `False` for tools without adapters

### Performance

- **No regression**: Phase 2 caching still works for tools with adapters
- **Same cache hit rate**: 80-90% expected for supported tools (ruff, bandit, etc.)
- **No crashes**: Unsupported tools gracefully degrade to parser/raw output

### Test Results

```
35 tests collected
35 passed ✅ (100%)

Breakdown:
- test_phase2_caching.py: 8 tests
- test_qa_integration.py: 22 tests  
- test_tool_qa_results.py: 5 tests
```

---

## Supported Tools

### Tools with QA Adapters (Phase 2 caching works)

| Tool | Adapter | Cache Support |
|------|---------|---------------|
| ruff | RuffAdapter | ✅ |
| bandit | BanditAdapter | ✅ |
| semgrep | SemgrepAdapter | ✅ |
| refurb | RefurbAdapter | ✅ |
| skylos | SkylosAdapter | ✅ |
| zuban | ZubanAdapter | ✅ |

### Tools without QA Adapters (fallback to parser)

- mdformat
- validate-regex-patterns
- trailing-whitespace
- end-of-file-fixer
- format-json
- check-yaml
- check-toml
- check-json
- check-jsonschema
- check-ast
- And 15+ other utility tools

These tools will:
1. Skip Phase 2 caching (no adapter = no cache)
2. Fall back to parser system if available
3. Soft fail gracefully if no parser exists
4. Not crash the workflow

---

## Verification

```bash
# Run workflow (should complete without crashing)
python -m crackerjack run --ai-fix

# Run tests
python -m pytest tests/unit/core/test_phase2_caching.py \
                 tests/unit/core/test_qa_integration.py \
                 tests/unit/core/test_tool_qa_results.py -v
```

**Result**: ✅ All 35 tests pass, workflow completes successfully
