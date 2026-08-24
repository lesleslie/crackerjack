from __future__ import annotations

import fnmatch
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

ARCHIVE_PATTERNS = [
    "*PLAN*.md",
    "*SUMMARY*.md",
    "*ANALYSIS*.md",
    "*MIGRATION*.md",
    "*PROGRESS*.md",
    "SPRINT*.md",
    "PHASE*.md",
    "*CLEANUP*.md",
    "*CONFIG*.md",
    "*PERFORMANCE*.md",
]


def is_archived_filename(filename: str) -> bool:
    return any(fnmatch.fnmatch(filename, pattern) for pattern in ARCHIVE_PATTERNS)


def extract_markdown_links(content: str) -> list[tuple[str, int]]:
    links = []

    pattern = r"\[([^\]]+)\]\(([^\s)<>]+)(?:\s+[\"'][^\"']*[\"'])?\)"
    inline_code = re.compile(r"`[^`]*`")

    in_code_block = False

    for line_num, line in enumerate(content.split("\n"), start=1):
        if line.strip().startswith("```"):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        # Strip inline code spans (single-backtick delimited) so we don't
        # mistake `` `[name](server)` `` for a markdown link. We preserve
        # the line's column positions for accurate error reporting by
        # replacing the span with the same number of space characters.
        stripped_line = inline_code.sub(
            lambda m: " " * len(m.group(0)),
            line,
        )

        for match in re.finditer(pattern, stripped_line):
            url = match.group(2)

            if "<" in url or ">" in url:
                continue
            links.append((url, line_num))

    return links


def is_local_link(url: str) -> bool:
    parsed = urlparse(url)

    external_schemes = {"http", "https", "mailto", "ftp", "ftps", "ssh", "git"}

    return not (parsed.scheme and parsed.scheme.lower() in external_schemes)


def validate_local_link(
    link_url: str,
    source_file: Path,
    repo_root: Path,
) -> tuple[bool, str]:
    link_url = unquote(link_url)
    path_part = _extract_path_part(link_url)

    if not path_part:
        return True, ""

    target_filename = Path(path_part).name
    if _check_archived_file(target_filename, repo_root):
        return True, ""

    target_path = _resolve_target_path(path_part, source_file, repo_root)

    if not target_path.exists():
        return False, f"File not found: {path_part}"

    return True, ""


def _extract_path_part(link_url: str) -> str:
    if "#" in link_url:
        path_part, _anchor = link_url.split("#", 1)
    else:
        path_part = link_url
    return path_part


def _check_archived_file(filename: str, repo_root: Path) -> bool:
    if not is_archived_filename(filename):
        return False

    archive_path = repo_root / "docs" / "archive"
    if not archive_path.exists():
        return False

    for archived_file in archive_path.rglob(filename):
        if archived_file.is_file():
            return True

    return False


def _resolve_target_path(path_part: str, source_file: Path, repo_root: Path) -> Path:
    if path_part.startswith("/"):
        return repo_root / path_part.lstrip("/")
    return (source_file.parent / path_part).resolve()


def check_file(file_path: Path, repo_root: Path) -> list[tuple[str, int, str]]:
    if file_path.is_symlink():
        return []

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return [(file_path, 0, f"Failed to read file: {e}")]  # type: ignore

    links = extract_markdown_links(content)
    broken_links = []

    for link_url, line_num in links:
        if not is_local_link(link_url):
            continue

        is_valid, error_msg = validate_local_link(link_url, file_path, repo_root)

        if not is_valid:
            broken_links.append((link_url, line_num, error_msg))

    return broken_links


def _list_markdown_via_git(repo_root: Path) -> list[Path]:
    """Return tracked markdown files using ``git ls-files`` directly.

    Bypasses ``get_git_tracked_files`` (and its ``_load_gitignore_spec``
    walk) because git's own path filtering is dramatically faster than
    re-loading every ``.gitignore`` in the repo and matching each
    candidate file with pathspec. On large repos (1000+ docs), the
    python-side filter took ~50s of the ~60s link-checker runtime; this
    path returns in well under a second for the same workload.

    ``git ls-files`` excludes anything git itself considers untracked or
    ignored, which is the same semantics callers expect for "tracked
    markdown files".
    """
    try:
        result = subprocess.run(
            ["git", "ls-files", "-z", "--", "*.md", "*.markdown"],
            capture_output=True,
            check=True,
            cwd=repo_root,
        )
    except subprocess.CalledProcessError, FileNotFoundError:
        return []

    raw = result.stdout
    if isinstance(raw, bytes):  # pragma: no cover - defensive
        raw = raw.decode("utf-8", errors="replace")

    return [
        repo_root / name
        for name in raw.split("\x00")
        if name and not name.startswith("docs/archive/")
    ]


def main(argv: list[str] | None = None) -> int:
    repo_root = Path.cwd()

    if argv:
        files = [Path(f).resolve() for f in argv if f.endswith((".md", ".markdown"))]
    else:
        files = _list_markdown_via_git(repo_root)

    if not files:
        return 0

    total_broken = 0
    files_with_issues = []

    for file_path in files:
        broken_links = check_file(file_path, repo_root)

        if broken_links:
            total_broken += len(broken_links)
            files_with_issues.append((file_path, broken_links))

    if total_broken == 0:
        return 0

    for file_path, broken_links in files_with_issues:
        relative_path = (
            file_path.relative_to(repo_root)
            if file_path.is_relative_to(repo_root)
            else file_path
        )

        for link_url, line_num, error_msg in broken_links:
            print(
                f"{relative_path}:{line_num}: {link_url} - {error_msg}",
                file=sys.stderr,
            )

    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
