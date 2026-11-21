---
title: Lift the mdformat frontmatter skip and protect numbered lists
description: "The mdformat hook kept every YAML-frontmatter document out of formatting, which left 783 documents across the six fleet repos unformatted. The mdformat-frontmatter plugin, installed by 78b3c8ca, made it safe to lift that exclusion -- but only once the hook also stopped renumbering ordered lists, because mdformat's default collapses `1. 2. 3.` to `1. 1. 1.` and that destroys cross-references inside decision records and plans. Phase 1 added `--number` and lifted the skip; Phase 2 rolled the resulting formatting churn across the fleet, one repository at a time. Both phases are executed and committed locally. The rollout reaches the other five repositories once the release carrying `mdformat-frontmatter` is published and each repository syncs -- see §6, 'Still to do'."
audience: crackerjack maintainer
created: 2026-11-20
status: partial
role: implementation
topic: process-discipline
date: 2026-11-20
last_reviewed: 2026-11-21
superseded_by:
blocks_on: []
---

# Lift the mdformat frontmatter skip and protect numbered lists

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

## 1. Brief (intent-driven)

> **Current state (2026-11-21):** both phases are executed. Phase 1 shipped in
> crackerjack (`e9448967`, `7556b402`, `10341d2a`); Phase 2's rollout is
> committed locally in all six repositories (§6, per-repository table). What
> remains is operator-side: publish the release that carries
> `mdformat-frontmatter`, then push each repository's commit. Until the
> release lands, the other five repositories' hooks still skip frontmatter
> documents and their markdown stays in the pre-lift state. **This document is
> therefore a record of executed work, not a brief to execute.** The sections
> below are preserved as written so the reasoning survives, with the
> corrections the post-execution review made marked in place.

### Goal

783 YAML-frontmatter documents across the six fleet repositories are
formatted for the first time, and no document loses meaning in the
process.

`should_skip_file` excluded every document whose first line is
`---`, so those files never reached mdformat at all: their bodies kept
whatever formatting they had when written. Lifting the exclusion gives
the fleet one markdown style, which is the point of having a format
gate at all.

The goal is *not* "run the formatter over everything". It is "run the
formatter over everything, without changing what the documents say".
Two specific hazards are in scope because both rewrite meaning rather
than style, and both are measured below rather than assumed.

### Constraints

- The `mdformat-frontmatter` plugin is already declared
  (`crackerjack/pyproject.toml`, commit `78b3c8ca`) and already
  guarded: the hook fails loud when a tracked frontmatter document
  exists and the extension is missing from the environment that will run
  mdformat. This plan does not redeclare the dependency and does not
  re-architect the guard.
- Version bumps and PyPI publishes are the operator's.
- Push is the operator's.
- One commit per phase, each independently revertible. The fleet
  rollout is one commit per repository, each independently revertible.
- The plan index must stay complete. A document whose frontmatter stops
  parsing disappears from `PLAN_INDEX.md`, which is exactly how the
  original failure presented.
- No plan file, ADR, or decision record may change its *meaning*. Style
  changes are in scope; content changes are not.

### Failure Conditions (verifier-only)

Each condition is mechanically checkable.

1. `should_skip_file` in `crackerjack/tools/mdformat_wrapper.py` no longer
   excludes a document whose first line is `---`. Two `stripped == "---"`
   tests survive (lines 140 and 162), and both are the *guarded* BOM and
   multi-document-YAML checks this plan's own follow-up commits added
   (`7556b402`, `10341d2a`) — not the blanket exclusion. This condition
   was written before those commits existed and was falsified by them.
2. `rg -n '\-\-number' crackerjack/tools/mdformat_wrapper.py` returns
   a match.
3. For each of the six repositories: the frontmatter semantic check
   (§2.3) reports `semantic differences: 0` and `errors: 0`. This check
   is an operator measurement over the repository's live frontmatter'd
   documents, not a committed script: the §6 per-repository table records
   the numbers each repository produced. No script in the fleet emits
   `semantic differences: 0`, so this condition cannot be re-run as a
   one-liner today.
4. For each of the six repositories: `git diff --name-only` contains no
   file with an extension other than `.md` or `.markdown`.
5. For each of the six repositories: no ordered-list marker is
   *decreased* by the diff, compared **numerically** rather than
   textually. Every marker that changes increases or stays the same.
   This is what "source numbering is preserved" has to mean in
   practice, and it is the property that protects a reference like
   "item 4": no marker ever decreases, so `2.` never becomes `1.` and
   the item a reader was pointed at is still the item they find.
   (A marker-only hunk is not a failure. `--number` renders consecutive
   numbering, so a list whose markers were collapsed to `1. 1. 1.` by an
   earlier default-mode pass is *repaired* to `1. 2. 3.` — see §2.4 and
   §2.7. The comparison is numeric because the zero-padded rendering of
   §2.4 changes `1.` to `01.`, which is numerically equal but
   textually smaller.)
   **The one exception:** the three documents with a genuine hole listed in
   §2.7 each have one marker decreased when `--number` closes the gap.
   That is the accepted repair, and those three documents are the only
   allowed exception:
   - `crackerjack/mcp/agents/crackerjack-specialist.md`
   - `crackerjack/docs/plans/2026-09-07-bodai-shared-gitignore-snippet.md`
   - `mahavishnu/docs/decisions/2026-10-15-unified-event-bus-wrapper.md`
6. The plan-index audit reports zero frontmatter'd files missing from
   `PLAN_INDEX.md`. **Only mahavishnu ships an index audit**
   (`scripts/audit_plan_index.py`); the other five repositories have no
   such script, so for them this condition is satisfied by regenerating
   the index with that repository's own `scripts/regenerate_plan_index.py`
   and confirming a second run reports no change. mahavishnu's audit
   currently **fails** — `docs/plans/2026-11-21-fleet-session-start-status-banners.md`
   is missing from its index. That is a post-rollout addition, not a
   rollout defect.
7. `pytest tests/unit/tools/test_mdformat_wrapper.py --no-cov` passes. The
   `--no-cov` is required: the repository's `addopts` carry
   `--cov-fail-under=75.0`, so a single-file run exits 1 on the coverage
   floor (5.23% measured) even when all 53 tests pass. The bare command
   fails as written.

## 2. Context

### 2.1 Why the documents are excluded

`crackerjack/tools/mdformat_wrapper.py:43`:

```python
    stripped = first_line.strip()
    return stripped == "---" or (len(stripped) >= 3 and set(stripped) == {"_"})
```

The first clause excludes every document whose first line opens a YAML
frontmatter block. It is there because mdformat 1.0.0 core has no
frontmatter support: given such a document it rewrites the `---` fence
into a horizontal rule and flattens the YAML into body text. That
corruption then breaks frontmatter extraction, and a plan whose
frontmatter no longer parses drops out of `PLAN_INDEX.md` entirely --
its lifecycle state becomes invisible rather than wrong.

Frontmatter'd documents by repository, counted from tracked files:

| repository | documents with frontmatter |
|---|---|
| crackerjack | 306 |
| mahavishnu | 311 |
| oneiric | 99 |
| session-buddy | 31 |
| akosha | 30 |
| mcp-common | 6 |
| **total** | **783** |

The underscore clause (a file whose first line is a run of `_`) is a
different rule about a different thing and stays.

### 2.2 The plugin makes the exclusion unnecessary

