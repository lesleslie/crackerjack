#!/usr/bin/env uv run python

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

LIFECYCLE_VALUES = {"draft", "active", "partial", "shipped", "complete"}
ROLE_VALUES = {"canonical", "implementation", "umbrella", "historical", "superseded"}
RESERVED_WORDS = LIFECYCLE_VALUES | ROLE_VALUES

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TOPIC_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{2,40}$")
EXT_LINK_RE = re.compile(r"^ext:[A-Za-z0-9_.\-:]+$")


DEFAULT_STORES = (
    "docs/adr/",
    "docs/plans/",
    "docs/superpowers/specs/",
    "docs/superpowers/plans/",
    ".claude/decisions/",
    "docs/followups/",
)


ALWAYS_EXCLUDE_REL = ("docs/plans/PLAN_INDEX.md",)
ALWAYS_EXCLUDE_DIRS_REL = ("docs/plans/drafts/",)
ALWAYS_EXCLUDE_SUFFIXES = (".backup", ".backup.json")


DECISIONS_DIR = Path(".claude/decisions")


INLINE_STATUS_HEADING_RE = re.compile(
    r"^#{2,}\s*Status\s*$", re.IGNORECASE | re.MULTILINE
)


@dataclass
class Issue:
    severity: str
    rule: str
    message: str
    line: int = 0

    def format(self, path: str) -> str:
        location = f"{path}:{self.line}" if self.line else path
        return f"file={location} [{self.severity}] {self.rule}={self.message}"


@dataclass
class FileResult:
    path: str
    status: str
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)

    @property
    def issues(self) -> list[Issue]:
        return [*self.errors, *self.warnings]

    def add(self, issue: Issue) -> None:
        if issue.severity == "ERROR":
            self.errors.append(issue)
        else:
            self.warnings.append(issue)


def load_seed_topics(repo_root: Path) -> set[str]:
    vocab_path = repo_root / "docs/schemas/topic-vocabulary-v1.md"
    if not vocab_path.is_file():
        return set()

    text = vocab_path.read_text(encoding="utf-8")
    seeds: set[str] = set()

    in_seed_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_seed_section = stripped.lower().startswith("## seed list")
            continue
        if not in_seed_section:
            continue

        if "|" not in stripped:
            continue
        seeds.update(
            match.group(1)
            for match in re.finditer(r"`([a-z][a-z0-9-]{2,40})`", stripped)
        )
    return seeds


_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)


def extract_frontmatter(
    text: str,
) -> tuple[dict[str, Any] | None, str | None, int]:
    """Parse the leading ``---`` YAML block from ``text``.

    Returns ``(parsed, error_message, error_line)``:

    - ``parsed`` is the YAML mapping, ``{}`` for an empty block, or ``None``
      when no frontmatter exists.
    - ``error_message`` is non-``None`` when parsing failed; ``error_line``
      is the 1-indexed file line where the parse broke (0 when unknown).
    """
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        return None, None, 0

    raw = match.group(1)
    try:
        import yaml
    except ImportError as exc:
        return None, f"PyYAML unavailable: {exc}", 0

    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        problem_mark = getattr(exc, "problem_mark", None)
        # PyYAML marks are 0-indexed line/column within the matched YAML
        # block; add 1 for the opening ``---`` itself to get the file line.
        block_start_line = text.count("\n", 0, match.start()) + 1
        error_line = block_start_line + int(problem_mark.line) if problem_mark else 0
        return None, f"YAML parse error: {exc}", error_line

    if parsed is None:
        return {}, None, 0
    if not isinstance(parsed, dict):
        return None, "Frontmatter is not a YAML mapping", 0
    return parsed, None, 0


def _frontmatter_field_lines(text: str) -> dict[str, int]:
    """Map each top-level YAML key in the frontmatter to its 1-indexed file line.

    Validator helpers use this so an error like ``date_invalid`` can be
    attributed to the line where the offending ``date:`` key lives instead
    of just the file path. Lines after the closing ``---`` are ignored
    because ``^key:`` matches only top-level YAML keys, and body content
    rarely matches the pattern. Collisions on the same key keep the first
    occurrence (a file with two ``topic:`` lines is itself a YAML error).
    """
    return {
        m.group(1): text.count("\n", 0, m.start()) + 1
        for m in re.finditer(r"^([A-Za-z_][A-Za-z0-9_-]*)\s*:", text, re.MULTILINE)
    }


