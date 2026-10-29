---
title: Crackerjack Oneiric Action-Kit Adoption Audit — Findings and Remediation Plan
description: Audit crackerjack against the oneiric action-kit catalog, record which kits fit and which do not, remove a 235-line duplicated retry module, correct the catalog's stale adoption metadata, and adopt the two kits whose API genuinely matches a crackerjack call site.
audience: crackerjack maintainer
created: 2026-10-28
status: active
role: implementation
topic: action-kit-adoption
date: 2026-10-28
last_reviewed: 2026-10-28
superseded_by: null
blocks_on: []
---

# Crackerjack Oneiric Action-Kit Adoption Audit — Findings and Remediation Plan

## Brief (intent-driven)

### Goal

crackerjack's primitives that duplicate a `oneiric.actions` kit are either
adopted from the kit or carry a documented reason they do not fit; no
duplicated implementation survives in the tree; and the kit catalog's
adoption metadata is true, so the discovery surface does not mislead
contributors.

### Audit result

The audit ran a per-kit trigger scan over all **1264** tracked Python files
and then hand-verified every candidate site. The headline is that
**crackerjack's kit-adoption opportunity is narrow** — the catalog's kits
were designed for shapes crackerjack does not have — but the scan surfaced
one significant defect and two significant truthfulness gaps.

#### Fit matrix

| Kit | crackerjack site | Verdict |
|---|---|---|
| `security.signature` | `crackerjack/services/status_authentication.py:226,290` | **Adopt** — keyed HMAC over a message, exactly the kit's shape |
| `security.secure` | `crackerjack/services/status_authentication.py:85,102` | **Adopt** — secret/token generation, exactly the kit's shape |
| `workflow.retry` | `crackerjack/core/retry.py:20-56` | **Partial** — the kit *computes* the next delay; crackerjack needs the loop |
| `http.fetch` | `services/connection_pool.py`, `skills/github_client.py`, `skills/health.py` | Skip — pooled httpx clients with auth headers; the kit builds its own per-call client |
| `data.sanitize` | `services/secure_status_formatter.py` (484 lines) | Skip — the kit filters *record fields*; crackerjack redacts *string content* |
| `compression.hash` | `services/file_hasher.py` | Skip — the kit hashes *values* for idempotency keys; crackerjack digests *file bytes* for change detection |
| `validation.schema` | `services/input_validator.py` | Skip — the kit is JSON Schema type enforcement; crackerjack is regex-based SQL/code-injection detection |
| `compression.encode`, `compression.stream`, `data.transform`, `debug.console`, `event.dispatch`, `serialization.encode`, `task.schedule`, `workflow.audit`, `workflow.notify`, `workflow.orchestrate`, `automation.trigger` | — | No matching site |

**2 adopt, 1 partial, 4 explicit skips, 11 with no site.**

#### Findings

**F1 — Dead duplicated module (high).** `crackerjack/utils/retry_utils.py`
is **235 lines, byte-for-byte identical** to `crackerjack/core/retry.py`
(`diff` exits 0). It has **zero importers**: only `core.retry` is imported,
by `crackerjack/managers/publish_manager.py:15` and
`crackerjack/services/version_checker.py:10`. The twin has been tracked and
public since `7bd7d775` (2026-07-10).

**F2 — The catalog's adoption metadata is wrong (medium-high, cross-repo).**
`oneiric/docs/action-kits.md` annotates **16 of its 18 kits** with
`**Adopted by**: (none yet — internal scaffolding only)`, a 17th with
`(none yet — production candidate)`, and names a real adopter for only
`compression.stream`. But mahavishnu imports **six** of those "scaffolding"
kits in **eight** production modules:

| Kit | Production importer |
|---|---|
| `http.fetch` | `mahavishnu/core/health.py:23`, `mahavishnu/core/http_probe.py:20` |
| `compression.hash` | `mahavishnu/core/idempotency.py:39`, `mahavishnu/mcp/tools/pool_tools.py:239` |
| `workflow.retry` | `mahavishnu/core/retry_policy.py:27` |
| `validation.schema` | `mahavishnu/jot/markdown_parser.py:13` |
| `data.transform` | `mahavishnu/jot/markdown_export.py:8` |
| `data.sanitize` | `mahavishnu/webhooks/ecosystem_intake.py:29` |

The catalog is the discovery surface's canonical reference. A contributor
who reads "internal scaffolding only" and then finds mahavishnu shipping it
in production receives contradictory guidance — and the skill's whole
proposition is "use the kit?", which is a bad question to ask about a kit
the catalog calls scaffolding.

