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


def test_entry_link_targets_resolve_from_plans_dir() -> None:
    """Every link ``_entry_link`` emits must resolve to an existing file
    when read from ``docs/plans/PLAN_INDEX.md``.

    Prior to the 2026-09-28 fix, ``_entry_link`` treated ``rel`` as a
    repo-root-relative path: same-directory files rendered as
    ``[docs/plans/foo.md](docs/plans/foo.md)`` which resolves to
    ``docs/plans/docs/plans/foo.md`` (broken); ``docs/adr/foo.md``
    rendered as ``../docs/adr/foo.md`` (resolves to ``docs/docs/...``,
    also broken); ``.claude/...`` likewise. The contract this test pins
    matches the format akosha's ``PLAN_INDEX.md`` uses (verified by
    reading its link targets directly).

    Split into two halves:

    * **Format** (no disk I/O): the link *target* must be the path of
      ``rel`` relative to ``docs/plans/``. Covers all three store
      families (same-dir, sibling-tree, dotfile-tree).
    * **Resolution** (real files): each format target, joined to the
      index file's directory, must exist on disk. This is the
      end-to-end contract — without it, a string-only assertion could
      pass even if the link points to a typo or stale path.
    """
    from crackerjack.tools import plan_index_sync as pis

    index_dir = REPO_ROOT / "docs" / "plans"

    # (rel, expected_target from docs/plans/) — target uses POSIX separators.
    format_cases = [
        ("docs/plans/foo.md", "foo.md"),
        ("docs/plans/2026-09-27-pyproject-single-source-of-truth.md",
         "2026-09-27-pyproject-single-source-of-truth.md"),
        ("docs/adr/ADR-001-mcp-first-architecture.md",
         "../adr/ADR-001-mcp-first-architecture.md"),
        ("docs/superpowers/specs/foo.md", "../superpowers/specs/foo.md"),
        ("docs/superpowers/plans/foo.md", "../superpowers/plans/foo.md"),
        (".claude/decisions/deployability-discipline.md",
         "../../.claude/decisions/deployability-discipline.md"),
    ]
    for rel, expected_target in format_cases:
        rendered = pis._entry_link(rel, "")
        # Markdown link is `[display](target)`.
        assert rendered.endswith(f"]({expected_target})"), (
            f"rel={rel!r}: expected target {expected_target!r}, got {rendered!r}"
        )
        # Display text preserves the full repo-relative path so readers
        # see an absolute-looking identifier.
        assert f"[`{rel}`]" in rendered, (
            f"rel={rel!r}: display text should preserve full path, got {rendered!r}"
        )

    # Resolution cases — only real files. Same-dir cases use PLAN_INDEX's
    # actual neighbours; cross-tree cases use well-known canonical docs.
    resolution_cases = [
        ("docs/plans/AI_FIX_IMPROVEMENT_PLAN.md", "AI_FIX_IMPROVEMENT_PLAN.md"),
        ("docs/adr/ADR-001-mcp-first-architecture.md",
         "../adr/ADR-001-mcp-first-architecture.md"),
        (".claude/decisions/deployability-discipline.md",
         "../../.claude/decisions/deployability-discipline.md"),
    ]
    for rel, expected_target in resolution_cases:
        rendered = pis._entry_link(rel, "")
        resolved = (index_dir / expected_target).resolve()
        assert resolved.exists(), (
            f"rel={rel!r}: rendered link {rendered!r} resolves to "
            f"{resolved} which does not exist on disk"
        )


def test_entry_link_is_dr_branchless() -> None:
    """The function should not have three hand-written branches — using
    ``os.path.relpath(rel, "docs/plans")`` is the canonical fix. This
    test pins the implementation shape so a future refactor doesn't
    re-introduce the original branch bug."""
    import inspect

    from crackerjack.tools import plan_index_sync as pis

    source = inspect.getsource(pis._entry_link)
    # If anyone re-adds explicit branches like `if rel.startswith("docs/"):`
    # this will catch it. The clean fix is a single relpath() call.
    assert "startswith" not in source, (
        f"_entry_link should not have hand-rolled prefix branches; "
        f"found one in:\n{source}"
    )
