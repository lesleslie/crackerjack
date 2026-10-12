-- UUID7 Contract Rollback
-- Migration: V5__uuid7_contract (down)
-- Date: 2026-10-12
-- Description: Reverse the UUID7 contract migration. Restores the
-- legacy `jobs` schema (INTEGER id + job_id UNIQUE) and drops the
-- new tables (errors, hook_executions, test_executions,
-- individual_test_executions, strategy_decisions).

PRAGMA foreign_keys=off;

-- ============================================================================
-- Drop new tables (cascading FK references)
-- ============================================================================

DROP TABLE IF EXISTS strategy_decisions;
DROP TABLE IF EXISTS individual_test_executions;
DROP TABLE IF EXISTS test_executions;
DROP TABLE IF EXISTS hook_executions;
DROP TABLE IF EXISTS errors;

-- ============================================================================
-- Rebuild jobs with the legacy INTEGER id + UNIQUE job_id shape
-- ============================================================================

CREATE TABLE jobs_legacy (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT UNIQUE NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    status TEXT NOT NULL,
    issue_count INTEGER DEFAULT 0,
    fixes_applied INTEGER DEFAULT 0
);
INSERT INTO jobs_legacy (job_id, start_time, end_time, status, issue_count, fixes_applied)
    SELECT job_id, start_time, end_time, status, issue_count, fixes_applied FROM jobs;
DROP TABLE jobs;
ALTER TABLE jobs_legacy RENAME TO jobs;

CREATE INDEX IF NOT EXISTS idx_agent_executions_job_id ON agent_executions(job_id);
CREATE INDEX IF NOT EXISTS idx_agent_executions_agent_name ON agent_executions(agent_name);
CREATE INDEX IF NOT EXISTS idx_provider_performance_provider_id ON provider_performance(provider_id);

PRAGMA foreign_keys=on;

-- ============================================================================
-- Notes
-- ============================================================================
-- 1. This down migration is a complete schema reversal. After running
--    it, the database state is identical to the pre-V5 schema.
-- 2. The down does NOT restore the V5__ulid_migration / V6__ulid_contract
--    SQL files (those were stand-alone hedge scripts deleted by the
--    V5__uuid7_contract commit, never run).
-- 3. The deleted `crackerjack/services/ulid_generator.py` and
--    `scripts/run_ulid_migration.py` are NOT restored by the down; the
--    up migration is non-reversible for those files (use git to
--    restore if needed).
