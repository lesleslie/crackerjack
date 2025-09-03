#!/usr/bin/env python3
"""Memory and reflection management MCP tools.

This module provides tools for storing, searching, and managing reflections and conversation memories.
"""

from datetime import datetime

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
            raise ImportError(
                msg,
            )

    return _reflection_db


def _check_reflection_tools_available() -> bool:
    """Check if reflection tools are available."""
    global _reflection_tools_available

    if _reflection_tools_available is None:
        try:
            # Check if reflection_tools module is importable
            import importlib.util

            spec = importlib.util.find_spec("session_mgmt_mcp.reflection_tools")
            _reflection_tools_available = spec is not None
        except ImportError:
            _reflection_tools_available = False

    return _reflection_tools_available


# Tool implementations
async def _store_reflection_impl(content: str, tags: list[str] | None = None) -> str:
    """Implementation for store_reflection tool."""
    if not _check_reflection_tools_available():
        return "❌ Reflection tools not available. Install dependencies: uv sync --extra embeddings"

    try:
        db = await _get_reflection_database()
        success = await db.store_reflection(content, tags=tags or [])

        if success:
            output = []
            output.append("💾 Reflection stored successfully!")
            output.append(
                f"📝 Content: {content[:100]}{'...' if len(content) > 100 else ''}",
            )
            if tags:
                output.append(f"🏷️ Tags: {', '.join(tags)}")
            output.append(f"📅 Stored: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            logger.info("Reflection stored", content_length=len(content), tags=tags)
            return "\n".join(output)
        return "❌ Failed to store reflection"

    except Exception as e:
        logger.exception("Error storing reflection", error=str(e))
        return f"❌ Error storing reflection: {e}"


async def _quick_search_impl(
    query: str,
    min_score: float = 0.7,
    project: str | None = None,
) -> str:
    """Implementation for quick_search tool."""
    if not _check_reflection_tools_available():
        return "❌ Reflection tools not available. Install dependencies: uv sync --extra embeddings"

    try:
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
                f"📝 {result['content'][:150]}{'...' if len(result['content']) > 150 else ''}",
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

    except Exception as e:
        logger.exception("Error in quick search", error=str(e), query=query)
        return f"❌ Search error: {e}"


async def _search_summary_impl(
    query: str,
    min_score: float = 0.7,
    project: str | None = None,
) -> str:
    """Implementation for search_summary tool."""
    if not _check_reflection_tools_available():
        return "❌ Reflection tools not available. Install dependencies: uv sync --extra embeddings"

    try:
        db = await _get_reflection_database()
        results = await db.search_reflections(
            query=query,
            project=project,
            limit=20,
            min_score=min_score,
        )

        output = []
        output.append(f"📊 Search Summary for: '{query}'")
        output.append("=" * 50)

        if results:
            output.append(f"📈 Total results: {len(results)}")

            # Project distribution
            projects = {}
            for result in results:
                proj = result.get("project", "Unknown")
                projects[proj] = projects.get(proj, 0) + 1

            if len(projects) > 1:
                output.append("📁 Project distribution:")
                for proj, count in sorted(
                    projects.items(),
                    key=lambda x: x[1],
                    reverse=True,
                ):
                    output.append(f"   • {proj}: {count} results")

            # Time distribution
            timestamps = [r.get("timestamp") for r in results if r.get("timestamp")]
            if timestamps:
                output.append(f"📅 Time range: {len(timestamps)} results with dates")

            # Average relevance score
            scores = [r.get("score", 0) for r in results if r.get("score")]
            if scores:
                avg_score = sum(scores) / len(scores)
                output.append(f"⭐ Average relevance: {avg_score:.2f}")

            # Common themes
            all_content = " ".join([r["content"] for r in results])
            words = all_content.lower().split()
            word_freq = {}
            for word in words:
                if len(word) > 4:
                    word_freq[word] = word_freq.get(word, 0) + 1

            if word_freq:
                top_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)[
                    :5
                ]
                output.append("🔤 Common themes:")
                for word, freq in top_words:
                    output.append(f"   • {word}: {freq} mentions")

        else:
            output.append("🔍 No results found")
            output.append(
                "💡 Try different search terms or lower the min_score threshold",
            )

        logger.info("Search summary generated", query=query, results_count=len(results))
        return "\n".join(output)

    except Exception as e:
        logger.exception("Error generating search summary", error=str(e), query=query)
        return f"❌ Search summary error: {e}"


async def _search_by_file_impl(
    file_path: str,
    limit: int = 10,
    project: str | None = None,
) -> str:
    """Implementation for search_by_file tool."""
    if not _check_reflection_tools_available():
        return "❌ Reflection tools not available. Install dependencies: uv sync --extra embeddings"

    try:
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
                    f"\n{i}. 📝 {result['content'][:200]}{'...' if len(result['content']) > 200 else ''}",
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
                "💡 The file might not have been discussed in previous sessions",
            )

        logger.info(
            "File search performed",
            file_path=file_path,
            results_count=len(results),
        )
        return "\n".join(output)

    except Exception as e:
        logger.exception("Error searching by file", error=str(e), file_path=file_path)
        return f"❌ File search error: {e}"


