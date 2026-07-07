"""Tests for ``crackerjack.agents.iterative_fix_agent``.

Tier-3 dispatch architecture. Tests cover:

* Signature stability across files (the same PATTERN -> same hash).
* Skill replay fast-path vs. worker-dispatch slow-path.
* Skill capture on success.
* Skill replay applier (unidiff-based patch application):
    happy path, context mismatch, malformed diff, wrong target
    file, and partial-apply safety.
* Local fallback implementations work without Mahavishnu or
  Session-Buddy (subprocess + dict).
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest

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
    def _unsafe(self, command: tuple[str, ...]) -> LocalClaudeSubprocess:
        """Test-only escape hatch that bypasses the executable allowlist.

        Lets tests verify dispatch/error handling without depending on
        the actual ``claude`` binary. Production callers should never
        use this — pass a ``claude`` or ``qwen`` command to
        ``__init__``.
        """
        instance = LocalClaudeSubprocess.__new__(LocalClaudeSubprocess)
        instance.command = command
        return instance

    def test_dispatch_with_success_exit_code(self, tmp_path: Path) -> None:
        # Use echo as a stand-in for `claude` — exit 0 with stdout.
        pool = self._unsafe(("echo", "fixed"))
        result = pool.dispatch(prompt="x", working_directory=tmp_path)
        assert result.success is True
        assert "fixed" in result.diff

    def test_dispatch_with_failure_exit_code(self, tmp_path: Path) -> None:
        pool = self._unsafe(("false",))
        result = pool.dispatch(prompt="x", working_directory=tmp_path)
        assert result.success is False

    def test_dispatch_handles_command_not_found(self, tmp_path: Path) -> None:
        pool = self._unsafe(("/no/such/command/anywhere",))
        result = pool.dispatch(prompt="x", working_directory=tmp_path)
        assert result.success is False
        assert "not found" in result.message.lower()

    def test_dispatch_handles_timeout(self, tmp_path: Path) -> None:
        # sleep with tiny timeout — TimeoutExpired on the run.
        pool = self._unsafe(("sleep", "5"))
        result = pool.dispatch(
            prompt="x", working_directory=tmp_path, timeout_seconds=1
        )
        assert result.success is False
        assert "timed out" in result.message.lower()

    def test_dispatch_passes_prompt_via_stdin(self, tmp_path: Path) -> None:
        # cat echoes its stdin back to stdout — we can read the prompt.
        pool = self._unsafe(("cat",))
        result = pool.dispatch(prompt="the-magic-prompt", working_directory=tmp_path)
        assert result.success is True
        assert "the-magic-prompt" in result.diff

    def test_constructor_rejects_unknown_executable(self) -> None:
        # The allowlist is the defense-in-depth against footgun.
        with pytest.raises(ValueError, match="must be one of"):
            LocalClaudeSubprocess(command=("/no/such/binary",))

    def test_constructor_rejects_empty_command(self) -> None:
        with pytest.raises(ValueError, match="non-empty command"):
            LocalClaudeSubprocess(command=())

    def test_constructor_accepts_claude_and_qwen(self) -> None:
        # Both allowed executables construct without error.
        LocalClaudeSubprocess(command=("claude", "--print"))
        LocalClaudeSubprocess(command=("qwen",))


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

    def test_skill_replay_when_signature_known_applies_patch(
        self, tmp_path: Path
    ) -> None:
        # Replay path now uses the unidiff-based applier. The agent
        # applies the recorded diff to ``target`` in-place and
        # surfaces a successful skill-replay outcome. Crucially,
        # no dispatch should be triggered — the whole point of the
        # fast path is to avoid paying LLM cost to re-derive a
        # fix we already have.
        diagnostics = self._diagnostics()
        sig = signature_for(diagnostics)
        store = InMemorySkillStore()
        diff = textwrap.dedent(
            """\
            --- a/foo.py
            +++ b/foo.py
            @@ -1 +1 @@
            -old
            +new
            """
        )
        store.record(
            sig,
            Skill(diff=diff, source_path="foo.py", recorded_at="t"),
        )
        pool = _StubPool()
        agent = IterativeFixAgent(pool=pool, skill_store=store)

        target = tmp_path / "foo.py"
        target.write_text("old\n")

        outcome = agent.fix_file(target, diagnostics)
        assert outcome.success is True
        assert outcome.path_was_skill_replay is True
        assert outcome.dispatched_to_pool is False
        # The diff was actually applied to disk.
        assert target.read_text() == "new\n"
        # And no pool call was made.
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

    def test_evidence_threshold_one_records_immediately(self, tmp_path: Path) -> None:
        # Default threshold=1 captures every successful dispatch
        # (back-compat with the original behavior before the gate).
        diagnostics = self._diagnostics()
        store = InMemorySkillStore()
        pool = _StubPool(success=True, diff="the-diff")
        agent = IterativeFixAgent(pool=pool, skill_store=store)

        target = tmp_path / "foo.py"
        target.write_text("")

        outcome = agent.fix_file(target, diagnostics)
        assert outcome.success is True
        assert outcome.dispatched_to_pool is True
        assert outcome.skill_recorded is True
        assert store.find(signature_for(diagnostics)) is not None
        # Counter is tracked but the threshold is already met.
        assert agent._success_counts[signature_for(diagnostics)] == 1

    def test_evidence_threshold_three_requires_three_successes(
        self, tmp_path: Path
    ) -> None:
        # threshold=3 means we only record the skill on the third
        # successful dispatch of the same signature. The first two
        # dispatch + accumulate counters but skip the record call.
        diagnostics = self._diagnostics()
        sig = signature_for(diagnostics)
        store = InMemorySkillStore()
        pool = _StubPool(success=True, diff="diff")
        agent = IterativeFixAgent(pool=pool, skill_store=store, evidence_threshold=3)

        target = tmp_path / "foo.py"
        target.write_text("")

        # First call: dispatches, success but NOT recorded (count=1, threshold=3).
        first = agent.fix_file(target, diagnostics)
        assert first.success is True
        assert first.dispatched_to_pool is True
        assert first.skill_recorded is False
        assert store.find(sig) is None

        # Second call: still under threshold.
        second = agent.fix_file(target, diagnostics)
        assert second.success is True
        assert second.dispatched_to_pool is True
        assert second.skill_recorded is False
        assert store.find(sig) is None

        # Third call: threshold met, recorded.
        third = agent.fix_file(target, diagnostics)
        assert third.success is True
        assert third.dispatched_to_pool is True
        assert third.skill_recorded is True
        assert store.find(sig) is not None
        # Counter reflects all three successes.
        assert agent._success_counts[sig] == 3

    def test_evidence_threshold_per_signature_independent(self, tmp_path: Path) -> None:
        # Counters are per-signature: signature A accumulating toward
        # the threshold must not bleed into signature B's count.
        diag_a = [
            TyDiagnostic(
                file=Path("foo.py"),
                line=10,
                col=4,
                code="unsupported-attribute",
                message="Attribute `lower` is not defined on `None`",
            )
        ]
        diag_b = [
            TyDiagnostic(
                file=Path("foo.py"),
                line=10,
                col=4,
                code="not-subscriptable",
                message="Cannot subscript object of type `None`",
            )
        ]
        sig_a = signature_for(diag_a)
        sig_b = signature_for(diag_b)
        assert sig_a != sig_b  # sanity check

        store = InMemorySkillStore()
        pool = _StubPool(success=True, diff="diff")
        agent = IterativeFixAgent(pool=pool, skill_store=store, evidence_threshold=3)

        target = tmp_path / "foo.py"
        target.write_text("")

        # Two successes each, neither recorded yet (each is < 3).
        for _ in range(2):
            assert agent.fix_file(target, diag_a).skill_recorded is False
        for _ in range(2):
            assert agent.fix_file(target, diag_b).skill_recorded is False

        # B is still at 2 — verify the counter explicitly.
        assert agent._success_counts[sig_a] == 2
        assert agent._success_counts[sig_b] == 2
        assert store.find(sig_a) is None
        assert store.find(sig_b) is None

        # One more success for A: A records, B still doesn't.
        outcome_a = agent.fix_file(target, diag_a)
        assert outcome_a.skill_recorded is True
        assert store.find(sig_a) is not None
        assert store.find(sig_b) is None
        assert agent._success_counts[sig_a] == 3
        assert agent._success_counts[sig_b] == 2  # B unchanged

    def test_dispatched_to_pool_set_even_when_evidence_threshold_not_met(
        self, tmp_path: Path
    ) -> None:
        # When dispatch succeeds but threshold not met, we DID
        # dispatch (so dispatched_to_pool=True) but DID NOT record
        # (skill_recorded=False). The two states must remain
        # independent — the operator needs to see "we tried, but
        # we're waiting for more evidence before caching".
        diagnostics = self._diagnostics()
        store = InMemorySkillStore()
        pool = _StubPool(success=True, diff="diff")
        agent = IterativeFixAgent(pool=pool, skill_store=store, evidence_threshold=5)

        target = tmp_path / "foo.py"
        target.write_text("")

        outcome = agent.fix_file(target, diagnostics)
        assert outcome.success is True
        assert outcome.dispatched_to_pool is True
        assert outcome.skill_recorded is False
        # Pool was actually called once.
        assert len(pool.calls) == 1
        # And nothing was stored yet.
        assert store.find(signature_for(diagnostics)) is None


# ---------------------------------------------------------------------------
# _replay_skill (the unidiff applier)
# ---------------------------------------------------------------------------


class TestReplaySkill:
    """Direct unit tests for ``IterativeFixAgent._replay_skill``.

    Bypasses the ``fix_file`` dispatch flow so we can pin the
    applier's behavior in isolation: parse, validate, apply, or
    cleanly refuse without writing partial state.
    """

    def _agent(self) -> IterativeFixAgent:
        return IterativeFixAgent(pool=_StubPool(), skill_store=InMemorySkillStore())

    def test_replay_applies_simple_diff(self, tmp_path: Path) -> None:
        # Happy path: the diff context matches the file content,
        # and after replay the file reflects the patched content.
        target = tmp_path / "foo.py"
        target.write_text("old\n")
        diff = textwrap.dedent(
            """\
            --- a/foo.py
            +++ b/foo.py
            @@ -1 +1 @@
            -old
            +new
            """
        )
        skill = Skill(diff=diff, source_path="foo.py", recorded_at="t")

        assert self._agent()._replay_skill(target, skill) is True
        assert target.read_text() == "new\n"

    def test_replay_applies_multi_line_diff_with_context(self, tmp_path: Path) -> None:
        # Multi-line context with both context lines and changes.
        # The applier must preserve the unchanged context lines
        # around the modified region.
        target = tmp_path / "foo.py"
        target.write_text("a\nkeep1\nold\nkeep2\nz\n")
        diff = textwrap.dedent(
            """\
            --- a/foo.py
            +++ b/foo.py
            @@ -2,3 +2,3 @@
             keep1
            -old
            +new
             keep2
            """
        )
        skill = Skill(diff=diff, source_path="foo.py", recorded_at="t")

        assert self._agent()._replay_skill(target, skill) is True
        assert target.read_text() == "a\nkeep1\nnew\nkeep2\nz\n"

    def test_replay_returns_false_on_mismatched_context(self, tmp_path: Path) -> None:
        # The diff's source context doesn't match the file. The
        # applier must refuse (False) and leave the file untouched.
        target = tmp_path / "foo.py"
        original = "completely-different-content\n"
        target.write_text(original)
        diff = textwrap.dedent(
            """\
            --- a/foo.py
            +++ b/foo.py
            @@ -1 +1 @@
            -old
            +new
            """
        )
        skill = Skill(diff=diff, source_path="foo.py", recorded_at="t")

        assert self._agent()._replay_skill(target, skill) is False
        assert target.read_text() == original

    def test_replay_returns_false_on_malformed_diff(self, tmp_path: Path) -> None:
        # Garbage text in ``skill.diff`` should not raise — the
        # applier swallows parse failures and returns False.
        target = tmp_path / "foo.py"
        original = "untouched\n"
        target.write_text(original)

        for garbage in (
            "this is not a diff at all",
            "@@ -1 +1 @@\n",  # hunk without file header
            "--- a\n",  # incomplete header
        ):
            skill = Skill(diff=garbage, source_path="foo.py", recorded_at="t")
            assert self._agent()._replay_skill(target, skill) is False, (
                f"garbage {garbage!r} should not be replayable"
            )
            assert target.read_text() == original

    def test_replay_returns_false_for_different_file_path(self, tmp_path: Path) -> None:
        # The patch targets ``a.py`` but we replay on ``b.py``.
        # The applier must refuse — even if the content WOULD
        # match, the diff's file header is the contract.
        target = tmp_path / "b.py"
        original = "old\n"
        target.write_text(original)
        diff = textwrap.dedent(
            """\
            --- a/a.py
            +++ b/a.py
            @@ -1 +1 @@
            -old
            +new
            """
        )
        skill = Skill(diff=diff, source_path="a.py", recorded_at="t")

        assert self._agent()._replay_skill(target, skill) is False
        assert target.read_text() == original

    def test_replay_does_not_partial_apply(self, tmp_path: Path) -> None:
        # The diff has two hunks: the first applies cleanly, the
        # second's context doesn't match. The applier must refuse
        # the whole replay and leave the file untouched — no
        # half-applied state.
        target = tmp_path / "foo.py"
        original = "line1\nline2\n"
        target.write_text(original)
        diff = textwrap.dedent(
            """\
            --- a/foo.py
            +++ b/foo.py
            @@ -1 +1 @@
            -line1
            +LINE1
            @@ -2 +2 @@
            -WRONG-CONTEXT
            +line2
            """
        )
        skill = Skill(diff=diff, source_path="foo.py", recorded_at="t")

        assert self._agent()._replay_skill(target, skill) is False
        # No partial write: line1 still has its original value.
        assert target.read_text() == original

    def test_replay_returns_false_when_file_missing(self, tmp_path: Path) -> None:
        # If the target file doesn't exist on disk, replay is a
        # no-op (no auto-creation from a diff that has no
        # @@ -0,0 +1,N @@ insertion hunk).
        target = tmp_path / "missing.py"
        diff = textwrap.dedent(
            """\
            --- a/missing.py
            +++ b/missing.py
            @@ -1 +1 @@
            -old
            +new
            """
        )
        skill = Skill(diff=diff, source_path="missing.py", recorded_at="t")

        assert self._agent()._replay_skill(target, skill) is False
        assert not target.exists()

    def test_replay_rejects_cross_collision_via_basename(self, tmp_path: Path) -> None:
        # A patch for ``a/foo.py`` must NOT apply to ``b/foo.py``
        # even though both share the basename ``foo.py``. This was
        # the security review finding: basename-only matching would
        # let a patch leak from one directory to another.
        sub_a = tmp_path / "a"
        sub_b = tmp_path / "b"
        sub_a.mkdir()
        sub_b.mkdir()
        target_b = sub_b / "foo.py"
        target_b.write_text("shared content\n")

        diff = textwrap.dedent(
            """\
            --- a/a/foo.py
            +++ b/a/foo.py
            @@ -1 +1 @@
            -shared content
            +attacker content
            """
        )
        skill = Skill(diff=diff, source_path="a/foo.py", recorded_at="t")

        assert self._agent()._replay_skill(target_b, skill) is False
        # File must be unchanged.
        assert target_b.read_text() == "shared content\n"

    def test_replay_rejects_oversized_diff(self, tmp_path: Path) -> None:
        # Defensive size cap — an adversarial or corrupted skill must
        # not be allowed to OOM the parser.
        target = tmp_path / "foo.py"
        target.write_text("x = 1\n")
        # Diff larger than the 1 MiB cap; body just overflows.
        huge_diff = (
            "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-x\n+"
            + ("a" * (2 * 1024 * 1024))
            + "\n"
        )
        skill = Skill(diff=huge_diff, source_path="x.py", recorded_at="t")

        assert self._agent()._replay_skill(target, skill) is False
        # File must be unchanged.
        assert target.read_text() == "x = 1\n"


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
