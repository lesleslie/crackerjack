---
title: Lift the mdformat frontmatter skip and protect numbered lists
description: "The mdformat hook keeps every YAML-frontmatter document out of formatting, which leaves 783 documents across the six fleet repos unformatted. The mdformat-frontmatter plugin, installed by 78b3c8ca, makes it safe to lift that exclusion -- but only once the hook also stops renumbering ordered lists, because mdformat's default collapses `1. 2. 3.` to `1. 1. 1.` and that destroys cross-references inside decision records and plans. This plan adds `--number` first, lifts the skip second, and rolls the resulting formatting churn across the fleet one repository at a time."
audience: crackerjack maintainer
created: 2026-11-20
status: draft
role: implementation
topic: process-discipline
date: 2026-11-20
last_reviewed: 2026-11-20
superseded_by: null
blocks_on: []
---

# Lift the mdformat frontmatter skip and protect numbered lists

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps
> use checkbox (`- [ ]`) syntax for tracking.

## 1. Brief (intent-driven)

### Goal

783 YAML-frontmatter documents across the six fleet repositories are
formatted for the first time, and no document loses meaning in the
process.

Today `should_skip_file` excludes every document whose first line is
`---`, so those files never reach mdformat at all: their bodies keep
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
  mdformat. This plan does not re-declare the dependency and does not
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

1. `rg -n 'stripped == "---"' crackerjack/tools/mdformat_wrapper.py`
   returns nothing.
2. `rg -n '\-\-number' crackerjack/tools/mdformat_wrapper.py` returns
   a match.
3. For each of the six repositories: the frontmatter semantic check
   (§2.3) reports `semantic differences: 0` and `errors: 0`.
4. For each of the six repositories: `git diff --name-only` contains no
   file with an extension other than `.md` or `.markdown`.
5. For each of the six repositories: no ordered-list marker is
   *decreased* by the diff. Every marker that changes increases or
   stays the same. This is what "source numbering is preserved" has to
   mean in practice, and it is the property that protects a reference
   like "item 4": no marker ever decreases, so `2.` never becomes `1.`
   and the item a reader was pointed at is still the item they find.
   (A marker-only hunk is not a failure. `--number` renders consecutive
   numbering, so a list whose markers were collapsed to `1. 1. 1.` by an
   earlier default-mode pass is *repaired* to `1. 2. 3.` — see §2.4 and
   §2.7.)
6. For each of the six repositories: the plan-index audit reports zero
   frontmatter'd files missing from `PLAN_INDEX.md`.
7. `pytest tests/unit/tools/test_mdformat_wrapper.py` passes.

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
| frontmatter on a hostile fixture | byte-for-byte preserved | re-serialized, quotes stripped |
| `"yes"` | stays the string `yes` | becomes bare `yes`, which YAML 1.1 parses as the boolean `True` |
| formats | YAML only | YAML, TOML, JSON |
| extra CLI | none | `--strict-front-matter`, `--sort-front-matter` |

The plural package's strict mode would fail loudly on *malformed*
frontmatter, which the fleet's schema validator already covers. It was
not chosen because re-serializing the YAML is the worse trade for
frontmatter that machine readers parse.

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

One risk deserves its own measurement, because lifting the skip hands
mdformat a document it has never seen before: a file whose first line
is `---` but which is not a YAML block. Measured across all six
repositories, **every** tracked `.md` and `.markdown` file whose first
line is `---` also has a closing `---` fence — there is no lookalike
document anywhere in the fleet. Where one did exist, the plugin
degrades it safely: on a `---\n\n# heading` fixture it renders the
`---` as an underscore horizontal rule and exits 0, which is what the
`---` meant anyway (a thematic break).

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

- **A collapsed list is repaired, not preserved.** 5545 of the fleet's
  7897 ordered lists carry the `1. 1. 1.` signature of an earlier
  default-mode format pass. `--number` turns them back into
  consecutive numbering. That is a content change to
  already-committed documents, in the direction of correctness, and it
  is the larger part of the churn.
