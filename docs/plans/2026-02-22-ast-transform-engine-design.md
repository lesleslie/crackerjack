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
1. **Complexity reduction:** New complexity < original complexity (with timeout protection)
1. **Behavior preservation:**
   - Same function signatures (name, parameters, return type annotations)
   - No deleted statements (unless semantically equivalent replacement)
   - Return value type consistency (can't change `return []` to `return None`)
   - Exception raising patterns preserved
   - Variable scope analysis (closures preserved)
   - Type annotation syntax consistency (`X | Y` not converted to `Union[X, Y]`)
1. **Formatting preservation:**
   - Comments preserved (inline, block, docstrings)
   - F-strings not converted to `.format()`
   - Whitespace and indentation consistent

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
| BothSurgeonsFailed | Both libcst and redbaron produce invalid output | Mark for manual review, log both attempts |
| ComplexityIncreased | Transform made complexity WORSE | Reject immediately, try simpler pattern |
| FormattingLost | Comments/whitespace destroyed | Use redbaron fallback, or reject if already tried |
| ComplexityTimeout | Complexity calculation exceeds 30s | Reject transform, file too complex |
| WalrusOperatorConflict | Guard clause conflicts with `:=` operator | Skip this pattern, try next pattern |
| AsyncPatternUnsupported | Pattern doesn't support async/await | Skip pattern for async functions |

**Important:** Each surgeon receives the ORIGINAL code, not the output from a previous surgeon attempt. This ensures fallback is independent.

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
    "redbaron>=0.9.2",  # ⚠️ WARNING: Last release 2022, verify Python 3.13 compatibility before Phase 3
]
```

**⚠️ Critical Pre-Implementation Check:**

- Redbaron has not had a release since 2022
- Must verify Python 3.13 compatibility before Phase 3
- Alternative fallback options if redbaron fails:
  - Use `black` for formatting restoration post-libcst
  - Custom formatting heuristic based on original indentation

## Testing Strategy

### Test Pyramid

```
                    ┌─────────────────────┐
                    │   E2E Integration   │  ← Full pipeline tests (15-20)
                    └──────────┬──────────┘
                               │
          ┌────────────────────┴────────────────────┐
          │          Integration Tests              │  ← Pattern + Surgeon + Validator (35-50)
          └────────────────────┬────────────────────┘
                               │
    ┌──────────────────────────┴──────────────────────────┐
    │                  Component Tests                      │  ← PatternMatcher in isolation (15-20)
    └──────────────────────────┬──────────────────────────┘
                               │
    ┌──────────────────────────┴──────────────────────────┐
    │                    Unit Tests                        │  ← Each component isolated (120-150)
    └──────────────────────────────────────────────────────┘
```

### Test Fixtures

```
tests/
├── fixtures/
│   └── ast_transform/
│       ├── patterns/
│       │   ├── early_return/
│       │   │   ├── nested_if_before.py
│       │   │   ├── nested_if_after.py
│       │   │   ├── deeply_nested_else.py
│       │   │   └── return_with_side_effects.py
│       │   ├── guard_clause/
│       │   │   ├── validation_chain_before.py
│       │   │   ├── validation_chain_after.py
│       │   │   ├── async_validation.py
│       │   │   └── guard_with_cleanup.py
│       │   ├── extract_method/
│       │   │   ├── long_method_before.py
│       │   │   ├── long_method_after.py
│       │   │   ├── method_with_closure.py
│       │   │   └── method_with_yield.py
│       │   └── decompose_conditional/
│       │       ├── complex_boolean_before.py
│       │       ├── complex_boolean_after.py
│       │       └── short_circuit_eval.py
│       ├── surgeon_challenges/
│       │   ├── comment_preservation.py
│       │   ├── multiline_strings.py
│       │   ├── type_annotations.py
│       │   ├── async_code.py
│       │   ├── decorators_complex.py
│       │   ├── context_managers.py
│       │   ├── match_statements.py      # Python 3.10+
│       │   └── formatting_sensitive.py
│       ├── validation/
│       │   ├── behavior_change_scenarios/
│       │   │   ├── signature_modified.py
│       │   │   ├── return_type_changed.py
│       │   │   └── variable_scope_changed.py
│       │   └── complexity_increase/
│       │       └── refactor_increases_complexity.py
│       └── edge_cases/
│           ├── already_simple.py
│           ├── syntax_error.py
│           ├── dynamic_code.py
│           ├── empty_file.py
│           ├── only_comments.py
│           ├── massive_nesting.py        # 50+ levels deep
│           ├── walrus_operator.py        # := patterns
│           ├── py310_match_statement.py  # Python 3.10+ pattern matching
│           └── ipython_magic.py          # Should fail gracefully
├── unit/
│   └── ast_transform/
│       ├── test_pattern_matcher.py
│       ├── test_patterns/
│       │   ├── test_early_return_pattern.py     # 25+ tests
│       │   ├── test_guard_clause_pattern.py     # 25+ tests
│       │   ├── test_extract_method_pattern.py   # 30+ tests
│       │   └── test_decompose_conditional_pattern.py  # 25+ tests
│       ├── test_surgeons/
│       │   ├── test_libcst_surgeon.py           # 40+ tests
│       │   ├── test_redbaron_surgeon.py         # 30+ tests
│       │   └── test_surgeon_equivalence.py      # 15+ tests
│       ├── test_transform_validator.py          # 30+ tests (3 gates)
│       └── test_ast_transform_engine.py
├── integration/
│   └── ast_transform/
│       ├── test_pattern_surgeon_integration.py  # 15+ tests
│       └── test_engine_integration.py           # 10+ tests
└── e2e/
    └── ast_transform/
        └── test_full_pipeline.py                # 15-20 tests
