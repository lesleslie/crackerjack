______________________________________________________________________

## description: Run Crackerjack with advanced orchestrated AI-powered auto-fix mode to automatically resolve all code quality issues with intelligent execution strategies and granular progress tracking.

# /crackerjack:run

Run Crackerjack with advanced orchestrated AI-powered auto-fix mode to automatically resolve all code quality issues with intelligent execution strategies and granular progress tracking.

## Usage

```
/crackerjack:run [--debug]
```

### Arguments

- `--debug`: Run in foreground with debug output visible (for troubleshooting)
  - Shows all crackerjack command output directly to console
  - Runs synchronously instead of in background
  - Useful for debugging issues with hooks, tests, or AI fixes
  - No need for progress monitoring - output is immediate

## Description

This slash command runs Crackerjack with AI agent mode for autonomous code quality enforcement:

- `--ai-agent`: AI agent mode for structured error output and intelligent fixing
- `--test`: Run tests with comprehensive test coverage
- `--verbose`: Show detailed AI decision-making and execution details

## 💡 Agent Recommendation

**For optimal results, use the `crackerjack-architect` agent alongside `/crackerjack:run`:**

```bash
# 1. Plan with crackerjack-architect first
Task tool with subagent_type="crackerjack-architect" for feature planning

# 2. Run crackerjack for quality enforcement
/crackerjack:run

# 3. Use crackerjack-architect for any remaining issues
```

**Why?** The crackerjack-architect agent ensures code follows crackerjack patterns from the start, reducing the number of iterations needed for `/crackerjack:run` to achieve full compliance.

## What It Does

**Iterative AI-Powered Auto-Fixing Process (up to 10 iterations):**

### Pre-Execution Safety Checks:

0. 🔍 **Comprehensive Status Check** (automatic conflict prevention)

   - Check for active crackerjack jobs in the same project to prevent file conflicts
   - Verify MCP and WebSocket server health status
   - Identify beneficial cleanup opportunities (stale temp files, old debug logs)
   - Auto-start missing services if needed
   - Report resource usage and system health

### Each Iteration Cycle:

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

### Final Result:

🎉 **Perfect Code Quality**: All hooks pass, all tests pass, zero manual intervention!

## Example

When an AI assistant uses this command:

```
User: Can you fix all the code quality issues in this project?
AI: I'll use the /crackerjack:run command to automatically fix all code quality issues.

/crackerjack:run

[AI runs: python -m crackerjack --ai-agent --test --verbose]

The crackerjack AI agent completed successfully after 3 iterations! Here's what was automatically fixed:

**Iteration 1**: Fixed formatting and imports
- Reformatted 5 files with proper indentation
- Organized imports in 3 modules
- Removed trailing whitespace

**Iteration 2**: Resolved type and security issues
- Added type hints to 7 functions
- Fixed 2 hardcoded temp path security warnings
- Removed 1 unused variable

**Iteration 3**: Final test fixes
- Fixed missing test fixture import
- Updated assertion in test_workflow.py
- All 42 tests now pass with 45% coverage

🎉 **Result**: Perfect code quality achieved with zero manual intervention!
```

## Benefits

- **Zero Configuration**: AI doesn't need to remember complex flag combinations
- **Optimal Settings**: Always uses the most effective options
- **Complete Automation**: Handles the entire quality workflow automatically
- **Consistent Results**: Same high-quality outcome every time

## Implementation

**CRITICAL**: When an AI assistant encounters `/crackerjack:run`, it MUST ONLY use the MCP server tools. Never fall back to bash/shell execution of `python -m crackerjack`.

When an AI assistant encounters `/crackerjack:run`, it calls the MCP server tool directly:

**Note**: The WebSocket server on localhost:8675 is automatically started when the command runs, so no manual setup is required.

```python
# Call MCP server tool for orchestrated iterative auto-fixing (returns job_id immediately)
job_result = execute_crackerjack("/crackerjack:run")
job_id = job_result["job_id"]

# For debugging, use the --debug flag:
job_result = execute_crackerjack("/crackerjack:run --debug")
# This runs in foreground and shows all output directly
```

This runs the AI agent auto-fixing process:

- **Background Execution**: Workflow runs in background, returns job_id immediately
- **Progress Tracking**: Real-time progress updates via MCP tools
- **Autonomous Fixing**: Makes actual code changes to resolve all issues
- **Comprehensive Coverage**: Handles ALL error types (not just formatting)
- **Iterative Process**: Continues fixing until perfect quality achieved (up to 10 iterations)
- **Zero Manual Work**: No human intervention required

**Note**: This is NOT the same as basic hook auto-fix modes (like `ruff --fix`) which only handle simple formatting. The AI agent performs sophisticated code analysis and coordinated modification.
