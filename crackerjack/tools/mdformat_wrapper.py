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

    # Skip files with YAML frontmatter: mdformat (without mdformat-frontmatter
    # plugin) renders --- as a thematic break and rewrites the whole block
    # as a 70-underscore heading, which corrupts metadata that Crackerjack's
    # own validate_document_frontmatter.py then refuses to parse. Frontmatter
    # is metadata, not document content — formatting it is meaningless and
    # destructive. Detect by reading only the first line.
    try:
        with open(file_path, encoding="utf-8") as fh:
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
        print("No git-tracked markdown files found", file=sys.stderr)  # noqa: T201
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

        format_result = subprocess.run(
            cmd,
            cwd=Path.cwd(),
            check=False,
            capture_output=True,
            text=True,
        )

        if format_result.stdout:
            pass
        if format_result.stderr:
            pass

        files_formatted = format_result.returncode
        if files_formatted:
            if format_result.stderr:
                print(format_result.stderr, file=sys.stderr)  # noqa: T201
            return 1

        return 0
    except FileNotFoundError:
        return 127
    except Exception as e:
        print(f"Error running mdformat: {e}", file=sys.stderr)  # noqa: T201
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
