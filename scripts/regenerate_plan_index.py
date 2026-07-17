#!/usr/bin/env uv run python
"""Regenerate docs/plans/PLAN_INDEX.md from per-store frontmatter.

Walks the six Bodai documentation stores, parses YAML frontmatter on each
``.md`` file, and emits a deterministic index grouped by store and sorted
by date DESC within each store. The output mirrors the structure of the
previous hand-edited PLAN_INDEX.md (status legend, authority matrix, review
entry points, registry tables, lifecycle-by-role distribution) but every
registry entry is mechanically derived from `status:` / `role:` / `topic:`
on the source files, so the index cannot drift from the corpus.

Usage:
    uv run python scripts/regenerate_plan_index.py [--dry-run] [--out PATH]

Default --out: docs/plans/PLAN_INDEX.md. Pass --dry-run to print the
generated markdown to stdout and skip writing.

Default stores scanned (POSIX, relative to repo root):
    docs/adr/
    docs/plans/                    (excluding drafts/ subdirectory)
    docs/superpowers/specs/
    docs/superpowers/plans/
    .claude/decisions/
    docs/followups/

Always excluded:
    docs/plans/PLAN_INDEX.md (this script's own output — self-skip)
    Any *.archive* or *.backup* / *.backup.json subdirectory anywhere
    under the six stores.

Exit codes:
    0 = success (file written or --dry-run)
    2 = bad CLI args or missing dependency
"""
from __future__ import annotations

import argparse
import datetime
import re
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants — mirrors validate_document_frontmatter.py
# ---------------------------------------------------------------------------

LIFECYCLE_VALUES: tuple[str, ...] = (
    "draft",
    "active",
    "partial",
    "shipped",
    "complete",
)
ROLE_VALUES: tuple[str, ...] = (
    "canonical",
    "implementation",
    "umbrella",
    "historical",
    "superseded",
)

# The six stores scanned, relative to the repo root. Order in this list is
# the order they appear in the registry section.
DEFAULT_STORES: tuple[str, ...] = (
    "docs/adr/",
    "docs/plans/",
    "docs/superpowers/specs/",
    "docs/superpowers/plans/",
    ".claude/decisions/",
    "docs/followups/",
)

# Display labels per store (used as section headers).
STORE_LABELS: dict[str, str] = {
    "docs/adr/": "Architecture Decision Records (`docs/adr/`)",
    "docs/plans/": "Plans & Specifications (`docs/plans/`)",
    "docs/superpowers/specs/": "Superpowers Specs (`docs/superpowers/specs/`)",
    "docs/superpowers/plans/": "Superpowers Plans (`docs/superpowers/plans/`)",
    ".claude/decisions/": "Repo-local Decisions (`.claude/decisions/`)",
    "docs/followups/": "Follow-up Notes (`docs/followups/`)",
}

# Always-excluded entries.
SELF_SKIP_REL = "docs/plans/PLAN_INDEX.md"
DRAFTS_PREFIX = "docs/plans/drafts/"
ARCHIVE_PARTS = ("archive", ".archive")
BACKUP_SUFFIXES = (".backup", ".backup.json")

# Frontmatter regex — captures the YAML block between the opening and
# closing `---` fences. Anchored at start of file (DOTALL via the inner
# pattern but \A prevents matches inside the body).
_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|$)", re.DOTALL)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Entry:
    """One row in the registry — a file with parsed frontmatter."""

    rel: str           # repo-relative POSIX path
    store: str         # e.g. "docs/adr/"
    date: str          # ISO-8601 (YYYY-MM-DD), or "" if missing
    status: str        # lifecycle value, or "unknown" if missing
    role: str          # role value, or "unknown" if missing
    topic: str         # topic slug, or "—" if missing
    title: str         # one-line title derived from first H1 / filename


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------


def _load_yaml_module() -> Any:
    """PyYAML is part of crackerjack's env. Defer import so the script's
    error message names the missing dependency instead of a Traceback."""
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover - exercised only on bare envs
        sys.stderr.write(
            "PyYAML is required to parse document frontmatter. "
            "Install with: uv pip install pyyaml\n"
            f"Original error: {exc}\n"
        )
        raise SystemExit(2) from exc
    return yaml


def extract_frontmatter(text: str, yaml_module: Any) -> dict[str, Any] | None:
    """Return the parsed YAML mapping from `text`, or None when no
    frontmatter block is present. Returns {} for an empty `---` block."""
    match = _FRONTMATTER_RE.match(text)
    if match is None:
        return None
    raw = match.group(1)
    parsed = yaml_module.safe_load(raw)
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        # Not a mapping — treat as malformed so the entry is filtered later.
        return None
    return parsed


def _coerce_date(value: Any) -> str:
    """PyYAML parses bare `date: 2026-07-16` into datetime.date; coerce
    both that and string forms to YYYY-MM-DD."""
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, str):
        return value
    return ""


