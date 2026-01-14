# refurb.py - Implementation Analysis

**File**: crackerjack/adapters/refactor/refurb.py
**Lines**: 272
**Statements**: 137
**Status**: 0% coverage → Target 65-70%

---

## Implementation Structure

### Module Overview

RefurbAdapter integrates the refurb refactoring tool into crackerjack:

1. **Command Building**: Constructs refurb CLI arguments from settings
2. **Output Parsing**: Parses refurb's human-readable output format
3. **Package Detection**: Auto-detects package directory from pyproject.toml
4. **Config Generation**: Provides default configuration for crackerjack

---

## Public API (2 classes)

### 1. RefurbSettings (lines 30-37)

**Purpose**: Configuration settings for refurb adapter

**Fields**:
- `tool_name: str = "refurb"` - Tool identifier
- `use_json_output: bool = False` - JSON output mode (unused, future feature)
- `enable_all: bool = False` - Enable all refurb checks
- `disable_checks: list[str] = []` - Checks to disable
- `enable_checks: list[str] = []` - Specific checks to enable
- `python_version: str | None = None` - Target Python version
- `explain: bool = False` - Enable explanations

**Extends**: `ToolAdapterSettings`

---

### 2. RefurbAdapter (lines 40-271)

**Purpose**: Adapter for refurb refactoring tool

**Extends**: `BaseToolAdapter`

**Fields**:
- `settings: RefurbSettings | None = None` - Adapter settings

---

## Public Methods (11)

### Constructor & Initialization (2)

#### 1. __init__(settings) (lines 43-48)
**Purpose**: Initialize adapter with settings
**Parameters**: `settings: RefurbSettings | None`
**Logic**:
- Calls super().__init__
- Logs initialization

#### 2. init() (lines 50-69)
**Purpose**: Async initialization with default settings
**Logic**:
- Creates default RefurbSettings if not provided
- Sets timeout_seconds from settings
- Sets max_workers=4
- Calls super().init()
- Logs initialization details

**Lazy Imports**: None

---

### Properties (3)

#### 3. adapter_name (lines 71-73)
**Returns**: `"Refurb (Refactoring)"`

#### 4. module_id (lines 75-77)
**Returns**: `MODULE_ID` constant

#### 5. tool_name (lines 79-81)
**Returns**: `"refurb"`

---

### Command Building (1)

#### 6. build_command(files, config) (lines 83-123)
**Purpose**: Build refurb CLI command from settings
**Parameters**:
- `files: list[Path]` - Files to check
- `config: QACheckConfig | None = None` - Optional config

**Returns**: `list[str]` - Command arguments

**Logic**:
- Starts with `[self.tool_name]`
- Adds `--enable-all` if enable_all=True
- Adds `--ignore <check>` for each disabled check
- Adds `--enable <check>` for each enabled check
- Adds `--python-version <version>` if set
- Adds `--explain` if explain=True
- Adds file paths
- Logs command details
- Raises RuntimeError if settings not initialized

**Raises**: `RuntimeError` if settings is None

---

### Output Parsing (2)

#### 7. parse_output(result) (lines 125-153)
**Purpose**: Parse refurb output into ToolIssue objects
**Parameters**: `result: ToolExecutionResult`
**Returns**: `list[ToolIssue]`

**Logic**:
- Returns [] if no raw_output
- Splits output by lines
- Skips lines without "[FURB"
- Calls _parse_refurb_line() for each line
- Collects valid issues
- Logs parsing results

#### 8. _parse_refurb_line(line) (lines 155-183)
**Purpose**: Parse single refurb line into ToolIssue
**Parameters**: `line: str`
**Returns**: `ToolIssue | None`

**Logic**:
- Returns None if ":" not in line
- Splits by ":" (maxsplit=3)
- Extracts file_path, line_number
- Calls _extract_column_number() for column
- Calls _extract_message_part() for message
- Calls _extract_code_and_message() for code/message
- Returns ToolIssue with severity="warning"
- Returns None on parsing errors

**Raises**: Returns None on ValueError/IndexError

---

### Helper Methods (6)

#### 9. _extract_column_number(remaining) (lines 185-190)
**Purpose**: Extract column number from remaining text
**Parameters**: `remaining: str`
**Returns**: `int | None`

**Logic**:
- Splits by space
- Returns int if first part is digit
- Returns None otherwise

#### 10. _extract_message_part(remaining, column_number) (lines 192-196)
**Purpose**: Extract message part after column number
**Parameters**:
- `remaining: str`
- `column_number: int | None`

**Returns**: `str`