def _validate_date(
    value: Any, field_name: str, result: FileResult, line: int = 0
) -> None:

    if isinstance(value, datetime.date):
        candidate = value.isoformat()
    elif isinstance(value, str):
        candidate = value
    else:
        candidate = None
    if candidate is None or not ISO_DATE_RE.match(candidate):
        result.add(
            Issue(
                "ERROR",
                f"{field_name}_invalid",
                f"{field_name} must be ISO-8601 YYYY-MM-DD; got {value!r}",
                line=line,
            )
        )


def _validate_topic(
    value: Any,
    known_topics: set[str],
    strict: bool,
    result: FileResult,
    line: int = 0,
) -> None:
    if not isinstance(value, str):
        result.add(
            Issue(
                "ERROR",
                "topic_invalid",
                f"topic must be a slug string; got {type(value).__name__}",
                line=line,
            )
        )
        return
    if not TOPIC_SLUG_RE.match(value):
        result.add(
            Issue(
                "ERROR",
                "topic_invalid",
                f"topic {value!r} does not match ^[a-z][a-z0-9-]{{2,40}}$",
                line=line,
            )
        )
        return
    if value.lower() in RESERVED_WORDS:
        result.add(
            Issue(
                "ERROR",
                "topic_reserved",
                f"topic {value!r} collides with a lifecycle/role word",
                line=line,
            )
        )
        return
    if known_topics and value not in known_topics:
        severity = "ERROR" if strict else "WARNING"
        result.add(
            Issue(
                severity,
                "topic_unknown",
                f"topic {value!r} not in seed vocabulary; add to "
                f"docs/schemas/topic-vocabulary-v1.md to silence",
                line=line,
            )
        )


def _validate_superseded_by(
    value: Any,
    repo_root: Path,
    known_files: set[str],
    result: FileResult,
    line: int = 0,
) -> None:
    if value is None:
        return

    if isinstance(value, str):
        items: list[Any] = [value]
    elif isinstance(value, list):
        items = value
    else:
        result.add(
            Issue(
                "ERROR",
                "superseded_by_invalid",
                f"superseded_by must be a string path/ext:<id> or list thereof; "
                f"got {type(value).__name__}",
                line=line,
            )
        )
        return
    for entry in items:
        if not isinstance(entry, str):
            result.add(
                Issue(
                    "ERROR",
                    "superseded_by_invalid",
                    f"superseded_by entries must be strings; got {type(entry).__name__}",
                    line=line,
                )
            )
            continue
        if EXT_LINK_RE.match(entry):
            continue
        if entry in known_files or (repo_root / entry).is_file():
            continue
        result.add(
            Issue(
                "ERROR",
                "superseded_by_unresolved",
                f"superseded_by entry {entry!r} does not resolve to a known file or ext:<id>",
                line=line,
            )
        )


def _validate_blocks_on(
    value: Any,
    repo_root: Path,
    known_files: set[str],
    result: FileResult,
    line: int = 0,
) -> None:
    if value is None:
        return
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = value
    else:
        result.add(
            Issue(
                "ERROR",
                "blocks_on_invalid",
                f"blocks_on must be a list of paths or ext:<id>; got {type(value).__name__}",
                line=line,
            )
        )
        return
    for entry in items:
        if not isinstance(entry, str):
            result.add(
                Issue(
                    "ERROR",
                    "blocks_on_invalid",
                    f"blocks_on entries must be strings; got {type(entry).__name__}",
                    line=line,
                )
            )
            continue
        if EXT_LINK_RE.match(entry):
            continue
        if entry in known_files or (repo_root / entry).is_file():
            continue
        result.add(
            Issue(
                "ERROR",
                "blocks_on_unresolved",
                f"blocks_on entry {entry!r} does not resolve to a known file or ext:<id>",
                line=line,
            )
        )


def _validate_role_status_pair(
    front: dict[str, Any], result: FileResult, role_line: int = 0
) -> None:
    role = front.get("role")
    if role == "superseded":
        if "superseded_by" not in front or front.get("superseded_by") in (None, "", []):
            result.add(
                Issue(
                    "ERROR",
                    "superseded_by_required",
                    "role: superseded requires a populated superseded_by field",
                    line=role_line,
                )
            )


