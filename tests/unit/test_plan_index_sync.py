"""Unit tests for ``crackerjack.tools.plan_index_sync``.

Pins the regeneration contract for the Bodai doc-store frontmatter
format. Designed to run offline (no PyYAML constraint raises
here because pytest runs inside crackerjack's test env which
already bundles PyYAML).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
TOOL_MODULE = "crackerjack.tools.plan_index_sync"


def _tool_help() -> str:
    out = subprocess.run(
        [sys.executable, "-m", TOOL_MODULE, "--help"],
        check=True,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    return out.stdout


def test_help_smoke() -> None:
    """Help text lists the documented switches."""
    assert "--repo-root" in _tool_help()
    assert "--out" in _tool_help()
    assert "--dry-run" in _tool_help()


def test_no_changes_when_index_current(tmp_path: Path) -> None:
    """When the existing ``PLAN_INDEX.md`` already matches the rendered output,
    the tool reports ``up-to-date`` and exits 0 — no wasted writes."""
    from crackerjack.tools import plan_index_sync as pis

    rendered = pis.render_plan_index(REPO_ROOT)
    (tmp_path / "PLAN_INDEX.md").write_text(rendered, encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            TOOL_MODULE,
            "--repo-root",
            str(REPO_ROOT),
            "--out",
            str(tmp_path / "PLAN_INDEX.md"),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stderr
    assert "up-to-date" in result.stdout


def test_dry_run_detects_drift(tmp_path: Path) -> None:
    """When the existing index differs from the rendered output, ``--dry-run``
    exits 1 and prints the rewrite notice (without writing)."""
    from crackerjack.tools import plan_index_sync as pis

    rendered = pis.render_plan_index(REPO_ROOT)
    (tmp_path / "PLAN_INDEX.md").write_text("# stale\n", encoding="utf-8")
    assert rendered != "# stale\n"  # sanity: renderer is non-trivial

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            TOOL_MODULE,
            "--repo-root",
            str(REPO_ROOT),
            "--out",
            str(tmp_path / "PLAN_INDEX.md"),
            "--dry-run",
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 1, (
        f"--dry-run should exit 1 on drift, got {result.returncode}\n"
        f"stdout={result.stdout!r}\nstderr={result.stderr!r}"
    )
    assert "would rewrite" in result.stdout


def test_rendered_contains_all_six_canonical_stores() -> None:
    """The regenerated body lists every canonical Bodai doc store section.

    The renderer strips a ``docs/`` prefix → ``Docs: …`` heading and
    keeps ``.claude/decisions/`` paths intact (preserves the dot,
    which would otherwise look like a numbered markdown list item).
    Both forms verify in the rendered body.
    """
    from crackerjack.tools import plan_index_sync as pis

    rendered = pis.render_plan_index(REPO_ROOT)
    expected_headings = {
        "Docs: adr",
        "Docs: plans",
        "Docs: superpowers/specs",
        "Docs: superpowers/plans",
        ".claude/decisions",
        "Docs: followups",
    }
    for heading in expected_headings:
        assert f"### {heading}" in rendered, (
            f"Store heading {heading!r} missing from rendered output"
        )


def test_default_stores_match_akosha_canonical_set() -> None:
    """Crackerjack's stores mirror the akosha/Bodai canonical 6.

    If this test fails after adding a new store, run the akosha-side
    regenerator locally and confirm the crackerjack tool still parses
    the new file shape; both repos should drift together.
    """
    from crackerjack.tools import plan_index_sync as pis

    assert pis.DEFAULT_STORES == (
        "docs/adr/",
        "docs/plans/",
        "docs/superpowers/specs/",
        "docs/superpowers/plans/",
        ".claude/decisions/",
        "docs/followups/",
    )
