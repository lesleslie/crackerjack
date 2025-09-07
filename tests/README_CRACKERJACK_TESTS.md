# Crackerjack Integration Tests

This document describes the comprehensive test suite created to prevent the CrackerjackIntegration issues that were encountered during development.

## Tests Created

### 1. Unit Tests (`tests/unit/test_crackerjack_integration.py`)

**Purpose**: Test individual CrackerjackIntegration class methods and functionality.

**Key Test Classes**:

- `TestCrackerjackIntegrationMethodExists`: Verifies required methods exist with correct signatures
- `TestExecuteCommandMethod`: Tests synchronous execute_command method
- `TestExecuteCrackerjackCommandMethod`: Tests async execute_crackerjack_command method
- `TestProtocolCompliance`: Ensures CommandRunner protocol compliance
- `TestDatabaseIntegration`: Tests database functionality
- `TestMCPToolIntegration`: Tests MCP tool compatibility
- `TestRegressionTests`: Specific tests for the exact bugs encountered

**Critical Tests**:

```bash
# Test that would have caught the original error
pytest tests/unit/test_crackerjack_integration.py::TestCrackerjackIntegrationMethodExists::test_execute_command_method_exists
```

### 2. Integration Tests (`tests/integration/test_mcp_crackerjack_tools.py`)

**Purpose**: Test MCP tool integration and end-to-end workflows.

**Key Test Classes**:

- `TestMCPCrackerjackToolRegistration`: Tests MCP tool registration
- `TestMCPToolExecution`: Tests actual MCP tool execution
- `TestErrorHandlingAndRecovery`: Tests error scenarios
- `TestRealIntegration`: Tests with mocked subprocess calls
- `TestProtocolCompliance`: Tests external protocol compatibility

### 3. Protocol Compliance Tests (`tests/unit/test_protocol_compliance.py`)

**Purpose**: Test compliance with external protocols and prevent interface regressions.

**Key Test Classes**:

- `TestCommandRunnerProtocol`: Tests crackerjack CommandRunner protocol compliance
- `TestAsyncMethodCompatibility`: Tests async method interfaces
- `TestResultTypeCompatibility`: Tests result type consistency
- `TestMCPToolCompatibility`: Tests MCP system compatibility
- `TestErrorHandlingProtocol`: Tests error handling consistency
- `TestRegressionPreventionTests`: Specific regression prevention

## Issues These Tests Would Have Caught

### 1. Missing `execute_command` Method

**Original Error**: `'CrackerjackIntegration' object has no attribute 'execute_command'`

**Test That Catches This**:

```python
def test_execute_command_method_exists(self):
    integration = CrackerjackIntegration()
    assert hasattr(integration, "execute_command"), "execute_command method missing"
```

### 2. Incorrect Command Structure

**Original Error**: `Got unexpected extra argument (lint)`

**Test That Catches This**:

```python
def test_prevents_command_structure_error(self):
    # Verifies command is ['crackerjack', '--fast'], NOT ['crackerjack', 'lint']
    assert "lint" not in cmd, "Command should not contain 'lint' as separate argument"
```

### 3. Result Type Mismatches

**Original Issue**: MCP tools expected dict but got CrackerjackResult

**Test That Catches This**:

```python
def test_return_types_consistency(self):
    # Sync method should return dict
    sync_result = integration.execute_command(["test"])
    assert isinstance(sync_result, dict)

    # Async method should return CrackerjackResult
    async_result = await integration.execute_crackerjack_command("test", [], ".")
    assert isinstance(async_result, CrackerjackResult)
```

## Running the Tests

### Run All Crackerjack Tests

```bash
pytest tests/unit/test_crackerjack_integration.py tests/integration/test_mcp_crackerjack_tools.py tests/unit/test_protocol_compliance.py -v
```

### Run Critical Method Existence Tests

```bash
pytest tests/unit/test_crackerjack_integration.py::TestCrackerjackIntegrationMethodExists -v
```

### Run Regression Prevention Tests

```bash
pytest tests/unit/test_protocol_compliance.py::TestRegressionPreventionTests -v
```

### Run Integration Tests

```bash
pytest tests/integration/test_mcp_crackerjack_tools.py -v
```

## Test Coverage

The tests cover:

- ✅ Method existence and signatures
- ✅ CommandRunner protocol compliance
- ✅ Command structure correctness
- ✅ Result type consistency
- ✅ MCP tool integration
- ✅ Error handling scenarios
- ✅ Database integration
- ✅ Async/sync method compatibility
- ✅ Specific regression prevention

## Command Mapping Tests

The tests verify correct command mappings:

- `lint` → `crackerjack --fast`
- `check` → `crackerjack --comp`
- `test` → `crackerjack --test`
- `format` → `crackerjack --fast`
- `typecheck` → `crackerjack --comp`
- `clean` → `crackerjack --clean`
- `all` → `crackerjack --all`

## CI Integration

Add to your CI pipeline:

```yaml
- name: Run Crackerjack Integration Tests
  run: |
    pytest tests/unit/test_crackerjack_integration.py \
           tests/integration/test_mcp_crackerjack_tools.py \
           tests/unit/test_protocol_compliance.py \
           --cov=session_mgmt_mcp.crackerjack_integration \
           --cov=session_mgmt_mcp.tools.crackerjack_tools \
           --cov-fail-under=85
```

## Maintenance

When modifying CrackerjackIntegration:

1. **Always run method existence tests first**:

   ```bash
   pytest tests/unit/test_crackerjack_integration.py::TestCrackerjackIntegrationMethodExists
   ```

1. **Check protocol compliance**:

   ```bash
   pytest tests/unit/test_protocol_compliance.py::TestCommandRunnerProtocol
   ```

1. **Verify MCP integration**:

   ```bash
   pytest tests/integration/test_mcp_crackerjack_tools.py::TestMCPToolExecution
   ```

1. **Run regression tests**:

   ```bash
   pytest tests/unit/test_protocol_compliance.py::TestRegressionPreventionTests
   ```

These tests provide comprehensive coverage to prevent the issues that were encountered and ensure robust integration between the session-mgmt-mcp server and crackerjack.
