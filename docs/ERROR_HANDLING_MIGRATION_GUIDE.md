# Error Handling Pattern Migration Guide

**Date**: February 8, 2025
**Status**: Strategic Plan with Examples
**Task**: Medium-Term Task #2 - Apply error handling pattern to remaining handlers

---

## Executive Summary

We identified **175 files** with exception handling that should be reviewed for compliance with the standardized error handling pattern defined in `ERROR_HANDLING_STANDARD.md` and `error_handling.py`. This document provides a **phased migration strategy** with concrete examples.

---

## The Standard Pattern

### ✅ CORRECT Pattern (from error_handling.py)

```python
import logging
from crackerjack.utils.error_handling import log_exception

logger = logging.getLogger(__name__)

try:
    risky_operation()
except Exception as e:
    log_exception(
        "Failed to process file",
        file_path=str(path),
        operation="parse_yaml"
    )
    raise  # or return error value
```

**Key Requirements**:
1. Use `log_exception()` or `logger.exception()` for full stack trace
2. Include meaningful context (what, where, why)
3. Never use console.print only (lost in headless mode)
4. Re-raise or return appropriate error value
5. Preserve original exception with `from e` if converting

---

## Current Issues Found

### Issue 1: Console-Only Logging ❌

**File**: `crackerjack/managers/test_manager.py:1511`
```python
# ❌ WRONG - Lost in headless mode
except Exception as e:
    self.console.print(f"[dim]LSP diagnostics failed: {e}[/dim]")
```

**Should be**:
```python
# ✅ CORRECT
except Exception as e:
    logger.exception(
        "LSP diagnostics failed",
        extra={
            "lsp_client": str(self.lsp_client),
            "operation": "diagnostics"
        }
    )
```

### Issue 2: Silent Exception Swallowing ❌

**File**: `crackerjack/services/testing/test_result_parser.py:178`
```python
# ❌ WRONG - Warning only, loses context
except Exception as e:
    logger.warning(f"Failed to parse failure section: {e}")
    return None
```

**Should be**:
```python
# ✅ CORRECT
except Exception as e:
    logger.exception(
        "Failed to parse failure section",
        extra={"section_length": len(section)}
    )
    return None
```

### Issue 3: Logging Without Context ❌

**File**: `crackerjack/services/testing/test_result_parser.py:94`
```python
# ❌ WRONG - No stack trace, no context
except json.JSONDecodeError as e:
    logger.error(f"Failed to parse pytest JSON output: {e}")
    return []
```

**Should be**:
```python
# ✅ CORRECT
except json.JSONDecodeError as e:
    logger.error(
        f"Failed to parse pytest JSON output: {e}",
        exc_info=True,  # Include stack trace
        extra={"output_length": len(output)}
    )
    return []
```

---

## Phased Migration Strategy

### Phase 1: High-Priority Services (Week 1)

**Focus**: Services that run in headless mode or process critical data

**Files** (12 high-priority):
```
crackerjack/managers/test_manager.py
crackerjack/managers/publish_manager.py
crackerjack/services/testing/coverage_manager.py
crackerjack/services/testing/test_result_parser.py
crackerjack/core/autofix_coordinator.py
crackerjack/core/proactive_workflow.py
crackerjack/services/ai/embeddings.py
crackerjack/services/lsp_client.py
crackerjack/services/command_execution_service.py
crackerjack/services/version_analyzer.py
crackerjack/services/vector_store.py
crackerjack/executors/hook_executor.py
```

**Action**: Review each exception handler, apply standard pattern.

**Estimated Time**: 2-3 hours

### Phase 2: Core Infrastructure (Week 2)

**Focus**: Coordinators, executors, core services