`78b3c8ca` added `mdformat-frontmatter>=2.2.0` to
`crackerjack/pyproject.toml` and added the fail-loud guard. mdformat's
CLI enables every installed parser extension by default, so the plugin
activates with no further wiring.

The singular package name is deliberate. Two near-identical packages
exist and they behave oppositely on the same input, tested in isolated
venvs against mdformat 1.0.0:

| | `mdformat-frontmatter` (butler54) | `mdformat-front-matters` (KyleKing) |
|---|---|---|
| frontmatter on a hostile fixture | re-serialized, **quotes preserved** | re-serialized, quotes stripped |
| `"yes"` | stays the string `yes` | becomes bare `yes`, which YAML 1.1 parses as the boolean `True` |
| formats | YAML only | YAML, TOML, JSON |
| extra CLI | none | `--strict-front-matter`, `--sort-front-matter` |

The plural package's strict mode would fail loudly on *malformed*
frontmatter, which the fleet's schema validator already covers. It was
not chosen because stripping quotes is the worse trade for frontmatter
that machine readers parse.

**Neither package preserves the block byte-for-byte.** The singular one
parses the block with ruamel and dumps it again
(`preserve_quotes = True`, `indent(mapping=2, sequence=4, offset=2)`,
`width = maxsize`), so quotes, comments and key order survive and the
parsed values are unchanged, but the text is not identical — a
`None`-valued key comes back as an empty value, and long scalars are
re-wrapped. The byte-preserving path is its *error* fallback, used only
when the block cannot be parsed. This distinction matters: the earlier
wording in this plan said "byte-for-byte", and the plan's own
measurement below is what disproved it.

The two packages register under **different entry-point names** —
`frontmatter` and `front_matters` — so pip installs both side by side
without complaint. mdformat then logs a plugin conflict, keeps one
renderer, and the disagreement about quotes becomes a silent semantic
change to frontmatter. The guard counts front-matter extensions rather
than looking for one by name, and refuses to run unless there is exactly
one.

### 2.3 What the plugin actually does to the fleet's documents

Measured by formatting live (non-archived) frontmatter'd documents with
the plugin and comparing parsed YAML before and after:

| measurement | result |
|---|---|
| live documents checked | 65, across all six repositories |
| **semantic differences** (what the YAML parsers read) | **0** |
| text-only differences | 24 |
| frontmatter blocks that vanished | 0 |
| YAML parse errors | 0 |

Every one of the 24 text-only differences is the same rewrite:
`superseded_by: null` becomes `superseded_by:`. Both parse to `None`,
so the schema, the plan index and `superseded_by` resolution all see
the same value.

**This is the property that makes the churn safe: the frontmatter the
tools read does not change, so nothing downstream of it can break.**
The text does change — that is the ruamel round-trip, and it is exactly
what the `null`-to-empty rewrite above is. The same measurement over
crackerjack's full tracked set, 307 documents, gives 277 text-only
differences and not one of a different kind.

One risk deserves its own measurement, because lifting the skip hands
mdformat a document it has never seen before: a file whose first line
is `---` but which is not a YAML block. Measured across all six
repositories, **every** tracked `.md` and `.markdown` file whose first
line is `---` also has a closing `---` fence — there is no lookalike
document anywhere in the fleet. Where one did exist, the plugin
degrades it safely: on a `---\n\n# heading` fixture it renders the
`---` as an underscore horizontal rule and exits 0, which is what the
`---` meant anyway (a thematic break).

A second lookalike does exist and is handled explicitly: a document
whose first line is a **byte-order mark followed by** `---`. The
plugin's front-matter rule is BOM-blind, so formatting such a document
flattens its frontmatter into a heading and the document drops out of
`PLAN_INDEX.md`. Such documents are excluded from formatting and
reported. No tracked document in any of the six repositories currently
has one.

### 2.4 The hazard that is NOT about frontmatter

The bodies do change, and one of mdformat's normalizations rewrites
meaning.

mdformat's default renders every ordered-list item with the marker
`1.`. Measured across a live sample of the fleet's documents, 211
ordered-list markers are rewritten. In a decision record the number is
often a reference:

```markdown
3. **Should we replace the custom /health route with `register_http_health_route`?**
4. **What happens to the `RateLimitingMiddleware`?**
```

becomes

```markdown
3. **Should we replace the custom /health route with `register_http_health_route`?**
1. **What happens to the `RateLimitingMiddleware`?**
```

The second item's number is now a lie, and any prose referring to
"item 4" refers to nothing. This is the damage recorded in the fleet's
own gotcha memory for the mdformat hook.

mdformat's `--number` flag renders consecutive numbering instead. It
keeps the FIRST marker of each list and numbers the rest consecutively
from it, so a well-formed list is unchanged, a list that continues a
count from a sibling list is unchanged, and a list that an earlier
default-mode pass collapsed is repaired:

| source | default | `--number` |
|---|---|---|
| `1. 2. 3.` | `1. 1. 1.` | `1. 2. 3.` |
| `3. 4.` (continuing) | `3. 1.` | `3. 4.` |
| `1. 1. 1.` (collapsed by an earlier pass) | `1. 1. 1.` | `1. 2. 3.` |
| nested `1. / 1. 2. / 1.` | `1. / 1. 1. / 1.` | `1. / 1. 2. / 2.` |

Two consequences the fleet's own documents decide for us:

- **A collapsed list is repaired, not preserved.** 3366 of the fleet's
  4551 ordered lists carry the `1. 1. 1.` signature of an earlier
  default-mode format pass. `--number` turns them back into
  consecutive numbering. That is a content change to
  already-committed documents, in the direction of correctness, and it
  is the larger part of the churn.
- **A list is rendered zero-padded once it would number past 9.** The
  rule is `pad = len(str(list_len + starting_number - 1))`, so the width
  comes from the **item count plus the starting number**, not from the
  largest marker in the source. A ten-item list whose source markers are
  all `1.` renders `01. … 10.`, even though no marker above `1.` appears
  anywhere in the source; a two-item list starting at `9.` renders
  `09. 10.`, because 2 + 9 - 1 = 10; and `1. … 9.` (nine items) does not
  change, because 9 + 1 - 1 = 9. Measured over every tracked
  `.md`/`.markdown` in the six repositories — 1,532 files, archived
  included — **1,027 zero-padded markers across 99 files**, over **610
  lists** of 4,137 ordered lists. The earlier figure of **179** was taken
  over a narrower, live-only corpus, so the two counts measure different
  sets; the trigger itself was wrong either way. CommonMark renders the
  list as `1.` through `13.` regardless — the leading zero is a
  source-text artefact, not a rendered one.

**`--number` is therefore a prerequisite for the lift, not an
afterthought.** Lifting the skip first would collapse the numbering in
783 documents and a later commit would only partially restore it.

Two further body effects were observed and accepted as style-only:

- **151 double-backtick code spans become single-backtick.** In
  CommonMark both render as a code span with identical content, so the
  rendered document is unchanged. It is a source-text change to decision
  records, which the operator may want to know about.
- **221 documents lose their table column padding, and `<` inside a
  table cell is escaped** (`(<500 LOC)` becomes `(\<500 LOC)`). mdformat
  has no table support at all (§2.9) — a table is a paragraph to it.
  The padding disappears because markdown-it's inline parser collapses
  runs of whitespace, and the `<` is escaped because mdformat escapes
  the characters that could open an HTML tag. Neither changes the
  rendered document, so both are style-only — but they are source-text
  changes across 221 documents, which is the larger of the two.

### 2.5 The `--extensions` flag must not be used

