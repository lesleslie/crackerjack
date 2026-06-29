from __future__ import annotations

import argparse
import operator
import re
import subprocess
import sys
from contextlib import suppress
from dataclasses import dataclass, field
from pathlib import Path

from ._git_utils import get_git_tracked_files

# ty concise output format:
#   <file>:<line>:<col>: <level>[<code>] <message>
# Examples:
#   foo.py:10:5: warning[unused-type-ignore-comment] Unused blanket `type: ignore` directive
#   foo.py:42:9: warning[redundant-cast] Value is already of type `bool`
_TY_OUTPUT_RE = re.compile(
    r"^(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+):\s+"
    r"(?P<level>error|warning)\[(?P<code>[a-z0-9-]+)\]\s+"
    r"(?P<message>.+)$"
)

# Warning codes this tool auto-fixes. Pure cleanup only — never touch errors.
AUTO_FIX_CODES: frozenset[str] = frozenset(
    {
        "unused-type-ignore-comment",
        "redundant-cast",
    }
)

# Regex matching a trailing ``# type: ignore[code]`` (or blank ``# type: ignore``) comment.  # ty: ignore[invalid-ignore-comment]
# Anchored to the right-hand side of a logical line. The directive must appear at end
# of line to qualify, so we don't accidentally strip in-line ignore comments that
# precede other code.
_TYPE_IGNORE_RE = re.compile(
    r"(?P<lead>[ \t]*#\s*type:\s*ignore"
    r"(?:\[[^\]]*\])?)"
    r"[ \t]*(?:#.*)?"
    r"[ \t]*$"
)

# Regex for a redundant `cast(T, expr)` call — we only need to locate it precisely.
# Matches `cast(` as a function call identifier followed by an opening paren.
_REDUNDANT_CAST_RE = re.compile(r"\bcast\s*\(")


@dataclass
class FixSite:
    """One concrete site to remove from a source file.

    For ``unused-type-ignore-comment`` sites, ``start`` and ``end`` are character
    offsets into the file (0-indexed, ``end`` exclusive) covering the directive
    plus its trailing newline if present.

    For ``redundant-cast`` sites, ``start``/``end`` cover the entire ``cast(``
    identifier-and-paren span — the matching close paren is resolved later during
    the rewrite pass.
    """

    file: Path
    line: int
    col: int
    code: str
    message: str
    start: int = 0
    end: int = 0
    raw_match: str = ""


@dataclass
class FileEdits:
    """Aggregated edits for a single file.

    ``replacements`` is a list of ``(start, end, new_text)`` tuples. ``new_text``
    of ``""`` means a pure deletion. Applied right-to-left so offsets stay stable.
    """

    path: Path
    replacements: list[tuple[int, int, str]] = field(default_factory=list)
    sites: list[FixSite] = field(default_factory=list)

    def add(self, start: int, end: int, new_text: str, site: FixSite) -> None:
        self.replacements.append((start, end, new_text))
        self.sites.append(site)

    def is_empty(self) -> bool:
        return not self.replacements


def run_ty(package_root: Path) -> list[FixSite]:
    """Run ty in concise mode and return parseable cleanup sites.

    ty exit code is non-zero whenever there are findings; we only care about
    stdout. Falls back to an empty list on subprocess failure (ty missing,
    etc.) — the autofix coordinator will simply see "nothing to do".
    """

    try:
        proc = subprocess.run(
            [
                "ty",
                "check",
                "--output-format",
                "concise",
                "--no-progress",
                f"./{package_root.name}",
            ],
            capture_output=True,
            text=True,
            cwd=package_root.parent,
            check=False,
        )
    except FileNotFoundError:
        return []
    except OSError:
        return []

    sites: list[FixSite] = []
    for raw_line in proc.stdout.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        match = _TY_OUTPUT_RE.match(line)
        if not match:
            continue

        code = match["code"]
        if code not in AUTO_FIX_CODES:
            continue

        file_path = (package_root.parent / match["file"]).resolve()
        sites.append(
            FixSite(
                file=file_path,
                line=int(match["line"]),
                col=int(match["col"]),
                code=code,
                message=match["message"],
            )
        )

    return sites


def _line_starts(content: str) -> list[int]:
    """Return the character offset where each 1-indexed line begins."""

    starts = [0]
    for idx, ch in enumerate(content):
        if ch == "\n":
            starts.append(idx + 1)
    return starts


