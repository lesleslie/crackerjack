-- ULID Migration Rollback
-- Migration: V5__ulid_migration
-- Description: Rollback ULID migration if needed

-- ============================================================================
-- Rollback: Remove ULID columns
-- ============================================================================

-- Jobs table rollback
ALTER TABLE jobs DROP COLUMN job_ulid;
ALTER TABLE jobs DROP COLUMN job_ulid_generated_at;

-- Errors table rollback
ALTER TABLE errors DROP COLUMN error_ulid;
ALTER TABLE errors DROP COLUMN error_ulid_generated_at;

-- Hook executions table rollback
ALTER TABLE hook_executions DROP COLUMN hook_ulid;
ALTER TABLE hook_executions DROP COLUMN hook_ulid_generated_at;

-- Test executions table rollback (aggregate)
ALTER TABLE test_executions DROP COLUMN test_ulid;
ALTER TABLE test_executions DROP COLUMN test_ulid_generated_at;

-- Individual test executions table rollback (granular)
ALTER TABLE individual_test_executions DROP COLUMN test_execution_ulid;
ALTER TABLE individual_test_executions DROP COLUMN test_execution_ulid_generated_at;

-- Strategy decisions table rollback
ALTER TABLE strategy_decisions DROP COLUMN decision_ulid;
ALTER TABLE strategy_decisions DROP COLUMN decision_ulid_generated_at;

-- ============================================================================
-- Rollback: Drop ULID indexes
-- ============================================================================

DROP INDEX IF EXISTS idx_jobs_ulid;
DROP INDEX IF EXISTS idx_errors_ulid;
DROP INDEX IF EXISTS idx_hook_executions_ulid;
DROP INDEX IF EXISTS idx_test_executions_ulid;
DROP INDEX IF EXISTS idx_individual_test_executions_ulid;
DROP INDEX IF EXISTS idx_strategy_decisions_ulid;

-- ============================================================================
-- Notes:
-- ============================================================================
-- 1. Restores database to pre-migration state
-- 2. INTEGER id and job_id TEXT remain active identifiers
-- 3. Application code changes must be reverted to remove ULID generation
-- 4. Data backfilled during migration remains in ULID columns
-- 5. Safe to run during maintenance window with no active CI/CD jobs
-- 6. Foreign key references preserved (job_id still links tables)
-- ============================================================================
