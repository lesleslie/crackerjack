# Complexipy Adapter Fix - Complete Analysis

**Date**: 2025-11-10
**Issue**: Complexipy showing only 1 issue when 24 functions exceed complexity threshold

______________________________________________________________________

## Root Cause Analysis

The complexipy adapter had **two critical bugs**:

### 1. Command-Line Flags Mismatch

The adapter was using outdated/incorrect flag names that don't match the actual tool API:

| Adapter Used | Actual Tool Flag | Result |
|--------------|------------------|---------|
| `--json` | `--output-json` | Exit code 2 (option error) |
| `--max-complexity` | `--max-complexity-allowed` | Exit code 2 (option error) |
| `--cognitive` | ❌ Doesn't exist | Exit code 2 (option error) |
| `--maintainability` | ❌ Doesn't exist | Exit code 2 (option error) |
| `--sort complexity` | `--sort [asc\|desc\|name]` | Exit code 2 (invalid value) |

**Impact**: Tool failed with exit code 2, preventing any issues from being detected.

### 2. JSON Parsing Structure Mismatch

The adapter expected **nested structure**:

```python
{
    "files": [
        {"path": "...", "functions": [{"name": "...", "line": 123, "complexity": 16}]}
    ]
}
```

But complexipy outputs **flat list**:

```python
[
    {
        "complexity": 16,
        "file_name": "claude.py",
        "function_name": "ClaudeCodeFixer::_ensure_client",
        "path": "crackerjack/adapters/ai/claude.py",
    },
    ...,
]
```

**Impact**: Parser expected `data.get("files", [])` which returned empty list, resulting in 0 issues parsed.

______________________________________________________________________

## Fix Implementation

### 1. Command Flag Corrections

**File**: `crackerjack/adapters/complexity/complexipy.py`

#### Lines 51-56 (ComplexipySettings):

```python
# Before:
sort_by: str = "complexity"  # ❌ Invalid value

# After:
sort_by: str = "desc"  # ✅ Valid option (sorts by complexity descending)
```

#### Lines 149-167 (build_command):

```python
# Before:
if self.settings.use_json_output:
    cmd.append("--json")  # ❌ Wrong flag
cmd.extend(["--max-complexity", str(self.settings.max_complexity)])  # ❌ Wrong flag
if self.settings.include_cognitive:
    cmd.append("--cognitive")  # ❌ Doesn't exist
if self.settings.include_maintainability:
    cmd.append("--maintainability")  # ❌ Doesn't exist

# After:
if self.settings.use_json_output:
    cmd.append("--output-json")  # ✅ Correct flag
cmd.extend(
    ["--max-complexity-allowed", str(self.settings.max_complexity)]
)  # ✅ Correct flag
# NOTE: --cognitive and --maintainability flags don't exist in complexipy
# Complexity tool only reports cyclomatic complexity, not cognitive/maintainability
# These settings are kept in ComplexipySettings for backwards compatibility but ignored
```

### 2. JSON Parsing Logic Update

**File**: `crackerjack/adapters/complexity/complexipy.py:220-257`

```python
def _process_complexipy_data(self, data: list | dict) -> list[ToolIssue]:
    """Process the complexipy JSON data to extract issues.

    Args:
        data: Parsed JSON data from complexipy (flat list or legacy nested dict)

    Returns:
        List of ToolIssue objects
    """
    issues = []

    # Handle flat list structure (current complexipy format)
    if isinstance(data, list):
        for func in data:
            complexity = func.get("complexity", 0)
            if complexity <= self.settings.max_complexity:
                continue

            file_path = Path(func.get("path", ""))
            function_name = func.get("function_name", "unknown")
            severity = (
                "error" if complexity > self.settings.max_complexity * 2 else "warning"
            )

            issue = ToolIssue(
                file_path=file_path,
                line_number=None,  # complexipy JSON doesn't include line numbers
                message=f"Function '{function_name}' - Complexity: {complexity}",
                code="COMPLEXITY",
                severity=severity,
                suggestion=f"Consider refactoring to reduce complexity below {self.settings.max_complexity}",
            )
            issues.append(issue)
        return issues

    # Handle legacy nested structure (backwards compatibility)
    for file_data in data.get("files", []):
        file_path = Path(file_data.get("path", ""))
        issues.extend(
            self._process_file_data(file_path, file_data.get("functions", []))
        )
    return issues
```