def _title_from_text(text: str, fallback: str) -> str:
    """First level-1 heading text, or `fallback` (typically the filename
    stem) when the document has no H1."""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
    return fallback


# ---------------------------------------------------------------------------
# File discovery & filtering
# ---------------------------------------------------------------------------


def _is_excluded(rel: str) -> bool:
    if rel == SELF_SKIP_REL:
        return True
    if rel.startswith(DRAFTS_PREFIX):
        return True
    parts = rel.split("/")
    for part in parts:
        if part in ARCHIVE_PARTS:
            return True
    for suffix in BACKUP_SUFFIXES:
        if rel.endswith(suffix):
            return True
    return False


def discover_files(repo_root: Path, store_rel: str) -> list[tuple[Path, str]]:
    """Return [(absolute_path, repo_relative_posix_path)] for every .md
    file under the given store, after applying exclusion rules."""
    root = repo_root / store_rel.rstrip("/")
    if not root.is_dir():
        return []
    out: list[tuple[Path, str]] = []
    for path in sorted(root.rglob("*.md")):
        rel = path.relative_to(repo_root).as_posix()
        if _is_excluded(rel):
            continue
        out.append((path, rel))
    return out


# ---------------------------------------------------------------------------
# Per-file entry construction
# ---------------------------------------------------------------------------


def _entry_from_file(
    abs_path: Path, rel: str, store: str, yaml_module: Any
) -> Entry | None:
    """Parse one file. Returns None when the file has no valid frontmatter
    or fails to read — those are silently skipped because PLAN_INDEX only
    indexes docs that have frontmatter (the validator's contract)."""
    try:
        text = abs_path.read_text(encoding="utf-8")
    except OSError:
        return None
    front = extract_frontmatter(text, yaml_module)
    if front is None:
        return None
    if not isinstance(front, dict):
        return None

    date = _coerce_date(front.get("date"))
    status = front.get("status") if isinstance(front.get("status"), str) else "unknown"
    role = front.get("role") if isinstance(front.get("role"), str) else "unknown"
    topic = front.get("topic") if isinstance(front.get("topic"), str) else "—"
    fallback_title = abs_path.stem.replace("-", " ").replace("_", " ")
    title = _title_from_text(text, fallback=fallback_title)

    return Entry(
        rel=rel,
        store=store,
        date=date,
        status=status,
        role=role,
        topic=topic,
        title=title,
    )


# ---------------------------------------------------------------------------
# Rendering — fixed (static) sections
# ---------------------------------------------------------------------------

# Status legend copied verbatim from docs/schemas/document-frontmatter-v1.md
# (Vocabulary — Lifecycle + Vocabulary — Role).
STATUS_LEGEND = """\
## Status Legend

The vocabulary is defined canonically in
[`docs/schemas/document-frontmatter-v1.md`](../schemas/document-frontmatter-v1.md)
and reproduced here for index readability.

- **Lifecycle (`status`)** — five values:
  - `draft` — in preparation; not yet approved for implementation or adoption.
  - `active` — approved and in current use; being executed or applied as policy.
  - `partial` — approved and partially implemented; remaining work documented.
  - `shipped` — delivered and verified in production; closed.
  - `complete` — delivered; verification or follow-up may still be open.
- **Role (`role`)** — five values:
  - `canonical` — authoritative reference; source of truth for its topic.
  - `implementation` — a plan, spec, or followup that drives concrete work.
  - `umbrella` — aggregates multiple child plans or decisions under one banner.
  - `historical` — records decisions or outcomes after they were acted on.
  - `superseded` — replaced by a newer document; always paired with `superseded_by`.
- Legal combinations read as lifecycle + role, e.g. `active, implementation`,
  `draft, umbrella`, `shipped, canonical`.
"""


def _authority_matrix() -> str:
    """Small table mapping concerns to authorities. Mirrors the original
    PLAN_INDEX.md authority matrix and is intentionally narrow — the
    bulk of navigation now lives in the registry below."""
    return """\
## Authority Matrix

| Concern | Authority |
|---|---|
| Plan navigation and current ownership | `docs/plans/PLAN_INDEX.md` (this file, regenerated from frontmatter) |
| Frontmatter vocabulary and migration contract | `docs/schemas/document-frontmatter-v1.md` |
| Cross-repo LLM provider defaults and Bifrost routing | `docs/plans/2026-05-10-minimax27-provider-migration.md` |
| Legacy backlog item details | `docs/plans/2026-05-07-mahavishnu-master-backlog.md` |
| Bodai control-plane convergence C0–C7 | `docs/plans/2026-05-10-bodai-control-plane-convergence-plan.md` |
| Bodai-wide observability surface | `docs/plans/2026-07-11-phase-6-bodai-observability.md` |
| Repo-local decisions index | `.claude/decisions/README.md` |
| Follow-up tracker index | `docs/followups/README.md` |
| Source plan defining this index | `docs/superpowers/plans/2026-07-16-plan-lifecycle-unification.md` |
"""


