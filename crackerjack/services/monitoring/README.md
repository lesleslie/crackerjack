# Monitoring Services

System health, performance metrics, and error pattern analysis services.

## Services

- **`health_metrics.py`** - System health monitoring and metric collection
- **`metrics.py`** - Performance metrics aggregation and reporting
- **`dependency_monitor.py`** - Dependency health tracking and version monitoring
- **`error_pattern_analyzer.py`** - Error pattern detection and analysis
- **`performance_benchmarks.py`** - Performance baseline tracking and regression detection

## Features

- **Health Checks** - Real-time system health status
- **Performance Tracking** - Benchmark execution times and resource usage
- **Error Analysis** - Pattern detection in test failures and build errors
- **Dependency Monitoring** - Track outdated or vulnerable dependencies
- **Metric Aggregation** - Collect and report quality metrics

## Integration

These services are used throughout Crackerjack for:

- MCP server health endpoints
- Test execution monitoring
- Quality trend analysis
- Performance regression detection

See parent `services/README.md` for service architecture details.
