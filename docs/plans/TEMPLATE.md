---
status: active
role: canonical
kind: template
title: "Plan Template — Integration-Contract Required"
date: 2026-11-14
last_reviewed: 2026-11-14
superseded_by:
topic: process-discipline
---

# Plan Template — Integration-Contract Required

> **Why this template exists**: a plan is not "done" until every phase
> deliverable has an Integration Contract block, even if that block says
> "no wiring required (rationale: …)". A deliverable nobody can point a
> command at is a deliverable nobody will notice is missing.
>
> This is crackerjack's own template. The sibling repo
> (`~/Projects/mahavishnu/docs/plans/TEMPLATE.md`) has a different one with
> requirements-traceability machinery (`scripts/audit_requirements.py`,
> `requirements:` frontmatter, `REQ-NNN` IDs) that crackerjack does not have.
> Do not copy that one here.
>
> Frontmatter vocabulary: `docs/schemas/document-frontmatter-v1.md`.

## Frontmatter

```yaml
---
title: <Human-readable title>
description: "<One paragraph: what changes, and what the reader needs to know to act.>"
audience: crackerjack maintainer
created: YYYY-MM-DD
status: draft          # draft | active | partial | shipped | complete
role: implementation   # canonical | implementation | umbrella | historical | superseded
topic: architecture
date: YYYY-MM-DD
last_reviewed: YYYY-MM-DD
superseded_by: null
blocks_on: []
---
```

`status`, `role`, `date`, `last_reviewed` and `topic` are **required** — the
frontmatter validator enforces them (`crackerjack/services/frontmatter.py`).

After writing a plan, regenerate the index:

```bash
python -m crackerjack.tools.plan_index_sync
```

## 1. Brief (intent-driven)

### Goal

\<What user-observable change exists when this plan ships? How will we know
it succeeded — a concrete metric, signal, or artifact?>

### Constraints

- <What this plan may not touch. Name other plans that own files here.>
- \<Version bumps and PyPI publishes are the operator's.>
- \<Push is the operator's.>
- \<One commit per phase, each independently revertible.>

### Failure Conditions (verifier-only)

\<The conditions a verifier can mechanically check after each phase. Each must
be checkable — a grep, a command, a file's existence or absence. A condition
that cannot be checked is not a failure condition.>

1. <checkable condition>
2. <checkable condition>

## 2. Context

\<What was discovered, with `file:line` citations. State what is live, what
is dead, and how each was established — do not assert reachability from a
grep alone; name the mechanism.>

\<The taxonomy table, the consumer map, the inventory. If a claim is
load-bearing, it gets a citation.>

## 3. Phases

One `## Phase N — <name>` per phase. Each carries the same five blocks.

### Scope

\<The files and symbols this phase touches. Name files explicitly; do not
describe a package as "the X layer" unless every module in it has been
inventoried and given a verdict.>

### Integration Contract

- **Triggered from**: \<the exact symbol, command path, MCP tool, or scheduler
  invocation that reaches the new code>
- **Returns to / updates**: \<the destination state, file, store, or artifact>
- **Demonstrable by**: \<one checkable proof — a command, a request, a log line,
  a test name>
- **Rollback signal**: \<the log line, metric threshold, or failure that says
  this landed wrong>
- **Observability added**: <what a user can now see that they could not before>

### Resolved decisions

\<Numbered. Each entry states the decision and why. A decision that is still
open does not belong in this block — either resolve it here, or name it in
the phase's Scope as a blocking prerequisite.>

### Risks

\<Numbered. What could go wrong, and what happens if it does.>

### Estimated scope

\<Modules, lines, and test files. A guess that is wrong by 2× is a bad guess.>

## 4. Risks

\<Risks that span phases: ordering against other plans, public API removal,
behaviour changes with no rollback story.>

## 5. References

- \<Other plans, decision records, commits.>

## 6. Execution record

<Leave as the placeholder below. The executing session fills it in.>

_(To be filled in as the phases execute. Each phase records the commit SHA,
the baseline captured before it, the deltas it produced, and any decision
taken that the plan left open. The closing entry names the findings that
turned up during execution that the plan did not anticipate.)_
