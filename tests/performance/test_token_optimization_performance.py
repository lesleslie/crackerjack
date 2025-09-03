#!/usr/bin/env python3
"""Performance tests for token optimization."""

import asyncio
import time
from datetime import datetime, timedelta

import pytest
from session_mgmt_mcp.token_optimizer import TokenOptimizer, optimize_search_response


@pytest.fixture
def large_conversations_dataset():
    """Create a large dataset for performance testing."""
    conversations = []
    base_time = datetime.now()

    # Create different types of conversations
    content_templates = [
        "This is a short conversation about Python functions. def hello(): return 'world'",
        "This is a medium conversation discussing various aspects of software development including testing strategies and API design. "
        * 5,
        "This is a very long conversation that covers many topics in software engineering including database design, scalability patterns, microservices architecture, and deployment strategies. "
        * 15,
        "Error troubleshooting conversation with traceback. TypeError: object is not callable. Here's the full stack trace and debugging process...",
        "Code review discussion with multiple suggestions for improvements and architectural considerations for the project.",
    ]

    for i in range(1000):  # Large dataset
        template_idx = i % len(content_templates)
        conversations.append(
            {
                "id": f"conv_{i}",
                "content": content_templates[template_idx] + f" Conversation #{i}",
                "timestamp": (base_time - timedelta(minutes=i)).isoformat(),
                "project": f"project_{i % 10}",  # 10 different projects
                "score": 0.5 + (i % 50) / 100,  # Scores from 0.5 to 0.99
            },
        )

    return conversations


class TestTokenOptimizerPerformance:
    """Performance tests for TokenOptimizer class."""

    def test_token_counting_performance(self):
        """Test token counting performance with various text sizes."""
        optimizer = TokenOptimizer()

        # Test different text sizes
        text_sizes = [100, 1000, 10000, 50000]  # characters

        for size in text_sizes:
            text = "a" * size

            start_time = time.time()
            token_count = optimizer.count_tokens(text)
            end_time = time.time()

            duration = end_time - start_time

            # Should be fast even for large texts
            assert duration < 0.1, (
                f"Token counting too slow for {size} chars: {duration:.3f}s"
            )
            assert token_count > 0

    def test_truncation_strategy_performance(self, large_conversations_dataset):
        """Test performance of truncation strategy with large dataset."""
        optimizer = TokenOptimizer()

        start_time = time.time()
        optimized, info = optimizer._truncate_old_conversations(
            large_conversations_dataset,
            max_tokens=5000,
        )
        end_time = time.time()

        duration = end_time - start_time

        # Should complete within reasonable time
        assert duration < 2.0, f"Truncation strategy too slow: {duration:.3f}s"
        assert len(optimized) <= len(large_conversations_dataset)
        assert info["strategy"] == "truncate_old"

    def test_summarization_strategy_performance(self, large_conversations_dataset):
        """Test performance of summarization strategy."""
        optimizer = TokenOptimizer()

        # Use smaller subset for summarization due to processing overhead
        subset = large_conversations_dataset[:100]

        start_time = time.time()
        optimized, info = optimizer._summarize_long_content(subset, max_tokens=10000)
        end_time = time.time()

        duration = end_time - start_time

        # Summarization can be slower but should still be reasonable
        assert duration < 5.0, f"Summarization strategy too slow: {duration:.3f}s"
        assert len(optimized) == len(subset)
        assert info["strategy"] == "summarize_content"

    def test_prioritization_strategy_performance(self, large_conversations_dataset):
        """Test performance of prioritization strategy."""
        optimizer = TokenOptimizer()

        start_time = time.time()
        optimized, info = optimizer._prioritize_recent_content(
            large_conversations_dataset,
            max_tokens=3000,
        )
        end_time = time.time()

        duration = end_time - start_time

        # Should be reasonably fast for sorting and scoring
        assert duration < 1.0, f"Prioritization strategy too slow: {duration:.3f}s"
        assert len(optimized) <= len(large_conversations_dataset)
        assert info["strategy"] == "prioritize_recent"

    def test_deduplication_performance(self):
        """Test performance of deduplication with many similar conversations."""
        optimizer = TokenOptimizer()

        # Create conversations with many duplicates
        conversations = []
        base_content = "This is a duplicate conversation about Python"

        for i in range(500):
            conversations.append(
                {
                    "id": f"conv_{i}",
                    "content": base_content
                    + f" variation {i % 10}",  # Only 10 unique variations
                    "timestamp": datetime.now().isoformat(),
                },
            )

        start_time = time.time()
        optimized, info = optimizer._filter_duplicate_content(
            conversations,
            max_tokens=10000,
        )
        end_time = time.time()

        duration = end_time - start_time

        assert duration < 1.0, f"Deduplication too slow: {duration:.3f}s"
        assert len(optimized) < len(conversations)  # Should remove duplicates
        assert info["duplicates_removed"] > 0

    def test_chunking_performance(self, large_conversations_dataset):
        """Test performance of response chunking."""
        optimizer = TokenOptimizer(chunk_size=1000)

        start_time = time.time()
        optimized, info = optimizer._chunk_large_response(
            large_conversations_dataset,
            max_tokens=2000,
        )
        end_time = time.time()

        duration = end_time - start_time

        assert duration < 2.0, f"Chunking too slow: {duration:.3f}s"

        if info["action"] == "chunked":
            assert info["total_chunks"] > 1
            assert "cache_key" in info

    @pytest.mark.asyncio
    async def test_async_optimization_performance(self, large_conversations_dataset):
        """Test performance of async optimization wrapper."""
        start_time = time.time()
        optimized, info = await optimize_search_response(
            large_conversations_dataset[:200],  # Moderate size for async test
            strategy="prioritize_recent",
            max_tokens=2000,
        )
        end_time = time.time()

        duration = end_time - start_time

        assert duration < 1.0, f"Async optimization too slow: {duration:.3f}s"
        assert isinstance(optimized, list)
        assert isinstance(info, dict)