**Files** (15 core infrastructure):
```
crackerjack/core/phase_coordinator.py
crackerjack/core/service_watchdog.py
crackerjack/core/workflow_orchestrator.py
crackerjack/executors/async_hook_executor.py
crackerjack/executors/cached_hook_executor.py
crackerjack/executors/progress_hook_executor.py
crackerjack/executors/individual_hook_executor.py
crackerjack/executors/lsp_aware_hook_executor.py
crackerjack/executors/tool_proxy.py
crackerjack/executors/hook_lock_manager.py
crackerjack/services/batch_processor.py
crackerjack/services/parallel_executor.py
crackerjack/services/thread_safe_status_collector.py
crackerjack/services/quality/qa_orchestrator.py
crackerjack/agents/coordinator.py
```

**Estimated Time**: 2-3 hours

### Phase 3: Adapters & Agents (Week 3)

**Focus**: QA adapters, AI adapters, agents

**Files** (20 adapters & agents):
```
crackerjack/adapters/_tool_adapter_base.py
crackerjack/adapters/ai/base.py
crackerjack/adapters/ai/registry.py
crackerjack/agents/refactoring_agent.py
crackerjack/agents/test_creation_agent.py
crackerjack/agents/documentation_agent.py
crackerjack/agents/semantic_agent.py
crackerjack/agents/performance_agent.py
crackerjack/agents/security_agent.py
crackerjack/agents/test_specialist_agent.py
```

**Estimated Time**: 2-3 hours

### Phase 4: MCP Tools & CLI (Week 4)

**Focus**: MCP server tools, CLI handlers

**Files** (25 MCP & CLI):
```
crackerjack/cli/handlers/*.py (8 files)
crackerjack/mcp/tools/*.py (12 files)
crackerjack/mcp/server_core.py
crackerjack/mcp/client_runner.py
crackerjack/mcp/task_manager.py
```

**Estimated Time**: 2-3 hours

### Phase 5: Remaining Services (Ongoing)

**Focus**: All other files with exception handling

**Files**: ~100 remaining files

**Estimated Time**: 5-8 hours (spread over multiple sprints)

---

## Migration Examples

### Example 1: TestManager Migration

**Before** (crackerjack/managers/test_manager.py:1511):
```python
except Exception as e:
    self.console.print(f"[dim]LSP diagnostics failed: {e}[/dim]")
```

**After**:
```python
except Exception as e:
    logger.exception(
        "LSP diagnostics failed",
        extra={
            "lsp_client": str(self.lsp_client),
            "file_path": str(self.file_path) if self.file_path else None,
        }
    )
    # Optional: Re-raise if critical
    # raise
```

### Example 2: TestResultParser Migration

**Before** (crackerjack/services/testing/test_result_parser.py:94):
```python
except json.JSONDecodeError as e:
    logger.error(f"Failed to parse pytest JSON output: {e}")
    return []
```

**After**:
```python
except json.JSONDecodeError as e:
    logger.error(
        f"Failed to parse pytest JSON output: {e}",
        exc_info=True,
        extra={"output_length": len(output)}
    )
    return []
```

### Example 3: CoverageManager Migration

**Before** (crackerjack/services/testing/coverage_manager.py):
```python
except Exception as e:
    # Silently ignore
    return None
```

**After**:
```python
except Exception as e:
    logger.exception(
        "Failed to extract coverage from coverage.json",
        extra={"file_path": str(coverage_file_path)}
    )
    return None
```

---

## Migration Checklist

For each exception handler, verify:

- [ ] Uses `logger.exception()` or `logger.error(..., exc_info=True)`
- [ ] Includes meaningful context (what operation failed)
- [ ] Logs at appropriate level (ERROR for failures, WARNING for recoverable)
- [ ] Either re-raises or returns appropriate error value
- [ ] Never silently catches exceptions
- [ ] Preserves original exception with `from e` when re-raising

---

## Automated Validation

### Pre-Migration Check

```bash
# Find all exception handlers
grep -r "except Exception as e:" crackerjack --include="*.py" | wc -l
# Expected: ~175 occurrences

# Find handlers without logger
grep -r "except Exception as e:" crackerjack --include="*.py" -A 2 | grep -v "logger\." | wc -l
# These need migration
```

