# Crackerjack Integration Details

This document provides comprehensive technical details about session-mgmt-mcp's deep integration with Crackerjack, the AI-driven Python development platform.

## Integration Architecture

Session-mgmt-mcp includes a comprehensive `crackerjack_integration.py` module (50KB+) that provides sophisticated integration capabilities, making it the most advanced MCP server for Python development workflows.

### Core Integration Module

The `session_mgmt_mcp/crackerjack_integration.py` module provides:

- **Command Execution Framework**: Direct Crackerjack command execution with result capture
- **Progress Monitoring System**: Real-time tracking during Crackerjack operations
- **Quality Metrics Intelligence**: Advanced quality metric extraction and trend analysis
- **Test Pattern Recognition**: Test result monitoring and pattern detection
- **Error Resolution Learning**: Building knowledge base of project-specific fix patterns
- **Build Status Tracking**: Comprehensive build and deployment monitoring

## Available Crackerjack Commands

The integration supports the full range of Crackerjack operations through the `CrackerjackCommand` enum:

### Core Quality Commands

```python
CrackerjackCommand.ANALYZE  # Comprehensive analysis command
CrackerjackCommand.CHECK  # Basic quality checks
CrackerjackCommand.TEST  # Test execution with reporting
CrackerjackCommand.LINT  # Linting and style checks
CrackerjackCommand.FORMAT  # Code formatting operations
CrackerjackCommand.TYPECHECK  # Type checking support
```

### Security and Complexity Analysis

```python
CrackerjackCommand.SECURITY  # Security vulnerability scanning
CrackerjackCommand.COMPLEXITY  # Cognitive complexity analysis
CrackerjackCommand.COVERAGE  # Test coverage reporting
```

### Build and Maintenance

```python
CrackerjackCommand.BUILD  # Build operations
CrackerjackCommand.CLEAN  # Cleanup operations
CrackerjackCommand.DOCS  # Documentation generation
```

### Release Management

```python
CrackerjackCommand.RELEASE  # Release workflow management
```

## Quality Metrics Tracked

The integration captures and analyzes comprehensive quality metrics:

### Primary Metrics

```python
QualityMetric.CODE_COVERAGE  # Test coverage percentage
QualityMetric.COMPLEXITY  # Cognitive complexity scores
QualityMetric.LINT_SCORE  # Code style and quality scores
QualityMetric.SECURITY_SCORE  # Security assessment scores
QualityMetric.TEST_PASS_RATE  # Test success rate
QualityMetric.BUILD_STATUS  # Build success/failure status
```

### Derived Intelligence

- **Quality Trends**: Track improvement or degradation over time
- **Pattern Recognition**: Identify recurring issues and successful fixes
- **Predictive Analysis**: Estimate completion times based on historical data
- **Workflow Optimization**: Suggest most effective command sequences

## Test Status Management

Comprehensive test result tracking with detailed status classification:

### Test Status Types

```python
TestStatus.PASSED  # Test executed successfully
TestStatus.FAILED  # Test failed with assertion or logic errors
TestStatus.SKIPPED  # Test was skipped (conditional or marked)
TestStatus.ERROR  # Test had execution errors (setup, teardown, etc.)
TestStatus.XFAIL  # Expected failure (known issues)
TestStatus.XPASS  # Unexpected pass (previously failing test now passes)
```

### Test Result Analysis

```python
@dataclass
class TestResult:
    test_id: str  # Unique test identifier
    test_name: str  # Human-readable test name
    status: TestStatus  # Test execution status
    duration: float  # Test execution time in seconds
    file_path: str  # Path to test file
    error_message: str  # Error details (if applicable)
    stack_trace: str  # Full stack trace (if applicable)
```

## Command Execution Results

Each Crackerjack command execution produces comprehensive results:

```python
@dataclass
class CrackerjackResult:
    command: str  # Command that was executed
    exit_code: int  # Process exit code
    stdout: str  # Standard output
    stderr: str  # Standard error
    execution_time: float  # Total execution time
    timestamp: datetime  # When execution completed
    working_directory: str  # Directory where command ran
    parsed_data: dict[str, Any] | None  # Structured data extraction
    quality_metrics: dict[str, float]  # Quality scores and metrics
    test_results: list[dict[str, Any]]  # Individual test results
    memory_insights: list[str]  # Insights for future sessions
```

## API Reference

### Primary Execution Functions

#### execute_crackerjack_command()

Execute a Crackerjack command with comprehensive result capture:

