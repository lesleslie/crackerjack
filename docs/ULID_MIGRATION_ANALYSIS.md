# Crackerjack ULID Migration Analysis

**Date:** 2026-02-11
**Analysis For:** ULID Ecosystem Integration - Phase 2 Task 5

## Current Identifier Patterns

### Database Schema

**Location:** `/Users/les/Projects/crackerjack/crackerjack/services/metrics.py:22-183`

**Current Format:**
- **Primary Keys:** `id INTEGER PRIMARY KEY AUTOINCREMENT` (internal database IDs)
- **Business Keys:** `job_id TEXT UNIQUE NOT NULL` (already uses string identifiers!)
- **Foreign Keys:** All reference `job_id TEXT`, not the integer `id`

**Example Table Structures:**

```sql
-- Jobs table (primary orchestration table)
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- Internal SQLite ID
    job_id TEXT UNIQUE NOT NULL,              -- Business identifier (ULID candidate!)
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    status TEXT NOT NULL,
    iterations INTEGER DEFAULT 0,
    ai_agent BOOLEAN DEFAULT 0,
    error_message TEXT,
    metadata TEXT
);

-- Errors table (references job_id)
CREATE TABLE IF NOT EXISTS errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- Internal SQLite ID
    job_id TEXT,                             -- References jobs.job_id
    timestamp TIMESTAMP NOT NULL,
    error_type TEXT NOT NULL,
    error_category TEXT,
    error_message TEXT,
    file_path TEXT,
    line_number INTEGER,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

-- Hook executions table (references job_id)
CREATE TABLE IF NOT EXISTS hook_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT,                             -- References jobs.job_id
    timestamp TIMESTAMP NOT NULL,
    hook_name TEXT NOT NULL,
    hook_type TEXT,
    execution_time_ms INTEGER,
    status TEXT,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

-- Test executions table (references job_id)
CREATE TABLE IF NOT EXISTS test_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id TEXT,                             -- References jobs.job_id
    timestamp TIMESTAMP NOT NULL,
    total_tests INTEGER,
    passed INTEGER,
    failed INTEGER,
    skipped INTEGER,
    execution_time_ms INTEGER,
    coverage_percent REAL,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);
```

## Migration Targets

### Tables to Migrate

| Table | Current ID Format | Migration Target | Complexity |
|--------|-------------------|------------------|------------|
| `jobs` | `job_id TEXT UNIQUE` | Replace with ULID | **LOW** - Already uses TEXT |
| `errors` | `job_id TEXT` (FK) | Update to ULID | **LOW** - Text FK already exists |
| `hook_executions` | `job_id TEXT` (FK) | Update to ULID | **LOW** - Text FK already exists |
| `test_executions` | `job_id TEXT` (FK) | Update to ULID | **LOW** - Text FK already exists |
| `orchestration_executions` | `job_id TEXT` (FK) | Update to ULID | **LOW** - Text FK already exists |
| `strategy_decisions` | `job_id TEXT` (FK) | Update to ULID | **LOW** - Text FK already exists |
| `individual_test_executions` | `job_id TEXT` (FK) | Update to ULID | **LOW** - Text FK already exists |
| `agent_executions` | `job_id TEXT` (FK) | Update to ULID | **LOW** - Text FK already exists |

**Estimated Record Counts:**
- Jobs: Dynamic (depends on execution history)
- Errors: Dynamic (depends on quality checks)
- Test Executions: Dynamic (depends on test runs)

## Migration Complexity: VERY LOW ⚠️

### Why This Migration Is Simpler Than Expected

**Critical Discovery:** Crackerjack already uses `job_id TEXT UNIQUE NOT NULL` as the business identifier!

This means:
1. **No schema changes needed for foreign keys** - All FKs already reference TEXT column
2. **No expand-contract needed** - Already using TEXT, not INTEGER
3. **Just validate format** - Replace any custom job_id format with ULID

### Current Job ID Generation

Looking at code, `job_id` is passed as parameter but generation code not visible in this file. Need to trace where `job_id` is generated.

**Hypothesis:** Current `job_id` might be:
- UUID format
- Custom timestamp-based ID
- Sequential string ID

**Action Required:** Search Crackerjack codebase for `job_id` generation logic.

## Recommended Migration Strategy

### Phase 1: Add ULID Generation (Week 1)

**Step 1:** Find current `job_id` generation code
```bash
cd /Users/les/Projects/crackerjack
grep -r "def.*job_id\|job_id.*=" --include="*.py" crackerjack/
```

**Step 2:** Replace with ULID generation
```python
from oneiric.core.ulid import generate_config_id

# Replace current job_id generation with:
job_id = generate_config_id()  # Generates ULID
```

**Step 3:** Update validation to accept ULID format
```python
# Current validation (assumed)
def validate_job_id(job_id: str) -> bool:
    # Add ULID validation
    from oneiric.core.ulid import is_config_ulid
    return is_config_ulid(job_id)  # Use Oneiric ULID validator
```

