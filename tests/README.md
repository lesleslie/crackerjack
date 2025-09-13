# Session-mgmt-mcp Test Infrastructure

This directory contains a comprehensive, modern async pytest testing infrastructure for the session-mgmt-mcp project.

## Architecture

### Core Files

- **`conftest.py`**: Global test configuration with async fixtures and session management
- **`pytest.ini`**: Pytest configuration with async support, coverage, and comprehensive markers
- **`helpers.py`**: Shared test utilities, data factories, and helper classes

### Test Organization

```
tests/
├── conftest.py              # Global fixtures and configuration
├── pytest.ini              # Pytest configuration
├── helpers.py               # Shared utilities and factories
├── functional/              # Complete workflow tests
├── unit/                    # Individual component tests
└── integration/             # Cross-component tests
```

## Key Features

### 1. Modern Async Support

- **pytest-asyncio** integration with proper event loop management
- Session-scoped event loop for consistency across tests
- Automatic async task leak detection
- Context manager support for async resources

### 2. Comprehensive Fixtures

#### Database Fixtures

```python
@pytest.fixture
async def reflection_db(temp_db_path: str) -> AsyncGenerator[ReflectionDatabase, None]:
    """Provide initialized ReflectionDatabase instance."""


@pytest.fixture
async def reflection_db_with_data(
    reflection_db: ReflectionDatabase,
) -> AsyncGenerator[ReflectionDatabase, None]:
    """Provide ReflectionDatabase with test data."""
```

#### Environment Fixtures

```python
@pytest.fixture
def clean_environment() -> Generator[dict[str, Any], None, None]:
    """Provide clean environment with common patches."""


@pytest.fixture
async def temp_claude_dir() -> AsyncGenerator[Path, None]:
    """Provide temporary ~/.claude directory structure."""
```

#### Mocking Fixtures

```python
@pytest.fixture
def mock_onnx_session() -> Mock:
    """Provide mock ONNX session for embedding tests."""


@pytest.fixture
def mock_embeddings_disabled():
    """Fixture to disable embeddings for testing fallback behavior."""
```

### 3. Test Helper Classes

#### TestDataFactory

Generate realistic test data:

```python
# Individual conversation
conversation = TestDataFactory.conversation("Test content", "project-name")

# Bulk conversations
conversations = TestDataFactory.bulk_conversations(50, "bulk-project")

# Reflections with tags
reflection = TestDataFactory.reflection("Important insight", ["tag1", "tag2"])
```

#### DatabaseTestHelper

Database testing utilities:

```python
# Temporary database
async with DatabaseTestHelper.temp_reflection_db() as db:
    # Use database for testing

# Populate with test data
data_ids = await DatabaseTestHelper.populate_test_data(db, 10, 5)

# Performance measurement
perf_data = await DatabaseTestHelper.measure_query_performance(db, search_func, "query")
```

#### MockingHelper

Comprehensive mocking utilities:

```python
# Mock embedding system
mocks = MockingHelper.mock_embedding_system()

# Mock MCP server
async with MockingHelper.mock_mcp_server() as server:
    # Use mocked server

# Environment patching
with MockingHelper.patch_environment(TEST_VAR="value"):
    # Test with environment variables
```

#### AssertionHelper

Specialized assertions:

```python
# UUID validation
AssertionHelper.assert_valid_uuid(conversation_id)

# Timestamp validation
AssertionHelper.assert_valid_timestamp(iso_timestamp)

# Embedding validation
AssertionHelper.assert_embedding_shape(embedding_vector)

# Similarity score validation
AssertionHelper.assert_similarity_score(0.85)

# Database record validation
AssertionHelper.assert_database_record(record, ["id", "content", "project"])
```

#### PerformanceHelper

Performance testing utilities:

```python
# Time measurement
async with PerformanceHelper.measure_time() as measurements:
    await expensive_operation()

# Performance thresholds
PerformanceHelper.assert_performance_threshold(
    actual_time,
    1.0,  # 1 second threshold
    "operation description",
)

# Benchmarking
benchmark_results = await PerformanceHelper.benchmark_async_operation(
    operation, iterations=100
)
```