```

### Test Anti-Patterns to Avoid

1. **Testing implementation details** - Test behavior, not internal method calls
1. **Over-mocking AST nodes** - Use real AST parsing, not Mock objects
1. **Ignoring formatting** - Always verify comments/whitespace preserved
1. **Happy path only** - Every test class needs success, failure, and edge cases
1. **Non-deterministic ordering** - Use explicit priority lists, not sets/dicts for ordering

### Test Implementation Order

1. **Week 1:** TransformValidator (all 4 gates), LibcstSurgeon basics, EarlyReturnPattern
1. **Week 2:** GuardClausePattern, RedbaronSurgeon basics, SurgeonFallback
1. **Week 3:** ExtractMethodPattern, DecomposeConditionalPattern, edge case fixtures
1. **Week 4:** Integration tests, E2E tests, PlanningAgent integration

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

### Phase 1.5: Dependency Verification ⚠️ CRITICAL

- **Verify redbaron Python 3.13 compatibility:**
  ```bash
  uv pip install redbaron
  python -c "from redbaron import RedBaron; RedBaron('def foo(): pass')"
  ```
- If redbaron fails, implement alternative fallback:
  - Use `black` for formatting restoration post-libcst
  - Or implement custom formatting heuristic

### Phase 2: Core Patterns

- Implement `EarlyReturnPattern` with priority ordering
- Implement `GuardClausePattern` with walrus operator detection
- Implement `LibcstSurgeon` with these patterns
- Add pattern priority enum:
  ```python
  class PatternPriority(IntEnum):
      EARLY_RETURN = 1      # Try first - smallest change
      GUARD_CLAUSE = 2
      DECOMPOSE_CONDITIONAL = 3
      EXTRACT_METHOD = 4    # Try last - largest change
  ```

### Phase 3: Validation & Fallback

- Implement `TransformValidator` with all 4 gates
- Implement `RedbaronSurgeon` fallback (if Phase 1.5 passed)
- Wire up fallback logic in `ASTTransformEngine`
- Add complexity calculation timeout (30s per file)

### Phase 3.5: Concurrency Safety

- Add file-level locking for pytest-xdist parallelization:
  ```python
  class ASTTransformEngine:
      _file_locks: dict[str, asyncio.Lock] = {}

      async def transform(self, issue: Issue, context: dict) -> ChangeSpec | None:
          file_path = str(issue.file_path)
          if file_path not in self._file_locks:
              self._file_locks[file_path] = asyncio.Lock()

          async with self._file_locks[file_path]:
              # ... transformation logic
  ```
- Add backup/rollback mechanism:
  ```python
  # Before transformation
  original_content = file.read_text()

  # On validation failure or error
  file.write_text(original_content)  # Rollback
  ```

### Phase 4: Integration

- Update `PlanningAgent._refactor_for_clarity()` to use `ASTTransformEngine`
- Add logging and metrics with `TransformMetrics` dataclass
- Handle line offset tracking for multiple changes per file
- Write comprehensive tests

### Phase 5: Advanced Patterns

- Implement `ExtractMethodPattern` with import dependency tracking
- Implement `DecomposeConditionalPattern` with short-circuit preservation
- Performance optimization (cache parsed ASTs, batch complexity calculations)

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Plans with 0 changes | ~34 per run | < 5 per run |
| Complexity issues auto-fixed | 0% | 60-70% |
| Valid transformations | N/A | 100% (validated) |
| Formatting preserved | N/A | 95%+ |

______________________________________________________________________

## Power Trio Review Summary

**Review Date:** 2026-02-22
**Reviewers:** Code Reviewer, QA Expert

### Risk Assessment: MEDIUM

### Critical Issues Addressed

1. **Redbaron Python 3.13 Compatibility**

   - Added Phase 1.5 verification step
   - Alternative fallback strategy documented

1. **Validation Insufficient**

   - Expanded from 3 to 4 validation gates
   - Added return value consistency, exception patterns, type annotation preservation

1. **Concurrency Safety**

   - Added Phase 3.5 with file-level locking
   - Required for pytest-xdist parallelization

1. **Missing Error Types**

   - Added BothSurgeonsFailed, ComplexityIncreased, FormattingLost, ComplexityTimeout
   - Added WalrusOperatorConflict, AsyncPatternUnsupported

### Testing Enhancements

- Expanded E2E tests from 5-10 to 15-20
- Added component test layer (15-20 tests)
- Expanded integration tests from 20-30 to 35-50
- Added pattern-specific fixtures for all 4 patterns
- Added surgeon challenge fixtures (8 files)
- Added validation fixtures (behavior change scenarios)
- Expanded edge cases from 3 to 12+

### Key Design Clarifications

- Each surgeon receives ORIGINAL code, not previous surgeon output
- Pattern ordering enforced via `PatternPriority` enum
- Backup/rollback mechanism added to data flow
- Complexity calculation has 30s timeout protection
