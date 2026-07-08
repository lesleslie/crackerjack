"""Tests for IssueClassifier (PR 2 of 2026-07-07 ai-fix design).

The classifier is a pure function. Each branch of the decision order
gets a dedicated test class so a regression in one branch surfaces
as a single failing test, not a confused suite.

Decision order under test (do not reorder without updating PR 6):

1. Aggregate metric by ``stage`` prefix or ``message`` token → NON_FIXABLE
2. Built-in mechanical fixer for the issue's type → FIXABLE_MECHANICAL
3. Otherwise → NEEDS_LLM

The tests use a stub :class:`~crackerjack.ai_fix.fixer_registry.FixerRegistry`
because the real one is built incrementally by ``FixerCoordinator`` and
we want the classifier to be testable in isolation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from crackerjack.agents.base import Issue, IssueType, Priority
from crackerjack.ai_fix.fixer_registry import FixerRegistry
from crackerjack.ai_fix.issue_classifier import (
    AGGREGATE_MESSAGE_TOKENS,
    AGGREGATE_STAGE_PREFIXES,
    IssueKind,
    classify,
)

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


@dataclass
class _StubRegistry:
    """A tiny in-memory stand-in for :class:`FixerRegistry`.

    The classifier only needs ``has_mechanical_fixer(issue_type)`` to
    answer correctly. We use a dict-shaped object so each test can
    pre-load just the keys it cares about — keeps the assertions
    explicit and the tests orthogonal.
    """

    builtins: dict[str, Any] = field(default_factory=dict)

    def has_mechanical_fixer(self, issue_type: str) -> bool:
        return issue_type in self.builtins


def _issue(
    issue_type: Any = IssueType.TYPE_ERROR,
    message: str = "type error in foo",
    stage: str = "ty",
    file_path: str | None = "crackerjack/foo.py",
    line_number: int | None = 10,
) -> Issue:
    return Issue(
        type=issue_type,
        severity=Priority.LOW,
        message=message,
        file_path=file_path,
        line_number=line_number,
        stage=stage,
    )


# ---------------------------------------------------------------------------
# 1. Aggregate-metric branch
# ---------------------------------------------------------------------------


class TestAggregateMetricByStage:
    """``stage`` field carries an aggregate-metric source tag → NON_FIXABLE."""

    @pytest.mark.parametrize("prefix", AGGREGATE_STAGE_PREFIXES)
    def test_every_known_prefix_returns_non_fixable(self, prefix: str) -> None:
        issue = _issue(stage=f"{prefix}some-suffix")
        registry = _StubRegistry()  # empty; should be ignored on aggregate
        assert classify(issue, registry) == IssueKind.NON_FIXABLE.value

    def test_stage_prefix_match_is_case_insensitive(self) -> None:
        issue = _issue(stage="PYMETRICA-aggregate")
        registry = _StubRegistry()
        assert classify(issue, registry) == IssueKind.NON_FIXABLE.value

    def test_aggregate_overrides_built_in_fixer(self) -> None:
        """An aggregate metric must NEVER route to Tier-1 even if a fixer exists.

        The decision order is aggregate-first; the registry is only
        consulted for non-aggregate issues. This is the most important
        ordering invariant in the classifier.
        """
        issue = _issue(
            issue_type=IssueType.COMPLEXITY,
            stage="pymetrica-aggregate",
        )
        registry = _StubRegistry(
            builtins={"COMPLEXITY": object()}
        )  # would otherwise match
        assert classify(issue, registry) == IssueKind.NON_FIXABLE.value


class TestAggregateMetricByMessage:
    """The ``message`` field contains an aggregate-metric token → NON_FIXABLE."""

    @pytest.mark.parametrize("token", AGGREGATE_MESSAGE_TOKENS)
    def test_every_known_token_returns_non_fixable(self, token: str) -> None:
        issue = _issue(
            stage="ty",  # no aggregate stage; rely on message
            message=f"{token} exceeds the fail threshold of 30",
        )
        registry = _StubRegistry()
        assert classify(issue, registry) == IssueKind.NON_FIXABLE.value

    def test_message_token_is_case_insensitive(self) -> None:
        issue = _issue(stage="ty", message="HALSTEAD VOLUME 41.97 exceeds")
        registry = _StubRegistry()
        assert classify(issue, registry) == IssueKind.NON_FIXABLE.value

    def test_cyclomatic_complexity_is_NOT_aggregate(self) -> None:
        """Line-level CC violations stay FIXABLE; only project-wide aggregates are skipped.

        CC is a per-function metric with a per-function mechanical
        path. Treating it as aggregate would silently drop real fixes.
        """
        issue = _issue(
            stage="pymetrica",
            message="cyclomatic complexity 28 exceeds the fail threshold of 15",
        )
        registry = _StubRegistry()  # no fixer
        assert classify(issue, registry) == IssueKind.NEEDS_LLM.value


# ---------------------------------------------------------------------------
# 2. Built-in mechanical-fixer branch
# ---------------------------------------------------------------------------


class TestBuiltInFixer:
    """Registry has a fixer for the issue's type → FIXABLE_MECHANICAL."""

    def test_string_type_name_matches(self) -> None:
        issue = _issue(issue_type=IssueType.TYPE_ERROR)
        registry = _StubRegistry(builtins={"TYPE_ERROR": object()})
        assert classify(issue, registry) == IssueKind.FIXABLE_MECHANICAL.value

    def test_string_type_value_matches(self) -> None:
        """If the registry was keyed by enum value (``"type_error"``) instead of name, still match."""
        issue = _issue(issue_type=IssueType.TYPE_ERROR)
        registry = _StubRegistry(builtins={"type_error": object()})
        assert classify(issue, registry) == IssueKind.FIXABLE_MECHANICAL.value

    def test_no_fixable_fixer_means_needs_llm(self) -> None:
        issue = _issue(issue_type=IssueType.SEMANTIC_CONTEXT)
        registry = _StubRegistry(builtins={"TYPE_ERROR": object()})
        assert classify(issue, registry) == IssueKind.NEEDS_LLM.value


