# Agent Performance Tracking System

## Overview

The Agent Performance Tracking System provides comprehensive monitoring and analytics for AI agent execution metrics within Crackerjack. This system tracks agent effectiveness, timing, confidence levels, and model performance across different issue types.

## Architecture

### Core Components

#### 1. AgentAttempt (Dataclass)

Represents a single agent fix attempt with detailed metrics:

```python
@dataclass
class AgentAttempt:
    timestamp: str           # ISO format timestamp
    agent_name: str          # Agent identifier (e.g., "RefactoringAgent")
    model_name: str          # Model used (e.g., "claude-sonnet-4-5-20250929")
    issue_type: str          # Issue category (e.g., "complexity", "security")
    success: bool            # Whether the fix was successful
    confidence: float        # Agent's confidence score (0.0-1.0)
    time_seconds: float      # Execution time in seconds
```

#### 2. AgentMetrics (Dataclass)

Aggregates performance metrics for a specific agent/model/issue_type combination:

**Fields:**

- `total_attempts`: Total number of fix attempts
- `successful_fixes`: Number of successful fixes
- `failed_fixes`: Number of failed fixes
- `avg_confidence`: Running average of confidence scores
- `avg_time_seconds`: Running average of execution time
- `recent_results`: Last 100 attempts (FIFO buffer)

**Key Methods:**

- `add_attempt()`: Record a new attempt and update running averages
- `get_success_rate()`: Calculate success rate as percentage (0.0-100.0)
- `to_dict()`: Serialize to dictionary for JSON storage
- `from_dict()`: Deserialize from dictionary

#### 3. AgentPerformanceTracker

Thread-safe tracker with comprehensive analytics and persistence:

**Key Methods:**

##### Recording Attempts

```python
tracker.record_attempt(
    agent_name="RefactoringAgent",
    model_name="claude-sonnet-4-5-20250929",
    issue_type="complexity",
    success=True,
    confidence=0.85,
    time_seconds=2.3,
)
```

##### Querying Metrics

**Get success rate for specific agent/model/issue:**

```python
rate = tracker.get_success_rate(
    agent_name="RefactoringAgent",
    model_name="claude-sonnet-4-5-20250929",
    issue_type="complexity"
)
# Returns: 85.0 (percentage)
```

**Get aggregated success rates:**

```python
# Group by issue type for a specific agent
rates = tracker.get_success_rate(agent_name="RefactoringAgent")
# Returns: {"complexity": 85.0, "formatting": 92.0, ...}

# Group by agent for a specific issue type
rates = tracker.get_success_rate(issue_type="complexity")
# Returns: {"RefactoringAgent": 85.0, "ArchitectAgent": 78.0, ...}
```

##### Agent Recommendation

**Find best agent for issue type:**

```python
best = tracker.get_best_agent_for_issue_type(
    "complexity",
    min_attempts=5  # Require statistical significance
)
# Returns: {
#     "agent_name": "RefactoringAgent",
#     "model_name": "claude-sonnet-4-5-20250929",
#     "success_rate": 85.0,
#     "total_attempts": 20,
#     "avg_confidence": 0.82,
#     "avg_time_seconds": 2.1
# }
```

##### Model Comparison

**Compare performance across models:**

```python
comparison = tracker.get_model_comparison(
    issue_type="complexity",
    min_attempts=5
)
# Returns: {
#     "claude-sonnet-4-5-20250929": {
#         "avg_success_rate": 85.0,
#         "total_attempts": 100,
#         "avg_confidence": 0.82,
#         "avg_time_seconds": 2.1,
#         "issue_types": ["complexity", "security", ...]
#     },
#     "claude-opus-4-6-20250101": {
#         "avg_success_rate": 88.0,
#         ...
#     }
# }
```

##### Comprehensive Reporting

**Generate full performance report:**