```python
async def execute_crackerjack_command(
    command: str,
    *,
    test: bool = False,
    ai_agent: bool = False,
    interactive: bool = False,
    verbose: bool = False,
    working_directory: str | None = None,
    timeout: int = 300,
    capture_progress: bool = True,
) -> CrackerjackResult:
    """
    Execute Crackerjack command with full result capture.

    Args:
        command: Crackerjack command to execute
        test: Include test execution
        ai_agent: Enable AI agent auto-fixing
        interactive: Enable interactive mode
        verbose: Enable verbose output
        working_directory: Directory to execute command in
        timeout: Command timeout in seconds
        capture_progress: Enable real-time progress capture

    Returns:
        Comprehensive execution result with metrics
    """
```

#### get_crackerjack_quality_metrics()

Retrieve quality metrics with trend analysis:

```python
async def get_crackerjack_quality_metrics(
    *,
    days: int = 30,
    working_directory: str | None = None,
    include_trends: bool = True,
    metric_types: list[QualityMetric] | None = None,
) -> dict[str, Any]:
    """
    Retrieve quality metrics with trend analysis.

    Args:
        days: Number of days to analyze
        working_directory: Project directory
        include_trends: Include trend calculations
        metric_types: Specific metrics to retrieve

    Returns:
        Quality metrics with trends and analysis
    """
```

#### analyze_crackerjack_test_patterns()

Analyze test execution patterns for optimization:

```python
async def analyze_crackerjack_test_patterns(
    *,
    days: int = 7,
    working_directory: str | None = None,
    include_failures: bool = True,
    pattern_types: list[str] | None = None,
) -> dict[str, Any]:
    """
    Analyze test patterns for workflow optimization.

    Args:
        days: Analysis period in days
        working_directory: Project directory
        include_failures: Include failure pattern analysis
        pattern_types: Specific pattern types to analyze

    Returns:
        Test patterns and optimization suggestions
    """
```

## Usage Examples

### Basic Command Execution

Execute Crackerjack commands with automatic result capture:

```python
# Run comprehensive quality analysis
result = await execute_crackerjack_command(
    "analyze", test=True, ai_agent=True, working_directory="/path/to/project"
)

print(f"Quality Score: {result.quality_metrics.get('overall_score', 0)}")
print(f"Test Pass Rate: {result.quality_metrics.get('test_pass_rate', 0)}")
print(f"Execution Time: {result.execution_time:.2f}s")
```

### Quality Trend Analysis

Track quality metrics over time:

```python
# Get 30-day quality trend
metrics = await get_crackerjack_quality_metrics(
    days=30, working_directory="/path/to/project", include_trends=True
)

# Analyze trends
coverage_trend = metrics["trends"]["coverage"]
if coverage_trend["direction"] == "improving":
    print(f"Coverage improving by {coverage_trend['rate']:.1f}% per week")
else:
    print(f"Coverage declining by {coverage_trend['rate']:.1f}% per week")
```

### Test Pattern Recognition

Identify test patterns for optimization:

```python
# Analyze test patterns
patterns = await analyze_crackerjack_test_patterns(
    days=7, working_directory="/path/to/project", include_failures=True
)

# Show failure patterns
for pattern in patterns["failure_patterns"]:
    print(f"Frequent failure: {pattern['error_type']}")
    print(f"Success rate: {pattern['success_rate']:.1f}%")
    print(f"Suggested fix: {pattern['suggested_fix']}")
```

### Integrated Session Workflow

Complete workflow with session memory integration:

```python
async def integrated_development_session():
    """Example integrated development session."""

    # 1. Initialize session with historical context
    await init_session_with_crackerjack_context()

    # 2. Run quality analysis
    result = await execute_crackerjack_command("analyze", test=True, ai_agent=True)

    # 3. Store results for future sessions
    await store_quality_metrics(result.quality_metrics)
    await store_test_results(result.test_results)

    # 4. Generate insights for future sessions
    insights = await generate_session_insights(result)
    await store_reflection(
        content=f"Quality session completed with score {result.quality_metrics.get('overall_score')}",
        tags=["quality", "crackerjack", "analysis"],
    )

    return result
```

## Advanced Features

### Predictive Analysis

The integration uses historical data to provide predictive insights:

```python
# Predict completion time for complex operations
prediction = await predict_crackerjack_completion_time(
    command="test", ai_agent=True, project_size_lines=15000, test_count=450
)

print(f"Estimated completion: {prediction['estimated_minutes']} minutes")
print(f"Confidence: {prediction['confidence']:.1f}%")
```

### Error Pattern Learning

Learn from successful error resolutions:

```python
# Record successful fix
await record_successful_fix(
    error_pattern="F401: imported but unused",
    fix_method="ai_agent_refactoring",
    success_rate=0.95,
    project_context="/path/to/project",
)

# Query historical fixes
fixes = await get_historical_fixes(
    error_pattern="complexity exceeds 15", confidence_threshold=0.8
)
```

