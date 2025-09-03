# Testing Framework Documentation

## Overview

This project now includes a comprehensive testing framework designed specifically for MCP (Model Context Protocol) server testing. The framework provides unit, integration, performance, and security testing with industry best practices.

## Quick Start

```bash
# Run all tests with coverage
python run_tests.py

# Run specific test suites
python run_tests.py --unit           # Unit tests only
python run_tests.py --integration    # Integration tests only
python run_tests.py --performance    # Performance tests only
python run_tests.py --security       # Security tests only

# Quick smoke tests
python run_tests.py --quick

# Parallel execution
python run_tests.py --parallel

# Coverage only (no test execution)
python run_tests.py --coverage-only
```

## Test Structure

```
tests/
├── conftest.py              # Global fixtures and configuration
├── fixtures/
│   ├── data_factories.py    # Test data generation factories
│   └── __init__.py
├── unit/                    # Unit tests
│   ├── test_session_permissions.py
│   ├── test_reflection_tools.py
│   └── __init__.py
├── integration/             # Integration tests
│   ├── test_mcp_tools.py
│   └── __init__.py
├── performance/             # Performance tests
│   ├── test_database_performance.py
│   └── __init__.py
├── security/               # Security tests
│   ├── test_permission_security.py
│   └── __init__.py
├── mcp/                    # MCP-specific utilities
│   ├── test_helpers.py
│   └── __init__.py
└── utils/                  # Test utilities
    ├── test_runner.py      # Comprehensive test runner
    ├── test_data_manager.py # Test data lifecycle management
    └── __init__.py
```

## Key Features

### 1. Async Testing Support

- Full async/await support for MCP server testing
- Proper event loop management
- Concurrent operation testing

### 2. Database Testing

- Temporary database fixtures
- Database integrity verification
- Performance profiling for DuckDB operations
- Memory usage monitoring

### 3. MCP Server Testing

- Mock MCP server creation
- Tool registration verification
- Session workflow testing
- Error handling validation

### 4. Performance Monitoring

- Execution time tracking
- Memory usage analysis
- Concurrent access testing
- Baseline comparison

### 5. Security Testing

- SQL injection prevention
- Input sanitization validation
- Rate limiting tests
- Permission boundary testing

### 6. Quality Metrics

- 85% minimum coverage requirement
- Quality scoring algorithm
- Comprehensive reporting
- Recommendations system

## Test Data Management

The framework includes sophisticated test data management:

```python
# Create test project structure
data_manager = TestDataManager()
with data_manager.temp_directory() as temp_dir:
    project_path = data_manager.create_test_project_structure(temp_dir, "test_project")

# Generate test datasets
reflections = data_manager.generate_test_dataset("reflections", size="medium")
sessions = data_manager.generate_test_dataset("sessions", size="small")

# Database testing
async with data_manager.temp_database(populate=True) as db:
    # Your test code here
    pass
```

## Coverage Configuration

Coverage is configured via `.coveragerc`:

- Source: `session_mgmt_mcp` package
- Excludes test files, migrations, and debug code
- HTML, XML, and JSON output formats
- 85% minimum coverage threshold

## Running Tests

### Command Line Options

```bash
# Test suite selection
--all                    # Run all test suites (default)
--quick                  # Quick smoke tests only
--unit                   # Unit tests only
--integration            # Integration tests only
--performance            # Performance tests only
--security               # Security tests only

# Coverage options
--coverage               # Enable coverage reporting (default)
--no-coverage            # Disable coverage reporting
--coverage-only          # Generate coverage report only

# Execution options
--parallel               # Run tests in parallel
--verbose                # Verbose output
--quiet                  # Minimal output
--timeout 600            # Test timeout in seconds

# Quality thresholds
--min-coverage 85.0      # Minimum coverage percentage
--fail-on-coverage       # Fail if coverage below minimum

# Output options
--output-dir test_reports    # Output directory for reports
--json-output results.json   # Save results to JSON file
--no-cleanup                 # Skip cleanup (for debugging)
```

### Example Commands

```bash
# Production-ready test run
python run_tests.py --parallel --min-coverage 90 --fail-on-coverage

# Quick development check
python run_tests.py --quick --no-coverage

# Debug specific issues
python run_tests.py --unit --verbose --no-cleanup

# Performance baseline
python run_tests.py --performance --json-output perf_baseline.json

# Security audit
python run_tests.py --security --verbose
```

