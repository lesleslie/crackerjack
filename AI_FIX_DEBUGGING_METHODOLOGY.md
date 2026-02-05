# AI-Fix Debugging Methodology

**Date**: 2026-02-04
**Status**: 🔍 Investigating why AI agents don't fix issues in production

______________________________________________________________________

## Debug Methodology

### Phase 1: Isolation Testing ✅

**Goal**: Verify agents work independently of the full workflow

**Method**:

```python
# Create minimal test issue
from crackerjack.agents.base import Issue, IssueType, Priority

test_issue = Issue(
    type=IssueType.FORMATTING,
    severity=Priority.MEDIUM,
    message="Replace try/except/pass...",
    file_path="crackerjack/services/ai_fix_progress.py",
    line_number=170,
)

# Invoke agent directly
result = await coordinator.handle_issues([test_issue])
```

**Result**: ✅ **SUCCESS** - Agent fixed the issue in ~6 seconds

- Confidence: 1.0
- Fixes applied: 4 (ruff formatting, trailing whitespace, EOF fix)
- Files modified: 1

**Conclusion**: Agents are **NOT** the problem. They work perfectly when given properly formatted issues.

______________________________________________________________________

### Phase 2: Workflow Integration Analysis 🔍

**Goal**: Identify where issue parsing/formatting breaks in the full workflow

**Key Components**:

1. **Hook Execution** → Produces raw output (zuban, refurb, complexipy, etc.)
1. **Issue Parsing** → `_parse_hook_results_to_issues()` converts raw output to `Issue` objects
1. **Agent Invocation** → `coordinator.handle_issues()` receives `Issue` objects
1. **Fix Application** → Agents apply fixes and return `FixResult`

**Suspected Break Points**:

#### Point A: Issue Parsing (Most Likely)

- **Location**: `_parse_hook_to_issues()` → `parser_factory.parse_with_validation()`
- **Problem**: Hook output format might not match parser expectations
- **Evidence**: "Detected 14 issues" but "14 → 14" (no reduction)

#### Point B: Issue Format Mismatch

- **Location**: After parsing, before agent invocation
- **Problem**: Parsed issues might lack required fields
- **Evidence**: Agents work with manually created issues but not parsed ones

#### Point C: Silent Failures

- **Location**: During agent execution
- **Problem**: Errors caught but not logged
- **Evidence**: No error messages in output

______________________________________________________________________

### Phase 3: Data Flow Tracing 🔍

**Tracing Steps**:

1. **Capture Raw Hook Output**

   ```python
   raw_output = self._extract_raw_output(result)
   print(f"Raw output from {hook_name}:", raw_output[:500])
   ```

1. **Verify Parsing**

   ```python
   issues = parser.parse_with_validation(tool_name, raw_output, expected_count)
   print(f"Parsed {len(issues)} issues")
   for issue in issues[:3]:
       print(f"  - {issue.type}: {issue.message[:60]}")
   ```

1. **Validate Issue Objects**

   ```python
   assert all(hasattr(i, 'type') for i in issues)
   assert all(hasattr(i, 'severity') for i in issues)
   assert all(hasattr(i, 'message') for i in issues)
   assert all(i.file_path for i in issues)
   ```

1. **Trace Agent Execution**

   ```python
   self.logger.info(f"Sending {len(issues)} issues to agent")
   result = await coordinator.handle_issues(issues)
   self.logger.info(f"Agent result: success={result.success}, fixes={len(result.fixes_applied)}")
   ```

______________________________________________________________________

## Current Investigation Status

### What Works ✅

- Agent initialization (9 agents loaded)
- Agent invocation with manually created issues
- Fix application when properly formatted
- Progress bar infrastructure

### What Doesn't Work ❌

- Issue parsing from hook results
- Issue format conversion
- Fix application in real workflow
- Progress bar advancement (stays at 0%)

### Key Findings 📊

1. **Agents Are Functional**: Debug script proves agents can fix issues
1. **Hook Results Are Captured**: "Detected 14 issues" confirms parsing happens
1. **No Fixes Applied**: "14 → 14 → 14 → 14" indicates issues aren't being resolved
1. **Silent Failures**: No error messages despite no fixes being applied

______________________________________________________________________

## Next Investigation Steps

### Step 1: Add Detailed Logging 📝

Add logging at each break point:

```python
def _parse_hook_to_issues(self, hook_name: str, raw_output: str) -> list[Issue]:
    # Log raw output
    self.logger.debug(f"Raw output from {hook_name}:\n{raw_output[:500]}")

    issues = self._parser_factory.parse_with_validation(...)
    self.logger.info(f"Parsed {len(issues)} issues from {hook_name}")

    # Log parsed issue structure
    for i, issue in enumerate(issues[:3]):
        self.logger.info(
            f"  Issue {i}: type={issue.type}, "
            f"severity={issue.severity}, "
            f"file={issue.file_path}, "
            f"line={issue.line_number}, "
            f"msg={issue.message[:60]}"
        )

    return issues
```

