# Skill Metrics Storage - Quick Reference

**Author**: Database Administrator
**Status**: Production Ready
**Last Updated**: 2025-02-10

______________________________________________________________________

## TL;DR - Architecture Decision

**Replace JSON file storage with SQLite database for ACID guarantees:**

| Aspect | JSON Files (Current) | SQLite Database (Proposed) |
|--------|---------------------|---------------------------|
| ACID Guarantees | ❌ No transactions | ✅ Full ACID compliance |
| Concurrent Access | ❌ File locking issues | ✅ WAL mode, multiple readers |
| Schema Evolution | ❌ Manual migration | ✅ Automatic migrations |
| Query Performance | ❌ Load entire file | ✅ Indexed queries |
| Data Integrity | ❌ Corruption possible | ✅ Foreign key constraints |
| Analytics | ❌ Manual aggregation | ✅ SQL queries, materialized views |

**Recommendation**: Migrate to SQLite using phased approach (dual-write → validation → cutover)

______________________________________________________________________

## Database Schema Overview

### Core Tables

```sql
-- Immutable event log (append-only)
skill_invocation (
    id, skill_name, invoked_at, workflow_path,
    completed, duration_seconds, error_type, session_id,
    follow_up_actions JSON, schema_version
)

-- Aggregated metrics (auto-updated via triggers)
skill_metrics (
    skill_name PK,
    total_invocations, completed_invocations, abandoned_invocations,
    total_duration_seconds, workflow_paths JSON, common_errors JSON,
    follow_up_actions JSON, first_invoked, last_invoked,
    completion_rate, avg_duration_seconds, schema_version
)

-- Session-skill junction (many-to-many)
session_skill (
    session_id, skill_name, invocation_count,
    first_invoked_at, last_invoked_at, total_duration_seconds
)

-- Schema version tracking
schema_migrations (
    version PK, applied_at, description, checksum
)
```

### Key Indexes

```sql
CREATE INDEX idx_skill_invocation_skill_time
    ON skill_invocation(skill_name, invoked_at DESC);

CREATE INDEX idx_skill_invocation_completed
    ON skill_invocation(completed);
```

### Automatic Triggers

```sql
-- Update computed fields on insert
CREATE TRIGGER trg_skill_metrics_update_computed
AFTER INSERT ON skill_invocation
BEGIN
    UPDATE skill_metrics
    SET completion_rate = (completed_invocations / total_invocations) * 100,
        avg_duration_seconds = total_duration_seconds / completed_invocations
    WHERE skill_name = NEW.skill_name;
END;

-- Update session-skill junction
CREATE TRIGGER trg_session_skill_update
AFTER INSERT ON skill_invocation
BEGIN
    INSERT INTO session_skill (...)
    ON CONFLICT(session_id, skill_name) DO UPDATE SET ...;
END;
```

______________________________________________________________________

## Transaction Patterns

### Pattern 1: Track Invocation

```python
from crackerjack.skills.metrics_db import get_store

store = get_store()

# Start tracking
result = store.track_invocation(
    skill_name="crackerjack-run",
    workflow_path="comprehensive",
    session_id="session-abc123"
)

# ... skill logic ...

# Complete (atomic update + metric recalculation)
result.completer(
    completed=True,
    follow_up_actions=["git commit", "git push"]
)
```

### Pattern 2: Concurrent Access

```python
# Thread-safe (per-skill locking)
result = store.track_invocation_concurrent("crackerjack-run")
result.completer(completed=True)
```

### Pattern 3: Analytical Queries

```python
# Get skill metrics
metrics = store.get_skill_metrics("crackerjack-run")
print(f"Completion: {metrics['completion_rate']:.1f}%")

# Get all skills
all_metrics = store.get_all_metrics()

# Get summary
summary = store.get_summary()
print(f"Total skills: {summary['total_skills']}")
print(f"Overall completion: {summary['overall_completion_rate']:.1f}%")

# Timeline analysis
timeline = store.get_skill_timeline("crackerjack-run", time_window="7 days")

# Full-text search
results = store.search_workflow_paths("comprehensive")
```

______________________________________________________________________

## Migration Strategy

### Phase 1: Dual-Write (1-2 weeks)