**Key Changes**:

1. Type annotation changed from `dict` to `list | dict` for flexibility
1. Added `isinstance(data, list)` check to handle flat list structure
1. Direct iteration over flat list entries
1. Proper threshold filtering (`complexity > max_complexity`)
1. Severity determination based on 2x threshold
1. Maintained backwards compatibility with legacy nested structure

______________________________________________________________________

## Verification Results

### Direct Tool Execution:

```bash
$ uv run complexipy --output-json --max-complexity-allowed 15 --sort desc crackerjack
```

**Result**: 24 functions found with complexity > 15 (highest: 32, lowest: 16)

### Adapter Parsing Test:

```python
# Load complexipy.json (6,826 total functions)
issues = adapter._process_complexipy_data(data)
print(f"Issues parsed: {len(issues)}")
# Output: Issues parsed: 24
```

**Result**: ✅ All 24 issues correctly parsed

### Sample Issues Detected:

1. `workflow_orchestrator.py` - `WorkflowOrchestrator::_orchestrate_phases` - Complexity: 32
1. `utility_tools.py` - `clean_temp_files` - Complexity: 30
1. `phase_coordinator.py` - `PhaseCoordinator::_execute_phase` - Complexity: 29
1. `skylos.py` - `SkylosAdapter::get_command_args` - Complexity: 29
1. `end_of_file_fixer.py` - `main` - Complexity: 24

______________________________________________________________________

## Impact Assessment

### Before Fix:

- ❌ Exit code 2 (command-line errors)
- ❌ 0 issues parsed from JSON
- ❌ `issues=1` displayed (false positive from some other source)
- ❌ No visibility into codebase complexity problems

### After Fix:

- ✅ Exit code 0 (successful execution)
- ✅ 24 issues correctly parsed
- ✅ `issues=24` displayed in comprehensive hooks output
- ✅ Complete visibility into all complexity violations

______________________________________________________________________

## Configuration Details

**Hook Configuration** (`crackerjack/config/hooks.py:319-328`):

```python
(
    HookDefinition(
        name="complexipy",
        command=[],
        timeout=120,
        stage=HookStage.COMPREHENSIVE,
        manual_stage=True,
        security_level=SecurityLevel.MEDIUM,
        use_precommit_legacy=False,  # Direct invocation
        accepts_file_paths=True,  # Incremental execution support
    ),
)
```

**Adapter Settings** (`ComplexipySettings`):

- `max_complexity`: 15 (crackerjack standard)
- `include_cognitive`: True (kept for backwards compat, not used)
- `include_maintainability`: True (kept for backwards compat, not used)
- `sort_by`: "desc" (sorts by complexity descending)
- `use_json_output`: True (structured parsing)

______________________________________________________________________

## Testing Recommendations

1. **Run comprehensive hooks**:

   ```bash
   python -m crackerjack run --comp
   ```

   Expected: complexipy shows `issues=24` (not `issues=1`)

1. **Verify incremental mode**:

   ```bash
   # Make changes to high-complexity file
   python -m crackerjack run --comp --changed-only
   ```

   Expected: Only modified files' issues reported

1. **Test threshold adjustment**:

   ```bash
   # In settings/local.yaml:
   # complexity:
   #   max_complexity: 20
   python -m crackerjack run --comp
   ```

   Expected: Fewer issues (only functions > 20 complexity)

______________________________________________________________________

## Future Enhancements

1. **Line Number Support**: If complexipy adds line numbers to JSON output, update `line_number=None` to use them
1. **Cognitive Complexity**: If tool adds cognitive complexity metrics, enable parsing
1. **Maintainability Index**: If tool adds maintainability scores, include in issue messages
1. **Incremental Optimization**: Consider caching previous results for faster incremental runs

______________________________________________________________________

## References

- Complexipy tool: https://github.com/rohaquinlop/complexipy
- Adapter source: `crackerjack/adapters/complexity/complexipy.py`
- Hook configuration: `crackerjack/config/hooks.py:319-328`
- Refurb/Creosote behavior docs: `docs/refurb_creosote_behavior.md` (similar patterns)
