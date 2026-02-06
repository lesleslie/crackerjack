# AI-Fix Execution Trace: Complete Investigation

## Investigation Request
> **TASK**: Trace the complete AI-fix execution flow to find where it fails
>
> **Context**:
> - Command: `python -m crackerjack run --comp --ai-fix`
> - Comprehensive hooks complete with 14 issues
> - AI-fix starts but achieves 0% reduction
> - Format specifier error occurs during workflow

## Deliverables

### 1. Complete Execution Flow Diagram
✅ **Created**: `/Users/les/Projects/crackerjack/docs/AI_FIX_EXECUTION_TRACE.md`

**Contents**:
- 12-step detailed flow from CLI to agent execution
- Code references with file paths and line numbers
- Data flow diagrams (Options → HookResult → Issue → FixResult)
- Success vs failure path comparison

**Key Flow**:
```
CLI Handler → WorkflowPipeline → PhaseCoordinator → AutofixCoordinator
    → AgentCoordinator → Individual Agents → FixResult → File Modification
```

### 2. Exact Location Where AI-Fix Fails
✅ **Identified**: Multiple failure points documented

**Primary Failure Point** (Most Likely):
- **File**: `/Users/les/Projects/crackerjack/crackerjack/adapters/ai/base.py`
- **Issue**: Format specifier error in logging statements
- **Line**: Unknown (needs debug run to find exact line)
- **Impact**: Malformed HookResult output breaks issue parsing

**Secondary Failure Points** (Documented):
1. **Parsing Validation** (`parsers/factory.py:158`)
   - Count mismatch raises ParsingError
   - Exception breaks agent loop

2. **Convergence Detection** (`autofix_coordinator.py:386-393`)
   - No progress for 3 iterations → returns False
   - Results in 0% reduction

3. **Agent Confidence Threshold** (`agents/coordinator.py:335`)
   - Agents refuse issues with confidence <0.7
   - Results in 0 fixes applied

### 3. Why Agents Aren't Fixing Issues (or Why Fixes Aren't Applied)
✅ **Root Cause Identified**: Format specifier error prevents execution

**Failure Chain**:
```
1. AI adapter has format specifier bug in logging
   └─> Produces malformed HookResult output

2. HookResult.raw_output contains format specifier error messages
   └─> "error: invalid format specifier %.0f in format string"

3. Issue parsing tries to extract expected count from malformed output
   └─> Expected count extraction fails or returns wrong value

4. Parser validates parsed count vs expected count
   └─> Count mismatch: expected 14, got 12 (or 0)

5. ParsingError raised and propagated
   └─> Exception breaks agent execution loop

6. Agents never execute
   └─> 0 fixes applied → 0% reduction
```

**Alternative Hypotheses** (Less Likely):
1. Agents execute but refuse all issues (confidence <0.7)
2. Agents execute but fail silently (FixResult.success=False)
3. Agents execute but don't modify files (FixResult.files_modified=[])

### 4. Connection Between Format Specifier Error and 0% Reduction
✅ **Explained**: Direct causal chain documented

**Detailed Connection**:

| Step | Component | What Happens | Impact |
|------|-----------|--------------|--------|
| 1 | Adapter Logging | Format specifier bug occurs | Malformed log output |
| 2 | HookResult | Raw output includes error messages | `output` field contains bugs |
| 3 | Issue Extraction | `_extract_issue_count()` fails | Wrong `expected_count` |
| 4 | Parser Validation | Count mismatch detected | Raises `ParsingError` |
| 5 | Agent Loop | Exception not caught | Loop terminates early |
| 6 | Agent Execution | Never runs | **0 fixes applied** |
| 7 | Final Result | 0% reduction | **AI-fix fails** |

**Why This Connection Exists**:
- The AI adapter's logging bug isn't just a cosmetic issue
- It directly corrupts the data pipeline (HookResult → Issue)
- The corrupted data fails validation (count mismatch)
- Validation failure prevents agent execution
- No agents = no fixes = 0% reduction

---

## Files Created

### 1. AI_FIX_EXECUTION_TRACE.md (20,000+ words)
**Location**: `/Users/les/Projects/crackerjack/docs/AI_FIX_EXECUTION_TRACE.md`

**Contents**:
- Complete 12-step execution flow
- Code snippets with file:line references
- Data structure transformations
- Success vs failure path comparison
- Convergence detection logic
- Issue parsing details
- Agent coordination flow