mdformat's `--extensions` flag *requires* and *enables* named
extensions, and naming one **restricts** the enabled set to just that
one. Confirmed in mdformat's own CLI (`mdformat/_cli.py`: when
`--extensions` is given the enabled set is
`{k: PARSER_EXTENSIONS[k] for k in opts["extensions"]}`, otherwise it
is every installed extension), and observed against mdformat-gfm: with
`--extensions frontmatter`, the `tables` extension stopped formatting
tables. The CLI enables every installed extension by default, so the
wrapper names none, and the frontmatter extension is verified
separately by the probe added in `78b3c8ca`.

**No fleet repository installs mdformat-gfm.** Measured across all six
venvs: every one carries mdformat 1.0.0 and none carries the GFM
extension, so the fleet's mdformat is table-blind everywhere. That is
why §2.9's table guard is the *only* protection tables have here rather
than a second line of defence — and why installing mdformat-gfm into a
fleet venv later would change the fleet's formatting output.

### 2.6 Where the churn lands

The wrapper runs against the repository it is invoked in, preferring
that repository's own `.venv/bin/mdformat`. Every fleet repository
installs crackerjack as a dependency, so every repository's venv
carries the plugin once it is synced. The rollout is therefore six runs
of the existing hook, one per repository, plus the plan-index
regeneration each repository needs.

Measured over the live (non-archived) markdown of all six
repositories, by formatting each file and comparing:

| repository | live `.md` files | change under default | change under `--number` |
|---|---|---|---|
| crackerjack | 301 | 172 | 236 |
| mahavishnu | 551 | 256 | 430 |
| oneiric | 133 | 85 | 112 |
| akosha | 80 | 30 | 55 |
| session-buddy | 153 | 102 | 129 |
| mcp-common | 40 | 3 | 14 |
| **total** | **1258** | **648** | **976** |

**Reconciling the counts that appear across this plan** (added
2026-11-21, after the rollout made them look inconsistent). They measure
different sets, and the plan did not say so:

| figure | what it counts | measured over |
|---|---|---|
| **1,258** | live markdown files | live, non-archived tracked markdown (the table above) |
| **976** | files that *change* under `--number` | that same live set, before the rollout |
| **1,038** | the wrapper's in-scope set across the fleet | tracked, non-gitignored, non-skipped documents (§2.9) |
| **777** | files the rollout actually changed | the six rollout commits, added up (221 + 403 + 81 + 32 + 32 + 8) |

The 976 and the 777 differ because the census ran over live markdown
while the rollout ran over the wrapper's tracked set, and because some of
the predicted changes were already applied when the rollout reached those
repositories.

Two things this table says.

**`--number` touches MORE files than the default does**, because the
fleet's markdown was formatted under the default, so its ordered lists
carry the collapsed `1.` markers. Switching to `--number` restores the
real numbering, which changes documents that the current gate already
considers formatted. That is a correction, not new damage, but it is
why Phase 1's diff is larger than "the files the skip was hiding".

**The default column is not zero either.** 648 live files are not
mdformat-clean today, because the frontmatter exclusion hides most of
them from the gate entirely.

One correction to how "live" is counted, which the rollout depends on.
The wrapper does not see every tracked markdown file:
`get_git_tracked_files` drops any file matching a `.gitignore` pattern,
and tracked files can match an ignore rule. In crackerjack that is 556
tracked `.md` files, of which **300** reach the wrapper — 254 of the
256 exclusions being `docs/**/.archive/**` (which `should_skip_file`
excludes anyway) and two `data/README.md` files. Of the 180
frontmatter'd documents the wrapper sees, **172** are now in scope.
So Phase 2's crackerjack rollout touches 287 files, not 556, and the
archives stay where they are.

### 2.7 What the fleet's ordered lists actually look like

`--number` renumbers a list consecutively from its first marker, so
whether that is a repair or a loss depends entirely on the shape of the
list it finds. Measured over every tracked markdown file in all six
repositories, classifying each ordered list by what `--number` does to
it:

| shape | example | what `--number` does | count (fleet) |
|---|---|---|---|
| **collapsed** | `1. 1. 1.` | repairs to `1. 2. 3.` | 3366 |
| **signature** | `4. 1. 1.` | repairs to `4. 5. 6.` | 80 |
| **consecutive** | `1. 2. 3.` | unchanged | 1101 |
| **genuine hole** | `1. 2. 4. 5.` | closes the hole: `1. 2. 3. 4.` | 3 |

The census that produced these numbers treats a list as continuing
across a continuation line — an indented line that is not itself a
marker — and ignores markers inside fenced code blocks. An earlier
census did neither, and reported 5545/53/3/2296: it ended a list at
every non-marker line, so a list that wrapped was never grouped and
every gap inside it went unseen. The fence rule matters for the same
reason it matters to the formatter: a `---` or a `1.` inside a fence is
sample content, not a list.

The first two shapes are damage from the earlier default-mode format
pass, and `--number` undoes it. The **signature** shape is the one that
looks alarming and is not: the first item keeps its number, so a
reference to "item 4" still lands on the same item.

The genuine holes are the only lists where `--number` *decreases* a
number a reader might have been given. There are three:

| repository | document | markers | verdict |
|---|---|---|---|
| crackerjack | `crackerjack/mcp/agents/crackerjack-specialist.md` | `1. 2. 3. 4. 5. 7.` | item 6 was deleted at some point; no prose in the document names a list item by number |
| crackerjack | `docs/plans/2026-09-07-bodai-shared-gitignore-snippet.md` | `1. 2. 4. 5. 6.` | item 3 was deleted at some point; no prose in the document names a list item by number |
| mahavishnu | `docs/decisions/2026-10-15-unified-event-bus-wrapper.md` | `1. 3. 4. 5.` | item 2 was deleted; the only numbered references in the document are to "Phase 6.4", not to list items |

None of them has prose that names a list item by number, so closing the
holes is a fix, not a loss. The rollout confirms the count: exactly three
documents decreased a marker — crackerjack's two and mahavishnu's one.

A fourth candidate is **not** a hole.
`mahavishnu/docs/plans/2026-10-29-bifrost-bodai-cache-wiring.md` carries
`1. 2. 1.` — the third item is mis-numbered in the source and should be
`3.`, so `--number` *raises* it to `1. 2. 3.`. The only prose reference is
to "step 1", which `--number` leaves alone. It sat in the table above
because it was counted alongside the genuine holes; the rollout diffs show
it as an increase, not a decrease.

An earlier census also counted `oneiric/docs/implementation/PACKAGE7_SUMMARY.md`
(`1. 5.`) as a hole. It is a false positive: the sequence is inside a
fenced code block, which mdformat does not touch. The census now skips
fenced content, so it no longer appears.

### 2.8 How the hook actually invokes the wrapper

The hook runs `python -m crackerjack.tools.mdformat_wrapper`
(`crackerjack/config/tool_commands.py`), and the wrapper computes its
own file list from `get_git_tracked_files`. The executor also has an
incremental path: for a hook with `accepts_file_paths=True` it calls
`hook.build_command(changed_files)`, which appends the changed files to
the command line
(`crackerjack/executors/hook_executor.py:525-531`,
`crackerjack/config/hooks.py:92-99`).

Two consequences:

- **The wrapper formats its whole tracked set in either mode.** The
  changed files are appended to a command that already carries every
  tracked non-skipped file, so the incremental path adds a duplicate
  argument, not a narrower scope.
