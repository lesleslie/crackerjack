# AST Transform Engine Design

**Date:** 2026-02-22
**Status:** Approved
**Author:** Claude + User collaborative design

## Overview

Enhance PlanningAgent to handle complex refactoring (cognitive complexity reduction) using AST-based code transformation with graceful degradation.

## Problem Statement

PlanningAgent's `_generate_changes()` method can only handle simple patterns (adding TODO comments, type ignore comments). For complex issues like cognitive complexity > 15, it cannot generate meaningful fixes, resulting in:

- Empty plans returning `success=True` (now fixed)
- 34+ plans failing per run
- No actual complexity reduction

## Design Decision

**Approach:** Pattern-based extraction (A) falling back to Full AST surgery (B)

**Failure Strategy:** Try smaller transformation (2) with iterative refinement (3) as fallback

**Library Choice:** Libcst (primary) → Redbaron (fallback for formatting preservation)

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PlanningAgent                                │
│  - Receives Issue from AnalysisCoordinator                          │
│  - Determines issue type (COMPLEXITY, TYPE_ERROR, etc.)            │
│  - Delegates complexity issues to ASTTransformEngine                │
└───────────────────────────────┬─────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      ASTTransformEngine (new)                        │
│                                                                      │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐      │
│  │  PatternMatcher │  │  LibcstSurgeon  │  │ RedbaronSurgeon │      │
│  │  (AST-based)    │  │  (primary)      │  │  (fallback)     │      │
│  │                 │  │                 │  │                 │      │
│  │ • EarlyReturn   │  │ • CST transforms│  │ • FST preserves │      │
│  │ • GuardClause   │  │ • Type-safe     │  │   formatting    │      │
│  │ • ExtractMethod │  │ • Well-maintained│  │ • Exact matches │      │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘      │
│           │                    │                    │               │
│           └────────────────────┼────────────────────┘               │
│                                ▼                                    │
│                    ┌─────────────────────┐                          │
│                    │  TransformValidator │                          │
│                    │  • Syntax check     │                          │
│                    │  • Complexity delta │                          │
│                    │  • Behavior compare │                          │
│                    └─────────────────────┘                          │
└─────────────────────────────────────────────────────────────────────┘
```

## Components

### PatternMatcher (`pattern_matcher.py`)

Identifies refactoring opportunities using AST analysis.

**Patterns (ordered by simplicity):**

| Pattern | Complexity Reduction | When It Matches |
|---------|---------------------|-----------------|
| `EarlyReturnPattern` | 1-3 per branch | `if x: do_stuff` → `if not x: return; do_stuff` |
| `GuardClausePattern` | 1-2 per guard | Nested validation at function start |
| `ExtractMethodPattern` | 3-10 per extraction | Cohesive code block with clear inputs/outputs |
| `DecomposeConditionalPattern` | 2-5 per branch | Complex boolean expressions |

### LibcstSurgeon (`libcst_surgeon.py`)

Primary transformer using libcst for type-safe CST manipulation.

- Preserves comments in most cases
- Type-safe node replacement
- Well-documented API from Meta

### RedbaronSurgeon (`redbaron_surgeon.py`)

Fallback transformer using Redbaron for exact formatting preservation.

**When used:**
- Libcst produces valid code but formatting differs significantly
- Complex comment placement that libcst mishandles

### TransformValidator (`transform_validator.py`)

**Validation gates:**
1. **Syntax check:** `ast.parse()` succeeds
2. **Complexity reduction:** New complexity < original complexity
3. **Behavior preservation:** Same function signatures, no deleted statements

## Data Flow

```
1. ASTTransformEngine.transform(issue, context)
   │
   ▼
2. Read file content → Parse to AST
   │
   ▼
3. PatternMatcher.match(ast_node)
   │
   ├─▶ EarlyReturnPattern.match() ──▶ match? ──┐
   ├─▶ GuardClausePattern.match() ──▶ match? ──┤
   ├─▶ ExtractMethodPattern.match() ──▶ match? ──┤
   └─▶ DecomposeConditional.match() ──▶ match? ─┘
   │
   ▼ (first match or None)

4. IF match:
   │
   ├─▶ LibcstSurgeon.apply(code, match)
   │        │
   │        ▼
   │   TransformValidator.validate(original, transformed)
   │        │
   │        ├─▶ VALID ──▶ return ChangeSpec
   │        │
   │        └─▶ INVALID ──▶ Try RedbaronSurgeon
   │                      │
   │                      ▼
   │                 TransformValidator.validate()
   │                      │
   │                      ├─▶ VALID ──▶ return ChangeSpec
   │                      │
   │                      └─▶ INVALID ──▶ return None
   │
5. IF no match OR all surgeons fail:
   │
   └─▶ return None (PlanningAgent will mark for manual review)
