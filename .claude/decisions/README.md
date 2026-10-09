---
status: active
role: canonical
date: 2026-07-20
last_reviewed: 2026-07-20
superseded_by: null
blocks_on: []
topic: lifecycle
---



# Repo-local Decisions Index

Operational and policy decisions that affect how contributors work inside
the Crackerjack repository. This index is the source of truth for
recurring rules — anything recorded here must be followed by future code,
frontmatter, or docs.

## When to add a file here

- A change introduces a recurring rule (e.g. "no speculative `required_scripts:`
  entries") that future contributors will need to know.
- A reviewer repeatedly has to explain the same tradeoff — write it down so
  the next reviewer doesn't have to.
- A script or frontmatter reference points at something that intentionally
  does not exist, and the reason for the absence should not be lost.

## When to use `docs/adr/` instead

`docs/adr/` is for **architectural decisions** — choices that affect the
structure or long-term direction of the system (e.g. "MCP-first design",
"oneiric for config"). Use ADRs when the decision is about *what to
build*; use this directory when the decision is about *how to operate
within the current build*.

## File shape

One file per topic. A short header (`## Context`, `## Decision rule`,
`## Status`) is enough; full ADR-style structure is not required.

## Current decisions

- [`tool-profile-rationale.md`](tool-profile-rationale.md) — W2a (2026-08-18)
  rationale for the `CRACKERJACK_TOOL_PROFILE` tier composition (MINIMAL /
  STANDARD / FULL) and which groups live in each tier (e.g. `eventbridge_tools`
  and `progress_tools` are FULL-only, `validate_claude_md` is STANDARD).