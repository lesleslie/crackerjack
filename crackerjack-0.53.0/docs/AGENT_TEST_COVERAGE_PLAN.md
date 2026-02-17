# Agent System Test Coverage Plan

## Current Status

### Existing Tests (Already Pass)
- ✅ `tests/unit/agents/test_base.py` - 47 tests passing
- ✅ `tests/unit/agents/test_refactoring_agent.py` - exists
- ✅ `tests/unit/agents/test_security_agent.py` - exists
- ✅ `tests/unit/agents/test_test_creation_agent.py` - exists
- ✅ `tests/unit/agents/test_performance_agent.py` - exists
- ✅ `tests/unit/agents/test_semantic_agent.py` - exists

### Missing Tests
- ❌ `tests/unit/agents/test_error_middleware.py` - NEW
- ❌ `tests/integration/agents/test_agent_workflow.py` - NEW
- ❌ Additional edge case tests for base agent

## Test Creation Strategy

### 1. Error Middleware Tests (`test_error_middleware.py`)

**Purpose**: Test the `agent_error_boundary` decorator that wraps agent execution.

**Test Cases**:
1. **Decorator applies correctly**
   - Verify decorator wraps async functions
   - Check function signature is preserved

2. **Error handling**
   - Agent raises exception → returns FixResult with success=False
   - Exception message propagated to remaining_issues
   - Recommendations include "Review agent logs"
   - Console.error called if console available

3. **Success path**
   - Agent returns FixResult → returned unchanged
   - No side effects on success

4. **Edge cases**
   - Missing logger attribute
   - Missing console attribute
   - None console vs missing console

**Mocking Strategy**:
```python
- Mock AgentCoordinator with context, logger
- Mock SubAgent with analyze_and_fix that raises
- Mock Console for output verification
- Use pytest.raises for exception testing
```

### 2. Integration Tests (`test_agent_workflow.py`)

**Purpose**: Test end-to-end agent coordination and workflow.

**Test Cases**:
1. **Multi-agent coordination**
   - Multiple agents handle different issue types
   - Results merged correctly
   - No duplicate fixes applied

2. **Issue routing**
   - Issue routed to correct agent based on type
   - Agent with highest confidence selected
   - Fallback to generic agent if no match

3. **Sequential fixing**
   - Issues processed in order
   - Failed fixes don't stop remaining fixes
   - Results accumulated properly

4. **Real-world scenarios**
   - Complexity + security issues in same file
   - Dead code + type errors
   - Multiple files in single batch

**Fixtures**:
```python
- mock_project_path: tmp_path with sample Python files
- mock_issues: predefined Issue objects
- mock_coordinator: AgentCoordinator with mocked dependencies
```

### 3. Enhanced Base Agent Tests

**Add to existing `test_base.py`**:

1. **Async file operations**
   - `async_get_file_content` success/failure
   - `async_write_file_content` validation
   - Async write verification

2. **Edge cases for write validation**
   - Files with encoding issues
   - Files with BOM markers
   - Mixed line endings (CRLF vs LF)

3. **SubAgent command execution**
   - Command with environment variables
   - Command with custom timeout
   - stderr vs stdout handling

## Coverage Goals

### Target Metrics
- **Base classes**: 85%+ coverage (currently ~80%)
- **Error middleware**: 90%+ coverage (new, critical infrastructure)
- **Integration tests**: 70%+ coverage (end-to-end workflows)

### Priority Areas
1. **Critical**: Error handling (error middleware)
2. **High**: Agent coordination (integration tests)
3. **Medium**: Edge cases in base operations

## Implementation Plan

### Phase 1: Error Middleware Tests
- File: `tests/unit/agents/test_error_middleware.py`
- Estimated lines: 200-300
- Time: 30 minutes

### Phase 2: Integration Tests
- File: `tests/integration/agents/test_agent_workflow.py`
- Estimated lines: 400-500
- Time: 45 minutes

### Phase 3: Enhanced Base Tests
- Extend: `tests/unit/agents/test_base.py`
- Add: ~100 lines of new tests
- Time: 20 minutes

## Verification

```bash
# Run all agent tests
python -m pytest tests/unit/agents/ tests/integration/agents/ -v

# Check coverage (separate run to avoid import issues)
python -m pytest tests/unit/agents/test_base.py --cov=crackerjack.agents.base --cov-report=html

# View detailed coverage
open htmlcov/index.html
```

## Success Criteria

1. ✅ All new tests pass
2. ✅ No regressions in existing tests
3. ✅ Coverage increased for agent modules
4. ✅ Integration tests cover real workflows
5. ✅ Error middleware properly tested

## Notes

- Current tests already cover base classes well (47 passing)
- Specialized agents (RefactoringAgent, SecurityAgent, etc.) already have tests
- Focus on **missing** components: error middleware and integration
- Keep tests synchronous where possible (avoid async complexity)
- Use tmp_path fixture for file operations
- Mock external dependencies (LLM, filesystem)
