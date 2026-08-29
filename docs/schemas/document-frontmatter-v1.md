______________________________________________________________________

## status: active role: canonical topic: lifecycle date: 2026-07-17 last_reviewed: 2026-07-17 superseded_by: null blocks_on: []

# Document Frontmatter Schema v1

**Date:** 2026-07-16
**Status:** accepted

## Goal

This schema unifies the eight ad-hoc status conventions currently scattered across Mahavishnu's six documentation stores — `.claude/decisions/`, `docs/followups/`, `docs/adr/`, `docs/superpowers/specs/`, `docs/superpowers/plans/`, and `docs/plans/` — into a single YAML frontmatter contract. After migration, agents greping for `status:` reach one source of truth, `PLAN_INDEX.md` is regenerated mechanically, and `superseded_by` / `blocks_on` are machine-readable rather than buried in prose. The contract covers 178 in-scope files and is intentionally small: eight keys plus a two-enum vocabulary.

## Vocabulary — Lifecycle

Five values, applied to the `status` field. A file carries exactly one lifecycle value.

- **`draft`** — In preparation; not yet approved for implementation or adoption.
- **`active`** — Approved and in current use; either being executed or being applied as policy.
- **`partial`** — Approved and partially implemented; remaining work is documented but not closed.
- **`shipped`** — Delivered and verified in production; closed, no follow-up expected.
- **`complete`** — Delivered; verification or follow-up may still be open. Distinguished from `shipped` by the absence of post-delivery verification.

## Vocabulary — Role

Five values, applied to the `role` field. A file carries exactly one role. Role describes the *kind* of document, not its stage.

- **`canonical`** — Authoritative reference; the file is the source of truth for its topic.
- **`implementation`** — A plan, spec, or followup that drives concrete work.
- **`umbrella`** — Aggregates multiple child plans or decisions under a single banner.
- **`historical`** — Records decisions or outcomes after they have been acted upon; preserved for traceability, not for current action.
- **`superseded`** — Replaced by a newer document; retained for the chain. Always paired with a populated `superseded_by` field.

## Full Schema

Applied to `docs/adr/`, `docs/plans/`, `docs/superpowers/specs/`, `docs/superpowers/plans/`, and `docs/followups/`.

```yaml
status: active
role: canonical
date: 2026-07-16
last_reviewed: 2026-07-16
superseded_by: null
blocks_on: []
topic: mcp-design
decision_date: 2026-07-16
id: 014-honcho-peer-model-routing-precedence
```

| Key | Required | Format | Notes |
|---|---|---|---|
| `status` | yes | one of the five lifecycle values | |
| `role` | yes | one of the five role values | |
| `date` | yes | ISO-8601 `YYYY-MM-DD` | The document's authoring or last substantive update date. |
| `last_reviewed` | yes | ISO-8601 `YYYY-MM-DD` | When the frontmatter was last verified accurate. |
| `superseded_by` | when `role: superseded` | repo-relative path or `ext:<id>` | Resolves to an existing file at validation time. |
| `blocks_on` | optional | array of paths or `ext:<id>` | Each entry resolves to a file or external identifier. |
| `topic` | yes | slug string | See [topic-vocabulary-v1.md](./topic-vocabulary-v1.md). |
| `decision_date` | ADR-only | ISO-8601 `YYYY-MM-DD` | The date the decision was ratified. |
| `id` | optional | stable identifier string | Reserved for cross-repo referencing; not required for in-repo files. |

## Lite Schema

Applied to `.claude/decisions/` only. Decisions are not chained — a decision is either current or it is not. The lite schema is the full schema minus `superseded_by` and `blocks_on`.

```yaml
status: active
role: canonical
date: 2026-07-16
last_reviewed: 2026-07-16
topic: decision-index
```

Eight keys total: `status`, `role`, `date`, `last_reviewed`, `topic`, plus `decision_date` and `id` where applicable (the `id` row from the full schema remains optional in lite context). The two chaining fields are dropped because `.claude/decisions/` files do not point at successors and are not gated on external prerequisites.

## Legacy Mapping

The migration replaces the following strings with the values shown. Each row is the *exact* legacy string observed in the corpus; the mapping is unambiguous except where noted.

| Legacy string (as observed) | Normalized `status` | Normalized `role` | Notes |
|---|---|---|---|
| Accepted | `active` | unchanged | Default for accepted ADRs. |
| Accepted (rev N) | `active` | unchanged | Revision numbers discarded. |
| approved / Approved | `active` | unchanged | Case-insensitive. |
| approved for implementation | `active` | `implementation` | Force role when context is implementation. |
| Proposed | `draft` | unchanged | |
| Proposed standard | `draft` | unchanged | |
| Draft / Drafted / Draft for review | `draft` | unchanged | |
| Ready for Implementation | `draft` | `implementation` | |
| brainstormed | `draft` | unchanged | |
| DEFERRED | `draft` | unchanged | Populate `blocks_on` with the named dependency. |
| In progress / active | `active` | unchanged | |
| Complete / completed | `complete` or `shipped` | unchanged | Read the body to determine whether verification is closed. |
| All phases complete | `complete` or `shipped` | unchanged | Same rule as Complete. |
| Delivered | `complete` or `shipped` | unchanged | Same rule as Complete. |
| Shipped / SHIPPED | `shipped` | unchanged | |
| Resolved | `complete` | `historical` | Default role is historical for closed followups. |
| Superseded / SUPERSEDED | `complete` | `superseded` | Populate `superseded_by` with the successor path. |
| (no frontmatter) | `draft` | `implementation` | Default for files with no status marker and no plan context. |
| (no frontmatter, umbrella context) | `active` | `umbrella` | For plans that aggregate other plans. |

