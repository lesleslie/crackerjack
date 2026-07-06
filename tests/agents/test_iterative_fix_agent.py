"""Tests for ``crackerjack.agents.iterative_fix_agent``.

Tier-3 dispatch architecture. Tests cover:

* Signature stability across files (the same PATTERN -> same hash).
* Skill replay fast-path vs. worker-dispatch slow-path.
* Skill capture on success.
* Local fallback implementations work without Mahavishnu or
  Session-Buddy (subprocess + dict).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from crackerjack.agents.iterative_fix_agent import (
    DispatchResult,
    InMemorySkillStore,
    IterativeFixAgent,
    LocalClaudeSubprocess,
    MahavishnuPool,
    SessionBuddySkillStore,
    Skill,
    TyDiagnostic,
    signature_for,
)

# ---------------------------------------------------------------------------
# signature_for
# ---------------------------------------------------------------------------


class TestSignatureFor:
    def test_same_pattern_in_two_files_produces_same_signature(self) -> None:
        # Two unrelated files, same error shape — same signature.
        a = TyDiagnostic(
            file=Path("a.py"),
            line=10,
            col=4,
            code="unsupported-attribute",
            message="Attribute `lower` is not defined on `None` in union `str | None`",
        )
        b = TyDiagnostic(
            file=Path("b.py"),
            line=99,
            col=12,
            code="unsupported-attribute",
            message="Attribute `lower` is not defined on `None` in union `str | None`",
        )
        assert signature_for([a]) == signature_for([b])

    def test_different_messages_produce_different_signatures(self) -> None:
        # The signatures differ when the *non-backtick* portions of
        # the message differ. Backtick identifiers are normalized
        # to `X` by design — that's how pattern-level dedup works.
        a = TyDiagnostic(
            file=Path("a.py"),
            line=1,
            col=1,
            code="unsupported-attribute",
            message="Attribute `lower` is not defined on `None`",
        )
        b = TyDiagnostic(
            file=Path("b.py"),
            line=1,
            col=1,
            code="not-subscriptable",
            message="Cannot subscript object of type `None` with no `__getitem__` method",
        )
        assert signature_for([a]) != signature_for([b])

    def test_different_codes_produce_different_signatures(self) -> None:
        a = TyDiagnostic(
            file=Path("a.py"),
            line=1,
            col=1,
            code="unsupported-attribute",
            message="Attribute `lower` is not defined on `None`",
        )
        b = TyDiagnostic(
            file=Path("a.py"),
            line=1,
            col=1,
            code="not-subscriptable",
            message="Attribute `lower` is not defined on `None`",
        )
        assert signature_for([a]) != signature_for([b])

    def test_signature_is_deterministic(self) -> None:
        a = TyDiagnostic(
            file=Path("a.py"),
            line=1,
            col=1,
            code="unsupported-attribute",
            message="Attribute `lower` is not defined on `None`",
        )
        sigs = {signature_for([a]) for _ in range(20)}
        assert len(sigs) == 1  # always the same

    def test_empty_diagnostics_returns_valid_signature(self) -> None:
        # Even with no diagnostics, we should produce a deterministic hash.
        sig = signature_for([])
        assert len(sig) == 16  # sha256 truncated


# ---------------------------------------------------------------------------
# InMemorySkillStore
# ---------------------------------------------------------------------------


class TestInMemorySkillStore:
    def test_record_and_find(self) -> None:
        store = InMemorySkillStore()
        skill = Skill(diff="--- a\n+++ b\n", source_path="/x.py", recorded_at="now")
        store.record("sig-1", skill)
        assert store.find("sig-1") == skill
        assert store.find("missing") is None

    def test_record_overwrites(self) -> None:
        store = InMemorySkillStore()
        first = Skill(diff="v1", source_path="/x.py", recorded_at="t1")
        second = Skill(diff="v2", source_path="/x.py", recorded_at="t2")
        store.record("sig", first)
        store.record("sig", second)
        assert store.find("sig") == second

    def test_len_counts_skills(self) -> None:
        store = InMemorySkillStore()
        assert len(store) == 0
        store.record("a", Skill(diff="", source_path="", recorded_at=""))
        store.record("b", Skill(diff="", source_path="", recorded_at=""))
        assert len(store) == 2


# ---------------------------------------------------------------------------
# LocalClaudeSubprocess
# ---------------------------------------------------------------------------


class TestLocalClaudeSubprocess:
    def test_dispatch_with_success_exit_code(self, tmp_path: Path) -> None:
        # Use echo as a stand-in for `claude` — exit 0 with stdout.
        pool = LocalClaudeSubprocess(command=("echo", "fixed"))
        result = pool.dispatch(prompt="x", working_directory=tmp_path)
        assert result.success is True
        assert "fixed" in result.diff

    def test_dispatch_with_failure_exit_code(self, tmp_path: Path) -> None:
        pool = LocalClaudeSubprocess(command=("false",))
        result = pool.dispatch(prompt="x", working_directory=tmp_path)
        assert result.success is False

    def test_dispatch_handles_command_not_found(self, tmp_path: Path) -> None:
        pool = LocalClaudeSubprocess(command=("/no/such/command/anywhere",))
        result = pool.dispatch(prompt="x", working_directory=tmp_path)
        assert result.success is False
        assert "not found" in result.message.lower()

    def test_dispatch_handles_timeout(self, tmp_path: Path) -> None:
        # sleep with tiny timeout — TimeoutExpired on the run.
        pool = LocalClaudeSubprocess(command=("sleep", "5"))
        result = pool.dispatch(
            prompt="x", working_directory=tmp_path, timeout_seconds=1
        )
        assert result.success is False
        assert "timed out" in result.message.lower()

    def test_dispatch_passes_prompt_via_stdin(self, tmp_path: Path) -> None:
        # cat echoes its stdin back to stdout — we can read the prompt.
        # Use sh -c to make the cat command work on all platforms.
        pool = LocalClaudeSubprocess(command=("cat",))
        result = pool.dispatch(prompt="the-magic-prompt", working_directory=tmp_path)
        assert result.success is True
        assert "the-magic-prompt" in result.diff


# ---------------------------------------------------------------------------
# IterativeFixAgent
# ---------------------------------------------------------------------------


class _StubPool:
    """Minimal WorkerPool stub for testing the agent's dispatch flow."""

    def __init__(self, *, success: bool = True, diff: str = "fake-diff") -> None:
        self.success = success
        self.diff = diff
        self.calls: list[dict] = []

    def dispatch(
        self, prompt: str, working_directory: Path, timeout_seconds: int = 600
    ) -> DispatchResult:
        self.calls.append(
            {
                "prompt": prompt,
                "working_directory": working_directory,
                "timeout_seconds": timeout_seconds,
            }
        )
        return DispatchResult(
            success=self.success,
            diff=self.diff,
            message="stub",
        )


