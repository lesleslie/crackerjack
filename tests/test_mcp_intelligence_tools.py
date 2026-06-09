"""Tests for intelligence_tools.py MCP tools.

Covers execute_smart_agent_task, get_smart_agent_recommendation,
get_intelligence_system_status, and analyze_agent_performance.

The intelligence backend is mocked at the get_intelligent_agent_system
boundary to keep these tests fast and hermetic.
"""

from __future__ import annotations

import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from crackerjack.agents.base import FixResult
from crackerjack.intelligence.agent_orchestrator import ExecutionStrategy
from crackerjack.intelligence.agent_selector import TaskContext
from crackerjack.intelligence.integration import SmartAgentResult
from crackerjack.mcp.tools.intelligence_tools import (
    analyze_agent_performance,
    execute_smart_agent_task,
    get_intelligence_system_status,
    get_smart_agent_recommendation,
)


def _build_fix_result() -> FixResult:
    return FixResult(
        success=True,
        confidence=0.9,
        fixes_applied=["reformat import"],
        remaining_issues=[],
        recommendations=["run tests"],
        files_modified=["a.py"],
    )


def _build_smart_result(
    *,
    success: bool = True,
    result: object | None = None,
    fix_result: bool = False,
    agents_used: list[str] | None = None,
    execution_time: float = 1.25,
    confidence: float = 0.85,
    recommendations: list[str] | None = None,
    learning_applied: bool = True,
) -> SmartAgentResult:
    payload: object = _build_fix_result() if fix_result else result
    return SmartAgentResult(
        success=success,
        result=payload,
        agents_used=agents_used or ["refactor-agent"],
        execution_time=execution_time,
        confidence=confidence,
        recommendations=recommendations or ["All good"],
        learning_applied=learning_applied,
    )


def _patched_system(smart_result: SmartAgentResult | None = None) -> MagicMock:
    """Create a mocked IntelligentAgentSystem.

    ``execute_smart_task`` defaults to returning ``smart_result`` when set,
    otherwise an AsyncMock that returns a fresh SmartAgentResult.
    """
    system = MagicMock()
    system._initialized = True
    system.registry = MagicMock()
    system.orchestrator = MagicMock()
    system.learning_system = MagicMock()

    if smart_result is not None:
        system.execute_smart_task = AsyncMock(return_value=smart_result)
    else:
        system.execute_smart_task = AsyncMock(
            return_value=_build_smart_result(),
        )

    system.get_best_agent_for_task = AsyncMock(return_value=("best-agent", 0.92))
    system.analyze_task_complexity = AsyncMock(
        return_value={"complexity": "medium", "score": 0.5},
    )
    system.get_system_status = AsyncMock(
        return_value={
            "initialized": True,
            "registry": {"total_agents": 12, "by_source": "prefect=12"},
            "orchestration": {"total_executions": 7},
            "learning": {"enabled": True},
        },
    )
    system.initialize = AsyncMock()

    system.learning_system.get_learning_summary = MagicMock(
        return_value={"total_records": 3, "average_confidence": 0.8},
    )
    system.orchestrator.get_execution_stats = MagicMock(
        return_value={"total": 7, "successes": 6, "failures": 1},
    )
    system.registry.get_agent_stats = MagicMock(
        return_value={"total_agents": 12, "by_source": "prefect=12"},
    )

    insight = MagicMock()
    insight.insight_type = "performance"
    insight.agent_name = "refactor-agent"
    insight.confidence = 0.7
    insight.description = "Speed improved"
    system.learning_system._learning_insights = [insight]

    return system


@pytest.fixture
def mock_system() -> MagicMock:
    return _patched_system()


@pytest.fixture
def mock_mcp_context() -> MagicMock:
    """Patch get_context so execute_smart_agent_task's precheck doesn't raise."""
    ctx = MagicMock()
    with patch(
        "crackerjack.mcp.tools.intelligence_tools.get_context",
        return_value=ctx,
    ):
        yield ctx