### Post-Migration Validation

```bash
# Run tests to ensure no behavior changes
python -m pytest tests/ -v

# Check all handlers now use logger
grep -r "except Exception as e:" crackerjack --include="*.py" -A 2 | grep "logger\." | wc -l
# Should be ~175 (all migrated)
```

---

## Benefits of Migration

### Immediate Benefits

1. **Debuggability**: Full context and stack traces for troubleshooting
2. **Observability**: Persistent logs in headless CI/CD environments
3. **Consistency**: Predictable error handling patterns across codebase
4. **Maintainability**: Easier onboarding for new developers

### Long-Term Benefits

1. **Reduced Debugging Time**: Rich context reduces investigation time
2. **Better Error Analytics**: Structured logs enable error aggregation
3. **Improved Reliability**: No silent failures, all errors logged
4. **Production Readiness**: Professional-grade error handling

---

## Risk Mitigation

### Low Risk Changes

- Adding `exc_info=True` to existing logger calls
- Adding context via `extra` dict
- Converting `console.print` to `logger.error`

**Testing**: Run existing test suite to verify no behavior changes

### Medium Risk Changes

- Re-raising exceptions that were previously swallowed
- Adding new logging where none existed

**Testing**: Manual verification in development environment

### High Risk Changes

- Changing exception types (converting ValueError to custom error)
- Modifying error handling flow

**Testing**: Full QA regression testing required

**Recommendation**: Focus on Low-Medium risk changes for now.

---

## Success Metrics

### Phase 1 Completion Criteria

- [ ] All 12 high-priority files reviewed
- [ ] 90%+ of exception handlers use standard pattern
- [ ] All handlers include context information
- [ ] Zero console-only error logs
- [ ] Test suite still passing (no behavior changes)

### Overall Completion Criteria

- [ ] All 175 files reviewed
- [ ] 95%+ compliance with error handling standard
- [ ] Documentation updated with examples
- [ ] Team training completed

---

## Tools & Utilities

### Helper Functions (from error_handling.py)

```python
from crackerjack.utils.error_handling import (
    log_exception,
    log_and_return_error,
    safe_execute,
    get_error_context,
    raise_with_context,
    format_error_message,
    handle_file_operation_error,
)
```

### Usage Examples

```python
# Pattern 1: Log and return error
try:
    config = load_config(path)
except Exception as e:
    log_and_return_error(
        e,
        "Failed to load configuration",
        file_path=str(path)
    )
    return None

# Pattern 2: Safe execute with default
result = safe_execute(
    parse_json,
    json_content,
    error_message="Failed to parse JSON",
    default_return={},
    file_path=str(path)
)

# Pattern 3: File operations
try:
    content = Path(file_path).read_text()
except OSError as e:
    handle_file_operation_error(e, file_path, "read", reraise=True)
```

---

## Training Materials

### Team Workshop Outline (1 hour)

1. **Why Standard Error Handling Matters** (10 min)
   - Debuggability in CI/CD
   - Silent failures cost
   - Real-world incident examples

2. **The Standard Pattern** (15 min)
   - Core requirements
   - Code examples
   - Anti-patterns to avoid

3. **Hands-On Migration** (25 min)
   - Select 3 files from Phase 1
   - Apply pattern as group
   - Code review and discussion

4. **Q&A** (10 min)

---

## Conclusion

The error handling pattern migration is a **systematic quality improvement** that will pay dividends in debuggability and maintainability. By taking a **phased approach** and focusing on **high-priority files first**, we can achieve 95%+ compliance over 4-5 weeks without disrupting development velocity.

**Current Status**: Strategic plan complete, ready to begin Phase 1 execution.

**Next Steps**:
1. Get team approval on migration strategy
2. Schedule Phase 1 migration sprint
3. Create pull request template for error handling changes
4. Begin with high-priority services

---

**Last Updated**: 2025-02-08
**Owner**: Architecture Team
**Status**: Ready for Execution