```

## Error Handling

| Error Type | Example | Recovery Strategy |
|------------|---------|-------------------|
| ParseError | Invalid Python syntax | Mark for manual review |
| NoPatternMatch | Code doesn't match any pattern | Try simpler patterns, then manual review |
| TransformFailed | Libcst raises exception | Try RedbaronSurgeon, then manual review |
| ValidationFailed | Syntax invalid after transform | Rollback, try fallback, then manual review |
| ComplexityNotReduced | Transform valid but complexity same/↑ | Try different pattern, then manual review |
| BehaviorChanged | Function signature modified | Reject, try alternative approach |

## File Structure

```
crackerjack/
└── agents/
    └── helpers/
        └── ast_transform/
            ├── __init__.py
            ├── engine.py              # ASTTransformEngine
            ├── pattern_matcher.py     # PatternMatcher + base Pattern class
            ├── patterns/
            │   ├── __init__.py
            │   ├── early_return.py
            │   ├── guard_clause.py
            │   ├── extract_method.py
            │   └── decompose_conditional.py
            ├── surgeons/
            │   ├── __init__.py
            │   ├── base.py            # BaseSurgeon interface
            │   ├── libcst_surgeon.py
            │   └── redbaron_surgeon.py
            ├── validator.py           # TransformValidator
            └── exceptions.py          # TransformError hierarchy
```

## Dependencies

Add to `pyproject.toml`:
```toml
dependencies = [
    # ... existing ...
    "libcst>=1.0.0",
    "redbaron>=0.9.2",
]
```

## Testing Strategy

### Test Pyramid

```
                ┌─────────────────────┐
                │   E2E Integration   │  ← Full pipeline tests
                │     (5-10 tests)    │
                └──────────┬──────────┘
                           │
            ┌──────────────┴──────────────┐
            │     Integration Tests       │  ← Pattern + Surgeon + Validator
            │       (20-30 tests)         │
            └──────────────┬──────────────┘
                           │
    ┌──────────────────────┴──────────────────────┐
    │              Unit Tests                      │  ← Each component isolated
    │              (100+ tests)                    │
    └──────────────────────────────────────────────┘
```

### Test Fixtures

```
tests/
├── fixtures/
│   ├── complexity/
│   │   ├── nested_if_before.py
│   │   ├── nested_if_after.py
│   │   ├── long_method_before.py
│   │   ├── long_method_after.py
│   │   └── ...
│   └── edge_cases/
│       ├── already_simple.py
│       ├── syntax_error.py
│       └── dynamic_code.py
└── unit/
    └── ast_transform/
        ├── test_pattern_matcher.py
        ├── test_libcst_surgeon.py
        ├── test_redbaron_surgeon.py
        ├── test_transform_validator.py
        └── test_ast_transform_engine.py
```

## Additional Tasks

### 1. Investigate Complexipy Timeout

**Issue:** Complexipy timing out at 600 seconds with CPU < 0.1%, indicating hang (not slowness).

**Investigation needed:**
- Verify `--exclude` patterns are being passed correctly
- Check if complexipy has internal caching issues
- Test with smaller file sets to isolate problematic files
- Consider adding `--quiet` flag to reduce output overhead
- Check for infinite loops in specific code patterns

**Files to investigate:**
- `crackerjack/adapters/complexity/complexipy.py`
- Complexipy library issues/bugs

### 2. Fix JSON Logging After Progress Bar

**Issue:** JSON log messages appear immediately after progress bar without newline, causing visual corruption:

```
  Running comprehensive hooks: ━━━━━━━━━━━━━━━━╺━━━  9/11 0:00:35{"timestamp": ...
```

**Solution:** Add `console.print()` or newline before structured logging output.

**Files to modify:**
- `crackerjack/executors/individual_hook_executor.py` - Add newline before error logging
- `crackerjack/services/security_logger.py` - Consider using `console.print()` for Rich compatibility

**Example fix:**
```python
# Before logging JSON, ensure we're on a new line
self.console.print("")  # or use console.line()
logger.error(f"Subprocess failed: {error_details}")
```

## Implementation Phases

### Phase 1: Foundation
- Create `ast_transform/` directory structure
- Implement `BasePattern` and `BaseSurgeon` interfaces
- Add `libcst` and `redbaron` dependencies

### Phase 2: Core Patterns
- Implement `EarlyReturnPattern`
- Implement `GuardClausePattern`
- Implement `LibcstSurgeon` with these patterns

### Phase 3: Validation & Fallback
- Implement `TransformValidator`
- Implement `RedbaronSurgeon` fallback
- Wire up fallback logic in `ASTTransformEngine`

### Phase 4: Integration
- Update `PlanningAgent._refactor_for_clarity()` to use `ASTTransformEngine`
- Add logging and metrics
- Write comprehensive tests

### Phase 5: Advanced Patterns
- Implement `ExtractMethodPattern`
- Implement `DecomposeConditionalPattern`
- Performance optimization

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Plans with 0 changes | ~34 per run | < 5 per run |
| Complexity issues auto-fixed | 0% | 60-70% |
| Valid transformations | N/A | 100% (validated) |
| Formatting preserved | N/A | 95%+ |
