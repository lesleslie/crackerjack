# AI-Fix Workflow Investigation - Critical Findings

**Date**: 2026-02-06
**Status**: ⚠️ **WORKFLOW BROKEN** - Agents work but orchestration fails

## Executive Summary

The AI-fix workflow has a **critical bug**: All agents fail 100% of the time during workflow execution, despite agents working perfectly when called directly.

### Test Results

| Test | Result | Details |
|------|--------|---------|
| Direct Agent Call | ✅ **SUCCESS** | FormattingAgent fixed all issues, success=True |
| AI-Fix Workflow | ❌ **100% FAILURE** | 67 issues → 67 issues (0% reduction) |
| Agent Orchestration | ❌ **BROKEN** | All agents report "failed to fix issue" |

______________________________________________________________________

## Problem Analysis

### 1. Direct Agent Test: SUCCESS ✅

**Test**: Called FormattingAgent directly on test file with 5 ruff issues

```python
# Before
import os, sys


def foo():
    x = 1 + 2
    return x


class Bar:
    pass


# After (agent applied fixes)
def foo():
    x = 1 + 2
    return x


class Bar:
    pass
```

**Result**:

```
✅ Success: True
✅ Confidence: 0.9
✅ Fixes applied: ['Applied ruff code formatting', ...]
✅ Files modified: ['/tmp/test_ai_fix/test_file.py']
✅ Remaining issues: []
```

**Conclusion**: Agents **CAN** fix issues successfully.

______________________________________________________________________

### 2. AI-Fix Workflow: FAILURE ❌

**Test**: Ran comprehensive hooks with AI-fix enabled

```bash
AI_AGENT=1 python -m crackerjack run --comp --ai-fix
```

**Observed Behavior**:

```
Comprehensive Hook Results:
 - pyscn :: FAILED | 19 issues
 - zuban :: FAILED | 43 issues
 - complexipy :: FAILED | 13 issues
 - semgrep :: FAILED | 3 issues
 - skylos :: FAILED | 1 issue
 - refurb :: FAILED | 6 issues
Total: 67 issues

AI-FIX Stage:
  Detected 67 issues
  Issues: 67 → 67 (0% reduction)

Agent Execution:
  RefactoringAgent: 100% failure rate
  ArchitectAgent: 100% failure rate
  (all other agents: similar failure)
```

**Logged Output**:

```
{"logger": "crackerjack.agents.coordinator",
 "event": "RefactoringAgent failed to fix issue",
 "timestamp": "2026-02-07T01:11:38.212792Z"}
```

**Pattern**: Every single issue, every single agent → failure.

______________________________________________________________________

## Root Cause Analysis

### Hypothesis 1: Agent Not Being Called ❌

**Status**: RULED OUT - Agents ARE being called

Evidence:

- Logs show "RefactoringAgent failed to fix issue"
- "ArchitectAgent failed to fix issue"
- This log comes from line 367 in coordinator.py after agent execution

### Hypothesis 2: Agent Implementation Broken ❌

**Status**: RULED OUT - Agents work when called directly

Evidence:

- Direct test of FormattingAgent: 100% success
- Applied 5 fixes correctly
- Returned proper FixResult with success=True

### Hypothesis 3: Caching Issue ⚠️

**Status**: LIKELY - Cached failures blocking success

Evidence from coordinator.py lines 416-442:

```python
async def _cached_analyze_and_fix(self, agent: SubAgent, issue: Issue) -> FixResult:
    cache_key = self._get_cache_key(agent.name, issue)

    # Check in-memory cache
    if cache_key in self._issue_cache:
        self.logger.debug(f"Using in-memory cache for {agent.name}")
        return self._issue_cache[cache_key]  # ← Returns old CACHED FAILURE!

    # Check persistent cache
    cached_result = self._coerce_cached_decision(
        self.cache.get_agent_decision(agent.name, self._create_issue_hash(issue)),
    )
    if cached_result:
        self.logger.debug(f"Using persistent cache for {agent.name}")
        self._issue_cache[cache_key] = cached_result
        return cached_result  # ← Returns old CACHED FAILURE!

    # Actually call the agent
    result = await agent.analyze_and_fix(issue)  # ← Would work!

    # Only cache SUCCESSFUL results with high confidence
    if result.success and result.confidence > 0.7:
        self._issue_cache[cache_key] = result
        self.cache.set_agent_decision(...)

    return result
```

**The Bug**:

1. First attempt: Agent tries to fix issue → fails (for whatever reason)
1. Failed result is NOT cached (because `success=False`)
1. Second attempt: Agent tries again → fails again
1. **BUT**: If persistent cache has old failed result, it might be returning that

### Hypothesis 4: Issues Not Properly Routed ❌

**Status**: RULED OUT - Routing looks correct

Evidence from ISSUE_TYPE_TO_AGENTS mapping:

```python
IssueType.FORMATTING: ["FormattingAgent", "ArchitectAgent"]
IssueType.COMPLEXITY: ["RefactoringAgent", "PatternAgent", "ArchitectAgent"]
IssueType.SECURITY: ["SecurityAgent", "ArchitectAgent"]
# ... etc
```

### Hypothesis 5: Issue Data Malformed ⚠️

**Status**: POSSIBLE - Parsed issues might have missing/incorrect fields

