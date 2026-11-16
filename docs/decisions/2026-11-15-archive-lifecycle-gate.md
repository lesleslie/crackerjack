# The documentation cleanup must not archive a live document

**Date:** 2026-11-15

## Context

`crackerjack`'s `documentation_cleanup` phase decides what to archive by
**filename regex alone**. `DocumentationCategorizer.categorize_file()`
(`crackerjack/services/doc_categorizer.py`) maps a filename to a category;
the `implementation_reports` category matches `r".*-implementation\.md"`.
`get_archival_candidates()` returns every file matching any non-`keep`
category, and `DocumentationCleanup._detect_archivable_files()` is the
oracle that turns candidates into what the archiver takes.

Nothing in that path looked at the document's *lifecycle*. A canonical
plan named `2026-10-19-bodai-substrate-otel-v7-implementation.md` matches
`.*-implementation\.md`, so the archiver swept it — the name is a
coincidence, not a lifecycle statement.

### Why the sweep is destructive, not merely untidy

`DocumentationCleanup._move_files_to_archive()` moves the file to
`docs/plans/.archive/<category>/` and then `git rm --cached`s the source.
The archive path is matched by the fleet-wide `**/.archive/` gitignore
rule, so the archived document is **untracked**. It is not moved — it
leaves the repository. `git log` still holds it; the working tree does not.

### Why it surfaced as a link error

`PLAN_INDEX.md` is not regenerated after the sweep. In mahavishnu,
`settings/crackerjack.yaml` sets `auto_plan_index_sync_on_publish: false`
because cracker's `plan_index_sync` fork re-renders the index in a plainer
format and drops the `docs/decisions/` and `docs/audits/` rows; that repo's
own `scripts/regenerate_plan_index.py` is authoritative there. The
committed index keeps its rows, the files behind them are gone, and the
`check-local-links` fast hook fails on the dangling relative links.

### The policy this bypassed

`~/Projects/mahavishnu/docs/decisions/2026-10-18-archive-completed-plans.md`
rule 2 is explicit: *"Plans being archived must have `status: shipped`
first. Mechanical 'complete → archive' is not allowed; the gate forces
per-plan verification."* Rule 1 draws the line — `complete` means
"delivered; verification or follow-up may still be open", `shipped` means
"delivered and verified in production; closed".

The lifecycle vocabulary is shared fleet-wide:
`crackerjack/services/frontmatter.py` already carries
`LIFECYCLE_VALUES = {"draft", "active", "partial", "shipped", "complete"}`,
matching `oneiric.schemas.document-frontmatter-v1`.

### Incident history (mahavishnu)

| Date | Event |
|---|---|
| 2026-10-21 | read-path implementation plan archived |
| 2026-10-27 | v7 implementation plan archived |
| 2026-10-28 | `8f149717` archived both again and rewrote `PLAN_INDEX.md` without mentioning it |
| 2026-11-07 | `eaf9e162` reviewed both plans, verified their state, restored them |
| 2026-11-08 | read-path plan archived again (index **not** rewritten) |
| 2026-11-13 | v7 plan archived again |
| 2026-11-15 | `check-local-links` failed on the two dangling links; both restored; mahavishnu disabled `auto_cleanup_on_publish` as an interim guard |

The two plans were lost three times before the mechanism was understood.
Every earlier occurrence was recovered by hand, from git history, by
reading the index and noticing a link pointed at nothing.

## Decision

**A document that carries YAML frontmatter is lifecycle-governed. The
archiver may move it only when its `status:` is `shipped`.**

A markdown file with **no** frontmatter is not governed — it is a scratch
artifact, a progress report, or a legacy note — and keeps the
filename-based behaviour. The cleanup phase keeps doing its job on those.

Only markdown is governed, because only markdown carries a frontmatter
lifecycle. The loose non-markdown root artifacts the archiver also sweeps
(`.json`, `.py`, `.backup`) have none, and a binary `.backup` cannot be
read as UTF-8 at all — gating them would make them unarchivable, which is
the cleanup's actual job.

The test is on the **name**, not the suffix: a candidate whose name
carries `.md` is gated even when it is not markdown-suffixed. The name
test is case-insensitive because the categorisation is.

This is a **live** path, not a hypothetical one. `re.match` anchors at the
*start* of the name, so a pattern that is not end-anchored matches a
prefix: the `analysis` category's `TEST_.*\.md` pattern classifies
`TEST_foo.md.backup` as an analysis document, and `.*_SUMMARY.*\.md`
classifies `X_SUMMARY_report.md.backup` as a completion report. Both
carry `.md` without ending in `.md`, and the `*.backup` glob proposes
them as candidates. A suffix test would have swept both ungated; the name
test gates them like the documents they copy.

