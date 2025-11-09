import asyncio
import json
import logging
import typing as t

from crackerjack.intelligence import ExecutionStrategy, TaskContext
from crackerjack.intelligence.integration import get_intelligent_agent_system
from crackerjack.mcp.context import get_context


async def execute_smart_agent_task(
    task_description: str,
    context_type: str = "general",
    strategy: str = "single_best",
    max_agents: int = 3,
    use_learning: bool = True,
) -> dict[str, t.Any]:
    get_context()
    logger = logging.getLogger(__name__)

    try:
        task_context = None
        context_map = {
            "architecture": TaskContext.ARCHITECTURE,
            "refactoring": TaskContext.REFACTORING,
            "testing": TaskContext.TESTING,
            "security": TaskContext.SECURITY,
            "performance": TaskContext.PERFORMANCE,
            "documentation": TaskContext.DOCUMENTATION,
            "code_quality": TaskContext.CODE_QUALITY,
            "debugging": TaskContext.DEBUGGING,
            "project_setup": TaskContext.PROJECT_SETUP,
            "general": TaskContext.GENERAL,
        }

        if context_type.lower() in context_map:
            task_context = context_map[context_type.lower()]

        strategy_map = {
            "single_best": ExecutionStrategy.SINGLE_BEST,
            "parallel": ExecutionStrategy.PARALLEL,
            "sequential": ExecutionStrategy.SEQUENTIAL,
            "consensus": ExecutionStrategy.CONSENSUS,
        }

        execution_strategy = strategy_map.get(
            strategy.lower(), ExecutionStrategy.SINGLE_BEST
        )

        system = await get_intelligent_agent_system()

        logger.info(
            f"Executing smart task: '{task_description[:50]}...' "
            f"(context: {context_type}, strategy: {strategy})"
        )

        result = await system.execute_smart_task(
            description=task_description,
            context=task_context,
            strategy=execution_strategy,
        )

        response = {
            "success": result.success,
            "agents_used": result.agents_used,
            "execution_time": result.execution_time,
            "confidence": result.confidence,
            "recommendations": result.recommendations,
            "learning_applied": result.learning_applied,
            "task_description": task_description,
            "context_type": context_type,
            "strategy_used": strategy,
        }

        if hasattr(result.result, "__dict__"):
            try:
                if hasattr(result.result, "success"):
                    response["fix_result"] = {
                        "success": getattr(result.result, "success", False),
                        "confidence": getattr(result.result, "confidence", 0.0),
                        "fixes_applied": getattr(result.result, "fixes_applied", []),
                        "remaining_issues": getattr(
                            result.result, "remaining_issues", []
                        ),
                        "recommendations": getattr(
                            result.result, "recommendations", []
                        ),
                        "files_modified": getattr(result.result, "files_modified", []),
                    }
                else:
                    response["result"] = str(result.result)
            except Exception:
                response["result"] = str(result.result)
        else:
            response["result"] = result.result

        if result.success:
            logger.info(
                f"Smart task completed successfully using {len(result.agents_used)} agents "
                f"in {result.execution_time: .2f}s"
            )
        else:
            logger.warning(f"Smart task failed: {result.recommendations}")

        return response

    except Exception as e:
        logger.exception(f"Error in smart agent execution: {e}")
        return {
            "success": False,
            "error": str(e),
            "task_description": task_description,
            "context_type": context_type,
            "strategy_used": strategy,
        }


async def get_smart_agent_recommendation(
    task_description: str,
    context_type: str = "general",
    include_analysis: bool = True,
) -> dict[str, t.Any]:
    logger = logging.getLogger(__name__)

    try:
        task_context = None
        context_map = {
            "architecture": TaskContext.ARCHITECTURE,
            "refactoring": TaskContext.REFACTORING,
            "testing": TaskContext.TESTING,
            "security": TaskContext.SECURITY,
            "performance": TaskContext.PERFORMANCE,
            "documentation": TaskContext.DOCUMENTATION,
            "code_quality": TaskContext.CODE_QUALITY,
            "debugging": TaskContext.DEBUGGING,
            "project_setup": TaskContext.PROJECT_SETUP,
            "general": TaskContext.GENERAL,
        }

        if context_type.lower() in context_map:
            task_context = context_map[context_type.lower()]

        system = await get_intelligent_agent_system()

        recommendation = await system.get_best_agent_for_task(
            description=task_description,
            context=task_context,
        )

        response: dict[str, t.Any] = {
            "task_description": task_description,
            "context_type": context_type,
        }

        if recommendation:
            agent_name, confidence = recommendation
            response.update(
                {
                    "recommended_agent": agent_name,
                    "confidence": confidence,
                    "has_recommendation": True,
                }
            )
        else:
            response.update(
                {
                    "recommended_agent": None,
                    "confidence": 0.0,
                    "has_recommendation": False,
                    "message": "No suitable agent found for this task",
                }
            )

        if include_analysis:
            try:
                analysis = await system.analyze_task_complexity(task_description)
                response["complexity_analysis"] = json.dumps(analysis, indent=2)
            except Exception as e:
                logger.warning(f"Failed to analyze task complexity: {e}")
                response["complexity_analysis"] = json.dumps(
                    {"error": str(e)}, indent=2
                )

        logger.debug(f"Generated recommendation for task: {task_description[:50]}")
        return response

    except Exception as e:
        logger.exception(f"Error getting smart recommendation: {e}")
        return {
            "task_description": task_description,
            "context_type": context_type,
            "error": str(e),
            "has_recommendation": False,
        }


async def get_intelligence_system_status() -> dict[str, t.Any]:
    logger = logging.getLogger(__name__)

    try:
        system = await get_intelligent_agent_system()
        status = await system.get_system_status()

        status["runtime_info"] = {
            "system_initialized": system._initialized,
            "components_loaded": {
                "registry": system.registry is not None,
                "orchestrator": system.orchestrator is not None,
                "learning_system": system.learning_system is not None,
            },
        }

        logger.debug("Generated intelligence system status")
        return status

    except Exception as e:
        logger.exception(f"Error getting intelligence system status: {e}")
        return {
            "error": str(e),
            "initialized": False,
        }


async def analyze_agent_performance() -> dict[str, t.Any]:
    logger = logging.getLogger(__name__)

    try:
        system = await get_intelligent_agent_system()
        await system.initialize()

        learning_summary = system.learning_system.get_learning_summary()

        orchestration_stats = system.orchestrator.get_execution_stats()

        registry_stats = system.registry.get_agent_stats()

        performance_analysis = {
            "learning_summary": learning_summary,
            "orchestration_stats": orchestration_stats,
            "registry_overview": registry_stats,
            "analysis_timestamp": asyncio.get_event_loop().time(),
        }

        if hasattr(system.learning_system, "_learning_insights"):
            recent_insights = [
                {
                    "type": insight.insight_type,
                    "agent": insight.agent_name,
                    "confidence": insight.confidence,
                    "description": insight.description,
                }
                for insight in system.learning_system._learning_insights[-10:]
            ]
            performance_analysis["recent_insights"] = recent_insights

        logger.debug("Generated agent performance analysis")
        return performance_analysis

    except Exception as e:
        logger.exception(f"Error analyzing agent performance: {e}")
        return {
            "error": str(e),
            "analysis_available": False,
        }
