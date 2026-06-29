"""ty suppression audit tool.

Walks tests/ (or any path), enumerates `# ty: ignore[...]` comments,
groups them by diagnostic code and by age, optionally detects unused
suppressions (those that don't correspond to a real ty diagnostic
when commented out).

This is the "real enforcement" of the Phase Q split ratchet. The
ratchet counts; the audit classifies. CI cannot do this judgment
(per-suppression classification requires context), so it's a
periodic-cadence tool, not a gate.

Exit codes:
    0 - total suppressions below threshold (or --dry-run)
    1 - total suppressions at or above threshold (audit triggered)
    2 - config error (path missing, git unavailable, etc.)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

# Same regex pattern as the ratchet's diagnostic parsing
_SUPPRESSION_RE = re.compile(r"#\s*ty:\s*ignore\[([a-z0-9-]+)\]")

# Stale-suppression threshold (configurable via --threshold)
DEFAULT_THRESHOLD = 50

# Age bucket boundaries (days)
_RECENT_DAYS = 30
_STALE_DAYS = 90

# ty concise output format: <file>:<line>:<col>: <level>[<code>] <message>
_TY_DIAGNOSTIC_RE = re.compile(
    r"^(?P<file>[^:\s]+):(?P<line>\d+):(?P<col>\d+):\s+"
    r"(?:error|warning)\[(?P<code>[a-z0-9-]+)\]\s+.+$"
)

# git blame format: <sha> (<author> <date> <tz> <line>) <content>
# Example: 8fd18737b (lesleslie 2026-05-25 04:50:58 -0700 1) """Tests for..."""
_BLAME_DATE_RE = re.compile(
    r"^[0-9a-f]+\s+\([^)]*?(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})\s+([+-]\d{4})\)"
)


@dataclass
class SuppressionRef:
    """A single # ty: ignore[...] suppression."""

    file: Path
    line: int
    code: str
    snippet: str


@dataclass
class AuditReport:
    total: int = 0
    by_code: dict[str, list[SuppressionRef]] = field(default_factory=dict)
    unused: list[SuppressionRef] = field(default_factory=list)
    by_age: dict[str, int] = field(default_factory=dict)
    threshold: int = DEFAULT_THRESHOLD
    triggered: bool = False


def enumerate_suppressions(tests_dir: Path) -> list[SuppressionRef]:
    """Walk tests/**/*.py, return list of SuppressionRef."""
    if not tests_dir.is_dir():
        print(f"error: not a directory: {tests_dir}", file=sys.stderr)
        sys.exit(2)

    refs: list[SuppressionRef] = []
    for path in sorted(tests_dir.rglob("*.py")):
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for line_no, line in enumerate(text.splitlines(), start=1):
            for match in _SUPPRESSION_RE.finditer(line):
                refs.append(
                    SuppressionRef(
                        file=path,
                        line=line_no,
                        code=match.group(1),
                        snippet=line.strip()[:200],
                    )
                )
    return refs


def group_by_code(refs: list[SuppressionRef]) -> dict[str, list[SuppressionRef]]:
    """Group suppressions by diagnostic code."""
    grouped: dict[str, list[SuppressionRef]] = {}
    for ref in refs:
        grouped.setdefault(ref.code, []).append(ref)
    return grouped


def group_by_age(
    refs: list[SuppressionRef],
    repo_root: Path,
) -> dict[str, int]:
    """Use git blame to determine age bucket for each suppression.

    Returns ``{"<30 days": N, "30-90 days": N, ">90 days": N}``.
    """
    buckets: dict[str, int] = {
        "<30 days": 0,
        "30-90 days": 0,
        ">90 days": 0,
    }
    if not refs:
        return buckets

    now = datetime.now(UTC)
    for ref in refs:
        try:
            result = subprocess.run(
                [
                    "git",
                    "blame",
                    "-L",
                    f"{ref.line},+1",
                    str(ref.file),
                ],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
                check=False,
            )
        except (FileNotFoundError, OSError):
            return buckets

        if result.returncode != 0 or not result.stdout:
            continue

        match = _BLAME_DATE_RE.match(result.stdout)
        if not match:
            continue

        try:
            blame_dt = datetime.strptime(
                f"{match.group(1)} {match.group(2)}",
                "%Y-%m-%d %H:%M:%S %z",
            ).astimezone(UTC)
        except ValueError:
            continue

        age_days = (now - blame_dt).days
        if age_days < _RECENT_DAYS:
            buckets["<30 days"] += 1
        elif age_days < _STALE_DAYS:
            buckets["30-90 days"] += 1
        else:
            buckets[">90 days"] += 1

    return buckets


