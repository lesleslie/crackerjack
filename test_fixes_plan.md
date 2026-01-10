# Test Fixes Plan

## Issues Identified

### 1. check_added_large_files.py - Missing Output
**Problem**: Lines 76-77 have a `pass` statement instead of printing file details
**Test failures**:
- `test_cli_mixed_valid_and_large` - expects "large.bin" in stderr
- `test_size_formatting_in_output` - expects "MB" in output

**Fix**: Replace `pass` with actual print statement showing file name and formatted size

### 2. trailing_whitespace.py - Line Ending Normalization
**Problem**: `splitlines(keepends=True)` normalizes line endings, breaking CRLF preservation
**Test failures**:
- `test_preserves_newline_type` - expects CRLF to be preserved
- `test_python_file_with_code` - likely related to line ending handling

**Fix**: Read and process file byte-by-byte or use different approach that preserves original line endings

## Implementation Plan

1. Fix check_added_large_files.py line 76-77
2. Fix trailing_whitespace.py to preserve line endings
3. Run tests to verify
4. Run crackerjack quality checks