- **The changed files bypass `should_skip_file` entirely.** The
  wrapper passes `argv` straight through to mdformat
  (`_build_mdformat_cmd` does `cmd.extend(argv)`), so a changed
  document that the skip list excluded is still handed to mdformat.
  This is how the original frontmatter destruction was reachable even
  while the skip existed — and it is why the fail-loud guard, which
  scans every tracked document regardless of how the command was
  built, is the protection that actually holds.

The skip patterns that remain (`*PLAN.md`, `**/.archive/**`, …) are
still bypassable in incremental mode. That is a pre-existing
inconsistency, unchanged by this plan and not fixed by it.

**Correction (2026-11-21):** the last clause no longer holds for this
plan's own additions. The BOM and multi-document-YAML guards introduced
in §2.9 sit *inside* the bypassed function, so they do not hold on the
argv path — see the end of §2.9.

### 2.9 Three things the lift is not safe against

The frontmatter skip was the only thing standing between mdformat and
this fleet's documents, and removing it exposed three hazards that the
plan did not anticipate. All three were found by running the rollout,
not by reading mdformat's source, and all three corrupt a file rather
than failing loudly. The wrapper now handles them (crackerjack
`10341d2a`) — with one exception, recorded at the end of this section:
the two new guards do not cover the argv path.

**A `.md` file that is really a stream of YAML documents.**
`mahavishnu/mahavishnu/commands/jot.md` holds Claude Code slash-command
definitions — a run of `---`-separated YAML documents wearing a `.md`
extension. mdformat is a *markdown* formatter: it read the prose line
before each separator as a setext heading underline and turned every
separator into an ATX heading, so

```markdown
---
description: Show jot inbox vitals
allowed-tools: []
---
```

became `## description: Show jot inbox vitals allowed-tools: []`.
Twenty separators became eighteen headings. The discriminator is the
COUNT of YAML blocks, not their presence: a markdown document with
frontmatter has exactly one (its own opener), a YAML stream has many.
A `---` inside a fenced code block does not count — the fleet's
templates show frontmatter inside a fence, and without the fence rule
twelve ordinary documents would be excluded for no reason. Measured
over the fleet's 1038 tracked documents: exactly one multi-document
YAML file, and zero false positives.

**A GFM table.** mdformat 1.0.0 has no table support. Its own safety
net — `mdformat._util.is_md_equal` — renders both sides of a
comparison with mdformat's parser, which sees a table as a paragraph.
So the check cannot see damage to a table, because it cannot parse what
changed. Three documents in mahavishnu were silently corrupted this
way:

| document | what mdformat did |
|---|---|
| `docs/cookbook/workflows.md` | merged three table rows into one paragraph line, dropping the row separators |
| `docs/plans/2026-11-20-fleet-memory-retrieval-quality.md` | re-indented a table out of the list item that held it, so literal text became a real table |
| `docs/specs/2026-10-19-bodai-substrate-otel-v7.md` | destroyed table rows |

The trigger in the first case is instructive: the cell contains
backslash-escaped backticks inside a code span, and CommonMark does not
treat backslashes as escapes inside a code span — so the code span ran
past the row boundary and swallowed the following rows' pipes as code
content.

The fix is to ask the question mdformat's check does not ask. Instead
of "did the parse tree change?", the wrapper compares each file's GFM
rendering before and after, using a table-aware renderer, and restores
any file that reads differently. The comparison is exact rather than
heuristic: on crackerjack's 287-file corpus zero files change their
rendering, and the three documents above are the only ones it flags in
mahavishnu.

**mdformat aborts the whole batch at the first file it cannot
format.** A document whose formatted output renders to different HTML
than the input is refused, and the refusal stops every file after it
in the same invocation. The tree is left half-formatted, and the
formatter reports the same failure on every subsequent run, so the gate
never converges — which is exactly what happened here: one file in
mahavishnu (`docs/GETTING_STARTED.md`, whose emphasis is ambiguous)
kept the whole 521-file batch from formatting. The batch is now run
iteratively: the refused file is named in mdformat's own error
message, dropped from the set, and the batch re-run. The refusal is
reported, because an excluded document is one nobody notices.

**The argv path, which the two new guards do not cover.** §2.8 records
that the wrapper passes `argv` straight through to mdformat, so a file
handed to it on the command line bypasses `should_skip_file` entirely.
The BOM and multi-document-YAML guards added by this plan live *inside*
that bypassed function, so they do not hold there. Demonstrated against
the real `mahavishnu/mahavishnu/commands/jot.md`: passed via argv, the
YAML stream was corrupted — its `---` separators and keys replaced by
`## description: …` headings — while the wrapper simultaneously printed
`excluded (multi-document YAML): jot.md`. The control run, the same file
through the tracked set, excluded it correctly and preserved the bytes.
The GFM-table restore, by contrast, holds on both paths.

That is a guard reporting success on a path it does not run, which is
worse than no guard: it converts a corruption into a false all-clear. The
argv path is not reachable from `crackerjack run` today —
`use_incremental` defaults to `False` and the only production
construction site does not set it — and it becomes live the moment any
caller passes changed files to `build_command`. **This is an open
defect. The plan does not fix it, and §2.9's "the wrapper now handles
them" does not extend to it.**

### 2.10 The front-matter extension is required per repository, and the wrapper fails closed

mdformat 1.0.0 core has no frontmatter support: given a document whose
first line is `---` it rewrites the fence into a horizontal rule and
flattens the YAML into body text. The `mdformat-frontmatter` plugin is
what prevents that, and the plugin lives in a *venv*, not in crackerjack's
source.

The wrapper therefore probes the interpreter that will actually run
mdformat — the repository's own `.venv/bin/mdformat` when there is one —
and counts the registered front-matter renderers. Zero means the
frontmatter would be destroyed, so the wrapper refuses to format and
says why. Two means two front-matter packages are installed side by side
under different entry-point names, one of which strips quotes and turns
a quoted `"yes"` into a YAML 1.1 boolean; that is refused too.

Measured today: all six repositories carry mdformat 1.0.0, and only
crackerjack's venv has a front-matter extension registered. The other
five run an *older* crackerjack, whose wrapper skips frontmatter
documents outright, so nothing is at risk in them today. The change
arrives with the published release, which carries `mdformat-frontmatter`
as a hard dependency — the plugin and the code that needs it land in
the same install, which is what keeps the guard from refusing.

## 3. Phases

### Phase 1 — the wrapper change: `--number`, then lift the skip

#### Scope

- `crackerjack/tools/mdformat_wrapper.py`
  - `_build_mdformat_cmd` — add `--number` to the command.
  - `should_skip_file` — remove the `stripped == "---"` clause; keep
    the underscore clause.
- `tests/unit/tools/test_mdformat_wrapper.py`
  - `test_skip_frontmatter_documents` — replace with an assertion that
    a frontmatter document is now NOT skipped.
  - `test_build_cmd_does_not_pass_an_extensions_flag` — extend to
    assert `--number` IS passed.
  - `test_main_proceeds_when_the_extension_is_installed` — the
    frontmatter document is now in scope, so the guard's "in scope"
    path is exercised for real.

#### Integration Contract

- **Triggered from**: `python -m crackerjack.tools.mdformat_wrapper`,
  invoked by the `mdformat` hook in `crackerjack/config/hooks.py`.
- **Returns to / updates**: the markdown files of the repository the
  hook runs in. Nothing else mutates.
