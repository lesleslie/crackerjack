#!/usr/bin/env python3
"""Unit tests for token optimization functionality."""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from session_mgmt_mcp.token_optimizer import (
    ChunkResult,
    TokenOptimizer,
    TokenUsageMetrics,
    get_cached_chunk,
    get_token_usage_stats,
    optimize_search_response,
    track_token_usage,
)


@pytest.fixture
def token_optimizer():
    """Create a token optimizer instance for testing."""
    return TokenOptimizer(max_tokens=1000, chunk_size=500)


@pytest.fixture
def sample_conversations():
    """Sample conversation data for testing."""
    base_time = datetime.now() - timedelta(days=1)
    return [
        {
            "id": "conv1",
            "content": 'This is a short conversation about Python functions. def hello(): return "world"',
            "timestamp": base_time.isoformat(),
            "project": "test-project",
            "score": 0.8,
        },
        {
            "id": "conv2",
            "content": "This is a much longer conversation that discusses various aspects of software development, including database design, API architecture, testing strategies, and deployment practices. "
            * 20,
            "timestamp": (base_time - timedelta(hours=2)).isoformat(),
            "project": "test-project",
            "score": 0.6,
        },
        {
            "id": "conv3",
            "content": "Recent conversation with error troubleshooting. TypeError: object is not callable. Here is the traceback...",
            "timestamp": (base_time + timedelta(hours=1)).isoformat(),
            "project": "test-project",
            "score": 0.9,
        },
        {
            "id": "conv4",
            "content": "Old conversation from last month about basic concepts",
            "timestamp": (base_time - timedelta(days=30)).isoformat(),
            "project": "old-project",
            "score": 0.4,
        },
    ]


