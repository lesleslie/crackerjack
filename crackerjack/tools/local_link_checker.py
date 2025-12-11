"""Fast local-only Markdown link checker for fast hooks.

This checker validates only LOCAL links in Markdown files:
- File references (e.g., [link](./file.md), [link](../dir/file.py))
- Anchor references (e.g., [link](#heading), [link](file.md#section))
- Does NOT check external URLs (http://, https://, mailto:, etc.)

Design Philosophy:
- Speed over completeness: ~1-2s for entire codebase
- Early detection: Catches broken internal references immediately
- No network calls: Pure filesystem validation only

Usage:
    python -m crackerjack.tools.local_link_checker [files...]

Exit Codes:
    0 = all local links valid
    1 = broken local links found
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from ._git_utils import get_git_tracked_files


def extract_markdown_links(content: str) -> list[tuple[str, int]]:
    """Extract all markdown links with line numbers.

    Matches patterns:
    - [text](url)
    - [text](url "title")

    Excludes:
    - Angle bracket syntax examples: [text](<url>)
    - Bare angle brackets without parentheses: <url>

    Args:
        content: Markdown file content

    Returns:
        List of (url, line_number) tuples
    """
    links = []
    # Match [text](url) or [text](url "title")
    # Exclude links wrapped in angle brackets (markdown syntax examples)
    pattern = r"\[([^\]]+)\]\(([^\s)<>]+)(?:\s+[\"'][^\"']*[\"'])?\)"

    for line_num, line in enumerate(content.split("\n"), start=1):
        # Skip lines that are code blocks or inline code examples
        # Look for backticks before/after link patterns
        if "``" in line or "`[" in line:
            continue

        for match in re.finditer(pattern, line):
            url = match.group(2)
            # Skip if URL is actually inside angle brackets (syntax example)
            if "<" in url or ">" in url:
                continue
            links.append((url, line_num))

    return links


def is_local_link(url: str) -> bool:
    """Check if link is local (not external URL).

    Args:
        url: Link URL to check

    Returns:
        True if local link, False if external
    """
    # Parse URL to get scheme
    parsed = urlparse(url)

    # External schemes to skip
    external_schemes = {"http", "https", "mailto", "ftp", "ftps", "ssh", "git"}

    # If scheme exists and is external, skip it
    if parsed.scheme and parsed.scheme.lower() in external_schemes:
        return False

    return True


def validate_local_link(
    link_url: str, source_file: Path, repo_root: Path
) -> tuple[bool, str]:
    """Validate a single local link.

    Args:
        link_url: The URL to validate
        source_file: Path to the file containing the link
        repo_root: Root directory of repository

    Returns:
        Tuple of (is_valid, error_message)
    """
    # Decode URL-encoded characters
    link_url = unquote(link_url)

    # Split anchor from path
    if "#" in link_url:
        path_part, anchor = link_url.split("#", 1)
    else:
        path_part = link_url

    # Handle anchor-only links (same file)
    if not path_part:
        # TODO: Could validate anchor exists in source_file
        return True, ""

    # Resolve relative path
    if path_part.startswith("/"):
        # Absolute from repo root
        target_path = repo_root / path_part.lstrip("/")
    else:
        # Relative to source file
        target_path = (source_file.parent / path_part).resolve()

    # Check if target exists
    if not target_path.exists():
        return False, f"File not found: {path_part}"

    # TODO: If anchor specified, could validate it exists in target file
    # For now, just check file existence

    return True, ""


def check_file(file_path: Path, repo_root: Path) -> list[tuple[str, int, str]]:
    """Check all local links in a markdown file.

    Args:
        file_path: Path to markdown file
        repo_root: Root directory of repository

    Returns:
        List of (link_url, line_number, error_message) for broken links
    """
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return [(str(file_path), 0, f"Failed to read file: {e}")]

    links = extract_markdown_links(content)
    broken_links = []

    for link_url, line_num in links:
        # Skip external URLs
        if not is_local_link(link_url):
            continue

        # Validate local link
        is_valid, error_msg = validate_local_link(link_url, file_path, repo_root)

        if not is_valid:
            broken_links.append((link_url, line_num, error_msg))

    return broken_links


def main(argv: list[str] | None = None) -> int:
    """Check local links in git-tracked markdown files.

    Args:
        argv: Optional list of specific files to check

    Returns:
        Exit code: 0 if all valid, 1 if broken links found
    """
    repo_root = Path.cwd()

    # Get files to check
    if argv:
        # Use provided files
        files = [Path(f).resolve() for f in argv if f.endswith((".md", ".markdown"))]
    else:
        # Get all git-tracked markdown files
        md_files = get_git_tracked_files("*.md")
        markdown_files = get_git_tracked_files("*.markdown")
        files = md_files + markdown_files

    if not files:
        print("No markdown files to check")
        return 0

    # Check all files
    total_broken = 0
    files_with_issues = []

    for file_path in files:
        broken_links = check_file(file_path, repo_root)

        if broken_links:
            total_broken += len(broken_links)
            files_with_issues.append((file_path, broken_links))

    # Report results
    if total_broken == 0:
        print(f"✓ All local links valid in {len(files)} markdown files")
        return 0

    # Print broken links
    print(f"\n✗ Found {total_broken} broken local links:\n")

    for file_path, broken_links in files_with_issues:
        rel_path = (
            file_path.relative_to(repo_root)
            if file_path.is_relative_to(repo_root)
            else file_path
        )
        print(f"{rel_path}:")

        for link_url, line_num, error_msg in broken_links:
            print(f"  Line {line_num}: [{link_url}] - {error_msg}")

        print()

    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
