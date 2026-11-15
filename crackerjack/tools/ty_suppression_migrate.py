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

# A mypy-syntax directive: ``type: ignore`` or ``type: ignore[code, ...]``.
# The leading ``#`` is omitted from the spellings on purpose -- ty parses the
# *text* of a comment for directives, so a comment that shows the hash becomes
# a malformed directive itself and draws an ``invalid-ignore-comment`` warning.
RE_MYPY_DIRECTIVE = re.compile(r"#\s*type:\s*ignore(?:\[[^\]]*\])?")

# The same, matched anywhere in a comment body so that trailing prose such as
# ``# type: ignore[attr-defined] dynamically attached`` is recognised as a
# directive plus prose rather than as one undifferentiated blob.
RE_MYPY_LOOSE = re.compile(r"type:\s*ignore(?:\[[^\]]*\])?")

# A ty-syntax directive, used to recognise a line that already carries one.
RE_TY_DIRECTIVE = re.compile(r"#\s*ty:\s*ignore(?:\[[^\]]*\])?")
RE_TY_LOOSE = re.compile(r"ty:\s*ignore(?:\[[^\]]*\])?")

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
        ".archive",
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


@dataclass(frozen=True)
class Comment:
    """One comment token, with its contents classified."""

    line: int
    col: int
    end_col: int
    text: str
    mypy_bare: tuple[str, ...]
    mypy_bracketed: tuple[str, ...]
    ty: tuple[str, ...]
    prose: str

    @property
    def mypy(self) -> tuple[str, ...]:
        return self.mypy_bare + self.mypy_bracketed


RE_BACKTICK_RUN = re.compile(r"``[^`]*``|`[^`]*`")


def _backtick_mask(body: str) -> list[bool]:
    """Mark every character of ``body`` that sits inside a backtick run.

    A comment that *documents* a directive writes it in backticks — ``# type:
    ignore[import-not-found]`` directive covers Mypy/Pyright``. That is prose
    about a directive, not a directive, and rewriting it would mangle the
    documentation. The run is computed over the whole body because it
    straddles the ``#`` that separates the comment's segments.
    """
    mask = [False] * len(body)
    for match in RE_BACKTICK_RUN.finditer(body):
        for index in range(match.start(), match.end()):
            mask[index] = True
    return mask


def _classify(body: str) -> tuple[list[str], list[str], list[str], str]:
    """Split a comment body into mypy directives, ty directives and prose.

    A comment can hold more than one directive, and a directive can be
    followed by prose in the same segment — ``# type: ignore[attr-defined]
    dynamically attached``. Removing only the directive text would leave the
    prose behind as bare code, so a comment is rebuilt from its parts rather
    than patched in place.
    """
    bare: list[str] = []
    bracketed: list[str] = []
    ty: list[str] = []
    prose: list[str] = []
    mask = _backtick_mask(body)
    # Whether a directive survives in this comment. A prose segment that
    # followed a *removed* directive loses the nested ``#`` that introduced
    # it -- ``# type: ignore[x] # note`` becomes ``# note`` -- while prose
    # that followed a *surviving* one keeps it.
    surviving = False

    def in_backticks(start: int, end: int) -> bool:
        return any(mask[start:end])

    offset = 0
    for index, segment in enumerate(body.split("#")):
        stripped = segment.strip()
        lead = len(segment) - len(segment.lstrip())
        base = offset + lead
        offset += len(segment) + 1
        if not stripped:
            continue

        match = RE_MYPY_LOOSE.match(stripped)
        if match and not in_backticks(base + match.start(), base + match.end()):
            raw = match.group(0)
            if "[" in raw:
                bracketed.append(raw)
            else:
                bare.append(raw)
            remainder = (
                stripped[: match.start()] + " " + stripped[match.end() :]
            ).strip()
            if remainder:
                prose.append(remainder)
            continue
        match = RE_TY_LOOSE.match(stripped)
        if match and not in_backticks(base + match.start(), base + match.end()):
            ty.append(match.group(0))
            surviving = True
            remainder = (
                stripped[: match.start()] + " " + stripped[match.end() :]
            ).strip()
            if remainder:
                prose.append(remainder)
            continue
        prose.append(("# " if surviving and index > 0 else "") + stripped)
    return bare, bracketed, ty, " ".join(prose)


def find_comments(text: str) -> list[Comment]:
    """Every comment token in ``text``, classified.

    Token offsets are relative to the comment token's own string, so the
    column is the token's start column plus the match offset. Getting this
    wrong silently corrupts trailing comments.
    """
    try:
        tokens = list(tokenize.tokenize(io.BytesIO(text.encode("utf-8")).readline))
    except tokenize.TokenError, IndentationError, SyntaxError:
        return []

    comments: list[Comment] = []
    for token in tokens:
        if token.type != tokenize.COMMENT:
            continue
        body = token.string.lstrip("#").strip()
        bare, bracketed, ty, prose = _classify(body)
        comments.append(
            Comment(
                line=token.start[0],
                col=token.start[1],
                end_col=token.end[1],
                text=token.string,
                mypy_bare=tuple(bare),
                mypy_bracketed=tuple(bracketed),
                ty=tuple(ty),
                prose=prose,
            )
        )
    return comments


