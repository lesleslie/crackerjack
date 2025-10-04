# Auto-Fix Workflow Guide

This guide explains how to use crackerjack's AI-powered auto-fix workflow to automatically detect and repair code quality issues.

## Overview

The auto-fix workflow uses Claude AI to iteratively fix code issues detected by pre-commit hooks. It runs in a loop:

1. **Detect**: Run quality checks (lint, type checking, tests)
1. **Fix**: Apply AI-powered fixes to failing hooks
1. **Verify**: Re-run checks to confirm fixes
1. **Repeat**: Continue until all checks pass or max iterations reached

## Prerequisites

### 1. API Key Configuration

Set your Anthropic API key as an environment variable:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Or add to your shell profile (`~/.zshrc`, `~/.bashrc`):

```bash
echo 'export ANTHROPIC_API_KEY=sk-ant-...' >> ~/.zshrc
source ~/.zshrc
```

### 2. Adapter Configuration

Create or update `settings/adapters.yml`:

```yaml
ai: claude
```

### 3. Project Setup

Ensure your project has:

- Pre-commit hooks configured (`.pre-commit-config.yaml`)
- Python 3.13+ environment
- ACB with AI adapter installed: `uv add "acb[ai]"`

## Basic Usage

### Standard Auto-Fix

Run auto-fix with default settings (max 10 iterations):

```bash
python -m crackerjack --ai-fix --run-tests --verbose
```

This will:

- Run all pre-commit hooks
- Apply AI fixes for any failures
- Re-run hooks to verify fixes
- Continue for up to 10 iterations
- Stop when all hooks pass

### Dry-Run Mode

Preview fixes without applying them:

```bash
python -m crackerjack --dry-run --run-tests --verbose
```

Dry-run mode:

- Shows what fixes would be applied
- Doesn't modify any files
- Useful for reviewing AI suggestions
- Automatically enables `--ai-fix`

### Custom Iteration Limit

Control maximum fix attempts:

```bash
# Allow up to 15 fix iterations
python -m crackerjack --ai-fix --max-iterations 15

# Allow up to 5 iterations (faster, less thorough)
python -m crackerjack --ai-fix --max-iterations 5
```

## Advanced Usage

### Targeting Specific Commands

Use semantic commands to control which hooks run:

```bash
# Run only fast hooks (lint, format)
python -m crackerjack --ai-fix lint

# Run comprehensive checks (test, type checking, security)
python -m crackerjack --ai-fix check

# Run everything
python -m crackerjack --ai-fix all
```

### Combining with Other Options

```bash
# Auto-fix with version bump and commit
python -m crackerjack --ai-fix -p 0.1.2 -c

# Auto-fix with verbose output and custom timeout
python -m crackerjack --ai-fix --verbose --timeout 600
```

## MCP Integration

When using crackerjack via MCP tools (session-mgmt-mcp):

### ✅ Correct Usage

Use the `ai_agent_mode` parameter with semantic commands:

```python
# Enable AI auto-fix mode
await crackerjack_run(command="test", ai_agent_mode=True)

# With additional arguments
await crackerjack_run(
    command="check", args="--verbose", ai_agent_mode=True, timeout=600
)

# Dry-run mode
await crackerjack_run(command="lint", args="--dry-run --verbose", ai_agent_mode=True)
```

### ❌ Incorrect Usage

Don't put flags in the command parameter:

```python
# WRONG - This will error!
await crackerjack_run(command="--ai-fix -t")

# WRONG - Use ai_agent_mode instead
await crackerjack_run(command="test", args="--ai-fix")
```

The MCP integration automatically translates `ai_agent_mode=True` to the appropriate CLI flags.

## Understanding the Workflow

### Iteration Loop

Each iteration follows this sequence:

1. **Hook Execution**: Run pre-commit hooks based on command

   - `test/check/all`: Comprehensive hooks (slower, thorough)
   - `lint/format`: Fast hooks (quick feedback)

1. **Issue Detection**: Parse hook failures

   - Identify failing hooks (refurb, pyright, pytest, etc.)
   - Extract error messages and context
   - Convert to Issue objects for AI processing

1. **AI Fixing**: Apply fixes via Claude AI

   - Send issue context to Claude API
   - Generate code fixes with confidence scores
   - Validate fixes meet minimum confidence threshold (0.7)
   - Apply fixes to files with backup creation

1. **Verification**: Re-run hooks

   - Confirm fixes resolved the issues
   - Detect any new issues introduced
   - Track iteration metrics (fixes applied, success rate)

