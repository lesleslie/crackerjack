______________________________________________________________________

title: Release Governance Workflow
owner: Delivery Operations
last_reviewed: 2025-02-06
related_tools:

- commands/tools/deployment/release-management.md
- commands/tools/development/testing/quality-validation.md
- commands/tools/monitoring/observability-lifecycle.md
  risk: high
  status: active
  id: 01K6EF5K31G84FC47F8TFBZ1EN

______________________________________________________________________

## Release Governance Workflow

[Extended thinking: Bridge build completion to customer availability by coordinating quality, risk, and communication checkpoints.]

## Overview

Leverage this workflow to shepherd a release from readiness review through launch and stabilization.

## Prerequisites

- Consolidated release scope and change log.
- Evidence from testing, security, and observability gates.
- Stakeholder roster for approvals and communications.

## Inputs

- `$ARGUMENTS` — release identifier and summary (e.g., "v2.3 payments rollout").
- `$RELEASE_WINDOW` — planned deployment window or freeze dates.
- `$RISK_PROFILE` — known risks or blockers to surface during governance.

## Outputs

- Signed-off release checklist with approvals.
- Go/No-Go decision log and mitigation plan.
- Launch communication packet, plus post-release report.

## Phases

### Phase 0 – Prerequisites Validation

**Before initiating release governance process, validate all release readiness requirements:**

1. **Release Artifacts & Documentation:**

   ```bash
   # Verify release notes exist
   [ -f "CHANGELOG.md" ] || [ -f "releases/v${VERSION}/RELEASE_NOTES.md" ] || \
     echo "ERROR: No release notes found"

   # Check version tagging
   git tag | grep "^v${VERSION}$" || echo "WARNING: Version not tagged in git"

   # Verify deployment manifests exist
   [ -d "deploy/${ENVIRONMENT}" ] || echo "ERROR: Missing deployment configs for ${ENVIRONMENT}"

   # Check migration scripts (if applicable)
   ls migrations/*.sql 2>/dev/null || echo "INFO: No database migrations"
   ```

1. **Testing Evidence:**

   ```bash
   # Verify test results available
   [ -f "test-results/junit.xml" ] || [ -f "test-results/summary.json" ] || \
     echo "ERROR: No test results found"

   # Check test coverage meets threshold
   coverage_pct=$(cat coverage.json | jq '.totals.percent_covered')
   if (( $(echo "$coverage_pct < 80" | bc -l) )); then
       echo "WARNING: Coverage ${coverage_pct}% below 80% threshold"
   fi

   # Verify integration tests passed
   [ -f "test-results/integration-tests.xml" ] || \
     echo "WARNING: No integration test results"

   # Check performance test results (if required)
   [ -f "test-results/performance-report.html" ] || \
     echo "INFO: No performance test results"
   ```

1. **Security & Compliance Gates:**

   ```bash
   # Verify security scan completed
   [ -f "security-scan-results.json" ] || \
     echo "ERROR: No security scan results"

   # Check for critical vulnerabilities
   critical_vulns=$(cat security-scan-results.json | jq '.summary.critical // 0')
   if [ "$critical_vulns" -gt 0 ]; then
       echo "BLOCKER: ${critical_vulns} critical vulnerabilities found"
       exit 1
   fi

   # Verify dependency audit
   npm audit --audit-level=high || \
     pip-audit --strict || \
     echo "WARNING: Dependency vulnerabilities detected"

   # Check compliance documentation (if regulated)
   [ -f "compliance/privacy-impact-assessment.md" ] || \
     echo "INFO: No PIA documented"
   ```

1. **Stakeholder Approvals:**

   ```bash
   # Check required approvals in PR/MR
   gh pr view $PR_NUMBER --json reviews | \
     jq '.reviews | map(select(.state=="APPROVED")) | length' || \
     echo "ERROR: Cannot verify approvals"

   # Verify change advisory board (CAB) approval for high-risk releases
   if [ "$RISK_PROFILE" == "high" ] || [ "$RISK_PROFILE" == "critical" ]; then
       [ -f "approvals/cab-approval-${VERSION}.md" ] || \
         echo "BLOCKER: CAB approval required for high-risk release"
   fi
   ```

