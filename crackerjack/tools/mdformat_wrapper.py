from __future__ import annotations

import fnmatch
import shutil
import subprocess
import sys
from pathlib import Path

from ._git_utils import get_git_tracked_files


def should_skip_file(file_path: Path) -> bool:
    skip_patterns = [
        "docs/archive/**",
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
    file_str = file_path
    if any(fnmatch.fnmatch(file_str, pattern) for pattern in skip_patterns):
        return True

    try:
        with file_path.open(encoding="utf-8") as fh:
            first_line = fh.readline()
    except OSError:
        return False
    stripped = first_line.strip()
    return stripped == "---" or (len(stripped) >= 3 and set(stripped) == {"_"})


def main(argv: list[str] | None = None) -> int:
    md_files = get_git_tracked_files("*.md")
    markdown_files = get_git_tracked_files("*.markdown")
    all_files = md_files + markdown_files

    files = [f for f in all_files if not should_skip_file(f)]

    if not files:
        print("No git-tracked markdown files found", file=sys.stderr)
        return 0

    mdformat_bin = Path.cwd() / ".venv" / "bin" / "mdformat"
    if mdformat_bin.exists():
        cmd = [str(mdformat_bin), "--no-codeformatters"]
    else:
        resolved = shutil.which("mdformat")
        cmd = [resolved or "mdformat", "--no-codeformatters"]

    if argv:
        cmd.extend(argv)

    cmd.extend([str(f) for f in files])

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

        needs_formatting = True

        format_result = subprocess.run(
            cmd,
            cwd=Path.cwd(),
            check=False,
            capture_output=True,
            text=True,
        )

        if format_result.stderr:
            print(format_result.stderr, file=sys.stderr)
        if needs_formatting:
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
            return 1
        return 0
    except FileNotFoundError:
        return 127
    except Exception as e:
        print(f"Error running mdformat: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
