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
        "Docs: specs",
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
        "docs/specs/",
        "docs/plans/",
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
        ("docs/specs/foo.md", "../specs/foo.md"),
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
        ("docs/plans/2026-05-20-phase-0-event-bus-plan.md",
         "2026-05-20-phase-0-event-bus-plan.md"),
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


# ---------------------------------------------------------------------------
# Output formatting helpers — _display_path and _format_bytes
# ---------------------------------------------------------------------------


def test_display_path_strips_cwd_prefix() -> None:
    """An absolute path under cwd renders as the repo-relative form.

    Prevents leaking the local filesystem layout (e.g.
    ``/Users/les/Projects/<repo>/...``) into shared logs and terminals.
    """
    from crackerjack.tools import plan_index_sync as pis

    inside = REPO_ROOT / "docs" / "plans" / "PLAN_INDEX.md"
    out = pis._display_path(inside)
    assert out == "docs/plans/PLAN_INDEX.md"
    assert "/Users/les" not in out
    assert str(REPO_ROOT) not in out


def test_display_path_falls_back_to_absolute_outside_cwd(tmp_path: Path) -> None:
    """A path outside cwd falls back to the absolute form (no crash)."""
    from crackerjack.tools import plan_index_sync as pis

    outside = tmp_path / "elsewhere.md"
    out = pis._display_path(outside)
    assert out == str(outside)


def test_display_path_already_relative_passes_through() -> None:
    """A path already relative to cwd is returned unchanged."""
    from crackerjack.tools import plan_index_sync as pis

    rel = Path("docs/plans/PLAN_INDEX.md")
    out = pis._display_path(rel)
    assert out == "docs/plans/PLAN_INDEX.md"


def test_format_bytes_below_one_kib() -> None:
    """Sub-KiB values render as plain bytes."""
    from crackerjack.tools import plan_index_sync as pis

    for n, expected in [(0, "0 B"), (1, "1 B"), (742, "742 B"), (1023, "1023 B")]:
        assert pis._format_bytes(n) == expected, f"failed for {n}"


def test_format_bytes_kib_boundary() -> None:
    """KiB boundary: 1024 bytes renders as '1.0 KB'."""
    from crackerjack.tools import plan_index_sync as pis

    assert pis._format_bytes(1024) == "1.0 KB"


def test_format_bytes_realistic_plan_index_size() -> None:
    """21800 bytes (the size from the user's report) renders as '21.3 KB'."""
    from crackerjack.tools import plan_index_sync as pis

    assert pis._format_bytes(21800) == "21.3 KB"


def test_format_bytes_mib_and_above() -> None:
    """Values >= 1 MiB render with one decimal in MB."""
    from crackerjack.tools import plan_index_sync as pis

    assert pis._format_bytes(1024 * 1024) == "1.0 MB"
    assert pis._format_bytes(int(1.5 * 1024 * 1024)) == "1.5 MB"
    assert pis._format_bytes(5 * 1024 * 1024) == "5.0 MB"


def test_dry_run_output_uses_relative_path_and_kb(capsys: pytest.CaptureFixture[str]) -> None:
    """End-to-end: dry-run output line strips cwd prefix and shows KB units.

    Mirrors the user's report (``wrote /Users/les/Projects/<repo>/docs/plans/
    PLAN_INDEX.md (21800 bytes)``) — verify the new format omits the local
    path prefix and expresses bytes in KB.
    """
    from crackerjack.tools import plan_index_sync as pis

    # Force a non-empty change to trigger the `would rewrite` branch.
    rendered = pis.render_plan_index(REPO_ROOT)

    tampered = rendered + "\n<!-- tampered for test -->\n"
    target = REPO_ROOT / "docs" / "plans" / "PLAN_INDEX.md"
    original = target.read_text(encoding="utf-8")
    target.write_text(tampered, encoding="utf-8")
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                TOOL_MODULE,
                "--repo-root",
                str(REPO_ROOT),
                "--out",
                str(target),
                "--dry-run",
            ],
            check=False,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
        )
    finally:
        target.write_text(original, encoding="utf-8")

    assert result.returncode == 1, f"expected drift exit, got {result.returncode}"
    out = result.stdout
    assert "would rewrite" in out
    # Local path prefix must NOT appear.
    assert "/Users/les" not in out
    assert str(REPO_ROOT) + "/" not in out
    # Path should be the repo-relative form.
    assert "docs/plans/PLAN_INDEX.md" in out
    # Raw byte counts should be replaced by KB.
    assert "bytes" not in out
    assert "KB" in out


# ---------------------------------------------------------------------------
# Git-aware discovery — `_tracked_md_names` + `_discover_files`
# ---------------------------------------------------------------------------


