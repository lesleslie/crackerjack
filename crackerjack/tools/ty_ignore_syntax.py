from __future__ import annotations

import argparse
import io
import re
import sys
import tokenize
from pathlib import Path

from ._git_utils import get_files_by_extension

# A ty suppression is spelled ``ty: ignore[<code>]``. The mypy spelling
# (``type: ignore``) reads like a suppression but suppresses nothing in ty —
# ty does not interpret it — so it is rejected whatever code it names.
#
# Rule-name validity for ``ty: ignore[...]`` is enforced by ty itself: it
# reports ``ignore-comment-unknown-rule`` and exits non-zero for a code it
# does not know. That is why this tool carries no registry of ty rule names.
# A curated list would need updating on every ty rename, and would drift:
# ty 0.0.104 renamed three rules and split a fourth into two.
#
# The leading ``#`` is omitted from the examples above on purpose. ty parses
# the *text* of a comment looking for directives, so a comment that shows the
# hash becomes a malformed directive itself and draws an
# ``invalid-ignore-comment`` warning against this file. Docstrings and string
# literals are not scanned, so the same text is safe there.

RE_MYPY_IGNORE = re.compile(r"^type:\s*ignore\b")
RE_TY_IGNORE = re.compile(r"^ty:\s*ignore\b")
RE_BARE_TYPE_IGNORE = re.compile(r"^type:\s*ignore\s*$")

# A backtick-quoted run. A comment that *documents* a directive writes the
# directive inside backticks, so it is prose about a directive rather than
# a directive.
RE_BACKTICK_RUN = re.compile(r"``[^`]*``|`[^`]*`")


def _mask_backticks(body: str) -> str:
    """Blank out backtick-quoted runs, keeping every offset stable.

    The mask character is not whitespace, so a masked segment cannot be
    mistaken for a directive that starts at its beginning.
    """
    return RE_BACKTICK_RUN.sub(lambda m: "x" * len(m.group(0)), body)


DEFAULT_EXCLUDES: tuple[str, ...] = (
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    ".git",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".crackerjack_cache",
    # The crackerjack tool cache holds a vendored copy of the source, so
    # scanning it would report every finding twice.
    ".crackerjack",
    ".worktrees",
    "htmlcov",
    "site-packages",
)


def _is_excluded(path: Path, exclude_dirs: tuple[str, ...]) -> bool:
    parts = set(path.parts)
    return any(excluded in parts for excluded in exclude_dirs)


def _iter_real_comments(text: str) -> list[tuple[int, str]]:
    comments: list[tuple[int, str]] = []
    try:
        tokens = list(
            tokenize.tokenize(
                io.BytesIO(text.encode("utf-8")).readline,
            )
        )
    except tokenize.TokenError, IndentationError, SyntaxError:
        return comments

    for tok in tokens:
        if tok.type == tokenize.COMMENT:
            comments.append((tok.start[0], tok.string.lstrip("#").lstrip()))
    return comments


def _split_directives(comment_body: str) -> tuple[list[str], list[str]]:
    """Split a comment body into the mypy and ty ignore directives it carries.

    One line can hold more than one directive, for example
    ``# type: ignore[attr-defined]  # ty: ignore[missing-attribute]``.
    ``tokenize`` yields that whole line as a single comment token, so the
    individual directives are separated on the inner ``#`` markers.
    """
    mypy_parts: list[str] = []
    ty_parts: list[str] = []
    for segment in _mask_backticks(comment_body).split("#"):
        stripped = segment.strip()
        if not stripped:
            continue
        if RE_MYPY_IGNORE.match(stripped):
            mypy_parts.append(stripped)
        elif RE_TY_IGNORE.match(stripped):
            ty_parts.append(stripped)
    return mypy_parts, ty_parts


