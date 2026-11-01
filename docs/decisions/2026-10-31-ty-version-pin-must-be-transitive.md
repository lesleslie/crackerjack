# The ty version pin must be a runtime dependency, not a dependency group

Status: Active
Date: 2026-10-31

## Context

On 2026-10-31 the `ty` hook failed in session-buddy with seven errors
across three files:

```
session_buddy/mcp/tools/tasks_identity.py:118:33: error[not-iterable]
session_buddy/mcp/tools/tasks_link_storage.py:138:20: error[unresolved-attribute]
session_buddy/mcp/tools/tasks_link_storage.py:152:47: error[invalid-assignment]
session_buddy/mcp/tools/tasks_storage.py:155:47: error[invalid-assignment]
session_buddy/mcp/tools/tasks_storage.py:180:42: error[invalid-assignment]
session_buddy/mcp/tools/tasks_storage.py:203:42: error[invalid-assignment]
session_buddy/mcp/tools/tasks_storage.py:228:42: error[invalid-assignment]
```

None of that code was wrong. `session.exec(select(Model)).first()` is the
canonical SQLModel idiom, and `principal.get("permissions") or []` is
ordinary Python. The same tree passes cleanly under ty 0.0.90 and
0.0.94.

The gate had run a **ty 0.0.55** — a `uv tool` install from 2026-06-27,
five months stale. That build predates SQLModel's `Unpack[_Ts]`
overloads for `Session.exec`, so it selected the wrong overload
(`TupleResult` instead of `ScalarResult`) and reported the tuple-shaped
results as type errors. It also failed to narrow `None` out of the `or`.

The failure was silent in the worst way: the gate reported a broken
repository, and every recent ty on the machine said the repository was
fine. The version was the entire difference between those two verdicts.

The mechanism was the resolution order. Every ty call site spelled the
bare name `"ty"` and let `PATH` decide:

- a developer shell with a project virtualenv activated put that
  virtualenv's `ty` first, and
- a plain shell fell through to `~/.local/bin/ty`, the stale `uv tool`.

And the pin could not prevent that. Crackerjack declared
`ty>=0.0.84` in the **`type-checking` dependency group**. PEP 735
groups are not installed for consumers, so a pin living in one never
reaches the repositories that call crackerjack — which is every
repository in the fleet.

## Decision

1. **`ty` is a runtime dependency** (`[project.dependencies]`), not a
   dependency group. A runtime dependency is transitive, so every repo
   that installs crackerjack receives a pinned `ty` in its own
   virtualenv, and `uv run` — which the gate uses to launch itself —
   puts that virtualenv's `bin` first on `PATH`.

2. **The call sites resolve the binary explicitly** through
   `crackerjack/tools/_ty_binary.resolve_ty_binary()`: the `ty` beside
   the running interpreter (`Path(sys.executable).parent / "ty"`) first,
   then `PATH`, then the bare name so a missing binary raises
   `FileNotFoundError` instead of silently skipping the check. The pin
   makes the build *available* everywhere; the resolver makes it
   *authoritative*.

   The anchor is the **environment, not the directory tree**. An
   earlier draft preferred `<git-root>/.venv/bin/ty`, discovered by
   walking the directory ancestry upwards. That is an uncontrolled
   search path (CWE-427): the checkout's contents — attacker-
   controllable in a CI run over a fork's pull request — would decide
   which binary the gate executed. The interpreter anchor is strictly
   better on every axis: it is derived from the process itself rather
   than from the filesystem, and it is the environment whose lockfile
   pinned the installed dependency versions, so it is the build whose
   inference matches the code it is about to check. Under `uv run` —
   how the gate launches itself — that environment *is* the target
   repository's virtualenv, and because `ty` is a runtime dependency of
   crackerjack, it always carries the pinned build.

   The interpreter path is **not** resolved. `sys.executable` is itself
   a symlink inside a virtualenv, pointing at the base interpreter, so
   `Path(sys.executable).resolve().parent / "ty"` lands in the base
   interpreter's directory — which holds no `ty` at all, and the
   resolution would silently fall through to `PATH`. The virtualenv's
   own `bin` is the correct anchor.

   The `PATH` fallback is the gate's pre-existing behaviour, and `uv
   run` already puts the project's `.venv/bin` first on `PATH`, so the
   interpreter candidate narrows the search rather than widening it.

3. **`ty` has a `uv` `exclude-newer` carve-out.** The repo's 7-day
   cooldown would otherwise strand the fleet on a stale ty for up to a
   week after each release — and a type checker that is a week behind is
   not a security posture, it is a broken signal. The cooldown still
   applies to every other package.

4. **`ty` is in the creosote exclusion list.** It is a Rust binary
   invoked as an external CLI, never imported by name, so creosote
   cannot see it in use.

## Consequences

- The ty wheel (~14 MB) is installed wherever crackerjack is installed.
  Crackerjack is a development tool, so this is a dev-time cost.
- **Consumers must re-lock after crackerjack publishes.** The
  transitive pin reaches a repository only when that repository's lock
  resolves a crackerjack release carrying the pin. Until then, the
  ambient `ty` on `PATH` decides the verdict — which is why the fleet's
  `uv tool` install of ty was upgraded to 0.0.95 as an independent
  mitigation.
- The floor in the `type-checking` group is kept in sync with the
  runtime floor. The runtime pin is the one that reaches consumers; the
  group entry just keeps crackerjack's own checkout aligned.
- A ty upgrade can change a repository's diagnostic count. On
  crackerjack's own `tests/` tree, 0.0.90 reported 2728 diagnostics and
  0.0.95 reports 2745. That tree was already far over its advisory
  budget; the prod gate, which controls the exit code, is unaffected.

## Verification

A scratch project whose only dependency is `crackerjack` was synced and
checked for `.venv/bin/ty`:

```
$ uv sync --project /tmp/ty-transitive-check
$ /tmp/ty-transitive-check/.venv/bin/ty --version
ty 0.0.95 (48c5ea1ba 2026-10-29)
```

The pin is transitive, and `resolve_ty_binary()` returns that build.

The resolution boundary is pinned by `tests/tools/test_ty_binary.py`:
a `.venv/bin/ty` inside the checkout is never selected, the interpreter
symlink is not resolved, and a non-executable file or a directory is
rejected.