### 4. Test Categories and Markers

#### Test Categories

- **`unit`**: Fast, isolated component tests
- **`integration`**: Cross-component interaction tests
- **`functional`**: Complete workflow tests
- **`performance`**: Performance and benchmark tests
- **`security`**: Security and validation tests

#### Specialized Markers

- **`async_test`**: Requires async event loop
- **`database`**: Requires database operations
- **`embedding`**: Requires embedding/vector operations
- **`mcp`**: Tests MCP server functionality
- **`slow`**: Long-running tests (use `-m "not slow"` to skip)

### 5. Running Tests

#### Basic Commands

```bash
# All tests with coverage
python -m pytest

# Specific test categories
python -m pytest -m unit          # Unit tests only
python -m pytest -m integration   # Integration tests only
python -m pytest -m "not slow"    # Skip slow tests

# Specific test files
python -m pytest tests/functional/test_simple_validation.py -v

# Async tests only
python -m pytest -k "async" -v
```

#### Advanced Usage

```bash
# Parallel execution
python -m pytest -n auto

# With performance benchmarking
python -m pytest --benchmark-only

# Coverage with branch analysis
python -m pytest --cov-branch --cov-report=html

# Timeout for long-running tests
python -m pytest --timeout=300
```

## Example Usage

### Unit Test Example

```python
class TestExampleUnit:
    def test_data_generation(self):
        """Example unit test with test data factory."""
        conversation = TestDataFactory.conversation("Test content", "test-project")

        AssertionHelper.assert_valid_uuid(conversation["id"])
        assert conversation["content"] == "Test content"
        assert conversation["project"] == "test-project"

    def test_with_mocking(self):
        """Example unit test with mocking."""
        mocks = MockingHelper.mock_embedding_system()

        # Use mocked embedding system
        assert mocks["onnx_session"] is not None
        assert mocks["tokenizer"] is not None
```

### Integration Test Example

```python
class TestExampleIntegration:
    @pytest.mark.integration
    @pytest.mark.asyncio
    async def test_database_workflow(self):
        """Example integration test."""
        async with DatabaseTestHelper.temp_reflection_db() as db:
            # Store conversation
            conv_id = await db.store_conversation(
                "Integration test conversation", {"project": "integration-test"}
            )

            # Validate stored data
            AssertionHelper.assert_valid_uuid(conv_id)

            # Verify retrieval
            results = db.conn.execute(
                "SELECT content FROM conversations WHERE id = ?", [conv_id]
            ).fetchall()

            assert len(results) == 1
            assert results[0][0] == "Integration test conversation"
```

### Performance Test Example

```python
class TestPerformance:
    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_bulk_operations(self, perf_helper):
        """Example performance test."""
        async with DatabaseTestHelper.temp_reflection_db() as db:
            # Measure performance
            async with perf_helper.measure_time() as measurements:
                for i in range(100):
                    await db.store_conversation(f"Perf test {i}", {"project": "perf"})

            # Assert performance threshold
            perf_helper.assert_performance_threshold(
                measurements["duration"],
                5.0,  # 5 seconds max for 100 operations
                "bulk conversation storage",
            )
```

## Configuration

### pytest.ini Features

- Async mode enabled (`asyncio_mode = auto`)
- Comprehensive test markers defined
- Coverage reporting with branch analysis
- Warning filters for common libraries
- Timeout protection (300s default)
- Test discovery patterns

### Environment Variables

- `TESTING=1`: Automatically set during test execution
- `LOG_LEVEL=DEBUG`: Verbose logging for debugging
- Custom variables via `clean_environment` fixture

## Best Practices

### 1. Test Organization

- Use appropriate test categories (`unit`, `integration`, `functional`)
- Add descriptive markers for filtering
- Keep tests focused and independent

### 2. Async Testing

