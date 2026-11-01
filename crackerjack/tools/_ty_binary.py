"""Resolve which ``ty`` executable the quality gates should run.

``ty`` is a Rust binary, not an importable module, so every gate that
type-checks has to shell out to it. Those call sites used to spell the
bare name ``"ty"`` and let ``PATH`` choose the build, which made the
gate's verdict depend on the caller's shell rather than on the repo:

* a developer shell with a project virtualenv activated put that
  virtualenv's ``ty`` first, and
* a plain shell fell through to ``~/.local/bin/ty`` -- a ``uv tool``
  install that was five months stale.

A stale ty does not fail loudly. It resolves SQLModel's
``Session.exec`` overloads differently and reports phantom errors
against code that is correct -- seven of them across session-buddy on
2026-10-31, from a ty that predated SQLModel's ``Unpack[_Ts]``
overloads. The gate declared the repo broken when nothing was.

Resolution order:

1. **The virtualenv crackerjack is running in** --
   ``Path(sys.executable).parent / "ty"``. This is the environment
   whose lockfile pinned the installed dependency versions, so it is
   the build whose inference matches the code it is about to check.
   Under ``uv run`` -- how the gate launches itself -- this is the
   target repository's own virtualenv.

2. **``PATH``** -- the fallback for an environment whose virtualenv does
   not carry ty. This is the gate's pre-existing behaviour, and
   ``uv run`` already puts the project's ``.venv/bin`` first on
   ``PATH``, so the candidate above narrows the search rather than
   widening it.

The pin in ``pyproject.toml`` makes the build *available* everywhere;
this module makes it *authoritative*, so a gate never silently falls
back to an ambient build that happens to be older.

Two properties this module deliberately does NOT have
------------------------------------------------------------

**No repository-local executable.** An earlier draft preferred
``<git-root>/.venv/bin/ty``, discovered by walking the directory
ancestry upwards. That is an uncontrolled search path (CWE-427): the
checkout's contents -- attacker-controllable in a CI run over a fork's
pull request -- would decide which binary the gate executed. The
virtualenv anchor is strictly better on every axis: it is derived from
the running interpreter rather than from the directory tree, and it is
the environment crackerjack actually resolved its own dependencies
against. Because crackerjack declares ``ty`` as a runtime dependency,
that virtualenv always carries the pinned build.

**The interpreter path is not resolved.** ``sys.executable`` is itself
a symlink inside a virtualenv, pointing at the base interpreter::

    /repo/.venv/bin/python -> /usr/local/Cellar/python@3.14/.../bin/python3.14

Resolving it lands in the base interpreter's directory, which holds no
``ty`` at all -- so ``Path(sys.executable).resolve().parent / "ty"``
finds nothing and the resolution silently falls through to ``PATH``.
Use ``Path(sys.executable).parent`` un-resolved: that is the
virtualenv's own ``bin`` directory, which is where the console script
was installed.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _is_runnable(candidate: Path) -> bool:
    """True when ``candidate`` is an existing, executable regular file.

    ``is_file()`` follows symlinks, which is intentional here: the
    containing directory is the virtualenv crackerjack was installed
    into, a location the user controls and the package manager owns.
    A symlink inside it is the user's own choice, not an injection
    point.
    """
    if not candidate.is_file():
        return False
    return os.access(candidate, os.X_OK)


def resolve_ty_binary() -> str:
    """Return the ``ty`` executable the gates should invoke.

    Returns the build installed alongside the running interpreter when
    there is one, else the first ``ty`` on ``PATH``, else the bare name
    -- so a missing binary surfaces as the caller's own
    ``FileNotFoundError`` rather than as a silently skipped check.
    """
    candidate = Path(sys.executable).parent / "ty"
    if _is_runnable(candidate):
        return str(candidate)
    return shutil.which("ty") or "ty"