1. **Deployment Infrastructure:**

   ```bash
   # Verify target environment is healthy
   kubectl get nodes -o json | jq '.items[].status.conditions[] | select(.type=="Ready" and .status!="True")' | \
     [ $(wc -l) -eq 0 ] || echo "WARNING: Some nodes not ready"

   # Check deployment namespace exists
   kubectl get namespace $TARGET_NAMESPACE || \
     echo "ERROR: Target namespace does not exist"

   # Verify sufficient resources available
   kubectl top nodes | awk 'NR>1 {if ($3+0 > 85 || $5+0 > 85) print "WARNING: High resource usage on " $1}'

   # Check deployment tools accessible
   helm version || echo "WARNING: Helm not accessible"
   kubectl version || echo "ERROR: kubectl not accessible"
   ```

1. **Monitoring & Alerting:**

   ```bash
   # Verify monitoring dashboards exist for release
   dashboard_exists=$(curl -s -H "Authorization: Bearer $GRAFANA_TOKEN" \
     "$GRAFANA_URL/api/search?query=${SERVICE_NAME}" | jq 'length')

   if [ "$dashboard_exists" -eq 0 ]; then
       echo "WARNING: No Grafana dashboard found for ${SERVICE_NAME}"
   fi

   # Check alert rules configured
   alert_count=$(curl -s "$PROMETHEUS_URL/api/v1/rules" | \
     jq "[.data.groups[].rules[] | select(.labels.service==\"${SERVICE_NAME}\")] | length")

   echo "✓ Found ${alert_count} alert rules for ${SERVICE_NAME}"

   # Verify on-call schedule
   oncall_engineer=$(curl -s -H "Authorization: $PAGERDUTY_TOKEN" \
     "$PAGERDUTY_API/oncalls?schedule_ids[]=$SCHEDULE_ID" | \
     jq -r '.oncalls[0].user.summary')

   echo "✓ On-call engineer: ${oncall_engineer}"
   ```

1. **Rollback Readiness:**

   ```bash
   # Verify previous version is tagged and available
   previous_version=$(git describe --tags --abbrev=0 HEAD^)
   echo "✓ Rollback target: ${previous_version}"

   # Check rollback procedure documented
   [ -f "docs/runbooks/rollback-${VERSION}.md" ] || \
     [ -f "docs/runbooks/rollback-procedure.md" ] || \
     echo "WARNING: No rollback procedure documented"

   # Verify database migration rollback tested
   if [ -d "migrations" ]; then
       [ -f "migrations/rollback-tested.txt" ] || \
         echo "WARNING: Database migration rollback not verified in staging"
   fi

   # Check feature flags configured for instant disable
   if [ -f "feature-flags.yaml" ]; then
       echo "✓ Feature flags configured for controlled rollout"
   fi
   ```

1. **Communication Readiness:**

   ```bash
   # Verify release announcement drafted
   [ -f "communications/release-announcement-${VERSION}.md" ] || \
     echo "INFO: No release announcement drafted"

   # Check status page prepared
   [ -f "communications/status-page-update.md" ] || \
     echo "INFO: No status page update prepared"

   # Verify customer notification list (if customer-facing)
   [ -f "communications/customer-notification-list.csv" ] || \
     echo "INFO: No customer notification list"

   # Check internal communication channels ready
   slack_channel=$(curl -s -H "Authorization: Bearer $SLACK_TOKEN" \
     "$SLACK_API/conversations.info?channel=${RELEASE_CHANNEL}" | \
     jq -r '.channel.name')
   echo "✓ Release channel: #${slack_channel}"
   ```

1. **Compliance & Legal:**

   ```bash
   # For regulated industries, verify compliance sign-off
   if [[ "$COMPLIANCE_FLAGS" =~ "PCI" ]]; then
       [ -f "compliance/pci-review-${VERSION}.md" ] || \
         echo "BLOCKER: PCI compliance review required"
   fi

   if [[ "$COMPLIANCE_FLAGS" =~ "SOC2" ]]; then
       [ -f "compliance/soc2-review-${VERSION}.md" ] || \
         echo "BLOCKER: SOC2 compliance review required"
   fi

   if [[ "$COMPLIANCE_FLAGS" =~ "GDPR" ]]; then
       [ -f "compliance/privacy-impact-assessment-${VERSION}.md" ] || \
         echo "BLOCKER: GDPR privacy impact assessment required"
   fi

   # Verify legal review for ToS/Privacy Policy changes
   if git diff ${previous_version}..HEAD -- legal/ | grep -q "diff"; then
       [ -f "approvals/legal-approval-${VERSION}.md" ] || \
         echo "BLOCKER: Legal review required for policy changes"
   fi
   ```

