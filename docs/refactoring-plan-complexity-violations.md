# Complexity Violations Refactoring Plan

## Overview

Refactor 11 functions exceeding complexity threshold of 15 to meet crackerjack quality standards (≤15).

## Violations to Fix (Ordered by Complexity)

### Priority 1: Highest Complexity (27-22)

1. **AsyncTimeoutManager.timeout_context** - Complexity 27

   - File: `crackerjack/core/timeout_manager.py:184`
   - Current: 27 → Target: ≤15
   - Strategy: Extract error handling methods for each exception type
   - Helpers to create:
     - `_handle_success_completion()` - Handle successful yield completion
     - `_handle_custom_timeout_error()` - Handle TimeoutError
     - `_handle_asyncio_timeout()` - Handle builtins.TimeoutError
     - `_handle_cancelled_error()` - Handle asyncio.CancelledError
     - `_handle_generic_exception()` - Handle other exceptions

1. **QualityIntelligenceService.generate_ml_recommendations** - Complexity 22

   - File: `crackerjack/services/quality/quality_intelligence.py:665`
   - Current: 22 → Target: ≤15
   - Strategy: Extract recommendation generation by category
   - Helpers to create:
     - `_generate_anomaly_recommendations()` - Critical/quality drop recommendations
     - `_generate_pattern_recommendations()` - Pattern-based insights
     - `_generate_prediction_recommendations()` - Forecast-based recommendations
     - `_generate_general_ml_insights()` - General ML insights

### Priority 2: High Complexity (21-19)

3. **DocumentationServiceImpl.extract_api_documentation** - Complexity 21

   - File: `crackerjack/services/documentation_service.py:43`
   - Current: 21 → Target: ≤15
   - Strategy: Extract file type categorization and extraction logic
   - Helpers to create:
     - `_categorize_source_files()` - Group files by type
     - `_extract_python_apis()` - Extract from Python files
     - `_extract_specialized_apis()` - Extract protocols, services, managers, CLI, MCP

1. **TestManager.\_extract_structured_failures** - Complexity 21

   - File: `crackerjack/managers/test_manager.py:1014`
   - Current: 21 → Target: ≤15
   - Strategy: Extract parsing logic for different sections
   - Helpers to create:
     - `_parse_failure_header()` - Parse FAILED/ERROR lines
     - `_parse_location_line()` - Parse file:line:error format
     - `_parse_assertion_error()` - Parse AssertionError lines
     - `_parse_captured_output()` - Parse stdout/stderr sections
     - `_parse_traceback_lines()` - Parse traceback content

1. **FileSystemService.read_lines_streaming** - Complexity 19

   - File: `crackerjack/services/filesystem.py:379`
   - Current: 19 → Target: ≤15
   - Strategy: Extract validation and error handling
   - Helpers to create:
     - `_validate_file_exists()` - Validate file existence
     - `_handle_file_read_errors()` - Centralized error handling

1. **FileSystemService.read_file_chunked** - Complexity 19

   - File: `crackerjack/services/filesystem.py:339`
   - Current: 19 → Target: ≤15
   - Strategy: Extract validation and error handling (same as #5)
   - Reuse helpers from read_lines_streaming

### Priority 3: Medium Complexity (18-17)

7. **FileSystemService.mkdir** - Complexity 18

   - File: `crackerjack/services/filesystem.py:98`
   - Current: 18 → Target: ≤15
   - Strategy: Extract error handling logic
   - Helpers to create:
     - `_handle_mkdir_permission_error()` - Permission error handling
     - `_handle_mkdir_os_error()` - OSError handling with disk space check

1. **FileSystemService.read_file** - Complexity 17

   - File: `crackerjack/services/filesystem.py:21`
   - Current: 17 → Target: ≤15
   - Strategy: Extract validation and error handling
   - Reuse helpers from read_lines_streaming

1. **FileSystemService.\_perform_file_copy** - Complexity 17

   - File: `crackerjack/services/filesystem.py:218`
   - Current: 17 → Target: ≤15
   - Strategy: Extract error handling logic
   - Helpers to create:
     - `_handle_copy_permission_error()` - Permission error handling
     - `_handle_copy_os_error()` - OSError handling with disk space check

1. **EnhancedFileSystemService.\_read_file_direct** - Complexity 17

   - File: `crackerjack/services/enhanced_filesystem.py:332`
   - Current: 17 → Target: ≤15
   - Strategy: Extract error handling logic (similar to FileSystemService.read_file)
   - Reuse error handling pattern from FileSystemService

### Priority 4: Low Complexity (16)

11. **\_apply_graph_filters** - Complexity 16
    - File: `crackerjack/mcp/websocket/monitoring/utils.py:84`
    - Current: 16 → Target: ≤15
    - Strategy: Extract node filtering and prioritization logic
    - Helpers to create:
    - `_filter_nodes_by_criteria()` - Apply type and external filters
    - `_prioritize_and_limit_nodes()` - Priority sorting and limiting

## Implementation Principles

### Follow DRY/YAGNI/KISS

- Extract meaningful helper methods, not just code blocks
- Each helper should have single responsibility
- Reuse common patterns (e.g., error handling)

### Maintain ACB Architecture

- Preserve all `@depends.inject` decorators
- Keep protocol-based dependency injection intact
- Import protocols from `models/protocols.py`

### Preserve Functionality

- No behavior changes - only structural refactoring
- All tests must pass after refactoring
- Maintain type annotations

### Error Handling Patterns

Common pattern across FileSystemService methods:

```python
def _handle_read_errors(self, path: Path, error: Exception) -> None:
    """Centralized error handling for file read operations."""
    if isinstance(error, PermissionError):
        raise FileError(message="Permission denied", ...) from error
    elif isinstance(error, UnicodeDecodeError):
        raise FileError(message="Encoding error", ...) from error
    elif isinstance(error, OSError):
        raise FileError(message="System error", ...) from error
```

## Testing Strategy

1. Run existing test suite after each refactoring
1. Verify complexity with: `python -m crackerjack run`
1. Ensure no behavior changes with integration tests
1. Check coverage ratchet is maintained

## Implementation Order

1. Start with highest complexity (AsyncTimeoutManager.timeout_context)
1. Work through FileSystemService methods (5 functions) as a group
1. Complete remaining high-complexity functions
1. Finish with lowest complexity violation

## Success Criteria

- All functions ≤15 complexity
- All existing tests pass
- Coverage ratchet maintained (≥21.6%)
- No behavior changes detected
- Code follows crackerjack architecture patterns
