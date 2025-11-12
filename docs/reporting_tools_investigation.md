# Reporting Tools Investigation & Fix

## Problem Statement

Gitleaks, creosote, refurb, and complexipy were showing as `PASSED` with non-zero issue counts:
- complexipy: PASSED with 2 issues
- refurb: PASSED with 2 issues
- gitleaks: PASSED with 1 issue
- creosote: PASSED with 1 issue

**User Requirement**: These hooks need to FAIL when they find issues so the auto-fix stage can be triggered.

## Root Cause Analysis

### Discovery 1: Reporting vs. Linting Tools

These are **reporting/analysis tools**, not linters:

**Linters** (ruff, mypy, pyright):
- Exit code 0 = No violations found
- Exit code ≠ 0 = Violations detected

**Reporting Tools** (complexipy, refurb, gitleaks, creosote):
- Exit code 0 = Tool executed successfully (even with findings!)
- Exit code ≠ 0 = Tool crashed or had execution errors

### Discovery 2: Issue Counting Problems

Original `_extract_issues_from_process_output()` logic:
```python
if status == "passed":
    return []  # No parsing!
```

This meant:
1. Tool returns exit code 0 → status = "passed"
2. Status "passed" → return empty list (no parsing)
3. No issues found → displays PASSED with 0 issues

However, the output showed 1-2 issues. This means issues WERE being counted somewhere, but inaccurately.

### Discovery 3: Inaccurate Issue Parsing

When status was "failed", the fallback parser just split output on newlines and counted everything:
```python
return [line.strip() for line in error_output.split("\n") if line.strip()]
```

This counted:
- Header rows
- Summary messages
- Formatting characters
- Functions below complexity threshold
- Warning messages

## Solution Implemented

### 1. Parse Issues Regardless of Exit Code

Modified `/Users/les/Projects/crackerjack/crackerjack/executors/hook_executor.py`:

```python
def _extract_issues_from_process_output(...) -> list[str]:
    error_output = (result.stdout + result.stderr).strip()

    # Reporting tools need special handling
    reporting_tools = {"complexipy", "refurb", "gitleaks", "creosote"}

    if hook.name in reporting_tools:
        # Always parse for reporting tools (they exit 0 even with findings)
        if hook.name == "complexipy":
            return self._parse_complexipy_issues(error_output)
        # ... other reporting tools

    # For non-reporting tools, only parse if failed
    if status == "passed":
        return []
```

### 2. Override Status Based on Issues Found

```python
def _create_hook_result_from_process(...) -> HookResult:
    # Initial status based on exit code
    status = "passed" if result.returncode == 0 else "failed"

    # Extract issues (for reporting tools, happens regardless of exit code)
    issues_found = self._extract_issues_from_process_output(hook, result, status)

    # Override status if reporting tool found issues
    if hook.name in reporting_tools and issues_found:
        status = "failed"  # Triggers auto-fix stage!
```

### 3. Tool-Specific Parsing Methods

#### complexipy
```python
def _parse_complexipy_issues(self, output: str) -> list[str]:
    """Only count functions exceeding complexity 15."""
    issues = []
    for line in output.split("\n"):
        if "│" in line and "crackerjack" in line:
            if not any(x in line for x in ["Path", "─────", "┌", "└", ...]):
                parts = [p.strip() for p in line.split("│") if p.strip()]
                if len(parts) >= 4:
                    complexity = int(parts[-1])
                    if complexity > 15:  # Only violations!
                        issues.append(line.strip())
    return issues
```

#### refurb
```python
def _parse_refurb_issues(self, output: str) -> list[str]:
    """Only count lines with [FURB codes."""
    issues = []
    for line in output.split("\n"):
        if "[FURB" in line and ":" in line:
            issues.append(line.strip())
    return issues
```

#### gitleaks
```python
def _parse_gitleaks_issues(self, output: str) -> list[str]:
    """Ignore warnings, only count actual leaks."""
    if "no leaks found" in output.lower():
        return []
    issues = []
    for line in output.split("\n"):
        if "WRN" in line and "Invalid .gitleaksignore" in line:
            continue  # Skip warnings
        if any(x in line.lower() for x in ["leak", "secret", "credential", "api"]):
            if "found" not in line.lower():  # Skip summary lines
                issues.append(line.strip())
    return issues
```

#### creosote
```python
def _parse_creosote_issues(self, output: str) -> list[str]:
    """Only count unused dependencies."""
    if "No unused dependencies found" in output:
        return []
    issues = []
    parsing_unused = False
    for line in output.split("\n"):
        if "unused" in line.lower() and "dependenc" in line.lower():
            parsing_unused = True
            continue
        if parsing_unused and line.strip() and not line.strip().startswith("["):
            dep_name = line.strip().lstrip("- ")
            if dep_name:
                issues.append(f"Unused dependency: {dep_name}")
        if not line.strip():
            parsing_unused = False
    return issues
```