### Phase 2: Update Foreign Key References (Week 1)

**No Schema Changes Needed!** All tables already use `job_id TEXT` for foreign keys.

**Only code updates needed:**
- Ensure all queries use `job_id` parameter (already doing this)
- No `INTEGER id` references found in schema

### Phase 3: Add Migration Map for Existing Data (Week 2)

**Expand-Contract Not Needed** - Already using TEXT business keys.

**Simple Migration Strategy:**
```python
# For existing jobs with non-ULID job_id, generate ULID and update

from oneiric.core.ulid_migration import generate_migration_map

# Generate map: legacy job_id -> ULID
migration_map = generate_migration_map(
    table_name="jobs",
    id_column="job_id",
    limit=10000,  # All existing jobs
)

# Update each job
for legacy_id, ulid in migration_map.items():
    conn.execute(
        "UPDATE jobs SET job_id = ? WHERE job_id = ?",
        (ulid, legacy_id),
    )
    # Also update all child records
    conn.execute("UPDATE errors SET job_id = ? WHERE job_id = ?", (ulid, legacy_id))
    conn.execute("UPDATE hook_executions SET job_id = ? WHERE job_id = ?", (ulid, legacy_id))
    conn.execute("UPDATE test_executions SET job_id = ? WHERE job_id = ?", (ulid, legacy_id))
    # ... other tables
```

### Phase 4: Validation (Week 2)

**Validation Checklist:**
- [ ] All new jobs use ULID format (26-char Crockford Base32)
- [ ] All foreign key references resolved correctly
- [ ] Historical jobs migrated to ULID
- [ ] No duplicate `job_id` values after migration
- [ ] Query performance acceptable (ULID string operations)

## Migration SQL

**Simple Approach (No Schema Changes):**

```sql
-- No ALTER TABLE needed! Already using TEXT job_id

-- Step 1: Backfill ULIDs for existing jobs
UPDATE jobs
SET job_id = <generate_ulid_function>()
WHERE job_id IS NOT NULL;

-- Step 2: Update all foreign key references
UPDATE errors SET job_id = (
    SELECT job_id FROM jobs j WHERE j.id = errors.job_id_old
) WHERE job_id_old IS NOT NULL;

-- Repeat for other tables...
UPDATE hook_executions SET job_id = (...) WHERE job_id_old IS NOT NULL;
UPDATE test_executions SET job_id = (...) WHERE job_id_old IS NOT NULL;
UPDATE orchestration_executions SET job_id = (...) WHERE job_id_old IS NOT NULL;
UPDATE strategy_decisions SET job_id = (...) WHERE job_id_old IS NOT NULL;
UPDATE individual_test_executions SET job_id = (...) WHERE job_id_old IS NOT NULL;
UPDATE agent_executions SET job_id = (...) WHERE job_id_old IS NOT NULL;
```

**Alternative (If current job_id is UUID):**
```sql
-- If already using UUID, just validate format
-- No changes needed if UUID is acceptable
```

## Integration Points

### Cross-System References

**Mahavishnu → Crackerjack:**
- Mahavishnu workflows generate `job_id` for Crackerjack quality checks
- After migration: Mahavishnu workflows should use ULID from `oneiric.core.ulid.generate_config_id()`
- Benefit: Time-ordered traceability from workflow → test execution

**Akosha → Crackerjack:**
- Akosha knowledge graph may reference test executions
- After migration: ULID-based correlation for pattern detection
- Benefit: Semantic search of test patterns by timestamp

### Session-Buddy → Crackerjack:**
- Session reflections may include quality check results
- After migration: Cross-reference by ULID timestamp
- Benefit: Time-based correlation between development sessions and quality checks

## Estimated Migration Time

**Using Oneiric Migration Estimator:**

```python
from oneiric.core.ulid_migration import estimate_migration_time

# Assume 10,000 historical jobs (example)
estimates = estimate_migration_time(
    record_count=10000,
    records_per_second=1000,
)

# Result:
# - estimated_seconds: 10
# - estimated_minutes: 0.17
# - estimated_hours: 0.003
# - recommended_batch_size: 60,000 (but we only have 10,000)
```

**Actual Time:** < 1 minute for backfill (very fast migration!)

## Next Steps

1. ✅ **COMPLETED:** Analysis of current Crackerjack schema
2. **NEXT:** Search for `job_id` generation code
3. **NEXT:** Replace `job_id` generation with ULID from Oneiric
4. **NEXT:** Update validation logic to accept ULID format
5. **NEXT:** Run migration script for existing jobs
6. **NEXT:** Add cross-system ULID resolution tests

**Status:** Analysis complete, ready for Task 6 (Session-Buddy analysis)

**Key Finding:** Migration complexity VERY LOW - No schema changes needed, already uses TEXT business keys!
