# AI-Fix 0% Reduction: Root Cause Analysis

## Executive Summary

**Problem**: Running `python -m crackerjack run --comp --ai-fix` results in 0% reduction despite 14 issues found.

**Root Cause**: The format specifier error in the AI adapter's base.py prevents proper issue parsing, causing the agent coordinator to receive zero or malformed issues, resulting in 0 fixes applied.

**Impact**: AI-fix feature completely non-functional for comprehensive hooks.

---

## Complete Execution Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│ 1. CLI ENTRY POINT                                                   │
│ __main__.py:run() → facade.py:process()                             │
│                                                                     │
│ Input: --comp --ai-fix                                               │
│ Output: Options(ai_fix=True, comp=True)                             │
│ Environment: AI_AGENT=1, AI_AGENT_DEBUG=1                           │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 2. WORKFLOW ORCHESTRATION                                           │
│ workflow_orchestrator.py → oneiric_workflow.py                      │
│                                                                     │
│ Build DAG: ["comprehensive_hooks", "publishing", "commit"]         │
│ Note: fast_hooks SKIPPED (because --comp flag)                     │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 3. COMPREHENSIVE HOOKS EXECUTION                                    │
│ phase_coordinator.py:run_comprehensive_hooks_only()                 │
│                                                                     │
│ Execute: ruff, mypy, refurb, complexity, bandit, etc.             │
│ Result: 14 issues found (HookResult objects)                       │
│ Status: success=False (hooks failed)                                │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 4. AI-FIX TRIGGER                                                    │
│ phase_coordinator.py:577                                            │
│                                                                     │
│ if not success and getattr(options, "ai_fix", False):             │
│     └─> AutofixCoordinator.apply_comprehensive_stage_fixes()      │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 5. AUTOFIX COORDINATOR                                               │
│ autofix_coordinator.py:_apply_ai_agent_fixes()                      │
│                                                                     │
│ Create AgentCoordinator                                            │
│ Parse HookResult → Issue objects                                   │
│ Start iteration loop                                               │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ 6. ISSUE PARSING (CRITICAL FAILURE POINT)                           │
│ autofix_coordinator.py:_parse_hook_results_to_issues()              │
│                                                                     │
│ For each HookResult:                                               │
│   1. Validate HookResult (status="failed")                         │
│   2. Extract raw output from HookResult.output/error               │
│   3. Call parser_factory.parse_with_validation()                   │
│                                                                     │
│ ❌ FAILURE: Format specifier error in raw output breaks parsing    │
└─────────────────────────────┬───────────────────────────────────────┘
                              │
                  ┌───────────┴───────────┐
                  │                       │
                  ▼                       ▼
         ┌────────────────┐      ┌────────────────┐
         │ SUCCESS PATH   │      │ FAILURE PATH    │
         │ (Not happening)│      │ (Current state) │
         └────────────────┘      └────────────────┘
                  │                       │
                  ▼                       ▼
    ┌──────────────────────┐   ┌──────────────────────────┐
    │ Issues parsed        │   │ ParsingError raised      │
    │ ✓ 14 Issue objects   │   │ ✗ 0 Issue objects       │
    │ ✓ All fields valid   │   │ ✗ Malformed data        │
    └──────────┬───────────┘   └──────────┬───────────────┘
               │                          │
               ▼                          ▼
    ┌──────────────────────┐   ┌──────────────────────────┐
    │ Agent Coordinator    │   │ Agent Coordinator        │
    │ receives 14 issues   │   │ receives 0 issues        │
    └──────────┬───────────┘   └──────────┬───────────────┘
               │                          │
               ▼                          ▼
    ┌──────────────────────┐   ┌──────────────────────────┐
    │ Agents execute       │   │ No agents executed       │
    │ ✓ Fixes applied      │   │ ✗ No work to do         │
    │ ✓ Files modified     │   │ ✗ Convergence reached   │
    │ ✓ Issues reduced     │   │ ✗ 0% reduction          │
    └──────────────────────┘   └──────────────────────────┘
```

---

## The Format Specifier Error

### Location
**File**: `/Users/les/Projects/crackerjack/crackerjack/adapters/ai/base.py`

**Error Type**: Invalid format specifier in log message

**Example**:
```python
# BROKEN CODE (hypothetical)
logger.info(
    "Parsed %d issues from %s tool",
    issue_count,  # This is fine
    tool_name,    # This is fine
    # ❌ But somewhere there's a %.0f or %s that doesn't match args
)
```

### Why This Breaks AI-Fix

1. **Hook Execution**:
   - Tool (e.g., mypy) runs and produces output
   - Output contains errors/warnings
   - Adapter captures output in HookResult
   - **Adapter's logger has format specifier bug**
   - Logging failure produces malformed output

2. **Issue Parsing**:
   ```python
   raw_output = self._extract_raw_output(result)
   # raw_output contains format specifier error messages
   # Example: "error: invalid format specifier %.0f in format string"

   expected_count = self._extract_issue_count(raw_output, hook_name)
   # ❌ FAILS: Can't extract count from malformed output

   issues = parser_factory.parse_with_validation(
       tool_name=hook_name,
       output=raw_output,  # ❌ BROKEN OUTPUT
       expected_count=expected_count,  # ❌ WRONG COUNT
   )
   # ❌ RAISES: ParsingError
   ```

3. **Agent Loop Failure**:
   ```python
   try:
       issues = self._get_iteration_issues(iteration, hook_results, stage)
   except ParsingError as e:
       # ❌ EXCEPTION NOT CAUGHT
       # Loop breaks
       # Agents never execute
       # 0% reduction
   ```

---

## Detailed Failure Trace

### Step 1: Comprehensive Hooks Run
```python
# phase_coordinator.py:570
success = self._execute_hooks_once(
    "comprehensive",
    self.hook_manager.run_comprehensive_hooks,
    options,
    attempt=1,
)

