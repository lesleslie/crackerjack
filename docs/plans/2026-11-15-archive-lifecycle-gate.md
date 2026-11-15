---
status: active
role: implementation
topic: lifecycle
date: 2026-11-15
last_reviewed: 2026-11-15
superseded_by: null
blocks_on: []
---

# Archive lifecycle gate — the cleanup must not archive live documents

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The `documentation_cleanup` phase must never auto-archive a
lifecycle-governed document whose declared `status:` is not `shipped`. A
mechanical sweep may not be the thing that decides a governed document's
fate.

**Architecture:** The categorizer owns the *predicate* —
`DocumentationCategorizer.lifecycle_permits_archival()` reads the file's
YAML frontmatter and consults a configurable set of archivable statuses —
and the *candidate detection*, `get_archival_candidates()`, which answers
"does this name look archivable?" and applies no gate. The cleanup
service owns the verdict: `DocumentationCleanup._detect_archivable_files()`
filters the candidates from whichever detection path produced them, so the
gate is applied at exactly one point. `DocumentationCleanup` supplies the
status set from `DocumentationSettings`.

Only markdown is gated: it is the only thing that carries a frontmatter
lifecycle. The loose non-markdown root artifacts the archiver also
sweeps have none, and a binary `.backup` cannot be read as UTF-8 at all.

**Tech Stack:** Python 3.13+, pytest, PyYAML (already a dependency of
`crackerjack.services.frontmatter`).

---

## 1. Brief (intent-driven)

### Goal

A governed document reaches the archive only when it declares
`status: shipped`. Documents at `complete`, `active`, `partial`, or
`draft` stay where they are, no matter what their filename looks like.

### Constraints

- The gate applies to **documents with frontmatter**. A file with no
  frontmatter is a scratch artifact or a legacy note, not a governed
  document; it keeps the existing filename-based behaviour.
- Version bumps and PyPI publishes are the operator's.
- Push is the operator's.
- One commit per phase, each independently revertible.

### Failure Conditions (verifier-only)

1. `DocumentationCleanup._detect_archivable_files()` on a fixture tree
   containing a `status: complete` file named `*-implementation.md` does
   **not** return that file.
2. The same call on a fixture tree containing a `status: shipped` file
   named `*-implementation.md` **does** return that file.
3. A file with no frontmatter named `*-implementation.md` is still
   returned (the cleanup keeps working on scratch artifacts).
4. A file whose frontmatter block does not parse is **not** returned
   (fail closed).
5. A file whose frontmatter parses but declares no `status:` is **not**
   returned (fail closed).
6. The same holds when the categorizer raises and the legacy fallback
   detector takes over — the fallback is not a bypass.
7. `grep -c "2026-10-19-bodai-substrate-otel-v7-implementation.md"` over
   the archivable list produced against `~/Projects/mahavishnu` is `0`.

---

## 2. Context

### The defect

`crackerjack/services/doc_categorizer.py:301` `categorize_file()` classifies
a document by **filename regex alone**. The `implementation_reports`
category matches `r".*-implementation\.md"`. `get_archival_candidates()`
returns every file that matches any non-`keep` category, and
`documentation_cleanup.py` turns candidates into what the archiver takes —
oracle for "what does the archiver take".

There is no frontmatter gate anywhere in that path. A canonical plan named
`2026-10-19-bodai-substrate-otel-v7-implementation.md` matches
`.*-implementation\.md` and is swept, regardless of its lifecycle.

### Why the sweep is destructive

`DocumentationCleanup._move_files_to_archive()`
(`documentation_cleanup.py:359`) moves the file to
`docs/plans/.archive/<category>/` and then `git rm --cached`s the source.
The archive path is matched by the fleet-wide `**/.archive/` gitignore
rule, so the archived document is **untracked** — it is not moved, it leaves
the repository. `git log` still holds it; the working tree does not.

### Why the failure surfaces as a link error

`PLAN_INDEX.md` is not regenerated after the sweep. In mahavishnu,
`settings/crackerjack.yaml` sets `auto_plan_index_sync_on_publish: false`
because cracker's `plan_index_sync` fork re-renders the index in a plainer
format and drops the `docs/decisions/` and `docs/audits/` rows; the repo's
own `scripts/regenerate_plan_index.py` is authoritative there. The
committed index keeps its rows, the files behind them are gone, and the
`check-local-links` fast hook fails on the dangling relative links.

### The policy this violates

`~/Projects/mahavishnu/docs/decisions/2026-10-18-archive-completed-plans.md`
rule 2 is explicit: *"Plans being archived must have `status: shipped`
first. Mechanical 'complete → archive' is not allowed; the gate forces
per-plan verification."* Rule 1 draws the line: `complete` means "delivered;
verification or follow-up may still be open", `shipped` means "delivered
and verified in production; closed".

The lifecycle vocabulary is shared fleet-wide —
`crackerjack/services/frontmatter.py:16` already carries
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

### Measured blast radius

Candidates the archiver would take, measured against the fleet with the
pre-gate categorizer:

| Repo | Candidates | Frontmatter | Gate effect |
|---|---|---|---|
| mahavishnu | 2 | both `status: complete` | **both protected** |
| crackerjack | 1 (`coverage.json`) | none | unaffected |
| akosha | 0 | — | — |
| session-buddy | 0 | — | — |
| mcp-common | 1 (`coverage.json`) | none | unaffected |
| oneiric | 0 | — | — |

The gate changes the outcome for exactly two files in the fleet: the two
OTel substrate plans that were lost three times.

---

## 3. Phases

### Phase 1 — the lifecycle gate

#### Scope

- `crackerjack/services/doc_categorizer.py` — new
  `lifecycle_permits_archival()` (the gate predicate), an
  `archivable_statuses` constructor parameter, and
  `get_archival_candidates()` (name-based detection, ungated).
- `crackerjack/core/lifecycle.py` — `ARCHIVABLE_STATUSES`, the one
  source for the default.