class TestTokenOptimizer:
    """Test the core TokenOptimizer class."""

    def test_token_counting_with_tiktoken(self, token_optimizer):
        """Test token counting when tiktoken is available."""
        text = "Hello world, this is a test message"
        token_count = token_optimizer.count_tokens(text)
        assert isinstance(token_count, int)
        assert token_count > 0

    def test_token_counting_fallback(self, token_optimizer):
        """Test token counting fallback when tiktoken fails."""
        with patch.object(token_optimizer, "encoding", None):
            text = "Hello world, this is a test message"
            token_count = token_optimizer.count_tokens(text)
            assert isinstance(token_count, int)
            assert token_count > 0
            # Should be roughly len(text) // 4
            assert token_count == len(text) // 4

    def test_truncate_old_conversations(self, token_optimizer, sample_conversations):
        """Test truncating old conversations strategy."""
        optimized, info = token_optimizer._truncate_old_conversations(
            sample_conversations,
            max_tokens=200,
        )

        assert len(optimized) <= len(sample_conversations)
        assert info["strategy"] == "truncate_old"
        assert info["action"] in ["truncated", "no_truncation_needed"]
        assert "final_token_count" in info

        # Should prioritize recent conversations
        if len(optimized) > 0:
            # Most recent should be first (conv3)
            assert optimized[0]["id"] == "conv3"

    def test_summarize_long_content(self, token_optimizer, sample_conversations):
        """Test content summarization strategy."""
        optimized, info = token_optimizer._summarize_long_content(
            sample_conversations,
            max_tokens=1000,
        )

        assert len(optimized) == len(sample_conversations)
        assert info["strategy"] == "summarize_content"

        # Check if long content was summarized
        long_conv = next(conv for conv in optimized if conv["id"] == "conv2")
        assert "[auto-summarized]" in long_conv["content"]
        assert len(long_conv["content"]) < len(sample_conversations[1]["content"])

    def test_filter_duplicate_content(self, token_optimizer):
        """Test duplicate content filtering."""
        duplicate_conversations = [
            {
                "id": "conv1",
                "content": "This is a test message",
                "timestamp": datetime.now().isoformat(),
            },
            {
                "id": "conv2",
                "content": "This is a test message",  # Exact duplicate
                "timestamp": datetime.now().isoformat(),
            },
            {
                "id": "conv3",
                "content": "This  is  a   test   message",  # Same after normalization
                "timestamp": datetime.now().isoformat(),
            },
            {
                "id": "conv4",
                "content": "This is a different message",
                "timestamp": datetime.now().isoformat(),
            },
        ]

        optimized, info = token_optimizer._filter_duplicate_content(
            duplicate_conversations,
            max_tokens=1000,
        )

        assert len(optimized) == 2  # Should keep only 2 unique messages
        assert info["strategy"] == "filter_duplicates"
        assert info["duplicates_removed"] == 2

    def test_prioritize_recent_content(self, token_optimizer, sample_conversations):
        """Test recent content prioritization strategy."""
        optimized, info = token_optimizer._prioritize_recent_content(
            sample_conversations,
            max_tokens=300,
        )

        assert len(optimized) <= len(sample_conversations)
        assert info["strategy"] == "prioritize_recent"

        # Should prioritize recent and high-scoring conversations
        if len(optimized) > 0:
            # Check that conv3 (recent, high score, has error) is included
            recent_ids = [conv["id"] for conv in optimized]
            assert "conv3" in recent_ids

    def test_chunk_large_response(self, token_optimizer):
        """Test response chunking strategy."""
        # Create large conversation set that exceeds max_tokens
        large_conversations = []
        for i in range(10):
            large_conversations.append(
                {
                    "id": f"conv{i}",
                    "content": "This is a long conversation that contains lots of text. "
                    * 20,
                    "timestamp": datetime.now().isoformat(),
                },
            )

        optimized, info = token_optimizer._chunk_large_response(
            large_conversations,
            max_tokens=500,
        )

        if info["action"] == "chunked":
            assert len(optimized) < len(
                large_conversations,
            )  # Should return first chunk
            assert info["total_chunks"] > 1
            assert info["current_chunk"] == 1
            assert "cache_key" in info
            assert info["has_more"] is True

        # Test cache creation
        if "cache_key" in info:
            cache_key = info["cache_key"]
            assert cache_key in token_optimizer.chunk_cache

    def test_create_quick_summary(self, token_optimizer):
        """Test quick summary creation."""
        long_text = (
            "This is the first sentence of a long document. "
            "Here are many sentences in between that contain various details. "
            * 5
            + "This is the final sentence that concludes everything."
        )

        summary = token_optimizer._create_quick_summary(long_text, max_length=100)

        assert len(summary) <= 100
        assert summary.startswith("This is the first sentence")
        # Should include last sentence or be truncated
        assert "..." in summary or "concludes" in summary

    def test_truncate_content(self, token_optimizer):
        """Test content truncation."""
        long_content = "This is a sentence. This is another sentence. " * 10
        max_tokens = 20

        truncated = token_optimizer._truncate_content(long_content, max_tokens)

        assert len(truncated) < len(long_content)
        assert token_optimizer.count_tokens(truncated) <= max_tokens

        # Should try to preserve sentence boundaries
        if ". " in long_content and ". " in truncated:
            assert truncated.endswith((". ", "."))

    def test_chunk_cache_operations(self, token_optimizer):
        """Test chunk caching and retrieval."""
        # Create some test chunks
        chunks = [
            [{"id": "conv1", "content": "Chunk 1 content"}],
            [{"id": "conv2", "content": "Chunk 2 content"}],
            [{"id": "conv3", "content": "Chunk 3 content"}],
        ]

        cache_key = token_optimizer._create_chunk_cache_entry(chunks)

        # Test retrieving valid chunk
        chunk_data = token_optimizer.get_chunk(cache_key, 1)
        assert chunk_data is not None
        assert chunk_data["current_chunk"] == 1
        assert chunk_data["total_chunks"] == 3
        assert chunk_data["has_more"] is True

        # Test retrieving last chunk
        chunk_data = token_optimizer.get_chunk(cache_key, 3)
        assert chunk_data is not None
        assert chunk_data["has_more"] is False

        # Test invalid chunk index
        chunk_data = token_optimizer.get_chunk(cache_key, 5)
        assert chunk_data is None

        # Test invalid cache key
        chunk_data = token_optimizer.get_chunk("invalid_key", 1)
        assert chunk_data is None

    def test_token_savings_calculation(self, token_optimizer, sample_conversations):
        """Test token savings calculation."""
        # Create optimized version with fewer conversations
        optimized = sample_conversations[:2]

        savings = token_optimizer._calculate_token_savings(
            sample_conversations,
            optimized,
        )

        assert "original_tokens" in savings
        assert "optimized_tokens" in savings
        assert "tokens_saved" in savings
        assert "savings_percentage" in savings

        assert savings["original_tokens"] >= savings["optimized_tokens"]
        assert savings["tokens_saved"] >= 0
        assert 0 <= savings["savings_percentage"] <= 100

    def test_usage_tracking(self, token_optimizer):
        """Test token usage tracking."""
        # Track some usage
        token_optimizer.track_usage("test_operation", 100, 200, "truncate_old")
        token_optimizer.track_usage("another_operation", 150, 250)

        assert len(token_optimizer.usage_history) == 2

        latest_metric = token_optimizer.usage_history[-1]
        assert latest_metric.operation == "another_operation"
        assert latest_metric.request_tokens == 150
        assert latest_metric.response_tokens == 250
        assert latest_metric.total_tokens == 400
        assert latest_metric.optimization_applied is None

    def test_usage_stats(self, token_optimizer):
        """Test usage statistics generation."""
        # Add some test usage data
        now = datetime.now()

        # Add metrics with different timestamps
        token_optimizer.usage_history = [
            TokenUsageMetrics(
                100,
                200,
                300,
                (now - timedelta(hours=1)).isoformat(),
                "op1",
                "truncate_old",
            ),
            TokenUsageMetrics(150, 250, 400, now.isoformat(), "op2", None),
            TokenUsageMetrics(
                80,
                120,
                200,
                (now - timedelta(days=2)).isoformat(),
                "op3",
                "summarize",
            ),
        ]

        stats = token_optimizer.get_usage_stats(hours=24)

        assert stats["status"] == "success"
        assert stats["total_requests"] == 2  # Only last 24 hours
        assert stats["total_tokens"] == 700  # 300 + 400
        assert stats["average_tokens_per_request"] == 350.0

        # Check optimizations tracking
        assert "truncate_old" in stats["optimizations_applied"]
        assert stats["optimizations_applied"]["truncate_old"] == 1

    def test_cache_cleanup(self, token_optimizer):
        """Test cache cleanup of expired entries."""
        # Create some cache entries with different expiration times
        now = datetime.now()

        # Create expired entry
        expired_chunks = ChunkResult(
            chunks=["chunk1"],
            total_chunks=1,
            current_chunk=1,
            cache_key="expired_key",
            metadata={
                "created": (now - timedelta(hours=2)).isoformat(),
                "expires": (now - timedelta(hours=1)).isoformat(),
            },
        )
        token_optimizer.chunk_cache["expired_key"] = expired_chunks

        # Create valid entry
        valid_chunks = ChunkResult(
            chunks=["chunk2"],
            total_chunks=1,
            current_chunk=1,
            cache_key="valid_key",
            metadata={
                "created": now.isoformat(),
                "expires": (now + timedelta(hours=1)).isoformat(),
            },
        )
        token_optimizer.chunk_cache["valid_key"] = valid_chunks

        # Run cleanup
        cleaned_count = token_optimizer.cleanup_cache(max_age_hours=1)

        assert cleaned_count == 1
        assert "expired_key" not in token_optimizer.chunk_cache
        assert "valid_key" in token_optimizer.chunk_cache


