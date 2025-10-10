from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import pytest

from rich.console import Console

from crackerjack.agents.base import (
    AgentContext,
    FixResult,
    Issue,
    IssueType,
    Priority,
    SubAgent,
)
from crackerjack.agents.error_middleware import agent_error_boundary


class _FailingAgent(SubAgent):
    async def can_handle(self, issue: Issue) -> float:
        return 1.0

    async def analyze_and_fix(self, issue: Issue) -> FixResult:
        raise ValueError("simulated failure")

    def get_supported_types(self) -> set[IssueType]:
        return {IssueType.FORMATTING}


@pytest.mark.asyncio
async def test_agent_error_boundary_returns_fallback(caplog: pytest.LogCaptureFixture) -> None:
    class DummyCoordinator:
        def __init__(self) -> None:
            self.logger = logging.getLogger("crackerjack.test.agent_error")
            self.logger.setLevel(logging.ERROR)
            self.context = AgentContext(project_path=Path("."))
            self.context.console = Console()

        @agent_error_boundary
        async def execute(self, agent: SubAgent, issue: Issue) -> FixResult:
            raise ValueError("simulated failure")

    coordinator = DummyCoordinator()

    agent = _FailingAgent(context=AgentContext(project_path=Path(".")))
    issue = Issue(
        id="issue-1",
        type=IssueType.FORMATTING,
        severity=Priority.HIGH,
        message="Format code",
    )

    caplog.set_level(logging.ERROR, logger="crackerjack.test.agent_error")
    result = await coordinator.execute(agent, issue)

    assert result.success is False
    assert result.confidence == 0.0
    assert any("simulated failure" in entry for entry in result.remaining_issues)
    assert "simulated failure" in caplog.text