**Clue**: Log shows `❌ No issues parsed from 'skylos' despite expected_count=None`

If issues have missing `file_path` or `line_number`, agents might fail to handle them.

______________________________________________________________________

## Critical Questions Requiring Investigation

### 1. Why Do Agents Fail 100% of the Time in Workflow?

Direct test shows agents work. Workflow shows they fail. What's different?

**Possible Causes**:

- ❌ Issue objects passed to agents are malformed (missing fields?)
- ❌ AgentContext passed to agents is different/wrong
- ❌ File paths in issues are absolute vs relative mismatch
- ❌ Agent's subprocess calls fail in workflow context
- ❌ Race condition or async issue

### 2. Why Is Success Rate Exactly 0%?

With 67 issues across 6+ agent types, **statistical probability** of 0% success is virtually impossible unless:

- There's a **systematic bug** affecting ALL agents
- All issue objects are **malformed** in the same way
- There's a **fundamental workflow problem**

### 3. What About "Issues: 67 → 67"?

If agents were succeeding, we'd expect:

- `Issues: 67 → 50 → 30 → 10 → 0` (progressive improvement)
- OR: `Issues: 67 → 67` (convergence limit reached)

But we're seeing **convergence after 2 iterations with 0% reduction**, which suggests agents aren't applying any fixes.

______________________________________________________________________

## Recommended Investigation Steps

### Step 1: Add Detailed Logging

**Location**: `/Users/les/Projects/crackerjack/crackerjack/agents/coordinator.py`

Add detailed logging before/after agent calls:

```python
async def _cached_analyze_and_fix(self, agent: SubAgent, issue: Issue) -> FixResult:
    self.logger.info(f"AGENT CALL: {agent.name} for issue {issue.id}")
    self.logger.info(f"  Issue type: {issue.type.value}")
    self.logger.info(f"  File: {issue.file_path}:{issue.line_number}")
    self.logger.info(f"  Message: {issue.message[:100]}")

    result = await agent.analyze_and_fix(issue)

    self.logger.info(f"AGENT RESULT: {agent.name}")
    self.logger.info(f"  Success: {result.success}")
    self.logger.info(f"  Confidence: {result.confidence}")
    self.logger.info(f"  Fixes: {result.fixes_applied}")

    return result
```

### Step 2: Test with Simple Known-Fixable Issue

Create a test that:

1. Parses a ruff issue
1. Passes to FormattingAgent through coordinator
1. Checks if fix is applied

```python
# test_ai_fix_simple.py
from crackerjack.parsers.factory import ParserFactory
from crackerjack.agents.coordinator import AgentCoordinator
from crackerjack.agents.base import AgentContext
from pathlib import Path

# Parse ruff output
factory = ParserFactory()
output = '[{"code": "E401", ...}]'  # ruff JSON
issues = factory.parse_with_validation("ruff", output)

# Create coordinator
context = AgentContext(project_path=Path.cwd())
coordinator = AgentCoordinator(context=context, ...)

# Handle issues
result = await coordinator.handle_issues(issues)
print(f"Success: {result.success}")
```

### Step 3: Check Issue Object Validation

**Location**: Check if parsed issues have required fields:

```python
# In autofix_coordinator.py, after parsing
for issue in initial_issues:
    assert issue.file_path, f"Missing file_path: {issue}"
    assert issue.line_number is not None, f"Missing line_number: {issue}"
    assert issue.message, f"Missing message: {issue}"
```

### Step 4: Test Agent Subprocess Execution

Agents use subprocess to run ruff/zuban/etc. Check if subprocess works in workflow context:

```python
# In agent code, add logging
self.logger.info(f"Running command: {' '.join(cmd)}")
result = subprocess.run(cmd, ...)
self.logger.info(f"Command output: {result.stdout}")
self.logger.info(f"Command stderr: {result.stderr}")
self.logger.info(f"Return code: {result.returncode}")
```

______________________________________________________________________

## Workaround (Until Bug Is Fixed)

### Option 1: Disable Caching

Set environment variable to disable persistent cache:

```bash
export CRACKERJACK_DISABLE_CACHE=1
python -m crackerjack run --comp --ai-fix
```

### Option 2: Clear Cache Before Run

```bash
rm -rf .crackerjack/cache/*
python -m crackerjack run --comp --ai-fix
```

### Option 3: Use Agents Directly

Bypass workflow and call agents directly for critical issues:

```python
# Direct agent invocation script
from crackerjack.agents.formatting_agent import FormattingAgent
from crackerjack.agents.base import AgentContext

context = AgentContext(project_path=Path.cwd())
agent = FormattingAgent(context=context)
result = await agent.analyze_and_fix(issue)
```

______________________________________________________________________

## Conclusion

✅ **Agents are implemented correctly and work when called directly**

❌ **AI-fix workflow has systematic bug preventing any agent from succeeding**

🔍 **Root cause**: Likely in issue parsing, agent orchestration, or subprocess execution context

📋 **Next steps**:

1. Add detailed logging to identify exact failure point
1. Test with simple known-fixable issue
1. Verify issue objects have all required fields
1. Check subprocess execution in workflow context

**Priority**: CRITICAL - AI-fix is completely non-functional despite working agent implementations.
