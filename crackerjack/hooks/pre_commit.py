"""Pre-commit hook registry for the Crackerjack workflow.

This module is the canonical integration point for the
``pre_commit_skill_coverage_gate``. It runs the gate *after* format and
lint gates and *before* the test gate, per the
``2026-07-29-session-buddy-extension`` plan.

The two-stage hook execution model in Crackerjack keeps format and lint
in the FAST stage and the heavy checks (type checking, security scanning,
complexity analysis) in the COMPREHENSIVE stage. Tests are run as their
own subsequent stage. The skill-coverage gate is a non-LLM health check
that observes the Phase 1.5 distilled-skill store, so it slots in between
fast and the test stages.

Exit-code semantics:

  0 — pass
  1 — warn (default; ``crackerjack run --strict`` makes this fatal)
  2 — programming bug (reserved)

``--no-verify`` skips the gate entirely per the existing pre-commit
convention.
"""

from __future__ import annotations

import asyncio
import pathlib
import sys

from crackerjack.hooks.skill_coverage import (
    pre_commit_skill_coverage_gate,
)


def main(repo_path: pathlib.Path | None = None) -> int:
    """Synchronous entry point for subprocess-based hook integrations.

    Args:
        repo_path: Repository root. Defaults to the current working directory.

    Returns:
        Exit code from ``pre_commit_skill_coverage_gate``:

        * 0 — all skills fresh.
        * 1 — stale skills detected or Session-Buddy unreachable (warn).
        * 2 — programming bug (reserved).
    """
    resolved = repo_path if repo_path is not None else pathlib.Path.cwd()
    return asyncio.run(pre_commit_skill_coverage_gate(resolved))


if __name__ == "__main__":
    sys.exit(main())


__all__ = ["main", "pre_commit_skill_coverage_gate"]
