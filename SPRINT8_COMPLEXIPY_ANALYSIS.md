# complexipy.py - Implementation Analysis

**File**: crackerjack/adapters/complexity/complexipy.py
**Lines**: 455
**Statements**: 220 (from coverage report)
**Status**: 0% coverage → Target 60-65%

---

## Implementation Structure

### Dataclasses (1)

#### ComplexipySettings (lines 32-38)
**Purpose**: Configuration settings for ComplexipyAdapter
**Base Class**: ToolAdapterSettings
**Fields**:
- `tool_name: str = "complexipy"`
- `use_json_output: bool = True`
- `max_complexity: int = 15`
- `include_cognitive: bool = True`
- `include_maintainability: bool = True`
- `sort_by: str = "desc"`

**Inherits from ToolAdapterSettings**:
- `timeout_seconds: int`
- `max_workers: int`
- Other base adapter settings

---

### Main Class: ComplexipyAdapter (lines 41-455)

**Base Class**: BaseToolAdapter
**Purpose**: QA adapter for complexity analysis using complexipy tool
**Module ID**: UUID("33a3f9ff-5fd2-43f5-a6c9-a43917618a17")
**Status**: STABLE

#### Public Methods (7)

##### 1. __init__(settings) (lines 44-49)
**Purpose**: Initialize adapter with optional settings
**Parameters**:
- `settings: ComplexipySettings | None = None`

**Logic**:
- Calls super().__init__()
- Logs initialization with settings status

##### 2. async init() (lines 51-73)
**Purpose**: Async initialization with config loading
**Logic**:
- If no settings, load config from pyproject.toml
- Create ComplexipySettings with max_complexity from config
- Call super().init()
- Log initialization complete with settings details

**Key behavior**: Loads max_complexity from [tool.complexipy] in pyproject.toml

##### 3. adapter_name (property) (lines 75-77)
**Returns**: "Complexipy (Complexity)"

##### 4. module_id (property) (lines 79-81)
**Returns**: MODULE_ID (UUID constant)

##### 5. tool_name (property) (lines 83-85)
**Returns**: "complexipy"

##### 6. build_command(files, config) (lines 87-118)
**Purpose**: Build complexipy command line
**Parameters**:
- `files: list[Path]` - Files to analyze
- `config: QACheckConfig | None = None`

**Returns**: `list[str]` - Command arguments

**Logic**:
- Raises RuntimeError if settings not initialized
- Builds command: `[complexipy, --output-json, --max-complexity-allowed, N, --sort, desc, file1, file2, ...]`
- Loads max_complexity from pyproject.toml or settings
- Extends command with file paths

**Raises**: RuntimeError if settings is None

##### 7. async parse_output(result) (lines 120-176)
**Purpose**: Parse complexipy tool execution result
**Parameters**:
- `result: ToolExecutionResult` - Tool execution result with raw_output

**Returns**: `list[ToolIssue]` - List of complexity issues

**Logic Flow**:
1. Try to move complexipy JSON results file to output dir
2. If settings.use_json_output and JSON file exists:
   - Load JSON from file
   - Fall back to stdout parsing on error
3. Else, parse raw_output as JSON
   - Fall back to text parsing on JSON decode error
4. Call `_process_complexipy_data()` to convert JSON to ToolIssue list
5. Log and return issues

**Fallback chain**: JSON file → JSON stdout → Text parsing

##### 8. get_default_config() (lines 337-363)
**Purpose**: Get default QA check configuration
**Returns**: `QACheckConfig`

**Logic**:
- Loads exclude_patterns and max_complexity from pyproject.toml
- Returns QACheckConfig with:
  - check_id: MODULE_ID
  - check_name: adapter_name
  - check_type: QACheckType.COMPLEXITY
  - enabled: True
  - file_patterns: ["**/*.py"]
  - exclude_patterns: from config or defaults
  - timeout_seconds: 90
  - parallel_safe: True
  - stage: "comprehensive"
  - settings: dict with max_complexity, include_cognitive, include_maintainability, sort_by

