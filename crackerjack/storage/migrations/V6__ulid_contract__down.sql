-- ULID Contract Rollback: Restore legacy IDs from backup
-- This restores the state before contract migration

-- Step 1: Drop new indexes
DROP INDEX IF EXISTS idx_jobs_job_id;
DROP INDEX IF EXISTS idx_errors_job_id_new;
DROP INDEX IF EXISTS idx_hooks_job_id_new;
DROP INDEX IF EXISTS idx_tests_job_id_new;
DROP INDEX IF EXISTS idx_individual_tests_job_id_new;

-- Step 2: Restore job_id column from job_ulid (ULID)
ALTER TABLE jobs RENAME COLUMN job_id TO job_ulid;

-- Step 3: Make job_ulid nullable again
ALTER TABLE jobs ALTER COLUMN job_ulid DROP NOT NULL;

-- Step 4: Restore job_ulid_generated_at column
ALTER TABLE jobs ADD COLUMN job_ulid_generated_at TIMESTAMP;

-- Step 5: Drop PRIMARY KEY constraint (will be recreated with original schema)
-- Note: SQLite doesn't support DROP PRIMARY KEY directly, need table rebuild
CREATE TABLE jobs_backup (
    job_ulid TEXT PRIMARY KEY,
    job_ulid_generated_at TIMESTAMP,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    status TEXT NOT NULL,
    iterations INTEGER DEFAULT 0,
    ai_agent BOOLEAN DEFAULT 0,
    error_message TEXT,
    metadata TEXT
);

INSERT INTO jobs_backup SELECT job_id, job_ulid_generated_at, start_time, end_time, status, iterations, ai_agent, error_message, metadata FROM jobs;

DROP TABLE jobs;

ALTER TABLE jobs_backup RENAME TO jobs;

-- Step 6: Restore original foreign key indexes
CREATE INDEX IF NOT EXISTS idx_errors_job_id ON errors(job_id);
CREATE INDEX IF NOT EXISTS idx_hooks_job_id ON hook_executions(job_id);
CREATE INDEX IF NOT EXISTS idx_tests_job_id ON test_executions(job_id);
CREATE INDEX IF NOT EXISTS idx_individual_tests_job_id ON individual_test_executions(job_id);
