---
status: active
role: canonical
date: 2026-08-11
last_reviewed: 2026-08-11
superseded_by: null
blocks_on: []
topic: lifecycle
---

# Feature Tracking Template

> Copy this file to `docs/feature-tracking/<YYYY-MM-DD>-<feature-slug>.md` and fill in the sections. Filename convention matches `docs/superpowers/plans/`.
>
> Referenced by `crackerjack/CLAUDE.md` (Process Discipline → "Track `{built, wired, adopted}` state for every feature") and by every implementation plan that lands in `docs/superpowers/plans/`.

**What this is for:** Tracking the *delivery lifecycle* of a feature from "code exists" through "in production use" through "removed." It is **not** a feature spec or architecture doc — those live in `docs/features/<feature>.md`. One tracking entry per feature; reference the canonical doc from the `links.canonical_doc` field below.

## Lifecycle states

| State | Definition of done | Typical duration |
|-------|-------------------|------------------|
| `draft` | This entry exists; the feature is proposed but not committed. | hours → days |
| `built` | Code lands (PRs merged, tests pass). Wiring work is **open** and dated. | days → weeks |
| `wired` | Code is exercised by an end-to-end call site (CLI flag, hook invocation, MCP tool call). Demonstrable per the plan's Integration Contract. | weeks |
| `adopted` | Observability shows the feature in regular production use across the target surface. No "release-blocker" issues open for ≥ 1 release. | steady-state |
| `decommissioned` | Feature removed from the codebase. `superseded_by` points at the replacement (or `null` if no successor). | terminal |

Per `crackerjack/CLAUDE.md`:

> A feature stays in `built` state only while the wiring work is open and dated.

When the wiring work closes, transition `built → wired` immediately. Do **not** park a feature in `built` once it is wired — that state is reserved for "code exists, no caller yet."

`★ Insight ─────────────────────────────────────`
The state machine intentionally treats `built` as a *transitional* state, not a stable resting point. This forces a hard question after every code merge: "who calls this?" If the answer is "nobody yet," the feature is unfinished — either wire it in this PR or mark it `draft` and remove it. This is the same posture as the wire-up contract: a built-but-not-wired feature is dead weight that erodes trust in the codebase.
`─────────────────────────────────────────────────`

## Transitions

Record every transition in the table below. The `evidence` column must point at a concrete artifact (PR URL, commit SHA, plan task ID, observability dashboard query, etc.).

| From | To | Date | Trigger | Evidence |
|------|----|------|---------|----------|
| (none) | `draft` | YYYY-MM-DD | Entry created | — |
| `draft` | `built` | YYYY-MM-DD | Code landed | `<PR URL or commit SHA>` |
| `built` | `wired` | YYYY-MM-DD | First end-to-end call site exercised | `<plan task id, hook name, CLI command>` |
| `wired` | `adopted` | YYYY-MM-DD | Production observability shows regular use | `<dashboard query, log sample, sweep report>` |
| `<state>` | `decommissioned` | YYYY-MM-DD | Removal commit landed | `<commit SHA>` |

A feature that goes straight from `draft` to `wired` (no separate `built` window) is fine — collapse the rows. A feature that lands in `built` and then sits for > 30 days without transitioning is a red flag; either wire it or delete it.

## Frontmatter (edit in place)

```yaml
---
status: <draft|built|wired|adopted|decommissioned>     # current state
role: lifecycle                                           # always "lifecycle" for tracking entries
topic: <lifecycle|quality|adapters|mcp|hooks|...>        # one of the project topic tags
date: YYYY-MM-DD                                          # entry created
last_reviewed: YYYY-MM-DD                                 # most recent review
superseded_by: null                                       # set to filename of replacement entry if decommissioned
blocks_on: []                                             # list of feature-tracking entries this depends on
---
```

The `status` field **must** match the latest row of the Transitions table. If they disagree, the entry is stale and needs a review.

## Required content

### Summary

One paragraph (3-5 sentences): what the feature does, what surface it lives in, and the current state.

### Why

Bullet list of the concrete reasons this feature exists. Each bullet should be answerable with "yes / no / measured" evidence (a bug ticket, a benchmark, a usage number). Vague goals ("improve DX") do not count.

### What is delivered

Bullet list of the user-visible behavior, hook names, CLI flags, or MCP tools that landed. Keep this concrete — names, paths, flags. The wire-up contract's "Demonstrable by" criterion is the input here.

### Links

