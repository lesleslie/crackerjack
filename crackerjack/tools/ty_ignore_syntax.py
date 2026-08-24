from __future__ import annotations

import argparse
import io
import re
import sys
import tokenize
from pathlib import Path

from ._git_utils import get_files_by_extension

# Kebab-case ty diagnostic codes. A `# type: ignore[code-name]` comment only


KNOWN_TY_CODES: frozenset[str] = frozenset(
    {
        "invalid-argument-type",
        "unresolved-attribute",
        "invalid-assignment",
        "unresolved-import",
        "call-arg",
        "invalid-await",
        "invalid-return-type",
        "unused-type-ignore-comment",
    }
)

# Match a bare type: ignore directive at the END of a real `# ...` comment.

RE_BARE_TYPE_IGNORE = re.compile(r"^type:\s*ignore\s*$")
RE_BRACKETED_TYPE_IGNORE = re.compile(r"^type:\s*ignore\[([a-zA-Z0-9_,\- ]+)\]\s*$")


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
    "site-packages",
)


def _is_excluded(path: Path, exclude_dirs: tuple[str, ...]) -> bool:
    parts = set(path.parts)
    return any(excluded in parts for excluded in exclude_dirs)


def _normalise_codes(raw_codes: str) -> list[str]:
    return [code.strip() for code in raw_codes.split(",") if code.strip()]


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


def scan_file(file_path: Path) -> list[tuple[int, str]]:
    try:
        text = file_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [(0, f"Could not read {file_path}: {exc}")]

    findings: list[tuple[int, str]] = []
    seen_lines: set[int] = set()

    for line_number, comment_body in _iter_real_comments(text):
        bracketed = RE_BRACKETED_TYPE_IGNORE.match(comment_body)
        if bracketed is not None:
            codes = _normalise_codes(bracketed.group(1))
            if not codes:
                findings.append(
                    (
                        line_number,
                        (
                            "`# type: ignore[]` with empty code list; "
                            "use `# ty: ignore[<code>]` with a real ty code"
                        ),
                    ),
                )
                seen_lines.add(line_number)
                continue
            unknown = [c for c in codes if c not in KNOWN_TY_CODES]
            if unknown:
                formatted = ", ".join(repr(c) for c in unknown)
                findings.append(
                    (
                        line_number,
                        (
                            f"`# type: ignore[{','.join(codes)}]` uses mypy/ruff code(s) "
                            f"{formatted}; ty only recognises the kebab-case codes in "
                            f"`crackerjack.tools.ty_ignore_syntax.KNOWN_TY_CODES`. "
                            f"Use `# ty: ignore[<code>]` with a ty code or fix the code."
                        ),
                    ),
                )
                seen_lines.add(line_number)
            continue

        if RE_BARE_TYPE_IGNORE.match(comment_body):
            findings.append(
                (
                    line_number,
                    (
                        "bare `# type: ignore` does not suppress anything in ty; "
                        "use `# ty: ignore[<code>]` with a specific ty diagnostic code"
                    ),
                ),
            )
            seen_lines.add(line_number)

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
        default=[Path("crackerjack")],
        help="Files or directories to scan (default: ./crackerjack).",
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
                    "known_ty_codes": sorted(KNOWN_TY_CODES),
                },
                indent=2,
            )
        )
    else:
        if total_findings == 0:
            print(
                f"✓ ty-ignore-syntax: 0 findings across {len(files)} file(s); "
                f"all suppressions use the kebab-case `# ty: ignore[<code>]` form."
            )
        else:
            print(
                f"\n✗ ty-ignore-syntax: {total_findings} finding(s) across "
                f"{len(file_results)} file(s). "
                f"Replace bare `# type: ignore` and mypy/ruff codes with "
                f"`# ty: ignore[<known-code>]`."
            )

    if args.dry_run:
        return 0

    return 0 if total_findings == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