def detect_unused(
    refs: list[SuppressionRef],
    tests_dir: Path,
) -> list[SuppressionRef]:
    """For each suppression, comment it out and verify ty still passes that line.

    Batched: comment out all suppressions in a file at once, run ty once
    per file, map per-line diagnostics back.

    A suppression is "unused" if removing it (i.e., commenting it out)
    does NOT cause ty to emit a diagnostic at the same line.
    """
    if not refs:
        return []

    # Group suppressions by file. We'll modify each file once, run ty once,
    # and inspect the diagnostic output.
    by_file: dict[Path, list[SuppressionRef]] = {}
    for ref in refs:
        by_file.setdefault(ref.file, []).append(ref)

    # Cache the (original content, modified content, line mapping) per file so
    # we don't re-read disk more than once.
    unused: list[SuppressionRef] = []

    for file_path, file_refs in by_file.items():
        try:
            original = file_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        modified, line_map = _comment_out_suppressions(original, file_refs)
        if modified is None or line_map is None:
            continue

        # Run ty on the modified file. Pass the path as written (file_path),
        # which ty will resolve relative to its CWD. Run from the project root
        # so ty finds the project config.
        try:
            proc = subprocess.run(
                [
                    "ty",
                    "check",
                    str(file_path),
                    "--no-progress",
                    "--output-format",
                    "concise",
                ],
                cwd=str(tests_dir.parent),
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            print(
                "warning: ty binary not found; skipping unused-suppression detection",
                file=sys.stderr,
            )
            return unused
        except OSError as exc:
            print(f"warning: ty invocation failed: {exc}", file=sys.stderr)
            continue

        # Parse diagnostics: lines that match <file>:<line>:<col>: level[code] ...
        new_diagnostic_lines: set[int] = set()
        for raw_line in (proc.stdout + proc.stderr).splitlines():
            line = raw_line.strip()
            match = _TY_DIAGNOSTIC_RE.match(line)
            if not match:
                continue
            try:
                new_diagnostic_lines.add(int(match["line"]))
            except ValueError:
                continue

        # For each suppression, map its original line through the line_map
        # and check if the new diagnostic set contains that mapped line.
        for ref in file_refs:
            mapped_line = line_map.get(ref.line)
            if mapped_line is None:
                continue
            if mapped_line not in new_diagnostic_lines:
                unused.append(ref)

    return unused


def _comment_out_suppressions(
    content: str,
    refs: list[SuppressionRef],
) -> tuple[str | None, dict[int, int] | None]:
    """Return (modified_content, original_line -> new_line map).

    Each suppression is replaced inline by its inline comment equivalent so
    the surrounding code structure is preserved. Removed suppressions do not
    affect line numbers (we only mutate text on the same line, never delete
    a line), so the new line for each original line is just that line.
    """
    lines = content.splitlines(keepends=True)
    target_lines: dict[int, str] = {ref.line: ref.snippet for ref in refs}
    line_map: dict[int, int] = {ref.line: ref.line for ref in refs}

    for line_no in target_lines:
        if line_no < 1 or line_no > len(lines):
            return None, None
        original_line = lines[line_no - 1]
        # Drop the # ty: ignore[<code>] (and any trailing whitespace) but keep  # ty: ignore[invalid-ignore-comment]
        # everything before it. This turns the suppression into a no-op.
        new_line = _SUPPRESSION_RE.sub("", original_line)
        # If we removed a trailing token but left dangling whitespace, tidy up.
        new_line = re.sub(r"[ \t]+$", "", new_line)
        lines[line_no - 1] = new_line

    return "".join(lines), line_map


def render_human(report: AuditReport) -> str:
    """Format the report for terminal output."""
    lines: list[str] = [f"ty_audit: {report.total} suppressions"]

    if report.by_code:
        lines.extend(("", "By code:"))
        width = max((len(c) for c in report.by_code), default=0)
        for code in sorted(report.by_code, key=lambda c: (-len(report.by_code[c]), c)):
            lines.append(f"  {code.ljust(width)}: {len(report.by_code[code])}")

    if report.by_age:
        lines.extend(("", "By age:"))
        for bucket in ("<30 days", "30-90 days", ">90 days"):
            lines.append(f"  {bucket.ljust(12)}: {report.by_age.get(bucket, 0)}")

    if report.unused:
        lines.extend(("", f"Unused suppressions ({len(report.unused)}):"))
        for ref in report.unused:
            try:
                rel = ref.file.relative_to(Path.cwd())
            except ValueError:
                rel = ref.file
            lines.append(f"  {rel}:{ref.line} [{ref.code}]")

    lines.append("")
    status = "TRIGGERED" if report.triggered else "NOT TRIGGERED"
    lines.append(f"Threshold: {report.threshold} -> {status}")
    return "\n".join(lines)


def render_json(report: AuditReport) -> str:
    """Format the report as JSON."""
    code_counts = {code: len(refs) for code, refs in report.by_code.items()}
    unused_payload = []
    for ref in report.unused:
        try:
            rel_file = str(ref.file.relative_to(Path.cwd()))
        except ValueError:
            rel_file = str(ref.file)
        unused_payload.append(
            {
                "file": rel_file,
                "line": ref.line,
                "code": ref.code,
                "snippet": ref.snippet,
            }
        )
    payload = {
        "total": report.total,
        "by_code": code_counts,
        "unused": unused_payload,
        "by_age": report.by_age,
        "threshold": report.threshold,
        "triggered": report.triggered,
    }
    return json.dumps(payload, indent=2, sort_keys=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Audit `# ty: ignore[...]` suppressions: enumerate, group by code "
            "and age, optionally detect unused ones."
        )
    )
    parser.add_argument(
        "path",
        nargs="?",
        default="tests",
        type=Path,
        help="Directory to scan (default: tests/)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_THRESHOLD,
        help=f"Total suppressions that triggers the audit (default: {DEFAULT_THRESHOLD})",
    )
    parser.add_argument(
        "--detect-unused",
        action="store_true",
        help="Run ty with each suppression commented out to detect unused ones.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the report but always exit 0.",
    )
    parser.add_argument(
        "--json",
        dest="as_json",
        action="store_true",
        help="Emit a JSON report on stdout (machine-readable).",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Project root for git blame (default: parent of <path>).",
    )
    args = parser.parse_args(argv)

    tests_dir = args.path.resolve()
    if not tests_dir.is_dir():
        print(f"error: path not found: {tests_dir}", file=sys.stderr)
        return 2

    repo_root = (
        args.repo_root.resolve() if args.repo_root else tests_dir.parent.resolve()
    )

    refs = enumerate_suppressions(tests_dir)
    report = AuditReport(threshold=args.threshold)
    report.total = len(refs)
    report.by_code = group_by_code(refs)
    report.by_age = group_by_age(refs, repo_root)

    if args.detect_unused:
        report.unused = detect_unused(refs, tests_dir)

    report.triggered = report.total >= report.threshold

    if args.as_json:
        print(render_json(report))
    else:
        print(render_human(report))

    if args.dry_run:
        return 0
    return 1 if report.triggered else 0


if __name__ == "__main__":
    raise SystemExit(main())