- **Plan:** `docs/superpowers/plans/<plan-filename>.md` — the implementation plan this entry tracks. Required.
- **Canonical doc:** `docs/features/<feature>.md` — if a feature-level architecture/usage doc exists. Optional but recommended for `adopted` features.
- **Issue / discussion:** ticket URLs, design-doc paths, or Slack thread links that justify the feature.
- **Related entries:** list of other feature-tracking entries this depends on or supersedes. Symmetric with `blocks_on`.

### Rollback signal

The exact reversible action an operator takes if the feature needs to be turned off. Examples:
- "Set `enable_<feature>: false` in `settings/local.yaml`."
- "Run `git revert <SHA>` of the wiring commit."
- "Unset the CLI flag and re-run `crackerjack`."

If rollback is not possible without a code change, say so explicitly. That is itself a signal that the feature should not have shipped without a flag.

### Observability

How to confirm the feature is in `adopted` state. List concrete queries (Prometheus, log files, sweep reports). If no observability exists yet, that is a gap to close before transitioning from `wired` to `adopted`.

## Review cadence

- `draft` entries: review weekly until they move to `built` or are deleted.
- `built` entries: review weekly; `built` should not exceed 30 days without a transition.
- `wired` entries: review at each minor release until `adopted`.
- `adopted` entries: review quarterly. Update `last_reviewed`.
- `decommissioned` entries: terminal. No further reviews required.

## Examples

The two existing plans that already cite this template are good references once their tracking entries are written:

- `docs/superpowers/plans/2026-08-11-skill-coverage-out-of-fast-hooks.md` (skill-coverage removal — already in `docs/feature-tracking/`-shaped state via Phase 4-5 of that plan)
- `docs/superpowers/plans/2026-08-11-darnlink-replaces-check-local-links.md` (this template's first real user, when implementation begins)

When in doubt, look at how those entries resolve their `{built, wired, adopted}` mapping in the plans' Self-review sections, then mirror that structure here.

---

# Example filled-in entry (delete this section before committing the template)

The block below shows what a complete entry looks like once filled. **Delete it before committing the template as a real file.** It exists only to give the implementer a concrete shape to copy from.

```markdown
---
status: wired
role: lifecycle
topic: hooks
date: 2026-08-11
last_reviewed: 2026-08-11
superseded_by: null
blocks_on: []
---

# Magic-Hook Feature

## Summary

`magic-hook` adds a fast local link checker that survives markdown file refactors by anchoring links to per-target UUIDs. Replaces `check-local-links`. Currently wired into `crackerjack run` as the default local link checker.

## Why

- `check-local-links` produces false-negatives on `#anchor` references — it only validates file paths.
- Renaming a markdown file in the docs tree breaks every link to it; UUID anchoring makes those links refactor-survivable.
- The AI-fix subsystem (removed in commit `907ab860`) used to speculate about moved files; UUID anchors give deterministic lookup.

## What is delivered

- `crackerjack/tools/darnlink_wrapper.py` — subprocess wrapper around `darnlink check --format json`.
- `HookDefinition(name="darnlink", enable_flag="enable_darnlink")` registered in `crackerjack/config/hooks.py`.
- Parser registered in `crackerjack/parsers/regex_parsers.py`.
- Exit code mapping: `0` clean, `1` any failure, `127` tool missing.

## Transitions

| From | To | Date | Trigger | Evidence |
|------|----|------|---------|----------|
| (none) | `draft` | 2026-08-11 | Entry created | — |
| `draft` | `built` | 2026-08-15 | Wrapper + tests landed | commit `abc1234` |
| `built` | `wired` | 2026-08-22 | `crackerjack --enable-darnlink run` exercised end-to-end | plan task 1.7 |

## Links

- **Plan:** `docs/superpowers/plans/2026-08-11-darnlink-replaces-check-local-links.md`
- **Canonical doc:** `docs/features/DARNLINK_HOOK.md` (pending)
- **Issue / discussion:** bodai/bodai#145
- **Related entries:** none

## Rollback signal

Set `enable_darnlink: false` in `settings/local.yaml` and re-run. `darnlink` becomes dormant; `check-local-links` resumes as the authoritative local link checker.

## Observability

- Log file: `~/.crackerjack/logs/darnlink.log` (one JSON line per finding).
- Metric: `crackerjack_darnlink_findings_total` (counter, exposed via the Prometheus exporter).
- Sweep dashboard: `mahavishnu/monitoring/dashboards/sweep.json` column "darnlink clean / has findings" per repo.
```