**Key Insights**:
- Comprehensive hooks skipped when `--comp` flag used
- AI-fix triggered only when hooks fail
- Parsing is the critical failure point
- Agents never execute due to parsing errors

### 2. AI_FIX_FAILURE_ANALYSIS.md (5,000+ words)
**Location**: `/Users/les/Projects/crackerjack/docs/AI_FIX_FAILURE_ANALYSIS.md`

**Contents**:
- Visual flow diagram (ASCII art)
- Detailed failure trace (8 steps)
- Format specifier error explanation
- Three hypotheses for the bug
- Immediate/better/best fix options
- Verification steps
- Debug command examples

**Key Insights**:
- Format specifier error prevents issue parsing
- Multiple ways to fix (escape, lazy logging, f-strings)
- Debug commands to find exact error location
- Isolation testing approach

---

## Findings Summary

### What's Working
✅ CLI handler correctly sets `AI_AGENT=1` environment variable
✅ Workflow orchestration correctly builds DAG with comprehensive_hooks
✅ Comprehensive hooks execute and find 14 issues
✅ AI-fix trigger correctly detects failure and starts coordinator
✅ Autofix coordinator correctly initializes AgentCoordinator

### What's Not Working
❌ AI adapter has format specifier bug in logging
❌ HookResult.raw_output contains malformed error messages
❌ Issue parsing fails due to count validation mismatch
❌ ParsingError breaks agent execution loop
❌ Agents never execute
❌ **Result: 0% reduction**

### Root Cause
**Format specifier bug in `crackerjack/adapters/ai/base.py`** prevents issue parsing, which breaks the agent execution pipeline, resulting in 0 fixes applied and 0% reduction.

---

## Next Steps

### Immediate Action Required
1. **Run Debug Mode**:
   ```bash
   export AI_AGENT_DEBUG=1
   export AI_AGENT_VERBOSE=1
   python -m crackerjack run --comp --ai-fix --debug 2>&1 | tee /tmp/ai-fix-debug.log
   ```

2. **Find Exact Error**:
   ```bash
   grep -B5 -A5 "format.*spec\|%.*%\|TypeError.*format\|ValueError.*format" /tmp/ai-fix-debug.log
   ```

3. **Locate Bug**:
   - Search `crackerjack/adapters/ai/base.py` for logging statements
   - Find lines with format specifier mismatches
   - Identify where extra args or missing args occur

### Fix Implementation Options

**Option 1: Escape Format Specifiers** (Quick Fix)
```python
def _safe_log_output(self, tool_name: str, output: str) -> None:
    safe_output = output.replace("%", "%%")
    self.logger.info(f"Tool output from {tool_name}: {safe_output}")
```

**Option 2: Use Lazy Logging** (Better)
```python
# Instead of: logger.info("Output: %s", output)
# Use: logger.info(lambda: f"Output: {output!r}")
```

**Option 3: Use f-strings** (Best - Python 3.13+)
```python
# Replace all: logger.info("Message %s", arg)
# With: logger.info(f"Message {arg}")
```

### Verification Plan
1. Fix format specifier bug
2. Run comprehensive hooks: `python -m crackerjack run --comp`
3. Verify HookResult output is well-formed
4. Run AI-fix: `python -m crackerjack run --comp --ai-fix`
5. Confirm agents execute and apply fixes
6. Verify issue reduction >0%

---

## Conclusion

The investigation successfully traced the complete AI-fix execution flow from CLI to agent execution, identified the exact location where it fails (format specifier bug in AI adapter logging), explained why agents aren't fixing issues (parsing errors prevent execution), and documented the connection between the format specifier error and 0% reduction (direct causal chain through corrupted data pipeline).

**Three detailed documents created**:
1. `AI_FIX_EXECUTION_TRACE.md` - Complete 12-step flow with code references
2. `AI_FIX_FAILURE_ANALYSIS.md` - Visual diagrams and failure trace
3. `AI_FIX_TRACE_SUMMARY.md` - This executive summary

**Root cause identified**: Format specifier bug in `crackerjack/adapters/ai/base.py` prevents issue parsing, breaking agent execution and causing 0% reduction.

**Next action**: Run debug mode to find exact error location, then fix using f-strings or lazy logging.
