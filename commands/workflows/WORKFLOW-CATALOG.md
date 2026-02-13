______________________________________________________________________

## title: Workflow Catalog & Decision Tree description: Navigate the workflow ecosystem to find the right workflow for your task owner: Platform Engineering last_reviewed: 2025-10-01 risk: low status: active id: 01K6EGMX8YTJN4P9ZVW0ERBQ2H

## Workflow Catalog & Decision Tree

This catalog helps you navigate 15 active workflows across 5 categories. Use the decision tree below to find the right workflow for your task.

## Quick Decision Tree

```
What are you building or fixing?
│
├─ 🚀 NEW FEATURE OR PRODUCT
│  │
│  ├─ Is this a new product idea or major initiative?
│  │  └─ YES → feature/product-discovery-sprint.md
│  │
│  └─ Any other feature (simple to complex)?
│     └─ YES → feature/feature-delivery-lifecycle.md
│
├─ 🔧 MAINTENANCE & IMPROVEMENTS
│  │
│  ├─ Active incident (system down, major issue)?
│  │  └─ YES → maintenance/incident-response.md (P0 - USE IMMEDIATELY)
│  │
│  ├─ Disaster recovery (datacenter failure, ransomware)?
│  │  └─ YES → maintenance/disaster-recovery.md (P0 - USE IMMEDIATELY)
│  │
│  ├─ System is unstable (errors, crashes, downtime)?
│  │  └─ YES → maintenance/stability-lifecycle.md
│  │
│  ├─ Modernizing legacy system?
│  │  └─ YES → maintenance/legacy-modernize.md
│  │
│  ├─ Security audit or hardening?
│  │  └─ YES → maintenance/security-hardening.md
│  │
│  └─ Improving an existing agent?
│     └─ YES → maintenance/improve-agent.md
│
├─ 🚢 DEPLOYMENT & RELEASE
│  │
│  ├─ Deploying containers (Docker/Kubernetes)?
│  │  └─ YES → deployment/container-deployment.md
│  │
│  ├─ ML model deployment/pipeline?
│  │  └─ YES → deployment/ml-pipeline.md
│  │
│  ├─ Database schema changes?
│  │  └─ YES → deployment/database-migration.md
│  │
│  ├─ API version sunset/deprecation?
│  │  └─ YES → deployment/api-versioning.md
│  │
│  └─ Multi-team release coordination?
│     └─ YES → deployment/release-governance.md
│
├─ 🤖 AUTOMATION
│  │
│  └─ Any automation workflow?
│     └─ YES → automation/automation-orchestration.md
│
├─ 📊 MONITORING & ANALYTICS
│  │
│  └─ Tracking feature adoption or usage metrics?
│     └─ YES → monitoring/adoption-analytics.md
│
└─ ❓ NOT SURE?
   └─ See "Workflow Categories" section below for full descriptions
```

## Workflow Categories

### 🚀 Feature Development (2 workflows)

Build new features, products, and user experiences.

| Workflow | Use When | Risk | Key Agents |
|----------|----------|------|------------|
| **product-discovery-sprint.md** | Starting new product/initiative, need validation | Medium | product-manager, ux-researcher |
| **feature-delivery-lifecycle.md** | End-to-end feature delivery with rollback safety | Medium | product-manager, release-manager, qa-strategist |

**Decision Criteria:**

- **New product?** → Use product-discovery-sprint.md first
- **Building feature?** → Use feature-delivery-lifecycle.md for comprehensive delivery

**Examples:**

- "Validate new SaaS product idea" → product-discovery-sprint.md
- "Build user dashboard" → feature-delivery-lifecycle.md
- "Build checkout flow" → feature-delivery-lifecycle.md (mission-critical)

______________________________________________________________________

### 🔧 Maintenance & Improvements (6 workflows)

Fix, optimize, and modernize existing systems.

| Workflow | Use When | Risk | Key Agents |
|----------|----------|------|------------|
| **incident-response.md** | Active incident (P0 - use immediately) | Critical | observability-incident-lead, devops-troubleshooter |
| **disaster-recovery.md** | Datacenter failure, ransomware (P0) | Critical | release-manager, security-auditor |
| **stability-lifecycle.md** | System unstable (errors, crashes) | Medium | observability-incident-lead, observability-incident-lead |
| **security-hardening.md** | Security audit, threat modeling | High | security-auditor, api-security-specialist |
| **legacy-modernize.md** | Modernizing legacy systems | High | developer-enablement-lead, architecture-council |
| **improve-agent.md** | Improving existing AI agent | Low | agent-creation-specialist |

**Decision Criteria:**

- **Urgency:** Incident (minutes), high (days), medium (weeks), low (months)
- **Scope:** Single bug vs system-wide modernization
- **Risk:** Can this break production?

**Examples:**

