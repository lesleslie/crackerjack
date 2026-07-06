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

from crackerjack.agents.iterative_fix_agent import (
    DispatchResult,
    InMemorySkillStore,
    IterativeFixAgent,
    LocalClaudeSubprocess,
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