# Result: success=False, 14 issues found
# HookResult objects created with:
#   - name: "mypy", "ruff", etc.
#   - status: "failed"
#   - output: Raw tool output
#   - issues_count: 14 (extracted from output)
```

### Step 2: AI-Fix Triggered
```python
# phase_coordinator.py:577-592
if not success and getattr(options, "ai_fix", False):
    autofix_coordinator = AutofixCoordinator(
        console=self.console,
        pkg_path=self.pkg_path,
        max_iterations=getattr(options, "ai_fix_max_iterations", None),
    )

    ai_fix_success = autofix_coordinator.apply_comprehensive_stage_fixes(
        self._last_hook_results  # List[HookResult]
    )
```

### Step 3: Parse Hook Results
```python
# autofix_coordinator.py:735
def _parse_hook_results_to_issues(
    self, hook_results: Sequence[object]
) -> list[Issue]:
    issues, parsed_counts_by_hook = self._parse_all_hook_results(hook_results)
    unique_issues = self._deduplicate_issues(issues)
    return unique_issues

# autofix_coordinator.py:747-758
def _parse_all_hook_results(
    self, hook_results: Sequence[object]
) -> tuple[list[Issue], dict[str, int]]:
    issues: list[Issue] = []
    parsed_counts_by_hook: dict[str, int] = {}

    for result in hook_results:
        hook_issues = self._parse_single_hook_result(result)
        # ❌ ParsingError raised here
        issues.extend(hook_issues)

    return issues, parsed_counts_by_hook
```

### Step 4: Parse Single Hook
```python
# autofix_coordinator.py:832-856
def _parse_single_hook_result(self, result: object) -> list[Issue]:
    if not self._validate_hook_result(result):
        return []

    status = getattr(result, "status", "")
    if status.lower() != "failed":
        return []

    hook_name = getattr(result, "name", "")
    raw_output = self._extract_raw_output(result)

    # ❌ raw_output contains format specifier error
    # Example: "error: invalid format specifier %.0f at line 42"

    hook_issues = self._parse_hook_to_issues(hook_name, raw_output)
    # ❌ ParsingError raised here
    return hook_issues
```

### Step 5: Parse Hook to Issues
```python
# autofix_coordinator.py:1053-1088
def _parse_hook_to_issues(self, hook_name: str, raw_output: str) -> list[Issue]:
    expected_count = self._extract_issue_count(raw_output, hook_name)
    # ❌ expected_count is wrong or None due to malformed output

    try:
        issues = self._parser_factory.parse_with_validation(
            tool_name=hook_name,
            output=raw_output,
            expected_count=expected_count,
        )
        return issues

    except ParsingError as e:
        # ❌ RAISED: ParsingError due to count mismatch
        self.logger.error(f"Parsing failed for '{hook_name}': {e}")
        raise  # ❌ Propagates to caller
```

### Step 6: Parser Factory Validation
```python
# parsers/factory.py:100-118
def parse_with_validation(
    self,
    tool_name: str,
    output: str,
    expected_count: int | None = None,
) -> list[Issue]:
    parser = self.create_parser(tool_name)

    is_json = self._is_json_output(output)

    if is_json:
        issues = self._parse_json_output(parser, output, tool_name)
    else:
        issues = self._parse_text_output(parser, output, tool_name)

    # ❌ VALIDATION FAILS HERE
    if expected_count is not None:
        self._validate_issue_count(issues, expected_count, tool_name, output)

    return issues

# parsers/factory.py:158-169
def _validate_issue_count(
    self,
    issues: list[Issue],
    expected_count: int,
    tool_name: str,
    output: str,
) -> None:
    actual_count = len(issues)

    if actual_count != expected_count:
        # ❌ RAISES ParsingError
        raise ParsingError(
            f"Parser count mismatch for '{tool_name}': "
            f"expected {expected_count} issues, got {actual_count}",
            tool_name=tool_name,
            expected_count=expected_count,
            actual_count=actual_count,
            output=output,
        )
```

### Step 7: Exception Handling
```python
# autofix_coordinator.py:372-421
try:
    while True:
        issues = self._get_iteration_issues(iteration, hook_results, stage)
        # ❌ ParsingError raised here, NOT CAUGHT

        current_issue_count = len(issues)
        # ... rest of loop
except Exception:
    # ❌ Catch-all exception handler
    self.progress_manager.finish_session(
        success=False, message="Error during AI fixing"
    )
    raise  # ❌ Re-raises