class TestIterativeFixAgent:
    def _diagnostics(self) -> list[TyDiagnostic]:
        return [
            TyDiagnostic(
                file=Path("foo.py"),
                line=10,
                col=4,
                code="unsupported-attribute",
                message="Attribute `lower` is not defined on `None`",
            )
        ]

    def test_skill_replay_when_signature_known(self, tmp_path: Path) -> None:
        # Pre-record a skill for the signature with a real (non-empty)
        # diff so the scaffold replay path treats it as a hit.
        diagnostics = self._diagnostics()
        sig = signature_for(diagnostics)
        store = InMemorySkillStore()
        store.record(
            sig,
            Skill(
                diff="--- a\n+++ b\n@@ -1 +1 @@\n-old\n+new\n",
                source_path="x.py",
                recorded_at="t",
            ),
        )
        pool = _StubPool()
        agent = IterativeFixAgent(pool=pool, skill_store=store)

        target = tmp_path / "foo.py"
        target.write_text("")

        outcome = agent.fix_file(target, diagnostics)
        assert outcome.success is True
        assert outcome.path_was_skill_replay is True
        assert outcome.dispatched_to_pool is False
        # Pool must NOT be called on skill replay.
        assert pool.calls == []

    def test_dispatch_when_no_skill(self, tmp_path: Path) -> None:
        # No skill in store -> must dispatch to pool.
        store = InMemorySkillStore()
        pool = _StubPool(success=True, diff="real-diff")
        agent = IterativeFixAgent(pool=pool, skill_store=store)

        target = tmp_path / "foo.py"
        target.write_text("")

        outcome = agent.fix_file(target, self._diagnostics())
        assert outcome.success is True
        assert outcome.dispatched_to_pool is True
        assert outcome.path_was_skill_replay is False
        assert outcome.skill_recorded is True
        assert len(pool.calls) == 1
        # Prompt should mention the file and the error.
        prompt = pool.calls[0]["prompt"]
        assert str(target) in prompt
        assert "unsupported-attribute" in prompt

    def test_no_skill_recorded_on_dispatch_failure(self, tmp_path: Path) -> None:
        store = InMemorySkillStore()
        pool = _StubPool(success=False, diff="")
        agent = IterativeFixAgent(pool=pool, skill_store=store)

        target = tmp_path / "foo.py"
        target.write_text("")

        outcome = agent.fix_file(target, self._diagnostics())
        assert outcome.success is False
        assert outcome.skill_recorded is False
        assert len(store) == 0  # no skill recorded

    def test_dispatch_exception_returns_failure(self, tmp_path: Path) -> None:
        class ExplodingPool:
            def dispatch(self, prompt, working_directory, timeout_seconds=600):
                raise RuntimeError("boom")

        store = InMemorySkillStore()
        agent = IterativeFixAgent(pool=ExplodingPool(), skill_store=store)
        target = tmp_path / "foo.py"
        target.write_text("")

        outcome = agent.fix_file(target, self._diagnostics())
        assert outcome.success is False
        assert "boom" in outcome.message

    def test_prompt_includes_max_iterations(self, tmp_path: Path) -> None:
        store = InMemorySkillStore()
        pool = _StubPool()
        agent = IterativeFixAgent(pool=pool, skill_store=store, max_iterations=7)

        target = tmp_path / "foo.py"
        target.write_text("")

        agent.fix_file(target, self._diagnostics())
        assert "max 7 times" in pool.calls[0]["prompt"]

    def test_no_dispatch_for_skill_replay_with_empty_diff(self, tmp_path: Path) -> None:
        # An empty diff means the skill can't actually be replayed.
        # Scaffold behavior: return failure, do NOT fall through
        # to dispatch (would double the cost for a fix that we
        # couldn't even describe). Real PR with patch-applier
        # would re-dispatch on replay fail.
        diagnostics = self._diagnostics()
        sig = signature_for(diagnostics)
        store = InMemorySkillStore()
        store.record(sig, Skill(diff="", source_path="x.py", recorded_at="t"))
        pool = _StubPool()
        agent = IterativeFixAgent(pool=pool, skill_store=store)

        target = tmp_path / "foo.py"
        target.write_text("")

        outcome = agent.fix_file(target, diagnostics)
        assert outcome.success is False
        assert pool.calls == []