```python
report = tracker.generate_performance_report()
# Returns: {
#     "generated_at": "2025-01-09T12:00:00",
#     "summary": {
#         "total_attempts": 500,
#         "total_successful": 425,
#         "overall_success_rate": 85.0,
#         "total_agents": 12,
#         "total_issue_types": 15,
#         "total_models": 3
#     },
#     "by_agent": {
#         "RefactoringAgent": {
#             "total_attempts": 100,
#             "success_rate": 85.0,
#             "issue_types": ["complexity", "dead_code", ...]
#         },
#         ...
#     },
#     "by_issue_type": {
#         "complexity": {
#             "total_attempts": 200,
#             "success_rate": 82.5,
#             "agents_used": ["RefactoringAgent", "ArchitectAgent", ...]
#         },
#         ...
#     },
#     "by_model": { ... },
#     "recommendations": {
#         "complexity": {
#             "agent_name": "RefactoringAgent",
#             "success_rate": 85.0,
#             ...
#         },
#         ...
#     }
# }
```

## Integration with Agent Coordinator

The performance tracker is integrated into `AgentCoordinator` to automatically record metrics after each agent execution:

```python
class AgentCoordinator:
    def __init__(self, ...):
        # ...
        self.performance_tracker = AgentPerformanceTracker()

    async def _handle_with_single_agent(self, agent: SubAgent, issue: Issue) -> FixResult:
        # ... agent execution ...

        execution_time_seconds = time.time() - start_time

        # Record performance metrics
        self._record_performance_metrics(
            agent_name=agent.name,
            issue_type=issue.type.value,
            result=result,
            confidence=confidence,
            execution_time_seconds=execution_time_seconds,
        )

        return result

    def _record_performance_metrics(self, ...):
        """Record agent performance metrics for analytics."""
        try:
            model_name = self.context.config.get("model_name", "unknown")

            self.performance_tracker.record_attempt(
                agent_name=agent_name,
                model_name=model_name,
                issue_type=issue_type,
                success=result.success,
                confidence=confidence,
                time_seconds=execution_time_seconds,
            )
        except Exception as e:
            # Don't let tracking errors break the workflow
            self.logger.debug(f"Failed to record performance metrics: {e}")
```

## Persistence

### Storage Location

Metrics are persisted to `/tmp/agent_performance.json` by default (configurable via constructor).

### Storage Format

```json
{
  "version": "1.0",
  "last_updated": "2025-01-09T12:00:00",
  "metrics": {
    "RefactoringAgent:claude-sonnet-4-5-20250929:complexity": {
      "agent_name": "RefactoringAgent",
      "model_name": "claude-sonnet-4-5-20250929",
      "issue_type": "complexity",
      "total_attempts": 20,
      "successful_fixes": 17,
      "failed_fixes": 3,
      "avg_confidence": 0.825,
      "avg_time_seconds": 2.15,
      "recent_results": [
        {
          "timestamp": "2025-01-09T12:00:00",
          "agent_name": "RefactoringAgent",
          "model_name": "claude-sonnet-4-5-20250929",
          "issue_type": "complexity",
          "success": true,
          "confidence": 0.85,
          "time_seconds": 2.3
        },
        ... (up to 100 recent attempts)
      ]
    },
    ...
  }
}
```

### Atomic Writes

Metrics are saved atomically to prevent corruption:

1. Write to temporary file (`.tmp` suffix)
1. Atomic rename to final location
1. Automatic loading on initialization

## Thread Safety

All public methods use `threading.Lock` to ensure thread-safe operations:

```python
def record_attempt(self, ...):
    with self._lock:
        # ... update metrics ...
        self._save_metrics()
```

This is critical for scenarios where multiple agents may be executing concurrently.

## Error Handling

The tracker is designed to never break the workflow:

- Tracking failures are logged at DEBUG level
- Corrupted metrics files are handled gracefully
- No exceptions propagate to caller
- Failed loads start with empty metrics

## Usage Examples

### Example 1: Track Agent Performance