- **A list of ten or more items is rendered zero-padded.** `1. 2. …
  13.` becomes `01. 02. … 13.`. 98 lists in the fleet are long enough
  to be affected. CommonMark renders the list as `1.` through `13.`
  regardless — the leading zero is a source-text artefact, not a
  rendered one.

**`--number` is therefore a prerequisite for the lift, not an
afterthought.** Lifting the skip first would collapse the numbering in
783 documents and a later commit would only partially restore it.

Two further body effects were observed and accepted as style-only:

- **151 double-backtick code spans become single-backtick.** In
  CommonMark both render as a code span with identical content, so the
  rendered document is unchanged. It is a source-text change to decision
  records, which the operator may want to know about.
- **221 table reformats** (column padding). Purely visual.

### 2.5 The `--extensions` flag must not be used

mdformat's `--extensions` flag *requires* and *enables* named
extensions, and naming one **restricts** the enabled set to just that
one. Verified against mdformat-gfm: with `--extensions frontmatter`,
the `tables` extension stopped formatting tables. The CLI enables every
installed extension by default, so the wrapper names none, and the
frontmatter extension is verified separately by the probe added in
`78b3c8ca`.

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
| **collapsed** | `1. 1. 1.` | repairs to `1. 2. 3.` | 5545 |
| **signature** | `4. 1. 1.` | repairs to `4. 5. 6.` | 53 |
| **consecutive** | `1. 2. 3.` | unchanged | 2296 |
| **genuine hole** | `1. 2. 4. 5.` | closes the hole: `1. 2. 3. 4.` | 3 |

The first two shapes are damage from the earlier default-mode format
pass, and `--number` undoes it. The **signature** shape is the one that
looks alarming and is not: the first item keeps its number, so a
reference to "item 4" still lands on the same item.

The genuine holes are the only lists where `--number` moves a number a
reader might have been given. There are three, and one is a false
positive:

| repository | document | markers | verdict |
|---|---|---|---|
| crackerjack | `docs/plans/2026-09-07-bodai-shared-gitignore-snippet.md` | `1. 2. 4. 5. 6.` | item 3 was deleted at some point; no prose in the document names a list item by number |
| mahavishnu | `docs/decisions/2026-10-15-unified-event-bus-wrapper.md` | `1. 3. 4. 5.` | item 2 was deleted; the only numbered references in the document are to "Phase 6.4", not to list items |
| oneiric | `docs/implementation/PACKAGE7_SUMMARY.md` | `1. 5.` | **false positive** — a numbered sequence written inline inside a fenced code block, which mdformat does not touch |

So two documents in the fleet have a hole in a list, and neither has
prose that names a list item by number. Closing both holes is a fix,
not a loss.

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

## 3. Phases

### Phase 1 — the wrapper change: `--number`, then lift the skip

#### Scope

- `crackerjack/tools/mdformat_wrapper.py`
  - `_build_mdformat_cmd` — add `--number` to the command.
  - `should_skip_file` — remove the `stripped == "---"` clause; keep
    the underscore clause.
- `crackerjack/tests/unit/tools/test_mdformat_wrapper.py`
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
- **Demonstrable by**: `pytest tests/unit/tools/test_mdformat_wrapper.py`
  passes, and `python -m crackerjack.tools.mdformat_wrapper` exits 0
  with a clean tree afterwards.
- **Rollback signal**: the hook exits 1 with `files were modified by
  this hook` on a second consecutive run, which means the formatter is
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
   unambiguously repair (§2.7), and exactly two documents fleet-wide
   have a genuine hole, neither of which names a list item by number.

#### Estimated scope

One module (about 15 lines changed), one test module (about 30 lines
changed), one new test asserting a frontmatter document is in scope.

### Phase 2 — the fleet-wide formatting rollout

#### Scope

