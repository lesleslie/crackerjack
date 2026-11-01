# The ty adapter module must not be named `ty`

Status: Active
Date: 2026-11-01
Related: `2026-10-31-ty-version-pin-must-be-transitive.md`

## Context

The comprehensive stage failed with:

```
Redundant exclusion 'ty': import detected in source code
```

Two facts from the 2026-10-31 decision combine to produce it.

1. **`ty` is a runtime dependency.** It is a Rust binary, invoked as an
   external CLI by `crackerjack.tools._ty_binary`, and never imported by
   name. A runtime dependency is what makes the pin transitive, so every
   repo that installs crackerjack receives the pinned build.

1. **`ty` is in `[tool.creosote].exclude-deps`.** The exclusion is what
   stops creosote reporting the distribution as an unused dependency.

Creosote decides whether a dependency is imported by looking for its name
as an element of the dotted path of every import in the package
(`creosote/resolvers.py`, `associate_dep_with_import`):

```python
if not imp.module and import_name in imp.name:   # import a.b.c
elif imp.name and import_name in imp.module:       # from a.b import c
```

Crackerjack shipped the adapter for the `ty` type checker at
`crackerjack/adapters/type/ty.py`. Every
`from crackerjack.adapters.type.ty import TyAdapter` statement therefore
put `ty` in an import path, and creosote concluded that the third-party
`ty` distribution was imported.

That makes the exclusion look unnecessary, and creosote says so:

```
Found dependencies in pyproject.toml: ..., typer, vulture
Redundant exclusion 'ty': import detected in source code
No unused dependencies found! ✨
```

Creosote exits 0 — the redundant-exclusion check is opt-in
(`--use-feature fail-redundant-excludes`) and only ever warns. The
crackerjack hook executor, however, parses the warning off stderr and
flips the hook to `failed`, because creosote is a status-flipping
reporting tool.

The autofixer made the trap worse. `crackerjack/fixers/dependency.py`
treats "Redundant exclusion" as a request to delete the entry from
`[tool.creosote].exclude-deps`. One autofix pass would have removed a
legitimate exclusion — and the exclusion is load-bearing, because without
it creosote reports `ty` as an unused dependency.

## Decision rule

**No module in the packaged source may have a dotted path containing a
path element equal to the name of an excluded dependency.**

The leaf name is the whole collision. `crackerjack.adapters.type.ty` has
`ty` as its last element; `crackerjack.adapters.type.ty_adapter` does
not. The rule therefore constrains the leaf of a module path, not the
distribution of names across the tree.

The module is renamed to `crackerjack/adapters/type/ty_adapter.py`. The
sibling adapters keep their names (`pyrefly.py`, `pyright.py`); neither
`pyrefly` nor `pyright` is an excluded dependency, so neither collides.
The asymmetry is deliberate and is documented in the module docstring so
the name is not "corrected" back.

The exclusion for `ty` stays in `[tool.creosote].exclude-deps`. Removing
it would silence the warning only by relying on the very collision this
decision removes — and would break the moment the adapter module moved.

## Consequences

- `crackerjack.adapters.type.ty` no longer exists. The import path is a
  public surface, but crackerjack is pre-1.0 and the project does not
  carry backwards-compatibility shims.
- `tests/unit/test_creosote_exclusion_shadowing.py` pins the invariant:
  it parses every import in the package with `ast` and fails if any
  excluded dependency name appears as a path element. The test mirrors
  creosote's own import model, so it covers the absolute `from` form,
  the relative `from .ty import` form, and the plain `import a.b.ty`
  form.
- The underlying behaviour in creosote is a substring-of-path match, so a
  distribution named `ty` can still be satisfied by a first-party module
  anywhere in the path. The guard test is the enforcement point, not
  creosote.

## Verification

```bash
$ .venv/bin/creosote --venv .venv -p crackerjack --include-deferred
Found dependencies in pyproject.toml: aiofiles, aiohttp, bandit, ...
No unused dependencies found! ✨
$ echo $?
0
```

The `Redundant exclusion 'ty'` line is gone, and `ty` remains in
`exclude-deps` so creosote still does not report it as an unused
dependency.

## References

- `crackerjack/adapters/type/ty_adapter.py` — the renamed module
- `crackerjack/adapters/factory.py` — the `("type.ty_adapter", "TyAdapter")` registry entry
- `crackerjack/tools/_ty_binary.py` — where the `ty` binary is actually resolved
- `.venv/.../creosote/resolvers.py` — `associate_dep_with_import`, the substring match
- `.venv/.../creosote/cli.py` — `get_redundant_excludes`, the warning
- `crackerjack/executors/hook_executor.py` — `_parse_creosote_issues`, where the warning becomes a failure
- `crackerjack/fixers/dependency.py` — `fix_dependency_issue`, the autofix that would delete the exclusion
