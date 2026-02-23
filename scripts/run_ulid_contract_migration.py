#!/usr/bin/env python3

import sqlite3
import sys
from pathlib import Path


def get_db_path():
    db_dir = Path.home() / ".cache" / "crackerjack"
    return db_dir / "metrics.db"


def run_contract_migration():

    print("=" * 60)
    print("Crackerjack ULID Contract Migration")
    print("=" * 60)
    print()
    print("⚠️  DEV/TEST MODE - Skipping verification period")
    print("   Contracting: Dropping legacy IDs, making ULIDs primary")
    print()

    db_path = get_db_path()

    if not db_path.exists():
        print(f"   ⚠️  Database not found at {db_path}")
        print("   No migration needed")
        return


    migration_sql_path = (
        Path(__file__).parent.parent
        / "crackerjack"
        / "storage"
        / "migrations"
        / "V6__ulid_contract__up.sql"
    )

    if not migration_sql_path.exists():
        print(f"   ❌ Migration SQL not found: {migration_sql_path}")
        sys.exit(1)

    with open(migration_sql_path) as f:
        migration_sql = f.read()


    conn = sqlite3.connect(str(db_path))

    try:

        with conn:

            conn.execute("PRAGMA journal_mode=WAL")


            for statement in migration_sql.split(";"):
                statement = statement.strip()
                if statement and not statement.startswith("--"):
                    print(f"   Executing: {statement[:60]}...")
                    conn.execute(statement)

        print()
        print("✅ Contract Migration Complete!")
        print("   Changes:")
        print("   - Dropped legacy ID columns")
        print("   - Made ULID the primary identifier (renamed to id)")
        print("   - Dropped ULID timestamp columns (no longer needed)")
        print()
        print("⏭️  Next Steps:")
        print("   1. Update application code to reference ULID as 'id'")
        print("   2. Test all functionality")
        print("   3. Deploy to production")
        print()

    except Exception as e:
        print(f"   ❌ Migration failed: {e}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    run_contract_migration()