1. **Release Window Validation:**

   ```bash
   # Check for deployment freezes
   current_date=$(date +%Y-%m-%d)

   # Holiday freeze check
   if grep -q "$current_date" deployment-freeze-dates.txt 2>/dev/null; then
       echo "BLOCKER: Deployment freeze in effect on ${current_date}"
       exit 1
   fi

   # Business hours check for production deployments
   if [ "$ENVIRONMENT" == "production" ]; then
       day_of_week=$(date +%u)  # 1=Monday, 7=Sunday
       hour=$(date +%H)

       # Prevent Friday deployments after 2pm
       if [ "$day_of_week" -eq 5 ] && [ "$hour" -ge 14 ]; then
           echo "WARNING: Friday afternoon deployment not recommended"
       fi

       # Prevent weekend deployments
       if [ "$day_of_week" -ge 6 ]; then
           echo "WARNING: Weekend deployment requires executive approval"
       fi
   fi
   ```

**Validation Checklist:**

- [ ] Release notes and changelog completed
- [ ] Version tagged in source control
- [ ] All required tests passed (unit, integration, e2e)
- [ ] Test coverage meets threshold (≥80%)
- [ ] Security scans completed with 0 critical vulnerabilities
- [ ] Dependency audit passed
- [ ] Required stakeholder approvals obtained
- [ ] CAB approval obtained (for high-risk releases)
- [ ] Target infrastructure healthy and ready
- [ ] Monitoring dashboards configured
- [ ] Alert rules defined for new/changed services
- [ ] On-call engineer identified and available
- [ ] Rollback procedure documented and tested
- [ ] Previous version available for rollback
- [ ] Database migration rollback verified in staging
- [ ] Release communications prepared
- [ ] Compliance reviews completed (PCI, SOC2, GDPR)
- [ ] Legal approval obtained (if policies changed)
- [ ] Deployment window validated (no freeze)

**Go/No-Go Criteria:**

| Category | Blocker Conditions | Resolution |
|----------|-------------------|------------|
| **Testing** | Critical test failures, coverage \<60% | Fix tests or defer release |
| **Security** | Critical vulnerabilities present | Patch vulnerabilities before release |
| **Approvals** | Missing required approvals (CAB, legal, compliance) | Obtain approvals or escalate |
| **Infrastructure** | >30% nodes unhealthy, critical services down | Fix infrastructure issues |
| **Compliance** | Regulatory requirements unmet | Complete compliance review |
| **Timing** | Deployment freeze, Friday PM, major holiday | Reschedule to next window |

**Risk-Based Validation:**

| Risk Level | Required Validations | Approval Authority |
|-----------|---------------------|-------------------|
| **Low** | Basic checklist (testing, security scan) | Engineering Manager |
| **Medium** | Full checklist + staging deployment | Director of Engineering |
| **High** | Full checklist + CAB + compliance | VP Engineering + CAB |
| **Critical** | Full checklist + executive + legal | CTO + CEO + Legal |

### Phase 1 – Readiness Assessment

- Use Task tool with `subagent_type="release-manager"` to compile status from QA, security, and compliance partners.
- Partner with `qa-strategist` to validate critical test suites via `commands/tools/development/testing/quality-validation.md`.

### Phase 2 – Governance & Approvals

- Engage `delivery-lead` to run the release review meeting, capturing decisions and action items.
- Loop in `privacy-officer` and `security-auditor` for regulatory checks when applicable.

### Phase 3 – Deployment Coordination

- Delegate to `developer-enablement-lead` for deployment sequencing instructions and runbook finalization.
- Ask `observability-incident-lead` to staff on-call coverage and define escalation triggers.

### Phase 4 – Launch Communications & Support

- Use `customer-success-lead` to prepare customer-facing updates and success plans.
- Coordinate with `support-analytics-specialist` to monitor support channels during rollout.

## Handoffs & Follow-Up

- Within 48 hours, capture release metrics and incident summaries for leadership.
- Schedule a release retrospective to feed improvements into the next governance cycle.