def _resolve_unused_type_ignore(
    content: str,
    line_starts: list[int],
    site: FixSite,
) -> tuple[int, int, str] | None:
    """Find the ``# type: ignore`` directive on ``site.line`` and return offsets.

    Returns ``(start, end, "")`` so the caller can splice the directive (plus its
    trailing newline if the directive was the only content on the line) out of the
    file. Returns ``None`` if the directive can't be located — that means the
    source has drifted since ty flagged it, and we should silently skip.
    """

    line_no = site.line
    if line_no < 1 or line_no >= len(line_starts) + 1:
        return None

    line_start = line_starts[line_no - 1]
    if line_no - 1 < len(line_starts) - 1:
        line_end = line_starts[line_no]
    else:
        line_end = len(content)

    line = content[line_start:line_end]
    match = _TYPE_IGNORE_RE.search(line)
    if not match:
        return None

    directive_start = line_start + match.start("lead")
    directive_end = line_start + match.end("lead")

    # If the directive is the only non-whitespace content on the line, drop the
    # whole line (including the newline). Otherwise preserve the leading code.
    stripped = line[: match.start("lead")].strip()
    if not stripped:
        if line.endswith("\n"):
            return (directive_start, line_start + len(line), "")
        return (line_start, line_start + len(line), "")

    return (directive_start, directive_end, "")


def _find_cast_close_paren(line: str, open_paren: int) -> int:
    """Return the index just past the ``)`` that closes ``open_paren``.

    Walks forward tracking nesting depth and string state. Returns ``-1`` if
    the close paren is missing or the line ends first.
    """
    depth = 0
    i = open_paren
    in_str: str | None = None
    while i < len(line):
        ch = line[i]
        if in_str is not None:
            if ch == "\\" and i + 1 < len(line):
                i += 2
                continue
            if ch == in_str:
                in_str = None
        else:
            if ch in ('"', "'"):
                in_str = ch
            elif ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    return i + 1
        i += 1
    return -1


def _find_first_top_level_comma(inner: str) -> int:
    """Return the index of the first comma at depth 0, or ``-1``."""
    depth = 0
    in_str: str | None = None
    for j, ch in enumerate(inner):
        if in_str is not None:
            if ch == "\\" and j + 1 < len(inner):
                # Skip escaped char; loop still advances via the `for` step.
                continue
            if ch == in_str:
                in_str = None
            continue
        if ch in ('"', "'"):
            in_str = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            return j
    return -1


def _resolve_redundant_cast(
    content: str,
    line_starts: list[int],
    site: FixSite,
) -> tuple[int, int, str] | None:
    """Return offsets for replacing ``cast(T, x)`` with just ``x``.

    The rewrite preserves the original argument expression and its trailing
    comma. Returns ``None`` if parens can't be balanced (source drifted).
    """

    line_no = site.line
    if line_no < 1 or line_no >= len(line_starts) + 1:
        return None

    line_start = line_starts[line_no - 1]
    line_end = (
        line_starts[line_no] if line_no - 1 < len(line_starts) - 1 else len(content)
    )
    line = content[line_start:line_end]

    # Find the `cast(` token at or near the column ty reported.
    candidates: list[int] = [m.start() for m in _REDUNDANT_CAST_RE.finditer(line)]
    if not candidates:
        return None

    col_idx = max(0, site.col - 1)
    pick = min(candidates, key=lambda pos: abs(pos - col_idx))
    open_paren = line.find("(", pick)
    if open_paren < 0:
        return None

    close_paren_end = _find_cast_close_paren(line, open_paren)
    if close_paren_end <= 0:
        return None
    i = close_paren_end - 1  # index of the ``)`` itself

    inner = line[open_paren + 1 : i]
    # inner looks like "TYPE, EXPR". Strip the first comma-separated token.
    split = _find_first_top_level_comma(inner)
    if split < 0:
        return None

    expr = inner[split + 1 :].lstrip()
    if not expr:
        return None

    abs_start = line_start + pick
    abs_end = line_start + i + 1
    return (abs_start, abs_end, expr)


def _resolve_site(
    content: str,
    line_starts: list[int],
    site: FixSite,
) -> tuple[int, int, str] | None:
    if site.code == "unused-type-ignore-comment":
        return _resolve_unused_type_ignore(content, line_starts, site)
    if site.code == "redundant-cast":
        return _resolve_redundant_cast(content, line_starts, site)
    return None