class TestAsyncWrappers:
    """Test async wrapper functions."""

    @pytest.mark.asyncio
    async def test_optimize_search_response(self, sample_conversations):
        """Test async search response optimization."""
        result, info = await optimize_search_response(
            sample_conversations,
            strategy="prioritize_recent",
            max_tokens=500,
        )

        assert isinstance(result, list)
        assert isinstance(info, dict)
        assert "strategy" in info

    @pytest.mark.asyncio
    async def test_track_token_usage(self):
        """Test async usage tracking."""
        # Should not raise any exceptions
        await track_token_usage("test_op", 100, 200, "test_strategy")

    @pytest.mark.asyncio
    async def test_get_token_usage_stats(self):
        """Test async usage stats retrieval."""
        stats = await get_token_usage_stats(hours=24)
        assert isinstance(stats, dict)
        assert "status" in stats

    @pytest.mark.asyncio
    async def test_get_cached_chunk_async(self):
        """Test async chunk retrieval."""
        # Test with invalid cache key
        result = await get_cached_chunk("invalid_key", 1)
        assert result is None


class TestOptimizationStrategies:
    """Test different optimization strategies with various scenarios."""

    def test_empty_conversations_list(self, token_optimizer):
        """Test optimization strategies with empty input."""
        empty_list = []

        for strategy_name, strategy_func in token_optimizer.strategies.items():
            result, info = strategy_func(empty_list, 1000)
            assert result == empty_list
            assert info["strategy"] == strategy_name

    def test_single_conversation(self, token_optimizer):
        """Test optimization strategies with single conversation."""
        single_conv = [
            {
                "id": "conv1",
                "content": "Single conversation content",
                "timestamp": datetime.now().isoformat(),
                "project": "test",
            },
        ]

        result, info = token_optimizer._truncate_old_conversations(single_conv, 1000)
        assert len(result) == 1
        assert result[0]["id"] == "conv1"

    def test_large_token_limit(self, token_optimizer, sample_conversations):
        """Test optimization with very large token limit."""
        result, info = token_optimizer._truncate_old_conversations(
            sample_conversations,
            max_tokens=10000,
        )

        # Should keep all conversations
        assert len(result) == len(sample_conversations)

    def test_very_small_token_limit(self, token_optimizer, sample_conversations):
        """Test optimization with very small token limit."""
        result, info = token_optimizer._truncate_old_conversations(
            sample_conversations,
            max_tokens=10,
        )

        # Should keep at least some conversations, but heavily truncated
        assert len(result) > 0
        assert info["final_token_count"] <= 10


