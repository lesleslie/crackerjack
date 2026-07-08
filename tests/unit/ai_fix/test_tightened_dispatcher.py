from __future__ import annotations

from pathlib import Path

import pytest

from crackerjack.agents.base import FixResult
from crackerjack.ai_fix.tightened_dispatcher import dispatch_with_bytes_check
from crackerjack.models.fix_plan import FixPlan


class _RecordingFixer:
    """Minimal fixer that records calls and returns a preset result."""

    def __init__(self, result: FixResult) -> None:
        self.result = result
        self.calls: list[FixPlan] = []

    async def execute(self, plan: FixPlan) -> FixResult:
        self.calls.append(plan)
        return self.result


def _plan_for(target: Path) -> FixPlan:
    return FixPlan(
        file_path=str(target),
        issue_type="refurb",
        risk_level="low",
        validated_by="test",
        rationale="test plan",
    )


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


async def test_success_and_bytes_differ_returns_result_unchanged(
    tmp_path: Path,
) -> None:
    """When the fixer succeeds AND the file content changed, return result as-is."""
    target = tmp_path / "module.py"
    _write(target, "original = 1\n")
    before = target.read_bytes()

    expected = FixResult(
        success=True, fixes_applied=["applied"], files_modified=[str(target)]
    )

    # Fixer that mutates bytes (so the no-op gate doesn't fire).
    class WritingFixer:
        def __init__(self, result: FixResult) -> None:
            self.result = result
            self.calls: list[FixPlan] = []

        async def execute(self, plan: FixPlan) -> FixResult:
            self.calls.append(plan)
            target.write_text("rewritten = 2\n", encoding="utf-8")
            return self.result

    fixer = WritingFixer(expected)

    result = await dispatch_with_bytes_check(fixer, _plan_for(target), target)

    assert result is expected
    assert fixer.calls and fixer.calls[0].file_path == str(target)
    after = target.read_bytes()
    assert before != after


async def test_success_but_bytes_unchanged_becomes_no_op_failure(
    tmp_path: Path,
) -> None:
    """When fixer reports success but the file is byte-identical, mark as no-op failure."""
    target = tmp_path / "module.py"
    _write(target, "original = 1\n")

    lying_result = FixResult(
        success=True, fixes_applied=["swears it fixed"], files_modified=[str(target)]
    )
    fixer = _RecordingFixer(lying_result)

    result = await dispatch_with_bytes_check(fixer, _plan_for(target), target)

    assert result.success is False
    assert result.remaining_issues == ["no-op fix: file content unchanged"]
    # No spurious confidence either - drop the lie
    assert result.confidence == 0.0


async def test_failure_with_unchanged_bytes_returns_failure_unchanged(
    tmp_path: Path,
) -> None:
    """When the fixer reports failure, always return the failure as-is."""
    target = tmp_path / "module.py"
    _write(target, "original = 1\n")

    failure = FixResult(success=False, remaining_issues=["something bad"])
    fixer = _RecordingFixer(failure)

    result = await dispatch_with_bytes_check(fixer, _plan_for(target), target)

    assert result is failure
    assert result.success is False


async def test_target_does_not_exist_propagates(tmp_path: Path) -> None:
    """Reading bytes from a nonexistent target should raise FileNotFoundError."""
    target = tmp_path / "missing.py"

    fixer = _RecordingFixer(FixResult(success=True))

    with pytest.raises(FileNotFoundError):
        await dispatch_with_bytes_check(fixer, _plan_for(target), target)


async def test_success_with_real_byte_diff_passes_through_unchanged(
    tmp_path: Path,
) -> None:
    """Fixer that actually changes bytes and reports success: result passes through verbatim."""
    target = tmp_path / "module.py"
    _write(target, "x = 1\n")

    expected = FixResult(
        success=True,
        fixes_applied=["renamed x to y"],
        files_modified=[str(target)],
        confidence=0.95,
    )
    fixer = _RecordingFixer(expected)

    async def execute(_plan: FixPlan) -> FixResult:
        target.write_text("y = 1\n", encoding="utf-8")
        return expected

    fixer.execute = execute  # type: ignore[method-assign]

    result = await dispatch_with_bytes_check(fixer, _plan_for(target), target)

    assert result.success is True
    assert result.fixes_applied == ["renamed x to y"]
    assert result.confidence == 0.95


async def test_no_op_failure_preserves_files_modified_metadata(
    tmp_path: Path,
) -> None:
    """The synthesized no-op failure should retain the original files_modified list.

    Other fixers (PR 6) will inspect files_modified to decide what to revert or
    stage downstream — we mustn't lose that signal by overwriting it.
    """
    target = tmp_path / "module.py"
    _write(target, "x = 1\n")

    lying_result = FixResult(
        success=True,
        fixes_applied=["would have fixed"],
        files_modified=[str(target)],
        confidence=0.9,
    )
    fixer = _RecordingFixer(lying_result)

    result = await dispatch_with_bytes_check(fixer, _plan_for(target), target)

    assert result.success is False
    assert result.files_modified == [str(target)]


async def test_accepts_any_object_with_execute(tmp_path: Path) -> None:
    """Dispatcher uses structural typing — duck-typed execute(plan) is enough."""

    class FakeFixer:
        def __init__(self) -> None:
            self.invoked_with: FixPlan | None = None

        async def execute(self, plan: FixPlan) -> FixResult:
            self.invoked_with = plan
            return FixResult(success=True)

    target = tmp_path / "module.py"
    target.write_text("x = 1\n", encoding="utf-8")

    fixer = FakeFixer()
    plan = _plan_for(target)

    # Change bytes so the no-op gate doesn't fire.
    async def execute(plan: FixPlan) -> FixResult:
        target.write_text("y = 2\n", encoding="utf-8")
        fixer.invoked_with = plan
        return FixResult(success=True)

    fixer.execute = execute  # type: ignore[method-assign]

    result = await dispatch_with_bytes_check(fixer, plan, target)

    assert result.success is True
    assert fixer.invoked_with is plan