### Workflow Optimization

Suggest optimal command sequences based on success patterns:

```python
# Get optimized workflow suggestions
suggestions = await get_workflow_suggestions(
    current_state="test_failures", project_type="python_package", quality_score=75
)

for suggestion in suggestions["recommended_sequence"]:
    print(f"Step {suggestion['order']}: {suggestion['command']}")
    print(f"Success rate: {suggestion['success_rate']:.1f}%")
    print(f"Expected improvement: +{suggestion['quality_improvement']:.1f}")
```

## Configuration Options

### Integration Settings

Configure integration behavior through environment variables or configuration files:

```python
# Environment variables
CRACKERJACK_INTEGRATION_ENABLED = "true"
CRACKERJACK_MAX_EXECUTION_TIME = "600"  # 10 minutes
CRACKERJACK_CAPTURE_PROGRESS = "true"
CRACKERJACK_STORE_METRICS = "true"
CRACKERJACK_AI_LEARNING = "true"

# Configuration file settings
integration_config = {
    "enabled": True,
    "max_execution_time": 600,
    "capture_progress": True,
    "store_metrics": True,
    "ai_learning": True,
    "quality_thresholds": {
        "coverage_minimum": 10.0,
        "complexity_maximum": 15,
        "security_score_minimum": 8.0,
    },
}
```

### Monitoring Configuration

```python
monitoring_config = {
    "track_trends": True,
    "trend_window_days": 30,
    "alert_on_degradation": True,
    "degradation_threshold": 0.1,  # 10% decrease
    "store_detailed_results": True,
    "compress_old_data": True,
    "retention_days": 90,
}
```

## Performance Considerations

### Resource Management

The integration is designed for efficiency:

- **Lazy Loading**: Quality data loaded only when needed
- **Compression**: Historical data compressed for storage efficiency
- **Caching**: Frequently accessed patterns cached in memory
- **Batch Processing**: Multiple operations batched when possible

### Scalability

Handles large projects effectively:

- **Streaming Results**: Large result sets streamed rather than loaded entirely
- **Parallel Processing**: Independent operations executed in parallel
- **Resource Limits**: Configurable limits prevent resource exhaustion
- **Progressive Loading**: Data loaded progressively as needed

### Memory Management

```python
# Memory optimization settings
memory_config = {
    "max_cached_results": 100,
    "compress_stored_data": True,
    "cleanup_interval_hours": 24,
    "max_memory_mb": 512,
}
```

## Troubleshooting

### Common Issues

#### Integration Not Working

```python
# Check integration status
status = await check_crackerjack_integration_status()
if not status["enabled"]:
    print("Integration disabled, enable in configuration")
if not status["crackerjack_available"]:
    print("Crackerjack not found, check installation")
```

#### Performance Issues

```python
# Monitor performance
perf_stats = await get_integration_performance_stats()
print(f"Average execution time: {perf_stats['avg_execution_time']:.2f}s")
print(f"Memory usage: {perf_stats['memory_mb']:.1f}MB")
print(f"Cache hit rate: {perf_stats['cache_hit_rate']:.1f}%")
```

#### Data Consistency Issues

```python
# Validate data consistency
validation = await validate_integration_data()
if validation["errors"]:
    print(f"Found {len(validation['errors'])} data consistency errors")
    for error in validation["errors"]:
        print(f"- {error['type']}: {error['message']}")
```

### Debug Mode

Enable detailed debugging:

```python
import logging

logging.getLogger("session_mgmt_mcp.crackerjack_integration").setLevel(logging.DEBUG)

# Execute with debug logging
result = await execute_crackerjack_command("test", verbose=True, capture_progress=True)
```

## Future Enhancements

### Planned Features

1. **Machine Learning**: Use ML models for better prediction accuracy
1. **Real-time Dashboards**: Live quality metric visualization
1. **Team Analytics**: Multi-developer pattern analysis
1. **Custom Metrics**: User-defined quality measurements
1. **Integration APIs**: REST APIs for external tool integration

### Extensibility

The integration is designed for extensibility:

```python
# Custom metric extractors
async def custom_metric_extractor(result: CrackerjackResult) -> dict[str, float]:
    """Extract custom metrics from Crackerjack results."""
    return {
        "custom_score": calculate_custom_score(result),
        "project_health": assess_project_health(result),
    }


# Register custom extractor
register_metric_extractor("custom", custom_metric_extractor)
```

This comprehensive integration makes session-mgmt-mcp the most powerful companion for Crackerjack-based Python development, providing intelligent memory, learning capabilities, and deep workflow optimization.