- **Demonstrable by**: `pytest tests/unit/tools/test_mdformat_wrapper.py --no-cov`
  passes, and `python -m crackerjack.tools.mdformat_wrapper` exits 0
  with a clean tree afterwards. The `--no-cov` is required — the
  repository's `addopts` carry `--cov-fail-under=75.0`, so a single-file
  run exits 1 on the coverage floor even when every test passes.
- **Rollback signal**: the hook exits 1 with `files were modified by this hook` on a second consecutive run, which means the formatter is
  not idempotent over the tree.
- **Observability added**: the hook's existing stderr surface now
  reports the files it reformatted, including frontmatter documents
  that were previously invisible to it.

#### Resolved decisions

1. **Add `--number` before lifting the skip, in the same commit.**
   Two reasons. The ordering avoids a churn round-trip: lifting first
   would collapse numbering across 783 documents and a later commit
   would only partly restore it. And the two changes are one behaviour
   ("format the fleet's documents without changing what they say"),
   which is one commit's worth of intent.
2. **Do not pass `--extensions`.** Naming an extension restricts the
   enabled set (§2.5). The default enables everything installed.
3. **Keep the guard from `78b3c8ca` unchanged.** It now guards the
   in-scope path as well as the tracked path, and it is what makes
   Phase 2 safe to run unattended.
4. **Do not adopt the plural plugin for its strict mode.** The schema
   validator already gates conformance, and re-serializing frontmatter
   is the worse trade (§2.2).

#### Risks

1. **The lint hook and the format hook disagree.** `ruff format` and
   `mdformat` both touch the tree. Run the format hook first, then the
   lint hook, and confirm a second run of each is a no-op.
2. **`--number` changes files that are already in scope today.**
   Documents already formatted under the default have all-`1.` lists;
   adding `--number` restores their real numbering. That is a content
   change to already-committed documents, in the direction of
   correctness, and it will show up in this phase's diff.
3. **A decision record's numbering is itself the record.** Restoring
   `2.` where the file said `2.` is a fix. Restoring it where the file
   deliberately said `1.` because a previous format pass collapsed it
   is a change to history. Phase 1's diff must be read for this, not
   skimmed. Measured: the collapsed shape dominates the fleet and is
   unambiguously repair (§2.7), and exactly three documents fleet-wide
   have a genuine hole, none of which names a list item by number.

#### Estimated scope

One module (about 15 lines changed), one test module (about 30 lines
changed), one new test asserting a frontmatter document is in scope.

### Phase 2 — the fleet-wide formatting rollout

#### Scope

Six repositories, one commit each, in this order: crackerjack first
(it owns the hook), then mahavishnu, oneiric, akosha, session-buddy,
mcp-common.

Per repository:

- **Publish first, then sync.** The plugin arrives with a *published*
  crackerjack release, not with a local edit. The latest release on PyPI
  at the time of writing is 0.96.0, published 2026-11-17; the three lift
  commits are dated 2026-11-20, so **no published release carries the
  lift yet**, and `uv sync --all-groups` against an unchanged lockfile
  moves nothing — `uv sync --all-groups --dry-run` reports "no changes"
  and `uv lock --dry-run --upgrade-package crackerjack` reports "no
  lockfile changes detected". The operator publishes the release first;
  until then the sync step is a no-op and the hook's guard correctly
  fails loud.
- Sync the venv: `uv sync --all-groups`. The plugin arrives with the
  crackerjack dependency bump, and the hook's guard fails loud until
  it is there. The guard naming the fix is the intended behaviour, not
  a problem to route around.
- Run the format hook: `python -m crackerjack.tools.mdformat_wrapper`
  from the repository root, using that repository's own venv.
- Re-run the frontmatter semantic check (§2.3) over the live
  documents and require `semantic differences: 0` and `errors: 0`.
- **Regenerate the plan index with that repository's own renderer**:
  `python scripts/regenerate_plan_index.py`. Every one of the six
  repositories ships this script, and each one reproduces its own
  committed `PLAN_INDEX.md` byte-for-byte. Do **not** use crackerjack's
  `plan_index_sync` tool here: it renders the simple shape, and against
  mahavishnu it would rewrite `docs/plans/PLAN_INDEX.md` from 95,120 B /
  470 table rows / 31 headers down to 28.0 KB / 138 rows, dropping the
  Status Legend, the Authority Matrix, the Review Entry Points, the
  per-store registries and the By Kind section. The instruction this
  replaces was backwards: it named `plan_index_sync` as the sanctioned
  renderer and forbade mahavishnu's own script, which is the one that
  reproduces the rich shape.
- Confirm the plan-index audit reports no frontmatter'd file missing
  from `PLAN_INDEX.md`. Only mahavishnu ships such an audit
  (`scripts/audit_plan_index.py`); in the other five repositories,
  confirm instead that a second regeneration reports no change.
- Confirm `git diff --name-only` lists only `.md` and `.markdown`.
- Confirm the hook's stderr names no excluded document. A byte-order
  mark before a frontmatter fence, a second front-matter extension in
  the venv, a document that is a stream of YAML rather than markdown,
  and a document whose GFM rendering mdformat would change all make
  the hook report something, and all are conditions to fix rather than
  to commit past. The last two are conditions the rollout *expects* to
  meet: a document is excluded, restored to its original bytes, and
  reported — it is not silently reformatted.
- Confirm the hook's stderr names no document it *restored*. A restored
  document is one the formatter would have damaged; it is left as it
  was and reported (§2.9).
- Commit.

#### Integration Contract

- **Triggered from**: the `mdformat` hook, run per repository.
- **Returns to / updates**: the markdown documents of that repository,
  and its `docs/plans/PLAN_INDEX.md`.
- **Demonstrable by**: `git diff --name-only` in each repository lists
  only markdown; the plan index reports zero missing files (in
  mahavishnu, via its `scripts/audit_plan_index.py`; elsewhere, by a
  second regeneration reporting no change); a second hook run in each
  repository is a no-op; the hook's stderr names no excluded document.
- **Rollback signal**: any repository whose second hook run still
  reports changes. The formatter is not idempotent over that tree, and
  the commit must not land until it is.
- **Observability added**: each repository's `PLAN_INDEX.md` reflects
  the formatted tree, and the hook's stderr names every file it
  touched.

#### Resolved decisions

1. **One commit per repository.** A fleet-wide formatting change that
   cannot be reverted repository-by-repository is not revertible in
   practice.
2. **crackerjack goes first.** It owns the hook and the plugin
   declaration; every other repository's venv picks the plugin up from
   the same dependency.
3. **The plan index is regenerated in the same commit as the
   formatting.** A stale index and a formatted tree in separate commits
   leave a window where the index does not describe the tree.

#### Risks

1. **A repository's venv predates the plugin.** The plugin arrives with
   the next `uv sync` of the dependency bump. If a repository's venv is
   stale, the guard fires and the hook exits 1 with the fix named.
   That is the guard working, not a failure to route around.
2. **The diff is large and mechanical.** 783 documents is a review
   burden. The review that matters is the sampled one: confirm that
   every changed hunk is a known mdformat normalization and that no
   frontmatter value changed.
3. **A document that only *looks* like frontmatter.** A file whose
   first line is `---` but which is not a YAML block would be handed to
   mdformat for the first time. The plugin's own README warns that
   incorrectly formed blocks may behave strangely. The semantic check
   catches the case where the result stops parsing.
