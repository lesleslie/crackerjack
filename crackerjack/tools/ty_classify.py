"""Pre-fix classification of ``ty`` diagnostics into auto-fix tiers.

Run this BEFORE dispatching the ai-fix pipeline to get a fast
rule-based read on:

* how many of each tier there are
* which files are the worst offenders (for tier-3 prioritization)
* what percentage of errors are realistically auto-fixable today

The classifier is intentionally pure-Python — no LLM, no subprocess,
no I/O beyond what the caller hands us. That keeps it cheap enough
to run on every CI cycle.

Tier mapping (single source of truth):

* ``TIER_1_MECHANICAL`` — ty_cleanup, ty_imports, ty_narrow (planned)
* ``TIER_2_ONE_SHOT_LLM`` — TypeErrorSpecialistAgent
* ``TIER_3_ITERATIVE`` — IterativeFixAgent (CLI session)
* ``TIER_4_HUMAN`` — surface in dashboard for human review

Out of scope (deliberately):

* Running ty itself — caller hands us the parsed output
* Actually fixing anything — this only classifies
* Distinguishing "resolvable" vs "unresolvable" within a tier —
  that's a per-fix decision, not a per-code one
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# Tier constants (exported so fixers and dashboards can reference them)
# ---------------------------------------------------------------------------

TIER_1_MECHANICAL = "tier-1-mechanical"
TIER_2_ONE_SHOT_LLM = "tier-2-one-shot-llm"
TIER_3_ITERATIVE = "tier-3-iterative"
TIER_4_HUMAN = "tier-4-human"

# Conservative default for codes we haven't classified yet.
# Tier 3 is the right fallback because the iterative agent has the
# best chance of figuring out unknown codes.
UNKNOWN_TIER = TIER_3_ITERATIVE


# ty error code → tier mapping. Single source of truth — when a new
# mechanical fixer lands, add its codes here so the report stays accurate.
_CODE_TO_TIER: dict[str, str] = {
    # Tier 1: handled by ty_cleanup.py
    "unused-type-ignore-comment": TIER_1_MECHANICAL,
    "redundant-cast": TIER_1_MECHANICAL,
    # Tier 1: handled by ty_imports.py
    "unresolved-reference": TIER_1_MECHANICAL,
    "unresolved-import": TIER_1_MECHANICAL,
    # Tier 1: handled by ty_narrow.py (None-coercion default substitution
    # for `in` / `not in` / dict subscripts). Note: ty_narrow's
    # candidate finder rejects non-bare-identifier LHS and non-
    # `dict | None` unions; the rest still fall through to tier 3.
    "unsupported-operator": TIER_1_MECHANICAL,
    "not-subscriptable": TIER_1_MECHANICAL,
    # Tier 3: requires reasoning / narrowing / signature design
    "unsupported-right-operand": TIER_3_ITERATIVE,
    "unsupported-left-operand": TIER_3_ITERATIVE,
    "unsupported-bool-operand": TIER_3_ITERATIVE,
    "unresolved-attribute": TIER_3_ITERATIVE,
    "invalid-argument-type": TIER_3_ITERATIVE,
    "invalid-return-type": TIER_3_ITERATIVE,
    "invalid-assignment": TIER_3_ITERATIVE,
    "invalid-key": TIER_3_ITERATIVE,
    "not-iterable": TIER_3_ITERATIVE,
    "not-callable": TIER_3_ITERATIVE,
    "missing-argument": TIER_3_ITERATIVE,
    "too-many-arguments": TIER_3_ITERATIVE,
    "invalid-await": TIER_3_ITERATIVE,
    "invalid-context-manager": TIER_3_ITERATIVE,
    "invalid-overload": TIER_3_ITERATIVE,
    # Tier 4: design decisions, not auto-fixable
    "invalid-method-override": TIER_4_HUMAN,
    "invalid-base": TIER_4_HUMAN,
    "invalid-type-form": TIER_4_HUMAN,
    "abstract-method-instantiation": TIER_4_HUMAN,
    "invalid-decorator": TIER_4_HUMAN,
    "invalid-metaclass": TIER_4_HUMAN,
}


def classify_code(code: str) -> str:
    """Return the tier name for a single ty error code."""
    return _CODE_TO_TIER.get(code, UNKNOWN_TIER)


# ---------------------------------------------------------------------------
# Diagnostic-line parsing
# ---------------------------------------------------------------------------

# Mirrors the ty concise format we already use elsewhere:
#   path/to/file.py:LINE:COL: error[CODE] message
_LINE_RE = re.compile(
    r"^(?P<file>[^:]+):(?P<line>\d+):(?P<col>\d+):\s+"
    r"(?P<level>error|warning)\[(?P<code>[a-z0-9-]+)\]\s+"
    r"(?P<message>.+)$"
)


@dataclass(frozen=True)
class Diagnostic:
    file: Path
    line: int
    col: int
    code: str
    message: str


def _parse_line(line: str) -> Diagnostic | None:
    match = _LINE_RE.match(line.strip())
    if not match:
        return None
    return Diagnostic(
        file=Path(match["file"]),
        line=int(match["line"]),
        col=int(match["col"]),
        code=match["code"],
        message=match["message"],
    )


# ---------------------------------------------------------------------------
# Report shape
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FileCount:
    """Per-file error totals, for the dashboard's "top offenders" view."""

    path: Path
    count: int