---

#### Private Methods (12)

##### 1. _process_complexipy_data(data) (lines 178-215)
**Purpose**: Process complexipy JSON data (list or dict format)
**Parameters**:
- `data: list | dict` - Parsed JSON data

**Returns**: `list[ToolIssue]`

**Logic**:
- If settings not initialized, return empty list
- If data is list: Process each function dict
  - Skip if complexity <= max_complexity
  - Create ToolIssue with severity "error" if complexity > 2x max, else "warning"
- If data is dict: Extract "files" list and process each
  - Calls `_process_file_data()` for each file

**Issue severity logic**:
- `complexity > max_complexity * 2` → "error"
- Otherwise → "warning"

##### 2. _process_file_data(file_path, functions) (lines 217-227)
**Purpose**: Process functions for a single file
**Parameters**:
- `file_path: Path`
- `functions: list[dict]`

**Returns**: `list[ToolIssue]`

**Logic**: Iterate functions, call `_create_issue_if_needed()` for each

##### 3. _create_issue_if_needed(file_path, func) (lines 229-248)
**Purpose**: Create ToolIssue if function complexity exceeds threshold
**Parameters**:
- `file_path: Path`
- `func: dict` - Function data dict

**Returns**: `ToolIssue | None`

**Logic**:
- If settings not initialized, return None
- If complexity <= max_complexity, return None
- Build message with `_build_issue_message()`
- Determine severity with `_determine_issue_severity()`
- Return ToolIssue with:
  - file_path
  - line_number (from func["line"])
  - message
  - code="COMPLEXITY"
  - severity
  - suggestion

##### 4. _build_issue_message(func, complexity) (lines 250-261)
**Purpose**: Build formatted issue message
**Parameters**:
- `func: dict` - Function data
- `complexity: int`

**Returns**: `str` - Formatted message

**Message format**:
```
"Function '{name}' - Complexity: N, Cognitive: N, Maintainability: N.N"
```

**Conditional includes**:
- Always includes "Complexity: N"
- If `include_cognitive`: adds "Cognitive: N"
- If `include_maintainability`: adds "Maintainability: N.N"

##### 5. _determine_issue_severity(complexity) (lines 263-269)
**Purpose**: Determine issue severity based on complexity
**Parameters**:
- `complexity: int`

**Returns**: `str` - "error" or "warning"

**Logic**:
- If `complexity > max_complexity * 2`: return "error"
- Otherwise: return "warning"
- If no settings: return "warning"

##### 6. _parse_text_output(output) (lines 271-290)
**Purpose**: Fallback text parsing (when JSON unavailable)
**Parameters**:
- `output: str` - Raw text output

**Returns**: `list[ToolIssue]`

**Logic**:
- Split output into lines
- Track current file from "File:" lines
- For lines containing "complexity": parse with `_parse_complexity_line()`
- Log and return issues

**Expected text format**:
```
File: /path/to/file.py
function_name(line 42) complexity 20
```

##### 7. _update_current_file(line, current_file) (lines 292-296)
**Purpose**: Update current file path from "File:" lines
**Parameters**:
- `line: str`
- `current_file: Path | None`

**Returns**: `Path | None`

**Logic**:
- If line starts with "File:", extract path and return new Path
- Otherwise, return current_file unchanged

##### 8. _parse_complexity_line(line, current_file) (lines 298-320)
**Purpose**: Parse a complexity line from text output
**Parameters**:
- `line: str`
- `current_file: Path`

**Returns**: `ToolIssue | None`

**Logic**:
- Extract function data with `_extract_function_data()`
- If extraction succeeds and complexity > max_complexity:
  - Determine severity (error if > 2x max)
  - Return ToolIssue
- Uses `suppress(ValueError, IndexError)` to handle parse failures

