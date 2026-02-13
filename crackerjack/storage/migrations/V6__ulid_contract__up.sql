-- ULID Contract Migration: Drop legacy IDs, make ULIDs primary
-- This is the CONTRACT phase of expand-contract migration
-- After this migration, all foreign keys and indexes should use ULID

-- Jobs table: Drop legacy job_id, make job_ulid NOT NULL
-- Step 1: Drop foreign key constraints that reference job_id
PRAGMA foreign_keys=off;  -- Disable foreign keys temporarily

-- Step 2: Migrate any remaining NULL job_ulid values (shouldn't be any, but safety check)
UPDATE jobs SET job_ulid = 'fallback_' || substr(hex(randomblob(16)), 1, 26) WHERE job_ulid IS NULL;

-- Step 3: Make job_ulid NOT NULL
ALTER TABLE jobs ALTER COLUMN job_ulid SET NOT NULL;

-- Step 4: Drop job_id column (legacy identifier)
ALTER TABLE jobs DROP COLUMN job_id;

-- Step 5: Rename job_ulid to job_id (become primary identifier)
ALTER TABLE jobs ALTER COLUMN job_ulid RENAME TO job_id;

-- Step 6: Make job_id PRIMARY KEY
CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_job_id ON jobs(job_id);

-- Step 7: Update dependent tables to use new job_id (ULID)
-- Errors table
DROP INDEX IF EXISTS idx_errors_job_id;
CREATE INDEX IF NOT EXISTS idx_errors_job_id ON errors(job_id);

-- Hook executions table
DROP INDEX IF EXISTS idx_hooks_job_id;
CREATE INDEX IF NOT EXISTS idx_hooks_job_id ON hook_executions(job_id);

-- Test executions table
DROP INDEX IF EXISTS idx_tests_job_id;
CREATE INDEX IF NOT EXISTS idx_tests_job_id ON test_executions(job_id);

-- Individual test executions table
DROP INDEX IF EXISTS idx_individual_tests_job_id;
CREATE INDEX IF NOT EXISTS idx_individual_tests_job_id ON individual_test_executions(job_id);

-- Step 8: Re-enable foreign keys
PRAGMA foreign_keys=on;

-- Step 9: Drop timestamp columns (no longer needed with ULID as sortable ID)
ALTER TABLE jobs DROP COLUMN job_ulid_generated_at;
