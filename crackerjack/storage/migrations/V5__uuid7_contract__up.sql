-- UUID7 Contract Migration
-- Migration: V5__uuid7_contract
-- Date: 2026-10-12
-- Description: Establish UUID7 (RFC 9562) as the canonical ID substrate
-- for all crackerjack entities. Replaces the legacy INTEGER surrogate
-- keys and the dropped V5/V6 ULID hedge migrations (V5__ulid_migration
-- and V6__ulid_contract) with a single UUID7-native contract.
--
-- Assumptions:
--   1. The base schema (agent_executions, provider_performance, jobs)
--      was created by crackerjack.services.metrics.MetricsCollector
--      on first connection. INTEGER id and job_id TEXT UNIQUE NOT NULL
--      exist on `jobs`.
--   2. SQLite supports `PRAGMA foreign_keys = off` for table rebuilds
--      and back on afterwards.
--
-- Effect:
--   * jobs.id (INTEGER surrogate) is dropped; jobs.job_id (TEXT) becomes
--     the PRIMARY KEY, holding a UUID7 32-hex string.
--   * New tables (errors, hook_executions, test_executions,
--     individual_test_executions, strategy_decisions) are created with
--     UUID7 PKs.
--   * FKs from new tables reference jobs.job_id.

-- ============================================================================
-- Phase 1: rebuild jobs with UUID7 PK
-- ============================================================================

PRAGMA foreign_keys=off;

-- Rebuild jobs: drop INTEGER id, make job_id the PRIMARY KEY.
CREATE TABLE jobs_new (
    job_id TEXT PRIMARY KEY,                  -- UUID7 32-hex
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    status TEXT NOT NULL,
    issue_count INTEGER DEFAULT 0,
    fixes_applied INTEGER DEFAULT 0
);
INSERT INTO jobs_new (job_id, start_time, end_time, status, issue_count, fixes_applied)
    SELECT job_id, start_time, end_time, status, issue_count, fixes_applied FROM jobs;
DROP TABLE jobs;
ALTER TABLE jobs_new RENAME TO jobs;

-- Recreate indexes on the rebuilt jobs table.
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_start_time ON jobs(start_time);

-- ============================================================================
-- Phase 2: errors (UUID7 PK)
-- ============================================================================

CREATE TABLE IF NOT EXISTS errors (
    error_id TEXT PRIMARY KEY,                -- UUID7 32-hex
    job_id TEXT NOT NULL,                    -- FK -> jobs.job_id
    error_type TEXT NOT NULL,
    error_message TEXT,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);
CREATE INDEX IF NOT EXISTS idx_errors_job_id ON errors(job_id);
CREATE INDEX IF NOT EXISTS idx_errors_timestamp ON errors(timestamp);

-- ============================================================================
-- Phase 3: hook_executions (UUID7 PK)
-- ============================================================================

CREATE TABLE IF NOT EXISTS hook_executions (
    hook_id TEXT PRIMARY KEY,                -- UUID7 32-hex
    job_id TEXT NOT NULL,
    hook_name TEXT NOT NULL,
    status TEXT NOT NULL,
    execution_time_ms REAL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);
CREATE INDEX IF NOT EXISTS idx_hook_executions_job_id ON hook_executions(job_id);
CREATE INDEX IF NOT EXISTS idx_hook_executions_hook_name ON hook_executions(hook_name);

-- ============================================================================
-- Phase 4: test_executions (UUID7 PK)
-- ============================================================================

CREATE TABLE IF NOT EXISTS test_executions (
    test_id TEXT PRIMARY KEY,                -- UUID7 32-hex
    job_id TEXT NOT NULL,
    test_file TEXT NOT NULL,
    test_name TEXT NOT NULL,
    status TEXT NOT NULL,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);
CREATE INDEX IF NOT EXISTS idx_test_executions_job_id ON test_executions(job_id);
CREATE INDEX IF NOT EXISTS idx_test_executions_test_file ON test_executions(test_file);

-- ============================================================================
-- Phase 5: individual_test_executions (UUID7 PK, FK -> test_executions)
-- ============================================================================

CREATE TABLE IF NOT EXISTS individual_test_executions (
    execution_id TEXT PRIMARY KEY,           -- UUID7 32-hex
    test_execution_id TEXT NOT NULL,         -- FK -> test_executions.test_id
    test_name TEXT NOT NULL,
    status TEXT NOT NULL,
    duration_ms REAL,
    error_message TEXT,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (test_execution_id) REFERENCES test_executions(test_id)
);
CREATE INDEX IF NOT EXISTS idx_individual_test_executions_test_execution_id
    ON individual_test_executions(test_execution_id);
CREATE INDEX IF NOT EXISTS idx_individual_test_executions_status
    ON individual_test_executions(status);

-- ============================================================================
-- Phase 6: strategy_decisions (UUID7 PK)
-- ============================================================================

CREATE TABLE IF NOT EXISTS strategy_decisions (
    decision_id TEXT PRIMARY KEY,            -- UUID7 32-hex
    job_id TEXT NOT NULL,
    strategy TEXT NOT NULL,
    rationale TEXT,
    timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);
CREATE INDEX IF NOT EXISTS idx_strategy_decisions_job_id ON strategy_decisions(job_id);
CREATE INDEX IF NOT EXISTS idx_strategy_decisions_strategy ON strategy_decisions(strategy);

-- ============================================================================
-- Phase 7: re-enable foreign keys
-- ============================================================================

PRAGMA foreign_keys=on;

-- ============================================================================
-- Notes
-- ============================================================================
-- 1. UUID7 (RFC 9562 sec 5.7) gives time-ordered, globally-unique 32-hex
--    identifiers. Application code emits them via `from uuid import uuid7;
--    uuid7().hex` (or `oneiric.core.ids.generate_id()` in downstream repos).
-- 2. The legacy V5__ulid_migration / V6__ulid_contract SQL files have
--    been removed; this V5 supersedes both. The down migration recreates
--    the original `jobs` schema (INTEGER id + job_id UNIQUE) and drops
--    the new tables; it does NOT restore the deleted V5/V6 SQL files
--    (those were stand-alone hedge scripts, never run).
-- 3. agent_executions and provider_performance were unaffected by the
--    V5/V6 hedge; they continue to use their existing INTEGER id PKs
--    and reference jobs by job_id (now UUID7).
-- 4. The down migration is a complete schema reversal -- safe to run
--    after up; idempotency guarded by IF NOT EXISTS / IF EXISTS guards.
