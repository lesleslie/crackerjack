from __future__ import annotations

import fnmatch
import shutil
import subprocess
import sys
from pathlib import Path

from ._git_utils import get_git_tracked_files


def should_skip_file(file_path: Path) -> bool:
    skip_patterns = [
        # Per-area archives land under `<area>/.archive/` — match any
        # of them via a recursive glob (`**/.archive/**`) so the new
        # `docs/plans/.archive/`, `docs/specs/.archive/`, etc. are
        # excluded alongside the legacy `docs/archive/` location.
        "**/.archive/**",
        "**/archives/**",
        "*COMPLETE.md",
        "*ANALYSIS.md",
        "*PROGRESS.md",
        "*STATUS.md",
        "*PLAN.md",
        "*SUMMARY.md",
        "CHECKPOINT_*.md",
        "NOTES.md",
        "CLEANUP_*.md",
        "COMPREHENSIVE_*.md",
        "PYPROJECT_*.md",
        "TEST_*.md",
    ]
    file_str = str(file_path)
    if any(fnmatch.fnmatch(file_str, pattern) for pattern in skip_patterns):
        return True

    try:
        with file_path.open(encoding="utf-8") as fh:
            first_line = fh.readline()
    except OSError:
        return False
    stripped = first_line.strip()
    # NOTE: a document whose first line is ``---`` is NOT skipped. That
    # exclusion existed because mdformat 1.0.0 core has no frontmatter
    # support -- it rewrites the fence into a horizontal rule and
    # flattens the YAML into body text, and a plan whose frontmatter
    # stops parsing drops out of PLAN_INDEX.md entirely. The
    # ``mdformat-frontmatter`` plugin preserves the block byte-for-byte,
    # so the exclusion is no longer needed and the fleet's 783
    # frontmatter'd documents can finally be formatted.
    #
    # The underscore clause below is a different rule about a different
    # thing and stays.
    return len(stripped) >= 3 and set(stripped) == {"_"}


def _resolve_mdformat_bin() -> str:
    """Locate the mdformat binary.

    Prefers the repo's own ``.venv`` binary and falls back to whatever
    ``mdformat`` is on ``PATH``.
    """
    mdformat_bin = Path.cwd() / ".venv" / "bin" / "mdformat"
    if mdformat_bin.exists():
        return str(mdformat_bin)
    return shutil.which("mdformat") or "mdformat"


def _build_mdformat_cmd(files: list[Path], argv: list[str] | None) -> list[str]:
    """Assemble the mdformat command line for ``files``.

    ``--number`` preserves the source numbering of ordered lists.
    mdformat's default renders every ordered-list item with the marker
    ``1.``, so a list written ``3. 4.`` becomes ``3. 1.``. In a decision
    record or a plan the number is often a reference rather than
    decoration -- an item numbered 4 becomes 1, and any prose pointing
    at "item 4" points at nothing.

    With ``--number`` mdformat applies consecutive numbering: it keeps
    the first marker of each list and numbers the rest from it. A
    well-formed list is unchanged, a list that continues a count from a
    sibling list is unchanged, and a list that an earlier default-mode
    format pass collapsed to ``1. 1. 1.`` is repaired to ``1. 2. 3.``.
    No marker is ever decreased, so a reference to "item N" still lands
    on the same item.

    The ``--extensions`` flag is deliberately NOT passed. mdformat's CLI
    enables every installed parser extension by default, and naming one
    explicitly *restricts* the enabled set to just that one -- passing
    ``--extensions frontmatter`` silently disables ``tables`` and any
    other extension that happens to be installed. The frontmatter
    extension is verified separately, by
    :func:`_frontmatter_extension_available`.
    """
    cmd = [_resolve_mdformat_bin(), "--no-codeformatters", "--number"]

    if argv:
        cmd.extend(argv)

    cmd.extend([str(f) for f in files])
    return cmd


# Probes whether the environment that will run mdformat has the
# ``frontmatter`` parser extension registered. It runs in a subprocess
# because mdformat is executed as a separate binary: the extension must
# be present in THAT interpreter's site-packages, not in crackerjack's
# own imports.
_FRONTMATTER_PROBE = (
    "import importlib.metadata as m; "
    "print(any(e.name == 'frontmatter' for e in "
    "m.entry_points(group='mdformat.parser_extension')))"
)