##### 9. _extract_function_data(line) (lines 322-332)
**Purpose**: Extract function name, line number, complexity from text line
**Parameters**:
- `line: str`

**Returns**: `tuple[str, int, int] | None` - (func_name, line_number, complexity) or None

**Parsing logic**:
- Example: `function_name(line 42) complexity 20`
- Split by "(", extract function name
- Extract line number from between "(" and ")"
- Find "complexity" keyword, extract number after it
- Returns tuple or None if parse fails

##### 10. _get_check_type() (lines 334-335)
**Returns**: `QACheckType.COMPLEXITY`

##### 11. _load_config_from_pyproject() (lines 365-402)
**Purpose**: Load complexipy configuration from pyproject.toml
**Returns**: `dict` with keys:
- `exclude_patterns: list[str]`
- `max_complexity: int`

**Logic**:
- Default config: exclude_patterns=["**/.venv/**", "**/venv/**", "**/tests/**"], max_complexity=15
- If pyproject.toml exists:
  - Load TOML
  - Extract [tool.complexipy] section
  - Override exclude_patterns and max_complexity if present
  - Log loaded values
- Catch and log TOML decode errors, return defaults

##### 12. _load_exclude_patterns_from_config() (lines 404-409)
**Purpose**: Load exclude patterns from config
**Returns**: `list[str]`

**Logic**: Calls `_load_config_from_pyproject()` and returns exclude_patterns key

##### 13. _move_complexipy_results_to_output_dir() (lines 411-455)
**Purpose**: Move complexipy JSON result files to centralized output location
**Returns**: `Path | None` - Path to moved file or None

**Logic**:
- Find all `complexipy_results_*.json` files in project root
- Sort by modification time (newest first)
- Move newest file to `AdapterOutputPaths.get_output_dir("complexipy")`
- Clean up old outputs (keep latest 5)
- Log success or failure
- Return moved file path or original file path on error

**Uses**:
- `shutil.move()` to move file
- `AdapterOutputPaths.cleanup_old_outputs()` to clean up

---

## Testing Strategy

### Test Groups (estimated 50-60 tests)

#### Group 1: ComplexipySettings (3 tests)
- ✅ Default field values
- ✅ Custom values override defaults
- ✅ Inherits from ToolAdapterSettings

#### Group 2: Constructor (3 tests)
- ✅ Initialize with settings
- ✅ Initialize without settings (None)
- ✅ Logs initialization

#### Group 3: init() (4 tests) ⭐ CRITICAL
- ✅ Loads config from pyproject.toml when no settings
- ✅ Creates ComplexipySettings with loaded config
- ✅ Calls super().init()
- ✅ Logs initialization complete

#### Group 4: Properties (3 tests)
- ✅ adapter_name returns "Complexipy (Complexity)"
- ✅ module_id returns MODULE_ID constant
- ✅ tool_name returns "complexipy"

#### Group 5: build_command() (6 tests) ⭐ CRITICAL
- ✅ Builds basic command with files
- ✅ Includes --output-json flag when use_json_output=True
- ✅ Includes --max-complexity-allowed with value from config
- ✅ Includes --sort flag with sort_by setting
- ✅ Raises RuntimeError when settings not initialized
- ✅ Converts file paths to strings

#### Group 6: parse_output() - JSON file path (5 tests) ⭐ CRITICAL
- ✅ Loads JSON from file when it exists
- ✅ Returns empty list when no JSON file
- ✅ Falls back to stdout parsing on JSON read error
- ✅ Calls _process_complexipy_data() with loaded data
- ✅ Logs parsing results

#### Group 7: parse_output() - JSON stdout (4 tests) ⭐ CRITICAL
- ✅ Parses JSON from raw_output when no file
- ✅ Falls back to text parsing on JSON decode error
- ✅ Returns empty list when no output
- ✅ Handles empty data structures

