#!/usr/bin/env python3
"""Integration tests for token optimization in MCP server."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from session_mgmt_mcp.server import (
    get_cached_chunk,
    get_token_usage_stats,
    optimize_memory_usage,
    reflect_on_past,
)


@pytest.fixture
def mock_reflection_db():
    """Mock reflection database with sample data."""
    db = AsyncMock()

    # Sample conversation data
    sample_conversations = [
        {
            "id": "conv1",
            "content": 'This is a conversation about Python functions. def hello(): return "world"',
            "timestamp": datetime.now().isoformat(),
            "project": "test-project",
            "score": 0.8,
        },
        {
            "id": "conv2",
            "content": "This is a much longer conversation about software architecture. "
            * 20,
            "timestamp": (datetime.now() - timedelta(hours=1)).isoformat(),
            "project": "test-project",
            "score": 0.6,
        },
        {
            "id": "conv3",
            "content": "Recent error troubleshooting. TypeError: cannot call object. Traceback shows...",
            "timestamp": (datetime.now() + timedelta(minutes=30)).isoformat(),
            "project": "test-project",
            "score": 0.9,
        },
    ]

    db.search_conversations.return_value = sample_conversations
    return db


@pytest.fixture
def mock_token_optimizer():
    """Mock token optimizer."""
    optimizer = MagicMock()
    optimizer.count_tokens.return_value = 100
    return optimizer


class TestReflectOnPastOptimization:
    """Test token optimization in reflect_on_past tool."""

    @pytest.mark.asyncio
    async def test_reflect_on_past_with_optimization(self, mock_reflection_db):
        """Test reflect_on_past with token optimization enabled."""
        with (
            patch("session_mgmt_mcp.server.get_reflection_database") as mock_get_db,
            patch("session_mgmt_mcp.server.TOKEN_OPTIMIZER_AVAILABLE", True),
            patch("session_mgmt_mcp.server.REFLECTION_TOOLS_AVAILABLE", True),
            patch("session_mgmt_mcp.server.optimize_search_response") as mock_optimize,
            patch("session_mgmt_mcp.server.track_token_usage") as mock_track,
        ):
            mock_get_db.return_value = mock_reflection_db
            mock_optimize.return_value = (
                mock_reflection_db.search_conversations.return_value[
                    :2
                ],  # Optimized results
                {
                    "strategy": "prioritize_recent",
                    "token_savings": {"tokens_saved": 150, "savings_percentage": 30},
                },
            )

            result = await reflect_on_past(
                query="Python functions",
                limit=5,
                optimize_tokens=True,
                max_tokens=500,
            )

            # Verify optimization was applied
            mock_optimize.assert_called_once()
            assert "⚡ Token optimization: 30% saved" in result

            # Verify usage tracking
            mock_track.assert_called_once()

    @pytest.mark.asyncio
    async def test_reflect_on_past_optimization_disabled(self, mock_reflection_db):
        """Test reflect_on_past with token optimization disabled."""
        with (
            patch("session_mgmt_mcp.server.get_reflection_database") as mock_get_db,
            patch("session_mgmt_mcp.server.TOKEN_OPTIMIZER_AVAILABLE", True),
            patch("session_mgmt_mcp.server.REFLECTION_TOOLS_AVAILABLE", True),
            patch("session_mgmt_mcp.server.optimize_search_response") as mock_optimize,
        ):
            mock_get_db.return_value = mock_reflection_db

            result = await reflect_on_past(
                query="Python functions",
                optimize_tokens=False,
            )

            # Optimization should not be called
            mock_optimize.assert_not_called()
            assert "⚡ Token optimization" not in result

    @pytest.mark.asyncio
    async def test_reflect_on_past_optimization_error_handling(
        self,
        mock_reflection_db,
    ):
        """Test error handling when optimization fails."""
        with (
            patch("session_mgmt_mcp.server.get_reflection_database") as mock_get_db,
            patch("session_mgmt_mcp.server.TOKEN_OPTIMIZER_AVAILABLE", True),
            patch("session_mgmt_mcp.server.REFLECTION_TOOLS_AVAILABLE", True),
            patch("session_mgmt_mcp.server.optimize_search_response") as mock_optimize,
            patch("session_mgmt_mcp.server.session_logger") as mock_logger,
        ):
            mock_get_db.return_value = mock_reflection_db
            mock_optimize.side_effect = Exception("Optimization failed")

            # Should not crash and should log warning
            result = await reflect_on_past(
                query="Python functions",
                optimize_tokens=True,
            )

            assert "Found 3 relevant conversations" in result
            mock_logger.warning.assert_called_once()

    @pytest.mark.asyncio
    async def test_reflect_on_past_token_optimizer_unavailable(
        self,
        mock_reflection_db,
    ):
        """Test when token optimizer is not available."""
        with (
            patch("session_mgmt_mcp.server.get_reflection_database") as mock_get_db,
            patch("session_mgmt_mcp.server.TOKEN_OPTIMIZER_AVAILABLE", False),
            patch("session_mgmt_mcp.server.REFLECTION_TOOLS_AVAILABLE", True),
            patch("session_mgmt_mcp.server.optimize_search_response") as mock_optimize,
        ):
            mock_get_db.return_value = mock_reflection_db

            result = await reflect_on_past(
                query="Python functions",
                optimize_tokens=True,
            )

            # Should work without optimization
            mock_optimize.assert_not_called()
            assert "Found 3 relevant conversations" in result


class TestCachedChunkRetrieval:
    """Test cached chunk retrieval MCP tool."""

    @pytest.mark.asyncio
    async def test_get_cached_chunk_success(self):
        """Test successful chunk retrieval."""
        mock_chunk_data = {
            "chunk": [{"id": "conv1", "content": "Test content"}],
            "current_chunk": 1,
            "total_chunks": 3,
            "cache_key": "test_key",
            "has_more": True,
        }

        with (
            patch("session_mgmt_mcp.server.TOKEN_OPTIMIZER_AVAILABLE", True),
            patch("session_mgmt_mcp.server.get_cached_chunk") as mock_get_chunk,
        ):
            mock_get_chunk.return_value = mock_chunk_data

            result = await get_cached_chunk("test_key", 1)

            assert "📄 Chunk 1 of 3" in result
            assert "Test content" in result
            assert "More chunks available" in result
            mock_get_chunk.assert_called_once_with("test_key", 1)

    @pytest.mark.asyncio
    async def test_get_cached_chunk_not_found(self):
        """Test chunk retrieval when chunk not found."""
        with (
            patch("session_mgmt_mcp.server.TOKEN_OPTIMIZER_AVAILABLE", True),
            patch("session_mgmt_mcp.server.get_cached_chunk") as mock_get_chunk,
        ):
            mock_get_chunk.return_value = None

            result = await get_cached_chunk("invalid_key", 1)

            assert "❌ Chunk not found" in result

    @pytest.mark.asyncio
    async def test_get_cached_chunk_optimizer_unavailable(self):
        """Test chunk retrieval when token optimizer unavailable."""
        with patch("session_mgmt_mcp.server.TOKEN_OPTIMIZER_AVAILABLE", False):
            result = await get_cached_chunk("test_key", 1)

            assert "❌ Token optimizer not available" in result

    @pytest.mark.asyncio
    async def test_get_cached_chunk_last_chunk(self):
        """Test retrieving the last chunk."""
        mock_chunk_data = {
            "chunk": [{"id": "conv3", "content": "Final chunk content"}],
            "current_chunk": 3,
            "total_chunks": 3,
            "cache_key": "test_key",
            "has_more": False,
        }

        with (
            patch("session_mgmt_mcp.server.TOKEN_OPTIMIZER_AVAILABLE", True),
            patch("session_mgmt_mcp.server.get_cached_chunk") as mock_get_chunk,
        ):
            mock_get_chunk.return_value = mock_chunk_data

            result = await get_cached_chunk("test_key", 3)

            assert "📄 Chunk 3 of 3" in result
            assert "More chunks available" not in result


class TestTokenUsageStats:
    """Test token usage statistics MCP tool."""

    @pytest.mark.asyncio
    async def test_get_token_usage_stats_success(self):
        """Test successful token usage stats retrieval."""
        mock_stats = {
            "status": "success",
            "total_requests": 25,
            "total_tokens": 5000,
            "average_tokens_per_request": 200.0,
            "optimizations_applied": {"prioritize_recent": 10, "truncate_old": 5},
            "estimated_cost_savings": {
                "savings_usd": 0.0125,
                "estimated_tokens_saved": 1250,
                "requests_optimized": 15,
            },
        }

        with (
            patch("session_mgmt_mcp.server.TOKEN_OPTIMIZER_AVAILABLE", True),
            patch("session_mgmt_mcp.server.get_token_usage_stats") as mock_get_stats,
        ):
            mock_get_stats.return_value = mock_stats

            result = await get_token_usage_stats(hours=24)

            assert "📊 Token Usage Statistics" in result
            assert "Total Requests: 25" in result
            assert "Total Tokens Used: 5,000" in result
            assert "Average Tokens per Request: 200.0" in result
            assert "prioritize_recent: 10 times" in result
            assert "truncate_old: 5 times" in result
            assert "$0.0125 USD saved" in result
            assert "1,250 tokens saved" in result

    @pytest.mark.asyncio
    async def test_get_token_usage_stats_no_data(self):
        """Test token usage stats when no data available."""
        mock_stats = {"status": "no_data"}

        with (
            patch("session_mgmt_mcp.server.TOKEN_OPTIMIZER_AVAILABLE", True),
            patch("session_mgmt_mcp.server.get_token_usage_stats") as mock_get_stats,
        ):
            mock_get_stats.return_value = mock_stats

            result = await get_token_usage_stats(hours=24)

            assert "No token usage data available" in result

    @pytest.mark.asyncio
    async def test_get_token_usage_stats_optimizer_unavailable(self):
        """Test token usage stats when optimizer unavailable."""
        with patch("session_mgmt_mcp.server.TOKEN_OPTIMIZER_AVAILABLE", False):
            result = await get_token_usage_stats()

            assert "❌ Token optimizer not available" in result

    @pytest.mark.asyncio
    async def test_get_token_usage_stats_error_handling(self):
        """Test error handling in token usage stats."""
        with (
            patch("session_mgmt_mcp.server.TOKEN_OPTIMIZER_AVAILABLE", True),
            patch("session_mgmt_mcp.server.get_token_usage_stats") as mock_get_stats,
        ):
            mock_get_stats.side_effect = Exception("Stats error")

            result = await get_token_usage_stats()

            assert "❌ Error getting token usage stats" in result


class TestOptimizeMemoryUsage:
    """Test memory usage optimization MCP tool."""

    @pytest.mark.asyncio
    async def test_optimize_memory_usage_dry_run(self):
        """Test memory optimization in dry run mode."""
        mock_optimization_results = {
            "status": "success",
            "total_conversations": 100,
            "conversations_to_keep": 60,
            "conversations_to_consolidate": 40,
            "clusters_created": 8,
            "space_saved_estimate": 15000,
            "compression_ratio": 0.35,
            "consolidated_summaries": [
                {
                    "original_count": 5,
                    "projects": ["project1", "project2"],
                    "summary": "Consolidated summary of related conversations about API development...",
                },
            ],
        }

        with (
            patch("session_mgmt_mcp.server.TOKEN_OPTIMIZER_AVAILABLE", True),
            patch("session_mgmt_mcp.server.REFLECTION_TOOLS_AVAILABLE", True),
            patch("session_mgmt_mcp.server.get_reflection_database") as mock_get_db,
        ):
            # Mock MemoryOptimizer
            mock_db = AsyncMock()
            mock_get_db.return_value = mock_db

            with patch(
                "session_mgmt_mcp.server.MemoryOptimizer",
            ) as mock_optimizer_class:
                mock_optimizer = AsyncMock()
                mock_optimizer.compress_memory.return_value = mock_optimization_results
                mock_optimizer_class.return_value = mock_optimizer

                result = await optimize_memory_usage(
                    strategy="auto",
                    max_age_days=30,
                    dry_run=True,
                )

                assert "🧠 Memory Optimization Results (DRY RUN)" in result
                assert "Total Conversations: 100" in result
                assert "Conversations to Keep: 60" in result
                assert "Conversations to Consolidate: 40" in result
                assert "Clusters Created: 8" in result
                assert "15,000 characters saved" in result
                assert "35.0% compression ratio" in result
                assert "5 conversations → 1 summary" in result
                assert "Run with dry_run=False to apply changes" in result

    @pytest.mark.asyncio
    async def test_optimize_memory_usage_aggressive_strategy(self):
        """Test memory optimization with aggressive strategy."""
        mock_optimization_results = {
            "status": "success",
            "total_conversations": 50,
            "conversations_to_keep": 20,
            "conversations_to_consolidate": 30,
            "clusters_created": 6,
        }

        with (
            patch("session_mgmt_mcp.server.TOKEN_OPTIMIZER_AVAILABLE", True),
            patch("session_mgmt_mcp.server.REFLECTION_TOOLS_AVAILABLE", True),
            patch("session_mgmt_mcp.server.get_reflection_database") as mock_get_db,
        ):
            mock_db = AsyncMock()
            mock_get_db.return_value = mock_db

            with patch(
                "session_mgmt_mcp.server.MemoryOptimizer",
            ) as mock_optimizer_class:
                mock_optimizer = AsyncMock()
                mock_optimizer.compress_memory.return_value = mock_optimization_results
                mock_optimizer_class.return_value = mock_optimizer

                result = await optimize_memory_usage(
                    strategy="aggressive",
                    max_age_days=15,
                    dry_run=False,
                )

                # Verify aggressive policy was set
                mock_optimizer.compress_memory.assert_called_once()
                call_args = mock_optimizer.compress_memory.call_args
                policy = call_args.kwargs["policy"]
                assert policy["consolidation_age_days"] == 15
                assert policy["importance_threshold"] == 0.3  # Aggressive threshold

                assert "🧠 Memory Optimization Results" in result
                assert "(DRY RUN)" not in result  # Not in dry run

    @pytest.mark.asyncio
    async def test_optimize_memory_usage_dependencies_unavailable(self):
        """Test memory optimization when dependencies unavailable."""
        with patch("session_mgmt_mcp.server.TOKEN_OPTIMIZER_AVAILABLE", False):
            result = await optimize_memory_usage()

            assert (
                "❌ Memory optimization requires both token optimizer and reflection tools"
                in result
            )

        with (
            patch("session_mgmt_mcp.server.TOKEN_OPTIMIZER_AVAILABLE", True),
            patch("session_mgmt_mcp.server.REFLECTION_TOOLS_AVAILABLE", False),
        ):
            result = await optimize_memory_usage()

            assert (
                "❌ Memory optimization requires both token optimizer and reflection tools"
                in result
            )

    @pytest.mark.asyncio
    async def test_optimize_memory_usage_error_handling(self):
        """Test error handling in memory optimization."""
        with (
            patch("session_mgmt_mcp.server.TOKEN_OPTIMIZER_AVAILABLE", True),
            patch("session_mgmt_mcp.server.REFLECTION_TOOLS_AVAILABLE", True),
            patch("session_mgmt_mcp.server.get_reflection_database") as mock_get_db,
        ):
            mock_get_db.side_effect = Exception("Database error")

            result = await optimize_memory_usage()

            assert "❌ Error optimizing memory" in result

    @pytest.mark.asyncio
    async def test_optimize_memory_usage_optimization_error(self):
        """Test handling of optimization errors."""
        mock_error_results = {"error": "Database not available"}

        with (
            patch("session_mgmt_mcp.server.TOKEN_OPTIMIZER_AVAILABLE", True),
            patch("session_mgmt_mcp.server.REFLECTION_TOOLS_AVAILABLE", True),
            patch("session_mgmt_mcp.server.get_reflection_database") as mock_get_db,
        ):
            mock_db = AsyncMock()
            mock_get_db.return_value = mock_db

            with patch(
                "session_mgmt_mcp.server.MemoryOptimizer",
            ) as mock_optimizer_class:
                mock_optimizer = AsyncMock()
                mock_optimizer.compress_memory.return_value = mock_error_results
                mock_optimizer_class.return_value = mock_optimizer

                result = await optimize_memory_usage()

                assert "❌ Memory optimization error: Database not available" in result


class TestOptimizationIntegration:
    """Test integration of token optimization across multiple tools."""

    @pytest.mark.asyncio
    async def test_end_to_end_optimization_workflow(self, mock_reflection_db):
        """Test complete optimization workflow."""
        # Step 1: Search with optimization
        with (
            patch("session_mgmt_mcp.server.get_reflection_database") as mock_get_db,
            patch("session_mgmt_mcp.server.TOKEN_OPTIMIZER_AVAILABLE", True),
            patch("session_mgmt_mcp.server.REFLECTION_TOOLS_AVAILABLE", True),
            patch("session_mgmt_mcp.server.optimize_search_response") as mock_optimize,
            patch("session_mgmt_mcp.server.track_token_usage") as mock_track,
        ):
            mock_get_db.return_value = mock_reflection_db

            # Mock chunking result
            mock_optimize.return_value = (
                mock_reflection_db.search_conversations.return_value[:1],  # First chunk
                {
                    "strategy": "chunk_response",
                    "action": "chunked",
                    "total_chunks": 3,
                    "current_chunk": 1,
                    "cache_key": "test_cache_key",
                    "has_more": True,
                    "token_savings": {"tokens_saved": 200, "savings_percentage": 40},
                },
            )

            # Step 1: Search with chunking
            search_result = await reflect_on_past(
                query="Python functions",
                optimize_tokens=True,
                max_tokens=100,  # Force chunking
            )

            assert "⚡ Token optimization: 40% saved" in search_result
            mock_track.assert_called()

            # Step 2: Retrieve additional chunks
            with patch("session_mgmt_mcp.server.get_cached_chunk") as mock_get_chunk:
                mock_chunk_data = {
                    "chunk": [mock_reflection_db.search_conversations.return_value[1]],
                    "current_chunk": 2,
                    "total_chunks": 3,
                    "cache_key": "test_cache_key",
                    "has_more": True,
                }
                mock_get_chunk.return_value = mock_chunk_data

                chunk_result = await get_cached_chunk("test_cache_key", 2)
                assert "📄 Chunk 2 of 3" in chunk_result
                assert "More chunks available" in chunk_result

    @pytest.mark.asyncio
    async def test_optimization_fallback_behavior(self, mock_reflection_db):
        """Test fallback behavior when optimization fails."""
        with (
            patch("session_mgmt_mcp.server.get_reflection_database") as mock_get_db,
            patch("session_mgmt_mcp.server.TOKEN_OPTIMIZER_AVAILABLE", True),
            patch("session_mgmt_mcp.server.REFLECTION_TOOLS_AVAILABLE", True),
            patch("session_mgmt_mcp.server.optimize_search_response") as mock_optimize,
        ):
            mock_get_db.return_value = mock_reflection_db
            mock_optimize.side_effect = Exception("Optimization failed")

            # Should fall back to unoptimized results
            result = await reflect_on_past(
                query="Python functions",
                optimize_tokens=True,
            )

            # Should still show results, just without optimization
            assert "Found 3 relevant conversations" in result
            assert "⚡ Token optimization" not in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
