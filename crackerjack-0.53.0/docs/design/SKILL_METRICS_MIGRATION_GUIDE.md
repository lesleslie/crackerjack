# Skill Metrics Migration Guide

**Author**: Database Administrator
**Status**: Production Ready
**Last Updated**: 2025-02-10

______________________________________________________________________

## Executive Summary

Complete migration strategy from JSON file storage to ACID-compliant relational database with zero downtime and data integrity guarantees.

______________________________________________________________________

## Migration Strategy Overview

### Phase 1: Dual-Write (Pre-Migration)

**Duration**: 1-2 weeks
**Risk**: Low
**Goal**: Validate new system without affecting production

```python
class DualWriteMetricsTracker:
    """Write to both JSON and database during migration.

    Reads from JSON (source of truth), writes to both.
    Allows validation of database writes before cutover.
    """

    def __init__(
        self,
        json_tracker: SkillMetricsTracker,
        db_store: SkillMetricsStore,
    ):
        self.json_tracker = json_tracker  # Legacy (read/write)
        self.db_store = db_store  # New (write-only)

    def track_invocation(
        self,
        skill_name: str,
        workflow_path: str | None = None,
    ) -> Callable[[], None]:
        """Track invocation, writing to both systems."""

        # Track in legacy system (source of truth)
        json_completer = self.json_tracker.track_invocation(skill_name, workflow_path)

        def dual_completer(
            *,
            completed: bool = True,
            follow_up_actions: list[str] | None = None,
            error_type: str | None = None,
        ) -> None:
            # Complete in both systems
            json_completer(completed=completed, follow_up_actions=follow_up_actions, error_type=error_type)

            try:
                # Track in database (fire-and-forget during migration)
                result = self.db_store.track_invocation(skill_name, workflow_path)
                result.completer(completed=completed, follow_up_actions=follow_up_actions, error_type=error_type)
            except Exception as e:
                # Log but don't fail migration
                logger.warning(f"Database write failed (dual-write phase): {e}")

        return dual_completer

    def get_skill_metrics(self, skill_name: str) -> SkillMetrics | None:
        """Read from JSON (source of truth during migration)."""
        return self.json_tracker.get_skill_metrics(skill_name)

    def get_all_metrics(self) -> dict[str, SkillMetrics]:
        """Read from JSON (source of truth during migration)."""
        return self.json_tracker.get_all_metrics()
```

### Phase 2: Data Migration

**Duration**: 1-2 days
**Risk**: Medium
**Goal**: Migrate all historical data to database