# ---------------------------------------------------------------------------
# MahavishnuPool
# ---------------------------------------------------------------------------


class TestMahavishnuPool:
    def test_dispatches_via_mcp_client(self, tmp_path: Path) -> None:
        mcp = MagicMock()
        mcp.pool_route_execute.return_value = {"success": True, "result": "diff"}
        pool = MahavishnuPool(mcp_client=mcp)

        pool.dispatch(
            prompt="fix this",
            working_directory=tmp_path,
            timeout_seconds=300,
        )

        mcp.pool_route_execute.assert_called_once_with(
            prompt="fix this",
            pool_selector="least_loaded",
            timeout=300,
        )

    def test_returns_dispatch_result_on_success(self, tmp_path: Path) -> None:
        mcp = MagicMock()
        mcp.pool_route_execute.return_value = {
            "success": True,
            "result": "diff content",
        }
        pool = MahavishnuPool(mcp_client=mcp)

        result = pool.dispatch(prompt="x", working_directory=tmp_path)

        assert result.success is True
        assert result.diff == "diff content"

    def test_returns_dispatch_result_on_failure(self, tmp_path: Path) -> None:
        mcp = MagicMock()
        mcp.pool_route_execute.return_value = {"success": False}
        pool = MahavishnuPool(mcp_client=mcp)

        result = pool.dispatch(prompt="x", working_directory=tmp_path)

        assert result.success is False

    def test_custom_pool_selector(self, tmp_path: Path) -> None:
        mcp = MagicMock()
        mcp.pool_route_execute.return_value = {"success": True, "result": ""}
        pool = MahavishnuPool(mcp_client=mcp, selector="affinity")

        pool.dispatch(prompt="x", working_directory=tmp_path)

        assert mcp.pool_route_execute.call_args.kwargs["pool_selector"] == "affinity"

    def test_default_timeout_matches_local_fallback(self, tmp_path: Path) -> None:
        # MahavishnuPool should default to 600s — same as LocalClaudeSubprocess.
        # Drift between the two would surface as an "uneven worker" footgun.
        mcp = MagicMock()
        mcp.pool_route_execute.return_value = {"success": True, "result": ""}
        pool = MahavishnuPool(mcp_client=mcp)

        pool.dispatch(prompt="x", working_directory=tmp_path)

        assert mcp.pool_route_execute.call_args.kwargs["timeout"] == 600

    def test_stringifies_non_string_result_payload(self, tmp_path: Path) -> None:
        # Defensive parsing: result may be a dict (worker JSON dump).
        # We coerce to str rather than crash.
        mcp = MagicMock()
        mcp.pool_route_execute.return_value = {
            "success": True,
            "result": {"patched_files": 3},
        }
        pool = MahavishnuPool(mcp_client=mcp)

        result = pool.dispatch(prompt="x", working_directory=tmp_path)

        assert result.success is True
        assert "patched_files" in result.diff

    def test_handles_non_dict_response(self, tmp_path: Path) -> None:
        # Worst case: worker returns a bare string. Don't crash.
        mcp = MagicMock()
        mcp.pool_route_execute.return_value = "just a string"
        pool = MahavishnuPool(mcp_client=mcp)

        result = pool.dispatch(prompt="x", working_directory=tmp_path)

        assert result.success is False