Four cases fail **closed**, because each of them means "the lifecycle is
unknown":

- the frontmatter block does not parse,
- the block parses but declares no `status:`,
- the block is empty, or otherwise unreadable — a file that opens with the
  `---` fence declares a frontmatter block even when the extractor cannot
  match it,
- the file cannot be read as UTF-8.

In each case the file stays put and the categorizer logs a warning. The
point is that a mechanical sweep must never be the thing that decides a
governed document's fate — the sweep moves files by name, and a name is
not a lifecycle.

**Detection is deliberately more tolerant than the extractor.** The gate's
own "does this file declare frontmatter?" check also accepts a leading
UTF-8 BOM and leading blank lines, because the anchored extractor misses
a real frontmatter block in both cases — and a missed frontmatter reads
as "not governed", the one direction that must never happen. The shared
extractor strips a BOM too, so the frontmatter validator sees the same
frontmatter the gate does. The plan index does not: it carries its own
`extract_frontmatter` and its own anchored regex
(`crackerjack/tools/plan_index_sync.py`), with no BOM handling — see
"Known residuals".

### Where the gate lives

In exactly one place: `DocumentationCleanup._detect_archivable_files()`.

The categorizer owns the *predicate* —
`DocumentationCategorizer.lifecycle_permits_archival()` — and the
*candidate detection* — `get_archival_candidates()`, which answers "does
this name look archivable?" and applies no gate. The cleanup service
applies the predicate to whatever candidates any detection path produced:

```python
try:
    candidates = self.categorizer.get_archival_candidates()
except Exception:
    candidates = self._detect_archivable_files_legacy()

return [p for p in candidates if self._passes_lifecycle_gate(p)]
```

`_passes_lifecycle_gate` applies the predicate to **markdown** only. The
non-markdown candidates the archiver also sweeps (`.json`, `.py`,
`.backup`) carry no frontmatter lifecycle, and a binary `.backup` cannot
be read as UTF-8 — gating them would make them unarchivable, which is the
cleanup's actual job.

**One choke point, deliberately.** Both detection paths — the
categorizer's and the legacy fallback's — pass through that single
filter, so adding or removing a detection path cannot open a bypass. The
alternative (applying the gate once per detection path) fails *quietly*:
an editor deleting one of the two calls reopens the bypass with no
symptom. A single application point fails *loudly* — removing it removes
the rule from every path at once, which review catches.

That is the whole reason the legacy fallback needs the gate too: it is
the one path where the categorizer's own filtering is unavailable, and a
fallback that quietly drops the rule is worse than no fallback.

The archivable statuses are configurable:
`DocumentationSettings.archivable_statuses` defaults to `["shipped"]`, and
a repo with a different vocabulary widens the list in
`settings/crackerjack.yaml` without a code change. The default lives in
one place — `crackerjack.core.lifecycle.ARCHIVABLE_STATUSES` — and
both the setting and the tool read it, so the two cannot drift. The
configured values are matched case-insensitively.

### Measured blast radius

Candidates the archiver would take, measured across the fleet before and
after the gate:

| Repo | Before | After | Effect |
|---|---|---|---|
| mahavishnu | 2 (both `status: complete`) | 0 | **both protected** |
| crackerjack | 1 (`coverage.json`, no frontmatter) | 1 | unaffected |
| akosha | 0 | 0 | — |
| session-buddy | 0 | 0 | — |
| mcp-common | 1 (`coverage.json`, no frontmatter) | 1 | unaffected |
| oneiric | 0 | 0 | — |

The gate changes the outcome for exactly two files in the fleet — the two
OTel substrate plans that were lost three times. It is strictly
conservative: it can only move fewer files, never more.

## Known residuals

Six boundaries of the gate, recorded so a reader does not mistake them
for oversights:

- **A backup whose name carries no `.md` is not gated.**
  The gate keys on the name, so `TEST_foo.md.backup` — which the
  categorizer classifies as an analysis document — is gated like the
  document it copies, while `pyproject.toml.backup` (the `temp_files`
  category has an explicit pattern for it) carries no `.md`, is
  classified as a temporary artifact, and is swept ungated. That is the
  intended split: a config backup has no lifecycle to declare, and a copy
  of a document does.

  Separately, a backup the categorizer does not classify at all is
  neither swept nor gated: the `test_artifacts` backup pattern is
  `r"\.backup$"`, and `re.match` anchors at the *start* of the name,
  so it matches only a file literally named `.backup`. `plan.backup`
  and `foo.md.backup` match no category, so the sweep never proposes
  them. That is a pre-existing limitation of the categorizer's patterns
  rather than a property of the gate, and widening it is a separate
  change with its own blast-radius measurement.

