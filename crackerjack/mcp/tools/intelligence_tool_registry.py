"""Intelligence tool registry for MCP server."""

from .intelligence_tools import (
    analyze_agent_performance,
    execute_smart_agent_task,
    get_intelligence_system_status,
    get_smart_agent_recommendation,
)


def register_intelligence_tools(mcp_app) -> None:
    """Register intelligence system tools with the MCP server."""

    @mcp_app.tool()
    async def execute_smart_task(
        task_description: str,
        context_type: str = "general",
        strategy: str = "single_best",
        max_agents: int = 3,
        use_learning: bool = True,
    ):
        """Execute a task using intelligent agent selection.

        Args:
            task_description: Description of the task to execute
            context_type: Type of task context (architecture, refactoring, testing, etc.)
            strategy: Execution strategy (single_best, parallel, sequential, consensus)
            max_agents: Maximum number of agents to consider
            use_learning: Whether to apply adaptive learning

        Returns:
            Dictionary with execution results and metadata
        """
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
    ):
        """Get intelligent agent recommendation for a task without executing it.

        Args:
            task_description: Description of the task
            context_type: Type of task context
            include_analysis: Whether to include complexity analysis

        Returns:
            Dictionary with recommendation details
        """
        return await get_smart_agent_recommendation(
            task_description,
            context_type,
            include_analysis,
        )

    @mcp_app.tool()
    async def intelligence_system_status():
        """Get comprehensive status of the intelligent agent system.

        Returns:
            Dictionary with system status and statistics
        """
        return await get_intelligence_system_status()

    @mcp_app.tool()
    async def agent_performance_analysis():
        """Analyze agent performance and learning insights.

        Returns:
            Dictionary with performance analysis and insights
        """
        return await analyze_agent_performance()