**F3 — crackerjack has no kit-discovery surface (medium).**
`crackerjack/.claude/skills/` does not exist. The
`oneiric-action-kit-awareness` auto-trigger skill is installed in
mahavishnu only; crackerjack's sole pointer is prose at
`crackerjack/docs/guides/CLAUDE.md:353-355`. This is why crackerjack has
zero kit usage despite depending on oneiric (`oneiric>=0.33`, installed
0.33.4, imported by 39 tracked modules).

**F4 — The adoptable sites are sync; every kit is async (medium).** Every
method in `crackerjack/services/status_authentication.py` is `def`, while
every action kit's entry point is `async def execute`. Adoption needs an
explicit async-bridge decision, or the adoption is cosmetic.

### Constraints

1. **Adoption must be honest.** A kit that does not fit is skipped with a
   one-line code comment linking back to its catalog entry — the escape
   hatch the promoting decision explicitly provides. Do not adopt a kit to
   make a metric move.
2. **The skip reasons are shape mismatches, not style preferences.** Each
   skip in the fit matrix names the structural difference (fields vs
   content, value vs bytes, compute vs loop, pooled client vs per-call
   client). A skip with no structural reason is not a skip, it is a
   deferral.
3. **Do not change behavior in the name of adoption.** `status_authentication.py`
   signs, verifies, and compares signatures with `hmac.compare_digest`. The
   constant-time comparison path must survive the refactor intact.
4. **The dead duplicate's deletion is behavior-preserving.** `utils/retry_utils.py`
   has no importers; deleting it must not change any import path. The
   `core.retry` module stays the single home.
5. **The catalog fix lands in the oneiric repo, not in crackerjack.**
   `oneiric/docs/action-kits.md` is oneiric's file. This plan is written in
   crackerjack because the audit and the adoption decision are crackerjack's;
   the catalog edit is a cross-repo deliverable that needs explicit
   operator authorization at implementation time.
6. **Do not regenerate the catalog's kit list.** The audit found no missing
   kit — it found missing *adoption facts*. Only the `**Adopted by**` lines
   change.
7. Pre-1.0 — direct commit to local `main`, no PR, per
   `feedback-bodai-pre-1.0-merge-policy.md`. No push without explicit
   operator approval.
8. `feedback-bodai-push-is-user-controlled.md` — the operator pushes.

### Failure Conditions (verifier-only)

1. `git grep -rn "oneiric.actions" -- crackerjack/` returns matches only in
   the two files Phase 3 adopts into, plus any skip-comment files.
2. `crackerjack/utils/retry_utils.py` no longer exists, and
   `git grep -rn "retry_utils" -- crackerjack/` returns zero matches.
3. `diff crackerjack/core/retry.py` against its former twin is not
   reproducible — the twin is gone.
4. Every kit listed in the **Kits not adopted, and why** table has either a
   matching code comment linking to its catalog entry, or is listed there as
   having no site at all.
5. `oneiric/docs/action-kits.md` names a real adopter for every kit that has
   one, and no kit annotated "(none yet)" is imported by a production
   module in mahavishnu.
6. `status_authentication.py`'s HMAC verification path still uses
   constant-time comparison, and `pytest tests/unit/services/test_status_security.py`
   passes.
7. `ruff check` and `ty check` pass on every changed file.
8. `crackerjack.tools.plan_index_sync` regenerates `docs/plans/PLAN_INDEX.md`
   with the new plan listed at `active`.

## Phase 1 — Remove the dead retry duplicate

### Design

Delete `crackerjack/utils/retry_utils.py`. Nothing imports it; the live
module is `crackerjack/core/retry.py`, which keeps the `retry` decorator,
the `retry_api_call` helper, and the sync/async executors.

Before deleting, verify the no-importer claim at implementation time rather
than trusting this plan's snapshot:

```bash
cd <crackerjack checkout>
git grep -n "retry_utils" -- .            # expect zero hits outside the file itself
diff crackerjack/core/retry.py crackerjack/utils/retry_utils.py  # expect exit 0
```

Then delete the file and re-run the grep to confirm zero remaining
references. `tests/test_retry.py` and `tests/core/test_retry.py` already
import from `crackerjack.core.retry`, so neither needs touching.

This phase is the audit's most concrete deliverable: 235 duplicated lines
in a public repository, with no reader.

### Integration Contract

**Integration Contract:**
- **Triggered from:** nothing — the module has no importers, which is the
  premise of the phase.
- **Returns to / updates:** nothing. No import path changes.
- **Demonstrable by:** `python -c "import crackerjack.utils.retry_utils"`
  raises `ModuleNotFoundError`, and `crackerjack run` still passes the
  publish manager's and version checker's retry paths.
- **Rollback signal:** any module fails to import at runtime — restore the
  file from the deleted commit.
- **Observability added:** none — this phase only removes duplication.

## Phase 2 — Correct the catalog's adoption metadata

### Design