@dataclass
class ClassificationReport:
    """Bucketed counts plus per-code and per-file breakdowns."""

    tier_1: int = 0
    tier_2: int = 0
    tier_3: int = 0
    tier_4: int = 0
    by_code: dict[str, int] = field(default_factory=dict)
    by_file: dict[Path, int] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return self.tier_1 + self.tier_2 + self.tier_3 + self.tier_4

    def top_files(self, limit: int = 10) -> list[FileCount]:
        items = sorted(self.by_file.items(), key=lambda kv: kv[1], reverse=True)
        return [FileCount(path=p, count=c) for p, c in items[:limit]]

    def render(self) -> str:
        """Human-readable summary suitable for CLI output."""
        total = self.total
        if total == 0:
            return "No ty errors found.\n"

        def pct(n: int) -> str:
            return f"{n} ({100 * n / total:.0f}%)"

        lines: list[str] = []
        lines.append(f"Total: {total} ty errors")
        lines.append("")
        lines.append("Tier breakdown:")
        lines.append(f"  Tier 1 (mechanical):      {pct(self.tier_1)}")
        lines.append(f"  Tier 2 (one-shot LLM):    {pct(self.tier_2)}")
        lines.append(f"  Tier 3 (iterative CLI):   {pct(self.tier_3)}")
        lines.append(f"  Tier 4 (human review):    {pct(self.tier_4)}")
        lines.append("")
        # Coverage estimate: tiers 1+2 are essentially auto-fixable today
        # (1 with the fixers shipped, 2 with the LLM agent that exists).
        auto_fixable = self.tier_1 + self.tier_2
        lines.append(f"Auto-fixable today (tiers 1+2): {pct(auto_fixable)}")
        lines.append(
            f"With tier-3 iterative agent:    {pct(auto_fixable + self.tier_3)}"
        )

        top = self.top_files(limit=5)
        if top:
            lines.append("")
            lines.append("Top offenders:")
            for fc in top:
                lines.append(f"  {fc.path}: {fc.count}")

        return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Public driver
# ---------------------------------------------------------------------------


def classify_diagnostics(lines: Iterable[str]) -> ClassificationReport:
    """Read ty output lines and return a tier-classified report."""
    report = ClassificationReport()
    for raw in lines:
        diag = _parse_line(raw)
        if diag is None:
            continue
        tier = classify_code(diag.code)
        if tier == TIER_1_MECHANICAL:
            report.tier_1 += 1
        elif tier == TIER_2_ONE_SHOT_LLM:
            report.tier_2 += 1
        elif tier == TIER_3_ITERATIVE:
            report.tier_3 += 1
        else:
            report.tier_4 += 1
        report.by_code[diag.code] = report.by_code.get(diag.code, 0) + 1
        report.by_file[diag.file] = report.by_file.get(diag.file, 0) + 1
    return report