4. **A document mdformat would damage.** The frontmatter guard proves
   the frontmatter survives; it says nothing about the body. A GFM
   table is the case that bit: mdformat has no table support and its
   own check cannot see the damage (§2.9). The wrapper now compares the
   GFM rendering before and after and restores anything that reads
   differently, so a damaged document is reported and left alone
   rather than committed.
5. **A document mdformat refuses.** mdformat aborts the whole batch at
   the first refusal, so one unformattable file can stop a repository
   from being formatted at all — and the gate never converges, because
   the same refusal recurs on every run. The batch is now iterative
   (§2.9) and the refusal is reported.

#### Estimated scope

976 live documents across six repositories change under `--number`
(§2.6), plus six regenerated plan indexes. The changes are almost all
indentation, table padding and list-marker width. Two of the six
repositories carry most of it: mahavishnu (430 files) and crackerjack
(236).

## 4. Risks

1. **Ordering against other plans.** The fleet-standardisation spine
   (`mahavishnu/docs/plans/2026-11-19-fleet-standardisation.md`) and
   the retrieval-quality plan
   (`mahavishnu/docs/plans/2026-11-20-fleet-memory-retrieval-quality.md`)
   both add markdown files to the same trees. Formatting a tree that
   another session is editing produces conflicts. Phase 2's per-repo
   commits should land when the tree is quiet, and the operator's
   staged work is never swept in.
2. **The plan file itself is in the churn set.** A plan written before
   the rollout is formatted by the rollout. That is expected; the
   plan-index regeneration in the same commit absorbs it.
3. **A behaviour change with no rollback story.** `--number` changes
   how every future format run renders ordered lists. It is revertible
   by removing the flag, but the documents it has already rewritten
   keep their restored numbering. The direction is correct, so the
   asymmetry is acceptable; it should be stated rather than discovered.
4. **The gotcha memories become stale.** The fleet's memories
   `m#1746` ("plan files are intentionally left outside mdformat
   cleanup"), `m#2031` and `m#2001` describe the pre-lift state.
   `m#10092` already supersedes `m#1746` with the plugin decision;
   the other two should be revisited when this plan ships, because the
   behaviour they describe is what this plan changes.

## 5. References

- `78b3c8ca` — Step one: the plugin declaration and the fail-loud
  guard.
- `crackerjack/tools/mdformat_wrapper.py` — `should_skip_file`, where
  this plan lifts the `stripped == "---"` exclusion. The line number 43
  was correct when the plan was written (pre-`e9448967`) and has since
  aged: line 43 now falls inside `_is_multi_document_yaml`.
- `crackerjack/docs/plans/TEMPLATE.md` — this plan's template.
- `oneiric/oneiric/schemas/topic-vocabulary-v1.md` — the `topic:`
  vocabulary.
- `docs/plans/2026-11-19-fleet-standardisation.md` (mahavishnu) — the
  fleet spine; unrelated to formatting but edits the same trees.
- `docs/plans/2026-11-20-fleet-memory-retrieval-quality.md`
  (mahavishnu) — the retrieval plan; unrelated to formatting but edits
  the same trees.
- mdformat 1.0.0 documentation, "Plugins" — the extension table and
  the `--extensions` restriction.
- `mdformat-frontmatter` 2.2.0 (butler54) and
  `mdformat-front-matters` 2.0.0 (KyleKing) — the two packages, and
  the reason one was chosen.

## 6. Execution record

_(To be filled in as the phases execute. Each phase records the commit SHA,
the baseline captured before it, the deltas it produced, and any decision
taken that the plan left open. The closing entry names the findings that
turned up during execution that the plan did not anticipate.)_

### Phase 1 — the wrapper change

**Commits:**

- `e9448967` — `fix(format): format frontmatter documents and preserve list numbering` — the lift itself
- `7556b402` — `fix(format): close three holes the frontmatter lift left open` — the review findings below

**Baseline:** `c8bd7d4c`
**Changed:** `crackerjack/tools/mdformat_wrapper.py`,
`crackerjack/services/doc_categorizer.py` (docstring only),
`tests/unit/tools/test_mdformat_wrapper.py`,
`tests/tools/test_mdformat_wrapper.py`.

**What was measured, before the change was made:**

- `--number` exists in mdformat 1.0.0 and is a top-level CLI flag, not
  an extension. Verified against the binary in this repo's venv.
- Its behaviour, on a scratch fixture in both modes: `3. 4.` becomes
  `3. 1.` under the default and stays `3. 4.` under `--number`; a
  nested `1. 2.` becomes `1. 1.` under the default and stays under
  `--number`.
- The safety property, over the 307 tracked frontmatter'd documents in
  this repo, using the wrapper's exact command line on scratch copies:
  **zero** semantic differences in the parsed YAML, **zero**
  frontmatter blocks vanished, **zero** YAML parse errors caused by the
  change, and every one of the **277** text-only differences is the
  identical rewrite `superseded_by: null` → `superseded_by:`, which
  parses to the same `None`.
- The shape of every ordered list in all six repositories, classified by
  what `--number` does to it — §2.7.
- The guard's precondition, on the real tree rather than in a fixture:
  the plugin is present in the environment that will run mdformat
  (`.venv/bin/mdformat`, `mdformat_frontmatter 2.2.0`), so the guard
  does not fire — and it is live rather than vacuous, because 180
  tracked frontmatter'd documents exist here and 172 of them are now
  in scope.
- That every tracked `.md` and `.markdown` file in all six
  repositories whose first line is `---` also has a closing `---`
  fence: there is no frontmatter lookalike anywhere in the fleet
  (§2.3).

**What the plan did not anticipate:**

1. **Failure Condition 5 was unsatisfiable as written.** It required
   "no hunk whose only change is an ordered-list marker", but
   `--number` renders consecutive numbering, so it *repairs* the 3366
   collapsed lists fleet-wide and those repairs are marker-only hunks.
   The condition now says what its own parenthetical meant: no marker
   is decreased, compared numerically, with an explicit exception for
   the documents of §2.7.
2. **`--number` zero-pads a list that would number past 9** (`1.` →
   `01.`). The trigger is the item count plus the starting number, *not*
   the largest marker: a ten-item list whose source markers are all `1.`
   renders `01. … 10.`. Measured over every tracked markdown in the six
   repositories, **1,027 zero-padded markers across 99 files**, over 610
   lists of 4,137 ordered lists — against the 179 this record originally
   claimed, which was taken over a narrower, live-only corpus.
   CommonMark renders the list as `1.` through `13.` either way, so the
   leading zero is a source-text artefact and not a rendered one.
3. **The `[N, 1, 1, …]` shape looks like a hazard and is not.** The
   first marker is kept and the rest are numbered consecutively from it,
   so a reference to "item N" still lands on the same item. 53 lists
   fleet-wide.
4. **Exactly three documents in the fleet have a genuine hole in a list**,
   and none of them names a list item by number in its prose. A fourth
   candidate is a false positive of a different kind —
   `mahavishnu/docs/plans/2026-10-29-bifrost-bodai-cache-wiring.md`
   carries `1. 2. 1.`, which `--number` *raises* to `1. 2. 3.`, so it is
   an increase rather than a hole. (An earlier census also counted
   `oneiric/docs/implementation/PACKAGE7_SUMMARY.md` (`1. 5.`), a
   numbered sequence written inline inside a fenced code block, which
   mdformat does not touch.) §2.7.
5. **One tracked document has invalid YAML frontmatter already**:
   `crackerjack/mcp/agents/crackerjack-specialist.md`, whose unquoted
   `description` contains a bare colon, so PyYAML rejects it. This
   change neither causes nor worsens it — the block comes back with the
   same text, and mdformat preserves it and warns. Left alone as out of
   scope; it is an authoring problem, not a formatter problem. (The
   warning it produces was invisible until `7556b402`: see finding 8.)
6. **`doc_categorizer` documented itself as mirroring this module's
   `---` rule**, and that claim became false when the skip was lifted.
   The docstring is corrected; the behaviour is deliberately unchanged.
7. **"Preserves the frontmatter byte-for-byte" was false.** The plugin
   re-serialises the block through a ruamel round-trip with
   `preserve_quotes=True`, so the parsed values are unchanged but the
   text is not — and the plan's own measurement (277 text-only
   differences, all of them `null` → empty) is what disproved the
   wording. Corrected in §2.2, in the wrapper's comments and in the test
   docstrings.