def _review_entry_points(generated_at: str) -> str:
    return f"""\
## Review Entry Points

This file is regenerated mechanically from the per-file YAML frontmatter
across the six stores. The registry tables below are sorted by `date`
DESC within each store and group entries by store. The lifecycle × role
distribution at the bottom is a quick consistency check — it should
match the counts of the registry rows modulo files in skipped
directories (see exclusion rules in the script header).

Before implementing from any entry:

1. Confirm the file's lifecycle is `active` or `partial` and its role is
   `implementation` or `canonical`. Files with `role: historical`,
   `role: superseded`, or `status: shipped` are reference material only.
1. If the file has a populated `superseded_by:` field, jump to the
   successor before reading further.
1. If the file has a non-empty `blocks_on:` list, verify every entry
   has shipped before scheduling the dependent work.

Last regenerated: {generated_at}.
"""


# ---------------------------------------------------------------------------
# Rendering — registry tables
# ---------------------------------------------------------------------------


def _entry_link(rel: str, store: str) -> str:
    """POSIX link to the file from the index's home at docs/plans/.
    Files outside docs/plans/ need an explicit relative prefix."""
    if rel.startswith("docs/plans/"):
        depth = 1  # file lives in same directory as the index
    elif rel.startswith("docs/"):
        depth = 2  # up one (docs/), then down into the actual path
    elif rel.startswith(".claude/"):
        depth = 2  # up one to repo root, then into .claude/
    else:
        depth = 2
    prefix = "../" * (depth - 1)
    return f"[`{rel}`]({prefix}{rel})"


def _render_store_table(store: str, entries: list[Entry]) -> str:
    label = STORE_LABELS.get(store, store.rstrip("/"))
    rows: list[str] = []
    rows.append(f"### {label}")
    rows.append("")
    rows.append(
        "| Path | Date | Status | Role | Topic | Title |"
    )
    rows.append(
        "|---|---|---|---|---|---|"
    )
    if not entries:
        rows.append("| _no entries with valid frontmatter_ | | | | | |")
        rows.append("")
        return "\n".join(rows)

    # Sort by date DESC, then by rel ASC for deterministic ordering when
    # two files share the same date.
    sorted_entries = sorted(entries, key=lambda e: (-_date_sort_key(e.date), e.rel))
    for entry in sorted_entries:
        link = _entry_link(entry.rel, entry.store)
        rows.append(
            f"| {link} "
            f"| {entry.date or '—'} "
            f"| `{entry.status}` "
            f"| `{entry.role}` "
            f"| `{entry.topic}` "
            f"| {entry.title} |"
        )
    rows.append("")
    return "\n".join(rows)


def _date_sort_key(value: str) -> int:
    """Encode YYYY-MM-DD as a sortable int (yyyymmdd); empty/invalid keys
    sort to 0 so unknown dates cluster at the bottom."""
    if not value:
        return 0
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", value)
    if not match:
        return 0
    return int(match.group(1)) * 10000 + int(match.group(2)) * 100 + int(match.group(3))


# ---------------------------------------------------------------------------
# Rendering — lifecycle × role distribution
# ---------------------------------------------------------------------------


def _render_distribution(entries: list[Entry]) -> str:
    counts: Counter[tuple[str, str]] = Counter()
    for e in entries:
        # Skip "unknown" rows so they don't pollute the matrix.
        if e.status == "unknown" or e.role == "unknown":
            continue
        counts[(e.status, e.role)] += 1

    rows: list[str] = []
    rows.append("## Lifecycle × Role Distribution")
    rows.append("")
    rows.append("Counts of entries per (lifecycle, role) cell across all six stores. "
                 "Useful as a sanity check that the registry above is internally consistent.")
    rows.append("")
    # Build a header: blank corner + each lifecycle.
    header = "| Role \\\\ Lifecycle | " + " | ".join(LIFECYCLE_VALUES) + " | Total |"
    sep = "|---|" + "|".join(["---"] * (len(LIFECYCLE_VALUES) + 1)) + "|"
    rows.append(header)
    rows.append(sep)

    for role in ROLE_VALUES:
        cells: list[str] = []
        row_total = 0
        for lifecycle in LIFECYCLE_VALUES:
            cell_value = counts.get((lifecycle, role), 0)
            row_total += cell_value
            cells.append(str(cell_value) if cell_value else "·")
        rows.append(f"| `{role}` | " + " | ".join(cells) + f" | **{row_total}** |")
    rows.append("")

    # Column totals row.
    col_totals: list[str] = []
    grand_total = 0
    for lifecycle in LIFECYCLE_VALUES:
        col_sum = sum(counts.get((lifecycle, role), 0) for role in ROLE_VALUES)
        grand_total += col_sum
        col_totals.append(str(col_sum) if col_sum else "·")
    rows.append(
        "| **Total** | "
        + " | ".join(f"**{t}**" for t in col_totals)
        + f" | **{grand_total}** |"
    )
    rows.append("")
    return "\n".join(rows)