# ---------------------------------------------------------------------------
# 3. Default (needs LLM)
# ---------------------------------------------------------------------------


class TestNeedsLLM:
    """No aggregate, no mechanical fixer → NEEDS_LLM."""

    def test_default_is_needs_llm(self) -> None:
        issue = _issue(issue_type=IssueType.SEMANTIC_CONTEXT, stage="semantic")
        registry = _StubRegistry()
        assert classify(issue, registry) == IssueKind.NEEDS_LLM.value

    def test_empty_registry_is_needs_llm(self) -> None:
        # Use the *real* registry, not the stub. Even with an empty
        # real registry, classify must still answer.
        issue = _issue(issue_type=IssueType.TYPE_ERROR)
        assert classify(issue, FixerRegistry()) == IssueKind.NEEDS_LLM.value


# ---------------------------------------------------------------------------
# 4. Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Inputs the classifier must not blow up on."""

    def test_missing_stage_attribute(self) -> None:
        """An Issue-like object without a ``stage`` attribute should still classify."""

        # Build a minimal duck-typed object: only ``type``, ``message``.
        @dataclass
        class _Partial:
            type: Any
            message: str = ""

        partial = _Partial(type=IssueType.TYPE_ERROR, message="x")
        registry = _StubRegistry(builtins={"TYPE_ERROR": object()})
        # Must not raise. Stage is missing → no aggregate match.
        assert classify(partial, registry) == IssueKind.FIXABLE_MECHANICAL.value

    def test_missing_type_attribute(self) -> None:
        @dataclass
        class _Partial:
            message: str = "x"
            stage: str = "ty"

        partial = _Partial()
        registry = _StubRegistry(builtins={"TYPE_ERROR": object()})
        assert classify(partial, registry) == IssueKind.NEEDS_LLM.value

    def test_empty_message_and_stage(self) -> None:
        issue = _issue(stage="", message="")
        registry = _StubRegistry(builtins={"TYPE_ERROR": object()})
        assert classify(issue, registry) == IssueKind.FIXABLE_MECHANICAL.value

    def test_pure_function_no_side_effects(self) -> None:
        """Calling classify twice on the same inputs returns the same result.

        The function is documented as pure. This test guards against
        any future regression that introduces state.
        """
        issue = _issue(issue_type=IssueType.TYPE_ERROR, stage="ty")
        registry = _StubRegistry(builtins={"TYPE_ERROR": object()})
        first = classify(issue, registry)
        second = classify(issue, registry)
        assert first == second == IssueKind.FIXABLE_MECHANICAL.value
        # The registry must be unchanged.
        assert list(registry.builtins) == ["TYPE_ERROR"]


# ---------------------------------------------------------------------------
# 5. Enum contract
# ---------------------------------------------------------------------------


class TestEnumContract:
    """The IssueKind values used in the design are stable strings.

    Several downstream callers compare against the literal values
    (e.g. ``FixRouter`` in PR 6). Renaming them is a breaking change.
    """

    def test_issue_kind_values_match_design(self) -> None:
        assert IssueKind.FIXABLE_MECHANICAL.value == "fixable_mechanical"
        assert IssueKind.NEEDS_LLM.value == "needs_llm"
        assert IssueKind.NON_FIXABLE.value == "non_fixable"

    def test_classify_returns_string_value(self) -> None:
        """The return type is the enum *value* (a string), not the enum member."""
        issue = _issue(issue_type=IssueType.TYPE_ERROR)
        registry = _StubRegistry(builtins={"TYPE_ERROR": object()})
        result = classify(issue, registry)
        assert isinstance(result, str)
        assert result == "fixable_mechanical"
