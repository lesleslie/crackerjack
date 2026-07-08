"""PR 7 — SkillStore wiring into the router.

PR 7 of the 2026-07-07 ai-fix design wires the existing
:class:`SkillStore` protocol into :class:`FixRouter` so:

1. The router consults ``SkillStore.find(signature)`` between Tier-1
   and Tier-2; a hit short-circuits the remaining tiers.
2. On Tier-3 success, the router asks the Tier-3 dispatcher for the
   freshly generated ``Skill`` (``last_generated_skill`` attribute) and
   persists it via ``SkillStore.record(signature, skill)`` so the next
   occurrence of the same defect replays instead of re-dispatching.

These tests pin both halves, plus the signature helper that derives the
keys. They are intentionally additive — the PR-6 tests live alongside
without being modified.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from crackerjack.agents.base import FixResult, Issue, IssueType, Priority
from crackerjack.agents.iterative_fix_agent import Skill
from crackerjack.ai_fix.fix_router import FixRouter
from crackerjack.ai_fix.fixer_registry import FixerRegistry
from crackerjack.ai_fix.issue_classifier import IssueKind
from crackerjack.ai_fix.issue_lifecycle import signature_for_issue

# ---------------------------------------------------------------------------
# Stub collaborators
# ---------------------------------------------------------------------------


class CountingSkillStore:
    """A SkillStore double that records both find and record invocations."""

    def __init__(
        self,
        *,
        skills: dict[str, Skill] | None = None,
    ) -> None:
        self._skills: dict[str, Skill] = dict(skills or {})
        self.find_calls: list[str] = []
        self.record_calls: list[tuple[str, Skill]] = []

    def find(self, signature: str) -> Skill | None:
        self.find_calls.append(signature)
        return self._skills.get(signature)

    def record(self, signature: str, skill: Skill) -> None:
        self.record_calls.append((signature, skill))
        self._skills[signature] = skill


class _NoOpFixer:
    """A built-in fixer that intentionally fails so the router falls through."""

    def __init__(self) -> None:
        self.calls = 0

    async def execute(self, plan) -> FixResult:
        self.calls += 1
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["tier-1 always fails (intentional)"],
        )


class _CapturingTier2:
    async def fix(self, issue: Issue) -> FixResult:
        return FixResult(
            success=True,
            confidence=0.7,
            fixes_applied=["tier2-ok"],
        )


class _SkillProducingTier3:
    """Tier-3 dispatcher that exposes ``last_generated_skill`` after fix().

    Matches :class:`crackerjack.agents.iterative_fix_agent.IterativeFixAgent`'s
    convention — the router reads that attribute on success to persist the
    skill via ``SkillStore.record``.
    """

    def __init__(
        self,
        *,
        success: bool,
        skill: Skill | None = None,
    ) -> None:
        self._success = success
        self._skill = skill
        self.calls = 0
        self.last_issue: Issue | None = None

    async def fix(self, issue: Issue) -> FixResult:
        self.calls += 1
        self.last_issue = issue
        return FixResult(
            success=self._success,
            confidence=0.5,
            fixes_applied=["tier3"],
            files_modified=[issue.file_path]
            if self._success and issue.file_path
            else [],
        )

    @property
    def last_generated_skill(self) -> Skill | None:
        return self._skill


def _issue(
    *,
    file_path: str = "/tmp/test/module.py",
    message: str = "Attribute `lower` is not defined on `None`",
    issue_type: IssueType = IssueType.TYPE_ERROR,
) -> Issue:
    return Issue(
        type=issue_type,
        severity=Priority.MEDIUM,
        message=message,
        file_path=file_path,
        line_number=1,
    )


def _router(
    *,
    skill_store: CountingSkillStore,
    tier2: object | None = None,
    tier3: object | None = None,
    classifier=lambda _: IssueKind.FIXABLE_MECHANICAL,
    skill_signature_fn=None,
) -> FixRouter:
    registry = FixerRegistry()
    return FixRouter(
        registry=registry,
        skill_store=skill_store,
        tier2=tier2 if tier2 is not None else _CapturingTier2(),
        tier3=tier3 if tier3 is not None else _SkillProducingTier3(success=False),
        classifier=classifier,
        skill_signature_fn=skill_signature_fn,
    )


# ---------------------------------------------------------------------------
# signature_for_issue (signature helper used by the router)
# ---------------------------------------------------------------------------


class TestSignatureForIssue:
    def test_same_pattern_yields_same_signature(self) -> None:
        """Two issues with the same normalized pattern share a signature.

        Backtick identifiers (e.g. ``lower``, ``upper``) collapse to ``X``
        so the same defect shape in two different files produces one
        signature.
        """
        a = _issue(message="Attribute `lower` is not defined on `None`")
        b = _issue(message="Attribute `upper` is not defined on `None`")
        assert signature_for_issue(a) == signature_for_issue(b)

    def test_different_patterns_yield_different_signatures(self) -> None:
        a = _issue(message="Attribute `lower` is not defined on `None`")
        b = _issue(
            message="Cannot subscript `None` with `int`",
            issue_type=IssueType.TYPE_ERROR,
        )
        assert signature_for_issue(a) != signature_for_issue(b)

    def test_different_codes_yield_different_signatures(self) -> None:
        a = _issue(message="some error", issue_type=IssueType.TYPE_ERROR)
        b = _issue(message="some error", issue_type=IssueType.FORMATTING)
        assert signature_for_issue(a) != signature_for_issue(b)

    def test_signature_is_16_chars(self) -> None:
        sig = signature_for_issue(_issue())
        assert len(sig) == 16
        # Hex-only output of sha256 truncated.
        int(sig, 16)


# ---------------------------------------------------------------------------
# SkillStore consultation between Tier-1 and Tier-2
# ---------------------------------------------------------------------------


class TestSkillStoreConsult:
    def test_skill_store_is_consulted_with_default_signature(self) -> None:
        """A cache hit short-circuits all lower tiers.

        The router's default signature fn hashes the normalized
        ``Issue.type.value + Issue.message``, so we pre-compute the
        same key here.
        """
        issue = _issue()
        expected_signature = signature_for_issue(issue)
        cached_skill = Skill(
            diff=("--- a/module.py\n+++ b/module.py\n@@ -1 +1 @@\n-old\n+new\n"),
            source_path=issue.file_path,
            recorded_at="2026-07-07T00:00:00Z",
        )
        skill_store = CountingSkillStore(skills={expected_signature: cached_skill})
        router = _router(skill_store=skill_store)

        result = asyncio.run(router.fix(issue))

        assert result.success is True
        # The find happened, with the router's signature as key.
        assert skill_store.find_calls == [expected_signature]
        # No record call — a cache hit is read-only.
        assert skill_store.record_calls == []

    def test_skill_store_find_called_with_signature_for_issue_key(
        self, tmp_path: Path
    ) -> None:
        """The router's default ``skill_signature_fn`` uses ``signature_for_issue``.

        Pinning this separately so a future change to the default key
        shape is intentional.
        """
        target = tmp_path / "module.py"
        target.write_text("x = 1\n", encoding="utf-8")
        issue = _issue(file_path=str(target))

        skill_store = CountingSkillStore()
        # No tier-1 fixer registered; route skips Tier-1 cleanly.
        router = _router(skill_store=skill_store)

        asyncio.run(router.fix(issue))

        # Tier-1 miss → tier-1.5 consult → cache miss → tier-2.
        # One find call is expected.
        assert len(skill_store.find_calls) == 1
        assert skill_store.find_calls[0] == signature_for_issue(issue)


# ---------------------------------------------------------------------------
# SkillStore.record on Tier-3 success
# ---------------------------------------------------------------------------


class TestSkillStoreRecordOnTier3:
    def test_record_called_after_tier3_success_with_generated_skill(
        self, tmp_path: Path
    ) -> None:
        """On Tier-3 success with ``last_generated_skill``, the router records it."""
        target = tmp_path / "module.py"
        target.write_text("x = 1\n", encoding="utf-8")
        issue = _issue(file_path=str(target))
        generated = Skill(
            diff="--- a/module.py\n+++ b/module.py\n@@ -1 +1 @@\n-x = 1\n+x = 2\n",
            source_path=issue.file_path or "",
            recorded_at="2026-07-07T00:00:00Z",
        )
        skill_store = CountingSkillStore()
        tier3 = _SkillProducingTier3(success=True, skill=generated)
        registry = FixerRegistry()
        # Register a no-op tier-1 so tier-1 fails and the router falls
        # through to tier-1.5 (cache miss) → tier-2 (success in
        # ``_CapturingTier2`` has only one of Tier-2/Tier-3 succeed; here
        # we override tier-2 to fail so the router escalates to tier-3).
        registry.register_builtin("TYPE_ERROR", _NoOpFixer())
        router = FixRouter(
            registry=registry,
            skill_store=skill_store,
            tier2=_FailingTier2(),
            tier3=tier3,
            classifier=lambda _: IssueKind.FIXABLE_MECHANICAL,
        )

        result = asyncio.run(router.fix(issue))

        assert result.success is True
        assert tier3.calls == 1
        # Skill recorded under the router's signature.
        expected_signature = signature_for_issue(issue)
        assert len(skill_store.record_calls) == 1
        recorded_signature, recorded_skill = skill_store.record_calls[0]
        assert recorded_signature == expected_signature
        assert recorded_skill is generated

    def test_record_skipped_when_tier3_fails(self, tmp_path: Path) -> None:
        """A failed Tier-3 must not produce a SkillStore.record call."""
        target = tmp_path / "module.py"
        target.write_text("x = 1\n", encoding="utf-8")
        skill_store = CountingSkillStore()
        tier3 = _SkillProducingTier3(
            success=False,
            skill=Skill(diff="not-used", source_path="x.py", recorded_at="t"),
        )
        registry = FixerRegistry()
        registry.register_builtin("TYPE_ERROR", _NoOpFixer())
        router = FixRouter(
            registry=registry,
            skill_store=skill_store,
            tier2=_FailingTier2(),
            tier3=tier3,
            classifier=lambda _: IssueKind.FIXABLE_MECHANICAL,
        )

        asyncio.run(router.fix(_issue(file_path=str(target))))

        assert skill_store.record_calls == []

    def test_record_skipped_when_tier3_succeeds_but_no_skill_available(
        self, tmp_path: Path
    ) -> None:
        """Tier-3 success without ``last_generated_skill`` is a no-op for record."""
        target = tmp_path / "module.py"
        target.write_text("x = 1\n", encoding="utf-8")
        skill_store = CountingSkillStore()
        tier3 = _SkillProducingTier3(success=True, skill=None)
        registry = FixerRegistry()
        registry.register_builtin("TYPE_ERROR", _NoOpFixer())
        router = FixRouter(
            registry=registry,
            skill_store=skill_store,
            tier2=_FailingTier2(),
            tier3=tier3,
            classifier=lambda _: IssueKind.FIXABLE_MECHANICAL,
        )

        asyncio.run(router.fix(_issue(file_path=str(target))))

        assert skill_store.record_calls == []

    def test_record_handles_dispatcher_without_last_generated_skill_attribute(
        self, tmp_path: Path
    ) -> None:
        """The router tolerates a Tier-3 dispatcher that omits the attribute.

        The ``getattr(self._tier3, "last_generated_skill", None)`` call
        must default to ``None`` so the router stays behavior-compatible
        with the PR-6 stub dispatchers.
        """
        target = tmp_path / "module.py"
        target.write_text("x = 1\n", encoding="utf-8")
        skill_store = CountingSkillStore()
        registry = FixerRegistry()
        registry.register_builtin("TYPE_ERROR", _NoOpFixer())
        router = FixRouter(
            registry=registry,
            skill_store=skill_store,
            tier2=_FailingTier2(),
            tier3=_PlainTier3(),
            classifier=lambda _: IssueKind.FIXABLE_MECHANICAL,
        )

        result = asyncio.run(router.fix(_issue(file_path=str(target))))

        assert result.success is True
        assert skill_store.record_calls == []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FailingTier2:
    async def fix(self, issue: Issue) -> FixResult:
        return FixResult(
            success=False,
            confidence=0.0,
            remaining_issues=["tier2 failed"],
        )


class _PlainTier3:
    """Tier-3 dispatcher without ``last_generated_skill``."""

    def __init__(self) -> None:
        self.calls = 0

    async def fix(self, issue: Issue) -> FixResult:
        self.calls += 1
        return FixResult(
            success=True,
            confidence=0.5,
            fixes_applied=["tier3"],
            files_modified=[issue.file_path] if issue.file_path else [],
        )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