def test_tracked_md_names_returns_none_when_git_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``_tracked_md_names`` returns ``None`` when git is unavailable.

    Lets the caller fall back to ``pathlib.rglob`` so non-git test
    fixtures (and any future ad-hoc invocation outside a repo) still
    see every file on disk. Pinned because the silent ``return None``
    contract is the difference between "filter is active" and "filter
    skipped — run everything".
    """
    from crackerjack.tools import plan_index_sync as pis

    monkeypatch.setattr(
        "crackerjack.tools.plan_index_sync.subprocess.run",
        _raise_file_not_found,
    )
    assert pis._tracked_md_names(REPO_ROOT, "docs/plans/") is None


def test_tracked_md_names_returns_set_of_tracked_paths() -> None:
    """``_tracked_md_names`` returns a ``set[str]`` of repo-relative paths
    ending in ``.md`` / ``.markdown`` for the scoped store."""
    from crackerjack.tools import plan_index_sync as pis

    out = pis._tracked_md_names(REPO_ROOT, "docs/plans/")
    assert isinstance(out, set)
    # All returned names are markdown files under the store.
    for name in out:
        assert name.startswith("docs/plans/"), name
        assert name.endswith((".md", ".markdown")), name
    # At least one tracked plan exists in this repo.
    assert any(name.endswith(".md") for name in out)


def test_discover_files_excludes_untracked_in_git_repo(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``_discover_files`` excludes untracked ``.md`` files when git is
    available. This is the root-cause fix for the latent bug where a
    stray untracked ``.claude/decisions/README.md`` got indexed into
    ``PLAN_INDEX.md``, then the rendered link failed
    ``check-local-links`` on fresh clones.
    """
    from crackerjack.tools import plan_index_sync as pis

    store = tmp_path / "store"
    store.mkdir()
    tracked = store / "tracked.md"
    tracked.write_text("---\ntitle: T\n---\n# T\n", encoding="utf-8")
    untracked = store / "untracked.md"
    untracked.write_text("---\ntitle: U\n---\n# U\n", encoding="utf-8")

    monkeypatch.setattr(
        pis,
        "_tracked_md_names",
        lambda repo_root, store_rel: {str(tracked.relative_to(repo_root).as_posix())},
    )

    found = pis._discover_files(tmp_path, "store/")
    rels = sorted(rel for _, rel in found)
    assert rels == ["store/tracked.md"]


def test_discover_files_falls_back_to_rglob_when_git_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When ``_tracked_md_names`` returns ``None`` (git unavailable),
    ``_discover_files`` falls back to ``pathlib.rglob`` and sees every
    file. Keeps non-git test fixtures working.
    """
    from crackerjack.tools import plan_index_sync as pis

    store = tmp_path / "store"
    store.mkdir()
    (store / "a.md").write_text("---\ntitle: A\n---\n# A\n", encoding="utf-8")
    (store / "b.md").write_text("---\ntitle: B\n---\n# B\n", encoding="utf-8")

    monkeypatch.setattr(pis, "_tracked_md_names", lambda *_: None)

    found = pis._discover_files(tmp_path, "store/")
    rels = sorted(rel for _, rel in found)
    assert rels == ["store/a.md", "store/b.md"]


def _raise_file_not_found(*_args: object, **_kwargs: object) -> object:
    raise FileNotFoundError(2, "No such file or directory: 'git'")


def test_dry_run_translates_to_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """crackerjack's --dry-run flag must translate to oneiric.plan_index.regenerate(check=True).

    Invokes the dispatcher module DIRECTLY (NOT ``crackerjack run``). The
    ``crackerjack run`` CLI does not bind ``--repo-root`` (``grep`` of
    ``crackerjack/cli/options.py`` and ``crackerjack/__main__.py:806``
    confirms); ``PhaseCoordinator`` constructs ``--repo-root`` itself from
    ``process.cwd`` (``crackerjack/core/phase_coordinator.py:858``).
    Calling ``crackerjack run --plan-index-sync --dry-run --repo-root
    <tmp>`` would silently ignore the ``--repo-root`` flag and run against
    the worktree's cwd, NOT against ``tmp_path``. Mirror the existing
    pattern at ``crackerjack/tests/unit/test_plan_index_sync.py:18`` (the
    ``_tool_help()`` probe) — direct module invocation only.

    NOTE: env var is ``CRACKERJACK_DOCUMENTATION__USE_SHARED_REGENERATOR``
    (not ``CRACKERJACK_DOCS__...``). The crackerjack env-overlay at
    ``crackerjack/config/loader.py:25`` splits on ``__`` and looks the
    section up in ``CrackerjackSettings.model_fields``; the top-level
    field is ``documentation`` (``docs`` is not an alias), so the brief
    env-var spelling would silently no-op.
    """
    monkeypatch.setenv("CRACKERJACK_DOCUMENTATION__USE_SHARED_REGENERATOR", "true")
    docs = tmp_path / "docs" / "plans"
    docs.mkdir(parents=True)
    (docs / "foo.md").write_text("---\nstatus: active\n---\n# Foo\n", encoding="utf-8")
    # Run the dispatcher module directly with --dry-run
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            TOOL_MODULE,
            "--repo-root",
            str(tmp_path),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=REPO_ROOT,
    )
    # exit 0 = no drift, exit 1 = drift (either is valid; key is no exception)
    assert result.returncode in (0, 1), result.stderr