**Logic**:
- If column_number exists and space in remaining:
  - Removes first part (column number)
  - Returns stripped remainder
- Otherwise returns remaining as-is

#### 11. _extract_code_and_message(message_part) (lines 198-207)
**Purpose**: Extract [FURB###] code and message
**Parameters**: `message_part: str`
**Returns**: `tuple[str | None, str]`

**Logic**:
- Finds "[" and "]" in message_part
- Extracts code between brackets
- Extracts message after "]"
- Removes leading ":" from message
- Returns (code, message) tuple
- Returns (None, message_part) if no brackets

#### 12. _get_check_type() (lines 209-210)
**Returns**: `QACheckType.REFACTOR`

#### 13. _detect_package_directory() (lines 212-234)
**Purpose**: Auto-detect package directory from pyproject.toml
**Returns**: `str` - Package directory name

**Logic**:
- Gets current directory
- Checks for pyproject.toml
- Imports tomllib (lazy import!)
- Loads and parses pyproject.toml
- Extracts project.name and replaces "-" with "_"
- Returns package name if directory exists
- Falls back to current_dir.name if that exists
- Defaults to "src"

**Lazy Imports**:
- Line 213: `from contextlib import suppress`
- Line 220: `import tomllib`

#### 14. get_default_config() (lines 236-271)
**Purpose**: Generate default QACheckConfig for refurb
**Returns**: `QACheckConfig`

**Logic**:
- Imports QACheckConfig (lazy import!)
- Calls _detect_package_directory()
- Creates QACheckConfig with:
  - check_id=MODULE_ID
  - check_name=adapter_name
  - check_type=QACheckType.REFACTOR
  - enabled=True
  - file_patterns=[f"{package_dir}/**/*.py"]
  - exclude_patterns=[test files, venv, build, cache dirs]
  - timeout_seconds=240
  - parallel_safe=True
  - stage="comprehensive"
  - settings dict with defaults

**Lazy Imports**:
- Line 237: `from crackerjack.models.qa_config import QACheckConfig`

---

## Testing Strategy

### Test Groups (estimated 35-40 tests)

#### Group 1: RefurbSettings (5 tests)
- ✅ Has correct default values
- ✅ Extends ToolAdapterSettings
- ✅ All fields present and typed
- ✅ Field default factory functions work
- ✅ Pydantic Field configuration works

#### Group 2: __init__ (3 tests)
- ✅ Initializes with provided settings
- ✅ Initializes without settings (None)
- ✅ Logs initialization

#### Group 3: init() (5 tests) ⭐ CRITICAL
- ✅ Creates default RefurbSettings when None
- ✅ Sets timeout from _get_timeout_from_settings()
- ✅ Sets max_workers=4
- ✅ Logs initialization details
- ✅ Calls super().init()

#### Group 4: Properties (3 tests)
- ✅ adapter_name returns correct string
- ✅ module_id returns MODULE_ID
- ✅ tool_name returns "refurb"

#### Group 5: build_command() (8 tests) ⭐ CRITICAL
- ✅ Builds basic command with files
- ✅ Adds --enable-all when enable_all=True
- ✅ Adds --ignore for each disabled check
- ✅ Adds --enable for each enabled check
- ✅ Adds --python-version when set
- ✅ Adds --explain when explain=True
- ✅ Raises RuntimeError when settings not initialized
- ✅ Logs command details

#### Group 6: parse_output() (6 tests) ⭐ CRITICAL
- ✅ Returns [] when raw_output is empty
- ✅ Returns [] when raw_output has no [FURB
- ✅ Parses single issue correctly
- ✅ Parses multiple issues correctly
- ✅ Skips lines without [FURB
- ✅ Logs parsing results

#### Group 7: _parse_refurb_line() (6 tests) ⭐ CRITICAL
- ✅ Returns None when ":" not in line
- ✅ Returns None when parts < 3
- ✅ Parses line without column number
- ✅ Parses line with column number
- ✅ Extracts [FURB###] code correctly
- ✅ Returns None on ValueError/IndexError

#### Group 8: _extract_column_number() (3 tests)
- ✅ Returns int when first part is digit
- ✅ Returns None when no space
- ✅ Returns None when first part not digit

#### Group 9: _extract_message_part() (3 tests)
- ✅ Removes column number when present
- ✅ Returns remaining when column_number is None
- ✅ Handles edge cases

#### Group 10: _extract_code_and_message() (4 tests)
- ✅ Extracts code and message when [code] present
- ✅ Removes leading ":" from message
- ✅ Returns (None, message_part) when no brackets
- ✅ Handles edge cases

#### Group 11: _get_check_type() (1 test)
- ✅ Returns QACheckType.REFACTOR

#### Group 12: _detect_package_directory() (7 tests) ⭐ CRITICAL
- ✅ Returns package name from pyproject.toml
- ✅ Replaces "-" with "_" in package name
- ✅ Returns current_dir.name if that directory exists
- ✅ Returns "src" as final fallback
- ✅ Handles missing pyproject.toml
- ✅ Handles missing project.name in toml
- ✅ Handles exceptions gracefully (with suppress)

#### Group 13: get_default_config() (6 tests) ⭐ CRITICAL
- ✅ Creates QACheckConfig with correct structure
- ✅ Calls _detect_package_directory()
- ✅ Sets check_id to MODULE_ID
- ✅ Sets check_name to adapter_name
- ✅ Sets check_type to REFACTOR
- ✅ Includes all exclude patterns

---

## Key Testing Points

### MUST Test:
1. ✅ All public methods (__init__, init, build_command, parse_output)
2. ✅ All properties
3. ✅ Text parsing logic (refurb format)
4. ✅ Package directory detection from pyproject.toml
5. ✅ Default config generation
6. ✅ Command building with various settings combinations
7. ✅ Lazy import patching (tomllib, QACheckConfig)

### MOCK:
1. ✅ logging.getLogger (for log verification)
2. ✅ Path.cwd() and Path operations
3. ✅ tomllib.load (lazy import at line 220)
4. ✅ QACheckConfig (lazy import at line 237)
5. ✅ contextlib.suppress (lazy import at line 213)
6. ✅ _get_timeout_from_settings() (from base class)

### SKIP (intentionally):
1. ❌ Actual refurb command execution (handled by base class)
2. ❌ Integration with refurb tool
3. ❌ File system scanning beyond config

---

## Refurb Output Format

**Sample Refurb Output**:
```
crackerjack/adapters/refactor/refurb.py:123:45 [FURB123]: This is a message
crackerjack/cli/handlers/analytics.py:67:10 [FURB456]: Another message
```

**Format**: `{file}:{line}:{column} [{code}]: {message}`

**Parsing Logic**:
1. Split by ":" → [file, line, column_and_message]
2. Extract column from first part of remaining
3. Extract message after column
4. Extract [FURB###] code from message
5. Create ToolIssue with extracted data

---

## Estimated Coverage

**Target**: 65-70% of 137 statements = 89-96 statements

**Achievable via**:
- 35-40 test methods
- Testing all public methods
- Testing parsing logic branches
- Testing command building variations
- Testing package detection paths
- Testing default config structure

**Uncovered** (~30-35%):
- Some logging branches
- Some exception handling paths
- Edge cases in text parsing
- Some pyproject.toml parsing branches

---

## Dependencies

### Internal
- **BaseToolAdapter** from adapters._tool_adapter_base
- **ToolAdapterSettings, ToolExecutionResult, ToolIssue** from adapters._tool_adapter_base
- **AdapterStatus** from models.adapter_metadata
- **QACheckType, QACheckConfig** from models.qa_config

### External
- **logging** (standard library)
- **pathlib.Path** (standard library)
- **uuid.UUID** (standard library)
- **pydantic.Field** (external)
- **typing** (standard library)
- **tomllib** (Python 3.11+, lazy import)
- **contextlib.suppress** (standard library, lazy import)

---

## Complexity Assessment

**Expected Complexity**: Low

**Simplifying factors**:
- No subprocess execution (handled by base class)
- Simple text-based parsing (not JSON)
- Clear linear logic
- Well-structured helper methods

**Challenges**:
- Lazy import patching (tomllib at line 220, QACheckConfig at line 237)
- Text parsing edge cases
- Package detection logic with multiple fallbacks
- File system operations (mocking Path.cwd())

---

## Test Creation Strategy

1. **Module-level import**: Follow complexipy pattern
2. **Mock lazy imports**: Patch tomllib and QACheckConfig at import locations
3. **Test command building**: Verify correct command structure
4. **Test output parsing**: Use sample refurb output strings
5. **Test package detection**: Mock Path.cwd() and tomllib.load()
6. **Test default config**: Verify structure and values
7. **Skip base class methods**: Don't test execute() or run() (inherited)

---

## Success Criteria

- ✅ 100% test pass rate
- ✅ 65-70% statement coverage
- ✅ All public methods tested
- ✅ Parsing logic thoroughly tested
- ✅ Package detection tested
- ✅ Command building tested
- ✅ Zero implementation bugs introduced
