______________________________________________________________________

title: Stability Response Lifecycle
owner: Platform Reliability Guild
last_reviewed: 2025-02-06
related_tools:

- commands/tools/monitoring/observability-lifecycle.md
- commands/tools/maintenance/maintenance-cadence.md
- commands/tools/development/testing/quality-validation.md
  risk: high
  status: active
  id: 01K6EF5K54WWNSV9ZSCT17CF06

______________________________________________________________________

## Stability Response Lifecycle

[Extended thinking: Provide a unified playbook for hotfixes, performance tuning, and hardening without juggling multiple redundant workflows.]

## Overview

Use this workflow when production health is at risk and you must stabilize, remediate, and prevent recurrence.

## Prerequisites

- Active incident or performance signal with owner acknowledgment.
- Access to telemetry dashboards, logs, and release history.
- Alignment on severity and blast radius.

## Inputs

- `$ARGUMENTS` — incident description or degradation summary.
- `$IMPACTED_SERVICES` — list of affected services or components.
- `$SCENARIOS` — select from `hotfix`, `performance`, `hardening`.

## Outputs

- Mitigation plan with owners and timelines.
- Validated fix deployed with supporting evidence.
- Post-incident review with preventative actions tracked.

## Phases

### Phase 1 – Triage & Contain

- `observability-incident-lead` evaluates telemetry, isolates blast radius, and recommends immediate safeguards.
- `developer-enablement-lead` coordinates feature flag toggles or rollback steps.

### Phase 2 – Remediate & Validate

- For `hotfix`, engage `developer-enablement-lead` and `architecture-council` to design minimal-risk fixes.
- For `performance`, involve `data-engineer` and `observability-incident-lead` to profile bottlenecks.
- `qa-strategist` ensures validation suites target the regression using `commands/tools/development/testing/quality-validation.md`.

### Phase 3 – Harden & Prevent

- `release-manager` schedules staged rollout with guardrails from `commands/tools/deployment/release-management.md`.
- `maintenance-cadence.md` (tool) informs backlog grooming of maintenance debt.
- `finops-specialist` evaluates cost impacts if performance improvements are applied.

## Handoffs & Follow-Up

- Run a post-incident review within five business days, capturing action items and owners in maintenance trackers.
- Update runbooks and ensure monitoring/alerting thresholds reflect new learnings.
