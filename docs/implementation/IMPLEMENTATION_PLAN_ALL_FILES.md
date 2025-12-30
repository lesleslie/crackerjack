# Implementation Plan: --all-files Flag + File Passing Fixes

## Problem Summary

Three critical issues identified:

1. **ACB mode placeholder**: Uses hardcoded `passed` results with 0.0s duration and empty file lists
1. **Legacy mode uses --all-files**: Forces hooks to check entire codebase, not just changed files
1. **Executor doesn't pass files**: Calls `get_command()` instead of `build_command(files)` with changed files

**Current Behavior**:

- Hooks always report `files=0` and `0.00s` because they're not actually running
- `GitService.get_changed_files()` correctly detects changes, but files aren't passed to tools
- Tools use `git ls-files` (all 512 tracked Python files) instead of changed files

## Solution: Three-Part Fix

### Part 1: Add `--all-files` CLI Flag

**Files to Modify**:

- `crackerjack/cli/options.py`: Add `all_files: bool = False` field
- `crackerjack/__main__.py`: Add `--all-files / --no-all-files` Typer option
- `crackerjack/cli/handlers.py`: Pass `all_files` flag to executors

**Purpose**: Allow users to explicitly run hooks on entire codebase (e.g., CI/CD, after dependency updates)

**Default**: `False` (only check changed files for performance)

### Part 2: Fix File Passing in Legacy Mode

**Current Problem**:

```python
# executors/hook_executor.py:167-168
return subprocess.run(
    hook.get_command(),  # ❌ Missing file list!
    ...,
)
```

**Solution**:

```python
# Get changed files from GitService
files_to_check = git_service.get_changed_files() if not all_files else []

# Use build_command() which supports file passing
return subprocess.run(
    hook.build_command(files_to_check),  # ✅ Files passed correctly
    ...,
)
```

**Files to Modify**:

- `crackerjack/executors/hook_executor.py`:
  - Add `all_files` parameter to `__init__`
  - Inject `GitService` via DI
  - Update `_run_hook_subprocess()` to use `build_command(files)`

### Part 3: Remove `--all-files` from Legacy Pre-commit Path

**Current Problem**:

```python
# config/hooks.py:78
cmd.extend([self.name, "--all-files"])  # ❌ Forces all files!
```

**Solution**:

```python
# Only add --all-files if explicitly requested
if all_files:
    cmd.extend([self.name, "--all-files"])
else:
    cmd.append(self.name)  # ✅ pre-commit will use changed files
```

**Files to Modify**:

- `crackerjack/config/hooks.py`:
  - Add `all_files` parameter to `get_command()` and `build_command()`
  - Conditionally add `--all-files` flag

### Part 4: Fix ACB Mode Placeholder (Future Work)

**Current Problem**:

```python
# orchestration/hook_orchestrator.py:669-676
result = HookResult(
    name=hook.name,
    status="passed",  # ❌ Always passes!
    duration=0.0,  # ❌ Fake duration!
)
```

**Solution**: Implement actual adapter execution (Phase 8+ work)

- This requires completing the direct adapter integration
- Not blocking for --all-files flag feature
- Users can use legacy mode (`orchestration_mode: "legacy"`) in the meantime

## Implementation Order

1. **Add CLI option** (`options.py`, `__main__.py`)
1. **Fix legacy mode file passing** (`hook_executor.py`, `hooks.py`)
1. **Add progress bar investigation** (check why `show_progress` is disabled)
1. **Test with real file changes**
1. **Document new flag** (update `CLAUDE.md`)

## Testing Strategy

```bash
# Test 1: Default behavior (changed files only)
echo "# test" >> crackerjack/__init__.py
python -m crackerjack run
# Expected: Hooks run on 1 file (crackerjack/__init__.py)

# Test 2: All files mode
python -m crackerjack run --all-files
# Expected: Hooks run on all 512 Python files

# Test 3: Clean repo (no changes)
git restore crackerjack/__init__.py
python -m crackerjack run
# Expected: Hooks run on 0 files (nothing to check)

# Test 4: All files on clean repo
python -m crackerjack run --all-files
# Expected: Hooks run on all 512 Python files
```

## Success Criteria

- [ ] `--all-files` flag available in CLI help
- [ ] Default mode checks only changed files
- [ ] `--all-files` mode checks entire codebase
- [ ] Hooks report correct file counts (`files=N` where N > 0)
- [ ] Progress bars show when there's actual work
- [ ] Hook durations reflect actual execution time (not 0.00s)

## Files to Modify

1. `crackerjack/cli/options.py` - Add `all_files` field
1. `crackerjack/__main__.py` - Add CLI option
1. `crackerjack/cli/handlers.py` - Pass flag to executors
1. `crackerjack/executors/hook_executor.py` - Add file passing logic
1. `crackerjack/managers/hook_manager.py` - Pass flag through
1. `crackerjack/config/hooks.py` - Conditional --all-files
1. `CLAUDE.md` - Document new flag

## Architectural Notes

**DI Integration**:

```python
@depends.inject
def __init__(
    self,
    console: Inject[Console],
    git_service: Inject[GitInterface],  # ✅ Inject GitService
    pkg_path: Path,
    all_files: bool = False,  # ✅ New parameter
) -> None: ...
```

**Backward Compatibility**:

- Default `all_files=False` maintains current incremental behavior
- Existing tests should pass without changes
- No breaking changes to public APIs
