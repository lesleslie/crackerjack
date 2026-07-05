"""Tests for ProactiveAgent truthful-fix-reporting (Bug 3a).

Bug 3a: ``ProactiveAgent.execute_with_plan`` is a stub that returns
``FixResult(success=True, ...)`` with empty ``fixes_applied`` and no
``files_modified``. This is a "ghost fix" — the agent claims success
without writing anything. Per the user decision, the fix is to flip
the default to ``success=False`` so the agent is honest about doing
no work.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from crackerjack.agents.base import AgentContext, FixResult, Issue, IssueType, Priority
from crackerjack.agents.proactive_agent import ProactiveAgent


class _ConcreteProactiveAgent(ProactiveAgent):
    """Concrete subclass that supplies the missing abstract method.

    ``ProactiveAgent`` does not implement ``analyze_and_fix`` (a
    pre-existing latent bug — only the ``EnhancedProactiveAgent``
    subclass supplies it). We subclass here with a shim that
    delegates to ``analyze_and_fix_proactively`` so we can exercise
    the truthfulness fix in isolation. The abstract-method gap is
    out of scope for the Bug 3 PR.
    """

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        return await self.analyze_and_fix_proactively(issue)


def _build_agent(tmp_path: Path) -> ProactiveAgent:
    return _ConcreteProactiveAgent(AgentContext(project_path=tmp_path))


def _make_issue(tmp_path: Path) -> Issue:
    return Issue(
        type=IssueType.TYPE_ERROR,
        severity=Priority.MEDIUM,
        message="missing annotation",
        file_path=str(tmp_path / "module.py"),
    )


class TestProactiveAgentTruthfulReporting:
    """Bug 3a — ghost-fix default flip."""

    @pytest.mark.asyncio
    async def test_execute_with_plan_returns_failure_by_default(
        self, tmp_path: Path
    ) -> None:
        """Stub must report failure (no fix applied) instead of
        claiming success without writing."""
        agent = _build_agent(tmp_path)
        plan: dict = {"strategy": "default"}

        result = await agent.execute_with_plan(
            _make_issue(tmp_path), plan
        )

        assert result.success is False, (
            "execute_with_plan is a stub — must report failure, not "
            "claim success without applying any fix"
        )
        assert result.fixes_applied == []
        assert result.files_modified == []

    @pytest.mark.asyncio
    async def test_analyze_and_fix_does_not_warm_cache_on_stub(
        self, tmp_path: Path
    ) -> None:
        """Caller-side assertion: when the stub returns failure,
        the pattern cache must NOT be warmed. The cache-warming
        guard (line 56: ``result.success and confidence >= 0.8``)
        means a stub success+confidence=0.5 would already skip the
        cache, but a stub success=True is still a lie — this test
        asserts the full caller behavior flips after the fix.
        """
        agent = _build_agent(tmp_path)
        cache_calls: list[tuple] = []
        agent._cache_successful_pattern = MagicMock(  # type: ignore[method-assign]
            side_effect=lambda *args, **kwargs: cache_calls.append((args, kwargs))
        )

        result = await agent.analyze_and_fix_proactively(_make_issue(tmp_path))

        assert result.success is False
        assert cache_calls == [], (
            f"stub must not warm the pattern cache; got {cache_calls!r}"
        )