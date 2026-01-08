from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

from ._git_utils import get_git_tracked_files


def extract_markdown_links(content: str) -> list[tuple[str, int]]:
    links = []

    pattern = r"\[([^\]]+)\]\(([^\s)<>]+)(?:\s+[\"'][^\"']*[\"'])?\)"

    in_code_block = False

    for line_num, line in enumerate(content.split("\n"), start=1):
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        if "`]" in line or "`[" in line or "``" in line:
            continue

        for match in re.finditer(pattern, line):
            url = match.group(2)

            if "<" in url or ">" in url:
                continue
            links.append((url, line_num))

    return links


def is_local_link(url: str) -> bool:
    parsed = urlparse(url)

    external_schemes = {"http", "https", "mailto", "ftp", "ftps", "ssh", "git"}

    if parsed.scheme and parsed.scheme.lower() in external_schemes:
        return False

    return True


def validate_local_link(
    link_url: str, source_file: Path, repo_root: Path
) -> tuple[bool, str]:
    link_url = unquote(link_url)

    if "#" in link_url:
        path_part, anchor = link_url.split("#", 1)
    else:
        path_part = link_url

    if not path_part:
        # TODO: Could validate anchor exists in source_file
        return True, ""

    if path_part.startswith("/"):
        target_path = repo_root / path_part.lstrip("/")
    else:
        target_path = (source_file.parent / path_part).resolve()

    if not target_path.exists():
        return False, f"File not found: {path_part}"

    # TODO: If anchor specified, could validate it exists in target file

    return True, ""


def check_file(file_path: Path, repo_root: Path) -> list[tuple[str, int, str]]:
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return [(str(file_path), 0, f"Failed to read file: {e}")]

    links = extract_markdown_links(content)
    broken_links = []

    for link_url, line_num in links:
        if not is_local_link(link_url):
            continue

        is_valid, error_msg = validate_local_link(link_url, file_path, repo_root)

        if not is_valid:
            broken_links.append((link_url, line_num, error_msg))

    return broken_links


def main(argv: list[str] | None = None) -> int:
    repo_root = Path.cwd()

    if argv:
        files = [Path(f).resolve() for f in argv if f.endswith((".md", ".markdown"))]
    else:
        md_files = get_git_tracked_files("*.md")
        markdown_files = get_git_tracked_files("*.markdown")
        files = md_files + markdown_files

    if not files:
        print("No markdown files to check")
        return 0

    total_broken = 0
    files_with_issues = []

    for file_path in files:
        broken_links = check_file(file_path, repo_root)

        if broken_links:
            total_broken += len(broken_links)
            files_with_issues.append((file_path, broken_links))

    if total_broken == 0:
        print(f"✓ All local links valid in {len(files)} markdown files")
        return 0

    print(f"\n✗ Found {total_broken} broken local links:\n")

    for file_path, broken_links in files_with_issues:
        rel_path = (
            file_path.relative_to(repo_root)
            if file_path.is_relative_to(repo_root)
            else file_path
        )
        print(f"{rel_path}:")

        for link_url, line_num, error_msg in broken_links:
            print(f" Line {line_num}: [{link_url}] - {error_msg}")

        print()

    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