async def _search_by_concept_impl(
    concept: str,
    include_files: bool = True,
    limit: int = 10,
    project: str | None = None,
) -> str:
    """Implementation for search_by_concept tool."""
    if not _check_reflection_tools_available():
        return "❌ Reflection tools not available. Install dependencies: uv sync --extra embeddings"

    try:
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
                    f"\n{i}. 📝 {result['content'][:250]}{'...' if len(result['content']) > 250 else ''}",
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
            "Concept search performed",
            concept=concept,
            results_count=len(results),
        )
        return "\n".join(output)

    except Exception as e:
        logger.exception("Error searching by concept", error=str(e), concept=concept)
        return f"❌ Concept search error: {e}"


async def _reflection_stats_impl() -> str:
    """Implementation for reflection_stats tool."""
    if not _check_reflection_tools_available():
        return "❌ Reflection tools not available. Install dependencies: uv sync --extra embeddings"

    try:
        db = await _get_reflection_database()
        stats = await db.get_reflection_stats()

        output = []
        output.append("📊 Reflection Database Statistics")
        output.append("=" * 40)

        if stats:
            output.append(f"📈 Total reflections: {stats.get('total_reflections', 0)}")
            output.append(f"📁 Projects: {stats.get('projects', 0)}")

            date_range = stats.get("date_range")
            if date_range:
                output.append(
                    f"📅 Date range: {date_range.get('start')} to {date_range.get('end')}",
                )

            recent_activity = stats.get("recent_activity", [])
            if recent_activity:
                output.append("\n🕐 Recent activity:")
                for activity in recent_activity[:5]:
                    output.append(f"   • {activity}")

            # Database health info
            output.append(
                f"\n🏥 Database health: {'✅ Healthy' if stats.get('total_reflections', 0) > 0 else '⚠️ Empty'}",
            )

        else:
            output.append("📊 No statistics available")
            output.append("💡 Database may be empty or inaccessible")

        logger.info("Reflection stats retrieved")
        return "\n".join(output)

    except Exception as e:
        logger.exception("Error getting reflection stats", error=str(e))
        return f"❌ Stats error: {e}"


async def _reset_reflection_database_impl() -> str:
    """Implementation for reset_reflection_database tool."""
    if not _check_reflection_tools_available():
        return "❌ Reflection tools not available. Install dependencies: uv sync --extra embeddings"

    try:
        global _reflection_db

        # Close existing connection if any
        if _reflection_db and hasattr(_reflection_db, "conn") and _reflection_db.conn:
            try:
                _reflection_db.conn.close()
            except Exception as e:
                logger.warning(f"Error closing old connection: {e}")

        # Reset the global instance
        _reflection_db = None

        # Try to create a new connection
        await _get_reflection_database()

        output = []
        output.append("🔄 Reflection database connection reset")
        output.append("✅ New connection established successfully")
        output.append("💡 Database locks should be resolved")

        logger.info("Reflection database reset successfully")
        return "\n".join(output)

    except Exception as e:
        logger.exception("Error resetting reflection database", error=str(e))
        return f"❌ Reset error: {e}"


def register_memory_tools(mcp_server) -> None:
    """Register all memory management tools with the MCP server."""

    @mcp_server.tool()
    async def store_reflection(content: str, tags: list[str] | None = None) -> str:
        """Store an important insight or reflection for future reference."""
        return await _store_reflection_impl(content, tags)

    @mcp_server.tool()
    async def quick_search(
        query: str,
        min_score: float = 0.7,
        project: str | None = None,
    ) -> str:
        """Quick search that returns only the count and top result for fast overview."""
        return await _quick_search_impl(query, min_score, project)

    @mcp_server.tool()
    async def search_summary(
        query: str,
        min_score: float = 0.7,
        project: str | None = None,
    ) -> str:
        """Get aggregated insights from search results without individual result details."""
        return await _search_summary_impl(query, min_score, project)

    @mcp_server.tool()
    async def search_by_file(
        file_path: str,
        limit: int = 10,
        project: str | None = None,
    ) -> str:
        """Search for conversations that analyzed a specific file."""
        return await _search_by_file_impl(file_path, limit, project)

    @mcp_server.tool()
    async def search_by_concept(
        concept: str,
        include_files: bool = True,
        limit: int = 10,
        project: str | None = None,
    ) -> str:
        """Search for conversations about a specific development concept."""
        return await _search_by_concept_impl(concept, include_files, limit, project)

    @mcp_server.tool()
    async def reflection_stats() -> str:
        """Get statistics about the reflection database."""
        return await _reflection_stats_impl()

    @mcp_server.tool()
    async def reset_reflection_database() -> str:
        """Reset the reflection database connection to fix lock issues."""
        return await _reset_reflection_database_impl()
