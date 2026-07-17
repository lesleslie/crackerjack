#!/usr/bin/env uv run python
"""Validate document frontmatter against the document-frontmatter-v1 schema.

Usage:
    uv run python scripts/validate_document_frontmatter.py [--dry-run]
        [--allow-nonstandard] [--strict] [--store=NAME]
        [--validate-links] [--json] [PATH...]

Default scan covers six stores under the repo root:
    docs/adr/, docs/plans/, docs/superpowers/specs/,
    docs/superpowers/plans/, .claude/decisions/, docs/followups/

Always excluded:
    docs/plans/PLAN_INDEX.md, docs/plans/drafts/*, *.backup, *.backup.json

Exit codes:
    0 = clean (or --dry-run)
    1 = validation errors
    2 = broken CLI args
"""

from __future__ import annotations

import argparse
import datetime
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Schema constants
LIFECYCLE_VALUES = {"draft", "active", "partial", "shipped", "complete"}
ROLE_VALUES = {"canonical", "implementation", "umbrella", "historical", "superseded"}
RESERVED_WORDS = (
    LIFECYCLE_VALUES | ROLE_VALUES
)  # words that cannot be used as topic slugs

ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
TOPIC_SLUG_RE = re.compile(r"^[a-z][a-z0-9-]{2,40}$")
EXT_LINK_RE = re.compile(r"^ext:[A-Za-z0-9_.\-:]+$")

# The six stores scanned by default, relative to the repo root.
DEFAULT_STORES = (
    "docs/adr/",
    "docs/plans/",
    "docs/superpowers/specs/",
    "docs/superpowers/plans/",
    ".claude/decisions/",
    "docs/followups/",
)

# Paths to skip no matter how the file was reached.
ALWAYS_EXCLUDE_REL = (
    "docs/plans/PLAN_INDEX.md",
)
ALWAYS_EXCLUDE_DIRS_REL = (
    "docs/plans/drafts/",
)
ALWAYS_EXCLUDE_SUFFIXES = (".backup", ".backup.json")

# Files in .claude/decisions/ use the lite schema (no superseded_by/blocks_on).
DECISIONS_DIR = Path(".claude/decisions")

# Inline status blocks under a "## Status" heading are tolerated when
# --allow-nonstandard is set; otherwise they emit NONSTANDARD_INLINE_STATUS.
INLINE_STATUS_HEADING_RE = re.compile(
    r"^#{2,}\s*Status\s*$", re.IGNORECASE | re.MULTILINE
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Issue:
    severity: str  # "ERROR" | "WARNING" | "NOTE"
    rule: str  # short machine-friendly code
    message: str

    def format(self, path: str) -> str:
        return f"file={path} [{self.severity}] {self.rule}={self.message}"


@dataclass
class FileResult:
    path: str  # repo-relative POSIX path
    status: str  # "ok" | "missing" | "invalid" | "warning"
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


# ---------------------------------------------------------------------------
# Topic vocabulary loader
# ---------------------------------------------------------------------------


def load_seed_topics(repo_root: Path) -> set[str]:
    """Parse topic-vocabulary-v1.md and return the seed slug set."""
    vocab_path = repo_root / "docs/schemas/topic-vocabulary-v1.md"
    if not vocab_path.is_file():
        # Missing vocabulary file is not fatal — degrade to unknown-topic warnings.
        return set()

    text = vocab_path.read_text(encoding="utf-8")
    seeds: set[str] = set()

    # Slugs only appear in the seed list table; scan for backtick-wrapped
    # single-word entries that match the slug pattern.
    in_seed_section = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            in_seed_section = stripped.lower().startswith("## seed list")
            continue
        if not in_seed_section:
            continue
        # Format is `| `mcp-design` | Definition |`
        if "|" not in stripped:
            continue
        for match in re.finditer(r"`([a-z][a-z0-9-]{2,40})`", stripped):
            seeds.add(match.group(1))
    return seeds


# ---------------------------------------------------------------------------
# Frontmatter extraction
# ---------------------------------------------------------------------------


_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL
)