# ---------------------------------------------------------------------------
# SessionBuddySkillStore
# ---------------------------------------------------------------------------


class TestSessionBuddySkillStore:
    def test_record_calls_distill_skills_now(self) -> None:
        mcp = MagicMock()
        mcp.distill_skills_now.return_value = None
        store = SessionBuddySkillStore(mcp_client=mcp)

        store.record(
            "sig-abc",
            Skill(diff="the-diff", source_path="/a.py", recorded_at="now"),
        )

        mcp.distill_skills_now.assert_called_once_with(
            problem="sig-abc",
            because="applied at /a.py",
            approach="the-diff",
            evidence_threshold=3,
        )

    def test_record_uses_custom_evidence_threshold(self) -> None:
        mcp = MagicMock()
        mcp.distill_skills_now.return_value = None
        store = SessionBuddySkillStore(mcp_client=mcp, evidence_threshold=7)

        store.record(
            "sig-1",
            Skill(diff="d", source_path="/a.py", recorded_at="now"),
        )

        assert mcp.distill_skills_now.call_args.kwargs["evidence_threshold"] == 7

    def test_find_calls_search_distilled_skills(self) -> None:
        mcp = MagicMock()
        mcp.search_distilled_skills.return_value = [
            {"diff": "d", "source_path": "/x.py", "recorded_at": "t"},
        ]
        store = SessionBuddySkillStore(mcp_client=mcp)

        skill = store.find("sig-1")

        mcp.search_distilled_skills.assert_called_once_with(query="sig-1")
        assert skill is not None
        assert skill.diff == "d"
        assert skill.source_path == "/x.py"
        assert skill.recorded_at == "t"

    def test_find_returns_none_on_no_hit(self) -> None:
        mcp = MagicMock()
        mcp.search_distilled_skills.return_value = []
        store = SessionBuddySkillStore(mcp_client=mcp)

        assert store.find("missing") is None

    def test_find_returns_none_on_exception(self) -> None:
        mcp = MagicMock()
        mcp.search_distilled_skills.side_effect = RuntimeError("boom")
        store = SessionBuddySkillStore(mcp_client=mcp)

        # Lookup is best-effort — never crash the dispatch path
        # on a memory-layer miss.
        assert store.find("sig") is None

    def test_find_returns_none_on_non_list_response(self) -> None:
        mcp = MagicMock()
        mcp.search_distilled_skills.return_value = "not a list"
        store = SessionBuddySkillStore(mcp_client=mcp)

        assert store.find("sig") is None
