"""Issue classification for the ai-fix pipeline.

This module is the spec home for :class:`IssueKind` (2026-07-07 ai-fix design).
PR 4 introduces the enum so :class:`~crackerjack.ai_fix.issue_lifecycle.IssueLifecycle`
can carry a classification. The pure ``classify(...)`` function and its
``FixerRegistry`` collaborator land in PR 2/5 and extend this same module.
"""

from __future__ import annotations

from enum import Enum


class IssueKind(Enum):
    """How the fix loop should treat an issue.

    - ``FIXABLE_MECHANICAL`` — a deterministic fixer can resolve it (Tier-1).
    - ``NEEDS_LLM`` — no mechanical fixer applies; route to an LLM tier.
    - ``NON_FIXABLE`` — an aggregate metric or false positive; skip the loop.
    """

    FIXABLE_MECHANICAL = "fixable_mechanical"
    NEEDS_LLM = "needs_llm"
    NON_FIXABLE = "non_fixable"


__all__ = ["IssueKind"]
