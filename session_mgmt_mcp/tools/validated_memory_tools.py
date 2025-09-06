#!/usr/bin/env python3
"""Example integration of parameter validation models with MCP tools.

This module demonstrates how to integrate Pydantic parameter validation
models with existing MCP tools for improved type safety and error handling.

Following crackerjack patterns:
- EVERY LINE IS A LIABILITY: Clean, focused tool implementations
- DRY: Reusable validation across all tools
- KISS: Simple integration without over-engineering
"""

from __future__ import annotations

from datetime import datetime

from session_mgmt_mcp.parameter_models import (
    ConceptSearchParams,
    FileSearchParams,
    ReflectionStoreParams,
    SearchQueryParams,
    validate_mcp_params,
)
from session_mgmt_mcp.utils.logging import get_session_logger

logger = get_session_logger()

# Lazy loading for optional dependencies
_reflection_db = None
_reflection_tools_available = None


async def _get_reflection_database():
    """Get reflection database instance with lazy loading."""
    global _reflection_db, _reflection_tools_available

    if _reflection_tools_available is False:
        msg = "Reflection tools not available"
        raise ImportError(msg)

    if _reflection_db is None:
        try:
            from session_mgmt_mcp.reflection_tools import ReflectionDatabase

            _reflection_db = ReflectionDatabase()
            _reflection_tools_available = True
        except ImportError as e:
            _reflection_tools_available = False
            msg = f"Reflection tools not available. Install dependencies: {e}"
            raise ImportError(msg) from e

    return _reflection_db


def _check_reflection_tools_available() -> bool:
    """Check if reflection tools are available."""
    global _reflection_tools_available

    if _reflection_tools_available is None:
        try:
            import importlib.util

            spec = importlib.util.find_spec("session_mgmt_mcp.reflection_tools")
            _reflection_tools_available = spec is not None
        except ImportError:
            _reflection_tools_available = False

    return _reflection_tools_available