def _read_source_file(path: Path, result: FileResult) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        result.add(Issue("ERROR", "read_error", f"cannot read file: {exc}"))
        result.status = "invalid"
        return None


def _handle_missing_frontmatter(result: FileResult, allow_nonstandard: bool) -> None:
    if not allow_nonstandard:
        result.add(
            Issue(
                "ERROR",
                "MISSING_FRONTMATTER",
                "no YAML frontmatter (expected --- delimited block at top)",
            )
        )
    result.status = "missing"


def _check_required_keys(
    front: dict[str, Any],
    result: FileResult,
    field_lines: dict[str, int] | None = None,
) -> None:
    for key in ("status", "role", "date", "last_reviewed", "topic"):
        if key not in front:
            # Missing keys live nowhere in the file, so we attribute the
            # error to the frontmatter opening ``---`` line (line 1). The
            # renderer's ``file:line`` formatter gracefully degrades to
            # just ``file`` when line is 0, so we use 1 explicitly to
            # point at the frontmatter block.
            line = (field_lines or {}).get(key, 1) or 1
            result.add(
                Issue(
                    "ERROR",
                    f"{key}_missing",
                    f"required key {key!r} absent",
                    line=line,
                )
            )


def _normalize_status(front: dict[str, Any]) -> None:
    status = front.get("status")
    if isinstance(status, str) and status.strip().rstrip(".").lower() == "resolved":
        front["status"] = "complete"


def _validate_status(
    front: dict[str, Any], result: FileResult, status_line: int = 0
) -> None:
    status = front.get("status")
    if "status" in front and status not in LIFECYCLE_VALUES:
        result.add(
            Issue(
                "ERROR",
                "status_invalid",
                f"status {status!r} not in {sorted(LIFECYCLE_VALUES)}",
                line=status_line,
            )
        )


def _validate_role(
    front: dict[str, Any], result: FileResult, role_line: int = 0
) -> None:
    role = front.get("role")
    if "role" in front and role not in ROLE_VALUES:
        result.add(
            Issue(
                "ERROR",
                "role_invalid",
                f"role {role!r} not in {sorted(ROLE_VALUES)}",
                line=role_line,
            )
        )


def _validate_superseded_by_link(
    front: dict[str, Any],
    repo_root: Path,
    known_files: set[str],
    validate_links: bool,
    skip_link_note: bool,
    result: FileResult,
    field_lines: dict[str, int] | None = None,
) -> None:
    if "superseded_by" not in front:
        return
    link_line = (field_lines or {}).get("superseded_by", 0)
    if validate_links:
        _validate_superseded_by(
            front.get("superseded_by"),
            repo_root,
            known_files,
            result,
            line=link_line,
        )
    elif skip_link_note:
        result.add(
            Issue(
                "NOTE",
                "link_validation_skipped",
                "superseded_by present; --validate-links disabled, skipping "
                "resolution check",
                line=link_line,
            )
        )


def _validate_blocks_on_link(
    front: dict[str, Any],
    repo_root: Path,
    known_files: set[str],
    validate_links: bool,
    skip_link_note: bool,
    result: FileResult,
    field_lines: dict[str, int] | None = None,
) -> None:
    if "blocks_on" not in front:
        return
    link_line = (field_lines or {}).get("blocks_on", 0)
    if validate_links:
        _validate_blocks_on(
            front.get("blocks_on"),
            repo_root,
            known_files,
            result,
            line=link_line,
        )
    elif skip_link_note:
        result.add(
            Issue(
                "NOTE",
                "link_validation_skipped",
                "blocks_on present; --validate-links disabled, skipping "
                "resolution check",
                line=link_line,
            )
        )


def _check_inline_status_heading(
    text: str, allow_nonstandard: bool, result: FileResult
) -> None:
    if allow_nonstandard:
        return
    match = INLINE_STATUS_HEADING_RE.search(text)
    if match is None:
        return
    # ``text.count('\n', 0, m.start())`` gives the 0-indexed line of the
    # match's first character; +1 makes it 1-indexed for users.
    line = text.count("\n", 0, match.start()) + 1
    result.add(
        Issue(
            "WARNING",
            "NONSTANDARD_INLINE_STATUS",
            "inline '## Status' block detected outside frontmatter; "
            "pass --allow-nonstandard to tolerate",
            line=line,
        )
    )