class TestTokenUsageMetrics:
    """Test TokenUsageMetrics dataclass."""

    def test_token_usage_metrics_creation(self):
        """Test creating TokenUsageMetrics."""
        metrics = TokenUsageMetrics(
            request_tokens=100,
            response_tokens=200,
            total_tokens=300,
            timestamp="2023-01-01T00:00:00",
            operation="test_op",
            optimization_applied="test_optimization",
        )

        assert metrics.request_tokens == 100
        assert metrics.response_tokens == 200
        assert metrics.total_tokens == 300
        assert metrics.operation == "test_op"
        assert metrics.optimization_applied == "test_optimization"


class TestChunkResult:
    """Test ChunkResult dataclass."""

    def test_chunk_result_creation(self):
        """Test creating ChunkResult."""
        chunks = ["chunk1", "chunk2"]
        metadata = {"test": "data"}

        chunk_result = ChunkResult(
            chunks=chunks,
            total_chunks=2,
            current_chunk=1,
            cache_key="test_key",
            metadata=metadata,
        )

        assert chunk_result.chunks == chunks
        assert chunk_result.total_chunks == 2
        assert chunk_result.current_chunk == 1
        assert chunk_result.cache_key == "test_key"
        assert chunk_result.metadata == metadata


class TestErrorHandling:
    """Test error handling in token optimization."""

    def test_invalid_timestamp_handling(self, token_optimizer):
        """Test handling of invalid timestamps."""
        conversations_with_bad_timestamps = [
            {
                "id": "conv1",
                "content": "Content with bad timestamp",
                "timestamp": "invalid_timestamp",
                "project": "test",
            },
            {
                "id": "conv2",
                "content": "Content with no timestamp",
                "project": "test",
                # Missing timestamp key
            },
        ]

        # Should not crash and should handle gracefully
        result, info = token_optimizer._prioritize_recent_content(
            conversations_with_bad_timestamps,
            max_tokens=1000,
        )

        assert len(result) == len(conversations_with_bad_timestamps)
        assert info["strategy"] == "prioritize_recent"

    def test_missing_content_handling(self, token_optimizer):
        """Test handling of conversations with missing content."""
        conversations_with_missing_content = [
            {
                "id": "conv1",
                "timestamp": datetime.now().isoformat(),
                "project": "test",
                # Missing content key
            },
            {
                "id": "conv2",
                "content": "",  # Empty content
                "timestamp": datetime.now().isoformat(),
                "project": "test",
            },
        ]

        # Should not crash
        result, info = token_optimizer._summarize_long_content(
            conversations_with_missing_content,
            max_tokens=1000,
        )

        assert len(result) == len(conversations_with_missing_content)
        assert info["strategy"] == "summarize_content"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
