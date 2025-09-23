# Pre-commit Hook Handling Documentation

This directory contains documentation about how Crackerjack handles pre-commit hooks.

## Files

- `CRACKERJACK_PRECOMMIT_HANDLING_IMPLEMENTATION_SUMMARY.md` - Technical implementation details
- `FINAL_PRECOMMIT_HANDLING_VERIFICATION.md` - Final verification of the implementation
- `PRECOMMIT_HANDLING_SUMMARY.md` - Summary of pre-commit hook handling

## Key Points

Crackerjack provides flexible control over pre-commit hooks:

1. **Skip Hooks Option**: Use the `-s` or `--skip-hooks` flag to skip all pre-commit hook execution
1. **Initialization Behavior**: New projects no longer automatically get pre-commit configuration
1. **User Control**: Users can choose when to run or skip hooks

## Usage

```bash
# Skip hooks during normal workflow
python -m crackerjack -s

# Skip hooks during testing
python -m crackerjack -s -t

# Skip hooks during full release workflow
python -m crackerjack -s -a patch
```
