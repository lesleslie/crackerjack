"""Tests for :class:`PromotionPipeline` (PR 8 of 2026-07-07 ai-fix design).

The pipeline is the self-improving loop's heart: it turns a cached
skill into a mechanical fixer. The tests cover every gate, with
mocks for the LLM codegen, sandbox runner, and PR creator so the
suite is hermetic.

The most important invariant: with ``promotion_enabled=False``
(the default), the pipeline is a *pure no-op*. No LLM call, no
subprocess, no PR. Every short-circuit gate returns
``promoted=False`` with a ``reason`` naming the gate that fired.

With ``promotion_enabled=True``, the four gates fire in order:
``skill_not_found`` / ``insufficient_evidence`` → ``llm_error`` →
``sandbox_failed`` → ``pr_creation_failed`` → ``success``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from crackerjack.ai_fix.llm_codegen import StubLLMCodegen
from crackerjack.ai_fix.promotion_pipeline import (
    DEFAULT_EVIDENCE_THRESHOLD,
    PromotionPipeline,
    PromotionResult,
    SandboxResult,
    SkillSnapshot,
)


# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


@dataclass
class _StubSandbox:
    """A controllable sandbox for tests.

    Tests set ``passed`` to the desired outcome. ``run_tests``
    records the inputs it received so tests can assert on them.
    """

    passed: bool = True
    stdout: str = "SANDBOX_OK"
    stderr: str = ""
    call_count: int = 0
    last_fixer_source: str | None = None
    last_signature: str | None = None
    last_project_root: Path | None = None

    def run_tests(
        self,
        *,
        fixer_source: str,
        signature: str,
        project_root: Path,
    ) -> SandboxResult:
        self.call_count += 1
        self.last_fixer_source = fixer_source
        self.last_signature = signature
        self.last_project_root = project_root
        return SandboxResult(
            passed=self.passed,
            stdout=self.stdout,
            stderr=self.stderr,
        )


@dataclass
class _StubPRCreator:
    """A controllable PR creator for tests.

    ``should_raise`` controls whether ``create_pr`` raises; tests
    for the pr_creation_failed gate set it to True.
    """

    url: str = "https://github.com/example/repo/pull/42"
    should_raise: bool = False
    call_count: int = 0
    last_fixer_source: str | None = None
    last_signature: str | None = None
    last_skill_diff: str | None = None

    def create_pr(
        self,
        *,
        fixer_source: str,
        signature: str,
        skill_diff: str,
    ) -> str:
        self.call_count += 1
        self.last_fixer_source = fixer_source
        self.last_signature = signature
        self.last_skill_diff = skill_diff
        if self.should_raise:
            raise RuntimeError("gh failed: rate limit")
        return self.url


@dataclass
class _SkillTable:
    """A minimal stand-in for :class:`SkillStore` that returns a fixed snapshot."""

    snapshots: dict[str, SkillSnapshot] = field(default_factory=dict)
    read_count: int = 0

    def __call__(self, signature: str) -> SkillSnapshot | None:
        self.read_count += 1
        return self.snapshots.get(signature)


def _snapshot(
    signature: str = "abc123",
    diff: str = "@@ -1 +1 @@\n-x\n+y\n",
    original_error: str = "TypeError: foo",
    recorded_count: int = 5,
) -> SkillSnapshot:
    return SkillSnapshot(
        signature=signature,
        diff=diff,
        original_error=original_error,
        recorded_count=recorded_count,
    )


@pytest.fixture
def pipeline_kwargs(tmp_path: Path) -> dict[str, Any]:
    """Default kwargs for a promotion-enabled pipeline with a populated skill table."""
    skills = _SkillTable(
        snapshots={"abc123": _snapshot()},
    )
    sandbox = _StubSandbox()
    pr_creator = _StubPRCreator()
    llm = StubLLMCodegen(canned_response="# generated fixer\n")
    return {
        "skill_reader": skills,
        "llm_codegen": llm,
        "sandbox_runner": sandbox,
        "pr_creator": pr_creator,
        "promotion_enabled": True,
        "evidence_threshold": 3,
        "project_root": tmp_path,
    }


# ---------------------------------------------------------------------------
# 1. The flag gate (most important)
# ---------------------------------------------------------------------------


class TestPromotionDisabled:
    """With ``promotion_enabled=False`` the pipeline is a pure no-op."""

    @pytest.mark.asyncio
    async def test_disabled_returns_no_op_no_llm_call(self, tmp_path: Path) -> None:
        skills = _SkillTable(snapshots={"abc123": _snapshot()})
        sandbox = _StubSandbox()
        pr_creator = _StubPRCreator()
        llm = StubLLMCodegen()

        pipeline = PromotionPipeline(
            skill_reader=skills,
            llm_codegen=llm,
            sandbox_runner=sandbox,
            pr_creator=pr_creator,
            promotion_enabled=False,
            project_root=tmp_path,
        )
        result = await pipeline.maybe_promote("abc123")

        assert result.promoted is False
        assert result.reason == "promotion_disabled"
        assert result.pr_url is None
        # And critically: no collaborators were invoked.
        assert llm.call_count == 0
        assert sandbox.call_count == 0
        assert pr_creator.call_count == 0
        assert skills.read_count == 0

    @pytest.mark.asyncio
    async def test_disabled_default(self, tmp_path: Path) -> None:
        """The default constructor value is False (defense in depth)."""
        pipeline = PromotionPipeline(
            skill_reader=_SkillTable(),
            llm_codegen=StubLLMCodegen(),
            sandbox_runner=_StubSandbox(),
            pr_creator=_StubPRCreator(),
            project_root=tmp_path,
        )
        assert pipeline.promotion_enabled is False


# ---------------------------------------------------------------------------
# 2. The evidence gate
# ---------------------------------------------------------------------------


class TestEvidenceGate:
    """Skill must exist with enough replayed count."""

    @pytest.mark.asyncio
    async def test_skill_not_found(self, pipeline_kwargs: dict[str, Any]) -> None:
        pipeline = PromotionPipeline(**pipeline_kwargs)
        result = await pipeline.maybe_promote("nonexistent_signature")
        assert result.promoted is False
        assert result.reason == "skill_not_found"
        assert pipeline_kwargs["llm_codegen"].call_count == 0
        assert pipeline_kwargs["sandbox_runner"].call_count == 0

    @pytest.mark.asyncio
    async def test_insufficient_evidence(self, pipeline_kwargs: dict[str, Any]) -> None:
        pipeline_kwargs["skill_reader"].snapshots["abc123"] = _snapshot(recorded_count=1)
        pipeline = PromotionPipeline(**pipeline_kwargs)
        result = await pipeline.maybe_promote("abc123")
        assert result.promoted is False
        assert result.reason == "insufficient_evidence"
        assert pipeline_kwargs["llm_codegen"].call_count == 0

    @pytest.mark.asyncio
    async def test_evidence_threshold_exact(
        self, pipeline_kwargs: dict[str, Any]
    ) -> None:
        """recorded_count == threshold passes (boundary check)."""
        pipeline_kwargs["skill_reader"].snapshots["abc123"] = _snapshot(
            recorded_count=pipeline_kwargs["evidence_threshold"]
        )
        pipeline = PromotionPipeline(**pipeline_kwargs)
        result = await pipeline.maybe_promote("abc123")
        # Should pass the evidence gate and reach the LLM call.
        assert pipeline_kwargs["llm_codegen"].call_count == 1
        assert result.promoted is True

    @pytest.mark.asyncio
    async def test_custom_evidence_threshold(
        self, pipeline_kwargs: dict[str, Any]
    ) -> None:
        """A higher threshold blocks the promotion."""
        pipeline_kwargs["evidence_threshold"] = 10
        pipeline_kwargs["skill_reader"].snapshots["abc123"] = _snapshot(recorded_count=5)
        pipeline = PromotionPipeline(**pipeline_kwargs)
        result = await pipeline.maybe_promote("abc123")
        assert result.promoted is False
        assert result.reason == "insufficient_evidence"


# ---------------------------------------------------------------------------
# 3. The LLM gate
# ---------------------------------------------------------------------------


class TestLLMGate:
    """LLM codegen must produce non-empty output; exceptions are caught."""

    @pytest.mark.asyncio
    async def test_llm_exception_caught(self, pipeline_kwargs: dict[str, Any]) -> None:
        class _BoomLLM:
            async def generate_fixer(
                self,
                *,
                signature: str,
                original_error: str,
                skill_diff: str,
            ) -> str:
                raise RuntimeError("claude --print failed: timeout")

        pipeline_kwargs["llm_codegen"] = _BoomLLM()
        pipeline = PromotionPipeline(**pipeline_kwargs)
        result = await pipeline.maybe_promote("abc123")
        assert result.promoted is False
        assert result.reason.startswith("llm_error:")
        assert "RuntimeError" in result.reason
        assert pipeline_kwargs["sandbox_runner"].call_count == 0

    @pytest.mark.asyncio
    async def test_llm_empty_rejected(self, pipeline_kwargs: dict[str, Any]) -> None:
        pipeline_kwargs["llm_codegen"] = StubLLMCodegen(canned_response="")
        pipeline = PromotionPipeline(**pipeline_kwargs)
        result = await pipeline.maybe_promote("abc123")
        assert result.promoted is False
        assert result.reason == "llm_returned_empty"
        assert pipeline_kwargs["sandbox_runner"].call_count == 0


# ---------------------------------------------------------------------------
# 4. The sandbox gate
# ---------------------------------------------------------------------------


class TestSandboxGate:
    """Sandbox must pass; failures short-circuit before the PR is created."""

    @pytest.mark.asyncio
    async def test_sandbox_failure(self, pipeline_kwargs: dict[str, Any]) -> None:
        pipeline_kwargs["sandbox_runner"] = _StubSandbox(
            passed=False, stderr="import error: missing apply()"
        )
        pipeline = PromotionPipeline(**pipeline_kwargs)
        result = await pipeline.maybe_promote("abc123")
        assert result.promoted is False
        assert result.reason == "sandbox_failed"
        assert pipeline_kwargs["pr_creator"].call_count == 0


# ---------------------------------------------------------------------------
# 5. The PR-creation gate
# ---------------------------------------------------------------------------


class TestPRCreationGate:
    """PR creation failures are caught and reported; the generated fixer is left for pickup."""

    @pytest.mark.asyncio
    async def test_pr_creation_failure(self, pipeline_kwargs: dict[str, Any]) -> None:
        pipeline_kwargs["pr_creator"] = _StubPRCreator(should_raise=True)
        pipeline = PromotionPipeline(**pipeline_kwargs)
        result = await pipeline.maybe_promote("abc123")
        assert result.promoted is False
        assert result.reason.startswith("pr_creation_failed:")
        assert "RuntimeError" in result.reason


# ---------------------------------------------------------------------------
# 6. The happy path
# ---------------------------------------------------------------------------


class TestHappyPath:
    """End-to-end success: skill is promoted, PR is created, URL is returned."""

    @pytest.mark.asyncio
    async def test_success(self, pipeline_kwargs: dict[str, Any]) -> None:
        pipeline = PromotionPipeline(**pipeline_kwargs)
        result = await pipeline.maybe_promote("abc123")

        assert result.promoted is True
        assert result.reason == "success"
        assert result.pr_url == "https://github.com/example/repo/pull/42"
        assert result.duration_s >= 0.0

        # The LLM got the snapshot data.
        llm: StubLLMCodegen = pipeline_kwargs["llm_codegen"]
        assert llm.last_signature == "abc123"
        assert llm.last_original_error == "TypeError: foo"
        assert llm.last_skill_diff.startswith("@@ -1 +1 @@")

        # The sandbox got the LLM's canned source.
        sandbox: _StubSandbox = pipeline_kwargs["sandbox_runner"]
        assert sandbox.call_count == 1
        assert sandbox.last_fixer_source == "# generated fixer\n"
        assert sandbox.last_signature == "abc123"
        assert sandbox.last_project_root == pipeline_kwargs["project_root"]

        # The PR creator got the same data.
        pr: _StubPRCreator = pipeline_kwargs["pr_creator"]
        assert pr.call_count == 1
        assert pr.last_signature == "abc123"
        assert pr.last_skill_diff.startswith("@@ -1 +1 @@")


# ---------------------------------------------------------------------------
# 7. Default threshold contract
# ---------------------------------------------------------------------------


class TestDefaultThreshold:
    """The :data:`DEFAULT_EVIDENCE_THRESHOLD` constant is 3 (the design default)."""

    def test_default_value(self) -> None:
        assert DEFAULT_EVIDENCE_THRESHOLD == 3


# ---------------------------------------------------------------------------
# 8. Pure-function invariance for the disabled path
# ---------------------------------------------------------------------------


class TestDisabledInvariance:
    """Two calls with the same input and ``promotion_enabled=False`` return the same result."""

    @pytest.mark.asyncio
    async def test_two_identical_calls(self, tmp_path: Path) -> None:
        pipeline = PromotionPipeline(
            skill_reader=_SkillTable(),
            llm_codegen=StubLLMCodegen(),
            sandbox_runner=_StubSandbox(),
            pr_creator=_StubPRCreator(),
            promotion_enabled=False,
            project_root=tmp_path,
        )
        r1 = await pipeline.maybe_promote("sig")
        r2 = await pipeline.maybe_promote("sig")
        assert r1 == r2
        assert r1.promoted is False
        assert r1.reason == r2.reason == "promotion_disabled"
