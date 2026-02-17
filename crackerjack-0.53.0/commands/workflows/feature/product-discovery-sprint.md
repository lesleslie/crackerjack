______________________________________________________________________

title: Product Discovery Sprint
owner: Product Leadership
last_reviewed: 2025-02-06
related_tools:

- commands/tools/workflow/privacy-impact-assessment.md
- commands/tools/workflow/support-readiness.md
  risk: medium
  status: active
  id: 01K6EF5K4BN0K2WRJC4MC0Q969

______________________________________________________________________

## Product Discovery Sprint

[Extended thinking: Align cross-functional partners on the problem space before investing in delivery.]

## Overview

This workflow guides a one- to two-week discovery sprint to clarify user problems, validate hypotheses, and prioritize solutions.

## Prerequisites

- Executive sponsor or product trio ready to invest in discovery.
- Access to stakeholders, users, or proxies for interviews.
- Agreement on decision criteria for prioritization.

## Inputs

- `$ARGUMENTS` — problem statement or opportunity area.
- `$DISCOVERY_SCOPE` — focus areas such as `user-research`, `data-analysis`, `compliance`.
- `$DECISION_DATE` — date to present findings.

## Outputs

- Discovery brief with validated insights and recommended next steps.
- Prioritized backlog or experiment plan.
- Risk and compliance considerations documented.

## Phases

### Phase 1 – Frame & Plan

- `product-manager` refines goals, success metrics, and stakeholder map.
- `ux-researcher` designs the research plan and recruiting needs.
- `support-analytics-specialist` surfaces existing customer feedback or ticket data.

### Phase 2 – Explore & Validate

- Conduct interviews and usability tests via `ux-researcher` with focus from `$DISCOVERY_SCOPE`.
- Use `data-scientist` for quantitative validation when data analysis is required.
- Engage `privacy-officer` leveraging `commands/tools/workflow/privacy-impact-assessment.md` if personal data is involved.

### Phase 3 – Synthesize & Decide

- `product-manager` facilitates synthesis workshop, distilling insights into opportunity solution trees.
- `delivery-lead` assesses feasibility and sequencing for candidate solutions.
- `customer-success-lead` outlines early adopter enablement and feedback loops.

## Handoffs & Follow-Up

- Present discovery outcomes to leadership, capturing go/no-go decisions.
- Feed prioritized items into the Feature Delivery Lifecycle workflow.
