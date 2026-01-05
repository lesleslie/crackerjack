# Test Executor Working Directory Fix

## Problem

When Crackerjack was used to run tests for other projects (e.g., session-buddy), it would incorrectly use **Crackerjack's own package directory** as the working directory for pytest execution. This caused pytest to read Crackerjack's `pyproject.toml` configuration instead of the target project's configuration, leading to errors like:

```
ERROR: Unknown config option: benchmark
```

This occurred when the target project (session-buddy) had `pytest-benchmark` configured in their `pyproject.toml`, but Crackerjack did not.

## Root Cause

The `TestExecutor` class was initialized with `pkg_path` which always pointed to Crackerjack's package directory. This path was used directly as the `cwd` parameter in all `subprocess.run()` and `subprocess.Popen()` calls:

```python
# Before fix (in test_executor.py)
process = subprocess.Popen(
    cmd,
    cwd=self.pkg_path,  # ❌ Always Crackerjack's directory
    ...
)
```

## Solution

Added a new method `_detect_target_project_dir()` that intelligently detects the target project directory from the test command itself:

```python
def _detect_target_project_dir(self, cmd: list[str]) -> Path:
    """Detect the target project directory from the test command.

    Parses the pytest command to find test paths (directories or .py files)
    and returns the parent directory of the first test path found.
    """
    # Look for test paths in the command
    test_start_idx = -1
    for i, arg in enumerate(cmd):
        if arg == "pytest":
            test_start_idx = i + 1
            break

    if test_start_idx > 0:
        for arg in cmd[test_start_idx:]:
            if arg.startswith("-"):
                continue  # Skip options

            test_path = Path(arg)
            if test_path.exists():
                if test_path.is_dir():
                    return test_path.parent  # e.g., 'tests/' -> '.'
                elif test_path.is_file():
                    return test_path.parent.parent  # 'tests/test_foo.py' -> '.'

    return self.pkg_path  # Fallback
```

Updated all three subprocess calls to use the detected directory:

```python
# After fix (in test_executor.py)
process = subprocess.Popen(
    cmd,
    cwd=self._detect_target_project_dir(cmd),  # ✅ Target project directory
    ...
)
```

## Files Modified

- `crackerjack/managers/test_executor.py:20-64` - Added `_detect_target_project_dir()` method
- `crackerjack/managers/test_executor.py:142` - Updated `_pre_collect_tests()`
- `crackerjack/managers/test_executor.py:172` - Updated `_execute_with_live_progress()`
- `crackerjack/managers/test_executor.py:448` - Updated `_execute_test_process_with_progress()`

## Testing

Verified the fix with session-buddy:

```bash
# Before fix
$ cd session-buddy
$ python -m crackerjack run --run-tests
ERROR: Unknown config option: benchmark

# After fix
$ cd session-buddy
$ python -m crackerjack run --run-tests
✅ Test environment validated
🧪 Running tests (workers: auto, timeout: 1800s)
# Tests run successfully without config errors
```

## Impact

- **Fixed**: Pytest now reads the correct `pyproject.toml` from the target project
- **Fixed**: Projects can use their own pytest plugins (like pytest-benchmark) without errors
- **No Breaking Changes**: Falls back to `pkg_path` if no test paths are detected
- **Backward Compatible**: Existing behavior preserved for normal use cases

## Example

When Crackerjack is invoked from `/Users/les/Projects/crackerjack` to run tests for `/Users/les/Projects/session-buddy`:

```python
# Test command built by session-buddy's TestCommandBuilder
cmd = ['uv', 'run', 'python', '-m', 'pytest', '/Users/les/Projects/session-buddy/tests/']

# Old behavior: Run from crackerjack's directory
cwd = '/Users/les/Projects/crackerjack'  # ❌ Wrong config

# New behavior: Run from session-buddy's directory
cwd = '/Users/les/Projects/session-buddy'  # ✅ Correct config
```