class TestExecuteSmartAgentTask:
    """Tests for execute_smart_agent_task handler."""

    @pytest.mark.asyncio
    async def test_success_with_string_result(
        self,
        mock_system: MagicMock,
        mock_mcp_context: MagicMock,
    ) -> None:
        """Test task execution returns string results unchanged."""
        smart = _build_smart_result(result="plain string output")
        mock_system.execute_smart_task = AsyncMock(return_value=smart)

        with patch(
            "crackerjack.mcp.tools.intelligence_tools.get_intelligent_agent_system",
            AsyncMock(return_value=mock_system),
        ):
            response = await execute_smart_agent_task(
                task_description="Refactor module",
            )

        assert response["success"] is True
        assert response["result"] == "plain string output"
        assert response["task_description"] == "Refactor module"
        assert response["context_type"] == "general"
        assert response["strategy_used"] == "single_best"
        assert response["agents_used"] == ["refactor-agent"]

    @pytest.mark.asyncio
    async def test_success_with_fix_result(
        self,
        mock_system: MagicMock,
        mock_mcp_context: MagicMock,
    ) -> None:
        """Test task execution serializes FixResult into fix_result dict."""
        smart = _build_smart_result(fix_result=True)
        mock_system.execute_smart_task = AsyncMock(return_value=smart)

        with patch(
            "crackerjack.mcp.tools.intelligence_tools.get_intelligent_agent_system",
            AsyncMock(return_value=mock_system),
        ):
            response = await execute_smart_agent_task(
                task_description="Fix formatting",
            )

        assert response["success"] is True
        assert "fix_result" in response
        fix = response["fix_result"]
        assert fix["success"] is True
        assert fix["confidence"] == pytest.approx(0.9)
        assert fix["fixes_applied"] == ["reformat import"]
        assert fix["files_modified"] == ["a.py"]
        assert "result" not in response

    @pytest.mark.asyncio
    async def test_success_with_object_result_no_success_attr(
        self,
        mock_system: MagicMock,
        mock_mcp_context: MagicMock,
    ) -> None:
        """Test result that is an object without success attr falls back to str()."""

        class _Result:
            def __str__(self) -> str:
                return "rendered"

        smart = _build_smart_result(result=_Result())
        mock_system.execute_smart_task = AsyncMock(return_value=smart)

        with patch(
            "crackerjack.mcp.tools.intelligence_tools.get_intelligent_agent_system",
            AsyncMock(return_value=mock_system),
        ):
            response = await execute_smart_agent_task(
                task_description="Handle opaque payload",
            )

        assert response["result"] == "rendered"

    @pytest.mark.asyncio
    async def test_maps_known_context_and_strategy(
        self,
        mock_system: MagicMock,
        mock_mcp_context: MagicMock,
    ) -> None:
        """Test that valid context_type and strategy strings are mapped."""
        smart = _build_smart_result()
        mock_system.execute_smart_task = AsyncMock(return_value=smart)

        with patch(
            "crackerjack.mcp.tools.intelligence_tools.get_intelligent_agent_system",
            AsyncMock(return_value=mock_system),
        ):
            await execute_smart_agent_task(
                task_description="Run suite",
                context_type="testing",
                strategy="parallel",
            )

        call_kwargs = mock_system.execute_smart_task.call_args.kwargs
        assert call_kwargs["context"] is TaskContext.TESTING
        assert call_kwargs["strategy"] is ExecutionStrategy.PARALLEL

    @pytest.mark.asyncio
    async def test_unknown_context_yields_none(
        self,
        mock_system: MagicMock,
        mock_mcp_context: MagicMock,
    ) -> None:
        """Test that an unknown context_type maps to None."""
        smart = _build_smart_result()
        mock_system.execute_smart_task = AsyncMock(return_value=smart)

        with patch(
            "crackerjack.mcp.tools.intelligence_tools.get_intelligent_agent_system",
            AsyncMock(return_value=mock_system),
        ):
            await execute_smart_agent_task(
                task_description="Do thing",
                context_type="not_a_real_context",
            )

        call_kwargs = mock_system.execute_smart_task.call_args.kwargs
        assert call_kwargs["context"] is None

    @pytest.mark.asyncio
    async def test_unknown_strategy_defaults_to_single_best(
        self,
        mock_system: MagicMock,
        mock_mcp_context: MagicMock,
    ) -> None:
        """Test unknown strategy falls back to SINGLE_BEST."""
        smart = _build_smart_result()
        mock_system.execute_smart_task = AsyncMock(return_value=smart)

        with patch(
            "crackerjack.mcp.tools.intelligence_tools.get_intelligent_agent_system",
            AsyncMock(return_value=mock_system),
        ):
            await execute_smart_agent_task(
                task_description="Do thing",
                strategy="not_a_real_strategy",
            )

        call_kwargs = mock_system.execute_smart_task.call_args.kwargs
        assert call_kwargs["strategy"] is ExecutionStrategy.SINGLE_BEST

    @pytest.mark.asyncio
    async def test_failed_result_records_recommendations(
        self,
        mock_system: MagicMock,
        mock_mcp_context: MagicMock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that failure path returns success=False but keeps recommendations."""
        smart = _build_smart_result(
            success=False,
            recommendations=["try a different agent"],
        )
        mock_system.execute_smart_task = AsyncMock(return_value=smart)

        with caplog.at_level(logging.WARNING):
            with patch(
                "crackerjack.mcp.tools.intelligence_tools.get_intelligent_agent_system",
                AsyncMock(return_value=mock_system),
            ):
                response = await execute_smart_agent_task(
                    task_description="Will fail",
                )

        assert response["success"] is False
        assert response["recommendations"] == ["try a different agent"]
        assert any("Smart task failed" in rec.message for rec in caplog.records)

    @pytest.mark.asyncio
    async def test_exception_falls_back_to_error_dict(
        self,
        mock_system: MagicMock,
        mock_mcp_context: MagicMock,
    ) -> None:
        """Test that exceptions produce an error response with success=False."""
        mock_system.execute_smart_task = AsyncMock(
            side_effect=RuntimeError("backend offline"),
        )

        with patch(
            "crackerjack.mcp.tools.intelligence_tools.get_intelligent_agent_system",
            AsyncMock(return_value=mock_system),
        ):
            response = await execute_smart_agent_task(
                task_description="Will raise",
                context_type="refactoring",
                strategy="sequential",
            )

        assert response["success"] is False
        assert "backend offline" in response["error"]
        assert response["task_description"] == "Will raise"
        assert response["context_type"] == "refactoring"
        assert response["strategy_used"] == "sequential"


class TestGetSmartAgentRecommendation:
    """Tests for get_smart_agent_recommendation handler."""

    @pytest.mark.asyncio
    async def test_recommendation_present(
        self,
        mock_system: MagicMock,
    ) -> None:
        """Test that a recommendation tuple is unpacked into the response."""
        mock_system.get_best_agent_for_task = AsyncMock(
            return_value=("arch-agent", 0.88),
        )

        with patch(
            "crackerjack.mcp.tools.intelligence_tools.get_intelligent_agent_system",
            AsyncMock(return_value=mock_system),
        ):
            response = await get_smart_agent_recommendation(
                task_description="Design new module",
                include_analysis=False,
            )

        assert response["recommended_agent"] == "arch-agent"
        assert response["confidence"] == pytest.approx(0.88)
        assert response["has_recommendation"] is True
        assert "complexity_analysis" not in response

    @pytest.mark.asyncio
    async def test_recommendation_absent(
        self,
        mock_system: MagicMock,
    ) -> None:
        """Test missing recommendation yields has_recommendation=False and a message."""
        mock_system.get_best_agent_for_task = AsyncMock(return_value=None)

        with patch(
            "crackerjack.mcp.tools.intelligence_tools.get_intelligent_agent_system",
            AsyncMock(return_value=mock_system),
        ):
            response = await get_smart_agent_recommendation(
                task_description="Do obscure task",
            )

        assert response["has_recommendation"] is False
        assert response["recommended_agent"] is None
        assert response["confidence"] == 0.0
        assert "No suitable agent" in response["message"]

    @pytest.mark.asyncio
    async def test_include_analysis_attaches_complexity(
        self,
        mock_system: MagicMock,
    ) -> None:
        """Test complexity analysis is attached as serialized JSON when requested."""
        mock_system.get_best_agent_for_task = AsyncMock(
            return_value=("a", 0.5),
        )

        with patch(
            "crackerjack.mcp.tools.intelligence_tools.get_intelligent_agent_system",
            AsyncMock(return_value=mock_system),
        ):
            response = await get_smart_agent_recommendation(
                task_description="Anything",
                include_analysis=True,
            )

        assert "complexity_analysis" in response
        parsed = json.loads(response["complexity_analysis"])
        assert parsed == {"complexity": "medium", "score": 0.5}

    @pytest.mark.asyncio
    async def test_include_analysis_handles_inner_failure(
        self,
        mock_system: MagicMock,
    ) -> None:
        """Test complexity analysis failure still produces a JSON error block."""
        mock_system.analyze_task_complexity = AsyncMock(
            side_effect=ValueError("oops"),
        )

        with patch(
            "crackerjack.mcp.tools.intelligence_tools.get_intelligent_agent_system",
            AsyncMock(return_value=mock_system),
        ):
            response = await get_smart_agent_recommendation(
                task_description="Anything",
                include_analysis=True,
            )

        parsed = json.loads(response["complexity_analysis"])
        assert "error" in parsed
        assert "oops" in parsed["error"]

    @pytest.mark.asyncio
    async def test_maps_valid_context(
        self,
        mock_system: MagicMock,
    ) -> None:
        """Test that a valid context string is forwarded to the system."""
        with patch(
            "crackerjack.mcp.tools.intelligence_tools.get_intelligent_agent_system",
            AsyncMock(return_value=mock_system),
        ):
            await get_smart_agent_recommendation(
                task_description="Improve speed",
                context_type="performance",
            )

        call_kwargs = mock_system.get_best_agent_for_task.call_args.kwargs
        assert call_kwargs["context"] is TaskContext.PERFORMANCE

    @pytest.mark.asyncio
    async def test_exception_falls_back_to_error_dict(
        self,
        mock_system: MagicMock,
    ) -> None:
        """Test that exceptions surface in the response, not propagated."""
        mock_system.get_best_agent_for_task = AsyncMock(
            side_effect=RuntimeError("ranking failure"),
        )

        with patch(
            "crackerjack.mcp.tools.intelligence_tools.get_intelligent_agent_system",
            AsyncMock(return_value=mock_system),
        ):
            response = await get_smart_agent_recommendation(
                task_description="Will raise",
            )

        assert response["has_recommendation"] is False
        assert "ranking failure" in response["error"]
        assert response["task_description"] == "Will raise"


class TestGetIntelligenceSystemStatus:
    """Tests for get_intelligence_system_status handler."""

    @pytest.mark.asyncio
    async def test_success_adds_runtime_info(
        self,
        mock_system: MagicMock,
    ) -> None:
        """Test successful status includes a runtime_info block."""
        with patch(
            "crackerjack.mcp.tools.intelligence_tools.get_intelligent_agent_system",
            AsyncMock(return_value=mock_system),
        ):
            status = await get_intelligence_system_status()

        assert status["initialized"] is True
        assert "runtime_info" in status
        runtime = status["runtime_info"]
        assert runtime["system_initialized"] is True
        assert runtime["components_loaded"]["registry"] is True
        assert runtime["components_loaded"]["orchestrator"] is True
        assert runtime["components_loaded"]["learning_system"] is True

    @pytest.mark.asyncio
    async def test_runtime_info_reflects_missing_components(
        self,
        mock_system: MagicMock,
    ) -> None:
        """Test that False component refs are reflected in runtime_info."""
        mock_system.registry = None
        mock_system.orchestrator = MagicMock()
        mock_system.learning_system = None

        with patch(
            "crackerjack.mcp.tools.intelligence_tools.get_intelligent_agent_system",
            AsyncMock(return_value=mock_system),
        ):
            status = await get_intelligence_system_status()

        loaded = status["runtime_info"]["components_loaded"]
        assert loaded == {
            "registry": False,
            "orchestrator": True,
            "learning_system": False,
        }

    @pytest.mark.asyncio
    async def test_exception_returns_error_dict(
        self,
        mock_system: MagicMock,
    ) -> None:
        """Test that backend errors surface as initialized=False error dict."""
        mock_system.get_system_status = AsyncMock(
            side_effect=RuntimeError("init failed"),
        )

        with patch(
            "crackerjack.mcp.tools.intelligence_tools.get_intelligent_agent_system",
            AsyncMock(return_value=mock_system),
        ):
            status = await get_intelligence_system_status()

        assert status == {
            "error": "init failed",
            "initialized": False,
        }


class TestAnalyzeAgentPerformance:
    """Tests for analyze_agent_performance handler."""

    @pytest.mark.asyncio
    async def test_success_aggregates_subsystem_stats(
        self,
        mock_system: MagicMock,
    ) -> None:
        """Test successful analysis returns subsystem summaries + insights."""
        with patch(
            "crackerjack.mcp.tools.intelligence_tools.get_intelligent_agent_system",
            AsyncMock(return_value=mock_system),
        ):
            analysis = await analyze_agent_performance()

        assert analysis["learning_summary"] == {
            "total_records": 3,
            "average_confidence": 0.8,
        }
        assert analysis["orchestration_stats"] == {
            "total": 7,
            "successes": 6,
            "failures": 1,
        }
        assert analysis["registry_overview"]["total_agents"] == 12
        assert "analysis_timestamp" in analysis

        insights = analysis["recent_insights"]
        assert len(insights) == 1
        assert insights[0]["type"] == "performance"
        assert insights[0]["agent"] == "refactor-agent"
        assert insights[0]["confidence"] == pytest.approx(0.7)
        assert insights[0]["description"] == "Speed improved"

    @pytest.mark.asyncio
    async def test_no_insights_attr_omits_recent_insights(
        self,
        mock_system: MagicMock,
    ) -> None:
        """Test that a learning_system without _learning_insights omits the field."""
        # Drop the attribute to exercise the hasattr branch.
        del mock_system.learning_system._learning_insights

        with patch(
            "crackerjack.mcp.tools.intelligence_tools.get_intelligent_agent_system",
            AsyncMock(return_value=mock_system),
        ):
            analysis = await analyze_agent_performance()

        assert "recent_insights" not in analysis
        assert analysis["learning_summary"]["total_records"] == 3

    @pytest.mark.asyncio
    async def test_exception_returns_unavailable_dict(
        self,
        mock_system: MagicMock,
    ) -> None:
        """Test that backend errors produce a graceful unavailable dict."""
        mock_system.initialize = AsyncMock(
            side_effect=RuntimeError("registry offline"),
        )

        with patch(
            "crackerjack.mcp.tools.intelligence_tools.get_intelligent_agent_system",
            AsyncMock(return_value=mock_system),
        ):
            analysis = await analyze_agent_performance()

        assert analysis == {
            "error": "registry offline",
            "analysis_available": False,
        }


class TestGetContext:
    """Smoke test: get_context() runs without raising."""

    def test_get_context_runs(self) -> None:
        """Test the get_context() call at top of execute_smart_agent_task runs."""
        # Importing the module must not raise, and get_context must be reachable
        # via the tool's module namespace.
        from crackerjack.mcp.tools import intelligence_tools

        assert callable(intelligence_tools.get_context)