def _finalize_status(result: FileResult) -> None:
    if result.errors:
        result.status = "invalid"
    elif result.warnings:
        result.status = "warning"
    else:
        result.status = "ok"


def validate_file(
    path: Path,
    rel: str,
    *,
    repo_root: Path,
    known_files: set[str],
    known_topics: set[str],
    strict: bool,
    allow_nonstandard: bool,
    validate_links: bool,
    skip_link_note: bool,
) -> FileResult:
    result = FileResult(path=rel, status="ok")

    text = _read_source_file(path, result)
    if text is None:
        return result

    front, err, parse_line = extract_frontmatter(text)
    if err is not None:
        result.add(Issue("ERROR", "frontmatter_parse", err, line=parse_line))
        result.status = "invalid"
        return result
    if front is None:
        _handle_missing_frontmatter(result, allow_nonstandard)
        return result

    is_lite = rel.startswith(".claude/decisions/")

    # Build a {key: file_line} map once per file so every validator helper
    # can attribute its errors to the line where the offending frontmatter
    # key lives. Helpers default to ``line=0`` when called without one, so
    # callers that skip this step still produce valid (if less precise)
    # output.
    field_lines = _frontmatter_field_lines(text)

    _check_required_keys(front, result, field_lines)
    _normalize_status(front)
    _validate_status(front, result, status_line=field_lines.get("status", 0))
    _validate_role(front, result, role_line=field_lines.get("role", 0))
    _validate_date(
        front.get("date"),
        "date",
        result,
        line=field_lines.get("date", 0),
    )
    _validate_date(
        front.get("last_reviewed"),
        "last_reviewed",
        result,
        line=field_lines.get("last_reviewed", 0),
    )
    _validate_topic(
        front.get("topic"),
        known_topics,
        strict,
        result,
        line=field_lines.get("topic", 0),
    )

    if not is_lite:
        _validate_superseded_by_link(
            front,
            repo_root,
            known_files,
            validate_links,
            skip_link_note,
            result,
            field_lines,
        )
        _validate_blocks_on_link(
            front,
            repo_root,
            known_files,
            validate_links,
            skip_link_note,
            result,
            field_lines,
        )

    _validate_role_status_pair(front, result, role_line=field_lines.get("role", 0))
    _check_inline_status_heading(text, allow_nonstandard, result)
    _finalize_status(result)
    return result


def _is_excluded(rel: str) -> bool:
    if rel in ALWAYS_EXCLUDE_REL:
        return True
    for prefix in ALWAYS_EXCLUDE_DIRS_REL:
        if rel.startswith(prefix):
            return True

    parts = rel.split("/")
    if "archive" in parts or ".archive" in parts:
        return True
    for suffix in ALWAYS_EXCLUDE_SUFFIXES:
        if rel.endswith(suffix):
            return True
    return False


def discover_files(
    repo_root: Path, stores: list[Path], extra_paths: list[Path]
) -> list[tuple[Path, str]]:
    seen: set[Path] = set()
    out: list[tuple[Path, str]] = []

    candidates: list[Path] = [*stores, *extra_paths]

    for root in candidates:
        if root.is_file():
            abs_path = root.resolve()
            if abs_path in seen:
                continue
            seen.add(abs_path)
            rel = abs_path.relative_to(repo_root).as_posix()
            if _is_excluded(rel):
                continue
            out.append((abs_path, rel))
            continue
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            abs_path = path.resolve()
            if abs_path in seen:
                continue
            seen.add(abs_path)
            rel = abs_path.relative_to(repo_root).as_posix()
            if _is_excluded(rel):
                continue
            out.append((abs_path, rel))
    return out


def _print_text(results: list[FileResult]) -> None:
    summary_lines: list[str] = []
    for r in results:
        for issue in r.issues:
            summary_lines.append(issue.format(r.path))

    if summary_lines:
        sys.stdout.write("\n".join(summary_lines) + "\n")

    ok = sum(1 for r in results if r.status == "ok")
    warning = sum(1 for r in results if r.status == "warning")
    missing = sum(1 for r in results if r.status == "missing")
    invalid = sum(1 for r in results if r.status == "invalid")
    sys.stderr.write(
        f"\nSummary: total={len(results)} ok={ok} warning={warning} "
        f"missing={missing} invalid={invalid}\n"
    )


