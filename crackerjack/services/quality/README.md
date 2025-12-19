> Crackerjack Docs: [Main](../../../README.md) | [CLAUDE.md](../../../docs/guides/CLAUDE.md) | [Services](../README.md) | Quality Services

# Quality Services

Quality baseline management, pattern detection, and anomaly detection services.

## Overview

The quality services package provides intelligent quality monitoring, baseline tracking, and pattern detection capabilities. These services power crackerjack's coverage ratchet system, detect code quality degradation, and orchestrate quality checks across multiple tools.

## Services

- **`quality_baseline_enhanced.py`** - Quality baseline tracking and trend analysis
- **`pattern_detector.py`** - Code and error pattern detection
- **`pattern_cache.py`** - Pattern caching for improved performance
- **`anomaly_detector.py`** - Quality anomaly detection and alerting
- **`qa_orchestrator.py`** - Quality assurance workflow orchestration

## Features

### Baseline Tracking

Monitor quality metrics over time with ratchet enforcement:

- **Coverage Tracking** - Track test coverage with never-decrease policy
- **Metric History** - Historical trend analysis for all quality metrics
- **Baseline Enforcement** - Prevent quality degradation
- **Automatic Updates** - Auto-update baselines on improvement
- **Trend Visualization** - Visual trend reporting

### Pattern Recognition

Detect code smells and anti-patterns:

- **Code Pattern Detection** - Identifies common anti-patterns
- **Error Pattern Analysis** - Categorizes and learns from errors
- **Duplicate Detection** - Finds code duplication
- **Complexity Patterns** - Identifies high-complexity patterns
- **Security Patterns** - Detects security anti-patterns

### Anomaly Detection

Identify unusual quality degradation:

- **Statistical Analysis** - Detects outliers in quality metrics
- **Threshold Monitoring** - Alerts on threshold violations
- **Trend Analysis** - Identifies negative trends early
- **Alerting** - Configurable alert mechanisms
- **Root Cause Analysis** - Helps identify degradation causes

### Performance Caching

Improve performance with intelligent pattern caching:

- **Pattern Cache** - Caches detected patterns for reuse
- **TTL Management** - Time-to-live based cache invalidation
- **Hit Rate Tracking** - Monitors cache effectiveness
- **Selective Caching** - Caches only high-value patterns
- **Memory Efficient** - LRU eviction for large projects

### QA Orchestration

Coordinate quality checks across tools:

- **Multi-Tool Coordination** - Orchestrates Ruff, pytest, mypy, etc.
- **Parallel Execution** - Runs compatible checks in parallel
- **Dependency Management** - Respects tool dependencies
- **Result Aggregation** - Combines results from all tools
- **Retry Logic** - Smart retry for transient failures

## Usage Examples

### Quality Baseline Tracking

```python
from crackerjack.services.quality import QualityBaselineEnhanced
from acb.depends import depends

baseline = depends.get(QualityBaselineEnhanced)

# Record current metrics
await baseline.record_metrics(
    {"coverage": 21.6, "complexity": 8.2, "lint_issues": 0, "security_issues": 0}
)

# Check if current metrics meet baseline
results = await baseline.validate_metrics(
    {
        "coverage": 22.1,  # Improved!
        "complexity": 8.2,
        "lint_issues": 0,
        "security_issues": 0,
    }
)

if results.all_passed:
    print("✅ All quality metrics improved or maintained")
    # Update baseline with new improved values
    await baseline.update_baseline()
else:
    print("❌ Quality regression detected:")
    for metric, result in results.items():
        if not result.passed:
            print(f"  {metric}: {result.current} < {result.baseline}")
```

### Pattern Detection

```python
from crackerjack.services.quality import PatternDetector
from pathlib import Path
from acb.depends import depends

detector = depends.get(PatternDetector)

# Detect patterns in code file
patterns = await detector.detect_patterns(
    file_path=Path("src/main.py"),
    pattern_types=["complexity", "duplication", "security"],
)

for pattern in patterns:
    print(f"Pattern: {pattern.type}")
    print(f"  Location: {pattern.file}:{pattern.line}")
    print(f"  Severity: {pattern.severity}")
    print(f"  Message: {pattern.message}")
    if pattern.suggestion:
        print(f"  Suggestion: {pattern.suggestion}")

# Detect error patterns from test output
error_patterns = await detector.detect_error_patterns(error_output=test_failure_output)

for error in error_patterns:
    print(f"Error Category: {error.category}")
    print(f"  Pattern: {error.pattern}")
    print(f"  Occurrences: {error.count}")
    print(f"  Files: {', '.join(error.files)}")
```