### Step 2: Validate Issue Fields ✅

Add validation after parsing:

```python
def _validate_parsed_issues(self, issues: list[Issue]) -> bool:
    for issue in issues:
        if not hasattr(issue, 'type') or issue.type is None:
            self.logger.error(f"Issue missing type: {issue}")
            return False
        if not hasattr(issue, 'severity') or issue.severity is None:
            self.logger.error(f"Issue missing severity: {issue}")
            return False
        if not hasattr(issue, 'message') or not issue.message:
            self.logger.error(f"Issue missing message: {issue}")
            return False
        if not issue.file_path:
            self.logger.warning(f"Issue {issue.id} has no file_path")
    return True
```

### Step 3: Trace Agent Selection 🔍

Add logging to show which agent handles which issue:

```python
def _run_ai_fix_iteration(self, coordinator, issues: list[Issue]) -> bool:
    self.logger.info(f"Starting iteration with {len(issues)} issues")

    for i, issue in enumerate(issues[:3]):
        self.logger.info(
            f"  Issue {i+1}: type={issue.type.value}, "
            f"file={issue.file_path}:{issue.line_number}"
        )

    # Log before agent call
    self.logger.info(f"Invoking coordinator.handle_issues()...")
    result = self._execute_ai_fix(coordinator, issues)

    # Log result
    if result:
        self.logger.info(
            f"Result: success={result.success}, "
            f"fixes={len(result.fixes_applied)}, "
            f"remaining={len(result.remaining_issues)}"
        )
    else:
        self.logger.error("Agent returned None result")

    return result is not None
```

______________________________________________________________________

## Progress Bar Issues

### Problem

Bar shows `|⚠︎ | (!) 0% [0/100]` and never advances

### Root Cause

1. **No Issues Fixed**: Bar advances based on `issues_fixed / initial_issues * 100`
1. **If no fixes applied**: Bar stays at 0%
1. **Animation Not Working**: alive-progress bar fill not rendering (terminal capability issue)

### Solution

1. **Fix the actual problem**: Get agents to fix issues
1. **Bar will advance automatically**: Once issues are fixed, bar will show progress
1. **Visual rendering**: The `|⚠︎` is alive-progress's warning spinner - actual bar fill depends on terminal

______________________________________________________________________

## Hypotheses

### Hypothesis 1: Parser Returns Empty List 🔥

**Probability**: HIGH

**Evidence**:

- "Detected 14 issues" but none fixed
- Manual test issues work fine
- Hook output format might not match parser expectations

**Test**:

```python
issues = parser.parse_with_validation(tool_name, raw_output, expected_count)
print(f"Parsed {len(issues)} from expected {expected_count}")
assert len(issues) > 0, "Parser returned empty list!"
```

### Hypothesis 2: Issue Type Mapping Wrong

**Probability**: MEDIUM

**Evidence**:

- Different hooks have different issue types
- Agent selection depends on issue type
- Wrong type = wrong agent = no fix

**Test**:

```python
for issue in issues:
    print(f"Issue type: {issue.type} -> Agent: {get_agent_for_type(issue.type)}")
```

### Hypothesis 3: File Path Issues

**Probability**: MEDIUM

**Evidence**:

- Hooks might return relative paths
- Agents need absolute paths
- Path mismatch = file not found = no fix

**Test**:

```python
for issue in issues:
    if not Path(issue.file_path).exists():
        print(f"❌ File not found: {issue.file_path}")
    else:
        print(f"✅ File exists: {issue.file_path}")
```

______________________________________________________________________

## Recommended Actions

1. **Add detailed logging** at each break point (Step 1 above)
1. **Run with `--ai-debug --verbose`** to capture logs
1. **Examine parsed issues** to verify structure
1. **Test parser directly** with actual hook output
1. **Validate issue fields** before sending to agents

______________________________________________________________________

## Debug Commands

### Run with full debug logging

```bash
python -m crackerjack run --ai-debug --ai-fix --comp --verbose
```

### Check logs in real-time

```bash
tail -f ~/.crackerjack/logs/crackerjack.log | grep -i "issue\|agent\|fix\|error"
```

### Test parser directly

```python
from crackerjack.parsers.json_parsers import JSONParserFactory

parser = JSONParserFactory()
raw_output = """{"results": [...]}"""  # Actual hook output
issues = parser.parse_with_validation("zuban", raw_output, 3)
print(f"Parsed {len(issues)} issues")
```

______________________________________________________________________

**Status**: 🔍 Actively investigating issue parsing/formatting as root cause