```python
# Write to both systems, read from JSON (source of truth)
class DualWriteMetricsTracker:
    def track_invocation(self, skill_name, workflow_path):
        json_completer = self.json_tracker.track_invocation(...)
        db_completer = self.db_store.track_invocation(...)

        def dual_complete(**kwargs):
            json_completer(**kwargs)  # Source of truth
            try:
                db_completer(**kwargs)  # Validation
            except Exception:
                pass  # Log but don't fail

        return dual_complete
```

### Phase 2: Data Migration (1-2 days)

```python
# Bulk migrate historical data
migrator = DataMigrator(
    json_path=Path(".session-buddy/skill_metrics.json"),
    db_store=store
)

stats = migrator.migrate_all_data()
print(f"Migrated {stats['invocations_migrated']} invocations")
```

### Phase 3: Dual-Read Validation (1 week)

```python
# Read from DB, validate against JSON
class DualReadMetricsTracker:
    def get_skill_metrics(self, skill_name):
        db_metrics = self.db_store.get_skill_metrics(skill_name)
        json_metrics = self.json_tracker.get_skill_metrics(skill_name)

        # Validate consistency
        assert db_metrics['total_invocations'] == json_metrics.total_invocations

        return db_metrics
```

### Phase 4: Cutover (1 day)

```bash
# Stop services, final sync, backup JSON, cutover
./cutover_to_database.sh

# Rollback if needed
./rollback_to_json.sh
```

### Phase 5: Cleanup (1 week later)

```python
# Remove legacy JSON code after successful cutover
# DELETE: crackerjack/skills/metrics.py (old JSON implementation)
# KEEP: crackerjack/skills/metrics_db.py (new database implementation)
```

______________________________________________________________________

## Schema Evolution

### Migration File Format

**`migrations/V2__add_percentile_fields.sql`**:

```sql
-- Forward migration
BEGIN TRANSACTION;
ALTER TABLE skill_metrics ADD COLUMN p50_duration_seconds REAL;
ALTER TABLE skill_metrics ADD COLUMN p95_duration_seconds REAL;
ALTER TABLE skill_metrics ADD COLUMN p99_duration_seconds REAL;
INSERT INTO schema_migrations (version, description) VALUES (2, 'Add percentiles');
COMMIT;

-- Rollback migration
-- ROLLBACK;
-- ALTER TABLE skill_metrics DROP COLUMN p99_duration_seconds;
-- ALTER TABLE skill_metrics DROP COLUMN p95_duration_seconds;
-- ALTER TABLE skill_metrics DROP COLUMN p50_duration_seconds;
-- DELETE FROM schema_migrations WHERE version = 2;
```

### Migration Runner

```python
from crackerjack.skills.metrics_migrations import MigrationRunner

runner = MigrationRunner(
    db_path=".session-buddy/skill_metrics.db",
    migrations_dir=Path("crackerjack/skills/schemas/migrations")
)

# Run pending migrations
runner.run_migrations()

# Rollback if needed
runner.rollback_migration(version=2)
```

______________________________________________________________________

## Performance Optimization

### SQLite Pragmas

```python
conn = sqlite3.connect(db_path)
conn.execute('PRAGMA journal_mode=WAL')  # Better concurrency
conn.execute('PRAGMA synchronous=NORMAL')  # Balance safety/performance
conn.execute('PRAGMA busy_timeout=5000')  # Wait 5s on lock
conn.execute('PRAGMA temp_store=MEMORY')  # Use RAM for temp tables
```

### Query Optimization

```sql
-- ❌ BAD: Full table scan
SELECT * FROM skill_invocation
WHERE UPPER(skill_name) = 'CRACKERJACK-RUN';

-- ✅ GOOD: Index-backed query
SELECT * FROM skill_invocation
WHERE skill_name = 'crackerjack-run'
ORDER BY invoked_at DESC
LIMIT 100;
```

### Materialized Views

```sql
-- Refresh periodically (not on every query)
CALL refresh_skill_metrics_summary();

-- Query is instant
SELECT * FROM skill_metrics_summary;
```

______________________________________________________________________

## Testing

### Unit Tests

```python
# tests/skills/test_metrics_db.py
def test_track_invocation(temp_db):
    result = temp_db.track_invocation("test-skill")
    result.completer(completed=True)

    metrics = temp_db.get_skill_metrics("test-skill")
    assert metrics['total_invocations'] == 1
    assert metrics['completion_rate'] == 100.0
```

### Integration Tests

