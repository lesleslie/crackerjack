"""Golden-diff test for the unsafe-fix output.

Catches upstream Ruff rule changes that would silently alter the diff and
introduce a new auto-applied rewrite. Update the golden file via:

    unset VIRTUAL_ENV
    uv run --no-sync ruff check --diff --unsafe-fixes --select B006 \\
        --isolated tests/fixtures/ruff_unsafe_golden_input.py \\
        > tests/fixtures/ruff_unsafe_diff_golden.txt

The update must be reviewed by a human before commit.

Stage 4 of the Ruff fix-safety policy: this test pins the diff for B006
(mutable-argument-default) so a future ruff release that changes the
auto-applied rewrite (e.g. flipping `[]` -> `None` with a guard to a
different transformation) breaks this test rather than silently altering
a downstream --fix run.
"""

from pathlib import Path

FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures"
GOLDEN_DIFF = FIXTURE_DIR / "ruff_unsafe_diff_golden.txt"
GOLDEN_INPUT = FIXTURE_DIR / "ruff_unsafe_golden_input.py"


def test_unsafe_diff_matches_golden() -> None:
    import os
    import subprocess

    # Strip the inherited mahavishnu venv so `uv run --no-sync` resolves to
    # the crackerjack project venv (which contains ruff 0.16.0).
    env = {k: v for k, v in os.environ.items() if k != "VIRTUAL_ENV"}

    if not GOLDEN_INPUT.exists():
        import pytest

        pytest.skip(f"missing {GOLDEN_INPUT}; create it before running this test")

    # Pass the file relative to cwd (FIXTURE_DIR) so ruff's diff header
    # prints the path consistently regardless of absolute-path invocation.
    relative_input = GOLDEN_INPUT.name

    result = subprocess.run(
        [
            "uv",
            "run",
            "--no-sync",
            "ruff",
            "check",
            "--diff",
            "--unsafe-fixes",
            "--isolated",
            "--select",
            "B006",
            relative_input,
        ],
        capture_output=True,
        text=True,
        cwd=FIXTURE_DIR,
        env=env,
    )
    # Exit 1 means fixes would be applied; that is the expected signal here.
    assert result.returncode in (0, 1), (
        f"unexpected ruff exit {result.returncode}: stderr={result.stderr!r}"
    )
    assert result.stdout == GOLDEN_DIFF.read_text(), (
        f"ruff diff drifted from golden:\n"
        f"--- expected ---\n{GOLDEN_DIFF.read_text()}\n"
        f"--- actual ---\n{result.stdout}\n"
    )