## Testing & Verification

### Test 1: Parsing Logic (Isolated)
✅ Created `/tmp/test_parsing.py` - parsing works correctly in isolation
✅ Created `/tmp/test_executor_parsing.py` - HookExecutor methods work correctly

### Test 2: Module Loading
✅ Verified changes are in the loaded module using `inspect.getsource()`

### Test 3: Python Bytecode Cache
✅ Cleared all `__pycache__/` directories and `.pyc` files

### Test 4: Crackerjack Cache
⏳ Running `python -m crackerjack --clear-cache && python -m crackerjack --comp`

## Caching Issue Discovered

Crackerjack has its own caching system that stores hook results. Even with Python bytecode cleared, old results persist. This is why the changes weren't taking effect immediately.

**Solution**: Use `--clear-cache` flag to clear crackerjack's internal cache.

## Files Modified

1. `/Users/les/Projects/crackerjack/crackerjack/executors/hook_executor.py`:
   - Line 387-425: Modified `_create_hook_result_from_process()`
   - Line 428-461: Modified `_extract_issues_from_process_output()`
   - Line 463-495: Added `_parse_complexipy_issues()`
   - Line 497-504: Added `_parse_refurb_issues()`
   - Line 506-520: Added `_parse_gitleaks_issues()`
   - Line 522-542: Added `_parse_creosote_issues()`

2. `/Users/les/Projects/crackerjack/docs/reporting_tools_fix.md`: User documentation
3. `/Users/les/Projects/crackerjack/docs/reporting_tools_investigation.md`: Technical investigation notes

## Expected Results (After Cache Clear)

### Before Fix
```
complexipy :: PASSED | 15s | issues=2
refurb :: PASSED | 120s | issues=2
gitleaks :: PASSED | 10s | issues=1
creosote :: PASSED | 50s | issues=1
```

### After Fix (Expected)
```
complexipy :: FAILED | 15s | issues=22  (or accurate count)
refurb :: PASSED | 120s | issues=0  (or accurate count if violations)
gitleaks :: PASSED | 10s | issues=0  (or accurate count if violations)
creosote :: PASSED | 50s | issues=0  (or accurate count if violations)
```

## Next Steps

1. ✅ Clear crackerjack cache: `python -m crackerjack --clear-cache`
2. ⏳ Run comprehensive hooks: `python -m crackerjack --comp`
3. ⏳ Verify accurate issue counts and FAILED status when issues exist
4. ⏳ Confirm auto-fix stage triggers when hooks fail

## Debug Commands

```bash
# Clear all caches
python -m crackerjack --clear-cache

# Run with debug output
python -m crackerjack --comp --debug

# Manual tool testing
uv run complexipy --max-complexity-allowed 15 crackerjack
uv run refurb crackerjack
uv run gitleaks protect -v
uv run creosote -p crackerjack --venv .venv

# Check loaded module
python -c "import sys; sys.path.insert(0, '/Users/les/Projects/crackerjack'); from crackerjack.executors.hook_executor import HookExecutor; import inspect; source = inspect.getsource(HookExecutor._parse_complexipy_issues); print('DEBUG' in source)"
```

## Architecture Notes

### Execution Flow
```
CLI (--comp flag)
  ↓
AsyncWorkflowOrchestrator
  ↓
PhaseCoordinator.run_comprehensive_hooks_only()
  ↓
HookManager.run_comprehensive_hooks()
  ↓
ProgressHookExecutor (extends HookExecutor)
  ↓
HookExecutor._create_hook_result_from_process()
  ↓
HookExecutor._extract_issues_from_process_output()
  ↓
HookExecutor._parse_complexipy_issues() [OUR CODE]
```

### Key Classes
- `HookExecutor`: Base class with hook execution logic (our changes here)
- `ProgressHookExecutor`: Extends HookExecutor with progress indicators
- `LSPAwareHookExecutor`: Extends HookExecutor with LSP integration (conditionally used)
- `PhaseCoordinator`: Orchestrates hook phases
- `HookManager`: Manages hook configuration and execution
- `AsyncWorkflowOrchestrator`: Async workflow coordination (ACB mode)

### Inheritance Chain
```
HookExecutor (our changes)
  ↑
  ├── ProgressHookExecutor (used by default with --comp)
  └── LSPAwareHookExecutor (used with tool proxy enabled)
```

Both subclasses inherit our modified methods unless they override them (they don't).

## Lessons Learned

1. **Exit Code Semantics Matter**: Not all tools use exit codes the same way
2. **Caching Layers**: Multiple caching layers (Python bytecode, crackerjack cache) can mask code changes
3. **Tool Categories**: Need to categorize tools by behavior (linters vs reporters vs formatters)
4. **Parsing Complexity**: Generic parsing doesn't work; each tool needs custom logic
5. **Status Override**: Sometimes need to override status AFTER parsing to get correct behavior
