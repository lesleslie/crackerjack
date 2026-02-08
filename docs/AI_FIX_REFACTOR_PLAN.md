# AI Fix Refactoring Plan

## Objective
Reduce complexity of `_apply_ai_agent_fixes` method from 21 to ≤15 by extracting helper methods.

## Current Method Structure
The method at `crackerjack/core/autofix_coordinator.py:1543` has these responsibilities:

1. **Setup** (lines 1546-1566): Initialize coordinator, context, cache
2. **Issue Collection** (lines 1568-1576): Parse hook results and check coverage
3. **Progress Session Start** (lines 1578-1581): Initialize progress tracking
4. **Main Iteration Loop** (lines 1586-1648): Core fixing logic with convergence checks
5. **Exception Handling** (lines 1649-1655): Error handling and cleanup
6. **Post-Fix Validation** (lines 1657-1712): Detailed issue validation

## Refactoring Strategy

### Helper Method 1: `_setup_ai_fix_coordinator`
**Extract**: Lines 1546-1566
**Purpose**: Initialize coordinator, context, and cache
**Complexity**: Low (≤5)

```python
def _setup_ai_fix_coordinator(self) -> AgentCoordinator:
    """Set up AI fix coordinator with context and cache."""
    # Create context and cache
    # Get or create coordinator
    # Return coordinator instance
```

### Helper Method 2: `_collect_fixable_issues`
**Extract**: Lines 1568-1576
**Purpose**: Parse hook results and add coverage issues
**Complexity**: Low (≤5)

```python
def _collect_fixable_issues(self, hook_results: Sequence[object]) -> list[Issue]:
    """Collect all fixable issues from hook results including coverage."""
    # Parse hook results to issues
    # Check coverage regression
    # Return combined issue list
```

### Helper Method 3: `_run_ai_fix_iteration_loop`
**Extract**: Lines 1586-1648
**Purpose**: Main iteration loop with convergence detection
**Complexity**: Medium (need to break down further)

This is the main complexity source. Need to extract sub-helpers:

#### Helper 3a: `_get_iteration_issues`
**Extract**: Lines 1589-1598
**Purpose**: Get issues for current iteration (initial or re-collected)

```python
def _get_iteration_issues(
    self, iteration: int, hook_results: Sequence[object], stage: str
) -> list[Issue]:
    """Get issues for the current iteration."""
    # Iteration 0: use initial hook results
    # Iteration >0: re-run hooks and collect current issues
```

#### Helper 3b: `_check_iteration_completion`
**Extract**: Lines 1604-1626
**Purpose**: Check if iteration should complete (success, max iterations, convergence)

```python
def _check_iteration_completion(
    self, iteration: int, current_issue_count: int, stage: str
) -> bool | None:
    """Check if iteration should complete and return result if done."""
    # Check zero issues case
    # Check max iterations
    # Check convergence
    # Return True/False if done, None if continue
```

#### Helper 3c: `_update_iteration_progress`
**Extract**: Lines 1628-1638
**Purpose**: Update progress tracking for iteration

```python
def _update_iteration_progress(
    self,
    iteration: int,
    current_issue_count: int,
    previous_issue_count: int,
    no_progress_count: int,
) -> int:
    """Update progress tracking and return new no_progress_count."""
    # Update progress count
    # Update progress manager
    # Return new count
```

### Helper Method 4: `_validate_final_issues`
**Extract**: Lines 1657-1712
**Purpose**: Post-fix validation of issue objects
**Complexity**: Medium (≤10)

```python
def _validate_final_issues(self, issues: list[Issue]) -> None:
    """Validate that final issue objects are well-formed."""
    # Check each issue for required fields
    # Validate aggregate issue handling
    # Raise ValueError if invalid
```

## Refactored Main Method

```python
def _apply_ai_agent_fixes(
    self, hook_results: Sequence[object], stage: str = "fast"
) -> bool:
    """Apply AI agent fixes with proper complexity management."""
    # Setup (Helper 1)
    coordinator = self._setup_ai_fix_coordinator()

    # Collect issues (Helper 2)
    issues = self._collect_fixable_issues(hook_results)

    # Start progress session
    self.progress_manager.start_fix_session(
        stage=stage,
        initial_issue_count=len(issues),
    )

    # Main iteration loop (refactored with sub-helpers)
    result = self._run_ai_fix_iteration_loop(
        coordinator, issues, hook_results, stage
    )

    # Post-fix validation (Helper 4)
    if result:
        self._validate_final_issues(issues)

    return result
```

## Expected Complexity After Refactoring

- `_apply_ai_agent_fixes`: ~8 (main orchestration)
- `_setup_ai_fix_coordinator`: ~5 (simple setup)
- `_collect_fixable_issues`: ~4 (issue collection)
- `_run_ai_fix_iteration_loop`: ~12 (main loop, still complex)
- `_get_iteration_issues`: ~3 (conditional logic)
- `_check_iteration_completion`: ~8 (completion checks)
- `_update_iteration_progress`: ~5 (progress updates)
- `_validate_final_issues`: ~10 (validation logic)

All methods ≤15! ✓

## Verification Steps

1. Run complexity check: `python -m ruff check crackerjack/core/autofix_coordinator.py --select=C901`
2. Run syntax check: `python -m compileall crackerjack/core/autofix_coordinator.py -q`
3. Run quality gates: `python -m crackerjack run --comprehensive`
4. Run tests: `python -m crackerjack run --run-tests`

## Implementation Order

1. Add helper methods at end of class (before existing private methods)
2. Update `_apply_ai_agent_fixes` to use helpers
3. Verify all checks pass
4. Update docstrings if needed

## Notes

- All helpers preserve original functionality
- Type annotations maintained
- No behavior changes
- Protocol-based DI pattern followed (import from `models/protocols.py`)