1. **Convergence Check**:

   - **Success**: All hooks passing → Exit with success
   - **No Progress**: No fixes applied → Exit with warning
   - **Continue**: Issues remain and fixes applied → Next iteration

### Convergence Criteria

The workflow stops when:

1. **All Passing**: All hooks pass successfully
1. **No Progress**: No fixes can be applied (confidence too low)
1. **Max Iterations**: Reached iteration limit (default: 10)

### Issue Type Mapping

Different hooks map to different AI fix strategies:

| Hook | Issue Type | AI Strategy |
|------|------------|-------------|
| refurb | DRY_VIOLATION | Extract common patterns, eliminate duplication |
| pyright | TYPE_ERROR | Add type annotations, fix type mismatches |
| bandit | SECURITY | Remove unsafe patterns, add input validation |
| ruff | FORMATTING | Apply PEP 8 style, fix import order |
| pytest | TEST_FAILURE | Fix test logic, update assertions |
| complexipy | COMPLEXITY | Break down complex functions, extract methods |
| vulture | DEAD_CODE | Remove unused code, clean imports |
| creosote | DEPENDENCY | Update requirements, remove unused deps |

## Workflow Results

After completion, the workflow provides:

### Success Summary

```
━━━ Auto-Fix Summary ━━━
✅ Status: converged
📊 Statistics:
  • Iterations: 3
  • Total issues found: 14
  • Total fixes applied: 14
  • Total duration: 45.23s
  • Exit reason: convergence

📋 Iteration Breakdown:
  ❌ Iteration 1: 5/6 fixes successful (12.45s)
  ❌ Iteration 2: 7/8 fixes successful (18.32s)
  ✅ Iteration 3: 0/0 fixes successful (14.46s)
```

### Incomplete Result

```
━━━ Auto-Fix Summary ━━━
⚠️  Status: incomplete
📊 Statistics:
  • Iterations: 10
  • Total issues found: 20
  • Total fixes applied: 18
  • Total duration: 120.55s
  • Exit reason: max_iterations

📋 Iteration Breakdown:
  ❌ Iteration 1: 8/10 fixes successful (15.23s)
  ❌ Iteration 2: 6/8 fixes successful (14.12s)
  ...
  ❌ Iteration 10: 4/5 fixes successful (11.89s)
```

## Troubleshooting

### Common Issues

#### 1. API Key Not Set

```
Error: ANTHROPIC_API_KEY environment variable not set
```

**Solution**: Export the API key:

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

#### 2. Adapter Not Configured

```
Error: AI adapter not configured in settings/adapters.yml
```

**Solution**: Add to `settings/adapters.yml`:

```yaml
ai: claude
```

#### 3. Low Confidence Fixes

```
⚠️  No fixes applied - cannot make progress
```

**Solution**:

- Review the issues manually
- The AI confidence threshold (0.7) wasn't met
- Consider fixing complex issues manually first
- Try with `--dry-run` to see suggested fixes

#### 4. Max Iterations Reached

```
⚠️  Max iterations (10) reached without full convergence
```

**Solution**:

- Increase iteration limit: `--max-iterations 15`
- Review remaining issues in the output
- Some issues may require manual intervention
- Check if new issues are being introduced

#### 5. Import Errors

```
Error: Cannot import ClaudeCodeFixer - install ACB with AI adapter
```

**Solution**:

```bash
uv add "acb[ai]"
```

### Debug Output

Enable verbose logging to see detailed workflow progress:

```bash
python -m crackerjack --ai-fix --verbose --run-tests
```

This shows:

- Each hook execution result
- AI fix generation details
- Confidence scores for each fix
- File modification status
- Iteration timing

## Best Practices

### 1. Start with Dry-Run

Always preview fixes before applying:

```bash
python -m crackerjack --dry-run --run-tests --verbose
```

### 2. Use Version Control

Commit your work before running auto-fix:

```bash
git add .
git commit -m "Before auto-fix"
python -m crackerjack --ai-fix --run-tests
```

### 3. Review AI Changes

After auto-fix completes:

```bash
git diff  # Review all changes
git add -p  # Stage changes selectively if needed
```

### 4. Iterate Incrementally

For large codebases, fix issues incrementally:

```bash
# First pass: formatting and simple fixes
python -m crackerjack --ai-fix lint --max-iterations 5

# Second pass: type checking
python -m crackerjack --ai-fix check --max-iterations 5

# Final pass: comprehensive
python -m crackerjack --ai-fix all --max-iterations 10
```

### 5. Combine with Manual Fixes

