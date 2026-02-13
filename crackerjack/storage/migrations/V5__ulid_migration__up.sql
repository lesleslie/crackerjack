-- ULID Migration: Add ULID columns for cross-system correlation
-- Migration: V5__ulid_migration
-- Date: 2026-02-12
-- Description: Add ULID columns alongside existing IDs for zero-downtime migration

-- ============================================================================
-- Phase 1: EXPAND - Add new ULID columns
-- ============================================================================

-- Jobs table expansion
ALTER TABLE jobs ADD COLUMN job_ulid TEXT;
ALTER TABLE jobs ADD COLUMN job_ulid_generated_at TIMESTAMP;

-- Errors table expansion
ALTER TABLE errors ADD COLUMN error_ulid TEXT;
ALTER TABLE errors ADD COLUMN error_ulid_generated_at TIMESTAMP;

-- Hook executions table expansion
ALTER TABLE hook_executions ADD COLUMN hook_ulid TEXT;
ALTER TABLE hook_executions ADD COLUMN hook_ulid_generated_at TIMESTAMP;

-- Test executions table expansion (aggregate)
ALTER TABLE test_executions ADD COLUMN test_ulid TEXT;
ALTER TABLE test_executions ADD COLUMN test_ulid_generated_at TIMESTAMP;

-- Individual test executions table expansion (granular)
ALTER TABLE individual_test_executions ADD COLUMN test_execution_ulid TEXT;
ALTER TABLE individual_test_executions ADD COLUMN test_execution_ulid_generated_at TIMESTAMP;

-- Strategy decisions table expansion
ALTER TABLE strategy_decisions ADD COLUMN decision_ulid TEXT;
ALTER TABLE strategy_decisions ADD COLUMN decision_ulid_generated_at TIMESTAMP;

-- ============================================================================
-- Phase 2: INDEXES - Create indexes for ULID lookups
-- ============================================================================

-- Unique indexes prevent duplicate ULIDs (unlikely but good practice)
CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_ulid
ON jobs(job_ulid);

CREATE UNIQUE INDEX IF NOT EXISTS idx_errors_ulid
ON errors(error_ulid);

CREATE UNIQUE INDEX IF NOT EXISTS idx_hook_executions_ulid
ON hook_executions(hook_ulid);

CREATE UNIQUE INDEX IF NOT EXISTS idx_test_executions_ulid
ON test_executions(test_ulid);

CREATE UNIQUE INDEX IF NOT EXISTS idx_individual_test_executions_ulid
ON individual_test_executions(test_execution_ulid);

CREATE UNIQUE INDEX IF NOT EXISTS idx_strategy_decisions_ulid
ON strategy_decisions(decision_ulid);

-- ============================================================================
-- Phase 3: MIGRATION - Backfill ULIDs (will be done in application code)
-- ============================================================================

-- Backfill happens in Python code to use generate_ulid() function
-- See: crackerjack/services/metrics.py updates

-- ============================================================================
-- Notes:
-- ============================================================================
-- 1. Existing INTEGER id and job_id TEXT remain unchanged (for compatibility)
-- 2. ULID columns are added alongside for dual-write period
-- 3. After verification period (14 days), can switch to ULID as primary
-- 4. Application code updates required to use ULID for new records
-- 5. Foreign key references maintained (job_id still links tables)
-- 6. These indexes enable efficient cross-system correlation queries:
--    - Mahavishnu workflow executions can reference Crackerjack jobs by ULID
--    - Time-ordered queries across systems (ULIDs embed timestamp)
-- 7. Unique constraint ensures no duplicate ULIDs per table
-- ============================================================================
