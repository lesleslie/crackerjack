______________________________________________________________________

title: Legacy Modernization Workflow
owner: Developer Enablement Guild
last_reviewed: 2025-02-06
related_tools:

- commands/tools/development/code-quality/dependency-lifecycle.md
- commands/tools/maintenance/maintenance-cadence.md
- commands/tools/development/testing/quality-validation.md
  risk: high
  status: active
  id: 01K6EF8EMW9PF2X3HV20GYWVHG

______________________________________________________________________

## Legacy Modernization Workflow

[Extended thinking: Execute incremental modernization with guardrails to protect existing customers.]

## Overview

Use this workflow to modernize legacy systems through staged refactors and migrations.

## Prerequisites

- Inventory of legacy assets and dependencies.
- Business impact assessment and risk tolerance.
- Agreement on migration strategy (strangler, module rewrite, etc.).

## Inputs

- `$ARGUMENTS` — system or module targeted for modernization.
- `$MIGRATION_STRATEGY` — e.g., `strangler`, `lift-shift`, `rewrite`.
- `$CONSTRAINTS` — uptime, compliance, or contract limits.

## Outputs

- Modernization roadmap with phases and owners.
- Updated components deployed with parity tests.
- Decommission plan for legacy assets.

## Phases

### Phase 1 – Discovery & Safeguards

- `developer-enablement-lead` documents architecture, dependencies, and risk controls.
- `architecture-council` validates target design and transition patterns.
- `qa-strategist` defines regression coverage and baselines.

### Phase 2 – Incremental Delivery & Data Migration

**Incremental Implementation:**

- Implement gated milestones with `developer-enablement-lead` and feature flags
- Use strangler fig pattern to incrementally replace legacy functionality
- Maintain dual-write capability during transition period

**Data Migration Validation:**

**Agent:** `data-engineer` or `database-operations-specialist` manages data migration

1. **Pre-Migration Data Profiling:**

   ```sql
   -- Capture baseline metrics from legacy system
   -- Row counts by table
   SELECT 'legacy_users' as table_name, COUNT(*) as row_count FROM legacy.users
   UNION ALL
   SELECT 'legacy_orders', COUNT(*) FROM legacy.orders
   UNION ALL
   SELECT 'legacy_products', COUNT(*) FROM legacy.products;

   -- Data distribution analysis
   SELECT
       DATE_TRUNC('month', created_at) as month,
       COUNT(*) as records,
       COUNT(DISTINCT user_id) as unique_users
   FROM legacy.orders
   GROUP BY month
   ORDER BY month DESC
   LIMIT 12;

   -- Identify data quality issues
   SELECT
       'null_emails' as issue,
       COUNT(*) as count
   FROM legacy.users WHERE email IS NULL
   UNION ALL
   SELECT 'duplicate_emails', COUNT(*)
   FROM (SELECT email FROM legacy.users GROUP BY email HAVING COUNT(*) > 1) dups
   UNION ALL
   SELECT 'orphaned_orders', COUNT(*)
   FROM legacy.orders o LEFT JOIN legacy.users u ON o.user_id = u.id
   WHERE u.id IS NULL;
   ```

1. **Migration Strategy Selection:**

   **Strategy A: Dual-Write (Zero Downtime)**

   ```python
   # Write to both legacy and modern systems
   def create_user(user_data):
       # Write to modern system first
       modern_user = modern_db.users.create(user_data)

       # Write to legacy system for backward compatibility
       try:
           legacy_user = legacy_db.users.create(transform_to_legacy(user_data))
       except Exception as e:
           # Log but don't fail - legacy is being phased out
           logger.warning(f"Legacy write failed: {e}")

       return modern_user
   ```

   **Strategy B: Batch Migration (Maintenance Window)**

   ```python
   # Migrate in batches with progress tracking
   def migrate_users_batch(batch_size=10000, checkpoint_interval=1000):
       last_id = get_last_migrated_id()

       while True:
           batch = legacy_db.query(
               "SELECT * FROM users WHERE id > ? LIMIT ?", (last_id, batch_size)
           )

           if not batch:
               break

           for i, user in enumerate(batch):
               # Transform and insert
               modern_user = transform_user(user)
               modern_db.users.create(modern_user)

               # Checkpoint progress
               if i % checkpoint_interval == 0:
                   save_checkpoint(user["id"])

           last_id = batch[-1]["id"]
           logger.info(f"Migrated batch ending at ID {last_id}")
   ```

   **Strategy C: CDC Replication (Continuous)**

   ```yaml
   # Debezium connector for real-time replication
   connector:
     name: legacy-to-modern-cdc
     config:
       connector.class: io.debezium.connector.mysql.MySqlConnector
       database.hostname: legacy-db.example.com
       database.port: 3306
       database.user: replication_user
       database.server.id: 184054
       database.include.list: legacy_db
       table.include.list: legacy_db.users,legacy_db.orders
       transforms: unwrap,route
       transforms.unwrap.type: io.debezium.transforms.ExtractNewRecordState
   ```