# ---------------------------------------------------------------------------
# Top-level composition
# ---------------------------------------------------------------------------


def _render_index(entries_by_store: dict[str, list[Entry]], generated_at: str) -> str:
    sections: list[str] = []
    sections.append(
        "---\n"
        "status: active\n"
        "role: canonical\n"
        "date: 2026-07-16\n"
        "last_reviewed: 2026-07-16\n"
        "superseded_by: null\n"
        "blocks_on:\n"
        "  - docs/schemas/document-frontmatter-v1.md\n"
        "topic: convergence-control-plane\n"
        "---"
    )
    sections.append("")
    sections.append("# Plan Index")
    sections.append("")
    sections.append(f"**Date:** 2026-07-16")
    sections.append(f"**Last regenerated:** {generated_at}")
    sections.append(
        "**Purpose:** Navigation map for finding and reviewing active "
        "Mahavishnu/Bodai plans. Generated by `scripts/regenerate_plan_index.py`. "
        "Do not edit by hand."
    )
    sections.append("")
    sections.append(
        "Use this file as the first stop before reviewing plan work. Older plans "
        "remain useful as source material, but the authority matrix below defines "
        "which document owns each kind of decision."
    )
    sections.append("")
    sections.append(STATUS_LEGEND.rstrip())
    sections.append("")
    sections.append(_authority_matrix().rstrip())
    sections.append("")
    sections.append(_review_entry_points(generated_at).rstrip())
    sections.append("")

    sections.append("## Canonical and Active Plan Registry")
    sections.append("")
    sections.append(
        "One table per store. Entries are sorted by `date` DESC, with ties broken "
        "by path ASC. Files without valid frontmatter are excluded; run "
        "`uv run python scripts/validate_document_frontmatter.py --allow-nonstandard` "
        "to surface them."
    )
    sections.append("")

    all_entries: list[Entry] = []
    for store in DEFAULT_STORES:
        store_entries = entries_by_store.get(store, [])
        all_entries.extend(store_entries)
        sections.append(_render_store_table(store, store_entries).rstrip())
        sections.append("")

    sections.append(_render_distribution(all_entries).rstrip())

    return "\n".join(sections) + "\n"


# ---------------------------------------------------------------------------
# CLI + main
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="regenerate_plan_index",
        description=(
            "Regenerate docs/plans/PLAN_INDEX.md from the YAML frontmatter "
            "of all .md files in the six Bodai doc stores."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the generated index to stdout instead of writing the file.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("docs/plans/PLAN_INDEX.md"),
        help="Output path (default: docs/plans/PLAN_INDEX.md).",
    )
    parser.add_argument(
        "--json-summary",
        action="store_true",
        help=(
            "Emit a JSON summary of counts (per store + total) on stderr. "
            "Useful for CI assertions."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code != 0 else 0

    repo_root = Path(__file__).resolve().parent.parent
    yaml_module = _load_yaml_module()

    entries_by_store: dict[str, list[Entry]] = {}
    total_with_frontmatter = 0
    total_discovered = 0
    for store in DEFAULT_STORES:
        files = discover_files(repo_root, store)
        store_entries: list[Entry] = []
        for abs_path, rel in files:
            total_discovered += 1
            entry = _entry_from_file(abs_path, rel, store, yaml_module)
            if entry is None:
                continue
            store_entries.append(entry)
        entries_by_store[store] = store_entries
        total_with_frontmatter += len(store_entries)

    generated_at = datetime.date.today().isoformat()
    rendered = _render_index(entries_by_store, generated_at=generated_at)

    if args.dry_run:
        sys.stdout.write(rendered)
    else:
        out_path = args.out
        if not out_path.is_absolute():
            out_path = (repo_root / out_path).resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: tempfile in the same directory + rename.
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=str(out_path.parent),
            prefix=f".{out_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as tmp:
            tmp.write(rendered)
            tmp_path = Path(tmp.name)
        try:
            tmp_path.replace(out_path)
        except OSError:
            # Fallback for cross-device moves etc.
            tmp_path.replace(out_path)

    if args.json_summary:
        import json
        summary = {
            "generated_at": generated_at,
            "discovered": total_discovered,
            "with_frontmatter": total_with_frontmatter,
            "per_store": {
                store: len(entries_by_store.get(store, []))
                for store in DEFAULT_STORES
            },
        }
        sys.stderr.write(json.dumps(summary, indent=2) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