Six repositories, one commit each, in this order: crackerjack first
(it owns the hook), then mahavishnu, oneiric, akosha, session-buddy,
mcp-common.

Per repository:

- Sync the venv: `uv sync --all-groups`. The plugin arrives with the
  crackerjack dependency bump, and the hook's guard fails loud until
  it is there. The guard naming the fix is the intended behaviour, not
  a problem to route around.
- Run the format hook: `python -m crackerjack.tools.mdformat_wrapper`
  from the repository root, using that repository's own venv.
- Re-run the frontmatter semantic check (§2.3) over the live
  documents and require `semantic differences: 0` and `errors: 0`.
- Regenerate the plan index: `python -m crackerjack.tools.plan_index_sync`
  (the sanctioned renderer; `scripts/regenerate_plan_index.py` in
  mahavishnu is known to produce a broken shape and must not be used).
- Confirm the plan-index audit reports no frontmatter'd file missing
  from `PLAN_INDEX.md`.
- Confirm `git diff --name-only` lists only `.md` and `.markdown`.
- Commit.

#### Integration Contract

- **Triggered from**: the `mdformat` hook, run per repository.
- **Returns to / updates**: the markdown documents of that repository,
  and its `docs/plans/PLAN_INDEX.md`.
- **Demonstrable by**: `git diff --name-only` in each repository lists
  only markdown; the plan-index audit reports zero missing files; a
  second hook run in each repository is a no-op.
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
- `crackerjack/tools/mdformat_wrapper.py:43` — the exclusion this plan
  lifts.
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

**Commit:** `e9448967` — `fix(format): format frontmatter documents and
preserve list numbering`
**Baseline:** `c8bd7d4c`
**Changed:** `crackerjack/tools/mdformat_wrapper.py`,
`crackerjack/services/doc_categorizer.py` (docstring only),
`tests/unit/tools/test_mdformat_wrapper.py`,
`tests/tools/test_mdformat_wrapper.py` (docstring only).

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
   `--number` renders consecutive numbering, so it *repairs* the 5545
   collapsed lists fleet-wide and those repairs are marker-only hunks.
   The condition now says what its own parenthetical meant: no marker
   is decreased.
2. **`--number` zero-pads lists of ten or more items** (`1.` → `01.`).
   98 lists in the fleet are affected. CommonMark renders the list as
   `1.` through `13.` either way, so the leading zero is a source-text
   artefact and not a rendered one.
3. **The `[N, 1, 1, …]` shape looks like a hazard and is not.** The
   first marker is kept and the rest are numbered consecutively from it,
   so a reference to "item N" still lands on the same item. 53 lists
   fleet-wide.
4. **Exactly two documents in the fleet have a genuine hole in a list**,
   and neither names a list item by number in its prose. A third
   candidate is a false positive — a numbered sequence written inline
   inside a fenced code block, which mdformat does not touch. §2.7.
5. **One tracked document has invalid YAML frontmatter already**:
   `crackerjack/mcp/agents/crackerjack-specialist.md`, whose unquoted
   `description` contains a bare colon, so PyYAML rejects it. This
   change neither causes nor worsens it — the block is byte-identical
   before and after formatting, and mdformat preserves it and warns.
   Left alone as out of scope; it is an authoring problem, not a
   formatter problem.
6. **`doc_categorizer` documented itself as mirroring this module's
   `---` rule**, and that claim became false when the skip was lifted.
   The docstring is corrected; the behaviour is deliberately unchanged.

**A note the plan does not need but the record should carry:** this plan
file is itself one of the damaged documents. Its own §2.4 example list
is `[3, 1]` in the source — the damage signature of the earlier
default-mode pass — and `--number` restores it to `[3, 4]`. The plan's
central hazard, demonstrated on the plan itself.

**Phase 2 is not executed.** The wrapper now formats crackerjack's own
306 frontmatter'd documents on its next run; that churn, plus the
regenerated plan index, is Phase 2's crackerjack commit, and it is
deliberately not folded into Phase 1's commit.

