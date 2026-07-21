"""C2 sweep: restore proper YAML frontmatter on docs the version-bump regressed.

Diagnostic script. Detects files that have the non-standard
'______________________________________________________________________\n\n## status: ...' header introduced by accident
in commit 46676c95 (chore: bump version to 0.69.1), and prints the proposed
replacement (--- delimited YAML frontmatter) for review.

NOT destructive. Apply with --apply after the dry-run is reviewed.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path("/Users/les/Projects/crackerjack")

# Match the broken header block. The first line is 70 underscores,
# the second line is blank, and the third line is `## status:` followed
# by all the key/value pairs collapsed onto one line.
BROKEN_HEADER_RE = re.compile(
    r"\A_{70}\n\n## status:\s*(?P<kv>.*?)(?=\n\n|\Z)",
    re.DOTALL,
)

# Each pair looks like: key: value (separated by single space). The values
# may be a literal (e.g. null, []) or a quoted string.
KV_RE = re.compile(r"(?P<key>[a-z_]+):\s*(?P<val>\"[^\"]*\"|\[[^\]]*\]|null|[^\s\[]+(?:\s+[^\s\[]+)*?)(?=\s+[a-z_]+:\s|$)")


def _parse_kv_line(line: str) -> dict[str, str]:
    """Parse the collapsed key: value line into a dict.

    The broken format puts the `status` value right after the `## status:`
    heading marker (no key), then key: value pairs follow. So the first
    token is the status value, and subsequent tokens are key: value.
    """
    text = line.strip()
    parts: dict[str, str] = {}

    # Split on first space to peel off the status value.
    # After `## status:` the status value is the first whitespace-delimited
    # token. The remaining tokens are key: value pairs.
    known_keys = ["role", "date", "last_reviewed", "superseded_by", "blocks_on", "topic"]
    first_space = text.find(" ")
    if first_space == -1:
        # Just a single status value, no other fields
        return {"status": text}
    parts["status"] = text[:first_space]
    rest = text[first_space + 1:].strip()

    # Walk `rest` capturing key: value pairs (same approach as before).
    cursor = 0
    while cursor < len(rest):
        next_pos = len(rest)
        next_key = None
        for k in known_keys:
            pattern = f" {k}: " if cursor > 0 else f"{k}: "
            idx = rest.find(pattern, cursor)
            if idx != -1 and idx < next_pos:
                next_pos = idx
                next_key = k
        if next_key is None:
            break
        val_start = next_pos + len(next_key) + 2
        val_end = len(rest)
        for k in known_keys:
            pattern = f" {k}: "
            idx = rest.find(pattern, val_start)
            if idx != -1 and idx < val_end:
                val_end = idx
        parts[next_key] = rest[val_start:val_end].strip()
        cursor = val_end
    return parts


def _render_yaml(parsed: dict[str, str]) -> str:
    """Render parsed dict as a YAML frontmatter block."""
    # Order matters: status, role, date, last_reviewed, superseded_by, blocks_on, topic
    order = ["status", "role", "date", "last_reviewed", "superseded_by", "blocks_on", "topic"]
    lines = ["---"]
    for key in order:
        if key not in parsed:
            continue
        val = parsed[key]
        # Quote values that contain spaces, brackets, or special chars
        if val in ("null", "[]") or val.startswith("[") or val.startswith('"'):
            lines.append(f"{key}: {val}")
        else:
            lines.append(f"{key}: {val}")
    lines.append("---")
    lines.append("")  # trailing blank
    return "\n".join(lines) + "\n"


def find_broken_files() -> list[Path]:
    """Walk the 6 validator stores, return files with the broken header."""
    stores = [
        "docs/adr",
        "docs/plans",
        "docs/superpowers/specs",
        "docs/superpowers/plans",
        ".claude/decisions",
        "docs/followups",
    ]
    broken: list[Path] = []
    for store in stores:
        root = REPO_ROOT / store
        if not root.is_dir():
            continue
        for p in root.rglob("*.md"):
            text = p.read_text(encoding="utf-8")
            if BROKEN_HEADER_RE.search(text):
                broken.append(p)
    return sorted(broken)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Apply the fix in place")
    args = parser.parse_args()

    broken = find_broken_files()
    if not broken:
        print("No broken files found.")
        return 0

    print(f"Found {len(broken)} files with broken frontmatter.\n")

    failures: list[str] = []
    for path in broken:
        rel = path.relative_to(REPO_ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        m = BROKEN_HEADER_RE.search(text)
        if not m:
            continue
        kv_line = m.group("kv")
        parsed = _parse_kv_line(kv_line)
        if not parsed:
            print(f"!! {rel}: could not parse kv line: {kv_line!r}")
            failures.append(rel)
            continue
        new_header = _render_yaml(parsed)
        body = text[m.end():]
        new_text = new_header + body

        if args.apply:
            path.write_text(new_text, encoding="utf-8")
            print(f"  fixed: {rel}")
        else:
            print(f"--- {rel} (dry-run) ---")
            print(new_header)
            print("  (...body unchanged...)")
            print()

    if failures:
        print(f"\n{len(failures)} file(s) could not be auto-fixed:")
        for f in failures:
            print(f"  {f}")
        return 1

    if not args.apply:
        print("\nRe-run with --apply to write changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
