# /crackerjack

Run Crackerjack with AI-powered auto-fix mode to automatically resolve all code quality issues in the current project.

## Usage

```
/crackerjack
```

## Description

This slash command runs Crackerjack with the optimal configuration for autonomous code quality enforcement:
- `--ai-agent-autofix`: Combined AI agent and auto-fix mode
- `--test`: Run tests after quality checks
- `--track-progress`: Enable session progress tracking
- `--verbose`: Show detailed AI decision-making

## What It Does

1. 🚀 **Fast Hooks**: Runs basic formatting and linting checks
2. 🤖 **AI Auto-Fix**: Automatically fixes any issues found
3. ✅ **Tests**: Runs test suite (only if fast hooks pass)
4. 🤖 **AI Auto-Fix**: Fixes any test-related issues
5. 🔍 **Comprehensive Hooks**: Runs advanced analysis (security, types, complexity)
6. 🤖 **AI Auto-Fix**: Applies advanced fixes for remaining issues
7. 🎉 **Success**: Perfect code quality achieved automatically!

## Example

When an AI assistant uses this command:

```
User: Can you fix all the code quality issues in this project?
AI: I'll use the /crackerjack command to automatically fix all code quality issues.

/crackerjack

[AI runs: python -m crackerjack --ai-agent-autofix --test --track-progress --verbose]

The crackerjack quality check completed successfully! Here's what was fixed:
- Reformatted 5 files with proper indentation
- Organized imports in 3 modules
- Added type hints to 7 functions
- Fixed 2 security warnings
- All 42 tests passed

Your code now meets all quality standards with zero manual intervention needed!
```

## Benefits

- **Zero Configuration**: AI doesn't need to remember complex flag combinations
- **Optimal Settings**: Always uses the most effective options
- **Complete Automation**: Handles the entire quality workflow automatically
- **Consistent Results**: Same high-quality outcome every time

## Implementation

When an AI assistant encounters `/crackerjack`, it should execute:

```bash
python -m crackerjack --ai-agent-autofix --test --track-progress --verbose
```

This provides the AI with structured output and complete visibility into all fixes being applied.