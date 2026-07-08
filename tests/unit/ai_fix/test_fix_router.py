"""Tests for the :class:`FixRouter` (PR 6 of the 2026-07-07 ai-fix design).

Pins:

- NON_FIXABLE returns a failure without invoking any tier.
- Tier-1 routes through ``FixerRegistry`` wrapped by
  :func:`crackerjack.ai_fix.tightened_dispatcher.dispatch_with_bytes_check`.
- Tier-1.5 replays a cached skill via ``SkillStore.find`` when present.
- Tier-2 (one-shot LLM) fires after Tier-1 fails.
- Tier-3 (LLM session) fires only when
  :meth:`IssueLifecycle.should_escalate_to_next_tier` returns True.
- Each tier's outcome is recorded on the ``IssueLifecycle`` so subsequent
  routing decisions respect the per-issue state.

Tests use stub collaborators — the goal is to verify the *routing decisions*
at PR 6's seam, not to retest the tiers (which have their own tests).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import pytest

from crackerjack.agents.base import FixResult, Issue, IssueType, Priority
from crackerjack.agents.iterative_fix_agent import Skill
from crackerjack.ai_fix.fix_router import FixRouter
from crackerjack.ai_fix.fixer_registry import FixerRegistry
from crackerjack.ai_fix.issue_classifier import IssueKind
from crackerjack.ai_fix.issue_lifecycle import IssueLifecycle

# ----------------------------------------------------------------------
# Stub collaborators — minimum surface to drive the router's branching.
# ----------------------------------------------------------------------


class StubSkillStore:
    """In-memory :class:`SkillStore` shim with call counters."""

    def __init__(self, skills: dict[str, Skill] | None = None) -> None:
        self._skills = dict(skills or {})
        self.find_calls: list[str] = []
        self.record_calls: list[tuple[str, Skill]] = []

    def find(self, signature: str) -> Skill | None:
        self.find_calls.append(signature)
        return self._skills.get(signature)

    def record(self, signature: str, skill: Skill) -> None:
        self.record_calls.append((signature, skill))
        self._skills[signature] = skill


class StubTier2:
    """Tier-2 dispatcher shim with a single ``fix`` method."""

    def __init__(self, result: FixResult | None = None) -> None:
        self._result = result or FixResult(
            success=True,
            confidence=0.8,
            fixes_applied=["tier2: applied"],
        )
        self.calls = 0
        self.last_issue: Issue | None = None

    async def fix(self, issue: Issue) -> FixResult:
        self.calls += 1
        self.last_issue = issue
        return self._result


class StubTier3:
    """Tier-3 dispatcher shim with a single ``fix`` method."""

    def __init__(self, result: FixResult | None = None) -> None:
        self._result = result or FixResult(
            success=True,
            confidence=0.5,
            fixes_applied=["tier3: applied"],
        )
        self.calls = 0
        self.last_issue: Issue | None = None

    async def fix(self, issue: Issue) -> FixResult:
        self.calls += 1
        self.last_issue = issue
        return self._result


class StubTier3Protocol(Protocol):
    """Shape FixRouter expects from a Tier-3 collaborator.

    The router only calls ``fix`` on it; tests use ``StubTier3`` to satisfy
    this without depending on the IterativeFixAgent class directly.
    """

    async def fix(self, issue: Issue) -> FixResult: ...


# ----------------------------------------------------------------------
# Fixtures
# ----------------------------------------------------------------------


def _issue(file_path: str = "/tmp/test/module.py") -> Issue:
    return Issue(
        type=IssueType.TYPE_ERROR,
        severity=Priority.MEDIUM,
        message="x is not defined",
        file_path=file_path,
        line_number=1,
    )


def _ok_result(fixes: tuple[str, ...] = ()) -> FixResult:
    return FixResult(
        success=True,
        confidence=1.0,
        fixes_applied=list(fixes) or ["applied"],
    )


def _fail_result(*remaining: str) -> FixResult:
    return FixResult(success=False, confidence=0.0, remaining_issues=list(remaining))


class StubFixer:
    """A built-in-style fixer with an ``execute`` method (auto-promoted shape).

    :class:`TightenedFixerDispatcher` wraps ``fixer.execute(plan)`` and reads
    bytes before/after, so this stub writes to ``plan.file_path`` to make
    the bytes-differ check pass on success. When ``should_succeed`` is True
    and ``plan.file_path`` is set, the fixer appends a newline to the file
    so the dispatcher sees a real change.
    """

    def __init__(
        self,
        result: FixResult | None = None,
        side_effect: BaseException | None = None,
        *,
        should_succeed: bool = True,
    ) -> None:
        self._result = result
        self._side_effect = side_effect
        self._should_succeed = should_succeed
        self.calls = 0

    async def execute(self, plan) -> FixResult:
        self.calls += 1
        if self._side_effect is not None:
            raise self._side_effect
        if self._should_succeed and plan and plan.file_path:
            target = Path(plan.file_path)
            if target.exists():
                target.write_text(target.read_text() + "\n", encoding="utf-8")
        if self._result is not None:
            return self._result
        return _ok_result(("tier1: applied",))


def _build_router(
    *,
    registry: FixerRegistry,
    skill_store: StubSkillStore,
    tier2: StubTier2,
    tier3: StubTier3,
) -> FixRouter:
    return FixRouter(
        registry=registry,
        skill_store=skill_store,
        tier2=tier2,
        tier3=tier3,
        classifier=lambda issue: IssueKind.FIXABLE_MECHANICAL,
    )


# ----------------------------------------------------------------------
# Classification routing
# ----------------------------------------------------------------------


class TestClassificationGate:
    def test_non_fixable_returns_failure_without_invoking_tiers(self) -> None:
        registry = FixerRegistry()
        registry.register_builtin("TYPE_ERROR", StubFixer())
        skill_store = StubSkillStore()
        tier2 = StubTier2()
        tier3 = StubTier3()

        def classifier(issue: Issue) -> IssueKind:
            return IssueKind.NON_FIXABLE

        router = FixRouter(
            registry=registry,
            skill_store=skill_store,
            tier2=tier2,
            tier3=tier3,
            classifier=classifier,
        )

        import asyncio

        result = asyncio.run(router.fix(_issue()))

        assert result.success is False
        assert any("non-fixable" in msg.lower() for msg in result.remaining_issues)
        assert tier2.calls == 0
        assert tier3.calls == 0
        assert skill_store.find_calls == []


# ----------------------------------------------------------------------
# Tier-1 routing
# ----------------------------------------------------------------------


class TestTier1Routing:
    def test_tier1_registry_lookup_invokes_built_in_fixer(self, tmp_path: Path) -> None:
        target = tmp_path / "module.py"
        target.write_text("x = 1\n", encoding="utf-8")
        registry = FixerRegistry()
        fixer = StubFixer(result=_ok_result(("tier1: applied",)))
        registry.register_builtin("TYPE_ERROR", fixer)
        skill_store = StubSkillStore()
        tier2 = StubTier2()
        tier3 = StubTier3()
        router = _build_router(
            registry=registry,
            skill_store=skill_store,
            tier2=tier2,
            tier3=tier3,
        )

        import asyncio

        result = asyncio.run(router.fix(_issue(file_path=str(target))))

        assert result.success is True
        assert fixer.calls == 1
        assert tier2.calls == 0
        assert tier3.calls == 0

    def test_tier1_failure_routes_to_skill_replay(self, tmp_path: Path) -> None:
        """When Tier-1 fails and a Skill is cached, the router should
        consult SkillStore next and replay via the injected skill_replay_fn."""
        target = tmp_path / "module.py"
        target.write_text("x = 1\n", encoding="utf-8")
        registry = FixerRegistry()
        # Built-in fails because its execute returns failure.
        registry.register_builtin(
            "TYPE_ERROR", StubFixer(result=_fail_result("tier1 failed"))
        )
        # Skill replay available for this signature.
        skill_signature = "test-skill-signature"
        skill = Skill(
            diff="--- a/module.py\n+++ b/module.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n",
            source_path=str(target),
            recorded_at="2026-07-07T00:00:00Z",
        )
        skill_store = StubSkillStore(skills={skill_signature: skill})
        tier2 = StubTier2()
        tier3 = StubTier3()

        # Inject a successful replay backend (production wires
        # IterativeFixAgent._replay_skill; here we stub it).
        async def _successful_replay(issue, skill):  # type: ignore[no-untyped-def]
            from crackerjack.agents.base import FixResult

            return FixResult(
                success=True,
                confidence=0.9,
                fixes_applied=[f"skill-replay: {skill_signature}"],
                files_modified=[issue.file_path],
            )

        router = FixRouter(
            registry=registry,
            skill_store=skill_store,
            tier2=tier2,
            tier3=tier3,
            classifier=lambda issue: IssueKind.FIXABLE_MECHANICAL,
            skill_signature_fn=lambda issue: skill_signature,
            skill_replay_fn=_successful_replay,
        )

        import asyncio

        result = asyncio.run(router.fix(_issue(file_path=str(target))))

        assert skill_store.find_calls == [skill_signature]
        # Tier-2 / Tier-3 must NOT have fired — skill replay is its own tier.
        assert tier2.calls == 0
        assert tier3.calls == 0
        # The result should indicate skill replay.
        assert result.success is True
        assert any("skill" in fix.lower() for fix in result.fixes_applied)

    def test_tier1_skill_miss_routes_to_tier2(self, tmp_path: Path) -> None:
        target = tmp_path / "module.py"
        target.write_text("x = 1\n", encoding="utf-8")
        registry = FixerRegistry()
        registry.register_builtin(
            "TYPE_ERROR", StubFixer(result=_fail_result("tier1 failed"))
        )
        skill_store = StubSkillStore()  # empty
        tier2 = StubTier2(result=_ok_result(("tier2: applied",)))
        tier3 = StubTier3()
        router = _build_router(
            registry=registry,
            skill_store=skill_store,
            tier2=tier2,
            tier3=tier3,
        )

        import asyncio

        result = asyncio.run(router.fix(_issue(file_path=str(target))))

        assert tier2.calls == 1
        assert tier3.calls == 0
        assert result.success is True

    def test_tier1_no_fixer_routes_to_tier2(self, tmp_path: Path) -> None:
        target = tmp_path / "module.py"
        target.write_text("x = 1\n", encoding="utf-8")
        registry = FixerRegistry()  # empty
        skill_store = StubSkillStore()
        tier2 = StubTier2(result=_ok_result(("tier2: applied",)))
        tier3 = StubTier3()
        router = _build_router(
            registry=registry,
            skill_store=skill_store,
            tier2=tier2,
            tier3=tier3,
        )

        import asyncio

        result = asyncio.run(router.fix(_issue(file_path=str(target))))

        assert tier2.calls == 1
        assert result.success is True


# ----------------------------------------------------------------------
# Tier-2 → Tier-3 escalation
# ----------------------------------------------------------------------


class TestTier2ToTier3Escalation:
    def test_tier2_failure_escalates_to_tier3(self, tmp_path: Path) -> None:
        target = tmp_path / "module.py"
        target.write_text("x = 1\n", encoding="utf-8")
        registry = FixerRegistry()
        registry.register_builtin(
            "TYPE_ERROR", StubFixer(result=_fail_result("tier1 failed"))
        )
        skill_store = StubSkillStore()
        tier2 = StubTier2(result=_fail_result("tier2 failed"))
        tier3 = StubTier3(result=_ok_result(("tier3: applied",)))
        router = _build_router(
            registry=registry,
            skill_store=skill_store,
            tier2=tier2,
            tier3=tier3,
        )

        import asyncio

        result = asyncio.run(router.fix(_issue(file_path=str(target))))

        assert tier2.calls == 1
        assert tier3.calls == 1
        assert result.success is True

    def test_tier2_failure_skips_tier3_for_non_fixable(self, tmp_path: Path) -> None:
        target = tmp_path / "module.py"
        target.write_text("x = 1\n", encoding="utf-8")
        registry = FixerRegistry()
        registry.register_builtin(
            "TYPE_ERROR", StubFixer(result=_fail_result("tier1 failed"))
        )
        skill_store = StubSkillStore()
        tier2 = StubTier2(result=_fail_result("tier2 failed"))
        tier3 = StubTier3()

        def classifier(issue: Issue) -> IssueKind:
            return IssueKind.NON_FIXABLE

        router = FixRouter(
            registry=registry,
            skill_store=skill_store,
            tier2=tier2,
            tier3=tier3,
            classifier=classifier,
        )

        import asyncio

        result = asyncio.run(router.fix(_issue(file_path=str(target))))

        assert tier3.calls == 0
        assert result.success is False


# ----------------------------------------------------------------------
# Lifecycle tracking
# ----------------------------------------------------------------------


class TestLifecycleTracking:
    def test_records_attempts_for_each_tier(self, tmp_path: Path) -> None:
        target = tmp_path / "module.py"
        target.write_text("x = 1\n", encoding="utf-8")
        registry = FixerRegistry()
        registry.register_builtin(
            "TYPE_ERROR", StubFixer(result=_fail_result("tier1 failed"))
        )
        skill_store = StubSkillStore()
        tier2 = StubTier2(result=_fail_result("tier2 failed"))
        tier3 = StubTier3(result=_ok_result(("tier3: applied",)))
        router = _build_router(
            registry=registry,
            skill_store=skill_store,
            tier2=tier2,
            tier3=tier3,
        )

        # Inspect the router's lifecycle after a fix.
        router._peek_lifecycle = lambda issue: IssueLifecycle(
            issue,
            IssueKind.FIXABLE_MECHANICAL,
        )

        import asyncio

        asyncio.run(router.fix(_issue(file_path=str(target))))

        # The router must have populated its lifecycle map for the issue.
        assert (
            router.last_attempts(file_path=str(target)) >= 2
        )  # tier1 + tier2 (tier3 succeeded)


# ----------------------------------------------------------------------
# Spec coverage for "SkillStore.find(signature) replay"
# ----------------------------------------------------------------------


class TestSkillReplayPath:
    def test_skill_replay_result_marks_skill_replay_in_fixes(
        self, tmp_path: Path
    ) -> None:
        target = tmp_path / "module.py"
        target.write_text("x = 1\n", encoding="utf-8")
        registry = FixerRegistry()
        registry.register_builtin(
            "TYPE_ERROR", StubFixer(result=_fail_result("tier1 failed"))
        )
        skill_signature = "sig-1"
        skill = Skill(
            diff="--- a/module.py\n+++ b/module.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n",
            source_path=str(target),
            recorded_at="2026-07-07T00:00:00Z",
        )
        skill_store = StubSkillStore(skills={skill_signature: skill})
        tier2 = StubTier2()
        tier3 = StubTier3()

        async def _successful_replay(issue, skill):  # type: ignore[no-untyped-def]
            from crackerjack.agents.base import FixResult

            return FixResult(
                success=True,
                confidence=0.9,
                fixes_applied=[f"skill-replay: {skill_signature}"],
                files_modified=[issue.file_path],
            )

        router = FixRouter(
            registry=registry,
            skill_store=skill_store,
            tier2=tier2,
            tier3=tier3,
            classifier=lambda issue: IssueKind.FIXABLE_MECHANICAL,
            skill_signature_fn=lambda issue: skill_signature,
            skill_replay_fn=_successful_replay,
        )

        import asyncio

        result = asyncio.run(router.fix(_issue(file_path=str(target))))

        assert result.success is True
        assert any("skill" in fix.lower() for fix in result.fixes_applied)
        assert tier2.calls == 0
        assert tier3.calls == 0

    def test_skill_replay_falls_through_to_tier2_when_no_replay_fn(
        self, tmp_path: Path
    ) -> None:
        """When no replay backend is wired, Tier-1.5 falls through to Tier-2.

        This is the new behavior (kill defect #1 class): the previous
        stub returned success=True on a non-empty diff without ever
        writing bytes. The new stub returns success=False so Tier-2
        gets a chance to do the work.
        """
        target = tmp_path / "module.py"
        target.write_text("x = 1\n", encoding="utf-8")
        registry = FixerRegistry()
        registry.register_builtin(
            "TYPE_ERROR", StubFixer(result=_fail_result("tier1 failed"))
        )
        skill_signature = "sig-1"
        skill = Skill(
            diff="--- a/module.py\n+++ b/module.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n",
            source_path=str(target),
            recorded_at="2026-07-07T00:00:00Z",
        )
        skill_store = StubSkillStore(skills={skill_signature: skill})
        tier2 = StubTier2()
        tier3 = StubTier3()
        # No skill_replay_fn — defaults to the no-op stub.
        router = FixRouter(
            registry=registry,
            skill_store=skill_store,
            tier2=tier2,
            tier3=tier3,
            classifier=lambda issue: IssueKind.FIXABLE_MECHANICAL,
            skill_signature_fn=lambda issue: skill_signature,
        )

        import asyncio

        result = asyncio.run(router.fix(_issue(file_path=str(target))))

        # Tier-2 fired because the skill-replay stub returned failure.
        assert tier2.calls == 1
        # The SkillStore was consulted.
        assert skill_store.find_calls == [skill_signature]
        # The final result comes from Tier-2 (success).
        assert result.success is True
        assert "tier2" in result.fixes_applied[0].lower()


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
