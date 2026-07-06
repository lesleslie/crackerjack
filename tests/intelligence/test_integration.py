"""Tests for IntelligentAgentSystem truthful-fix-reporting (Bug 3c).

Bug 3c: ``IntelligentAgentSystem.handle_crackerjack_issue`` synthesizes
a ``FixResult`` when ``smart_result.success=True`` but
``smart_result.result`` is not a ``FixResult`` instance. The previous
implementation mirrored ``smart_result.success=True`` into the
synthesized FixResult and fabricated a ``fixes_applied`` string,
claiming work was applied when nothing was written. This is a
"ghost fix" — the caller sees a fix as applied.

Currently this code is unreachable from production (no caller
invokes ``handle_crackerjack_issue``), but the principle still
applies and the new test catches future callers.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.agents.base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    Priority,
)
from crackerjack.intelligence.integration import (
    IntelligentAgentSystem,
    SmartAgentResult,
)


def _make_issue(tmp_path: Path) -> Issue:
    return Issue(
        type=IssueType.FORMATTING,
        severity=Priority.MEDIUM,
        message="missing whitespace",
        file_path=str(tmp_path / "module.py"),
    )


def _smart_result_no_fixresult_payload() -> SmartAgentResult:
    """Smart result that succeeded but whose ``result`` is NOT a
    FixResult — this is the synthesised-branch trigger.
    """
    return SmartAgentResult(
        success=True,
        result=None,
        agents_used=["formatter"],
        execution_time=0.1,
        confidence=0.7,
        recommendations=["check the file"],
    )


@pytest.mark.asyncio
class TestHandleCrackerjackIssueTruthfulReporting:
    """Bug 3c — synthesised FixResult must report failure, not lie."""

    async def test_synthesised_branch_returns_failure_when_no_fixresult_payload(
        self, tmp_path: Path
    ) -> None:
        """When ``smart_result.success=True`` but ``result`` is not a
        FixResult, the synthesised FixResult must NOT claim success
        and must NOT fabricate a ``fixes_applied`` description.
        """
        system = IntelligentAgentSystem()
        issue = _make_issue(tmp_path)
        context = AgentContext(project_path=tmp_path)
        smart_result = _smart_result_no_fixresult_payload()

        with patch.object(
            system,
            "execute_smart_task",
            new=AsyncMock(return_value=smart_result),
        ):
            with patch.object(
                system, "initialize", new=AsyncMock(return_value=None)
            ):
                with patch.object(
                    system,
                    "_map_issue_to_task_context",
                    return_value=MagicMock(),
                ):
                    with patch.object(
                        system,
                        "_map_severity_to_priority",
                        return_value=MagicMock(),
                    ):
                        result = await system.handle_crackerjack_issue(
                            issue, context
                        )

        assert result.success is False, (
            "synthesised FixResult must report failure when the smart "
            "task succeeded but did not return a FixResult payload — "
            "mirroring smart_result.success=True would be a lie"
        )
        assert result.fixes_applied == [], (
            "synthesised branch must NOT fabricate a fixes_applied "
            "description; no file was written"
        )
        assert result.files_modified == []
        assert "smart task returned success" in (
            result.remaining_issues[0]
            if result.remaining_issues
            else ""
        )

    async def test_recommendations_still_preserved_when_synthesised(
        self, tmp_path: Path
    ) -> None:
        """The synthesised branch must still surface
        ``smart_result.recommendations`` to the user — the fix removes
        the ghost-success lie but preserves the useful guidance.
        """
        system = IntelligentAgentSystem()
        issue = _make_issue(tmp_path)
        context = AgentContext(project_path=tmp_path)
        smart_result = SmartAgentResult(
            success=True,
            result=None,
            agents_used=["formatter"],
            execution_time=0.1,
            confidence=0.7,
            recommendations=["use black", "add trailing newline"],
        )

        with patch.object(
            system,
            "execute_smart_task",
            new=AsyncMock(return_value=smart_result),
        ):
            with patch.object(
                system, "initialize", new=AsyncMock(return_value=None)
            ):
                with patch.object(
                    system,
                    "_map_issue_to_task_context",
                    return_value=MagicMock(),
                ):
                    with patch.object(
                        system,
                        "_map_severity_to_priority",
                        return_value=MagicMock(),
                    ):
                        result = await system.handle_crackerjack_issue(
                            issue, context
                        )

        assert result.success is False
        assert result.recommendations == [
            "use black",
            "add trailing newline",
        ], (
            "recommendations from the smart task must still be "
            "propagated to the user even when success is False"
        )