The 12-row minimum is satisfied by the rows above. Cases where body semantics disambiguate (Complete vs. Shipped, Resolved with non-historical role) require manual review by the migrating agent.

## Topic Vocabulary

Topics are slug strings applied to the `topic` field. The controlled list lives in [`docs/schemas/topic-vocabulary-v1.md`](./topic-vocabulary-v1.md). The initial seed list contains ten well-established topics: `mcp-design`, `storage-consolidation`, `adapter-architecture`, `terminal`, `routing-composition`, `learning-pipeline`, `observability`, `auth`, `convergence-control-plane`, `worktree-management`.

The validator runs in **hybrid mode**: known topics pass without warning; unknown topics pass with a `--strict` warning so the maintainer can decide whether to expand the vocabulary or normalize the value. Editing the vocabulary file is a normal doc change requiring no plan amendment.

## Regeneration

`docs/plans/PLAN_INDEX.md` is **mechanically regenerated** from the frontmatter defined by this schema. Run:

```bash
uv run python scripts/regenerate_plan_index.py          # write to docs/plans/PLAN_INDEX.md
uv run python scripts/regenerate_plan_index.py --dry-run # print to stdout, do not write
uv run python scripts/regenerate_plan_index.py --out path/to/other.md
uv run python scripts/regenerate_plan_index.py --json-summary # emit per-store counts on stderr
```

Discovery rules (mirrors the validator's exclusion list):

- Default stores: `docs/adr/`, `docs/plans/`, `docs/superpowers/specs/`, `docs/superpowers/plans/`, `.claude/decisions/`, `docs/followups/`.
- Always excluded: `docs/plans/PLAN_INDEX.md` (self-skip), `docs/plans/drafts/`, any `*.archive*` or `*.backup*` subdirectory or suffix.
- Output is rendered with a fixed frontmatter block, the Status Legend, an Authority Matrix, a Review Entry Points block, one registry table per store (sorted by `date` DESC), and a Lifecycle × Role distribution table at the bottom.
- Files without valid frontmatter are silently skipped — they are the validator's job, not the indexer's.

Because the index is regenerated, the file is **not hand-edited**; do not edit by hand. If the index needs to change, change this schema (or the regenerator script) and re-run it. The output file's `Last regenerated:` line records the date of the last successful regeneration.

## Approved Adjustments

Two open questions were resolved before migration began. Both are binding for Phases P0–P6.

- **Adjustment A — Hybrid `topic` vocabulary.** Synonym-drift risk surfaced by adversarial review (e.g. `tui` vs `terminal-ui` vs `tui-design`) led to a curated seed list plus warning-mode acceptance for unknown topics. The vocabulary file is `docs/schemas/topic-vocabulary-v1.md`; editing it is a normal doc change.
- **Adjustment B — Two-pass per-store migration.** P3 specs point at P2 plans via `superseded_by`, so single-pass validation would either fail on forward-pointing links or silently pass them. Pass 1 writes frontmatter only (link validation skipped). Pass 2 is a single post-P5 link-validation sweep across the entire corpus. P6 is blocked until that sweep clears with zero broken links.

## Cross-References

- [`docs/schemas/topic-vocabulary-v1.md`](./topic-vocabulary-v1.md) — controlled topic list (seed + amendment rule).
- [`docs/plans/PLAN_INDEX.md`](../plans/PLAN_INDEX.md) — the index regenerated from frontmatter in Phase P6.
- [`.claude/decisions/README.md`](../../.claude/decisions/README.md) — the decision index; Status column re-derived from per-decision frontmatter in Phase P5.

## Change History

- **2026-07-16** — v1. Initial schema covering the 178 in-scope files across six stores; full and lite variants; legacy mapping table.

## Crackerjack Surface

The validator is wrapped by Crackerjack so the same checks run during
`crackerjack run` (in the `documentation_cleanup` phase), via the CLI
(`crackerjack docs validate [--strict] [--store] [--validate-links] [--json]`),
and via the MCP tool `mcp__crackerjack__crackerjack_doc_frontmatter_validate`.

The wrapper invokes the validator as a subprocess (one-directional
dependency: Crackerjack → Mahavishnu). The validator remains the single
source of truth in this repo; Crackerjack imports it via
`mahavishnu.scripts.validate_document_frontmatter`.

See the design doc
`docs/superpowers/specs/2026-07-16-frontmatter-validator-wiring-design.md`
for full integration details.
