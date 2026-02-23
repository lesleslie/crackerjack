#!/usr/bin/env python3

import asyncio
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).parent.parent))

from crackerjack.services.metrics import MetricsCollector


async def backfill_jobs(collector: MetricsCollector):
    query = "UPDATE jobs SET job_ulid = ?, job_ulid_generated_at = datetime('now') WHERE job_ulid IS NULL"
    params = (collector.generate_job_ulid(),)
    await collector.execute(query, params)


async def backfill_errors(collector: MetricsCollector):
    query = """
    UPDATE errors
    SET error_ulid = ?,
        error_ulid_generated_at = datetime('now')
    WHERE error_ulid IS NULL
    """
    params = (collector.generate_job_ulid(),)
    await collector.execute(query, params)


async def backfill_hook_executions(collector: MetricsCollector):
    query = """
    UPDATE hook_executions
    SET hook_ulid = ?,
        hook_ulid_generated_at = datetime('now')
    WHERE hook_ulid IS NULL
    """
    params = (collector.generate_job_ulid(),)
    await collector.execute(query, params)


async def backfill_test_executions(collector: MetricsCollector):
    query = """
    UPDATE test_executions
    SET test_ulid = ?,
        test_ulid_generated_at = datetime('now')
    WHERE test_ulid IS NULL
    """
    params = (collector.generate_job_ulid(),)
    await collector.execute(query, params)


async def backfill_individual_tests(collector: MetricsCollector):
    query = """
    UPDATE individual_test_executions
    SET test_execution_ulid = ?,
        test_execution_ulid_generated_at = datetime('now')
    WHERE test_execution_ulid IS NULL
    """
    params = (collector.generate_job_ulid(),)
    await collector.execute(query, params)


async def backfill_strategy_decisions(collector: MetricsCollector):
    query = """
    UPDATE strategy_decisions
    SET decision_ulid = ?,
        decision_ulid_generated_at = datetime('now')
    WHERE decision_ulid IS NULL
    """
    params = (collector.generate_job_ulid(),)
    await collector.execute(query, params)


async def run_migration():

    print("=" * 60)
    print("Crackerjack ULID Migration")
    print("=" * 60)
    print()
    print("📊 Phase 1: Expanding Schema")
    print("   (Skipping - migration SQL already applied)")
    print()
    print("📊 Phase 2: Backfilling ULIDs")
    print("   Generating ULIDs for existing records...")


    collector = MetricsCollector()


    if not hasattr(collector, "generate_job_ulid"):
        print("   ⚠️  ULID generation not available - cannot run migration")
        print("   Please ensure MetricsCollector has ULID support")
        sys.exit(1)


    await backfill_jobs(collector)
    print("   ✅ Jobs backfilled")
    await backfill_errors(collector)
    print("   ✅ Errors backfilled")
    await backfill_hook_executions(collector)
    print("   ✅ Hook executions backfilled")
    await backfill_test_executions(collector)
    print("   ✅ Test executions backfilled")
    await backfill_individual_tests(collector)
    print("   ✅ Individual test executions backfilled")
    await backfill_strategy_decisions(collector)

    print("   ✅ All tables backfilled")

    print()
    print("🎉 Migration Complete!")
    print("   Total tables migrated: 6 tables")
    print()
    print("⏭️  Next Steps:")
    print("   1. Application code updated to use ULID for new records")
    print("   2. Verification period: 14 days (keep both IDs active)")
    print("   3. After verification, can switch to ULID as primary identifier")
    print()


if __name__ == "__main__":
    asyncio.run(run_migration())