- "Database is down" → incident-response.md (P0)
- "System crashes intermittently" → stability-lifecycle.md
- "Rewrite PHP monolith to microservices" → legacy-modernize.md

______________________________________________________________________

### 🚢 Deployment & Release (5 workflows)

Deploy, migrate, and release software safely.

| Workflow | Use When | Risk | Key Agents |
|----------|----------|------|------------|
| **container-deployment.md** | Deploying Docker/Kubernetes apps | Medium | docker-specialist, cloud-native-architect |
| **ml-pipeline.md** | ML model deployment/training pipeline | Medium | ml-engineer, mlops-engineer, data-pipeline-engineer |
| **database-migration.md** | Schema changes, data migrations | High | database-operations-specialist, postgresql-specialist |
| **api-versioning.md** | API deprecation, version sunset | Medium | architecture-council, api-security-specialist |
| **release-governance.md** | Multi-team release coordination | Medium | release-manager, delivery-lead |

**Decision Criteria:**

- **Downtime Tolerance:** Zero-downtime vs maintenance window
- **Reversibility:** Can you rollback instantly?
- **Blast Radius:** How many users affected if failure?

**Examples:**

- "Add NOT NULL column to 100M row table" → database-migration.md
- "Deploy new microservice to K8s" → container-deployment.md
- "Sunset v1 API in 6 months" → api-versioning.md

______________________________________________________________________

### 🤖 Automation (1 workflow)

Automate repetitive tasks and workflows.

| Workflow | Use When | Risk | Key Agents |
|----------|----------|------|------------|
| **automation-orchestration.md** | Any automation workflow (desktop, research, multi-step) | Medium | workflow-orchestrator, platform-automation |

**Decision Criteria:**

- **Interface:** Supports API, GUI, terminal automation
- **Frequency:** One-time or recurring workflows

**Examples:**

- "Automate daily competitor price scraping" → automation-orchestration.md
- "Click through legacy desktop app to extract data" → automation-orchestration.md

______________________________________________________________________

### 📊 Monitoring & Analytics (1 workflow)

Track, measure, and analyze system/user behavior.

| Workflow | Use When | Risk | Key Agents |
|----------|----------|------|------------|
| **adoption-analytics.md** | Tracking feature adoption and usage metrics | Low | support-analytics-specialist, product-manager |

**Decision Criteria:**

- **Purpose:** Track feature adoption, user behavior, and usage metrics
- **Audience:** Product, engineering, and executives

**Examples:**

- "Track new checkout flow conversion" → adoption-analytics.md
- "Measure feature engagement after launch" → adoption-analytics.md

______________________________________________________________________

## Risk-Based Selection

### P0 - CRITICAL (Use Immediately)

**Active incidents, disasters, security breaches:**

- maintenance/incident-response.md
- maintenance/disaster-recovery.md

**When to use:** System down, data breach, ransomware, regional outage.

______________________________________________________________________

### High Risk (Careful Planning Required)

**Can cause outage, data loss, or security issues:**

- maintenance/legacy-modernize.md (rewriting production systems)
- deployment/database-migration.md (schema changes on large tables)
- maintenance/security-hardening.md (can break auth flows)

**Required safeguards:**

- Comprehensive testing in staging
- Gradual rollout (canary → 5% → 25% → 100%)
- Instant rollback capability
- On-call engineer availability

______________________________________________________________________

### Medium Risk (Standard Production Practices)

**Standard production changes:**

- feature/feature-delivery-lifecycle.md
- deployment/container-deployment.md
- deployment/ml-pipeline.md
- deployment/api-versioning.md
- deployment/release-governance.md
- maintenance/stability-lifecycle.md

**Required safeguards:**

- Code review
- Automated tests
- Staging validation
- Rollback plan

______________________________________________________________________

### Low Risk (Safe for Experimentation)

**Prototypes, non-production, or reversible changes:**

- feature/product-discovery-sprint.md
- automation/automation-orchestration.md
- monitoring/adoption-analytics.md
- maintenance/improve-agent.md

**Minimal safeguards needed.**

______________________________________________________________________

## Scenario-Based Recommendations

### "I need to ship a feature FAST"

**Timeline:** 1-3 days

**Use:**

1. feature/feature-delivery-lifecycle.md (skip discovery phase, focus on implementation)
1. Deploy with feature flag for instant rollback
1. Monitor metrics closely

**Note:** Even fast features should use feature-delivery-lifecycle.md for rollback safety.

______________________________________________________________________

### "I need to ship a feature SAFELY"

**Timeline:** 2-4 weeks

**Use:**

1. feature/product-discovery-sprint.md (validate idea first)
1. feature/feature-delivery-lifecycle.md (comprehensive delivery with rollback)
1. Full testing, gradual rollout, metrics monitoring

**Includes:**