## Integration with Development Workflow

### Pre-commit Testing

```bash
python run_tests.py --quick
```

### CI/CD Integration (Future)

The framework is designed to integrate with CI/CD systems:

- JUnit XML output support
- Exit codes for automation
- JSON results for parsing
- Parallel execution support

### Quality Gates

- Minimum 85% code coverage
- All security tests must pass
- Performance regression detection
- Comprehensive error handling validation

## Extending the Framework

### Adding New Test Categories

1. Create new directory under `tests/`
1. Add corresponding marker in `pytest.ini`
1. Update `run_tests.py` command line options
1. Implement test runner logic

### Custom Fixtures

Add to `tests/conftest.py` or create module-specific conftest files.

### Performance Metrics

Use `PerformanceTestDataManager` to track custom metrics:

```python
perf_manager = PerformanceTestDataManager(data_manager)
perf_manager.record_performance_metric("custom_metric", value)
perf_manager.set_baseline_metric("custom_metric", baseline_value)
```

## Troubleshooting

### Common Issues

1. **Import errors**: Ensure `session_mgmt_mcp` is in PYTHONPATH
1. **Database locks**: Use `--no-cleanup` to investigate temp databases
1. **Async issues**: Check event loop configuration in tests
1. **Coverage gaps**: Use `--coverage-only` to generate detailed reports

### Debug Mode

```bash
python run_tests.py --verbose --no-cleanup --timeout 0
```

This enables maximum debugging information and preserves test artifacts.

## Advanced Testing Patterns

### Async Testing Best Practices

```python
import pytest
from unittest.mock import AsyncMock, Mock, patch


@pytest.mark.asyncio
class TestAsyncPatterns:
    """Examples of proper async testing patterns"""

    async def test_async_mcp_tool_execution(self, mock_database):
        """Test async MCP tool with proper mocking"""
        # Use AsyncMock for async operations
        mock_db = AsyncMock()
        mock_db.store_reflection.return_value = "reflection-id-123"

        with patch(
            "session_mgmt_mcp.reflection_tools.ReflectionDatabase"
        ) as mock_class:
            mock_class.return_value = mock_db

            # Test the actual MCP tool
            from session_mgmt_mcp.server import store_reflection

            result = await store_reflection(
                content="Test reflection", tags=["async", "testing"]
            )

            assert result["success"] is True
            assert result["reflection_id"] == "reflection-id-123"
            mock_db.store_reflection.assert_called_once()

    @pytest.fixture
    async def isolated_database(self):
        """Create isolated test database with proper cleanup"""
        import tempfile
        from pathlib import Path
        from session_mgmt_mcp.reflection_tools import ReflectionDatabase

        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            db = ReflectionDatabase(str(db_path))
            await db.initialize()
            yield db
            await db.close()
```

### Property-Based Testing Integration

```python
from hypothesis import given, strategies as st, settings


@given(
    content=st.text(min_size=1, max_size=10000),
    tags=st.lists(st.text(min_size=1, max_size=50), max_size=10),
)
@settings(max_examples=50)
@pytest.mark.asyncio
async def test_reflection_storage_properties(content, tags, isolated_database):
    """Property-based test ensuring reflection storage is robust"""
    db = isolated_database

    # Property: All valid content should store successfully
    result = await db.store_reflection(
        content=content, tags=tags, project="property-test"
    )

    assert isinstance(result, str)
    assert len(result) > 0

    # Property: Stored data should be retrievable
    search_results = await db.search_reflections(
        query=content[:100],  # First 100 chars
        project="property-test",
    )
    assert search_results["count"] >= 0
```

### Performance Testing with Regression Detection

```python
from tests.fixtures.mcp_fixtures import AdvancedPerformanceTracker, PerformanceMetric
from datetime import datetime


@pytest.mark.performance
@pytest.mark.asyncio
async def test_with_performance_tracking():
    """Example of performance testing with baseline comparison"""
    tracker = AdvancedPerformanceTracker()
    tracker.start()

    # Your performance-sensitive operation
    start_time = time.perf_counter()
    await some_expensive_operation()
    operation_time = time.perf_counter() - start_time

    # Record structured performance metric
    tracker.record_metric(
        PerformanceMetric(
            name="expensive_operation_time",
            value=operation_time,
            unit="seconds",
            timestamp=datetime.now().isoformat(),
            context={"test_name": "performance_test", "operation_type": "database"},
            threshold=1.0,  # 1 second threshold
        )
    )

    metrics = tracker.stop()
    analysis = tracker.analyze_regressions()

    # Assert no performance regressions
    assert analysis["summary"]["overall_status"] == "PASS"
    assert len(analysis["threshold_violations"]) == 0
```

