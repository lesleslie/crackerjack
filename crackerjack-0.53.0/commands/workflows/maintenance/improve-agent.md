______________________________________________________________________

title: Agent Improvement Workflow
owner: Developer Enablement Guild
last_reviewed: 2025-02-06
related_tools:

- commands/tools/development/code-quality/dependency-lifecycle.md
- commands/tools/development/testing/quality-validation.md
  risk: medium
  status: active
  id: 01K6EF8EM6WQWW9KGRHXS02CMP

______________________________________________________________________

## Agent Improvement Workflow

[Extended thinking: Enhance Claude subagents with structured analysis, implementation, and validation.]

## Overview

Follow this workflow to update or extend an existing subagent’s capabilities.

## Prerequisites

- Current agent instructions and usage analytics.
- Identified gaps or feedback from users.
- Access to test harnesses for verification.

## Inputs

- `$ARGUMENTS` — target agent name and desired improvement.
- `$IMPROVEMENT_TYPE` — e.g., `scope`, `tone`, `playbook`, `metadata`.
- `$SUCCESS_METRICS` — criteria showing the update is effective.

## Outputs

- Revised agent instructions and metadata.
- Test results confirming expected behavior.
- Changelog entry for catalog governance.

## Phases

### Phase 1 – Assess & Plan

- `support-analytics-specialist` reviews usage logs and feedback to prioritize needs.
- `product-manager` aligns improvements with business impact.

### Phase 2 – Design & Draft

- `developer-enablement-lead` updates structure and metadata referencing `commands/tools/development/code-quality/dependency-lifecycle.md` for schema checks.
- `content-designer` polishes tone, clarity, and consistency.

### Phase 3 – Validate & Iterate

- `qa-strategist` runs scenario tests and regression prompts via `commands/tools/development/testing/quality-validation.md`.
- `observability-incident-lead` ensures any telemetry hooks remain valid.

### Phase 4 – Publish & Communicate

- `release-manager` coordinates catalog update and change announcement.
- `customer-success-lead` informs stakeholders if the agent is externally visible.

## Handoffs & Follow-Up

- Schedule follow-up review to measure success metrics.
- Archive previous agent versions for auditability.