**What a fresh review of the lift found, and `7556b402` fixed:**

08. **A BOM'd frontmatter document was destroyed.** The plugin's
    front-matter rule is BOM-blind, and a byte-order mark is not
    whitespace, so every `---` test in the wrapper missed it. Formatting
    such a document flattened its frontmatter into a heading, and the
    document then dropped out of `PLAN_INDEX.md` — the exact failure the
    guard exists to prevent. Such documents are now excluded from
    formatting and reported, because an excluded document is one nobody
    notices. No tracked document in the fleet has one today.
09. **A second front-matter extension was invisible.** The two packages
    register under different entry-point names (`frontmatter` and
    `front_matters`), so pip installs both side by side; mdformat then
    logs a plugin conflict, keeps one renderer, and the disagreement
    about quotes becomes a silent semantic change. The probe now counts
    front-matter extensions, and the guard refuses to run unless there is
    exactly one.
10. **mdformat's own diagnostics were swallowed.** The wrapper
    discarded `check_result.stderr` entirely when the check passed, so a
    front-matter block mdformat could not parse — or a plugin conflict —
    was invisible. They are surfaced now, prefixed with the success
    marker so they reach the operator without being counted as issues.

**A correction to an earlier note in this record.** An earlier draft
claimed that this plan file is itself one of the damaged documents, its
§2.4 example list being `[3, 1]` in the source. That was wrong: the
`[3, 1]` is inside a fenced code block — it is the illustration of the
default-mode output — and the plan's actual body lists are consecutive.
Running the wrapper's exact command line over the plan changes only
`superseded_by: null` → `superseded_by:`, three continuation-line
joins and a trailing blank line. No list marker in this file changes.
The measurement that produced the wrong claim counted fenced code
blocks.

**Counting note.** §2.1 lists 306 frontmatter'd documents for
crackerjack; the measurement over the tracked set finds **307** files
whose first line is `---`. The difference is
`crackerjack/mcp/agents/crackerjack-specialist.md`, whose frontmatter is
not valid YAML and so is not counted by a parser-based scan. Both
numbers are right about different things.

**Phase 2 was not executed as part of Phase 1.** The wrapper now
formats crackerjack's own frontmatter'd documents on its next run —
172 of them are newly in scope — and 287 files are in the wrapper's
set. That churn, plus the regenerated plan index, is Phase 2's
crackerjack commit, and it is deliberately not folded into Phase 1's
commits. See §6, "Phase 2 — the fleet-wide formatting rollout", for
what the rollout actually did.

### Phase 2 — the fleet-wide formatting rollout

All six repositories are done. The table at the end of this section has
the per-repository figures.

**crackerjack — 221 files.** 163 frontmatter documents checked, 0
semantic differences, 0 frontmatter blocks vanished, 0 YAML parse
errors, 0 files changed outside markdown. The frontmatter round-trip's
one rewrite — `superseded_by: null` → `superseded_by:` — appears 147
times; both parse to None. Two ordered lists lose a marker, both the
same shape: an item deleted at some point leaving a hole that
`--number` closes.

**mahavishnu — 403 files.** 247 frontmatter documents checked, 0
semantic differences, 0 frontmatter blocks vanished, 0 YAML parse
errors, 0 files changed outside markdown. The same
`superseded_by: null` rewrite appears 163 times. One ordered list loses
a marker: `docs/decisions/2026-10-15-unified-event-bus-wrapper.md`,
whose markers run `1. 3. 4. 5.` — item 2 was deleted, and the only
numbered references in the document are to "Phase 6.4", not to list
items. The plan index was regenerated and reports "no change"; it is
format-clean.

**Three documents in mahavishnu were left unformatted on purpose**,
because mdformat would have damaged them (§2.9). The wrapper restores
them to their original bytes and reports them by name:

- `docs/cookbook/workflows.md`
- `docs/plans/2026-11-20-fleet-memory-retrieval-quality.md`
- `docs/specs/2026-10-19-bodai-substrate-otel-v7.md`

**One document is excluded** because it is not markdown:
`mahavishnu/commands/jot.md`, a stream of YAML documents.

**One line was edited by hand.** `docs/GETTING_STARTED.md` was
unformattable — mdformat refuses a document whose formatted output
renders to different HTML, and that line's emphasis is ambiguous
(`**~~Workflow Diagrams~~ *(…)* **`). The emphasis was restructured to
be unambiguous: `**~~Workflow Diagrams~~** ***(…)***`. It keeps both
the bold title and the bold-italic removal note; only the nesting
boundary moves. This is the only prose change in the repository's
rollout.

**The rollout converges.** A second run of the wrapper reports no
changes and exits 0.

#### The findings that changed the wrapper

Running the rollout found three hazards the plan did not anticipate
(§2.9). Each was fixed in crackerjack `10341d2a` and the rollout was
re-run from the restored state:

1. A `.md` file that is a stream of YAML documents was destroyed. The
   skip rule now excludes it.
2. Three documents with GFM tables were silently corrupted. The
   wrapper now compares the GFM rendering before and after and
   restores anything that reads differently.
3. mdformat aborts the whole batch at the first file it refuses, so
   one unformattable file stopped a 521-file repository from being
   formatted at all — and the gate never converged, because the same
   refusal recurred on every run. The batch is now iterative.

#### Still to do

The rollout itself is done. Two operator-side steps remain, and neither
is this plan's to take:

1. **Publish the crackerjack release that carries `mdformat-frontmatter`.**
   The five non-crackerjack repositories run an older crackerjack whose
   wrapper skips frontmatter documents outright, and their venvs have no
   front-matter extension registered at all (measured 2026-11-20 — §2.10).
   Until the release lands and each repository syncs, their hooks keep
   skipping frontmatter and their markdown stays as the pre-lift state.
   The rollout's commits are already formatted, so nothing is lost by the
   wait; the hooks simply do not become live until it happens. All five
   pins are `>=` floors well below the current version, so no pin blocks
   the release.
   **The publish is still outstanding (re-measured 2026-11-21).** The
   latest release on PyPI is 0.96.0, published 2026-11-17; the three lift
   commits are dated 2026-11-20. No published release carries the lift,
   and `uv sync --all-groups` against the current lockfiles reports no
   changes — so the fleet-wide effect of this plan cannot begin until the
   release lands. `mdformat-frontmatter` 2.2.0 is installed in
   crackerjack's venv only; mahavishnu, oneiric, akosha and session-buddy
   each report `mdformat 1.0.0` with the extension absent.
2. **Push the commits.** Every repository's formatting commit is local
   only.