- Product discovery and validation
- Security review
- Load testing
- Comprehensive rollback procedures

______________________________________________________________________

### "Our database is slow"

**Use:**

1. maintenance/stability-lifecycle.md (if intermittent performance issues)
1. deployment/database-migration.md (if schema changes needed)

**Decision tree:**

- Queries slow? → Add indexes, optimize queries (stability-lifecycle or direct database work)
- Schema inefficient? → Redesign schema (database-migration)
- Hardware limits? → Scale vertically/horizontally (container-deployment)

______________________________________________________________________

### "We're getting hacked"

**Use:**

1. maintenance/incident-response.md (if active attack)
1. maintenance/security-hardening.md (preventive hardening)

**Decision tree:**

- Active breach? → incident-response.md (stop attack, contain damage)
- Vulnerability discovered? → security-hardening.md (patch, harden)
- Proactive security? → security-hardening.md (threat modeling)

______________________________________________________________________

### "We need to deprecate an API"

**Use:**

1. deployment/api-versioning.md (full deprecation lifecycle)

**Timeline:**

- **T-180 days:** Announce deprecation
- **T-90 days:** Email all API consumers
- **T-30 days:** Show deprecation warnings in responses
- **T-0 days:** Sunset old version

______________________________________________________________________

## Workflow Combinations

Some tasks require multiple workflows in sequence:

### Modernizing a Legacy Monolith

**Phase 1:** maintenance/legacy-modernize.md (plan migration)
**Phase 2:** deployment/database-migration.md (migrate data)
**Phase 3:** deployment/container-deployment.md (deploy microservices)
**Phase 4:** deployment/api-versioning.md (sunset old monolith APIs)

______________________________________________________________________

### Launching a New Product

**Phase 1:** feature/product-discovery-sprint.md (validate idea)
**Phase 2:** feature/feature-delivery-lifecycle.md (build and launch MVP)
**Phase 3:** deployment/release-governance.md (coordinate launch)
**Phase 4:** monitoring/adoption-analytics.md (track adoption)

______________________________________________________________________

### Responding to Performance Crisis

**Phase 1:** maintenance/incident-response.md (if system down)
**Phase 2:** maintenance/stability-lifecycle.md (fix bottlenecks and improve stability)
**Phase 3:** deployment/database-migration.md (if schema changes needed)
**Phase 4:** monitoring/adoption-analytics.md (track improvements)

______________________________________________________________________

### incident-response.md vs disaster-recovery.md

**Use incident-response.md when:**

- Service degradation or outage
- Single datacenter/region
- Recoverable in hours

**Use disaster-recovery.md when:**

- Complete datacenter failure
- Ransomware/catastrophic data loss
- Multi-region failover needed
- Recoverable in days

______________________________________________________________________

## Integration with Tools & Agents

Each workflow delegates to **specialized agents** and uses **development tools**.

### Key Agent Patterns

**For feature development:**

- product-manager → ux-researcher → frontend-developer → architecture-council → qa-strategist

**For deployment:**

- release-manager → docker-specialist → cloud-native-architect → observability-incident-lead

**For maintenance:**

- code-reviewer → security-auditor → observability-incident-lead → refactoring-specialist

### Key Tools Used

**Most workflows use:**

- `commands/tools/development/testing/quality-validation.md` - Test automation
- `commands/tools/development/code-quality/dependency-lifecycle.md` - Dependency management
- `commands/tools/deployment/release-management.md` - Release coordination
- `commands/tools/monitoring/observability-lifecycle.md` - Observability and metrics

______________________________________________________________________

## Workflow Metadata

All workflows include standardized frontmatter:

```yaml
---
title: Workflow Name
owner: Team/Guild responsible
last_reviewed: 2025-10-01
related_tools:
  - commands/tools/...
risk: low | medium | high | critical
status: active | deprecated | archived
id: 01K6... (ULID)
---
```

**Use `scripts/workflow_validator.py` to validate workflow integrity.**

______________________________________________________________________

## Getting Help

**Can't find the right workflow?**

1. Check the decision tree at the top
1. Review scenario-based recommendations
1. Use `scripts/workflow_validator.py` to validate custom workflows
1. Consult `CLAUDE.md` for agent/tool descriptions

**Need to create a custom workflow?**

1. Copy an existing workflow as template
1. Follow frontmatter format
1. Define phases with agent delegation
1. Run `python scripts/workflow_validator.py --workflow your-workflow.md`
1. Submit PR with validation passing

______________________________________________________________________

## Workflow Status

**Active:** 15 workflows ready for production use
**Deprecated:** 14 workflows removed (migration paths documented)
**Quality Score:** 92/100 (after Phase 3 - Quality Improvements + Cleanup)

**Last Updated:** 2025-10-01 (Phase 3 Complete + Deprecated Cleanup)
