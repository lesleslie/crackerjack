"""Migrate mypy-syntax ignore directives to ty's syntax.

This is the "strip and observe" technique made reusable. For every candidate
directive the tool removes it, asks ty what it now reports for that line, and
writes back the answer:

* a diagnostic appears -> the directive was live, so it becomes a specific
  ``# ty: ignore[<rule>]`` naming the rule ty actually reported;
* nothing appears -> the directive was dead, so it is deleted.

The distinction matters because the two spellings behave differently under ty:

* a bare ``# type: ignore`` is honoured by ty as a blanket per-line
  suppression, so it can be hiding real diagnostics;
* ``# type: ignore[code]`` is **not** read by ty at all, so it is inert
  noise that only ever mattered to mypy.

Only real COMMENT tokens are considered. The text ``# type: ignore`` inside a
string literal or a docstring is not a directive and is never edited.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import tokenize
from dataclasses import dataclass
from pathlib import Path

from crackerjack.tools._ty_binary import resolve_ty_binary

# A mypy-syntax directive: ``# type: ignore`` or ``# type: ignore[code, ...]``.
RE_MYPY_DIRECTIVE = re.compile(r"#\s*type:\s*ignore(?:\[[^\]]*\])?")

# A ty-syntax directive, used to recognise a line that already carries one.
RE_TY_DIRECTIVE = re.compile(r"#\s*ty:\s*ignore(?:\[[^\]]*\])?")

_CONCISE_DIAGNOSTIC = re.compile(
    r"^(?P<file>[^\s:][^:]*):(?P<line>\d+):(?P<col>\d+):\s+"
    r"(?:error|warning)\[(?P<rule>[a-z0-9-]+)\]"
)

# Directories that hold vendored copies of the source rather than source.
SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "node_modules",
        "dist",
        "build",
        "htmlcov",
        "__pycache__",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".crackerjack",
        ".crackerjack_cache",
        ".tox",
        ".worktrees",
        "site-packages",
    }
)


@dataclass(frozen=True)
class Directive:
    """One mypy-syntax directive found in a real comment."""

    line: int
    col: int
    end_col: int
    kind: str  # "bare" or "bracketed"
    codes: str
    text: str


def find_directives(text: str) -> list[Directive]:
    """Every mypy-syntax directive in ``text``, in comment tokens only.

    Token offsets are relative to the comment token's own string, so the
    column is the token's start column plus the match offset. Getting this
    wrong silently corrupts trailing comments.
    """
    try:
        tokens = list(tokenize.tokenize(io.BytesIO(text.encode("utf-8")).readline))
    except tokenize.TokenError, IndentationError, SyntaxError:
        return []

    found: list[Directive] = []
    for token in tokens:
        if token.type != tokenize.COMMENT:
            continue
        column = token.start[1]
        for match in RE_MYPY_DIRECTIVE.finditer(token.string):
            raw = match.group(0)
            found.append(
                Directive(
                    line=token.start[0],
                    col=column + match.start(),
                    end_col=column + match.end(),
                    kind="bracketed" if "[" in raw else "bare",
                    codes=raw[raw.index("[") + 1 : raw.rindex("]")]
                    if "[" in raw
                    else "",
                    text=raw,
                )
            )
    return found


def _apply_edits(text: str, edits: list[tuple[int, int, int, str]]) -> str:
    """Replace spans ``(line, col, end_col, replacement)`` in ``text``.

    Line count is preserved so that diagnostics ty reports afterwards map
    back onto the original lines.
    """
    lines = text.splitlines(keepends=True)
    by_line: dict[int, list[tuple[int, int, str]]] = {}
    for line, col, end_col, replacement in edits:
        by_line.setdefault(line, []).append((col, end_col, replacement))
    for line_number, spans in by_line.items():
        original = lines[line_number - 1]
        for col, end_col, replacement in sorted(spans, reverse=True):
            original = original[:col] + replacement + original[end_col:]
        lines[line_number - 1] = original
    return "".join(lines)


def strip_directives(text: str, targets: set[tuple[int, int]]) -> str:
    """Remove the directive text at each ``(line, col)`` in ``targets``."""
    edits = [
        (d.line, d.col, d.end_col, "")
        for d in find_directives(text)
        if (d.line, d.col) in targets
    ]
    return _apply_edits(text, edits)


def convert_blanket(text: str, replacements: dict[tuple[int, int], str]) -> str:
    """Replace the directive at each ``(line, col)`` with ``replacement``."""
    edits = [
        (d.line, d.col, d.end_col, replacements[(d.line, d.col)])
        for d in find_directives(text)
        if (d.line, d.col) in replacements
    ]
    return _apply_edits(text, edits)


def iter_python_files(repo: Path) -> list[Path]:
    """Every source file in ``repo``, skipping vendored copies."""
    found: list[Path] = []
    for path in sorted(repo.rglob("*.py")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        found.append(path)
    return found


def run_ty(target: Path, repo: Path, python: str | None) -> list[dict]:
    """Run ty over ``target``, reporting diagnostics as dicts.

    ``src.include`` is overridden so the tree is actually checked: repos that
    scope ty with ``[tool.ty] src = { include = ["<pkg>/**/*.py"] }`` filter
    ty's whole file discovery, and ``ty check tests`` would otherwise find
    nothing and report a clean run over zero files.
    """
    relative = target.relative_to(repo).as_posix()
    command = [
        resolve_ty_binary(),
        "check",
        relative,
        "-c",
        f'src.include=["{relative}/**/*.py"]',
        "--output-format",
        "concise",
        "--no-progress",
    ]
    if python:
        command += ["--python", python]
    proc = subprocess.run(
        command, capture_output=True, text=True, cwd=repo, check=False
    )
    diagnostics: list[dict] = []
    for line in (proc.stdout + proc.stderr).splitlines():
        match = _CONCISE_DIAGNOSTIC.match(line.strip())
        if match:
            diagnostics.append(
                {
                    "file": match.group("file"),
                    "line": int(match.group("line")),
                    "rule": match.group("rule"),
                }
            )
    return diagnostics


def _tree_names(repo: Path, prod_dir: str | None, test_dir: str | None) -> list[str]:
    trees: list[str] = []
    if prod_dir:
        trees.append(prod_dir)
    else:
        package = repo.name.replace("-", "_")
        if (repo / package).is_dir():
            trees.append(package)
    if test_dir:
        trees.append(test_dir)
    elif (repo / "tests").is_dir():
        trees.append("tests")
    return trees


def migrate(
    repo: Path,
    mode: str,
    prod_dir: str | None = None,
    test_dir: str | None = None,
    python: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Run one migration mode over ``repo`` and return a report."""
    trees = _tree_names(repo, prod_dir, test_dir)
    files = iter_python_files(repo)
    originals: dict[Path, str] = {}
    per_file: dict[Path, list[Directive]] = {}

    for path in files:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError, UnicodeDecodeError:
            continue
        directives = find_directives(text)
        if not directives:
            continue
        originals[path] = text
        per_file[path] = directives

    report = {
        "mode": mode,
        "repo": str(repo),
        "trees": trees,
        "files_scanned": len(originals),
        "deleted": 0,
        "converted": 0,
        "unchanged": 0,
        "sites": [],
    }

    if mode == "delete-bracketed":
        for path, directives in per_file.items():
            targets = {(d.line, d.col) for d in directives if d.kind == "bracketed"}
            if not targets:
                continue
            report["deleted"] += len(targets)
            for d in directives:
                if d.kind == "bracketed":
                    report["sites"].append(
                        {
                            "file": str(path.relative_to(repo)),
                            "line": d.line,
                            "action": "deleted",
                        }
                    )
            if not dry_run:
                path.write_text(
                    strip_directives(originals[path], targets), encoding="utf-8"
                )
        return report

    if mode == "convert-blanket":
        bare_by_file = {
            path: [d for d in directives if d.kind == "bare"]
            for path, directives in per_file.items()
        }
        bare_by_file = {p: d for p, d in bare_by_file.items() if d}
        if not bare_by_file:
            return report

        # Strip every bare directive, ask ty what appears, then write back.
        before: list[dict] = []
        for tree in trees:
            if (repo / tree).is_dir():
                before.extend(run_ty(repo / tree, repo, python))

        stripped_text: dict[Path, str] = {}
        for path, directives in bare_by_file.items():
            targets = {(d.line, d.col) for d in directives}
            stripped_text[path] = strip_directives(originals[path], targets)
            path.write_text(stripped_text[path], encoding="utf-8")

        after: list[dict] = []
        try:
            for tree in trees:
                if (repo / tree).is_dir():
                    after.extend(run_ty(repo / tree, repo, python))
        finally:
            for path, text in stripped_text.items():
                path.write_text(text, encoding="utf-8")

        revealed = _difference(after, before)
        rules_by_site: dict[tuple[str, int], list[str]] = {}
        for diagnostic in revealed:
            key = (diagnostic["file"], diagnostic["line"])
            rules = rules_by_site.setdefault(key, [])
            if diagnostic["rule"] not in rules:
                rules.append(diagnostic["rule"])

        for path, directives in bare_by_file.items():
            relative = path.relative_to(repo).as_posix()
            replacements: dict[tuple[int, int], str] = {}
            for directive in directives:
                rules = rules_by_site.get((relative, directive.line), [])
                if not rules:
                    # ty reports the diagnostic on the line the expression
                    # starts, which can differ from the directive's line.
                    rules = _rules_near(rules_by_site, relative, directive.line)
                if rules:
                    body = ", ".join(rules)
                    replacements[(directive.line, directive.col)] = (
                        f"# ty: ignore[{body}]"
                    )
                    report["converted"] += 1
                    report["sites"].append(
                        {
                            "file": relative,
                            "line": directive.line,
                            "action": "converted",
                            "rules": rules,
                        }
                    )
                else:
                    report["deleted"] += 1
                    report["sites"].append(
                        {"file": relative, "line": directive.line, "action": "deleted"}
                    )
            if replacements and not dry_run:
                path.write_text(
                    convert_blanket(originals[path], replacements), encoding="utf-8"
                )
        return report

    raise ValueError(f"unknown mode: {mode}")


