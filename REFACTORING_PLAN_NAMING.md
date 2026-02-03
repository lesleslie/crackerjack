# Refactoring Plan: Improve Naming Conventions

## Task 4.3: Improve Naming Conventions

### Objective
Eliminate generic `util.py` files and ensure consistent, descriptive naming throughout the codebase.

## Analysis Results

### Identified Generic util.py Files

Found 3 generic `util.py` files that need to be addressed:

1. **`/crackerjack/cli/utils.py`**
   - Purpose: Package version retrieval
   - Current status: DUPLICATE - properly named `version.py` already exists
   - Action: Remove obsolete `utils.py`

2. **`/crackerjack/decorators/utils.py`**
   - Purpose: Helper functions for decorators (async detection, signature preservation, function context)
   - Current status: DUPLICATE - properly named `helpers.py` already exists with improved implementation
   - Action: Remove obsolete `utils.py`

3. **`/crackerjack/services/patterns/utils.py`**
   - Purpose: Pattern operations and transformations
   - Current status: DUPLICATE - properly named `operations.py` already exists with improvements
   - Action: Remove obsolete `utils.py`

### Verification Status

✅ All properly named files already exist
✅ All imports reference the correctly named files (version.py, helpers.py, operations.py)
✅ No remaining imports from old utils.py files
✅ `__init__.py` files export from correct modules

## Implementation Plan

### Step 1: Remove Obsolete Files
Delete the 3 duplicate `utils.py` files:
- `crackerjack/cli/utils.py`
- `crackerjack/decorators/utils.py`
- `crackerjack/services/patterns/utils.py`

### Step 2: Verification
Run quality checks to ensure no broken imports:
```bash
python -m crackerjack run --run-tests -c
```

### Step 3: Documentation
Update any documentation that references the old file names.

## Benefits

1. **Improved Code Clarity**: Descriptive names immediately convey file purpose
2. **Reduced Confusion**: No duplicate files with generic names
3. **Better Maintainability**: Clear separation of concerns
4. **Consistent Naming**: Follows Python best practices (avoid "util" suffix)

## Risk Assessment

**Risk Level**: LOW

- All imports already reference correct files
- Properly named versions exist with identical or improved functionality
- No breaking changes required
- Simple file deletion operation

## Success Criteria

- [ ] No `util.py` or `utils.py` files remain in crackerjack directory
- [ ] All tests pass
- [ ] No import errors
- [ ] Quality gates pass

## Files to Modify

### Files to Delete
1. `/Users/les/Projects/crackerjack/crackerjack/cli/utils.py`
2. `/Users/les/Projects/crackerjack/crackerjack/decorators/utils.py`
3. `/Users/les/Projects/crackerjack/crackerjack/services/patterns/utils.py`

### Files That Reference Correct Names (No Changes Needed)
- `/Users/les/Projects/crackerjack/crackerjack/cli/__init__.py` ✅
- `/Users/les/Projects/crackerjack/crackerjack/decorators/__init__.py` ✅
- `/Users/les/Projects/crackerjack/crackerjack/services/patterns/__init__.py` ✅

## Additional Naming Improvements

### Other Files Reviewed
- `_rich_utils.py` in `cli/` - Acceptable (private module with descriptive name)
- No other generic naming issues found

## Conclusion

This refactoring is straightforward because the work has already been done - the properly named files exist and are in use. We simply need to remove the obsolete duplicate files to complete the naming convention improvement.
