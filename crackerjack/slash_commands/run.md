______________________________________________________________________

## description: Run crackerjack with AI-powered auto-fixing using intelligent session integration. Automatically tries enhanced session-mgmt execution first, then gracefully falls back to standard crackerjack execution if unavailable. Perfect for comprehensive code quality enforcement with zero configuration required.

# /run

Intelligent crackerjack runner that tries session-mgmt:crackerjack-run first with fallback to crackerjack:run for optimal integration with session management systems.

## Usage

```
/run [--debug]
```

### Arguments

- `--debug`: Run in foreground with debug output visible (for troubleshooting)
  - Shows all crackerjack command output directly to console
  - Runs synchronously instead of in background
  - Useful for debugging issues with hooks, tests, or AI fixes
  - No need for progress monitoring - output is immediate

## Description

This slash command provides intelligent crackerjack execution with automatic fallback:

1. **Primary**: Attempts `session-mgmt:crackerjack-run` for enhanced session integration
1. **Fallback**: Uses `crackerjack:run` if session-mgmt is unavailable

Both execution paths use AI agent mode for autonomous code quality enforcement:

- `--ai-fix`: AI auto-fixing mode for structured error output and intelligent fixing
- `--test`: Run tests with comprehensive test coverage
- `--verbose`: Show detailed AI decision-making and execution details

## 💡 Agent Recommendation

**For optimal results, use the `crackerjack-architect` agent alongside `/run`:**

```bash
# 1. Plan with crackerjack-architect first
Task tool with subagent_type="crackerjack-architect" for feature planning

# 2. Run crackerjack for quality enforcement
/run

# 3. Use crackerjack-architect for any remaining issues
```

**Why?** The crackerjack-architect agent ensures code follows crackerjack patterns from the start, reducing the number of iterations needed for `/run` to achieve full compliance.

## What It Does

**Smart Execution Strategy:**

### 1. 🧠 **Session-Mgmt Integration (Primary)**

When `session-mgmt:crackerjack-run` is available:

- **Enhanced Context**: Leverages session history for better AI decisions
- **Progress Continuity**: Builds on previous session learnings
- **Memory Integration**: Remembers past error patterns and fixes
- **Quality Trends**: Uses historical quality metrics for optimization

### 2. 🔄 **Standard Execution (Fallback)**

When session-mgmt is unavailable, falls back to `crackerjack:run`:

- **Full Functionality**: Complete AI auto-fixing capabilities
- **Zero Degradation**: All quality features remain available
- **Seamless Transition**: User experience unchanged

### 3. ⚡ **Iterative AI-Powered Auto-Fixing Process (up to 10 iterations)**

Both execution paths follow the same comprehensive workflow:

#### Pre-Execution Safety Checks:

0. 🔍 **Comprehensive Status Check** (automatic conflict prevention)

   - Check for active crackerjack jobs in the same project to prevent file conflicts
   - Verify MCP and WebSocket server health status
   - Identify beneficial cleanup opportunities (stale temp files, old debug logs)
   - Auto-start missing services if needed
   - Report resource usage and system health

#### Each Iteration Cycle:

1. ⚡ **Fast Hooks** (formatting & basic fixes)

   - Run `trailing-whitespace`, `end-of-file-fixer`, `ruff-format`, `ruff-check`, `gitleaks`
   - If any fail → **Retry fast hooks once** (formatting fixes often resolve downstream issues)
   - Only proceed when fast hooks pass or have been retried

1. 🧪 **Full Test Suite**

   - Run ALL tests, collect ALL test failures (don't stop on first failure)
   - Gather complete list of failing tests with error details

1. 🔍 **Comprehensive Hooks** (type checking, security, complexity)

   - Run `pyright`, `bandit`, `vulture`, `refurb`, `creosote`, `complexipy`
   - Collect ALL hook failures (don't stop on first failure)
   - Gather complete list of quality issues

1. 🤖 **AI Analysis & Batch Fixing**

   - Analyze ALL collected failures (tests + comprehensive hooks)
   - Apply intelligent fixes for ALL issues in one coordinated pass:
     - **Type Errors**: Adds missing annotations, fixes type mismatches
     - **Security Issues**: Removes hardcoded paths, fixes vulnerabilities
     - **Dead Code**: Removes unused imports, variables, functions
     - **Test Failures**: Fixes missing fixtures, import errors, assertions
     - **Code Quality**: Applies refactoring, reduces complexity
     - **Hook Failures**: All formatting, linting, style issues

1. 🔄 **Next Full Iteration**: Repeat entire cycle until ALL checks pass or max iterations (10) reached

#### Final Result:

🎉 **Perfect Code Quality**: All hooks pass, all tests pass, zero manual intervention!

## Example

When an AI assistant uses this command:

```
User: Can you fix all the code quality issues in this project?
AI: I'll use the /run command to automatically fix all code quality issues with intelligent session integration.

/run

[AI first tries: session-mgmt:crackerjack-run]
✅ Session-mgmt available - using enhanced execution mode

[Enhanced execution with session context: python -m crackerjack --ai-fix --test --verbose]

The crackerjack AI agent completed successfully after 2 iterations! Here's what was automatically fixed:

**Session Context Benefits**:
- Leveraged previous session learnings about this codebase
- Applied remembered fix patterns from similar issues
- Optimized execution based on historical performance data

**Iteration 1**: Fixed formatting and imports
- Reformatted 5 files with proper indentation
- Organized imports in 3 modules (using cached preferences)
- Removed trailing whitespace

**Iteration 2**: Final quality improvements
- Added type hints to 4 functions (improved from previous 7 due to session learning)
- All 42 tests now pass with 47% coverage

🎉 **Result**: Perfect code quality achieved with enhanced session integration!
```

## Benefits

- **Smart Integration**: Automatically leverages session-mgmt when available
- **Graceful Fallback**: No functionality loss when session-mgmt unavailable
- **Enhanced Learning**: Session context improves AI decision quality
- **Zero Configuration**: AI doesn't need to remember complex integration logic
- **Optimal Performance**: Uses best available execution method automatically
- **Consistent Results**: Same high-quality outcome regardless of execution path

## Implementation

**CRITICAL**: When an AI assistant encounters `/run`, it MUST implement the intelligent fallback strategy using MCP server tools.

### Execution Strategy

```python
# 1. Try session-mgmt integration first
try:
    job_result = session_mgmt_crackerjack_run()
    job_id = job_result["job_id"]
    print("✅ Using session-mgmt enhanced execution")
except (ConnectionError, ServiceUnavailable, ToolNotFound):
    # 2. Fallback to standard crackerjack execution
    job_result = execute_crackerjack("/crackerjack:run")
    job_id = job_result["job_id"]
    print("⚡ Using standard crackerjack execution")

# For debugging, append --debug flag to either execution path:
# session_mgmt_crackerjack_run("--debug") or execute_crackerjack("/crackerjack:run --debug")
```

### Key Features

- **Automatic Detection**: No manual configuration needed
- **Seamless Fallback**: User unaware of which execution path used
- **Progress Tracking**: Real-time progress updates via MCP tools for both paths
- **Enhanced Context**: Session-mgmt path leverages conversation history
- **Background Execution**: Both paths run in background, return job_id immediately
- **Debug Support**: --debug flag works with both execution methods

**Note**: This command provides the best of both worlds - enhanced session integration when available, with full functionality guaranteed through intelligent fallback.