def plan_edits(
    sites: list[FixSite],
    root: Path,
) -> dict[Path, FileEdits]:
    """Group sites by file and resolve each into concrete character offsets."""

    files: dict[Path, FileEdits] = {}
    cache: dict[Path, tuple[str, list[int]]] = {}

    for site in sites:
        if not site.file.exists():
            continue

        if site.file not in cache:
            try:
                content = site.file.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            cache[site.file] = (content, _line_starts(content))

        content, line_starts = cache[site.file]
        resolved = _resolve_site(content, line_starts, site)
        if resolved is None:
            continue

        start, end, new_text = resolved
        # Defensive: skip overlapping edits inside the same file.
        edits = files.setdefault(site.file, FileEdits(path=site.file))
        for prev_start, prev_end, _ in edits.replacements:
            if start < prev_end and end > prev_start:
                break
        else:
            edits.add(start, end, new_text, site)
            site.start, site.end, site.raw_match = start, end, content[start:end]

    return files


def apply_edits(file_edits: FileEdits) -> bool:
    """Apply replacements to the file in-place. Returns True if changed."""

    if file_edits.is_empty():
        return False

    try:
        content = file_edits.path.read_text(encoding="utf-8")
    except OSError:
        return False

    # Apply right-to-left so earlier offsets remain valid.
    for start, end, new_text in sorted(
        file_edits.replacements, key=operator.itemgetter(0), reverse=True
    ):
        content = content[:start] + new_text + content[end:]

    try:
        file_edits.path.write_text(content, encoding="utf-8")
    except OSError:
        return False
    return True


def describe_site(site: FixSite) -> str:
    rel = site.file
    with suppress(ValueError):
        rel = site.file.relative_to(Path.cwd())
    snippet = site.raw_match.strip()
    if len(snippet) > 80:
        snippet = snippet[:77] + "..."
    return f"{rel}:{site.line}:{site.col} [{site.code}] -> remove {snippet!r}"


def _collect_files() -> list[Path]:
    """Default to git-tracked Python files (mirrors other tools)."""

    files = get_git_tracked_files("*.py")
    return [f for f in files if f.is_file()]


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Remove unused `# type: ignore` directives and redundant `cast()` "
            "calls flagged by ty. Pure cleanup only."
        ),
    )
    parser.add_argument(
        "--package",
        type=Path,
        default=Path("crackerjack"),
        help="Package directory to scan (default: ./crackerjack)",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(),
        help="Project root (default: current directory)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be removed without modifying files",
    )
    parser.add_argument(
        "--files",
        nargs="*",
        type=Path,
        default=None,
        help="Restrict scan to these files (default: all git-tracked *.py)",
    )
    return parser


def _restrict_to_scope(
    sites: list[FixSite], files_arg: list[Path] | None
) -> list[FixSite]:
    """Filter ``sites`` to the user's requested scope (--files or git-tracked)."""
    if files_arg:
        allowed = {p.resolve() for p in files_arg}
        return [s for s in sites if s.file.resolve() in allowed]

    # When the user doesn't restrict --files, restrict to git-tracked Python
    # so we don't accidentally try to edit virtualenv / build artifacts that
    # ty may have scanned inside the package directory.
    tracked = {p.resolve() for p in _collect_files()}
    if not tracked:
        return sites
    return [s for s in sites if s.file.resolve() in tracked]


def _describe_planned_edits(file_edits: dict[Path, FileEdits]) -> int:
    """Print one line per fix in stable order. Returns total count."""
    total = 0
    for fe in sorted(file_edits.values(), key=lambda fe: str(fe.path)):
        for site in sorted(fe.sites, key=lambda s: (s.line, s.col)):
            print(describe_site(site))
            total += 1
    return total


def _apply_all_edits(file_edits: dict[Path, FileEdits]) -> int:
    """Apply each file's edits in place. Returns the number of files changed."""
    changed = 0
    for fe in file_edits.values():
        if apply_edits(fe):
            changed += 1
    return changed


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    package_root = (args.root / args.package).resolve()
    if not package_root.is_dir():
        print(f"error: package not found: {package_root}", file=sys.stderr)
        return 2

    sites = run_ty(package_root)
    if not sites:
        print("No ty cleanup candidates found.")
        return 0

    sites = _restrict_to_scope(sites, args.files)
    if not sites:
        print("No ty cleanup candidates in scope.")
        return 0

    file_edits = plan_edits(sites, args.root.resolve())
    total = _describe_planned_edits(file_edits)

    if args.dry_run:
        print(
            f"\n[dry-run] {total} change(s) would be applied across {len(file_edits)} file(s)"
        )
        return 1 if total else 0

    changed = _apply_all_edits(file_edits)
    print(f"\nApplied {total} change(s) across {changed} file(s)")
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main())
