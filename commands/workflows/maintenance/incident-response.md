______________________________________________________________________

title: Incident Response Workflow
owner: Platform Reliability Guild
last_reviewed: 2025-02-06
related_tools:

- commands/tools/monitoring/observability-lifecycle.md
  risk: critical
  status: active
  id: 01K6EF8EJN8EVC240V87X7KH92

______________________________________________________________________

## Incident Response Workflow

[Extended thinking: Provide a reliable incident lifecycle from detection through postmortem with clear ownership and communications.]

## Overview

Activate this workflow when a service degradation or outage is declared.

## Prerequisites

- Incident commander assigned and severity agreed.
- Communication channels (Slack, Zoom, StatusPage) ready.
- Access to telemetry and deployment history.

## Severity Level Definitions

| Level | Definition | Response Time | Communication | Examples |
|-------|-----------|---------------|---------------|----------|
| **SEV1** | Complete service outage, customer data at risk, major revenue impact, security breach | **15 minutes** | Immediate executive notification, public status page update, customer emails | Database down, authentication broken, payment processing failed, data breach, complete site outage |
| **SEV2** | Major feature degraded, significant customer subset affected, revenue impact | **1 hour** | Status page update, affected customer notification | Search broken, slow API response (>5s), critical feature unavailable, region outage |
| **SEV3** | Minor feature issue, workaround available, limited customer impact | **4 hours** | Internal tracking, optional status page update | UI glitch affecting single page, minor feature bug, non-critical service degraded |
| **SEV4** | Cosmetic issue, no customer impact, tracking item | **24 hours** | Internal tracking only | Documentation error, minor UI cosmetic issue, tech debt item, improvement idea |

### Automated Incident Declaration Triggers

**SEV1 Auto-Declaration:**

- Error rate > 10% for > 5 minutes
- Authentication failure rate > 5%
- Database connection failures
- Payment processing failures > 1%
- Security alerts (unauthorized access, data exfiltration)

**SEV2 Auto-Declaration:**

- Error rate 5-10% for > 15 minutes
- API response time > 5 seconds (p95) for > 10 minutes
- Major feature availability < 95% for > 15 minutes
- Customer support ticket spike > 3x baseline

**Incident Commander Assignment:**

- SEV1/SEV2: On-call Platform Reliability Engineer immediately assigned
- SEV3: On-call engineer notified, can defer if handling higher severity
- SEV4: Assigned during business hours, tracked in backlog

### Response Time SLAs

| Severity | Time to Acknowledge | Time to Mitigation | Time to Resolution |
|----------|-------------------|-------------------|-------------------|
| SEV1 | 15 minutes | 1 hour | 4 hours |
| SEV2 | 1 hour | 4 hours | 24 hours |
| SEV3 | 4 hours | 24 hours | 1 week |
| SEV4 | 24 hours | 1 week | 1 month |

## Inputs

- `$ARGUMENTS` — incident summary and customer impact.
- `$SEVERITY` — incident severity level (SEV1–SEV4).
- `$AFFECTED_AREAS` — services or regions impacted.

## Outputs

- Mitigation status log and incident timeline.
- Verified fix with supporting evidence.
- Post-incident report and follow-up actions.

## Workflow Visualization

```mermaid
graph TB
    Alert([Alert Triggered]) --> Severity{Severity Level?}

    Severity --> |SEV1: Complete outage<br/>Data at risk<br/>Security breach| SEV1[SEV1 Response]
    Severity --> |SEV2: Major degradation<br/>Significant impact| SEV2[SEV2 Response]
    Severity --> |SEV3: Minor issue<br/>Workaround available| SEV3[SEV3 Response]
    Severity --> |SEV4: Cosmetic<br/>No customer impact| SEV4[SEV4 Track Only]

    SEV1 --> IC1[Assign Incident Commander<br/>< 15 minutes]
    SEV2 --> IC2[Assign Incident Commander<br/>< 1 hour]
    SEV3 --> IC3[Assign On-Call Engineer<br/>< 4 hours]
    SEV4 --> Track[Track in Backlog]

    IC1 --> Triage1[Phase 1: Triage & Containment]
    IC2 --> Triage1
    IC3 --> Triage1

    Triage1 --> |Observability Lead| Investigate[Investigate Logs/Metrics]
    Triage1 --> |Developer Enablement| Contain[Rollback/Traffic Reroute]

    Investigate --> RootCause{Root Cause Found?}
    Contain --> RootCause

    RootCause --> |YES| Resolution[Phase 2: Resolution & Validation]
    RootCause --> |NO| Escalate[Escalate to Specialists]

    Escalate --> Resolution

    Resolution --> |Development Squad| Implement[Implement Fix]
    Resolution --> |QA Strategist| Validate[Validate in Staging]

    Implement --> Deploy{Deploy Fix?}
    Validate --> Deploy

    Deploy --> |Gradual Rollout| Monitor[Monitor Metrics]
    Deploy --> |Full Deploy| Monitor

    Monitor --> Recovered{Service Recovered?}
    Recovered --> |YES: Metrics normal<br/>Error rate < baseline<br/>No customer reports| Communicate[Phase 3: Communication & Postmortem]
    Recovered --> |NO: Still degraded| Rollback[Rollback Fix]

    Rollback --> Resolution

    Communicate --> |Customer Success| NotifyCustomers[Notify Affected Customers]
    Communicate --> |Incident Commander| UpdateStatus[Update Status Page]
    Communicate --> |Team| Postmortem[Conduct Postmortem]

    Postmortem --> ActionItems[Create Action Items]
    ActionItems --> Prevention[Implement Prevention Measures]

    Track --> End([Incident Closed])
    Prevention --> End

    style Alert fill:#ffe1e1
    style SEV1 fill:#ff9999
    style SEV2 fill:#ffcc99
    style SEV3 fill:#ffff99
    style SEV4 fill:#e1f5e1
    style End fill:#c6efce
    style Rollback fill:#ff9999
```

