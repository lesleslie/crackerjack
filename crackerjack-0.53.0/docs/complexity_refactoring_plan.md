# Complexity Refactoring Plan

## Objective

Reduce complexity for 9 functions to ≤15 using the standard refactoring pattern of extracting logical chunks into focused helper methods.

## Functions to Refactor

### 1. trailing_whitespace.py: main (complexity: 19 → target: ≤15)

**Current complexity**: 19 (4 points over limit)

**Refactoring strategy**: Extract file collection and processing logic into helpers

- `_collect_files_to_check()` - Handle file collection logic (lines 110-127)
- `_process_files_for_check()` - Handle check mode processing (lines 131-142)
- `_process_files_for_fix()` - Handle fix mode processing (lines 139-142)

### 2. check_jsonschema.py: \_check_internal_schema_ref (complexity: 16 → target: ≤15)

**Current complexity**: 16 (1 point over limit)

**Refactoring strategy**: Extract schema path resolution into helper

- `_resolve_local_schema_path()` - Handle local file path resolution (lines 46-51)

### 3. end_of_file_fixer.py: main (complexity: 24 → target: ≤15)

**Current complexity**: 24 (9 points over limit)

**Refactoring strategy**: Extract file collection and processing logic

- `_collect_files_to_check()` - Handle file collection (lines 108-125)
- `_check_files_for_newlines()` - Handle check mode processing (lines 129-142)
- `_fix_files_newlines()` - Handle fix mode processing (lines 139-140)

### 4. phase_coordinator.py: PhaseCoordinator::\_display_hook_failures (complexity: 34 → target: ≤15)

**Current complexity**: 34 (19 points over limit) - **MOST COMPLEX**

**Refactoring strategy**: Break into multiple helpers for different failure types

- `_format_failing_hooks()` - Format list of failing hooks (lines 700-716)
- `_display_issue_details()` - Display specific issues (lines 718-724)
- `_display_timeout_info()` - Display timeout information (lines 727-730)
- `_display_exit_code_info()` - Display exit code with context (lines 731-741)
- `_display_error_message()` - Display error message preview (lines 742-746)
- `_display_generic_failure()` - Display generic failure message (lines 748-756)

### 5. hook_manager.py: HookManagerImpl::\_load_orchestration_config (complexity: 16 → target: ≤15)

**Current complexity**: 16 (1 point over limit)

**Refactoring strategy**: Extract config loading branches

- `_load_from_project_config()` - Load from .crackerjack.yaml (lines 101-116)
- `_create_default_orchestration_config()` - Create default config (lines 118-138)

### 6. test_progress.py: TestProgress::\_format_execution_progress (complexity: 17 → target: ≤15)

**Current complexity**: 17 (2 points over limit)

**Refactoring strategy**: Extract status formatting logic

- `_format_progress_counters()` - Format pass/fail/skip/error counters (lines 150-168)

### 7. test_manager.py: TestManager::\_get_fallback_coverage (complexity: 17 → target: ≤15)

**Current complexity**: 17 (2 points over limit)

**Refactoring strategy**: Extract fallback chain steps

- `_try_service_coverage()` - Try coverage service fallback (lines 615-623)
- `_handle_zero_coverage_fallback()` - Handle 0.0% fallback case (lines 624-629)

### 8. claude_code_bridge.py: ClaudeCodeBridge::consult_on_issue (complexity: 17 → target: ≤15)

**Current complexity**: 17 (2 points over limit)

**Refactoring strategy**: Extract AI result processing steps

- `_validate_ai_result()` - Validate AI response (lines 483-501)
- `_apply_ai_fix()` - Apply fix to file (lines 504-533)

### 9. zuban.py: ZubanAdapter::\_extract_parts_from_line (complexity: 31 → target: ≤15)

**Current complexity**: 31 (16 points over limit) - **SECOND MOST COMPLEX**

**Refactoring strategy**: Break into format-specific parsers

- `_parse_with_column_format()` - Handle file:line:col: error: format (lines 245-274)
- `_parse_without_column_format()` - Handle file:line: error: format (lines 276-287)
- `_parse_standard_format()` - Handle standard error format (lines 291-304)

## Implementation Order

1. Simple cases first (1 point over): #2, #5
1. Medium cases (2 points over): #6, #7, #8
1. Complex cases (4-9 points): #1, #3
1. Most complex cases: #4 (19 over), #9 (16 over)

## Success Criteria

- All functions ≤15 complexity after refactoring
- All tests pass
- No functional changes
- Type hints maintained
- Coverage maintained or improved