```python
import hashlib
import json
from pathlib import Path

class DataMigrator:
    """Migrate data from JSON files to database."""

    def __init__(
        self,
        json_path: Path,
        db_store: SkillMetricsStore,
        batch_size: int = 1000,
    ):
        self.json_path = json_path
        self.db_store = db_store
        self.batch_size = batch_size

    def migrate_all_data(self) -> dict[str, int]:
        """Migrate all data from JSON to database.

        Returns:
            Dictionary with migration statistics
        """
        # Load JSON data
        data = json.loads(self.json_path.read_text())

        # Migrate invocations first (immutable log)
        invocations_migrated = self._migrate_invocations(data.get('invocations', []))

        # Migrate metrics (aggregates)
        metrics_migrated = self._migrate_metrics(data.get('skills', {}))

        # Validate migration
        validation_errors = self._validate_migration(data)

        return {
            'invocations_migrated': invocations_migrated,
            'metrics_migrated': metrics_migrated,
            'validation_errors': len(validation_errors),
        }

    def _migrate_invocations(self, invocations: list[dict]) -> int:
        """Migrate invocation records in batches.

        Args:
            invocations: List of invocation dictionaries

        Returns:
            Number of invocations migrated
        """
        migrated = 0

        for i in range(0, len(invocations), self.batch_size):
            batch = invocations[i:i + self.batch_size]

            with self.db_store._isolated_transaction('EXCLUSIVE'):
                for inv in batch:
                    try:
                        self.db_store.conn.execute(
                            """
                            INSERT INTO skill_invocation (
                                id, skill_name, invoked_at, workflow_path,
                                completed, duration_seconds, follow_up_actions,
                                error_type, schema_version
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                            """,
                            (
                                inv.get('id') or str(uuid.uuid4()),
                                inv['skill_name'],
                                inv['invoked_at'],
                                inv.get('workflow_path'),
                                inv['completed'],
                                inv.get('duration_seconds'),
                                json.dumps(inv.get('follow_up_actions', [])),
                                inv.get('error_type'),
                            )
                        )
                        migrated += 1
                    except Exception as e:
                        logger.error(f"Failed to migrate invocation: {e}")

            logger.info(f"Migrated batch {i // self.batch_size + 1}, total: {migrated}")

        return migrated

    def _migrate_metrics(self, skills: dict) -> int:
        """Migrate skill metrics.

        Args:
            skills: Dictionary of skill_name -> metrics

        Returns:
            Number of metrics migrated
        """
        migrated = 0

        for skill_name, skill_data in skills.items():
            try:
                # Remove computed fields before migrating
                skill_data.pop('completion_rate', None)
                skill_data.pop('avg_duration_seconds', None)

                self.db_store.conn.execute(
                    """
                    INSERT INTO skill_metrics (
                        skill_name, total_invocations, completed_invocations,
                        abandoned_invocations, total_duration_seconds,
                        workflow_paths, common_errors, follow_up_actions,
                        first_invoked, last_invoked, schema_version
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    ON CONFLICT(skill_name) DO NOTHING
                    """,
                    (
                        skill_name,
                        skill_data['total_invocations'],
                        skill_data['completed_invocations'],
                        skill_data['abandoned_invocations'],
                        skill_data['total_duration_seconds'],
                        json.dumps(skill_data.get('workflow_paths', {})),
                        json.dumps(skill_data.get('common_errors', {})),
                        json.dumps(skill_data.get('follow_up_actions', {})),
                        skill_data.get('first_invoked'),
                        skill_data.get('last_invoked'),
                    )
                )
                migrated += 1
            except Exception as e:
                logger.error(f"Failed to migrate metrics for {skill_name}: {e}")

        return migrated

    def _validate_migration(self, original_data: dict) -> list[str]:
        """Validate migrated data matches original.

        Args:
            original_data: Original JSON data

        Returns:
            List of validation errors
        """
        errors = []

        # Validate invocation counts
        original_count = len(original_data.get('invocations', []))
        db_count = self.db_store.conn.execute(
            "SELECT COUNT(*) FROM skill_invocation"
        ).fetchone()[0]

        if original_count != db_count:
            errors.append(f"Invocation count mismatch: JSON={original_count}, DB={db_count}")

        # Validate metrics
        for skill_name, skill_data in original_data.get('skills', {}).items():
            db_metrics = self.db_store.get_skill_metrics(skill_name)

            if not db_metrics:
                errors.append(f"Missing metrics for skill: {skill_name}")
                continue

            # Validate counts
            if skill_data['total_invocations'] != db_metrics['total_invocations']:
                errors.append(
                    f"Count mismatch for {skill_name}: "
                    f"JSON={skill_data['total_invocations']}, "
                    f"DB={db_metrics['total_invocations']}"
                )

        return errors
```

### Phase 3: Dual-Read Validation

**Duration**: 1 week
**Risk**: Low
**Goal**: Validate database reads match JSON reads

```python
class DualReadMetricsTracker:
    """Read from both systems, validate consistency.

    Reads from database, validates against JSON.
    Catches any data inconsistencies before cutover.
    """

    def __init__(
        self,
        json_tracker: SkillMetricsTracker,
        db_store: SkillMetricsStore,
    ):
        self.json_tracker = json_tracker  # Legacy (validation only)
        self.db_store = db_store  # New (primary)

    def get_skill_metrics(self, skill_name: str) -> SkillMetrics | None:
        """Get metrics from database, validate against JSON."""
        db_metrics = self.db_store.get_skill_metrics(skill_name)
        json_metrics = self.json_tracker.get_skill_metrics(skill_name)

        # Validate consistency
        if db_metrics and json_metrics:
            self._validate_metrics_consistency(skill_name, db_metrics, json_metrics)

        return db_metrics

    def _validate_metrics_consistency(
        self,
        skill_name: str,
        db_metrics: dict,
        json_metrics: SkillMetrics,
    ) -> None:
        """Validate database metrics match JSON metrics.

        Logs warnings for any inconsistencies.
        """
        if db_metrics['total_invocations'] != json_metrics.total_invocations:
            logger.warning(
                f"Inconsistent invocation count for {skill_name}: "
                f"DB={db_metrics['total_invocations']}, "
                f"JSON={json_metrics.total_invocations}"
            )

        if abs(db_metrics['completion_rate'] - json_metrics.completion_rate()) > 0.01:
            logger.warning(
                f"Inconsistent completion rate for {skill_name}: "
                f"DB={db_metrics['completion_rate']:.2f}, "
                f"JSON={json_metrics.completion_rate():.2f}"
            )
```