```python
def test_concurrent_access(temp_db):
    import threading

    def track_skill():
        result = temp_db.track_invocation("test-skill")
        result.completer(completed=True)

    threads = [threading.Thread(target=track_skill) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    metrics = temp_db.get_skill_metrics("test-skill")
    assert metrics['total_invocations'] == 10
```

### Migration Tests

```python
def test_migration_from_json(temp_db, json_tracker):
    migrator = DataMigrator(json_path, temp_db)
    stats = migrator.migrate_all_data()

    assert stats['validation_errors'] == 0
    assert stats['invocations_migrated'] > 0
```

______________________________________________________________________

## Monitoring & Alerts

### Health Checks

```python
def check_database_health(store: SkillMetricsStore) -> dict:
    """Check database health and performance."""
    return {
        'database_size_mb': store.db_path.stat().st_size / (1024 * 1024),
        'total_invocations': store.conn.execute(
            "SELECT COUNT(*) FROM skill_invocation"
        ).fetchone()[0],
        'total_skills': store.conn.execute(
            "SELECT COUNT(*) FROM skill_metrics"
        ).fetchone()[0],
        'schema_version': store.conn.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()[0],
    }
```

### Performance Metrics

```python
# Track query performance
import time

start = time.time()
metrics = store.get_skill_metrics("crackerjack-run")
duration_ms = (time.time() - start) * 1000

if duration_ms > 100:
    logger.warning(f"Slow query: get_skill_metrics took {duration_ms:.0f}ms")
```

______________________________________________________________________

## Backup & Restore

### Backup Strategy

```bash
# Daily automated backups
sqlite3 .session-buddy/skill_metrics.db ".backup skill_metrics_backup_$(date +%Y%m%d).db"

# Keep last 7 days
find .session-buddy/ -name "skill_metrics_backup_*.db" -mtime +7 -delete
```

### Restore Procedure

```bash
# Stop application
python -m crackerjack stop

# Restore from backup
cp skill_metrics_backup_20250210.db skill_metrics.db

# Verify integrity
sqlite3 skill_metrics.db "PRAGMA integrity_check;"

# Restart application
python -m crackerjack start
```

______________________________________________________________________

## Quick Start Checklist

- [ ] Create `crackerjack/skills/metrics_db.py` with `SkillMetricsStore` class
- [ ] Create `crackerjack/skills/schemas/migrations/` directory
- [ ] Write `V1__initial_schema.sql` migration
- [ ] Implement `MigrationRunner` class
- [ ] Write unit tests for `SkillMetricsStore`
- [ ] Write integration tests for migrations
- [ ] Create dual-write wrapper (`DualWriteMetricsTracker`)
- [ ] Deploy dual-write phase (monitor for 1-2 weeks)
- [ ] Run data migration (1-2 days)
- [ ] Create dual-read wrapper (`DualReadMetricsTracker`)
- [ ] Deploy dual-read phase (monitor for 1 week)
- [ ] Create cutover/rollback scripts
- [ ] Schedule cutover window (1 day)
- [ ] Execute cutover (monitor closely)
- [ ] Keep dual-read for 1 week as safety net
- [ ] Remove legacy JSON code
- [ ] Document operational procedures

______________________________________________________________________

## Summary

**Key Benefits**:

1. **ACID Guarantees**: All mutations atomic and consistent
2. **Concurrent Access**: Multiple readers/writers via WAL mode
3. **Schema Evolution**: Automatic migrations with rollback support
4. **Query Performance**: Indexed queries, materialized views
5. **Data Integrity**: Foreign key constraints, validation
6. **Analytics**: SQL queries, aggregations, timelines

**Estimated Migration Timeline**:

- Dual-write: 1-2 weeks
- Data migration: 1-2 days
- Dual-read validation: 1 week
- Cutover: 1 day
- Cleanup: 1 week later

**Total**: ~4-6 weeks from start to production

**Risk Level**: Medium (mitigated by phased approach, rollback plan)

**Recommendation**: Proceed with migration using dual-write/dual-read pattern for zero-downtime cutover.

______________________________________________________________________

## Document References

- **Schema Design**: `SKILL_METRICS_STORAGE_SCHEMA.md`
- **Transaction Patterns**: `SKILL_METRICS_TRANSACTION_PATTERNS.md`
- **Migration Guide**: `SKILL_METRICS_MIGRATION_GUIDE.md`
- **Implementation Guide**: `SKILL_METRICS_IMPLEMENTATION.md`

**Status**: Ready for implementation review