- **A legacy status value the validator resolves is not resolved here.**
  The frontmatter validator maps some older spellings (`resolved`) onto
  `complete`; the gate reads the raw value. The outcome is the same
  either way — both spellings are closed-but-unverified, so both block
  archival.

- **A document that declares its status in the body stays ungated.** The
  validator tolerates an inline `## Status` heading in place of
  frontmatter. The gate reads frontmatter, so such a document counts as
  ungoverned and is swept if its name matches. Reading a status out of
  prose would be a far larger and less reliable change than reading it
  out of a declared field, and the names that carry such documents
  (`progress-*.md`) are scratch artifacts by convention.

- **The plan index reads frontmatter with its own extractor.**
  `crackerjack/tools/plan_index_sync.py` carries a private
  `extract_frontmatter` and its own anchored regex, and it does not strip
  a UTF-8 BOM. The shared extractor does, and so does the frontmatter
  validator, so a BOM'd document is governed for the gate and for the
  validator while the plan index sees no frontmatter at all.

  The consequence is that a BOM'd file gets **no row at all**: its
  frontmatter parses to nothing, `_entry_from_file` returns `None`, and
  `render_plan_index` skips it. It is not indexed with a missing status —
  it is absent. Nothing in the archive path depends on the index's view —
  the index is a report, not a gate — but a BOM'd plan is invisible in
  it.

  This applies to the legacy in-crackerjack path only. When
  `documentation.use_shared_regenerator` is set, the plan index routes to
  `oneiric.plan_index.regenerate`, which uses the shared
  BOM-stripping extractor. Left alone here: the plan index is a separate
  subsystem with its own consumers, and changing its extractor is a
  change to it, not to this gate.

  > **Superseded 2026-11-16.** The shared branch was removed; there is no
  > longer a `use_shared_regenerator` setting and the plan index has one
  > renderer (`crackerjack.tools.plan_index_sync`). The BOM-stripping
  > extractor below is therefore the only one, and the limitation
  > described above applies unconditionally. See
  > `docs/decisions/2026-11-16-single-plan-index-renderer.md`.

- **The standalone cleanup script still forks the categorizer.**
  `scripts/docs_cleanup.py` carries its own copy of the category table,
  which still emits the old flat `docs/archive/<category>/` routes, and
  it cannot start at all — it registers `--dry-run` twice, so argparse
  rejects it before it reads a file. Both defects predate this change.
  The guidelines now say to use the tool rather than the script; making
  the script a faithful mirror of `DocumentationCategorizer` is a change
  to the script, and it has no tests of its own yet.

- **The cleanup's backup tar is flat.**
  `_create_backup` stores each file under its basename
  (`tar.add(file_path, arcname=file_path.name)`), so `rollback_cleanup`
  restores a file to the repository *root* rather than to the area it
  came from — a plan backed up from `docs/plans/` comes back at the
  root. Pre-existing, and unchanged here: the backup is what the gate
  runs behind, and its restore path is a separate mechanism. Worth
  fixing before a rollback is ever needed.

## Consequences

- **The cleanup archives less.** Intended. A repo that relied on
  `complete` documents being swept now keeps them;
  `archivable_statuses` is the escape hatch.
- **A governed document now needs a deliberate status flip** to be
  archived. That is the policy working as written: `complete` →
  `shipped` → archive, with the flip recording that verification closed.
- **mahavishnu's interim `auto_cleanup_on_publish: false` guard becomes
  unnecessary** and should be reverted once this ships.
- **The permanent fix lives here, not in the consuming repos.** A repo
  cannot enforce its own archive policy against a tool that ignores
  lifecycles.

## References

- `docs/plans/2026-11-15-archive-lifecycle-gate.md` — the implementation
  plan, with the measured blast radius and the phase contracts.
- `~/Projects/mahavishnu/docs/decisions/2026-10-18-archive-completed-plans.md`
  — the archive policy this gate enforces.
- `~/Projects/mahavishnu/docs/decisions/2026-11-15-publish-cleanup-bypasses-archive-gate.md`
  — the interim guard this supersedes.
