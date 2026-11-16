#!/usr/bin/env python3
"""Regenerate this repo's ``docs/plans/PLAN_INDEX.md``.

Thin wrapper. The index has exactly one renderer —
``crackerjack.tools.plan_index_sync`` — and the publish phase writes the
same bytes with it.

This file used to hold a *copy* of an older renderer. That was the source
of a long-standing inconsistency: the command documented in
``docs/schemas/document-frontmatter-v1.md`` produced one format, the
publish phase produced another, and ``docs/plans/PLAN_INDEX.md`` was
whichever ran last. One renderer, one output, one path.

Usage:
    uv run python scripts/regenerate_plan_index.py            # write the index
    uv run python scripts/regenerate_plan_index.py --dry-run  # report drift only
    uv run python scripts/regenerate_plan_index.py --out PATH # write elsewhere
    uv run python scripts/regenerate_plan_index.py --json-summary
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    """Delegate to the single renderer."""
    from crackerjack.tools.plan_index_sync import main as sync_main

    args = list(sys.argv[1:] if argv is None else argv)

    # The historical entry point took the repo root as a positional
    # argument; the renderer takes it as --repo-root.
    if args and not args[0].startswith("-"):
        repo_root = Path(args.pop(0)).resolve()
    else:
        repo_root = REPO_ROOT

    forwarded = ["--repo-root", str(repo_root)]
    # The renderer's --out default is relative to the process CWD, which
    # would write the index wherever the script happened to be invoked
    # from. Anchor it to the repo root unless the caller said otherwise.
    if "--out" not in args:
        forwarded += ["--out", str(repo_root / "docs" / "plans" / "PLAN_INDEX.md")]
    forwarded += args
    return sync_main(forwarded)


if __name__ == "__main__":
    sys.exit(main())
