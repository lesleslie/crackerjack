# Scripts

Automation helpers for reproducible workflows (CI-friendly). Use alongside `tools/` utilities.

- Install dev deps: `uv sync --group dev`
- Run tests locally: `uv run pytest --maxfail=1`

See root `README.md` and `docs/development/` for conventions.

______________________________________________________________________

## Skills Migration Scripts

### migrate_skills_to_sessionbuddy.py

Migrate crackerjack skills metrics from JSON to session-buddy Dhruva database.

**Usage:**

```bash
# Basic migration (default paths)
python -m scripts.migrate_skills_to_sessionbuddy

# With custom paths
python -m scripts.migrate_skills_to_sessionbuddy \
    --json-path /path/to/skill_metrics.json \
    --db-path /path/to/skills.db

# Dry run (validate without making changes)
python -m scripts.migrate_skills_to_sessionbuddy --dry-run
```

**What it does:**

1. Validates JSON structure
1. Backs up existing database (auto-creates `.pre-migration.backup`)
1. Migrates invocations and skills to Dhruva
1. Validates migrated data
1. Provides rollback capability on failure

**Default paths:**

- JSON source: `.crackerjack/skill_metrics.json`
- Database target: `.session-buddy/skills.db`

**Features:**

- ✅ Idempotent (safe to run multiple times)
- ✅ Automatic backup before migration
- ✅ Validation and error handling
- ✅ Dry run mode for testing
- ✅ Rollback support

______________________________________________________________________

### rollback_skills_migration.py

Rollback a migration by restoring from backup.

**Usage:**

```bash
# Rollback to most recent backup
python -m scripts.rollback_skills_migration

# With custom database path
python -m scripts.rollback_skills_migration \
    --db-path /path/to/skills.db
```

**What it does:**

1. Finds most recent backup file (`.pre-migration.backup*`)
1. Prompts for confirmation
1. Replaces current database with backup
1. Logs rollback result

**Safety:**

- ⚠️ Requires confirmation before proceeding
- ✅ Preserves backup file (doesn't delete it)
- ✅ Clear logging of actions taken

______________________________________________________________________

### validate_skills_migration.py

Validate that migration was successful.

**Usage:**

```bash
# Validate migration (default paths)
python -m scripts.validate_skills_migration

# With custom paths
python -m scripts.validate_skills_migration \
    --json-path /path/to/skill_metrics.json \
    --db-path /path/to/skills.db
```

**What it checks:**

- JSON file exists and is valid
- Database exists and is accessible
- Invocation counts match
- All skills from JSON are in database
- No missing data

**Exit codes:**

- `0` - Validation passed
- `1` - Validation failed (see errors)

______________________________________________________________________

## Migration Workflow

### Recommended Process

1. **Dry Run First**

   ```bash
   python -m scripts.migrate_skills_to_sessionbuddy --dry-run
   ```

   Review what will be migrated without making changes.

1. **Perform Migration**

   ```bash
   python -m scripts.migrate_skills_to_sessionbuddy
   ```

   Creates backup automatically, migrates data.

1. **Validate Migration**

   ```bash
   python -m scripts.validate_skills_migration
   ```

   Confirm all data migrated correctly.

1. **Rollback (if needed)**

   ```bash
   python -m scripts.rollback_skills_migration
   ```

   Restore from backup if something went wrong.

______________________________________________________________________

## Troubleshooting

### "JSON file not found"

**Cause**: The `.crackerjack/skill_metrics.json` file doesn't exist.

**Solution**: This is normal if you haven't tracked skills yet. The migration will be skipped.

### "session-buddy not available"

**Cause**: session-buddy package is not installed.

**Solution**: Install session-buddy:

```bash
pip install session-buddy
```

### "Database not found"

**Cause**: The session-buddy database hasn't been created yet.

**Solution**: This is normal for first run. The migration will create the database.

### "Invocation count mismatch"

**Cause**: JSON and database have different numbers of invocations.

**Solution**: Some invocations may have failed validation. Check the warnings in the migration output for details.
