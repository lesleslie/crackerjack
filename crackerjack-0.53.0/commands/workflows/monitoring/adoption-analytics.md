______________________________________________________________________

title: Adoption & Analytics Workflow
owner: Operations Enablement Guild
last_reviewed: 2025-02-06
related_tools:

- commands/tools/workflow/support-readiness.md
- commands/tools/monitoring/observability-lifecycle.md
  risk: medium
  status: active
  id: 01K6EF5K5NSZ099RKP9K44E6DF

______________________________________________________________________

## Adoption & Analytics Workflow

[Extended thinking: Close the loop between feature delivery and customer outcomes through data-informed rituals.]

## Overview

Run this workflow after launches or on a recurring cadence to analyze usage, adoption, and customer sentiment.

## Prerequisites

- Instrumentation and dashboards configured for the target product area.
- Access to support ticket systems and customer feedback channels.
- Baseline success metrics defined during feature planning.

## Inputs

- `$ARGUMENTS` — product area or feature to evaluate.
- `$EVALUATION_WINDOW` — time period for analysis (e.g., "last 30 days").
- `$METRICS` — key KPIs or OKRs to inspect.

## Outputs

- Adoption and performance summary with insights.
- Action plan for product, support, or enablement teams.
- Updated dashboards or alerts reflecting new targets.

## Phases

### Phase 1 – Gather Signals

- Use Task tool with `subagent_type="support-analytics-specialist"` to pull support trends and satisfaction data.
- Engage `observability-incident-lead` for telemetry on usage, latency, and error rates.
- `product-manager` compiles OKR status and experiment results.

### Phase 2 – Analyze & Interpret

- `data-scientist` performs deeper analysis on cohorts, funnels, or experiments.
- `customer-success-lead` adds qualitative insights from executive business reviews.
- `qa-strategist` assesses defect patterns to feed back into testing improvements.

### Phase 3 – Decide & Act

- `product-manager` facilitates decision meeting, prioritizing actions.
- `delivery-lead` maps resulting work into roadmaps or maintenance cadences.
- `content-designer` updates documentation or comms if behavior changes are required.

## Handoffs & Follow-Up

- Share outcomes with stakeholders and track actions in backlog systems.
- Schedule the next analytics review based on business cadence (monthly/quarterly).
