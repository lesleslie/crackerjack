______________________________________________________________________

## status: complete role: historical date: 2026-07-17 last_reviewed: 2026-07-17 superseded_by: null blocks_on: [] topic: lifecycle

# AI Agent Fixing (`--ai-fix`) - Expected Behavior

## Overview

The `--ai-fix` flag enables **fully automated fixing** of all quality issues detected by Crackerjack's fast hooks, comprehensive hooks, and test suite.

## Core Principle

**ALL quality issues should be automatically fixed by AI agents when `--ai-fix` is enabled:**

- ✅ Fast hook issues (formatting, style, imports)
- ✅ Comprehensive hook issues (type errors, security, complexity, dead code, refurb)
- ✅ Test failures (unit tests, integration tests) - **NEW: Safe failures with guardrails**
- ❌ **NOT** manual review requirements

**Test AI-Fix Guardrails (NEW):**

- Only attempts fixes for **safe** test failures:
  - Import errors (`ModuleNotFoundError`, `ImportError`)
  - Attribute errors on imported modules
  - "No module named" errors
  - Cannot import errors
- **Requires user confirmation** in interactive mode
- Skips **risky** failures (requires manual review):
  - Assertion failures
  - Logic errors in test expectations
  - Integration test failures
  - Test infrastructure issues

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
- Code modernization (refurb) ✅ **Now included in AI-fix loop**
- Complexity violations (complexipy)
- Security issues (bandit, semgrep)
- Dead code (vulture, skylos)
- Formatting (ruff)
- Test failures (pytest) ✅ **NEW: Safe failures with user confirmation**

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

## Recent Fixes (Completed)

### ✅ Fix 1: Test AI-Fix Implementation (Jan 2025)

**Location:** `crackerjack/core/phase_coordinator.py`

**Feature:** Added AI-fix capability for test failures with safety guardrails

**Implementation:**

- Classifies test failures as safe vs risky
- Safe: import errors, attribute errors, "no module named"
- Risky: assertions, logic errors, integration tests
- Requires user confirmation in interactive mode
- Re-runs tests after successful AI fixes

**Files Modified:**

- `crackerjack/managers/test_manager.py` - Fixed test failure display bug
- `crackerjack/core/phase_coordinator.py` - Added `_apply_ai_fix_for_tests()` method
- `crackerjack/core/phase_coordinator.py` - Added `_classify_safe_test_failures()` method
- `crackerjack/core/phase_coordinator.py` - Added `_run_ai_test_fix()` helper

### ✅ Fix 2: Refurb Added to AI-Fix Loop (Jan 2025)

**Location:** `crackerjack/core/autofix_coordinator.py:_build_check_commands()`

**Problem:** Refurb was excluded from `_collect_current_issues()`, causing:

- Wrong issue counts (showed 4 instead of 6)
- Refurb issues never detected or fixed during iterations

**Solution:** Added refurb check command to AI-fix loop

**Impact:** Now detects and fixes all comprehensive hook issues including refurb

### ✅ Fix 3: All Type Errors Fixed (Jan 2025)

**Location:** `crackerjack/core/phase_coordinator.py`

**Problems Fixed:**

1. `severity="high"` → `severity=Priority.HIGH` (proper enum)
1. Removed non-existent `priority` parameter
1. List comprehension instead of for loop with append
1. Tuple membership instead of list in `any()`
1. Removed unnecessary `else: return` pattern

**Result:** All 2 zuban type errors, 3 refurb warnings, and 1 complexity warning fixed

### ✅ Fix 4: AI-Fix Reporting Grammar (Jan 2025)

**Location:** `crackerjack/core/autofix_coordinator.py` (6 locations)

**Problem:** "1 issues" (grammatically incorrect)

**Solution:** Added pluralization logic

```python
issue_word = "issue" if count == 1 else "issues"
f"{count} {issue_word} to fix"  # ✅ "1 issue" or "2 issues"
```

**Locations Fixed:**

- Iteration progress reports
- Convergence detection messages
- Partial progress messages
- Max iterations reached messages

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

### Problem: Conservative Agent Behavior (RESOLVED)

**Previous Implementation:**

Agents were too conservative, but recent improvements include:

- ✅ Added refurb to AI-fix loop (was missing)
- ✅ Fixed issue counting and reporting
- ✅ Improved pluralization in user-facing messages

**Remaining Challenges:**

Agents may still be:

1. **Not attempting fixes** for complex architectural issues
1. **Too conservative** with confidence thresholds for some patterns
1. **Missing context** for business logic changes

### Problem: Parsing Issues (IMPROVED)

**Current Implementation:**

```python
def _parse_hook_to_issues(self, hook_name: str, raw_output: str) -> list[Issue]:
    # Parses zuban, refurb, complexipy, etc. into Issue objects
    # ✅ Now includes refurb parser
```

**Status:** <!-- legacy status — see YAML frontmatter -->

- ✅ Refurb parser exists and working
- ✅ All comprehensive hooks detected (zuban, refurb, complexipy)
- ✅ Proper issue counting and reporting

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
# Comprehensive hooks (including refurb):
python -m crackerjack run -c --ai-fix
# Should show: All hooks passing ✅

# Test AI-fix (NEW):
python -m crackerjack run -t --ai-fix -v
# Should prompt for confirmation on safe test failures
# Should re-run tests after AI fixes

# Full workflow:
python -m crackerjack run -t -c --ai-fix
# Should fix all issues automatically
```

### Expected Results:

**Comprehensive Hooks:**

- ✅ Zuban: 0 issues (type errors fixed)
- ✅ Refurb: 0 issues (modernization applied)
- ✅ Complexipy: 0 issues (complexity ≤15)
- ✅ All comprehensive hooks: 10/10 passing

**Test Suite:**

- ✅ Safe failures: AI-fixed with confirmation
- ✅ Risky failures: Require manual review
- ✅ All tests: Passing after fixes

**Workflow:**

- ✅ Correct issue counts (includes refurb)
- ✅ Proper pluralization ("1 issue" vs "2 issues")
- ✅ User confirmation for test AI-fix

## Conclusion

**The `--ai-fix` flag should result in ZERO remaining issues** for:

- All fast hooks (formatting, style) ✅
- All comprehensive hooks (type, security, complexity, refurb) ✅
- Safe test failures (import errors, typos) ✅ **NEW**

**Manual intervention should ONLY be required for:**

- Architectural decisions
- Business logic changes
- Feature requirements
- **Risky test failures** (assertions, logic errors, integration tests) ✅ **NEW**

**Current Status:** ✅ **IMPROVED** - Major enhancements completed:

1. ✅ Test AI-fix implemented with guardrails (Jan 2025)
1. ✅ Refurb added to AI-fix loop (Jan 2025)
1. ✅ All type errors and refurb warnings fixed (Jan 2025)
1. ✅ AI-fix reporting improved (issue counts, pluralization) (Jan 2025)

**Ongoing Work:**

- Continue improving agent confidence for complex issues
- Enhance parsing to capture tool suggestions
- Optimize agent coordination for faster convergence
