# Tools and Parsers Test Coverage Plan

## Overview
Add comprehensive test coverage for crackerjack's quality toolchain - the tools that run checks and the parsers that interpret their results.

## Target Modules

### Tools (Quality Hooks)
1. `crackerjack/tools/check_json.py` - JSON validation
2. `crackerjack/tools/check_yaml.py` - YAML validation
3. `crackerjack/tools/check_toml.py` - TOML validation
4. `crackerjack/tools/mdformat_wrapper.py` - Markdown formatter
5. `crackerjack/tools/codespell_wrapper.py` - Spell checker
6. `crackerjack/tools/_git_utils.py` - Git file utilities

### Parsers
1. `crackerjack/parsers/base.py` - Base parser classes
2. `crackerjack/parsers/json_parsers.py` - JSON parsers (Ruff, Mypy, Bandit, etc.)
3. `crackerjack/parsers/regex_parsers.py` - Regex parsers (Codespell, etc.)
4. `crackerjack/parsers/factory.py` - Parser factory

## Test Files to Create

### Unit Tests
1. `tests/unit/tools/test_check_json.py`
2. `tests/unit/tools/test_check_yaml.py`
3. `tests/unit/tools/test_check_toml.py`
4. `tests/unit/tools/test_mdformat_wrapper.py`
5. `tests/unit/tools/test_codespell_wrapper.py`
6. `tests/unit/tools/test_git_utils.py`
7. `tests/unit/parsers/test_base.py`
8. `tests/unit/parsers/test_json_parsers.py`
9. `tests/unit/parsers/test_regex_parsers.py`
10. `tests/unit/parsers/test_factory.py`

### Integration Tests
1. `tests/integration/tools/test_tool_parser_integration.py`

## Coverage Goals
- **Tool wrappers**: 75%+ coverage (each tool is fairly simple)
- **Parsers**: 70%+ coverage (parse logic, error handling)
- **Integration**: 60%+ coverage (end-to-end workflows)

## Testing Strategy

### Tool Tests
- Test successful validation with valid files
- Test error detection with invalid files
- Test CLI argument parsing
- Test git integration scenarios
- Test edge cases (empty files, malformed content)

### Parser Tests
- Test parsing valid tool output
- Test parsing empty output
- Test handling malformed output gracefully
- Test issue extraction accuracy
- Test severity mapping
- Test edge cases and error recovery

### Integration Tests
- Test complete workflow: file → tool → parser → issues
- Test tool-parser compatibility
- Test error propagation
- Test real-world scenarios

## Dependencies
- pytest
- pytest-cov (for coverage reporting)
- tempfile (for test file creation)
- subprocess mocking for tool execution

## Notes
- Tests should be synchronous where possible (avoid async complexity)
- Use tmp_path fixture for file operations
- Mock subprocess calls to avoid actual tool dependencies
- Test error paths, not just happy paths