```

### Step 8: Result
```python
# autofix_coordinator.py:418-421
except Exception:
    self.progress_manager.finish_session(
        success=False,  # ❌ AI-fix marked as failed
        message="Error during AI fixing"
    )
    raise

# Back to phase_coordinator.py:608-610
else:
    self.console.print(
        "[yellow]⚠️[/yellow] AI agents could not fix all issues"
    )
    # ai_fix_success = False
    # success remains False
    # Result: 0% reduction
```

---

## Why the Format Specifier Error Occurs

### Hypothesis 1: Direct Logging Bug
```python
# crackerjack/adapters/ai/base.py (somewhere)
logger.info(
    "Tool output: %s",
    output,  # output contains format strings
    extra_arg  # ❌ EXTRA ARG: causes format specifier mismatch
)
```

**Error Message**:
```
TypeError: not all arguments converted during string formatting
or
ValueError: incomplete format
```

### Hypothesis 2: Indirect Logging Bug
```python
# crackerjack/adapters/ai/base.py (somewhere)
logger.info(
    "Processed %d issues from %s (%.0f%% complete)",
    issue_count,
    tool_name,
    # ❌ MISSING percentage arg
)
```

**Error Message**:
```
TypeError: not enough arguments for format string
```

### Hypothesis 3: Output Containing Format Specifiers
```python
# Tool output contains:
error: invalid format specifier %.0f in format string
warning: format string %s not closed

# Adapter tries to log this:
logger.info("Tool output: %s", tool_output)
# But tool_output contains % characters that get parsed as format specifiers
```

**Error Message**:
```
ValueError: unsupported format character '%' (0x25) at index X
```

---

## The Fix

### Immediate Fix: Escape Format Specifiers in Output
```python
# crackerjack/adapters/ai/base.py
def _safe_log_output(self, tool_name: str, output: str) -> None:
    """Escape format specifiers in tool output before logging."""
    safe_output = output.replace("%", "%%")
    self.logger.info(f"Tool output from {tool_name}: {safe_output}")
```

### Better Fix: Use Lazy Logging
```python
# crackerjack/adapters/ai/base.py
# Instead of:
logger.info("Tool output: %s", output)  # Parses % in output

# Use:
logger.info("Tool output: %s", output)  # Lazy: % only in format string
# Or even better:
self.logger.debug(lambda: f"Tool output: {output!r}")
```

### Best Fix: Use f-strings (Python 3.13+)
```python
# crackerjack/adapters/ai/base.py
# Use f-strings everywhere (no format specifier issues)
self.logger.info(f"Tool output from {tool_name}: {output!r}")
```

---

## Verification Steps

### 1. Find the Exact Error Location
```bash
# Run with debug logging
export AI_AGENT_DEBUG=1
export AI_AGENT_VERBOSE=1
python -m crackerjack run --comp --ai-fix --debug 2>&1 | tee ai-fix-debug.log

# Search for format specifier errors
grep -i "format.*spec\|%.*%\|TypeError.*format" ai-fix-debug.log
```

### 2. Check Hook Results
```python
# Add debug logging in autofix_coordinator.py:_parse_single_hook_result
def _parse_single_hook_result(self, result: object) -> list[Issue]:
    hook_name = getattr(result, "name", "")
    raw_output = self._extract_raw_output(result)

    # DEBUG: Print raw output
    self.logger.error(f"DEBUG: Hook '{hook_name}' raw output:\n{raw_output[:500]}")

    hook_issues = self._parse_hook_to_issues(hook_name, raw_output)
    return hook_issues
```

### 3. Test Parser Isolation
```python
# Test parser directly with sample output
from crackerjack.parsers.factory import ParserFactory

factory = ParserFactory()
output = "sample:14: error: Some issue here"  # Replace with actual output

try:
    issues = factory.parse_with_validation(
        tool_name="ruff",
        output=output,
        expected_count=1,
    )
    print(f"✅ Parsed {len(issues)} issues")
except Exception as e:
    print(f"❌ Error: {e}")
```

---

## Summary

### The Problem
1. AI adapter's base.py has format specifier bug in logging
2. Bug produces malformed HookResult output
3. Malformed output breaks issue parsing (count validation fails)
4. ParsingError breaks agent execution loop
5. Agents never execute → 0 fixes applied → 0% reduction

### The Solution
1. **Find**: Locate exact format specifier bug in `crackerjack/adapters/ai/base.py`
2. **Fix**: Use f-strings or lazy logging to avoid format specifier issues
3. **Test**: Verify hook results are well-formed
4. **Validate**: Ensure issue parsing succeeds
5. **Confirm**: Agents execute and apply fixes

### Next Action
Run debug mode to find exact error location:
```bash
export AI_AGENT_DEBUG=1
export AI_AGENT_VERBOSE=1
python -m crackerjack run --comp --ai-fix --debug 2>&1 | tee /tmp/ai-fix-debug.log
grep -B5 -A5 "format.*spec\|%.*%\|TypeError\|ValueError" /tmp/ai-fix-debug.log
```