### Phase 4: Cutover

**Duration**: 1 day
**Risk**: High (rollback plan required)
**Goal**: Switch to database as source of truth

**Cutover Checklist**:

```bash
#!/bin/bash
# cutover_to_database.sh

set -e

echo "=== Skill Metrics Database Cutover ==="

# 1. Stop crackerjack services
echo "Stopping crackerjack services..."
python -m crackerjack stop

# 2. Final data sync
echo "Running final data sync..."
python scripts/migrate_metrics_data.py --final

# 3. Validate migration
echo "Validating migration..."
python scripts/validate_migration.py

# 4. Backup JSON files
echo "Backing up JSON files..."
cp .session-buddy/skill_metrics.json .session-buddy/skill_metrics.json.backup

# 5. Update configuration
echo "Updating configuration..."
# Set USE_DATABASE_METRICS=true in settings

# 6. Start crackerjack services
echo "Starting crackerjack services..."
python -m crackerjack start

# 7. Health check
echo "Running health check..."
python -m crackerjack health

echo "=== Cutover Complete ==="
echo "Monitor logs for any issues. Rollback script: rollback_to_json.sh"
```

**Rollback Plan**:

```bash
#!/bin/bash
# rollback_to_json.sh

set -e

echo "=== Rolling Back to JSON Storage ==="

# 1. Stop crackerjack services
python -m crackerjack stop

# 2. Restore JSON backup
cp .session-buddy/skill_metrics.json.backup .session-buddy/skill_metrics.json

# 3. Update configuration
# Set USE_DATABASE_METRICS=false in settings

# 4. Start crackerjack services
python -m crackerjack start

echo "=== Rollback Complete ==="
```

### Phase 5: Cleanup

**Duration**: 1 week after cutover
**Risk**: Low
**Goal**: Remove legacy JSON code

```python
# Remove after successful cutover + 1 week of monitoring

# DELETE: crackerjack/skills/metrics.py (old JSON implementation)
# KEEP: crackerjack/skills/metrics_db.py (new database implementation)
# DELETE: .session-buddy/skill_metrics.json (after backup confirmed)
```

______________________________________________________________________

## Schema Migration System

### Migration Runner

