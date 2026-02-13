______________________________________________________________________

title: Automation Orchestration Playbook
owner: Developer Enablement Guild
last_reviewed: 2025-02-06
related_tools:

- commands/tools/automation/platform-automation.md
- commands/tools/development/code-quality/dependency-lifecycle.md
- commands/tools/development/testing/quality-validation.md
  risk: medium
  status: active
  id: 01K6EF5K27MTEW5SYMD2WGD74T

______________________________________________________________________

## Automation Orchestration Playbook

[Extended thinking: Consolidate automation work across pipelines, environments, and guardrails so teams can iterate quickly without fragmenting responsibilities.]

## Overview

Use this workflow to scope, implement, and socialize automation spanning build pipelines, quality gates, and telemetry.

## Prerequisites

- Confirm target repository or service ownership and availability.
- Ensure required credentials for CI/CD, observability, and package registries are provisioned.
- Review recent incidents or automation gaps to prioritize fixes.

## Inputs

- `$ARGUMENTS` — short summary of the automation goal (e.g., "CI pipeline for payments service").
- `$AUTOMATION_SCOPE` — comma-separated modes: `pipeline`, `quality`, `telemetry`, `enablement`.
- `$TARGET_ENV` — environments affected (dev, staging, prod).

## Outputs

- Automation implementation plan with owners and milestones.
- Updated pipeline or workflow definition merged to main.
- Documentation and enablement assets for ongoing upkeep.

## Phases

### Phase 1 – Discovery & Intent

- Use Task tool with `subagent_type="developer-enablement-lead"` to analyze current workflows, tooling friction, and baseline metrics for `$ARGUMENTS`.
- Capture automation backlog, success criteria, and dependency list.

### Phase 2 – Build & Integrate

- For pipeline work, delegate to `developer-enablement-lead` with prompts referencing `commands/tools/development/code-quality/dependency-lifecycle.md` for bootstrap actions.
- For quality gates, engage `qa-strategist` to design test matrices and CI/CD guardrails, aligning with `commands/tools/development/testing/quality-validation.md`.

### Phase 3 – Telemetry & Safety Nets

- Engage `observability-incident-lead` to instrument pipelines and deployments, ensuring alerting on automation failure paths.
- Consult `privacy-officer` when automation touches personal data flows.

### Phase 4 – Enablement & Handoff

- Use Task tool with `subagent_type="content-designer"` to produce runbooks and quick-start guides.
- Partner with `support-analytics-specialist` to monitor adoption metrics and gather feedback.

## Handoffs & Follow-Up

- Schedule a review with the owning squad to validate automation outcomes.
- Set recurring freshness checks (quarterly) with `developer-enablement-lead` and `observability-incident-lead` to keep guardrails current.
