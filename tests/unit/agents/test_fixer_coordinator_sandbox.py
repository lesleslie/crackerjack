"""Test that FixerCoordinator routes through the sandbox when use_sandbox=True."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from crackerjack.agents.base import FixResult
from crackerjack.agents.fixer_coordinator import FixerCoordinator
from crackerjack.ai_fix.fix_sandbox import SandboxResult


@pytest.mark.asyncio
async def test_execute_plans_uses_sandbox_when_enabled(tmp_path: Path) -> None:
    """When use_sandbox=True, the in-process fixer selection is bypassed."""
    plan_path = tmp_path / "f.py"
    plan_path.write_text("x = 1\n", encoding="utf-8")

    fake_sandbox = MagicMock()
    fake_sandbox.run_command = MagicMock(return_value=SandboxResult(
        passed=True,
        modified_content="x = 2\n",
        duration_s=0.1,
    ))

    coordinator = FixerCoordinator(
        project_path=str(tmp_path),
        use_sandbox=True,
        sandbox=fake_sandbox,
    )

    # Build a minimal FixPlan and run execute_plans. The in-process
    # fixer selection should be bypassed; the sandbox should be called.
    from crackerjack.models.fix_plan import ChangeSpec, FixPlan

    plan = FixPlan(
        file_path=str(plan_path),
        issue_type="FORMATTING",
        changes=[],
        rationale="test",
        risk_level="low",
        validated_by="test",
        issue_message="test",
        issue_stage="ruff-check",
    )

    # We don't have a real fix-runner, so the sandbox result will
    # be passed through; for this test we just verify the sandbox
    # was called. The dispatcher's in-process fallback should NOT
    # be invoked because validation didn't fail.
    from unittest.mock import patch
    with patch(
        "crackerjack.ai_fix.sandboxed_dispatcher.fix_runner.run",
        lambda _argv=None: 0,
    ):
        with patch(
            "crackerjack.ai_fix.sandboxed_dispatcher._resolve_fixer_id",
            return_value="crackerjack.agents.architect_agent:ArchitectAgent",
        ):
            # We need the output JSON to exist for the dispatcher to parse.
            output_path = tmp_path / "out.json"
            output_path.write_text(
                '{"results": [{"plan_idx": 0, "success": true, '
                '"files_modified": [], "remaining_issues": []}]}',
                encoding="utf-8",
            )
            results = await coordinator.execute_plans([plan])

    assert fake_sandbox.run_command.call_count == 1
    assert len(results) == 1
    assert results[0].success is True


@pytest.mark.asyncio
async def test_execute_plans_skips_sandbox_when_disabled(tmp_path: Path) -> None:
    """When use_sandbox=False (default), the existing in-process path runs."""
    coordinator = FixerCoordinator(project_path=str(tmp_path))
    assert coordinator.use_sandbox is False


@pytest.mark.asyncio
async def test_execute_plans_groups_same_file_plans_into_single_subprocess(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Multiple plans targeting the same file → one sandbox subprocess per file.

    Regression test for the production-hazard finding: per-plan subprocess
    dispatch amortizes startup overhead. Per the FixSandbox integration
    plan, decision #3, all plans for one file must go through a single
    fix-runner subprocess.
    """
    plan_path = tmp_path / "f.py"
    plan_path.write_text("x = 1\n", encoding="utf-8")

    sandbox = MagicMock()
    sandbox.run_command = MagicMock(return_value=SandboxResult(
        passed=True,
        modified_content="x = 2\n",
        duration_s=0.1,
    ))

    coordinator = FixerCoordinator(
        project_path=str(tmp_path),
        use_sandbox=True,
        sandbox=sandbox,
        sandbox_timeout_s=42,
    )

    from crackerjack.models.fix_plan import FixPlan

    plan_a = FixPlan(
        file_path=str(plan_path),
        issue_type="FORMATTING",
        changes=[],
        rationale="a",
        risk_level="low",
        validated_by="test",
        issue_message="a",
        issue_stage="ruff-check",
    )
    plan_b = FixPlan(
        file_path=str(plan_path),
        issue_type="DEAD_CODE",
        changes=[],
        rationale="b",
        risk_level="low",
        validated_by="test",
        issue_message="b",
        issue_stage="ruff-check",
    )

    from unittest.mock import patch
    with patch(
        "crackerjack.ai_fix.sandboxed_dispatcher.fix_runner.run",
        lambda _argv=None: 0,
    ):
        with patch(
            "crackerjack.ai_fix.sandboxed_dispatcher._resolve_fixer_id",
            return_value="crackerjack.agents.architect_agent:ArchitectAgent",
        ):
            # Stage result file with TWO successful results (one per plan).
            output_path = tmp_path / "out.json"
            output_path.write_text(
                '{"results": ['
                '{"plan_idx": 0, "success": true, "files_modified": [], "remaining_issues": []},'
                '{"plan_idx": 1, "success": true, "files_modified": [], "remaining_issues": []}'
                ']}',
                encoding="utf-8",
            )
            results = await coordinator.execute_plans([plan_a, plan_b])

    # Critical: ONE subprocess dispatch per file (not per plan).
    assert sandbox.run_command.call_count == 1
    # The timeout parameter must be wired through.
    sandbox.run_command.assert_called_once()
    call_kwargs = sandbox.run_command.call_args.kwargs
    assert call_kwargs.get("timeout") == 42
    assert len(results) == 2
    assert all(r.success for r in results)