def extract_frontmatter(text: str) -> tuple[dict[str, Any] | None, str | None]:
    """Return (parsed_dict, error). On parse failure error is non-None."""
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        return None, None

    raw = match.group(1)
    try:
        import yaml  # local import — PyYAML is part of crackerjack's env
    except ImportError as exc:
        return None, f"PyYAML unavailable: {exc}"

    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        return None, f"YAML parse error: {exc}"

    if parsed is None:
        return {}, None
    if not isinstance(parsed, dict):
        return None, "Frontmatter is not a YAML mapping"
    return parsed, None


# ---------------------------------------------------------------------------
# Per-file validation
# ---------------------------------------------------------------------------


def _validate_date(
    value: Any, field_name: str, result: FileResult, path: str
) -> None:
    # PyYAML parses bare `date: 2026-07-16` into datetime.date; accept that as
    # equivalent to the canonical YYYY-MM-DD string form.
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
            )
        )


def _validate_topic(
    value: Any,
    known_topics: set[str],
    strict: bool,
    result: FileResult,
) -> None:
    if not isinstance(value, str):
        result.add(
            Issue(
                "ERROR",
                "topic_invalid",
                f"topic must be a slug string; got {type(value).__name__}",
            )
        )
        return
    if not TOPIC_SLUG_RE.match(value):
        result.add(
            Issue(
                "ERROR",
                "topic_invalid",
                f"topic {value!r} does not match ^[a-z][a-z0-9-]{{2,40}}$",
            )
        )
        return
    if value.lower() in RESERVED_WORDS:
        result.add(
            Issue(
                "ERROR",
                "topic_reserved",
                f"topic {value!r} collides with a lifecycle/role word",
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
            )
        )


def _validate_superseded_by(
    value: Any,
    repo_root: Path,
    known_files: set[str],
    result: FileResult,
) -> None:
    if value is None:
        return  # superseded_by is only required when role == superseded
    # BUG 2 fix: accept either a scalar string or a list of strings.
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
            )
        )


def _validate_blocks_on(
    value: Any,
    repo_root: Path,
    known_files: set[str],
    result: FileResult,
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
            )
        )


def _validate_role_status_pair(
    front: dict[str, Any], result: FileResult
) -> None:
    role = front.get("role")
    if role == "superseded":
        if "superseded_by" not in front:
            result.add(
                Issue(
                    "ERROR",
                    "superseded_by_required",
                    "role: superseded requires a populated superseded_by field",
                )
            )
        elif front.get("superseded_by") in (None, "", []):
            result.add(
                Issue(
                    "ERROR",
                    "superseded_by_required",
                    "role: superseded requires a populated superseded_by field",
                )
            )


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

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        result.add(
            Issue("ERROR", "read_error", f"cannot read file: {exc}")
        )
        result.status = "invalid"
        return result

    front, err = extract_frontmatter(text)
    if err is not None:
        result.add(Issue("ERROR", "frontmatter_parse", err))
        result.status = "invalid"
        return result
    if front is None:
        result.add(
            Issue(
                "ERROR",
                "MISSING_FRONTMATTER",
                "no YAML frontmatter (expected --- delimited block at top)",
            )
        )
        result.status = "missing"
        return result

    # Lite-schema path: .claude/decisions/ — no superseded_by / blocks_on required.
    is_lite = rel.startswith(".claude/decisions/")

    # Required key presence
    for key in ("status", "role", "date", "last_reviewed", "topic"):
        if key not in front:
            result.add(
                Issue("ERROR", f"{key}_missing", f"required key {key!r} absent")
            )

    # status enum
    status = front.get("status")
    # BUG 3 fix: coerce legacy "Resolved" / "Resolved." (case-insensitive,
    # optional trailing punctuation) to the canonical "complete" value before
    # running the vocabulary check. Source: legacy mapping table in
    # docs/schemas/document-frontmatter-v1.md ("Resolved -> complete").
    if isinstance(status, str):
        normalized = status.strip().rstrip(".").lower()
        if normalized == "resolved":
            front["status"] = "complete"
            status = front["status"]
    if "status" in front and status not in LIFECYCLE_VALUES:
        result.add(
            Issue(
                "ERROR",
                "status_invalid",
                f"status {status!r} not in {sorted(LIFECYCLE_VALUES)}",
            )
        )

    # role enum
    role = front.get("role")
    if "role" in front and role not in ROLE_VALUES:
        result.add(
            Issue(
                "ERROR",
                "role_invalid",
                f"role {role!r} not in {sorted(ROLE_VALUES)}",
            )
        )

    # date / last_reviewed
    _validate_date(front.get("date"), "date", result, rel)
    _validate_date(front.get("last_reviewed"), "last_reviewed", result, rel)

    # topic
    _validate_topic(front.get("topic"), known_topics, strict, result)

    # Full-schema fields: superseded_by / blocks_on
    if not is_lite:
        # When role: superseded, superseded_by must be populated (already checked
        # above in _validate_role_status_pair). Optional otherwise.
        if "superseded_by" in front and validate_links:
            _validate_superseded_by(
                front.get("superseded_by"), repo_root, known_files, result
            )
        elif "superseded_by" in front and not validate_links:
            if skip_link_note:
                result.add(
                    Issue(
                        "NOTE",
                        "link_validation_skipped",
                        "superseded_by present; --validate-links disabled, skipping "
                        "resolution check",
                    )
                )

        if "blocks_on" in front and validate_links:
            _validate_blocks_on(
                front.get("blocks_on"), repo_root, known_files, result
            )
        elif "blocks_on" in front and not validate_links:
            if skip_link_note:
                result.add(
                    Issue(
                        "NOTE",
                        "link_validation_skipped",
                        "blocks_on present; --validate-links disabled, skipping "
                        "resolution check",
                    )
                )

    _validate_role_status_pair(front, result)

    # Inline status blocks are tolerated only with --allow-nonstandard.
    if not allow_nonstandard and INLINE_STATUS_HEADING_RE.search(text):
        result.add(
            Issue(
                "WARNING",
                "NONSTANDARD_INLINE_STATUS",
                "inline '## Status' block detected outside frontmatter; "
                "pass --allow-nonstandard to tolerate",
            )
        )

    # Final status determination
    if result.errors:
        result.status = "invalid"
    elif result.warnings:
        result.status = "warning"
    else:
        result.status = "ok"
    return result


