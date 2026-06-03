from __future__ import annotations

import json
import logging
import typing as t
from pathlib import Path

from crackerjack.integration.git_semantic_search import (
    GitSemanticSearchConfig,
    create_git_semantic_search,
)
from crackerjack.services.input_validator import get_input_validator

logger = logging.getLogger(__name__)


def register_git_semantic_tools(mcp_app: t.Any) -> None:
    _register_search_git_history_tool(mcp_app)
    _register_find_workflow_patterns_tool(mcp_app)
    _register_recommend_git_practices_tool(mcp_app)
    _register_index_git_history_tool(mcp_app)


def _register_search_git_history_tool(mcp_app: t.Any) -> None:

    @mcp_app.tool()
    async def search_git_history(
        query: str, limit: int = 10, days_back: int = 30, repository_path: str = ""
    ) -> str:
        try:
            validator = get_input_validator()
            query_result = validator.validate_command_args(query)
            if not query_result.valid:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Invalid query: {query_result.error_message}",
                        "validation_type": query_result.validation_type,
                    }
                )
            sanitized_query = query_result.sanitized_value or query
            param_error = _validate_search_params(limit, days_back)
            if param_error:
                return json.dumps({"success": False, "error": param_error})
            repo_path = _get_repository_path(repository_path)
            config = GitSemanticSearchConfig(
                similarity_threshold=0.6, max_results=limit
            )
            searcher = create_git_semantic_search(repo_path=repo_path, config=config)  # type: ignore
            results = await searcher.search_git_history(
                query=sanitized_query, limit=limit, days_back=days_back
            )
            searcher.close()
            return json.dumps(results, indent=2, default=str)
        except ValueError as e:
            return json.dumps({"success": False, "error": f"Validation error: {e}"})
        except Exception as e:
            logger.error(f"search_git_history failed: {e}")
            return json.dumps(
                {
                    "success": False,
                    "error": f"Failed to search git history: {e}",
                    "query": query,
                }
            )


def _register_find_workflow_patterns_tool(mcp_app: t.Any) -> None:

    @mcp_app.tool()
    async def find_workflow_patterns(
        pattern_description: str,
        days_back: int = 90,
        min_frequency: int = 3,
        repository_path: str = "",
    ) -> str:
        try:
            validator = get_input_validator()
            pattern_result = validator.validate_command_args(pattern_description)
            if not pattern_result.valid:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Invalid pattern description: {pattern_result.error_message}",
                        "validation_type": pattern_result.validation_type,
                    }
                )
            sanitized_pattern = pattern_result.sanitized_value or pattern_description
            param_error = _validate_pattern_params(days_back, min_frequency)
            if param_error:
                return json.dumps({"success": False, "error": param_error})
            repo_path = _get_repository_path(repository_path)
            searcher = create_git_semantic_search(repo_path=repo_path)  # type: ignore
            results = await searcher.find_workflow_patterns(
                pattern_description=sanitized_pattern,
                days_back=days_back,
                min_frequency=min_frequency,
            )
            searcher.close()
            return json.dumps(results, indent=2, default=str)
        except ValueError as e:
            return json.dumps({"success": False, "error": f"Validation error: {e}"})
        except Exception as e:
            logger.error(f"find_workflow_patterns failed: {e}")
            return json.dumps(
                {
                    "success": False,
                    "error": f"Failed to find workflow patterns: {e}",
                    "pattern_description": pattern_description,
                }
            )


