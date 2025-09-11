#!/usr/bin/env python3
"""Search and reflection tools for session-mgmt-mcp.

Following crackerjack architecture patterns with focused, single-responsibility tools
for conversation memory, semantic search, and knowledge retrieval.
"""

from __future__ import annotations

import logging
from typing import Any

# Import will be handled by the get_reflection_database function at the end of the file

logger = logging.getLogger(__name__)


def register_search_tools(mcp) -> None:
    """Register all search-related MCP tools.

    Args:
        mcp: FastMCP server instance

    """

    @mcp.tool()
    async def _optimize_search_results(
        results: list,
        optimize_tokens: bool,
        max_tokens: int,
        query: str,
    ) -> dict[str, Any]:
        """Apply token optimization to search results if available."""
        try:
            # Import token optimizer if available
            from session_mgmt_mcp.token_optimizer import TokenOptimizer

            if optimize_tokens and results:
                optimizer = TokenOptimizer()
                return await optimizer.optimize_search_results(
                    results, max_tokens, query
                )

            return {
                "results": results,
                "optimized": False,
                "token_count": 0,
            }
        except ImportError:
            logger.info("Token optimizer not available, returning results as-is")
            return {
                "results": results,
                "optimized": False,
                "token_count": 0,
            }
        except Exception as e:
            logger.exception(f"Search optimization failed: {e}")
            return {
                "results": results,
                "optimized": False,
                "error": str(e),
            }

    @mcp.tool()
    async def store_reflection(content: str, tags: list[str] | None = None) -> str:
        """Store an important insight or reflection for future reference."""
        try:
            db = await get_reflection_database()
            if not db:
                return "❌ Reflection system not available. Install optional dependencies with `uv sync --extra embeddings`"

            async with db:
                reflection_id = await db.store_reflection(content, tags or [])
                tag_text = f" (tags: {', '.join(tags)})" if tags else ""
                return f"✅ Reflection stored successfully with ID: {reflection_id}{tag_text}"

        except Exception as e:
            logger.exception(f"Failed to store reflection: {e}")
            return f"❌ Error storing reflection: {e!s}"

    @mcp.tool()
    async def quick_search(
        query: str,
        project: str | None = None,
        min_score: float = 0.7,
    ) -> str:
        """Quick search that returns only the count and top result for fast overview."""
        try:
            db = await get_reflection_database()
            if not db:
                return "❌ Search system not available. Install optional dependencies with `uv sync --extra embeddings`"

            async with db:
                # Get total count
                total_results = await db.search_conversations(
                    query=query,
                    project=project,
                    min_score=min_score,
                    limit=100,  # Get more for accurate count
                )

                if not total_results:
                    return f"🔍 No results found for '{query}'"

                # Get top result
                top_result = total_results[0]

                # Format response
                result = f"🔍 **{len(total_results)} results** for '{query}'\n\n"
                result += (
                    f"**Top Result** (score: {top_result.get('similarity', 'N/A')}):\n"
                )
                result += f"{top_result.get('content', '')[:200]}..."

                if len(total_results) > 1:
                    result += f"\n\n💡 Use get_more_results to see additional {len(total_results) - 1} results"

                return result

        except Exception as e:
            logger.exception(f"Quick search failed: {e}")
            return f"❌ Search error: {e!s}"

    @mcp.tool()
    async def search_summary(
        query: str,
        project: str | None = None,
        min_score: float = 0.7,
    ) -> str:
        """Get aggregated insights from search results without individual result details."""
        try:
            db = await get_reflection_database()
            if not db:
                return "❌ Search system not available. Install optional dependencies with `uv sync --extra embeddings`"

            async with db:
                results = await db.search_conversations(
                    query=query,
                    project=project,
                    min_score=min_score,
                    limit=20,
                )

                if not results:
                    return f"🔍 No results found for '{query}'"

                # Generate summary
                summary = f"🔍 **Search Summary for '{query}'**\n\n"
                summary += f"**Found**: {len(results)} relevant conversations\n"

                # Analyze time distribution
                if results:
                    dates = [
                        r.get("timestamp", "") for r in results if r.get("timestamp")
                    ]
                    if dates:
                        summary += f"**Time Range**: {min(dates)} to {max(dates)}\n"

                # Key themes (basic)
                all_content = " ".join([r.get("content", "")[:100] for r in results])
                word_freq = {}
                for word in all_content.split():
                    if len(word) > 4:  # Skip short words
                        word_freq[word.lower()] = word_freq.get(word.lower(), 0) + 1

                if word_freq:
                    top_words = sorted(
                        word_freq.items(), key=lambda x: x[1], reverse=True
                    )[:5]
                    summary += (
                        f"**Key Terms**: {', '.join([w[0] for w in top_words])}\n"
                    )

                summary += "\n💡 Use search with same query to see individual results"

                return summary

        except Exception as e:
            logger.exception(f"Search summary failed: {e}")
            return f"❌ Search summary error: {e!s}"

    @mcp.tool()
    async def get_more_results(
        query: str,
        offset: int = 3,
        limit: int = 3,
        project: str | None = None,
    ) -> str:
        """Get additional search results after an initial search (pagination support)."""
        try:
            db = await get_reflection_database()
            if not db:
                return "❌ Search system not available. Install optional dependencies with `uv sync --extra embeddings`"

            async with db:
                results = await db.search_conversations(
                    query=query,
                    project=project,
                    limit=limit + offset,  # Get enough to skip offset
                )

                # Apply offset
                paginated_results = results[offset : offset + limit]

                if not paginated_results:
                    return f"🔍 No more results for '{query}' (offset: {offset})"

                # Format results
                output = f"🔍 **Results {offset + 1}-{offset + len(paginated_results)}** for '{query}'\n\n"

                for i, result in enumerate(paginated_results, offset + 1):
                    output += f"**{i}.** "
                    if result.get("timestamp"):
                        output += f"({result['timestamp']}) "
                    output += f"{result.get('content', '')[:150]}...\n\n"

                total_results = len(results)
                if offset + limit < total_results:
                    remaining = total_results - (offset + limit)
                    output += f"💡 {remaining} more results available"

                return output

        except Exception as e:
            logger.exception(f"Get more results failed: {e}")
            return f"❌ Pagination error: {e!s}"

    @mcp.tool()
    async def search_by_file(
        file_path: str,
        limit: int = 10,
        project: str | None = None,
    ) -> str:
        """Search for conversations that analyzed a specific file."""
        try:
            db = await get_reflection_database()
            if not db:
                return "❌ Search system not available. Install optional dependencies with `uv sync --extra embeddings`"

            async with db:
                # Search for the file path in conversations
                results = await db.search_conversations(
                    query=file_path,  # Simple text search for file path
                    project=project,
                    limit=limit,
                )

                if not results:
                    return f"🔍 No conversations found about file: {file_path}"

                output = f"🔍 **{len(results)} conversations** about `{file_path}`\n\n"

                for i, result in enumerate(results, 1):
                    output += f"**{i}.** "
                    if result.get("timestamp"):
                        output += f"({result['timestamp']}) "

                    content = result.get("content", "")
                    # Try to find context around the file path
                    if file_path in content:
                        start = max(0, content.find(file_path) - 50)
                        end = min(
                            len(content), content.find(file_path) + len(file_path) + 100
                        )
                        excerpt = content[start:end]
                    else:
                        excerpt = content[:150]

                    output += f"{excerpt}...\n\n"

                return output

        except Exception as e:
            logger.exception(f"File search failed: {e}")
            return f"❌ File search error: {e!s}"

    @mcp.tool()
    async def search_by_concept(
        concept: str,
        include_files: bool = True,
        limit: int = 10,
        project: str | None = None,
    ) -> str:
        """Search for conversations about a specific development concept."""
        try:
            db = await get_reflection_database()
            if not db:
                return "❌ Search system not available. Install optional dependencies with `uv sync --extra embeddings`"

            async with db:
                results = await db.search_conversations(
                    query=concept,
                    project=project,
                    limit=limit,
                    min_score=0.6,  # Lower threshold for concept searches
                )

                if not results:
                    return f"🔍 No conversations found about concept: {concept}"

                output = f"🔍 **{len(results)} conversations** about `{concept}`\n\n"

                for i, result in enumerate(results, 1):
                    output += f"**{i}.** "
                    if result.get("timestamp"):
                        output += f"({result['timestamp']}) "
                    if result.get("similarity"):
                        output += f"(relevance: {result['similarity']:.2f}) "

                    content = result.get("content", "")
                    # Find best excerpt mentioning the concept
                    if concept.lower() in content.lower():
                        start = max(0, content.lower().find(concept.lower()) - 75)
                        end = min(len(content), start + 200)
                        excerpt = content[start:end]
                    else:
                        excerpt = content[:150]

                    output += f"{excerpt}...\n\n"

                if include_files and results:
                    # Extract mentioned files
                    all_content = " ".join([r.get("content", "") for r in results])
                    from session_mgmt_mcp.utils.regex_patterns import SAFE_PATTERNS

                    # Use validated pattern for file extraction
                    files = []
                    for pattern_name in [
                        "python_files",
                        "javascript_files",
                        "typescript_files",
                        "markdown_files",
                        "json_files",
                    ]:
                        pattern = SAFE_PATTERNS[pattern_name]
                        matches = pattern.findall(all_content)
                        files.extend(matches)
                    if files:
                        unique_files = list(set(files))[:10]
                        output += f"📁 **Related Files**: {', '.join(unique_files)}"

                return output

        except Exception as e:
            logger.exception(f"Concept search failed: {e}")
            return f"❌ Concept search error: {e!s}"

    @mcp.tool()
    async def reset_reflection_database() -> str:
        """Reset the reflection database connection to fix lock issues."""
        try:
            db = await get_reflection_database()
            if not db:
                return "❌ Reflection database not available"

            async with db:
                await db.reset_connection()
                return "✅ Reflection database connection reset successfully"

        except Exception as e:
            logger.exception(f"Database reset failed: {e}")
            return f"❌ Database reset error: {e!s}"

    @mcp.tool()
    async def reflection_stats() -> str:
        """Get statistics about the reflection database."""
        try:
            db = await get_reflection_database()
            if not db:
                return "❌ Reflection database not available. Install optional dependencies with `uv sync --extra embeddings`"

            async with db:
                stats = await db.get_stats()

                output = "📊 **Reflection Database Statistics**\n\n"

                for key, value in stats.items():
                    output += f"**{key.replace('_', ' ').title()}**: {value}\n"

                return output

        except Exception as e:
            logger.exception(f"Stats collection failed: {e}")
            return f"❌ Stats error: {e!s}"

    # Advanced search tools
    @mcp.tool()
    async def search_code(
        query: str,
        pattern_type: str | None = None,
        limit: int = 10,
        project: str | None = None,
    ) -> str:
        """Search for code patterns in conversations using AST parsing."""
        try:
            db = await get_reflection_database()
            if not db:
                return "❌ Search system not available. Install optional dependencies with `uv sync --extra embeddings`"

            # Build enhanced query for code search
            code_query = f"code {query}"
            if pattern_type:
                code_query += f" {pattern_type}"

            async with db:
                results = await db.search_conversations(
                    query=code_query,
                    project=project,
                    limit=limit,
                    min_score=0.5,
                )

                if not results:
                    return f"🔍 No code patterns found for: {query}"

                output = f"🔍 **{len(results)} code patterns** for `{query}`"
                if pattern_type:
                    output += f" (type: {pattern_type})"
                output += "\n\n"

                for i, result in enumerate(results, 1):
                    output += f"**{i}.** "
                    if result.get("timestamp"):
                        output += f"({result['timestamp']}) "

                    content = result.get("content", "")
                    # Look for code blocks using validated pattern
                    from session_mgmt_mcp.utils.regex_patterns import SAFE_PATTERNS

                    code_pattern = SAFE_PATTERNS["generic_code_block"]
                    code_blocks = code_pattern.findall(content)

                    if code_blocks:
                        # Show first code block
                        code = code_blocks[0][:200]
                        output += f"\n```\n{code}...\n```\n\n"
                    else:
                        # Show context around query term
                        if query.lower() in content.lower():
                            start = max(0, content.lower().find(query.lower()) - 50)
                            end = min(len(content), start + 150)
                            excerpt = content[start:end]
                        else:
                            excerpt = content[:100]
                        output += f"{excerpt}...\n\n"

                return output

        except Exception as e:
            logger.exception(f"Code search failed: {e}")
            return f"❌ Code search error: {e!s}"

    @mcp.tool()
    async def search_errors(
        query: str,
        error_type: str | None = None,
        limit: int = 10,
        project: str | None = None,
    ) -> str:
        """Search for error patterns and debugging contexts in conversations."""
        try:
            db = await get_reflection_database()
            if not db:
                return "❌ Search system not available. Install optional dependencies with `uv sync --extra embeddings`"

            # Build enhanced query for error search
            error_query = f"error {query}"
            if error_type:
                error_query += f" {error_type}"

            async with db:
                results = await db.search_conversations(
                    query=error_query,
                    project=project,
                    limit=limit,
                    min_score=0.4,  # Lower threshold for error searches
                )

                if not results:
                    return f"🔍 No error patterns found for: {query}"

                output = f"🔍 **{len(results)} error contexts** for `{query}`"
                if error_type:
                    output += f" (type: {error_type})"
                output += "\n\n"

                for i, result in enumerate(results, 1):
                    output += f"**{i}.** "
                    if result.get("timestamp"):
                        output += f"({result['timestamp']}) "

                    content = result.get("content", "")

                    # Look for error patterns
                    error_keywords = [
                        "error",
                        "exception",
                        "traceback",
                        "failed",
                        "fix",
                    ]
                    best_excerpt = ""
                    best_score = 0

                    for keyword in error_keywords:
                        if keyword in content.lower():
                            start = max(0, content.lower().find(keyword) - 75)
                            end = min(len(content), start + 200)
                            excerpt = content[start:end]
                            score = content.lower().count(keyword)
                            if score > best_score:
                                best_score = score
                                best_excerpt = excerpt

                    if not best_excerpt:
                        best_excerpt = content[:150]

                    output += f"{best_excerpt}...\n\n"

                return output

        except Exception as e:
            logger.exception(f"Error search failed: {e}")
            return f"❌ Error search failed: {e!s}"

    @mcp.tool()
    async def search_temporal(
        time_expression: str,
        query: str | None = None,
        limit: int = 10,
        project: str | None = None,
    ) -> str:
        """Search conversations within a specific time range using natural language."""
        try:
            db = await get_reflection_database()
            if not db:
                return "❌ Search system not available. Install optional dependencies with `uv sync --extra embeddings`"

            # Parse time expression (basic implementation)
            from datetime import datetime, timedelta

            now = datetime.now()
            start_time = None

            if "yesterday" in time_expression.lower():
                start_time = now - timedelta(days=1)
            elif "last week" in time_expression.lower():
                start_time = now - timedelta(days=7)
            elif "last month" in time_expression.lower():
                start_time = now - timedelta(days=30)
            elif "today" in time_expression.lower():
                start_time = now - timedelta(hours=24)

            # For now, use regular search and filter by basic time logic
            async with db:
                search_query = query or ""
                results = await db.search_conversations(
                    query=search_query,
                    project=project,
                    limit=limit * 2,  # Get more to filter
                )

                # Basic time filtering (would need more sophisticated parsing)
                if start_time:
                    # This is a simplified filter - would need proper timestamp parsing
                    filtered_results = list(results)
                    results = filtered_results[:limit]

                if not results:
                    return (
                        f"🔍 No conversations found for time period: {time_expression}"
                    )

                output = f"🔍 **{len(results)} conversations** from `{time_expression}`"
                if query:
                    output += f" matching `{query}`"
                output += "\n\n"

                for i, result in enumerate(results, 1):
                    output += f"**{i}.** "
                    if result.get("timestamp"):
                        output += f"({result['timestamp']}) "

                    content = result.get("content", "")
                    output += f"{content[:150]}...\n\n"

                return output

        except Exception as e:
            logger.exception(f"Temporal search failed: {e}")
            return f"❌ Temporal search error: {e!s}"


async def get_reflection_database():
    """Get reflection database instance with lazy loading."""
    try:
        from session_mgmt_mcp.reflection_tools import ReflectionDatabase

        return ReflectionDatabase()
    except ImportError:
        return None
    except Exception:
        return None