```python
import hashlib
from pathlib import Path
from typing import Optional

class MigrationRunner:
    """Run database schema migrations."""

    def __init__(self, db_path: str, migrations_dir: Path):
        self.db_path = db_path
        self.migrations_dir = migrations_dir
        self.conn = sqlite3.connect(db_path)

    def run_migrations(self) -> None:
        """Run all pending migrations."""
        self._ensure_migrations_table()

        pending = self._get_pending_migrations()

        if not pending:
            print("No pending migrations")
            return

        print(f"Running {len(pending)} pending migrations...")

        for migration_file in pending:
            self._run_migration(migration_file)

        print("All migrations complete")

    def _ensure_migrations_table(self) -> None:
        """Create schema_migrations table if not exists."""
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP NOT NULL DEFAULT (datetime('now')),
                description TEXT NOT NULL,
                checksum TEXT,
                rollback_sql TEXT,
                migration_time_ms REAL
            )
            """
        )

    def _get_pending_migrations(self) -> list[Path]:
        """Get list of pending migration files."""
        # Get current version
        cursor = self.conn.execute(
            "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
        )
        current_version = cursor.fetchone()[0]

        # Find migration files
        migration_files = sorted(self.migrations_dir.glob("V*.sql"))

        # Filter out already applied migrations
        pending = [
            f for f in migration_files
            if int(f.stem.split('__')[0][1:]) > current_version
        ]

        return pending

    def _run_migration(self, migration_file: Path) -> None:
        """Run a single migration file.

        Args:
            migration_file: Path to migration SQL file
        """
        # Parse migration metadata
        stem = migration_file.stem  # e.g., "V2__add_success_rate_field"
        version = int(stem.split('__')[0][1:])
        description = stem.split('__', 1)[1].replace('_', ' ')

        print(f"Running migration V{version}: {description}")

        # Read migration SQL
        sql = migration_file.read_text()

        # Split into forward and rollback migrations
        parts = sql.split('-- Rollback migration')
        forward_sql = parts[0]
        rollback_sql = parts[1] if len(parts) > 1 else None

        # Calculate checksum
        checksum = hashlib.sha256(forward_sql.encode()).hexdigest()

        # Run migration
        start_time = time.time()

        try:
            with self._isolated_transaction():
                # Execute migration SQL
                self.conn.executescript(forward_sql)

                # Record migration
                migration_time = (time.time() - start_time) * 1000
                self.conn.execute(
                    """
                    INSERT INTO schema_migrations (
                        version, description, checksum, rollback_sql, migration_time_ms
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (version, description, checksum, rollback_sql, migration_time)
                )

            print(f"  ✓ Completed in {migration_time:.0f}ms")

        except Exception as e:
            print(f"  ✗ Failed: {e}")
            raise

    def rollback_migration(self, version: int) -> None:
        """Rollback a specific migration.

        Args:
            version: Migration version to rollback
        """
        # Get migration record
        cursor = self.conn.execute(
            "SELECT rollback_sql FROM schema_migrations WHERE version = ?",
            (version,)
        )
        row = cursor.fetchone()

        if not row:
            raise ValueError(f"Migration {version} not found")

        rollback_sql = row[0]

        if not rollback_sql:
            raise ValueError(f"Migration {version} has no rollback SQL")

        print(f"Rolling back migration V{version}...")

        try:
            with self._isolated_transaction():
                self.conn.executescript(rollback_sql)
                self.conn.execute("DELETE FROM schema_migrations WHERE version = ?", (version,))

            print(f"  ✓ Rollback complete")

        except Exception as e:
            print(f"  ✗ Rollback failed: {e}")
            raise

    @contextmanager
    def _isolated_transaction(self):
        """Context manager for isolated transactions."""
        try:
            self.conn.execute("BEGIN EXCLUSIVE TRANSACTION")
            yield self.conn
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
```

### Example Migration Files

**`migrations/V1__initial_schema.sql`**:

```sql
-- V1__initial_schema.sql
-- Description: Create initial skill metrics schema

BEGIN TRANSACTION;

-- Create skill_invocation table
CREATE TABLE skill_invocation (
    id TEXT PRIMARY KEY,
    skill_name TEXT NOT NULL,
    invoked_at TIMESTAMP NOT NULL DEFAULT (datetime('now')),
    workflow_path TEXT,
    completed BOOLEAN NOT NULL DEFAULT 0,
    duration_seconds REAL,
    error_type TEXT,
    session_id TEXT,
    follow_up_actions JSON,
    schema_version INTEGER NOT NULL DEFAULT 1,
    project_path TEXT,
    user_context JSON,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE SET NULL
);

-- Create indexes
CREATE INDEX idx_skill_invocation_skill_name ON skill_invocation(skill_name);
CREATE INDEX idx_skill_invocation_invoked_at ON skill_invocation(invoked_at DESC);
CREATE INDEX idx_skill_invocation_session_id ON skill_invocation(session_id);
CREATE INDEX idx_skill_invocation_completed ON skill_invocation(completed);
CREATE INDEX idx_skill_invocation_skill_time ON skill_invocation(skill_name, invoked_at DESC);

-- Create skill_metrics table
CREATE TABLE skill_metrics (
    skill_name TEXT PRIMARY KEY,
    total_invocations INTEGER NOT NULL DEFAULT 0,
    completed_invocations INTEGER NOT NULL DEFAULT 0,
    abandoned_invocations INTEGER NOT NULL DEFAULT 0,
    total_duration_seconds REAL NOT NULL DEFAULT 0.0,
    min_duration_seconds REAL,
    max_duration_seconds REAL,
    p50_duration_seconds REAL,
    p95_duration_seconds REAL,
    p99_duration_seconds REAL,
    workflow_paths JSON NOT NULL DEFAULT '{}',
    common_errors JSON NOT NULL DEFAULT '{}',
    follow_up_actions JSON NOT NULL DEFAULT '{}',
    first_invoked TIMESTAMP,
    last_invoked TIMESTAMP,
    completion_rate REAL,
    avg_duration_seconds REAL,
    schema_version INTEGER NOT NULL DEFAULT 1,
    last_aggregated_at TIMESTAMP DEFAULT (datetime('now'))
);

-- Create session_skill table
CREATE TABLE session_skill (
    id TEXT PRIMARY KEY,
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

-- Create triggers
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

-- Create materialized view
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

-- Create schema_migrations table
CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP NOT NULL DEFAULT (datetime('now')),
    description TEXT NOT NULL,
    checksum TEXT,
    rollback_sql TEXT,
    migration_time_ms REAL
);

-- Record initial migration
INSERT INTO schema_migrations (version, description, checksum)
VALUES (1, 'Initial skill metrics schema', '<sha256>');

COMMIT;

-- Rollback migration
-- ROLLBACK;
-- DROP TABLE IF EXISTS skill_metrics_summary;
-- DROP TABLE IF EXISTS session_skill;
-- DROP TRIGGER IF EXISTS trg_session_skill_update;
-- DROP TRIGGER IF EXISTS trg_skill_metrics_update_computed;
-- DROP TABLE IF EXISTS skill_metrics;
-- DROP TABLE IF EXISTS skill_invocation;
-- DROP TABLE IF EXISTS schema_migrations;
```

**`migrations/V2__add_percentile_fields.sql`**:

```sql
-- V2__add_percentile_fields.sql
-- Description: Add duration percentile tracking

BEGIN TRANSACTION;

-- Add percentile columns
ALTER TABLE skill_metrics ADD COLUMN p50_duration_seconds REAL;
ALTER TABLE skill_metrics ADD COLUMN p95_duration_seconds REAL;
ALTER TABLE skill_metrics ADD COLUMN p99_duration_seconds REAL;

-- Update schema version for existing records
UPDATE skill_metrics SET schema_version = 2;

-- Record migration
INSERT INTO schema_migrations (version, description, checksum)
VALUES (2, 'Add duration percentile fields', '<sha256>');

COMMIT;

-- Rollback migration
-- ROLLBACK;
-- UPDATE skill_metrics SET schema_version = 1;
-- ALTER TABLE skill_metrics DROP COLUMN p99_duration_seconds;
-- ALTER TABLE skill_metrics DROP COLUMN p95_duration_seconds;
-- ALTER TABLE skill_metrics DROP COLUMN p50_duration_seconds;
-- DELETE FROM schema_migrations WHERE version = 2;
```

______________________________________________________________________

## Summary

**Migration Phases**:

1. **Dual-Write** (1-2 weeks): Write to both systems, read from JSON
1. **Data Migration** (1-2 days): Bulk migrate historical data
1. **Dual-Read Validation** (1 week): Read from DB, validate against JSON
1. **Cutover** (1 day): Switch to DB as source of truth
1. **Cleanup** (1 week): Remove legacy JSON code

**Key Principles**:

- Zero downtime (dual-write/dual-read)
- Data validation at each phase
- Rollback plan always ready
- Gradual cutover with monitoring
- Backward compatibility maintained

**Risk Mitigation**:

- Dual-write validates DB writes before cutover
- Dual-read catches data inconsistencies early
- Automated rollback scripts for quick recovery
- JSON backup kept until after cleanup
- Health checks at each phase

**Next Steps**:

1. Create migration directory structure
1. Implement `MigrationRunner` class
1. Write dual-write/dual-read wrappers
1. Create cutover/rollback scripts
1. Document runbook for operations team