def _register_recommend_git_practices_tool(mcp_app: t.Any) -> None:

    @mcp_app.tool()
    async def recommend_git_practices(
        focus_area: str = "general", days_back: int = 60, repository_path: str = ""
    ) -> str:
        try:
            validator = get_input_validator()
            focus_result = validator.validate_command_args(focus_area)
            if not focus_result.valid:
                return json.dumps(
                    {
                        "success": False,
                        "error": f"Invalid focus area: {focus_result.error_message}",
                        "validation_type": focus_result.validation_type,
                    }
                )
            sanitized_focus = focus_result.sanitized_value or focus_area
            param_error = _validate_recommendation_params(days_back)
            if param_error:
                return json.dumps({"success": False, "error": param_error})
            normalized_focus = _normalize_focus_area(sanitized_focus)
            repo_path = _get_repository_path(repository_path)
            searcher = create_git_semantic_search(repo_path=repo_path)  # type: ignore
            results = await searcher.recommend_git_practices(
                focus_area=normalized_focus, days_back=days_back
            )
            searcher.close()
            return json.dumps(results, indent=2, default=str)
        except ValueError as e:
            return json.dumps({"success": False, "error": f"Validation error: {e}"})
        except Exception as e:
            logger.error(f"recommend_git_practices failed: {e}")
            return json.dumps(
                {
                    "success": False,
                    "error": f"Failed to recommend git practices: {e}",
                    "focus_area": focus_area,
                }
            )


def _register_index_git_history_tool(mcp_app: t.Any) -> None:

    @mcp_app.tool()
    async def index_git_history(days_back: int = 30, repository_path: str = "") -> str:
        try:
            param_error = _validate_index_params(days_back)
            if param_error:
                return json.dumps({"success": False, "error": param_error})
            repo_path = _get_repository_path(repository_path)
            config = GitSemanticSearchConfig(auto_index=True)
            searcher = create_git_semantic_search(repo_path=repo_path, config=config)  # type: ignore
            await searcher._ensure_index(days_back)
            searcher.close()
            return json.dumps(
                {
                    "success": True,
                    "message": f"Successfully indexed git history for the last {days_back} days",
                    "repository": repo_path,
                    "days_indexed": days_back,
                },
                indent=2,
            )
        except ValueError as e:
            return json.dumps({"success": False, "error": f"Validation error: {e}"})
        except Exception as e:
            logger.error(f"index_git_history failed: {e}")
            return json.dumps(
                {
                    "success": False,
                    "error": f"Failed to index git history: {e}",
                    "repository_path": repository_path,
                }
            )


def _validate_search_params(limit: int, days_back: int) -> str | None:
    if not 1 <= limit <= 50:
        return "limit must be between 1 and 50"
    if not 1 <= days_back <= 365:
        return "days_back must be between 1 and 365"
    return None


def _validate_pattern_params(days_back: int, min_frequency: int) -> str | None:
    if not 7 <= days_back <= 365:
        return "days_back must be between 7 and 365"
    if not 2 <= min_frequency <= 20:
        return "min_frequency must be between 2 and 20"
    return None


def _validate_recommendation_params(days_back: int) -> str | None:
    if not 7 <= days_back <= 365:
        return "days_back must be between 7 and 365"
    return None


def _validate_index_params(days_back: int) -> str | None:
    if not 1 <= days_back <= 365:
        return "days_back must be between 1 and 365"
    return None


def _get_repository_path(repository_path: str) -> Path:
    if repository_path and repository_path.strip():
        validator = get_input_validator()
        path_result = validator.validate_file_path(repository_path)
        if path_result.valid and path_result.sanitized_value:
            return Path(path_result.sanitized_value)
    return Path.cwd()


def _normalize_focus_area(focus_area: str) -> str:
    focus_map = {
        "general": "general",
        "branching": "branching",
        "commit quality": "commit_quality",
        "commit_quality": "commit_quality",
        "commits": "commit_quality",
        "merge conflicts": "merge_conflicts",
        "merge_conflicts": "merge_conflicts",
        "conflicts": "merge_conflicts",
        "velocity": "velocity",
        "speed": "velocity",
        "breaking changes": "breaking_changes",
        "breaking_changes": "breaking_changes",
        "breaking": "breaking_changes",
    }
    normalized = focus_map.get(focus_area.lower().strip(), "general")
    if normalized not in (
        "general",
        "branching",
        "commit_quality",
        "merge_conflicts",
        "velocity",
        "breaking_changes",
    ):
        logger.warning(f"Unknown focus area '{focus_area}', defaulting to 'general'")
        return "general"
    return normalized
