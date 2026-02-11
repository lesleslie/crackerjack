# Skill Metrics Storage Schema Design

**Author**: Database Administrator
**Status**: Production Ready
**Last Updated**: 2025-02-10

______________________________________________________________________

## Executive Summary

Migration from JSON file storage to ACID-compliant relational database with support for:
- Immutable event logs (skill invocations)
- Mutable aggregated metrics with automatic recalculation
- Schema versioning and migration support
- Concurrent access with proper locking
- High-performance aggregations via materialized views

______________________________________________________________________

## Database Schema

### Table: `skill_invocation` (Immutable Event Log)

**Purpose**: Append-only log of all skill usage events (never updated, never deleted)

```sql
CREATE TABLE skill_invocation (
    id TEXT PRIMARY KEY,  -- UUID
    skill_name TEXT NOT NULL,
    invoked_at TIMESTAMP NOT NULL DEFAULT (datetime('now')),
    workflow_path TEXT,
    completed BOOLEAN NOT NULL DEFAULT 0,
    duration_seconds REAL,
    error_type TEXT,
    session_id TEXT,  -- FK to session_buddy.sessions

    -- JSON array of follow-up actions
    follow_up_actions JSON,

    -- Schema versioning
    schema_version INTEGER NOT NULL DEFAULT 1,

    -- Metadata for analytics
    project_path TEXT,
    user_context JSON,

    -- Indexes for common queries
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
);

CREATE INDEX idx_skill_invocation_skill_name ON skill_invocation(skill_name);
CREATE INDEX idx_skill_invocation_invoked_at ON skill_invocation(invoked_at DESC);
CREATE INDEX idx_skill_invocation_session_id ON skill_invocation(session_id);
CREATE INDEX idx_skill_invocation_completed ON skill_invocation(completed);

-- Composite index for skill performance over time
CREATE INDEX idx_skill_invocation_skill_time
    ON skill_invocation(skill_name, invoked_at DESC);

-- Full-text search on workflow paths
CREATE VIRTUAL TABLE skill_invocation_fts USING fts5(
    skill_name, workflow_path, content=''
);
```

### Table: `skill_metrics` (Mutable Aggregates)

**Purpose**: Denormalized aggregated metrics for fast reads (updated via triggers)

```sql
CREATE TABLE skill_metrics (
    skill_name TEXT PRIMARY KEY,

    -- Invocation counts
    total_invocations INTEGER NOT NULL DEFAULT 0,
    completed_invocations INTEGER NOT NULL DEFAULT 0,
    abandoned_invocations INTEGER NOT NULL DEFAULT 0,

    -- Duration statistics
    total_duration_seconds REAL NOT NULL DEFAULT 0.0,
    min_duration_seconds REAL,
    max_duration_seconds REAL,
    p50_duration_seconds REAL,  -- Median
    p95_duration_seconds REAL,  -- 95th percentile
    p99_duration_seconds REAL,  -- 99th percentile

    -- Workflow path preferences (JSON object: {"path": count})
    workflow_paths JSON NOT NULL DEFAULT '{}',

    -- Error tracking (JSON object: {"error_type": count})
    common_errors JSON NOT NULL DEFAULT '{}',

    -- Follow-up actions (JSON object: {"action": count})
    follow_up_actions JSON NOT NULL DEFAULT '{}',

    -- Timestamps
    first_invoked TIMESTAMP,
    last_invoked TIMESTAMP,

    -- Computed fields (updated via triggers)
    completion_rate REAL,
    avg_duration_seconds REAL,

    -- Schema versioning
    schema_version INTEGER NOT NULL DEFAULT 1,

    -- Last update tracking
    last_aggregated_at TIMESTAMP DEFAULT (datetime('now'))
);

-- Trigger to auto-update computed fields on INSERT/UPDATE
CREATE TRIGGER trg_skill_metrics_update_computed
AFTER INSERT ON skill_invocation
BEGIN
    UPDATE skill_metrics
    SET completion_rate = CAST(completed_invocations AS REAL) / total_invocations * 100,
        avg_duration_seconds = CASE
            WHEN completed_invocations > 0
            THEN total_duration_seconds / completed_invocations
            ELSE 0
        END,
        last_aggregated_at = datetime('now')
    WHERE skill_name = NEW.skill_name;
END;
```

### Table: `session_skill` (Session-Skill Junction)

**Purpose**: Track which skills were used in each session (many-to-many)

