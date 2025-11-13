# Refurb and Creosote Behavior Documentation

**Date**: 2025-11-10
**Purpose**: Document when refurb and creosote fail builds and trigger autofix

______________________________________________________________________

## Executive Summary

| Hook | Security Level | Fails Build? | Autofix Support | Severity Filtering |
|------|----------------|--------------|-----------------|-------------------|
| **Refurb** | MEDIUM | ✅ Yes (on issues found) | ❌ No | All warnings fail |
| **Creosote** | HIGH | ✅ Yes (on issues found) | ❌ No | All warnings fail |

______________________________________________________________________

## Refurb (Python Refactoring Suggestions)

### Configuration

- **File**: `crackerjack/config/hooks.py:301-309`
- **Security Level**: `MEDIUM`
- **Timeout**: 240s (4 minutes)
- **Stage**: Comprehensive hooks
- **Incremental Execution**: ✅ Enabled (`accepts_file_paths=True`)

### When Refurb Fails Builds

**Exit Code Behavior:**

- Exit code 0: No refactoring suggestions → ✅ PASS
- Exit code 1+: Refactoring suggestions found → ❌ FAIL

**All FURB codes cause build failure**, including:

- FURB101: Use dict comprehension
- FURB109: Use operator.itemgetter
- FURB110: Use operator.methodcaller
- FURB118: Use operator.attrgetter
- And ~140 other refactoring patterns

**Why It Fails:**

1. Refurb is a **checker**, not a formatter
1. Security level (MEDIUM) is metadata - not currently enforcing behavior
1. Hook has `retry_on_failure=False` and `is_formatting=False`
1. Non-zero exit code = build failure

### Autofix Support

**Status**: ❌ **Not Implemented**

Refurb does not support automatic fixing. It only provides suggestions.

**Example Output:**

```
file.py:10:5 [FURB101]: Use dict comprehension instead of dict() with generator expression
```

**How to Fix:**

- Manual code changes required
- Refurb shows the pattern but doesn't rewrite code
- AI agent system (`--ai-fix`) can attempt fixes for high-confidence patterns

______________________________________________________________________

## Creosote (Unused Dependency Detection)

### Configuration

- **File**: `crackerjack/config/hooks.py:311-318`
- **Security Level**: `HIGH`
- **Timeout**: 180s (3 minutes)
- **Stage**: Comprehensive hooks
- **Incremental Execution**: ❌ Disabled (analyzes entire dependency graph)

### When Creosote Fails Builds

**Exit Code Behavior:**

- Exit code 0: No unused dependencies → ✅ PASS
- Exit code 1+: Unused dependencies found → ❌ FAIL

**All unused dependencies cause build failure:**

- Direct dependencies in `pyproject.toml` that are never imported
- Extra groups with unused packages
- Development dependencies that aren't used

**Why It Fails:**

1. Creosote is a **checker**, not a fixer
1. Security level (HIGH) indicates dependency hygiene is important
1. Hook has `retry_on_failure=False` and `is_formatting=False`
1. Non-zero exit code = build failure

### Autofix Support

**Status**: ❌ **Not Implemented**

Creosote does not support automatic fixing. It only reports unused dependencies.

**Example Output:**

```
The following dependencies are unused:
  - requests (not imported in any Python file)
  - pandas (not imported in any Python file)
```

**How to Fix:**

- Manual removal from `pyproject.toml` required
- Use `uv remove <package>` to cleanly uninstall
- AI agent system (`--ai-fix`) can attempt dependency removal

______________________________________________________________________

## Security Level Semantics

**Current Implementation**:
Security levels are **metadata only** - they don't enforce behavior yet.

| Level | Intent | Current Behavior |
|-------|--------|------------------|
| LOW | Cosmetic issues | Fails on non-zero exit |
| MEDIUM | Code quality | Fails on non-zero exit |
| HIGH | Dependencies/types | Fails on non-zero exit |
| CRITICAL | Security/secrets | Fails on non-zero exit |

**All hooks fail builds based on exit code, regardless of security level.**

______________________________________________________________________

## Comparison with Formatters

**Formatters** (e.g., ruff-format, mdformat):

- `is_formatting=True`
- `retry_on_failure=True`
- Auto-fix issues and retry
- Exit code ignored after fixing

**Checkers** (refurb, creosote):

- `is_formatting=False`
- `retry_on_failure=False`
- Report issues only
- Exit code determines pass/fail

______________________________________________________________________

## AI Agent Integration

Both tools can be handled by crackerjack's AI agent system:

**Refurb Fixes**:

```bash
python -m crackerjack --ai-fix --comp
```

- RefactoringAgent (confidence: 0.9) handles FURB codes
- Applies modern Python idioms
- Requires code review (high-impact changes)

**Creosote Fixes**:

```bash
python -m crackerjack --ai-fix --comp
```

- DRYAgent (confidence: 0.8) or RefactoringAgent
- Removes unused dependencies from `pyproject.toml`
- Runs `uv sync` after changes
- Safer than refurb (no code logic changes)

______________________________________________________________________

## Future Enhancements

**Potential Security Level Enforcement:**

1. **MEDIUM** (refurb): Warn only, don't fail
1. **HIGH** (creosote): Fail build
1. **CRITICAL** (semgrep, zuban): Always fail

**Potential Autofix:**

1. Integrate refurb with AST rewriting for safe transformations
1. Automate creosote dependency removal with user confirmation
1. Add `--autofix` mode for checkers

______________________________________________________________________

## References

- Refurb adapter: `crackerjack/adapters/refactor/refurb.py`
- Creosote adapter: `crackerjack/adapters/refactor/creosote.py`
- Hook configuration: `crackerjack/config/hooks.py`
- Comprehensive hooks audit: `docs/comprehensive_hooks_audit.md`