Re-verified 2026-11-20, after the plan's own corrections: mdformat
(`--no-codeformatters --number`) over each repository's in-scope
documents reports **1031 of 1038 format-clean**, and the seven that are
not are exactly the seven named below — nothing else regressed.

| repository | commit | files | frontmatter checked | semantic differences | blocks vanished | parse errors | non-markdown |
|---|---|---|---|---|---|---|---|
| crackerjack | `5bf0c8a9` | 221 | 163 | 0 | 0 | 0 | 0 |
| mahavishnu | `823eacf7` | 403 | 247 | 0 | 0 | 0 | 0 |
| oneiric | `868596c` | 81 | 71 | 0 | 0 | 0 | 0 |
| session-buddy | `b54db6f0` | 32 | 18 | 0 | 0 | 0 | 0 |
| akosha | `bfa0267` | 32 | 22 | 0 | 0 | 0 | 0 |
| mcp-common | `b5d16f3` | 8 | 2 | 0 | 0 | 0 | 0 |

Every repository reports `ordered-list markers decreased: 0` except
crackerjack's two and mahavishnu's one, which are the genuine holes of
§2.7 — the accepted repair, named.

`PLAN_INDEX.md` appears in the rollout commit of **two** repositories
(session-buddy and akosha). The other four regenerated their index and
got byte-identical output, so the file did not appear in the commit —
resolved decision 3 was honoured in all six, and four of them simply had
nothing to change. (Verified per repository against the rollout commit
SHAs above.)

#### What is deliberately not formatted

Seven documents across the fleet are left as they were, and the hook
says so by name on every run:

| repository | document | why |
|---|---|---|
| mahavishnu | `docs/cookbook/workflows.md` | mdformat damages it (§2.9) |
| mahavishnu | `docs/plans/2026-11-20-fleet-memory-retrieval-quality.md` | mdformat damages it (§2.9) |
| mahavishnu | `docs/specs/2026-10-19-bodai-substrate-otel-v7.md` | mdformat damages it (§2.9) |
| session-buddy | `docs/specs/2026-11-05-conversation-transcript-ingestion-design.md` | mdformat damages it (§2.9) |
| mahavishnu | `mahavishnu/commands/jot.md` | a stream of YAML, not markdown (§2.9) |
| oneiric | `docs/plans/2026-08-22-hybrid-embeddings-design.md` | another session's uncommitted work |
| session-buddy | `docs/plans/2026-11-06-fleet-embedding-width-768.md` | another session's uncommitted work |

The last two were snapshotted before their repository's rollout and
restored byte-for-byte after it, so the other session's working tree is
exactly what it was. The hook will report them on every run until their
owner commits; that is the exclusion being visible, not a failure.

Two further files are not formatted because crackerjack's own
`.mdformat.toml` exclude list covers them
(`exclude = ["commands/*.md", "templates/*.md"]`).

**Correction (2026-11-21):** this paragraph was wrong twice, and both
errors would mislead an operator. mdformat 1.0.0 **never reads
`pyproject.toml`** — the installed package contains no reference to it
whatsoever; it reads only `.mdformat.toml` (`mdformat/_conf.py:36-47`).
So `[tool.mdformat]` in `pyproject.toml`, which lists `templates/*.md`
and `CLAUDE*.md`, is a list mdformat never sees. The rollout bears this
out: `docs/guides/CLAUDE.md` **was** reformatted despite `CLAUDE*.md`
sitting in `pyproject.toml`, while `.claude/commands/` and
`templates/*.md` were untouched — exactly matching `.mdformat.toml`.
Second, the resolution root is **not** the file's own directory: mdformat
resolves the patterns relative to the `.mdformat.toml`'s parent
(`mdformat/_cli.py:359-378`). Tested against a temporary root,
`templates/x.md` is excluded while `docs/templates/y.md` is **not**.
The corrected statement: those paths are excluded relative to the
directory holding `.mdformat.toml`, not wherever they are copied to.

#### How the rollout was run

With crackerjack's own `mdformat` binary (which carries the
front-matter plugin) against the target repository's tracked markdown,
because the plugin arrives in the other repositories' venvs only with a
crackerjack release the operator publishes. Nothing in a target
repository is modified except its markdown, and no target venv is
touched.

#### Convergence

A second run of the hook in each repository reports no changes. The
files listed above are reported by name; they are excluded and
restored, not silently reformatted.

## 7. Post-execution review (2026-11-21)

A review of this document against the tree, after both phases executed,
found nine defects in the plan itself. Two of them are instructions that
would damage state if an operator followed them literally. The
corrections are applied in place above; this section is the index of
them.

| # | was | now | where |
|---|---|---|---|
| 1 | `status: draft` | `status: partial` — both phases executed, effect not yet distributed | frontmatter, §1 |
| 2 | FC1: `rg 'stripped == "---"'` returns nothing | returns two matches — the guarded BOM and multi-doc-YAML checks this plan's own later commits added | §1 FC1 |
| 3 | FC7: `pytest …test_mdformat_wrapper.py` passes | exits 1 on `--cov-fail-under=75.0`; needs `--no-cov` | §1 FC7, Phase 1 |
| 4 | FC3, FC5, FC6 named checks that do not exist | FC3 is an operator measurement, not a script; FC5's exception now names its three documents; FC6 scoped to mahavishnu, the only repo with an index audit | §1 |
| 5 | zero-padding trigger read as "the largest marker in the list" | it is the item count plus the starting number — a ten-item list of all `1.` renders `01. … 10.` | §2.4, §6 finding 2 |
| 6 | 179 affected lists | 1,027 zero-padded markers across 99 files, over 610 lists of 4,137 — a narrower corpus than the earlier figure | §2.4, §6 finding 2 |
| 7 | four genuine holes, "three documents" in the prose | three — the bifrost document is an *increase* (`1. 2. 1.` → `1. 2. 3.`), not a hole | §2.7, §6 finding 4 |
| 8 | the argv bypass is "unchanged by this plan" | the plan's own BOM and multi-doc-YAML guards live inside the bypassed function and do not hold there — an open defect | §2.8, §2.9 |
| 9 | Phase 2: `uv sync --all-groups` delivers the lift; use `plan_index_sync`, never mahavishnu's own script | no published release carries the lift yet (0.96.0 is 2026-11-17; the lift is 2026-11-20), so the sync is a no-op — and the index instruction was backwards: `plan_index_sync` would cut mahavishnu's index from 95,120 B / 470 rows / 31 headers to 28.0 KB / 138 rows | Phase 2 |
| 10 | `[tool.mdformat]` in `pyproject.toml` excludes `templates/*.md` and `CLAUDE*.md`; mdformat resolves it from the file's own directory | mdformat 1.0.0 never reads `pyproject.toml` — it reads `.mdformat.toml`, and resolves relative to that file's parent | §6 |
| 11 | Phase 1's test path `crackerjack/tests/unit/tools/test_mdformat_wrapper.py` | `tests/unit/tools/test_mdformat_wrapper.py` — the tests live at the repository root | Phase 1 |
| 12 | `crackerjack/tools/mdformat_wrapper.py:43` | line 43 now falls inside `_is_multi_document_yaml`; the citation aged | §5 |

The three counts that appear across the document are reconciled in §2.6.

**What the review did not change.** The plan's diagnosis holds: mdformat's
default really does collapse ordered lists, and `--number` really is a
prerequisite for the lift. The rollout really did produce zero semantic
frontmatter differences in every repository, and the seven documents the
hook refuses are the seven the plan names. The two dangerous instructions
were the only findings that would have cost something if followed.
