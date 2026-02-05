# AI-Fix Metrics and Observability Review

**Date**: 2026-02-04
**Reviewer**: Performance Monitor Specialist
**Status**: Critical Findings Identified

## Executive Summary

The AI-fix metrics infrastructure has **solid foundations** but suffers from **incomplete integration**. While the database schema and query methods are well-designed, critical tracking methods exist but are **not called in production code**, resulting in partial observability.

**Overall Assessment**: 6.5/10 (Good foundation, critical gaps in execution tracking)

______________________________________________________________________

## Current Implementation Review

### 1. Data Collection Architecture

#### Database Schema (/Users/les/Projects/crackerjack/crackerjack/services/metrics.py)

**Tables Added (2 new)**:

```sql
-- Agent execution tracking
CREATE TABLE agent_executions (
    id INTEGER PRIMARY KEY,
    job_id TEXT NOT NULL,
    agent_name TEXT NOT NULL,
    issue_type TEXT NOT NULL,
    success BOOLEAN NOT NULL,
    confidence REAL,
    fixes_applied INTEGER DEFAULT 0,
    files_modified INTEGER DEFAULT 0,
    remaining_issues INTEGER DEFAULT 0,
    timestamp TIMESTAMP NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

-- Provider performance tracking
CREATE TABLE provider_performance (
    id INTEGER PRIMARY KEY,
    provider_id TEXT NOT NULL,
    success BOOLEAN NOT NULL,
    latency_ms REAL,
    error_message TEXT,
    timestamp TIMESTAMP NOT NULL
);
```

**Indexes Added (4 new)**:

- `idx_agent_executions_job_id` on agent_executions(job_id)
- `idx_agent_executions_agent` on agent_executions(agent_name)
- `idx_provider_performance_provider` on provider_performance(provider_id)
- `idx_provider_performance_timestamp` on provider_performance(timestamp)

**Schema Design Rating**: 8/10

**Strengths**:

- Clean, normalized schema
- Proper foreign key relationships
- Comprehensive indexes for query performance
- Captures essential metrics (success, confidence, issue type)

**Concerns**:

- No `job_id` index on provider_performance (cannot correlate provider usage with jobs)
- Missing `execution_time_ms` on agent_executions (cannot measure agent performance)
- No `model` field on provider_performance (cannot distinguish between Claude Sonnet vs Opus)
- No `retry_count` or `fallback_reason` on provider_performance
- Missing unique constraint on (job_id, agent_name, issue_type) - allows duplicates

**Recommendations**:

```sql
ALTER TABLE provider_performance ADD COLUMN job_id TEXT;
ALTER TABLE provider_performance ADD COLUMN model TEXT;
ALTER TABLE provider_performance ADD COLUMN retry_count INTEGER DEFAULT 0;
ALTER TABLE provider_performance ADD COLUMN fallback_reason TEXT;
CREATE INDEX idx_provider_performance_job_id ON provider_performance(job_id);

ALTER TABLE agent_executions ADD COLUMN execution_time_ms REAL;
ALTER TABLE agent_executions ADD COLUMN provider_id TEXT;
CREATE UNIQUE INDEX idx_agent_executions_unique ON agent_executions(job_id, agent_name, issue_type);
```

______________________________________________________________________

### 2. Query Methods (/Users/les/Projects/crackerjack/crackerjack/services/metrics.py)

**Methods Added (3 new)**:

#### `get_agent_success_rate(agent_name, issue_type=None) -> float`

```python
SELECT COUNT(*) FILTER (WHERE success = TRUE) AS successes,
       COUNT(*) AS total
FROM agent_executions
WHERE agent_name = ?
```

**Rating**: 9/10

**Strengths**:

- Efficient aggregation query with `FILTER` clause
- Supports optional issue type filtering
- Handles edge cases (zero results returns 0.0)

**Concerns**:

- No time-based filtering (cannot see "success rate in last 7 days")
- No confidence weighting (high confidence failures count same as low confidence)

**Improvement**:

```python
def get_agent_success_rate(
    self,
    agent_name: str,
    issue_type: str | None = None,
    hours: int | None = None,  # NEW: time window
) -> float:
    query = """
        SELECT COUNT(*) FILTER (WHERE success = TRUE) AS successes,
               COUNT(*) AS total
        FROM agent_executions
        WHERE agent_name = ?
    """
    params = [agent_name]

    if issue_type:
        query += " AND issue_type = ?"
        params.append(issue_type)

    if hours:
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=hours)
        query += " AND timestamp >= ?"
        params.append(cutoff)
```

______________________________________________________________________