#### Group 8: _process_complexipy_data() - list format (5 tests) ⭐ CRITICAL
- ✅ Processes list of function dicts
- ✅ Skips functions with complexity <= max_complexity
- ✅ Creates ToolIssue with correct severity (error/warning)
- ✅ Returns empty list when no settings
- ✅ Handles missing fields gracefully

#### Group 9: _process_complexipy_data() - dict format (4 tests)
- ✅ Processes dict with "files" key
- ✅ Calls _process_file_data() for each file
- ✅ Returns empty list for empty dict
- ✅ Handles missing "files" key

#### Group 10: _process_file_data() (3 tests)
- ✅ Iterates through functions list
- ✅ Calls _create_issue_if_needed() for each function
- ✅ Returns list of issues

#### Group 11: _create_issue_if_needed() (6 tests) ⭐ CRITICAL
- ✅ Returns None when complexity <= max_complexity
- ✅ Returns ToolIssue when complexity > max_complexity
- ✅ Builds message with _build_issue_message()
- ✅ Determines severity with _determine_issue_severity()
- ✅ Returns None when no settings
- ✅ Extracts line_number from func dict

#### Group 12: _build_issue_message() (4 tests)
- ✅ Includes "Complexity: N" always
- ✅ Includes "Cognitive: N" when include_cognitive=True
- ✅ Includes "Maintainability: N.N" when include_maintainability=True
- ✅ Handles missing fields gracefully

#### Group 13: _determine_issue_severity() (4 tests)
- ✅ Returns "error" when complexity > max_complexity * 2
- ✅ Returns "warning" when complexity <= max_complexity * 2
- ✅ Returns "warning" when no settings
- ✅ Handles edge cases (complexity = 2x max)

#### Group 14: _parse_text_output() (5 tests)
- ✅ Parses "File:" lines to update current file
- ✅ Parses complexity lines with _parse_complexity_line()
- ✅ Returns empty list for empty output
- ✅ Logs parsing results
- ✅ Handles multiple files and functions

#### Group 15: _update_current_file() (3 tests)
- ✅ Extracts file path from "File:" line
- ✅ Returns new Path object
- ✅ Returns current_file unchanged for non-"File:" lines

#### Group 16: _parse_complexity_line() (4 tests)
- ✅ Parses valid complexity line
- ✅ Returns None when complexity <= max_complexity
- ✅ Returns ToolIssue with correct severity
- ✅ Returns None on parse errors (suppress)

#### Group 17: _extract_function_data() (5 tests)
- ✅ Extracts (func_name, line_number, complexity) from valid line
- ✅ Returns None for invalid line format
- ✅ Handles missing parenthesis
- ✅ Handles missing "complexity" keyword
- ✅ Handles non-numeric values (suppress)

#### Group 18: get_default_config() (4 tests)
- ✅ Returns QACheckConfig with correct fields
- ✅ Loads exclude_patterns from pyproject.toml
- ✅ Loads max_complexity from pyproject.toml
- ✅ Uses defaults when pyproject.toml missing

#### Group 19: _load_config_from_pyproject() (5 tests) ⭐ CRITICAL
- ✅ Returns default config when pyproject.toml missing
- ✅ Loads exclude_patterns from [tool.complexipy]
- ✅ Loads max_complexity from [tool.complexipy]
- ✅ Handles TOML decode errors (returns defaults)
- ✅ Handles file read errors (returns defaults)

#### Group 20: _move_complexipy_results_to_output_dir() (5 tests)
- ✅ Returns None when no result files found
- ✅ Moves newest result file to output dir
- ✅ Calls cleanup_old_outputs() after moving
- ✅ Returns original file path on move error
- ✅ Logs success/failure

---

## Key Testing Points

### MUST Test:
1. ✅ build_command() - command construction with all flags
2. ✅ parse_output() - JSON parsing with fallback chain
3. ✅ _process_complexipy_data() - list and dict formats
4. ✅ _create_issue_if_needed() - threshold checking and issue creation
5. ✅ _determine_issue_severity() - severity calculation logic
6. ✅ _load_config_from_pyproject() - config loading with error handling
7. ✅ _parse_text_output() - fallback text parsing