# Tool implementations with parameter validation
async def _store_reflection_validated_impl(**params) -> str:
    """Implementation for store_reflection tool with parameter validation."""
    if not _check_reflection_tools_available():
        return "❌ Reflection tools not available. Install dependencies: uv sync --extra embeddings"

    try:
        # Validate parameters using Pydantic model
        validated = validate_mcp_params(ReflectionStoreParams, **params)
        content = validated["content"]
        tags = validated.get("tags")

        db = await _get_reflection_database()
        success = await db.store_reflection(content, tags=tags or [])

        if success:
            output = []
            output.append("💾 Reflection stored successfully!")
            output.append(
                f"📝 Content: {content[:100]}{'...' if len(content) > 100 else ''}"
            )
            if tags:
                output.append(f"🏷️ Tags: {', '.join(tags)}")
            output.append(f"📅 Stored: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            logger.info("Reflection stored", content_length=len(content), tags=tags)
            return "\n".join(output)

        return "❌ Failed to store reflection"

    except ValueError as e:
        logger.warning(f"Parameter validation failed: {e}")
        return f"❌ Parameter validation error: {e}"
    except Exception as e:
        logger.exception(f"Error storing reflection: {e}")
        return f"❌ Error storing reflection: {e}"


async def _quick_search_validated_impl(**params) -> str:
    """Implementation for quick_search tool with parameter validation."""
    if not _check_reflection_tools_available():
        return "❌ Reflection tools not available. Install dependencies: uv sync --extra embeddings"

    try:
        # Validate parameters using Pydantic model
        validated = validate_mcp_params(SearchQueryParams, **params)
        query = validated["query"]
        min_score = validated["min_score"]
        project = validated.get("project")

        db = await _get_reflection_database()
        results = await db.search_reflections(
            query=query,
            project=project,
            limit=1,
            min_score=min_score,
        )

        output = []
        output.append(f"🔍 Quick search for: '{query}'")

        if results:
            result = results[0]
            output.append("📊 Found results (showing top 1)")
            output.append(
                f"📝 {result['content'][:150]}{'...' if len(result['content']) > 150 else ''}"
            )
            if result.get("project"):
                output.append(f"📁 Project: {result['project']}")
            if result.get("score"):
                output.append(f"⭐ Relevance: {result['score']:.2f}")
            output.append(f"📅 Date: {result.get('timestamp', 'Unknown')}")
        else:
            output.append("🔍 No results found")
            output.append("💡 Try adjusting your search terms or lowering min_score")

        logger.info("Quick search performed", query=query, results_count=len(results))
        return "\n".join(output)

    except ValueError as e:
        logger.warning(f"Parameter validation failed: {e}")
        return f"❌ Parameter validation error: {e}"
    except Exception as e:
        logger.exception(f"Error in quick search: {e}")
        return f"❌ Search error: {e}"


async def _search_by_file_validated_impl(**params) -> str:
    """Implementation for search_by_file tool with parameter validation."""
    if not _check_reflection_tools_available():
        return "❌ Reflection tools not available. Install dependencies: uv sync --extra embeddings"

    try:
        # Validate parameters using Pydantic model
        validated = validate_mcp_params(FileSearchParams, **params)
        file_path = validated["file_path"]
        limit = validated["limit"]
        project = validated.get("project")

        db = await _get_reflection_database()
        results = await db.search_reflections(
            query=file_path,
            project=project,
            limit=limit,
        )

        output = []
        output.append(f"📁 Searching conversations about: {file_path}")
        output.append("=" * 50)

        if results:
            output.append(f"📈 Found {len(results)} relevant conversations:")

            for i, result in enumerate(results, 1):
                output.append(
                    f"\n{i}. 📝 {result['content'][:200]}{'...' if len(result['content']) > 200 else ''}"
                )
                if result.get("project"):
                    output.append(f"   📁 Project: {result['project']}")
                if result.get("score"):
                    output.append(f"   ⭐ Relevance: {result['score']:.2f}")
                if result.get("timestamp"):
                    output.append(f"   📅 Date: {result['timestamp']}")
        else:
            output.append("🔍 No conversations found about this file")
            output.append(
                "💡 The file might not have been discussed in previous sessions"
            )

        logger.info(
            "File search performed", file_path=file_path, results_count=len(results)
        )
        return "\n".join(output)

    except ValueError as e:
        logger.warning(f"Parameter validation failed: {e}")
        return f"❌ Parameter validation error: {e}"
    except Exception as e:
        logger.exception(f"Error searching by file: {e}")
        return f"❌ File search error: {e}"


async def _search_by_concept_validated_impl(**params) -> str:
    """Implementation for search_by_concept tool with parameter validation."""
    if not _check_reflection_tools_available():
        return "❌ Reflection tools not available. Install dependencies: uv sync --extra embeddings"

    try:
        # Validate parameters using Pydantic model
        validated = validate_mcp_params(ConceptSearchParams, **params)
        concept = validated["concept"]
        include_files = validated["include_files"]
        limit = validated["limit"]
        project = validated.get("project")

        db = await _get_reflection_database()
        results = await db.search_reflections(
            query=concept,
            project=project,
            limit=limit,
        )

        output = []
        output.append(f"🧠 Searching for concept: '{concept}'")
        output.append("=" * 50)

        if results:
            output.append(f"📈 Found {len(results)} related conversations:")

            for i, result in enumerate(results, 1):
                output.append(
                    f"\n{i}. 📝 {result['content'][:250]}{'...' if len(result['content']) > 250 else ''}"
                )
                if result.get("project"):
                    output.append(f"   📁 Project: {result['project']}")
                if result.get("score"):
                    output.append(f"   ⭐ Relevance: {result['score']:.2f}")
                if result.get("timestamp"):
                    output.append(f"   📅 Date: {result['timestamp']}")

                if include_files and result.get("files"):
                    files = result["files"][:3]
                    if files:
                        output.append(f"   📄 Files: {', '.join(files)}")
        else:
            output.append("🔍 No conversations found about this concept")
            output.append("💡 Try related terms or broader concepts")

        logger.info(
            "Concept search performed", concept=concept, results_count=len(results)
        )
        return "\n".join(output)

    except ValueError as e:
        logger.warning(f"Parameter validation failed: {e}")
        return f"❌ Parameter validation error: {e}"
    except Exception as e:
        logger.exception(f"Error searching by concept: {e}")
        return f"❌ Concept search error: {e}"


def register_validated_memory_tools(mcp_server) -> None:
    """Register memory management tools with parameter validation.

    This demonstrates how to integrate Pydantic parameter validation
    with existing MCP tools for improved type safety.
    """

    @mcp_server.tool()
    async def store_reflection_validated(
        content: str,
        tags: list[str] | None = None,
    ) -> str:
        """Store an important insight or reflection with parameter validation.

        Args:
            content: Content to store as reflection (1-50,000 chars)
            tags: Optional tags for categorization (alphanumeric, hyphens, underscores only)

        Returns:
            Success/error message with validation feedback

        """
        return await _store_reflection_validated_impl(content=content, tags=tags)

    @mcp_server.tool()
    async def quick_search_validated(
        query: str,
        min_score: float = 0.7,
        project: str | None = None,
        limit: int = 10,
    ) -> str:
        """Quick search with parameter validation.

        Args:
            query: Search query text (1-1,000 chars)
            min_score: Minimum relevance score (0.0-1.0)
            project: Optional project identifier (1-200 chars)
            limit: Maximum results to return (1-1,000)

        Returns:
            Formatted search results with validation feedback

        """
        return await _quick_search_validated_impl(
            query=query, min_score=min_score, project=project, limit=limit
        )

    @mcp_server.tool()
    async def search_by_file_validated(
        file_path: str,
        limit: int = 10,
        project: str | None = None,
    ) -> str:
        """Search for conversations about a specific file with parameter validation.

        Args:
            file_path: File path to search for (cannot be empty)
            limit: Maximum results to return (1-1,000)
            project: Optional project identifier (1-200 chars)

        Returns:
            File-specific search results with validation feedback

        """
        return await _search_by_file_validated_impl(
            file_path=file_path, limit=limit, project=project
        )

    @mcp_server.tool()
    async def search_by_concept_validated(
        concept: str,
        include_files: bool = True,
        limit: int = 10,
        project: str | None = None,
    ) -> str:
        """Search for conversations about a development concept with parameter validation.

        Args:
            concept: Development concept to search for (1-200 chars)
            include_files: Include related files in results
            limit: Maximum results to return (1-1,000)
            project: Optional project identifier (1-200 chars)

        Returns:
            Concept-specific search results with validation feedback

        """
        return await _search_by_concept_validated_impl(
            concept=concept,
            include_files=include_files,
            limit=limit,
            project=project,
        )


# Example usage demonstrating error handling and validation feedback
class ValidationExamples:
    """Examples showing parameter validation in action."""

    @staticmethod
    async def example_valid_calls():
        """Examples of valid parameter calls."""
        # Valid reflection storage
        result1 = await _store_reflection_validated_impl(
            content="Learned that async/await patterns improve database performance significantly",
            tags=["python", "async", "database", "performance"],
        )

        # Valid search with all parameters
        result2 = await _quick_search_validated_impl(
            query="python async patterns",
            min_score=0.8,
            project="session-mgmt-mcp",
            limit=5,
        )

        # Valid file search
        result3 = await _search_by_file_validated_impl(
            file_path="src/reflection_tools.py", limit=20, project="session-mgmt-mcp"
        )

        return [result1, result2, result3]

    @staticmethod
    async def example_validation_errors():
        """Examples that would trigger validation errors."""
        # Empty content - would fail validation
        try:
            await _store_reflection_validated_impl(content="", tags=["test"])
        except ValueError as e:
            print(f"Expected validation error: {e}")

        # Invalid score range - would fail validation
        try:
            await _quick_search_validated_impl(
                query="test",
                min_score=1.5,  # Invalid: > 1.0
                limit=0,  # Invalid: < 1
            )
        except ValueError as e:
            print(f"Expected validation error: {e}")

        # Invalid tags format - would fail validation
        try:
            await _store_reflection_validated_impl(
                content="Valid content",
                tags=["valid-tag", "invalid tag with spaces", "another@invalid!tag"],
            )
        except ValueError as e:
            print(f"Expected validation error: {e}")


# Migration guide for existing tools
class MigrationGuide:
    """Guide for migrating existing MCP tools to use parameter validation."""

    @staticmethod
    def before_migration():
        """Example of tool before parameter validation."""
        """
        @mcp.tool()
        async def search_reflections(
            query: str,
            limit: int = 10,
            project: str | None = None,
            min_score: float = 0.7
        ) -> str:
            # No validation - any values could be passed
            # Could receive empty strings, negative numbers, etc.

            # Manual validation would be needed
            if not query.strip():
                return "❌ Query cannot be empty"
            if limit < 1 or limit > 1000:
                return "❌ Limit must be between 1 and 1000"
            # ... more manual validation

            # Implementation...
        """

    @staticmethod
    def after_migration():
        """Example of tool after parameter validation."""
        """
        @mcp.tool()
        async def search_reflections(
            query: str,
            limit: int = 10,
            project: str | None = None,
            min_score: float = 0.7
        ) -> str:
            try:
                # Validate all parameters at once
                validated = validate_mcp_params(
                    SearchQueryParams,
                    query=query,
                    limit=limit,
                    project=project,
                    min_score=min_score
                )

                # Use validated parameters (guaranteed to be valid)
                query = validated['query']  # Non-empty, properly formatted
                limit = validated['limit']  # 1-1000 range
                project = validated.get('project')  # None or valid project name
                min_score = validated['min_score']  # 0.0-1.0 range

                # Implementation with confidence in parameter validity...

            except ValueError as e:
                return f"❌ Parameter validation error: {e}"
        """
