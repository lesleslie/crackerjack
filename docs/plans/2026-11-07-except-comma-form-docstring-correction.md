---
title: Correct the Misstated Python 3.14 `except A, B:` Semantics in Test Docstrings
description: Three crackerjack test docstrings describe Python 3.14's unparenthesized `except A, B:` clause as the Python-2 binding form that catches only the first listed type. Under PEP 758 the form is exactly `except (A, B):` — it catches both listed types and binds no name — so the docstrings mislabel working production code as buggy and invite a future contributor to narrow a correct multi-catch into a single-catch regression.
audience: crackerjack maintainer
created: 2026-11-07
status: draft
role: implementation
topic: documentation
date: 2026-11-07
last_reviewed: 2026-11-07
superseded_by: null
blocks_on: []
---

# Correct the Misstated Python 3.14 `except A, B:` Semantics in Test Docstrings

## Brief (intent-driven)

### Goal

Correct the three crackerjack test docstrings that misstate the runtime semantics of
Python 3.14's unparenthesized `except A, B:` clause.

### Constraints

- Must not change the behavior of any module under `crackerjack/`.
- Must state the PEP 758 semantics: the unparenthesized form is the tuple form, catches
  both listed types, and binds no name.
- Must not restyle the `except A, B:` occurrences in production code.
- Must leave every existing test assertion unchanged.

### Failure Conditions (verifier-only)

- If the diff touches any file under `crackerjack/` (production code), fail.
- If any test assertion changes, fail.
- If the revised docstrings still contain "as the alias name" or "parses as", fail.
- If pytest does not pass for `tests/adapters/type/test_pyright.py`,
  `tests/checks/test_release_audit.py`, or `tests/tools/test_ty_cleanup.py`, fail.

## Evidence

Python 3.14 added PEP 758 ("Allow except and except* expressions without
parentheses"). Under it, `except A, B:` — no parentheses, no `as` — parses as the
tuple expression `(A, B)` and is semantically identical to `except (A, B):`. It
catches both listed types and binds no name. Before 3.14 the same text was a
`SyntaxError`.

Measured on Python 3.14.10:

```python
def classify(exc):
    try:
        raise exc
    except ValueError, IndexError:
        return "CAUGHT"
    return "not caught"

# ValueError -> CAUGHT
# IndexError -> CAUGHT
# TypeError  -> propagated
```

`IndexError` inside the handler body is still the builtin **class**, so there is no
alias binding to observe.

### Affected docstrings

| File | Current claim | Correction |
|---|---|---|
| `tests/adapters/type/test_pyright.py:333-338` | "In Python 3 this binds ``IndexError`` as the alias name. ValueError is caught, but IndexError is NOT." | The form catches both listed types and binds nothing. |
| `tests/checks/test_release_audit.py:7-11` | "use ``except X, Y:`` (Python 2 syntax) which Python 3 parses as ``except X as Y:`` (a binding form). Those branches behave differently from intended" | The form is ``except (X, Y):``; the branches behave as intended. |
| `tests/tools/test_ty_cleanup.py:18-20` | "Pre-existing Python-2 ``except UnicodeDecodeError, OSError:`` syntax" | Not Python-2; a valid 3.14 unparenthesized multi-catch (PEP 758). |

### Why the production code is correct as written

The comma form appears **107 times across 75 files** under `crackerjack/`. Every
occurrence is an intentional multi-catch — the authors listed two or more exception
types on purpose. Under the semantics the docstrings assert, every second listed type
would be unreachable, which is not what the authors meant.

Representative sites:

- `crackerjack/adapters/sast/pyscn.py:181` — `except ValueError, IndexError:`
- `crackerjack/adapters/type/pyright.py:246`, `adapters/type/pyrefly.py:312` —
  `except ValueError, IndexError:`
- `crackerjack/parsers/factory.py:135` — `except json.JSONDecodeError, ValueError:`
- `crackerjack/parsers/json_parsers.py:1048,1169` — `except OSError, json.JSONDecodeError:`
- `crackerjack/tools/trailing_whitespace.py:49` — `except UnicodeDecodeError, PermissionError, OSError:`
- `crackerjack/tools/local_link_checker.py:168` — `except subprocess.CalledProcessError, FileNotFoundError:`
- `crackerjack/tools/ty_audit.py:62,113,158`, `tools/ty_cleanup.py:283`
- `crackerjack/core/resource_manager.py:233`, `core/autofix_coordinator.py:1476`

### The form is ruff-canonical output, not hand-mangled code

With `[tool.ruff] target-version = "py314"`, ruff's formatter **rewrites**
`except (A, B):` to `except A, B:` (the PEP 758 unparenthesized form). The comma
form across the tree is therefore the formatter's output, not a series of manual
edits. Anyone who "restores" parentheses on these clauses will have the change
undone by the next `ruff format` run — a second, independent reason not to touch
the production code under this task.

Separately, semgrep's Python parser rejects **three-or-more-name** parenthesis-free
tuples, so the 3+ name occurrences silently drop out of semgrep's analysis. That is
a pre-existing gate-coverage gap with its own workaround (bind the tuple to a
module-level constant and use `except _CONST:`); it is not part of this task.

### Provenance of the incorrect claim

The claim entered the repo in commit `d6aaa1a2` ("chore: bump version to 0.75.0",
2026-08-24), which changed `except (ValueError, IndexError):` to
`except ValueError, IndexError:`. That edit is behaviorally a no-op — the parenthesized
and unparenthesized forms are equivalent under PEP 758 — but the surrounding prose
was written to describe the change as a Python-2 relic, and later copies of that
prose spread into the other two docstrings.

## Phase 1 — Revise the three docstrings

### Design

Reword the three docstrings so they state the PEP 758 semantics: the unparenthesized
form is the tuple form, catches both listed types, and binds no name.

Also note in each docstring that the form parses only on Python >= 3.14.
`pyproject.toml` already sets `requires-python = ">=3.14"`, so the note prevents a
future contributor from "fixing" the form for 3.13 compatibility.

No production code changes. No assertion changes.

### Integration Contract

- Triggered from: a maintainer reading `tests/adapters/type/test_pyright.py` or
  `tests/checks/test_release_audit.py` and acting on the docstring's claim.
- Returns to / updates: nothing at runtime; the three docstrings only.
- Demonstrable by: `pytest tests/adapters/type/test_pyright.py
  tests/checks/test_release_audit.py tests/tools/test_ty_cleanup.py` passes, and
  `git diff --stat` shows only the three test files.
- Rollback signal: any test module on those three paths starts failing.
- Observability added: none — documentation-only change.

## Out of Scope

- Changing the `except A, B:` occurrences in production code. They are correct.
- Adding parentheses for style. PEP 758 does not require it, and restyling 107 sites
  would bury the docstring correction in noise.
- The `pyscn==1.5.0` dependency pin, which is a separate concern and is already
  discussed upstream in `lesleslie/crackerjack` issue #5.