class TestCachePerformance:
    """Test performance of caching mechanisms."""

    def test_chunk_cache_creation_performance(self):
        """Test performance of chunk cache creation."""
        optimizer = TokenOptimizer()

        # Create large chunks
        large_chunks = []
        for i in range(10):
            chunk = []
            for j in range(50):  # 50 conversations per chunk
                chunk.append(
                    {
                        "id": f"conv_{i}_{j}",
                        "content": f"This is conversation {j} in chunk {i}. " * 20,
                        "timestamp": datetime.now().isoformat(),
                    },
                )
            large_chunks.append(chunk)

        start_time = time.time()
        cache_key = optimizer._create_chunk_cache_entry(large_chunks)
        end_time = time.time()

        duration = end_time - start_time

        assert duration < 1.0, f"Cache creation too slow: {duration:.3f}s"
        assert cache_key in optimizer.chunk_cache

        # Test retrieval performance
        start_time = time.time()
        chunk_data = optimizer.get_chunk(cache_key, 1)
        end_time = time.time()

        retrieval_duration = end_time - start_time

        assert retrieval_duration < 0.1, (
            f"Cache retrieval too slow: {retrieval_duration:.3f}s"
        )
        assert chunk_data is not None

    def test_cache_cleanup_performance(self):
        """Test performance of cache cleanup."""
        optimizer = TokenOptimizer()

        # Create many cache entries
        for i in range(100):
            cache_key = f"key_{i}"

            # Create entries with different expiration times
            from session_mgmt_mcp.token_optimizer import ChunkResult

            chunk_result = ChunkResult(
                chunks=[f"chunk_{i}"],
                total_chunks=1,
                current_chunk=1,
                cache_key=cache_key,
                metadata={
                    "created": datetime.now().isoformat(),
                    "expires": (
                        datetime.now() - timedelta(minutes=i)
                    ).isoformat(),  # Varying expiration
                },
            )
            optimizer.chunk_cache[cache_key] = chunk_result

        start_time = time.time()
        cleaned_count = optimizer.cleanup_cache(max_age_hours=1)
        end_time = time.time()

        duration = end_time - start_time

        assert duration < 0.5, f"Cache cleanup too slow: {duration:.3f}s"
        assert cleaned_count > 0