Let AI handle routine fixes, reserve manual effort for complex issues:

1. Run auto-fix to handle bulk issues
1. Review remaining failures
1. Manually fix complex cases
1. Run auto-fix again to clean up

## Performance Tips

### 1. Use Semantic Commands

Choose the right command for your needs:

- `lint`: Fastest (formatting, imports)
- `check`: Balanced (type checking, security)
- `test`: Thorough (includes test suite)
- `all`: Comprehensive (everything)

### 2. Adjust Iteration Limit

Balance thoroughness vs. speed:

- Quick fixes: `--max-iterations 5`
- Standard: `--max-iterations 10` (default)
- Thorough: `--max-iterations 15`

### 3. Increase Timeout

For large codebases or slow tests:

```bash
python -m crackerjack --ai-fix --timeout 1200  # 20 minutes
```

## Workflow Architecture

### Components

1. **AutoFixWorkflow** (`workflows/auto_fix.py`)

   - Orchestrates the iteration loop
   - Manages convergence detection
   - Tracks metrics and results

1. **EnhancedAgentCoordinator** (`agents/enhanced_coordinator.py`)

   - Coordinates fix application
   - Manages agent selection
   - Handles external agent consultation

1. **ClaudeCodeFixer** (`adapters/ai/claude.py`)

   - Real AI integration with Claude API
   - Generates code fixes with context
   - Validates fix confidence and safety

1. **AsyncHookManager** (`managers/async_hook_manager.py`)

   - Runs pre-commit hooks asynchronously
   - Parses hook results
   - Provides hook selection strategies

### Data Flow

```
CLI Command
    ↓
AutoFixWorkflow.run()
    ↓
Loop (max iterations):
    ↓
    AsyncHookManager.run_hooks()
    ↓
    Parse failures → Issue objects
    ↓
    EnhancedAgentCoordinator.handle_issues()
    ↓
    ClaudeCodeFixer.fix_code_issue()
    ↓
    SafeFileModifier.apply_fix()
    ↓
    Check convergence
    ↓
End loop
    ↓
Return WorkflowResult
```

## Example Workflows

### Scenario 1: Type Checking Errors

```bash
# Initial state: 14 type errors
python -m crackerjack --ai-fix check --verbose

# Output:
# Iteration 1: Fixed 12/14 issues
# Iteration 2: Fixed 2/2 issues
# ✅ All hooks passing - convergence achieved!
```

### Scenario 2: Test Failures

```bash
# Initial state: 5 failing tests
python -m crackerjack --ai-fix test --max-iterations 15

# Output:
# Iteration 1: Fixed 3/5 tests
# Iteration 2: Fixed 2/2 tests
# ✅ All hooks passing - convergence achieved!
```

### Scenario 3: Complex Refactoring

```bash
# Step 1: Preview fixes
python -m crackerjack --dry-run all

# Step 2: Apply fixes incrementally
python -m crackerjack --ai-fix lint --max-iterations 5

# Step 3: Review changes
git diff

# Step 4: Continue with type checking
python -m crackerjack --ai-fix check --max-iterations 10

# Step 5: Final comprehensive check
python -m crackerjack --ai-fix all
```

## Security Considerations

### File Safety

The auto-fix workflow includes safety features:

1. **Backup Creation**: Original files backed up before modification
1. **Confidence Threshold**: Fixes below 0.7 confidence rejected
1. **Dry-Run Mode**: Preview changes without applying
1. **Git Integration**: Easy rollback with version control

### API Security

Protect your Anthropic API key:

1. **Never commit**: Add to `.gitignore` or use environment variables
1. **Rotate regularly**: Update keys periodically
1. **Monitor usage**: Track API consumption in Anthropic dashboard
1. **Restrict access**: Use project-specific keys when possible

## Further Reading

- **Implementation Plan**: `/Users/les/Projects/acb/CRACKERJACK-FIX-IMPLEMENTATION-PLAN.md`
- **Workflow Code**: `/Users/les/Projects/crackerjack/crackerjack/workflows/auto_fix.py`
- **AI Adapter**: `/Users/les/Projects/crackerjack/crackerjack/adapters/ai/claude.py`
- **Agent Coordinator**: `/Users/les/Projects/crackerjack/crackerjack/agents/enhanced_coordinator.py`
- **CLI Options**: `/Users/les/Projects/crackerjack/crackerjack/cli/options.py`

## Support

For issues or questions:

1. Check this guide and troubleshooting section
1. Review implementation plan for technical details
1. Examine workflow logs with `--verbose`
1. Report bugs with detailed reproduction steps