```sql
CREATE TABLE session_skill (
    id TEXT PRIMARY KEY,  -- UUID
    session_id TEXT NOT NULL,
    skill_name TEXT NOT NULL,
    invocation_count INTEGER NOT NULL DEFAULT 1,
    first_invoked_at TIMESTAMP NOT NULL,
    last_invoked_at TIMESTAMP NOT NULL,
    total_duration_seconds REAL NOT NULL DEFAULT 0.0,

    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (skill_name) REFERENCES skill_metrics(skill_name) ON DELETE CASCADE,

    UNIQUE(session_id, skill_name)
);

CREATE INDEX idx_session_skill_session_id ON session_skill(session_id);
CREATE INDEX idx_session_skill_skill_name ON session_skill(skill_name);

-- Trigger to update junction table on new invocation
CREATE TRIGGER trg_session_skill_update
AFTER INSERT ON skill_invocation
WHEN NEW.session_id IS NOT NULL
BEGIN
    INSERT INTO session_skill (
        id, session_id, skill_name, invocation_count,
        first_invoked_at, last_invoked_at, total_duration_seconds
    )
    VALUES (
        lower(hex(randomblob(16))),
        NEW.session_id,
        NEW.skill_name,
        1,
        NEW.invoked_at,
        NEW.invoked_at,
        COALESCE(NEW.duration_seconds, 0.0)
    )
    ON CONFLICT(session_id, skill_name) DO UPDATE SET
        invocation_count = invocation_count + 1,
        last_invoked_at = NEW.invoked_at,
        total_duration_seconds = total_duration_seconds + COALESCE(NEW.duration_seconds, 0.0);
END;
```

### Table: `schema_migrations` (Version Tracking)

**Purpose**: Track schema evolution and run migrations

```sql
CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT (datetime('now')),
    description TEXT NOT NULL,
    checksum TEXT,  -- SHA256 of migration SQL
    rollback_sql TEXT,
    migration_time_ms REAL
);

-- Seed initial version
INSERT INTO schema_migrations (version, description, checksum)
VALUES (1, 'Initial skill metrics schema', '<sha256>');
```

### Materialized View: `skill_metrics_summary`

**Purpose**: Pre-computed aggregations for fast dashboard queries

```sql
CREATE TABLE skill_metrics_summary (
    refresh_time TIMESTAMP PRIMARY KEY,
    total_skills INTEGER NOT NULL,
    total_invocations INTEGER NOT NULL,
    overall_completion_rate REAL NOT NULL,
    most_used_skill TEXT,
    most_used_count INTEGER NOT NULL,
    avg_duration_seconds REAL NOT NULL,
    top_error_types JSON,
    top_workflow_paths JSON
);

-- Refresh procedure (call periodically or on demand)
CREATE PROCEDURE refresh_skill_metrics_summary()
BEGIN
    DELETE FROM skill_metrics_summary;

    INSERT INTO skill_metrics_summary
    SELECT
        datetime('now') as refresh_time,
        COUNT(*) as total_skills,
        SUM(total_invocations) as total_invocations,
        CASE
            WHEN SUM(total_invocations) > 0
            THEN CAST(SUM(completed_invocations) AS REAL) / SUM(total_invocations) * 100
            ELSE 0
        END as overall_completion_rate,
        (SELECT skill_name FROM skill_metrics ORDER BY total_invocations DESC LIMIT 1) as most_used_skill,
        (SELECT total_invocations FROM skill_metrics ORDER BY total_invocations DESC LIMIT 1) as most_used_count,
        CASE
            WHEN SUM(completed_invocations) > 0
            THEN SUM(total_duration_seconds) / SUM(completed_invocations)
            ELSE 0
        END as avg_duration_seconds,
        -- Top error types across all skills
        (
            SELECT json_group_object(error_type, total_count)
            FROM (
                SELECT
                    json_extract(value, '$.error_type') as error_type,
                    SUM(json_extract(value, '$.count')) as total_count
                FROM skill_metrics,
                     json_each(skill_metrics.common_errors)
                GROUP BY error_type
                ORDER BY total_count DESC
                LIMIT 10
            )
        ) as top_error_types,
        -- Top workflow paths across all skills
        (
            SELECT json_group_object(path, total_count)
            FROM (
                SELECT
                    json_extract(value, '$.path') as path,
                    SUM(json_extract(value, '$.count')) as total_count
                FROM skill_metrics,
                     json_each(skill_metrics.workflow_paths)
                GROUP BY path
                ORDER BY total_count DESC
                LIMIT 10
            )
        ) as top_workflow_paths
    FROM skill_metrics;
END;
```

______________________________________________________________________

## Schema Evolution Strategy

### Migration Format

**File Naming**: `migrations/V{version}__{description}.sql`

**Example**: `migrations/V2__add_success_rate_field.sql`

```sql
-- V2__add_success_rate_field.sql
-- Description: Add success_rate field to skill_metrics for better analytics

-- Forward migration
BEGIN TRANSACTION;

ALTER TABLE skill_metrics ADD COLUMN success_rate REAL;

-- Calculate initial values
UPDATE skill_metrics
SET success_rate = CASE
    WHEN total_invocations > 0
    THEN CAST(completed_invocations AS REAL) / total_invocations * 100
    ELSE 0
END;

-- Update schema version
INSERT INTO schema_migrations (version, description, checksum)
VALUES (2, 'Add success_rate field', '<sha256>');

COMMIT;

-- Rollback migration
-- ROLLBACK;
-- ALTER TABLE skill_metrics DROP COLUMN success_rate;
-- DELETE FROM schema_migrations WHERE version = 2;
```