### Anomaly Detection

```python
from crackerjack.services.quality import AnomalyDetector
from acb.depends import depends

detector = depends.get(AnomalyDetector)

# Configure thresholds
detector.configure_thresholds(
    {
        "coverage": {"min": 19.6, "warning": 20.0},
        "complexity": {"max": 15, "warning": 12},
        "test_duration": {"max": 300, "warning": 240},
    }
)

# Check for anomalies
anomalies = await detector.detect_anomalies(
    {
        "coverage": 18.5,  # Below minimum!
        "complexity": 14,
        "test_duration": 285,
    }
)

if anomalies:
    print("⚠️  Anomalies detected:")
    for anomaly in anomalies:
        print(f"  {anomaly.metric}: {anomaly.value}")
        print(f"    Severity: {anomaly.severity}")
        print(f"    Threshold: {anomaly.threshold}")
        print(f"    Recommendation: {anomaly.recommendation}")
```

### Pattern Caching

```python
from crackerjack.services.quality import PatternCache
from acb.depends import depends

cache = depends.get(PatternCache)

# Cache detected patterns
cache_key = "src/main.py:complexity"
patterns = await detect_complexity_patterns("src/main.py")
await cache.set(cache_key, patterns, ttl=3600)

# Retrieve cached patterns
cached_patterns = await cache.get(cache_key)
if cached_patterns:
    print(f"✅ Cache hit! Found {len(cached_patterns)} patterns")
else:
    print("❌ Cache miss - analyzing file...")
    patterns = await detect_complexity_patterns("src/main.py")

# Monitor cache performance
stats = await cache.get_stats()
print(f"Cache hit rate: {stats.hit_rate:.1%}")
print(f"Total hits: {stats.hits}")
print(f"Total misses: {stats.misses}")
print(f"Cache size: {stats.size} entries")
```

### QA Orchestration

```python
from crackerjack.services.quality import QAOrchestrator
from acb.depends import depends

orchestrator = depends.get(QAOrchestrator)

# Configure quality checks
orchestrator.configure(
    {
        "tools": ["ruff", "pytest", "mypy", "bandit"],
        "parallel": True,
        "fail_fast": False,  # Run all checks even if one fails
        "retry_attempts": 1,
    }
)

# Run orchestrated quality checks
results = await orchestrator.run_qa_workflow()

print(f"Overall Status: {results.status}")
print(f"Duration: {results.duration:.1f}s")
print(f"Tools Run: {len(results.tool_results)}")

for tool_result in results.tool_results:
    status_icon = "✅" if tool_result.passed else "❌"
    print(f"{status_icon} {tool_result.tool}: {tool_result.message}")
    if not tool_result.passed and tool_result.details:
        print(f"    Details: {tool_result.details}")
```

## Configuration

Quality services are configured through ACB Settings:

```yaml
# settings/crackerjack.yaml

# Baseline tracking
quality_baseline_file: ".crackerjack/quality_baseline.json"
coverage_ratchet_enabled: true
coverage_baseline: 19.6

# Pattern detection
pattern_detection_enabled: true
pattern_cache_ttl: 3600
pattern_types:
  - complexity
  - duplication
  - security
  - performance

# Anomaly detection
anomaly_detection_enabled: true
anomaly_thresholds:
  coverage_drop_threshold: 0.5  # Alert if coverage drops >0.5%
  complexity_increase_threshold: 2  # Alert if avg complexity increases >2
  test_duration_increase: 1.2  # Alert if tests take 20% longer

# QA orchestration
parallel_qa_checks: true
max_parallel_tools: 4
qa_retry_attempts: 1
qa_timeout_seconds: 600
```

### Local Configuration Overrides

```yaml
# settings/local.yaml (gitignored)
quality_baseline_file: ".crackerjack/quality_baseline_dev.json"
anomaly_detection_enabled: false  # Disable for local development
parallel_qa_checks: true
max_parallel_tools: 8  # More parallel tools on dev machine
```

## Integration Examples

### Coverage Ratchet Integration