def find_directives(text: str) -> list[Directive]:
    """Every mypy-syntax directive in ``text``, in comment tokens only."""
    found: list[Directive] = []
    for comment in find_comments(text):
        for raw in comment.mypy:
            found.append(
                Directive(
                    line=comment.line,
                    col=comment.col,
                    end_col=comment.end_col,
                    kind="bracketed" if "[" in raw else "bare",
                    codes=raw[raw.index("[") + 1 : raw.rindex("]")]
                    if "[" in raw
                    else "",
                    text=raw,
                )
            )
    return found


def _rebuild(
    comment: Comment,
    keep_mypy: tuple[str, ...] = (),
    extra: tuple[str, ...] = (),
) -> str:
    """Rebuild a comment from its surviving directives and prose."""
    parts: list[str] = []
    parts.extend(part.lstrip("# ").strip() for part in comment.ty)
    parts.extend(part.lstrip("# ").strip() for part in extra)
    for raw in comment.mypy:
        kind = "bracketed" if "[" in raw else "bare"
        if kind in keep_mypy:
            parts.append(raw)
    if comment.prose:
        parts.append(comment.prose)
    parts = [part for part in parts if part]
    if not parts:
        return ""
    return "# " + "  ".join(parts)


def _apply_edits(text: str, edits: list[tuple[int, int, int, str]]) -> str:
    """Replace spans ``(line, col, end_col, replacement)`` in ``text``.

    Line count is preserved so that diagnostics ty reports afterwards map
    back onto the original lines. Removing a comment entirely also takes the
    whitespace that preceded it, so the line does not end in trailing spaces.
    """
    lines = text.splitlines(keepends=True)
    by_line: dict[int, list[tuple[int, int, str]]] = {}
    for line, col, end_col, replacement in edits:
        by_line.setdefault(line, []).append((col, end_col, replacement))
    for line_number, spans in by_line.items():
        original = lines[line_number - 1]
        for col, end_col, replacement in sorted(spans, reverse=True):
            head = original[:col]
            if not replacement:
                head = head.rstrip()
            original = head + replacement + original[end_col:]
        lines[line_number - 1] = original
    return "".join(lines)


def strip_directives(
    text: str,
    targets: set[tuple[int, int]],
    kinds: tuple[str, ...] = ("bracketed",),
) -> str:
    """Remove mypy directives of the given ``kinds`` from selected comments.

    ``targets`` selects which comments to rewrite; a comment with no
    directive of that kind is left untouched. Any ty directive already in
    the comment is kept, and so is any prose — including prose that trailed
    the mypy directive in the same segment.
    """
    edits: list[tuple[int, int, int, str]] = []
    for comment in find_comments(text):
        if (comment.line, comment.col) not in targets:
            continue
        if not any(
            ("bracketed" if "[" in raw else "bare") in kinds for raw in comment.mypy
        ):
            continue
        edits.append(
            (
                comment.line,
                comment.col,
                comment.end_col,
                _rebuild(
                    comment, keep_mypy=("bare",) if kinds == ("bracketed",) else ()
                ),
            )
        )
    return _apply_edits(text, edits)


def convert_blanket(text: str, replacements: dict[tuple[int, int], str]) -> str:
    """Replace the mypy directive in each selected comment with ``replacement``.

    ``replacements`` maps a comment's ``(line, col)`` to the directive that
    should take the mypy directive's place. Any ty directive already in the
    comment is kept, and so is any prose — including prose that trailed the
    mypy directive in the same segment.
    """
    edits: list[tuple[int, int, int, str]] = []
    for comment in find_comments(text):
        key = (comment.line, comment.col)
        if key not in replacements:
            continue
        edits.append(
            (
                comment.line,
                comment.col,
                comment.end_col,
                _rebuild(comment, extra=(replacements[key],)),
            )
        )
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


def _scan_files(repo: Path) -> tuple[dict[Path, str], dict[Path, list[Directive]]]:
    """Read every source file that carries a mypy directive.

    Files that cannot be read, and files that carry no directive at all, are
    left out of the result: the report counts the files *with* directives,
    not the files that were seen.
    """
    originals: dict[Path, str] = {}
    per_file: dict[Path, list[Directive]] = {}
    for path in iter_python_files(repo):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError, UnicodeDecodeError:
            continue
        directives = find_directives(text)
        if not directives:
            continue
        originals[path] = text
        per_file[path] = directives
    return originals, per_file


