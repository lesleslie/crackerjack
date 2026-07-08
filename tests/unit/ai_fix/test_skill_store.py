"""Tests for the in-memory :class:`SkillStore` (PR 7).

PR 7 of the 2026-07-07 ai-fix design wires the existing
:class:`crackerjack.agents.iterative_fix_agent.SkillStore` protocol into
the ``FixRouter`` so a successful Tier-3 dispatch lands a cached ``Skill``
and the next dispatch with the same signature replays instead of
re-running the LLM.

The router does not care which concrete store backs the protocol — for
this PR the in-memory implementation
(:class:`crackerjack.agents.iterative_fix_agent.InMemorySkillStore`) is
the canonical implementation. These tests pin ``find`` / ``record`` /
overwrite / ``len`` and the round-trip with the ``Skill`` dataclass,
plus the on-disk semantics (``Skill.diff`` round-trips intact``).

The deeper ``_replay_skill`` applier is covered in
``tests/agents/test_iterative_fix_agent.py``; the protocol contract is
covered here.
"""

from __future__ import annotations

import pytest

from crackerjack.agents.iterative_fix_agent import (
    InMemorySkillStore,
    SessionBuddySkillStore,
    Skill,
)

# ---------------------------------------------------------------------------
# InMemorySkillStore
# ---------------------------------------------------------------------------


class TestInMemorySkillStore:
    def test_find_returns_none_when_empty(self) -> None:
        store = InMemorySkillStore()

        assert store.find("missing") is None

    def test_record_then_find_returns_same_skill(self) -> None:
        store = InMemorySkillStore()
        skill = Skill(
            diff="--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-old\n+new\n",
            source_path="x.py",
            recorded_at="2026-07-07T00:00:00Z",
        )

        store.record("sig-1", skill)

        assert store.find("sig-1") == skill

    def test_record_overwrites_previous_skill_for_same_signature(self) -> None:
        store = InMemorySkillStore()
        first = Skill(diff="diff-v1", source_path="a.py", recorded_at="t1")
        second = Skill(diff="diff-v2", source_path="a.py", recorded_at="t2")

        store.record("sig", first)
        store.record("sig", second)

        assert store.find("sig") is second

    def test_find_does_not_see_other_signatures(self) -> None:
        store = InMemorySkillStore()
        skill = Skill(diff="d", source_path="x.py", recorded_at="t")
        store.record("sig-A", skill)

        assert store.find("sig-A") == skill
        assert store.find("sig-B") is None

    def test_len_reflects_recorded_signatures(self) -> None:
        store = InMemorySkillStore()
        assert len(store) == 0

        store.record("a", Skill(diff="", source_path="", recorded_at=""))
        store.record("b", Skill(diff="", source_path="", recorded_at=""))
        assert len(store) == 2

        # Re-recording the same signature must not change the count.
        store.record("a", Skill(diff="overwritten", source_path="", recorded_at=""))
        assert len(store) == 2

    def test_diff_round_trips_intact(self) -> None:
        diff = (
            "--- a/module.py\n"
            "+++ b/module.py\n"
            "@@ -1,3 +1,3 @@\n"
            "-x = 1\n"
            "-y = 2\n"
            "+x = 2\n"
            "+y = 3\n"
            " z = 0\n"
        )
        store = InMemorySkillStore()
        store.record("sig", Skill(diff=diff, source_path="module.py", recorded_at="t"))

        retrieved = store.find("sig")
        assert retrieved is not None
        assert retrieved.diff == diff


# ---------------------------------------------------------------------------
# Replay round-trip (record → find → Skill is the one we recorded)
# ---------------------------------------------------------------------------


class TestReplayRoundTrip:
    def test_recorded_skill_is_usable_as_replay_payload(self) -> None:
        """A recorded skill must be usable as the diff payload for replay.

        The replier (IterativeFixAgent._replay_skill) parses the diff with
        ``unidiff``. These tests do not exercise that applier directly —
        see tests/agents/test_iterative_fix_agent.py — they only verify
        the store preserves the diff byte-for-byte.
        """
        store = InMemorySkillStore()
        diff = "--- a/x.py\n+++ b/x.py\n@@ -10,2 +10,2 @@\n line-a\n-line-b\n+line-B\n"
        skill = Skill(diff=diff, source_path="x.py", recorded_at="2026-07-07T00:00:00Z")
        store.record("sig-X", skill)

        reloaded = store.find("sig-X")
        assert reloaded is not None
        assert reloaded.source_path == "x.py"
        assert reloaded.recorded_at == "2026-07-07T00:00:00Z"
        assert reloaded.diff.startswith("--- a/x.py")
        assert "+line-B" in reloaded.diff


# ---------------------------------------------------------------------------
# SessionBuddySkillStore — protocol conformance check
# ---------------------------------------------------------------------------


class _FakeMCPClient:
    """Bare-bones MCP client double for SessionBuddySkillStore unit tests."""

    def __init__(
        self,
        *,
        search_results: list[dict[str, object]] | None = None,
        distill_raises: bool = False,
    ) -> None:
        self.search_calls: list[dict[str, object]] = []
        self.distill_calls: list[dict[str, object]] = []
        self._search_results = search_results
        self._distill_raises = distill_raises

    def search_distilled_skills(self, query: str) -> list[dict[str, object]]:
        self.search_calls.append({"query": query})
        if self._search_results is None:
            return []
        return list(self._search_results)

    def distill_skills_now(
        self,
        problem: str,
        because: str,
        approach: str,
        evidence_threshold: int,
    ) -> object:
        if self._distill_raises:
            raise RuntimeError("boom")
        self.distill_calls.append(
            {
                "problem": problem,
                "because": because,
                "approach": approach,
                "evidence_threshold": evidence_threshold,
            }
        )
        return {}


class TestSessionBuddySkillStore:
    """Pin the SessionBuddy-backed implementation's shape.

    The router only needs the protocol (``find``/``record``); these tests
    verify the SessionBuddy adapter behavior without going near the network.
    """

    def test_find_returns_none_when_search_returns_empty(self) -> None:
        store = SessionBuddySkillStore(_FakeMCPClient(search_results=[]))

        assert store.find("missing") is None

    def test_record_logs_failure_but_does_not_raise(self) -> None:
        store = SessionBuddySkillStore(_FakeMCPClient(distill_raises=True))
        skill = Skill(diff="d", source_path="x.py", recorded_at="t")

        # Distill failures must NOT propagate — they are logged only,
        # so a transient backend outage does not crash the fix loop.
        store.record("sig", skill)


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