- Always use `@pytest.mark.asyncio` for async tests
- Use proper async fixtures and context managers
- Test both happy path and error conditions

### 3. Database Testing

- Use temporary databases for isolation
- Clean up resources in finally blocks
- Test concurrent access patterns

### 4. Performance Testing

- Set realistic performance thresholds
- Measure actual operations, not just time
- Test with realistic data volumes

### 5. Mocking Strategy

- Mock external dependencies (ONNX, file system)
- Use helper utilities for consistent mocking
- Test both with mocks and real components when possible

## Validation

The test infrastructure is validated through comprehensive tests in:

- `tests/functional/test_simple_validation.py`: Infrastructure validation
- `tests/unit/test_example_unit.py`: Unit test examples
- `tests/integration/test_example_integration.py`: Integration test examples

All tests pass and demonstrate the infrastructure works correctly for:
✅ Async database operations
✅ Test data generation
✅ Mocking and patching
✅ Assertion helpers
✅ Performance measurement
✅ Environment management
✅ Concurrent testing

## Advanced Testing Patterns

### Property-Based Testing with Hypothesis

```python
from hypothesis import given, strategies as st, settings

@given(
    content=st.text(min_size=1, max_size=10000),
    tags=st.lists(st.text(min_size=1, max_size=50), max_size=10),
)
@settings(max_examples=50)
@pytest.mark.asyncio
async def test_reflection_storage_properties(content, tags, reflection_db):
    """Property-based test ensuring reflection storage is robust"""
    # Property: All valid content should store successfully
    result = await reflection_db.store_reflection(
        content=content, tags=tags, project="property-test"
    )
    
    assert isinstance(result, str)
    assert len(result) > 0
```

### Performance Regression Detection

```python
@pytest.mark.performance
@pytest.mark.asyncio
async def test_with_performance_tracking():
    """Performance testing with baseline comparison"""
    tracker = AdvancedPerformanceTracker()
    tracker.start()
    
    # Performance-sensitive operation
    start_time = time.perf_counter()
    await some_expensive_operation()
    operation_time = time.perf_counter() - start_time
    
    # Record structured performance metric
    tracker.record_metric(
        PerformanceMetric(
            name="expensive_operation_time",
            value=operation_time,
            unit="seconds",
            threshold=1.0,  # 1 second threshold
        )
    )
    
    metrics = tracker.stop()
    analysis = tracker.analyze_regressions()
    
    # Assert no performance regressions
    assert analysis["summary"]["overall_status"] == "PASS"
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
async def test_input_sanitization(malicious_input, reflection_db):
    """Test system handles malicious input safely"""
    try:
        result = await reflection_db.store_reflection(
            content=malicious_input, tags=["security-test"]
        )
        
        # If it succeeds, verify no SQL injection occurred
        if isinstance(result, str):
            stats = await reflection_db.get_stats()
            assert stats["total_reflections"] >= 1
            
    except (ValueError, TypeError) as e:
        # Acceptable to reject invalid input
        assert "invalid" in str(e).lower()
```

### Integration Workflow Testing

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_complete_session_lifecycle(tmp_path):
    """Test end-to-end session workflow"""
    from session_mgmt_mcp.server import init, checkpoint, end, status
    
    working_dir = str(tmp_path)
    
    # Phase 1: Initialize session
    init_result = await init(working_directory=working_dir)
    assert init_result["success"] is True
    session_id = init_result["session_id"]
    
    # Phase 2: Verify session is active
    status_result = await status(working_directory=working_dir)
    assert status_result["session"]["session_id"] == session_id
    
    # Phase 3: Create checkpoint  
    checkpoint_result = await checkpoint()
    assert checkpoint_result["success"] is True
    
    # Phase 4: End session
    end_result = await end()
    assert end_result["success"] is True
```

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

## Future Enhancements

Potential additions to consider:

- Mutation testing integration
- Chaos engineering tests
- Custom pytest plugins for MCP testing
- Test parallelization optimization
