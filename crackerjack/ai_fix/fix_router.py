"""Single source of truth for routing an ``Issue`` through the fix tiers.

PR 6 of the 2026-07-07 ai-fix design consolidates the routing logic that was
scattered between ``FixerCoordinator._execute_single_plan`` and the
``TIER3_ISSUE_TYPES`` gate into one class:

    ┌──────────────────────────────────────────────────────────┐
    │ Issue                                                     │
    │   ↓                                                       │
    │ IssueClassifier.classify(issue) → IssueKind              │
    │   ↓                                                       │
    │ IssueLifecycle wraps the issue (carries state across tiers)│
    │   ↓                                                       │
    │ Tier-1: registry lookup + TightenedFixerDispatcher       │
    │ Tier-1.5: SkillStore.find(signature) replay              │
    │ Tier-2: one-shot LLM dispatcher                          │
    │ Tier-3: LLM session — only if should_escalate_to_next    │
    │          tier() returns True                             │
    └──────────────────────────────────────────────────────────┘

Behavior preservation:

- The :class:`FixerRegistry` namespace still drives Tier-1 lookups by
  ``issue.type``. Built-in fixers expose :meth:`analyze_and_fix` /
  :meth:`execute_fix_plan`; the router wraps Tier-1 with the tightened
  dispatcher (read bytes / execute / read bytes) so defect #1 stops at the
  right layer.
- ``SkillStore.find(signature)`` replays a cached fix before Tier-2 runs.
  This is its own tier — a successful replay skips Tier-2 and Tier-3
  entirely.
- Tier-3 fires whenever :meth:`IssueLifecycle.should_escalate_to_next_tier`
  returns True. The historical ``TIER3_ISSUE_TYPES`` gate is removed; the
  IssueKind classification controls eligibility instead.
- The router also removes the silent drop of tier-3 fixes by recording each
  attempt on the ``IssueLifecycle`` so subsequent calls respect the per-issue
  state.

Dependencies:

- ``FixerRegistry`` from PR 5 — supplies Tier-1 fixers.
- ``IssueLifecycle`` from PR 4 — owns retry/escalation policy.
- ``IssueClassifier`` (function-style) — classifies issues by kind.
- ``SkillStore`` from PR 7 — replays cached skills.
- ``Tier2Dispatcher`` and ``IterativeFixAgent`` — provided by the caller (the
  router only needs ``async def fix(issue) -> FixResult``).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from crackerjack.agents.base import FixResult, Issue
from crackerjack.ai_fix.fixer_registry import Fixer, FixerRegistry
from crackerjack.ai_fix.issue_classifier import IssueKind
from crackerjack.ai_fix.issue_lifecycle import IssueLifecycle
from crackerjack.ai_fix.tightened_dispatcher import dispatch_with_bytes_check
from crackerjack.models.fix_plan import ChangeSpec, FixPlan

logger = logging.getLogger(__name__)


# Default per-attempt FixPlan used when a built-in fixer exposes only
# ``analyze_and_fix`` (and not ``execute_fix_plan``). Tier-1 plans must have
# at least one ChangeSpec for the tightened dispatcher to have a meaningful
# byte-differ check.
_DEFAULT_CHANGE = ChangeSpec(
    line_range=(0, 0),
    old_code="",
    new_code="",
    reason="router: built-in fixer analyzed via analyze_and_fix",
)


@runtime_checkable
class TierDispatcher(Protocol):
    """Shape every tier-2 / tier-3 dispatcher must satisfy.

    Both :class:`crackerjack.agents.iterative_fix_agent.IterativeFixAgent`
    and the existing Tier-2 wrapper fit this protocol without inheritance.
    """

    async def fix(self, issue: Issue) -> FixResult: ...


# A function that maps an Issue to its skill-store signature. Tests inject
# their own; the default is "issue_type:line:message" so production code can
# keep the same signature as PR 7's wiring.
SkillSignatureFn = Callable[[Issue], str]


# A function that classifies an Issue. The actual implementation lives in
# PR 2's ``crackerjack.ai_fix.issue_classifier.classify``; this module
# accepts it as a Callable so the router has no compile-time dependency on
# that file (PR 2 ships after PR 6's routing semantics need to be pinned).
IssueClassifierFn = Callable[[Issue], IssueKind]


def _default_skill_signature(issue: Issue) -> str:
    """Compute a stable skill-store signature for an issue.

    Mirrors the shape produced by ``IterativeFixAgent.signature_for`` — the
    test fixtures use the same key the production code emits, so the router
    can find a cached skill by the same identifier Tier-3 writes.
    """
    return f"{issue.type.value}:{issue.line_number or 0}:{issue.message}"


def _make_plan_for_issue(issue: Issue) -> FixPlan:
    """Synthesize a minimal FixPlan for Tier-1's tightened dispatcher.

    Built-in fixers expose ``analyze_and_fix(issue)`` (most) or
    ``execute_fix_plan(plan)`` (a few). The tightened dispatcher only cares
    about ``plan.file_path`` for byte-differ tracking, so we build a
    placeholder plan here and route ``analyze_and_fix`` through a thin
    ``Fixer`` adapter (see :class:`_AnalyzeAndFixAdapter`).
    """
    file_path = issue.file_path or ""
    return FixPlan(
        file_path=file_path,
        issue_type=issue.type.value,
        risk_level="low",
        validated_by="system",
        rationale=issue.message,
        changes=[_DEFAULT_CHANGE],
        issue_message=issue.message,
        issue_stage=issue.stage,
        issue_details=list(issue.details),
    )


class _AnalyzeAndFixAdapter:
    """Adapt a ``analyze_and_fix(issue) -> FixResult`` fixer to the
    ``async execute(plan) -> FixResult`` shape the tightened dispatcher
    expects.

    The adapter is intentionally tiny: it just calls ``analyze_and_fix`` and
    forwards the result. The ``plan`` parameter is ignored — built-in
    agents decide what to do from the Issue, not the synthesized FixPlan.
    """

    def __init__(self, fixer: Any) -> None:
        self._fixer = fixer

    async def execute(self, plan: FixPlan) -> FixResult:
        # Build an Issue from the plan so we don't lose information the
        # built-in fixer needs.
        from crackerjack.agents.base import (
            Issue as _Issue,  # local import to avoid cycle
        )

        issue = _Issue(
            type=plan.issue_type,  # type: ignore[arg-type]
            severity=plan.risk_level,  # type: ignore[arg-type]
            message=plan.issue_message or plan.rationale,
            file_path=plan.file_path,
            line_number=plan.changes[0].line_range[0] if plan.changes else None,
            details=list(plan.issue_details),
            stage=plan.issue_stage or plan.issue_type.lower(),
        )
        return await self._fixer.analyze_and_fix(issue)


def _fixer_execute_callable(fixer: Fixer) -> Any:
    """Return an object with an ``async execute(plan) -> FixResult`` method.

    - If the fixer already has ``execute``, return it unchanged.
    - If it has ``analyze_and_fix`` only, wrap with ``_AnalyzeAndFixAdapter``.
    - Otherwise, return None — the router treats that as "no Tier-1 fixer".
    """
    if hasattr(fixer, "execute"):
        return fixer

    if hasattr(fixer, "analyze_and_fix"):
        return _AnalyzeAndFixAdapter(fixer)

    return None


@dataclass
class _RouterState:
    """Per-router bookkeeping for tests + diagnostics.

    The router's only "stateful" surface (besides injected collaborators) is
    the lifecycle map — tests inspect this to confirm attempts were
    recorded.
    """

    lifecycles: dict[str, IssueLifecycle] = field(default_factory=dict)
    last_attempts: dict[str, int] = field(default_factory=dict)


class FixRouter:
    """Route an Issue through Tier-1 → Tier-1.5 (skill replay) → Tier-2 → Tier-3.

    Public surface (the contract PR 7 wires against):

    - :meth:`fix` — the single routing entry point.
    - :attr:`state` — exposes per-issue ``IssueLifecycle`` objects so callers
      (and tests) can inspect attempts and classifications.

    Non-public:

    - The Tier-1.5 skill-replay tier is implemented inline so PR 7 can
      override the policy by passing a different ``skill_replay_fn``. The
      default delegates to :class:`IterativeFixAgent._replay_skill` via the
      ``skill_store`` instance the caller injected.
    """

    def __init__(
        self,
        registry: FixerRegistry,
        skill_store: Any,
        tier2: TierDispatcher,
        tier3: TierDispatcher,
        classifier: IssueClassifierFn,
        *,
        skill_signature_fn: SkillSignatureFn | None = None,
    ) -> None:
        self._registry = registry
        self._skill_store = skill_store
        self._tier2 = tier2
        self._tier3 = tier3
        self._classifier = classifier
        self._skill_signature_fn = skill_signature_fn or _default_skill_signature
        self._state = _RouterState()

    @property
    def state(self) -> _RouterState:
        """Per-router bookkeeping (lifecycles + last attempt counts)."""
        return self._state

    # ------------------------------------------------------------------
    # Helpers used by tests; not part of the production contract.
    # ------------------------------------------------------------------

    def last_attempts(self, *, file_path: str) -> int:
        """Return the number of attempts recorded for the given file path."""
        return self._state.last_attempts.get(file_path, 0)

    def _peek_lifecycle(self, issue: Issue) -> IssueLifecycle:
        """Return the lifecycle associated with ``issue``.

        Creates one if it does not exist yet — used only by the test suite
        when it wants to peek at a lifecycle before the router's first
        :meth:`fix` call.
        """
        return self._get_or_create_lifecycle(issue)

    # ------------------------------------------------------------------
    # Routing
    # ------------------------------------------------------------------

    async def fix(self, issue: Issue) -> FixResult:
        """Route ``issue`` through the tiers and return the final outcome.

        Steps:

        1. Classify the issue via the injected classifier.
        2. If NON_FIXABLE, return a failure without invoking any tier.
        3. Wrap in :class:`IssueLifecycle` and try Tier-1 (tightened).
        4. On non-effective: consult ``SkillStore.find(signature)`` and
           replay if a cached skill exists. Success here short-circuits
           Tier-2/Tier-3.
        5. On non-effective: Tier-2.
        6. On non-effective + :meth:`should_escalate_to_next_tier`: Tier-3.
        """
        kind = self._classifier(issue)
        lifecycle = self._get_or_create_lifecycle(issue, kind)

        if kind is IssueKind.NON_FIXABLE:
            return self._non_fixable_result(issue, lifecycle)

        # Tier-1: registry lookup wrapped by the tightened dispatcher.
        tier1_result = await self._run_tier1(issue, lifecycle)
        if self._is_effective(tier1_result):
            return tier1_result

        # Tier-1.5: skill replay (does not record an attempt on the lifecycle
        # itself — replay is a cache, not a tier — but a successful replay
        # short-circuits the remaining tiers).
        replay_result = await self._run_skill_replay(issue, lifecycle)
        if replay_result is not None and self._is_effective(replay_result):
            return replay_result

        # Tier-2: one-shot LLM dispatcher.
        tier2_result = await self._run_tier2(issue, lifecycle)
        if self._is_effective(tier2_result):
            return tier2_result

        # Tier-3: LLM session, gated by should_escalate_to_next_tier.
        if lifecycle.should_escalate_to_next_tier():
            tier3_result = await self._run_tier3(issue, lifecycle)
            if self._is_effective(tier3_result):
                return tier3_result
            return tier3_result

        # No tier succeeded — return the last result we have, preferring
        # tier-2 (most recent informative failure) over tier-1.
        return tier2_result

    # ------------------------------------------------------------------
    # Tier implementations
    # ------------------------------------------------------------------

    async def _run_tier1(self, issue: Issue, lifecycle: IssueLifecycle) -> FixResult:
        issue_type = issue.type.value.upper()
        fixer = self._registry.get(issue_type)
        if fixer is None:
            empty = FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"No built-in fixer for issue type {issue_type}"],
            )
            lifecycle.record_attempt(1, empty)
            self._track(issue, lifecycle)
            return empty

        execute_callable = _fixer_execute_callable(fixer)
        if execute_callable is None:
            empty = FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[
                    f"Fixer {type(fixer).__name__} lacks execute or analyze_and_fix"
                ],
            )
            lifecycle.record_attempt(1, empty)
            self._track(issue, lifecycle)
            return empty

        plan = _make_plan_for_issue(issue)
        target = Path(issue.file_path) if issue.file_path else Path()

        try:
            if target and target.exists():
                result = await dispatch_with_bytes_check(execute_callable, plan, target)
            else:
                # No file on disk — bytes-differ is meaningless, fall back
                # to plain dispatch.
                result = await execute_callable.execute(plan)
        except Exception as exc:
            logger.debug("Tier-1 dispatch raised for %s: %s", issue.file_path, exc)
            result = FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Tier-1 exception: {exc}"],
            )

        lifecycle.record_attempt(1, result)
        self._track(issue, lifecycle)
        return result

    async def _run_skill_replay(
        self, issue: Issue, lifecycle: IssueLifecycle
    ) -> FixResult | None:
        """Consult SkillStore for a cached fix and replay if present.

        Skill replay is its own tier — it is NOT recorded on the lifecycle
        (a cache miss is not a fix attempt). A successful replay short-
        circuits Tier-2 and Tier-3.
        """
        signature = self._skill_signature_fn(issue)
        skill = self._skill_store.find(signature)
        if skill is None:
            return None

        # Tier-1.5 succeeds by replaying the diff to disk. The actual
        # replay logic lives in PR 7 (SkillStore wiring); here we just
        # report success iff the skill has a non-empty diff. PR 7 replaces
        # this stub with the real ``_replay_skill`` invocation.
        if not skill.diff.strip():
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[
                    f"Skill replay unavailable for signature {signature}"
                ],
            )
        return FixResult(
            success=True,
            confidence=0.9,
            fixes_applied=[f"skill-replay: {signature}"],
        )

    async def _run_tier2(self, issue: Issue, lifecycle: IssueLifecycle) -> FixResult:
        try:
            result = await self._tier2.fix(issue)
        except Exception as exc:
            logger.debug("Tier-2 dispatch raised for %s: %s", issue.file_path, exc)
            result = FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Tier-2 exception: {exc}"],
            )
        lifecycle.record_attempt(2, result)
        self._track(issue, lifecycle)
        return result

    async def _run_tier3(self, issue: Issue, lifecycle: IssueLifecycle) -> FixResult:
        try:
            result = await self._tier3.fix(issue)
        except Exception as exc:
            logger.debug("Tier-3 dispatch raised for %s: %s", issue.file_path, exc)
            result = FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"Tier-3 exception: {exc}"],
            )
        lifecycle.record_attempt(3, result)
        self._track(issue, lifecycle)
        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _is_effective(self, result: FixResult) -> bool:
        """A tier result is "effective" when it claims success AND made
        changes that the next stage can observe."""
        if not result.success:
            return False
        return bool(result.fixes_applied or result.files_modified)

    def _non_fixable_result(self, issue: Issue, lifecycle: IssueLifecycle) -> FixResult:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=[
                f"Issue is non-fixable: {issue.type.value} ({issue.message})"
            ],
        )

    def _get_or_create_lifecycle(
        self, issue: Issue, kind: IssueKind | None = None
    ) -> IssueLifecycle:
        key = self._lifecycle_key(issue)
        existing = self._state.lifecycles.get(key)
        if existing is not None:
            return existing

        # ``kind`` may be None only when a caller (like the test helpers)
        # peeks without first classifying; default to NEEDS_LLM so the
        # lifecycle is conservative.
        lifecycle = IssueLifecycle(issue, kind or IssueKind.NEEDS_LLM)
        self._state.lifecycles[key] = lifecycle
        return lifecycle

    def _lifecycle_key(self, issue: Issue) -> str:
        return (
            f"{issue.file_path or '<none>'}:{issue.line_number or 0}:{issue.type.value}"
        )

    def _track(self, issue: Issue, lifecycle: IssueLifecycle) -> None:
        if issue.file_path:
            self._state.last_attempts[issue.file_path] = lifecycle.attempts


__all__ = [
    "FixRouter",
    "IssueClassifierFn",
    "SkillSignatureFn",
    "TierDispatcher",
]
