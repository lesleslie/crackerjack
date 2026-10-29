"""Resolve the Mypy flags Crackerjack passes to Refurb for a target repo.

Refurb drives Mypy internally -- Mypy is a hard dependency rather than a
pluggable backend (``refurb/main.py`` imports ``mypy.build.build`` and
``mypy.main.process_options`` directly) -- so Mypy's own flags are the only
speed lever available. Pyright or ``ty`` cannot be substituted.

By default Mypy follows imports transitively (``follow_imports = "normal"``),
so every dependency shipping a ``py.typed`` marker is analyzed as if it were
first-party source. On the Bodai repos that meant roughly 8,100 modules
analyzed to lint ~120 files, costing 120s to 670s per hook run -- warm cache
included, because Refurb forces fine-grained incremental mode on, which does
not help while the whole third-party graph is re-verified each time.

``--follow-imports=skip`` leaves imported modules unanalyzed (``Any``). The
scanned package's own modules stay in Mypy's build set, so their types stay
precise and rules that depend on in-package types still fire. What is lost
is anything whose "correct" answer comes from a *third-party* library's
default value: FURB120 (redundant default argument) compares the argument
against the callee's default, and a skipped library has no default to
compare against. Measured on mcp-common, ``--enable-all`` drops from 30
findings to 21 -- the skipped set is a strict subset, no new findings, and
the repository's default check set is unaffected.

The effect depends on the repository's Mypy configuration. Where
``follow_imports`` is left at the default, the scan drops from minutes to
seconds -- mcp-common from 294s to 55s, mahavishnu from minutes to about
75s. Where a repository's config already sets ``follow_imports = "skip"``
(crackerjack's own mypy.ini does), the flag is effectively a no-op: it
still makes the behaviour explicit rather than incidental, so a change to
mypy.ini cannot silently slow the hook back down.

**These flags are only safe for package-wide scans.** A scan of an explicit
*file* list puts no sibling modules in Mypy's build set, so their types
degrade to ``Any`` too and type-aware rules silently stop firing: on a
single-file scan FURB123 stopped being reported while FURB173 still was.
Callers that scan file lists must not add these flags -- see
``adapters/refactor/refurb.py``, which carries the repository's own flags
with ``follow_imports`` forced back to ``normal``.

Refurb *replaces* the config-file ``mypy_args`` when flags are supplied on the
command line (``refurb/settings.py``: ``mypy_args=new.mypy_args or
old.mypy_args``). Passing flags on the command line would therefore silently
discard a repository's own ``[tool.refurb].mypy_args``. So the repository's
config is read here and passed through: when a repository configures
``mypy_args`` at all, its value is authoritative -- including when it is
explicitly empty, which is how a repository opts out of the speed flags.
Crackerjack's defaults apply only to repositories that do not configure
Refurb.

The flags are emitted after a ``--`` separator, which is how Refurb forwards
arguments to Mypy. Source targets must therefore be placed *before* that
separator: Mypy's positional is ``nargs="*"``, so a path after ``--`` is
reported as an unrecognized argument and the hook fails with zero findings.
"""

from __future__ import annotations

import tomllib
from collections.abc import Sequence
from pathlib import Path

DEFAULT_REFURB_MYPY_ARGS: tuple[str, ...] = (
    "--follow-imports=skip",
    "--ignore-missing-imports",
)


def read_repo_refurb_mypy_args(repo_root: Path | str | None) -> list[str] | None:
    """Read ``[tool.refurb].mypy_args`` from a repository's pyproject.toml.

    Returns ``None`` when the repository does not configure the setting (so
    the caller can fall back to its own defaults), and a list -- possibly
    empty -- when it does. An explicitly empty list is meaningful: it is how
    a repository opts out of the speed flags.

    A missing or unparsable pyproject.toml is treated as "not configured"
    rather than an error, so a repository that does not use Refurb simply
    inherits the defaults.
    """
    root = Path.cwd() if repo_root is None else Path(repo_root)
    try:
        with (root / "pyproject.toml").open("rb") as handle:
            data = tomllib.load(handle)
    except OSError, tomllib.TOMLDecodeError:
        return None
    tool = data.get("tool")
    if not isinstance(tool, dict):
        return None
    refurb = tool.get("refurb")
    if not isinstance(refurb, dict):
        return None
    raw = refurb.get("mypy_args")
    if not isinstance(raw, list):
        return None
    return [str(item) for item in raw]


