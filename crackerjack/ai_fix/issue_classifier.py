
from __future__ import annotations

from enum import Enum

from crackerjack.agents.base import Issue
from crackerjack.ai_fix.fixer_registry import FixerRegistry


class IssueKind(Enum):

    FIXABLE_MECHANICAL = "fixable_mechanical"
    NEEDS_LLM = "needs_llm"
    NON_FIXABLE = "non_fixable"


AGGREGATE_STAGE_PREFIXES: tuple[str, ...] = (
    "pymetrica-aggregate",
    "pymetrica-",
    "halstead-",
    "aloc-",
    "maintainability-",
)


AGGREGATE_MESSAGE_TOKENS: tuple[str, ...] = (
    "halstead volume",
    "maintainability cost",
    "aloc percentage",
)


def _is_aggregate_metric(issue: Issue) -> bool:
    stage = (getattr(issue, "stage", "") or "").strip().lower()
    if any(stage.startswith(prefix) for prefix in AGGREGATE_STAGE_PREFIXES):
        return True
    message = (getattr(issue, "message", "") or "").strip().lower()
    return any(token in message for token in AGGREGATE_MESSAGE_TOKENS)


def _has_builtin_fixer(issue: Issue, registry: FixerRegistry) -> bool:
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