def _frontmatter_extension_available(mdformat_bin: str) -> bool:
    """True when the environment that will run mdformat has the plugin.

    mdformat 1.0.0 core has no frontmatter support at all: given a
    document whose first line is ``---`` it rewrites the fence into a
    horizontal rule and flattens the YAML into body text. The
    ``mdformat-frontmatter`` plugin preserves the block byte-for-byte.
    """
    python = Path(mdformat_bin).with_name("python")
    if not python.exists():
        # A mdformat on PATH may live outside a venv. The hook itself
        # runs under the repo's interpreter, so probe that one.
        python = Path(sys.executable)
    if not python.exists():
        return False

    try:
        result = subprocess.run(
            [str(python), "-c", _FRONTMATTER_PROBE],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except OSError, subprocess.SubprocessError:
        return False
    return result.stdout.strip() == "True"


def _frontmatter_documents(files: list[Path]) -> list[Path]:
    """The files whose first line opens a YAML frontmatter block.

    Callers pass every tracked document, not only the ones about to be
    formatted: the skip list removes frontmatter documents before
    formatting, so a scope-limited check would never fire.
    """
    found: list[Path] = []
    for path in files:
        try:
            with path.open(encoding="utf-8") as fh:
                if fh.readline().strip() == "---":
                    found.append(path)
        except OSError:
            continue
    return found


def _report_auto_formatted(files: list[Path]) -> None:
    """Report the files mdformat just rewrote."""
    # Silent auto-format path: surface what was changed so the
    # next "mdformat (failed)" message has substance.
    #
    # Two downstream parsers both see this output:
    #
    # 1. ``crackerjack/parsers/regex_parsers.py`` (regex parser).
    #    Returns 0 issues because the success marker ``✓`` and
    #    the substring ``passed`` short-circuit the
    #    ``success_indicators`` check at
    #    ``crackerjack/parsers/regex_parsers.py:326``.
    #
    # 2. ``crackerjack/utils/issue_detection.extract_issue_lines``
    #    (line-counting safety net). The ``✓`` prefix hits the
    #    ``_SUCCESS_PREFIXES`` filter at
    #    ``crackerjack/utils/issue_detection.py:11`` so each
    #    diagnostic line is excluded from the count.
    #
    # The literal ``files were modified by this hook`` substring
    # is also emitted because
    # ``crackerjack/executors/hook_executor.py:802`` requires
    # it for any hook marked ``is_formatting=True`` that exits 1:
    # without it the panel re-routes exit-1 to status="failed".
    try:
        diff = subprocess.run(
            ["git", "diff", "--name-only"] + [str(f) for f in files],
            cwd=Path.cwd(),
            capture_output=True,
            text=True,
            check=False,
        )
        changed = [line for line in diff.stdout.splitlines() if line.strip()]
        print(
            f"✓ mdformat: PASSED hook after auto-formatted "
            f"{len(changed)} file(s) (re-run to confirm clean "
            f"state): files were modified by this hook",
            file=sys.stderr,
        )
        for line in changed:
            print(f"✓   {line}", file=sys.stderr)
    except Exception:
        # don't crash the hook just because git wasn't available
        print(
            "✓ mdformat: PASSED hook after auto-formatted "
            "<unknown> (git unavailable): files were modified "
            "by this hook",
            file=sys.stderr,
        )


def main(argv: list[str] | None = None) -> int:
    md_files = get_git_tracked_files("*.md")
    markdown_files = get_git_tracked_files("*.markdown")
    all_files = md_files + markdown_files

    # Fail loud rather than silently destroy frontmatter.
    #
    # mdformat 1.0.0 core rewrites a document's `---` YAML frontmatter
    # fence into a horizontal rule and flattens the YAML into body
    # text. A plan whose frontmatter is mangled can then fail
    # extraction and disappear from PLAN_INDEX.md, making its lifecycle
    # state invisible.
    #
    # The check scans every tracked document, not just the ones in
    # scope, and it runs BEFORE the "nothing to do" short-circuit. The
    # skip list still excludes documents by other rules (archive paths,
    # `*PLAN.md`), so a scope-limited check would miss a frontmatter'd
    # document that this run would not have formatted anyway, and a
    # later check would never fire at all when the scope is empty.
    # Scoping it to `all_files` makes it a live assertion of the safety
    # property over the whole tracked tree.
    #
    # The guard predates the lift of the frontmatter skip and is kept
    # unchanged by it. It is now the thing that makes the lift safe:
    # if the plugin is ever missing from the environment that will run
    # mdformat, the run stops instead of flattening 783 documents'
    # frontmatter into body text.
    if _frontmatter_documents(all_files) and not _frontmatter_extension_available(
        _resolve_mdformat_bin()
    ):
        print(
            "mdformat: the 'frontmatter' parser extension is not installed in "
            "the environment that will run mdformat. Without it mdformat "
            "rewrites YAML frontmatter into body text, which can drop a "
            "document out of the plan index. Run 'uv sync --all-groups' in "
            "the repo (crackerjack declares mdformat-frontmatter) and retry.",
            file=sys.stderr,
        )
        return 1

    files = [f for f in all_files if not should_skip_file(f)]

    if not files:
        print("No git-tracked markdown files found", file=sys.stderr)
        return 0

    cmd = _build_mdformat_cmd(files, argv)

    try:
        check_cmd = [*cmd, "--check"]
        check_result = subprocess.run(
            check_cmd,
            cwd=Path.cwd(),
            check=False,
            capture_output=True,
            text=True,
        )

        if check_result.returncode == 0:
            return 0

        format_result = subprocess.run(
            cmd,
            cwd=Path.cwd(),
            check=False,
            capture_output=True,
            text=True,
        )

        if format_result.stderr:
            print(format_result.stderr, file=sys.stderr)
        _report_auto_formatted(files)
        return 1
    except FileNotFoundError:
        return 127
    except Exception as e:
        print(f"Error running mdformat: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