- `crackerjack/config/settings.py` — new
  `DocumentationSettings.archivable_statuses`.
- `crackerjack/services/documentation_cleanup.py` — the single application
  point for the gate (`_detect_archivable_files`), and it passes the
  configured statuses into the categorizer. It also records the files
  the gate *held back* (`_gated_files`), so the cleanup's report can
  distinguish a held file from a file that never matched a category.
- `crackerjack/services/documentation_service.py` — the API generator's
  hidden-directory filter becomes relative to the repository root
  (`_visible_source_files`, `_relative_parts`), and
  `generate_full_api_documentation` refuses to write an empty reference
  over a committed one. The old filter tested each file's *absolute*
  path, so every file in a checkout under a dotted directory was
  dropped — this fleet's worktrees live under `~/.local/state/`, so the
  generator found zero files and wrote an empty API reference over a
  committed 18,000-line one. Shipping the gate without this fix would
  have let the gate's own demonstration — the generated reference
  changing under the operator's feet — go unnoticed.
- `tests/test_doc_categorizer.py` — new; covers failure conditions 1–5.
- `tests/test_documentation_cleanup.py` — covers failure condition 6.
- `docs/DOCS_CLEANUP_GUIDELINES.md` — the operator-facing contract.
- `docs/plans/PLAN_INDEX.md` — regenerated (the new plan's row).
- `crackerjack/docs/generated/api/{API_REFERENCE,SERVICES}.md` — the
  renamed method's entries.

#### Integration Contract

- **Triggered from**: `crackerjack run --publish` →
  `phase_coordinator.run_documentation_cleanup_phase` →
  `DocumentationCleanup.cleanup_documentation()` →
  `DocumentationCleanup._detect_archivable_files()` →
  `DocumentationCategorizer.get_archival_candidates()`. The same branch
  also fixes the API generator the publish stage runs:
  `DocumentationServiceImpl.generate_full_api_documentation()` →
  `_find_source_files()` → `_visible_source_files()`.
- **Returns to / updates**: the archivable list, and the list of files
  the gate held back. A governed document is in the first list only
  when its `status:` is archivable; a governed document that is *not*
  archivable appears in the second, by name. The cleanup's summary and
  the phase coordinator's task detail carry both, so the record says
  "held" rather than "essential". The API generator returns without
  writing when its scan finds nothing.
- **Demonstrable by**: `pytest tests/test_doc_categorizer.py
  tests/test_documentation_cleanup.py tests/unit/services/test_documentation_service.py -v`;
  and
  `DocumentationCleanup(pkg_path=Path("~/Projects/mahavishnu"))._detect_archivable_files()`
  returning `[]`. Measured against this repo's tree on 2026-11-15, the
  same call reports the two files the gate held — the two OTel
  substrate plans, the ones that were lost five times — so "nothing to
  archive" and "held on purpose" are now distinguishable.
- **Rollback signal**: `tests/test_documentation_cleanup.py` failing on the
  archive-move assertions, or the cleanup phase reporting
  `files_moved == 0` where the operator expected a move.
- **Observability added**: the categorizer logs, at WARNING level, every
  file it declines to archive because its lifecycle is unknown or
  unparsable — previously a silent skip. A *known* lifecycle that has
  not shipped is not an error, so the categorizer logs it at INFO and
  the cleanup reports it where the operator looks: the result carries
  `gated_files`, the summary counts them, and the completion display
  names them. Before this, a held file was invisible and the summary
  claimed "all files are essential" — false for exactly the files the
  gate exists to protect.

#### Resolved decisions

1. **The gate is on `status:`, not on `role:`.** The policy's gate is
   `status: shipped`; `role:` describes what kind of document a file is,
   not what stage it is at. `role: superseded` does not by itself permit
   archiving — a superseded document still has to be closed.
2. **No frontmatter means not governed.** Scratch artifacts, progress
   reports, and legacy notes carry no frontmatter and keep the existing
   filename-based behaviour. The cleanup phase keeps doing its job.
3. **Unparsable frontmatter and missing `status:` both fail closed.** Both
   mean the lifecycle is unknown. Leaving the file in place is the safe
   reading: the frontmatter validator already flags these files, and
   archiving them would silently destroy the thing the validator was
   complaining about.
4. **The status set is configurable, and the default has one home.**
   `DocumentationSettings.archivable_statuses` defaults to `["shipped"]`,
   sourced from `crackerjack.core.lifecycle.ARCHIVABLE_STATUSES`, so
   the setting and the tool cannot drift. A repo with a different
   lifecycle vocabulary widens the list in `settings/crackerjack.yaml`
   without a code change. Configured values are matched
   case-insensitively.
5. **The gate is applied in exactly one place.**
   `DocumentationCleanup._detect_archivable_files()` filters the
   candidates from *whichever* detection path produced them — the
   categorizer's or the legacy fallback's. One application point means a
   new detection path cannot bypass the gate by omission, and removing
   the gate removes it from every path at once (loudly) rather than from
   one path (quietly). The categorizer owns the predicate and the
   candidate detection; the cleanup service owns the verdict.

#### Risks

1. **The cleanup archives less than before.** Intended. A repo that
   depended on `complete` documents being swept now keeps them; the
   `archivable_statuses` setting is the escape hatch.
2. **Reading every candidate's frontmatter costs I/O.** Candidates are
   markdown files at the top level of the scanned areas; the cleanup
   phase already tars the same tree for its backup. Measured cost is
   negligible next to the backup.
3. **A document with `status: shipped` is still swept even if the operator
   wanted it kept.** That is the policy working as written — `shipped`
   means closed.

#### Estimated scope

The first estimate for this phase was "two source files (~60 lines), one
settings field (~3 lines), one new test file (~140 lines)". That was
wrong by an order of magnitude, and it understated the work in a way
that mattered: the review found a second source file
(`documentation_service.py`) and a documentation surface
(`docs/DOCS_CLEANUP_GUIDELINES.md`) that the estimate did not mention
at all, so nothing in the plan asked for them to be wired.

The measured scope of the branch against `main` (`8a8ed138`) is 16
files, +2,892 / −104 lines:

- 4 source files — `doc_categorizer.py` (+179/−15),
  `documentation_cleanup.py` (+59/−5), `documentation_service.py`
  (+46/−8), `frontmatter.py` (+20) — plus `config/settings.py` (+13).
- 3 test files — `tests/test_doc_categorizer.py` (+434, new),
  `tests/test_docs_cleanup_guidelines.py` (+393, new),
  `tests/test_documentation_cleanup.py` (+288/−6) — plus
  `tests/unit/services/test_documentation_service.py` (+76/−3).
- 3 documents — this plan (+924), the decision record (+282), and
  `docs/DOCS_CLEANUP_GUIDELINES.md` (+160/−61) — plus the regenerated
  `docs/plans/PLAN_INDEX.md` and the two generated API reference files.
- 1 lockfile line — the `crackerjack` version field in `uv.lock`.

Roughly two thirds of the line count is tests and documentation. The
source change itself is ~320 lines across four files; the size of the
diff is the review surface, not the size of the change.

---

## 4. Risks

- **Cross-repo behaviour change.** The gate applies to every repo that
  runs the cleanup. Measured blast radius is two files fleet-wide, and the
  change is strictly conservative: it can only move fewer files.
- **Version skew.** A repo whose venv pins an older crackerjack keeps the
  old behaviour until it picks up the release. mahavishnu installs
  crackerjack editable, so it picks this up immediately.

---

## 5. References

- `~/Projects/mahavishnu/docs/decisions/2026-10-18-archive-completed-plans.md`
  — the archive policy this gate enforces.
- `~/Projects/mahavishnu/docs/decisions/2026-11-15-publish-cleanup-bypasses-archive-gate.md`
  — the interim guard this fix supersedes.
- `crackerjack/services/frontmatter.py:16` — `LIFECYCLE_VALUES`.
- `oneiric.schemas.document-frontmatter-v1` — the shared vocabulary.

---

## 6. Execution record

### Phase 1 — the lifecycle gate

**Baseline:** `8a8ed138` (branch `fix/archive-lifecycle-gate` off `main`).

**Deltas:**

- `crackerjack/core/lifecycle.py` — `ARCHIVABLE_STATUSES`, the one
  source for the default.
- `crackerjack/services/doc_categorizer.py` — the
  `lifecycle_permits_archival()` predicate, the `_declares_frontmatter()`
  helper, an `archivable_statuses` constructor parameter, and
  `get_archival_candidates()` (the name-based detector, ungated).
- `crackerjack/config/settings.py` — `DocumentationSettings.archivable_statuses`,
  defaulted from `ARCHIVABLE_STATUSES`.
- `crackerjack/services/documentation_cleanup.py` — the **single**
  application point for the gate, in `_detect_archivable_files()`; it also
  passes the configured statuses into the categorizer, and records the
  files the gate held back (`_gated_files`) so the cleanup's report can
  name them: the result carries `gated_files`, the summary counts them,
  and the completion display lists them.
- `crackerjack/services/doc_categorizer.py` — a governed document whose
  status is known and *not* shipped is a decline, not an error, so it is
  logged at INFO; the unknown and unparsable cases keep their WARNING.
- `crackerjack/services/documentation_service.py` — the API generator's
  hidden-directory filter becomes relative to the repository root, and
  the generator refuses to write an empty reference over a committed
  one.
- `tests/test_doc_categorizer.py` — new.
- `tests/test_documentation_cleanup.py` — the gate's end-to-end contract,
  including the fallback path.
- `docs/DOCS_CLEANUP_GUIDELINES.md` — the operator-facing contract.

**Red/green:** the new tests failed 16/18 before the implementation
(`TypeError: unexpected keyword argument 'archivable_statuses'`,
`AttributeError: no attribute 'archivable_statuses'`, and the
`status: complete` file being returned as archivable); all pass after.

**Verification:**

- `pytest tests/test_doc_categorizer.py tests/test_documentation_cleanup.py`
  → 55 passed.
- The 8 test modules that touch the changed modules → 175 passed.
- The full crackerjack suite → 11636 passed, 128 skipped, 1 failed
  (`tests/unit/test_mermaid_renders.py::test_all_mermaid_blocks_parse`).
  The failure is environmental, not a regression: the validator needs
  `node_modules/jsdom` (an npm dev-dependency) which is not installed in
  a worktree. Re-run with `CRACKERJACK_JSDOM` pointed at the main
  checkout's install → **2 passed**. None of the markdown files this
  change touches contain a mermaid block.
- `ruff check` clean on the changed files; `ruff format --check` clean;
  `ty check` clean on the four changed source files.
- Fleet-wide archivable set, measured through
  `DocumentationCleanup._detect_archivable_files()` (the real cleanup
  entry point, not the categorizer alone):

  | Repo | Before | After |
  |---|---|---|
  | mahavishnu | 2 | **0** |
  | crackerjack | 1 (`coverage.json`) | 1 |
  | akosha | 0 | 0 |
  | session-buddy | 0 | 0 |
  | mcp-common | 1 (`coverage.json`) | 1 |
  | oneiric | 0 | 0 |

**Decision taken during execution that the plan left open:** the plan
listed "frontmatter that does not parse" and "frontmatter without a
`status:`" as the two fail-closed cases. A third surfaced during the red
phase: `extract_frontmatter`'s regex (`\A---\s*\n(.*?)\n---\s*(?:\n|$)`)
does **not** match an empty block (`---` / `---`), so an empty frontmatter
block read as "no frontmatter" and the file was archived. Fixed by
`_declares_frontmatter()`, which treats a leading `---` fence as a
declaration — the same convention
`crackerjack.tools.mdformat_wrapper.should_skip_file` already uses. A
file that opens with the fence and yields no readable status is now
fail-closed too.

**Finding that turned up during execution that the plan did not
anticipate:** `DocumentationCleanup._detect_archivable_files()` falls back
to `_detect_archivable_files_legacy()` when the categorizer raises. That
fallback matches by filename against `settings.documentation.archive_patterns`
and, before this fix, applied **no lifecycle gate at all** — so the
fallback was a gate bypass: the one path where a governed document could
be swept by name alone.

**What the ensemble review changed.** The first review round (2 of 3
reviewers returned; the third's dispatch hit the MCP idle timeout and
counts as a block) produced three findings, all of which landed:

1. *The legacy fallback was a gate bypass.* Fixed, and then fixed
   properly: the gate moved to a **single** application point in
   `_detect_archivable_files()`, so every detection path passes through it.
   Two application points would have failed quietly if an editor deleted
   one; one fails loudly.
2. *The operator contract still said "Complete → archive".*
   `docs/DOCS_CLEANUP_GUIDELINES.md` now states the `status:` table, the
   shipped-gated lifecycle, and that the tool enforces it.
3. *`archivable_statuses` was compared case-sensitively against a
   lower-cased status*, so a configuration written as `["Shipped"]` would
   have silently archived nothing. Both sides are now normalised, and the
   default has one home (`ARCHIVABLE_STATUSES`) instead of two literals.

**What the second review round changed.** All three reviewers returned
this time (`python-pro` passed; the other two asked for adjustments), and
both of them found the same regression, from opposite directions:

4. *The restructure over-applied the gate.* Moving the filter to the
   single choke point also moved it onto the non-markdown root artifacts
   — and a binary `.backup` cannot be read as UTF-8, so it failed closed
   and became **unarchivable**. The cleanup's actual job regressed. The
   gate now applies to markdown only (`_passes_lifecycle_gate`), and a
   test pins that a binary root artifact is still swept.
5. *A UTF-8 BOM defeats both detectors.* `read_text("utf-8")` keeps the
   BOM, so the anchored frontmatter regex missed the block and the
   first-line fence check missed it too — a BOM'd `status: draft`
   document read as "no frontmatter" and was swept. The shared
   extractor now strips a leading BOM, and the gate's own
   "does this declare frontmatter?" check also tolerates a BOM and
   leading blank lines. It is deliberately *more* tolerant than the
   extractor: a missed frontmatter is read as "not governed", which is
   the one direction that must never happen.
6. *The generated API docs still named the old method.* Updated by hand
   in `crackerjack/docs/generated/api/`. Regenerating them with
   `crackerjack run --generate-docs` from a worktree extracts **0
   files** and wipes 18k lines of `API_REFERENCE.md`, so it is not safe
   to run there.
7. *The plan's Architecture section and its Deltas list still described
   the earlier design.* Both now match the code, and the Deltas list
   names every file the change touches.

**What the third review round changed.** One reviewer returned; the other
two dispatches hit the pool timeout and count as blocks under the
fail-loud rule. The one that returned found two more doc/code
contradictions:

8. *The operator guidelines' Decision Tree still sent a completed plan to
   the archive*, contradicting the shipped-only rule the same document
   states. The tree now asks "Is it closed (`status: shipped`)?" and the
   `complete` → `shipped` step is spelled out.
9. *The guidelines and the decision record described the gate as applying
   to every candidate*, while the code exempts non-markdown. Both now
   state the markdown-only scope, and the decision record's code snippet
   shows `_passes_lifecycle_gate` rather than the raw predicate.

**What the fourth review round changed.** All three reviewers returned.
Two more real findings, both now fixed:

10. *Whitespace before the BOM defeats both detectors.* The gate's
    "does this declare frontmatter?" check stripped the BOM before the
    whitespace, so a file starting `" \ufeff---"` exposed the BOM rather
    than removing it — and the anchored extractor missed the block too.
    The check now strips whitespace and BOM together, in any order and
    any number, and a test pins that exact case.
11. *A bare string for `archivable_statuses` iterated characters.*
    `archivable_statuses="shipped"` would have produced a set of single
    letters and matched nothing. A bare string is now treated as one
    status, with a test.

    The same round's other reviewer asked for two things that are now
    tests: a *positive* BOM case (`status: shipped` behind a BOM must
    still archive — a BOM regression that blocked everything would look
    exactly like a working gate), and a structural test pinning the
    single-choke-point property, so a future module that moved files
    straight from `get_archival_candidates()` would fail a test rather
    than bypass the gate silently.

    The third reviewer found the operator guidelines still described the
    old flat `docs/archive/` scheme, which the 2026-10-15 archive-dir
    decision replaced with a per-area `<area>/.archive/<category>/`
    layout. That was stale on main, not introduced here, but it is a
    doc/code contradiction in a file this change edits, so the archive
    section and the decision tree now describe the scheme the code
    actually produces — including the categories the categorizer really
    writes (`summaries`, not `completion-reports`).

**What the fifth review round changed.** One reviewer passed; the other
two asked for adjustments, and every item landed:

12. *The markdown test was case-sensitive while the categorisation is
    not.* ``categorize_file`` matches its patterns with
    ``re.IGNORECASE``, so ``PLAN.MD`` is categorised the same as
    ``plan.md`` — but the gate's ``suffix != ".md"`` test treated it as
    non-markdown and left it ungated. The comparison is now
    case-insensitive.
13. *The structural pin only covered one module.* A new module that asked
    the categorizer for candidates, or composed an archive path itself,
    would have bypassed the gate with every test still green. The pin now
    walks the whole package and asserts that ``get_archival_candidates``
    and ``archive_target_path`` have exactly one caller each, and that
    the legacy fallback has exactly one.
14. *No end-to-end test that a governed document survives a real
    cleanup.* The unit tests exercised the detector; none ran the whole
    phase. There is now one that runs detect → back up → move and asserts
    a ``status: complete`` plan is still on disk afterwards, and its
    ``shipped`` counterpart is archived.
15. *A non-string or empty ``status:`` had no test.* Now pinned: an
    empty, null, numeric, or list value all block archival.
16. *The guidelines sent a completed plan to the wrong category.* The
    code routes ``*_PLAN.md`` to ``implementation-plans/``, not
    ``sprints-and-fixes/``.

**What the sixth review round changed.** One reviewer passed; the other
two asked for adjustments:

17. *A backup of a document slipped past the gate.* The gate keyed on the
    suffix, so ``foo.md.backup`` — which the categorizer's
    ``test_artifacts`` pattern matches — was swept ungated, and it holds
    a document's content. The gate now keys on the name, so a copy of a
    governed document is gated like the document.
18. *The decision record and the code comment disagreed about gitignore.*
    The categorizer's comment claimed a per-area ``!<area>/.archive/``
    un-ignore rule keeps moved files *tracked*; the decision record
    claimed the opposite. The record was right and the comment was
    stale: the fleet-wide ``**/.archive/`` catchall sits at the END of
    the shared gitignore block, so it wins over the earlier per-area
    negation (git takes the last matching pattern) — verified with
    ``git check-ignore -v`` in both mahavishnu and crackerjack. The
    comment now says so, because a reader who believed it would
    conclude the opposite about what an archived document does to the
    repository.
19. *The guidelines' tree said a frontmatter-less plan stays in root.* The
    code sweeps it by name — no frontmatter means "not governed", which is
    the scratch-artifact rule. The tree now says to give a live plan
    frontmatter, and why.

**What the seventh review round changed.** One reviewer passed; one asked
for a documentation fix, which landed:

20. *The guidelines still described the gate as suffix-based.* The code
    keys on the name, so ``foo.md.backup`` is gated like the document it
    is a copy of, while the guidelines said only markdown was gated. The
    paragraph now states the name rule.

**What the eighth review round changed.** One reviewer passed; one asked
for two documentation fixes, both landed:

21. *The guidelines' tree said a plan "without a `status:`" is swept by
    name.* That reads as "frontmatter with no ``status:`` field", which
    the code leaves in place — the fail-closed rule. The branch is
    reached only by a file with NO frontmatter at all, and it now says
    so.
22. *The examples still used the old flat archive paths and a category
    the code does not produce* (``completion-reports/``, which is
    ``summaries/``). Updated.

**What the ninth review round changed.** Two reviewers passed; one asked
for a documentation fix. Every example the guidelines name was then checked
by running the **real categorizer** against that exact filename, rather than
by reading the patterns — which is how the round's own report turned out to
be partly wrong, and how two further contradictions surfaced that it had not
reported.

23. *The guidelines' examples contradicted the code's routing.* Five were
    wrong: ``progress-indicator-analysis.md`` routes to
    ``implementation-reports/`` (the ``progress-.*`` pattern precedes
    ``analysis``), not ``analysis/``; ``PHASE_4_COMPLETION.md`` is
    ``keep_in_root`` and is never archived, though the example showed it
    under a ``.archive/summaries/`` path; ``TY_MIGRATION_PLAN.md`` routes to
    ``implementation-plans/``, though it was listed under "Keep in Root";
    ``MCP_GLOBAL_MIGRATION_GUIDE.md`` is ``keep_in_root``, though it was
    listed under "Keep in docs/"; and three examples showed
    ``summaries`` paths under ``sprints-and-fixes/`` and ``analysis/``
    headings. All now state the categorizer's real verdict.
24. *The archive section's glob bullets over-promised.* ``*_FIX*.md`` reads
    as covering ``*_FIX_ABC.md``, which the code does not match — its
    pattern is ``_FIXE`` optionally followed by ``S``. ``ZUBAN_*.md`` and
    ``AGENT_*.md`` match nothing the code classifies; the agent pattern
    needs an underscore on both sides (``*_AGENT_*.md``). Rewritten to the
    patterns the categorizer really uses.
25. *The decision record's residual bullet was false.* It claimed a copy
    whose name has no markdown extension (``plan.backup``) "is swept like
    any other artifact". It is not: the categorizer's backup pattern is
    ``r"\.backup$"``, and ``re.match`` anchors at the *start* of the name,
    so it matches only a file literally named ``.backup``. ``plan.backup``
    matches no category at all — it is neither swept nor gated, simply not
    classified. The bullet now says that, records the ``re.match``
    anchoring as the reason, and notes that widening the pattern is a
    separate change with its own blast-radius measurement. The code
    comment in ``_passes_lifecycle_gate`` was corrected to match.

    The same correction applies to the round-six finding 17: ``foo.md.backup``
    is not in fact swept — it matches no category either. The gate's
    name-based ``.md`` test still covers it, and the decision record and the
    code comment now describe it as the guard it is rather than as a live
    path.

    The round's report also claimed ``comprehensive_hooks_audit.md`` reaches
    no category. That one is wrong: ``categorize_file`` matches with
    ``re.IGNORECASE``, so ``.*_AUDIT\.md`` does match ``_audit.md``, and
    the file does route to ``audits/``. Checking the claim against the code
    is what caught it.

**What the tenth review round changed.** Two reviewers ran a confirmation
round on the ninth round's fix. Both found real problems — and both reached
their conclusions by *checking the code*, which is what made the
difference.

26. *The decision record had a stray code fence.* A ```` ``` ```` opener at
    line 140 with its closer at line 235 meant 95 lines of prose — the
    "One choke point" paragraph, the measured blast-radius table, the
    Known residuals, the Consequences, and the References — rendered as a
    literal code block. Both markers were left over from an earlier edit
    that replaced the fenced content with prose. Removed.
27. *A residual bullet used a universal quantifier that was false.* It
    said "A backup file is neither swept nor gated", but
    ``pyproject.toml.backup`` has its own pattern in ``temp_files`` and
    *is* swept. Narrowed to the case that is actually true: a backup
    whose name carries no ``.md``.
28. *The claim that the name test was "a guard rather than a live path"
    was false.* ``re.match`` anchors at the *start* of the name, so a
    pattern that is not end-anchored matches a prefix: the ``analysis``
    category's ``TEST_.*\.md`` classifies ``TEST_foo.md.backup`` as an
    analysis document, and the ``*.backup`` glob proposes it as a
    candidate. The name test is a **live** path — a suffix test would
    have swept that copy of a governed document ungated. The decision
    record and the code comment now say so, and two tests pin it: one
    that the copy is still classified, one that the gate gates it.
29. *The guidelines test could silently pass.* It matched only column-0
    ``-`` bullets and captured only the first backtick span, so a bullet
    written in another shape was skipped and a ``name`` → ``path`` bullet
    was misread as a keep-claim. Rewritten: list items are detected in
    every shape markdown allows (``, ``*``, ``+``, ``1.``, ``1)``, at any
    indentation); every backtick span in a bullet is extracted; a list
    item with no span is an error rather than a skip; and a completeness
    guard fails when a filename mentioned *anywhere* in the section — a
    table row, a prose sentence — is not one the checker checked. Verified
    red-green against five scenarios: a ``*`` bullet with a wrong
    destination fails, a ``*`` bullet with a right destination passes, a
    table row naming an unchecked file fails, a two-span bullet with a
    wrong path fails, and a list item with no span fails.

**Two findings recorded but not changed.** Both are pre-existing and
outside the gate's blast radius:

30. *``files_preserved`` does not report what the gate protected.* It
    counts only the root files in the ``essential_files`` setting, so a
    cleanup that preserves two governed documents still reports them
    only in the "Files moved: 0" line — the gate's skips are dropped
    without a count or a log line. The field's meaning is asserted with
    exact strings in four existing tests, so changing it is a separate
    change rather than a quiet edit here.
31. *``_validate_preconditions`` creates an unused directory.* The
    ``"."`` entry in ``SCANNED_ARCHIVE_AREAS`` makes it create
    ``pkg_path/.archive/``, which nothing writes to — the categorizer
    routes a root file under the ``docs`` area instead. Pre-existing, and
    harmless.

**What the eleventh review round changed.** The round's specialists
confirmed the gate itself is sound — no fail-open path, a single choke
point over both detection paths, and one source of truth for the default
status set — and put the last two findings into the *test* rather than
the code. Both were silent-pass shapes, which is the one failure mode a
pin must not have:

32. *A path-shaped claim was neither mentioned nor checked.* The helper
    that maps a span to a filename returned "not a filename" for any
    span containing a ``/`` that was not an ``.archive/`` destination, so
    ``docs/plans/foo.md`` was invisible to the checker. Every span is now
    reduced to its basename before the extension check, so a path names a
    file exactly as a bare name does.
33. *A bullet that named a destination skipped its other filenames.* The
    destination branch ``continue``d, so the remaining filename spans in
    the same bullet counted as "checked" in the completeness guard
    without ever being compared to the categorizer — a ``name`` → ``path``
    bullet agreed with the code without having been checked against it.
    The claimed category is now extracted first, and every filename in
    the bullet is compared against it, so both halves are verified.

Verified red-green against four more scenarios on top of the earlier
five: a path-shaped span routing elsewhere than the claimed category
fails; a path-shaped span in a table row fails; an arrow bullet whose
source half routes elsewhere than the claimed category fails; an arrow
bullet whose source half agrees passes.

**What the twelfth review round changed.** One finding, in the guidelines
rather than the code:

34. *A pattern bullet contradicted the example right below it.* The
    ``.archive/sprints-and-fixes/`` bullet said the fix pattern is
    "``_FIXE`` optionally followed by ``S``" — which is one of the two
    patterns the ``fixes`` category uses. The other is ``.*_fix\.md``,
    and the bullet's own example, ``ERROR_DETAILS_DISPLAY_FIX.md``,
    matches **only** through that omitted one. The bullet now cites both
    patterns, and the section now says plainly that the patterns are
    illustrative and that
    ``DocumentationCategorizer.CATEGORIES`` is the authority — the
    examples are the part the test checks.

**What the merge pipeline's ensemble review changed.** The pipeline's own
three-agent ensemble returned ``needs_adjustment`` from all three
reviewers, and it exited 1 — no merge landed, which is the fail-loud
behaviour working. All three converged on two claim errors plus one
stale artifact:

35. *The guidelines' claim about ``scripts/docs_cleanup.py`` was false.*
    It said the script "tells you where the tool would put things". It
    does not: it registers ``--dry-run`` **twice**, so argparse rejects
    it before it reads a single file, and its forked category table still
    emits the old flat ``docs/archive/<category>/`` routes rather than
    the per-area paths. Both defects predate this change — the script
    has never run. The paragraph now says to use the tool rather than
    the script, and the decision record records the script's state.
    Making the script a faithful mirror of ``DocumentationCategorizer`` is
    a change to the script, and it has no tests of its own yet.
36. *The decision record credited the plan index with the shared
    extractor.* It said "the validator and the plan index see the same
    frontmatter the gate does". True for the validator — it imports the
    shared extractor, which strips a BOM. False for the plan index:
    ``crackerjack/tools/plan_index_sync.py`` carries its own
    ``extract_frontmatter`` and its own anchored regex, and does not
    strip a BOM. The claim is narrowed to the validator, and the plan
    index's divergence is recorded as a residual.
37. *The generated API docs omitted the new public method.* They had been
    hand-edited for the rename, but ``lifecycle_permits_archival`` was
    missing from both ``API_REFERENCE.md`` and ``SERVICES.md``. It is
    now in both, in the generator's own rendering — extracted to a
    scratch file and copied, so the text matches what the generator
    produces.

**Why the API docs were hand-edited rather than regenerated** — the
reviewers' finding exposed why. The generator cannot run from a
worktree: ``documentation_service._find_source_files`` filtered hidden
directories by the *absolute* path's parts, and every file in a checkout
under a dotted directory has a dotted component in its absolute path.
This fleet's worktrees live under ``~/.local/state/``, so every file was
filtered out — the generator reported "Extracted documentation from 0
files" and wrote a 23-line API reference over the committed 18,441-line
one. That is the wipe an earlier round had to undo with ``git restore``;
the cause was never diagnosed.

38. *The hidden-directory filter now tests the path relative to the
    repository root.* Both call sites share one helper. Two tests pin it:
    a checkout under a dotted path still yields its files, and
    ``.venv`` inside the repo is still skipped. With the fix the
    generator finds 1,125 files where it found 0.

    Regenerating wholesale is still the wrong move for this change: the
    generator's scope is the whole repository root, and it renders 40,883
    lines against the committed 18,441 — the committed file was produced
    from a narrower scope. So the new method was added in the
    generator's own rendering rather than by replacing 18,000 lines of
    unrelated drift.

**What the confirmation round on that commit changed.** The parallel
three-reviewer round came back with one ``needs_adjustment`` and two
``pass`` — and the ``needs_adjustment`` was in my prose, again, plus one
real hole in a test:

39. *The residual count was stale.* The section said "Three boundaries of
    the gate" while listing five bullets. It says five.
40. *The plan-index residual's consequence was false.* It claimed "a
    BOM'd plan's index row can be built without its declared status". It
    cannot: `_entry_from_file` returns ``None`` for a file whose
    frontmatter does not parse, and ``render_plan_index`` skips it
    (``if entry is None: continue``). A BOM'd file gets **no row at
    all** — it is absent from the index, not indexed with a missing
    status. The residual now says that, and narrows the BOM-blindness
    to the legacy in-crackerjack path: with
    ``documentation.use_shared_regenerator`` set, the plan index routes to
    ``oneiric.plan_index.regenerate``, which uses the shared
    BOM-stripping extractor.
41. *The generator could still truncate a committed reference.* The
    hidden-directory fix removed the cause of the zero-file scan, but the
    failure mode — "regenerate" silently meaning "truncate" — outlived
    it. The generator now refuses an empty scan and returns ``False``
    without writing. Verified red-green: with the guard removed, the
    committed reference is overwritten and the test fails.
42. *An existing test's mock had gone ineffective.* It mocked
    ``_find_source_files``, but the code called ``_visible_source_files``
    directly, so the mock did nothing. The generator now calls
    ``_find_source_files()`` — the single seam, which delegates to
    ``_visible_source_files()`` — so the mock works again. That test's
    expectation changed from ``True`` to ``False``: refusing an empty
    scan is the point, and the old expectation encoded the behaviour
    that caused the wipe.
43. *The guidelines test had a multi-destination hole.* A bullet naming
    two destinations compared every filename in it against only the
    **last** claimed category, so a wrong first destination passed. Each
    destination is now checked against its own category, and a bare name
    alongside destinations must match one of the categories the bullet
    claims. Verified red-green: a two-destination bullet whose first
    half is wrong now fails.
44. *The new path tests asserted basenames.* A filter that looked only at
    the first path segment would have passed them. They now assert
    relative paths (``crackerjack/services/thing.py``), so depth is
    pinned too.

**What the final review round changed.** The next three-reviewer round
came back with one ``needs_adjustment`` and two ``pass``. The
``needs_adjustment`` was the test — three silent-skip shapes in it — and
one more false example in the guidelines.

45. *The basename-keyed claims dictionary dropped a destination.* The
    checker keyed each destination's claimed category by basename, so a
    bullet naming two destinations with the **same** basename kept only
    the last category; the first was never compared. That is exactly
    what the code comment said the change prevented. Each destination is
    now compared directly, on its own.
46. *The extension allowlist made the completeness guard circular.*
    ``_filename_of`` and ``_mentioned_filenames`` shared one hand-written
    list, so a span outside it was invisible to both the checker and the
    guard that asks whether anything was left unchecked. There is no
    extension list any more: a span is a routing claim exactly when the
    categorizer classifies it, so the checker covers precisely the files
    the sweep can touch — and a mention of a ``.yaml`` is not a routing
    claim at all. The categorizer gained ``CANDIDATE_PATTERNS`` so the
    globs have one home.
47. *Destinations were collected from list items only.* A destination
    written in a table row or a prose sentence was never compared, and
    passed if its basename appeared in any bullet. Destinations are now
    collected from the whole section, and each is checked against its own
    category. A category named in words on a line that names a routable
    file is checked too.

    Every one of these was verified against a scratch copy of the
    guidelines rather than by mutating the tracked file: a wrong
    first destination, a wrong destination in a table row, a routable
    file mentioned only in prose, a keep-heading bullet naming an
    archivable file, and a prose category claim.
48. *The guidelines cited the wrong example for the name gate.* They
    cited ``foo.md.backup`` — but that name matches no category and is
    never proposed for archival, as the decision record's own residual
    says. The live example is ``TEST_foo.md.backup``, which the
    ``analysis`` category's ``TEST_.*\.md`` pattern classifies by prefix
    match.

One residual was checked and cleared rather than changed: a binary
``*.md.backup`` enters the frontmatter-read path, and the reviewer
wondered whether ``lifecycle_permits_archival`` swallows
``UnicodeDecodeError``. It does — ``except (OSError, UnicodeDecodeError)``
returns ``False`` — and a binary ``TEST_binary.md.backup`` was verified
to stay put with a warning rather than abort the cleanup.

**What the last review round changed.** One reviewer hit the dispatch
timeout (a block under the fail-loud rule) and the other two returned
``needs_adjustment``. Their findings:

49. *``analyze_all`` hardcoded the five globs.* That is exactly the
    copy-drift ``CANDIDATE_PATTERNS`` was introduced to forbid, in the
    one place the constant was not wired in. It uses the constant now.
50. *Two of the new checks could fail on a correct document.* A
    keep-file named in the same bullet as a destination was flagged
    (its destination is ``None``, which is not the claimed category),
    and a line naming two categories required the file to match *every*
    one. A keep-file alongside a destination is the keep half of the
    claim, and a file has to match *one* of the categories named on its
    line. Both verified in both directions: the false failures no longer
    fire, and a genuinely wrong claim is still caught.
51. *The prose-category check only knew destination names.* It
    recognised ``summaries`` but not the internal key
    ``completion_reports``. Both are recognised now, and both map to the
    destination they mean.
52. *``_resolve_collision`` was uncovered.* The archive path's numeric
    suffix had no test at all. There is one now, verified red-green:
    with collision resolution disabled, the existing destination would
    be overwritten and the test fails.
53. *A question about the extractor's contract, answered with tests.*
    The reviewer asked whether ``lifecycle_permits_archival`` assumes
    ``parsed`` is a dict — ``parsed.get`` would raise ``AttributeError``
    on a scalar or list frontmatter and abort the whole cleanup. It
    cannot: ``extract_frontmatter`` rejects a non-mapping before it
    returns ("Frontmatter is not a YAML mapping"), so the gate sees a
    parse error and fails closed. Two tests now pin that contract, and
    the scalar and list cases were both run to confirm.

**A pre-existing defect recorded, not changed.** The cleanup's backup
tar is flat: ``tar.add(file_path, arcname=file_path.name)`` stores each
file under its basename, so ``rollback_cleanup`` restores a file to the
repository *root* rather than to the area it came from. It predates this
change and is unchanged here, but it is the mechanism that would undo a
sweep, so it is now a recorded residual.

**What the last round changed.** One reviewer returned
``needs_adjustment``; the other two dispatches hit the MCP idle timeout
and count as blocks under the fail-loud rule.

54. *The ``*.md`` glob was hardcoded in three places besides the
    constant* — the categorizer's markdown scan, the cleanup service's
    legacy fallback, and its essential-file count. That is the
    copy-drift ``CANDIDATE_PATTERNS`` was introduced to forbid, in the
    places the constant was not wired in. The constant is now
    self-describing (``MARKDOWN_PATTERN``, ``OTHER_CANDIDATE_PATTERNS``,
    ``CANDIDATE_PATTERNS``) and every glob reads from it. Behaviour-
    neutral: the legacy fallback still scans markdown only, which is
    what it always did.
55. *The gate now checks the extractor's contract rather than trusting
    it.* The reviewer asked — twice — whether ``parsed.get("status")``
    assumes a mapping, and a scalar or list frontmatter would raise
    ``AttributeError`` and abort the whole cleanup. The premise was
    checked and is false: ``extract_frontmatter`` rejects a non-mapping
    before it returns ("Frontmatter is not a YAML mapping"), and both
    cases were run to confirm they fail closed. But the gate reads
    arbitrary files, and one malformed document must not abort a whole
    cleanup, so the gate now checks for itself. The guard is pinned by a
    test that violates the extractor's contract — verified red-green:
    with the guard removed, the test fails with an ``AttributeError``.

    (Writing the guard also caught an ordering bug in the guard itself:
    placed before the ``parsed is None`` branch, it would have gated
    every *ungoverned* document — no frontmatter at all — instead of
    letting it through.)

**What the last round changed.** One reviewer passed; the other two asked
for adjustments, and both findings were in prose that contradicted the
document it sat in:

56. *Core Principle 2 contradicted the shipped-only rule.* It said
    "Completion reports and historical docs go to ``<area>/.archive/``"
    — while the same document says a completion report at ``status:
    complete`` stays put. It now says *closed* documents go there, and
    that a document is closed at ``shipped``, not at ``complete``.
57. *The Maintenance checklist repeated the contradiction.* "Archive
    completed implementation plans" and "When to run cleanup: After major
    feature completion" both said *completed*, which is the status the
    rule explicitly refuses. Both now say *shipped*.
58. *The guidelines test's docstring overstated what it reads.* It
    claimed to check "every filename mentioned anywhere in the section —
    in a bullet, a table row, or a prose sentence". It reads backticked
    spans. The docstring now says so, and says why: the guidelines
    write every path and name as a code span, and a checker that
    guessed at prose would produce false failures as readily as it would
    find real ones.

**What the last round changed.** One reviewer passed; the other two asked
for adjustments — one about the guidelines' own wording, one about the
test's scope.

59. *The keep-criterion drifted from the rule it sits next to.* Three
    places said a document "stays" if it is *active* or *not yet
    completed*, while the rule keeps anything that is not ``shipped``. A
    ``status: complete`` document stayed put but appeared in no list at
    all. All three now say "until they are ``status: shipped``" and
    "Shipped implementation plans".
60. *A routing claim about a file the categorizer no longer routes was
    skipped* — which is the exact drift a routing check exists to catch.
    A routing claim (a destination path, or a category named on a line)
    is now checked for any file-like name; a name the categorizer does
    not route is a stale claim, and it is flagged.
61. *The prose-category check lacked the keep-file exemption* the
    example check had, so a stay-put file named beside a category was a
    false failure. It has the exemption now. Verified in both
    directions: a keep file beside a *correct* category claim passes,
    and beside a *wrong* one it is caught.

All three verified against scratch copies of the guidelines rather than
by mutating the tracked file.

**Anticipated but not needed:** the plan considered applying the gate to
the non-markdown root artifacts (`*.py`, `*.json`, `*.txt`, `*.backup`).
They cannot carry a document lifecycle, and reading them as UTF-8 to find
out would have made binary `.backup` files unarchivable — a regression in
the cleanup's actual job. The gate is applied to the markdown scan only.
(The second review round re-introduced exactly this regression; finding 4
above undoes it.)

**Still open (cross-repo):** mahavishnu's interim
`documentation.auto_cleanup_on_publish: false` guard becomes unnecessary
now that the tool enforces the gate. It should be reverted once this
lands; the guard is recorded in
`~/Projects/mahavishnu/docs/decisions/2026-11-15-publish-cleanup-bypasses-archive-gate.md`.