1. **Data Validation During Migration:**

   ```python
   # Automated validation script
   def validate_migration(sample_size=10000):
       """
       Compare legacy and modern data to ensure migration accuracy
       """
       results = {
           "row_count_match": False,
           "sample_data_match": False,
           "schema_compatible": False,
           "foreign_keys_valid": False,
           "null_constraints_valid": False,
       }

       # 1. Row count validation
       legacy_count = legacy_db.query("SELECT COUNT(*) FROM users")[0][0]
       modern_count = modern_db.query("SELECT COUNT(*) FROM users")[0][0]
       results["row_count_match"] = legacy_count == modern_count

       if not results["row_count_match"]:
           logger.error(
               f"Row count mismatch: Legacy={legacy_count}, Modern={modern_count}"
           )

       # 2. Sample data comparison
       sample_ids = random.sample(range(1, legacy_count), min(sample_size, legacy_count))
       mismatches = []

       for user_id in sample_ids:
           legacy_user = legacy_db.users.get(user_id)
           modern_user = modern_db.users.get(user_id)

           if not compare_users(legacy_user, modern_user):
               mismatches.append(
                   {"id": user_id, "legacy": legacy_user, "modern": modern_user}
               )

       results["sample_data_match"] = len(mismatches) == 0

       if mismatches:
           logger.error(f"Found {len(mismatches)} data mismatches in sample")
           # Log first 10 mismatches for analysis
           for mismatch in mismatches[:10]:
               logger.error(f"Mismatch: {mismatch}")

       # 3. Schema validation
       legacy_schema = get_table_schema(legacy_db, "users")
       modern_schema = get_table_schema(modern_db, "users")
       results["schema_compatible"] = validate_schema_compatibility(
           legacy_schema, modern_schema
       )

       # 4. Foreign key integrity
       orphaned_orders = modern_db.query("""
           SELECT COUNT(*) FROM orders o
           LEFT JOIN users u ON o.user_id = u.id
           WHERE u.id IS NULL
       """)[0][0]
       results["foreign_keys_valid"] = orphaned_orders == 0

       # 5. NOT NULL constraint validation
       null_violations = modern_db.query("""
           SELECT
               'email' as column_name,
               COUNT(*) as null_count
           FROM users WHERE email IS NULL
           UNION ALL
           SELECT 'username', COUNT(*) FROM users WHERE username IS NULL
       """)
       results["null_constraints_valid"] = all(row[1] == 0 for row in null_violations)

       return results


   # Run validation
   validation_results = validate_migration()
   if all(validation_results.values()):
       logger.info("✓ All validation checks passed")
   else:
       logger.error("✗ Validation failed:")
       for check, passed in validation_results.items():
           logger.error(f"  {check}: {'✓' if passed else '✗'}")
   ```

1. **Performance Comparison:**

   ```python
   # Compare query performance between legacy and modern systems
   import time


   def compare_query_performance(queries, iterations=100):
       results = []

       for query_name, query_sql in queries.items():
           # Legacy system
           legacy_times = []
           for _ in range(iterations):
               start = time.time()
               legacy_db.execute(query_sql)
               legacy_times.append(time.time() - start)

           # Modern system
           modern_times = []
           for _ in range(iterations):
               start = time.time()
               modern_db.execute(query_sql)
               modern_times.append(time.time() - start)

           results.append(
               {
                   "query": query_name,
                   "legacy_avg_ms": np.mean(legacy_times) * 1000,
                   "legacy_p95_ms": np.percentile(legacy_times, 95) * 1000,
                   "modern_avg_ms": np.mean(modern_times) * 1000,
                   "modern_p95_ms": np.percentile(modern_times, 95) * 1000,
                   "speedup": np.mean(legacy_times) / np.mean(modern_times),
               }
           )

       return pd.DataFrame(results)


   # Test critical queries
   critical_queries = {
       "user_lookup": "SELECT * FROM users WHERE email = 'test@example.com'",
       "order_history": "SELECT * FROM orders WHERE user_id = 12345 ORDER BY created_at DESC LIMIT 10",
       "product_search": "SELECT * FROM products WHERE name LIKE '%widget%' LIMIT 20",
   }

   perf_results = compare_query_performance(critical_queries)
   print(perf_results)
   ```

