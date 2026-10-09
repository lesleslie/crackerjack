#!/usr/bin/env python3
"""SessionEnd hook for the trunk-based agent-review merge workflow.

Fires ``python -m mahavishnu.core.merge_to_main`` at the end of a session
when ALL skip conditions are clear (per spec §4.2). The hook is the
primary in-session surface for the merge cycle; the
``/merge-to-main`` slash command and the ``Skill(skill="merge-to-main", ...)``
surface both invoke the same Python module.

**Skip conditions** (evaluated in order, all short-circuit before any
subprocess call):

1. ``MAHAVISHNU_AUTO_MERGE`` env var set to a falsy value (``=0`` /
   ``=false`` / ``=no`` / ``=off``). Unset defaults to "auto-merge on"
   per spec §4.2 — the user has explicitly chosen default-on for this
   workflow because (a) the failure modes are loud (non-FF push fails
   the hook), (b) cleanup routes through the existing
   ``mahavishnu worktree prune-merged`` classifier (not silent),
   (c) the user is the operator.
2. ``worktree_path`` is empty or unresolvable.
3. ``is_worktree(worktree_path)`` returns False (cwd is not inside a
   git worktree).
4. ``is_sticky_failed(worktree_path)`` returns True (``.review-state.json``
   has a non-null ``stage_failed`` field — typically "stage 6 cleanup
   failed; user must resolve").

**Coexistence with ``worktree-session-isolation.py``:** Both hooks fire
at SessionEnd. Order matters: the existing hook runs first (marks
worktree ``abandoned``, runs bridge routing); this hook runs second
(decides whether to merge). The merge hook's "no-op if already merged"
check inside ``mahavishnu.core.merge_to_main`` handles the case where
the existing hook already cleaned up.

Module load is stdlib-only. The ``mahavishnu.core.merge_to_main``
import is gated behind the eligibility check, so default-off sessions
incur no mahavishnu import cost (mirrors the pattern in
``worktree-session-isolation.py``).

Reference: spec §4.2 (REQ-005); REQ-006 wires it into ``settings.json``.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess  # nosec B404 — argv-list only, no shell
import sys

# Shared helper lives in the same .claude/hooks directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _hook_io import read_session_payload  # noqa: E402 — sys.path mutation must precede import


# Env var that gates the whole feature. Per spec §4.2: unset = on (default);
# truthy = on (explicit); falsy = off (opt-out). The worktree-session-isolation
# hook uses the same default-on contract (Phase 8, 2026-07-20).
AUTO_MERGE_ENV: str = "MAHAVISHNU_AUTO_MERGE"

# Filename of the sticky-failure marker (mirrors the constant in
# mahavishnu.core.merge_to_main). Imported lazily below to keep module load
# stdlib-only; the literal fallback is correct per spec §4.4.
_REVIEW_STATE_FILENAME_LITERAL: str = ".review-state.json"


def _review_state_filename() -> str:
    """Resolve ``.review-state.json`` filename from mahavishnu, else literal.

    Lazy import — keeps the hook's module load stdlib-only. If
    ``mahavishnu`` is not importable (e.g. fresh worktree before
    ``uv sync``), fall back to the literal string, which is the
    spec-defined filename.
    """
    try:
        from mahavishnu.core.merge_to_main import REVIEW_STATE_FILENAME

        return REVIEW_STATE_FILENAME
    except ImportError:
        return _REVIEW_STATE_FILENAME_LITERAL


def _is_truthy(value: str | None) -> bool:
    """True for ``1`` / ``true`` / ``yes`` / ``on`` (case-insensitive).

    Mirrors ``worktree-session-isolation._is_truthy`` so the two hooks
    agree on truthy parsing.
    """
    if not value:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _log(msg: str) -> None:
    """Write a single line to stderr; Claude Code surfaces as Hook output."""
    sys.stderr.write(f"merge-to-main-hook: {msg}\n")
    sys.stderr.flush()


def is_worktree(worktree_path: str) -> bool:
    """True when ``worktree_path`` is the working tree of a git worktree.

    Uses ``git rev-parse --git-dir`` which returns the worktree-specific
    git directory:

    - Main repo: ``.git`` (relative to the repo root)
    - Worktree: ``.git/worktrees/<wt-name>`` (relative to the worktree root)

    The existing ``worktree-session-isolation._cwd_is_inside_worktree``
    helper uses the same logic (the prior implementation used
    ``--git-common-dir`` which returns the SHARED git dir and always
    returned False — that bug was fixed 2026-07-20 in the sister hook).

    Returns False on any git failure — never raises; never blocks the
    SessionEnd contract.
    """
    if not worktree_path:
        return False
    try:
        result = subprocess.run(  # nosec B603 — worktree_path is a session-provided path; argv-list only
            ["git", "-C", worktree_path, "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
        return False
    git_dir = result.stdout.strip()
    return "/worktrees/" in git_dir


def is_sticky_failed(worktree_path: str) -> bool:
    """True when ``.review-state.json`` in ``worktree_path`` marks a sticky failure.

    Per spec §4.2 failure mode: "Cleanup fails (worktree's branch is
    ``not_merged`` per existing classifier) → ``mahavishnu worktree
    prune-merged`` refuses → module surfaces classifier output; user
    resolves manually. Sticky marker in ``.review-state.json`` to
    prevent re-attempt."

    The marker is the JSON file at ``<worktree_path>/.review-state.json``
    whose ``stage_failed`` field is non-null. Returns False when:

    - the path is empty,
    - the file does not exist (clean state),
    - the file is unreadable,
    - the JSON is corrupt (per REQ-014 graceful fallback, the merge
      module starts from stage 2 — so the hook SHOULD retry; sticky
      only applies to a parsed sticky-failure dict),
    - the parsed dict has ``stage_failed`` of None or absent.
    """
    if not worktree_path:
        return False
    state_path = Path(worktree_path) / _review_state_filename()
    if not state_path.exists():
        return False
    try:
        data = json.loads(state_path.read_text())
    except (json.JSONDecodeError, OSError):
        return False
    if not isinstance(data, dict):
        return False
    stage_failed = data.get("stage_failed")
    return stage_failed is not None


def _is_auto_merge_enabled() -> bool:
    """True when the auto-merge gate is open (env unset OR truthy).

    Per spec §4.2: unset defaults to "on" (the user has explicitly chosen
    default-on for this workflow). Falsy env value ("0", "false", etc.)
    opts out.
    """
    opt_in = os.environ.get(AUTO_MERGE_ENV)
    if opt_in is None:
        return True  # unset → default-on
    return _is_truthy(opt_in)


def _build_invoke_argv(worktree_path: str) -> list[str]:
    """Build argv for ``python -m mahavishnu.core.merge_to_main``.

    Returns a plain list (never ``shell=True``) so the caller can pass
    it directly to ``subprocess.run``. The ``--`` is unnecessary here
    (the only positional after the module name is no-arg invocation),
    but we keep the explicit argv structure for symmetry with
    ``worktree-session-isolation._git_worktree_add_argv``.
    """
    return [sys.executable, "-m", "mahavishnu.core.merge_to_main"]


def run_hook(
    *,
    worktree_path: str,
    payload: dict,
) -> int:
    """Apply skip conditions; on eligibility, invoke ``merge_to_main``.

    Return codes:

    - 0 — skip (one of the four skip conditions triggered) or full
      success (subprocess rc == 0). The hook's exit-0-always posture for
      skips mirrors ``worktree-session-isolation.py`` so a SessionEnd
      failure here cannot block Claude Code shutdown.
    - non-zero — subprocess invocation return code (1=review, 2=gate,
      3=rebase, 4=push, 5=cleanup per spec §4.1 Outputs). Propagated
      verbatim so Claude Code surfaces the failure as a post-session
      summary (per spec §4.2 "Rollback signal").

    The ``payload`` parameter is reserved for future skip rules (e.g.
    branch-name filtering, force-push guard). It is accepted but not
    inspected in v0.1.
    """
    if not _is_auto_merge_enabled():
        _log(f"auto-merge disabled ({AUTO_MERGE_ENV}={os.environ.get(AUTO_MERGE_ENV)!r}); skipping")
        return 0

    if not worktree_path:
        _log("empty worktree_path; skipping")
        return 0

    if not is_worktree(worktree_path):
        _log(f"{worktree_path!r} is not a git worktree; skipping")
        return 0

    if is_sticky_failed(worktree_path):
        _log(
            f"{worktree_path!r} marked sticky-failed in "
            f"{_review_state_filename()}; user must resolve manually; skipping"
        )
        return 0

    _log(f"invoking mahavishnu.core.merge_to_main for {worktree_path!r}")

    # Subprocess invocation. stdout/stderr are piped so the hook can
    # surface merge failures to Claude Code's Hook output. A short
    # timeout defends against the merge pipeline hanging in CI; the
    # underlying merge_to_main stages each have their own subprocess
    # boundaries and can be re-entered via ``.review-state.json`` resume.
    try:
        result = subprocess.run(  # nosec B603 — argv-list, no shell
            _build_invoke_argv(worktree_path),
            cwd=worktree_path,
            capture_output=True,
            text=True,
            check=False,
            timeout=600,
        )
    except subprocess.TimeoutExpired:
        _log(f"merge_to_main timed out after 600s in {worktree_path!r}")
        return 124  # conventional timeout exit code
    except OSError as exc:
        _log(f"merge_to_main invocation failed: {exc}")
        return 1

    if result.stdout:
        sys.stdout.write(result.stdout)
        sys.stdout.flush()
    if result.stderr:
        sys.stderr.write(result.stderr)
        sys.stderr.flush()

    if result.returncode != 0:
        _log(
            f"merge_to_main exited {result.returncode} in {worktree_path!r}; "
            f"see .review-state.json for the failed stage"
        )
    return result.returncode


def main() -> int:
    """SessionEnd entry point — read stdin → extract cwd → invoke ``run_hook``.

    Mirrors ``worktree-session-isolation.main()``: read stdin once
    via the shared ``_hook_io.read_session_payload`` helper, then
    thread the parsed cwd + raw dict into ``run_hook``. Returns the
    run_hook return code verbatim. No bridge routing — the existing
    worktree hook already covers event-bus publishing for SessionEnd.

    The stdin schema is the Claude Code SessionEnd contract: a JSON
    dict carrying at least ``cwd`` (and typically ``session_id``);
    see ``_hook_io.read_session_payload`` for the shared helper.
    """
    hook_payload = read_session_payload()
    return run_hook(worktree_path=hook_payload.cwd, payload=hook_payload.raw)


if __name__ == "__main__":
    sys.exit(main())