## Phases

### Phase 1 – Triage & Containment

- `observability-incident-lead` leads investigation using `commands/tools/monitoring/observability-lifecycle.md`.
- `developer-enablement-lead` assists with feature flags, rollbacks, or traffic rerouting.

### Phase 2 – Resolution & Validation

- Task `development` squads via `developer-enablement-lead` to implement fixes.
- `qa-strategist` validates remediation using targeted regression suites.

### Phase 3 – Communication & Recovery

- `release-manager` coordinates controlled rollout of the fix.
- `customer-success-lead` manages customer updates and executive summaries.

### Phase 4 – Post-Incident Review

- `observability-incident-lead` documents timeline and contributing factors.
- `finops-specialist` or `privacy-officer` join when impact includes cost or data exposure.

## Postmortem Template

**Required for:** SEV1 (within 48 hours), SEV2 (within 1 week)
**Optional for:** SEV3, SEV4

### 1. Incident Summary

- **Incident ID:** [Auto-generated]
- **Severity:** SEV1 / SEV2 / SEV3 / SEV4
- **Duration:** [Time from detection to full resolution]
- **Incident Commander:** [Name]
- **Teams Involved:** [List all teams]

### 2. Impact Assessment

- **Customer Impact:** [Number of users affected, % of total]
- **Service Impact:** [Which services/features were degraded]
- **Revenue Impact:** [Estimated financial impact if applicable]
- **Data Impact:** [Any data loss, corruption, or exposure]
- **SLA Breach:** [Yes/No, which SLAs were violated]

### 3. Timeline

| Time | Event | Action Taken | Owner |
|------|-------|-------------|-------|
| HH:MM | Initial detection | Alert fired from monitoring | System |
| HH:MM | Incident declared | IC assigned, war room opened | [Name] |
| HH:MM | Root cause identified | [Brief description] | [Name] |
| HH:MM | Mitigation deployed | [What was done] | [Name] |
| HH:MM | Service restored | Metrics returned to baseline | [Name] |
| HH:MM | Incident closed | All systems verified healthy | [Name] |

### 4. Root Cause Analysis

**What Happened:**
[Detailed technical explanation of what went wrong]

**Why It Happened:**

- **Immediate Cause:** [Direct technical trigger]
- **Contributing Factors:** [Configuration, process, human factors]
- **Underlying Cause:** [Systemic issues that allowed this to happen]

### 5. What Went Well

- [Things that helped resolve the incident quickly]
- [Monitoring/alerting that worked effectively]
- [Team coordination successes]

### 6. What Went Poorly

- [Gaps in monitoring or alerting]
- [Communication breakdowns]
- [Process failures]
- [Technical debt that contributed]

### 7. Action Items

| Priority | Action | Owner | Due Date | Status |
|----------|--------|-------|----------|--------|
| P0 | [Critical preventive measure] | [Name] | [Date] | Open |
| P1 | [High-priority improvement] | [Name] | [Date] | Open |
| P2 | [Medium-priority task] | [Name] | [Date] | Open |

### 8. Prevention & Detection Improvements

- **Monitoring:** [New alerts, dashboards, or metrics to add]
- **Testing:** [Test coverage gaps to address]
- **Documentation:** [Runbooks or procedures to create/update]
- **Architecture:** [System changes to prevent recurrence]

### 9. Lessons Learned

[Key takeaways that apply to future incidents or system design]

## Handoffs & Follow-Up

- Track all action items in maintenance cadences until resolved.
- Update runbooks and monitor configurations to prevent recurrence.
- Schedule postmortem review meeting for SEV1/SEV2 incidents.
- Share postmortem with broader engineering team and leadership.