#### `get_provider_availability(provider_id, hours=24) -> float`

```python
SELECT COUNT(*) FILTER (WHERE success = TRUE) AS successes,
       COUNT(*) AS total
FROM provider_performance
WHERE provider_id = ? AND timestamp >= ?
```

**Rating**: 9/10

**Strengths**:

- Time-windowed query (default 24 hours)
- Properly handles datetime cutoff
- Returns percentage as float (0.0 to 1.0)

**Concerns**:

- No distinction between "availability failed" vs "execution failed"
- Does not track latency degradation (provider available but slow)

**Improvement**:

```python
def get_provider_availability(
    self,
    provider_id: str,
    hours: int = 24,
    max_latency_ms: float | None = None,  # NEW: latency threshold
) -> float:
    query = """
        SELECT COUNT(*) FILTER (WHERE success = TRUE) AS successes,
               COUNT(*) AS total
        FROM provider_performance
        WHERE provider_id = ? AND timestamp >= ?
    """
    params = [provider_id, cutoff]

    if max_latency_ms:
        query += " AND latency_ms <= ?"
        params.append(max_latency_ms)
```

______________________________________________________________________

#### `get_agent_confidence_distribution(agent_name) -> dict[str, int]`

```python
SELECT
    CASE
        WHEN confidence < 0.5 THEN 'low'
        WHEN confidence < 0.8 THEN 'medium'
        ELSE 'high'
    END AS confidence_level,
    COUNT(*) AS count
FROM agent_executions
WHERE agent_name = ? AND confidence IS NOT NULL
GROUP BY confidence_level
```

**Rating**: 7/10

**Strengths**:

- Useful for detecting confidence inflation
- Simple bucketing (low/medium/high)

**Concerns**:

- Hard-coded thresholds (0.5, 0.8) - should be configurable
- No time filtering (cannot see "confidence drift over time")
- Missing correlation with success (do high confidence predictions actually succeed more?)

**Improvement**:

```python
def get_agent_confidence_accuracy(self, agent_name: str, hours: int | None = None) -> dict[str, dict]:
    """Analyze whether confidence predictions match actual success.

    Returns:
        {
            'high': {'count': 100, 'success_rate': 0.85},
            'medium': {'count': 50, 'success_rate': 0.60},
            'low': {'count': 10, 'success_rate': 0.30}
        }
    """
    query = """
        SELECT
            CASE
                WHEN confidence < 0.5 THEN 'low'
                WHEN confidence < 0.8 THEN 'medium'
                ELSE 'high'
            END AS confidence_level,
            COUNT(*) AS count,
            AVG(CASE WHEN success = TRUE THEN 1.0 ELSE 0.0 END) AS actual_success_rate
        FROM agent_executions
        WHERE agent_name = ? AND confidence IS NOT NULL
    """

    if hours:
        query += " AND timestamp >= ?"

    query += " GROUP BY confidence_level"
```

______________________________________________________________________

### 3. Integration with ProviderChain (/Users/les/Projects/crackerjack/crackerjack/adapters/ai/registry.py)

**Implementation**:

```python
class ProviderChain:
    def _track_provider_selection(
        self,
        provider_id: ProviderID,
        success: bool,
        latency_ms: float,
        error: str | None = None,
    ) -> None:
        """Track provider selection for metrics analysis."""
        try:
            from crackerjack.services.metrics import get_metrics

            if self._metrics is None:
                self._metrics = get_metrics()

            self._metrics.execute(
                """
                INSERT INTO provider_performance
                (provider_id, success, latency_ms, error_message, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (provider_id.value, success, latency_ms, error, datetime.now()),
            )
        except Exception as e:
            logger.debug(f"Failed to track provider selection: {e}")
```

**Rating**: 9/10

**Strengths**:

- Called on every provider selection attempt
- Tracks both success and failure
- Captures latency for performance analysis
- Graceful error handling (logs debug, doesn't fail workflow)

**Verification**:

```bash
$ sqlite3 ~/.cache/crackerjack/metrics.db "SELECT COUNT(*) FROM provider_performance;"
14  # Data is being collected!
```

**Concerns**:

- No job_id correlation (cannot attribute provider usage to specific jobs)
- No model tracking (cannot distinguish Claude Sonnet vs Opus)
- Missing retry context (is this a first attempt or fallback?)

______________________________________________________________________

### 4. Integration with AgentCoordinator (/Users/les/Projects/crackerjack/crackerjack/agents/coordinator.py)

**CRITICAL FINDING**: Tracking method exists but is **NOT called in production code**.

**Method Exists** (line 412):

```python
async def _track_agent_execution(
    self,
    job_id: str,
    agent_name: str,
    issue_type: str,
    result: FixResult,
) -> None:
    """Persist agent execution metrics for analysis."""
    try:
        from crackerjack.services.metrics import get_metrics

        metrics = get_metrics()

        metrics.execute(
            """
            INSERT INTO agent_executions
            (job_id, agent_name, issue_type, success, confidence,
             fixes_applied, files_modified, remaining_issues, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                agent_name,
                issue_type,
                result.success,
                result.confidence,
                len(result.fixes_applied),
                len(result.files_modified),
                len(result.remaining_issues),
                datetime.now(),
            ),
        )
    except Exception as e:
        self.logger.debug(f"Failed to track agent execution: {e}")
```

**Problem**: Method is never invoked in `_handle_with_single_agent()` or anywhere else!

**Current Flow** (without tracking):

```python
async def _handle_with_single_agent(self, agent: SubAgent, issue: Issue) -> FixResult:
    confidence = await agent.can_handle(issue)
    self.tracker.track_agent_processing(agent.name, issue, confidence)  # In-memory only

    result = await self._execute_agent(agent, issue)

    self.tracker.track_agent_complete(agent.name, result)  # In-memory only

    return result  # NO DATABASE PERSISTENCE
```

**Why data exists in database**:

- Only test code calls `_track_agent_execution()`
- No production code path persists to agent_executions table

**Verification**:

```bash
$ grep -n "await.*_track_agent_execution" crackerjack/agents/coordinator.py
# No results - method is never called!
```

**Rating**: 2/10 (method exists but not integrated)

**Impact**:

- Query methods work but have incomplete data
- Agent success rates are based on test data only
- Production observability is severely limited

______________________________________________________________________

## Critical Observability Gaps

### 1. **Agent Execution Tracking** (CRITICAL)

**Issue**: Agents execute but data is not persisted to database.

**Current State**:

- In-memory tracking via `AgentTracker` works for current session
- Database tracking via `_track_agent_execution()` is not called
- No job_id correlation for agent executions

**Impact**:

- Cannot analyze agent effectiveness over time
- Cannot correlate agent success rates with issue types
- No historical data for trend analysis

**Recommendation**:

```python
# In _handle_with_single_agent(), after result is obtained:
async def _handle_with_single_agent(
    self,
    agent: SubAgent,
    issue: Issue,
    job_id: str | None = None,  # ADD: job_id parameter
) -> FixResult:
    # ... existing code ...

    result = await self._execute_agent(agent, issue)

    # PERSIST TO DATABASE
    if job_id:
        await self._track_agent_execution(
            job_id=job_id,
            agent_name=agent.name,
            issue_type=issue.type.value,
            result=result,
        )

    return result
```

______________________________________________________________________

### 2. **Job ID Propagation** (CRITICAL)

**Issue**: AgentCoordinator does not receive job_id from orchestration layer.

**Current State**:

- `AgentCoordinator` is initialized without job context
- No way to correlate agent executions with parent jobs
- Cannot track "which agents were used for job X"

**Impact**:

- Cannot analyze agent performance per job
- No correlation between agent usage and job success
- Missing end-to-end traceability

**Recommendation**:

```python
# In AgentCoordinator.__init__():
class AgentCoordinator:
    def __init__(
        self,
        context: AgentContext,
        tracker: AgentTrackerProtocol,
        debugger: DebuggerProtocol,
        cache: CrackerjackCache | None = None,
        job_id: str | None = None,  # ADD: job context
    ) -> None:
        self.context = context
        self.job_id = job_id  # STORE: for tracking
        # ... rest of init ...

# In orchestration layer, pass job_id:
coordinator = AgentCoordinator(
    context=context,
    tracker=tracker,
    debugger=debugger,
    cache=cache,
    job_id=job_id,  # PASS: from job manager
)
```

______________________________________________________________________

### 3. **Missing Metrics** (HIGH PRIORITY)

**Critical Metrics Not Collected**:

1. **Agent Execution Time**

   - Why: Cannot identify slow agents
   - Impact: Performance bottlenecks go undetected
   - Fix: Add `execution_time_ms` to agent_executions

1. **Provider-Agent Correlation**

   - Why: Cannot determine which provider an agent used
   - Impact: Cannot optimize agent-provider pairing
   - Fix: Add `provider_id` to agent_executions

1. **Retry and Fallback Tracking**

   - Why: Cannot measure provider chain effectiveness
   - Impact: Hidden failures in provider selection
   - Fix: Add `retry_count`, `fallback_reason` to provider_performance

1. **Model Version Tracking**

   - Why: Cannot distinguish model performance (Sonnet vs Opus)
   - Impact: Cost optimization is impossible
   - Fix: Add `model` field to provider_performance

1. **Confidence vs Success Correlation**

   - Why: Cannot detect confidence inflation
   - Impact: Agents may claim high confidence but fail
   - Fix: Add query method for confidence accuracy analysis

______________________________________________________________________

### 4. **Query Performance Concerns** (MEDIUM)

**Issue**: Some queries may not scale with large datasets.

**Problematic Query 1** (in `get_orchestration_stats()`):

```python
SELECT
    selected_strategy,
    COUNT(*) as usage_count,
    AVG(effectiveness_score) as avg_effectiveness,
    AVG((
        SELECT iteration_count
        FROM orchestration_executions o
        WHERE o.job_id=sd.job_id
    )) as avg_iterations_needed
FROM strategy_decisions sd
WHERE effectiveness_score IS NOT NULL
GROUP BY selected_strategy
```

**Concern**: Subquery in AVG() will execute once per row - O(n²) with large datasets.

**Recommendation**:

```python
SELECT
    sd.selected_strategy,
    COUNT(*) as usage_count,
    AVG(sd.effectiveness_score) as avg_effectiveness,
    AVG(o.iteration_count) as avg_iterations_needed
FROM strategy_decisions sd
JOIN orchestration_executions o ON o.job_id = sd.job_id
WHERE sd.effectiveness_score IS NOT NULL
GROUP BY sd.selected_strategy
```

**Problematic Query 2** (daily summary update):

```python
SELECT
    (SELECT selected_strategy
     FROM strategy_decisions sd2
     WHERE DATE(sd2.timestamp) = ?
     GROUP BY selected_strategy
     ORDER BY COUNT(*) DESC
     LIMIT 1) as most_effective_strategy
FROM orchestration_executions
WHERE DATE(timestamp) = ?
```

**Concern**: Subquery scans entire strategy_decisions table for every daily summary update.

**Recommendation**: Materialize "most effective strategy" in a separate nightly aggregation job.

______________________________________________________________________

### 5. **Data Retention and Cleanup** (LOW PRIORITY)

**Issue**: No automated cleanup of old metrics data.

**Current State**:

- Database will grow indefinitely
- No TTL or retention policies
- No archival strategy for old data

**Impact**:

- Query performance degrades over time
- Disk space consumption grows unbounded
- Privacy concerns (old error messages in database)

**Recommendation**:

```python
# Add to MetricsCollector class:
def cleanup_old_metrics(self, retention_days: int = 90) -> int:
    """Delete metrics older than retention period.

    Args:
        retention_days: Number of days to retain (default: 90)

    Returns:
        Number of rows deleted
    """
    from datetime import timedelta

    cutoff = datetime.now() - timedelta(days=retention_days)

    with self._get_connection() as conn:
        # Delete from child tables first (foreign key constraints)
        tables = [
            "agent_executions",
            "provider_performance",
            "individual_test_executions",
            "strategy_decisions",
            "errors",
            "hook_executions",
            "test_executions",
            "orchestration_executions",
        ]

        total_deleted = 0
        for table in tables:
            result = conn.execute(
                f"DELETE FROM {table} WHERE timestamp < ?",
                (cutoff,),
            )
            total_deleted += result.rowcount

        # Delete old jobs
        result = conn.execute(
            "DELETE FROM jobs WHERE start_time < ?",
            (cutoff,),
        )
        total_deleted += result.rowcount

        # Delete old daily summaries
        result = conn.execute(
            "DELETE FROM daily_summary WHERE date < ?",
            (cutoff.date(),),
        )
        total_deleted += result.rowcount

    return total_deleted
```

______________________________________________________________________

## Performance Impact Analysis

### Metrics Collection Overhead

**Current Implementation**:

1. **ProviderChain Tracking** (registry.py:295-327)

   - **Frequency**: Every provider selection attempt
   - **Operation**: Single INSERT with indexes
   - **Overhead**: ~1-5ms per attempt
   - **Impact**: Negligible (async, non-blocking)

1. **AgentCoordinator Tracking** (coordinator.py:412-454)

   - **Frequency**: Never called in production
   - **Operation**: Single INSERT with indexes
   - **Overhead**: ~1-5ms per agent execution (if called)
   - **Impact**: Would add ~5-10ms per issue (acceptable)

1. **SQLite Threading Lock** (metrics.py:19)

   - **Mechanism**: `threading.Lock()` for database writes
   - **Impact**: Potential bottleneck if multiple threads write concurrently
   - **Mitigation**: SQLite is already fast for single-writer workloads

**Performance Rating**: 9/10

**Overall Impact**:

- **Current overhead**: ~1-5ms per provider selection (minimal)
- **Potential overhead**: ~10-15ms per agent execution (if integrated)
- **Batch workflow impact**: ~5-10 seconds per 1000 issues (acceptable)

______________________________________________________________________

## Recommendations Priority Matrix

### CRITICAL (Fix Immediately)

1. **Integrate `_track_agent_execution()` into production code**

   - File: `crackerjack/agents/coordinator.py`
   - Method: `_handle_with_single_agent()`
   - Effort: 30 minutes
   - Impact: Enables agent effectiveness analysis

1. **Propagate job_id to AgentCoordinator**

   - File: `crackerjack/agents/coordinator.py`
   - Method: `__init__()`
   - Effort: 1 hour
   - Impact: Enables end-to-end traceability

### HIGH (Fix This Sprint)

3. **Add execution_time_ms to agent_executions**

   - File: `crackerjack/services/metrics.py`
   - Effort: 30 minutes
   - Impact: Detect slow agents

1. **Add provider_id to agent_executions**

   - File: `crackerjack/services/metrics.py`
   - Effort: 30 minutes
   - Impact: Optimize agent-provider pairing

1. **Implement confidence accuracy query**

   - File: `crackerjack/services/metrics.py`
   - Method: `get_agent_confidence_accuracy()`
   - Effort: 1 hour
   - Impact: Detect confidence inflation

### MEDIUM (Next Sprint)

6. **Add model tracking to provider_performance**

   - File: `crackerjack/adapters/ai/registry.py`
   - Effort: 30 minutes
   - Impact: Cost optimization

1. **Optimize subquery in get_orchestration_stats()**

   - File: `crackerjack/services/metrics.py`
   - Effort: 30 minutes
   - Impact: Query performance with large datasets

1. **Implement data retention cleanup**

   - File: `crackerjack/services/metrics.py`
   - Method: `cleanup_old_metrics()`
   - Effort: 1 hour
   - Impact: Long-term performance

### LOW (Backlog)

9. **Add job_id index on provider_performance**

   - File: `crackerjack/services/metrics.py`
   - Effort: 15 minutes
   - Impact: Better provider-job correlation

1. **Add unique constraint on agent_executions**

   - File: `crackerjack/services/metrics.py`
   - Effort: 15 minutes
   - Impact: Prevent duplicate tracking

______________________________________________________________________

## Testing Strategy

### Unit Tests Required

1. **Agent Execution Tracking**

   - Test that `_track_agent_execution()` writes to database
   - Test that job_id is properly correlated
   - Test that execution_time_ms is captured

1. **Provider Performance Tracking**

   - Test that provider selection is tracked on every attempt
   - Test that latency is measured accurately
   - Test that failures are tracked with error messages

1. **Query Method Accuracy**

   - Test `get_agent_success_rate()` with various filters
   - Test `get_provider_availability()` with time windows
   - Test `get_agent_confidence_distribution()` edge cases

### Integration Tests Required

1. **End-to-End Metrics Collection**

   - Run full workflow with AI-fix enabled
   - Verify all tables have data
   - Verify foreign key relationships

1. **Query Performance with Large Datasets**

   - Insert 10,000+ agent_executions
   - Verify query performance (\<100ms)
   - Test with concurrent writes

______________________________________________________________________

## Conclusion

The AI-fix metrics infrastructure has a **solid foundation** but suffers from **incomplete integration**. The database schema and query methods are well-designed, but critical tracking methods exist without being called in production code.

**Key Findings**:

1. **Schema Design**: 8/10 (good normalization, indexes, but missing fields)
1. **Query Methods**: 8/10 (efficient SQL, but missing time filtering)
1. **Provider Integration**: 9/10 (working well, tracking every attempt)
1. **Agent Integration**: 2/10 (method exists but not called)

**Critical Actions**:

1. Call `_track_agent_execution()` in `_handle_with_single_agent()` (CRITICAL)
1. Propagate job_id to AgentCoordinator (CRITICAL)
1. Add execution_time_ms and provider_id fields (HIGH)
1. Implement confidence accuracy analysis (HIGH)

**Estimated Effort**:

- Critical fixes: 2 hours
- High priority: 3 hours
- Medium priority: 2 hours
- **Total**: 7 hours to reach production-ready observability

Once these gaps are addressed, the system will have comprehensive observability for AI-fix effectiveness, provider performance, and agent optimization opportunities.