def scan_file(file_path: Path) -> list[tuple[int, str]]:
    try:
        text = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [(0, f"Could not read {file_path}: {exc}")]

    findings: list[tuple[int, str]] = []

    for line_number, comment_body in _iter_real_comments(text):
        mypy_parts, ty_parts = _split_directives(comment_body)
        if not mypy_parts:
            # No mypy-syntax directive on this line. A `ty: ignore[...]`
            # directive is left to ty, which reports unknown rule names
            # itself.
            continue

        if ty_parts:
            findings.append(
                (
                    line_number,
                    (
                        "combines a `# type: ignore[...]` and a "
                        "`# ty: ignore[...]` directive on one line; keep only "
                        "the `# ty: ignore[...]` form. ty does not interpret "
                        "the mypy spelling, so it suppresses nothing."
                    ),
                ),
            )
            continue

        if RE_BARE_TYPE_IGNORE.match(mypy_parts[0]):
            findings.append(
                (
                    line_number,
                    (
                        "bare `# type: ignore` does not suppress anything in ty; "
                        "use `# ty: ignore[<code>]` with a specific ty diagnostic code"
                    ),
                ),
            )
            continue

        findings.append(
            (
                line_number,
                (
                    "`# type: ignore[...]` uses mypy/ruff ignore syntax; ty "
                    "does not interpret it, so it suppresses nothing. Use "
                    "`# ty: ignore[<code>]` with the ty diagnostic code, or "
                    "fix the code."
                ),
            ),
        )

    return findings


def collect_python_files(
    roots: list[Path], exclude_dirs: tuple[str, ...]
) -> list[Path]:
    seen: set[Path] = set()
    collected: list[Path] = []

    for root in roots:
        root = root.resolve()
        if root.is_file() and root.suffix == ".py":
            seen.add(root)
            collected.append(root)
            continue

        if not root.exists():
            print(f"⚠️ ty-ignore-syntax: path does not exist: {root}", file=sys.stderr)
            continue

        for candidate in get_files_by_extension([".py"], use_git=True, root=root):
            absolute = candidate if candidate.is_absolute() else (root / candidate)
            absolute = absolute.resolve()
            if _is_excluded(absolute, exclude_dirs):
                continue
            if absolute in seen:
                continue
            seen.add(absolute)
            collected.append(absolute)

    return collected


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crackerjack.tools.ty_ignore_syntax",
        description=(
            "Reject bare `# type: ignore` directives and `# type: ignore[<code>]` "
            "comments that use mypy/ruff codes ty does not understand. "
            "Use `# ty: ignore[<code>]` with a kebab-case ty code instead."
        ),
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[Path(".")],
        help=(
            "Files or directories to scan (default: the repository root). "
            "The root is the default because this tool runs in every repo in "
            "the fleet, and a fixed package name would scan nothing outside "
            "crackerjack itself."
        ),
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="DIR",
        help=(
            "Directory name to skip (matched against any path segment). "
            f"Built-in excludes: {', '.join(DEFAULT_EXCLUDES)}. "
            "May be passed multiple times."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print findings but always exit 0 (do not enforce the gate).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Emit a JSON summary on stdout (machine-readable for CI).",
    )
    args = parser.parse_args(argv)

    exclude_dirs = DEFAULT_EXCLUDES + tuple(args.exclude)
    files = collect_python_files(list(args.paths), exclude_dirs)

    total_findings = 0
    file_results: list[dict[str, object]] = []

    for file_path in files:
        findings = scan_file(file_path)
        if not findings:
            continue
        total_findings += len(findings)
        if not args.as_json:
            print(f"✗ {file_path}")
            for line_number, message in findings:
                print(f" line {line_number}: {message}")
        file_results.append(
            {
                "file": str(file_path),
                "findings": [
                    {"line": line_number, "message": message}
                    for line_number, message in findings
                ],
            }
        )

    if args.as_json:
        import json

        print(
            json.dumps(
                {
                    "files_scanned": len(files),
                    "files_with_findings": len(file_results),
                    "total_findings": total_findings,
                    "files": file_results,
                    "gate_passes": total_findings == 0,
                },
                indent=2,
            )
        )
    else:
        if total_findings == 0:
            print(
                f"✓ ty-ignore-syntax: 0 findings across {len(files)} file(s); "
                f"all suppressions use the `# ty: ignore[<code>]` form."
            )
        else:
            print(
                f"\n✗ ty-ignore-syntax: {total_findings} finding(s) across "
                f"{len(file_results)} file(s). "
                f"Replace mypy/ruff `# type: ignore[...]` directives with "
                f"`# ty: ignore[<code>]`."
            )

    if args.dry_run:
        return 0

    return 0 if total_findings == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