### MOCK:
1. ✅ BaseToolAdapter methods (super().__init__, super().init())
2. ✅ AdapterOutputPaths (get_output_dir, cleanup_old_outputs)
3. ✅ Path operations (glob, stat, shutil.move)
4. ✅ tomllib.load() for pyproject.toml
5. ✅ json.load() and json.loads() for JSON parsing

### File I/O:
1. ✅ pyproject.toml reading (use tmp_path fixture)
2. ✅ complexipy_results_*.json file moving (use tmp_path fixture)

### SKIP (intentionally):
1. ❌ Actual complexipy tool execution (test command building, not running)
2. ❌ Exact JSON format edge cases (use representative samples)

---

## Estimated Coverage

**Target**: 60-65% of 220 statements = 132-143 statements

**Achievable via**:
- 50-60 test methods
- Testing all public methods
- Testing core private helpers
- Testing error handling paths
- Testing fallback logic (JSON → text parsing)

**Uncovered** (~35-40%):
- Some edge cases in text parsing
- Some JSON format variations
- Some error handling branches
- Logging statements

---

## Dependencies

### Internal
- **BaseToolAdapter** from adapters._tool_adapter_base
- **ToolAdapterSettings** from adapters._tool_adapter_base
- **ToolExecutionResult** from adapters._tool_adapter_base
- **ToolIssue** from adapters._tool_adapter_base
- **AdapterOutputPaths** from adapters._output_paths
- **AdapterStatus** from models.adapter_metadata
- **QACheckType** from models.qa_results
- **QACheckConfig** from models.qa_config (TYPE_CHECKING only)

### External
- **json** (standard library)
- **logging** (standard library)
- **shutil** (standard library)
- **pathlib.Path** (standard library)
- **uuid.UUID** (standard library)
- **tomllib** (standard library, Python 3.11+)
- **contextlib.suppress** (standard library)
- **typing** (standard library)

---

## Complexity Assessment

**Expected Complexity**: Medium

**Challenges**:
- Async init() method (but simple logic)
- Multiple parsing strategies (JSON file, JSON stdout, text)
- Fallback chain (3 parsing paths)
- File system operations (glob, move)
- Configuration loading from TOML

**Simplifying factors**:
- Clear separation of concerns
- Well-defined data structures (ToolIssue)
- Comprehensive error handling
- Good logging for debugging

---

## Test Creation Strategy

1. **Mock BaseToolAdapter**: Prevent actual tool execution
2. **Mock AdapterOutputPaths**: Control file system operations
3. **Mock tomllib**: Control pyproject.toml loading
4. **Use tmp_path fixture**: For config files and result files
5. **Test fallback chain**: JSON file → JSON stdout → text parsing
6. **Focus on core logic**: Command building, JSON parsing, severity calculation
7. **Test error cases**: Missing config, parse errors, file errors
8. **Use representative data**: Realistic complexipy JSON samples

---

## Key Edge Cases to Test

1. **Settings not initialized** → RuntimeError in build_command()
2. **Empty JSON data** → Empty issues list
3. **Missing fields in function dict** → Graceful handling
4. **Complexity exactly at threshold** → No issue created
5. **Complexity = 2x threshold** → Severity = "error" (boundary)
6. **JSON decode error** → Fallback to text parsing
7. **File move error** → Return original file path
8. **Invalid TOML** → Return default config
9. **Missing pyproject.toml** → Return default config
10. **Text parsing failures** → suppress() returns None

---

## Success Criteria

- ✅ 100% test pass rate
- ✅ 60-65% statement coverage
- ✅ All public methods tested
- ✅ Core parsing logic covered
- ✅ Error handling paths tested
- ✅ Fallback logic tested
- ✅ Configuration loading tested
- ✅ Zero implementation bugs introduced