def _migrate_delete_bracketed(
    repo: Path,
    originals: dict[Path, str],
    per_file: dict[Path, list[Directive]],
    dry_run: bool,
) -> tuple[int, list[dict[str, object]]]:
    """Remove every bracketed directive and report what was removed.

    The count is of the *comments* that carried a bracketed directive; the
    sites list holds one entry per directive, so a comment that carried two
    of them adds one to the count and two to the list.
    """
    deleted = 0
    sites: list[dict[str, object]] = []
    for path, directives in per_file.items():
        targets = {(d.line, d.col) for d in directives if d.kind == "bracketed"}
        if not targets:
            continue
        deleted += len(targets)
        for d in directives:
            if d.kind == "bracketed":
                sites.append(
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
    return deleted, sites


def _bare_directives(
    per_file: dict[Path, list[Directive]],
) -> dict[Path, list[Directive]]:
    """The bare directives of every file that has any."""
    bare_by_file = {
        path: [d for d in directives if d.kind == "bare"]
        for path, directives in per_file.items()
    }
    return {path: bare for path, bare in bare_by_file.items() if bare}


def _ty_diagnostics(repo: Path, trees: list[str], python: str | None) -> list[dict]:
    """Every diagnostic ty reports over ``trees``."""
    diagnostics: list[dict] = []
    for tree in trees:
        if (repo / tree).is_dir():
            diagnostics.extend(run_ty(repo / tree, repo, python))
    return diagnostics


def _strip_bare_directives(
    bare_by_file: dict[Path, list[Directive]],
    originals: dict[Path, str],
) -> dict[Path, str]:
    """Strip every bare directive, writing the stripped file out.

    Returns the stripped text of every file that was written, so the
    caller can put it back.
    """
    stripped: dict[Path, str] = {}
    for path, directives in bare_by_file.items():
        targets = {(d.line, d.col) for d in directives}
        stripped[path] = strip_directives(
            originals[path], targets, kinds=("bare",)
        )
        path.write_text(stripped[path], encoding="utf-8")
    return stripped


def _revealed_rules(
    repo: Path,
    trees: list[str],
    python: str | None,
    bare_by_file: dict[Path, list[Directive]],
    originals: dict[Path, str],
) -> dict[tuple[str, int], list[str]]:
    """The rules ty revealed once every bare directive was stripped.

    Discovering the revealed rules needs ty to see the files *without* their
    bare directives, so the stripped text is written out for the second ty
    pass and the original text is written back afterwards. The caller writes
    the converted result, if it is writing one at all.
    """
    # Strip every bare directive, ask ty what appears, then write back.
    before = _ty_diagnostics(repo, trees, python)
    stripped_text = _strip_bare_directives(bare_by_file, originals)
    after: list[dict] = []
    try:
        after = _ty_diagnostics(repo, trees, python)
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
    return rules_by_site


def _rules_for(
    rules_by_site: dict[tuple[str, int], list[str]],
    relative: str,
    directive: Directive,
) -> list[str]:
    """The rules ty revealed for one directive."""
    rules = rules_by_site.get((relative, directive.line), [])
    if not rules:
        # ty reports the diagnostic on the line the expression
        # starts, which can differ from the directive's line.
        rules = _rules_near(rules_by_site, relative, directive.line)
    return rules


def _migrate_convert_blanket(
    repo: Path,
    trees: list[str],
    originals: dict[Path, str],
    per_file: dict[Path, list[Directive]],
    python: str | None,
    dry_run: bool,
) -> tuple[int, int, list[dict[str, object]]]:
    """Rewrite each bare directive to the ty rule it was hiding.

    A directive that revealed nothing was suppressing nothing, so it is
    dropped rather than converted.

    A dry run reports the same result but leaves every file exactly as it
    found it: revealing the rules needs ty to see the files without their
    bare directives, so the stripped text is written out for that pass and
    the original text is written back afterwards.
    """
    bare_by_file = _bare_directives(per_file)
    if not bare_by_file:
        return 0, 0, []

    rules_by_site = _revealed_rules(repo, trees, python, bare_by_file, originals)

    deleted = 0
    converted = 0
    sites: list[dict[str, object]] = []
    for path, directives in bare_by_file.items():
        relative = path.relative_to(repo).as_posix()
        replacements: dict[tuple[int, int], str] = {}
        for directive in directives:
            rules = _rules_for(rules_by_site, relative, directive)
            if rules:
                body = ", ".join(rules)
                replacements[(directive.line, directive.col)] = f"ty: ignore[{body}]"
                converted += 1
                sites.append(
                    {
                        "file": relative,
                        "line": directive.line,
                        "action": "converted",
                        "rules": rules,
                    }
                )
            else:
                # Nothing appeared when the directive was removed, so it
                # was suppressing nothing. Drop it.
                replacements[(directive.line, directive.col)] = ""
                deleted += 1
                sites.append(
                    {"file": relative, "line": directive.line, "action": "deleted"}
                )
        if replacements and not dry_run:
            path.write_text(
                convert_blanket(originals[path], replacements), encoding="utf-8"
            )
    return deleted, converted, sites


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
    originals, per_file = _scan_files(repo)

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
        deleted, sites = _migrate_delete_bracketed(repo, originals, per_file, dry_run)
        report["deleted"] += deleted
        report["sites"].extend(sites)
        return report

    if mode == "convert-blanket":
        deleted, converted, sites = _migrate_convert_blanket(
            repo, trees, originals, per_file, python, dry_run
        )
        report["deleted"] += deleted
        report["converted"] += converted
        report["sites"].extend(sites)
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
