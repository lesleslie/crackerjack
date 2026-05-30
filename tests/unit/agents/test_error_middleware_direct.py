from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from dataclasses import dataclass, field
from pathlib import Path
from unittest.mock import MagicMock


@dataclass
class _FixResult:
    success: bool
    confidence: float = 0.0
    fixes_applied: list[str] = field(default_factory=list)
    remaining_issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)


@dataclass
class _Issue:
    id: str
    message: str = "issue"


@dataclass
class _SubAgent:
    name: str = "agent"


def _load_error_middleware_module():
    fake_package = types.ModuleType("fakepkg")
    fake_package.__path__ = []  # type: ignore[attr-defined]
    fake_agents = types.ModuleType("fakepkg.agents")
    fake_agents.__path__ = []  # type: ignore[attr-defined]
    fake_base = types.ModuleType("fakepkg.agents.base")
    fake_base.FixResult = _FixResult
    fake_base.Issue = _Issue
    fake_base.SubAgent = _SubAgent

    sys.modules["fakepkg"] = fake_package
    sys.modules["fakepkg.agents"] = fake_agents
    sys.modules["fakepkg.agents.base"] = fake_base

    module_path = (
        Path(__file__).resolve().parents[3]
        / "crackerjack"
        / "agents"
        / "error_middleware.py"
    )
    spec = importlib.util.spec_from_file_location(
        "fakepkg.agents.error_middleware",
        module_path,
    )
    assert spec and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["fakepkg.agents.error_middleware"] = module
    spec.loader.exec_module(module)
    return module


def test_agent_error_boundary_success_and_exception_paths() -> None:
    module = _load_error_middleware_module()

    class Context:
        console = None

    coordinator = types.SimpleNamespace(
        context=Context(),
        logger=MagicMock(),
    )
    coordinator.logger.exception = MagicMock()
    agent = _SubAgent(name="TestAgent")
    issue = _Issue(id="issue-1")

    @module.agent_error_boundary
    async def process_issue(self, agent, issue):
        return _FixResult(success=True, confidence=0.7)

    assert asyncio.run(process_issue(coordinator, agent, issue)).success is True

    @module.agent_error_boundary
    async def fail_issue(self, agent, issue):
        raise ValueError("boom")

    result = asyncio.run(fail_issue(coordinator, agent, issue))

    assert result.success is False
    assert result.confidence == 0.0
    assert "TestAgent" in result.remaining_issues[0]
    assert "issue-1" in result.remaining_issues[0]
    assert "boom" in result.remaining_issues[0]
    coordinator.logger.exception.assert_called_once()