### Migration Principles

1. **Additive Changes**: Always add columns, never remove
   - Renaming: Add new column, migrate data, deprecate old column
   - Removal: Mark deprecated, remove in next major version

2. **Backward Compatibility**: Old code works with new schema
   - Default values for new columns
   - Optional columns (nullable)
   - JSON fields for flexible metadata

3. **Data Migration**: Use transactions and batch processing
   ```sql
   -- Process in batches to avoid locking
   UPDATE skill_metrics
   SET new_field = calculated_value
   WHERE id IN (
       SELECT id FROM skill_metrics LIMIT 1000
   );
   -- Repeat until all rows migrated
   ```

4. **Rollback Support**: Every migration has rollback SQL
   - Test rollback in staging
   - Document migration dependencies

______________________________________________________________________

## Indexing Strategy

### Query Patterns & Indexes

| Query Pattern | Index | Type |
|--------------|-------|------|
| Skill usage over time | `(skill_name, invoked_at DESC)` | Composite |
| Session skill history | `(session_id, invoked_at DESC)` | Composite |
| Find recent invocations | `(invoked_at DESC)` | Simple |
| Skill completion stats | `(skill_name, completed)` | Composite |
| Error type lookup | `(skill_name, error_type)` via JSON | JSON index |
| Full-text workflow search | FTS5 virtual table | Full-text |

### Index Maintenance

```sql
-- Reindex (run weekly/monthly)
REINDEX skill_invocation;
ANALYZE skill_invocation;

-- Check index usage
EXPLAIN QUERY PLAN
SELECT * FROM skill_invocation
WHERE skill_name = 'crackerjack-run'
ORDER BY invoked_at DESC
LIMIT 100;

-- Should show: USING INDEX idx_skill_invocation_skill_time
```

______________________________________________________________________

## Performance Optimization

### Query Optimization

```sql
-- ❌ BAD: Full table scan
SELECT * FROM skill_invocation
WHERE UPPER(skill_name) = 'CRACKERJACK-RUN';

-- ✅ GOOD: Index-backed query
SELECT * FROM skill_invocation
WHERE skill_name = 'crackerjack-run';

-- ❌ BAD: N+1 query problem
SELECT * FROM skill_metrics WHERE skill_name = 'skill1';
SELECT * FROM skill_metrics WHERE skill_name = 'skill2';
-- ... repeat for each skill

-- ✅ GOOD: Single query with IN clause
SELECT * FROM skill_metrics
WHERE skill_name IN ('skill1', 'skill2', 'skill3');
```

### Aggregation Optimization

```sql
-- Use materialized view for dashboard queries
-- Refresh every 5 minutes instead of computing on demand

CALL refresh_skill_metrics_summary();

-- Query is now instant
SELECT * FROM skill_metrics_summary;
```

### Connection Pooling

```python
# Use connection pooling for concurrent access
import sqlite3
from threading import local

class ConnectionPool:
    def __init__(self, db_path: str, pool_size: int = 5):
        self.db_path = db_path
        self.pool_size = pool_size
        self.local = local()

    def get_connection(self) -> sqlite3.Connection:
        if not hasattr(self.local, 'conn'):
            self.local.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                isolation_level=None  # Autocommit mode
            )
            self.local.conn.execute('PRAGMA journal_mode=WAL')
            self.local.conn.execute('PRAGMA busy_timeout=5000')
        return self.local.conn

    def close_all(self):
        if hasattr(self.local, 'conn'):
            self.local.conn.close()
            del self.local.conn
```

______________________________________________________________________

## Summary

**Key Design Decisions**:

1. **Immutable Event Log**: `skill_invocation` is append-only (never updated)
2. **Denormalized Metrics**: `skill_metrics` stores aggregates (fast reads)
3. **Automatic Triggers**: Computed fields updated automatically
4. **Schema Versioning**: Built-in migration tracking
5. **Materialized Views**: Pre-computed summaries for dashboards
6. **Full-Text Search**: FTS5 for workflow path search
7. **JSON Flexibility**: Optional metadata without schema changes

**ACID Guarantees**:

- **Atomicity**: All mutations in transactions
- **Consistency**: Foreign keys and triggers maintain invariants
- **Isolation**: WAL mode with appropriate isolation levels
- **Durability**: `synchronous=NORMAL` (balance performance/safety)

**Next Steps**:

1. Implement migration system
2. Create transaction patterns for common operations
3. Build Python ORM/abstraction layer
4. Add monitoring for query performance
5. Document backup/restore procedures