class TestMemoryUsageOptimization:
    """Test memory usage during optimization operations."""

    def test_memory_efficiency_large_dataset(self, large_conversations_dataset):
        """Test memory usage doesn't grow excessively with large datasets."""
        optimizer = TokenOptimizer()

        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Process large dataset multiple times
        for strategy in ["truncate_old", "prioritize_recent", "filter_duplicates"]:
            strategy_func = optimizer.strategies[strategy]
            optimized, info = strategy_func(
                large_conversations_dataset,
                max_tokens=3000,
            )

            current_memory = process.memory_info().rss / 1024 / 1024  # MB
            memory_increase = current_memory - initial_memory

            # Memory increase should be reasonable (less than 50MB for this dataset)
            assert memory_increase < 50, (
                f"Memory usage too high for {strategy}: {memory_increase:.1f}MB"
            )

    def test_token_counting_memory_efficiency(self):
        """Test memory efficiency of token counting."""
        optimizer = TokenOptimizer()

        import os

        import psutil

        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Count tokens for many large texts
        large_text = "This is a large text for token counting. " * 1000

        for i in range(100):
            token_count = optimizer.count_tokens(large_text + f" iteration {i}")
            assert token_count > 0

        final_memory = process.memory_info().rss / 1024 / 1024  # MB
        memory_increase = final_memory - initial_memory

        # Memory increase should be minimal
        assert memory_increase < 10, (
            f"Token counting memory inefficient: {memory_increase:.1f}MB"
        )


class TestScalabilityBenchmarks:
    """Benchmark tests for different dataset sizes."""

    @pytest.mark.parametrize("dataset_size", [100, 500, 1000, 2000])
    def test_optimization_scalability(self, dataset_size):
        """Test how optimization performance scales with dataset size."""
        optimizer = TokenOptimizer()

        # Create dataset of specified size
        conversations = []
        for i in range(dataset_size):
            conversations.append(
                {
                    "id": f"conv_{i}",
                    "content": f"This is conversation {i} with some content. " * 10,
                    "timestamp": (datetime.now() - timedelta(minutes=i)).isoformat(),
                    "project": "test",
                },
            )

        # Test truncation strategy scaling
        start_time = time.time()
        optimized, info = optimizer._truncate_old_conversations(
            conversations,
            max_tokens=2000,
        )
        duration = time.time() - start_time

        # Performance should scale reasonably (not exponentially)
        max_expected_time = dataset_size * 0.005  # 5ms per conversation maximum
        assert duration < max_expected_time, (
            f"Poor scaling for {dataset_size} items: {duration:.3f}s"
        )

    def test_concurrent_optimization_performance(self, large_conversations_dataset):
        """Test performance under concurrent optimization requests."""

        async def optimize_batch(batch_id, conversations):
            """Optimize a batch of conversations."""
            start_time = time.time()
            result, info = await optimize_search_response(
                conversations,
                strategy="prioritize_recent",
                max_tokens=1000,
            )
            duration = time.time() - start_time
            return batch_id, duration, len(result)

        async def run_concurrent_test():
            # Split large dataset into smaller batches
            batch_size = 50
            batches = [
                large_conversations_dataset[i : i + batch_size]
                for i in range(0, len(large_conversations_dataset), batch_size)
            ][:10]  # Test with 10 batches

            # Run optimizations concurrently
            tasks = [optimize_batch(i, batch) for i, batch in enumerate(batches)]

            start_time = time.time()
            results = await asyncio.gather(*tasks)
            total_duration = time.time() - start_time

            return results, total_duration

        results, total_duration = asyncio.run(run_concurrent_test())

        # Should complete concurrent operations efficiently
        assert total_duration < 5.0, (
            f"Concurrent optimization too slow: {total_duration:.3f}s"
        )
        assert len(results) == 10

        # Check individual batch performance
        for batch_id, duration, result_count in results:
            assert duration < 2.0, f"Batch {batch_id} too slow: {duration:.3f}s"
            assert result_count > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--benchmark-only"])