def _difference(after: list[dict], before: list[dict]) -> list[dict]:
    """Diagnostics in ``after`` that were not in ``before``."""
    seen = {(d["file"], d["line"], d["rule"]) for d in before}
    unique: list[dict] = []
    emitted: set[tuple[str, int, str]] = set()
    for diagnostic in after:
        key = (diagnostic["file"], diagnostic["line"], diagnostic["rule"])
        if key in seen or key in emitted:
            continue
        emitted.add(key)
        unique.append(diagnostic)
    return unique


def _rules_near(
    rules_by_site: dict[tuple[str, int], list[str]], file: str, line: int
) -> list[str]:
    """Rules for a diagnostic ty attributes to a nearby line.

    ty attributes a diagnostic to the line its expression starts on, which
    for a multi-line call is not the line the closing bracket (and therefore
    the directive) sits on.
    """
    for offset in range(6):
        for candidate in (line - offset, line + offset):
            if offset == 0 and candidate != line:
                continue
            rules = rules_by_site.get((file, candidate))
            if rules:
                return rules
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="crackerjack.tools.ty_suppression_migrate",
        description=(
            "Migrate mypy-syntax ignore directives to ty's syntax. "
            "'delete-bracketed' removes the bracketed codes ty never reads; "
            "'convert-blanket' rewrites each bare directive to the specific "
            "ty rule it was hiding, and deletes the ones that hide nothing."
        ),
    )
    parser.add_argument("--repo", type=Path, required=True, help="Repository root.")
    parser.add_argument(
        "--mode",
        choices=("delete-bracketed", "convert-blanket"),
        default="convert-blanket",
        help="Migration mode (default: convert-blanket).",
    )
    parser.add_argument("--prod-dir", default=None, help="Package directory name.")
    parser.add_argument("--test-dir", default=None, help="Test directory name.")
    parser.add_argument(
        "--python", default=None, help="Python environment ty should resolve against."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Report without writing any file."
    )
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args(argv)

    report = migrate(
        repo=args.repo.resolve(),
        mode=args.mode,
        prod_dir=args.prod_dir,
        test_dir=args.test_dir,
        python=args.python,
        dry_run=args.dry_run,
    )

    if args.as_json:
        print(json.dumps(report, indent=2))
    else:
        print(
            f"ty-suppression-migrate [{args.mode}] {args.repo}: "
            f"{report['converted']} converted, {report['deleted']} deleted, "
            f"across {report['files_scanned']} file(s) with directives."
        )
        if args.dry_run:
            print("  (dry run — no file was written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