Edit `oneiric/docs/action-kits.md` in the **oneiric** repo. For each of the
16 kits annotated "(none yet — internal scaffolding only)" that is in fact
imported by a production module, replace the annotation with the real
adopter. The verified facts from this audit:

| Kit | Real adopter |
|---|---|
| `http.fetch` | mahavishnu — `core/health.py`, `core/http_probe.py` |
| `compression.hash` | mahavishnu — `core/idempotency.py`, `mcp/tools/pool_tools.py` |
| `workflow.retry` | mahavishnu — `core/retry_policy.py` |
| `validation.schema` | mahavishnu — `jot/markdown_parser.py` |
| `data.transform` | mahavishnu — `jot/markdown_export.py` |
| `data.sanitize` | mahavishnu — `webhooks/ecosystem_intake.py` |

The remaining ten keep "(none yet — internal scaffolding only)" — that
annotation is accurate for them.

**Verify each annotation at implementation time rather than copying this
table.** The adoption set drifts; the point of the phase is that the
catalog becomes a source of truth, and it only stays one if the annotations
are checked against the tree. The check is mechanical:

```bash
cd <mahavishnu checkout>
git grep -ln "from oneiric.actions" -- '*.py'
```

Every kit that appears must be named in the catalog's `**Adopted by**` line
for that kit, and every kit named must appear in the grep.

Also update the oneiric-side discovery pointer if it exists, so the two
surfaces agree.

### Integration Contract

**Integration Contract:**
- **Triggered from:** a contributor reading the catalog to decide whether a
  kit is production-ready.
- **Returns to / updates:** `oneiric/docs/action-kits.md` — the
  `**Adopted by**` annotation on six kit entries.
- **Demonstrable by:** every kit named by a `**Adopted by**` line is
  imported by a production module in the named repo, and every kit imported
  by a production module is named by a `**Adopted by**` line.
- **Rollback signal:** the annotations drift from the tree again — which is
  why Phase 4 adds a conformance check rather than leaving this to
  discipline.
- **Observability added:** none — this phase only corrects a record.

## Phase 3 — Adopt the two kits that fit, and document the rest

### Design

Two kits in one module. `crackerjack/services/status_authentication.py`
hand-rolls exactly what `security.signature` and `security.secure` provide:

- `_generate_secret_key` (`:84`) and `_generate_api_key` (`:101`) call
  `secrets.token_urlsafe(32)` directly — the kit's `security.secure` covers
  token and secret generation.
- `_validate_jwt_token` (`:226`) and `_validate_hmac_signature` (`:290`)
  call `hmac.new(..., hashlib.sha256)` and compare with
  `hmac.compare_digest` — the kit's `security.signature` covers keyed HMAC
  over a message with `sha256`/`sha512`/`blake2b` and `hex`/`base64`
  encoding.

**The async bridge (F4) is the crux of this phase.** The module is entirely
sync; the kit's entry point is `async def execute`. Three options, in
descending preference:

1. **Add async sibling methods** and leave the sync ones delegating to a
   cached event-loop runner. Preserves the public sync API exactly.
2. **Cache a single background loop thread** and submit the kit call to it.
   Same outcome, more machinery.
3. **Skip the adoption** and keep the stdlib calls, with a comment linking
   to the catalog entry and the reason (sync call path).

Option 3 is legitimate under constraint 1 and is explicitly permitted by the
promoting decision ("Kit API genuinely does not fit — wrap with a one-line
comment linking back to the catalog entry"). If the bridge costs more
complexity than the hand-rolled call it replaces, take option 3 and say so
in the plan's evidence. **Do not adopt to move a metric.**

For each of the four skips with a matching site, leave a one-line comment
at the site naming the kit and the structural reason, e.g. at
`crackerjack/services/secure_status_formatter.py`:

```python
# Not oneiric.actions.data.DataSanitizeAction: that kit filters record
# *fields* by name; this redacts *string content* (paths, secrets) in
# place. See oneiric/docs/action-kits.md#data.sanitize.
```

Per the promoting decision, this is a discovery surface, not an
enforcement gate — the comment is the whole mechanism.

### Integration Contract

**Integration Contract:**
- **Triggered from:** `crackerjack/mcp/tools/monitoring_tools.py:15`, which
  imports from `status_authentication`.
- **Returns to / updates:** `status_authentication.py` internals; the
  public API (`get_status_authenticator`, `authenticate_request`, key
  management) is unchanged.
- **Demonstrable by:** `pytest tests/unit/services/test_status_security.py`
  passes, including the HMAC verification cases; a signature produced and
  verified through the kit round-trips.
- **Rollback signal:** a signature that verifies locally fails against a
  peer, or `hmac.compare_digest` is no longer used on the verification
  path — constant-time comparison must survive.
- **Observability added:** the kit's own logging (`oneiric.actions.*` logs
  to the oneiric logger namespace), which is a new log source for
  crackerjack's status path.

