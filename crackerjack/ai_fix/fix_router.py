from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from crackerjack.agents.base import FixResult, Issue
from crackerjack.ai_fix.fixer_registry import Fixer, FixerRegistry
from crackerjack.ai_fix.issue_classifier import IssueKind
from crackerjack.ai_fix.issue_lifecycle import IssueLifecycle, signature_for_issue
from crackerjack.ai_fix.tightened_dispatcher import dispatch_with_bytes_check
from crackerjack.models.fix_plan import ChangeSpec, FixPlan

logger = logging.getLogger(__name__)


_DEFAULT_CHANGE = ChangeSpec(
    line_range=(0, 0),
    old_code="",
    new_code="",
    reason="router: built-in fixer analyzed via analyze_and_fix",
)


@runtime_checkable
class TierDispatcher(Protocol):
    async def fix(self, issue: Issue) -> FixResult: ...


SkillSignatureFn = Callable[[Issue], str]


IssueClassifierFn = Callable[[Issue], IssueKind]


SkillReplayFn = Callable[[Issue, Any], Any]


def _default_skill_signature(issue: Issue) -> str:
    return signature_for_issue(issue)


def _make_plan_for_issue(issue: Issue) -> FixPlan:
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
    def __init__(self, fixer: Any) -> None:
        self._fixer = fixer

    async def execute(self, plan: FixPlan) -> FixResult:

        from crackerjack.agents.base import (
            Issue as _Issue,
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
    if hasattr(fixer, "execute"):
        return fixer

    if hasattr(fixer, "analyze_and_fix"):
        return _AnalyzeAndFixAdapter(fixer)

    return None


@dataclass
class _RouterState:
    lifecycles: dict[str, IssueLifecycle] = field(default_factory=dict)
    last_attempts: dict[str, int] = field(default_factory=dict)


class FixRouter:
    def __init__(
        self,
        registry: FixerRegistry,
        skill_store: Any,
        tier2: TierDispatcher,
        tier3: TierDispatcher,
        classifier: IssueClassifierFn,
        *,
        skill_signature_fn: SkillSignatureFn | None = None,
        skill_replay_fn: SkillReplayFn | None = None,
    ) -> None:
        self._registry = registry
        self._skill_store = skill_store
        self._tier2 = tier2
        self._tier3 = tier3
        self._classifier = classifier
        self._skill_signature_fn = skill_signature_fn or _default_skill_signature
        self._skill_replay_fn = skill_replay_fn or _stub_skill_replay
        self._state = _RouterState()

    @property
    def state(self) -> _RouterState:
        return self._state

    def last_attempts(self, *, file_path: str) -> int:
        return self._state.last_attempts.get(file_path, 0)

    def _peek_lifecycle(self, issue: Issue) -> IssueLifecycle:
        return self._get_or_create_lifecycle(issue)

    async def fix(self, issue: Issue) -> FixResult:
        kind = self._classifier(issue)
        lifecycle = self._get_or_create_lifecycle(issue, kind)

        if kind is IssueKind.NON_FIXABLE:
            return self._non_fixable_result(issue, lifecycle)

        tier1_result = await self._run_tier1(issue, lifecycle)
        if self._is_effective(tier1_result):
            return tier1_result

        replay_result = await self._run_skill_replay(issue, lifecycle)
        if replay_result is not None and self._is_effective(replay_result):
            return replay_result

        tier2_result = await self._run_tier2(issue, lifecycle)
        if self._is_effective(tier2_result):
            return tier2_result

        if lifecycle.should_escalate_to_next_tier():
            tier3_result = await self._run_tier3(issue, lifecycle)
            if self._is_effective(tier3_result):
                return tier3_result
            return tier3_result

        return tier2_result

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
        signature = self._skill_signature_fn(issue)
        skill = self._skill_store.find(signature)
        if skill is None:
            return None

        try:
            result = await self._skill_replay_fn(issue, skill)
        except Exception as exc:
            logger.debug("Skill replay raised for signature %s: %s", signature, exc)
            return FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"skill replay exception: {exc}"],
            )
        return result

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

        if result.success:
            generated = getattr(self._tier3, "last_generated_skill", None)
            if generated is not None:
                signature = self._skill_signature_fn(issue)
                self._skill_store.record(signature, generated)

        lifecycle.record_attempt(3, result)
        self._track(issue, lifecycle)
        return result

    def _is_effective(self, result: FixResult) -> bool:
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


async def _stub_skill_replay(issue: Issue, skill: Any) -> FixResult:
    return FixResult(
        success=False,
        confidence=0.0,
        remaining_issues=[
            "skill_replay_disabled: no replay fn injected; falling through to Tier-2"
        ],
    )


__all__ = [
    "FixRouter",
    "IssueClassifierFn",
    "SkillReplayFn",
    "SkillSignatureFn",
    "TierDispatcher",
    "build_fix_router",
]


def build_fix_router(
    fixer_coordinator: object,
) -> FixRouter:
    from crackerjack.agents.iterative_fix_agent import InMemorySkillStore
    from crackerjack.ai_fix.adapters import _Tier2Adapter, _Tier3Adapter
    from crackerjack.ai_fix.issue_classifier import IssueKind, classify

    registry = fixer_coordinator.fixers  # type: ignore[attr-defined]

    def _production_classifier(issue: object) -> IssueKind:
        return IssueKind(classify(issue, registry))  # type: ignore[arg-type]

    if fixer_coordinator.iterative_agent is not None:  # type: ignore[attr-defined]
        skill_store = fixer_coordinator.iterative_agent.skill_store  # type: ignore[attr-defined]

        iterative_agent = fixer_coordinator.iterative_agent  # type: ignore[attr-defined]

        async def _real_skill_replay(issue: object, skill: object) -> object:
            from pathlib import Path as _Path

            from crackerjack.agents.base import FixResult as _FixResult

            target = (
                _Path(issue.file_path)  # type: ignore[attr-defined]
                if getattr(issue, "file_path", None)
                else None
            )
            if target is None:
                return _FixResult(
                    success=False,
                    confidence=0.0,
                    remaining_issues=["skill replay: no file_path"],
                )

            ok = iterative_agent._replay_skill(target, skill)  # type: ignore[attr-defined]
            if ok:
                return _FixResult(
                    success=True,
                    confidence=0.9,
                    fixes_applied=[f"skill-replay: {skill}"],
                    files_modified=[str(target)],
                )
            return _FixResult(
                success=False,
                confidence=0.0,
                remaining_issues=[f"skill replay failed for signature (file={target})"],
            )

        skill_replay_fn = _real_skill_replay
    else:
        skill_store = InMemorySkillStore()
        skill_replay_fn = None

    tier3_adapter = _Tier3Adapter(fixer_coordinator.iterative_agent)  # type: ignore[attr-defined]
    tier2_adapter = _Tier2Adapter(fixer_coordinator)  # type: ignore[arg-defined]

    return FixRouter(
        registry=registry,
        skill_store=skill_store,
        tier2=tier2_adapter,
        tier3=tier3_adapter,
        classifier=_production_classifier,
        skill_replay_fn=skill_replay_fn,
    )
