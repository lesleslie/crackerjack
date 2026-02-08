# Adapter Test Coverage Implementation Plan

## Overview

This document outlines the comprehensive test coverage strategy for crackerjack's QA adapter system.

## Target Modules

1. **crackerjack/adapters/factory.py** - DefaultAdapterFactory
2. **crackerjack/adapters/format/ruff.py** - RuffAdapter
3. **crackerjack/adapters/sast/bandit.py** - BanditAdapter
4. **crackerjack/adapters/sast/semgrep.py** - SemgrepAdapter
5. **crackerjack/adapters/refactor/refurb.py** - RefurbAdapter
6. **crackerjack/adapters/refactor/skylos.py** - SkylosAdapter
7. **crackerjack/adapters/lsp/zuban.py** - ZubanAdapter

## Test Files to Create

### Unit Tests

1. `tests/unit/adapters/test_factory.py` - Factory pattern tests
2. `tests/unit/adapters/test_ruff_adapter.py` - Ruff adapter unit tests
3. `tests/unit/adapters/test_bandit_adapter.py` - Bandit adapter unit tests
4. `tests/unit/adapters/test_semgrep_adapter.py` - Semgrep adapter unit tests
5. `tests/unit/adapters/test_refurb_adapter.py` - Refurb adapter unit tests
6. `tests/unit/adapters/test_skylos_adapter.py` - Skylos adapter unit tests
7. `tests/unit/adapters/test_zuban_adapter.py` - Zuban adapter unit tests

### Integration Tests

8. `tests/integration/adapters/test_adapter_parser_integration.py` - End-to-end integration tests
9. `tests/integration/adapters/test_factory_workflow.py` - Factory workflow tests

## Coverage Goals

- **Factory**: 90%+ coverage
- **Each adapter**: 70-80% coverage
- **Integration**: 60%+ coverage (end-to-end scenarios)

## Test Strategy

### Factory Tests

1. **Name Mapping**: Test `get_adapter_name()` and `tool_has_adapter()`
2. **Adapter Creation**: Test `create_adapter()` for all adapter types
3. **AI Agent Integration**: Test `_enable_tool_native_fixes()` with environment variable
4. **Error Handling**: Test unknown adapter raises ValueError

### Adapter Interface Tests

For each adapter (Ruff, Bandit, Semgrep, Refurb, Skylos, Zuban):

1. **Initialization**: Test `__init__()` and `init()` async methods
2. **Properties**: Test `adapter_name`, `module_id`, `tool_name`
3. **Command Building**: Test `build_command()` with various settings
4. **Output Parsing**:
   - JSON parsing (where applicable)
   - Text parsing (fallback)
   - Empty output handling
   - Malformed output handling
5. **Error Handling**: Test timeouts, missing tools, invalid output
6. **Default Config**: Test `get_default_config()` returns valid config

### Integration Tests

1. **Adapter + Parser**: Test that adapter output integrates with parsers
2. **Factory + Adapter**: Test factory creates working adapters
3. **End-to-End**: Test full check workflow from file list to QA result

## Test Patterns

### Mock Strategy

- Use `unittest.mock.AsyncMock` for async methods
- Use `unittest.mock.patch` for subprocess calls
- Create fixture-based temporary files for file operations
- Mock tool availability checks to avoid dependency on installed tools

### Fixture Strategy

```python
@pytest.fixture
async def mock_ruff_settings():
    """Provide RuffSettings for testing."""
    return RuffSettings(
        timeout_seconds=60,
        max_workers=4,
        mode="check",
        fix_enabled=False,
    )

@pytest.fixture
def sample_python_file(tmp_path):
    """Create a sample Python file for testing."""
    test_file = tmp_path / "test.py"
    test_file.write_text("x = 1\n")
    return test_file
```

### Async Test Pattern

```python
@pytest.mark.asyncio
async def test_adapter_check(adapter, tmp_path):
    """Test adapter check method."""
    test_file = tmp_path / "test.py"
    test_file.write_text("x = 1\n")

    result = await adapter.check([test_file])

    assert result.status in (QAResultStatus.SUCCESS, QAResultStatus.WARNING)
```

## Implementation Order

1. **Factory tests** (simple, no async complexity)
2. **Ruff adapter tests** (representative adapter with JSON + text parsing)
3. **Bandit/Semgrep tests** (SAST adapters, similar patterns)
4. **Refurb/Skylos tests** (refactoring adapters, text parsing only)
5. **Zuban tests** (LSP adapter, most complex)
6. **Integration tests** (end-to-end workflows)

## Success Criteria

- All new tests pass
- Coverage targets met (see above)
- No existing tests broken
- Tests follow crackerjack patterns (DI, fixtures, async/await)
- Documentation updated with test examples

## Dependencies

- pytest >= 7.0
- pytest-asyncio >= 0.21
- pytest-cov >= 4.0
- Existing conftest.py fixtures
- Existing test infrastructure

## Timeline

- Phase 1: Factory tests (1 file)
- Phase 2: Format/SAST adapters (3 files)
- Phase 3: Refactor/LSP adapters (3 files)
- Phase 4: Integration tests (2 files)
- Phase 5: Coverage verification and documentation

## Notes

- Tests should NOT require actual tools to be installed (use mocks)
- Tests should be fast (avoid real subprocess calls where possible)
- Tests should be isolated (no shared state between tests)
- Tests should be readable (clear test names, good documentation)