## Phase 4 — Give crackerjack a kit-discovery surface

### Design

`crackerjack/.claude/skills/` does not exist. Create
`crackerjack/.claude/skills/oneiric-action-kit-awareness/SKILL.md`,
mirroring mahavishnu's skill but with crackerjack's own trigger surface —
the same 18-kit trigger list, with crackerjack's actual call sites named
(`status_authentication.py` for signature/secure,
`core/retry.py` for retry, `secure_status_formatter.py` for sanitize,
`file_hasher.py` for hash, `input_validator.py` for validation,
`connection_pool.py` for http.fetch).

Include the skip reasons from Phase 3 in the skill body, so the skill
answers "why didn't crackerjack use the kit?" without the contributor
re-deriving it.

Also add a **conformance check** that keeps Phase 2 from re-drifting: a
script that greps every Bodai repo for `from oneiric.actions` and compares
the result against the catalog's `**Adopted by**` annotations, failing when
they disagree. That closes the loop that made F2 possible in the first
place. The script belongs in crackerjack (it already owns fleet-wide
conformance gates, e.g. the gitignore conformance check) and writes a
report rather than mutating the catalog.

## Kits not adopted, and why

| Kit | Site | Structural reason |
|---|---|---|
| `data.sanitize` | `services/secure_status_formatter.py` | The kit applies an allow/drop/mask list to a record's **fields**. Crackerjack redacts **string content** — path prefixes and secret substrings inside free text — and walks nested structures recursively. The catalog itself says "Sanitize only *transforms shape*". |
| `compression.hash` | `services/file_hasher.py` | The kit produces a **value** hash (mahavishnu uses it for idempotency keys). Crackerjack digests **file bytes** (md5) to detect change between runs. Different inputs, different contracts. |
| `validation.schema` | `services/input_validator.py` | The kit is **JSON Schema** type enforcement with error aggregation. Crackerjack detects **SQL and code injection via regex patterns**. A schema cannot express "this string looks like a SQL comment". |
| `http.fetch` | `services/connection_pool.py`, `skills/github_client.py`, `skills/health.py` | crackerjack manages **pooled `httpx` clients** with per-service auth headers; the kit constructs its own client per call and injects trace context. The catalog notes "for streaming/long-polling, no built-in kit — bring your own `httpx.AsyncClient`". |
| `workflow.retry` | `core/retry.py` | The kit **computes** the next delay ("bring your own loop"); crackerjack's decorator *is* the loop, in both sync and async form. Adopting the kit for `_calculate_delay` alone would add an async bridge to a sync-capable decorator for ~35 of 235 lines. |

## Out of Scope

1. **Adopting the eleven kits with no crackerjack site.** No reinvention
   exists to remove. The audit is about closing real gaps, not maximizing a
   kit count.
2. **The `oneiric` skill's trigger list itself.** mahavishnu's skill is the
   upstream source; Phase 4 mirrors it rather than forking it.
3. **Rewriting `core/retry.py` to use `workflow.retry`.** Deferred per the
   skip table; revisit only if the retry loop grows a second implementation.
4. **`crackerjack/docs/guides/CLAUDE.md:353-355`** keeps its prose pointer.
   Phase 4 adds a skill alongside it; rewriting the prose is cosmetic.
5. **The oneiric-side catalog edit is not authored in this repo.** Phase 2
   describes the change; it lands in oneiric with operator authorization.
6. **The 106 pre-existing mahavishnu unit-suite failures** — unrelated to
   this work.

## Evidence

Audit performed 2026-10-28 against crackerjack `main` at `6477b5c7`
(oneiric 0.33.4 installed; `oneiric.actions` importable).

- Trigger scan: 1264 tracked `.py` files, per-kit regex sweep.
- `diff crackerjack/core/retry.py crackerjack/utils/retry_utils.py` → exit 0
  (byte-identical, 235 lines each).
- `git grep -rn "retry_utils"` → zero importers.
- `git grep -n "from oneiric.actions"` in mahavishnu → 8 production
  modules, 6 distinct kits.
- `grep -n "Adopted by" oneiric/docs/action-kits.md` → 18 annotations; 16
  "(none yet — internal scaffolding only)", 1 "(none yet — production
  candidate)", 1 real adopter (`compression.stream`).
- `grep -rn "oneiric.actions" --include="*.py" crackerjack/` → 0 hits.
- `crackerjack/pyproject.toml:65` → `"oneiric>=0.33"`; installed 0.33.4;
  `oneiric.actions` imports cleanly in crackerjack's venv.
- `ls crackerjack/.claude/skills/` → does not exist.