def resolve_refurb_mypy_args(
    repo_root: Path | str | None,
    defaults: Sequence[str] | None = None,
) -> list[str]:
    """Resolve the Mypy flags Refurb should receive for a repository.

    The repository's own ``[tool.refurb].mypy_args`` wins when present.
    Otherwise the supplied defaults (or the module defaults) apply.
    """
    repo = read_repo_refurb_mypy_args(repo_root)
    if repo is not None:
        return repo
    return list(DEFAULT_REFURB_MYPY_ARGS if defaults is None else defaults)


def build_refurb_mypy_args(
    repo_root: Path | str | None,
    defaults: Sequence[str] | None = None,
) -> list[str]:
    """Return the ``--``-prefixed argument tail for a Refurb invocation."""
    args = resolve_refurb_mypy_args(repo_root, defaults)
    if not args:
        return []
    return ["--", *args]


def resolve_refurb_mypy_args_for_file_list(
    repo_root: Path | str | None,
    defaults: Sequence[str] | None = None,
) -> list[str]:
    """Mypy flags for a scan of an explicit file list.

    A file-list scan needs ``--follow-imports=normal``: skipping imports
    leaves the sibling modules outside Mypy's build set, so their types
    degrade to ``Any`` and type-aware rules silently stop firing.

    Everything else the repository configured is preserved. In particular
    ``--ignore-missing-imports`` has to survive: dropping it makes Mypy
    report an unresolved import for an optional dependency that is absent
    from the venv. That import error is not a blocker, so Refurb drops it
    -- but the general case still bites: a *blocker* Mypy error (a syntax
    error, a "Duplicate module named" complaint, a rejected command line)
    is surfaced by Refurb as its own error with exit code 1, and the tool
    adapter treats "exit 1 with output" as success, so the check would
    report "No issues found" while Mypy had actually failed.

    Only ``follow_imports`` is overridden. Mypy parses its config file
    first and lets command-line args override it, so the rest of the
    repository's list has to be carried over explicitly; Refurb likewise
    replaces the config file's ``mypy_args`` with the command-line value
    rather than merging them.

    Both spellings of the flag are recognised -- ``--follow-imports=skip``
    and the space-separated ``--follow-imports skip`` -- because Mypy
    accepts either and argparse keeps the last occurrence. Recognising only
    the ``=`` form would let a repository's own ``skip`` survive and
    silently degrade the file-list scan.
    """
    args = resolve_refurb_mypy_args(repo_root, defaults).copy()
    forced: list[str] = []
    kept: list[str] = []
    skip_next = False
    for arg in args:
        if skip_next:
            # The value belonging to a space-separated --follow-imports.
            skip_next = False
            continue
        if arg == "--follow-imports":
            if not forced:
                forced.append("--follow-imports=normal")
            skip_next = True
            continue
        if arg.startswith("--follow-imports="):
            if not forced:
                forced.append("--follow-imports=normal")
            continue
        kept.append(arg)
    if not forced:
        forced.append("--follow-imports=normal")
    return [*forced, *kept]


def build_refurb_mypy_args_for_file_list(
    repo_root: Path | str | None,
    defaults: Sequence[str] | None = None,
) -> list[str]:
    """``--``-prefixed Mypy tail for a scan of an explicit file list."""
    args = resolve_refurb_mypy_args_for_file_list(repo_root, defaults)
    if not args:
        return []
    return ["--", *args]
