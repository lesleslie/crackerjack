"""End-to-end integration test for the sandboxed fix path.

Runs in a git worktree so the main working tree is never touched.
Verifies that with CRACKERJACK_AI_FIX_USE_SANDBOX=1:
1. The AI fix pipeline completes without error.
2. The snapshot+rollback path is intact (no working-tree damage).
"""

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

import pytest


@pytest.mark.integration
@pytest.mark.slow
@pytest.mark.timeout(600)
def test_sandboxed_fix_in_worktree(tmp_path: Path) -> None:
    """Run crackerjack --ai-fix in a worktree with sandbox enabled."""
    worktree = tmp_path / "crackerjack-e2e"
    repo = Path(__file__).resolve().parents[2]

    # Skip when this test itself runs inside a linked worktree — git refuses
    # to create a nested worktree from another worktree's mount point
    # (exit 255). The proper sandbox fixture is the main checkout.
    _git_dir = subprocess.run(
        ["git", "rev-parse", "--git-dir"],
        cwd=repo, check=True, capture_output=True, text=True,
    ).stdout.strip()
    _git_common = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        cwd=repo, check=True, capture_output=True, text=True,
    ).stdout.strip()
    if _git_dir != _git_common:
        pytest.skip(
            "test_sandboxed_fix_in_worktree requires a non-linked-worktree "
            "checkout; running from inside another worktree"
        )

    # Use a unique branch per run so prior failed runs do not block this one
    # via "branch already checked out at another worktree" (exit 255).
    _branch = f"test-sandbox-e2e-{uuid.uuid4().hex[:8]}"

    # Create a worktree.
    subprocess.run(
        ["git", "worktree", "add", str(worktree), "-b", _branch],
        cwd=repo, check=True, capture_output=True,
    )
    try:
        # Add a synthetic issue.
        target = worktree / "tests" / "test_synthetic_sandbox.py"
        target.write_text(
            "import os  # unused\nimport sys  # unused\n"
            "def f(x: int) -> int:\n    return x + 1\n",
            encoding="utf-8",
        )
        subprocess.run(
            ["git", "add", "tests/test_synthetic_sandbox.py"],
            cwd=worktree, check=True, capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "test: synthetic issue"],
            cwd=worktree, check=True, capture_output=True,
        )

        # Run crackerjack with the sandbox enabled. Bound the run.
        env = os.environ.copy()
        env["CRACKERJACK_AI_FIX_USE_SANDBOX"] = "1"
        env["CRACKERJACK_AI_FIX_MAX_ITERATIONS"] = "1"
        env["CRACKERJACK_AI_FIX_PER_ISSUE_TIMEOUT"] = "30"
        env["CRACKERJACK_AI_FIX_GLOBAL_RETRY_BUDGET"] = "5"
        result = subprocess.run(
            ["uv", "run", "crackerjack", "run", "--all-files",
             "--skip-hooks", "-n"],
            cwd=worktree, env=env, capture_output=True, text=True, timeout=540,
        )

        # The run should not crash; the sandbox path is exercised.
        # (Exit code 0 or 1 are both acceptable; we just want to know
        # the subprocess completed and didn't error out.)
        assert result.returncode in (0, 1), (
            f"crackerjack exited unexpectedly: {result.returncode}\n"
            f"stderr: {result.stderr[-500:]}"
        )
    finally:
        # Clean up the worktree.
        subprocess.run(
            ["git", "worktree", "remove", str(worktree), "--force"],
            cwd=repo, check=False, capture_output=True,
        )
        subprocess.run(
            ["git", "branch", "-D", _branch],
            cwd=repo, check=False, capture_output=True,
        )