# ---------------------------------------------------------------------------
# File discovery
# ---------------------------------------------------------------------------


def _is_excluded(rel: str) -> bool:
    if rel in ALWAYS_EXCLUDE_REL:
        return True
    for prefix in ALWAYS_EXCLUDE_DIRS_REL:
        if rel.startswith(prefix):
            return True
    # BUG 1 fix: skip any archive or .archive subdirectory in any path.
    # Mirrors docs/plans/drafts/ exclusion but applies recursively.
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
    """Return [(absolute_path, repo_relative_posix_path)] for every candidate file."""
    seen: set[Path] = set()
    out: list[tuple[Path, str]] = []

    candidates: list[Path] = []
    for store in stores:
        candidates.append(store)
    candidates.extend(extra_paths)

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


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


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
    payload = []
    for r in results:
        payload.append(
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
        )
    sys.stdout.write(json.dumps(payload, indent=2) + "\n")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


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


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code != 0 else 0

    repo_root = Path(__file__).resolve().parent.parent

    # Resolve stores
    if args.store:
        stores_rel: list[str] = []
        for token in args.store:
            if token not in STORE_LOOKUP:
                sys.stderr.write(
                    f"unknown --store value {token!r}; valid: "
                    f"{sorted(STORE_LOOKUP)}\n"
                )
                return 2
            stores_rel.append(STORE_LOOKUP[token])
    else:
        stores_rel = list(DEFAULT_STORES)

    stores = [repo_root / s for s in stores_rel]
    extra_paths = [Path(p).resolve() for p in args.paths]

    files = discover_files(repo_root, stores, extra_paths)
    if not files:
        sys.stderr.write("No candidate files found for the given inputs.\n")
        return 0

    known_topics = load_seed_topics(repo_root)
    known_files = {rel for _, rel in files}
    # Also add everything under the repo's six stores (cheap approx) so a path
    # like ../foo.md resolves when foo.md is itself in the scan set.
    known_files.update(_index_extra(repo_root))

    results: list[FileResult] = []
    for abs_path, rel in files:
        results.append(
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
        )

    if args.json:
        _print_json(results)
    else:
        _print_text(results)

    has_errors = any(r.errors for r in results)
    if has_errors:
        return 1
    return 0


def _index_extra(repo_root: Path) -> set[str]:
    """Expand the known-files set with the always-eligible store paths so a
    `superseded_by` may point at any file in those stores."""
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


if __name__ == "__main__":
    raise SystemExit(main())