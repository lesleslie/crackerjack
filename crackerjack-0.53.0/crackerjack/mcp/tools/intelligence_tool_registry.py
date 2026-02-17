import typing as t

from .intelligence_tools import (
    analyze_agent_performance,
    execute_smart_agent_task,
    get_intelligence_system_status,
    get_smart_agent_recommendation,
)


def register_intelligence_tools(mcp_app: t.Any) -> None:
    @mcp_app.tool()
    async def execute_smart_task(
        task_description: str,
        context_type: str = "general",
        strategy: str = "single_best",
        max_agents: int = 3,
        use_learning: bool = True,
    ) -> t.Any:
        return await execute_smart_agent_task(
            task_description,
            context_type,
            strategy,
            max_agents,
            use_learning,
        )

    @mcp_app.tool()
    async def get_agent_recommendation(
        task_description: str,
        context_type: str = "general",
        include_analysis: bool = True,
    ) -> t.Any:
        return await get_smart_agent_recommendation(
            task_description,
            context_type,
            include_analysis,
        )

    @mcp_app.tool()
    async def intelligence_system_status() -> t.Any:
        return await get_intelligence_system_status()

    @mcp_app.tool()
    async def agent_performance_analysis() -> t.Any:
        return await analyze_agent_performance()