```python
# Create tracker
tracker = AgentPerformanceTracker()

# Record attempts
tracker.record_attempt(
    agent_name="RefactoringAgent",
    model_name="claude-sonnet-4-5-20250929",
    issue_type="complexity",
    success=True,
    confidence=0.85,
    time_seconds=2.3,
)

# Get success rate
rate = tracker.get_success_rate(
    agent_name="RefactoringAgent",
    model_name="claude-sonnet-4-5-20250929",
    issue_type="complexity"
)
print(f"Success rate: {rate}%")
```

### Example 2: Find Best Agent

```python
# Get best agent for complexity issues
best = tracker.get_best_agent_for_issue_type("complexity", min_attempts=5)

if best:
    print(f"Best agent: {best['agent_name']}")
    print(f"Success rate: {best['success_rate']}%")
    print(f"Avg confidence: {best['avg_confidence']}")
    print(f"Avg time: {best['avg_time_seconds']}s")
```

### Example 3: Compare Models

```python
# Compare model performance
comparison = tracker.get_model_comparison(issue_type="complexity")

for model, stats in comparison.items():
    print(f"{model}:")
    print(f"  Success rate: {stats['avg_success_rate']}%")
    print(f"  Avg confidence: {stats['avg_confidence']}")
    print(f"  Avg time: {stats['avg_time_seconds']}s")
```

### Example 4: Generate Report

```python
# Generate comprehensive report
report = tracker.generate_performance_report()

# Print summary
summary = report['summary']
print(f"Total attempts: {summary['total_attempts']}")
print(f"Overall success rate: {summary['overall_success_rate']}%")
print(f"Agents tracked: {summary['total_agents']}")
print(f"Issue types: {summary['total_issue_types']}")

# Print best agents by issue type
print("\nRecommendations:")
for issue_type, best in report['recommendations'].items():
    print(f"  {issue_type}: {best['agent_name']} ({best['success_rate']}%)")
```

## Performance Considerations

### Memory Usage

- Each `AgentMetrics` instance stores up to 100 recent attempts
- Typical memory footprint: ~1KB per agent/model/issue combination
- For 100 combinations: ~100KB total

### I/O Performance

- Metrics saved after each attempt (atomic write)
- Typical write time: \<10ms for ~100KB file
- No I/O blocking due to thread-safe locking

### Computational Complexity

- `record_attempt()`: O(1) - direct dict lookup and update
- `get_success_rate()`: O(n) where n = number of metrics entries
- `get_best_agent_for_issue_type()`: O(n) - single pass filtering
- `generate_performance_report()`: O(n) - single pass aggregation

## Testing

The system includes comprehensive unit tests covering:

- Dataclass serialization/deserialization
- Metrics calculation and averaging
- Thread safety with concurrent operations
- Persistence and corruption recovery
- Atomic file writes
- Report generation

Run tests:

```bash
python -m pytest tests/unit/test_performance_tracker.py -v
```

## Future Enhancements

Potential improvements for future versions:

1. **Time-based filtering**: Filter metrics by date range (last 7 days, 30 days, etc.)
1. **Trend analysis**: Detect improving/degrading performance over time
1. **Confidence intervals**: Statistical significance testing for success rates
1. **Custom persistence backends**: SQLite, PostgreSQL, or Redis instead of JSON
1. **Real-time dashboard**: Live performance monitoring UI
1. **Alerting**: Notifications for performance degradation
1. **A/B testing**: Compare different agent configurations
1. **Cost tracking**: Track API costs by agent/model/issue type

## Related Documentation

- [Agent System](../reviews/layer-6-agent-system.md) - Overview of agent architecture
- [AI Fix System](./AI_FIX_PROGRESS_BAR_REDESIGN.md) - AI fix workflow integration

## Files

- **Implementation**: `/crackerjack/agents/performance_tracker.py`
- **Integration**: `/crackerjack/agents/coordinator.py` (AgentCoordinator)
- **Tests**: `/tests/unit/test_performance_tracker.py`
- **Metrics Storage**: `/tmp/agent_performance.json` (default)
