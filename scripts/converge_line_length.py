#!/usr/bin/env python3
"""converge_line_length.py — set a repo's line length to the fleet standard.

The Bodai fleet's ruff line-length is not uniform by accident: the three
crackerjack project templates (``pyproject-{full,library,minimal}.toml``)
all pin 88, and 27 of the 36 repos match. A handful of repos drifted to 100
and were never brought back.

This script converges one repo onto the fleet standard:

- ``pyproject.toml`` — ``[tool.ruff] line-length`` and
  ``[tool.pylint.format] max-line-length``
- ``CLAUDE.md`` / ``AGENTS.md`` / ``.claude/**`` — the live guidance that
  states the limit to agents and to humans
- optionally, a ``ruff format`` pass over the repo's Python sources

Only *live* guidance is rewritten. Historical plans and specs are records of
past decisions, so they are deliberately left alone.

The script is idempotent: running it on a converged repo reports
"already converged" and changes nothing.

Usage:
    python scripts/converge_line_length.py ~/Projects/akosha
    python scripts/converge_line_length.py ~/Projects/akosha --dry-run
    python scripts/converge_line_length.py ~/Projects/akosha --format
    python scripts/converge_line_length.py ~/Projects/akosha --check
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_TARGET = 88

# Files whose text carries the live line-length guidance.
GUIDANCE_FILES = (
    "CLAUDE.md",
    "AGENTS.md",
)

GUIDANCE_GLOBS = (
    ".claude/agents/*.md",
    ".claude/skills/*/SKILL.md",
)

# Phrases that state the limit. Each is (pattern, template) where the
# template is rendered with ``old`` and ``target``.
GUIDANCE_PATTERNS = (
    (r"\| Line length \| \d+ chars \|", "| Line length | {target} chars |"),
    (r"Max line length: \*\*\d+ chars\*\*", "Max line length: **{target} chars**"),
    (r"Line length: \d+ chars", "Line length: {target} chars"),
    (r"line-length = \d+", "line-length = {target}"),
    (r"max-line-length = \d+", "max-line-length = {target}"),
)


@dataclass
class Report:
    """What the convergence pass changed."""

    repo: Path
    old_target: int | None = None
    new_target: int = DEFAULT_TARGET
    pyproject_changed: bool = False
    guidance_changed: list[str] = field(default_factory=list)
    reformatted_files: int = 0
    format_error: str = ""

    @property
    def converged(self) -> bool:
        return self.old_target == self.new_target


def read_toml_int(text: str, section: str, key: str) -> int | None:
    """Read an integer from a specific TOML table."""
    pattern = re.compile(
        rf"(?ms)^\[{re.escape(section)}\]\s*$(.*?)(?=^\[|\Z)",
    )
    match = pattern.search(text)
    if match is None:
        return None
    key_match = re.search(
        rf"(?m)^{re.escape(key)}\s*=\s*(\d+)[^\S\n]*$", match.group(1)
    )
    return int(key_match.group(1)) if key_match else None


def set_toml_int(text: str, section: str, key: str, value: int) -> tuple[str, bool]:
    """Set an integer inside a specific TOML table.

    Scoping to the table matters: several projects carry a ``[tool.black]``
    ``line-length`` alongside ruff's, and only ruff's is ours to change.
    """
    section_pattern = re.compile(
        rf"(?ms)^(\[{re.escape(section)}\]\s*)$(.*?)(?=^\[|\Z)",
    )
    match = section_pattern.search(text)
    if match is None:
        return text, False
    body = match.group(2)
    # ``[^\S\n]*`` rather than ``\s*``: a trailing ``\s`` would swallow the
    # newline and join the next line onto this one.
    new_body, count = re.subn(
        rf"(?m)^({re.escape(key)}\s*=\s*)(\d+)([^\S\n]*)$",
        rf"\g<1>{value}\g<3>",
        body,
    )
    if count == 0 or new_body == body:
        return text, False
    return text[: match.start(2)] + new_body + text[match.end(2) :], True


def has_ruff_config(repo: Path) -> bool:
    """True when the repo's pyproject declares a ``[tool.ruff]`` table.

    A repo with no ruff configuration has no line length to converge; it is
    skipped rather than reported as a failure forever.
    """
    pyproject = repo / "pyproject.toml"
    if not pyproject.is_file():
        return False
    text = pyproject.read_text(encoding="utf-8", errors="replace")
    return re.search(r"(?m)^\[tool\.ruff\]\s*$", text) is not None


def guidance_files(repo: Path) -> list[Path]:
    """Collect the files that carry live line-length guidance."""
    files: list[Path] = []
    for name in GUIDANCE_FILES:
        candidate = repo / name
        if candidate.is_file():
            files.append(candidate)
    for pattern in GUIDANCE_GLOBS:
        files.extend(sorted(repo.glob(pattern)))
    return files


def rewrite_guidance(text: str, target: int) -> tuple[str, bool]:
    """Rewrite the stated limit in a guidance document.

    Reports ``changed`` only when the text actually differs, so the script
    is idempotent: a converged repo reports no changes on a second run.
    """
    rewritten = text
    for pattern, template in GUIDANCE_PATTERNS:
        replacement = template.format(target=target)
        rewritten = re.sub(pattern, replacement, rewritten)
    return rewritten, rewritten != text


def resolve_ruff_command(repo: Path) -> list[str] | None:
    """Return the command prefix that runs ruff inside ``repo``."""
    if shutil.which("uv"):
        return ["uv", "run", "ruff"]
    if shutil.which("ruff"):
        return ["ruff"]
    return None


def count_files_ruff_would_reformat(
    repo: Path, ruff_cmd: list[str], target: int
) -> tuple[int, str]:
    """Ask ruff how many files it would reformat, without changing anything."""
    result = subprocess.run(
        [*ruff_cmd, "format", "--check", "--line-length", str(target), "."],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    combined = f"{result.stdout}\n{result.stderr}"
    match = re.search(r"Would reformat: (\d+) files?", combined)
    if match:
        return int(match.group(1)), ""
    return 0, combined.strip()


def run_ruff_format(repo: Path, ruff_cmd: list[str], target: int) -> tuple[int, str]:
    """Reformat the repo's Python sources at the target line length."""
    result = subprocess.run(
        [*ruff_cmd, "format", "--line-length", str(target), "."],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    combined = f"{result.stdout}\n{result.stderr}"
    match = re.search(r"(\d+) files? reformatted", combined)
    if result.returncode != 0:
        return 0, combined.strip()
    return (int(match.group(1)) if match else 0), ""


def converge(
    repo: Path,
    target: int,
    *,
    dry_run: bool = False,
    do_format: bool = False,
) -> Report:
    """Converge one repo onto the target line length."""
    report = Report(repo=repo, new_target=target)

    pyproject = repo / "pyproject.toml"
    if not pyproject.is_file():
        raise FileNotFoundError(f"no pyproject.toml in {repo}")

    text = pyproject.read_text(encoding="utf-8")
    report.old_target = read_toml_int(text, "tool.ruff", "line-length")

    updated, ruff_changed = set_toml_int(text, "tool.ruff", "line-length", target)
    updated, pylint_changed = set_toml_int(
        updated, "tool.pylint.format", "max-line-length", target
    )
    report.pyproject_changed = ruff_changed or pylint_changed
    if report.pyproject_changed and not dry_run:
        pyproject.write_text(updated, encoding="utf-8")

    for guidance in guidance_files(repo):
        original = guidance.read_text(encoding="utf-8")
        rewritten, changed = rewrite_guidance(original, target)
        if changed:
            report.guidance_changed.append(str(guidance.relative_to(repo)))
            if not dry_run:
                guidance.write_text(rewritten, encoding="utf-8")

    if do_format:
        ruff_cmd = resolve_ruff_command(repo)
        if ruff_cmd is None:
            report.format_error = "neither `uv` nor `ruff` is on PATH"
        else:
            count, error = run_ruff_format(repo, ruff_cmd, target)
            report.reformatted_files = count
            report.format_error = error

    return report


def check_repo(repo: Path, target: int) -> bool:
    """Return True when the repo already declares the target line length."""
    pyproject = repo / "pyproject.toml"
    if not pyproject.is_file():
        return False
    text = pyproject.read_text(encoding="utf-8")
    current = read_toml_int(text, "tool.ruff", "line-length")
    if current != target:
        return False
    for guidance in guidance_files(repo):
        original = guidance.read_text(encoding="utf-8")
        _, changed = rewrite_guidance(original, target)
        if changed:
            return False
    return True


def main(argv: list[str] | None = None) -> int:
    """Converge one or more repos onto the fleet line length."""
    parser = argparse.ArgumentParser(
        description="Set a repo's ruff/pylint line length to the fleet standard.",
    )
    parser.add_argument("repos", nargs="+", type=Path, help="Repository path(s).")
    parser.add_argument(
        "--target",
        type=int,
        default=DEFAULT_TARGET,
        help=f"Target line length (default: {DEFAULT_TARGET}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report what would change without writing.",
    )
    parser.add_argument(
        "--format",
        dest="do_format",
        action="store_true",
        help="Also run `ruff format` over the repo's Python sources.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if any repo is not converged. Writes nothing.",
    )
    args = parser.parse_args(argv)

    exit_code = 0
    for repo in args.repos:
        repo = repo.expanduser().resolve()
        if not repo.is_dir():
            print(f"{repo}: not a directory", file=sys.stderr)
            exit_code = 1
            continue

        if args.check:
            if not has_ruff_config(repo):
                print(f"{repo}: no [tool.ruff] config — skipped")
                continue
            converged = check_repo(repo, args.target)
            state = "converged" if converged else "NOT converged"
            print(f"{repo}: {state} (target {args.target})")
            if not converged:
                exit_code = 1
            continue

        try:
            report = converge(
                repo,
                args.target,
                dry_run=args.dry_run,
                do_format=args.do_format,
            )
        except FileNotFoundError as exc:
            print(f"{repo}: {exc}", file=sys.stderr)
            exit_code = 1
            continue

        prefix = "[dry-run] " if args.dry_run else ""
        before = report.old_target if report.old_target is not None else "unset"
        if before == "unset":
            print(f"{repo}: no [tool.ruff] line-length — skipped")
            continue
        print(f"{repo}: {prefix}line-length {before} -> {report.new_target}")
        if report.pyproject_changed:
            print("  pyproject.toml: updated")
        for guidance in report.guidance_changed:
            print(f"  {guidance}: updated")
        if args.do_format:
            if report.format_error:
                print(f"  ruff format: {report.format_error}", file=sys.stderr)
            else:
                print(f"  ruff format: {report.reformatted_files} files reformatted")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