1. **Data Migration Validation Checklist:**

   - [ ] **Row Count Match:**

     - Legacy row count = Modern row count (per table)
     - No data loss during migration

   - [ ] **Data Integrity:**

     - Sample comparison shows 100% accuracy (random 10k records)
     - Foreign key constraints valid (no orphaned records)
     - NOT NULL constraints satisfied
     - Unique constraints satisfied (no duplicates)

   - [ ] **Schema Compatibility:**

     - All required fields present in modern schema
     - Data types compatible or correctly transformed
     - Indexes created for query performance

   - [ ] **Business Logic Validation:**

     - Calculated fields produce same results (e.g., order_total)
     - Audit timestamps preserved (created_at, updated_at)
     - Soft delete flags migrated correctly (is_deleted, deleted_at)

   - [ ] **Performance Validation:**

     - Query response times ≤ legacy system (or within 10%)
     - No regressions in critical user journeys
     - Database CPU/memory usage acceptable

   - [ ] **Data Quality Improvements:**

     - Known data quality issues fixed during migration
     - Missing data filled with defaults or flagged
     - Duplicate records deduplicated

   - [ ] **Rollback Capability:**

     - Legacy system still operational during transition
     - Ability to switch back to legacy if issues found
     - Dual-write enabled for rollback safety

1. **Zero-Downtime Cutover Procedure:**

   ```bash
   # Phase 1: Dual-write enabled (writes go to both systems)
   kubectl set env deployment/api-server DUAL_WRITE=true

   # Phase 2: Validate data sync (10 minutes)
   python scripts/validate_dual_write.py --check-lag

   # Phase 3: Switch reads to modern (feature flag)
   curl -X PATCH $FEATURE_FLAG_API/flags/use-modern-db \
     -d '{"enabled": true, "rollout_percentage": 5}'

   # Monitor for 1 hour at 5%
   # Gradually increase: 10%, 25%, 50%, 100%

   # Phase 4: Stop writes to legacy
   kubectl set env deployment/api-server DUAL_WRITE=false

   # Phase 5: Archive legacy data (keep for 90 days)
   pg_dump legacy_db > backups/legacy_final_$(date +%Y%m%d).sql
   ```

**Data Migration Deliverables:**

- Migration validation report (row counts, integrity checks, performance)
- Data quality improvement summary
- Performance comparison (legacy vs modern)
- Rollback procedure tested and documented

### Phase 3 – Validation & Cutover

**Parallel System Validation:**

- Run parallel runbooks with `qa-strategist` ensuring parity tests pass
- Execute synthetic transactions on both legacy and modern systems
- Compare results for 100% parity

**Performance Monitoring:**

- `observability-incident-lead` monitors key metrics during cutover:
  - Error rates (should be ≤ baseline)
  - Response times (should be ≤ 1.1x legacy)
  - Database query performance
  - Memory and CPU utilization

**Cutover Coordination:**

- `release-manager` coordinates change windows
- Gradual traffic shift (5% → 10% → 25% → 50% → 100%)
- Monitor each step for 1-4 hours before proceeding
- Keep legacy system running for 30 days minimum

**Cutover Validation Checklist:**

- [ ] **Functional Parity:**

  - All user journeys work identically on modern system
  - Edge cases tested (null values, large datasets, concurrent users)
  - Integration tests pass (APIs, webhooks, third-party services)

- [ ] **Performance Parity:**

  - 95th percentile response time ≤ 110% of legacy
  - Database query performance acceptable
  - No memory leaks or resource exhaustion

- [ ] **Business Metrics:**

  - Conversion rates stable (within 2% of baseline)
  - User engagement metrics stable
  - Error rates ≤ legacy system
  - Customer support tickets not elevated

- [ ] **Data Consistency:**

  - Ongoing validation shows 100% data integrity
  - No data loss detected
  - Replication lag < 1 second (if using CDC)

- [ ] **Rollback Readiness:**

  - Legacy system still operational
  - Rollback procedure tested in staging
  - Feature flag can instantly revert to legacy
  - On-call team briefed and available

**Rollback Triggers:**

Execute rollback if:

- Error rate increases >5%
- Response time degrades >25%
- Data integrity issues discovered
- Critical business metrics drop >10%
- Customer escalations spike
- Security vulnerability introduced

### Phase 4 – Decommission & Cleanup

- `maintenance-cadence.md` tool tracks follow-up debt and patch removal.
- `customer-success-lead` communicates user-facing changes and support guidance.

## Handoffs & Follow-Up

- Archive legacy documentation and update runbooks.
- Schedule post-modernization review for residual risks and lessons learned.
