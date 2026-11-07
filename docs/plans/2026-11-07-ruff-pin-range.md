---
title: Replace the Exact `ruff==0.16.0` Pin with a Bounded Version Range
description: Crackerjack declares `ruff==0.16.0` in `[project].dependencies`, which force-installs that exact linter into every downstream consumer of the published wheel and contradicts the rest of the fleet (mahavishnu `>=0.16.0`, akosha `>=0.8.0`). The pin was added to hold the rule-set baseline steady after ruff 0.16.0 expanded defaults from 59 to 413 rules; a bounded range `>=0.16.0,<0.17` preserves that baseline, admits the ten unclaimed 0.16.x patch releases, and leaves reproducibility to `uv.lock`.
audience: crackerjack maintainer
created: 2026-11-07
status: draft
role: implementation
topic: dependency-management
date: 2026-11-07
last_reviewed: 2026-11-07
superseded_by: null
blocks_on: []
---

# Replace the Exact `ruff==0.16.0` Pin with a Bounded Version Range

## Brief (intent-driven)

### Goal

Widen crackerjack's ruff dependency from an exact pin to a bounded version range.

### Constraints

- Must keep the resolved ruff version inside the 0.16.x minor series, so the
  rule-set baseline the 2026-08-06 ruff fix-policy spec was tuned against does not
  shift.
- Must leave `uv.lock` as the mechanism that pins the exact resolved version.
- Must not change the `[tool.ruff]` configuration.
- Must not change any source file.

### Failure Conditions (verifier-only)

- If the resolved ruff version in `uv.lock` falls outside 0.16.x, fail.
- If `ruff check ./crackerjack` reports findings that were not present under the
  0.16.0 baseline, fail.
- If `ruff format --check` reports files needing reformatting that were clean
  before the change, fail.
- If any file other than `pyproject.toml` and `uv.lock` changes, fail.

## What the pin was for

`docs/specs/2026-08-06-crackerjack-ruff-fix-policy-design.md` §4.8 records the
intent:

> Ruff 0.16.0 expanded its default enabled rule set from 59 rules to 413 rules.
> Crackerjack's working lock file now selects Ruff 0.16.0, and `ruff check
> ./crackerjack` reports 1249 findings on the current working tree.

and:

> The pin is the floor for reproducible CI; it is not a substitute for safe-fix
> defaults.

So the pin exists to hold the *rule-set baseline* steady. That goal is a property of
the **minor series**, not of the patch level.

## What the exact pin costs

1. **It leaks into every downstream install.** `ruff` sits in
   `[project].dependencies` — runtime deps, not a dependency group — so installing
   the published crackerjack wheel force-installs ruff 0.16.0 into the consumer's
   environment. A consumer that needs a newer ruff for its own repo hits a resolver
   conflict against a transitive exact pin.
2. **It contradicts the fleet.** mahavishnu declares `ruff>=0.16.0`, akosha declares
   `ruff>=0.8.0`. Crackerjack is the only Bodai repo using `==`.
3. **It withholds ten patch releases.** Ruff 0.16.1 through 0.16.10 are published and
   unpinned here. Patch releases do not change rule sets, so the pin blocks fixes for
   no baseline benefit.
4. **It duplicates `uv.lock`.** CI reproducibility comes from the lock file, which
   already records the exact version and hash. The `==` in `pyproject.toml` adds a
   second, stricter constraint on a *published* artifact.

## Proposed change

```toml
# before
"ruff==0.16.0",

# after
"ruff>=0.16.0,<0.17",
```

with a corresponding `uv.lock` refresh as a separate, reviewable change.

The upper bound keeps the rule-set baseline the fix-policy spec was tuned against.
The lower bound keeps the 0.16.0 rule-set expansion in place. The lock file keeps
the exact resolution.

## Deliberately out of scope: the 0.17 series

Ruff is at **0.17.4** as of 2026-11-07, so `>=0.16.0,<0.17` still leaves a minor
series on the table. A 0.17 bump must be evaluated separately, because a minor bump
is exactly what moved the default rule set last time. That evaluation is a rule-list
diff plus a `ruff check --statistics` diff on the tree, run in a scratch checkout —
not a dependency edit. Do not widen the range past `<0.17` until that diff is
reviewed.

## Note: `ruff format` is why the tree is full of `except A, B:`

Not part of this task, but it bears on anyone who considers "restoring" parentheses
on the 107 comma-form `except` clauses in `crackerjack/`: with `target-version =
"py314"`, ruff's formatter rewrites `except (A, B):` to `except A, B:` (the PEP 758
unparenthesized form). Those clauses are ruff-canonical output rather than
hand-mangled code, so a change that adds parentheses back is undone by the next
`ruff format` run.

Separately, semgrep's Python parser rejects **three-or-more-name** parenthesis-free
tuples, so the 3+ name occurrences silently drop out of semgrep's analysis. That is
a pre-existing gate-coverage gap; the documented workaround is to bind the tuple to
a module-level constant and use `except _CONST:`.

## Out of Scope

- The `pyscn==1.5.0` pin. It is load-bearing on Intel macOS: 1.5.0 is the highest
  release with a macOS x86_64 wheel, no later release publishes an sdist, and
  upstream has stated the Intel wheel will not return.
- Moving `ruff` out of `[project].dependencies` into a dependency group. The runtime
  placement is deliberate — the gate invokes ruff as an external CLI, and every repo
  that installs crackerjack must run the same build.
- The 0.17.x evaluation described above.