def _print_json(results: list[FileResult]) -> None:
    payload = [
        {
            "path": r.path,
            "status": r.status,
            "errors": [
                {"severity": i.severity, "rule": i.rule, "message": i.message}
                for i in r.errors
            ],
            "warnings": [
                {"severity": i.severity, "rule": i.rule, "message": i.message}
                for i in r.warnings
            ],
        }
        for r in results
    ]
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")


def _parse_store_arg(raw: str) -> str:
    return raw.strip("/")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="validate_document_frontmatter",
        description=(
            "Validate YAML frontmatter across the six Bodai doc stores "
            "against docs/schemas/document-frontmatter-v1.md."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Emit report and exit 0; never write anything (default behavior).",
    )
    parser.add_argument(
        "--allow-nonstandard",
        action="store_true",
        help="Tolerate inline ## Status markers outside frontmatter.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat unknown topic slugs as errors instead of warnings.",
    )
    parser.add_argument(
        "--validate-links",
        action="store_true",
        help="Resolve superseded_by / blocks_on entries against the corpus.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit one JSON object per file instead of structured text lines.",
    )
    parser.add_argument(
        "--store",
        action="append",
        default=[],
        metavar="NAME",
        help=(
            "Restrict scan to one of the six default stores by short name "
            "(adr, plans, superpowers-specs, superpowers-plans, decisions, followups). "
            "May be passed multiple times."
        ),
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        metavar="PATH",
        help="Repo root to validate. Defaults to first positional path or cwd.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Optional extra file or directory paths to include in the scan.",
    )
    return parser


STORE_LOOKUP = {
    "adr": "docs/adr/",
    "plans": "docs/plans/",
    "superpowers-specs": "docs/superpowers/specs/",
    "superpowers-plans": "docs/superpowers/plans/",
    "decisions": ".claude/decisions/",
    "followups": "docs/followups/",
}


def _resolve_repo_root(args: argparse.Namespace) -> Path:
    if args.repo_root is not None:
        return Path(args.repo_root).resolve()
    if args.paths:
        first = Path(args.paths[0]).resolve()
        return first if first.is_dir() else first.parent
    return Path.cwd()


def _resolve_stores(args: argparse.Namespace, repo_root: Path) -> list[Path] | None:
    if not args.store:
        return [repo_root / s for s in DEFAULT_STORES]
    stores_rel: list[str] = []
    for token in args.store:
        if token not in STORE_LOOKUP:
            sys.stderr.write(
                f"unknown --store value {token!r}; valid: {sorted(STORE_LOOKUP)}\n"
            )
            return None
        stores_rel.append(STORE_LOOKUP[token])
    return [repo_root / s for s in stores_rel]


def _validation_exit_code(results: list[FileResult]) -> int:
    return 1 if any(r.errors for r in results) else 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code != 0 else 0

    repo_root = _resolve_repo_root(args)
    stores = _resolve_stores(args, repo_root)
    if stores is None:
        return 2

    extra_paths = [Path(p).resolve() for p in args.paths]

    files = discover_files(repo_root, stores, extra_paths)
    if not files:
        sys.stderr.write("No candidate files found for the given inputs.\n")
        return 0

    known_topics = load_seed_topics(repo_root)
    known_files = {rel for _, rel in files}
    known_files.update(_index_extra(repo_root))

    results: list[FileResult] = [
        validate_file(
            abs_path,
            rel,
            repo_root=repo_root,
            known_files=known_files,
            known_topics=known_topics,
            strict=args.strict,
            allow_nonstandard=args.allow_nonstandard,
            validate_links=args.validate_links,
            skip_link_note=not args.validate_links,
        )
        for abs_path, rel in files
    ]

    if args.json:
        _print_json(results)
    else:
        _print_text(results)

    return _validation_exit_code(results)


def _index_extra(repo_root: Path) -> set[str]:
    found: set[str] = set()
    for store in DEFAULT_STORES:
        root = repo_root / store
        if not root.is_dir():
            continue
        for path in root.rglob("*.md"):
            try:
                rel = path.relative_to(repo_root).as_posix()
            except ValueError:
                continue
            if _is_excluded(rel):
                continue
            found.add(rel)
    return found
