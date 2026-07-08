"""Issue classification for the ai-fix pipeline.

PR 2 of the 2026-07-07 ai-fix design. Provides a single pure function
:class:`classify` that decides how the fix loop should treat a given
:class:`~crackerjack.agents.base.Issue`. The decision is the very first
gate in the routing order established by PR 6 (``FixRouter``).

Decision order (deliberate; do not reorder without updating PR 6):

1. **Aggregate metric** (NON_FIXABLE) — the issue is a project-wide
   metric violation (Halstead Volume, Maintainability Cost, ALOC,
   pymetrica-aggregate) that has no line-level fix. Two ways to
   detect: the ``stage`` field carries an aggregate-metric source
   tag (``"pymetrica-aggregate"`` etc.), or the ``message`` field
   contains an aggregate-metric token.
2. **Built-in mechanical fixer exists** (FIXABLE_MECHANICAL) — the
   ``FixerRegistry`` has a registered fixer for the issue's
   ``IssueType``. No LLM needed; the mechanical path is enough.
3. **Otherwise** (NEEDS_LLM) — no mechanical path; route to Tier-2
   or Tier-3 to find a Claude/Qwen session that can resolve it.

The function is **pure**: no I/O, no logging, no side effects. The
``FixerRegistry`` is passed in (dependency injection) so the same
function can be unit-tested with a stub registry.
"""

from __future__ import annotations

from enum import Enum

from crackerjack.agents.base import Issue
from crackerjack.ai_fix.fixer_registry import FixerRegistry


class IssueKind(Enum):
    """How the fix loop should treat an issue.

    - ``FIXABLE_MECHANICAL`` — a deterministic fixer can resolve it (Tier-1).
    - ``NEEDS_LLM`` — no mechanical fixer applies; route to an LLM tier.
    - ``NON_FIXABLE`` — an aggregate metric or false positive; skip the loop.
    """

    FIXABLE_MECHANICAL = "fixable_mechanical"
    NEEDS_LLM = "needs_llm"
    NON_FIXABLE = "non_fixable"


# Stage prefixes that mark an issue as a non-fixable aggregate metric.
# Matches pymetrica's PR-1 output (``code="pymetrica-aggregate"`` and
# the future ``"pymetrica-..."`` family) plus headroom for
# ``halstead-*`` / ``aloc-*`` from any future aggregate-metric
# adapter.  Lower-cased before comparison.
AGGREGATE_STAGE_PREFIXES: tuple[str, ...] = (
    "pymetrica-aggregate",
    "pymetrica-",
    "halstead-",
    "aloc-",
    "maintainability-",
)

# Message tokens that mark an issue as a non-fixable aggregate metric.
# ``"cyclomatic complexity"`` is intentionally NOT in this list — that
# is a line-level CC violation that the existing mechanical fixers
# handle (see ``crackerjack.adapters.complexity.pymetrica._CC_KEYWORDS``).
# Kept here as a frozen tuple so the classifier can be re-evaluated
# without re-importing.
AGGREGATE_MESSAGE_TOKENS: tuple[str, ...] = (
    "halstead volume",
    "maintainability cost",
    "aloc percentage",
)


def _is_aggregate_metric(issue: Issue) -> bool:
    """Return True if ``issue`` represents an aggregate (non-line-level) metric."""
    stage = (getattr(issue, "stage", "") or "").strip().lower()
    if any(stage.startswith(prefix) for prefix in AGGREGATE_STAGE_PREFIXES):
        return True
    message = (getattr(issue, "message", "") or "").strip().lower()
    return any(token in message for token in AGGREGATE_MESSAGE_TOKENS)


def _has_builtin_fixer(issue: Issue, registry: FixerRegistry) -> bool:
    """Return True if the registry has a built-in fixer for the issue's type.

    The registry is keyed by the ``IssueType`` *name* (e.g. ``"TYPE_ERROR"``,
    ``"REFURB"``) — matching the convention used by
    :meth:`FixerCoordinator._try_register_fixer` and the dict-like shim
    on :class:`FixerRegistry`. We try both the ``.name`` and ``.value``
    forms so a caller passing either an enum member or a stringified
    type gets the same answer.
    """
    issue_type = getattr(issue, "type", None)
    if issue_type is None:
        return False
    for candidate in (
        str(issue_type),
        getattr(issue_type, "name", None),
        getattr(issue_type, "value", None),
    ):
        if candidate and registry.has_mechanical_fixer(candidate):
            return True
    return False


def classify(issue: Issue, fixer_registry: FixerRegistry) -> str:
    """Classify an issue as ``fixable_mechanical`` / ``needs_llm`` / ``non_fixable``.

    Returns the ``IssueKind`` enum *value* (a string) rather than the
    enum member, so callers that don't want to import the enum can
    compare to a string literal. Tests that need the enum member
    can do ``IssueKind(classify(issue, registry))``.
    """
    if _is_aggregate_metric(issue):
        return IssueKind.NON_FIXABLE.value
    if _has_builtin_fixer(issue, fixer_registry):
        return IssueKind.FIXABLE_MECHANICAL.value
    return IssueKind.NEEDS_LLM.value


__all__ = [
    "AGGREGATE_MESSAGE_TOKENS",
    "AGGREGATE_STAGE_PREFIXES",
    "IssueKind",
    "classify",
]