```python
from crackerjack.services.quality import QualityBaselineEnhanced
from crackerjack.services.coverage_ratchet import CoverageRatchet
from acb.depends import depends

baseline = depends.get(QualityBaselineEnhanced)
ratchet = depends.get(CoverageRatchet)

# After test run
current_coverage = await get_current_coverage()
baseline_coverage = await baseline.get_baseline("coverage")

if ratchet.validate_coverage(current_coverage, baseline_coverage):
    print(f"✅ Coverage {current_coverage:.1%} meets baseline {baseline_coverage:.1%}")
    await baseline.update_baseline({"coverage": current_coverage})
else:
    print(f"❌ Coverage {current_coverage:.1%} below baseline {baseline_coverage:.1%}")
    raise CoverageRegressionError(
        f"Coverage dropped from {baseline_coverage:.1%} to {current_coverage:.1%}"
    )
```

### AI Agent Integration

```python
from crackerjack.services.quality import PatternDetector
from crackerjack.intelligence import AgentOrchestrator
from acb.depends import depends

detector = depends.get(PatternDetector)
orchestrator = depends.get(AgentOrchestrator)

# Detect patterns
patterns = await detector.detect_patterns("src/complex_module.py")

# Feed patterns to appropriate agents
for pattern in patterns:
    if pattern.type == "complexity":
        # Route to RefactoringAgent
        await orchestrator.execute_agent(
            agent_type="refactoring", context={"patterns": [pattern]}
        )
    elif pattern.type == "security":
        # Route to SecurityAgent
        await orchestrator.execute_agent(
            agent_type="security", context={"patterns": [pattern]}
        )
```

### Workflow Integration

```python
from crackerjack.services.quality import QAOrchestrator
from crackerjack.workflows import CrackerjackWorkflowEngine
from acb.depends import depends

orchestrator = depends.get(QAOrchestrator)
engine = depends.get(CrackerjackWorkflowEngine)


# Register QA orchestrator as workflow action
@engine.register_action("run_quality_checks")
async def run_quality_checks(context):
    results = await orchestrator.run_qa_workflow()
    return {"success": results.status == "passed", "results": results.tool_results}


# Quality checks now integrated into workflows
workflow_result = await engine.execute_workflow("STANDARD_WORKFLOW")
```

## Best Practices

1. **Enable Ratcheting** - Always use coverage ratchet to prevent degradation
1. **Cache Aggressively** - Enable pattern caching for large projects
1. **Set Appropriate Baselines** - Start with achievable baselines, improve incrementally
1. **Monitor Trends** - Review quality trends regularly, not just current values
1. **Configure Thresholds** - Set anomaly thresholds based on project needs
1. **Use Orchestration** - Leverage QA orchestrator for consistent quality checks
1. **Parallel When Possible** - Enable parallel execution to speed up checks
1. **Review Patterns** - Regularly review detected patterns for false positives
1. **Integrate with CI/CD** - Run quality checks in CI/CD pipeline
1. **Document Baselines** - Keep quality baseline changes in version control

## Performance Considerations

### Caching Strategy

- **Pattern Cache**: Cache pattern detection results (default TTL: 1 hour)
- **Baseline Cache**: Cache baseline data in memory (refresh on update)
- **Result Cache**: Cache tool execution results for unchanged files

### Parallel Execution

Quality checks run in parallel when possible:

```python
# These can run in parallel (no dependencies)
parallel_tools = ["ruff", "bandit", "complexity_check"]

# These must run sequentially
sequential_tools = ["tests", "coverage_report"]
```

### Memory Optimization

For large projects:

```yaml
# settings/crackerjack.yaml
pattern_cache_max_size: 1000  # Limit cache size
pattern_cache_eviction: "lru"  # Use LRU eviction
quality_history_max_entries: 100  # Limit history size
```

## Related

- [Services](../README.md) - Parent services documentation
- [AI Services](../ai/README.md) - AI-powered quality analysis
- [Workflows](../../workflows/README.md) - Quality workflow integration
- [COVERAGE_POLICY.md](../../../docs/reference/COVERAGE_POLICY.md) - Coverage ratchet policy
- [CLAUDE.md](../../../docs/guides/CLAUDE.md) - AI agent integration

## Future Enhancements

- [ ] Machine learning for pattern detection improvement
- [ ] Predictive quality degradation alerts
- [ ] Custom pattern definition language
- [ ] Integration with more static analysis tools
- [ ] Quality dashboard with real-time metrics
- [ ] Automated baseline recommendations