### Security Testing Patterns

```python
@pytest.mark.security
@pytest.mark.parametrize(
    "malicious_input",
    [
        "'; DROP TABLE reflections; --",
        "<script>alert('xss')</script>",
        "../../etc/passwd",
        "\x00\x01\x02\x03",  # Binary injection
        "A" * 10000,  # Buffer overflow attempt
    ],
)
@pytest.mark.asyncio
async def test_input_sanitization(malicious_input, isolated_database):
    """Test system handles malicious input safely"""
    db = isolated_database

    # Should not crash or cause security issues
    try:
        result = await db.store_reflection(
            content=malicious_input, tags=["security-test"], project="security"
        )

        # If it succeeds, data should be properly escaped
        if isinstance(result, str):
            # Verify no SQL injection occurred
            stats = await db.get_stats()
            assert stats["total_reflections"] >= 1

    except (ValueError, TypeError) as e:
        # Acceptable to reject invalid input
        assert "invalid" in str(e).lower() or "malicious" in str(e).lower()
```

### Integration Testing with Workflow Validation

```python
@pytest.mark.integration
@pytest.mark.asyncio
class TestSessionWorkflowIntegration:
    """Test complete session management workflows"""

    async def test_complete_session_lifecycle(
        self, temporary_project_structure, mock_session_permissions
    ):
        """Test end-to-end session lifecycle"""
        from session_mgmt_mcp.server import init, checkpoint, end, status

        working_dir = str(temporary_project_structure)

        # Phase 1: Initialize session
        init_result = await init(working_directory=working_dir)
        assert init_result["success"] is True
        session_id = init_result["session_id"]

        # Phase 2: Verify session is active
        status_result = await status(working_directory=working_dir)
        assert status_result["session"]["session_id"] == session_id
        assert status_result["session"]["active"] is True

        # Phase 3: Create checkpoint
        checkpoint_result = await checkpoint()
        assert checkpoint_result["success"] is True
        assert "checkpoint_id" in checkpoint_result

        # Phase 4: End session
        end_result = await end()
        assert end_result["success"] is True
        assert end_result["cleanup"]["completed"] is True
```

## Test Execution Recommendations

### Development Workflow

1. **Before committing**: `python run_tests.py --quick`
1. **Before push**: `python run_tests.py --unit --integration`
1. **Weekly**: `python run_tests.py --performance` (check for regressions)
1. **Before release**: `python run_tests.py --parallel --fail-on-coverage`

### Debugging Failed Tests

1. **Run with verbose output**: `--verbose`
1. **Preserve test artifacts**: `--no-cleanup`
1. **Isolate the problem**: Run specific test categories
1. **Check coverage gaps**: `--coverage-only` to see uncovered code

### Performance Optimization

1. **Use parallel execution**: `--parallel` for faster feedback
1. **Skip coverage in dev**: `--no-coverage` for speed
1. **Set realistic timeouts**: `--timeout` based on your hardware
1. **Profile slow tests**: Add performance tracking to identify bottlenecks

## Quality Assurance Standards

### Coverage Requirements

- **Minimum**: 85% line coverage (enforced)
- **Target**: 90% line coverage for critical components
- **Branch coverage**: Monitor but don't enforce (aim for 80%)
- **Exclude patterns**: Test files, debug code, platform-specific code

### Performance Benchmarks

- **Database operations**: < 100ms average, < 500ms P95
- **MCP tool execution**: < 200ms average, < 1s P95
- **Memory growth**: < 50MB per 1000 operations
- **Concurrent access**: Support 50+ simultaneous operations

### Security Standards

- **All inputs validated**: No raw user input reaches database
- **SQL injection prevention**: Parameterized queries only
- **Rate limiting**: Prevent abuse through excessive requests
- **Permission boundaries**: Enforce access controls consistently
