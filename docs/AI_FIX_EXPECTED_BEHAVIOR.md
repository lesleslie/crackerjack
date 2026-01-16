# AI Agent Fixing (`--ai-fix`) - Expected Behavior

## Overview

The `--ai-fix` flag enables **fully automated fixing** of all quality issues detected by Crackerjack's fast hooks, comprehensive hooks, and test suite.

## Core Principle

**ALL quality issues should be automatically fixed by AI agents when `--ai-fix` is enabled:**

- ✅ Fast hook issues (formatting, style, imports)
- ✅ Comprehensive hook issues (type errors, security, complexity, dead code)
- ✅ Test failures (unit tests, integration tests)
- ❌ **NOT** manual review requirements

## Expected Workflow

### Phase 1: Quality Detection

```
1. Run fast hooks → collect failures
2. Run comprehensive hooks → collect failures
3. Run test suite → collect failures
```

### Phase 2: AI Agent Analysis

```
🤖 AI AGENT FIXING Attempting automated fixes
```

**Parse ALL failures into Issue objects:**

- Type errors (zuban, pyright, mypy)
- Code modernization (refurb)
- Complexity violations (complexipy)
- Security issues (bandit, semgrep)
- Dead code (vulture, skylos)
- Formatting (ruff)
- Test failures (pytest)

### Phase 3: Automated Fixes

```
✅ AI agents applied fixes, retrying...
```

**Apply fixes with appropriate agents:**

- RefactoringAgent → Complexity, modernization
- SecurityAgent → Security issues
- FormattingAgent → Style, formatting
- TestCreationAgent → Test failures
- TypeCheckingAgent → Type errors
- **ALL agents should attempt fixes**

### Phase 4: Verification

```
Re-run fast hooks
Re-run comprehensive hooks
Re-run test suite
```

**Success criteria:**

- All hooks pass ✅
- All tests pass ✅
- Zero remaining issues ✅

## Current Issues (Should Be Fixed)

### ❌ Issue 1: Zuban Type Error

**Location:** `crackerjack/executors/hook_executor.py:664`

**Error:**

```
error: Need type annotation for "issues" (hint: "issues: List[<type>] = ...")  [var-annotated]
```

**Expected AI Fix:**

```python
# Before (line 664):
issues = []

# After (AI should fix):
issues: list[str] = []
```

**Why Not Fixed:** The RefactoringAgent or FormattingAgent should handle this automatically.

### ❌ Issue 2: Refurb Modernization #1

**Location:** `crackerjack/executors/hook_executor.py:737:33`

**Error:**

```
[FURB102]: Replace `x.startswith(y) or x.startswith(z)` with `x.startswith((y, z))`
```

**Expected AI Fix:**

```python
# Before:
if line.startswith(("Found", "Checked")):
    return False

# After (AI should fix):
if line.startswith(("Found", "Checked")):
    return False
```

**Why Not Fixed:** The RefactoringAgent should apply this modernization automatically.

### ❌ Issue 3: Refurb Modernization #2

**Location:** `crackerjack/managers/test_manager.py:185:13`

**Error:**

```
[FURB126]: Replace `else: return x` with `return x`
```

**Expected AI Fix:**

```python
# Before:
if result.returncode == 0:
    return self._handle_test_success(...)
else:
    return self._handle_test_failure(...)

# After (AI should fix):
if result.returncode == 0:
    return self._handle_test_success(...)
return self._handle_test_failure(...)
```

**Why Not Fixed:** The RefactoringAgent should apply this simplification automatically.

## Agent Capabilities

### Agents That SHOULD Be Handling These Issues:

1. **RefactoringAgent** (0.9 confidence)

   - Complexity reduction ✅
   - Code modernization ✅
   - Dead code removal ✅
   - **Should fix:** refurb issues, complexity violations

1. **FormattingAgent** (0.8 confidence)

   - Style violations ✅
   - Import optimization ✅
   - **Should fix:** Type annotations, formatting

1. **SemanticAgent** (0.85 confidence)

   - Intelligent refactoring ✅
   - Code comprehension ✅
   - **Should fix:** Type inference improvements

## Why Issues Aren't Being Fixed

### Problem: Conservative Agent Behavior

**Current Implementation:**

```python
# crackerjack/core/autofix_coordinator.py
if fix_result.success:
    self.logger.info(f"AI agents fixed {len(fix_result.fixes_applied)} issues")
else:
    self.logger.warning(f"AI agents could not fix all issues")
```

**Issue:** Agents may be:

1. **Not attempting fixes** for simple issues
1. **Too conservative** with confidence thresholds
1. **Missing specialized agents** for certain issue types

### Problem: Parsing Issues

**Current Implementation:**

```python
def _parse_hook_to_issues(self, hook_name: str, raw_output: str) -> list[Issue]:
    # Parses zuban, refurb, etc. into Issue objects
    # But may not be extracting all the details needed
```

**Issue:** Parser may not be capturing:

- Exact line numbers
- Suggested fixes from tools
- Context needed for automatic fixing

## Expected Behavior

### When `--ai-fix` Is Enabled:

1. **ALL zuban type errors** → Fixed by TypeCheckingAgent
1. **ALL refurb suggestions** → Fixed by RefactoringAgent
1. **ALL complexity violations** → Fixed by RefactoringAgent
1. **ALL test failures** → Fixed by TestCreationAgent
1. **ALL security issues** → Fixed by SecurityAgent
1. **ALL formatting issues** → Fixed by FormattingAgent

### Success Criteria:

```
✅ Fast hooks: 15/15 passed
✅ Comprehensive hooks: 11/11 passed
✅ Tests: All passed
✅ Zero issues remaining
```

## Implementation Requirements

### 1. Agent Confidence Thresholds

**Current Problem:** Agents may be too conservative.

**Required:**

- Simple fixes (type annotations, formatting) → **0.95+ confidence**
- Modernization (refurb) → **0.85+ confidence**
- Complex refactoring → **0.75+ confidence**

### 2. Issue Parsing Enhancement

**Required:**

- Parse tool suggestions (e.g., refurb's `Replace X with Y`)
- Extract exact line numbers and context
- Include tool recommendations in Issue objects

### 3. Agent Coordination

**Required:**

- Route issues to most appropriate agent
- Allow multiple agents to attempt fixes
- Iterate until all issues resolved or max attempts reached

## Testing Checklist

### Manual Testing:

```bash
# Before fix:
python -m crackerjack run -c
# Should show: zuban (1 issue), refurb (2 issues)

# Run AI fix:
python -m crackerjack run --ai-fix -c
# Should show: AI agents applied fixes

# After fix:
python -m crackerjack run -c
# Should show: All hooks passing ✅
```

### Expected Results:

- ✅ Zuban: 0 issues (type annotation added)
- ✅ Refurb: 0 issues (modernization applied)
- ✅ All hooks: 11/11 passing
- ✅ All tests: Passing

## Conclusion

**The `--ai-fix` flag should result in ZERO remaining issues** for:

- All fast hooks (formatting, style)
- All comprehensive hooks (type, security, complexity)
- All tests

**Manual intervention should ONLY be required for:**

- Architectural decisions
- Business logic changes
- Feature requirements

**Current Status:** ❌ **FAILING** - AI agents not fixing simple issues

**Required Action:** Enhance agent confidence, parsing, and coordination to achieve 100% automated fixing.
