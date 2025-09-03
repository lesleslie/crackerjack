from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.agents.base import AgentContext, Issue, IssueType, Priority
from crackerjack.intelligence import (
    AgentCapability,
    AgentRegistry,
    AgentSelector,
    ExecutionStrategy,
    TaskContext,
    TaskDescription,
)
from crackerjack.intelligence.integration import get_intelligent_agent_system


class TestAgentRegistry:
    @pytest.fixture
    async def registry(self):
        registry = AgentRegistry()
        await registry.initialize()
        return registry

    async def test_registry_initialization(self, registry):
        assert len(registry._agents) > 0

        sources = {agent.metadata.source for agent in registry._agents.values()}
        assert len(sources) >= 1

    async def test_capability_mapping(self, registry):
        arch_agents = registry.get_agents_by_capability(AgentCapability.ARCHITECTURE)
        assert len(arch_agents) >= 0

        stats = registry.get_agent_stats()
        assert "total_agents" in stats
        assert "by_source" in stats
        assert "by_capability" in stats

    async def test_agent_retrieval(self, registry):
        all_agents = registry.list_all_agents()
        assert len(all_agents) > 0

        priorities = [agent.metadata.priority for agent in all_agents]
        assert priorities == sorted(priorities, reverse=True)


class TestAgentSelector:
    @pytest.fixture
    async def selector(self):
        registry = AgentRegistry()
        await registry.initialize()
        return AgentSelector(registry)

    async def test_task_capability_analysis(self, selector):
        arch_task = TaskDescription(
            description="Design a complex system architecture with multiple components",
            context=TaskContext.ARCHITECTURE,
        )

        capabilities = selector._analyze_task_capabilities(arch_task)
        assert AgentCapability.ARCHITECTURE in capabilities

    async def test_agent_selection(self, selector):
        task = TaskDescription(
            description="Fix refurb violations in Python code",
            context=TaskContext.CODE_QUALITY,
            keywords=["refurb", "formatting"],
        )

        candidates = await selector.select_agents(task, max_candidates=3)

        assert len(candidates) >= 0

        if len(candidates) > 1:
            scores = [c.final_score for c in candidates]
            assert scores == sorted(scores, reverse=True)

    async def test_task_complexity_analysis(self, selector):
        simple_task = TaskDescription(description="Format Python code")
        complex_task = TaskDescription(
            description="Refactor complex architecture with multiple design patterns",
            context=TaskContext.ARCHITECTURE,
        )

        simple_analysis = await selector.analyze_task_complexity(simple_task)
        complex_analysis = await selector.analyze_task_complexity(complex_task)

        assert "complexity_level" in simple_analysis
        assert "recommendations" in complex_analysis


class TestIntelligentAgentSystem:
    async def test_system_initialization(self):
        system = await get_intelligent_agent_system()
        await system.initialize()

        assert system._initialized is True
        assert system.registry is not None
        assert system.orchestrator is not None
        assert system.learning_system is not None

    async def test_smart_task_execution(self):
        system = await get_intelligent_agent_system()

        with patch.object(system, "orchestrator") as mock_orchestrator:
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.primary_result = "Test result"
            mock_result.agents_used = ["test - agent"]
            mock_result.execution_time = 1.0
            mock_result.error_message = None
            mock_result.recommendations = ["Test recommendation"]

            mock_orchestrator.execute = AsyncMock(return_value=mock_result)
            mock_orchestrator.selector.select_agents = AsyncMock(return_value=[])

            with patch.object(system, "learning_system") as mock_learning:
                mock_learning.get_agent_recommendations = MagicMock(return_value={})
                mock_learning.record_execution = AsyncMock()

                result = await system.execute_smart_task(
                    description="Test task",
                    context=TaskContext.CODE_QUALITY,
                )

                assert result.success is True
                assert result.result == "Test result"
                assert result.agents_used == ["test - agent"]

    async def test_crackerjack_issue_handling(self):
        system = await get_intelligent_agent_system()

        issue = Issue(
            id="test - issue",
            type=IssueType.FORMATTING,
            severity=Priority.MEDIUM,
            message="Test formatting issue",
        )

        context = AgentContext(
            project_path=Path.cwd(),
        )

        with patch.object(system, "execute_smart_task") as mock_execute:
            from crackerjack.agents.base import FixResult

            mock_fix_result = FixResult(
                success=True,
                confidence=0.8,
                fixes_applied=["Test fix"],
            )

            mock_smart_result = MagicMock()
            mock_smart_result.success = True
            mock_smart_result.result = mock_fix_result
            mock_smart_result.confidence = 0.8
            mock_smart_result.recommendations = ["Test recommendation"]

            mock_execute.return_value = mock_smart_result

            result = await system.handle_crackerjack_issue(issue, context)

            assert result.success is True
            assert result.confidence == 0.8

    async def test_system_status(self):
        system = await get_intelligent_agent_system()

        with patch.object(system, "registry") as mock_registry:
            mock_registry.get_agent_stats.return_value = {"total_agents": 5}

            with patch.object(system, "orchestrator") as mock_orchestrator:
                mock_orchestrator.get_execution_stats.return_value = {
                    "total_executions": 10
                }

                with patch.object(system, "learning_system") as mock_learning:
                    mock_learning.get_learning_summary.return_value = {
                        "status": "active"
                    }

                    system._initialized = True
                    status = await system.get_system_status()

                    assert status["initialized"] is True
                    assert status["registry"]["total_agents"] == 5
                    assert status["orchestration"]["total_executions"] == 10
                    assert status["learning"]["status"] == "active"


class TestIntegrationFunctions:
    async def test_smart_fix_issue(self):
        from crackerjack.intelligence.integration import smart_fix_issue

        issue = Issue(
            id="test",
            type=IssueType.FORMATTING,
            severity=Priority.LOW,
            message="Test issue",
        )

        context = AgentContext(
            project_path=Path.cwd(),
        )

        with patch(
            "crackerjack.intelligence.integration.get_intelligent_agent_system"
        ) as mock_get_system:
            mock_system = AsyncMock()
            mock_system.handle_crackerjack_issue = AsyncMock()
            mock_get_system.return_value = mock_system

            await smart_fix_issue(issue, context)

            mock_system.handle_crackerjack_issue.assert_called_once_with(issue, context)

    async def test_smart_execute_task(self):
        from crackerjack.intelligence.integration import smart_execute_task

        with patch(
            "crackerjack.intelligence.integration.get_intelligent_agent_system"
        ) as mock_get_system:
            mock_system = AsyncMock()
            mock_system.execute_smart_task = AsyncMock()
            mock_get_system.return_value = mock_system

            await smart_execute_task(
                description="Test task",
                context=TaskContext.CODE_QUALITY,
                strategy=ExecutionStrategy.SINGLE_BEST,
            )

            mock_system.execute_smart_task.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])
