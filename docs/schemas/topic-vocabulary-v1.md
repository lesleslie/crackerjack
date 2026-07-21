______________________________________________________________________

## status: active role: canonical topic: lifecycle date: 2026-07-17 last_reviewed: 2026-07-17 superseded_by: null blocks_on: []

# Topic Vocabulary v1

**Date:** 2026-07-16
**Status:** accepted

## Goal

This document provides a curated seed list of roughly ten topic slugs used in
the `topic:` field of YAML frontmatter across Bodai documentation. The
vocabulary is intentionally small and opinionated: it exists to keep the most
common documentation areas consistently labeled so they can be grouped,
filtered, and cross-referenced. Free-form values are **allowed** — a document
may use a `topic:` slug that is not in this seed list — but the frontmatter
validator will emit a **warning** for any slug it does not recognize, nudging
authors either to reuse an existing slug or to add a new one here via the
contribution workflow below.

## Seed List

| Slug | Definition |
|------|------------|
| `oneiric-config` | Oneiric layered configuration (defaults, settings/*.yaml, MAHAVISHNU\_* env vars). |
| `mcp-design` | MCP-first architecture, tool registration, server design. |
| `error-handling` | Exception hierarchy, retry, circuit breaker, dead-letter queue (ADR 003). |
| `storage-consolidation` | Akosha/Dhara/Session-Buddy storage ownership. |
| `memory-architecture` | Unified memory layer across Bodai components (ADR 005). |
| `adapter-architecture` | Engine adapter (Prefect/LlamaIndex/Agno/Pydantic-AI) patterns. |
| `adapter-registry` | Hybrid adapter registry with dynamic discovery (ADR 009). |
| `adapter-security` | Adapter security specification (ADR 010). |
| `adapter-tool-boundary` | Mahavishnu ↔ Dhara adapter-tool boundary (ADR 013). |
| `saga-pattern` | Saga coordinator for distributed transactions (ADR 007). |
| `zero-downtime-migration` | Zero-downtime SQLite-to-PostgreSQL migration (ADR 008). |
| `terminal` | iTerm2, MockTerminal, CrowTerminal, GenericShellWorker, workers/protocol.py. |
| `routing-composition` | Two-router composition, fitness feedback loop, peer affinity (ADR 011 / ADR 014). |
| `honcho-routing` | Honcho peer-model routing precedence (ADR 014). |
| `learning-pipeline` | Skill distillation, conscious agent, pattern library (ADR 012). |
| `observability` | Bodai observability surface, EventBridge subscriber pattern, Phase 6. |
| `auth` | Auth standardization (Bodai auth spec), JWT, multi-provider. |
| `convergence-control-plane` | Convergence program C0-C7, umbrella plans. |
| `worktree-management` | Worktree MCP dispatcher, isolation, planning. |
| `persistence` | State persistence across checkpoints, session restarts, and subagent dispatch windows (covers git stash/rebase cycles, auto-checkpoint hooks, durable storage paths). |
| `lifecycle` | Wiring lifecycle for components, plans, and followups — drafted/active/partial/shipped/complete transitions, completion reports, plan-to-followup handoffs. |
| `plugin-standardization` | Claude Code plugin manifest, marketplace layout, slash command namespace, plugin validation scaffold (introduced for Bodai plugin rollout 2026-07-16). |
| `architecture` | Project-wide architecture, module boundaries, integration diagrams, design docs, ADR source material. (Crackerjack addition 2026-07-17.) |

## Contribution Workflow

Anyone can add a topic to this list via a normal documentation PR — **no schema
amendment is needed**. To add a topic, edit this file's seed list table in a PR
that includes:

- **Slug** — kebab-case, matching `^[a-z][a-z0-9-]{2,40}$`.
- **One-line definition** — a concise description of what the topic covers.
- **Area association** — the ecosystem area, component, or ADR the topic maps to.

The validator rejects malformed slugs (see the validation rules below), so a PR
that introduces a slug not matching the pattern will fail validation before it
can be merged.

## Validation Rules

- Slug is **kebab-case**.
- Slug **length is 3-40 characters**.
- Slug **starts with a letter** (matches `^[a-z][a-z0-9-]{2,40}$`).
- Slugs **must be unique** within this file.
- Slug **must not be a reserved word**. The reserved words are:
  `draft`, `active`, `partial`, `shipped`, `complete`, `canonical`,
  `implementation`, `umbrella`, `historical`, `superseded`.

## Cross-Reference

See [document-frontmatter-v1.md](document-frontmatter-v1.md) for the frontmatter
contract that consumes this vocabulary.
